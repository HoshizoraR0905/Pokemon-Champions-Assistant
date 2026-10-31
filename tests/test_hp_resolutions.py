"""Action/target resolution contracts; synthetic hits are not video accuracy."""
from copy import deepcopy
import pytest
from tracking.state_engine import hash_state
from tracking.hp_causes import resolve_hits
from tests.test_hp_attribution import seed, endpoint
from tests.test_semantic_state import deliver
from tests.test_evidence_fusion import active,hud

SINGLE=dict(verification='champions_verified',hit_range=[1,1],sources=[dict(kind='synthetic_test_contract')])
MULTI=dict(verification='champions_verified',hit_range=[2,5],sources=[dict(kind='synthetic_test_contract')])


def close(e,n=10):deliver(e,'对手的暴飞龙使出了守住！',n)


def one(e):
    values=e.hp_resolutions()['episodes']
    assert len(values)==1
    return values[0]


def test_normal_action_uses_pre_move_and_last_plateau_not_animation_segments():
    e=seed();deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    endpoint(e,3,95);endpoint(e,4,80);endpoint(e,5,80)
    # Temporary stop during one animation must not close the action.
    endpoint(e,6,70);deliver(e,'对钢铠鸦效果绝佳！',7)
    endpoint(e,8,70);close(e)
    before=hash_state(e.state);o=one(e)
    assert hash_state(e.state)==before
    assert (o['before'],o['after'],o['delta'])==(100,70,-30)
    assert o['attribution_status']=='supported' and len(o['segment_event_ids'])==3
    assert o['source_move']['name']=='喷射火焰'
    assert o['actor_instance_id']!=o['target_instance_id']
    assert o['critical_hit'] is None


def test_critical_and_effectiveness_stay_in_same_action_and_retract_cleanly():
    e=seed();deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    endpoint(e,3,80);crit,records=deliver(e,'击中了要害！',4)
    assert records[0].application_status=='recorded_observation'
    deliver(e,'对钢铠鸦效果绝佳！',5);endpoint(e,6,80);endpoint(e,7,80);close(e)
    o=e.hp_resolutions(mechanics={'pokeapi:move:53':SINGLE})['episodes'][0]
    assert o['delta']==-20 and o['critical_hit'] is True
    assert o['hit_resolution']['hits'][0]['critical_hit'] is True
    eid=crit['events'][0]['event_id'];e.retract(eid,reason='bad critical reading')
    assert one(e)['critical_hit'] is None
    replacement=deepcopy(crit['events'][0]);replacement['event_type']='multi_hit';replacement['attributes']['hits']=1;replacement['original_text']='击中了1次！'
    e.correct(eid,replacement,sequence=40,reason='correct notice')
    assert one(e)['hit_resolution']['hit_count']==1 and one(e)['critical_hit'] is None


def test_spread_has_distinct_targets_and_bare_critical_is_not_copied_to_both():
    e=seed();e.apply(hud(99,1.7,530,slot='left',hp=dict(current=100,maximum=173)),sequence=3)
    deliver(e,'对手的暴飞龙使出了岩崩！',2)
    endpoint(e,3,80);endpoint(e,4,70,sid=530,slot='left')
    deliver(e,'对钢铠鸦效果绝佳！',5);deliver(e,'对龙头地鼠效果不好！',6)
    deliver(e,'击中了要害！',7)
    endpoint(e,8,80);endpoint(e,9,70,sid=530,slot='left')
    endpoint(e,10,80);endpoint(e,11,70,sid=530,slot='left');close(e,12)
    out=e.hp_resolutions();assert len(out['episodes'])==2
    assert sorted(o['delta'] for o in out['episodes'])==[-30,-20]
    assert all(o['critical_hit'] is None and o['attribution_status']=='supported' for o in out['episodes'])
    assert len(out['actions'][0]['target_instance_ids'])==2


@pytest.mark.parametrize('notice,kind',[
 ('钢铠鸦因闪焰冲锋受到了反作用力造成的伤害！','move_recoil'),
 ('钢铠鸦因对手的暴飞龙的凸凸头盔受到了伤害！','item'),
 ('钢铠鸦因对手的暴飞龙的粗糙皮肤受到了伤害！','ability')])
