"""Portable regressions for the three B17/B18 corrections; no OCR/models/video."""
from collections import Counter
from copy import deepcopy
import json
from types import SimpleNamespace

import numpy as np
import pytest

from battle_events.parser import EventParser
from battle_events.schema import BattleEvent, Evidence
from models import IconEvidence
from recognition import box
from recognition.event_schedule import IdentitySchedule
from recognition.message_occurrences import MessageOccurrences
from tracking.battle_state import BattleState
from tracking.state_engine import StateEngine


@pytest.mark.parametrize('text,side', [
    ('对手的踏冰人偶\n要用逃脱按键回去了！','opponent'),
    (' 对手的 踏冰人偶 \r\n 要用 逃脱按键 回去了 ! ','opponent'),
    ('踏冰人偶\n要用逃脱按键回去了！','self'),
])
def test_explicit_eject_withdrawal_grammar(text,side):
    e=EventParser().parse(dict(entry_id='eject',raw_text=text,ocr_confidence=.99,
        source_region_type='battle_message'))
    assert (e.event_type,e.side,e.actor['species_id'])==('switch_out',side,866)
    assert e.attributes['cause']=='eject_button'
    assert e.attributes['item_consumption_rule']['game']=='Champions'
    assert e.canonical_references['item']['canonical_id']=='pokeapi:item:590'
    assert 'unrecognized_message' not in e.uncertainty
    assert e.original_text==text


def test_banner_is_not_switch_and_repeated_explicit_message_emits_once():
    parser=EventParser()
    assert parser.parse(dict(entry_id='banner',raw_text='踏冰人偶的逃脱按键',ocr_confidence=.99)).event_type=='item_activation'
    group=MessageOccurrences('test',source_occurrence_ids=True);events=[]
    for i,t in enumerate([341.507,342.008,342.508]):
        events+=group.observe(dict(timestamp=t,sha256=str(i),source_id=f'video#{t}',image='frame.png',
            message=dict(selected=True,source_region_type='battle_message',confidence=.99,
                raw_text='对手的踏冰人偶\n要用逃脱按键回去了！')))['events']
    assert len(events)==1 and events[0]['event_type']=='switch_out'


def send(parser,n,sid,slot,t):
    actor=parser.identity({818:'千面避役',866:'踏冰人偶',6:'喷火龙'}[sid],'species')
    return BattleEvent(str(n),'send_out','opponent',actor,None,'入场',{},None,
        [Evidence('video_message',f'video#{t}',[str(n)],dict(timestamp=t))],.99,'supported',[],
        dict(slot=slot,observation_time=t))


def test_eject_switch_preserves_hp_history_and_unique_opponent_slot():
    parser=EventParser();engine=StateEngine(BattleState('test',knowledge=dict(
        active_continuity_v1=True,reliability_v1=True,identity_v1=True)))
    engine.apply(send(parser,1,818,'left',132.505),sequence=1)
    engine.apply(send(parser,2,866,'right',240.007),sequence=2)
    before=deepcopy(engine.state.sides['opponent'].active_slots);pid=before['right']
    hp=BattleEvent('hp','hp_change','opponent',parser.identity('踏冰人偶','species'),None,'85%',{},None,
        [Evidence('video_hud','video#335',['hp'])],.99,'supported',[],dict(unit='displayed_percent',after=85))
    engine.apply(hp,sequence=3)
    stat=deepcopy(hp);stat.event_id='stat';stat.event_type='stat_change';stat.attributes=dict(stats=['special_attack'],change='replace',value=-1)
    engine.apply(stat,sequence=4);saved_hp=deepcopy(engine.state.pokemon[pid].hp)
    e=parser.parse(dict(entry_id='eject',raw_text='对手的踏冰人偶\n要用逃脱按键回去了！',ocr_confidence=.99,source_region_type='battle_message'))
    e.attributes['observation_time']=341.507
    assert engine.apply(e,sequence=5).application_status=='applied_candidate'
    assert engine.state.sides['opponent'].active_slots=={'left':before['left']}
    mon=engine.state.pokemon[pid]
    assert mon.location.value==dict(kind='bench',slot=None) and mon.hp==saved_hp
    assert mon.item.status.value=='consumed' and mon.item.status.knowledge=='derived'
    assert mon.item.status.provenance[-1]['rule_evidence']['source']['revision_id']==2635531
    assert mon.stages['special_attack'].changes and not mon.stages['special_attack'].value.known
    incoming=send(parser,6,6,None,347.508);incoming.attributes.pop('slot')
    assert engine.apply(incoming,sequence=6).application_status=='applied_candidate'
    slots=engine.state.sides['opponent'].active_slots
    assert slots['left']==before['left'] and engine.state.pokemon[slots['right']].species.value['species_id']==6
    saved=engine.to_dict();engine.replay();assert engine.to_dict()==saved


