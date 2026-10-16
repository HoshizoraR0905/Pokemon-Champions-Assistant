"""Measure a fresh standard-CLI fast run, including process startup and packaging."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts,canonical_id
from recognition.video_sampling import atomic_json


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--video',type=Path,required=True)
    p.add_argument('--run-id',required=True);a=p.parse_args();run_id=canonical_id(a.run_id)
    paths=BattleArtifacts.select(video=a.video).prepare();folder=paths.cache('fast/'+run_id)
    if folder.exists():raise ValueError('Cold benchmark requires a new empty run namespace; preserve prior runs')
    folder.mkdir(parents=True)
    hardware=dict(platform=platform.platform(),machine=platform.machine(),python=sys.version)
    for key,cmd in [('cpu',['sysctl','-n','machdep.cpu.brand_string']),('memory_bytes',['sysctl','-n','hw.memsize'])]:
        r=subprocess.run(cmd,capture_output=True,text=True);hardware[key]=r.stdout.strip() if r.returncode==0 else 'unavailable'
    cmd=[sys.executable,str(ROOT/'main.py'),'--video',str(a.video),'--profile','fast','--run-id',run_id]
    record=dict(status='running',command=cmd,hardware=hardware,prediction_caches_initially_empty=True,
        reused_static_assets='Pinned OCR weights, icon templates and knowledge only; no previous frames, predictions or states',
        benchmark_runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    atomic_json(folder/'benchmark.json',record)
    started=time.monotonic();result=subprocess.run(cmd,cwd=ROOT);elapsed=time.monotonic()-started
    manifest_path=folder/'manifest.json';manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    target=manifest.get('performance_target_seconds')
    record.update(status='complete' if result.returncode==0 and manifest.get('status')=='complete' else 'failed',
        returncode=result.returncode,cold_cli_end_to_end_wall_seconds=elapsed,performance_target_seconds=target,
        performance_target_met=elapsed<=target if target is not None else None)
    atomic_json(folder/'benchmark.json',record);print(json.dumps(record,indent=2))
    return result.returncode


if __name__=='__main__':raise SystemExit(main())
