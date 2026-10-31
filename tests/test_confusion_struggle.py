"""Literal confusion/Struggle → existing state and HP projection, no damage formula."""
from copy import deepcopy
import pytest
from tests.test_evidence_fusion import active,hud
from tests.test_hp_attribution import seed,endpoint
from tests.test_semantic_state import deliver
from tracking.state_engine import StateEngine,hash_state
from tracking.battle_state import BattleState


def close(e,n=12):deliver(e,'对手的暴飞龙使出了守住！',n)


@pytest.mark.parametrize('prefix,side',[('','self'),('对手的','opponent')])
def test_confusion_lifecycle_is_volatile_observed_and_retractable(prefix,side):
    e=seed();name='钢铠鸦' if side=='self' else '暴飞龙'
    for t,suffix,change,value in [(2,'混乱了！','start',True),(3,'正在混乱中！','observe',True),
                                  (4,'混乱解除了！','end',False)]:
        d,r=deliver(e,prefix+name+'\n'+suffix,t)
        assert d['events'][0]['attributes']['change']==change
        assert r[0].application_status=='applied_candidate'
        condition=active(e,side=side).volatile['confusion']
        assert condition.active.value is value
        if value:assert not condition.duration.remaining.known
    assert not active(e,side=side).major_status.known
    e.retract(d['events'][0]['event_id'],reason='incorrect end notice')
    assert active(e,side=side).volatile['confusion'].active.value is True
    assert active(e,side=side).hp.observations[0]['after']==100


@pytest.mark.parametrize('preceding',['喷射火焰','羽栖'])
def test_confusion_self_hit_is_own_damage_never_the_previous_move(preceding):
    e=seed();deliver(e,'钢铠鸦混乱了！',2)
    deliver(e,'对手的暴飞龙使出了'+preceding+'！',3)
    endpoint(e,4,100)
    deliver(e,'钢铠鸦正在混乱中！',5)
    d,r=deliver(e,'不知所以地攻击了自己！',6)
    assert r[0].application_status=='recorded_observation'
    obs=endpoint(e,7,90);endpoint(e,8,90);close(e)
    pid=active(e).pokemon_instance_id
    assert obs['cause']['kind']=='confusion_self_damage' and obs['source_instance_id']==pid
    out=e.hp_resolutions();o=out['episodes'][0]
    assert o['cause']['kind']=='confusion_self_damage' and o['delta']==-10
    assert o['actor_instance_id']==o['affected_instance_id']==pid
    assert o['parent_action_id'] is None and o['source_move'] is None
    assert all(c['cause']['kind']!='move' for c in o['candidate_causes'])
    e.retract(d['events'][0]['event_id'],reason='bad self-hit reading')
    assert all(o.get('cause',{}).get('kind')!='confusion_self_damage' for o in active(e).hp.observations if o.get('cause'))


def test_bare_self_hit_cannot_reuse_context_after_an_independent_move():
    e=seed();deliver(e,'钢铠鸦正在混乱中！',2)
    deliver(e,'对手的暴飞龙使出了喷射火焰！',3)
    _,records=deliver(e,'不知所以地攻击了自己！',4)
    assert records[0].application_status=='deferred'
    assert 'actor' not in records[0].bindings


def test_missing_confusion_final_hp_remains_unknown():
    e=seed();deliver(e,'钢铠鸦正在混乱中！',2)
    deliver(e,'不知所以地攻击了自己！',3)
    assert active(e).hp.current.value==100
    notice=active(e).hp.observations[-1]
    assert notice['before'] is None and notice['after'] is None
    assert notice['cause']['kind']=='confusion_self_damage'
    close(e);assert e.hp_resolutions()['episodes']==[]


def struggle_seed():
    e=StateEngine(BattleState('test'))
    e.apply(hud(1,1,823,hp=dict(current=200,maximum=200)),sequence=1)
    e.apply(hud(2,1.5,373,side='opponent',hp=100),sequence=2)
    return e


def own(e,t,value):
    e.apply(hud(1000+t,t,823,hp=dict(current=value,maximum=200)),sequence=t*10)


