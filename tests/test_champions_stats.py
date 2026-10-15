"""Independent published ranges, exact integer sets and joint legality."""
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path

import pytest

from knowledge import KnowledgeBase
from knowledge.champions_stats import (
    STATS, ChampionsStats, adjustment_factors, alignment_patterns,
    legal_allocations, validate_training_points,
)

FIXTURE = json.loads(Path('tests/fixtures/champions_stats/52poke-ranges.json').read_text())
ZERO = dict.fromkeys(STATS, 0)
NEUTRAL = {'increase': None, 'decrease': None}
ADAMANT = {'increase': 'attack', 'decrease': 'special_attack'}


@pytest.mark.parametrize('case', FIXTURE['cases'], ids=lambda c: c['identity'])
@pytest.mark.parametrize('stat', STATS)
def test_published_champions_ranges(case, stat):
    model = ChampionsStats(case['identity'], form=case['form'])
    assert model.base_stats == case['base_stats']
    result = model.attainable(stat, adjustments=['1.0'] if stat == 'hp' else ['0.9', '1.0', '1.1'])
    assert [result['minimum'], result['maximum']] == case['ranges'][stat]
    assert result['provenance']['profile'] == '52poke-champions-stats-v1'


def test_exact_floors_and_reverse_exhaustively():
    model = ChampionsStats('Charizard', form='base')
    for stat in STATS:
        adjustments = ['1.0'] if stat == 'hp' else ['0.9', '1.0', '1.1']
        expected = set()
        for p in range(33):
            for a in adjustments:
                base = model.base_stats[stat]
                actual = base+p+75 if stat == 'hp' else int(Fraction(base+p+20) * Fraction(a))
                expected.add(actual)
                configurations = model.reverse_lookup(stat, actual, adjustments=adjustments)['configurations']
                assert dict(training_points=p, adjustment=a, actual_stat=actual) in configurations
        assert model.attainable(stat, adjustments=adjustments)['values'] == sorted(expected)


def test_discrete_gaps_are_preserved():
    result = ChampionsStats('Charizard', form='base').attainable('attack', adjustments=['0.9','1.0','1.1'])
    assert result['has_gaps']
    assert 142 not in result['values'] and result['minimum'] == 93 and result['maximum'] == 149
    assert ChampionsStats('Charizard', form='base').reverse_lookup('attack', 142, adjustments=['0.9','1.0','1.1'])['configurations'] == []


def test_calculate_complete_build_and_no_mutation():
    points = dict(ZERO, attack=32, speed=32, hp=2)
    original = deepcopy(points)
    model = ChampionsStats('喷火龙', form='base')
    result = model.calculate(points, ADAMANT)
    assert result['stats'] == dict(hp=155, attack=149, defense=98, special_attack=116, special_defense=105, speed=152)
    assert result['unused_points'] == 0 and points == original
    assert model.calculate(ZERO, NEUTRAL)['unused_points'] == 66
    result['provenance']['sources'].clear()
    assert model.provenance['sources']
    base = model.base_stats
    base['attack'] = 999
    assert model.base_stats['attack'] == 84


@pytest.mark.parametrize('points', [dict(ZERO, attack=-1), dict(ZERO, attack=33),dict(ZERO, hp=3, attack=32, speed=32),dict(ZERO, attack=True),dict(ZERO, attack=1.5),{},dict(ZERO, bogus=0)])
def test_invalid_allocations(points):
    with pytest.raises(ValueError): validate_training_points(points)


@pytest.mark.parametrize('alignment', [None,{}, {'increase':'hp','decrease':'attack'}, {'increase':'attack','decrease':None}, {'increase':'attack','decrease':'attack'}, {'increase':[], 'decrease':'speed'}])
def test_invalid_alignments(alignment):
    with pytest.raises(ValueError): adjustment_factors(alignment)


def test_alignment_patterns():
    rows = alignment_patterns()
    assert len(rows) == 21
    for row in rows:
        factors = adjustment_factors(row)
        assert factors['hp'] == '1.0'
        assert list(factors.values()).count('1.1') == list(factors.values()).count('0.9') <= 1


def test_allocation_enumeration_budget_and_work_bound():
    domains = dict.fromkeys(STATS, [0])
    domains.update(attack=[31,32], speed=[31,32], hp=[0,2,3])
    rows = list(legal_allocations(domains))
    assert len(rows) == 11 and all(sum(r.values()) <= 66 for r in rows)
    with pytest.raises(ValueError, match='work limit'):
        legal_allocations(dict.fromkeys(STATS, range(33)))
    with pytest.raises(ValueError): legal_allocations(dict.fromkeys(STATS, []))
    with pytest.raises(ValueError): legal_allocations(dict.fromkeys(STATS, range(1000000000)))


