"""Synthetic mechanism/oracle checks; recorded evidence stays in its own fixture."""
from copy import deepcopy
from itertools import product
import json
from pathlib import Path

import pytest

from damage import calculate
from damage.abilities import contextual_neutrality
from damage.joint import allocation_count, concrete_ids, filter_joint, project_joint
from knowledge.champions_stats import STATS, ChampionsStats

FIXTURE=json.loads(Path('tests/fixtures/damage/m343a-contextual-abilities.json').read_text())


@pytest.mark.parametrize('row',FIXTURE['cases'],ids=lambda r:r['id'])
def test_contextual_abilities_match_pinned_champions_oracle(row):
    r=calculate(row['input'])
    assert r['status']=='exact_reference',r
    assert r['distribution']['rolls']==row['rolls']
    assert any('ability_audit' in step for step in r['trace'])


def test_neutrality_is_contextual_and_unknown_abilities_stay_unknown():
    assert contextual_neutrality('Magic Bounce',{'category':'Special','flags':{}})
    assert contextual_neutrality('Magic Bounce',{'category':'Status'}) is None
    assert contextual_neutrality('Magic Bounce',{'category':'Special','flags':{'reflectable':1}}) is None
    assert contextual_neutrality('Healer',{'category':'Special'},phase='end_of_turn') is None
    assert contextual_neutrality('Drought',{'category':'Special'}) is None
    assert contextual_neutrality('Drought',{'category':'Special'},field={'weather':'rain'})
    assert contextual_neutrality('Blaze',{'category':'Special'}) is None
    assert contextual_neutrality('Huge Power',{'category':'Physical'}) is None
    assert contextual_neutrality('Air Lock',{'category':'Special'}) is None
    r=deepcopy(FIXTURE['cases'][0]['input']);r['attacker']['ability']='Air Lock'
    assert calculate(r)['status']=='unsupported'


def config(item='none',key='same-opponent',points=None):
    domains={s:[0] for s in STATS};domains['special_attack']=list(range(33)) if points is None else points
    domains['speed']=[32];domains['hp']=[0,16,32]
    return dict(id=key,form='pokeapi:species:858',ability='Magic Bounce',item=item,speed=81,
                training=dict(alignment=dict(increase=None,decrease=None),point_domains=domains))


def observation(c,*,key='first',point=16,critical=False,roll=0,second=False):
    request=deepcopy(FIXTURE['cases'][0]['input'])
    request['attacker'].update(ability=c['ability'],item=c['item'])
    request['attacker']['stats']['special_attack']=ChampionsStats('Hatterene',form='base').calculate(
        dict.fromkeys(STATS,0)|{'special_attack':point},c['training']['alignment'])['stats']['special_attack']
    request['defender'].update(current_hp=500,maximum_hp=500)
    if second:
        request['defender'].update(identity='Pelipper',form='base',ability='Drizzle')
        request['defender']['stats']['defense']=121
    request['field']['critical']=critical
    result=calculate(request);assert result['status']=='exact_reference',result
    return dict(id=key,timestamp=2 if second else 1,admitted=True,battle_id='synthetic',
        attacker='persistent-hatterene',source_event_id=key,target='target-b' if second else 'target-a',
        target_side='self',damage=result['distribution']['rolls'][roll],input=request,
        field_alternatives=[{'critical':False},{'critical':True}])


def test_psyshock_uses_special_attack_against_defense():
    o=observation(config());r=calculate(o['input'])
    request=deepcopy(o['input']);request['defender']['stats']['special_defense']+=100
    assert calculate(request)['distribution']['rolls']==r['distribution']['rolls']
    request['defender']['stats']['defense']+=100
    assert calculate(request)['distribution']['rolls']!=r['distribution']['rolls']


def test_independent_rolls_and_critical_flags_on_one_persistent_configuration():
    c=config(points=[16]);a=observation(c,roll=0);b=observation(c,key='second',roll=15,critical=True,second=True)
    saved=deepcopy(c)
    r=filter_joint([c],[a,b]);assert concrete_ids(r['configurations'])=={c['id']}
    assert c==saved
    assert [u['critical_hypotheses'] for u in r['updates']]==[[False],[True]]
    roll_sets=[]
    for o in (a,b):
        rolls=calculate(o['input'])['distribution']['rolls']
        roll_sets.append({i for i,d in enumerate(rolls) if d==o['damage']})
    assert not (roll_sets[0]&roll_sets[1])


