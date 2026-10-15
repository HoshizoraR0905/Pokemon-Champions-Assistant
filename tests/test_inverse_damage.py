from copy import deepcopy
import json
from pathlib import Path

import pytest
from damage import calculate
from damage.inverse import infer_attack_stat

PROFILE = 'showdown-champions-reference-v1'
BASE = json.loads(Path('examples/damage/neutral.json').read_text())


def observation(oid='hit1', request=None, damage=35):
    return dict(id=oid,battle_id='example',attacker_instance_id='opponent:1',target_instance_id='self:1',
                stat_epoch='original',damage=damage,damage_kind='direct_move_damage',
                evidence='Explicit synthetic direct hit; no residual effects or HP censoring.',input=deepcopy(request or BASE))


def infer(obs, candidates=range(80,151), **kwargs):
    return infer_attack_stat(observations=obs,candidate_stats=candidates,ruleset=PROFILE,**kwargs)


def test_single_and_multiple_exact_forward_support():
    a=observation(); b=observation('hit2');b['input']['attacker']['stages']['attack']=2;b['damage']=70
    r=infer([a,b]); assert r['status']=='exact'
    expected=[]
    for v in range(80,151):
        if all(any(d==o['damage'] for d in calculate(dict(o['input'],attacker=dict(o['input']['attacker'],stats=dict(o['input']['attacker']['stats'],attack=v))))['distribution']['rolls']) for o in [a,b]): expected.append(v)
    assert r['feasible']['values']==expected
    assert r['feasible']['values']==sorted(set(r['scenarios'][0]['per_observation'][0]['feasible']['values']) & set(r['scenarios'][0]['per_observation'][1]['feasible']['values']))


def test_intervals_sets_and_immutable_inputs():
    o=observation(damage={'allowed_values':[34,36]}); original=deepcopy(o)
    r=infer([o]); assert o==original
    assert r['status']=='exact'
    assert all(set(row['compatible_rolls']) <= {34,36} for row in r['scenarios'][0]['per_observation'][0]['compatibility'])
    broad=infer([observation(damage={'minimum':34,'maximum':36})])
    assert set(r['feasible']['values']) <= set(broad['feasible']['values'])


def test_empty_and_minimal_conflict():
    a=observation(damage=33); b=observation('hit2',damage=59)
    r=infer([a,b],range(80,201))
    assert r['status']=='empty' and all(x['individually_feasible'] for x in r['per_observation'])
    assert r['inconsistency']['conflicting_observation_ids']==['hit1','hit2']
    r=infer([observation(damage=60000)])
    assert r['status']=='empty' and r['feasible']['hull'] is None


@pytest.mark.parametrize('move,stat,informative',[('Body Press','attack',False),('Psyshock','special_attack',True),('Seismic Toss','attack',False),('Flamethrower','attack',False)])
def test_forward_dependencies(move,stat,informative):
    o=observation();o['input']['move']=move
    o['damage']=calculate(o['input'])['distribution']['rolls'][0]
    r=infer([o],stat=stat)
    assert r['per_observation'][0]['informative_dependency']==informative
    if not informative: assert r['unconstrained']
    dep=r['scenarios'][0]['per_observation'][0]['dependencies'][0]
    if move=='Body Press': assert dep['attacker']==['defense']
    if move=='Psyshock': assert dep['defender']==['defense']


def test_immunity_noninformative():
    o=observation(damage=0);o['input']['defender']['identity']='Gengar'
    r=infer([o]);assert r['unconstrained'] and not r['per_observation'][0]['informative_dependency']


def test_shared_item_cannot_change_between_hits():
    a=observation(damage=35);b=observation('hit2',damage=47)
    for o in [a,b]:o['input']['attacker']['item']=None
    variable=dict(id='held_item',scope='shared',observation_ids=['hit1','hit2'],path='attacker.item',values=['none','Life Orb'])
    r=infer([a,b],[100],variables=[variable])
    assert r['status']=='empty' and all(o['individually_feasible'] for o in r['per_observation'])
    assert len(r['scenarios'])==2
    variable['scope']='observation'
    r=infer([a,b],[100],variables=[variable])
    assert r['status']=='conditional' and r['feasible']['values']==[100] and len(r['scenarios'])==4
    feasible=[s for s in r['scenarios'] if s['feasible']['count']]
    assert feasible[0]['assignment']=={'held_item:hit1':'none','held_item:hit2':'Life Orb'}


def test_identity_epoch_and_explicit_continuity():
    a=observation();b=observation('hit2');b['attacker_instance_id']='other';b['stat_epoch']='changed'
    assert infer([a,b])['status']=='insufficient_information'
    continuity=dict(subject_id='evidenced-same-stat',observation_ids=['hit1','hit2'],evidence='External continuity and invariant stat established.',unchanged_stat=True)
    assert infer([a,b],continuity=continuity)['status']=='exact'
    continuity['unchanged_stat']=False
    assert infer([a,b],continuity=continuity)['status']=='insufficient_information'


