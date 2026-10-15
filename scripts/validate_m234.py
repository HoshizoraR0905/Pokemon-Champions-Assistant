"""Resumable cache-only M2.3.4 validation. Never opens videos or calls OCR."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json, fingerprint
from tracking.battle_state import BattleState
from tracking.state_engine import StateEngine, EventRecord, ordering, event_from_dict
from tracking.hidden_state import HiddenEngine
from recognition.visual_adapter import visual_events, selected_panel_side, move_alternatives
from scripts.evaluate_m233c import input_events, event_time, hud_score

FIXTURE=ROOT/'tests/fixtures/battles/m233c_semantic_review.json'
VISUAL=ROOT/'.cache/m234/visual-results.json'
CODE=['battle_events/schema.py','battle_events/parser.py','recognition/visual_adapter.py','recognition/visual_evidence.py','recognition/move_resolution.py','tracking/state_engine.py','tracking/evidence_fusion.py','tracking/reliability.py','tracking/evidence_projection.py','tracking/hidden_state.py','scripts/validate_m234.py']


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def audit():
    import cv2
    from recognition.visual_evidence import variants
    d=json.loads(VISUAL.read_text());assert d['status']=='complete';seen=set();rows=0;all_seen=set()
    checkpoint=json.loads((ROOT/'.cache/m234/visual-results-checkpoint.json').read_text());assert checkpoint['status']=='complete'
    for index,row in enumerate(d['results']+checkpoint['results']):
        req=row['request'];assert sha(ROOT/req['image'])==req['sha256'];im=cv2.imread(str(ROOT/req['image']))
        assert json.loads((ROOT/row['artifact']).read_text())=={k:row[k] for k in ('status','identity','readings','parsed')}
        assert row['identity']['backend']==sha(ROOT/'recognition/onnx_ocr.py')
        assert row['identity']['model']==sha(ROOT/'.cache/m15-onnx-medium/local-manifest.json')
        for reads in row['readings'].values():
            for r in reads:
                crop=dict(variants(im,r['box']))[r['config_id'].rsplit(':',1)[1]]
                key=fingerprint(dict(crop_sha256=hashlib.sha256(crop.tobytes()).hexdigest(),backend=row['identity']['backend'],model=row['identity']['model']))
                p=BattleArtifacts(req['battle_id'],ROOT).cache(f'm234/reads/{key}.json')
                assert json.loads(p.read_text())==dict(text=r['text'],confidence=r['confidence']);all_seen.add(str(p))
                if index<len(d['results']):seen.add(str(p));rows+=1
    baseline=json.loads((ROOT/'.cache/m234/baseline.json').read_text())
    changes=[p for p,h in baseline.items() if not (ROOT/p).exists() or sha(ROOT/p)!=h]
    # Frozen outputs, knowledge, fixtures and all M3 code stay exact. C's implementation
    # hashes are evidence of intentional production changes, not permission to reseal C.
    allowed={'tracking/state_engine.py','tracking/evidence_fusion.py','tracking/hidden_state.py','battle_events/schema.py'}
    unexpected=[p for p in changes if p not in allowed]
    assert not unexpected,unexpected
    result=dict(status='complete',visual_rows=len(d['results']),crop_readings=rows,unique_crops=len(seen),
        checkpoint_sha256=sha(ROOT/'.cache/m234/visual-results-checkpoint.json'),visual_sha256=sha(VISUAL),
        original_predictions_preserved=sum(len(rs) for row in checkpoint['results'] for rs in row['readings'].values()),all_unique_predictions=len(all_seen),
        baseline_entries=len(baseline),intentional_code_changes=changes,preserved_entries=len(baseline)-len(changes),ocr_calls=0)
    atomic_json(ROOT/'.cache/m234/audit.json',result);print(json.dumps(result),flush=True);return result


def replay(bid,mode):
    import cv2
    paths=BattleArtifacts(bid,ROOT);labels=[r for r in json.loads(FIXTURE.read_text())['hud_checkpoints'] if r['battle_id']==bid]
    queries=sorted({r['timestamp']+(.000001 if mode=='inclusive' else 0) for r in labels})
    rows=[r for r in json.loads(VISUAL.read_text())['results'] if r['request']['battle_id']==bid]
    if mode=='augmented':queries=sorted(set(queries+[r['request']['timestamp']+.000001 for r in rows]))
    held=labels if mode in {'strict','augmented'} else [max(labels,key=lambda r:r['timestamp'])] if mode=='persistence' else []
    excluded={r['sha256'] for r in held}
    events=input_events(bid)
    if mode=='augmented':
        byhash={r['request']['sha256']:r for r in rows if r['request']['kind']=='message'}
        for e in events:
            matches=[byhash[oid] for s in e['evidence'] for oid in s['observation_ids'] if oid in byhash]
            if matches:e['attributes']['move_ocr_alternatives']=move_alternatives(matches[0])
        for row in rows:
            selection=selected_panel_side(cv2.imread(str(ROOT/row['request']['image']))) if row['request']['kind']=='detail' else None
            events.extend(e.to_dict() for e in visual_events(row,selection=selection))
    events=[deepcopy(e) for e in events if event_time(e)<=max(queries) and not any(oid in excluded for s in e['evidence'] for oid in s['observation_ids'])]
    events.sort(key=lambda e:(event_time(e),0 if e['event_type']=='hud_observation' else 1,e['event_id']))
    identity=dict(mode=mode,battle_id=bid,events_sha256=fingerprint(events),labels_sha256=sha(FIXTURE),visual_sha256=sha(VISUAL) if mode=='augmented' else None,code={p:sha(ROOT/p) for p in CODE})
    target=paths.cache(f'm234/replay-{mode}.json')
    if target.exists():
        old=json.loads(target.read_text())
        if old.get('identity')==identity and old.get('status')=='complete':print(bid,mode,'reused',flush=True);return old
    progress=paths.cache(f'm234/{mode}-manifest.json');atomic_json(progress,dict(status='running',identity=identity,output=str(target.relative_to(ROOT))))
    began=time.perf_counter();initial=BattleState(bid,knowledge={'reliability_v1':True});engine=StateEngine(initial);hidden=HiddenEngine();hidden.seed(initial.to_dict());prefixes={};qindex=0
    for i,e in enumerate(events,1):
        e['attributes']['sequence']=i;engine.history.append(EventRecord(e,i,ordering(event_from_dict(e))))
    # Exclusive prefixes: a query at t excludes every event at t.
    first_t=event_time(events[0]) if events else float('inf')
    while qindex<len(queries) and queries[qindex]<=first_t:
        q=queries[qindex];prefixes[str(q)]=dict(state=initial.to_dict(),projection=None,hidden=hidden.projection());qindex+=1
    def capture(record,state):
        nonlocal qindex
        t=event_time(record.event)
        e=deepcopy(record.bindings.get('resolved_event',record.event))
        if record.bindings.get('identity'):e['actor']=deepcopy(record.bindings['identity'])
        if record.bindings.get('visual_receipt'):e['attributes']['visual_receipt']=deepcopy(record.bindings['visual_receipt'])
        hidden.apply(e,instance_id=record.bindings.get('actor',{}).get('pokemon_instance_id'),side=e['side'],sequence=record.delivery_index,application_status=record.application_status)
        next_t=event_time(events[record.delivery_index]) if record.delivery_index<len(events) else float('inf')
        while qindex<len(queries) and t<queries[qindex]<=next_t:
            q=queries[qindex];prefixes[str(q)]=dict(state=state.to_dict(),projection=engine.evidence_projection(as_of=q),hidden=hidden.projection());qindex+=1
    try:
        engine.replay(snapshot_callback=capture)
        while qindex<len(queries):
            q=queries[qindex];prefixes[str(q)]=dict(state=engine.state.to_dict(),projection=engine.evidence_projection(as_of=q),hidden=hidden.projection());qindex+=1
        scores=[dict(timestamp=l['timestamp'],rows=hud_score(l,prefixes[str(l['timestamp']+(.000001 if mode=='inclusive' else 0))]['state'])) for l in labels]
        result=dict(status='complete',identity=identity,excluded_frame_hashes=sorted(excluded),events=len(events),seconds=time.perf_counter()-began,
            status_counts=dict(Counter(r.application_status for r in engine.history)),scores=scores,prefixes=prefixes,
            history=[dict(event_id=r.event['event_id'],event_type=r.event['event_type'],timestamp=event_time(r.event),status=r.application_status,reason=r.reason,bindings=r.bindings) for r in engine.history])
        atomic_json(target,result);atomic_json(progress,dict(status='complete',identity=identity,output=str(target.relative_to(ROOT)),sha256=sha(target)))
        print(bid,mode,round(result['seconds'],2),result['status_counts'],flush=True);return result
    except Exception as exc:
        atomic_json(progress,dict(status='error',identity=identity,error=repr(exc)));raise


def summary():
    result={}
    labels=json.loads(FIXTURE.read_text())['hud_checkpoints']
    for mode in ('strict','persistence','inclusive','augmented'):
        metrics={k:Counter() for k in ('identity','hp','attributed_hp')};details=[]
        for i in range(5):
            bid=f'sample_battle_{i}';d=json.loads(BattleArtifacts(bid,ROOT).cache(f'm234/replay-{mode}.json').read_text());assert d['status']=='complete'
            assert d['identity']['code']=={p:sha(ROOT/p) for p in CODE}, 'Stale replay '+bid+' '+mode
            scores=d['scores']
            if mode=='persistence':scores=[max(scores,key=lambda r:r['timestamp'])] if sum(l['battle_id']==bid for l in labels)>1 else []
            for s in scores:
                for row in s['rows']:
                    for key in metrics:metrics[key][row[key]]+=1
            details.append(dict(battle_id=bid,events=d['events'],seconds=d['seconds']))
        result[mode]=dict(metrics={k:dict(v) for k,v in metrics.items()},battles=details)
    atomic_json(ROOT/'.cache/m234/summary.json',result);print(json.dumps(result,indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',required=True,choices=['audit','replay','summary']);p.add_argument('--battle-id');p.add_argument('--mode',choices=['strict','persistence','inclusive','augmented'],default='strict');a=p.parse_args()
    if a.stage=='audit':audit()
    elif a.stage=='summary':summary()
    else:
        if not a.battle_id:p.error('--battle-id required for scoped replay')
        replay(a.battle_id,a.mode)
