"""Constraint gates and saved-evidence trace contracts, not recognition accuracy."""
from copy import deepcopy

import pytest

from battle_evidence.life_orb import absence_constraint
from battle_evidence.team_items import six_member_exclusions
from battle_evidence.constraint_trace import (refine_numeric, infer_complete_speed,
    infer_complete_offense, message_absence_window, ChronologicalTrace)
from knowledge.stat_feasibility import summary
from tests.test_dynamic_action_order import observation, configurations
from tests.test_inverse_damage import observation as damage_observation


def negative(**changes):
    evidence=dict(sources=[{'source_id':'synthetic:post-action'}],
        rule={'accepted_ui_guarantee':True,'verification':'synthetic_contract'},
        ability='Intimidate',ability_active=True,magic_guard_excluded=True,
        sheer_force_suppression_excluded=True,successful_hit=True,not_protected=True,
        not_immune=True,resolution_complete=True,multi_hit=False,multi_hit_complete=True,
        item_active=True,item_history_clear=True,after_move_hook_reached=True,
        display_window_complete=True,loss_displayed=False)
    evidence.update(changes);return evidence


def test_life_orb_valid_absence_and_user_rule_identity():
    e=negative();before=deepcopy(e);result=absence_constraint(e)
    assert result['status']=='supported' and result['exclude_current_life_orb']
    assert result['rule']['verification']=='synthetic_contract' and e==before


@pytest.mark.parametrize('field,value',[
    ('successful_hit',False),('not_protected',False),('not_immune',False),
    ('resolution_complete',False),('display_window_complete',False),
    ('item_history_clear',None),('item_active',False),('after_move_hook_reached',None),
    ('loss_displayed',True),('loss_displayed',None)])
def test_life_orb_incomplete_failed_or_unread_is_not_an_exclusion(field,value):
    assert not absence_constraint(negative(**{field:value}))['exclude_current_life_orb']


def test_magic_guard_sheer_force_and_unknown_suppression():
    assert absence_constraint(negative(ability='Magic Guard'))['status']=='rejected'
    assert absence_constraint(negative(ability='Sheer Force',sheer_force_boosted=True))['status']=='rejected'
    assert absence_constraint(negative(ability='Sheer Force',sheer_force_boosted=None))['status']=='conditional'
    assert absence_constraint(negative(ability='Sheer Force',sheer_force_boosted=False))['exclude_current_life_orb']
    result=absence_constraint(negative(ability=None,magic_guard_excluded=False))
    assert result['status']=='conditional' and not result['exclude_current_life_orb']
    # A complete current-ability domain may rule out suppression without naming one ability.
    assert absence_constraint(negative(ability=None,ability_active=None))['exclude_current_life_orb']


def test_multi_hit_completes_before_absence_and_ui_reference_is_explicit():
    assert not absence_constraint(negative(multi_hit=True,multi_hit_complete=False))['exclude_current_life_orb']
    assert absence_constraint(negative(multi_hit=True,multi_hit_complete=True))['exclude_current_life_orb']
    assert absence_constraint(negative(rule={'accepted_ui_guarantee':False}))['status']=='conditional'


def roster():return [f'b:opponent:preview:{i}' for i in range(1,7)]


def test_item_clause_covers_six_and_does_not_infer_ownership_from_transfer():
    members=roster();claim=dict(owner=members[0],item='Leftovers',sources=['synthetic'],
        original_equipped_verified=True,kind='initial_held')
    result=six_member_exclusions(members,[claim],battle_id='b',rule_verified=True)
    assert len(result['updates'])==5
    assert {x['target'] for x in result['updates']}==set(members[1:])
    assert all(x['status']=='exact' for x in result['updates'])
    consumed=dict(claim,current_status='consumed')
    assert len(six_member_exclusions(members,[consumed],battle_id='b',rule_verified=True)['updates'])==5
    for kind in ('transferred','current_only'):
        assert six_member_exclusions(members,[dict(claim,kind=kind)],battle_id='b',rule_verified=True)['updates']==[]
    assert all(x['status']=='conditional' for x in six_member_exclusions(members,[claim],battle_id='b',rule_verified=False)['updates'])
    assert all(x['status']=='conditional' for x in six_member_exclusions(members,[dict(claim,original_equipped_verified=False)],battle_id='b',rule_verified=True)['updates'])


def test_item_clause_duplicate_owners_report_a_contradiction_and_scope_is_checked():
    members=roster();claims=[dict(owner=m,item='Leftovers',sources=['synthetic'],original_equipped_verified=True,kind='initial_held') for m in members[:2]]
    assert six_member_exclusions(members,claims,battle_id='b',rule_verified=True)['contradictions']
    with pytest.raises(ValueError):six_member_exclusions(members[:4],claims,battle_id='b',rule_verified=True)
    with pytest.raises(ValueError):six_member_exclusions(members[:-1]+['other:opponent:preview:6'],claims,battle_id='b',rule_verified=True)


def test_speed_ties_priority_and_trick_room_use_existing_m3_engine():
    obs=observation(own_speed=180,first='opp')
    result=infer_complete_speed(obs,configurations([170,180,190]))
    assert result['feasible']['values']==[180,190]
    room=deepcopy(obs);room['state']['field']['trick_room']=True
    assert infer_complete_speed(room,configurations([170,180,190]))['feasible']['values']==[170,180]
    pri=observation(own_speed=180,first='own');pri['actions'][0]['move']='Fake Out'
    assert infer_complete_speed(pri,configurations([100,180,220]))['feasible']['values']==[100,180,220]


