"""Prepare only missing B11/12 evidence with frozen recognizer/visual algorithms.

Run acquisition first: scripts/run_production_evaluation.py --battle
sample_battle_11 --run-id m341-actions-acquisition-v1
"""
from pathlib import Path
import argparse
import json
import os
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from speed_inference.offline import atomic_json,file_hash,RUNS
from battle_evidence.offline import run as evidence_run
from battle_evidence.visual_offline import run as visual_run
from battle_evidence.visual_v22 import VisualPhaseEstimatorV22,replay_observations,VERSION
from battle_evidence.turns import TurnReconstruction
from battle_evidence.ui_counters import CounterTimeline,reconcile_segments
from battle_artifacts import BattleArtifacts


def run(n):
    os.chdir(ROOT);battle=BattleArtifacts(f'sample_battle_{n}',ROOT).prepare()
    execution=battle.cache('evaluation/m341-actions-acquisition-v1/execution.json')
    if json.loads(execution.read_text())['status']!='complete': raise ValueError('Acquisition incomplete')
    RUNS[n]='m341-actions-acquisition-v1'
    prior=evidence_run(n,root=ROOT)
    # Same isolated routing technique as B10; do not rewrite the old global index.
    sandbox=ROOT/'.cache/m341-actions/acquisition-root';sandbox.mkdir(parents=True,exist_ok=True)
    for name in ('battle_evidence','recognition','knowledge','damage','tracking','speed_inference','battle_events','battle_artifacts.py'):
        p=sandbox/name
        if not p.exists():p.symlink_to(ROOT/name)
    (sandbox/'.cache').mkdir(exist_ok=True)
    for name in ('battles','m15-onnx-medium'):
        p=sandbox/'.cache'/name
        if not p.exists():p.symlink_to(ROOT/'.cache'/name)
    atomic_json(sandbox/'.cache/m34e/battle-index.json',[prior]);os.chdir(sandbox)
    try: prediction=visual_run(n,profile='v2')
    finally: os.chdir(ROOT)
    p=json.loads((ROOT/prediction).read_text());estimator=VisualPhaseEstimatorV22(battle.battle_id)
    for o in replay_observations(p):estimator.consume(o)
    visual=estimator.export();turns=TurnReconstruction(battle.battle_id);ct=CounterTimeline()
    for e in p['reconstruction']['ledger']:turns.consume(e)
    for o in p['counter_observations']:ct.consume(o)
    live=[e for e in turns.ledger if e.get('timestamp') is not None and not e.get('source_retracted') and not e.get('source_revision_requires_review')]
    visual['segments']=reconcile_segments(visual['segments'],ct,sorted(live,key=lambda e:e['timestamp']))
    turns.attach_visual(visual['segments'])
    source=ROOT/prediction;identity=dict(version=VERSION,input=str(source),input_sha256=file_hash(source),
        dependencies={str(f):file_hash(f) for f in [Path(__file__),ROOT/'battle_evidence/visual_v22.py',ROOT/'battle_evidence/visual.py',ROOT/'battle_evidence/turns.py',ROOT/'battle_evidence/ui_counters.py']})
    dest=battle.cache('m34-visual-v22');dest.mkdir(exist_ok=True)
    output=dest/'visual-evidence.json';manifest=dest/'manifest.json'
    if manifest.exists():
        old=json.loads(manifest.read_text())
        if old['identity']!=identity:raise ValueError('Preserve old v2.2 output before changed-input replay')
        if old['status']=='complete' and output.exists() and old['output_hash']==file_hash(output):return str(output)
    atomic_json(manifest,dict(status='running',identity=identity))
    result=dict(schema=VERSION,battle_id=battle.battle_id,input_identity=identity,visual=visual,reconstruction=turns.export(),
        counter_observations=ct.observations,counter_constraints=ct.constraints,
        scope='Frozen v2.2 first-pass segmentation; no human timing benchmark or effect-continuity certification')
    atomic_json(output,result);atomic_json(manifest,dict(status='complete',identity=identity,output_hash=file_hash(output)))
    return str(output)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',type=int,required=True,choices=[11,12])
    print(run(p.parse_args().battle),flush=True)
