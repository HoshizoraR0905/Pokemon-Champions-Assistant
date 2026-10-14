"""Replay the saved M2.1 events; never load OCR or decode a video."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tracking.battle_state import from_dict
from tracking.state_engine import StateEngine, hash_state
from tracking.state_summary import summary

ROOT=Path(__file__).resolve().parents[1]


def run(events_path,initial_path):
    payload=json.loads(events_path.read_text());initial=json.loads(initial_path.read_text())
    engine=StateEngine(from_dict(initial['state']))
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
    p.add_argument('--events',type=Path,default=ROOT/'reports/M2.1-battle-log-events.json')
    p.add_argument('--initial',type=Path,default=ROOT/'tests/fixtures/m22_initial_context.json')
    p.add_argument('--output',type=Path,default=ROOT/'reports/M2.2-battle-state.json')
    p.add_argument('--snapshots',type=Path,default=ROOT/'reports/M2.2-state-snapshots.json')
    p.add_argument('--summary',type=Path,default=ROOT/'reports/M2.2-battle-state.txt')
    args=p.parse_args();engine,snapshots=run(args.events,args.initial)
    result=engine.to_dict();result['input_provenance']={
        str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (args.events,args.initial)}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    args.snapshots.write_text(json.dumps({'schema_version':1,'snapshots':snapshots},ensure_ascii=False,indent=2)+'\n')
    text=summary(engine);args.summary.write_text(text);print(text,end='')

if __name__=='__main__':main()
