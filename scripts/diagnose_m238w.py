"""Replay sealed events under current rules in an isolated diagnostic namespace.

No recognition acquisition, annotation import, or first-pass output mutation.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.event_report import verify_seal
from recognition.fast_video import digest
from recognition.video_sampling import atomic_json
from scripts.run_production_evaluation import runtime_sources
from tracking.battle_state import from_dict
from tracking.state_engine import StateEngine,EventRecord


def forbidden(*args,**kwargs):
    raise AssertionError('Diagnostic replay cannot acquire recognition')


def diagnose(owner,run_id,diagnostic_id):
    source=owner.cache('event-driven/'+run_id)
    target=owner.cache('evaluation/'+diagnostic_id)
    if source.resolve()==target.resolve():raise ValueError('Separate diagnostic namespace required')
    verify_seal(source)
    identity=dict(replay_sha256=digest(source/'replay.json'),sources=runtime_sources(),
                  runner_sha256=digest(Path(__file__)))
    manifest=target/'diagnostic-manifest.json'
    if manifest.exists():
        previous=json.loads(manifest.read_text())
        if previous['identity']!=identity:raise ValueError('Diagnostic identity changed; choose a new ID')
        if previous['status']=='complete':
            for name,h in previous['outputs'].items():
                if digest(target/name)!=h:raise ValueError('Diagnostic output changed: '+name)
            return json.loads((target/'summary.json').read_text())
    elif target.exists():
        raise ValueError('Existing namespace without diagnostic manifest; choose a new ID')
    target.mkdir(parents=True,exist_ok=True)
    atomic_json(manifest,dict(status='running',identity=identity,source_run=run_id,
                             diagnostic_only=True,recognition_calls=0))
    started=time.monotonic()
    try:
        original=json.loads((source/'replay.json').read_text())
        engine=StateEngine(from_dict(original['initial_state']))
        engine.history=[EventRecord(deepcopy(h['event']),h['delivery_index'],deepcopy(h['ordering']),
                                   retracted=h.get('retracted',False)) for h in original['history']]
        def progress(record,state):
            if record.delivery_index%100==0:
                atomic_json(target/'progress.json',dict(completed=record.delivery_index,total=len(engine.history)))
                print(f'Diagnostic replay: {record.delivery_index}/{len(engine.history)}',flush=True)
        with ExitStack() as stack:
            for name in ['recognition.fast_video.CachedOCR.read','recognition.fast_video.CachedOCR.predict',
                         'recognition.fast_video.CachedIcons.identify','recognition.fast_video.decoded_frames',
                         'cv2.VideoCapture','cv2.imread']:
                stack.enter_context(patch(name,forbidden))
            engine.replay(snapshot_callback=progress)
        changes=[];regressions=[]
        for old,new in zip(original['history'],engine.history):
            before=(old['application_status'],old['reason']);after=(new.application_status,new.reason)
            if before!=after:
                e=new.bindings.get('resolved_event',new.event)
                change=dict(event_id=e['event_id'],timestamp=e['attributes']['observation_time'],
                            original_text=e['original_text'],before=list(before),after=list(after))
                changes.append(change)
                if before[0].startswith('applied') and not after[0].startswith('applied'):regressions.append(change)
        violations=[side for side,team in engine.state.sides.items()
                    if len(team.active_slots.values())!=len(set(team.active_slots.values()))]
        summary=dict(diagnostic_only=True,recognition_calls=0,source_run=run_id,
                     records=len(engine.history),wall_seconds=time.monotonic()-started,
                     before=dict(Counter(h['application_status'] for h in original['history'])),
                     after=dict(Counter(h.application_status for h in engine.history)),
                     changes=changes,applied_status_regressions=regressions,
                     duplicate_active_instance_violations=violations,
                     limitations=['Saved event reparse only; command detection/scheduling are unchanged.',
                                  'This corrected diagnostic does not replace first-pass acceptance.'])
        atomic_json(target/'replay.json',engine.to_dict())
        atomic_json(target/'summary.json',summary)
        verify_seal(source)
        if digest(source/'replay.json')!=identity['replay_sha256']:raise ValueError('Source replay changed')
        atomic_json(manifest,dict(status='complete',identity=identity,source_run=run_id,
                    diagnostic_only=True,recognition_calls=0,
                    outputs={name:digest(target/name) for name in ['replay.json','summary.json']}))
        return summary
    except BaseException as exc:
        atomic_json(manifest,dict(status='failed',identity=identity,error=repr(exc),source_run=run_id))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--battle',required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--diagnostic-id',required=True)
    args=parser.parse_args()
    result=diagnose(BattleArtifacts(args.battle),args.run_id,args.diagnostic_id)
    print(json.dumps({k:v for k,v in result.items() if k!='changes'},ensure_ascii=False,indent=2))
