"""Frozen saved-state component measurements, separate from production timings.

No replay, image access, model calls, packaging or performance modifications.
Run one battle per process; each completed operation is atomically checkpointed.
"""
import argparse
from copy import deepcopy
import cProfile
import hashlib
import json
from pathlib import Path
import platform
import pstats
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
RUNS={23:'mega-b23-20261030-v1',24:'fresh-b24-20261101-v1'}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def atomic(path,data):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)

def run(battle,repeats,experiment):
    source=ROOT/f'.cache/battles/sample_battle_{battle}/event-driven'/RUNS[battle]
    if not experiment.replace('-','').isalnum():raise ValueError('Invalid experiment name')
    output=ROOT/f'.cache/battles/sample_battle_{battle}/diagnosis'/experiment/'manifest.json'
    identity=dict(script=sha(Path(__file__)),replay=sha(source/'replay.json'),repeats=repeats,
        frozen={str(p.relative_to(source/'source')):sha(p) for p in (source/'source').rglob('*.py')})
    if output.exists():
        old=json.loads(output.read_text())
        if old['identity']==identity and old['status']=='complete':print('Reused',output);return
        raise ValueError('Preserve previous component profile; inspect manifest and select a new experiment namespace')
    # Use frozen tracking/battle_events packages; no current repository fallback.
    sys.path=[str(source/'source')]+[p for p in sys.path if p and Path(p).resolve()!=ROOT]
    import tracking.battle_state as bs
    import tracking.state_engine as se
    import tracking.hp_causes as hp
    assert Path(se.__file__).is_relative_to(source/'source')
    payload=json.loads((source/'replay.json').read_text())
    output.parent.mkdir(parents=True,exist_ok=True)
    (output.parent/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    result=dict(status='running',identity=identity,battle=battle,
        scope='initial/final saved-state microbenchmarks; not production replay or historical wall attribution',
        python=sys.version,platform=platform.platform(),measurements={},
        timing=f'perf_counter plus process_time, warm process, default GC, {repeats} repetitions; setup/input loading and warmup excluded')
    atomic(output,result)
    def measure(label,fn,setup=lambda:None):
        fn(setup())  # one unmeasured warmup
        times=[];cpu=[]
        for _ in range(repeats):
            arg=setup();began=time.perf_counter();cpu_began=time.process_time();value=fn(arg)
            cpu.append(time.process_time()-cpu_began);times.append(time.perf_counter()-began)
            del value
        result['measurements'][label]=dict(samples_seconds=times,median_seconds=statistics.median(times),
            minimum_seconds=min(times),maximum_seconds=max(times),cpu_samples_seconds=cpu,median_cpu_seconds=statistics.median(cpu))
        atomic(output,result);print(battle,label,round(statistics.median(times),6),flush=True)
    states={}
    try:
        for stage in ('initial_state','state'):
            state=bs.from_dict(payload[stage]);states[stage]=state
            assert state.to_dict()==payload[stage], 'Frozen schema must round-trip exact saved state'
            data=state.to_dict()
            measure(stage+':deepcopy',lambda _:deepcopy(state))
            measure(stage+':to_dict',lambda _:state.to_dict())
            measure(stage+':json_dumps_sorted',lambda _:json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode())
            measure(stage+':hash_state',lambda _:se.hash_state(state))
        # A single full-prefix enrichment operation over a copied final state.
        # Measures that terminal workload, not all prefix enrichments in replay.
        engine=se.StateEngine(states['initial_state']);engine.history=[se.EventRecord(**r) for r in payload['history']]
        def setup():engine.state=deepcopy(states['state']);return engine
        measure('final_prefix:hp_enrich',lambda e:hp.enrich(e,e.history),setup)
        profiler=cProfile.Profile();profiler.enable()
        deepcopy(states['state']);se.hash_state(states['state'])
        profiler.disable()
        stats=pstats.Stats(profiler)
        result['copy_hash_profile_top_cumulative']=[dict(file=k[0],line=k[1],function=k[2],
            primitive_calls=v[0],total_calls=v[1],self_seconds=v[2],cumulative_seconds=v[3])
            for k,v in sorted(stats.stats.items(),key=lambda kv:kv[1][3],reverse=True)[:20]]
        assert sha(source/'replay.json')==identity['replay']
        result.update(status='complete',source_replay_unchanged=True,finished_epoch=time.time(),
            loaded_source_modules={k:v.__file__ for k,v in sys.modules.items() if k.startswith(('tracking','battle_events')) and getattr(v,'__file__',None)})
    except BaseException as exc:
        result.update(status='failed',error=repr(exc));atomic(output,result);raise
    atomic(output,result)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',type=int,choices=RUNS,required=True)
    p.add_argument('--repeats',type=int,default=5)
    p.add_argument('--experiment',default='runtime-components-v2');a=p.parse_args();run(a.battle,a.repeats,a.experiment)
