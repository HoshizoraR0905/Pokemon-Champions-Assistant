"""Phase-only video timeline; intentionally emits no battle events or turns."""
import argparse
import json
import math
from pathlib import Path
import time

import cv2
import numpy as np

from capture import video_frames
from recognition import box
from recognition.phases import classify_phase, small_signature


def _distance(a, b):
    return float(np.mean(np.abs(a.astype(np.float32) - b.astype(np.float32))) / 255)


SELECTION_PURPOSES = frozenset({'voluntary', 'move_triggered', 'faint_replacement',
                                'revival_target_selection', 'unknown'})


def _observation_evidence(sample):
    return {key: sample[key] for key in ('source', 'frame_index', 'timestamp',
                                        'raw_phase', 'confidence', 'evidence')}


def build_timeline(frames, *, interval, duration=None, message_reader=None,
                   context_annotations=()):
    """Group sampled visual observations, retaining uncertain transition bounds."""
    if not math.isfinite(interval) or interval <= 0:
        raise ValueError("Timeline interval must be positive and finite")
    if duration is not None and (not math.isfinite(duration) or duration < 0):
        raise ValueError("Timeline duration must be nonnegative and finite")
    for annotation in context_annotations:
        if (annotation['purpose'] not in SELECTION_PURPOSES
                or annotation['start'] > annotation['end']
                or not annotation.get('provenance') or not annotation.get('evidence')):
            raise ValueError("Context annotations require a valid purpose, range, provenance and evidence")
    samples, signatures = [], []
    last_message = None
    last_message_signature = None
    for frame in frames:
        if frame.timestamp is None or not math.isfinite(frame.timestamp) or frame.timestamp < 0:
            raise ValueError("Timeline requires finite nonnegative timestamps")
        if samples and (frame.source != samples[0]["source"]
                        or frame.timestamp <= samples[-1]["timestamp"]
                        or frame.index <= samples[-1]["frame_index"]):
            raise ValueError("Timeline requires one source and increasing timestamps and frame indices")
        phase, confidence, evidence, warnings = classify_phase(frame.image)
        signature = small_signature(frame.image)
        sample = {'source': frame.source, 'frame_index': frame.index,
                  'timestamp': frame.timestamp, 'phase': phase, 'raw_phase': phase,
                  'confidence': confidence, 'evidence': evidence, 'warnings': warnings,
                  'capture_metadata': frame.metadata.copy()}
        if phase == 'battle_message' and message_reader is not None:
            bounds = box(frame.image, (.22, .685, .64, .797))
            x1, y1, x2, y2 = bounds
            message_signature = small_signature(frame.image[y1:y2, x1:x2])
            if last_message_signature is None or _distance(message_signature, last_message_signature) > .035:
                bounds = box(frame.image, (.22, .685, .64, .797))
                observation = message_reader(frame.image, bounds)
                last_message = {'text': observation.value, 'raw_text': observation.raw_text,
                                'confidence': observation.confidence,
                                'frame_index': frame.index, 'timestamp': frame.timestamp,
                                'region': bounds}
                last_message_signature = message_signature
            if last_message and last_message['text']:
                sample['message_evidence'] = last_message.copy()
        if phase in {'pokemon_selection', 'switch_selection'}:
            sample['selection_purpose'] = 'unknown'
            sample['purpose_evidence'] = []
            sample['purpose_provenance'] = 'unresolved'
            if (last_message and last_message['confidence'] >= .75 and last_message['text']
                    and '复生祈祷' in last_message['text']
                    and frame.timestamp is not None and last_message['timestamp'] is not None
                    and 0 <= frame.timestamp - last_message['timestamp'] <= 8):
                sample['selection_purpose'] = 'revival_target_selection'
                sample['purpose_evidence'] = [last_message.copy()]
                sample['purpose_provenance'] = 'visible_message_context'
                sample['warnings'].append('Revival target interface; no switch or restoration event inferred')
        applicable = [a for a in context_annotations if a['source'] == frame.source
                      and a['start'] - a.get('timestamp_tolerance', .05) <= frame.timestamp
                      <= a['end'] + a.get('timestamp_tolerance', .05)]
        if len({a['purpose'] for a in applicable}) > 1:
            sample['warnings'].append('Conflicting contextual annotations; purpose unresolved')
            sample['selection_purpose'] = 'unknown'
            sample['purpose_provenance'] = 'conflicting_annotations'
            sample['purpose_evidence'] = applicable
        elif applicable:
            annotation = applicable[0]
            sample['switching_context'] = annotation['purpose']
            sample['context_provenance'] = annotation['provenance']
            sample['context_evidence'] = annotation['evidence']
            if phase in {'pokemon_selection', 'switch_selection'}:
                sample['selection_purpose'] = annotation['purpose']
                sample['purpose_provenance'] = annotation['provenance']
                sample['purpose_evidence'] = (annotation['evidence'] +
                    [_observation_evidence(o) for o in samples[-2:]] +
                    [_observation_evidence(sample)])
        elif phase in {'pokemon_selection', 'switch_selection'}:
            sample['switching_context'] = sample['selection_purpose']
        if phase != 'battle_message':
            last_message_signature = None
        if phase in {'move_selection', 'move_target_selection', 'team_preview', 'team_configuration', 'battle_screen'}:
            last_message = None
            last_message_signature = None
        samples.append(sample)
        signatures.append(signature)

    # Correct only an isolated unclassified frame that is visually nearly
    # identical to its agreeing neighbors; preserve short distinct phases.
    for i in range(1, len(samples)-1):
        left, current, right = samples[i-1:i+2]
        if (current['phase'] == 'unknown' and current['raw_phase'] == 'unknown'
                and current['evidence'] == ['no_supported_visual_evidence']
                and left['phase'] == right['phase'] != 'unknown'
                and _distance(signatures[i], signatures[i-1]) < .06
                and _distance(signatures[i], signatures[i+1]) < .06):
            current['phase'] = left['phase']
            current['confidence'] = min(.55, left['confidence'], right['confidence'])
            current['evidence'].append('near_identical_neighbor_frames')
            current['warnings'].append('Temporally reconciled low-confidence classification')

    segments = []
    for sample in samples:
        if not segments or segments[-1]['phase'] != sample['phase']:
            segments.append({'phase': sample['phase'],
                             'start_timestamp': sample['timestamp'],
                             'end_timestamp': sample['timestamp'],
                             'start_frame_index': sample['frame_index'],
                             'end_frame_index': sample['frame_index'],
                             'confidence': sample['confidence'],
                             'observations': [], 'warnings': []})
        segment = segments[-1]
        segment['observations'].append(sample)
        segment['end_frame_index'] = sample['frame_index']
        segment['last_observed_timestamp'] = sample['timestamp']
        segment['confidence'] = round(sum(o['confidence'] for o in segment['observations']) /
                                      len(segment['observations']), 3)
        segment['warnings'] = sorted({w for o in segment['observations'] for w in o['warnings']})
    transitions = []
    for i in range(1, len(segments)):
        old, new = segments[i-1], segments[i]
        a, b = old['observations'][-1], new['observations'][0]
        old['end_timestamp'] = b['timestamp']
        gap = b['frame_index'] - a['frame_index']
        transitions.append({'from': old['phase'], 'to': new['phase'],
                            'earliest_timestamp': a['timestamp'],
                            'latest_timestamp': b['timestamp'],
                            'latest_frame_index': b['frame_index'],
                            'earliest_frame_index': a['frame_index'],
                            'provenance': 'observed_adjacent_frames' if gap == 1
                                          else 'inferred_across_sampled_frames',
                            'uncertainty_seconds': round(b['timestamp'] - a['timestamp'], 3)
                                                   if a['timestamp'] is not None and b['timestamp'] is not None else None,
                            'validation': 'unresolved' if 'unknown' in (old['phase'], new['phase']) else 'supported_by_samples',
                            'supporting_observations': [a, b]})
    if samples and duration is not None and duration < samples[-1]["timestamp"]:
        raise ValueError("Duration precedes the last observation")
    if segments:
        last = segments[-1]
        observed_end = last['observations'][-1]['timestamp']
        last['end_timestamp'] = (min(duration, observed_end + interval) if duration is not None
                                 else observed_end + interval)
    return {'schema_version': 2, 'source': samples[0]['source'] if samples else None,
            'sampling_interval_seconds': interval, 'duration_seconds': duration,
            'sample_count': len(samples), 'segments': segments, 'transitions': transitions,
            'warnings': ['Timeline records UI phases only; no turns, switches, revivals, or battle state are inferred']}


