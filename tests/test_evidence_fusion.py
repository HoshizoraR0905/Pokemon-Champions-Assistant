"""Portable observation-fusion tests: no media or generated artifact prerequisites."""
from copy import deepcopy
import pytest
from battle_events.schema import BattleEvent, Evidence
from tracking.battle_state import BattleState
from tracking.state_engine import StateEngine
from tracking.hidden_state import HiddenEngine
from tracking.evidence_fusion import identity_evidence

NAMES={373:'暴飞龙',530:'龙头地鼠',823:'钢铠鸦',936:'红莲铠骑',903:'大狃拉',876:'爱管侍'}


def species(sid, confidence=.99, method='exact'):
    return dict(raw_text=NAMES[sid],confidence=confidence,resolution=dict(status='resolved',method=method,
        species_id=sid,confidence='strong',canonical_identity=f'pokeapi:pokemon:{sid}',identity_status='resolved_unique'))


def hud(number,t,sid,*,slot='right',side='self',hp=None,mon=None,icon=None,bid='test',continuity=None):
    return BattleEvent(f'hud:{number}','hud_observation',side,None,None,'HUD',{},None,
        [Evidence('cached_hud',f'{bid}.mp4#{t}',[str(number)],dict(timestamp=t))],None,'supported',[],
        dict(battle_id=bid,slot=slot,observation_time=t,species=mon or species(sid),icon=icon or {},
             hp=dict(value=hp,confidence=.99) if hp is not None else {},continuity=continuity or {}))


def message(number,t,text):
    return BattleEvent(f'msg:{number}','unknown','unknown',None,None,text,{},None,
        [Evidence('video_message',f'test.mp4#{t}',[str(number)],dict(timestamp=t))],.99,'uncertain',[],
        dict(fusion_context=True,observation_time=t))


def active(engine,slot='right',side='self'):
    return engine.state.pokemon[engine.state.sides[side].active_slots[slot]]


def test_progressive_later_hud_and_unknown_transition_interval():
    engine=StateEngine(BattleState('test'))
    assert not engine.state.pokemon
    engine.apply(hud(1,10,530,hp={'current':185,'maximum':185}),sequence=1)
    old=active(engine).pokemon_instance_id
    record=engine.apply(hud(2,364,823,hp={'current':162,'maximum':173}),sequence=2)
    assert active(engine).species.value['species_id']==823
    assert engine.state.pokemon[old].location.knowledge=='unknown'
    change=record.bindings['hud']['occupancy_change']
    assert change['after']==10 and change['at_or_before']==364
    assert change['cause'] is None and change['action_time'] is None
    assert all(r.event['event_type']=='hud_observation' for r in engine.history)
    assert engine.state.pokemon[old].fainted.knowledge=='unknown'


def test_hp_observations_have_no_damage_cause_and_preserve_instance():
    engine=StateEngine(BattleState('test'))
    for n,hp in enumerate([172,106,52],1):
        engine.apply(hud(n,n*10,373,hp={'current':hp,'maximum':172}),sequence=n)
    p=active(engine)
    assert len(engine.state.pokemon)==1 and p.hp.current.value==52
    assert [x['after'] for x in p.hp.observations]==[172,106,52]
    assert all(x['before'] is None for x in p.hp.observations)
    assert not p.fainted.known


def test_exact_semantics_require_unique_raw_name_and_confidence():
    assert identity_evidence(species(823),{})[1]=='accepted'
    corrupted=species(823);corrupted['raw_text']='钢铠鸟'
    assert identity_evidence(corrupted,{})[1]=='deferred'
    assert identity_evidence(species(823,.8),{})[1]=='deferred'
    assert identity_evidence(species(823,.8),{},dict(raw='钢铠鸦',species_id=823,status='deferred',confidence=.8))[1]=='accepted'
    assert identity_evidence(species(823),dict(status='resolved',species_id=530))[1]=='conflicting'


def test_ambiguous_identity_preserves_evidence_without_forced_assignment():
    engine=StateEngine(BattleState('test'));bad=species(823)
    bad['resolution'].update(status='ambiguous',method='ambiguous_exact')
    r=engine.apply(hud(1,10,823,mon=bad),sequence=1)
    assert not engine.state.pokemon
    assert r.bindings['hud']['status']=='deferred'
    assert engine.state.observations[0]['event_id']=='hud:1'


def test_low_confidence_hud_can_be_confirmed_only_prospectively():
    engine=StateEngine(BattleState('test'))
    engine.apply(hud(1,10,823,mon=species(823,.8)),sequence=1)
    assert not engine.state.pokemon
    engine.apply(hud(2,20,823,mon=species(823,.8)),sequence=2)
    assert len(engine.state.pokemon)==1
    engine.retract('hud:2',reason='bad later frame')
    assert not engine.state.pokemon


