"""Read-only verification of saved milestone outputs. Never invokes recognition."""
import hashlib,json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from scripts.benchmark_m233b1 import evaluation_key


def verify():
    counts=Counter();seen={}
    def check(path,digest):
        p=ROOT/path
        if str(p) not in seen:seen[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        assert seen[str(p)]==digest,str(path)
    for i in range(5):
        root=ROOT/f'.cache/battles/sample_battle_{i}'
        for stage in ['m232','m233a']:
            d=json.loads((root/stage/'pipeline-manifest.json').read_text())
            record=d['stages']['replay'] if stage=='m232' else d
            assert record['status']=='complete'
            for p,h in record['outputs'].items():check(p,h);counts['prior_outputs_unchanged']+=1
        b1=root/'m233b1'
        for p in b1.glob('sampling/**/frames.json'):
            d=json.loads(p.read_text())
            for r in d['frames']:check(r['image'],r['sha256']);counts['frame_references']+=1
            counts['sampling_manifests']+=1
        for p in b1.glob('runs/*/manifest.json'):
            d=json.loads(p.read_text())
            if d['status']!='complete':counts['incomplete_runs_retained']+=1;continue
            check(d['observations'],d['observations_sha256']);counts['complete_run_manifests']+=1
        p=b1/'experiment/results-manifest.json'
        if p.exists():
            d=json.loads(p.read_text());assert d['status']=='complete'
            assert d['input_hash']==evaluation_key(BattleArtifacts(f'sample_battle_{i}'))
            check(str((p.parent/'results.json').relative_to(ROOT)),d['output_sha256'])
            counts['current_experiment_manifests']+=1
    assert counts['prior_outputs_unchanged']==65 and counts['current_experiment_manifests']==4
    print(json.dumps(dict(counts),indent=2));return dict(counts)
if __name__=='__main__':verify()
