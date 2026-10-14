"""Portable Git policy and deterministic compatibility setup checks."""
import json
from pathlib import Path
import subprocess
import pytest
from scripts.setup_battle_workspace import setup
ROOT = Path(__file__).resolve().parents[1]


def test_generated_outputs_ignored_curated_inputs_and_docs_visible():
    paths = ['reports/battles/sample_battle_3/new-timeline.html',
             'reports/battles/sample_battle_3/new-state.json',
             'reports/new-ocr.json', 'reports/legacy-timeline.html',
             'reports/trace.jsonl', 'reports/frames/frame.png', '.cache/battles/a/frame.jpg']
    for path in paths:
        assert subprocess.run(['git', 'check-ignore', '--no-index', '-q', path], cwd=ROOT).returncode == 0
    for path in ['reports/battles/sample_battle_3/inputs/m223_annotations.json',
                 'reports/battles/sample_battle_3/summary.md', 'tracking/hidden_state.py',
                 'tests/fixtures/battles/sample_battle_3/reviewed_mechanic_events.json']:
        assert subprocess.run(['git', 'check-ignore', '--no-index', '-q', path], cwd=ROOT).returncode == 1


def test_compatibility_setup_is_repeatable_and_never_creates_broken_links(tmp_path):
    (tmp_path/'data').mkdir()
    (tmp_path/'data/battle_artifact_aliases.json').write_text(json.dumps({'aliases': [
        {'legacy': 'reports/old.json', 'canonical': 'reports/battles/sample_battle_3/state.json'},
        {'legacy': 'reports/missing.json', 'canonical': 'reports/battles/sample_battle_3/missing.json'}]}))
    target=tmp_path/'reports/battles/sample_battle_3/state.json';target.parent.mkdir(parents=True);target.write_text('preserve')
    result=setup(tmp_path)
    assert result['created']==['reports/old.json']
    assert not (tmp_path/'reports/missing.json').is_symlink()
    assert (tmp_path/'reports/old.json').samefile(target)
    assert setup(tmp_path)['created']==[] and target.read_text()=='preserve'
    (tmp_path/'reports/old.json').unlink();(tmp_path/'reports/old.json').write_text('historical data')
    with pytest.raises(FileExistsError):setup(tmp_path)
    assert (tmp_path/'reports/old.json').read_text()=='historical data'
