"""B21 recipient grammar, conditional field recovery and explicit missed targets."""
from copy import deepcopy
import pytest
from battle_events.schema import BattleEvent,Evidence
from tests.test_hp_attribution import seed,endpoint
from tests.test_evidence_fusion import active
from tests.test_semantic_state import deliver


def phase(e,n,value='end_of_turn'):
    ev=BattleEvent('phase:'+str(n),'phase_observation','field',None,None,'resolution phase',{},None,
        [Evidence('fixture','fixture#'+str(n),[],dict(timestamp=n))],1.,'supported',[],
        dict(phase=value,observation_time=n,resolution_cycle_start=value=='command'))
    return e.apply(ev,sequence=n*10)


def grassy(e):deliver(e,'脚下青草如茵！',2)
def close(e,n=12):phase(e,n,'command')


@pytest.mark.parametrize('side,prefix,name',[('self','','钢铠鸦'),('opponent','对手的','暴飞龙')])
def test_possessive_recovery_names_the_recipient_not_an_unknown_actor(side,prefix,name):
    e=seed();d,r=deliver(e,prefix+name+'的\n体力回复了！',3)
    assert len(d['events'])==1 and r[0].application_status=='recorded_observation'
    assert d['events'][0]['actor']['name']==name
    assert r[0].bindings['actor']['pokemon_instance_id']==active(e,side=side).pokemon_instance_id
    assert active(e,side=side).hp.observations[-1]['cause'] is None


def test_grassy_recovery_uses_observed_endpoints_and_preserves_recipient_order():
    e=seed();grassy(e);endpoint(e,3,90,side='opponent',sid=373);phase(e,4)
    first,_=deliver(e,'对手的暴飞龙的体力回复了！',5)
    endpoint(e,6,95,side='opponent',sid=373);endpoint(e,7,95,side='opponent',sid=373)
    second,_=deliver(e,'钢铠鸦的体力回复了！',8);endpoint(e,9,106);endpoint(e,10,106);close(e)
    notices=[o for o in e.state.observations if (o.get('cause') or {}).get('kind')=='grassy_terrain']
    assert [o['affected_instance_id'] for o in notices]==[active(e,side='opponent').pokemon_instance_id,active(e).pokemon_instance_id]
    assert [o['recovery_order_index'] for o in notices]==[0,1]
    out=e.hp_resolutions()['episodes'];heals=[o for o in out if (o.get('cause') or {}).get('kind')=='grassy_terrain']
    assert sorted(o['delta'] for o in heals)==[5,6]
    assert all(o['attribution_status']=='supported' for o in heals)
    assert all(not p.stages['speed'].changes for p in e.state.pokemon.values())


@pytest.mark.parametrize('active_terrain,end_phase',[(False,True),(True,False)])
def test_terrain_presence_and_end_of_turn_are_both_required(active_terrain,end_phase):
    e=seed()
    if active_terrain:grassy(e)
    if end_phase:phase(e,3)
    _,r=deliver(e,'钢铠鸦的体力回复了！',4)
    assert r[0].application_status=='recorded_observation'
    assert e.state.observations[-1]['cause'] is None


def test_ended_terrain_and_explicit_source_are_not_grassy_recovery():
    e=seed();grassy(e);deliver(e,'脚下的青草消失了！',3);phase(e,4)
    deliver(e,'钢铠鸦的体力回复了！',5);assert e.state.observations[-1]['cause'] is None
    e=seed();grassy(e);phase(e,3)
    deliver(e,'钢铠鸦因钢铠鸦的吃剩的东西回复了体力！',4)
    assert e.state.observations[-1]['cause']['kind']=='item'


def test_explicit_turn_end_item_banner_overrides_field_for_same_recipient():
    e=seed();grassy(e);phase(e,3);deliver(e,'钢铠鸦的吃剩的东西！',4)
    deliver(e,'钢铠鸦的体力回复了！',5)
    assert e.state.observations[-1]['cause']['kind']=='item'


def test_one_grassy_recovery_per_recipient_per_resolution_and_no_fabricated_hp():
    e=seed();grassy(e);phase(e,3);deliver(e,'钢铠鸦的体力回复了！',4)
    assert active(e).hp.current.value==100
    endpoint(e,5,106);endpoint(e,6,106)
    deliver(e,'钢铠鸦的体力回复了！',7);endpoint(e,8,112);endpoint(e,9,112);close(e)
    notices=[o for o in e.state.observations if (o.get('cause') or {}).get('kind')=='grassy_terrain']
    assert len(notices)==1
    heals=[o for o in e.hp_resolutions()['episodes'] if (o.get('cause') or {}).get('kind')=='grassy_terrain']
    assert len(heals)==1 and heals[0]['after']==106 and heals[0]['delta']==6
    phase(e,13);deliver(e,'钢铠鸦的体力回复了！',14)
    assert e.state.observations[-1]['cause']['kind']=='grassy_terrain'


def test_current_own_status_move_recovery_is_not_forced_to_terrain():
    e=seed();grassy(e);phase(e,3);deliver(e,'钢铠鸦使出了羽栖！',4)
    deliver(e,'钢铠鸦的体力回复了！',5)
    assert e.state.observations[-1]['cause'] is None