@pytest.mark.parametrize('target_after',[80,40])
def test_struggle_observed_target_loss_and_separate_max_hp_recoil(target_after):
    e=struggle_seed();d,r=deliver(e,'钢铠鸦使出了挣扎！',2)
    assert d['events'][0]['canonical_references']['move']['canonical_id']=='pokeapi:move:165'
    assert r[0].application_status=='applied_partial'
    endpoint(e,3,target_after,side='opponent',sid=373);endpoint(e,4,target_after,side='opponent',sid=373)
    own(e,5,150);own(e,6,150);close(e)
    before=hash_state(e.state);episodes=e.hp_resolutions()['episodes'];assert hash_state(e.state)==before
    assert len(episodes)==2
    target=next(o for o in episodes if o['cause']['kind']=='move')
    recoil=next(o for o in episodes if o['cause']['kind']=='struggle_recoil')
    assert target['delta']==target_after-100 and recoil['delta']==-50
    assert target['affected_instance_id']!=recoil['affected_instance_id']
    assert recoil['actor_instance_id']==recoil['affected_instance_id']==active(e).pokemon_instance_id
    assert recoil['effect_semantics']['recoil']['fraction']==[1,4]
    assert recoil['effect_semantics']['recoil']['basis']=='user_maximum_hp'
    assert recoil['source_move'] is None and recoil['parent_move']['canonical_id']=='pokeapi:move:165'
    assert all(o['attribution_status']=='supported' for o in episodes)
    assert next(o for o in reversed(active(e).hp.observations) if o.get('delta'))['cause']['kind']=='struggle_recoil'
    assert not active(e).volatile.get('confusion')


@pytest.mark.parametrize('notice',['钢铠鸦因挣扎受到了反作用力造成的伤害！',
                                  '钢铠鸦受到了反作用力造成的伤害！','受到了反作用力造成的伤害！'])
def test_struggle_recoil_notice_is_not_confusion(notice):
    e=struggle_seed();deliver(e,'钢铠鸦使出了挣扎！',2)
    endpoint(e,3,80,side='opponent',sid=373);endpoint(e,4,80,side='opponent',sid=373)
    _,r=deliver(e,notice,5);assert r[0].application_status=='recorded_observation'
    own(e,6,150);own(e,7,150);close(e)
    o=e.hp_resolutions()['episodes'][-1]
    assert o['cause']['kind']=='struggle_recoil' and o['delta']==-50
    assert next(o for o in reversed(active(e).hp.observations) if o.get('delta'))['cause']['kind']=='struggle_recoil'


def test_struggle_missing_user_hp_or_target_hp_never_generates_damage():
    e=struggle_seed();deliver(e,'钢铠鸦使出了挣扎！',2)
    endpoint(e,3,80,side='opponent',sid=373);endpoint(e,4,80,side='opponent',sid=373)
    deliver(e,'受到了反作用力造成的伤害！',5);close(e)
    assert active(e).hp.current.value==200
    episodes=e.hp_resolutions()['episodes'];assert len(episodes)==1 and episodes[0]['cause']['kind']=='move'
    e=struggle_seed();deliver(e,'钢铠鸦使出了挣扎！',2);own(e,3,150);own(e,4,150);close(e)
    episodes=e.hp_resolutions()['episodes']
    assert all(o['cause'] is None for o in episodes) # execution alone does not prove success/recoil
    assert all(o['affected_instance_id']==active(e).pokemon_instance_id for o in episodes)


def test_unknown_pp_never_creates_struggle_and_single_hp_sample_is_not_final():
    e=struggle_seed();assert active(e).moves.pp=={} and active(e).moves.executed==[]
    own(e,2,150);assert not e.hp_resolutions()['actions']
    e=struggle_seed();deliver(e,'钢铠鸦使出了挣扎！',2)
    endpoint(e,3,80,side='opponent',sid=373);own(e,4,150);close(e,8)
    assert all(o['delta'] is None for o in e.hp_resolutions()['episodes'])


@pytest.mark.parametrize('ending',['从混乱中恢复了！','不再混乱了！'])
def test_explicit_confusion_end_variants(ending):
    e=seed();deliver(e,'钢铠鸦混乱了！',2);deliver(e,'钢铠鸦'+ending,3)
    assert active(e).volatile['confusion'].active.value is False


