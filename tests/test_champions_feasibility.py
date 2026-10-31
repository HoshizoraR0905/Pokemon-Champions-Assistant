from copy import deepcopy
import json
from pathlib import Path
from itertools import product
import subprocess
import sys

import pytest
from knowledge.champions_stats import ChampionsStats, STATS, alignment_patterns
from knowledge.stat_feasibility import champions_attainable_stats, allowed
from damage.champions_feasibility import infer_champions_attack_stat
from damage.inverse_cli import solve

RANGES=json.loads(Path('tests/fixtures/champions_stats/52poke-ranges.json').read_text())


def request(damage=35):
    r=json.loads(Path('examples/inverse_damage/single.json').read_text())
    r['champions']=dict(identity='Charizard',form='base')
    r['observations'][0]['damage']=damage
    # These template fields were synthetic placeholders, not known actual stats.
    a=r['observations'][0]['input']['attacker']
    a['stats']={s:None for s in a['stats']};a['maximum_hp']=None;a['current_hp']=None
    return r


@pytest.mark.parametrize('case',RANGES['cases'],ids=lambda c:c['identity'])
@pytest.mark.parametrize('stat',STATS)
def test_independent_published_champions_tables(case,stat):
    r=champions_attainable_stats(identity=case['identity'],form=case['form'],stat=stat)
    assert r['status']=='exact' and r['joint_feasible']==r['attainable']
    assert r['attainable']['hull']==case['ranges'][stat]
    assert r['provenance']['sources'][0]['revision_id']==2607357


def test_joint_budget_cannot_combine_marginal_maxima():
    # Explicit neutral means HP=185, Attack=136, Speed=152 each cost 32.
    neutral=[dict(increase=None,decrease=None)]
    r=champions_attainable_stats(identity='Charizard',form='base',stat='attack',alignments=neutral,
        stat_constraints={'hp':185,'attack':136,'speed':152})
    assert r['attainable']['values'] and r['joint_feasible']['values']==[]
    assert r['configurations']['branches']==[]
    r=champions_attainable_stats(identity='Charizard',form='base',stat='attack',alignments=neutral,
        stat_constraints={'hp':185,'speed':152})
    assert r['joint_feasible']['values']==[104,105,106]


def test_shared_alignment_cannot_boost_two_stats():
    r=champions_attainable_stats(identity='Charizard',form='base',stat='attack',stat_constraints={'attack':149,'special_attack':177})
    assert r['status']=='empty'
    r=champions_attainable_stats(identity='Charizard',form='base',stat='attack',adjustments={'attack':'1.1','speed':'1.1'})
    assert r['status']=='empty'


def test_known_training_factors_gaps_and_witnesses():
    args=dict(identity='喷火龙',form='base',stat='attack',known_training_points={'hp':32,'speed':32},adjustments={'attack':'1.1'})
    r=champions_attainable_stats(**args)
    assert r['joint_feasible']['values']==[114,115,116]
    for w in r['witnesses']:
        assert sum(w['training_points'].values())<=66
        assert ChampionsStats('Charizard',form='base').calculate(w['training_points'],w['alignment'])['stats']==w['stats']
    g=champions_attainable_stats(identity='Charizard',form='base',stat='attack')
    assert g['attainable']['has_gaps'] and 142 not in g['attainable']['values']
    assert g==champions_attainable_stats(identity='Charizard',form='base',stat='attack')


@pytest.mark.parametrize('constraints',[{'hp':{'minimum':153,'maximum':155}}, {'attack':{'allowed_values':[104,115,116]}}, {'speed':{'minimum':120,'maximum':140},'special_attack':116}])
def test_compact_representation_matches_exhaustive_legacy_utility(constraints):
    domains=dict.fromkeys(STATS,[0]);domains.update(attack=[0,1,2],speed=[0,1,2],special_attack=[0,1,2])
    model=ChampionsStats('Charizard',form='base')
    expected=set();expected_configs=set()
    for alignment in alignment_patterns():
        for values in product(*(domains[s] for s in STATS)):
            points=dict(zip(STATS,values));built=model.calculate(points,alignment)
            if all(allowed(built['stats'][s],c) for s,c in constraints.items()):
                expected.add(built['stats']['attack'])
                expected_configs.add((json.dumps(alignment,sort_keys=True),values))
    r=champions_attainable_stats(identity='Charizard',form='base',stat='attack',point_domains=domains,stat_constraints=constraints)
    actual_configs=set()
    for branch in r['configurations']['branches']:
        for rows in product(*(branch['stat_point_domains'][s] for s in STATS)):
            points=tuple(x['training_points'] for x in rows)
            if sum(points)<=r['configurations']['total_training_points_max']:
                actual_configs.add((json.dumps(branch['alignment'],sort_keys=True),points))
    assert r['joint_feasible']['values']==sorted(expected) and actual_configs==expected_configs


def test_damage_intersection_backward_compatibility_and_evidence():
    req=request();original=deepcopy(req)
    numerical=solve({k:v for k,v in req.items() if k!='champions'})
    r=infer_champions_attack_stat(**req)
    assert req==original and r['damage_result']==numerical
    assert r['damage_feasible']['values']==list(range(89,110))
    assert r['final_feasible']['values']==list(range(93,110))
    assert r['excluded_by_stat_legality']==[89,90,91,92]
    assert set(r['final_feasible']['values'])<=set(r['damage_feasible']['values'])
    assert r['compatible_configurations']['branches'] and r['witnesses']
    assert all(w['value'] in r['final_feasible']['values'] for w in r['witnesses'])


