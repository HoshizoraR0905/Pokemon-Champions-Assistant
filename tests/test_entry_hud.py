"""Causal episode binding and bounded first-opportunity auditing."""
from copy import deepcopy
from tests.test_provisional_occupancy import arrival
from tests.test_trainer_nickname_binding import visual_fixture, parse
from tests.test_switch_continuity import apply_text
from tracking.active_continuity import current_episode
from battle_events.parser import BattleContext


def observe(e,t,frame,**kwargs):
    _,_,factory=visual_fixture();h=factory(t,frame)
    h.attributes['battle_id']='test'
    if 'raw' in kwargs:h.attributes['species']['raw_text']=kwargs['raw']
    if 'region' in kwargs:h.attributes['source_region_type']=kwargs['region']
    if 'confidence' in kwargs:h.attributes['species']['confidence']=kwargs['confidence']
    return e.apply(h,sequence=len(e.history)+1)


def episode(e):return current_episode(e.state,e.state.sides['opponent'].active_slots['right'])


def test_failed_candidate_is_audited_before_first_eligible_and_resolution():
    e,_=arrival();observe(e,2,'bad',raw='?');observe(e,3,'one')
    a=episode(e)['hud_binding'];assert a['first_candidate_time']==2 and a['first_eligible_time']==3
    assert a['candidates'][0]['reasons']==['episode_name_unassociated']
    observe(e,4,'two');assert episode(e)['species_resolution_time']==4
    assert episode(e)['hud_binding']['identity_source']['timestamp']==3


def test_same_frame_and_unrelated_overlay_cannot_confirm():
    e,_=arrival();observe(e,2,'one');observe(e,3,'one');observe(e,4,'two',region='party')
    assert episode(e)['species_id'] is None
    assert 'not_genuine_battle_hud' in episode(e)['hud_binding']['candidates'][-1]['reasons']


def test_expiry_requires_fresh_prospective_pair_without_backfill():
    e,_=arrival();observe(e,2,'one');observe(e,7,'two')
    assert episode(e)['species_id'] is None
    assert episode(e)['hud_binding']['status']=='expired'
    observe(e,8,'three');ep=episode(e)
    assert ep['species_resolution_time']==8 and ep['hud_binding']['status']=='resolved_prospectively'
    assert ep['hud_binding']['expired_at']==5


def test_arrival_horizon_does_not_allow_indefinite_entry_confirmation():
    e,_=arrival();observe(e,40,'one');observe(e,41,'two')
    assert episode(e)['hud_binding']['status']=='resolved_prospectively'
    assert episode(e)['species_resolution_time']==41


def test_title_suffix_requires_an_independent_episode_hud_pair():
    e,_=arrival(name='获奖的Pebble');observe(e,2,'one')
    assert episode(e)['species_id'] is None and not episode(e).get('hud_display_name')
    observe(e,3,'two')
    ep=episode(e)
    assert ep['display_reference']=='获奖的Pebble' and ep['species_id']==205
    assert ep['hud_display_name']['value']=='Pebble'
    assert ep['hud_display_name']['possible_title_segment']=='获奖的'
    assert ep['hud_display_name']['established_at']==ep['species_resolution_time']==3


def test_unidentified_actor_can_reveal_move_without_species_mechanics():
    e,_=arrival();pid=episode(e)['instance_id']
    r=apply_text(e,2,'对手的Pebble使出了守住！')
    assert r.application_status=='applied_partial' and not e.state.pokemon[pid].species.known
    assert len(e.state.pokemon[pid].moves.executed)==1


def test_departure_and_reentry_do_not_share_a_confirmation_frame():
    e,_=arrival();observe(e,2,'one');old=episode(e)['episode_id']
    apply_text(e,3,'Guest换下了Pebble！');apply_text(e,4,'Guest派出了Pebble！');observe(e,5,'two')
    assert episode(e)['episode_id']!=old and episode(e)['species_id'] is None


def test_no_effect_explicit_receiver_precedes_same_species_alias_ownership():
    c=BattleContext()
    for side in ('self','opponent'):
        c.active[side].add('pokeapi:species:279')
        c.display_aliases['Mirror'+(' ' if side=='self' else '  ')]=dict(side=side,
            identity=dict(canonical_id='pokeapi:species:279',species_id=279,name='大嘴鸥'),
            instance_id=side,evidence=[dict(source='icon')])
    e=parse('对于对手的Mirror，好像没有效果.....',c)
    assert e.side=='opponent' and e.event_type=='effectiveness'
    assert {a['instance_id'] for a in e.attributes['display_alias_evidence']}=={'opponent'}
    assert 'side_unknown' not in e.uncertainty
    e,_=arrival();r=apply_text(e,2,'对于对手的Pebble，好像没有效果.....')
    assert r.application_status=='recorded_observation'
    assert r.bindings['resolved_event']['attributes']['target_instance_id']==episode(e)['instance_id']