def test_item_continuity_preserves_a_numerical_contradiction():
    plain=config(points=[16]);orb=config('Life Orb','orb',points=[16])
    a=observation(orb,roll=15);b=observation(plain,key='second',roll=0,second=True)
    for o in (a,b):o['field_alternatives']=[{'critical':False}]
    assert filter_joint([plain,orb],[a])['configurations']
    assert filter_joint([plain,orb],[b])['configurations']
    r=filter_joint([plain,orb],[a,b]);assert not r['configurations']
    assert r['updates'][-1]['after']['configuration_classes']==0


def test_compact_item_domain_equals_concrete_solver_and_never_reintroduces_ids():
    items=['none','Life Orb','Twisted Spoon','King’s Rock']
    group=config(key='speed-parent');group.update(item_options=items,speed_parent_id='speed-parent')
    concrete=[config(i,'speed-parent@'+i) for i in items]
    a=observation(concrete[0]);b=observation(concrete[0],key='second',second=True)
    source=deepcopy(group);prefix=[]
    compact=filter_joint([group],[a,b],on_update=prefix.append)
    exact=filter_joint(concrete,[a,b])
    assert concrete_ids(compact['configurations'])==concrete_ids(exact['configurations'])
    assert concrete_ids(prefix[1]['configurations'])<=concrete_ids(prefix[0]['configurations'])
    assert group==source
    for stat in ('attack','special_attack','speed'):
        x=project_joint(compact['configurations'],stat);y=project_joint(exact['configurations'],stat)
        for key in ('values','joint_allocations','configuration_classes','items','abilities'):
            assert x[key]==y[key]
    def domains(rows):
        return {i:row['training'] for row in rows for i in concrete_ids([row])}
    assert domains(compact['configurations'])==domains(exact['configurations'])
    # Independent bounded enumeration of the actual stat and each hit's rolls;
    # no marginal-interval intersection or common-roll assumption.
    for item in items[:-1]:
        feasible=[]
        for point in range(33):
            matches=[]
            for o in (a,b):
                branches=[]
                for critical in (False,True):
                    request=deepcopy(o['input']);request['attacker'].update(item=item)
                    request['attacker']['stats']['special_attack']=156+point
                    request['field']['critical']=critical
                    branches.append(o['damage'] in calculate(request)['distribution']['rolls'])
                matches.append(any(branches))
            if all(matches):feasible.append(point)
        actual=domains(compact['configurations']).get('speed-parent@'+item)
        assert (actual['point_domains']['special_attack'] if actual else [])==feasible
    assert compact['requirements']['necessary_item'] is None
    assert 'King’s Rock' in compact['requirements']['supported_items']


def test_budget_dp_and_cached_counts_follow_mutated_domains():
    c=config();t=c['training'];domains=t['point_domains']
    expected=sum(sum(v)<=66 for v in product(*(domains[s] for s in STATS)))
    assert allocation_count(t)==expected
    domains['special_attack']=[32]
    assert allocation_count(t)==sum(sum(v)<=66 for v in product(*(domains[s] for s in STATS)))


def test_sealed_prefix_resume_does_not_replay_the_first_hit():
    c=config();a=observation(c);b=observation(c,key='second',second=True)
    prior=filter_joint([c],[a]);seen=[]
    resumed=filter_joint([c],[a,b],prior=prior,on_update=lambda r:seen.append(r['updates'][-1]['id']))
    whole=filter_joint([c],[a,b])
    assert seen==['second']
    assert resumed['configurations']==whole['configurations']
    def semantic(updates):return [{k:v for k,v in u.items() if k not in {'incremental_seconds','forward_evaluations','incremental_cpu_seconds','projection_seconds','filter_loop_seconds'}} for u in updates]
    assert semantic(resumed['updates'])==semantic(whole['updates'])
    changed=deepcopy(a);changed['id']='wrong-prefix'
    with pytest.raises(ValueError,match='prefix'):filter_joint([c],[changed,b],prior=prior)
    changed=deepcopy(a);changed['input']['defender']['stats']['defense']+=1
    with pytest.raises(ValueError,match='inputs changed'):filter_joint([c],[changed,b],prior=prior)


def test_shared_point_values_are_immutable_between_prefix_snapshots():
    c=config();a=observation(c);b=observation(c,key='second',second=True);prefix=[]
    filter_joint([c],[a,b],on_update=prefix.append)
    values=prefix[0]['configurations'][0]['training']['point_domains']['special_attack']
    with pytest.raises(TypeError,match='immutable'):values.append(99)