def test_active_confusion_does_not_turn_struggle_recoil_into_confusion_damage():
    e=struggle_seed();deliver(e,'钢铠鸦混乱了！',2)
    deliver(e,'钢铠鸦使出了Struggle！',3)
    endpoint(e,4,80,side='opponent',sid=373);endpoint(e,5,80,side='opponent',sid=373)
    own(e,6,150);own(e,7,150);close(e)
    assert active(e).volatile['confusion'].active.value is True
    assert {o['cause']['kind'] for o in e.hp_resolutions()['episodes']}=={'move','struggle_recoil'}


def test_confusion_self_hit_after_struggle_belongs_to_confused_actor():
    e=struggle_seed();deliver(e,'钢铠鸦使出了挣扎！',2)
    endpoint(e,3,80,side='opponent',sid=373);endpoint(e,4,80,side='opponent',sid=373)
    deliver(e,'对手的暴飞龙正在混乱中！',5);deliver(e,'不知所以地攻击了自己！',6)
    endpoint(e,7,70,side='opponent',sid=373);endpoint(e,8,70,side='opponent',sid=373);close(e)
    episodes=e.hp_resolutions()['episodes']
    assert [o['cause']['kind'] for o in episodes]==['move','confusion_self_damage']
    assert episodes[1]['delta']==-10 and episodes[1]['actor_instance_id']==active(e,side='opponent').pokemon_instance_id


def test_struggle_recoil_correction_replay_and_cross_battle_isolation():
    e=struggle_seed();deliver(e,'钢铠鸦使出了挣扎！',2)
    endpoint(e,3,80,side='opponent',sid=373);endpoint(e,4,80,side='opponent',sid=373)
    d,_=deliver(e,'钢铠鸦因挣扎受到了反作用力造成的伤害！',5)
    own(e,6,150);own(e,7,150);close(e)
    saved=e.to_dict();again=StateEngine.from_dict(deepcopy(saved));assert again.to_dict()==saved
    replacement=deepcopy(d['events'][0]);replacement['original_text']='钢铠鸦受到了灼伤的伤害！'
    replacement['attributes'].update(cause=dict(kind='status',status='burn'))
    e.correct(replacement['event_id'],replacement,sequence=50,reason='correct literal cause')
    assert e.hp_resolutions()['episodes'][-1]['cause']['kind']=='status'
    assert struggle_seed().hp_resolutions()['episodes']==[]


def test_continued_confusion_without_self_hit_does_not_reuse_old_damage_source():
    e=seed();deliver(e,'对手的暴飞龙使出了喷射火焰！',2)
    endpoint(e,3,90);deliver(e,'对钢铠鸦效果绝佳！',4);endpoint(e,5,90)
    deliver(e,'钢铠鸦正在混乱中！',6);obs=endpoint(e,7,80);endpoint(e,8,80);close(e)
    assert obs['cause'] is None
    assert not any(c['cause']['kind']=='move' for c in obs['candidate_causes'])
    assert e.hp_resolutions()['episodes'][-1]['cause'] is None


def test_failed_struggle_does_not_support_target_damage_or_recoil():
    e=struggle_seed();d,_=deliver(e,'钢铠鸦使出了挣扎！',2)
    replacement=deepcopy(d['events'][0]);replacement['attributes']['effect_outcome']='failed'
    e.correct(replacement['event_id'],replacement,sequence=20,reason='observed failure')
    endpoint(e,3,80,side='opponent',sid=373);endpoint(e,4,80,side='opponent',sid=373)
    own(e,5,150);own(e,6,150);close(e)
    assert all(o['cause'] is None for o in e.hp_resolutions()['episodes'])


def test_curated_b20_exact_observed_messages_work_without_video_artifacts():
    import json
    from pathlib import Path
    messages=json.loads((Path(__file__).parent/'fixtures/b20-confusion-messages.json').read_text())['messages']
    e=StateEngine(BattleState('test'))
    mon=dict(raw_text='风妖精',confidence=.99,resolution=dict(status='resolved',method='exact',
        species_id=547,confidence='strong',canonical_identity='pokeapi:pokemon:547',identity_status='resolved_unique'))
    e.apply(hud(1,1,547,side='opponent',hp=17,mon=mon),sequence=1)
    for t,m in enumerate(messages,2):
        assert m['evidence_kind']=='frozen_observed_text' and m['partial_log_entries']
        d,r=deliver(e,m['text'],t)
        assert len(d['events'])==1 and r[0].application_status in {'applied_candidate','recorded_observation'}
    for t in [6,7]:e.apply(hud(t,t,547,side='opponent',hp=10,mon=mon),sequence=t*10)
    close(e)
    o=e.hp_resolutions()['episodes'][0]
    assert (o['before'],o['after'],o['delta'])==(17,10,-7)
    assert o['cause']['kind']=='confusion_self_damage'


