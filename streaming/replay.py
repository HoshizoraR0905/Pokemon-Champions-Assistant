"""Input adapters and replay scheduling, independent of recognition decisions."""
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import time

from capture import Frame, load_image


def cached_frames(manifest_path, *, start=None, end=None):
    """Read only selected cached samples. No video decoding or future-frame classification."""
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    root = Path(__file__).resolve().parents[1]
    for entry in manifest['frames']:
        timestamp = entry['timestamp']
        if start is not None and timestamp < start:
            continue
        if end is not None and timestamp > end:
            continue
        path = root/entry['image']
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError(f'Cached input checksum mismatch: {path}')
        yield Frame(load_image(path).image,manifest['source'],entry['index'],timestamp,
                    {**entry['metadata'],'frame_reference':str(path),'replay_origin':str(manifest_path),
                     'sampling_interval_seconds':manifest['interval']})


def recorded_frames(path, *, start=None, end=None):
    """Explicit recorded sequence: source/index/timestamp/image per row."""
    path = Path(path)
    for entry in json.loads(path.read_text())['frames']:
        if start is not None and entry['timestamp'] < start:
            continue
        if end is not None and entry['timestamp'] > end:
            continue
        image_path = path.parent/entry['image']
        expected = entry.get('metadata',{}).get('sha256')
        if expected and hashlib.sha256(image_path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Recorded frame checksum mismatch: {image_path}')
        yield Frame(load_image(image_path).image,entry['source'],entry['index'],entry['timestamp'],
                    {**entry.get('metadata',{}),'frame_reference':str(image_path)})


def replay(frames, pipeline, sink, *, speed=None, poll_interval=.01):
    """speed=None is burst replay; speed=1 is simulated real-time capture cadence.

    Synthetic capture monotonic timestamps follow the requested cadence. Dispatch
    lateness is reported separately, including disk I/O/producer backpressure.
    All modes use the identical process_frame path and never look ahead.
    """
    if speed is not None and (not math.isfinite(speed) or speed <= 0):
        raise ValueError('Replay speed must be positive')
    origin = time.monotonic()
    first = None
    try:
        for frame in frames:
            if first is None:
                first = frame.timestamp
            target = time.monotonic() if speed is None else origin+(frame.timestamp-first)/speed
            while time.monotonic() < target:
                for bundle in pipeline.poll():
                    sink({'type':'observations','data':bundle})
                for message in pipeline.poll_messages():
                    sink({'type':'message_available','data':message})
                for update in pipeline.decision_updates():
                    sink({'type':'decision_settled','data':update})
                time.sleep(min(poll_interval,max(0,target-time.monotonic())))
            dispatched = time.monotonic()
            frame = replace(frame,capture_monotonic=target,
                            metadata={**frame.metadata,'replay_speed':speed,
                                      'dispatch_lateness_seconds':max(0,dispatched-target)})
            result = pipeline.process_frame(frame)
            sink({'type':'capture_update','data':{k:v for k,v in result.items() if k!='completed'}})
            for bundle in result['completed']:
                sink({'type':'observations','data':bundle})
            for message in pipeline.poll_messages():
                sink({'type':'message_available','data':message})
            for update in pipeline.decision_updates():
                sink({'type':'decision_settled','data':update})
        final = pipeline.finish()
        for bundle in final.pop('completed'):
            sink({'type':'observations','data':bundle})
        for message in pipeline.poll_messages():
            sink({'type':'message_available','data':message})
        for update in pipeline.decision_updates():
            sink({'type':'decision_settled','data':update})
        sink({'type':'stream_end','data':final})
    except BaseException:
        pipeline.mark_interruption('replay_or_source_interrupted')
        raise
    finally:
        pipeline.close()
