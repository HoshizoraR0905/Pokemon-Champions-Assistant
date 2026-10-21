from collections import Counter
from copy import deepcopy
from types import SimpleNamespace
import numpy as np
import pytest
from recognition.identity_modes import message_identity, EntryVerifier, read_hp
from tests.test_switch_continuity import engine, trainers, apply_text
from tests.test_evidence_fusion import hud
from tracking.active_continuity import current_episode, occupancy


def mode_engine():
    e=engine();e.initial.knowledge['message_identity_v1']=True
    e.initial.sides['self'].vacant_slots=['left']
    trainers(e)
    return e


@pytest.mark.parametrize('name,sid', [('喷火龙',6),('曾是头目的班基拉斯',248),('胡编的喷火龙',None),('Pebble',None)])
def test_exact_message_species_titles_and_unknown(name,sid):
    e=mode_engine();r=apply_text(e,1,f'上吧！{name}！',slot='left')
    assert r.application_status=='applied_candidate', r.reason
    pid=e.state.sides['self'].active_slots['left'];p=e.state.pokemon[pid]
    assert (p.species.value or {}).get('species_id')==sid
    assert current_episode(e.state,pid)['start']==1
    assert occupancy(e.state,'self','left')==('occupied_identified' if sid else 'occupied_unidentified')
    assert r.event['original_text']==f'上吧！{name}！'


def test_message_hp_and_mismatched_hud_cannot_rewrite_identity():
    e=mode_engine();apply_text(e,1,'上吧！喷火龙！',slot='left')
    event=hud(2,2,823,slot='left',hp={'current':80,'maximum':100});event.attributes['battle_id']='test'
    r=e.apply(event,sequence=len(e.history)+1)
    pid=e.state.sides['self'].active_slots['left'];p=e.state.pokemon[pid]
    assert p.species.value['species_id']==6
    assert p.hp.current.value==80
    assert r.bindings['hud']['hp_status']=='accepted'


def test_both_sides_same_species_and_reentry_separate():
    e=mode_engine()
    apply_text(e,1,'上吧！喷火龙！',slot='left')
    apply_text(e,2,'Guest派出了喷火龙！',slot='left')
    assert e.state.sides['self'].active_slots['left']!=e.state.sides['opponent'].active_slots['left']
    apply_text(e,3,'喷火龙，回来！')
    apply_text(e,4,'上吧！喷火龙！',slot='left')
    episodes=[ep for ep in e.state.knowledge['active_entry_episodes'] if ep['side']=='self']
    assert len(episodes)==2 and episodes[0]['departure']['timestamp']==3


def prediction(**kw):
    return dict(episode_id='ep',event_id='send',timestamp=1,side='self',slot='left',
                identity={'species_id':6},outcome='pending',attempts=[],**kw)


@pytest.mark.parametrize('raw,expected', [('喷火龙','match'),('妙蛙花','mismatch'),('?','inconclusive')])
def test_first_hud_independent_bounded_without_prediction_leak(raw,expected):
    from models import Observation, IconEvidence
    v=EntryVerifier('test');v.predictions['ep']=prediction()
    reads=[];icons=[]
    def read(image,bounds,**kw):
        reads.append(kw);return Observation(raw,.99,bounds,raw)
    def identify(*args):
        icons.append(True);return IconEvidence()
    recognizer=SimpleNamespace(ocr=SimpleNamespace(read=read),icons=SimpleNamespace(identify=identify))
    frame=SimpleNamespace(image=np.zeros((603,1311,3),dtype=np.uint8),timestamp=2,source='frame2',metadata={})
    cards=[('own',0,0,(.1,.8,.2,.9))];counts=Counter()
    v.verify(recognizer,frame,cards,counts)
    assert v.predictions['ep']['outcome']==expected
    frame.timestamp=3;v.verify(recognizer,frame,cards,counts)
    assert len(reads)==len(icons)==1 and reads[0]['independent'] is True
    assert v.predictions['ep']['identity']=={'species_id':6}


def test_no_hud_and_unknown_placement_abstain():
    v=EntryVerifier('test');v.predictions['ep']=prediction()
    v.predictions['ep']['slot']=None
    v.verify(None,SimpleNamespace(timestamp=2),[],Counter())
    assert v.finish()['entries'][0]['outcome']=='not_observed'


def test_lightweight_hp_reader_never_reads_name_or_icon():
    from models import Observation
    def read(image,bounds,**kw):
        assert kw['numeric'];return Observation('50%',.99,bounds,'50%')
    recognizer=SimpleNamespace(ocr=SimpleNamespace(read=read))
    frame=SimpleNamespace(image=np.zeros((603,1311,3),dtype=np.uint8))
    result=read_hp(recognizer,frame,[('opponent',0,0,None)],Counter())
    assert result['pokemon'][0]['species']=={} and result['pokemon'][0]['hp']['value']==50


def test_prefix_verifier_freezes_episode_and_departure_before_hud():
    from tests.test_scrolling_semantics import row
    v=EntryVerifier('test')
    rows=[row(1,'上吧！喷火龙！妙蛙花！')]
    v.observe_prefix(rows)
    assert len(v.predictions)==2
    p=next(p for p in v.predictions.values() if (p['identity'] or {}).get('species_id')==6)
    assert p['timestamp']==1 and p['slot'] in {'left','right'}
    frozen=deepcopy(p)
    rows.append(row(2,'喷火龙，回来！'))
    v.observe_prefix(rows)
    assert v.predictions[p['episode_id']]['outcome']=='not_observed'
    assert v.predictions[p['episode_id']]['identity']==frozen['identity']
    rows.append(row(3,'上吧！喷火龙！'))
    v.observe_prefix(rows)
    assert len(v.predictions)==3


def test_prefix_verifier_freezes_verified_title_identity_in_ordered_child():
    from tests.test_scrolling_semantics import row
    v=EntryVerifier('test')
    v.observe_prefix([row(1,'上吧！曾是头目的班基拉斯！喷火龙！')])
    assert sorted((p['identity'] or {}).get('species_id',0) for p in v.predictions.values())==[6,248]


def test_incomplete_message_and_missing_placement_stay_unknown():
    from battle_events.parser import EventParser
    from battle_events.schema import BattleEvent
    e=EventParser().parse(dict(entry_id='x',raw_text='上吧！喷火龙',ocr_confidence=.99))
    assert message_identity(e).actor is None
    v=mode_engine();v.initial.sides['self'].vacant_slots=[];v.replay()
    r=apply_text(v,1,'上吧！Pebble！')
    assert r.application_status=='applied_candidate'
    assert occupancy(v.state,'self','left')=='placement_unresolved'


def test_new_mode_event_records_preserve_detected_title_and_unknown_species():
    from recognition.event_report import video_events
    from tests.test_scrolling_semantics import row
    observed=row(1,'上吧！曾是头目的班基拉斯！Pebble！');observed['identity_mode']='lightweight'
    entries=[e for e in video_events([observed],[],'test') if e['event_type']=='send_out']
    assert entries[0]['attributes']['message_identity']['title']['title']=='曾是头目的'
    assert entries[0]['actor']['species_id']==248 and entries[1]['actor'] is None
    assert all(e['original_text']==observed['occurrence_decision']['events'][0]['original_text'] for e in entries)


def test_lightweight_keeps_supported_major_status_observations():
    e=mode_engine();apply_text(e,1,'上吧！喷火龙！',slot='left')
    r=apply_text(e,2,'喷火龙麻痹了！')
    assert r.application_status=='applied_candidate'
    pid=e.state.sides['self'].active_slots['left']
    assert e.state.pokemon[pid].major_status.value=='paralysis'
