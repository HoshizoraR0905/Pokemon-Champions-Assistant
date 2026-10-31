"""External timing and freezing of new production recordings, one battle at a time.

No instrumentation, recognition tuning, historical logs or imported predictions.
HP projection/sealing have separate timings outside the normal CLI wall clock.
"""
import argparse
from dataclasses import asdict
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts,canonical_id
from recognition.event_report import atomic_json,verify_seal
from recognition.fast_video import digest


def now():return datetime.now(timezone.utc).isoformat()


def read(p):return json.loads(p.read_text())


def protect_b16(target):
    path=target/'b16-protected.json'
    if path.exists():return read(path)
    owner=BattleArtifacts('sample_battle_16',ROOT)
    paths=set(owner.cache_dir.glob('*/*/manifest.json'))
    paths.update(owner.report_dir.glob('evaluation/*/report.md'))
    paths.update(owner.report_dir.glob('evaluation/*/metrics.json'))
    for seal in owner.cache_dir.glob('event-driven/*/video-only-seal.json'):
        paths.add(seal)
        paths.update(seal.parent/name for name in read(seal)['files'])
    paths.add(owner.cache('evaluation/b16-semantic-state-20261027-v1/normal-process.json'))
    value=dict(created_at=now(),files={str(p.relative_to(ROOT)):digest(p) for p in sorted(paths) if p.is_file()},
        note='Read-only guard, no B16 replay or acquisition.')
    atomic_json(path,value);return value


def video_headers(owner,folder):
    import cv2
    import imageio_ffmpeg
    p=owner.video();cap=cv2.VideoCapture(str(p))
    fps=cap.get(cv2.CAP_PROP_FPS);frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT));cap.release()
    # Opening headers without an output performs no video decoding. FFmpeg exits
    # nonzero because no output was requested; its metadata text is retained.
    command=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-i',str(p)]
    result=subprocess.run(command,capture_output=True,text=True)
    (folder/'video-header.txt').write_text(result.stderr)
    duration=re.search(r'Duration: (\d+):(\d+):([\d.]+)',result.stderr)
    if not duration or fps<=0 or frames<=0:raise ValueError('Missing source header metadata')
    seconds=int(duration[1])*3600+int(duration[2])*60+float(duration[3])
    return dict(path=str(p.absolute()),resolved_path=str(p.resolve()),sha256=digest(p),bytes=p.stat().st_size,
        duration_seconds=seconds,source_frames=frames,source_average_fps=fps,width=width,height=height,
        stream_frames_over_average_fps_seconds=frames/fps,
        metadata_method='OpenCV/FFmpeg container headers; frame count cross-checked against production decoder',
        fps_note='Average stream rate; not a claim of constant source-frame intervals.',header_command=command)


def derived_projection(owner,run,folder):
    from tracking.battle_state import from_dict
    from tracking.state_engine import StateEngine,EventRecord
    source=owner.cache('event-driven/'+run);saved=read(source/'replay.json')
    engine=StateEngine(from_dict(saved['initial_state']))
    engine.state=from_dict(saved['state']);engine.history=[EventRecord(**r) for r in saved['history']]
    before=engine.to_dict();start=time.perf_counter();projection=engine.hp_resolutions()
    seconds=time.perf_counter()-start
    assert engine.to_dict()==before,'Derived HP projection mutated authoritative state/receipts'
    numeric={o['evidence']['event_id'] for p in engine.state.pokemon.values() for o in p.hp.observations if o.get('delta') and 'unit' in o}
    covered=[eid for o in projection['episodes'] for eid in o['segment_event_ids']]
    assert len(covered)==len(set(covered)) and set(covered)==numeric,'Dropped/duplicate HP segment'
    atomic_json(folder/'hp-resolutions.json',projection)
    adaptive=read(source/'adaptive-multi-hit.json') if (source/'adaptive-multi-hit.json').exists() else {}
    attempts=adaptive.get('completed',[])
    atomic_json(folder/'projection-stage.json',dict(status='complete',wall_seconds=seconds,
        state_and_receipts_unchanged=True,observed_nonzero_numeric_segments=len(numeric),
        projected_membership_exact=True,normal_cli_time_included=False,
        targeted_high_fps_passes=len(attempts),targeted_high_fps_frames=sum(a['measured']['sampled_frames'] for a in attempts),
        reason='Production adaptive 3/4 FPS attempts are recorded separately; this projection itself invokes no recognition.'))
    return seconds


def freeze(owner,run,target):
    source=owner.cache('event-driven/'+run);verify_seal(source)
    if (target/'initial-freeze.json').exists():return read(target/'initial-freeze.json')
    start=time.perf_counter();derived_projection(owner,run,target)
    files={str(p.relative_to(ROOT)):digest(p) for p in sorted(source.rglob('*')) if p.is_file()}
    for p in [target/'execution.json',target/'hp-resolutions.json',target/'projection-stage.json']:
        files[str(p.relative_to(ROOT))]=digest(p)
    value=dict(status='sealed',battle_id=owner.battle_id,run_id=run,sealed_at=now(),files=files,
        source_identity=read(source/'manifest.json')['identity'],
        stage_wall_seconds=time.perf_counter()-start,normal_cli_time_included=False,
        pre_tuning=True,reference_labels_used=False,battle_log_used=False,
        note='Raw frames/reads/icons/monitoring/observations, source snapshots, events, receipts, state, and HP projection sealed before failure review.')
    atomic_json(target/'initial-freeze.json',value);return value


