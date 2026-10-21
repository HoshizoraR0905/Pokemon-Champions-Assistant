"""Run the frozen v2 functions for Battle 10 with isolated index routing only."""
from pathlib import Path
import json
import os
import sys
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from speed_inference.offline import RUNS, atomic_json, file_hash
from battle_evidence.offline import run as evidence_run
from battle_evidence.visual_offline import run as visual_run

RUN='m34-v21-holdout-frozen-v1'


def main():
    os.chdir(ROOT)
    freeze=json.loads((ROOT/'.cache/m34-visual-v21/freeze.json').read_text())
    changed=[p for p,h in freeze['files'].items() if not Path(p).exists() or file_hash(p)!=h]
    if changed:raise ValueError(f'Frozen baseline changed: {changed}')
    execution=ROOT/f'.cache/battles/sample_battle_10/evaluation/{RUN}/execution.json'
    if json.loads(execution.read_text())['status']!='complete':raise ValueError('Production acquisition incomplete')
    RUNS[10]=RUN  # Routing only; no thresholds, estimator or recognizer changes.
    prior=evidence_run(10,root=ROOT)
    sandbox=ROOT/'.cache/m34-visual-v21/frozen-run-root';sandbox.mkdir(parents=True,exist_ok=True)
    for name in ('battle_evidence','recognition','knowledge','damage','tracking','speed_inference','battle_events','battle_artifacts.py'):
        p=sandbox/name
        if not p.exists():p.symlink_to(ROOT/name)
    (sandbox/'.cache').mkdir(exist_ok=True)
    for name in ('battles','m15-onnx-medium'):
        p=sandbox/'.cache'/name
        if not p.exists():p.symlink_to(ROOT/'.cache'/name)
    atomic_json(sandbox/'.cache/m34e/battle-index.json',[prior])
    os.chdir(sandbox)
    prediction=visual_run(10,profile='v2')
    os.chdir(ROOT)
    output=ROOT/prediction
    seal=ROOT/'.cache/m34-visual-v21/holdout-prediction-seal.json'
    payload=dict(battle_id='sample_battle_10',sealed_utc=datetime.now(timezone.utc).isoformat(),
                 result=str(output.relative_to(ROOT)),sha256=file_hash(output),manifest_sha256=file_hash(output.with_name('manifest.json')),
                 production_execution_sha256=file_hash(execution),freeze_sha256=file_hash(ROOT/'.cache/m34-visual-v21/freeze.json'),
                 routing='RUNS[10] and isolated m34e index only; frozen functions unchanged',source_reference_inspected=False)
    if seal.exists():
        old=json.loads(seal.read_text())
        if old['sha256']!=payload['sha256']:raise ValueError('Holdout prediction changed')
    else:atomic_json(seal,payload)
    print(json.dumps(payload,indent=2))


if __name__=='__main__':main()