def preview_recognizer():
    calls=[];identities={1:1018,3:768,4:279,6:445}
    def identify(image,bounds):
        n=1+round((bounds[1]/603-.12)/.117);calls.append(n)
        sid=identities.get(n)
        return IconEvidence(status='resolved' if sid else 'unresolved',species_id=sid,
            region=bounds,canonical_id=f'pokeapi:species:{sid}' if sid else None)
    recognizer=SimpleNamespace(icons=SimpleNamespace(identify=identify),resolve_entities=lambda r:None,
        context=SimpleNamespace(remember=lambda r:None))
    return recognizer,calls,identities


def frame(image,t):return SimpleNamespace(image=image,timestamp=t,index=int(t*2),source=f'frame#{t}',metadata={'sha256':str(t)})


def test_preview_retries_are_bounded_and_resolved_rows_retained():
    s=IdentitySchedule();r,calls,_=preview_recognizer();counts=Counter()
    image=np.full((603,1311,3),100,dtype=np.uint8);s.observe_phase('team_preview')
    for t in np.arange(0,10,.5):
        # Small countdown/background/animation changes must not trigger matching.
        image[:]=100+int(t)%4;s.acquire_team(r,frame(image,float(t)),'team_preview','test',counts)
    assert calls==[1,2,3,4,5,6]
    s.acquire_team(r,frame(image,10),'team_preview','test',counts)
    assert calls==[1,2,3,4,5,6,2,5]
    assert {v['species_id'] for v in s.team['opponent'].values()}=={1018,768,279,445}
    assert '2' not in s.team['opponent'] and '5' not in s.team['opponent']
    restored=IdentitySchedule();restored.__dict__.update(json.loads(json.dumps(s.__dict__)))
    restored.acquire_team(r,frame(image,10.5),'team_preview','test',counts)
    assert len(calls)==8
    restored.observe_phase('battle_animation');restored.observe_phase('team_preview')
    restored.acquire_team(r,frame(image,11),'team_preview','test',counts)
    assert calls[-2:]==[2,5] and len(calls)==10


def test_materially_changed_preview_does_not_reuse_previous_pokemon():
    s=IdentitySchedule();r,calls,ids=preview_recognizer();counts=Counter()
    image=np.full((603,1311,3),100,dtype=np.uint8)
    s.acquire_team(r,frame(image,0),'team_preview','test',counts)
    x,y,X,Y=box(image,(.778,.12,.832,.225));image[y:Y,x:X]=250;ids[1]=25
    rows=s.acquire_team(r,frame(image,.5),'team_preview','test',counts)
    assert calls[-1]==1 and len(calls)==7
    assert rows[0]['species_id']==25 and s.team['opponent']['1']['species_id']==25
    # A different unrecognized icon must not inherit the previous resolved mon.
    image[y:Y,x:X]=10;ids.pop(1)
    rows=s.acquire_team(r,frame(image,1),'team_preview','test',counts)
    assert rows[0]['species_id'] is None and '1' not in s.team['opponent']


def preview(n,*,sid=None,status='unresolved',candidate=866,form=None):
    row=dict(battle_id='test',side='opponent',preview_row=2,member_occurrence='test:opponent:preview:2',
        species_id=sid,status=status,icon=dict(status=status,species_id=sid,
            candidates=[dict(species_id=candidate,form_id=form,similarity=.60+n*.001,region=[n])]),
        evidence=dict(source=f'video#{n}',timestamp=n,sha256=str(n)))
    return BattleEvent(str(n),'preview_observation','opponent',None,None,'Observed team row',{},None,
        [Evidence('team_ui',f'video#{n}',[str(n)],dict(timestamp=n))],None,'supported',[],
        dict(battle_id='test',observation_time=n,row=row))


def test_preview_semantic_duplicates_compact_without_losing_events_or_new_candidates():
    engine=StateEngine(BattleState('test',knowledge=dict(identity_v1=True)))
    for n in range(1,21):engine.apply(preview(n),sequence=n)
    assert len(engine.history)==20
    assert len(engine.state.knowledge['identity_ledger']['roster'])==1
    assert len(engine.state.observations)==19
    assert engine.history[19].event['attributes']['row']['evidence']['source']=='video#20'
    engine.apply(preview(21,candidate=6),sequence=21)
    engine.apply(preview(22,form=10152),sequence=22)
    engine.apply(preview(23,sid=866,status='resolved'),sequence=23)
    assert len(engine.state.knowledge['identity_ledger']['roster'])==4
    value=engine.to_dict();engine.replay();assert engine.to_dict()==value
    engine.retract('1',reason='first source withdrawn')
    rows=engine.state.knowledge['identity_ledger']['roster']
    assert len(rows)==4 and rows[0]['evidence']['source']=='video#2'
