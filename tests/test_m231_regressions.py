"""Matching-profile observable facts and one authoritative revealed-move ledger."""
from copy import deepcopy
from pathlib import Path
import pytest
from scripts.replay_m231 import run
from scripts.optimize_state_timeline import payload
from tracking.state_timeline import unpack_timeline
from tracking.pokemon_knowledge import pokemon_knowledge
ROOT = Path(__file__).resolve().parents[1]
KING = 'sample_battle_3:opponent:preview:3'
SNEASLER = 'sample_battle_3:opponent:preview:5'


@pytest.mark.parametrize('reference', [False, True])
@pytest.mark.local_artifacts('reports/M2.2.4-enriched-battle-state.json','reports/M2.2.4-provisional-battle-state.json','reports/M2.2.4-enriched-timeline.html','reports/M2.2.4-provisional-timeline.html')
def test_matching_milestone_every_prefix(reference):
    engine, timeline, metrics = run(provisional=reference)
    stem = 'provisional' if reference else 'enriched'
    original = unpack_timeline(payload((ROOT / f'reports/M2.2.4-{stem}-timeline.html').read_text()))
    assert timeline['mechanic_rules'] == original['mechanic_rules']
    assert len(timeline['entries']) == len(original['entries']) == 197
    for before, after in zip(original['entries'], timeline['entries']):
        observable = deepcopy(after['after'])
        observable['knowledge'].pop('hidden_configuration')
        views = observable['knowledge'].pop('pokemon_projection')
        # All observable fields, including HP, identities, stages and causal receipts,
        # are preserved at every prefix, including initial state and switch resets.
        assert observable == before['after']
        hidden = after['after']['knowledge']['hidden_configuration']
        assert views == pokemon_knowledge(observable['pokemon'], hidden)
        for pid in (KING, SNEASLER):
            if pid in hidden['pokemon']:
                assert [m['canonical_id'] for m in views[pid]['revealed_moves']] == hidden['pokemon'][pid]['fields']['moves']['members']
                assert views[pid]['exact_slots'] == {}
    result = next(e for e in timeline['entries'] if e['event'] and e['event']['event_id'] == 'event:2738c9d3d00589c09fc08d39')
    stage = result['after']['pokemon'][KING]['stages']['attack']
    if reference:
        assert result['before']['pokemon'][KING]['stages']['attack']['value']['value'] == 0
        assert stage['value']['value'] == 2
        assert stage['changes'][-1]['amount'] == 2
    assert timeline['entries'][-1]['after']['pokemon'][KING]['stages']['attack']['value']['value'] is None
    final = timeline['entries'][-1]['after']['knowledge']['pokemon_projection']
    assert {m['canonical_id'] for m in final[KING]['revealed_moves']} == {'pokeapi:move:14', 'pokeapi:move:389'}
    assert {m['canonical_id'] for m in final[SNEASLER]['revealed_moves']} == {'pokeapi:move:370', 'pokeapi:move:182'}
    assert final[KING]['unrevealed_count'] == (2 if reference else None)
    assert metrics['hp_checkpoints'] == metrics['identity_checkpoints'] == 28
    seen = set()
    for entry in timeline['entries']:
        moves = {m['canonical_id'] for m in entry['after']['knowledge']['pokemon_projection'].get(SNEASLER, {}).get('revealed_moves', [])}
        assert seen <= moves
        seen = moves


@pytest.mark.parametrize('reference', [False, True])
def test_hidden_enabled_preserves_general_observable_prefixes(reference):
    from tests.test_knowledge_grounding import setup_pair
    from tracking.state_engine import StateEngine
    from tracking.hidden_state import HiddenEngine, HiddenRules
    baseline, use, result, pid = setup_pair(reference)
    enabled = StateEngine.from_dict(baseline.to_dict())
    hidden = HiddenEngine(rules=HiddenRules('showdown-champions-reference-v1' if reference else 'champions-evidence-only-v1'))
    hidden.seed(baseline.to_dict()['initial_state'])
    for sequence, event in enumerate([None, use, result]):
        if event:
            baseline.apply(event, sequence=sequence)
            enabled.apply(event, sequence=sequence)
            hidden.apply(event, instance_id=pid, side='opponent', sequence=sequence)
        before = enabled.to_dict()
        plain = baseline.decision_state()
        combined = enabled.decision_state(hidden_engine=hidden)
        assert enabled.to_dict() == before == baseline.to_dict()
        for key in ('field', 'sides', 'rule_profile', 'turn', 'phase'):
            assert combined[key] == plain[key]
        for key, mon in combined['pokemon'].items():
            observable = deepcopy(mon)
            view = observable.pop('knowledge')
            assert observable == plain['pokemon'][key]
            assert view == pokemon_knowledge(plain['pokemon'], hidden.projection())[key]


def test_projection_is_read_only_and_preserves_supported_slot_evidence():
    pokemon = {'p': {'moves': {'known_slots': {'2': {'knowledge': 'observed', 'value': {'canonical_id': 'pokeapi:move:14'}, 'provenance': [{'event_id': 'slot-evidence'}]}}}}}
    hidden = {'move_capacity': 4, 'pokemon': {'p': {'fields': {'moves': {'members': ['pokeapi:move:14'], 'slots': {}, 'status': 'confirmed', 'constraints': ['member-proof']}}}}}
    before = deepcopy((pokemon, hidden))
    view = pokemon_knowledge(pokemon, hidden)['p']
    assert view['exact_slots'] == {'2': 'pokeapi:move:14'}
    assert view['unrevealed_count'] == 3
    assert view['revealed_moves'][0]['name'] != 'pokeapi:move:14'
    assert (pokemon, hidden) == before
    view['exact_slot_evidence']['2']['provenance'].clear()
    assert (pokemon, hidden) == before