@pytest.mark.parametrize('gap',[100,100000])
def test_confusion_message_context_survives_long_gaps_and_hud_observations(gap):
    e=seed();deliver(e,'钢铠鸦正在混乱中！',2)
    endpoint(e,50,100);e.apply(hud(51,51,823),sequence=510) # occluded HP is not a message
    _,records=deliver(e,'不知所以地攻击了自己！',gap)
    assert records[0].application_status=='recorded_observation'
    assert records[0].bindings['actor']['pokemon_instance_id']==active(e).pokemon_instance_id
    assert records[0].bindings['resolved_event']['attributes']['binding_basis']=='chronological_confusion_notice'
    endpoint(e,gap+1,95);endpoint(e,gap+2,90);close(e,gap+100)
    o=e.hp_resolutions()['episodes'][0]
    assert o['cause']['kind']=='confusion_self_damage' and o['delta']==-10


def test_move_success_consumes_confusion_context_without_creating_self_damage():
    e=seed();deliver(e,'钢铠鸦正在混乱中！',2)
    deliver(e,'钢铠鸦使出了喷射火焰！',1000)
    endpoint(e,1001,80,side='opponent',sid=373);endpoint(e,1002,80,side='opponent',sid=373);close(e,1003)
    assert len(e.hp_resolutions()['episodes'])==1
    assert e.hp_resolutions()['episodes'][0]['cause']['kind']=='move'
    assert not any((o.get('cause') or {}).get('kind')=='confusion_self_damage' for o in active(e).hp.observations)


@pytest.mark.parametrize('preceding',['羽栖','喷射火焰','挣扎'])
def test_missing_confusion_notice_binds_unique_final_hp_loss_not_preceding_move(preceding):
    e=seed();deliver(e,'对手的暴飞龙使出了'+preceding+'！',2)
    d,r=deliver(e,'不知所以地攻击了自己！',3);eid=d['events'][0]['event_id']
    assert r[0].application_status=='deferred'
    e.apply(hud(4,4,823),sequence=40) # HUD need not remain continuously visible
    endpoint(e,5,96);endpoint(e,6,90)
    assert next(r for r in e.history if r.event['event_id']==eid).application_status=='deferred'
    close(e,1000)
    record=next(r for r in e.history if r.event['event_id']==eid)
    assert record.application_status=='recorded_observation'
    proof=record.bindings['resolved_event']['attributes']['confusion_hp_evidence']
    assert (proof['before'],proof['after'])==(100,90)
    assert record.bindings['resolved_event']['attributes']['binding_basis']=='unique_observed_confusion_hp_decrease'
    episodes=e.hp_resolutions()['episodes'];assert len(episodes)==1
    o=episodes[0];assert o['cause']['kind']=='confusion_self_damage'
    assert (o['before'],o['after'],o['delta'])==(100,90,-10)
    assert len(o['segment_event_ids'])==2 and o['hit_resolution']['per_hit_damage'] is None
    assert o['actor_instance_id']==o['affected_instance_id']==active(e).pokemon_instance_id
    assert o['parent_action_id'] is None and o['source_move'] is None
    assert record.event['actor'] is None # immutable original unknown-subject message


@pytest.mark.parametrize('scenario',['no_hp','unchanged','two_decreases','returned_to_baseline'])
def test_missing_confusion_notice_without_unique_final_decrease_stays_unknown(scenario):
    e=seed();d,_=deliver(e,'不知所以地攻击了自己！',2);eid=d['events'][0]['event_id']
    if scenario=='unchanged':endpoint(e,3,100)
    if scenario=='two_decreases':
        endpoint(e,3,90);endpoint(e,4,80,side='opponent',sid=373)
    if scenario=='returned_to_baseline':
        endpoint(e,3,90);endpoint(e,4,100)
    close(e,100)
    r=next(r for r in e.history if r.event['event_id']==eid)
    assert r.application_status=='deferred' and 'actor' not in r.bindings
    assert r.bindings['resolved_event']['actor'] is None


