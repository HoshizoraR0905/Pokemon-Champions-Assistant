"""M2.3.8-Q: saved-evidence diagnostics only; never replay or acquire video."""
from collections import Counter, defaultdict
from copy import deepcopy
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from battle_artifacts import BattleArtifacts
from battle_events.parser import EventParser
from recognition.battle_log import assemble_views

VERSION = 'm238-q-v1'
SLOTS = ('self:left', 'self:right', 'opponent:left', 'opponent:right')
ACCEPTED = {'applied_candidate', 'applied_confirmed', 'applied_partial'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact(text):
    return re.sub(r'[\s！!。.]+', '', text)


def identity(value):
    return {k: value.get(k) for k in ('canonical_id', 'species_id', 'name', 'canonical_identity', 'identity_status')
            if value.get(k) is not None} if isinstance(value, dict) else None


def reading(value):
    if not isinstance(value, dict):
        return value
    result = {k: value[k] for k in ('raw_text', 'value', 'confidence', 'region', 'provenance') if k in value}
    if value.get('resolution'):
        result['resolution'] = {k: value['resolution'].get(k) for k in
                                ('status', 'species_id', 'method', 'confidence', 'canonical_identity')}
    return result


def topic(text, parsed_type='unknown'):
    if parsed_type != 'unknown':
        return parsed_type
    for words, label in [(['回到', '换下', '回来'], 'withdrawal_observation'),
                         (['战胜了', '投降'], 'battle_outcome_observation'),
                         (['顺风'], 'side_condition_observation'),
                         (['生命', '削减', '体力', 'HP'], 'hp_or_healing_observation'),
                         (['进化石', '超级进化'], 'transformation_notice'),
                         (['攻击', '特攻', '防御', '速度'], 'stat_observation')]:
        if any(w in text for w in words):
            return label
    return 'unparsed_message'


def proof(row):
    return dict(source_id=row['source_id'], timestamp=row['timestamp'], sha256=row['sha256'],
                image=row['image'], href='battles/sample_battle_6/event-driven/m238-live-3-diagnostic/assets/' + row['sha256'] + '.png')


def source_proofs(event, by_source):
    result = []
    for ev in event.get('evidence', []):
        row = by_source.get(ev['source_id'])
        if row is None:
            image = ev.get('details', {}).get('image')
            row = next((r for r in by_source.values() if r['image'] == image), None)
        result.append(dict(source_type=ev['source_type'], observation_ids=ev.get('observation_ids', []),
                           **(proof(row) if row else dict(source_id=ev['source_id'], href=None))))
    return result


def inventory(prediction, replay, observations):
    by_source = {r['source_id']: r for r in observations['observations']}
    histories = {h['event']['event_id']: h for h in replay['history']}
    receipts = {r['id']: r for r in prediction['receipts']}
    events = []
    prefix_slots = {}; slot_pids = {}
    for event in prediction['events']:
        h = histories[event['event_id']]
        receipt = receipts[event['event_id']]
        binding = h['bindings']
        resolved = binding.get('resolved_event', event)
        attrs = event['attributes']
        hud = binding.get('hud', {})
        pid = binding.get('actor', {}).get('pokemon_instance_id')
        logical_slot = attrs.get('slot')
        slot_basis = 'explicit_event_slot' if logical_slot else None
        if logical_slot is None and pid in prefix_slots:
            logical_slot = prefix_slots[pid].split(':')[1]
            slot_basis = 'earlier_admitted_receipt_only'
        tags = []
        if h['application_status'] == 'applied_partial':
            tags += ['partially_applied']
        elif h['application_status'] == 'deferred':
            tags += ['deferred']
        elif h['application_status'] == 'recorded_observation':
            tags += ['observed_only']
        else:
            tags += ['state_candidate']
        missing = list(resolved.get('uncertainty', []))
        if hud.get('status') in {'deferred', 'conflicting'}:
            missing.append(hud['reason'])
            tags.append('missing')
        if h['application_status'] == 'deferred' and h['reason']:
            missing.append(h['reason'])
        if any('ambiguous' in str(x) or 'conflict' in str(x) for x in missing):
            tags.append('ambiguous')
        raw = event['original_text']
        if event['event_type'] == 'hud_observation':
            raw = dict(name=reading(attrs.get('species')), hp=reading(attrs.get('hp')),
                       identity_reused_from=attrs.get('identity_reused_from'))
        events.append(dict(id=event['event_id'], timestamp=attrs['observation_time'], origin='frozen_v3',
                           kind=event['event_type'], raw=raw, side=resolved['side'],
                           actor=identity(resolved.get('actor')) or identity(binding.get('identity')),
                           target=identity(resolved.get('target')), slot=logical_slot,
                           interpretation={k: deepcopy(v) for k, v in resolved['attributes'].items() if k in {
                               'stats', 'direction', 'stages', 'effect', 'terrain', 'weather', 'change', 'condition',
                               'mechanic', 'identity', 'before', 'after', 'unit', 'observation_only',
                               'ordered_display_references', 'announced_order', 'display_reference'}},
                           canonical_references={k: identity(v) for k, v in event.get('canonical_references', {}).items()},
                           visual_fields=deepcopy(attrs.get('fields')),
                           parser=dict(kind=event['event_type'], side=event['side'], actor=identity(event.get('actor')),
                                       confidence=event['parsing_confidence'], ocr_confidence=event['ocr_confidence'],
                                       uncertainty=event['uncertainty'], prefix_kind=resolved['event_type']),
                           binding=dict(actor=deepcopy(binding.get('actor')), target=deepcopy(binding.get('target')),
                                        identity=identity(binding.get('identity')), hud_status=hud.get('status'),
                                        hud_reason=hud.get('reason'), hp_status=hud.get('hp_status'),
                                        admissibility=deepcopy(binding.get('admissibility')),
                                        prefix_uncertainty=resolved['uncertainty'],
                                        logical_slot_basis=slot_basis, slot_inferred_from_future=False),
                           admission=dict(status=h['application_status'], code=h['reason'], explanation=receipt['reason'],
                                          independently_validated=False),
                           missing_evidence=missing, tags=tags, evidence=source_proofs(event, by_source)))
        if h['application_status'] in ACCEPTED and pid:
            if logical_slot and event['event_type'] in {'hud_observation', 'send_out'}:
                key = resolved['side'] + ':' + logical_slot
                old_pid = slot_pids.get(key)
                prefix_slots.pop(old_pid, None)
                if pid in prefix_slots:
                    slot_pids.pop(prefix_slots[pid], None)
                prefix_slots[pid] = key; slot_pids[key] = pid
            elif event['event_type'] in {'switch_out', 'faint'}:
                key = prefix_slots.pop(pid, None)
                slot_pids.pop(key, None)
    return events


def observation_gaps(observations, prediction):
    """Retain unsupported text and semantic changes swallowed inside an occurrence.

    Context-free parser results are diagnostic only, never imported into replay.
    Repeated readings are grouped by meaning within their original occurrence.
    """
    parser = EventParser()
    by_source = {r['source_id']: r for r in observations['observations']}
    emitted = defaultdict(list)
    for event in prediction['events']:
        if event['event_type'] != 'entry_observation':
            emitted[event['attributes'].get('occurrence_id')].append(event)
    gaps = []
    for group in observations['occurrences']:
        variants = {}
        for obs in group['observations']:
            parsed = parser.parse(dict(entry_id=obs['sha256'], source_id=obs['source_id'],
                                       raw_text=obs['raw_text'], ocr_confidence=obs['confidence']),
                                  battle_id=prediction['battle_id']).to_dict()
            move = (parsed['canonical_references'].get('move') or {}).get('canonical_id')
            key = (parsed['event_type'], move, (parsed.get('actor') or {}).get('species_id'),
                   parsed['side'], compact(obs['raw_text']) if parsed['event_type'] == 'unknown' else '')
            variants.setdefault(key, []).append((obs, parsed))
        for key, samples in variants.items():
            obs, parsed = samples[0]
            covered = any(e['event_type'] == parsed['event_type']
                          and (e['canonical_references'].get('move') or {}).get('canonical_id') == key[1]
                          and ((e.get('actor') or {}).get('species_id') == key[2] or e['event_type'] == 'send_out')
                          for e in emitted[group['id']])
            if covered:
                continue
            suppressed = parsed['event_type'] != 'unknown' and group['emitted']
            fragment = group['emitted'] and parsed['event_type'] == 'unknown'
            why = ('occurrence_already_emitted_different_semantics' if suppressed else
                   'unsupported_parser_vocabulary' if parsed['event_type'] == 'unknown' else
                   'below_occurrence_confidence_gate')
            gaps.append(dict(id='diagnostic:' + group['id'] + ':' + str(len(gaps)),
                             timestamp=obs['timestamp'], end_timestamp=samples[-1][0]['timestamp'],
                             origin='saved_message_diagnostic', kind=topic(obs['raw_text'], parsed['event_type']),
                             raw=obs['raw_text'], side=parsed['side'], actor=identity(parsed.get('actor')),
                             target=identity(parsed.get('target')), slot=None,
                             canonical_references={k: identity(v) for k, v in parsed['canonical_references'].items()},
                             parser=dict(kind=parsed['event_type'], confidence=parsed['parsing_confidence'],
                                         ocr_confidence=obs['confidence'], uncertainty=parsed['uncertainty']),
                             binding=dict(actor=None, reason='not_submitted_to_state_engine'),
                             admission=dict(status='not_emitted', code=why, independently_validated=False),
                             missing_evidence=[why], tags=['missing'] + (['duplicate'] if suppressed else [])
                             + (['ambiguous'] if fragment else []),
                             grouping=dict(occurrence_id=group['id'], emitted=group['emitted'],
                                           provisional_fragment=fragment, readings=len(samples)),
                             evidence=[proof(by_source[o['source_id']]) for o, _ in samples]))
    return gaps


def extra_visuals(observations):
    result = []
    for row in observations['observations']:
        for parsed in row['visual'].get('parsed', []):
            if parsed.get('status') == 'supported':
                continue
            result.append(dict(id=f'visual:{row["source_id"]}:{len(result)}', timestamp=row['timestamp'],
                               origin='saved_visual_diagnostic', kind='unresolved_' + parsed['kind'],
                               raw={k: [dict(text=x.get('text'), confidence=x.get('confidence')) for x in v]
                                    for k, v in parsed.get('readings', {}).items() if isinstance(v, list)},
                               side='unknown', actor=identity(parsed.get('species')), target=None, slot=None,
                               parser=dict(kind=parsed['kind'], status=parsed['status']), binding=dict(actor=None),
                               admission=dict(status='not_emitted', code='visual_not_supported'),
                               missing_evidence=['supported_visual_identity_or_fields'], tags=['missing', 'ambiguous'],
                               evidence=[proof(row)]))
        for region in row['ui']['regions']:
            if region['region_type'] == 'field_indicator' and 'ocr' in region:
                result.append(dict(id=f'field:{row["source_id"]}', timestamp=row['timestamp'],
                                   origin='saved_field_diagnostic', kind='field_indicator_reading',
                                   raw={k: reading(v) for k, v in region['ocr'].items()}, side='field',
                                   actor=None, target=None, slot=None, parser=dict(canonical=region.get('canonical')),
                                   binding=dict(actor=None), admission=dict(status='not_emitted', code='no_canonical_field_label'),
                                   missing_evidence=['recognized_field_label', 'counter_semantics_unverified'],
                                   tags=['missing', 'ambiguous'], evidence=[proof(row)]))
    return result


def move_failure(event, history, latest_hud, prior_events):
    """Classify the earliest evidenced failure; receipt text alone is insufficient."""
    resolved = history['bindings'].get('resolved_event', event)
    attrs = resolved['attributes']
    uncertainty = resolved['uncertainty']
    candidates = []
    identity_by_pid = {}
    for previous in prior_events:
        previous_pid = previous['bindings'].get('actor', {}).get('pokemon_instance_id')
        if previous_pid and previous['bindings'].get('identity'):
            identity_by_pid[previous_pid] = previous['bindings']['identity']
    sid = (resolved.get('actor') or {}).get('species_id')
    for key, h in latest_hud.items():
        e = h['event']; a = e['attributes']
        if e['side'] == resolved['side'] or resolved['side'] == 'unknown':
            ref = (h['bindings'].get('identity') or (a.get('species') or {}).get('resolution')
                   or identity_by_pid.get(h['bindings'].get('actor', {}).get('pokemon_instance_id'), {}))
            if ref.get('species_id') == sid:
                candidates.append(dict(slot=key, time=a['observation_time'], id=e['event_id'],
                                       status=h['bindings'].get('hud', {}).get('status', h['application_status']),
                                       reason=h['reason'] or h['bindings'].get('hud', {}).get('reason'),
                                       instance_id=h['bindings'].get('actor', {}).get('pokemon_instance_id')))
    result = dict(category='no_failure_partial_supported_admission', first_failure_time=None,
                  reason='Actor and move revealed; target and effects explicitly withheld.', causal_chain=[],
                  prefix_hud_candidates=candidates, prefix_slot=None)
    pid = history['bindings'].get('actor', {}).get('pokemon_instance_id')
    bound = [key for key, h in latest_hud.items() if h['bindings'].get('actor', {}).get('pokemon_instance_id') == pid and pid]
    if len(bound) == 1:
        result['prefix_slot'] = bound[0]
    if history['application_status'] == 'applied_partial':
        return result
    if event['attributes'].get('source_region_type') != 'battle_message':
        result.update(category='incorrect_ui_region_routing', reason='Candidate did not originate in live-message region.')
    elif not event.get('actor'):
        result.update(category='actor_text_unresolved', reason='Original parser did not resolve an actor.')
    elif not (event.get('canonical_references', {}).get('move') or {}).get('canonical_id'):
        result.update(category='event_parser_failure', reason='Move was not canonically resolved.')
    elif event['side'] == 'opponent' and 'active_identity_context_unresolved' in uncertainty:
        first = next((h for h in prior_events if h['event']['event_type'] == 'hud_observation'
                      and h['event']['side'] == 'opponent'
                      and h['bindings'].get('hud', {}).get('reason') == 'identity_not_independently_supported'), None)
        opening = next((h for h in prior_events if h['event']['event_type'] == 'send_out'
                        and h['event']['side'] == 'unknown'), None)
        result.update(category='side_or_active_instance_binding_failure',
                      first_failure_time=opening['event']['attributes']['observation_time'] if opening else None,
                      reason='Opponent entry trainer-side context is unknown; subsequent icon_only HUD identities '
                             'fail the evidence contract, so no opponent active instance exists.',
                      causal_chain=[dict(stage='initial_entry_side', id=opening['event']['event_id'],
                                         time=opening['event']['attributes']['observation_time'])] if opening else [])
        if first:
            result['causal_chain'].append(dict(stage='hud_contract_rejection', id=first['event']['event_id'],
                                              time=first['event']['attributes']['observation_time']))
    elif 'side_unknown' in uncertainty:
        side = (attrs.get('display_alias_evidence') or [{}])[0].get('side')
        recent = [h for k, h in latest_hud.items() if k.startswith(str(side) + ':')]
        failed = [h for h in recent if h['bindings'].get('hud', {}).get('status') != 'accepted']
        first_failed = []
        for key, last in latest_hud.items():
            if last not in failed:
                continue
            beginning = last
            for previous in reversed(prior_events):
                e = previous['event']
                if e['event_type'] != 'hud_observation' or e['side'] + ':' + e['attributes']['slot'] != key:
                    continue
                if previous['bindings'].get('hud', {}).get('status') == 'accepted':
                    break
                beginning = previous
            first_failed.append(beginning)
        result.update(category='side_or_active_instance_binding_failure',
                      first_failure_time=min((h['event']['attributes']['observation_time'] for h in first_failed), default=None),
                      reason='Latest own HUD evidence is unresolved; stored alias alone cannot establish active side/instance.',
                      causal_chain=[dict(stage='latest_unresolved_hud', id=h['event']['event_id'],
                                         time=h['event']['attributes']['observation_time']) for h in first_failed]
                      + [dict(stage='latest_unresolved_hud', id=h['event']['event_id'],
                              time=h['event']['attributes']['observation_time']) for h in failed])
    elif history['reason'] == 'move_actor_not_bound_to_observed_prefix':
        claims = attrs.get('display_alias_evidence', [])
        accepted = [h for h in latest_hud.values() if h['bindings'].get('actor', {}).get('pokemon_instance_id')
                    in {c['instance_id'] for c in candidates if c['instance_id']}]
        # Locate first observed occupancy for the current episode, never a future one.
        current_ids = {h['bindings'].get('actor', {}).get('pokemon_instance_id') for h in accepted}
        first = next((h for h in prior_events if h['event']['event_type'] == 'hud_observation'
                      and h['bindings'].get('actor', {}).get('pokemon_instance_id') in current_ids), None)
        result.update(category='side_or_active_instance_binding_failure',
                      first_failure_time=first['event']['attributes']['observation_time'] if first else None,
                      reason='Alias still points to the earlier Grimmsnarl episode; prefix matcher filters out '
                             'the new observed episode. Re-entry equivalence is unproven.',
                      causal_chain=[dict(stage='stale_alias_instance', instance_id=c.get('instance_id')) for c in claims]
                      + [dict(stage='current_hud_episode', instance_id=p) for p in sorted(current_ids) if p])
    elif 'slot' in str(history['reason']):
        result.update(category='missing_logical_slot_evidence', reason=history['reason'])
    else:
        result.update(category='state_engine_reliability_rejection', reason=history['reason'])
    return result


def move_audit(prediction, replay, rows):
    histories = {h['event']['event_id']: h for h in replay['history']}
    latest = {}; prior = []; moves = []
    for e in prediction['events']:
        h = histories[e['event_id']]
        if e['event_type'] == 'move_execution':
            result = move_failure(e, h, latest, prior)
            result.update(id=e['event_id'], timestamp=e['attributes']['observation_time'], raw=e['original_text'],
                          original_side=e['side'], resolved_side=h['bindings'].get('resolved_event', e)['side'],
                          actor=identity(e.get('actor')), move=identity(e['canonical_references'].get('move')),
                          admission=h['application_status'], admission_code=h['reason'],
                          original_parser_uncertainty=e['uncertainty'],
                          prefix_uncertainty=h['bindings'].get('resolved_event', e)['uncertainty'],
                          ocr_assessment='Text matches saved message crop in agent visual review; not independent human ground truth.',
                          routing='saved live battle_message', occurrence_id=e['attributes'].get('occurrence_id'),
                          evidence=source_proofs(e, rows))
            moves.append(result)
        if e['event_type'] == 'hud_observation':
            latest[e['side'] + ':' + e['attributes']['slot']] = h
        prior.append(h)
    return moves


def slot_timeline(prediction, replay, gaps, end):
    """Receipt-derived review intervals, NOT replay or an authoritative new state.

    Unresolved readings retain last known occupancy, but withdraw binding support.
    An announcement without a slot never selects one. Unknown-side events are
    left unplaced. No future HUD is used to backfill an earlier interval.
    """
    histories = {h['event']['event_id']: h for h in replay['history']}
    intervals = {k: [dict(start=0., end=None, status='unknown', instance_id=None, name=None,
                         species_id=None, reason='No earlier admitted slot evidence', evidence_id=None)] for k in SLOTS}
    current = {k: dict(intervals[k][0]) for k in SLOTS}
    episodes = []; identities = {}; chronology = []
    for i, e in enumerate(prediction['events']):
        chronology.append((e['attributes']['observation_time'], i, e, histories[e['event_id']]))
    for gap in gaps:
        if gap['kind'] == 'withdrawal_observation' and not gap['grouping']['provisional_fragment']:
            chronology.append((gap['timestamp'], -1, dict(event_type='unparsed_withdrawal', side=gap['side'],
                              actor=gap['actor'], event_id=gap['id'], attributes={}), None))

    def update(key, t, status, pid, ref, reason, event_id):
        ref = ref or identities.get(pid, {})
        if pid and ref:
            identities[pid] = ref
        old = current[key]
        item = dict(start=t, end=None, status=status, instance_id=pid,
                    name=ref.get('name'), species_id=ref.get('species_id'), reason=reason, evidence_id=event_id)
        if (old['status'], old['instance_id'], old.get('name')) == (status, pid, item['name']):
            return
        intervals[key][-1]['end'] = t
        intervals[key].append(item); current[key] = item

    for t, _, e, h in sorted(chronology, key=lambda item: item[:2]):
        typ = e['event_type']; a = e['attributes']; side = e['side']
        binding = h['bindings'] if h else {}
        resolved = binding.get('resolved_event', e)
        side = resolved['side']
        pid = binding.get('actor', {}).get('pokemon_instance_id')
        if typ == 'hud_observation':
            key = side + ':' + a['slot']; hud = binding.get('hud', {})
            if hud.get('status') == 'accepted' and h['application_status'] in ACCEPTED:
                update(key, t, 'accepted_candidate_occupancy', pid, binding.get('identity'), hud.get('reason'), e['event_id'])
            else:
                old = current[key]
                update(key, t, 'unknown_current_binding', old['instance_id'], identities.get(old['instance_id']),
                       h['reason'] or hud.get('reason', 'Unresolved HUD'), e['event_id'])
        elif typ == 'send_out' and a.get('slot') and h['application_status'] in ACCEPTED:
            update(side + ':' + a['slot'], t, 'candidate_announcement_slot', pid, e.get('actor'),
                   'Established screen-HUD ordering; candidate, not human validation', e['event_id'])
        elif typ in {'switch_out', 'faint'} and h['application_status'] in ACCEPTED:
            for key in SLOTS:
                if pid and current[key]['instance_id'] == pid:
                    update(key, t, 'vacant_candidate', None, {}, 'Admitted ' + typ, e['event_id'])
        elif typ == 'transformation' and h['application_status'] in ACCEPTED:
            for key in SLOTS:
                if pid and current[key]['instance_id'] == pid:
                    update(key, t, current[key]['status'], pid, a.get('identity'),
                           'Admitted transformation; same episode', e['event_id'])
        elif typ in {'send_out', 'unparsed_withdrawal', 'faint', 'switch_out'}:
            sid = (resolved.get('actor') or {}).get('species_id')
            affected = [k for k in SLOTS if (side in {'unknown', k.split(':')[0]})
                        and sid is not None and current[k].get('species_id') == sid]
            if typ == 'send_out' and side != 'unknown' and not affected:
                affected = [k for k in SLOTS if k.startswith(side + ':')]
            for key in affected:
                old = current[key]
                update(key, t, 'unknown_current_binding', old['instance_id'], identities.get(old['instance_id']),
                       'Observed transition lacks admitted placement/continuity: ' + typ, e['event_id'])
        if typ in {'entry_observation', 'send_out', 'switch_out', 'faint', 'transformation', 'position_change', 'unparsed_withdrawal'}:
            episodes.append(dict(timestamp=t, id=e['event_id'], kind=typ, side=side, slot=a.get('slot'),
                                 instance_id=pid, admission=h['application_status'] if h else 'not_emitted',
                                 raw=e.get('original_text'), note='No future evidence used'))
    for items in intervals.values():
        items[-1]['end'] = end
    episode_gaps = {}
    for key, items in intervals.items():
        for item in items:
            pid = item['instance_id']
            if not pid:
                continue
            entry = episode_gaps.setdefault(pid, dict(instance_id=pid, name=item['name'],
                first_admitted_slot_time=None, first_unresolved_after_support=None, slots=[]))
            if key not in entry['slots']:
                entry['slots'].append(key)
            if item['status'] in {'candidate_announcement_slot', 'accepted_candidate_occupancy'}:
                entry['first_admitted_slot_time'] = min(item['start'], entry['first_admitted_slot_time']
                                                       if entry['first_admitted_slot_time'] is not None else item['start'])
    for items in intervals.values():
        for item in items:
            if item['instance_id'] and item['status'] == 'unknown_current_binding':
                entry = episode_gaps[item['instance_id']]
                if entry['first_admitted_slot_time'] is not None and item['start'] >= entry['first_admitted_slot_time']:
                    entry['first_unresolved_after_support'] = min(item['start'],
                        entry['first_unresolved_after_support'] if entry['first_unresolved_after_support'] is not None else item['start'])
    return dict(intervals=intervals, transitions=episodes, episodes=list(episode_gaps.values()),
                semantics='Receipt-derived last-supported occupancy and explicit binding gaps; no biological continuity guarantee.')


def reference_coverage(reference, rows, prediction_events=()):
    by_position = defaultdict(list)
    for view in reference['views']:
        by_position[(view.get('turn'), view['geometry']['scroll_top'], view['geometry']['scroll_height'])].append(view)
    components = []; pages = []
    for (turn, top, height), views in sorted(by_position.items()):
        entries, issues = assemble_views(views, ignore_partial_overlap=True)
        parser = EventParser()
        for entry in entries:
            parsed = parser.parse(entry).to_dict()
            entry['diagnostic_parser'] = dict(kind=parsed['event_type'], side=parsed['side'],
                                             actor=identity(parsed.get('actor')), uncertainty=parsed['uncertainty'])
            text = compact(entry['raw_text'])
            entry['saved_live_observation_times'] = [r['timestamp'] for r in rows.values()
                if r['message'].get('selected') and compact(r['message'].get('raw_text', '')) == text]
            entry['frozen_prediction_ids'] = [e['event_id'] for e in prediction_events
                                              if compact(e['original_text']) == text]
            entry['comparison_status'] = ('literal_video_candidate_present' if entry['frozen_prediction_ids'] else
                'ocr_present_event_missing' if entry['saved_live_observation_times'] else
                'no_exact_live_text_match_not_proof_of_missed_event')
        components.append(dict(id=f'turn-{turn}-scroll-{top}', turn=turn, scroll_top=top, scroll_height=height,
                               entries=entries, assembly_issues=issues,
                               contiguous_with_other_components=False))
        for v in views:
            pages.append(dict(timestamp=v['timestamp'], source_id=v['source_id'], turn=v.get('turn'),
                              header=v.get('header_ocr'), scroll_top=top, scroll_height=height,
                              observations=v['observations'], evidence=proof(rows[v['source_id']]),
                              component=components[-1]['id']))
    return dict(version=VERSION + '-disconnected-reference', origin='Existing extraction only; no new OCR',
                observed_turns=sorted({v['turn'] for v in reference['views'] if v.get('detected') and v.get('turn') is not None}),
                pages=sorted(pages, key=lambda v: v['timestamp']), components=components,
                raw_row_observations=sum(len(v['observations']) for v in reference['views']),
                original_entries=len(reference['entries']), original_assembly_issues=reference['assembly_issues'],
                retained_component_entries=sum(len(c['entries']) for c in components),
                full_turn_coverage=False, whole_match_coverage=False,
                boundary='No reliable two-row overlap joins scroll 60 and 301. Intervening rows/count unknown; '
                         'similar Protect wording refers to opposite sides in inspected images. Keep components separate.',
                timestamps='Log inspection times only; never assign these as original action times.')


FIXES = [
    'Make the opponent literal-name/icon evidence contract explicit across adapter and HUD admission; '
    'preserve independent evidence and calibrate trainer-side context without treating nicknames as species declarations.',
    'Split an emitted message occurrence when supported event semantics change (Protect effect → own Protect; '
    'effectiveness → faint); preserve uncertain fragments and repeated same-event readings.',
    'Extend tested parser coverage for observed withdrawal wording, Tailwind activation and battle outcome; '
    'retain ambiguous actors and quantitative unknowns.',
    'Reconcile nickname claims with current re-entry episodes prospectively; do not let a stale alias suppress '
    'a later independently observed episode or merge biological individuals without evidence.',
    'Represent disconnected Battle Log scroll components and row coverage explicitly; admit no inferred turns '
    'or guessed gap rows, and expose failed field routing/canonicalization as coverage gaps.'
]


def build(prediction, replay, observations, reference):
    events = inventory(prediction, replay, observations)
    gaps = observation_gaps(observations, prediction)
    extras = extra_visuals(observations)
    by_source = {r['source_id']: r for r in observations['observations']}
    moves = move_audit(prediction, replay, by_source)
    events += gaps + extras
    events.sort(key=lambda x: (x['timestamp'], x['id']))
    end = observations['observations'][-1]['timestamp']
    coverage = reference_coverage(reference, by_source, prediction['events'])
    counts = dict(saved_observations=len(observations['observations']), frozen_events=len(prediction['events']),
                  frozen_event_types=dict(Counter(e['event_type'] for e in prediction['events'])),
                  frozen_receipt_statuses=dict(Counter(h['application_status'] for h in replay['history'])),
                  inventory_rows=len(events), supplemental_message_interpretations=len(gaps),
                  supplemental_visual_and_field_readings=len(extras), occurrence_groups=len(observations['occurrences']),
                  unemitted_occurrence_groups=sum(not g['emitted'] for g in observations['occurrences']),
                  moves=len(moves), move_first_failure_categories=dict(Counter(m['category'] for m in moves)),
                  move_admission=dict(Counter(m['admission'] for m in moves)),
                  suppressed_supported_semantics=sum('duplicate' in e['tags'] for e in gaps),
                  unsupported_visuals=sum(e['origin'] == 'saved_visual_diagnostic' for e in extras),
                  field_readings=sum(e['origin'] == 'saved_field_diagnostic' for e in extras),
                  canonical_field_readings=sum(bool(e['parser'].get('canonical')) for e in extras),
                  accepted_hud_by_slot=dict(Counter(h['event']['side'] + ':' + h['event']['attributes']['slot']
                      for h in replay['history'] if h['event']['event_type'] == 'hud_observation'
                      and h['bindings'].get('hud', {}).get('status') == 'accepted')))
    for slot in SLOTS:
        counts['accepted_hud_by_slot'].setdefault(slot, 0)
    return dict(schema=VERSION, battle_id=prediction['battle_id'], source_prediction='m238-live-3-diagnostic',
                status='diagnostic_only_not_semantically_accepted', counts=counts, inventory=events, moves=moves,
                slot_continuity=slot_timeline(prediction, replay, gaps, end), reference=coverage,
                proposed_fixes=FIXES,
                limits=['Agent visual inspection is not independent human ground truth.',
                        'All 23 frozen move messages inspected from saved crops; no OCR failure established for them.',
                        'Inventory covers saved observations, not every event in the original video.',
                        'No full replay or new recognition was performed; state admission is read from frozen receipts.',
                        'HP/status readings are observations; HP changes are not assigned a damage/healing cause.',
                        'No status or Ally Switch event is established by these saved predictions.',
                        'Victory/surrender text is observed, but frozen parser has no outcome event.',
                        'Battle Log coverage establishes displayed turn 4 only, not complete turn coverage.',
                        'Field-region OCR has zero canonical labels; counts are requests/readings, not valid field events.'])


def markdown(data):
    c = data['counts']; ref = data['reference']
    lines = ['# M2.3.8-Q — full-match saved-event quality audit', '',
             'Diagnostic audit of sealed v3; no runtime fixes, recognition, decoding or replay. '
             'Existing checkpoints, reports and annotations remain unchanged. Full-match here means the '
             'complete saved observation span, not proven video-event recall.', '',
             '## Verified counts', '', '```json', json.dumps(c, ensure_ascii=False, indent=2), '```', '',
             'The inventory separates frozen event candidates, saved unsupported messages, '
             'unresolved visual readings and failed field reads. Applied candidates are not human-validated facts. '
             'See the [offline viewer](M2.3.8-Q-event-audit.html) and [machine-readable inventory](M2.3.8-Q-event-audit.json).', '',
             '## Why only nine moves are admitted', '',
             'All 23 frozen announcements have resolved canonical actors and moves, correct saved live-message routing, '
             'and legible message crops in agent inspection. Nine bind to a prefix-supported own instance and reveal '
             'only the executed move. Target and effects remain unknown. Twelve opponent candidates fail active-instance '
             'binding: trainer-side entry context is unknown at 123.020s, and the opponent HUD adapter produces '
             '`icon_only` identities that HUD admission rejects at 134.007s even when raw names match species entries. '
             'The adapter deliberately discards text resolution for opponent display labels; the admission path accepts '
             'icon-only nickname evidence only when the raw label is absent from the exact species dictionary. '
             'This contract mismatch leaves both opponent slots without any accepted HUD identity. Later retained '
             'reads point to unaccepted originals. No threshold relaxation or nickname assumption was applied.', '',
             'The other two failures are own-side: Pelipper at 519.520s follows unresolved HUD readings (first such '
             'run starts at 487.015s; latest at 489.015s), so active side/context cannot be established. Grimmsnarl '
             'at 655.510s still has an alias bound to its old episode; the new right-slot episode first appears '
             'at 517.520s, but alias filtering excludes it. This is an episode-binding failure, not unreadable OCR.', '',
             '| # | Video s | Saved announcement | First failure category / explanation | Admission |',
             '| --- | ---: | --- | --- | --- |']
    for i, m in enumerate(data['moves'], 1):
        first = f' First upstream failure at {m["first_failure_time"]:.3f}s.' if m['first_failure_time'] is not None else ''
        lines.append(f'| {i} | {m["timestamp"]:.3f} | {m["raw"].replace(chr(10), " ")} | '
                     f'{m["category"]}: {m["reason"]}{first} | {m["admission"]} |')
    lines += ['', 'No failure attributed to OCR, UI routing, actor-text resolution or move parsing is established '
              'for these 23 candidates. This does not imply those stages are universally correct.', '',
              '## Recognized information lost before event admission', '',
              'Two supported semantic changes are swallowed by already-emitted occurrence groups: '
              'own Garchomp’s Protect at 456.010s follows the opponent protection effect in the 454.010–457.010s '
              'group; Rillaboom’s faint at 527.022s follows effectiveness in the 525.022–528.022s group. '
              'These are a diagnostic extra move announcement and an extra faint, separate from the frozen 23/two counts. '
              'Neither was added to frozen predictions. The saved `semantic` tuple is calculated by '
              '`MessageOccurrences.observe` but relatedness only forces a split for differing resolved move names; '
              'an already-emitted different event type is suppressed.', '',
              'Unsupported parser wording also loses withdrawals at 247.508s and 335.507s (“要回到…身边了”), '
              'Tailwind activation at 465.012s and 736.523s, and surrender/victory text at '
              '743.508s/745.508s. Incomplete prebattle/menu fragments are retained separately as unresolved observations, '
              'not promoted into battle events. All 446 saved field-indicator reads lack a canonical label; examples '
              'include “0”, “X” and “Hoshi”. This supports a field routing/geometry or interpretation concern, '
              'not 446 recognized field transitions. Cause per individual read is unverified.', '',
              '## Entry order and four-slot continuity', '',
              'Own double entry at 127.005s assigns Grimmsnarl left and Archaludon right, corroborated by HUD at '
              '134.007s. Opponent first entry is Gholdengo then Incineroar; the established opponent rule is '
              'right then left, consistent with inspected HUD labels at 134.007s, but the frozen event side stays unknown '
              'and those entry slots are never applied. No 3D model position was used.', '',
              'The interval list below is a receipt-derived diagnostic projection. `unknown_current_binding` retains '
              'the last admitted occupant as historical context; it does not vacate the slot or assert that occupant '
              'is still there. Repeated accepted readings do not establish continuous biological identity. '
              'No later HUD is backdated to an earlier announcement. Deferred transition details and all unknown '
              'intervals are also available in the HTML/JSON.', '',
              '| Own episode | First admitted slot s | First unresolved binding after support s |',
              '| --- | ---: | ---: |']
    for episode in data['slot_continuity']['episodes']:
        first = episode['first_unresolved_after_support']
        lines.append(f'| {episode["name"]} / {episode["instance_id"]} | '
                     f'{episode["first_admitted_slot_time"]:.3f} | {f"{first:.3f}" if first is not None else "none observed"} |')
    lines.append('')
    for slot, intervals in data['slot_continuity']['intervals'].items():
        lines += ['### ' + slot, '', '| Interval s | Status | Last observed identity / episode | Evidence / cause |',
                  '| --- | --- | --- | --- |']
        for interval in intervals:
            lines.append(f'| {interval["start"]:.3f}–{interval["end"]:.3f} | {interval["status"]} | '
                         f'{interval["name"] or "unknown"} / {interval["instance_id"] or "unknown"} | {interval["reason"]} |')
        lines.append('')
    lines += ['Own unplaced entries at 355.510s (Pelipper) and 393.000s (Garchomp) are first placed by HUD '
              'at 396.500s. Archaludon’s faint at 377.513s defers. Opponent Garchomp’s Mega Evolution '
              'at 328.505s defers; own Garchomp’s at 449.008s applies to its existing episode. Its withdrawal '
              'at 500.002s applies, but Grimmsnarl’s re-entry at 503.018s defers as ambiguous; HUD at 517.520s '
              'creates a new episode. Same-species re-entry is not proof of persistent individual identity. '
              'No supported Ally Switch announcement/execution is present.', '',
              '## Battle Log coverage', '',
              f'{len(ref["pages"])} saved inspected pages, {ref["raw_row_observations"]} raw row observations, '
              f'{len(ref["components"])} scroll positions, visible turn headers {ref["observed_turns"]}. '
              f'Original assembly retained {ref["original_entries"]} row groups. The separate versioned diagnostic '
              f'reference retains {ref["retained_component_entries"]} row groups in disconnected components; '
              'these are historical row observations, not twelve validated battle-state mutations.', '',
              '| Inspection s | Header | Scroll top / thumb height | Raw rows |',
              '| ---: | --- | --- | ---: |']
    for page in ref['pages']:
        lines.append(f'| {page["timestamp"]:.3f} | {page["header"]["raw_text"]} | '
                     f'{page["scroll_top"]} / {page["scroll_height"]} | {len(page["observations"])} |')
    lines += ['', ref['boundary'], '',
              'The bottom page adds own Protect, own protection effect, Tailwind announcement/activation, '
              'opponent healing and the 78%→83% HP row. Own Protect is visible in saved live OCR at '
              '456.010s but suppressed by occurrence grouping; Tailwind activation is legible but unsupported '
              'by the parser. These are event-pipeline omissions, not absent OCR. Missing intermediate scroll rows '
              'and turns other than 4 are reference coverage gaps, not evidence of video recognition failure. '
              'The original three provisional / one ambiguous / two incomplete comparison remains untouched. '
              'No whole-match recall or event time is inferred from log inspection timestamps.', '',
              '## Highest-impact issues / proposed future fixes', '']
    lines += [f'{i}. {fix}' for i, fix in enumerate(FIXES, 1)]
    lines += ['', 'None of these fixes was applied.', '', '## Validation, commands and limits', '',
              '```sh', *data.get('commands', []), '```', '',
              json.dumps(data.get('validation', {}), ensure_ascii=False, indent=2), '',
              *['- ' + limit for limit in data['limits']], '',
              'The source seal and input fingerprints are embedded in JSON. Diagnostic reference and progress '
              'files live under `.cache/battles/sample_battle_6/event-driven/m238-q-v1/`. The JSON/HTML outputs '
              'are generated local artifacts under the existing ignore policy. No commit or push was performed.', '']
    return '\n'.join(lines)


def render(data):
    template = (ROOT / 'scripts/templates/m238q_audit.html').read_text()
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    return template.replace('__DATA__', payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validation', type=Path, required=True)
    args = parser.parse_args()
    paths = BattleArtifacts('sample_battle_6', ROOT)
    cache = paths.cache('event-driven/' + VERSION)
    cache.mkdir(exist_ok=True)
    outputs = [ROOT / 'reports' / ('M2.3.8-Q-event-audit.' + ext) for ext in ('md', 'json', 'html')]
    if any(p.exists() for p in outputs) or (cache / 'reference-diagnostic.json').exists():
        raise ValueError('Audit output already exists; preserve it and choose a new version explicitly')
    base = paths.cache('event-driven/m238-live-3-diagnostic')
    source_files = [base / n for n in ('video-only.json', 'replay.json', 'observations.json', 'manifest.json', 'video-only-seal.json')]
    refpath = paths.cache('event-driven/m238-live-2/reference/battle-log.json')
    source_files += [refpath, refpath.parent / 'manifest.json']
    inputs = {str(p.relative_to(ROOT)): sha(p) for p in source_files}
    seal = json.loads((base / 'video-only-seal.json').read_text())
    assert seal['stage'] == 'video_only_frozen'
    assert all(sha(base / name) == digest for name, digest in seal['files'].items())
    manifest = json.loads((base / 'manifest.json').read_text())
    assert manifest['status'] == 'complete'
    assert all(sha(ROOT / name) == digest for name, digest in manifest['identity']['sources'].items())
    # Inventory and rehash old non-image artifacts; never modify these namespaces.
    preserved = {}
    for name in ('m238-live-1', 'm238-live-2', 'm238-live-3-diagnostic'):
        for directory in (paths.cache('event-driven/' + name), paths.report('event-driven/' + name)):
            for p in directory.rglob('*'):
                if p.is_file() and p.suffix not in {'.png', '.jpg'}:
                    preserved[str(p.relative_to(ROOT))] = sha(p)
    protected = json.loads(paths.cache('event-driven/protected-history.json').read_text())
    assert all(sha(ROOT / name) == digest for name, digest in protected.items())
    with (cache / 'inspection-manifest.json').open('x') as stream:
        json.dump(dict(stage='inspection_complete', inputs=inputs, preserved=preserved, protected=protected), stream)
    prediction, replay, observations = [json.loads((base / name).read_text()) for name in
                                        ('video-only.json', 'replay.json', 'observations.json')]
    print('Verified v3 seal; building chronological saved-data inventory', flush=True)
    data = build(prediction, replay, observations, json.loads(refpath.read_text()))
    assert len(data['moves']) == 23
    assert all((ROOT / 'reports' / p['href']).is_file() for e in data['inventory'] for p in e['evidence'] if p.get('href'))
    assert all(sha(ROOT / name) == digest for name, digest in preserved.items())
    data['inputs'] = inputs
    data['validation'] = dict(json.loads(args.validation.read_text()),
                              preserved_original_artifacts=len(preserved), protected_history_unchanged=len(protected),
                              image_links_checked=True, frozen_prediction_sha256=seal['files']['video-only.json'])
    data['commands'] = data['validation'].get('commands', []) + [
        'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/audit_m238q.py --validation ' + str(args.validation)]
    with (cache / 'reference-diagnostic.json').open('x') as stream:
        json.dump(data['reference'], stream, ensure_ascii=False, indent=2)
    for path, content in zip(outputs, (markdown(data), json.dumps(data, ensure_ascii=False, indent=2), render(data))):
        with path.open('x') as stream:
            stream.write(content)
    with (cache / 'report-manifest.json').open('x') as stream:
        json.dump(dict(stage='reports_complete_browser_pending', outputs={str(p.relative_to(ROOT)): sha(p) for p in outputs},
                       inputs=inputs, counts=data['counts']), stream, indent=2)
    print(json.dumps(data['counts'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
