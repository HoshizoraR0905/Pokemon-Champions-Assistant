"""The offline reviewer must reproduce sealed state, never acquire evidence."""
import json
import pytest
from scripts.build_battle_evaluation import timeline,slots
from tests.test_command_reconciliation import engine


def test_saved_timeline_matches_every_prefix_and_reuses_completed_output(tmp_path):
    e=engine();original=json.loads(json.dumps(e.to_dict()));folder=tmp_path/'run';target=tmp_path/'review'
    folder.mkdir();target.mkdir();p=folder/'replay.json';p.write_text(json.dumps(original))
    first=timeline(folder,target);assert first['all_original_receipts_and_hashes_equal']
    assert first['changes'][-1]['slots']==slots(e.state)
    assert timeline(folder,target)==first
    assert json.loads(p.read_text())==original


def test_frozen_timeline_refuses_a_mismatching_receipt(tmp_path):
    original=engine().to_dict();original['history'][0]['state_hash']='wrong'
    folder=tmp_path/'run';target=tmp_path/'review';folder.mkdir();target.mkdir()
    (folder/'replay.json').write_text(json.dumps(original))
    with pytest.raises(AssertionError):timeline(folder,target)
    assert not (target/'timeline.json').exists()
