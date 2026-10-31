"""Instrument the real production packaging function using sealed live observations.

No decoding/OCR; isolated output paths; nested spans report exclusive/inclusive
wall time separately. Use a new experiment ID after implementation changes.
"""
import argparse
from collections import defaultdict
from functools import wraps
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.fast_video import digest
from recognition.video_sampling import atomic_json


def run(battle,source_run,experiment):
    import recognition.event_report as report
    import tracking.state_engine as state
    import tracking.battle_state as bs
    import tracking.hp_causes as hp
    from speed_order.core import knowledge
    owner=BattleArtifacts(battle,ROOT);source=owner.cache('event-driven/'+source_run)
    report.verify_seal(source);data=json.loads((source/'observations.json').read_text())
    out=owner.cache('diagnosis/'+experiment);target=owner.report('diagnosis/'+experiment)
    out.mkdir(parents=True,exist_ok=True);path=out/'profile-manifest.json'
    identity=dict(input_sha256=digest(source/'observations.json'),script_sha256=digest(Path(__file__)),
        sources={str(p.relative_to(ROOT)):digest(p) for directory in ['tracking','recognition','battle_events'] for p in (ROOT/directory).glob('*.py')})
    if path.exists():
        prior=json.loads(path.read_text())
        if prior['identity']!=identity:raise ValueError('Changed profiling identity; use a new experiment ID')
        if prior['status']=='complete':print('Reused completed profile',out);return
        raise ValueError('Inspect interrupted profile before retrying in a new experiment')
    source_manifest=json.loads((source/'manifest.json').read_text())
    atomic_json(out/'manifest.json',dict(identity=source_manifest['identity'],reference_previously_available=False))
    # Packaging seals the observation input too; link the immutable saved input
    # before timing rather than reacquiring it or changing the original file.
    import os
    if not (out/'observations.json').exists():os.link(source/'observations.json',out/'observations.json')
    m=dict(status='running',identity=identity,source_run=source_run,experiment=experiment,
        caveat='Instrumented saved-observation component profile, not a full pipeline timing; static knowledge prewarmed.')
    atomic_json(path,m)
    for name in identity['sources']:
        p=out/'source'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/name).read_bytes())
    knowledge();totals=defaultdict(lambda:dict(calls=0,inclusive_seconds=0.,exclusive_seconds=0.));stack=[];restores=[]
    def patch(obj,name,label):
        original=getattr(obj,name)
        @wraps(original)
        def wrapped(*args,**kwargs):
            key=label(*args,**kwargs) if callable(label) else label
            node=[time.perf_counter(),0.];stack.append(node)
            try:return original(*args,**kwargs)
            finally:
                elapsed=time.perf_counter()-node[0];stack.pop();row=totals[key]
                row['calls']+=1;row['inclusive_seconds']+=elapsed;row['exclusive_seconds']+=elapsed-node[1]
                if stack:stack[-1][1]+=elapsed
        setattr(obj,name,wrapped);restores.append((obj,name,original))
    patch(report,'video_events','event_adaptation')
    patch(state.StateEngine,'replay','state_replay')
    patch(state,'hash_state','state_hash')
    patch(state,'deepcopy',lambda value,*a,**kw:'whole_state_copy' if isinstance(value,bs.BattleState) else 'payload_copy')
    patch(bs.BattleState,'to_dict','state_dataclass_serialization')
    patch(state.StateEngine,'to_dict','engine_export_serialization')
    patch(hp,'enrich','hp_causal_enrichment')
    patch(report,'atomic_json',lambda p,*a,**kw:'write_json:'+Path(p).name)
    patch(report,'write_viewer','viewer_export')
    patch(json,'dumps','json_serialization')
    began=time.perf_counter();error=None
    try:result=report.reconstruct_and_package(owner,out,target,data['observations'],data['roster'],data['occurrences'])
    except BaseException as exc:error=exc
    finally:
        elapsed=time.perf_counter()-began
        for obj,name,original in reversed(restores):setattr(obj,name,original)
        m.update(status='failed' if error else 'complete',wall_seconds=elapsed,spans=dict(totals),error=repr(error) if error else None)
        if not error:
            actual=json.loads((out/'replay.json').read_text());expected=json.loads((source/'replay.json').read_text())
            m['exact_saved_replay']=actual==expected
        atomic_json(path,m)
    if error:raise error
    print(json.dumps({k:v for k,v in m.items() if k not in {'identity'}},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--battle',required=True);p.add_argument('--source-run',required=True)
    p.add_argument('--experiment',required=True);a=p.parse_args();run(a.battle,a.source_run,a.experiment)
