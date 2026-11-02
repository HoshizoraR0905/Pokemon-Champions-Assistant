"""Versioned, isolated saved-event comparison; never acquires video/OCR.

Run one battle/implementation at a time. A completed identical stage is reused;
partial streams survive interruption. Use another experiment for changed code.
"""
import argparse
from collections import defaultdict
from dataclasses import asdict
from functools import wraps
import hashlib
import json
from pathlib import Path
import platform
import resource
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
RUNS={20:'fresh-b20-postfix-v1',21:'fresh-b21-context-v1',22:'fresh-b22-ditto-20261030-v1',23:'mega-b23-20261030-v1',24:'fresh-b24-20261101-v1'}
TAG='pre-state-engine-refactor-20261101'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def read(p):return json.loads(p.read_text())
def atomic(p,value):
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)

def run(battle,stage,experiment):
    source=ROOT if stage=='refactor' else ROOT/'.cache/baselines'/TAG/'source'
    folder=ROOT/f'.cache/battles/sample_battle_{battle}/diagnosis'/experiment/stage
    packet=ROOT/f'.cache/battles/sample_battle_{battle}/event-driven'/RUNS[battle]/'replay.json'
    identity=dict(input_sha256=sha(packet),script_sha256=sha(Path(__file__)),
        sources={str(p.relative_to(source)):sha(p) for directory in ('tracking','battle_events') for p in (source/directory).glob('*.py')})
    path=folder/'manifest.json'
    if path.exists():
        prior=read(path)
        if prior['identity']==identity and prior['status']=='complete':print('Reused complete',battle,stage,flush=True);return
        raise ValueError('Preserve changed/incomplete experiment; inspect manifest before choosing a new namespace')
    folder.mkdir(parents=True,exist_ok=True);(folder/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    sys.path=[str(source)]+[p for p in sys.path if p and Path(p).resolve()!=ROOT]
    import tracking.state_engine as se
    import tracking.battle_state as bs
    import tracking.hp_causes as hp
    import tracking.active_continuity as continuity
    import tracking.identity_ledger as ledger
    from tracking.mechanic_rules import MechanicRules
    assert Path(se.__file__).is_relative_to(source)
    p=read(packet);config=p['policy'];config['allowed_uncertainties']=tuple(config['allowed_uncertainties'])
    engine=se.StateEngine(bs.from_dict(p['initial_state']),se.ApplicationPolicy(**config),mechanic_rules=MechanicRules(**p.get('mechanic_rules',{})))
    engine.history=[se.EventRecord(**r) for r in p['history']]
    del p
    manifest=dict(status='running',pid=__import__('os').getpid(),identity=identity,battle=battle,stage=stage,
        source=str(source),input=str(packet.relative_to(ROOT)),hardware=dict(platform=platform.platform(),python=sys.version),
        scope='Bulk saved-production-event replay under baseline/refactor code; no recognition; original parser outputs and initial inputs unchanged',
        callback_scope='Every receipt decision projection; legacy full-state checkpoints every100 and non-HUD actions; callback time separately excluded from core spans',
        completed_receipts=0,spans={})
    atomic(path,manifest)
    totals=defaultdict(lambda:dict(calls=0,wall_inclusive=0.,wall_exclusive=0.,cpu_inclusive=0.,cpu_exclusive=0.));stack=[];restores=[]
    def patch(obj,name,label):
        old=getattr(obj,name)
        @wraps(old)
        def timed(*args,**kwargs):
            key=label(*args,**kwargs) if callable(label) else label
            node=[time.perf_counter(),time.process_time(),0.,0.];stack.append(node)
            try:return old(*args,**kwargs)
            finally:
                wall=time.perf_counter()-node[0];cpu=time.process_time()-node[1];stack.pop();r=totals[key]
                r['calls']+=1;r['wall_inclusive']+=wall;r['cpu_inclusive']+=cpu
                r['wall_exclusive']+=wall-node[2];r['cpu_exclusive']+=cpu-node[3]
                if stack:stack[-1][2]+=wall;stack[-1][3]+=cpu
        setattr(obj,name,timed);restores.append((obj,name,old))
    patch(se,'deepcopy',lambda value,*a,**k:'whole_state_copy' if isinstance(value,bs.BattleState) else 'payload_copy')
    patch(se,'hash_state','state_hash');patch(bs.BattleState,'to_dict','state_export')
    patch(hp,'enrich','hp_enrich');patch(continuity,'depart','departure');patch(continuity,'enter','entry')
    patch(ledger,'unique_roster_return','persistent_return')
    began=time.perf_counter();cpu_began=time.process_time();callback_wall=callback_cpu=0.;count=0;intervals=[]
    last=[began,cpu_began,0.,0.,0];error=None
    with (folder/'prefixes.jsonl').open('x',buffering=1) as stream:
        def callback(record,state):
            nonlocal callback_wall,callback_cpu,count
            t=time.perf_counter();c=time.process_time();count+=1
            decision=engine.decision_state()
            checkpoint=count%100==0 or record.event['event_type']!='hud_observation'
            legacy=None
            if checkpoint:
                legacy=record.state_hash if stage=='baseline' else digest(state.to_dict())
            stream.write(json.dumps(dict(index=count,event_id=record.event['event_id'],status=record.application_status,
                reason=record.reason,decision_hash=digest(decision),legacy_state_hash=legacy),ensure_ascii=False,separators=(',',':'))+'\n')
            callback_wall+=time.perf_counter()-t;callback_cpu+=time.process_time()-c
            if count%100==0:
                now=time.perf_counter();cpu=time.process_time()
                interval=dict(start_receipt=last[4],end_receipt=count,
                    wall_core=now-last[0]-(callback_wall-last[2]),cpu_core=cpu-last[1]-(callback_cpu-last[3]))
                intervals.append(interval);last[:]=[now,cpu,callback_wall,callback_cpu,count]
                manifest.update(completed_receipts=count,elapsed_wall=now-began,callback_wall=callback_wall,intervals=intervals,spans=dict(totals))
                atomic(path,manifest);print(battle,stage,count,'/',len(engine.history),'wall',round(now-began,2),flush=True)
        try:engine.replay(snapshot_callback=callback)
        except BaseException as exc:error=exc
    wall=time.perf_counter()-began;cpu=time.process_time()-cpu_began
    for obj,name,old in reversed(restores):setattr(obj,name,old)
    manifest.update(status='failed' if error else 'complete',error=repr(error) if error else None,
        replay_wall=wall,replay_cpu=cpu,callback_wall=callback_wall,callback_cpu=callback_cpu,
        core_wall=wall-callback_wall,core_cpu=cpu-callback_cpu,spans=dict(totals),completed_receipts=count,
        peak_process_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024))
    if not error:
        export=engine.to_dict();atomic(folder/'replay.json',export)
        projection=engine.hp_resolutions();atomic(folder/'hp-resolutions.json',projection)
        manifest.update(final_state_digest=digest(export['state']),
            receipt_semantics_digest=digest([{k:v for k,v in r.items() if k!='state_hash'} for r in export['history']]),
            hp_resolution_digest=digest(projection),outputs={p.name:sha(p) for p in [folder/'replay.json',folder/'hp-resolutions.json',folder/'prefixes.jsonl']},
            input_unchanged=sha(packet)==identity['input_sha256'])
        if hasattr(engine.state,'compact_export'):
            compact=engine.state.compact_export();atomic(folder/'compact-state.json',compact)
            manifest['compact_current_bytes']=len(json.dumps(compact['current'],ensure_ascii=False,separators=(',',':')).encode())
            manifest['legacy_state_bytes']=len(json.dumps(export['state'],ensure_ascii=False,separators=(',',':')).encode())
    atomic(path,manifest);print(battle,stage,manifest['status'],'core wall',round(manifest['core_wall'],3),flush=True)
    if error:raise error

