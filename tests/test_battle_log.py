"""M2.1 regressions: geometry, sequence identity, uncertainty and outcome parsing."""
import json
from pathlib import Path
import cv2
import pytest
from battle_events import EventParser, BattleContext, Participant, BattleEvent, Evidence
from recognition.battle_log import detect_log, assemble_views
from battle_events.evaluation import evaluate

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def parser():return EventParser()


def row(text,color=None,order=1,confidence=.99):
    return {'entry_id':f'test:{order}','raw_text':text,'color':color,'ocr_confidence':confidence,
            'source_id':'fixture','observation_ids':[f'raw:{order}'],'log_order':order,'turn':2}


def calibrated():return BattleContext(color_sides={'red':'opponent','purple':'self'})


@pytest.mark.parametrize('text,color,kind,side',[
 ('轰擂金刚猩，回来！',None,'switch_out','self'),
 ('上吧！蚊香蛙皇！',None,'send_out','self'),
 ('对手的红莲铠骑使出了铠农炮！','red','move_execution','opponent'),
 ('蚊香蛙皇 HP 197 → 173','purple','hp_change','self'),
 ('爱管侍的精神制造者','red','ability_activation','opponent'),
 ('大狃拉的精神种子','red','item_activation','opponent'),
 ('开始下雨了！',None,'weather_change','field'),
 ('脚下传来了奇妙的感觉！',None,'terrain_change','field'),
 ('对手的红莲铠骑的防御、特防降低了！',None,'stat_change','opponent'),
 ('对手的红莲铠骑倒下了！',None,'faint','opponent'),
 ('对手的蚊香蛙皇中毒了！',None,'status_change','opponent'),
 ('击中了要害！',None,'critical_hit','unknown'),
 ('击中了3次！',None,'multi_hit','unknown'),
 ('选择铠农炮',None,'unknown','unknown'),
 ('蚊香蛙皇 HP 197 → 173',None,'hp_change','unknown'),
])
def test_outcomes(parser,text,color,kind,side):
    event=parser.parse(row(text,color),calibrated())
    assert (event.event_type,event.side)==(kind,side)
    assert event.original_text==text and event.status=='candidate'


def test_unobserved_trainer_unique_id():
    assert Participant('self','Hoshi').unique_trainer_id is None
    assert Participant('opponent','训练家').unique_trainer_id is None


def test_same_species_both_sides_stays_unknown(parser):
    context=calibrated();context.active={'self':{'pokeapi:species:186'},'opponent':{'pokeapi:species:186'}}
    event=parser.parse(row('蚊香蛙皇 HP 197 → 173'),context)
    assert event.side=='unknown'
    assert 'species_active_on_both_sides' in event.uncertainty


def test_generic_trainer_needs_evidence(parser):
    event=parser.parse(row('训练家派出了爱管侍！'),calibrated())
    assert event.side=='unknown'
    context=calibrated()
    events=parser.parse_sequence([row('训练家换下了雷丘！',order=1),row('训练家派出了爱管侍！',order=2),row('爱管侍的精神制造者','red',3)],context)
    # Color-supported activation does not establish an arbitrary trainer ID.
    assert [e.side for e in events]==['unknown','unknown','opponent']
    assert 'side_hint_evidence' in events[0].attributes


def test_no_color_calibration_no_guess(parser):
    assert parser.parse(row('爱管侍的精神制造者','red')).side=='unknown'


def test_conflicting_side_unknown(parser):
    assert parser.parse(row('对手的红莲铠骑倒下了！','purple'),calibrated()).side=='unknown'


def test_shared_display_name_unknown(parser):
    c=calibrated();c.participants={s:Participant(s,'Sam') for s in ('self','opponent')}
    assert parser.parse(row('Sam派出了爱管侍！'),c).side=='unknown'


def test_corrupted_actor_is_unresolved(parser):
    event=parser.parse(row('对手的红莲错骑使出了铠农炮！'),calibrated())
    assert event.actor is None and 'actor_unresolved' in event.uncertainty
    assert event.canonical_references['move']['canonical_id']=='pokeapi:move:890'


def test_move_target_is_sequence_association(parser):
    alone=parser.parse(row('对手的红莲铠骑使出了铠农炮！'),calibrated())
    assert alone.target is None
    events=parser.parse_sequence([row('对手的红莲铠骑使出了铠农炮！',order=1),row('蚊香蛙皇 HP 197 → 173','purple',2)],calibrated())
    assert events[0].target['canonical_id']=='pokeapi:species:186'
    assert events[0].attributes['target_basis']['event_id']==events[1].event_id
    assert 'target_associated_from_sequence' in events[0].uncertainty


def test_hp_percent_not_damage_calculation(parser):
    event=parser.parse(row('红莲铠骑 HP 30% → 0%','red'),calibrated())
    assert event.attributes['unit']=='displayed_percent'
    assert 'damage' not in event.attributes


def test_stat_magnitude_unknown_and_low_ocr(parser):
    event=parser.parse(row('对手的红莲铠骑的防御、特防降低了！',confidence=.3),calibrated())
    assert set(event.attributes['stats'])=={'defense','special_defense'}
    assert event.attributes['stages'] is None and 'low_ocr_confidence' in event.uncertainty