def test_inconclusive_intermediate_frame_is_audited_without_becoming_proof():
    e,_=arrival();observe(e,2,'one');observe(e,2.5,'bad',raw='?');observe(e,3,'two')
    assert episode(e)['species_resolution_time']==3
    assert len(episode(e)['hud_binding']['candidates'])==3


def test_known_message_identity_also_records_first_hud_opportunity():
    e,_=arrival(name='佛烈托斯')
    ep=episode(e)
    assert ep['species_known_at_entry'] and ep['hud_binding']['first_candidate_time'] is None
    observe(e,2,'one',raw='佛烈托斯')
    ep=episode(e)
    assert ep['hud_binding']['first_candidate_time']==2
    assert ep['hud_binding']['first_eligible_time']==2
    assert ep['hud_binding']['status']=='pending'
    observe(e,3,'two',raw='佛烈托斯')
    assert episode(e)['hud_binding']['status']=='known_identity_verified'


def test_resolved_nickname_hud_remains_supported_without_restarting_entry_search():
    e,_=arrival();observe(e,2,'one');observe(e,3,'two')
    r=observe(e,5,'three')
    assert r.bindings['hud']['status']=='accepted'
    assert episode(e)['species_resolution_time']==3
    assert r.bindings['hud']['entry_identity_support']['policy']=='current_episode_independent_hud_v1'


# The current saved-run contract is separate from immutable historical results.
import json
from pathlib import Path
import pytest


@pytest.mark.local_artifacts('.cache/battles/sample_battle_7/evaluation/m238-entry-hud-v4/summary.json')
def test_final_saved_battle7_preserves_applied_facts_and_routes_both_named_results():
    root=Path('.cache/battles/sample_battle_7/evaluation')
    summary=json.loads((root/'m238-entry-hud-v4/summary.json').read_text())
    replay=json.loads((root/'m238-entry-hud-v4/replay.json').read_text())
    baseline=json.loads((root/'m238-provisional-entry-v2/replay.json').read_text())
    assert not summary['previously_applied_regressions'] and not summary['final_slot_changes'] and not summary['invariants']
    assert summary['after']['deferred']<=summary['before']['deferred']-2
    assert sum(summary['after'].values())==summary['records']
    assert [h['event'] for h in replay['history']]==[h['event'] for h in baseline['history']]
    papudo=next(e for e in summary['provisional_episodes'] if e['display_reference']=='Papudo')
    assert papudo['hud_binding']['first_candidate_time']==papudo['hud_binding']['first_eligible_time']==520.0216666666666
    results=[h for h in replay['history'] if '对于对手的Papudo' in h['event']['original_text']]
    assert len(results)==2
    for h in results:
        e=h['bindings']['resolved_event']
        assert h['application_status']=='recorded_observation' and e['side']=='opponent'
        assert e['attributes']['target_instance_id']==papudo['instance_id']
    timeline=json.loads((root/'m238-entry-hud-v4/timeline.json').read_text())
    start=next(i for i,row in enumerate(timeline) if row['event_id']==papudo['entry_event_id'])
    for row in timeline[start:]:
        p=row['slots']['opponent:right']
        if row['timestamp']<papudo['species_resolution_time']:
            assert p['instance_id']==papudo['instance_id'] and p['species_id'] is None


@pytest.mark.parametrize('message,hud_name,prefix',[
    ('级别对战大师Big Nugget','Big Nugget','级别对战大师'),
    ('喜欢宝可梦的Invincible','Invincible','喜欢宝可梦的'),
    ('想睡觉的铝钢桥龙','想睡觉的铝钢桥龙',None),
    ('喜欢宝可梦的Invincible','喜欢宝可梦的Invincible',None),
])
def test_authoritative_hud_name_preserves_title_like_nicknames(message,hud_name,prefix):
    e,_=arrival(name=message)
    assert episode(e)['species_id'] is None
    before=e.state.to_dict()
    observe(e,2,'frame-one',raw=hud_name);observe(e,3,'frame-two',raw=hud_name)
    ep=episode(e)
    assert ep['display_reference']==message
    assert ep['hud_display_name']['value']==hud_name
    assert ep['hud_display_name']['possible_title_segment']==prefix
    assert ep['species_id']==205
    assert before['pokemon'][ep['instance_id']]['species']['value'] is None
    r=apply_text(e,4,'对手的'+hud_name+'使出了守住！')
    assert r.application_status=='applied_partial'
    assert r.bindings['resolved_event']['attributes']['actor_instance_id']==ep['instance_id']