def test_secondary_damage_is_a_separate_resolution(notice,kind):
    e=seed();deliver(e,'钢铠鸦使出了闪焰冲锋！',2)
    endpoint(e,3,80,side='opponent',sid=373);endpoint(e,4,80,side='opponent',sid=373)
    deliver(e,'对对手的暴飞龙效果不好！',5)
    deliver(e,notice,6);endpoint(e,7,90);endpoint(e,8,90);close(e)
    episodes=e.hp_resolutions()['episodes'];assert len(episodes)==2
    assert episodes[0]['delta']==-20 and episodes[1]['delta']==-10
    assert episodes[0]['cause']['kind']=='move' and episodes[1]['cause']['kind']==kind
    assert episodes[0]['affected_instance_id']!=episodes[1]['affected_instance_id']


def test_residual_and_healing_are_separate_from_move_damage():
    e=seed();deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    endpoint(e,3,80);endpoint(e,4,80);deliver(e,'对钢铠鸦效果绝佳！',5)
    deliver(e,'钢铠鸦受到了灼伤的伤害！',6);endpoint(e,7,70);endpoint(e,8,70)
    deliver(e,'钢铠鸦因钢铠鸦的吃剩的东西回复了体力！',9)
    endpoint(e,10,75);endpoint(e,11,75);close(e,12)
    episodes=e.hp_resolutions()['episodes']
    assert [o['delta'] for o in episodes]==[-20,-10,5]
    assert all(o['attribution_status']=='supported' for o in episodes)


def test_missing_pre_move_hp_does_not_turn_partial_observations_into_total():
    e=seed();e.retract('hud:1',reason='no reliable own pre-action reading')
    deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    endpoint(e,3,80);endpoint(e,4,60);endpoint(e,5,60)
    deliver(e,'对钢铠鸦效果绝佳！',6);close(e)
    o=one(e);assert o['before'] is None and o['delta'] is None
    assert o['observed_partial_before']==80 and o['observed_partial_after']==60
    assert 'pre_action_hp_missing' in o['reasons']


def test_last_single_visible_value_is_not_proven_final_stable_hp():
    e=seed();deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    endpoint(e,3,70);deliver(e,'对钢铠鸦效果绝佳！',4);close(e)
    o=one(e);assert o['after']==70 and o['delta'] is None
    assert 'final_visible_plateau_unresolved' in o['reasons']


def test_observed_zero_then_faint_closes_endpoint_without_synthesizing_hp():
    e=seed();deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    endpoint(e,3,0);deliver(e,'对钢铠鸦效果绝佳！',4);deliver(e,'钢铠鸦倒下了！',5)
    o=one(e);assert o['delta']==-100 and o['final_endpoint_basis']=='observed_zero_then_faint'


def test_bound_hp_change_identifies_target_without_named_message():
    e=seed();deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    endpoint(e,3,80);endpoint(e,4,80);close(e)
    assert one(e)['cause']['kind']=='move' and one(e)['attribution_status']=='supported'
    d,_=deliver(e,'对钢铠鸦效果绝佳！',5)
    assert one(e)['cause']['kind']=='move'
    e.retract(d['events'][0]['event_id'],reason='named notice incorrect; independent HUD binding remains')
    assert one(e)['cause']['kind']=='move'


def samples(values):
    return [dict(time=i*.2,event_id=f'dense:{i}',value=v) for i,v in enumerate(values)]


def test_dense_plateaus_with_independent_count_resolve_hits_and_scoped_critical():
    seq=samples([100,97,94,91,91,91,85,79,73,73,73])
    out=resolve_hits(seq,sampling_fps=5,capability=MULTI,hit_count=2,
                     critical_events=[dict(event_id='crit:2',hit_index=2)])
    assert out['per_hit_damage']==[9,18]
    assert out['hits'][0]['critical_hit'] is None and out['hits'][1]['critical_hit'] is True
    assert sum(out['per_hit_damage'])==27


def test_plateaus_alone_never_establish_hit_count_or_per_hit_damage():
    seq=samples([100,97,94,91,91,91,85,79,73,73,73])
    assert resolve_hits(seq,sampling_fps=5)['hits'] is None
    out=resolve_hits(seq,sampling_fps=5,capability=MULTI)
    assert len(out['hit_candidates'])==2 and out['per_hit_damage'] is None and out['hit_count'] is None


def test_one_animation_with_brief_pause_remains_one_hit():
    out=resolve_hits(samples([100,97,94,91,91,85,79,73,73,73]),sampling_fps=5,capability=SINGLE)
    assert out['per_hit_damage']==[27]


def test_distinct_hits_without_visible_plateau_keep_total_and_unknown_hit_amounts():
    out=resolve_hits(samples([100,97,94,91,85,79,73,73,73]),sampling_fps=5,capability=MULTI,hit_count=2)
    assert out['per_hit_damage'] is None and out['hit_count']==2
    assert 'independent_hit_count_and_boundaries_not_both_resolved' in out['reasons']


