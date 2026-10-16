"""Portable checks for the saved-reference branch; no acquisition or models."""
import hashlib
import json

import pytest

from battle_artifacts import BattleArtifacts
from scripts import compare_battle_log as comparison


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def setup_saved(tmp_path):
    paths = BattleArtifacts('test', tmp_path)
    folder = paths.cache('event-driven/diagnostic')
    report = paths.report('event-driven/diagnostic')
    reference = paths.cache('event-driven/original/reference/battle-log.json')
    save(folder / 'manifest.json', dict(identity=dict(video_sha256='same-video')))
    save(folder / 'video-only.json', dict(events=[]))
    save(report / 'video-only.json', dict(events=[]))
    # A historical overlay in saved observations must not trigger acquisition.
    save(folder / 'observations.json', dict(observations=[dict(ui=dict(overlay='battle_log_overlay'))]))
    save(folder / 'replay.json', {})
    hashes = {name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
              for name in ['video-only.json', 'observations.json', 'replay.json']}
    save(folder / 'video-only-seal.json', dict(stage='video_only_frozen', battle_id='test',
                                             frozen_at='2026-10-16T12:00:00Z', files=hashes))
    for name, value in [('frames.json', []), ('summary.json', {}), ('monitoring.json', [])]:
        save(report / name, value)
    row = dict(observation_id='saved-row', source_id='test.mp4#100', timestamp=100,
               raw_text='对手的龙头地鼠使出了守住！', partial=False, ocr_confidence=.99,
               color='white')
    view = dict(source_id='test.mp4#100', timestamp=100, turn=4, detected=True,
                geometry=dict(scroll_top=0, scroll_height=100), observations=[row])
    save(reference, dict(battle_id='test', views=[view]))
    save(reference.parent / 'manifest.json', dict(identity=dict(sources={
        'recognition/battle_log.py': comparison.digest(comparison.ROOT / 'recognition/battle_log.py')})))
    save(reference.parent.parent / 'manifest.json', dict(identity=dict(video_sha256='same-video')))
    return paths, folder, report, reference


def forbidden(*args, **kwargs):
    raise AssertionError('Saved-reference comparison attempted acquisition')


def test_cached_views_are_reassembled_without_acquisition_and_seal_is_preserved(tmp_path, monkeypatch):
    paths, folder, report, reference = setup_saved(tmp_path)
    before = {p: p.read_bytes() for p in [reference, folder / 'video-only.json',
                                         folder / 'observations.json', folder / 'replay.json']}
    # Backend construction is inert; any OCR read/prediction is forbidden.
    class NoOCR:
        def __init__(self, *args):
            pass
        read = forbidden
        predict = forbidden
    monkeypatch.setattr(comparison, 'CachedOCR', NoOCR)
    monkeypatch.setattr(comparison, 'extract_view', forbidden)
    monkeypatch.setattr(comparison.cv2, 'imread', forbidden)
    result = comparison.compare(paths, 'diagnostic', reference_cache=reference)
    assert result['status'] == 'complete'
    assert result['counts'] == {'reference_views_reused': 1}
    assert result['observed_log_entries'] == 1
    raw = json.loads((report / 'battle-log.json').read_text())
    assert raw['entries'][0]['raw_text'] == '对手的龙头地鼠使出了守住！'
    assert raw['entries'][0]['original_event_time'] is None
    assert raw['whole_match_coverage_established'] is False
    assert all(p.read_bytes() == value for p, value in before.items())
    assert comparison.compare(paths, 'diagnostic', reference_cache=reference, resume=True) == result


@pytest.mark.parametrize('mismatch', ['extractor', 'video', 'battle'])
def test_incompatible_saved_reference_is_rejected_before_acquisition(tmp_path, monkeypatch, mismatch):
    paths, folder, report, reference = setup_saved(tmp_path)
    if mismatch == 'extractor':
        save(reference.parent / 'manifest.json', dict(identity=dict(sources={'recognition/battle_log.py': 'changed'})))
    elif mismatch == 'video':
        save(reference.parent.parent / 'manifest.json', dict(identity=dict(video_sha256='other-video')))
    else:
        save(reference, dict(battle_id='other', views=[]))
    monkeypatch.setattr(comparison, 'CachedOCR', forbidden)
    with pytest.raises(ValueError):
        comparison.compare(paths, 'diagnostic', reference_cache=reference)
    assert not (folder / 'reference/manifest.json').exists()
    assert not (report / 'battle-log.json').exists()
