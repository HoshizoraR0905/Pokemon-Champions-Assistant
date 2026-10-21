"""Freeze message-only arrivals, then compare separate saved HUD evidence offline.

No image decoding, OCR, icon recognition, roster lookup or HUD-assisted repair.
The two phases have separate files and input hashes. Production remains untouched.
"""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from battle_artifacts import BattleArtifacts
from battle_events.parser import EventParser
from recognition.event_schedule import ordered_entries
from recognition.fast_video import digest
from recognition.video_sampling import atomic_json
from tracking.battle_state import BattleState
from tracking.state_engine import StateEngine, EventRecord, event_from_dict, ordering
from tracking.evidence_fusion import identity_evidence


def read(path):
    return json.loads(path.read_text())


def literal_prediction(event, parser, names_resolver=None):
    attrs = event['attributes']
    names = ordered_entries(event['original_text'])
    literal = attrs.get('display_reference') or (names[0] if len(names) == 1 else '')
    match = names_resolver.resolve(literal) if names_resolver and literal else {}
    ref = match.get('identity') if names_resolver else parser.identity(literal, 'species') if literal else None
    confidence = event.get('ocr_confidence') or 0
    complete = bool(literal and event['original_text'].rstrip().endswith(('！', '!')))
    # The original literal is retained even when it is readable but unmapped.
    supported = complete and confidence >= .95
    return dict(event_id=event['event_id'], timestamp=attrs['observation_time'],
                literal=literal, text=event['original_text'], side=event['side'],
                slot=attrs.get('slot'), evidence=deepcopy(event['evidence']),
                ocr_confidence=confidence, complete_readable_candidate=supported,
                identity=ref if supported else None,
                title_match=match if supported else None,
                reason=match.get('reason', 'exact_canonical_name') if supported and ref else
                       'unmapped_complete_display_reference' if supported else 'incomplete_or_low_confidence',
                form_unknown=not bool(supported and ref and ref.get('canonical_identity')))


def freeze(owner, run_id, target, names_resolver=None):
    source = owner.cache('event-driven/' + run_id)
    identity = dict(video_only_sha256=digest(source/'video-only.json'), evaluator_sha256=digest(Path(__file__)))
    if names_resolver:
        identity['title_vocabulary'] = names_resolver.data
    path = target/'message-predictions.json'
    if path.exists():
        saved = read(path)
        assert saved['inputs'] == identity, 'Preserve frozen predictions; select a new evaluation ID'
        return saved
    parser = EventParser()
    # Existing occupancy/episode engine sees message and trainer observations only.
    # Remove every HUD, checkpoint, roster, banner and detail input before replay.
    events = [deepcopy(e) for e in read(source/'video-only.json')['events']
              if e['event_type'] in {'trainer_observation', 'entry_observation'} or
              e['attributes'].get('source_region_type') == 'battle_message']
    predictions = {}
    for e in events:
        if e['event_type'] == 'send_out':
            p = literal_prediction(e, parser, names_resolver)
            predictions[e['event_id']] = p
            e['actor'] = deepcopy(p['identity'])
            e['attributes'].pop('display_alias_evidence', None)
            if e['actor'] is None and 'actor_unresolved' not in e['uncertainty']:
                e['uncertainty'].append('actor_unresolved')
    engine = StateEngine(BattleState(owner.battle_id, knowledge=dict(
        reliability_v1=True, reliability_v2=True, identity_v1=True,
        active_continuity_v1=True, active_persistence_v1=True)))
    engine.history = [EventRecord(e, i, ordering(event_from_dict(e))) for i, e in enumerate(events, 1)]
    def capture(record, state):
        p = predictions.get(record.event['event_id'])
        if p is None:
            return
        ep = record.bindings.get('entry_episode') or {}
        resolved = record.bindings.get('resolved_event') or record.event
        p.update(raw_side=p['side'], side=ep.get('side') or resolved['side'],
                 side_resolution='message-only prefix replay; HUD/checkpoints/rosters excluded',
                 slot=p['slot'] or ep.get('slot'), episode_id=ep.get('episode_id'),
                 message_application_status=record.application_status, message_application_reason=record.reason)
    engine.replay(snapshot_callback=capture)
    episodes = engine.state.knowledge.get('active_entry_episodes', [])
    for p in predictions.values():
        ep = next((e for e in episodes if e['episode_id'] == p['episode_id']), {})
        p['departure'] = (ep.get('departure') or {}).get('timestamp')
    result = dict(inputs=identity, hud_consulted=False, roster_consulted=False,
                  knowledge_snapshot=parser.kb.snapshot_id, identity_scope=parser.kb.identities.scope_id,
                  predictions=list(predictions.values()))
    atomic_json(path, result)
    return result


