"""Frozen B22 message/edge-HUD validation. No decoding, OCR or production CLI.

Usage: .venv/bin/python scripts/validate_b22_implementation.py --run-id b22-focused-v1
Existing completed stages are reused only with identical input/source hashes.
"""
import argparse
from collections import Counter
from copy import deepcopy
from itertools import groupby
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from battle_artifacts import BattleArtifacts, canonical_id
from recognition.event_report import atomic_json
from recognition.message_occurrences import MessageOccurrences
from tracking.battle_state import from_dict
from tracking.state_engine import StateEngine, EventRecord, event_from_dict, ordering

RUN = 'fresh-b22-ditto-20261030-v1'


def read(path):
    return json.loads(path.read_text())


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def timestamp(e):
    return e['attributes'].get('observation_time', 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args(); canonical_id(args.run_id)
    owner = BattleArtifacts('sample_battle_22', ROOT)
    prod = owner.cache('event-driven/' + RUN)
    bench = owner.cache('fresh-benchmark/' + RUN)
    out = owner.cache('diagnosis/' + args.run_id)
    if out in {prod, bench}:
        parser.error('Validation requires a separate namespace')
    out.mkdir(parents=True, exist_ok=True)
    dependencies = ['battle_events/parser.py', 'recognition/message_occurrences.py',
        'tracking/state_engine.py', 'tracking/evidence_fusion.py', 'tracking/identity_ledger.py',
        'tracking/active_continuity.py', 'tracking/transformation.py', 'tracking/unnerve.py',
        'tracking/decision_state.py', 'tracking/mechanics.py', 'tracking/hp_causes.py',
        'scripts/validate_b22_implementation.py']
    protected = [*bench.glob('*.json'), * (bench / 'diagnosis').glob('*.json'),
                 * (ROOT / 'docs/b22-ditto').glob('*')]
    protected = [p for p in protected if p.is_file()]
    identity = dict(inputs={str(p.relative_to(ROOT)): digest(p) for p in
        [prod / 'replay.json', prod / 'observations.json', bench / 'initial-freeze.json', bench / 'hp-resolutions.json']},
        sources={p: digest(ROOT / p) for p in dependencies},
        scope='All original non-HUD events plus first/last two reads of every unchanged HP run and original action-bounded final plateaus; conflict/non-admitted HUDs retained; four newly parsed occurrences only')
    path = out / 'manifest.json'
    if path.exists():
        previous = read(path)
        if previous['identity'] != identity:
            raise ValueError('Validation identity changed; preserve this run and use a new --run-id')
        if previous['status'] == 'complete':
            for name, h in previous['outputs'].items():
                assert digest(out / name) == h, name
            print('Reused completed validation:', out)
            print(json.dumps(read(out / 'summary.json')['counts'], ensure_ascii=False))
            return
        raise ValueError('Inspect incomplete manifest/process; use a new namespace after resolving the recorded error')
    manifest = dict(identity=identity, status='running', stages={}, ocr_invocations=0, decoded_frames=0,
                    protected={str(p.relative_to(ROOT)): digest(p) for p in protected})
    atomic_json(path, manifest)

    def stage(name, status):
        manifest['stages'][name] = status; atomic_json(path, manifest)
        print(name, status, flush=True)

    try:
        stage('integrity_before', 'running')
        guards = [read(bench / 'initial-freeze.json'), read(bench / 'b16-b21-protected.json')]
        for guard in guards:
            for i, (name, h) in enumerate(guard['files'].items()):
                assert digest(ROOT / name) == h, name
                if i and i % 2000 == 0:
                    print('verified', i, 'files', flush=True)
        stage('integrity_before', dict(verified_files=sum(len(g['files']) for g in guards)))
        frozen = read(prod / 'replay.json'); observations = read(prod / 'observations.json')
        raw = [h['event'] for h in frozen['history']]
        original = {h['event']['event_id']: h for h in frozen['history']}
        selected = {c['event_id'] for c in frozen['state']['conflicts']}
        old_projection = read(bench / 'hp-resolutions.json')
        # A constant-HP run may span an item activation or another action. Keep
        # its already cached action-bounded plateau edges as well, so pruning
        # repetition cannot invalidate an existing stable endpoint.
        for ep in old_projection['episodes']:
            for component in ep['components']:
                plateau = component.get('final_plateau_event_ids', [])
                selected.update(plateau[:2] + plateau[-2:])
        for mon in frozen['state']['pokemon'].values():
            numeric = [o for o in mon['hp']['observations'] if 'unit' in o]
            for _, group in groupby(numeric, key=lambda o: (o['unit'], o['after'])):
                values = list(group)
                selected.update(o['evidence']['event_id'] for o in values[:2] + values[-2:])
        kept = [deepcopy(e) for e in raw if e['event_type'] != 'hud_observation'
                or e['event_id'] in selected
                or original[e['event_id']]['application_status'] not in {'applied_candidate', 'applied_confirmed'}]
        # Reparse only the four diagnosed live occurrences. Their frame/source
        # IDs and occurrence IDs remain the original ones; logs supply no events.
        groups = [g for g in observations['occurrences'] if any(
            '变身成了' in o['raw_text'] or '而无法食用树果' in o['raw_text'] for o in g['observations'])]
        assert len(groups) == 4
        rows = {r['source_id']: r for r in observations['observations']}
        extra = []
        for group in groups:
            occurrence = MessageOccurrences(owner.battle_id, source_occurrence_ids=True)
            emitted = []
            for o in group['observations']:
                emitted += occurrence.observe(rows[o['source_id']])['events']
            assert len(emitted) == 1
            e = emitted[0]
            assert e['attributes']['occurrence_id'] == group['id']
            extra.append(e)
        assert not {e['event_id'] for e in extra} & set(original)
        old_order = {e['event_id']: i for i, e in enumerate(raw)}
        combined = sorted(kept + extra, key=lambda e: (timestamp(e), old_order.get(e['event_id'], len(raw))))
        for i, e in enumerate(combined):
            # Stable source/event identity; explicit replay ordering is a separate
            # argument, so do not rewrite any original event's sequence attribute.
            assert e['event_id'] not in original or e == original[e['event_id']]['event']
        atomic_json(out / 'added-events.json', extra)
        engine = StateEngine(from_dict(frozen['initial_state']))
        engine.history = [EventRecord(e, i, ordering(event_from_dict(e), i + 1)) for i, e in enumerate(combined)]
        manifest.update(selected_events=len(combined), original_events=len(kept), added_events=len(extra))
        stage('focused_replay', 'running')
        checkpoints = []

        def progress(record, state):
            if record.delivery_index % 50 == 0:
                manifest['processed_events'] = record.delivery_index
                atomic_json(path, manifest)
                print('processed', record.delivery_index, '/', len(combined), flush=True)
            e = record.event
            if (e['event_id'] in {x['event_id'] for x in extra}
                    or e['event_type'] in {'ability_activation', 'switch_out', 'send_out', 'faint'} and '百变怪' in e['original_text']):
                dittos = {pid: dict(identity=as_small(p.original_identity), location=as_small(p.location),
                    hp=dict(current=as_small(p.hp.current), maximum=as_small(p.hp.maximum), displayed_percent=as_small(p.hp.displayed_percent)),
                    item=as_small(p.item.identity), ability=as_small(p.ability.current),
                    transformations=deepcopy(p.transformations), mechanics={k: v.current['snapshot'].value
                        for k, v in p.mechanics.items() if k == 'temporary_transform' and v.current.get('active').value is True})
                    for pid, p in state.pokemon.items() if (p.original_identity.value or {}).get('species_id') == 132}
                checkpoints.append(dict(time=timestamp(e), event_id=e['event_id'], event_type=e['event_type'],
                    text=e['original_text'], status=record.application_status, reason=record.reason,
                    bindings=deepcopy(record.bindings), dittos=dittos))
                atomic_json(out / 'checkpoints.json', checkpoints)

        started = time.perf_counter()
        engine.replay(snapshot_callback=progress)
        manifest['focused_replay_seconds'] = time.perf_counter() - started
        atomic_json(out / 'replay.json', engine.to_dict())
        stage('focused_replay', 'complete')
        projection = engine.hp_resolutions(); atomic_json(out / 'hp-resolutions.json', projection)
        after = {r.event['event_id']: r for r in engine.history}
        recovered = [dict(event_id=e['event_id'], time=timestamp(e), text=e['original_text'],
            before='unknown_not_emitted', after=after[e['event_id']].application_status,
            reason=after[e['event_id']].reason, bindings=after[e['event_id']].bindings) for e in extra]
        assert all(r['after'] == 'applied_candidate' for r in recovered), recovered
        ditto_ids = [pid for pid, p in engine.state.pokemon.items() if (p.original_identity.value or {}).get('species_id') == 132]
        assert len(ditto_ids) == 1, ditto_ids
        pid = ditto_ids[0]; ditto = engine.state.pokemon[pid]
        assert len(ditto.transformations) == 2
        assert [r['snapshot']['target_identity']['value']['species_id'] for r in ditto.transformations] == [445, 279]
        assert ditto.transformations[0]['active'] is False and ditto.transformations[1]['active'] is True
        assert ditto.fainted.value is True and ditto.hp.displayed_percent.value == 0
        assert ditto.species.value['species_id'] == ditto.original_identity.value['species_id'] == 132
        entries = [ep for ep in engine.state.knowledge['active_entry_episodes'] if ep['instance_id'] == pid]
        assert len(entries) == 2 and entries[1]['persistent_identity_status'] == 'independently_supported'
        old_entries = [ep for ep in frozen['state']['knowledge']['active_entry_episodes'] if ep['species_id'] == 132]
        assert [ep['episode_id'] for ep in entries] == [ep['episode_id'] for ep in old_entries]
        # All retained old accepted events must keep their status and reason.
        changes = [dict(event_id=r.event['event_id'], type=r.event['event_type'], time=timestamp(r.event),
            before=original[r.event['event_id']]['application_status'], after=r.application_status,
            before_reason=original[r.event['event_id']]['reason'], after_reason=r.reason)
            for r in engine.history if r.event['event_id'] in original and
            (r.application_status, r.reason) != (original[r.event['event_id']]['application_status'], original[r.event['event_id']]['reason'])]
        assert not changes, changes
        def numeric(state):
            return {o['evidence']['event_id']: (o['observed_before'], o['after'], o['unit'], o['delta'])
                    for p in state['pokemon'].values() for o in p['hp']['observations'] if o.get('delta') and 'unit' in o}
        assert numeric(engine.state.to_dict()) == numeric(frozen['state'])
        assert len(numeric(frozen['state'])) == 45
        projection_fields = ['source_event_id', 'before', 'after', 'unit', 'complete_endpoints',
                             'attribution_status', 'net_endpoint_delta']
        assert len(projection['episodes']) == len(old_projection['episodes'])
        projection_changes = [{k: (a.get(k), b.get(k)) for k in projection_fields if a.get(k) != b.get(k)}
                              for a, b in zip(old_projection['episodes'], projection['episodes'])]
        assert not any(projection_changes), projection_changes
        assert len(engine.state.conflicts) == len(frozen['state']['conflicts'])
        first = ditto.transformations[0]['snapshot']
        assert first['unresolved_form_evidence'] and first['form']['knowledge'] == 'unknown'
        assert all(f['knowledge'] == 'unknown' for f in first['non_hp_stats'].values())
        summary = dict(counts=dict(recovered_messages=len(recovered), ditto_instances=len(ditto_ids),
            transformations=len(ditto.transformations), preserved_nonzero_numeric_hp=45,
            changed_original_statuses=len(changes), conflicts=len(engine.state.conflicts),
            changed_projection_totals_or_support=sum(bool(c) for c in projection_changes),
            deferred=sum(r.application_status == 'deferred' for r in engine.history),
            projection_episodes=len(projection['episodes'])), recovered=recovered,
            ditto=dict(instance_id=pid, entry_episodes=entries, final_hp=as_small(ditto.hp.displayed_percent)),
            receipt_counts=dict(Counter(r.application_status for r in engine.history)),
            conflicts=engine.state.conflicts,
            deferred=[dict(event_id=r.event['event_id'], time=timestamp(r.event), reason=r.reason)
                      for r in engine.history if r.application_status == 'deferred'],
            limitations=['Local saved-observation repair; no new whole-match accuracy or complete BattleState claim.',
                        'HP observations are checked separately from causal projection support.',
                        'Only numeric-run and action-plateau edge HUD reads retained; repeated readings omitted.'])
        atomic_json(out / 'summary.json', summary)
        stage('semantic_and_hp_checks', 'complete')
        for name, h in manifest['protected'].items():
            assert digest(ROOT / name) == h, name
        for guard in guards:
            for name, h in guard['files'].items():assert digest(ROOT / name) == h, name
        stage('integrity_after', 'complete')
        manifest.update(status='complete', outputs={name: digest(out / name) for name in
            ['added-events.json', 'checkpoints.json', 'replay.json', 'hp-resolutions.json', 'summary.json']})
        atomic_json(path, manifest)
        print(json.dumps(summary['counts'], ensure_ascii=False, indent=2))
    except Exception as exc:
        manifest.update(status='error', error=repr(exc)); atomic_json(path, manifest)
        raise


def as_small(f):
    return dict(value=deepcopy(f.value), knowledge=f.knowledge)


if __name__ == '__main__':
    main()
