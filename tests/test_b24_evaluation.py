"""Saved-evidence inputs must not invalidate caches on profile load time."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest
import scripts.evaluate_b24 as runner
from scripts.trace_hidden_constraints import context_fingerprint


def test_profile_load_timestamp_does_not_change_diagnostic_input(tmp_path, monkeypatch):
    from tests.test_inference_integration import engine
    import team_configuration.profiles
    import tracking.knowledge_grounding
    source = tmp_path / 'source'; source.mkdir()
    (source / 'replay.json').write_text(json.dumps({'initial_state':engine().initial.to_dict()}))
    review = tmp_path / 'review.json'
    review.write_text(json.dumps({'profile_id':'verified', 'own_roster':{}}))
    directory = tmp_path / '.cache/team-profiles'; directory.mkdir(parents=True)
    (directory / 'verified.json').write_text(json.dumps({'configuration':{'updated_at_utc':'persisted-time'}}))
    loads = []

    class Profiles:
        def __init__(self, path): self.directory = path
        def load(self, profile_id):
            loads.append(profile_id)
            return SimpleNamespace(data={'updated_at_utc':str(len(loads)), 'fact':42})

    def attach(state, configuration, roster, **kwargs):
        state.knowledge['verified_team_profile'] = {'configuration':deepcopy(configuration)}
        return state

    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(runner, 'SOURCE', source)
    monkeypatch.setattr(runner, 'REVIEW', review)
    monkeypatch.setattr(team_configuration.profiles, 'TeamProfiles', Profiles)
    monkeypatch.setattr(tracking.knowledge_grounding, 'attach_verified_profile', attach)
    first, second = runner.payload(), runner.payload()
    assert len(loads) == 2  # Validation/loading still occurs on each call.
    assert first == second
    assert context_fingerprint(first) == context_fingerprint(second)
    assert first['initial_state']['knowledge']['verified_team_profile']['configuration'] == {
        'updated_at_utc':'persisted-time', 'fact':42}


@pytest.mark.parametrize('fact_changed', [False, True])
def test_compatible_cache_requires_exact_former_fingerprint(tmp_path, fact_changed):
    previous = {'initial_state':{'knowledge':{'verified_team_profile':{
        'configuration':{'updated_at_utc':'load-time', 'attack':100}}}}}
    current = deepcopy(previous)
    current['initial_state']['knowledge']['verified_team_profile']['configuration']['updated_at_utc'] = 'persisted-time'
    if fact_changed:
        current['initial_state']['knowledge']['verified_team_profile']['configuration']['attack'] = 101
    output = tmp_path / 'contexts.jsonl'; output.write_text('{}\n')
    replay = tmp_path / 'replay.json'; replay.write_text(json.dumps(previous))
    old_key = 'contexts:' + context_fingerprint(previous)
    new_key = 'contexts:' + context_fingerprint(current)
    manifest = {'stages':{old_key:dict(status='complete', output=output.name,
        sha256=runner.sha(output), diagnostic_replay=dict(path=replay.name, sha256=runner.sha(replay)))}}
    runner.reuse_compatible_context(current, tmp_path, manifest)
    if fact_changed:
        assert new_key not in manifest['stages']
    else:
        reused = manifest['stages'][new_key]
        assert reused['compatibility_reuse']['exact_former_fingerprint_verified']
        assert reused['sha256'] == runner.sha(output)
        assert reused['diagnostic_replay']['sha256'] == runner.sha(replay)
