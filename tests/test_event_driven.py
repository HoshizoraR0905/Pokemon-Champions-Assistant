"""M2.3.8 focused portable contracts; no full recording/model invocation."""
from copy import deepcopy
from pathlib import Path
import cv2
import numpy as np
import pytest
from battle_events.parser import EventParser
from battle_events.schema import BattleEvent, Evidence
from recognition.event_schedule import EventInspection, command_label, ordered_entries
from tracking.battle_state import BattleState
from tracking.state_engine import StateEngine
from tests.test_evidence_fusion import hud


def test_default_two_fps_command_one_fps_and_temporary_loss():
    s=EventInspection()
    assert s.monitor(0,dict(visible=False))
    assert s.advance(0,phase='battle_animation',message_visible=False,changed=False)==2
    assert s.monitor(.5,dict(visible=True))
    assert s.advance(.5,phase='move_selection',message_visible=False,changed=False)==1
    assert s.monitor(1,dict(visible=False))
    s.advance(1,phase='unknown',message_visible=False,changed=False)
    assert not s.monitor(1.5,dict(visible=False)) and s.command
    assert s.last_monitor['temporary_loss']
    assert s.monitor(1.5,dict(visible=False),message_visible=True)
    assert s.advance(1.5,phase='move_selection',message_visible=True,changed=False)==2
    assert s.monitor(3,dict(visible=False)) and not s.command
    assert s.advance(3,phase='battle_animation',message_visible=False,changed=False)==2
    restored=EventInspection();restored.restore(s.dump())
    assert restored.dump()==s.dump()


@pytest.mark.parametrize('i,layout',[(0,'overlay'),(1,'move_menu'),(2,'overlay')])
def test_command_relocation_in_supplied_examples(i,layout):
    p=Path(__file__).parent/'fixtures'/'Image_Illustration'/f'Command_Label_Location_{i}.png'
    image=cv2.resize(cv2.imread(str(p)),(1311,603))
    observation=command_label(image)
    assert observation['visible'] and observation['layout']==layout
    assert observation['countdown'] is None
    image[:]=0
    assert not command_label(image)['visible']


def test_entry_order_keeps_nicknames_prefixes_and_literal_order():
    assert ordered_entries('上吧！皮卡丘！曾是头目的班基拉斯！')==['皮卡丘','曾是头目的班基拉斯']
    assert ordered_entries('XXX派出了赛富豪和想要睡觉的铝钢桥龙！')==['赛富豪','想要睡觉的铝钢桥龙']
    assert ordered_entries('X派出了A和B和C！')==['A和B和C']


@pytest.mark.parametrize('text,kind,side,field,value',[
    ('雨停了！','weather_change','field','weather','rain'),
    ('脚下的青草消失了！','terrain_change','field','terrain','grassy'),
    ('我方的顺风停止了！','side_condition_change','self','condition','tailwind'),
    ('对手的光墙消失了！','side_condition_change','opponent','condition','light_screen'),
    ('我方的反射壁消失了！','side_condition_change','self','condition','reflect'),
    ('我方的极光幕消失了！','side_condition_change','self','condition','aurora_veil'),
    ('扭曲的时空恢复了！','trick_room_change','field','change','end'),
])
def test_literal_endings_reach_state_with_original_time(text,kind,side,field,value):
    event=EventParser().parse(dict(entry_id=text,raw_text=text,ocr_confidence=.99,source_id='video#12'))
    assert (event.event_type,event.side,event.attributes[field])==(kind,side,value)
    event.attributes.update(observation_time=12,battle_id='test')
    engine=StateEngine(BattleState('test'));r=engine.apply(event,sequence=1)
    assert r.application_status=='applied_candidate'
    effect=(engine.state.weather if kind=='weather_change' else engine.state.terrain if kind=='terrain_change'
            else engine.state.trick_room if kind=='trick_room_change' else engine.state.sides[side].conditions[value])
    assert effect.active.value is False
    assert effect.active.provenance[0]['sources'][0]['source_id']=='video#12'


