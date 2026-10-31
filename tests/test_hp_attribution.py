"""Causal receipts enrich numeric observations without predicting HP."""
from copy import deepcopy
import pytest
from tracking.state_engine import StateEngine
from tracking.battle_state import BattleState
from tests.test_evidence_fusion import hud, active
from tests.test_semantic_state import deliver


def seed():
    e=StateEngine(BattleState('test'))
    e.apply(hud(1,1,823,hp=dict(current=100,maximum=173)),sequence=1)
    e.apply(hud(2,1.5,373,side='opponent',hp=100),sequence=2)
    return e


def endpoint(e,n,value,side='self',sid=823,slot='right'):
    e.apply(hud(n,n,sid,side=side,slot=slot,hp=dict(current=value,maximum=173) if side=='self' else value),sequence=n*10)
    return active(e,slot=slot,side=side).hp.observations[-1]


@pytest.mark.parametrize('text,kind,after',[
 ('钢铠鸦受到了灼伤的伤害！','status',90),
 ('钢铠鸦受到了毒的伤害！','status',90),
 ('钢铠鸦受到了沙暴的伤害！','weather',90),
 ('钢铠鸦受到了隐形岩的伤害！','entry_hazard',90),
 ('钢铠鸦因钢铠鸦的生命宝珠受到了伤害！','item',90),
 ('钢铠鸦因对手的暴飞龙的凸凸头盔受到了伤害！','item',90),
 ('钢铠鸦因对手的暴飞龙的粗糙皮肤受到了伤害！','ability',90),
 ('钢铠鸦因钢铠鸦的吃剩的东西回复了体力！','item',110),
 ('钢铠鸦因钢铠鸦的毒疗回复了体力！','ability',110),
 ('钢铠鸦的灭亡之歌倒数变成了0！','instant_faint',0),
])
def test_literal_effect_numeric_pair(text,kind,after):
    e=seed();deliver(e,text,2);o=endpoint(e,3,after)
    assert o['attribution_status']=='supported' and o['cause']['kind']==kind
    assert o['delta']==after-100
    e.retract(o['cause_event_ids'][0],reason='bad effect')
    assert active(e).hp.observations[-1]['cause'] is None


@pytest.mark.parametrize('move,notice,kind',[
 ('闪焰冲锋','因闪焰冲锋受到了反作用力造成的伤害','move_recoil'),
 ('腹鼓','因腹鼓削减了自己的HP','self_hp_cost')])
def test_self_action_is_not_competing_with_its_explicit_cost(move,notice,kind):
    e=seed();deliver(e,'钢铠鸦使出了'+move+'！',2);deliver(e,'钢铠鸦'+notice+'！',3)
    o=endpoint(e,4,80)
    assert o['cause']['kind']==kind and o['source_instance_id']==active(e).pokemon_instance_id


def test_late_named_target_backfills_animation_segments_and_retraction():
    e=seed();deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    assert endpoint(e,3,80)['cause'] is None
    endpoint(e,4,50)
    d,_=deliver(e,'对钢铠鸦效果绝佳！',5)
    changes=[o for o in active(e).hp.observations if o.get('delta')]
    assert len(changes)==2 and all(o['attribution_status']=='supported' for o in changes)
    assert all(o['cause']['source']['name']=='喷射火焰' for o in changes)
    serialized=e.to_dict();again=StateEngine.from_dict(serialized)
    assert again.to_dict()['state']==serialized['state']
    eid=d['events'][0]['event_id']
    e.retract(eid,reason='wrong receiver')
    assert all(o['cause'] is None for o in active(e).hp.observations if o.get('delta'))
    replacement=deepcopy(d['events'][0]);replacement['attributes']['effect']='immune'
    e.correct(eid,replacement,sequence=50,reason='correct outcome')
    assert all(o['cause'] is None for o in active(e).hp.observations if o.get('delta'))