def compare(battle,experiment):
    folder=ROOT/f'.cache/battles/sample_battle_{battle}/diagnosis'/experiment
    a,b=[read(folder/k/'manifest.json') for k in ('baseline','refactor')]
    assert a['status']==b['status']=='complete' and a['identity']['input_sha256']==b['identity']['input_sha256']
    mismatches=[]
    for key in ('final_state_digest','receipt_semantics_digest','hp_resolution_digest'):
        if a[key]!=b[key]:mismatches.append(key)
    pa,pb=[(folder/k/'prefixes.jsonl').read_text().splitlines() for k in ('baseline','refactor')]
    if pa!=pb:mismatches.append('per-receipt current decision and checkpoint states')
    result=dict(battle=battle,status='passed' if not mismatches else 'failed',mismatches=mismatches,
        receipts=a['completed_receipts'],core_wall_speedup=a['core_wall']/b['core_wall'],
        baseline=a,refactor=b,scope='Same saved inputs, complete final legacy state/receipts/HP projection, every decision prefix and full-state checkpoints; hash-profile difference excluded')
    atomic(folder/'comparison.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ('baseline','refactor')},indent=2))
    if mismatches:raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',type=int,choices=RUNS,required=True)
    p.add_argument('--stage',choices=['baseline','refactor','compare'],required=True)
    p.add_argument('--experiment',default='state-architecture-20261101-v1');a=p.parse_args()
    if a.stage=='compare':compare(a.battle,a.experiment)
    else:run(a.battle,a.stage,a.experiment)
