"""B16 source-pixel regressions and complete existing-adapter/state chains."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import cv2
import numpy as np
import pytest
from models import Observation
from recognition.visual_evidence import popup_regions, parse_popup
from recognition.identity_modes import read_hp, hp_refresh
from recognition.event_report import video_events
from battle_events.parser import EventParser
from tracking.state_engine import StateEngine
from tracking.battle_state import BattleState
from tests.test_evidence_fusion import hud, active
from tests.test_semantic_state import deliver

FIXTURE=Path(__file__).parent/'fixtures/battles/sample_battle_16/banner_hp_v1'


@pytest.mark.parametrize('name,side,species,label',[
    ('drizzle-right','opponent','大嘴鸥','降雨'),('drought-left','self','喷火龙','日照')])
def test_source_pixels_banner_visibility_and_two_text_lines(name,side,species,label):
    image=np.zeros((603,1311,3),np.uint8)
    image[187:277,105:1232]=cv2.imread(str(FIXTURE/(name+'.png')))
    regions=popup_regions(image)
    banner=next(b for b in regions if b['side']==side)
    assert len(banner['lines'])==2
    # The right sprite must not be inside either text crop.
    if side=='opponent':assert all(b[2]<=1135 for b in banner['lines'])


def popup(species,label,edge,t):
    readings={k:[dict(text=text,confidence=.999,config_id=k+':'+v) for v in ('native','double')]
        for k,text in [('species',species+'的'),('ability',label)]}
    return dict(timestamp=t,source_id=f'test.mp4#{t}',sha256=str(t),image='test.png',
        ui=dict(regions=[],overlay=None),snapshot={},message={},occurrence_decision=dict(events=[]),
        visual=dict(parsed=[dict(kind='popup',screen_edge='ability:'+edge,**parse_popup(readings))]))


@pytest.mark.parametrize('label,kind',[('降雨','ability'),('吃剩的东西','item')])
def test_banner_to_attributed_state_does_not_create_weather_or_hp(label,kind):
    engine=StateEngine(BattleState('test'))
    e=hud(1,1,823,side='opponent',hp=100)
    engine.apply(e,sequence=1)
    rows=[popup('钢铠鸦',label,'right',2),popup('钢铠鸦',label,'right',2.5)]
    events=video_events(rows,[],'test')
    assert len(events)==1 and events[0]['event_type']==kind+'_activation'
    receipt=engine.apply(events[0],sequence=2)
    assert receipt.application_status=='applied_candidate'
    mon=active(engine,side='opponent')
    if kind=='ability':assert mon.ability.current.value['name']==label
    else:assert mon.item.identity.value['name']==label
    assert mon.hp.displayed_percent.value==100 and not engine.state.weather.active.known
    _,records=deliver(engine,'开始下雨了！',3)
    assert records[0].application_status=='applied_candidate'
    assert engine.state.weather.kind.value=='rain'
    engine.retract(events[0]['event_id'],reason='bad banner')
    assert not active(engine,side='opponent').__dict__[kind].__dict__['current' if kind=='ability' else 'identity'].known
    assert engine.state.weather.kind.value=='rain'


def test_same_species_both_sides_banner_does_not_bind_from_screen_edge():
    engine=StateEngine(BattleState('test'))
    engine.apply(hud(1,1,823,side='self'),sequence=1)
    engine.apply(hud(2,1.5,823,side='opponent'),sequence=2)
    record=engine.apply(video_events([popup('钢铠鸦','降雨','right',2)],[],'test')[0],sequence=3)
    assert record.application_status=='deferred'
    assert not active(engine,side='self').ability.current.known
    assert not active(engine,side='opponent').ability.current.known


@pytest.mark.parametrize('value,expected,status',[(0,dict(current=0,maximum=173),'observed'),
    (None,None,'unreadable')])
def test_read_hp_preserves_numeric_zero_and_unreadable(value,expected,status):
    values=iter([value,173])
    ocr=SimpleNamespace(read=lambda *a,**kw:Observation(next(values),.99,(0,0,1,1),'raw'))
    result=read_hp(SimpleNamespace(ocr=ocr),SimpleNamespace(image=np.zeros((603,1311,3),np.uint8)),
        [('own',0,0,None)],Counter())
    mon=result['pokemon'][0]
    assert mon['hp']['value']==expected and mon['hp_read_status']==status


def test_region_change_opportunity_periodic_and_unreadable_retry():
    sig=np.zeros((24,128),np.uint8)
    old=dict(signature=sig,timestamp=1,reliable=True,retries=0)
    assert hp_refresh(None,sig,1)[0]
    assert not hp_refresh(old,sig,1.5)[0]
    assert hp_refresh(old,sig,1.5,opportunity=True)[0]
    assert hp_refresh(old,sig,3)[0]
    assert hp_refresh(old,np.ones_like(sig)*255,1.1)[0]
    old['reliable']=False
    assert hp_refresh(old,sig,1.1)[0]


@pytest.mark.parametrize('text,cause',[
    ('钢铠鸦受到了灼伤的伤害！',dict(kind='status',status='burn')),
    ('钢铠鸦受到了毒的伤害！',dict(kind='status',status='poison')),
    ('钢铠鸦受到了沙暴的伤害！',dict(kind='weather',weather='sandstorm')),
    ('钢铠鸦受到了隐形岩的伤害！',dict(kind='entry_hazard',hazard='stealth_rock')),
    ('钢铠鸦受到了反作用力的伤害！',dict(kind='move_recoil')),
])
def test_literal_cause_to_affected_hp_ledger_and_numeric_pair(text,cause):
    engine=StateEngine(BattleState('test'))
    engine.apply(hud(1,1,823,hp=dict(current=100,maximum=173)),sequence=1)
    d,records=deliver(engine,text,2)
    assert records[0].application_status=='recorded_observation'
    assert active(engine).hp.current.value==100
    assert active(engine).hp.observations[-1]['cause']==cause
    engine.apply(hud(3,3,823,hp=dict(current=90,maximum=173)),sequence=30)
    change=active(engine).hp.observations[-1]
    assert (change['observed_before'],change['after'],change['delta'])==(100,90,-10)
    assert change['cause']==cause and change['cause_event_ids']==[d['events'][0]['event_id']]
    engine.retract(d['events'][0]['event_id'],reason='not supported')
    assert active(engine).hp.observations[-1]['cause'] is None


@pytest.mark.parametrize('label,kind',[('凸凸头盔','item'),('生命宝珠','item'),('粗糙皮肤','ability'),('喷射火焰','move')])
def test_explicit_source_holder_differs_from_damaged_actor(label,kind):
    engine=StateEngine(BattleState('test'))
    engine.apply(hud(1,1,823,hp=dict(current=100,maximum=173)),sequence=1)
    engine.apply(hud(2,1.5,373,side='opponent',hp=100),sequence=2)
    _,records=deliver(engine,f'钢铠鸦因对手的暴飞龙的{label}受到了伤害！',2)
    assert records[0].application_status=='recorded_observation'
    cause=active(engine).hp.observations[-1]['cause']
    assert cause['kind']==kind and cause['holder']['species_id']==373
    assert cause['holder_side']=='opponent'
    assert not active(engine,side='opponent').hp.observations[-1].get('cause')


def test_multiple_effects_or_intervening_attack_veto_numeric_attribution():
    for texts in [('钢铠鸦受到了灼伤的伤害！','钢铠鸦受到了毒的伤害！'),
                  ('钢铠鸦受到了灼伤的伤害！','钢铠鸦使出了勇鸟猛攻！')]:
        engine=StateEngine(BattleState('test'))
        engine.apply(hud(1,1,823,hp=dict(current=100,maximum=173)),sequence=1)
        for i,t in enumerate(texts,2):deliver(engine,t,i)
        engine.apply(hud(4,4,823,hp=dict(current=90,maximum=173)),sequence=40)
        assert active(engine).hp.observations[-1]['cause'] is None


def test_actual_zero_before_faint_is_retained_without_fabrication():
    engine=StateEngine(BattleState('test'))
    engine.apply(hud(1,1,823,hp=dict(current=100,maximum=173)),sequence=1)
    engine.apply(hud(2,2,823,hp=dict(current=0,maximum=173)),sequence=2)
    pid=active(engine).pokemon_instance_id
    deliver(engine,'钢铠鸦倒下了！',3)
    assert engine.state.pokemon[pid].hp.current.value==0
    assert engine.state.pokemon[pid].hp.observations[-1]['delta']==-100


@pytest.mark.parametrize('text,kind,direction',[
    ('钢铠鸦因腹鼓削减了自己的HP！','self_hp_cost','down'),
    ('钢铠鸦因闪焰冲锋受到了反作用力造成的伤害！','move_recoil','down'),
    ('钢铠鸦的灭亡之歌倒数变成了0！','instant_faint','zero'),
    ('钢铠鸦因钢铠鸦的毒疗回复了体力！','ability','up'),
    ('钢铠鸦因钢铠鸦的吃剩的东西回复了体力！','item','up'),
])
def test_explicit_self_cost_heal_and_perish_never_manufacture_amount(text,kind,direction):
    engine=StateEngine(BattleState('test'))
    engine.apply(hud(1,1,823,hp=dict(current=100,maximum=173)),sequence=1)
    _,records=deliver(engine,text,2)
    assert records[0].application_status=='recorded_observation'
    mon=active(engine);change=mon.hp.observations[-1]
    assert mon.hp.current.value==100 and change['after'] is None
    assert change['cause']['kind']==kind and change['direction']==direction
    assert not mon.fainted.known


def test_opponent_percent_delta_and_unsupported_effect_stays_unknown():
    engine=StateEngine(BattleState('test'))
    engine.apply(hud(1,1,823,side='opponent',hp=100),sequence=1)
    deliver(engine,'对手的钢铠鸦受到了伤害！',2)
    engine.apply(hud(3,3,823,side='opponent',hp=67),sequence=30)
    hp=active(engine,side='opponent').hp;change=hp.observations[-1]
    assert (change['observed_before'],change['after'],change['delta'],change['unit'])==(100,67,-33,'displayed_percent')
    assert not hp.current.known and not hp.maximum.known and change['cause'] is None


def test_hud_change_and_banner_override_command_monitor_throttle():
    from recognition.event_schedule import EventInspection
    s=EventInspection();s.monitor(1,dict(visible=True));s.advance(1,phase='move_selection',message_visible=False,changed=False)
    assert not s.monitor(1.5,dict(visible=True))
    assert s.monitor(1.5,dict(visible=True),hud_changed=True)
    assert s.monitor(1.5,dict(visible=True),banner_visible=True)
    restored=EventInspection();restored.restore(s.dump())
    assert restored.hp_until==4.5


@pytest.mark.parametrize('case',[0,1,2])
def test_b16_visible_zero_gray_hud_is_acquired_without_assuming_zero(case):
    import json
    from recognition.fast_profile import independent_cards
    facts=json.loads((FIXTURE/'zero-provenance.json').read_text());f=facts[case]
    image=np.zeros((603,1311,3),np.uint8);x,y,X,Y=f['bounds']
    image[y:Y,x:X]=cv2.imread(str(FIXTURE/f['fixture']))
    cards=independent_cards(image)
    assert any(c[0]==f['side'] and c[1]==f['index'] for c in cards)
    # Acquisition only: the reader, not gray color or a faint message, supplies HP.


def test_blue_rain_scene_cannot_veto_a_local_banner():
    from recognition.visual_evidence import detail_layout
    image=np.empty((603,1311,3),np.uint8);image[:]=(130,55,25)
    image[187:277,105:1232]=cv2.imread(str(FIXTURE/'drizzle-rain-right.png'))
    assert detail_layout(image)
    assert any(b['side']=='opponent' for b in popup_regions(image))


def test_detail_species_label_without_possessive_is_not_a_banner_activation():
    readings={k:[dict(text=text,confidence=.999,config_id=k+v) for v in ('native','double')]
        for k,text in [('species','钢铠鸦'),('ability','压迫感')]}
    assert parse_popup(readings)['status']=='unresolved'


def test_calibrated_banner_binds_when_same_species_is_active_on_both_sides():
    engine=StateEngine(BattleState('test'))
    engine.apply(hud(1,1,823,side='self'),sequence=1)
    engine.apply(hud(2,1.5,823,side='opponent'),sequence=2)
    row=popup('钢铠鸦','降雨','right',2)
    row['ui']['regions']=[dict(region_id='ability:right',region_type='ability_banner',visibility='visible',bounds=[839,187,1232,277])]
    events=video_events([row],[],'test');r=engine.apply(events[0],sequence=3)
    assert r.application_status=='applied_candidate'
    assert active(engine,side='opponent').ability.current.value['name']=='降雨'
    assert not active(engine,side='self').ability.current.known
    assert r.bindings['resolved_event']['attributes']['side_hint_evidence']['calibration_id']=='champions-banner-1311x603-v1'
    assert events[0]['event_id']==video_events([row],[],'test')[0]['event_id']
    engine.retract(events[0]['event_id'],reason='unsupported layout')
    assert not active(engine,side='opponent').ability.current.known


@pytest.mark.parametrize('text',['钢铠鸦受到了反作用力造成的伤害！','钢铠鸦因反作用力受到了伤害！'])
def test_literal_recoil_without_named_move_keeps_move_unknown(text):
    engine=StateEngine(BattleState('test'))
    engine.apply(hud(1,1,823,hp=dict(current=100,maximum=173)),sequence=1)
    _,records=deliver(engine,text,2)
    assert records[0].application_status=='recorded_observation'
    assert active(engine).hp.observations[-1]['cause']==dict(kind='move_recoil')
    assert active(engine).hp.current.value==100


def test_explicit_numeric_pair_supplies_delta_without_a_prior_hud_read():
    engine=StateEngine(BattleState('test'))
    engine.apply(hud(1,1,823,side='opponent'),sequence=1)
    event=EventParser().parse(dict(entry_id='pair',raw_text='对手的钢铠鸦 HP100%→67%',ocr_confidence=.99))
    record=engine.apply(event,sequence=2)
    assert record.application_status=='applied_candidate'
    hp=active(engine,side='opponent').hp;change=hp.observations[-1]
    assert (change['observed_before'],change['after'],change['delta'],change['unit'])==(100,67,-33,'displayed_percent')
    assert not hp.current.known and change['cause'] is None


@pytest.mark.parametrize('geometry_changed',[False,True])
def test_cached_recognition_accepts_replay_metadata_but_rejects_geometry_changes(tmp_path,monkeypatch,geometry_changed):
    import json
    import recognition.event_report as report
    from recognition.event_schedule import VERSION
    source=tmp_path/'source';source.mkdir();(source/'monitor').mkdir()
    original=dict(battle_id='test',observations=[],roster=[],occurrences=[])
    (source/'observations.json').write_text(json.dumps(original))
    parent=dict(status='complete',counts={},identity=dict(version=VERSION,identity_mode='lightweight',video_sha256='video',
        sources={'tracking/hp_causes.py':'old','recognition/visual_evidence.py':'geometry'}))
    (source/'manifest.json').write_text(json.dumps(parent))
    identity=dict(version=VERSION,identity_mode='lightweight',video_sha256='video',sources={
        'tracking/hp_causes.py':'new','recognition/visual_evidence.py':'changed' if geometry_changed else 'geometry'})
    folder=tmp_path/'new';folder.mkdir()
    monkeypatch.setattr(report,'verify_seal',lambda p:None)
    monkeypatch.setattr(report,'reconstruct_and_package',lambda *args:dict(replayed=True))
    if geometry_changed:
        with pytest.raises(ValueError,match='Recognition dependency changed'):
            report.reconstruct_cached(None,folder,tmp_path/'report',source,identity)
    else:
        result=report.reconstruct_cached(None,folder,tmp_path/'report',source,identity)
        assert result['status']=='complete' and result['counts']['ocr_invocations_performed']==0
        assert (folder/'observations.json').read_bytes()==(source/'observations.json').read_bytes()
