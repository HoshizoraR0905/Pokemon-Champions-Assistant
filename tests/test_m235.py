"""Generalization contracts: deterministic source reuse and conservative identity."""
from copy import deepcopy
import json
from pathlib import Path
import cv2
import numpy as np
import pytest
from tracking.battle_state import BattleState
from tracking.state_engine import StateEngine
from recognition.message_recovery import context_variants,execution_prefix
from recognition.party_panel import parse
from recognition.hud_reuse import reuse
from recognition.move_resolution import resolve_move
from knowledge import KnowledgeBase
from tests.test_m234 import event,hud


def engine():return StateEngine(BattleState('test',knowledge={'reliability_v1':True,'reliability_v2':True}))


def test_gap_reobservation_does_not_merge_same_species_or_carry_ability():
    e=engine();e.apply(hud(1),sequence=1);old=e.state.sides['self'].active_slots['right']
    e.apply(event('visual_observation',2,fields={'ability':{'canonical_id':'pokeapi:ability:2'}}),sequence=2)
    e.apply(event('coverage_observation',3,attrs=dict(start=2,status='gap',fields=['occupancy'])),sequence=3)
    e.apply(hud(4),sequence=4);new=e.state.sides['self'].active_slots['right']
    assert old!=new and not e.state.pokemon[new].ability.current.known
    assert e.state.pokemon[old].ability.current.known and not e.state.pokemon[old].location.known
    assert e.evidence_projection(as_of=4)['occupancy']['self']['right']['current_instance_id']==new
    e.retract('coverage_observation:3',reason='full coverage supplied')
    assert e.state.sides['self'].active_slots['right']==old


def test_popup_can_reveal_unplaced_instance_without_weather_or_native_origin():
    e=engine();r=e.apply(event('visual_observation',1,fields={'ability':{'canonical_id':'pokeapi:ability:45'}}),sequence=1)
    assert r.application_status=='applied_candidate'
    p=next(iter(e.state.pokemon.values()))
    assert p.location.value==dict(kind='observed_unplaced',slot=None)
    assert not e.state.sides['self'].active_slots and not e.state.weather.active.known
    e.retract(r.event['event_id'],reason='wrong source');assert not e.state.pokemon


def test_party_information_does_not_fill_active_slot_or_reveal_moves():
    e=engine();v=event('visual_observation',1,fields=dict(item={'canonical_id':'pokeapi:item:252'},hp={'current':185,'maximum':185}))
    v.attributes['source_kind']='party_configuration_panel';r=e.apply(v,sequence=1)
    p=e.state.pokemon[r.bindings['actor']['pokemon_instance_id']]
    assert p.hp.current.value==185 and p.item.identity.known
    assert not p.moves.executed and not p.moves.known_slots and not e.state.sides['self'].active_slots
    assert all(not stage.value.known for stage in p.stages.values())


def test_v1_keeps_unknown_popup_instance_unresolved():
    e=StateEngine(BattleState('test',knowledge={'reliability_v1':True}))
    r=e.apply(event('visual_observation',1,fields={'ability':{'canonical_id':'pokeapi:ability:45'}}),sequence=1)
    assert r.reason=='visual_instance_unresolved' and not e.state.pokemon


def test_exact_hud_crop_reuse_requires_all_source_regions():
    image=np.zeros((100,100,3),np.uint8)
    snapshot=dict(pokemon=[dict(slot='own_active_1',species=dict(region=[5,5,10,10]),icon=dict(region=[10,5,15,10]),hp=dict(region=[18,92,24,96]))])
    prior=dict(snapshot=snapshot,sha256='anchor');row=dict(source_id='test#2',timestamp=2,sha256='current')
    result=reuse(prior,image,row,image.copy());assert result['pokemon'][0]['sample_equivalence']['source_sha256']=='current'
    changed=image.copy();changed[93,20]=255
    assert reuse(prior,image,row,changed) is None
    changed=image.copy();changed[50,50]=255
    assert reuse(prior,image,row,changed) is not None


def test_context_padding_is_geometry_driven_and_never_changes_threshold():
    image=np.zeros((100,200,3),np.uint8);v=context_variants(image,[2,5,30,20],150)
    assert [r[0] for r in v]==['native','double','context_native','context_double']
    assert v[2][2]==[2,5,92,20]
    readings=[dict(text='守住!',confidence=c,config_id=str(i),source_sha256='frame') for i,c in enumerate([.876,.857])]
    assert resolve_move('',KnowledgeBase(),readings)['canonical_id'] is None
    readings += [dict(text='守住!',confidence=.98,config_id='context'+str(i),source_sha256='frame') for i in range(2)]
    assert resolve_move('',KnowledgeBase(),readings)['canonical_id']=='pokeapi:move:182'


def test_prefix_requires_literal_execution_and_concordance():
    def reads(text):return [dict(text=text,confidence=.99,config_id=str(i)) for i in range(2)]
    assert execution_prefix(reads('班基拉斯使出了'))
    assert execution_prefix(reads('班基拉斯摆出了防守的架势！')) is None
    assert execution_prefix(reads('特性')) is None
    r=reads('班基拉斯使出了');r[1]['confidence']=.8;assert execution_prefix(r) is None