def test_no_future_evidence_leakage_and_retraction_rebinds_prefix():
    engine=StateEngine(BattleState('test'))
    use=message(1,5,'钢铠鸦使出了守住！')
    engine.apply(use,sequence=1)
    engine.apply(hud(2,10,823),sequence=2)
    assert engine.history[0].application_status=='deferred'
    r=engine.apply(message(3,15,'钢铠鸦使出了守住！'),sequence=3)
    assert r.application_status=='applied_partial'
    engine.retract('hud:2',reason='incorrect HUD')
    assert engine.history[0].application_status==engine.history[2].application_status=='deferred'
    engine.correct('hud:2',hud(2,10,823),sequence=2,reason='verified cached source')
    assert engine.history[0].application_status=='deferred'
    assert engine.history[2].application_status=='applied_partial'


def test_move_revelation_is_partial_and_hidden_membership_has_no_target_effect():
    engine=StateEngine(BattleState('test'));engine.apply(hud(1,10,823),sequence=1)
    before=deepcopy(active(engine).hp)
    event=message(2,12,'钢铠鸦使出了守住！');r=engine.apply(event,sequence=2)
    assert r.application_status=='applied_partial'
    assert r.bindings['admissibility']==dict(actor=True,move=True,target=False,effects=False,reason='target_and_effects_not_established')
    p=active(engine)
    assert p.hp==before and p.moves.known_slots=={}
    assert not p.mechanics.get('protect_chain')
    hidden=HiddenEngine();hidden.seed(engine.initial.to_dict())
    effective=r.bindings['resolved_event']
    hidden.apply(effective,instance_id=p.pokemon_instance_id,side='self',sequence=1,application_status=r.application_status)
    assert hidden.projection()['pokemon'][p.pokemon_instance_id]['fields']['moves']['members']==['pokeapi:move:182']
    assert hidden.projection()['pokemon'][p.pokemon_instance_id]['fields']['moves']['slots']=={}
    assert HiddenEngine.from_dict(hidden.to_dict()).to_dict()==hidden.to_dict()
    hidden.retract(effective['event_id'],reason='withdraw incorrect source')
    assert not hidden.projection()['pokemon']
    hidden.correct(effective['event_id'],effective,reason='verified original observation',instance_id=p.pokemon_instance_id)
    assert hidden.projection()['pokemon'][p.pokemon_instance_id]['fields']['moves']['members']==['pokeapi:move:182']


def test_repeated_observation_is_exactly_idempotent():
    engine=StateEngine(BattleState('test'));event=hud(1,10,823,hp={'current':52,'maximum':172})
    engine.apply(event,sequence=1);before=engine.to_dict()
    engine.apply(event,sequence=1)
    assert engine.to_dict()==before
    assert StateEngine.from_dict(before).to_dict()==before


def test_reappearance_does_not_merge_by_species_but_explicit_relation_can():
    engine=StateEngine(BattleState('test'));engine.apply(hud(1,10,823),sequence=1);original=active(engine).pokemon_instance_id
    engine.apply(message(2,12,'钢铠鸦使出了守住！'),sequence=2)
    engine.apply(hud(3,20,530),sequence=3)
    engine.apply(hud(4,30,823),sequence=4)
    assert active(engine).pokemon_instance_id!=original
    assert engine.state.pokemon[original].moves.executed
    engine.correct('hud:4',hud(4,30,823,continuity=dict(instance_id=original,evidence=[{'source':'verified-instance-relation'}])),
                   sequence=4,reason='independent instance continuity')
    assert active(engine).pokemon_instance_id==original and len(active(engine).moves.executed)==1


def test_percent_is_not_absolute_and_hp_conflict_does_not_erase_identity():
    engine=StateEngine(BattleState('test'));engine.apply(hud(1,10,823,hp=50),sequence=1)
    assert active(engine).hp.current.knowledge=='unknown'
    assert active(engine).hp.displayed_percent.value==50
    engine.apply(hud(2,20,823,hp={'current':52,'maximum':172}),sequence=2)
    r=engine.apply(hud(3,30,823,hp={'current':53,'maximum':173}),sequence=3)
    assert r.bindings['hud']['hp_status']=='conflicting'
    assert active(engine).hp.current.value==52
    assert active(engine).species.value['species_id']==823


def test_cross_battle_and_duplicate_species_do_not_merge():
    engine=StateEngine(BattleState('test'))
    rejected=engine.apply(hud(1,10,823,bid='other'),sequence=1)
    assert rejected.application_status=='rejected' and not engine.state.pokemon
    engine.apply(hud(2,20,823,slot='left'),sequence=2)
    engine.apply(hud(3,20,823,slot='right'),sequence=3)
    assert active(engine,'left').pokemon_instance_id!=active(engine,'right').pokemon_instance_id
    r=engine.apply(message(4,25,'钢铠鸦使出了守住！'),sequence=4)
    assert r.application_status=='deferred'