def process_video(path, *, interval=1.0, max_frames=None, message_reader=None,
                  context_annotations=(), cache_dir=None):
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise ValueError(f'Cannot read video: {path}')
        fps = cap.get(cv2.CAP_PROP_FPS)
        count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = count / fps if fps > 0 and count > 0 else None
    finally:
        cap.release()
    started = time.perf_counter()
    def frames_with_cache():
        for frame in video_frames(path, interval, max_frames):
            if cache_dir is not None:
                directory = Path(cache_dir)
                directory.mkdir(parents=True, exist_ok=True)
                # Cache the same lossless normalized image used by phase classification.
                image = frame.image
                if image.shape[1] > 1311:
                    image = cv2.resize(image, None, fx=1311/image.shape[1],
                                       fy=1311/image.shape[1], interpolation=cv2.INTER_AREA)
                target = directory/f'{frame.index:08d}.png'
                if not cv2.imwrite(str(target), image):
                    raise ValueError(f'Cannot cache frame: {target}')
                frame.metadata['phase_cache_path'] = str(target)
            yield frame
    timeline = build_timeline(frames_with_cache(), interval=interval,
                              duration=duration if max_frames is None else None,
                              message_reader=message_reader, context_annotations=context_annotations)
    elapsed = time.perf_counter() - started
    timeline['runtime_seconds'] = round(elapsed, 3)
    timeline['sampled_frames_per_second'] = round(timeline['sample_count'] / elapsed, 3) if elapsed else None
    return timeline