def exchange(t=4):
    return BattleEvent('exchange','position_change','self',None,None,'双方交换了位置！',{},None,
        [Evidence('video_message','test#4',['4'],dict(timestamp=t))],.99,'supported',[],
        dict(observation_time=t,mechanic='ally_switch',execution_observed=True))


def test_ally_switch_requires_execution_preserves_individual_history_and_retracts():
    engine=StateEngine(BattleState('test'))
    engine.apply(hud(1,1,530,slot='left',hp={'current':100,'maximum':185}),sequence=1)
    engine.apply(hud(2,2,823,slot='right',hp={'current':150,'maximum':173}),sequence=2)
    before=deepcopy(engine.state.sides['self'].active_slots)
    history={pid:deepcopy(mon.hp) for pid,mon in engine.state.pokemon.items()}
    engine.apply(exchange(),sequence=3)
    assert engine.state.sides['self'].active_slots==dict(left=before['right'],right=before['left'])
    assert all(mon.hp==history[pid] for pid,mon in engine.state.pokemon.items())
    engine.retract('exchange',reason='test correction')
    assert engine.state.sides['self'].active_slots==before
    announcement=EventParser().parse(dict(entry_id='move',raw_text='龙头地鼠使出了交换场地！',ocr_confidence=.99))
    assert announcement.event_type=='move_execution'
    assert engine.state.sides['self'].active_slots==before
    missing=StateEngine(BattleState('test'));assert missing.apply(exchange(),sequence=1).application_status=='deferred'


def test_retained_identity_updates_hp_without_new_icon_or_species_claim():
    engine=StateEngine(BattleState('test'))
    first=hud(1,1,530,hp={'current':185,'maximum':185});engine.apply(first,sequence=1)
    pid=engine.state.sides['self'].active_slots['right']
    species=deepcopy(engine.state.pokemon[pid].species)
    light=hud(2,2,530,hp={'current':100,'maximum':185})
    light.attributes['species']={};light.attributes['icon']={}
    light.attributes['identity_reused_from']=first.evidence[0].source_id
    record=engine.apply(light,sequence=2)
    assert record.application_status=='applied_candidate'
    assert engine.state.pokemon[pid].hp.current.value==100
    assert engine.state.pokemon[pid].species==species
    assert len(engine.state.pokemon)==1
    bad=deepcopy(light);bad.event_id='bad';bad.attributes['identity_reused_from']='other-battle#1'
    assert engine.apply(bad,sequence=3).application_status=='deferred'


def test_reviewed_entry_mapping_and_unknown_single_entry():
    import json
    from recognition.event_schedule import entry_slots
    data=json.loads((Path(__file__).parent/'fixtures/battles/m238_entry_order.json').read_text())
    for example in data['examples']:
        refs=ordered_entries(example['raw_text'])
        assert refs==example['ordered_references']
        assert entry_slots(example['side'],refs)==[example['first_slot'],example['second_slot']]
    assert entry_slots('unknown',['A','B'])==[None,None]
    assert entry_slots('self',['A'])==[None]


def live_row(t=1,text='龙头地鼠使出了守住！'):
    from recognition.message_occurrences import MessageOccurrences
    row=dict(timestamp=t,source_id=f'test.mp4#{t}',sha256='identical_pixels',image='frame.png',
        ui=dict(overlay=None),snapshot={},message=dict(selected=True,source_region_type='battle_message',raw_text=text,confidence=.99))
    group=MessageOccurrences('test',source_occurrence_ids=True)
    row['occurrence_decision']=group.observe(row)
    return row