def test_live_evidence_uses_same_schema():
    e=BattleEvent('live:1','hp_change','self',None,None,'',{},None,
        [Evidence('video_observation','capture:1',['hud:1'])],None,'uncertain',['actor_unknown'],{'before':197,'after':173})
    assert e.to_dict()['log_order'] is None
    assert e.to_dict()['evidence'][0]['source_type']=='video_observation'


def test_stable_event_id(parser):
    entry=row('开始下雨了！')
    assert parser.parse(entry,battle_id='b').event_id==parser.parse(entry,battle_id='b').event_id
    assert parser.parse(entry,battle_id='b').event_id!=parser.parse(entry,battle_id='other').event_id


@pytest.mark.parametrize('scale',[.75,1.,1.5])
@pytest.mark.local_artifacts('reports/M2.1-battle-log-evidence/log-full-374.png')
def test_log_positive_geometry(scale):
    full=cv2.imread(str(ROOT/'reports/M2.1-battle-log-evidence/log-full-374.png'))
    full=cv2.resize(full,None,fx=scale,fy=scale)
    geometry=detect_log(full)
    assert geometry is not None and len(geometry['separators'])==5


@pytest.mark.local_artifacts('reports/M2-battle-log-evidence/log-374.png','reports/M2.1-battle-log-evidence/team-preview-28.png')
def test_log_geometry_and_negative_fixture():
    image=cv2.imread(str(ROOT/'reports/M2-battle-log-evidence/log-374.png'))
    # Saved log crops intentionally do not carry the whole-screen geometry.
    assert detect_log(image) is None
    full=cv2.imread(str(ROOT/'tests/fixtures/battle_screen.png'))
    assert detect_log(full) is None
    preview=cv2.imread(str(ROOT/'reports/M2.1-battle-log-evidence/team-preview-28.png'))
    assert detect_log(preview) is None


@pytest.mark.local_artifacts('reports/M2.1-battle-log-raw-ocr.json','reports/M2.1-battle-log-events.json')
def test_saved_automatic_predictions_and_reference_evaluation():
    raw=json.loads((ROOT/'reports/M2.1-battle-log-raw-ocr.json').read_text())
    output=json.loads((ROOT/'reports/M2.1-battle-log-events.json').read_text())
    reference=json.loads((ROOT/'tests/fixtures/m21_battle_log_ground_truth.json').read_text())
    entries,issues=assemble_views(raw['views'])
    assert entries==output['entries']
    assert len(entries)==20
    assert {r['reason'] for r in issues}=={'countdown_overlay'}
    score=evaluate(raw,output,reference)
    assert score['entry_detection_recall']['correct']==20
    assert score['ocr_exact_text']['correct']==18
    assert score['fields']['event_type']['correct']==20
    assert score['chronological_order']['exact_sequence']
    assert not score['incorrect_fields']


def test_repeated_text_not_globally_deduplicated():
    def observation(text,i):
        return {'raw_text':text,'observation_id':str(i),'source_id':'battle#1','ocr_confidence':.9,'partial':False,'color':None}
    rows=[observation(t,i) for i,t in enumerate(['开始下雨了！','甲','开始下雨了！','乙'])]
    view={'turn':2,'timestamp':1,'source_id':'battle#1','detected':True,'geometry':{'scroll_top':0},'observations':rows}
    entries,issues=assemble_views([view])
    assert len(entries)==4 and entries[0]['entry_id']!=entries[2]['entry_id']
    assert not issues


def test_low_confidence_cannot_seed_context(parser):
    c=calibrated()
    parser.parse(row('上吧！蚊香蛙皇！',confidence=.3),c)
    assert not c.active['self']
    assert parser.parse(row('蚊香蛙皇 HP 197 → 173'),c).side=='unknown'


def test_terrain_does_not_use_stale_ability(parser):
    events=parser.parse_sequence([row('爱管侍的精神制造者','red',1),row('对手的红莲铠骑使出了铠农炮！','red',2),row('脚下传来了奇妙的感觉！',order=3)],calibrated())
    assert events[2].attributes['terrain'] is None


@pytest.mark.local_artifacts('reports/M2.1-battle-log-evidence/team-preview-28.png')
def test_preview_names_are_observations():
    from recognition.trainers import recognize_preview_trainers
    from models import Observation
    class Backend:
        def __init__(self):self.names=iter(['Hoshi','训练家'])
        def read(self,image,box):return Observation(raw_text=next(self.names),confidence=.99)
    image=cv2.imread(str(ROOT/'reports/M2.1-battle-log-evidence/team-preview-28.png'))
    found=recognize_preview_trainers(image,Backend(),source='preview',sha256='test')
    assert found['self']['display_name']=='Hoshi'
    assert found['opponent']['display_name']=='训练家'
    assert all(v['unique_trainer_id'] is None for v in found.values())
    assert recognize_preview_trainers(image*0,Backend(),source='blank',sha256='test')=={}


def test_target_association_does_not_cross_turn(parser):
    first=row('对手的红莲铠骑使出了铠农炮！','red',1)
    second=row('蚊香蛙皇 HP 197 → 173','purple',2);second['turn']=3
    events=parser.parse_sequence([first,second],calibrated())
    assert events[0].target is None
    assert events[1].attributes.get('associated_move') is None