@pytest.mark.parametrize('domain',[[],[True],[0],[65536],[1.5],None,range(10000000)])
def test_invalid_domain(domain):
    assert infer([observation()],domain)['status']=='insufficient_information'


@pytest.mark.parametrize('field,value',[('damage_kind','hp_delta'),('evidence',''),('stat_epoch',None),('damage',{'minimum':40,'maximum':30}),('damage',True)])
def test_invalid_observation(field,value):
    o=observation();o[field]=value
    assert infer([o])['status']=='insufficient_information'


@pytest.mark.parametrize('path',['attacker.item','field.weather','field.reflect','field.critical','attacker.stages.attack'])
def test_unknown_relevant_inputs_are_not_neutral(path):
    o=observation(); parts=path.split('.'); x=o['input']
    for p in parts[:-1]:x=x[p]
    x[parts[-1]]=None
    r=infer([o]);assert r['status']=='insufficient_information' and r['feasible'] is None


def test_unsupported_and_evidence_only_profile():
    o=observation();o['input']['move']='Foul Play'
    assert infer([o])['status']=='unsupported'
    o=observation();o['input']['profile']='champions-evidence-only-v1'
    assert infer_attack_stat(observations=[o],candidate_stats=[100])['status']=='unsupported'


def test_memo_and_limits_and_conditional_failure():
    a=observation();b=observation('hit2')
    r=infer([a,b],[100,101]);assert r['work']['memo_hits']==2 and r['work']['forward_evaluations']==2
    assert infer([a,b],limits={'max_evaluations':2})['status']=='insufficient_information'
    v=dict(id='weather',scope='shared',observation_ids=['hit1'],path='field.weather',values=['none','unsupported'])
    r=infer([a],[100],variables=[v]);assert r['status']=='unsupported' and r['feasible'] is None
    v['path']='attacker.stats.attack'
    assert infer([a],[100],variables=[v])['status']=='insufficient_information'


def test_optional_champions_stat_domain_preserves_gaps():
    from knowledge.champions_stats import ChampionsStats
    domain=ChampionsStats('Charizard',form='base').attainable('attack',adjustments=['0.9','1.0','1.1'])
    r=infer([observation(damage={'minimum':0,'maximum':65535})],domain['values'],domain_provenance=domain['provenance'])
    assert r['feasible']['values']==domain['values'] and r['feasible']['has_gaps'] and 142 not in r['feasible']['values']
    assert r['provenance']['domain']==domain['provenance']

ORACLE = json.loads(Path('tests/fixtures/inverse_damage/oracle-enumeration.json').read_text())


@pytest.mark.parametrize('group',ORACLE['groups'],ids=lambda g:g['id'])
def test_independent_exhaustive_domains(group):
    o=observation(request=group['input'],damage=group['damage'])
    r=infer([o],group['candidate_stats'],stat=group['stat'])
    assert r['status']=='exact' and r['feasible']['values']==group['expected_feasible']
    assert group['known_stat'] in r['feasible']['values']
    independent={row['candidate']:row['rolls'] for row in group['oracle_rolls']}
    for row in r['scenarios'][0]['per_observation'][0]['compatibility']:
        assert row['supported_rolls']==independent[row['candidate']]


REFERENCE_ROWS = [r for group in ['reference','combo','extra'] for r in
    json.loads(Path('tests/fixtures/damage/'+group+'-rolls.json').read_text())['cases']
    if r['id'] not in {'ability-attacker-Galvanize','ability-defender-Storm Drain'}]


