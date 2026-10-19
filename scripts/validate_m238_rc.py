"""Bounded M2.3.8 release-candidate validation, one Battle 5 run.

Runs the production event-driven entry point with untouched rules. Instrumentation
captures prefix slot state only. Frozen references are consulted after prediction.
"""
import argparse
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import resource
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.fast_video import analyze,digest
from recognition.video_sampling import atomic_json
from tracking.state_engine import StateEngine
from scripts.replay_m238t import slot_snapshot,intervals

OWNER=BattleArtifacts('sample_battle_5',ROOT)
RUN='m238-rc-b5-v1'
PIPE=OWNER.cache('event-driven/'+RUN)
META=OWNER.cache('release-candidate/'+RUN)
REPORT=OWNER.report('M2.3.8-release-candidate-v1')
SLOTS=('self:left','self:right','opponent:left','opponent:right')


def read(p):return json.loads(Path(p).read_text())


def run():
    if not (META/'preservation.json').exists():raise ValueError('Freeze preservation inventory first')
    if (PIPE/'manifest.json').exists():raise FileExistsError('Existing run: inspect checkpoint; never silently restart')
    states=[dict(timestamp=0,event_id=None,slots={k:dict(status='unknown',instance_id=None,episode_id=None) for k in SLOTS})]
    signature=None;replay=StateEngine.replay
    def observed_replay(engine,*args,**kwargs):
        nonlocal signature
        callback=kwargs.get('snapshot_callback')
        def observe(record,state):
            nonlocal signature
            t=record.event['attributes']['observation_time'];slots=slot_snapshot(state,t)
            sig=json.dumps({k:{a:v for a,v in x.items() if a!='evidence'} for k,x in slots.items()},sort_keys=True)
            if sig!=signature:
                states.append(dict(timestamp=t,event_id=record.event['event_id'],slots=slots));signature=sig
            if record.delivery_index%100==0:atomic_json(META/'partial-slots.json',states)
            if callback:callback(record,state)
        kwargs['snapshot_callback']=observe
        return replay(engine,*args,**kwargs)
    began=time.monotonic()
    atomic_json(META/'run-status.json',dict(status='running',kind='cold full-recording event-driven pipeline',started_unix=time.time(),runner_sha256=digest(Path(__file__))))
    try:
        with patch.object(StateEngine,'replay',observed_replay):
            result=analyze(OWNER.video(),run_id=RUN,event_driven=True)
        atomic_json(META/'slots.json',states)
        atomic_json(META/'run-status.json',dict(status='complete',kind='cold full-recording event-driven pipeline',wall_seconds=time.monotonic()-began,
            process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            peak_memory_scope='macOS ru_maxrss, peak resident memory of Python process, not aggregate process-tree peak',runner_sha256=digest(Path(__file__)),result_status=result['status']))
    except BaseException as exc:
        atomic_json(META/'partial-slots.json',states)
        atomic_json(META/'run-status.json',dict(status='failed',error=repr(exc),wall_seconds=time.monotonic()-began,resume='Inspect production checkpoint and source identity before main.py --resume; preserve this failed attempt'))
        raise


def brief(h):
    e=h['bindings'].get('resolved_event',h['event']);a=e['attributes']
    return dict(event_id=e['event_id'],timestamp=a.get('observation_time'),kind=e['event_type'],side=e['side'],raw=e['original_text'],
        actor=e.get('actor'),target=e.get('target'),status=h['application_status'],reason=h['reason'],uncertainty=e['uncertainty'],
        instance_id=h['bindings'].get('actor',{}).get('pokemon_instance_id'),slot=a.get('slot'),
        episode_id=h['bindings'].get('active_episode_id'),bindings=h['bindings'],evidence=e['evidence'])


def metrics(history):
    moves=[h for h in history if h['event']['event_type']=='move_execution']
    bound=[h for h in moves if h['bindings'].get('resolved_event',h['event'])['attributes'].get('actor_instance_id')]
    transitions=[h for h in history if h['event']['event_type'] in {'send_out','switch_out','faint','position_change'}]
    return dict(events=len(history),event_types=dict(Counter(h['event']['event_type'] for h in history)),
        receipts=dict(Counter(h['application_status'] for h in history)),
        deferred_causes=dict(Counter(h['reason'] for h in history if h['application_status']=='deferred')),
        moves=dict(candidates=len(moves),bound=len(bound),bound_fraction=len(bound)/len(moves) if moves else None,
            receipts=dict(Counter(h['application_status'] for h in moves))),
        transitions=dict(candidates=len(transitions),receipts=dict(Counter(h['application_status'] for h in transitions))))


def links(event,report_dir):
    out=[]
    for p in event.get('evidence',[]):
        details=p.get('details',{});image=details.get('image')
        if image:out.append(dict(timestamp=details.get('timestamp'),source_id=p['source_id'],image=os.path.relpath(ROOT/image,report_dir)))
    return out


def build_report():
    from scripts.report_m238_rc import build
    return build()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',required=True,choices=['run','report']);args=parser.parse_args()
    run() if args.stage=='run' else build_report()
