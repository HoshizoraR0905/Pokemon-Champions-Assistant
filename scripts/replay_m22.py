"""Replay the saved M2.1 events; never load OCR or decode a video."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from battle_artifacts import BattleArtifacts, add_arguments, check_event_ownership
from tracking.battle_state import from_dict
from tracking.state_engine import StateEngine, hash_state
from tracking.state_summary import summary

ROOT=Path(__file__).resolve().parents[1]


def run(events_path,initial_path,*,mechanic_rules=None):
    payload=json.loads(events_path.read_text());initial=json.loads(initial_path.read_text())
    engine=StateEngine(from_dict(initial['state']),mechanic_rules=mechanic_rules)
    snapshots=[]
    for e in payload['event_candidates']:
        record=engine.apply(e)
        snapshots.append({'event_id':e['event_id'],'log_order':e['log_order'],'application_status':record.application_status,
                          'state_hash':hash_state(engine.state),'state':engine.state.to_dict()})
    value=engine.to_dict()
    clone=StateEngine.from_dict(value)
    assert clone.to_dict()==value, 'Serialized deterministic replay failed'
    for e in payload['event_candidates']:engine.apply(e)
    assert engine.to_dict()==value, 'Repeated delivery changed state/history'
    return engine,snapshots


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--events',type=Path)
    p.add_argument('--initial',type=Path)
    p.add_argument('--output',type=Path)
    p.add_argument('--snapshots',type=Path)
    p.add_argument('--summary',type=Path)
    add_arguments(p)
    args=p.parse_args();paths=BattleArtifacts.select(args.battle_id,args.video,default='sample_battle_2').prepare()
    args.events=args.events or paths.report('M2.1-battle-log-events.json')
    args.initial=args.initial or paths.input('m22_initial_context.json')
    paths.check_identity(json.loads(args.initial.read_text())['state']['battle_id'])
    for key,name in [('output','M2.2-battle-state.json'),('snapshots','M2.2-state-snapshots.json'),('summary','M2.2-battle-state.txt')]:
        setattr(args,key,paths.guard_output(getattr(args,key) or paths.report(name)))
    check_event_ownership(paths,json.loads(args.events.read_text()))
    engine,snapshots=run(args.events,args.initial)
    result=engine.to_dict();result['input_provenance']={
        str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (args.events,args.initial)}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    args.snapshots.write_text(json.dumps({'schema_version':1,'snapshots':snapshots},ensure_ascii=False,indent=2)+'\n')
    text=summary(engine);args.summary.write_text(text);print(text,end='')

if __name__=='__main__':main()