def test_replay_storage_interns_training_and_issue_ids_without_losing_members():
    from battle_evidence.offensive import compact_offensive_storage
    c=config('Metronome');a=observation(config());r=filter_joint([c],[a])
    package=dict(offensive_inference=dict(updates=[dict(full=deepcopy(r),observed=deepcopy(r))]))
    compact_offensive_storage(package)
    inference=package['offensive_inference'];encoded=inference['updates'][0]['full']
    restored=[dict({k:v for k,v in row.items() if k!='training_ref'},training=inference['configuration_training_domains'][row['training_ref']]) for row in encoded['configurations']]
    assert restored==r['configurations']
    issue=encoded['unresolved'][0]
    assert inference['configuration_id_sets'][issue['configuration_ids_ref']]==r['unresolved'][0]['configuration_ids']
    assert len(inference['configuration_training_domains'])==1


def test_cache_does_not_cross_different_defenses_moves_or_field_contexts():
    c=config(points=[16]);a=observation(c)
    for mutate in (lambda r:r['defender']['stats'].update(defense=300),
                   lambda r:r.update(move='Psychic'),
                   lambda r:r['field'].update(terrain='none')):
        b=deepcopy(a);b.update(id='changed',timestamp=2);b['field_alternatives']=[{'critical':False}]
        mutate(b['input'])
        assert not filter_joint([c],[a,b])['configurations']


@pytest.mark.local_artifacts
def test_recorded_battle12_full_package_is_cumulative_and_causal():
    from battle_evidence.speed_replay_offline import file_hash
    pointer=Path('.cache/battles/sample_battle_12/m342-offensive/latest.json')
    if not pointer.exists():pytest.skip('Optional full Battle 12 package absent')
    source=Path(json.loads(pointer.read_text())['path'])
    seal=json.loads(source.with_name('manifest.json').read_text())
    assert seal['status']=='complete' and seal['outputs']['replay.json']==file_hash(source)
    d=json.loads(source.read_text());updates=d['offensive_inference']['updates']
    assert [u['observation']['damage'] for u in updates[:2]]==[126,100]
    assert len({u['attacker'] for u in updates})==1
    first,second=(u['full'] for u in updates[:2])
    assert concrete_ids(second['configurations'])<=concrete_ids(first['configurations'])
    for result in (first,second):
        last=result['updates'][-1]
        assert last['after']['configuration_classes']==len(concrete_ids(result['configurations']))
        assert last['supported_after']['configuration_classes']+last['unresolved_after']['configuration_classes']==last['after']['configuration_classes']
    assert second['updates'][-1]['supported_after']['values']['values']==list(range(148,197))+list(range(198,207))
    if d.get('team_item_relations'):
        assert 'Life Orb' not in first['requirements']['items']
        assert first['updates'][0]['team_item_excluded_items']==['Life Orb']
        assert next(i for i in first['item_explanations']['items'] if i['item']=='Life Orb')['states']==['excluded_by_team_uniqueness']
    elif d['offensive_inference'].get('item_profile')=='practical':
        assert 'Life Orb' in first['item_policy']['dormant']
    else:assert 'Life Orb' in first['requirements']['supported_items']
    assert 'Life Orb' not in second['requirements']['items']
    assert second['requirements']['necessary_item'] is None
    if d.get('empirical_measure_model',{}).get('version')=='M3.4.4':
        assert all(u['observed']['configurations'] for u in updates)
        assert all(not h['move_membership_excluded_ids'] for u in updates for h in u['observed']['updates'])
    else:assert all(u['observed']['configurations']==[] for u in updates)
    actor=updates[0]['attacker']
    def support(time):
        snap=next(s for s in reversed(d['snapshots']) if s['timestamp']<=time)
        return d['support_catalog'][snap['opponents'][actor]['support_ref']]
    before=deepcopy(support(365));after_first=deepcopy(support(366));after_second=deepcopy(support(449))
    assert 'offensive' not in before['full']
    if d.get('empirical_measure_model',{}).get('version')=='M3.4.4':assert after_first['observed']['complete_after']==1
    else:assert after_first['observed']['exhaustion_reason']=='revealed_move_membership'
    assert after_second['full']['offensive_stats']['special_attack']['evidence_ids']==[u['id'] for u in updates[:2]]
    assert support(365)==before and support(366)==after_first and support(449)==after_second