def test_hp_fallback_is_invalidated_by_correction_retraction_and_later_ambiguity():
    e=seed();d,_=deliver(e,'不知所以地攻击了自己！',2);eid=d['events'][0]['event_id']
    endpoint(e,3,90);close(e,100)
    assert next(r for r in e.history if r.event['event_id']==eid).application_status=='recorded_observation'
    before=e.to_dict();assert StateEngine.from_dict(deepcopy(before)).to_dict()==before
    endpoint(e,4,80,side='opponent',sid=373) # inserted inside the same message window
    assert next(r for r in e.history if r.event['event_id']==eid).application_status=='deferred'
    e.retract('hud:4',reason='incorrect second decline')
    assert next(r for r in e.history if r.event['event_id']==eid).application_status=='recorded_observation'
    e.retract('hud:3',reason='no reliable final HP')
    assert next(r for r in e.history if r.event['event_id']==eid).application_status=='deferred'


def test_hp_after_next_independent_message_cannot_resolve_earlier_self_hit():
    e=seed();d,_=deliver(e,'不知所以地攻击了自己！',2);eid=d['events'][0]['event_id']
    deliver(e,'钢铠鸦的防御提高了！',3)
    endpoint(e,4,80);endpoint(e,5,80);close(e)
    assert next(r for r in e.history if r.event['event_id']==eid).application_status=='deferred'


def test_hp_fallback_snapshots_publish_final_receipts_once_and_do_not_cross_battles():
    e=seed();deliver(e,'不知所以地攻击了自己！',2);endpoint(e,3,90);close(e,100)
    original=e.to_dict();seen=[]
    e.replay(snapshot_callback=lambda record,state:seen.append((record.event['event_id'],record.application_status)))
    assert len(seen)==len(e.history) and len({eid for eid,_ in seen})==len(e.history)
    assert e.to_dict()==original
    other=seed();d,_=deliver(other,'不知所以地攻击了自己！',2);close(other,100)
    assert next(r for r in other.history if r.event['event_id']==d['events'][0]['event_id']).application_status=='deferred'


def test_last_hp_observation_wins_over_an_earlier_decrease_on_another_pokemon():
    e=seed();d,_=deliver(e,'不知所以地攻击了自己！',2)
    endpoint(e,3,90);endpoint(e,4,100) # this instance did not lose HP overall
    endpoint(e,5,80,side='opponent',sid=373);close(e,100)
    record=next(r for r in e.history if r.event['event_id']==d['events'][0]['event_id'])
    assert record.bindings['actor']['pokemon_instance_id']==active(e,side='opponent').pokemon_instance_id


def test_fallback_does_not_require_visible_hud_between_animation_endpoints():
    e=seed();d,_=deliver(e,'不知所以地攻击了自己！',2)
    endpoint(e,3,95);e.apply(hud(4,4,823),sequence=40);endpoint(e,500,90);close(e,1000)
    r=next(r for r in e.history if r.event['event_id']==d['events'][0]['event_id'])
    assert r.application_status=='recorded_observation'
    assert e.hp_resolutions()['episodes'][0]['delta']==-10


def test_fallback_considers_active_pokemon_not_benched_hp_observations():
    from battle_events.schema import BattleEvent,Evidence
    e=seed();e.apply(hud(3,3,530,slot='left',hp=dict(current=100,maximum=173)),sequence=30)
    bench=active(e,slot='left').pokemon_instance_id;deliver(e,'龙头地鼠，回来！',4)
    d,_=deliver(e,'不知所以地攻击了自己！',5)
    e.apply(BattleEvent('party-hp:6','hp_change','self',None,None,'party reading',{},None,
        [Evidence('cached_party','test.mp4#6',[],dict(timestamp=6))],.99,'supported',[],
        dict(actor_instance_id=bench,observation_time=6,before=100,after=90,unit='absolute',maximum=173)),sequence=60)
    endpoint(e,7,90);close(e,100)
    r=next(r for r in e.history if r.event['event_id']==d['events'][0]['event_id'])
    assert r.application_status=='recorded_observation'
    assert r.bindings['actor']['pokemon_instance_id']==active(e).pokemon_instance_id
