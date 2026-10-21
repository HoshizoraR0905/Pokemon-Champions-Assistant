"""Fresh, resumable, immutable production acquisition with causal call profiling.

Uses canonical main.py --profile event-driven without supplying cached frames,
predictions, team profiles or expected identities. Existing runs are read only.
"""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import runpy
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.fast_video import digest
from recognition.video_sampling import atomic_json
from scripts.run_production_evaluation import runtime_sources,process_memory


def child(owner,run_id,segment,resume,identity_mode,recognition_cache=None):
    from scripts.production_profiler import Recorder
    folder=owner.cache(f'evaluation/{run_id}/profiler/segment-{segment:04d}')
    recorder=Recorder(folder);status='failed'
    try:
        recorder.install()
        sys.argv=[str(ROOT/'main.py'),'--video',str(owner.video()),'--profile','event-driven','--run-id',run_id,'--identity-mode',identity_mode]
        if recognition_cache:sys.argv+=['--recognition-cache',str(recognition_cache)]
        if resume:sys.argv.append('--resume')
        try:runpy.run_path(str(ROOT/'main.py'),run_name='__main__')
        except SystemExit as e:
            if e.code not in (None,0):raise
        status='complete'
    finally:recorder.close(status)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',required=True);p.add_argument('--run-id',required=True)
    p.add_argument('--recognition-cache',type=Path,help='Explicit same-battle compatible pixel cache; reported as warm acquisition')
    p.add_argument('--identity-mode', choices=['lightweight','development'], default='lightweight')
    p.add_argument('--resume',action='store_true');p.add_argument('--child',action='store_true',help=argparse.SUPPRESS);p.add_argument('--segment',type=int,default=0,help=argparse.SUPPRESS)
    a=p.parse_args();owner=BattleArtifacts(a.battle)
    owner.video()
    if a.child:return child(owner,a.run_id,a.segment,a.resume,a.identity_mode,a.recognition_cache)
    owner.prepare();folder=owner.cache('evaluation/'+a.run_id);production=owner.cache('event-driven/'+a.run_id)
    identity=dict(identity_mode=a.identity_mode,recognition_cache=dict(path=str(a.recognition_cache.resolve()),manifest_sha256=digest(a.recognition_cache/'manifest.json')) if a.recognition_cache else None,video=str(owner.video().relative_to(ROOT)),video_sha256=digest(owner.video()),sources=runtime_sources(),
        profiler_sources={str(path.relative_to(ROOT)):digest(path) for path in [Path(__file__),ROOT/'scripts/production_profiler.py']},
        ocr_model_manifest=digest(ROOT/'.cache/m15-onnx-medium/local-manifest.json'),icons=digest(ROOT/'.cache/champions-icons/index.json'))
    folder.mkdir(parents=True,exist_ok=True);execution=folder/'execution.json'
    if a.resume:
        data=json.loads(execution.read_text());assert data['identity']==identity,'Resume identity changed; preserve namespace'
        assert data['status']!='complete','Reuse completed profiling data'
        try:os.kill(data['segments'][-1]['pid'],0)
        except ProcessLookupError:pass
        else:raise RuntimeError('Previous child still exists; inspect before resuming')
    else:
        assert not execution.exists() and not production.exists(),'Occupied namespace; inspect existing data'
        data=dict(identity=identity,status='starting',segments=[],cold=not bool(a.recognition_cache),
            caches='Fresh crop caches and fresh process/model instances. Shared immutable weights/icons allowed. OS filesystem cache warmth uncontrolled. No team-profile cache consumed by canonical event-driven CLI.')
        if a.recognition_cache:data['caches']='Warm pixel predictions copied from '+str(a.recognition_cache.resolve())+'; fresh process/model instances and decoding. Shared immutable weights/icons; OS filesystem cache uncontrolled.'
        for name in [*identity['sources'],*identity['profiler_sources']]:
            dest=folder/'frozen-source'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/name).read_bytes())
        atomic_json(folder/'environment.json',dict(python=sys.version,platform=platform.platform(),
            commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            git_status=subprocess.check_output(['git','status','--short','-uall'],text=True),
            dependencies={d.metadata['Name']:d.version for d in importlib.metadata.distributions() if d.metadata['Name']},
            configuration='Canonical event-driven defaults, icons enabled, CPU OCR, target 2 FPS and confirmed COMMAND 1 FPS inspection. Profiling only; all policy functions delegate unchanged.'))
    number=len(data['segments']);command=[sys.executable,'-u',str(Path(__file__).resolve()),'--battle',a.battle,'--run-id',a.run_id,'--child','--segment',str(number),'--identity-mode',a.identity_mode]
    if a.recognition_cache:command+=['--recognition-cache',str(a.recognition_cache.resolve())]
    if a.resume:command.append('--resume')
    started=time.monotonic();segment=dict(command=command,resumed=a.resume,wall_seconds=0.,peak_process_tree_rss_mib=0.)
    data['segments'].append(segment)
    with (folder/f'production-{number:04d}.log').open('x') as out:
        proc=subprocess.Popen(command,cwd=ROOT,stdout=out,stderr=subprocess.STDOUT);segment['pid']=proc.pid;data['status']='running';atomic_json(execution,data)
        last=-30.
        while proc.poll() is None:
            segment['wall_seconds']=time.monotonic()-started;segment['peak_process_tree_rss_mib']=max(segment['peak_process_tree_rss_mib'],process_memory(proc.pid))
            atomic_json(execution,data)
            if segment['wall_seconds']-last>=30:
                last=segment['wall_seconds'];print(f'{a.battle} profiled: {last:.0f}s wall, {segment["peak_process_tree_rss_mib"]:.1f} MiB peak',flush=True)
            time.sleep(5)
    segment.update(wall_seconds=time.monotonic()-started,returncode=proc.returncode)
    data.update(status='complete' if proc.returncode==0 else 'failed',wall_seconds=sum(s['wall_seconds'] for s in data['segments']),
        peak_process_tree_rss_mib=max(s['peak_process_tree_rss_mib'] for s in data['segments']),
        runtime_unchanged=runtime_sources()==identity['sources'],video_unchanged=digest(owner.video())==identity['video_sha256'])
    assert data['runtime_unchanged'] and data['video_unchanged']
    if proc.returncode==0:
        data['sealed_outputs']={n:digest(production/n) for n in ['manifest.json','observations.json','video-only.json','replay.json','video-only-seal.json']}
        data['profile_outputs']={str(path.relative_to(folder)):digest(path) for path in (folder/'profiler').glob('segment-*/*') if path.is_file()}
    atomic_json(execution,data);print(json.dumps({k:v for k,v in data.items() if k not in ('identity','sealed_outputs','profile_outputs')},indent=2))
    raise SystemExit(proc.returncode)


if __name__=='__main__':main()
