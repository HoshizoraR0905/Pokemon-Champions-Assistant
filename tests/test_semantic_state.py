"""Live occurrence → prefix parser → StateEngine contracts, without video/model IO."""
from copy import deepcopy
import pytest
from battle_events.parser import EventParser
from recognition.message_occurrences import MessageOccurrences
from tracking.battle_state import BattleState
from tracking.state_engine import StateEngine
from tests.test_evidence_fusion import hud, active


def deliver(engine, text, n, *, confidence=.99):
    row=dict(timestamp=n,sha256=str(n),source_id=f'test.mp4#{n}',image='test.png',
        message=dict(selected=True,source_region_type='battle_message',raw_text=text,confidence=confidence))
    decision=MessageOccurrences('test').observe(row)
    records=[engine.apply(e,sequence=n*10+i) for i,e in enumerate(decision['events'])]
    return decision,records


def seeded(side='self'):
    engine=StateEngine(BattleState('test'))
    engine.apply(hud(1,1,823,side=side,hp={'current':100,'maximum':173}),sequence=1)
    return engine


@pytest.mark.parametrize('side,prefix',[('self',''),('opponent','对手的')])
def test_sleep_continues_and_wakes_on_bound_instance(side,prefix):
    engine=seeded(side)
    for n,suffix,status in [(2,'睡着了！','sleep'),(3,'正在呼呼大睡。','sleep'),(4,'醒过来了！','none')]:
        d,r=deliver(engine,prefix+'钢铠鸦\n'+suffix,n)
        assert len(d['events'])==1 and r[0].application_status=='applied_candidate'
        assert active(engine,side=side).major_status.value==status
    assert active(engine,side=side).hp.current.value==100
    engine.retract(r[0].event['event_id'],reason='test')
    assert active(engine,side=side).major_status.value=='sleep'


@pytest.mark.parametrize('text,side,condition',[
    ('从对手身后\n吹起了顺风！','opponent','tailwind'),
    ('从我方身后吹起了顺风！','self','tailwind'),
    ('我方周围正受到\n广域防守的保护！','self','wide_guard')])
def test_side_outcome_has_supported_side_onset_and_unknown_duration(text,side,condition):
    engine=StateEngine(BattleState('test'))
    d,r=deliver(engine,text,2)
    assert r[0].application_status=='applied_candidate'
    effect=engine.state.sides[side].conditions[condition]
    assert effect.active.value is True
    assert effect.initiated_by.value==dict(event_id=d['events'][0]['event_id'],turn=None)
    assert effect.duration.remaining.knowledge=='unknown'
    assert effect.active.provenance[0]['sources'][0]['details']['timestamp']==2
    assert not engine.state.sides['self' if side=='opponent' else 'opponent'].conditions['tailwind'].active.known


@pytest.mark.parametrize('text,weather',[('日照变强了！','sun'),('刮起了沙暴！','sandstorm')])
def test_weather_is_separate_from_ability(text,weather):
    engine=seeded()
    _,r=deliver(engine,'钢铠鸦的扬沙！',2)
    assert r[0].application_status=='applied_candidate'
    assert active(engine).ability.current.value['name']=='扬沙'
    assert not engine.state.weather.active.known
    _,r=deliver(engine,text,3)
    assert r[0].application_status=='applied_candidate'
    assert engine.state.weather.kind.value==weather
    assert not engine.state.weather.duration.remaining.known


@pytest.mark.parametrize('suffix,effect',[('摆出了防守的架势！','protection_established'),
    ('在攻击中守护住了自己！','protected_from_attack'),('受到了广域防守的保护！','wide_guard_received'),
    ('吸收了电力！','absorbed_electricity')])
def test_completed_effect_is_instance_scoped_without_inventing_move_target_or_timer(suffix,effect):
    engine=seeded();before=deepcopy(active(engine).hp)
    _,r=deliver(engine,'钢铠鸦'+suffix,2)
    assert r[0].application_status=='applied_candidate'
    m=next(m for k,m in active(engine).mechanics.items() if k.startswith('message_outcome:'))
    assert m.scope=='per_action' and m.current['effect'].value==effect
    assert not m.expiration.remaining.known and active(engine).hp==before


