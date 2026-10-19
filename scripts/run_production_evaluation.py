"""Freeze and run a fresh canonical video recognition evaluation with monitoring.

No baseline or annotation import. Resuming a failed run is explicit and requires
matching runtime source/input identity; no first-pass outputs are overwritten.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json
from recognition.fast_video import digest


def runtime_sources():
    files=[p for base in ['recognition','tracking','battle_events','models','knowledge','capture','damage']
        for p in (ROOT/base).rglob('*') if p.suffix in {'.py','.json','.yaml','.yml'} and '__pycache__' not in p.parts]
    files += [ROOT/name for name in ['main.py','battle_artifacts.py','scripts/process_m237.py','scripts/build_m236_review.py','scripts/templates/event_review.html','scripts/templates/fast_review.html']]
    return {str(p.relative_to(ROOT)):digest(p) for p in files if p.is_file()}


def process_memory(pid):
    rows=subprocess.check_output(['ps','-axo','pid=,ppid=,rss='],text=True)
    processes=[tuple(map(int,line.split())) for line in rows.splitlines() if len(line.split())==3]
    selected={pid}
    while True:
        more={p for p,parent,rss in processes if parent in selected}
        if more<=selected:break
        selected|=more
    return sum(rss for p,parent,rss in processes if p in selected)/1024


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',required=True);p.add_argument('--run-id',required=True);p.add_argument('--resume',action='store_true')
    args=p.parse_args();owner=BattleArtifacts(args.battle,ROOT).prepare();video=owner.video()
    folder=owner.cache('evaluation/'+args.run_id);folder.mkdir(parents=True,exist_ok=True)
    identity=dict(video=str(video.relative_to(ROOT)),video_sha256=digest(video),sources=runtime_sources(),
        ocr_model_manifest=digest(ROOT/'.cache/m15-onnx-medium/local-manifest.json'),icons=digest(ROOT/'.cache/champions-icons/index.json'))
    manifest_path=folder/'execution.json'
    command=[str(ROOT/'.venv/bin/python'),'-u',str(ROOT/'main.py'),'--video',str(video),'--profile','event-driven','--run-id',args.run_id]
    if args.resume:
        previous=json.loads(manifest_path.read_text());assert previous['identity']==identity,'Frozen implementation or input changed'
        assert previous['status']!='complete','Completed first pass must be reused'
        old_pid=previous.get('pid')
        if old_pid:
            try:os.kill(old_pid,0)
            except ProcessLookupError:pass
            else:raise RuntimeError('Previous process still exists; inspect it before resuming')
        command.append('--resume')
    else:
        assert not manifest_path.exists(),'First-pass evaluation exists; inspect and reuse it'
        assert not owner.cache('event-driven/'+args.run_id+'/manifest.json').exists(),'Production namespace is not fresh'
        for name,expected in identity['sources'].items():
            dest=folder/'frozen-source'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/name).read_bytes())
    data=dict(status='running',identity=identity,command=command,first_pass=True,resumed=args.resume,
        peak_process_tree_rss_mb=0,wall_seconds=0,notes='No cached observations, frame cache or prediction cache supplied.')
    started=time.monotonic();log=folder/('production-resume.log' if args.resume else 'production.log')
    with log.open('a' if args.resume else 'w') as out:
        child=subprocess.Popen(command,cwd=ROOT,stdout=out,stderr=subprocess.STDOUT)
        data['pid']=child.pid;atomic_json(manifest_path,data)
        while child.poll() is None:
            data['wall_seconds']=time.monotonic()-started
            data['peak_process_tree_rss_mb']=max(data['peak_process_tree_rss_mb'],process_memory(child.pid))
            atomic_json(manifest_path,data)
            if int(data['wall_seconds'])%30<5:
                with log.open('rb') as stream:
                    stream.seek(max(0,log.stat().st_size-1600));tail=stream.read().decode('utf-8','replace').splitlines()[-1:]
                print(f"{owner.battle_id}: {data['wall_seconds']:.0f}s; peak process-tree RSS {data['peak_process_tree_rss_mb']:.1f} MiB; {tail}",flush=True)
            time.sleep(5)
    data.update(status='complete' if child.returncode==0 else 'failed',returncode=child.returncode,wall_seconds=time.monotonic()-started,
        frozen_runtime_unchanged=runtime_sources()==identity['sources'],video_unchanged=digest(video)==identity['video_sha256'])
    assert data['frozen_runtime_unchanged'] and data['video_unchanged'],'First-pass runtime/input drift'
    production=owner.cache('event-driven/'+args.run_id)
    if child.returncode==0:
        data['sealed_outputs']={name:digest(production/name) for name in ['manifest.json','observations.json','video-only.json','replay.json','video-only-seal.json']}
    atomic_json(manifest_path,data);print(json.dumps({k:v for k,v in data.items() if k!='identity'},indent=2),flush=True)
    raise SystemExit(child.returncode)
if __name__=='__main__':main()