def compare(predictions, hud_events):
    """First accepted fresh HUD per message-only slot episode; never species join."""
    rows = []
    for p in predictions:
        row = deepcopy(p)
        end = p.get('departure')
        later = [x['timestamp'] for x in predictions if x['side'] == p['side'] and
                 x['slot'] == p['slot'] and x['timestamp'] > p['timestamp']]
        if later:
            end = min([*later, *([end] if end is not None else [])])
        previous = None
        attempts = []
        confirmation = None
        for e in hud_events:
            a = e['attributes']; t = a['observation_time']
            if (not p['slot'] or e['side'] != p['side'] or a['slot'] != p['slot'] or
                    t <= p['timestamp'] or end is not None and t >= end or a.get('identity_reused_from')):
                continue
            species = a.get('species') or {}; icon = a.get('icon') or {}
            ref, status, reason = identity_evidence(species, icon, previous, reliability=True)
            attempts.append(dict(event_id=e['event_id'], timestamp=t, status=status, reason=reason))
            previous = dict(raw=species.get('raw_text'), species_id=(species.get('resolution') or {}).get('species_id'),
                            confidence=species.get('confidence', 0), status=status)
            if status == 'accepted':
                confirmation = dict(event_id=e['event_id'], timestamp=t, identity=ref, reason=reason,
                                    species=deepcopy(species), icon=deepcopy(icon), evidence=deepcopy(e['evidence']))
                break
        row.update(hud=confirmation, hud_attempts=attempts, episode_end=end)
        a = p.get('identity'); b = (confirmation or {}).get('identity')
        row['comparison'] = ('inconclusive' if not a or not b else
                             'match' if a['species_id'] == b['species_id'] else 'mismatch')
        row['form_comparison'] = ('inconclusive' if not a or not b or not a.get('canonical_identity') or not b.get('canonical_identity')
                                  else 'match' if a['canonical_identity'] == b['canonical_identity'] else 'mismatch')
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--battle', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--evaluation-id', required=True)
    parser.add_argument('--verified-titles', action='store_true')
    args = parser.parse_args()
    owner = BattleArtifacts(args.battle)
    target = owner.cache('evaluation/' + args.evaluation_id); target.mkdir(parents=True, exist_ok=True)
    resolver = None
    if args.verified_titles:
        from knowledge.message_names import MessageNames
        resolver = MessageNames()
    frozen = freeze(owner, args.run_id, target, resolver)
    # The prediction file is durably written before loading any HUD observations.
    seal = digest(target/'message-predictions.json')
    source = owner.cache('event-driven/' + args.run_id)
    hud = [e for e in read(source/'video-only.json')['events'] if e['event_type'] == 'hud_observation']
    rows = compare(frozen['predictions'], hud)
    counts = dict(entries=len(rows), complete_readable_candidates=sum(r['complete_readable_candidate'] for r in rows),
                  uniquely_mapped_species=sum(bool(r['identity']) for r in rows),
                  independently_verifiable=sum(bool(r['hud']) for r in rows),
                  no_usable_hud=sum(not r['hud'] for r in rows), forms_unknown=sum(r['form_unknown'] for r in rows),
                  comparisons=dict(Counter(r['comparison'] for r in rows)),
                  form_comparisons=dict(Counter(r['form_comparison'] for r in rows)))
    result = dict(counts=counts, rows=rows, frozen_predictions_sha256=seal,
                  source_sha256=digest(source/'video-only.json'),
                  status='PENDING_COMPLETE_OBSERVABLE_SEND_OUT_REVIEW')
    assert seal == digest(target/'message-predictions.json')
    atomic_json(target/'comparisons.json', result)
    report = owner.report('M2.3.9-message-identity-entries-v1.md')
    lines = ['# Message-only identity versus independent HUD', '',
             'Offline exact-name predictions were frozen before the HUD comparison. Species-only matches do not resolve forms. Readability counts below are automatic candidates pending image review.', '',
             '| Time | Side / slot | Literal display reference | Message species | Form identity | First eligible HUD | Species comparison |',
             '|---|---|---|---|---|---|---|']
    for r in rows:
        a = r['identity'] or {}; h = r['hud'] or {}; b = h.get('identity') or {}
        lines.append(f"| {r['timestamp']:.3f} | {r['side']} / {r['slot'] or 'unknown'} | {r['literal']} | {a.get('species_id', 'unknown')} | {a.get('canonical_identity') or 'unknown'} | {str(round(h['timestamp'],3))+'s / '+str(b.get('species_id')) if h else 'none'} | {r['comparison']} |")
    lines += ['', '```json', json.dumps(counts, indent=2), '```', '',
              'Full immutable source IDs, evidence timestamps, independent HUD candidates and rejection reasons are in the local evaluation `comparisons.json`. No prediction is repaired from HUD.']
    report.parent.mkdir(parents=True, exist_ok=True); report.write_text('\n'.join(lines)+'\n')
    print(json.dumps(counts, indent=2))


if __name__ == '__main__':
    main()