def test_low_sampling_and_gaps_abstain_even_with_known_hit_count():
    seq=samples([100,91,91,91,73,73,73])
    assert resolve_hits(seq,sampling_fps=2,capability=MULTI,hit_count=2)['hits'] is None
    seq[3]['time']+=.1
    assert resolve_hits(seq,sampling_fps=5,capability=MULTI,hit_count=2)['hits'] is None


def test_unscoped_multi_hit_count_parses_but_does_not_guess_a_target():
    e=seed();deliver(e,'对手的暴飞龙使出了种子机关枪！',2)
    endpoint(e,3,73);endpoint(e,4,73)
    deliver(e,'对钢铠鸦效果不好！',5)
    _,r=deliver(e,'击中了2次！',6);close(e)
    assert r[0].application_status=='recorded_observation'
    o=one(e);assert o['delta']==-27
    assert o['hit_resolution']['hit_count']==2 and o['hit_resolution']['per_hit_damage'] is None


def test_literal_residual_wrong_direction_is_not_attributed():
    e=seed();deliver(e,'钢铠鸦受到了灼伤的伤害！',2)
    endpoint(e,3,110);endpoint(e,4,110);close(e)
    o=one(e);assert o['cause'] is None and 'literal_effect_direction_conflict' in o['reasons']


def test_multi_hit_planning_seeks_back_before_trigger_without_changing_default_sampling():
    from recognition.resolution_sampling import dense_plans
    e=seed();deliver(e,'对手的暴飞龙使出了种子机关枪！',2)
    endpoint(e,3,73);endpoint(e,4,73);deliver(e,'对钢铠鸦效果不好！',5);close(e)
    plan=dense_plans(e,sample_fps=7)[0]
    assert plan['sample_fps']==7 and plan['start']==1 and plan['trigger_time']==2
    assert plan['mechanics']['verification']=='simulator_reference_only'
    assert plan['target_instance_ids']==[active(e).pokemon_instance_id]
    with pytest.raises(ValueError):dense_plans(e,sample_fps=2)


def test_multi_hit_dense_data_connects_to_episode_and_sparse_failures_keep_total():
    e=seed();deliver(e,'对手的暴飞龙使出了种子机关枪！',2)
    endpoint(e,3,91);endpoint(e,4,73);endpoint(e,5,73)
    deliver(e,'对钢铠鸦效果不好！',6);deliver(e,'击中了2次！',7);close(e)
    o=one(e);pid=active(e).pokemon_instance_id
    seq=[dict(s,time=2+s['time'],pokemon_instance_id=pid,unit='absolute',maximum=173,confidence=.99,evidence={'fixture':s['event_id']})
         for s in samples([100,97,94,91,91,91,85,79,73,73,73])]
    dense={o['episode_id']:dict(sample_fps=5,samples=seq)}
    out=e.hp_resolutions(dense_samples=dense)['episodes'][0]
    assert out['delta']==-27 and out['hit_resolution']['per_hit_damage']==[9,18]
    # An incomplete or misbound dense pass cannot turn partial damage into a
    # fake hit or destroy the independently supported ordinary action total.
    dense[o['episode_id']]['samples']=seq[1:]
    out=e.hp_resolutions(dense_samples=dense)['episodes'][0]
    assert out['delta']==-27 and out['hit_resolution']['per_hit_damage'] is None


def test_action_projection_round_trip_does_not_change_state_and_revision_rebuilds_totals():
    from tracking.state_engine import StateEngine
    e=seed();deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    endpoint(e,3,80);endpoint(e,4,80);deliver(e,'对钢铠鸦效果绝佳！',5);close(e)
    before=e.to_dict();out=e.hp_resolutions()
    assert e.to_dict()==before
    assert StateEngine.from_dict(before).hp_resolutions()==out
    e.retract('hud:3',reason='bad intermediate endpoint')
    # Last 80 has only one visible observation after revision: stable final HP
    # must be established again, rather than trusting the old episode object.
    assert one(e)['delta'] is None


def test_bare_critical_cannot_choose_between_named_and_unresolved_spread_recipient():
    e=seed();e.apply(hud(99,1.7,530,slot='left',hp=dict(current=100,maximum=173)),sequence=3)
    deliver(e,'对手的暴飞龙使出了岩崩！',2)
    endpoint(e,3,80);endpoint(e,4,70,sid=530,slot='left')
    deliver(e,'对钢铠鸦效果绝佳！',5);deliver(e,'命中了要害！',6)
    endpoint(e,7,80);endpoint(e,8,70,sid=530,slot='left');close(e)
    assert all(o['critical_hit'] is None for o in e.hp_resolutions()['episodes'])