def run_battle(battle,run,*,resume=False):
    owner=BattleArtifacts(battle,ROOT).prepare();folder=owner.cache('fresh-benchmark/'+run)
    folder.mkdir(parents=True,exist_ok=True);path=folder/'execution.json'
    if path.exists():
        data=read(path)
        if data['status']=='complete':
            freeze(owner,run,folder);print(battle,'already complete and sealed',flush=True);return
        if not resume:raise ValueError('Prior attempt exists; inspect processes and use --resume')
        for pid in [data.get('child_pid'),data.get('driver_pid')]:
            if pid and pid!=os.getpid():
                try:os.kill(pid,0)
                except ProcessLookupError:pass
                else:raise ValueError(f'Existing benchmark process is active: {pid}')
        if data.get('status')=='running':raise ValueError('Unclosed timing interval: recover process outcome before resuming; do not invent elapsed time')
    else:data=None
    source=owner.cache('event-driven/'+run)
    if source.exists() and not resume:raise ValueError('Fresh acquisition requires an absent production namespace')
    metadata=video_headers(owner,folder)
    atomic_json(folder/'input.json',metadata)
    protect_b16(folder)
    command=[str(ROOT/'.venv/bin/python'),str(ROOT/'main.py'),'--video',str(owner.video()),
        '--profile','event-driven','--identity-mode','lightweight','--sample-fps','2','--run-id',run]
    if resume:command.append('--resume')
    attempt=dict(started_at=now(),status='running',command=command,driver_pid=os.getpid())
    prior=list(data.get('attempts',[])) if data else []
    data=dict(status='running',battle_id=battle,run_id=run,command=command,input=metadata,
        driver_pid=os.getpid(),attempts=prior+[attempt],hardware=dict(platform=platform.platform(),machine=platform.machine(),
        python=sys.version,logical_cpus=os.cpu_count()),prediction_namespace_initially_absent=not source.exists(),
        profiler_enabled=False,runner_sha256=digest(Path(__file__)),
        cache_policy='Fresh per-battle frames/recognition/state; shared pinned model/icon/knowledge assets only; no imported recognition caches',
        normal_time_definition='External perf_counter around actual production subprocess startup through exit, including final reconstruction/viewer export. Separate projection/sealing/verification/reporting excluded.')
    atomic_json(path,data)
    with (folder/f'normal-pipeline-attempt-{len(prior)+1}.log').open('w') as stream:
        attempt['subprocess_start_epoch_ns']=time.time_ns()
        began=time.perf_counter();process=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        data['child_pid']=process.pid;attempt['child_pid']=process.pid;atomic_json(path,data)
        while process.poll() is None:
            try:process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                attempt['elapsed_checkpoint_seconds']=time.perf_counter()-began;atomic_json(path,data)
                m=read(source/'manifest.json') if (source/'manifest.json').exists() else {}
                print(battle,'running',m.get('last_timestamp'),m.get('status'),flush=True)
        wall=time.perf_counter()-began
        attempt['subprocess_end_epoch_ns']=time.time_ns()
    attempt.update(status='complete' if process.returncode==0 else 'failed',returncode=process.returncode,
        wall_seconds=wall,finished_at=now())
    data.update(status=attempt['status'],returncode=process.returncode,normal_cli_wall_seconds=sum(a['wall_seconds'] for a in data['attempts']))
    atomic_json(path,data)
    if process.returncode:raise RuntimeError(f'{battle} production failed; preserve artifacts and inspect its log')
    manifest=read(source/'manifest.json');counts=manifest['counts'];duration=metadata['duration_seconds']
    assert manifest['status']=='complete' and manifest['identity']['end'] is None and manifest['identity']['max_frames'] is None
    assert not any(k in manifest['identity'] for k in ['frame_cache','recognition_caches','recognition_stage_source'])
    sampled=counts['frames_materialized_at_2fps'];inspected=counts['frames_sampled'];total=data['normal_cli_wall_seconds']
    data.update(sampled_frames=sampled,monitored_frames=counts['cheap_monitor_frames'],detailed_inspection_frames=inspected,
        ocr_model_invocations=counts['ocr_invocations_performed'],source_decoded_frames=manifest['decoder']['source_decoded_frames'],
        ms_per_sampled_frame=1000*total/sampled,ms_per_inspected_frame=1000*total/inspected,
        PTR=total/duration,effective_sampled_fps=sampled/total,
        internal_pipeline_seconds=manifest['cold_end_to_end_wall_seconds'],internal_active_seconds=manifest['active_seconds'],
        cold_run=manifest['cold_run'],full_cold_timing_comparable=len(data['attempts'])==1 and manifest['cold_run'],
        production_manifest_sha256=digest(source/'manifest.json'))
    atomic_json(path,data)
    freeze(owner,run,folder)
    print(battle,'COMPLETE AND SEALED',json.dumps({k:data[k] for k in ['normal_cli_wall_seconds','sampled_frames','detailed_inspection_frames','PTR']}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--battles',nargs='+',required=True)
    p.add_argument('--run-id',required=True);p.add_argument('--resume',action='store_true');a=p.parse_args()
    for battle in a.battles:run_battle(canonical_id(battle),canonical_id(a.run_id),resume=a.resume)