def summary(timeline):
    lines = [f"{timeline['source'] or 'video'}: {timeline['sample_count']} sampled frames, "
             f"{len(timeline['segments'])} segments, {len(timeline['transitions'])} transitions"]
    for segment in timeline['segments']:
        start, end = segment['start_timestamp'], segment['end_timestamp']
        lines.append(f"{start:07.2f}–{end:07.2f}  {segment['phase']}  "
                     f"({len(segment['observations'])} samples; confidence {segment['confidence']:.2f})")
    lines.append('Boundaries are bracketed by neighboring samples; no battle events are asserted.')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--video', type=Path)
    inputs.add_argument('--inspect', type=Path, help='Read an existing timeline JSON')
    parser.add_argument('--output', type=Path, help='Write timeline JSON')
    parser.add_argument('--interval', type=float, default=1.0)
    parser.add_argument('--max-frames', type=int)
    parser.add_argument('--context-annotations', type=Path, help='JSON array of reviewed contextual annotations')
    parser.add_argument('--cache-dir', type=Path, help='Save lossless sampled images for later reclassification')
    parser.add_argument('--context-ocr', action='store_true',
                        help='Read likely message panels for Revival Blessing context; slower')
    args = parser.parse_args()
    if args.inspect:
        print(summary(json.loads(args.inspect.read_text(encoding='utf-8'))))
        return
    reader = None
    if args.context_ocr:
        from recognition.paddle_ocr import create_ocr
        ocr = create_ocr('auto')
        reader = lambda image, bounds: ocr.read(image, bounds, multiline=True)
    annotations = json.loads(args.context_annotations.read_text()) if args.context_annotations else []
    timeline = process_video(args.video, interval=args.interval,
                             max_frames=args.max_frames, message_reader=reader,
                             context_annotations=annotations, cache_dir=args.cache_dir)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(timeline, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(summary(timeline))
    print(f"Runtime {timeline['runtime_seconds']:.2f}s; "
          f"{timeline['sampled_frames_per_second']:.2f} sampled frames/s")


if __name__ == '__main__':
    main()