def test_joint_observed_actual_hp_and_speed_are_respected():
    req=request({'minimum':0,'maximum':65535})
    req['champions']['alignments']=[dict(increase=None,decrease=None)]
    attacker=req['observations'][0]['input']['attacker'];attacker['maximum_hp']=185;attacker['stats']['speed']=152
    r=infer_champions_attack_stat(**req)
    assert r['final_feasible']['values']==[104,105,106]
    assert r['excluded_by_joint_constraints']
    attacker['stats']['special_attack']=161
    r=infer_champions_attack_stat(**req)
    assert r['status']=='empty' and r['stat_intersection']['values'] and not r['final_feasible']['values']


def test_empty_stat_intersection_and_conflicting_known_stats():
    req=request({'minimum':0,'maximum':65535});req['candidate_stats']=[142]
    r=infer_champions_attack_stat(**req)
    assert r['status']=='empty' and r['excluded_by_stat_legality']==[142]
    req=request();req['champions']['stat_constraints']={'speed':200};req['observations'][0]['input']['attacker']['stats']['speed']=100
    assert infer_champions_attack_stat(**req)['status']=='empty'


def test_shared_damage_scenarios_are_preserved():
    req=request();req['observations'][0]['input']['attacker']['item']=None
    req['variables']=[dict(id='item',scope='shared',observation_ids=['hit1'],path='attacker.item',values=['none','Life Orb'])]
    r=infer_champions_attack_stat(**req)
    assert r['status']=='conditional' and len(r['per_scenario'])==2
    for row in r['per_scenario']:
        assert set(row['final_feasible']['values'])==set(row['damage_feasible']['values']) & set(r['final_feasible']['values'])


@pytest.mark.parametrize('kwargs',[{'identity':'Charizard'}, {'identity':'missing','form':'base'}, {'identity':'Charizard','form':'Charizard-Mega-X','known_training_points':{'attack':33}}, {'identity':'Charizard','form':'base','adjustments':{'attack':None}}, {'identity':'Charizard','form':'base','stat_constraints':{'speed':None}}])
def test_diagnostic_for_ambiguous_missing_and_unknown_data(kwargs):
    r=champions_attainable_stats(stat='attack',**kwargs)
    assert r['status']=='insufficient_information' and r['joint_feasible'] is None


def test_identity_form_mismatch_and_unknown_forward_mechanics():
    req=request();req['champions']['identity']='Sneasler'
    assert infer_champions_attack_stat(**req)['status']=='insufficient_information'
    req=request();req['observations'][0]['input']['move']='Beat Up'  # Multi-hit remains unsupported; Foul Play now has a selector.
    assert infer_champions_attack_stat(**req)['status']=='unsupported'


def test_numerical_stat_scenarios_not_silently_decoupled():
    req=request();req['variables']=[dict(id='speed',scope='shared',observation_ids=['hit1'],path='attacker.stats.speed',values=[100,110])]
    assert infer_champions_attack_stat(**req)['status']=='insufficient_information'


def test_cli_smoke_and_error():
    p=subprocess.run([sys.executable,'-m','damage.champions_cli'],input=json.dumps(request()),capture_output=True,text=True)
    assert p.returncode==0 and json.loads(p.stdout)['final_feasible']['values']==list(range(93,110))
    p=subprocess.run([sys.executable,'-m','damage.champions_cli'],input='{}',capture_output=True,text=True)
    assert p.returncode==2 and json.loads(p.stdout)['status']=='insufficient_information'


def test_compact_joint_budget_matches_exhaustive_near_limit():
    model=ChampionsStats('Charizard',form='base');neutral=dict(increase=None,decrease=None)
    domains=dict.fromkeys(STATS,[0]);domains.update(hp=[30,31,32],attack=[30,31,32],speed=[3,4,5,6])
    result=champions_attainable_stats(identity='Charizard',form='base',stat='attack',point_domains=domains,alignments=[neutral])
    expected=set();actual=set()
    for values in product(*(domains[s] for s in STATS)):
        if sum(values)<=66:expected.add(values)
    for branch in result['configurations']['branches']:
        for rows in product(*(branch['stat_point_domains'][s] for s in STATS)):
            values=tuple(r['training_points'] for r in rows)
            if sum(values)<=66:actual.add(values)
    assert actual==expected and len(actual)<36
    assert all(sum(w['training_points'].values())<=66 for w in result['witnesses'])


def test_range_domains_are_json_safe_and_no_witness_preference():
    result=champions_attainable_stats(identity='Charizard',form='base',stat='attack',point_domains={'hp':range(3)},retain_witnesses=False)
    json.dumps(result,allow_nan=False)
    assert result['witnesses']==[] and len(result['configurations']['branches'])==21


def test_saved_composition_examples():
    folder=Path('examples/champions_feasibility')
    expected=json.loads((folder/'expected-results.json').read_text())
    for name,fields in expected.items():
        result=infer_champions_attack_stat(**json.loads((folder/(name+'.json')).read_text()))
        assert {k:result[k] for k in fields}==fields


def test_chinese_and_canonical_mega_identity_reuse():
    chinese=champions_attainable_stats(identity='喷火龙',form='base',stat='attack')
    canonical=champions_attainable_stats(identity='pokeapi:species:6',form='base',stat='attack')
    assert chinese['attainable']==canonical['attainable']
    mega=ChampionsStats('Charizard-Mega-X')
    r=champions_attainable_stats(identity=mega.identity,stat='attack')
    assert r['identity']==mega.identity and r['attainable']['hull']==[135,200]
