"""Synthetic policy/mechanics regressions; no claim of UI recognition accuracy."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from battle_evidence.item_policy import (apply_policy,item_state,action_item,split_identity,
    filter_policy_joint,quick_claw_activation,reviewed_order_activation,refine_revealed,validate_item_review)
from damage.items import registry,effect_applicable,candidate_applicable,damage_equivalent
from damage.joint import filter_joint,concrete_ids,legal_damage_items,project_joint
from damage import calculate
from speed_order.mechanics import override_options
from test_hatterene_damage import config,observation


def event(item,kind='held',time=1,available=None,**extra):
    return dict(battle_id='synthetic',individual='persistent-hatterene',item=item,kind=kind,
                timestamp=time,available_at=time if available is None else available,
                reviewer='synthetic',sources=[dict(source_id='synthetic:frame')],**extra)


def domain(items):
    c=config(key='parent');c.update(speed_parent_id='parent',item_options=items,item=items[0]);return [c]


def test_full_registry_coverage_identity_and_source_hashes():
    r=registry();assert set(r['items'])==set(legal_damage_items());assert len(r['items'])==166
    from speed_order.core import knowledge,name
    assert {v['id'] for v in r['items'].values()}==set(knowledge().facts['items'])
    for n,v in r['items'].items():
        assert name(v['id'],'item')==n
        assert v['primary_effect'] and v['forward_coverage'] and v['sources'] and v['uncertainty']
        assert v['category'] in {'standard','evidence_triggered','rare_specialized','species_specific'}
    source=r['sources']['canonical'];assert hashlib.sha256(Path(source['path']).read_bytes()).hexdigest()==source['sha256']
    assert not {'Choice Band','Choice Specs'}&set(r['items'])


@pytest.mark.parametrize('item',['Wise Glasses','Twisted Spoon','Choice Scarf','Sitrus Berry','Occa Berry','Focus Sash','Rocky Helmet'])
def test_important_standard_items_remain(item):
    rows,receipt=apply_policy(domain(['none',item]));assert item in receipt['retained'];assert rows


@pytest.mark.parametrize('item',['Life Orb','Air Balloon','Electric Seed','Grassy Seed','Misty Seed','Psychic Seed','Quick Claw','Metronome','Iron Ball'])
def test_dormancy_is_not_impossibility_and_diagnostic_keeps(item):
    rows,p=apply_policy(domain(['none',item]));assert p['dormant']==[item];assert item not in p['retained']
    diagnostic,q=apply_policy(domain(['none',item]),'comprehensive');assert item in q['retained']
    active,a=apply_policy(domain(['none',item]),confirmed=[item]);assert item in a['retained']


def test_species_effect_and_stone_applicability():
    assert effect_applicable('Light Ball','pokeapi:species:25')
    assert not effect_applicable('Light Ball','pokeapi:species:26')
    assert candidate_applicable('Light Ball','pokeapi:species:858') # holding is legal, boost does not apply
    assert not candidate_applicable('Charizardite Y','pokeapi:species:858')
    assert candidate_applicable('Charizardite Y','pokeapi:species:6')
    from speed_order.core import identity_key
    mega=identity_key('Mega Charizard Y','as_named')
    assert candidate_applicable('Charizardite Y',mega)
    assert not candidate_applicable('Charizardite X',mega)


def test_unknown_and_reviewed_negative_are_distinct_and_do_not_exclude():
    unknown=item_state([],battle_id='synthetic',individual='persistent-hatterene',at=5)
    negative=event('Air Balloon','reviewed_negative',coverage_complete=True)
    s=item_state([negative],battle_id='synthetic',individual='persistent-hatterene',at=5)
    assert unknown['coverage']=='unreviewed' and s['coverage']=='reviewed_negative'
    assert s['confirmed_item'] is None
    assert action_item('Air Balloon',[negative],battle_id='synthetic',individual='persistent-hatterene',at=5,available_at=5)=='Air Balloon'
    with pytest.raises(ValueError):item_state([event('Quick Claw','reviewed_negative')],battle_id='synthetic',individual='persistent-hatterene',at=5)


def test_positive_quick_claw_activation_vs_possession_and_ordering():
    e=event('Quick Claw','activated',action_id='move-a')
    state=item_state([e],battle_id='synthetic',individual='persistent-hatterene',at=5)
    assert quick_claw_activation(state,'move-a')=='activated'
    assert quick_claw_activation(state,'move-b')=='unknown'
    action=dict(kind='move',activation=reviewed_order_activation([e],battle_id='synthetic',individual='persistent-hatterene',action_id='move-a',at=5))
    holder=dict(item='Quick Claw',ability='Magic Bounce',ability_active=True)
    assert override_options(action,holder)==[1]
    assert override_options(action,dict(holder,item='none'))==[]
    action['activation'].update(state='not_activated',coverage_complete=True)
    assert override_options(action,holder)==[0] # nonactivation does not exclude possession


@pytest.mark.parametrize('item',['Electric Seed','Psychic Seed','Air Balloon'])
def test_consumption_preserves_previous_holding_and_causal_reveal(item):
    events=[event(item,'held',time=1),event(item,'consumed',time=3,available=4)]
    at=lambda t:item_state(events,battle_id='synthetic',individual='persistent-hatterene',at=t)
    assert at(2)['current_item']==item and at(3)['current_item']==item
    assert at(4)['current_item']=='none' and at(4)['confirmed_item']==item
    assert len(at(4)['consumed'])==1
    assert action_item(item,events,battle_id='synthetic',individual='persistent-hatterene',at=3,available_at=4)==item
    assert action_item(item,events,battle_id='synthetic',individual='persistent-hatterene',at=3.1,available_at=4)=='none'


def test_iron_ball_rescue_only_when_ordinary_speed_rows_cannot_explain():
    _,p=apply_policy(domain(['none','Iron Ball']));assert 'Iron Ball' in p['dormant']
    rows,r=apply_policy(domain(['Iron Ball']));assert rows and r['iron_ball_rescue']


def test_equivalent_items_split_by_later_evidence_without_new_sp():
    rows=domain(['none','Choice Scarf','King’s Rock','Twisted Spoon'])
    hit=observation(config());result=filter_joint(rows,[hit])
    subset=split_identity(result['configurations'],'Choice Scarf')
    assert concrete_ids(subset)<=concrete_ids(result['configurations'])
    for c in subset:assert c['training'] in [r['training'] for r in result['configurations']]
    assert damage_equivalent('Choice Scarf',config()['form'],'Magic Bounce',{'type':'Psychic','category':'Special'})=='none'


def test_late_reveal_replays_same_original_configuration_domain():
    rows=domain(['none','Metronome']);a=observation(config());b=observation(config(),key='second',second=True)
    e=event('Metronome',time=2)
    values=[];result=filter_policy_joint(rows,[a,b],item_events=[e],on_update=values.append)
    assert 'Metronome' not in values[0]['requirements']['items']
    assert 'Metronome' in result['requirements']['items']
    assert 'Metronome' in result['requirements']['unresolved_items']
    assert concrete_ids(result['configurations'])<=concrete_ids(rows)
    revealed=refine_revealed(result,[e],battle_id='synthetic',individual='persistent-hatterene',at=2)
    assert revealed['requirements']['items']==['Metronome']


def test_consumed_item_changes_current_request_without_switching_hidden_identity():
    rows=domain(['Twisted Spoon'])
    hit=observation(config(),point=16)
    e=event('Twisted Spoon','transferred_out',time=0)
    result=filter_joint(rows,[hit],item_events=[e])
    ordinary=filter_joint(domain(['none']),[hit])
    assert project_joint(result['configurations'],'special_attack')['values']==project_joint(ordinary['configurations'],'special_attack')['values']
    assert result['requirements']['items']==['Twisted Spoon']


def test_unimplemented_metronome_is_never_neutral():
    request=observation(config())['input'];request['attacker']['item']='Metronome'
    assert calculate(request)['status']=='unsupported'


def test_grounding_air_balloon_and_iron_ball():
    request=observation(config())['input'];request['field'].update(terrain='psychic',attacker_grounded=False)
    request['attacker']['item']='Air Balloon'
    assert calculate(request)['status']=='exact_reference'
    request['field']['attacker_grounded']=True
    assert calculate(request)['status']=='unsupported' # contradictory explicit grounding, never neutralized
    request['attacker']['item']='Iron Ball'
    assert calculate(request)['status']=='exact_reference'


def test_light_ball_only_boosts_eligible_species():
    request=observation(config())['input'];request['attacker']['item']='Light Ball'
    a=calculate(request);request['attacker']['item']='none';b=calculate(request)
    assert a['distribution']['rolls']==b['distribution']['rolls']
    request['attacker'].update(identity='Pikachu',form='base',ability='Static',item='Light Ball')
    boosted=calculate(request);request['attacker']['item']='none';base=calculate(request)
    assert boosted['status']=='exact_reference' and boosted['distribution']['rolls']!=base['distribution']['rolls']
    assert any(m['name']=='Light Ball' for m in boosted['applied_modifiers'])


def test_policy_omissions_separate_from_damage_exclusions():
    rows=domain(['none','Life Orb','Metronome']);hit=observation(config())
    result=filter_policy_joint(rows,[hit]);assert result['item_policy']['dormant']==['Life Orb','Metronome']
    assert all('Metronome' not in cid for cid in result['updates'][0]['excluded_ids'])


@pytest.mark.parametrize('trick_room',[False,True])
def test_reviewed_quick_claw_uses_existing_order_engine_under_trick_room(trick_room):
    from test_dynamic_action_order import participant,action,state,simulate
    e=event('Quick Claw','activated',action_id='persistent-hatterene:move')
    own=participant('own',180);opp=participant('persistent-hatterene',80,item='Quick Claw')
    move=action('persistent-hatterene')
    move['activation']=reviewed_order_activation([e],battle_id='synthetic',individual='persistent-hatterene',action_id=move['id'],at=1)
    result=simulate(state(own,opp,trick_room=trick_room),[action('own'),move])
    assert result['status']=='exact'
    assert result['traces'][0]['sequence'][0]==move['id']


def test_item_review_rejects_unbound_or_altered_source(tmp_path):
    frame=tmp_path/'frame.png';frame.write_bytes(b'synthetic source')
    source=dict(source_id='synthetic:frame',image='frame.png',sha256=hashlib.sha256(frame.read_bytes()).hexdigest())
    e=event('Air Balloon');e['sources']=[source]
    replay=dict(battle_id='synthetic',frames=[dict(source,timestamp=1)],snapshots=[dict(opponents={'persistent-hatterene':{}})])
    validate_item_review([e],replay,root=tmp_path)
    frame.write_bytes(b'altered')
    with pytest.raises(ValueError,match='altered'):validate_item_review([e],replay,root=tmp_path)


def test_late_item_only_reveal_changes_causal_overlay_and_keeps_two_layers(monkeypatch):
    import battle_evidence.offensive as overlay
    actor='persistent-hatterene'
    monkeypatch.setattr(overlay,'speed_configuration_domain',lambda r,p:domain(['none','Metronome']))
    monkeypatch.setattr(overlay,'observed_configuration_domain',lambda r,p:[])
    replay=dict(battle_id='synthetic',snapshots=[dict(timestamp=0,opponents={actor:dict(individual=actor,current_form=config()['form'],support_ref='ref')})],
                support_catalog={'ref':dict(full={},observed=dict(builds=[],ability_mappings={},complete_after=0),conditions=[])})
    hit=observation(config());hit.update(attacker_form=config()['form'],assumptions=[])
    reveal=event('Metronome',time=2)
    result=overlay.offensive_overlay(replay,[hit],item_profile='practical',item_events=[reveal])
    def support(t):
        snap=next(s for s in reversed(result['snapshots']) if s['timestamp']<=t)
        return result['support_catalog'][snap['opponents'][actor]['support_ref']]
    assert 'Metronome' not in support(1)['full']['offensive']['items']
    assert support(2)['full']['offensive']['items']==['Metronome']
    assert set(support(2))=={'full','observed','conditions'}
    assert len(result['offensive_inference']['updates'])==1 # item reveal is not a manufactured damage hit


def test_normal_gem_conditional_neutrality_does_not_erase_normal_move_gap():
    request=observation(config())['input'];request['attacker']['item']='Normal Gem'
    assert calculate(request)['status']=='exact_reference' # Psyshock cannot activate Normal Gem
    request['move']='Fake Out';request['attacker']['stats']['attack']=100
    assert calculate(request)['status']=='unsupported'


def test_late_iron_ball_speed_rescue_rechecks_all_prior_hits_without_new_parent():
    from battle_evidence.item_policy import rescue_from_speed
    original=[config('none','ordinary'),config('Iron Ball','slow-parent')]
    a=observation(config());b=observation(config(),key='second',second=True)
    assert rescue_from_speed(original,['ordinary','slow-parent'],[a,b]) is None
    result=rescue_from_speed(original,['slow-parent'],[a,b])
    expected=filter_joint([original[1]],[a,b])
    assert result['configurations']==expected['configurations']
    assert result['item_policy']['iron_ball_rescue']
    assert concrete_ids(result['configurations'])<=concrete_ids(original)
    assert rescue_from_speed(original,['invented-parent'],[a,b]) is None


@pytest.mark.local_artifacts
def test_pinned_source_receipts_if_available():
    sources=registry()['sources'].values()
    if any(not Path(s['path']).exists() for s in sources):pytest.skip('Optional pinned source audit snapshots unavailable')
    for source in sources:assert hashlib.sha256(Path(source['path']).read_bytes()).hexdigest()==source['sha256']


def test_consumption_on_same_move_keeps_item_for_damage_unless_before_action():
    e=event('Life Orb','transferred_out',time=1)
    args=dict(battle_id='synthetic',individual='persistent-hatterene',at=1,available_at=1)
    assert action_item('Life Orb',[e],**args)=='Life Orb'
    e['phase']='before_action'
    assert action_item('Life Orb',[e],**args)=='none'
