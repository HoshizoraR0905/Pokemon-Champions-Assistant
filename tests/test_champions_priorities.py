"""M-C priority corrections; no video or generation-wide data rewriting."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from battle_evidence.actions import action_priority
from knowledge import KnowledgeBase
from scripts.refresh_champions import apply_priority_corrections
from speed_order.execution import priority
from speed_order.mechanics import AUDITED_MOVES, effective_priority, move_fact, ordering_coverage, sources
from test_dynamic_action_order import action, participant, simulate, state


@pytest.mark.parametrize('cid,move,zh,expected', [
    ('pokeapi:move:252', 'Fake Out', '击掌奇袭', 3),
    ('pokeapi:move:266', 'Follow Me', '看我嘛', 2),
    ('pokeapi:move:476', 'Rage Powder', '愤怒粉', 2),
])
def test_mc_priority_across_catalog_and_order_adapters(cid, move, zh, expected):
    kb = KnowledgeBase(regulation='M-C')
    p = participant('a', 100)
    assert kb.facts['moves'][cid]['priority'] == expected
    for label in [move, zh, cid]:
        assert move_fact(label)[1:] == (cid, kb.facts['moves'][cid])
        assert priority(label, p) == expected
        assert effective_priority(action('a', label), p, state(p)['field'])['effective'] == expected
    assert action_priority(cid, None, None, None)['base_priority'] == expected
    receipt = ordering_coverage()['moves'][move]
    assert receipt['catalog_priority'] == receipt['reference_priority'] == expected
    assert receipt['supported'] or move in AUDITED_MOVES
    assert not receipt['priority_conflict']


@pytest.mark.parametrize('redirect', ['Follow Me', 'Rage Powder'])
def test_fake_out_precedes_faster_redirection_and_prankster_can_tie(redirect):
    a, b = participant('a', 50), participant('b', 200)
    result = simulate(state(a, b), [action('a', 'Fake Out'), action('b', redirect)])
    assert result['status'] == 'exact'
    assert result['traces'][0]['sequence'] == ['a:move', 'b:move']
    b.update(ability='Prankster', actual_speed=50)
    result = simulate(state(a, b), [action('a', 'Fake Out'), action('b', redirect)])
    assert result['status'] == 'exact'
    assert {tuple(t['sequence']) for t in result['traces']} == {
        ('a:move', 'b:move'), ('b:move', 'a:move')}


def test_same_priority_redirection_uses_speed_and_trick_room():
    a, b = participant('a', 100), participant('b', 150)
    actions = [action('a', 'Follow Me'), action('b', 'Rage Powder')]
    for room, expected in [(False, ['b:move', 'a:move']), (True, ['a:move', 'b:move'])]:
        result = simulate(state(a, b, trick_room=room), actions)
        assert result['status'] == 'exact'
        assert result['traces'][0]['sequence'] == expected


def test_correction_retains_upstream_assertions_and_is_scoped_and_repeatable():
    facts = deepcopy(KnowledgeBase().facts)
    for cid in ['pokeapi:move:266', 'pokeapi:move:476']:
        provenance = facts['moves'][cid]['priority_provenance']
        assert provenance['previous_priority'] == 3
        assert provenance['previous_source'] == facts['source']
        facts['moves'][cid].pop('priority_provenance')
        facts['moves'][cid]['priority'] = 3
    before = deepcopy(facts)
    apply_priority_corrections(facts)
    corrected = deepcopy(facts)
    apply_priority_corrections(facts)
    assert facts == corrected
    for cid, row in before['moves'].items():
        if cid not in {'pokeapi:move:266', 'pokeapi:move:476'}:
            assert facts['moves'][cid] == row
    historical = deepcopy(before)
    historical['regulation'] = 'Generation V'
    unchanged = deepcopy(historical)
    apply_priority_corrections(historical)
    assert historical == unchanged
    before['moves']['pokeapi:move:476']['priority'] = 1
    with pytest.raises(ValueError, match='Upstream priority changed'):
        apply_priority_corrections(before)


def test_correction_and_solver_provenance_hashes():
    root = Path(__file__).resolve().parents[1]
    kb = KnowledgeBase()
    for filename in ['champions_facts.json', 'champions_priority_corrections.json']:
        digest = hashlib.sha256((root/'knowledge/data'/filename).read_bytes()).hexdigest()
        assert kb.manifest['files'][filename] == digest
    assert sources()['knowledge_facts_sha256'] == kb.manifest['files']['champions_facts.json']
    assert sources()['champions_priority_corrections']['sha256'] == kb.manifest['files']['champions_priority_corrections.json']
    receipt = json.loads((root/'knowledge/data/champions_priority_corrections.json').read_text())
    for cid in receipt['moves']:
        assert kb.facts['moves'][cid]['priority_provenance']['source_sha256'] == kb.manifest['files']['champions_priority_corrections.json']