def test_remaining_budget_and_empty_projection():
    model = ChampionsStats('Sneasler', form='base')
    result = model.attainable('attack', adjustments=['1.1'], allocated_other={'hp':32,'speed':32})
    assert [r['training_points'] for r in result['configurations']] == [0,1,2]
    empty = model.attainable('attack', adjustments=['1.1'],point_domain=[32], allocated_other={'hp':32,'speed':32})
    assert empty['values'] == [] and empty['minimum'] is None
    with pytest.raises(ValueError): model.attainable('attack', adjustments=['1.0'], allocated_other={'attack':32})


def test_joint_reverse_lookup_rejects_incompatible_marginals():
    model = ChampionsStats('Charizard', form='base')
    # Both maxima are separately possible; both need the single increased stat.
    domains = dict.fromkeys(STATS, [0])
    domains.update(attack=[32],special_attack=[32])
    result = model.reverse_configurations({'attack':149,'special_attack':177}, alignments=alignment_patterns(), point_domains=domains)
    assert result['count'] == 0
    # All three require 32 points, exceeding the shared total even with neutral.
    domains.update(hp=[32])
    result = model.reverse_configurations({'hp':185,'attack':136,'special_attack':161}, alignments=[NEUTRAL], point_domains=domains)
    assert result['count'] == 0


def test_joint_reverse_retains_original_full_build():
    model = ChampionsStats('Sneasler', form='base')
    points = dict(ZERO, hp=2,attack=32,speed=32)
    actual = model.calculate(points, ADAMANT)['stats']
    domains = {s: sorted({max(0,p-1),p}) for s,p in points.items()}
    result = model.reverse_configurations(actual, alignments=alignment_patterns(), point_domains=domains)
    assert result['configurations'] == [dict(training_points=points,alignment=ADAMANT)]


@pytest.mark.parametrize('identity,form', [('Charizard',None),('Charizard','Sneasler'),('Charizard-Mega-X','base'),('bogus','base'),('pokeapi:pokemon:x',None)])
def test_invalid_or_ambiguous_identity(identity,form):
    with pytest.raises(ValueError): ChampionsStats(identity,form=form)


def test_shared_canonical_form_and_pokemon_identity():
    kb = KnowledgeBase()
    mega = kb.entities[ChampionsStats('Charizard-Mega-X').identity]
    assert ChampionsStats(mega.canonical_id).base_stats['attack'] == 130
    assert ChampionsStats('Charizard',form=mega.canonical_id).identity == mega.canonical_id
    row = kb.identities.forms[mega.form_id]
    assert ChampionsStats(f"pokeapi:pokemon:{row['pokemon_id']}").base_stats['attack'] == 130
    assert ChampionsStats('pokeapi:pokemon:6').base_stats['attack'] == 84


@pytest.mark.parametrize('kwargs',[{'adjustments':None},{'adjustments':[0.9]}, {'adjustments':['1.2']},{'adjustments':['1.0'],'point_domain':[True]}])
def test_invalid_projection_inputs(kwargs):
    with pytest.raises(ValueError): ChampionsStats('Charizard',form='base').attainable('attack',**kwargs)


def test_hp_adjustment_not_permitted():
    with pytest.raises(ValueError): ChampionsStats('Charizard',form='base').attainable('hp',adjustments=['1.1'])


def test_unknown_and_fixed_hp_data_fail_explicitly():
    kb = KnowledgeBase()
    entry = kb.facts['pokemon']['pokeapi:species:6']
    original = deepcopy(entry)
    try:
        entry['stats']['hp'] = 1
        with pytest.raises(NotImplementedError): ChampionsStats('Charizard',form='base',knowledge=kb)
        entry['stats'] = {}
        with pytest.raises(ValueError): ChampionsStats('Charizard',form='base',knowledge=kb)
    finally:
        kb.facts['pokemon']['pokeapi:species:6'] = original


def test_source_pins_and_fixture_integrity():
    manifest = json.loads(Path('tests/fixtures/champions_stats/manifest.json').read_text())
    for name,digest in manifest['files'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest
    rules = json.loads(Path('knowledge/data/champions_stat_rules.json').read_text())
    assert [s['revision_id'] for s in rules['sources']] == [2607357,2568467,2628728]
    assert all(s['license'] == 'CC BY-NC-SA 3.0' for s in rules['sources']+FIXTURE['sources'])
