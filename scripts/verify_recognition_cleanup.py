"""Read-only saved-evidence regression; one battle per invocation, no OCR/decoding.

Outputs use a separate battle-owned cleanup namespace. Completed stages resume
only with identical source/input fingerprints. No full state dumps are emitted.
"""
import argparse
from collections import Counter
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from battle_artifacts import BattleArtifacts, canonical_id
from recognition.fast_video import digest
from recognition.video_sampling import atomic_json
from recognition.event_report import verify_seal, video_events
from recognition.double_faint import DoubleFaintVerifier


def read(path):return json.loads(path.read_text())


def verify(args):
    paths = BattleArtifacts(args.battle)
    source = paths.cache('event-driven/' + canonical_id(args.source_run))
    out = paths.cache('cleanup/' + canonical_id(args.run_id))
    out.mkdir(parents=True, exist_ok=True)
    verify_seal(source)
    protected = ['manifest.json','observations.json','video-only.json','replay.json','video-only-seal.json']
    identity = dict(inputs={name:digest(source/name) for name in protected},
        sources={str(p.relative_to(ROOT)):digest(p) for folder in ['recognition','tracking','battle_events']
                 for p in (ROOT/folder).glob('*.py')}, script=digest(Path(__file__)),
        replay=args.replay, compare_prefix=args.compare_prefix)
    manifest = out/'manifest.json'
    result = read(manifest) if manifest.exists() else dict(identity=identity,stages={})
    if result['identity'] != identity:raise ValueError('Changed inputs/source; use another run ID')
    if result.get('status')=='complete':return result
    def save(stage, value):
        result['stages'][stage]=value;atomic_json(manifest,result)
        print(stage, json.dumps(value,ensure_ascii=False),flush=True)
    data = read(source/'observations.json');rows = data['observations']
    if 'events' not in result['stages']:
        events = video_events(rows,data['roster'],args.battle)
        for i,e in enumerate(events,1):e['attributes']['sequence']=i
        expected = read(source/'video-only.json')['events']
        save('events',dict(count=len(events),exact_semantics_ids_order_evidence=events==expected))
        if events != expected:raise ValueError('Saved event adaptation mismatch')
    if 'visual_geometry' not in result['stages']:
        import cv2
        import numpy as np
        from recognition.fast_profile import inspect
        frozen=source/'source/recognition/fast_profile.py'
        spec=importlib.util.spec_from_file_location('frozen_fast_profile',frozen)
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
        spec.loader.exec_module(module)
        phases={}
        for row in rows:phases.setdefault(row['ui']['phase'],row)
        checks=[]
        for phase,row in phases.items():
            path=paths.root/row['image']
            if digest(path)!=row['sha256']:raise ValueError('Saved frame hash changed')
            image=cv2.imread(str(path));old=module.inspect(image);new=inspect(image)
            equal=np.array_equal(old.pop('message_mask',None),new.pop('message_mask',None)) and old==new
            checks.append(dict(phase=phase,source_id=row['source_id'],exact_geometry=equal))
            if not equal:raise ValueError('Visual extraction geometry changed')
        save('visual_geometry',dict(checks=checks,scope='one saved frame per observed phase; frozen/current detector; no OCR'))
    if 'gate' not in result['stages']:
        verifier = DoubleFaintVerifier(args.battle);times=[];prefixes=[]
        for i,row in enumerate(rows):
            if any(e['event_type'] in {'send_out','switch_out','faint','position_change'}
                   for e in row['occurrence_decision']['events']) or row.get('trainer_observations'):
                began=time.perf_counter();verifier.observe_prefix(rows[:i+1],data['roster'])
                times.append(time.perf_counter()-began);prefixes.append(i+1)
        save('gate',dict(calls=len(times),seconds=sum(times),counts=dict(verifier.counts),
            last_prefix_rows=prefixes[-1],pending_sides=list(verifier.pending)))
    if args.compare_prefix and 'controlled_prefix' not in result['stages']:
        path=source/'source/recognition/double_faint.py'
        spec=importlib.util.spec_from_file_location('frozen_double_faint',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        end=result['stages']['gate']['last_prefix_rows'];prefix=rows[:end]
        print('Controlled last-prefix baseline replay starting:',end,'rows',flush=True)
        old=module.DoubleFaintVerifier(args.battle);began=time.perf_counter()
        old.observe_prefix(prefix,data['roster']);old_seconds=time.perf_counter()-began
        new=DoubleFaintVerifier(args.battle);began=time.perf_counter()
        new.observe_prefix(prefix,data['roster']);new_seconds=time.perf_counter()-began
        save('controlled_prefix',dict(rows=end,old_seconds=old_seconds,new_seconds=new_seconds,
            old_replays=1,new_replays=new.counts['candidate_prefix_replays'],
            pending_equal=old.pending==new.pending,
            scope='same saved prefix, same current engine and machine, no OCR; baseline first; one measurement'))
    if args.replay and 'replay' not in result['stages']:
        from tracking.battle_state import from_dict
        from tracking.state_engine import StateEngine, EventRecord
        expected=read(source/'replay.json')
        engine=StateEngine(from_dict(expected['initial_state']))
        engine.history=[EventRecord(**deepcopy(r)) for r in expected['history']]
        def progress(record,state):
            if record.delivery_index%100==0:
                print('Replay',record.delivery_index,'/',len(engine.history),flush=True)
                atomic_json(out/'progress.json',dict(stage='replay',record=record.delivery_index))
        began=time.perf_counter();engine.replay(snapshot_callback=progress);actual=json.loads(json.dumps(engine.to_dict()))
        save('replay',dict(events=len(engine.history),seconds=time.perf_counter()-began,
            exact_history_bindings_statuses_snapshots=actual['history']==expected['history'],
            exact_final_state=actual['state']==expected['state'],
            exact_final_hash=actual['state_hash']==expected['state_hash']))
        if actual != expected:raise ValueError('Saved replay mismatch')
    if 'battle_log' not in result['stages']:
        reference=paths.cache('evaluation/'+args.source_run+'/auto-reference/reference.json')
        if not reference.exists():reference=source/'reference/battle-log.json'
        if reference.exists():
            from recognition.battle_log import assemble_views
            from battle_events.parser import EventParser
            saved=read(reference);entries,issues=assemble_views(saved['views'],ignore_partial_overlap=True)
            observations={o['observation_id']:o for v in saved['views'] for o in v['observations']}
            parser=EventParser();events=[]
            for entry in entries:
                selected=observations[entry['selected_observation_id']]
                entry.update(partial=selected['partial'],inspection_timestamp=selected['timestamp'],original_event_time=None)
                events.append(parser.parse(entry,battle_id=args.battle).to_dict())
            old_events=saved.get('event_candidates',saved.get('events'))
            save('battle_log',dict(views=len(saved['views']),entries=len(entries),issues=len(issues),
                exact_entries=entries==saved['entries'],exact_events=events==old_events,
                source_sha256=digest(reference),scope='cached OCR views, no pixel re-extraction'))
            if entries != saved['entries'] or events != old_events:raise ValueError('Battle Log mismatch')
        else:save('battle_log',dict(status='not_available'))
    result['protected_files_unchanged']=all(digest(source/name)==sha for name,sha in identity['inputs'].items())
    verify_seal(source)
    result['status']='complete';atomic_json(manifest,result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--battle',required=True);parser.add_argument('--source-run',required=True)
    parser.add_argument('--run-id',required=True);parser.add_argument('--replay',action='store_true')
    parser.add_argument('--compare-prefix',action='store_true')
    args=parser.parse_args();verify(args)


if __name__=='__main__':main()