def test_intervening_effect_cannot_finish_unsettled_move_or_merge_the_amounts():
    e=seed();deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    endpoint(e,3,80);deliver(e,'对钢铠鸦效果绝佳！',4)
    deliver(e,'钢铠鸦受到了灼伤的伤害！',5)
    endpoint(e,6,70);endpoint(e,7,70);close(e)
    episodes=e.hp_resolutions()['episodes']
    assert len(episodes)==2 and episodes[0]['delta'] is None
    assert episodes[1]['delta']==-10
    assert 'final_visible_plateau_unresolved' in episodes[0]['reasons']


def test_distant_or_unreadable_observations_do_not_prove_a_stable_plateau():
    e=seed();deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    endpoint(e,3,80);endpoint(e,40,80);deliver(e,'对钢铠鸦效果绝佳！',41);close(e,50)
    assert 'final_visible_plateau_unresolved' in one(e)['reasons']
    e=seed();deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    endpoint(e,3,80);e.apply(hud(99,4,823),sequence=40)
    endpoint(e,5,80);deliver(e,'对钢铠鸦效果绝佳！',6);close(e)
    assert 'final_visible_plateau_unresolved' in one(e)['reasons']


def test_between_hit_damage_to_user_does_not_terminate_target_multi_hit_total():
    e=seed();deliver(e,'钢铠鸦使出了种子机关枪！',2)
    endpoint(e,3,91,side='opponent',sid=373);endpoint(e,4,91,side='opponent',sid=373)
    deliver(e,'钢铠鸦因对手的暴飞龙的凸凸头盔受到了伤害！',5)
    endpoint(e,6,90);endpoint(e,7,90)
    endpoint(e,8,73,side='opponent',sid=373);endpoint(e,9,73,side='opponent',sid=373)
    deliver(e,'对对手的暴飞龙效果不好！',10);deliver(e,'击中了2次！',11);close(e,12)
    episodes=e.hp_resolutions()['episodes']
    attack=next(o for o in episodes if o['source_move'])
    helmet=next(o for o in episodes if not o['source_move'])
    assert attack['delta']==-27 and attack['attribution_status']=='supported'
    assert helmet['delta']==-10 and helmet['cause']['kind']=='item'
    assert attack['hit_resolution']['per_hit_damage'] is None


def test_same_target_effect_between_hits_leaves_total_components_ambiguous():
    e=seed();deliver(e,'钢铠鸦使出了种子机关枪！',2)
    endpoint(e,3,91,side='opponent',sid=373);endpoint(e,4,91,side='opponent',sid=373)
    deliver(e,'对手的暴飞龙因对手的暴飞龙的生命宝珠受到了伤害！',5)
    endpoint(e,6,81,side='opponent',sid=373);endpoint(e,7,73,side='opponent',sid=373)
    endpoint(e,8,73,side='opponent',sid=373)
    deliver(e,'对对手的暴飞龙效果不好！',9);deliver(e,'击中了2次！',10);close(e,11)
    episodes=e.hp_resolutions()['episodes']
    assert len(episodes)==2
    assert episodes[0]['delta'] is None and 'multi_hit_interrupted_by_same_target_effect' in episodes[0]['reasons']
    assert episodes[1]['cause'] is None


def test_between_hit_item_banner_and_explicit_effect_bind_holder_and_recipient_separately():
    e=seed();deliver(e,'钢铠鸦使出了种子机关枪！',2)
    endpoint(e,3,91,side='opponent',sid=373);endpoint(e,4,91,side='opponent',sid=373)
    deliver(e,'对手的暴飞龙的凸凸头盔！',5)
    deliver(e,'钢铠鸦因对手的暴飞龙的凸凸头盔受到了伤害！',6)
    endpoint(e,7,90);endpoint(e,8,90)
    endpoint(e,9,73,side='opponent',sid=373);endpoint(e,10,73,side='opponent',sid=373)
    deliver(e,'对对手的暴飞龙效果不好！',11);deliver(e,'击中了2次！',12);close(e,13)
    episodes=e.hp_resolutions()['episodes']
    assert len(episodes)==2
    assert episodes[0]['delta']==-27 and episodes[1]['delta']==-10
    assert episodes[1]['actor_instance_id']==episodes[0]['target_instance_id']
    assert episodes[1]['target_instance_id']==episodes[0]['actor_instance_id']