@pytest.mark.parametrize('row',REFERENCE_ROWS,ids=lambda r:r['id'])
def test_known_stat_retained_for_independent_reference_rolls(row):
    # Every supported historical oracle case, three separate observed rolls.
    from damage.engine import stat_dependencies
    dependency=stat_dependencies(calculate(row['input']))
    stat='special_attack' if 'special_attack' in dependency['attacker'] else 'attack'
    original=row['input']['attacker']['stats'][stat]
    for damage in {row['rolls'][0],row['rolls'][len(row['rolls'])//2],row['rolls'][-1]}:
        result=infer([observation(request=row['input'],damage=damage)],
                     [max(1,original-1),original,min(65535,original+1)],stat=stat)
        assert original in result['feasible']['values'],(row['id'],result)


def test_mixed_moves_do_not_share_attack_and_special_attack_variable():
    physical=observation();special=observation('special');special['input']['move']='Flamethrower'
    special['damage']=calculate(special['input'])['distribution']['rolls'][0]
    r=infer([physical,special])
    assert not r['per_observation'][1]['informative_dependency']
    assert r['feasible']==infer([physical])['feasible']


def test_different_defender_move_stage_combination():
    a=observation();b=observation('other')
    b['input']['move']='Earthquake';b['input']['defender']['identity']='Blastoise';b['input']['defender']['stats']['defense']=145
    b['input']['attacker']['stages']['attack']=1;b['input']['defender']['stages']['defense']=2
    b['damage']=calculate(b['input'])['distribution']['rolls'][-1]
    r=infer([a,b]); assert 100 in r['feasible']['values']
    assert r['feasible']['count']<=infer([a])['feasible']['count']


def test_conflict_minimization_bound():
    r=infer([observation(damage=0),observation('irrelevant',damage=35)],limits={'max_conflict_checks':1})
    assert r['status']=='empty' and 'work limit' in r['inconsistency']['subset_kind']


def test_conflicting_inputs_keep_provenance():
    o=observation();o['input']['attacker']['item']={'state':'conflicting','values':['none','Life Orb']}
    r=infer([o]);assert r['status']=='insufficient_information'
    assert r['diagnostics'][0]['forward_status']=='conflicting_input'


def test_local_and_shared_context_variables_are_distinct():
    a=observation(damage={'minimum':0,'maximum':65535});b=observation('b',damage={'minimum':0,'maximum':65535})
    variables=[dict(id='weather',scope='shared',observation_ids=['hit1','b'],path='field.weather',values=['none','rain']),
               dict(id='screen',scope='observation',observation_ids=['hit1','b'],path='field.reflect',values=[False,True])]
    r=infer([a,b],[100],variables=variables)
    assert r['status']=='conditional' and len(r['scenarios'])==8
    assert r==infer([a,b],[100],variables=variables)
    assert infer([a,b],[100],variables=variables,limits={'max_assignments':4})['status']=='insufficient_information'
    assert infer([a,b],[100],variables=variables+[variables[0]])['status']=='insufficient_information'


def test_cli_valid_empty_and_invalid_requests(tmp_path):
    import subprocess,sys
    request=dict(observations=[observation()],candidate_stats={'minimum':80,'maximum':150},ruleset=PROFILE)
    p=subprocess.run([sys.executable,'-m','damage.inverse_cli'],input=json.dumps(request),capture_output=True,text=True)
    assert p.returncode==0 and json.loads(p.stdout)['status']=='exact'
    request['observations'][0]['damage']=60000
    path=tmp_path/'request.json';path.write_text(json.dumps(request))
    p=subprocess.run([sys.executable,'-m','damage.inverse_cli',str(path)],capture_output=True,text=True)
    assert p.returncode==0 and json.loads(p.stdout)['status']=='empty'
    p=subprocess.run([sys.executable,'-m','damage.inverse_cli'],input='{"candidate_stats": [NaN]}',capture_output=True,text=True)
    assert p.returncode==2 and json.loads(p.stdout)['status']=='insufficient_information'


def test_fixture_hashes_and_no_recognition_imports():
    import hashlib,subprocess,sys
    manifest=json.loads(Path('tests/fixtures/inverse_damage/manifest.json').read_text())
    for path,digest in manifest['files'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest
    code="from damage import infer_attack_stat; import sys; assert not any(n.split('.')[0] in {'cv2','pytesseract','recognition','capture'} for n in sys.modules)"
    assert subprocess.run([sys.executable,'-c',code],capture_output=True).returncode==0


def test_damage_rounding_creates_gaps_in_contiguous_domain():
    group=next(g for g in ORACLE['groups'] if g['id']=='stage-2')
    expected=[r['candidate'] for r in group['oracle_rolls'] if 106 in r['rolls']]
    assert expected==[80,82]
    result=infer([observation(request=group['input'],damage=106)],group['candidate_stats'])
    assert result['feasible']['values']==expected and result['feasible']['has_gaps']
    assert result['feasible']['hull']==[80,82] and result['feasible']['intervals']==[[80,80],[82,82]]


def test_joint_shared_scenarios_against_independent_oracle():
    tables=[{r['candidate']:r['rolls'] for r in next(g for g in ORACLE['groups'] if g['id']==name)['oracle_rolls']}
            for name in ['neutral-physical','scenario-LifeOrb-BodySlam']]
    domain=sorted(set.intersection(*(set(t) for t in tables)))
    shared_expected=[c for c in domain if any(35 in t[c] and 47 in t[c] for t in tables)]
    local_expected=[c for c in domain if all(any(d in t[c] for t in tables) for d in [35,47])]
    observations=[observation(),observation('hit2',damage=47)]
    for o in observations:o['input']['attacker']['item']=None
    variable=dict(id='item',scope='shared',observation_ids=['hit1','hit2'],path='attacker.item',values=['none','Life Orb'])
    assert infer(observations,domain,variables=[variable])['feasible']['values']==shared_expected
    variable['scope']='observation'
    assert infer(observations,domain,variables=[variable])['feasible']['values']==local_expected
    assert shared_expected==[] and 100 in local_expected


def test_same_species_in_different_battles_is_not_same_instance():
    a=observation();b=observation('hit2');b['battle_id']='another-battle'
    assert infer([a,b])['status']=='insufficient_information'


def test_examples_match_saved_exact_sets():
    from damage.inverse_cli import solve
    folder=Path('examples/inverse_damage')
    expected=json.loads((folder/'expected-results.json').read_text())
    for name,row in expected.items():
        result=solve(json.loads((folder/(name+'.json')).read_text()))
        assert {'status':result['status'],'feasible':result['feasible']}==row