def test_offense_uses_original_inverse_and_unknown_defender_is_not_filled():
    hit=damage_observation()
    result=infer_complete_offense(hit,list(range(80,151)),'attack')
    assert result['status']=='exact' and 0<result['feasible']['count']<71
    uncertain=deepcopy(hit);uncertain['input']['defender']['stats']['defense']=None
    unknown=infer_complete_offense(uncertain,list(range(80,151)),'attack')
    assert unknown['status'] not in {'exact','conditional'} and unknown['feasible'] is None


def test_monotonic_refinement_and_conflicting_observation_never_resets_domain():
    before=summary([100,101,103]);after,status=refine_numeric(before,summary([101,102,103]),evidence_id='one')
    assert after['values']==[101,103] and status['excluded']==[100]
    bad,conflict=refine_numeric(after,summary([104]),evidence_id='two')
    assert bad==after and conflict['status']=='contradiction'


def test_message_read_failure_is_not_observed_absence():
    rows=[dict(timestamp=1,source_id='a',message=dict(selected=False,visibility='partial',raw_text='',confidence=0))]
    assert not message_absence_window(rows,0,2)['complete']
    rows[0]['message']=dict(selected=True,visibility='visible',raw_text='普通消息',confidence=.99)
    assert message_absence_window(rows,0,2)['complete']
    rows[0]['message']['raw_text']='生命被少量削减了！'
    assert message_absence_window(rows,0,2)['loss_displayed']


def test_distinct_unproven_reentries_are_not_merged(monkeypatch):
    import battle_evidence.constraint_trace as module
    monkeypatch.setattr(module,'native_domains',lambda _:dict.fromkeys(('speed','attack','special_attack'),summary([100,101])))
    rows=[dict(preview_row=i+1,species_id=sid,member_occurrence=f'b:opponent:preview:{i+1}',icon={'canonical_id':f'pokeapi:species:{sid}'}) for i,sid in enumerate([727,6,9,3,25,132])]
    identity=dict(value={'species_id':727},knowledge='observed')
    p=dict(side_id='opponent',species=identity,original_identity=identity)
    trace=ChronologicalTrace('b',rows,[],dict(pokemon={'b:opponent:a':p,'b:opponent:b':p}))
    member=trace.members['b:opponent:preview:1']
    trace.lineage('b:opponent:a',member);trace.lineage('b:opponent:b',member)
    result=trace.result()['roster'][0]
    assert len(result['lineages'])==2 and result['remaining_identity_ambiguity']
    assert result['final_stats']==result['initial']


def synthetic_trace(monkeypatch,second_opponent=False):
    import battle_evidence.constraint_trace as module
    monkeypatch.setattr(module,'native_domains',lambda _:dict.fromkeys(('speed','attack','special_attack'),summary([100,101])))
    rows=[dict(preview_row=i+1,species_id=sid,member_occurrence=f'b:opponent:preview:{i+1}',icon={'canonical_id':f'pokeapi:species:{sid}'}) for i,sid in enumerate([132,6,9,3,25,727])]
    ids=['b:opponent:a','b:opponent:b' if second_opponent else 'b:self:a']
    pokemon={pid:dict(side_id='opponent' if ':opponent:' in pid else 'self',species=dict(value={'species_id':132 if i==0 else 6},knowledge='observed')) for i,pid in enumerate(ids)}
    return ChronologicalTrace('b',rows,[],dict(pokemon=pokemon)),ids


def receipt(pid,time,kind='move_execution',**attributes):
    event=dict(event_id=f'e:{time}',event_type=kind,attributes=dict(observation_time=time,**attributes),
        canonical_references={'move':{'canonical_id':'pokeapi:move:33'}},evidence=[])
    return dict(event=event,bindings={'actor':{'pokemon_instance_id':pid}},application_status='applied_confirmed')


def test_opponent_first_speed_pair_is_retained_and_available_at_cycle_end(monkeypatch):
    trace,ids=synthetic_trace(monkeypatch)
    records=[receipt(ids[0],1),receipt(ids[1],2)]
    trace.speed_pairs(records,{},[dict(start=0),dict(start=5)])
    updates=trace.result()['updates']
    assert len(updates)==1 and updates[0]['new_constraint']['first']==ids[0]
    assert updates[0]['timestamp']==5 and updates[0]['classification']=='unresolved'
    assert 'provisional command cycle is not a certified single order decision' in updates[0]['new_constraint']['admissibility_reasons']


def test_two_opponent_pair_is_one_relation_with_two_affected_panels(monkeypatch):
    trace,ids=synthetic_trace(monkeypatch,second_opponent=True)
    trace.speed_pairs([receipt(ids[0],1),receipt(ids[1],2)],{},[dict(start=0)])
    result=trace.result()
    assert len(result['updates'])==2 and result['counts']['unique_speed_pair_candidates']==1


def test_copy_ends_without_native_stat_claim_and_transfer_clears_only_current(monkeypatch):
    trace,ids=synthetic_trace(monkeypatch)
    member=trace.members['b:opponent:preview:1'];line=trace.lineage(ids[0],member)
    copied={'attack':dict(value=135,knowledge='derived')}
    trace.process_event(receipt(ids[0],1,move_origin='transformed'),{'pokemon':{ids[0]:{'copied_appearance':{'species_id':6},'copied_non_hp_stats':copied}}})
    assert line['native_moves']==[] and line['copied_stats']['attack']['value']==135
    trace.process_event(receipt(ids[0],2,'switch_out'),{'pokemon':{ids[0]:{}}})
    assert line['copied_stats'] is None and line['stats']==member['initial']
    line.update(current_item='Life Orb',original_item='Life Orb',excluded_current_items=['Leftovers'])
    trace.process_event(receipt(ids[0],3,'item_change',change='transfer'),{})
    assert line['current_item']=='none' and line['excluded_current_items']==[]
    assert line['original_item']=='Life Orb'