def test_spread_requires_separate_named_recipient_evidence():
    e=seed();e.apply(hud(10,1.6,530,slot='left',hp=dict(current=100,maximum=173)),sequence=3)
    deliver(e,'对手的暴飞龙使出了岩崩！',2)
    endpoint(e,3,80);endpoint(e,4,60,sid=530,slot='left')
    deliver(e,'对钢铠鸦效果绝佳！',5)
    assert active(e).hp.observations[-1]['cause']['kind']=='move'
    assert active(e,slot='left').hp.observations[-1]['cause'] is None
    deliver(e,'对龙头地鼠效果不好！',6)
    assert active(e,slot='left').hp.observations[-1]['cause']['kind']=='move'


def test_explicit_named_move_healing_after_its_action():
    e=seed();deliver(e,'钢铠鸦使出了羽栖！',2);deliver(e,'钢铠鸦因钢铠鸦的羽栖回复了体力！',3)
    assert endpoint(e,4,120)['cause']['source']['name']=='羽栖'


def test_opponent_points_and_zero_do_not_create_absolute_hp():
    e=seed();deliver(e,'钢铠鸦使出了喷射火焰！',2)
    endpoint(e,3,0,side='opponent',sid=373)
    deliver(e,'对对手的暴飞龙效果绝佳！',4)
    o=active(e,side='opponent').hp.observations[-1]
    assert o['cause']['kind']=='move' and o['delta']==-100 and o['unit']=='displayed_percent'
    assert not active(e,side='opponent').hp.current.known
    deliver(e,'对手的暴飞龙倒下了！',5)
    assert e.state.pokemon[o['affected_instance_id']].hp.observations[-1]['after']==0


@pytest.mark.parametrize('intervening',[
 '钢铠鸦受到了灼伤的伤害！','钢铠鸦的生命宝珠！','钢铠鸦使出了勇鸟猛攻！'])
def test_competition_abstains(intervening):
    e=seed();deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    deliver(e,'对钢铠鸦效果绝佳！',3);deliver(e,intervening,4)
    o=endpoint(e,5,60)
    assert o['cause'] is None and o['candidate_causes']


def test_unreadable_and_time_tie_abstain():
    e=seed();deliver(e,'钢铠鸦受到了灼伤的伤害！',2)
    e.apply(hud(30,2.5,823),sequence=25)
    assert endpoint(e,3,90)['cause'] is None
    e=seed();deliver(e,'钢铠鸦受到了灼伤的伤害！',2)
    e.apply(hud(30,1,823,hp=dict(current=90,maximum=173)),sequence=30)
    assert not any(o.get('attribution_status')=='supported' for o in active(e).hp.observations)


def test_ambiguous_order_cannot_supply_endpoint_or_cause():
    e=seed();d,_=deliver(e,'钢铠鸦受到了灼伤的伤害！',2)
    e.apply(hud(30,3,823,hp=dict(current=90,maximum=173)),sequence=20)
    assert active(e).hp.current.value==100


def test_late_target_cannot_bridge_effect_or_coverage_gap():
    e=seed();deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    endpoint(e,3,80)
    deliver(e,'钢铠鸦的生命宝珠！',4)
    deliver(e,'对钢铠鸦效果绝佳！',5)
    assert active(e).hp.observations[-1]['cause'] is None


def test_status_active_is_not_residual_occurrence():
    e=seed();deliver(e,'钢铠鸦灼伤了！',2)
    assert endpoint(e,3,90)['cause'] is None


def test_new_encounter_does_not_inherit_old_target_link():
    e=seed();deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    deliver(e,'对钢铠鸦效果绝佳！',3)
    e.apply(hud(40,4,530,hp=dict(current=100,maximum=173)),sequence=40)
    o=endpoint(e,5,80,sid=530)
    assert o['cause'] is None


def test_mismatched_healing_notice_does_not_prove_damage():
    e=seed();deliver(e,'钢铠鸦使出了羽栖！',2);deliver(e,'钢铠鸦体力回复了！',3)
    assert endpoint(e,4,90)['cause'] is None


def test_explicit_item_holder_must_have_unique_instance():
    e=seed()
    e.apply(hud(10,1.6,373,slot='left',side='opponent',hp=100),sequence=3)
    deliver(e,'钢铠鸦因对手的暴飞龙的凸凸头盔受到了伤害！',2)
    o=endpoint(e,3,80)
    assert o['cause'] is None and 'source_holder_instance_unresolved' in o['attribution_reasons']


