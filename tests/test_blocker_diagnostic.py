"""Diagnostics preserve frozen inputs and reject stale or occupied namespaces."""
import json
import pytest
from battle_artifacts import BattleArtifacts
from recognition.fast_video import digest
from scripts.diagnose_m238w import diagnose
from tests.test_command_reconciliation import engine


def test_diagnostic_keeps_sealed_source_and_reuses_only_matching_results(tmp_path):
    owner=BattleArtifacts('test',tmp_path);source=owner.cache('event-driven/original')
    source.mkdir(parents=True)
    (source/'replay.json').write_text(json.dumps(engine().to_dict()))
    original=digest(source/'replay.json')
    (source/'video-only-seal.json').write_text(json.dumps(dict(stage='video_only_frozen',
        files={'replay.json':original})))
    result=diagnose(owner,'original','diagnostic')
    assert result['recognition_calls']==0 and result['diagnostic_only']
    assert not result['applied_status_regressions']
    assert digest(source/'replay.json')==original
    assert diagnose(owner,'original','diagnostic')==result
    target=owner.cache('evaluation/diagnostic')
    (target/'summary.json').write_text('{}')
    with pytest.raises(ValueError,match='output changed'):
        diagnose(owner,'original','diagnostic')
    owner.cache('evaluation/occupied').mkdir()
    with pytest.raises(ValueError,match='Existing namespace'):
        diagnose(owner,'original','occupied')
