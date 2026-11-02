"""History isolation, legacy compatibility, and lossless compact transport."""
from copy import deepcopy
import hashlib
import json

import pytest

from tracking.battle_state import BattleState, PokemonState, Fact
from tracking.evidence_history import (
    EvidenceDict, EvidenceHistory, canonical, expand_compact, freeze, seal_state,
)
from tracking.state_engine import hash_state, StateEngine


def state_with_history():
    state = BattleState('history-test')
    p = PokemonState('p', 'self')
    state.pokemon['p'] = p
    state.sides['self'].party_instance_ids.append('p')
    p.hp.current = Fact(50, 'observed', [{'event_id': 'hp-1', 'sources': [{'text': '体力'}]}])
    p.hp.observations = [{'after': 50, 'unit': 'absolute', 'delta': None, 'evidence': {'event_id': 'hp-1'}}]
    seal_state(state)
    return state


def test_trial_shares_history_payload_but_isolates_current_and_revisions():
    before = state_with_history()
    trial = deepcopy(before)
    assert trial.pokemon['p'].hp.observations is not before.pokemon['p'].hp.observations
    assert trial.pokemon['p'].hp.observations[0] is before.pokemon['p'].hp.observations[0]
    trial.pokemon['p'].hp.current.value = 20
    trial.pokemon['p'].hp.observations[0] = {'after': 20}
    trial.pokemon['p'].hp.observations.append({'after': 10})
    seal_state(trial)
    assert before.pokemon['p'].hp.current.value == 50
    assert before.pokemon['p'].hp.observations == [{'after': 50, 'unit': 'absolute', 'delta': None, 'evidence': {'event_id': 'hp-1'}}]
    assert isinstance(trial.pokemon['p'].hp.observations[0], EvidenceDict)


@pytest.mark.parametrize('edit', [
    lambda x: x.clear(), lambda x: x.pop(), lambda x: x.reverse(),
    lambda x: x.insert(0, {'x': [4]}), lambda x: x.__setitem__(slice(None), [{'x': [5]}]),
    lambda x: x.__imul__(0), lambda x: x.remove(x[0]),
])
def test_reference_sequence_edits_never_share_unsealed_payloads(edit):
    history = EvidenceHistory([{'x': [1]}, {'x': [2]}])
    edit(history)
    history.append({'x': [3]})
    copy = deepcopy(history)
    copy[-1]['x'].append(7)
    assert history[-1]['x'] == [3]
    history.seal()
    assert isinstance(history[-1], EvidenceDict)
    with pytest.raises(TypeError):
        history[-1]['x'].append(4)


def test_legacy_hash_and_exports_stay_exact_and_detached():
    state = state_with_history()
    plain = state.to_dict()
    expected = hashlib.sha256(json.dumps(plain, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    assert hash_state(state) == expected
    plain['pokemon']['p']['hp']['observations'][0]['evidence']['event_id'] = 'edited'
    assert state.pokemon['p'].hp.observations[0]['evidence']['event_id'] == 'hp-1'
    for value in ({1: ['中文', None, True, -0.0]}, {None: 3}, {'a': (1, 2)}):
        assert canonical(value) == json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def test_departure_payload_is_shared_by_episode_and_return_proof():
    state = state_with_history()
    departure = freeze({'historical_hp': state.pokemon['p'].hp})
    state.knowledge = {'active_entry_episodes': [{'departure': departure}],
                       'identity_ledger': {'persistent_returns': [{'departure': departure}]}}
    trial = deepcopy(state)
    assert trial.knowledge['active_entry_episodes'][0]['departure'] is departure
    assert trial.knowledge['identity_ledger']['persistent_returns'][0]['departure'] is departure
    packet = state.compact_export()
    assert expand_compact(json.loads(json.dumps(packet))) == state.to_dict()
    refs = packet['current']['fields']['knowledge']['fields']
    a = refs['active_entry_episodes']['items'][0]['fields']['departure']
    b = refs['identity_ledger']['fields']['persistent_returns']['items'][0]['fields']['departure']
    assert a == b
    assert len([k for k in packet['evidence'] if k == a['sha256']]) == 1


def test_compact_transport_integrity_and_empty_knowledge():
    state = state_with_history()
    packet = state.compact_export()
    assert expand_compact(packet) == state.to_dict()
    key = next(iter(packet['evidence']))
    packet['evidence'][key] = {'node': 'value', 'value': 'corrupted'}
    with pytest.raises(ValueError, match='digest mismatch'):
        expand_compact(packet)
    packet = state.compact_export()
    key = next(iter(packet['evidence']))
    packet['evidence'][key] = {'node': 'evidence', 'sha256': key}
    with pytest.raises(ValueError, match='Cyclic'):
        expand_compact(packet)
    assert expand_compact(BattleState('empty').compact_export()) == BattleState('empty').to_dict()


def test_current_transport_does_not_expand_with_historical_payloads():
    state = state_with_history()
    small = state.compact_export()
    state.observations.extend({'event_id': str(i), 'raw_text': '历史消息' * 100} for i in range(200))
    seal_state(state)
    large = state.compact_export()
    assert len(json.dumps(small['current'])) == len(json.dumps(large['current']))
    assert len(json.dumps(large['evidence'])) > len(json.dumps(small['evidence']))
    assert expand_compact(large) == state.to_dict()


def test_rejected_trial_does_not_leak_shared_evidence():
    from tests.test_evidence_fusion import hud
    from tracking.mechanics import MechanicRegistry

    class RejectAfterHistoryRevision:
        mechanic_id = 'reject-test'
        def on_event(self, state, before, pokemon, event, rules):
            state.observations.append({'private_trial': True})
            raise ValueError('rejected after history append')

    engine = StateEngine(BattleState('test'), mechanic_registry=MechanicRegistry([RejectAfterHistoryRevision()]))
    record = engine.apply(hud(1, 1, 823), sequence=1)
    assert record.application_status == 'rejected'
    assert record.reason == 'rejected after history append'
    assert not engine.state.observations
    assert not engine.state.pokemon
    assert len(engine.state.conflicts) == 1
    record.bindings['caller_edit'] = True
    assert 'caller_edit' not in engine.history[0].bindings