def test_video_only_excludes_historical_rows_and_same_pixels_later_are_new_occurrences():
    from recognition.event_report import video_events
    from recognition.message_occurrences import MessageOccurrences
    row=live_row()
    assert video_events([row],[],'test')
    for k in ['log','battle_log','annotations','reference','ground_truth']:
        bad=deepcopy(row);bad[k]={}
        with pytest.raises(ValueError,match='live observations'):video_events([bad],[],'test')
    bad=deepcopy(row);bad['ui']['overlay']='battle_log_overlay'
    with pytest.raises(ValueError,match='Historical'):video_events([bad],[],'test')
    bad=deepcopy(row);bad['occurrence_decision']['events'][0]['evidence'][0]['source_type']='battle_log'
    with pytest.raises(ValueError,match='Historical'):video_events([bad],[],'test')
    group=MessageOccurrences('test',source_occurrence_ids=True)
    first=group.observe(row)['events'][0]['event_id']
    gap=deepcopy(row);gap['timestamp']=2;gap['message']['selected']=False;group.observe(gap)
    later=live_row(3);second=group.observe(later)['events'][0]['event_id']
    assert first!=second


def test_pair_entries_do_not_duplicate_the_first_actor_or_use_roster_membership():
    from recognition.event_report import video_events
    row=live_row(text='上吧！皮卡丘！曾是头目的班基拉斯！')
    events=video_events([row],[],'test');entries=[e for e in events if e['event_type']=='send_out']
    assert len(entries)==2
    assert [e['actor']['species_id'] for e in entries]==[25,248]
    assert [e['attributes']['slot'] for e in entries]==['left','right']
    row=live_row(text='X派出了昵称A和昵称B！')
    assert all(e['actor'] is None for e in video_events([row],[],'test') if e['event_type']=='send_out')


def test_alignment_is_one_to_one_log_inspection_times_are_irrelevant_and_outside_coverage_unscored():
    from recognition.log_comparison import align
    parser=EventParser()
    entries=[dict(entry_id='log1',source_id='log#999',raw_text='对手的龙头地鼠使出了守住！',turn=4,
                  ocr_confidence=.99,observation_ids=['a'],inspection_timestamp=999)]
    logs=[parser.parse(entries[0]).to_dict()]
    first=live_row(1,'对手的龙头地鼠使出了守住！')['occurrence_decision']['events'][0]
    other=live_row(50,'对手的龙头地鼠使出了岩崩！')['occurrence_decision']['events'][0]
    result=align(entries,logs,[first,other])
    assert result['comparisons'][0]['status']=='provisional_match'
    assert result['comparisons'][0]['prediction']['attributes']['observation_time']==1
    assert result['comparisons'][0]['prediction']['attributes'].get('turn') is None
    assert result['unmatched_predictions'][0]['status']=='unscored_log_coverage_unknown'
    duplicate=deepcopy(first);duplicate['event_id']='different-occurrence'
    assert align(entries,logs,[first,duplicate])['comparisons'][0]['status']=='ambiguous_alignment'


def test_prediction_seal_detects_any_modified_prediction(tmp_path):
    import json
    from recognition.event_report import verify_seal
    from recognition.fast_video import digest
    p=tmp_path/'video-only.json';p.write_text('{}')
    (tmp_path/'video-only-seal.json').write_text(json.dumps(dict(stage='video_only_frozen',files={'video-only.json':digest(p)})))
    assert verify_seal(tmp_path)['stage']=='video_only_frozen'
    p.write_text('{"changed":true}')
    with pytest.raises(ValueError,match='changed'):verify_seal(tmp_path)


def test_command_detector_output_is_accepted_by_scheduler():
    image=cv2.resize(cv2.imread(str(Path(__file__).parent/'fixtures/Image_Illustration/Command_Label_Location_0.png')),(1311,603))
    scheduler=EventInspection()
    assert scheduler.monitor(0,command_label(image))
    assert scheduler.last_monitor['active']


def test_historical_reference_cannot_run_before_frozen_prediction(tmp_path):
    from scripts.compare_battle_log import compare
    from battle_artifacts import BattleArtifacts
    with pytest.raises(FileNotFoundError):compare(BattleArtifacts('test',tmp_path),'absent')


