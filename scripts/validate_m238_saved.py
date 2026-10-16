"""Compare sealed M2.3.8 predictions in a NEW namespace without acquisition.

Existing runs and reports are read only. A used target run ID is rejected.
The output is diagnostic; reference data was already available before v3.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
import json
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from battle_artifacts import BattleArtifacts, canonical_id
from recognition.event_report import verify_seal
from recognition.fast_video import digest
from scripts.compare_battle_log import compare


def forbidden(*args, **kwargs):
    raise AssertionError('Acquisition is forbidden in saved M2.3.8 validation')


def validate(run_id):
    paths = BattleArtifacts('sample_battle_6', ROOT)
    source = paths.cache('event-driven/m238-live-3-diagnostic')
    source_report = paths.report('event-driven/m238-live-3-diagnostic')
    reference = paths.cache('event-driven/m238-live-2/reference/battle-log.json')
    run_id = canonical_id(run_id)
    target = paths.cache('event-driven/' + run_id)
    report = paths.report('event-driven/' + run_id)
    if target.exists() or report.exists():
        raise ValueError('Target already exists; preserve it and choose a new run ID')
    seal = verify_seal(source)
    manifest = json.loads((source / 'manifest.json').read_text())
    if manifest['status'] != 'complete' or not manifest.get('reference_previously_available'):
        raise ValueError('Expected completed post-reference diagnostic checkpoint')
    for name, expected in manifest['identity']['sources'].items():
        if digest(ROOT / name) != expected:
            raise ValueError('Current source changed: ' + name)
    prediction = json.loads((source / 'video-only.json').read_text())
    for name in ['video-only.json', 'summary.json', 'frames.json', 'monitoring.json']:
        json.loads((source_report / name).read_text())
    if digest(source_report / 'video-only.json') != seal['files']['video-only.json']:
        raise ValueError('Source report does not match sealed prediction')
    # Snapshot each original non-image artifact in these four scoped namespaces.
    originals = {}
    for base in [source, source_report, reference.parent,
                 paths.report('event-driven/m238-live-2')]:
        for p in base.rglob('*'):
            if p.is_file() and p.suffix in {'.json', '.html', '.py', '.txt', '.log'}:
                originals[p] = digest(p)
    target.mkdir(parents=True)
    report.mkdir(parents=True)
    for name in [*seal['files'], 'video-only-seal.json']:
        shutil.copy2(source / name, target / name)
    clone = dict(manifest, validation_copy_of=str(source.relative_to(ROOT)),
                 completed_stages=['sealed_prediction_copied'],
                 validation_kind='post_reference_diagnostic_no_reconstruction')
    with (target / 'manifest.json').open('x') as stream:
        json.dump(clone, stream, indent=2)
    for name in ['video-only.json', 'summary.json', 'frames.json', 'monitoring.json']:
        shutil.copy2(source_report / name, report / name)
    assets = report / 'assets'
    assets.mkdir()
    for p in (source_report / 'assets').glob('*.png'):
        # Only immutable images are linked; every mutable JSON is copied.
        try:
            os.link(p, assets / p.name)
        except OSError:
            shutil.copy2(p, assets / p.name)
    with ExitStack() as stack:
        for symbol in ['scripts.compare_battle_log.extract_view',
                       'recognition.fast_video.CachedOCR.read',
                       'recognition.fast_video.CachedOCR.predict',
                       'recognition.fast_video.decoded_frames',
                       'recognition.fast_video.CachedIcons.identify',
                       'cv2.imread', 'cv2.VideoCapture']:
            stack.enter_context(patch(symbol, forbidden))
        result = compare(paths, run_id, reference_cache=reference)
    verify_seal(target)
    if any(digest(p) != expected for p, expected in originals.items()):
        raise AssertionError('Original artifact changed')
    moves = [r for r in prediction['receipts'] if r['kind'] == 'move_execution']
    entries = [r for r in prediction['receipts'] if r['kind'] == 'entry_observation']
    audit = dict(status='complete', diagnostic=True, source_prediction_sha256=seal['files']['video-only.json'],
                 original_files_unchanged=len(originals), acquisition_calls=0,
                 reference_summary=result['summary'], reference_counts=result['counts'],
                 event_counts=dict(Counter(e['event_type'] for e in prediction['events'])),
                 move_receipts=dict(Counter(r['status'] for r in moves)),
                 entry_receipts=dict(Counter(r['status'] for r in entries)),
                 browser_validation='pending', semantic_acceptance=False)
    with (target / 'saved-validation.json').open('x') as stream:
        json.dump(audit, stream, indent=2)
    return audit


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    print(json.dumps(validate(parser.parse_args().run_id), indent=2))