@pytest.mark.parametrize('text,direction',[('钢铠鸦体力回复了！','up'),('钢铠鸦受到了伤害！','down'),('钢铠鸦HP降到了0！','zero')])
def test_qualitative_hp_never_manufactures_endpoint_or_cause(text,direction):
    engine=seeded();_,r=deliver(engine,text,2)
    assert r[0].application_status=='recorded_observation'
    hp=active(engine).hp
    assert hp.current.value==100
    assert hp.observations[-1]['direction']==direction and hp.observations[-1]['cause'] is None


def test_numeric_hp_after_move_has_no_attributed_cause():
    p=EventParser();events=p.parse_sequence([
        dict(entry_id='a',raw_text='钢铠鸦使出了勇鸟猛攻！',turn=1,ocr_confidence=.99),
        dict(entry_id='b',raw_text='对手的暴飞龙 HP100%→50%',turn=1,ocr_confidence=.99)])
    assert 'associated_move' not in events[1].attributes
    # A historical sequence target candidate never establishes an HP cause.
    assert events[1].attributes['after']==50


def test_canonical_stone_variant_preserves_raw_and_unrelated_text():
    p=EventParser();raw='喷火龙的喷火龙进化石丫和Hoshi的全一环起了反应!'
    e=p.parse(dict(entry_id='a',raw_text=raw,ocr_confidence=.99,source_region_type='battle_message'))
    assert e.event_type=='move_effect' and e.original_text==raw
    assert e.attributes['text_normalizations'][0]['normalized']=='Y'
    e=p.parse(dict(entry_id='b',raw_text='皮卡丘的神秘进化石丫和Hoshi起了反应!',ocr_confidence=.99))
    assert not e.attributes.get('text_normalizations')


def test_generic_mega_completion_does_not_invent_xy_form():
    from tracking.battle_state import PokemonState,fact
    p=EventParser();ref=p.identity('喷火龙','species');s=BattleState('test')
    mon=PokemonState('charizard','self',species=fact(ref,{}),location=fact(dict(kind='active',slot='left'),{}))
    s.pokemon['charizard']=mon;s.sides['self'].party_instance_ids=['charizard'];s.sides['self'].active_slots={'left':'charizard'}
    engine=StateEngine(s)
    e=p.parse(dict(entry_id='mega',raw_text='喷火龙超级进化成了超级喷火龙！',source_region_type='battle_message',ocr_confidence=.99))
    r=engine.apply(e,sequence=1)
    assert r.application_status=='applied_candidate'
    mon=engine.state.pokemon['charizard']
    assert mon.transformations[-1]['form_unresolved'] and mon.transformations[-1]['after'] is None
    assert not mon.current_variant.known and engine.state.sides['self'].resources['mega_evolution'].value


def test_unknown_side_and_conflicting_sleep_stay_unapplied():
    engine=StateEngine(BattleState('test'))
    _,r=deliver(engine,'从身后吹起了顺风！',2)
    assert not r
    engine=seeded();_,r=deliver(engine,'钢铠鸦麻痹了！',2)
    assert active(engine).major_status.value=='paralysis'
    _,r=deliver(engine,'钢铠鸦正在呼呼大睡。',3)
    assert r[0].application_status=='rejected' and active(engine).major_status.value=='paralysis'


def test_item_announcement_is_activation_without_healing_or_consumption():
    engine=seeded();before=deepcopy(active(engine).hp)
    d,r=deliver(engine,'钢铠鸦的文柚果！',2)
    assert r[0].application_status=='applied_candidate'
    assert active(engine).item.identity.value['name']=='文柚果'
    assert len(active(engine).item.activations)==1 and not active(engine).item.status.known
    assert active(engine).hp==before
    engine.apply(d['events'][0],sequence=20)
    assert len(active(engine).item.activations)==1


def test_semantic_candidate_is_auditable_below_occurrence_gate():
    engine=seeded();d,r=deliver(engine,'从对手身后吹起了顺风！',2,confidence=.85)
    assert not r and not d['events']
    assert d['semantic_admission']=='below_occurrence_confidence'
    assert d['semantic_candidates'][0]['event_type']=='side_condition_change'
    assert not engine.state.sides['opponent'].conditions['tailwind'].active.known
