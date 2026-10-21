"""Replay maintained compatible historical diagnostics; preserve original seals."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.fast_video import digest
from recognition.video_sampling import atomic_json, fingerprint
from recognition.event_report import verify_seal
from tracking.state_engine import StateEngine, EventRecord
from scripts.run_production_evaluation import runtime_sources


def main():
    target=ROOT/'reports/M2.4-historical-preservation.json'
    identity=dict(runtime=fingerprint(runtime_sources()),validator=digest(Path(__file__)))
    previous=json.loads(target.read_text()) if target.exists() else {}
    result=previous if previous.get('identity')==identity else dict(identity=identity,status='running',checks=[],errors=[])
    if result['status']=='complete':print('Reuse completed compatible historical validation');return
    result['status']='running';atomic_json(target,result)
    prior=json.loads((ROOT/'.cache/battles/sample_battle_8/evaluation/m239-task-v1/cross-battle-regressions.json').read_text())
    for battle in ('sample_battle_5','sample_battle_6','sample_battle_7'):
        owner=BattleArtifacts(battle);folder=owner.cache('evaluation/m238-hud-authority-v2');source=folder/'replay.json'
        sha=digest(source);expected=next(b['replay_sha256'] for b in prior['battles'] if b['battle_id']==battle)
        if sha!=expected:raise ValueError('Previously accepted compatible historical fixture changed: '+battle)
        if any(c.get('battle_id')==battle and c.get('source_sha256')==sha for c in result['checks']):
            print(battle+': reuse completed matching replay validation',flush=True);continue
        print(battle+': replay compatible saved events; no acquisition',flush=True);began=time.monotonic()
        saved=json.loads(source.read_text());engine=StateEngine.from_dict({**saved,'history':[]})
        engine.history=[EventRecord(**deepcopy(r)) for r in saved['history']]
        def progress(record,state):
            if record.delivery_index%100==0:
                result['progress']=dict(battle_id=battle,record=record.delivery_index,total=len(engine.history),seconds=time.monotonic()-began)
                atomic_json(target,result);print(f'{battle}: {record.delivery_index}/{len(engine.history)}',flush=True)
        engine.replay(snapshot_callback=progress);actual=json.loads(json.dumps(engine.to_dict()))
        row=dict(battle_id=battle,source=str(source.relative_to(ROOT)),seconds=time.monotonic()-began,source_sha256=sha,
            source_unchanged=digest(source)==sha,final_state_equal=actual['state']==saved['state'],
            state_hash_equal=actual['state_hash']==saved['state_hash'],history_equal=actual['history']==saved['history'],event_count=len(saved['history']))
        if not all(row[k] for k in ('source_unchanged','final_state_equal','state_hash_equal','history_equal')):
            result['errors'].append(dict(battle=battle,error='compatible historical semantics differ'))
        result['checks'].append(row);atomic_json(target,result)
        print(f'{battle}: completed in {time.monotonic()-began:.1f}s',flush=True)
    seals=prior['original_acquisitions']['seals']+[
        dict(seal=str(BattleArtifacts('sample_battle_8').cache('event-driven/m239-production-first-pass-v1/video-only-seal.json').relative_to(ROOT))),
        dict(seal=str(BattleArtifacts('sample_battle_9').cache('event-driven/m239-message-baseline-v1/video-only-seal.json').relative_to(ROOT)))]
    result['original_seals']=[]
    for entry in seals:
        path=ROOT/entry['seal'];verify_seal(path.parent)
        if entry.get('seal_sha256') and digest(path)!=entry['seal_sha256']:raise ValueError('Original seal bytes changed')
        result['original_seals'].append(dict(path=entry['seal'],unchanged=True))
    result['status']='failed' if result['errors'] else 'complete';result.pop('progress',None);atomic_json(target,result)
    print(json.dumps(result,indent=2));raise SystemExit(bool(result['errors']))

if __name__=='__main__':main()