def test_identity_models_are_not_repeated_for_hp_changes_and_only_departing_cache_is_invalidated(monkeypatch):
    from collections import Counter
    from types import SimpleNamespace
    from capture import Frame
    from models import Observation
    import recognition.event_schedule as schedule
    calls=[]
    def full(recognizer,frame,cards):
        calls.append(list(cards))
        return SimpleNamespace(to_dict=lambda:dict(pokemon=[dict(slot=f'{s}_active_{i+1}',species=dict(confidence=.99,
            resolution=dict(species_id=25+i)),icon={},hp={}) for s,i,o,name in cards]))
    monkeypatch.setattr(schedule,'recognize_cards',full)
    class OCR:
        def read(self,image,bounds,**kwargs):return Observation('100',.99,bounds,'100')
    image=np.zeros((603,1311,3),np.uint8);frame=Frame(image,'video#1',1,1,{})
    cards=[('own',0,0,(.139,.847,.226,.887)),('own',1,.168,(.307,.847,.394,.887))]
    controller=schedule.IdentitySchedule();counts=Counter();recognizer=SimpleNamespace(ocr=OCR())
    controller.recognize(recognizer,frame,cards,counts)
    frame.source='video#2';frame.timestamp=2
    result=controller.recognize(recognizer,frame,cards,counts)
    assert counts['full_identity_recognition_invocations']==2
    assert counts['identity_reads_reused']==2
    assert all(m['identity_reused_from']=='video#1' for m in result['pokemon'])
    controller.invalidate(dict(event_type='switch_out',side='self',actor=dict(species_id=25),event_id='out',attributes=dict(observation_time=2)))
    assert 'own_active_1' not in controller.known and 'own_active_2' in controller.known
    # A disappearing card supplies no departure evidence and leaves the other cache intact.
    controller.recognize(recognizer,frame,[],counts)
    assert 'own_active_2' in controller.known


def test_ability_banner_produces_ability_evidence_without_assuming_edge_side_or_execution():
    from recognition.event_report import video_events
    row=live_row();row['occurrence_decision']['events']=[]
    parser=EventParser()
    row['visual']=dict(parsed=[dict(kind='popup',status='supported',screen_edge='ability:left',
        species=parser.identity('皮卡丘','species'),ability=parser.identity('静电','ability'),readings={})])
    events=video_events([row],[],'test')
    assert len(events)==1 and events[0]['event_type']=='ability_activation'
    assert events[0]['side']=='unknown'
    assert events[0]['attributes']['source_region_type']=='ability_banner'
    assert events[0]['evidence'][0]['source_type']=='video_popup'
    assert not any(e['event_type']=='move_execution' for e in events)


def test_entry_observation_is_not_reparsed_into_a_second_send_out():
    from recognition.event_report import video_events
    from tracking.state_engine import event_from_dict
    row=live_row(text='上吧！皮卡丘！')
    events=video_events([row],[],'test')
    engine=StateEngine(BattleState('test',knowledge=dict(reliability_v1=True,reliability_v2=True,identity_v1=True)))
    for i,event in enumerate(events,1):engine.apply(event_from_dict(event),sequence=i)
    assert len(engine.state.knowledge['identity_ledger']['entries'])==1
    assert len(engine.state.knowledge['unplaced_entries'])==1
    assert len(engine.state.pokemon)==1


def test_ability_readings_in_one_continuous_banner_are_one_event_and_reentry_stays_separate():
    from recognition.event_report import video_events
    parser=EventParser();rows=[]
    for t in [1,1.5,2,5]:
        row=live_row(t);row['occurrence_decision']['events']=[]
        row['visual']=dict(parsed=[dict(kind='popup',status='supported',screen_edge='ability:left',
            species=parser.identity('皮卡丘','species'),ability=parser.identity('静电','ability'),readings={})])
        rows.append(row)
    events=video_events(rows,[],'test')
    assert len(events)==2
    assert [e['attributes']['observation_time'] for e in events]==[1,5]
