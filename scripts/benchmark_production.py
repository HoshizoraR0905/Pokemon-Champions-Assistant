"""Observe an unchanged canonical production run; never import expected answers.

Timers include nested calls. Generator timing measures time spent requesting a
frame, not the consumer's work or FFmpeg's concurrent lifetime. Instrumentation
adds overhead; no uninstrumented speedup is inferred from these measurements.
"""
import argparse
from collections import defaultdict
from functools import wraps
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import runpy
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.fast_video import digest
from recognition.video_sampling import atomic_json
from scripts.run_production_evaluation import runtime_sources, process_memory


def observe_child(owner, run_id, resume):
    started = time.monotonic()
    folder = owner.cache('evaluation/' + run_id)
    segment = 'resume' if resume else 'first'
    stats = defaultdict(lambda: dict(calls=0, inclusive_seconds=0., exclusive_seconds=0.))
    stack = []
    lock = threading.RLock()
    stop = threading.Event()

    def record(key, began, nested):
        elapsed = time.monotonic() - began
        with lock:
            row = stats[key]
            row['calls'] += 1
            row['inclusive_seconds'] += elapsed
            row['exclusive_seconds'] += elapsed - nested
        if stack:
            stack[-1][1] += elapsed

    def instrument(obj, name, key):
        original = getattr(obj, name)
        @wraps(original)
        def timed(*args, **kwargs):
            entry = [time.monotonic(), 0.]
            stack.append(entry)
            try:
                return original(*args, **kwargs)
            finally:
                stack.pop()
                record(key, *entry)
        setattr(obj, name, timed)

    import recognition.fast_video as video
    import recognition.event_report as report
    import recognition.command_checkpoint as command
    import tracking.command_reconciliation as reconciliation
    from tracking.state_engine import StateEngine
    from battle_events.parser import EventParser

    # Transparent delegation only: arguments, results, exceptions and policies
    # are unchanged. No expected identities, annotations or caches are supplied.
    for obj, name, key in [
        (video, 'analyze', 'canonical_analyze'),
        (video.CachedOCR, '__init__', 'ocr_adapter_init'),
        (video.CachedOCR, 'read', 'ocr_region_read'),
        (video.CachedOCR, 'predict', 'ocr_predict_with_cache_and_lazy_init'),
        (video.CachedIcons, '__init__', 'icon_adapter_init'),
        (video.CachedIcons, 'identify', 'icon_match_with_cache'),
        (report, 'video_events', 'event_adaptation'),
        (EventParser, 'parse', 'event_parser'),
        (StateEngine, 'replay', 'state_reconstruction'),
        (command, 'inspect_command', 'w_ui_detection'),
        (command.CommandCheckpointSchedule, 'observe', 'w_schedule'),
        (command, 'capture_checkpoint_huds', 'w_capture_huds'),
        (command, 'schedule_checkpoint', 'w_detection_schedule_capture'),
        (reconciliation, 'transition', 'w_reconciliation'),
        (report, 'reconstruct_and_package', 'reconstruction_and_exports'),
        (report, 'write_viewer', 'production_viewer_export'),
    ]:
        instrument(obj, name, key)

    original_decoder = video.decoded_frames
    @wraps(original_decoder)
    def decoded(*args, **kwargs):
        iterator = original_decoder(*args, **kwargs)
        try:
            while True:
                entry = [time.monotonic(), 0.]
                stack.append(entry)
                try:
                    item = next(iterator)
                except StopIteration:
                    return
                finally:
                    stack.pop()
                    record('decode_sampling_next_frame_wait', *entry)
                yield item
        finally:
            iterator.close()
    video.decoded_frames = decoded

    def save(status):
        with lock:
            snapshot = {key: dict(value) for key, value in stats.items()}
        atomic_json(folder / ('timers-' + segment + '.json'), dict(
            status=status, elapsed_since_observer_start=time.monotonic() - started,
            timers=snapshot, semantics='Inclusive timers nest; exclusive values remove timed children only. '
            'Decoder values measure generator-next wait; background FFmpeg overlaps recognition. '
            'In-flight calls are absent from partial snapshots. No sum is a wall-clock total.'))

    def checkpoint():
        while not stop.wait(15):
            save('running')
    worker = threading.Thread(target=checkpoint, daemon=True)
    worker.start()
    status = 'failed'
    try:
        sys.argv = [str(ROOT / 'main.py'), '--video', str(owner.video()),
                    '--profile', 'event-driven', '--run-id', run_id]
        if resume:
            sys.argv.append('--resume')
        try:
            runpy.run_path(str(ROOT / 'main.py'), run_name='__main__')
        except SystemExit as exc:
            if exc.code not in (0, None):
                raise
        status = 'complete'
    finally:
        stop.set()
        worker.join()
        save(status)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--battle', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    owner = BattleArtifacts(args.battle)
    owner.video()  # Fail before creating outputs when the fixture is missing.
    if args.child:
        observe_child(owner, args.run_id, args.resume)
        return
    owner.prepare()
    folder = owner.cache('evaluation/' + args.run_id)
    folder.mkdir(parents=True, exist_ok=True)
    execution = folder / 'execution.json'
    identity = dict(video=str(owner.video().relative_to(ROOT)), video_sha256=digest(owner.video()),
                    sources=runtime_sources(), observer_sha256=digest(Path(__file__)),
                    ocr_model_manifest=digest(ROOT / '.cache/m15-onnx-medium/local-manifest.json'),
                    icons=digest(ROOT / '.cache/champions-icons/index.json'))
    data = dict(identity=identity, first_pass=True, segments=[])
    if args.resume:
        data = json.loads(execution.read_text())
        assert data['identity'] == identity, 'Source/input/observer changed; preserve original run'
        assert data['status'] != 'complete'
        previous = data['segments'][-1]
        try:
            os.kill(previous['pid'], 0)
        except ProcessLookupError:
            pass
        else:
            raise RuntimeError('Previous child still exists; inspect it before resuming')
        assert len(data['segments']) == 1, 'Preserve resume timers; additional segments need explicit versioned observer support'
    else:
        assert not execution.exists(), 'Existing evaluation must be inspected and reused'
        assert not owner.cache('event-driven/' + args.run_id).exists(), 'Production namespace is occupied'
        for name in [*identity['sources'], str(Path(__file__).relative_to(ROOT))]:
            destination = folder / 'frozen-source' / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((ROOT / name).read_bytes())
        dirty = subprocess.check_output(['git', 'status', '--porcelain=v1', '-uall'], cwd=ROOT, text=True)
        versions = {d.metadata['Name']: d.version for d in importlib.metadata.distributions() if d.metadata['Name']}
        atomic_json(folder / 'environment.json', dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                    dirty_status=dirty, python=sys.version, platform=platform.platform(), dependencies=versions,
                    configuration='Canonical EventConfig, 2 FPS default; 1 FPS only while COMMAND confirmed; CPU OCR; icons enabled',
                    instrumentation='Transparent monotonic wrappers around existing functions; no policy/threshold changes. Observer overhead included.'))
    command = [sys.executable, '-u', str(Path(__file__).resolve()), '--battle', args.battle,
               '--run-id', args.run_id, '--child']
    if args.resume:
        command.append('--resume')
    segment = dict(command=command, resumed=args.resume, wall_seconds=0., peak_process_tree_rss_mb=0.)
    data['segments'].append(segment)
    started = time.monotonic()
    log = folder / ('production-resume.log' if args.resume else 'production.log')
    with log.open('x') as out:
        child = subprocess.Popen(command, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT)
        segment['pid'] = child.pid
        data['status'] = 'running'
        atomic_json(execution, data)
        last_notice = -30.
        while child.poll() is None:
            segment['wall_seconds'] = time.monotonic() - started
            segment['peak_process_tree_rss_mb'] = max(segment['peak_process_tree_rss_mb'], process_memory(child.pid))
            atomic_json(execution, data)
            if segment['wall_seconds'] - last_notice >= 30:
                last_notice = segment['wall_seconds']
                print(f"{args.battle}: {last_notice:.0f}s wall; {segment['peak_process_tree_rss_mb']:.1f} MiB peak", flush=True)
            time.sleep(5)
    segment.update(wall_seconds=time.monotonic() - started, returncode=child.returncode)
    data.update(status='complete' if child.returncode == 0 else 'failed',
                wall_seconds=sum(s['wall_seconds'] for s in data['segments']),
                peak_process_tree_rss_mb=max(s['peak_process_tree_rss_mb'] for s in data['segments']),
                frozen_runtime_unchanged=runtime_sources() == identity['sources'],
                video_unchanged=digest(owner.video()) == identity['video_sha256'])
    assert data['frozen_runtime_unchanged'] and data['video_unchanged']
    if child.returncode == 0:
        production = owner.cache('event-driven/' + args.run_id)
        data['sealed_outputs'] = {name: digest(production / name) for name in
                                  ['manifest.json', 'observations.json', 'video-only.json', 'replay.json', 'video-only-seal.json']}
    atomic_json(execution, data)
    print(json.dumps({k: v for k, v in data.items() if k not in {'identity', 'sealed_outputs'}}, indent=2), flush=True)
    raise SystemExit(child.returncode)


if __name__ == '__main__':
    main()
