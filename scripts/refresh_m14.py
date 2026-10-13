"""Refresh final M1.4 timelines once, or reclassify verified lossless sampled-frame caches."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capture import Frame, load_image
from phase_timeline import build_timeline, process_video, summary

ROOT = Path(__file__).resolve().parents[1]


def classifier_fingerprint():
    return {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
            ['recognition/__init__.py', 'recognition/phases.py', 'phase_timeline.py']}


def source_fingerprint(path):
    stat = path.stat()
    return {'size_bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns}


def refresh(name, *, reuse_cache=False):
    source = Path('tests/fixtures')/name
    destination = ROOT/'reports'/('M1.4-final-'+name.removesuffix('.mp4').replace('_','-')+'-timeline.json')
    context_path = ROOT/'tests/fixtures/m14_selection_context.json'
    annotations = json.loads(context_path.read_text())
    cache = ROOT/'.cache/m14-phases'/name.removesuffix('.mp4')
    manifest_path = cache/'manifest.json'
    started = time.perf_counter()
    fingerprint = source_fingerprint(ROOT/source)
    if reuse_cache:
        manifest = json.loads(manifest_path.read_text())
        if manifest['source_fingerprint'] != fingerprint or manifest['source'] != str(source):
            raise ValueError('Cached source fingerprint no longer matches the video')
        def cached_frames():
            for entry in manifest['frames']:
                path = ROOT/entry['image']
                if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                    raise ValueError(f'Cached frame checksum mismatch: {path}')
                frame = load_image(path)
                yield Frame(frame.image, str(source), entry['index'], entry['timestamp'], entry['metadata'])
        timeline = build_timeline(cached_frames(), interval=manifest['interval'],
                                  duration=manifest['duration'], context_annotations=annotations)
        timeline['runtime_seconds'] = round(time.perf_counter()-started,3)
        timeline['processing_method'] = 'reclassified_verified_lossless_sample_cache'
    else:
        timeline = process_video(source, interval=2., context_annotations=annotations,
                                 cache_dir=cache.relative_to(ROOT))
        timeline['processing_method'] = 'fresh_full_video_sequential_sampling'
        entries = []
        for segment in timeline['segments']:
            for observation in segment['observations']:
                path = Path(observation['capture_metadata']['phase_cache_path'])
                entries.append({'index':observation['frame_index'],'timestamp':observation['timestamp'],
                                'metadata':observation['capture_metadata'], 'image':str(path),
                                'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        manifest = {'schema_version':1,'source':str(source),'source_fingerprint':fingerprint,
                    'interval':2.,'duration':timeline['duration_seconds'],'frames':entries,
                    'encoding':'lossless PNG, normalized width <=1311; matching classify_phase preprocessing'}
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    timeline['source_fingerprint'] = fingerprint
    timeline['classifier_fingerprint'] = classifier_fingerprint()
    timeline['context_annotation_source'] = 'tests/fixtures/m14_selection_context.json'
    timeline['context_annotation_sha256'] = hashlib.sha256(context_path.read_bytes()).hexdigest()
    timeline['evaluation_coverage'] = 'Full recording sampled every two seconds; sparse manual labels only.'
    timeline['cache_manifest'] = str(manifest_path.relative_to(ROOT))
    destination.write_text(json.dumps(timeline,ensure_ascii=False,indent=2)+'\n')
    print(summary(timeline))
    print(f"Runtime: {timeline['runtime_seconds']}s; output: {destination}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video',choices=['sample_battle.mp4','sample_battle_1.mp4'],required=True)
    parser.add_argument('--reuse-cache',action='store_true')
    args=parser.parse_args()
    refresh(args.video,reuse_cache=args.reuse_cache)