def test_named_missed_target_is_not_the_attacker_and_no_damage_is_generated():
    e=seed();move,_=deliver(e,'对手的暴飞龙使出了催眠术！',2)
    d,r=deliver(e,'没有击中钢铠鸦！',3)
    assert d['events'][0]['event_type']=='move_miss'
    assert d['events'][0]['actor'] is None and d['events'][0]['target']['species_id']==823
    assert r[0].application_status=='recorded_observation'
    assert r[0].bindings['target']['pokemon_instance_id']==active(e).pokemon_instance_id
    assert r[0].bindings['resolved_event']['attributes']['effect_of']==move['events'][0]['event_id']
    assert active(e).hp.current.value==100 and e.hp_resolutions()['episodes']==[]
    endpoint(e,4,90);endpoint(e,5,90);close(e)
    assert all(o['cause'] is None for o in e.hp_resolutions()['episodes'])


def test_miss_retains_original_identity_evidence_and_retracts_action_outcome():
    e=seed();deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    d,r=deliver(e,'没有击中钢铠鸦！',3)
    assert r[0].bindings['resolved_event']['event_id']==d['events'][0]['event_id']
    assert r[0].bindings['resolved_event']['evidence']==d['events'][0]['evidence']
    endpoint(e,4,90);endpoint(e,5,90);close(e)
    assert e.hp_resolutions()['episodes'][0]['cause'] is None
    e.retract(d['events'][0]['event_id'],reason='incorrect miss')
    assert e.hp_resolutions()['episodes'][0]['cause']['kind']=='move'


def test_recovery_notice_after_hp_animation_rebinds_only_that_observed_increase():
    e=seed();grassy(e);phase(e,3)
    endpoint(e,4,95,side='opponent',sid=373);endpoint(e,5,95,side='opponent',sid=373)
    deliver(e,'对手的暴飞龙的体力回复了！',6)
    endpoint(e,7,106);endpoint(e,8,106)
    deliver(e,'钢铠鸦的体力回复了！',9);close(e)
    heals=[o for o in e.hp_resolutions()['episodes'] if (o.get('cause') or {}).get('kind')=='grassy_terrain']
    assert len(heals)==1 and heals[0]['before']==100 and heals[0]['after']==106 and heals[0]['delta']==6
    assert heals[0]['attribution_status']=='supported'
    assert len(e.state.pokemon[active(e).pokemon_instance_id].hp.observations)==4


def test_normal_command_cycle_requires_all_four_original_participant_actions():
    from tests.test_evidence_fusion import hud
    e=seed();e.apply(hud(21,2,530,slot='left'),sequence=21)
    e.apply(hud(22,2.1,936,side='opponent',slot='left'),sequence=22)
    grassy(e);phase(e,3,'command')
    deliver(e,'钢铠鸦使出了铁头！',4);deliver(e,'龙头地鼠使出了铁头！',5)
    deliver(e,'对手的暴飞龙使出了铁头！',6)
    early,_=deliver(e,'钢铠鸦的体力回复了！',7)
    assert e.state.observations[-1]['cause'] is None
    deliver(e,'对手的红莲铠骑使出了铁头！',8)
    final,_=deliver(e,'钢铠鸦的体力回复了！',9)
    assert e.state.observations[-1]['cause']['kind']=='grassy_terrain'
    e.retract(final['events'][0]['event_id'],reason='no final observed endpoint')
    assert all((o.get('cause') or {}).get('kind')!='grassy_terrain' for o in e.hp_resolutions()['episodes'])


def test_later_unchanged_hud_confirms_recovery_across_other_recipient_message():
    e=seed();grassy(e);phase(e,3)
    endpoint(e,4,106);deliver(e,'钢铠鸦的体力回复了！',5)
    deliver(e,'对手的暴飞龙的体力回复了！',6)
    endpoint(e,7,106);endpoint(e,8,106);close(e)
    own=[o for o in e.hp_resolutions()['episodes'] if o['affected_instance_id']==active(e).pokemon_instance_id]
    assert len(own)==1 and own[0]['delta']==6 and own[0]['attribution_status']=='supported'


def test_recovery_without_final_endpoint_is_qualitative_only():
    e=seed();grassy(e);phase(e,3);deliver(e,'钢铠鸦的体力回复了！',4);close(e)
    assert active(e).hp.current.value==100
    assert e.hp_resolutions()['episodes']==[]


def test_normal_command_observation_starts_one_cycle_per_visible_session():
    from recognition.event_report import video_events
    rows=[]
    for n,active_flag in enumerate([True,True,False,True]):
        rows.append(dict(timestamp=n,source_id='saved#'+str(n),sha256=str(n),image='saved.png',
            ui={},occurrence_decision={'events':[]},command={'active':active_flag},
            command_inspection={'reason':'normal_four_hud_command'}))
    events=video_events(rows,[],'test')
    assert len(events)==2 and all(e['event_type']=='phase_observation' for e in events)
    assert [e['attributes']['observation_time'] for e in events]==[0,3]
    assert all(e['attributes'].get('turn') is None for e in events)