def test_party_captions_and_hp_are_required_for_admission():
    def readings(text):return [dict(text=text,confidence=.99,config_id=str(i)) for i in range(2)]
    data=dict(species=readings('龙头地鼠'),hp=readings('185/185'),ability_label=readings('特性'),item_label=readings('持有物'))
    assert parse(data,{'side':'self'})['status']=='supported'
    data['item_label']=readings('招式说明');assert parse(data,{'side':'self'})['status']=='unresolved'


def test_frozen_split_does_not_share_occurrences():
    data=json.loads(Path('tests/fixtures/battles/m235_review.json').read_text());groups={}
    for r in data['examples']:groups.setdefault(r['occurrence_group'],set()).add(r['split'])
    assert all(len(v)==1 for v in groups.values())
    assert {r['split'] for r in data['examples']}=={'development','held_out'}


def test_scoped_namespace_is_not_a_battle_specific_pipeline(tmp_path):
    from scripts.process_m235 import ScopedArtifacts
    for bid in ['sample_battle_5','another_recording']:
        p=ScopedArtifacts(bid,tmp_path)
        assert p.cache('m233b1/sampling/x')==tmp_path/'.cache/battles'/bid/'m235/acquisition/sampling/x'


def test_color_correlation_keeps_channel_offset_evidence():
    from recognition.icons import color_correlation
    rng=np.random.default_rng(7)
    texture=rng.uniform(0,30,(12,15,1)).astype('float32')
    reference=texture+np.array([10,70,160],dtype='float32')
    recolored=texture+np.array([160,70,10],dtype='float32')
    mask=np.ones((12,15),dtype='uint8');mask[:2]=0
    assert color_correlation(reference,reference,mask)[0,0]>.999
    assert color_correlation(recolored,reference,mask)[0,0]<0
    canvas=np.zeros((16,21,3),dtype='float32');canvas[2:14,3:18]=reference
    scores=color_correlation(canvas,reference,mask)
    assert np.unravel_index(np.argmax(scores),scores.shape)==(2,3)


def test_mask_suppression_keeps_independent_source_evidence(monkeypatch):
    import recognition.repeat_evidence as module
    from recognition.message_selection import MessageSelector
    import recognition.message_selection as selector_module
    mask=np.zeros((20,30),dtype='uint8');mask[2:8,2:8]=255
    def features(image,config):
        return dict(mask=image[:,:,0],gray=image[:,:,0],text_geometry=True,glyphs=10,strokes=8,bounds=[0,0,30,20],roi_sha256='roi')
    monkeypatch.setattr(module,'features',features);monkeypatch.setattr(selector_module,'features',features)
    image=np.repeat(mask[:,:,None],3,axis=2);selector=MessageSelector();recorder=module.RepeatEvidence()
    def observe(t,image):
        row=dict(sha256=str(t),timestamp=t,selection=selector.select(image,'battle_message',timestamp=t))
        return recorder.observe(row,image)
    first=observe(1,image);second=observe(1.5,image.copy())
    assert first['ocr_selected'] and not second['ocr_selected']
    assert second['suppressed'] and second['exact_mask'] and second['anchor_sha256']=='1'
    assert second['source_sha256']=='1.5' and second['timestamp']==1.5
    changed=image.copy();changed[10:18,15:25]=255
    assert observe(2,changed)['ocr_selected']
    assert observe(10,image)['ocr_selected']  # no bridging missing observation time


def test_cache_only_mode_cannot_construct_inference_backend(tmp_path,monkeypatch):
    import recognition.onnx_ocr as module
    from scripts.process_m235 import CropCache,PredictionBudgetExceeded
    from battle_artifacts import BattleArtifacts
    def forbidden(*args,**kwargs):raise AssertionError('Inference backend constructed')
    monkeypatch.setattr(module.ONNXOCRBackend,'__init__',forbidden)
    cache=CropCache(BattleArtifacts('test',tmp_path),450)
    with pytest.raises(PredictionBudgetExceeded,match='inference disabled'):
        cache.predict([np.zeros((12,30,3),dtype='uint8')])
    assert cache.new==0


def test_evaluation_does_not_reward_unknown_or_call_withheld_attribution_false():
    from collections import Counter
    from scripts.score_m235 import measure
    c=Counter();measure(c,None,None)
    assert not c['correct'] and not c['facts']
    measure(c,185,185,attributed=None)
    assert c['unresolved_attribution']==1 and not c['false_admissions']
    measure(c,185,185,attributed=False)
    assert c['misattributed']==1 and c['false_admissions']==1
    measure(c,185,None)
    assert c['unresolved']==1 and not c['correct']


def test_gap_does_not_place_historical_slotless_arrival_as_current_individual():
    e=engine();r=e.apply(event('send_out',1),sequence=1);old=r.bindings['actor']['pokemon_instance_id']
    e.apply(event('visual_observation',2,fields={'ability':{'canonical_id':'pokeapi:ability:2'}}),sequence=2)
    e.apply(event('coverage_observation',3,attrs=dict(start=2,status='gap',fields=['occupancy'])),sequence=3)
    e.apply(hud(4),sequence=4);new=e.state.sides['self'].active_slots['right']
    assert new!=old and not e.state.pokemon[new].ability.current.known
    assert e.state.pokemon[old].ability.current.known
    e.retract('coverage_observation:3',reason='continuous evidence supplied')
    assert e.state.sides['self'].active_slots['right']==old
