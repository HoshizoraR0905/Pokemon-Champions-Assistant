"""Joint-derived explanations and synthetic Life Orb gates, not video detection."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from damage import calculate
from damage.explanations import explain_items,reconstruct
from damage.joint import filter_joint,concrete_ids,project_joint
from knowledge.champions_stats import STATS,ChampionsStats
from battle_evidence.item_policy import filter_policy_joint,apply_policy,item_state
from battle_evidence.life_orb import evidence_allows,expected_recoil
from test_hatterene_damage import config,observation
from test_item_policy import domain,event


def test_exact_items_keep_integer_gaps_and_evaluated_union_excludes_unknown():
    c=config(points=[0,2]);obs=observation(c,point=0)
    high=observation(c,point=2)
    common=set(calculate(obs['input'])['distribution']['rolls'])&set(calculate(high['input'])['distribution']['rolls'])
    assert common;obs['damage']=min(common)
    rows=[c,dict(config('Metronome',key='unknown',points=[32]))]
    result=filter_joint(rows,[obs]);explain=explain_items(result,[obs],original_configurations=rows)
    evaluated=next(i for i in explain['items'] if i['item']=='none')
    assert evaluated['evaluated']['values']['has_gaps']
    assert explain['evaluated_union']==project_joint([c for c in result['configurations'] if c['item']=='none'],'special_attack')['values']
    assert next(i for i in explain['items'] if i['item']=='Metronome')['states']==['unresolved']
    assert set(explain['evaluated_union']['values'])==set().union(*(set(i['evaluated']['values']['values']) for i in explain['items']))


def test_full_joint_witness_respects_shared_budget_and_replays_pinned_forward():
    c=config(points=list(range(33)));c['training']['point_domains']['hp']=[32]
    obs=observation(c,point=1)
    result=filter_joint([c],[obs]);assert result['configurations']
    explanation=explain_items(result,[obs],original_configurations=[c],requested_values=())
    for row in explanation['witnesses']:
        if row['witness'] is None:continue
        w=row['witness'];assert sum(w['training_points'].values())<=66
        assert w['training_points']['hp']==32 and w['training_points']['speed']==32
        assert w['training_points']['special_attack']<=2
        hit=w['hits'][0];forward=calculate(hit['forward_input'])
        assert forward['distribution']['rolls'][hit['roll']-85]==obs['damage']
        assert w['stats']['speed']==c['speed']


def test_rescue_restores_original_orb_and_preserves_independent_hits():
    rows=domain(['none','Life Orb']);orb=config('Life Orb',points=[32]);first=observation(orb,point=32,critical=True,roll=15)
    second=observation(orb,key='second',point=32,critical=False,roll=3,second=True)
    for o in (first,second):o['input']['attacker'].update(current_hp=None,maximum_hp=None)
    ordinary,_=apply_policy(rows);assert not filter_joint(ordinary,[first])['configurations']
    result=filter_policy_joint(rows,[first,second]);assert result['configurations']
    assert result['item_policy']['rescued']==['Life Orb'] and not result['item_policy']['activated']
    assert result['item_policy']['rescue_history'][0]['confirmation'] is False
    assert concrete_ids(result['configurations'])<={'parent@Life Orb'}
    ex=explain_items(result,[first,second],original_configurations=rows,requested_values=())
    w=next(w['witness'] for w in ex['witnesses'] if w['witness'])
    assert w['initial_item']=='Life Orb' and len(w['hits'])==2
    for obs,hit in zip([first,second],w['hits']):
        assert hit['forward_input']['attacker']['item']=='Life Orb'
        assert calculate(hit['forward_input'])['distribution']['rolls'][hit['roll']-85]==obs['damage']
    assert w['hits'][0]['critical'] is True and w['hits'][1]['critical'] is False
    assert w['hits'][0]['roll']!=w['hits'][1]['roll']


def test_ordinary_survival_never_triggers_rescue_and_dormancy_is_not_elimination():
    rows=domain(['none','Life Orb']);obs=observation(config())
    result=filter_policy_joint(rows,[obs]);assert result['configurations']
    assert result['item_policy']['rescued']==[]
    ex=explain_items(result,[obs],original_configurations=rows)
    orb=next(i for i in ex['items'] if i['item']=='Life Orb')
    assert orb['states']==['policy_dormant'] and orb['numerical_exclusions']==0
    assert all('Life Orb' not in cid for cid in result['updates'][0]['excluded_ids'])


def test_source_time_late_enable_revalidates_prefix_without_grafting():
    rows=domain(['none','Life Orb']);orb=config('Life Orb')
    first=observation(orb,point=32,critical=False,roll=15)
    second=observation(orb,key='second',point=32,critical=True,roll=15,second=True)
    e=event('Life Orb',time=2,available=3)
    early=filter_policy_joint(rows,[first],item_events=[e]);assert 'Life Orb' in early['item_policy']['dormant']
    later=filter_policy_joint(rows,[first,second],item_events=[e],available_at=3)
    assert concrete_ids(later['configurations'])<={'parent@Life Orb'} and later['configurations']
    ex=explain_items(later,[first,dict(second,timestamp=3)],original_configurations=rows,item_events=[e])
    assert 'source_confirmed' in next(i for i in ex['items'] if i['item']=='Life Orb')['states']
    assert 'Life Orb' in filter_policy_joint(rows,[first],item_events=[e])['item_policy']['dormant']
    incompatible=deepcopy(first);incompatible['damage']=1
    assert not filter_policy_joint(rows,[incompatible,second],item_events=[e],available_at=3)['configurations']


def test_unresolved_active_domain_does_not_trigger_false_infeasibility_rescue():
    rows=domain(['none','Life Orb','Metronome']);obs=observation(config());obs['damage']=999
    # Explicitly enabling an unsupported history retains a provisional domain.
    e=event('Metronome')
    result=filter_policy_joint(rows,[obs],item_events=[e]);assert result['unresolved']
    assert result['item_policy']['rescued']==[] and not result['requirements']['exhaustive']


@pytest.mark.parametrize('ability,move,expected',[
    ('Magic Guard',{},0),('Sheer Force',{'secondaries':[{'chance':10}]},0),
    ('Sheer Force',{},None),('Magic Bounce',{},16)])
def test_recoil_exceptions_are_pinned_evidence_gates_not_new_forward_mechanics(ability,move,expected):
    assert expected_recoil(ability=ability,move=move,maximum_hp=160,successful_hit=True,item_active=True,forced_switch=False,after_move_hook_reached=True)==expected


def test_no_item_absence_from_incomplete_or_unspecific_messages():
    args=dict(item='Life Orb',ability='Magic Bounce',move={},attack_event_id='a')
    evidence=dict(observed=False,coverage_complete=True,sources=['synthetic'],attack_event_id='a')
    assert evidence_allows(evidence,**args)
    evidence.update(basis='reviewed_post_attack_hp_window',hp_before=100,hp_after=100,other_hp_changes_excluded=True,conditions=dict(maximum_hp=160,successful_hit=True,item_active=True,forced_switch=False,after_move_hook_reached=True))
    assert not evidence_allows(evidence,**args)
    assert evidence_allows(evidence,**dict(args,ability='Magic Guard'))
    evidence['coverage_complete']=False;assert evidence_allows(evidence,**args)


def test_reviewed_activation_requires_specific_attribution_and_rewinds():
    with pytest.raises(ValueError,match='attack-bound'):item_state([event('Life Orb','activated')],battle_id='synthetic',individual='persistent-hatterene',at=5)
    e=event('Life Orb','activated',time=1,available=3,action_id='attack',activation_basis='reviewed_item_message')
    assert item_state([e],battle_id='synthetic',individual='persistent-hatterene',at=2)['confirmed_item'] is None
    assert item_state([e],battle_id='synthetic',individual='persistent-hatterene',at=3)['confirmed_item']=='Life Orb'
    e.update(activation_basis='attributed_recoil',exclusive_attribution=True,hp_before=100,hp_after=84,recoil_context=dict(ability='Magic Bounce',move={},maximum_hp=160,successful_hit=True,item_active=True,forced_switch=False,after_move_hook_reached=True))
    assert item_state([e],battle_id='synthetic',individual='persistent-hatterene',at=3)['confirmed_item']=='Life Orb'
    e['recoil_context']['ability']='Magic Guard'
    with pytest.raises(ValueError,match='exclusive'):item_state([e],battle_id='synthetic',individual='persistent-hatterene',at=3)
