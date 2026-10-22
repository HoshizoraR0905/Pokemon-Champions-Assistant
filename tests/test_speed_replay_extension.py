"""Explicit synthetic inputs, separate from source-reviewed battle evidence."""
from copy import deepcopy
import pytest
from speed_order.mechanics import move_fact, effective_priority
from test_dynamic_action_order import participant, action, state, simulate, change, E
from metagame.published.speed_support import SpeedSupportIndex, search_support, alignment
from battle_evidence.speed_reviewed import joint_phase_support, reviewed_action, infer_pair


@pytest.mark.parametrize('move', ['Snarl','Dragon Pulse','Weather Ball','Light Screen',
    'Reflect','Spirit Break','Flare Blitz','Encore','Psyshock','Parting Shot','Earth Power'])
def test_catalog_priority_for_reviewed_ordinary_moves(move):
    assert move_fact(move)[2]['priority'] == 0


@pytest.mark.parametrize('ability', ['Stamina','Sturdy','Intimidate','Swarm','Adaptability','Rough Skin'])
def test_reviewed_abilities_do_not_block_order(ability):
    result = simulate(state(participant('a',154,ability=ability),participant('b',100)),
                      [action('a','Earth Power'),action('b','Snarl')])
    assert result['status'] == 'exact', result['diagnostics']


def test_flinch_requires_selection_and_has_order_but_no_move_effect():
    s = state(participant('a',154),participant('b',154))
    a = action('a','Earth Power'); a['outcome']='flinched'
    assert simulate(s,[a,action('b','Tailwind')])['status']=='unresolved'
    a.update(selection_evidence=deepcopy(E),timing_evidence=deepcopy(E))
    assert len(simulate(s,[a,action('b','Tailwind')])['traces'])==2
    a['move']=None
    assert simulate(s,[a,action('b')])['status']=='unresolved'


@pytest.mark.parametrize('trick_room,first',[(False,'a'),(True,'b')])
def test_switch_phase_speed_and_trick_room(trick_room,first):
    s=state(participant('a',154,item='Quick Claw'),participant('b',108),trick_room=trick_room)
    actions=[dict(action(i),kind='voluntary_switch',move=None) for i in ['a','b']]
    r=simulate(s,actions)
    assert r['status']=='exact'
    assert r['traces'][0]['sequence'][0]==first+':move'


def test_switch_mega_and_move_are_distinct_phases():
    s=state(participant('a',50),participant('b',200),participant('c',100))
    actions=[dict(action('a'),kind='voluntary_switch',move=None),
             dict(action('b'),kind='mega_evolution',move=None),action('c','Fake Out')]
    r=simulate(s,actions)
    assert r['traces'][0]['sequence']==['a:move','b:move','c:move']
    actions[0]['kind']='pivot_replacement'
    assert simulate(s,actions)['status']=='unresolved'


def test_priority_ability_and_unknown_mechanics_remain_explicit():
    p=participant('a',100,ability='Prankster')
    assert effective_priority(action('a','Light Screen'),p,state(p)['field'])['effective']==1
    for m in ['Instruct','Electro Shot','After You']:
        with pytest.raises(ValueError): move_fact(m)


def test_empirical_joint_support_missingness_and_expansion():
    rows=[dict(species='fish',item='Scarf',ability='Swim',speed_alignment=1.1,speed_sp=32),
          dict(species='fish',item='Ball',ability='Adapt',speed_alignment=1.,speed_sp=0),
          dict(species='fish',item=None,ability='Adapt',speed_alignment=1.1,speed_sp=None)]
    index=SpeedSupportIndex(rows,dict(population='synthetic'))
    q=index.statistic('fish',dict(speed_sp=32),given=dict(speed_alignment=1.1))
    assert (q['numerator'],q['denominator'],q['missing_target'])==(1,1,1)
    assert index.statistic('fish',dict(item='Scarf'),given=dict(ability='Absent'))['frequency'] is None
    assert index.statistic('fish',dict(item='Scarf',speed_sp=0))['numerator']==0
    evaluate=lambda configs: dict(status='exact' if configs else 'empty',feasible=configs)
    r=search_support([],['legal'],evaluate)
    assert r['expanded'] and r['full_legal']['feasible']==['legal']
    r=search_support(['observed'],['legal'],evaluate)
    assert not r['expanded'] and r['full_legal'] is None
    assert search_support(['observed'],['legal'],evaluate,expand=True)['expanded']
    assert not search_support(['x'],['legal'],lambda _:dict(status='unresolved'))['expanded']


def test_nature_alignment_uses_champions_numerical_pattern():
    assert alignment('nature:timid')==dict(increase='speed',decrease='attack')
    assert alignment('nature:modest')==dict(increase='special_attack',decrease='attack')
    assert alignment('nature:hardy')==dict(increase=None,decrease=None)


def test_joint_switch_support_keeps_item_correlations_and_ties():
    s=state(participant('a',100),participant('b',100))
    def configs(speeds,items):
        return [dict(id=f'{v}:{i}',speed=v,ability='Blaze',item=i,form='pokeapi:species:6',training=None)
                for v in speeds for i in items]
    left=configs([88,108],['none']);right=configs([108],['none','Iron Ball'])
    actions=[dict(action(i),kind='voluntary_switch',move=None) for i in ['a','b']]
    l,r,receipt=joint_phase_support(left,right,s,actions)
    assert {c['speed'] for c in l}=={88,108}
    normal=next(b for b in receipt['item_branch_pairs'] if b['second_item_class']=='none')
    assert normal['first_speed']['values']==[108]
    ball=next(b for b in receipt['item_branch_pairs'] if b['second_item_class']=='Iron Ball')
    assert ball['first_speed']['values']==[88,108]
    s['field']['trick_room']=True
    l,r,_=joint_phase_support(left,right,s,actions)
    assert all(c['item']=='none' for c in r)


def test_prevented_action_does_not_invent_selection_provenance():
    e=dict(id='flinch',kind='prevented_action',individual='a',move='Earth Power',
           outcome='flinched',timestamp=10,sources=[dict(source_id='synthetic:10')])
    with pytest.raises(ValueError): reviewed_action(e)
    selection=dict(e,timestamp=9,kind='selected_action',move='Protect')
    with pytest.raises(ValueError): reviewed_action(e,selection)
    selection.update(move='Earth Power',timestamp=11)
    with pytest.raises(ValueError): reviewed_action(e,selection)


@pytest.mark.parametrize('outcome',['paralysed','sleep','frozen','failed','cancelled'])
def test_other_preventions_need_individual_timing_audit(outcome):
    a=action('a');a['outcome']=outcome
    assert simulate(state(participant('a',100),participant('b',90)),[a,action('b')])['status']=='unresolved'


def test_mega_phase_and_later_move_share_one_individual():
    p=participant('a',100);q=participant('b',200)
    mega=dict(action('a'),id='a:mega',kind='mega_evolution',move=None)
    result=simulate(state(p,q),[mega,action('a'),action('b')])
    assert result['traces'][0]['sequence']==['a:mega','b:move','a:move']
    switch=dict(mega,id='a:switch',kind='voluntary_switch')
    assert simulate(state(p,q),[switch,action('a'),action('b')])['status']=='unresolved'