def test_simultaneous_contradictory_huds_do_not_overwrite():
    engine=StateEngine(BattleState('test'));engine.apply(hud(1,10,823),sequence=1)
    r=engine.apply(hud(2,10,530),sequence=2)
    assert r.bindings['hud']['status']=='conflicting'
    assert active(engine).species.value['species_id']==823
    assert engine.apply(message(3,12,'钢铠鸦使出了守住！'),sequence=3).application_status=='deferred'


def test_partial_move_and_later_result_apply_quantitative_effect_once():
    engine=StateEngine(BattleState('test'));engine.apply(hud(1,10,823),sequence=1)
    pid=active(engine).pokemon_instance_id
    def stat(number,attrs):
        return BattleEvent(f'stat:{number}','stat_change','self',deepcopy(active(engine).species.value),None,
            'independently measured stage result',{},None,[Evidence('reviewed','test',[str(number)])],
            1,'supported',[],dict(actor_instance_id=pid,stats=['attack'],**attrs),status='confirmed')
    engine.apply(stat(1,dict(change='replace',value=0)),sequence=2)
    r=engine.apply(message(2,12,'钢铠鸦使出了剑舞！'),sequence=3)
    assert r.application_status=='applied_partial'
    assert active(engine).stages['attack'].value.value==0
    result=stat(2,dict(change='increment',stages=2,effect_of='msg:2'))
    engine.apply(result,sequence=4)
    assert active(engine).stages['attack'].value.value==2
    engine.apply(result,sequence=4)
    assert active(engine).stages['attack'].value.value==2


def test_nickname_requires_repeated_independent_icon_evidence():
    mon=species(823,method='icon_only');mon['raw_text']='Raven'
    icon=dict(status='resolved',species_id=823,canonical_identity='pokeapi:pokemon:823',candidates=[dict(similarity=.94)])
    engine=StateEngine(BattleState('test'))
    engine.apply(hud(1,10,823,mon=mon,icon=icon),sequence=1)
    assert not engine.state.pokemon
    engine.apply(hud(2,20,823,mon=mon,icon=icon),sequence=2)
    r=engine.apply(message(3,25,'Raven使出了守住！'),sequence=3)
    assert r.application_status=='applied_partial'
    assert r.bindings['actor']['pokemon_instance_id']==active(engine).pokemon_instance_id


def test_bare_exact_species_does_not_assert_default_form():
    ref,status,_=identity_evidence(species(373),{})
    assert status=='accepted' and 'canonical_identity' not in ref


def test_even_misordered_delivery_cannot_bind_future_hud():
    engine=StateEngine(BattleState('test'));engine.apply(hud(1,10,823),sequence=1)
    assert engine.apply(message(2,5,'钢铠鸦使出了守住！'),sequence=2).application_status=='deferred'


def test_earlier_explicit_sendout_supports_weaker_hud_without_backfill():
    engine=StateEngine(BattleState('test'))
    r=engine.apply(message(1,5,'上吧！钢铠鸦！'),sequence=1)
    assert r.application_status=='deferred' and not engine.state.pokemon
    r=engine.apply(hud(2,11,823,mon=species(823,.86)),sequence=2)
    assert r.bindings['hud']['status']=='accepted'
    assert r.bindings['hud']['corroboration']['timestamp']==5
    engine.retract('msg:1',reason='announcement was corrupted')
    assert not engine.state.pokemon


def test_stale_or_future_sendout_cannot_corroborate_weak_hud():
    engine=StateEngine(BattleState('test'))
    engine.apply(message(1,5,'上吧！钢铠鸦！'),sequence=1)
    r=engine.apply(hud(2,40,823,mon=species(823,.86)),sequence=2)
    assert r.bindings['hud']['status']=='deferred'


def test_selected_move_does_not_become_revealed_execution():
    engine=StateEngine(BattleState('test'));engine.apply(hud(1,10,823),sequence=1)
    event=message(2,12,'钢铠鸦使出了守住！');event.attributes['effect_outcome']='selected'
    assert engine.apply(event,sequence=2).application_status=='deferred'
    assert not active(engine).moves.executed


def test_endpoint_comparison_accounts_for_later_faint():
    from scripts.replay_m233a import replay, metrics
    first=hud(1,10,823).to_dict();first['attributes']['sequence']=1
    faint=message(2,12,'钢铠鸦倒下了！').to_dict();faint['attributes']['sequence']=2
    state,hidden,timeline=replay([first,faint],'test')
    comparison=metrics(state,hidden,timeline)['endpoint_identity_comparisons'][0]
    assert comparison['match'] is True and comparison['replayed_species']==823
    assert comparison['final_species'] is None
    assert comparison['later_accepted_vacancy_events']==['msg:2']
