"""Scoped initial-binding repair validation: frozen v3 events, no acquisition.

Run prefix first, full saved-event replay second, report last. Completed stages
are reused; all original predictions and their observation IDs remain immutable.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.fast_video import digest
from recognition.video_sampling import atomic_json
from recognition.event_report import verify_seal
from tracking.battle_state import BattleState
from tracking.state_engine import StateEngine, EventRecord, event_from_dict, ordering

RUN = 'm238-opponent-binding-v1'


def forbidden(*args, **kwargs):
    raise AssertionError('No decoding, images, OCR or icon recognition in saved replay')


def replay(events, checkpoint):
    engine = StateEngine(BattleState('sample_battle_6', knowledge=dict(
        reliability_v1=True, reliability_v2=True, identity_v1=True)))
    for i, event in enumerate(events, 1):
        engine.history.append(EventRecord(deepcopy(event), i, ordering(event_from_dict(event))))
    initial = {}
    def progress(record, state):
        if not initial and state.sides['opponent'].trainer.get('status') == 'accepted':
            initial.update(timestamp=record.event['attributes']['observation_time'], state=state.to_dict())
        if record.delivery_index % 100 == 0:
            row = dict(stage='replaying_saved_events', completed=record.delivery_index, total=len(events),
                       timestamp=record.event['attributes']['observation_time'])
            atomic_json(checkpoint, row)
            print(json.dumps(row), flush=True)
    with ExitStack() as stack:
        for name in ['recognition.fast_video.CachedOCR.read', 'recognition.fast_video.CachedOCR.predict',
                     'recognition.fast_video.CachedIcons.identify', 'recognition.fast_video.decoded_frames',
                     'cv2.imread', 'cv2.VideoCapture']:
            stack.enter_context(patch(name, forbidden))
        engine.replay(snapshot_callback=progress)
    result = engine.to_dict()
    result['initial_binding_checkpoint'] = initial
    return result


def report(before, after, prediction, prefix, manifest):
    old = {r['event']['event_id']: r for r in before['history']}
    new = {r['event']['event_id']: r for r in after['history']}
    codes = lambda rows: dict(Counter(r['reason'] for r in rows if r['application_status'] == 'deferred'))
    oldcodes, newcodes = codes(before['history']), codes(after['history'])
    hudcodes = lambda rows: dict(Counter(r['bindings']['hud']['reason'] for r in rows
        if r['event']['event_type'] == 'hud_observation' and r['bindings'].get('hud', {}).get('status') in {'deferred', 'conflicting'}))
    initial = after['initial_binding_checkpoint']
    slots = {}
    for side, team in initial['state']['sides'].items():
        for slot, pid in team['active_slots'].items():
            key = side + ':' + slot
            supporting = next(r for r in after['history'] if r['event']['event_type'] == 'hud_observation'
                and r['event']['side'] == side and r['event']['attributes']['slot'] == slot
                and r['bindings'].get('hud', {}).get('status') == 'accepted')
            slots[key] = dict(instance_id=pid, identity=supporting['bindings'].get('identity'),
                              hp=supporting['event']['attributes']['hp'], hud=supporting['bindings']['hud'],
                              original_hud_representation=supporting['event']['attributes']['species']['resolution']['method'])
    moves = []
    for e in prediction['events']:
        if e['event_type'] == 'move_execution':
            a, b = old[e['event_id']], new[e['event_id']]
            moves.append(dict(id=e['event_id'], timestamp=e['attributes']['observation_time'], raw=e['original_text'],
                              before=a['application_status'], after=b['application_status'], before_cause=a['reason'],
                              after_cause=b['reason'], binding=b['bindings'].get('actor'),
                              admissibility=b['bindings'].get('admissibility'),
                              resolved_side=b['bindings'].get('resolved_event', e)['side']))
    newly_accepted = []
    for r in after['history']:
        if (r['event']['event_type'] == 'hud_observation' and r['bindings'].get('hud', {}).get('status') == 'accepted'
                and old[r['event']['event_id']]['bindings'].get('hud', {}).get('status') != 'accepted'):
            a = r['event']['attributes']
            newly_accepted.append(dict(id=r['event']['event_id'], timestamp=a['observation_time'], side=r['event']['side'],
                                      slot=a['slot'], raw=(a.get('species') or {}).get('raw_text'),
                                      identity=r['bindings'].get('identity'), reason=r['bindings']['hud']['reason'],
                                      independent_support=r['bindings']['hud'].get('independent_identity_support')))
    return dict(run_id=RUN, source_prediction_sha256=manifest['inputs']['video-only.json'],
                initial_binding_time=initial['timestamp'], initial_slots=slots,
                trainer_claim=initial['state']['sides']['opponent']['trainer'],
                prefix_event_count=len(prefix['history']), all_four_initial_slots_established=len(slots) == 4,
                initial_announcements_still_unknown=[e['event_id'] for e in prediction['events']
                    if e['event_type'] == 'send_out' and 123 <= e['attributes']['observation_time'] < 127 and e['side'] == 'unknown'],
                before_deferred_causes=oldcodes, after_deferred_causes=newcodes,
                before_hud_withheld_causes=hudcodes(before['history']), after_hud_withheld_causes=hudcodes(after['history']),
                before_statuses=dict(Counter(r['application_status'] for r in before['history'])),
                after_statuses=dict(Counter(r['application_status'] for r in after['history'])),
                moves=moves, newly_accepted_hud_readings=newly_accepted,
                rejected_after=[dict(id=r['event']['event_id'], reason=r['reason']) for r in after['history'] if r['application_status'] == 'rejected'],
                provenance='Post-reference diagnostic, frozen source events, unchanged observations; no OCR/icons/decoding.',
                limits=['Initial four slots checked against saved 123–135s evidence, not independent human truth.',
                        'Later replay measures impact only; it is not a full-match accuracy acceptance.',
                        'Targets/effects remain withheld for partially admitted move revelations.',
                        'No correction is backdated to 123s; trainer-side proof first exists at the HUD timestamp.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['prefix', 'full', 'report'], required=True)
    args = parser.parse_args()
    paths = BattleArtifacts('sample_battle_6', ROOT)
    source = paths.cache('event-driven/m238-live-3-diagnostic')
    folder = paths.cache('event-driven/' + RUN)
    seal = verify_seal(source)
    inputs = {name: digest(source / name) for name in ['video-only.json', 'observations.json', 'replay.json', 'video-only-seal.json']}
    source_paths = ['tracking/evidence_fusion.py', 'tracking/identity_ledger.py', 'scripts/replay_initial_opponent_binding.py']
    identity = dict(inputs=inputs, source_code={name: digest(ROOT / name) for name in source_paths})
    manifest_path = folder / 'manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest['identity'] != identity:
            raise ValueError('Code/input identity changed; preserve the namespace and choose a new version')
    else:
        folder.mkdir()
        manifest = dict(identity=identity, inputs=inputs, status='ready', completed_stages=[],
                        acquisition_calls=0, pipeline_runs=0)
        atomic_json(manifest_path, manifest)
        for name in source_paths:
            target = folder / 'source' / name; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())
    if args.stage in manifest['completed_stages']:
        print(args.stage + ' already complete; reusing saved result'); return
    prediction = json.loads((source / 'video-only.json').read_text())
    if args.stage == 'prefix':
        events = [e for e in prediction['events'] if 123 <= e['attributes']['observation_time'] <= 135]
    elif args.stage == 'full':
        if 'prefix' not in manifest['completed_stages']: raise ValueError('Run prefix first')
        events = prediction['events']
    else:
        if 'full' not in manifest['completed_stages']: raise ValueError('Run full saved replay first')
        data = report(json.loads((source / 'replay.json').read_text()), json.loads((folder / 'full.json').read_text()),
                      prediction, json.loads((folder / 'prefix.json').read_text()), manifest)
        target = ROOT / 'reports/M2.3.8-opponent-initial-binding-v1.json'
        with target.open('x') as stream: json.dump(data, stream, ensure_ascii=False, indent=2)
        manifest['completed_stages'].append('report'); manifest['status'] = 'complete'
        atomic_json(manifest_path, manifest)
        print(json.dumps({k: v for k, v in data.items() if k in ['all_four_initial_slots_established', 'initial_binding_time', 'before_statuses', 'after_statuses', 'before_deferred_causes', 'after_deferred_causes']}, indent=2))
        return
    began = time.monotonic()
    manifest.update(status='running', current_stage=args.stage); atomic_json(manifest_path, manifest)
    try:
        result = replay(events, folder / (args.stage + '-progress.json'))
        atomic_json(folder / (args.stage + '.json'), result)
        verify_seal(source)
        assert all(digest(source / name) == value for name, value in inputs.items())
        manifest['completed_stages'].append(args.stage)
        manifest.update(status='ready', active_seconds=time.monotonic() - began)
        atomic_json(manifest_path, manifest)
        print(args.stage + ' complete; ' + str(len(events)) + ' saved events', flush=True)
    except BaseException as exc:
        manifest.update(status='failed', error=repr(exc)); atomic_json(manifest_path, manifest); raise


if __name__ == '__main__':
    main()
