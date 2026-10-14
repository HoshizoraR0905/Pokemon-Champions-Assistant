from copy import deepcopy
import pytest
from battle_events.parser import EventParser, BattleContext
from recognition.move_resolution import resolve_move
from knowledge import KnowledgeBase
from tests.test_evidence_fusion import hud,message,active
from tracking.state_engine import StateEngine
from tracking.battle_state import BattleState

@pytest.mark.parametrize('text,kind,attrs',[
 ('班基拉斯拍落了对手的奇麒麟的吃剩的东西！','item_change',{'change':'remove'}),
 ('对手的大狃拉用白色香草复原了能力！','item_activation',{'reported_effect':'stat_restoration','stat_values':None}),
 ('对手的奇麒麟扭曲了时空！','trick_room_change',{'change':'start'}),
 ('班基拉斯的班基拉斯进化石和Hoshi的全一环起了反应！','move_effect',{'completed_transformation':False}),
])
def test_new_patterns(text,kind,attrs):
 e=EventParser().parse(dict(entry_id='e',raw_text=text,ocr_confidence=.99))
 assert e.event_type==kind
 assert all(e.attributes[k]==v for k,v in attrs.items())
 if kind=='item_change':assert e.actor['name']=='奇麒麟' and e.side=='opponent'

@pytest.mark.parametrize('text',[
 '班基拉斯没有拍落对手的奇麒麟的吃剩的东西！',
 '班基拉斯拍落了对手的奇麒麟的未知物品！',
 '对手的大狃拉用白色香草没有复原能力！',
 '对手的大狃拉用未知物品复原了能力！',
 '对手的奇麒麟没有扭曲时空！',
 '班基拉斯的进化石没有起反应！',
])
def test_negative_patterns(text):
 e=EventParser().parse(dict(entry_id='e',raw_text=text,ocr_confidence=.99))
 assert e.event_type=='unknown'

@pytest.mark.parametrize('token',['雪地','出','石朋','岩丽','未知招式'])
def test_similarity_never_confirms(token):
 r=resolve_move(token,KnowledgeBase());assert r['canonical_id'] is None


def test_move_resolution_concordance_conflict_and_provenance():
 kb=KnowledgeBase()
 alt=[dict(text='岩崩！',confidence=.98,source_sha256='frame',config_id=c) for c in ['native','double']]
 r=resolve_move('石朋',kb,alt);assert r['canonical_id']=='pokeapi:move:157'
 assert r['method']=='concordant_image_ocr' and len(r['alternatives'])==2
 assert resolve_move('石朋',kb,alt[:1])['canonical_id'] is None
 assert resolve_move('地震',kb,alt)['canonical_id'] is None
 assert resolve_move(' 岩 崩。 ',kb)['canonical_id']=='pokeapi:move:157'


def test_white_herb_no_consumption_or_fabricated_stages():
 e=StateEngine(BattleState('test'));e.apply(hud(1,1,903,side='opponent'),sequence=1)
 r=e.apply(message(2,2,'对手的大狃拉用白色香草复原了能力！'),sequence=2)
 p=next(iter(e.state.pokemon.values()))
 assert r.application_status=='applied_candidate'
 assert p.item.activations and not p.item.status.known
 assert all(not s.value.known for s in p.stages.values())
 assert not p.item.changes


def test_recovered_move_through_prefix_fusion_retraction_and_unknown_target():
 e=StateEngine(BattleState('test'));e.apply(hud(1,1,823),sequence=1)
 m=message(2,2,'钢铠鸦使出了石朋！')
 m.attributes['move_ocr_alternatives']=[dict(text='岩崩！',confidence=.99,source_sha256='2',config_id=c) for c in ['native','double']]
 r=e.apply(m,sequence=2)
 assert r.application_status=='applied_partial'
 assert r.bindings['admissibility']['effects'] is False
 assert active(e).moves.executed[0]['move']['canonical_id']=='pokeapi:move:157'
 e.retract(m.event_id,reason='invalid crop');assert not active(e).moves.executed


def test_wrong_frame_cannot_repair_move_and_no_future_hud_binding():
 e=StateEngine(BattleState('test'));e.apply(hud(1,1,823),sequence=1)
 m=message(2,2,'钢铠鸦使出了石朋！')
 m.attributes['move_ocr_alternatives']=[dict(text='岩崩！',confidence=.99,source_sha256='future',config_id=c) for c in ['native','double']]
 assert e.apply(m,sequence=2).application_status=='deferred'
 assert not active(e).moves.executed


def test_knock_off_changes_only_owner_item_and_retracts():
 e=StateEngine(BattleState('test'))
 species=dict(raw_text='奇麒麟',confidence=.99,resolution=dict(status='resolved',method='exact',species_id=981,confidence='strong',canonical_identity='pokeapi:pokemon:981',identity_status='resolved_unique'))
 e.apply(hud(1,1,823,side='opponent',mon=species),sequence=1)
 m=message(2,2,'班基拉斯拍落了对手的奇麒麟的吃剩的东西！')
 assert e.apply(m,sequence=2).application_status=='applied_candidate'
 p=next(iter(e.state.pokemon.values()));assert p.item.status.value=='none'
 assert p.item.changes[-1]['item']['canonical_id']=='pokeapi:item:211'
 assert not p.hp.current.known
 e.apply(m,sequence=2);assert len(next(iter(e.state.pokemon.values())).item.changes)==1
 e.retract(m.event_id,reason='wrong message');assert not next(iter(e.state.pokemon.values())).item.status.known


def test_existing_ability_grammar_and_negative_menu_fragment():
 parser=EventParser()
 assert parser.parse(dict(entry_id='a',raw_text='对手的炽焰咆哮虎的威吓！')).event_type=='ability_activation'
 assert parser.parse(dict(entry_id='b',raw_text='特性威吓')).event_type=='unknown'

@pytest.mark.local_artifacts('.cache/m233b2/recovery.json')
def test_reviewed_same_evidence_evaluation():
 from scripts.evaluate_m233b2 import run
 scores=run()
 assert scores['total']==28 and scores['b2_pattern_correct']==28
 assert scores['b2_move_correct']==scores['move_examples']==4
 assert scores['false_canonical_assignments']==0