def test_suffix_without_supported_placement_cannot_borrow_a_party_or_state_guess():
    e,_=arrival(name='DecoratedPebble',vacancies=('left','right'))
    observe(e,2,'one');observe(e,3,'two')
    assert all(not p.species.known for p in e.state.pokemon.values())
    assert not any(ep.get('hud_display_name') for ep in e.state.knowledge['active_entry_episodes'])


def test_repeated_frame_and_changing_short_names_cannot_establish_a_title_boundary():
    e,_=arrival(name='DecoratedPebble')
    observe(e,2,'same');observe(e,3,'same')
    assert not episode(e).get('hud_display_name')
    observe(e,3.5,'new',raw='ble')
    assert not episode(e).get('hud_display_name')


def test_short_hud_name_does_not_carry_to_a_later_arrival_episode():
    e,_=arrival(name='DecoratedPebble');observe(e,2,'one');observe(e,3,'two')
    previous=episode(e)['episode_id'];apply_text(e,4,'Guest换下了Pebble！')
    apply_text(e,5,'Guest派出了DecoratedPebble！');observe(e,6,'three')
    assert episode(e)['episode_id']!=previous
    assert episode(e)['species_id'] is None and not episode(e).get('hud_display_name')



def test_suffix_with_a_competing_active_message_reference_abstains():
    from copy import deepcopy
    from tracking.battle_state import PokemonState
    from tracking.entry_hud import observe as audit_observation, support
    e,_=arrival(name='DecoratedPebble');first=episode(e)
    p=PokemonState('other','opponent');p.location=deepcopy(e.state.pokemon[first['instance_id']].location)
    p.location.value=dict(kind='active',slot='left');e.state.pokemon['other']=p
    e.state.sides['opponent'].active_slots['left']='other'
    other=deepcopy(first);other.update(instance_id='other',episode_id='other-entry',slot='left',display_reference='Pebble')
    e.state.knowledge['active_entry_episodes'].append(other)
    _,_,factory=visual_fixture()
    for t,frame in [(2,'one'),(3,'two')]:
        h=factory(t,frame);h.attributes['battle_id']='test'
        audit_observation(e.state,h)
        assert support(e.state,h) is None
    assert not first.get('hud_display_name')


def test_wrong_side_future_source_and_low_ocr_cannot_confirm_a_suffix():
    e,_=arrival(name='DecoratedPebble')
    _,_,factory=visual_fixture()
    h=factory(.5,'before');h.attributes['battle_id']='test';e.apply(h,sequence=len(e.history)+1)
    h=factory(2,'future');h.attributes['battle_id']='test';h.evidence[0].details['timestamp']=20
    e.apply(h,sequence=len(e.history)+1)
    h=factory(2.5,'wrong-side');h.side='self';h.attributes['battle_id']='test'
    e.apply(h,sequence=len(e.history)+1)
    observe(e,3,'weak',confidence=.8);observe(e,4,'one')
    assert episode(e)['species_id'] is None
    assert episode(e)['hud_binding']['first_candidate_time']==2
    assert episode(e)['hud_binding']['first_eligible_time']==4
    observe(e,5,'two');assert episode(e)['hud_display_name']['value']=='Pebble'


@pytest.mark.parametrize('confidence,occupied',[(.99,True),(.9,False)])
def test_saved_legacy_child_cannot_infer_species_from_a_title_like_substring(confidence,occupied):
    from battle_events.parser import EventParser
    e,_=arrival(name='Unclassified')
    receipt=next(h for h in e.history if h.event['event_type']=='send_out')
    old=deepcopy(receipt.bindings['resolved_event'])
    old['original_text']='Guest派出了想睡觉的佛烈托斯！';old['ocr_confidence']=confidence
    old['actor']=EventParser().identity('佛烈托斯','species')
    old['attributes'].update(display_reference='想睡觉的佛烈托斯',fusion_context=False,
        ordered_display_references=['想睡觉的佛烈托斯'])
    receipt.event=old;e.replay()
    assert receipt.event['actor']['species_id']==205  # immutable saved assertion
    assert not any(p.species.known for p in e.state.pokemon.values())
    assert bool(e.state.sides['opponent'].active_slots)==occupied