def test_multiple_action_candidates_are_preserved():
    e=seed();deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    deliver(e,'对钢铠鸦效果绝佳！',3)
    deliver(e,'对手的暴飞龙使出了岩崩！',4)
    deliver(e,'对钢铠鸦效果绝佳！',5)
    o=endpoint(e,6,60)
    assert o['cause'] is None
    assert {c['cause']['source']['name'] for c in o['candidate_causes']}=={'岩崩','喷射火焰'}


def test_protected_recipient_cannot_supply_numeric_damage_label():
    e=seed();deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    deliver(e,'钢铠鸦在攻击中守护住了自己！',3)
    endpoint(e,4,80);deliver(e,'对钢铠鸦效果绝佳！',5)
    assert active(e).hp.observations[-1]['cause'] is None


@pytest.mark.parametrize('notice,values',[
 ('钢铠鸦受到了灼伤的伤害！',[100,93,90]),
 ('钢铠鸦因钢铠鸦的吃剩的东西回复了体力！',[100,105,110]),
])
def test_effect_announcement_precedes_both_animation_endpoints(notice,values):
    e=seed();deliver(e,notice,2)
    for n,value in enumerate(values,3):endpoint(e,n,value)
    changes=[o for o in active(e).hp.observations if o.get('delta')]
    assert len(changes)==2 and all(o['attribution_status']=='supported' for o in changes)


def test_effect_window_ends_at_next_action():
    e=seed();deliver(e,'钢铠鸦受到了灼伤的伤害！',2)
    endpoint(e,3,100);deliver(e,'对手的暴飞龙使出了岩崩！',4)
    assert endpoint(e,5,90)['cause'] is None


def test_coverage_gap_between_move_and_target_requires_abstention():
    e=seed();e.initial.knowledge['reliability_v1']=True
    deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    gap=hud(50,2.5,823)
    gap.event_type='coverage_observation'
    gap.attributes=dict(battle_id='test',start=2.1,observation_time=2.5,status='gap',fields=['hp'])
    e.apply(gap,sequence=25)
    endpoint(e,3,80);deliver(e,'对钢铠鸦效果绝佳！',4)
    assert active(e).hp.observations[-1]['cause'] is None
    assert 'identity_or_coverage_gap' in active(e).hp.observations[-1]['attribution_reasons']


def test_recoil_and_item_in_one_endpoint_interval_remain_separate_candidates():
    e=seed();deliver(e,'钢铠鸦因闪焰冲锋受到了反作用力造成的伤害！',2)
    deliver(e,'钢铠鸦因钢铠鸦的生命宝珠受到了伤害！',3)
    o=endpoint(e,4,70)
    assert o['cause'] is None and o['attribution_status']=='ambiguous'
    assert {c['cause']['kind'] for c in o['candidate_causes']}=={'move_recoil','item'}


def test_generic_healing_alone_cannot_identify_its_source():
    e=seed();deliver(e,'钢铠鸦使出了羽栖！',2);deliver(e,'钢铠鸦体力回复了！',3)
    assert endpoint(e,4,120)['cause'] is None


def test_replay_audit_preserves_numeric_and_qualitative_semantics():
    from scripts.evaluate_hp_attribution import behavior
    original=dict(knowledge=dict(historical_hp=dict(observations=[
        dict(unit='absolute',after=90,evidence=dict(event_id='hp'),cause=None)])),
        observations=[dict(cause=dict(kind='status',status='burn'))])
    enriched=deepcopy(original)
    enriched['knowledge']['historical_hp']['observations'][0].update(
        attribution_status='supported',cause=dict(kind='status',status='burn'))
    assert behavior(original)==behavior(enriched)
    enriched['knowledge']['historical_hp']['observations'][0]['after']=80
    assert behavior(original)!=behavior(enriched)
    enriched=deepcopy(original);enriched['observations'][0]['cause']['status']='poison'
    assert behavior(original)!=behavior(enriched)
