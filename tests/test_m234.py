"""Independent reliability regressions; recognition fixtures never enter runtime."""
from copy import deepcopy
from dataclasses import asdict
import pytest
from battle_events.schema import BattleEvent, Evidence
from tracking.battle_state import BattleState
from tracking.state_engine import StateEngine, hash_state
from tracking.hidden_state import HiddenEngine
from tracking.evidence_fusion import identity_evidence
from recognition.visual_adapter import visual_events
from recognition.visual_evidence import parse_detail
from recognition.move_resolution import resolve_move
from knowledge import KnowledgeBase


def engine(bid='test'):
    return StateEngine(BattleState(bid,knowledge={'reliability_v1':True}))


def event(kind,t,*,side='self',sid=186,attrs=None,fields=None,bid='test'):
    a=dict(battle_id=bid,observation_time=t,**(attrs or {}))
    if fields is not None:a.update(source_kind='ability_popup',fields=fields)
    return BattleEvent(f'{kind}:{t}',kind,side,dict(species_id=sid,canonical_id=f'pokeapi:species:{sid}'),None,'direct observation',{},None,
        [Evidence('test','test.png',[str(t)],{'timestamp':t})],.99,'supported',[],a)


def hud(t,sid=186,**kwargs):
    from test_evidence_fusion import species
    mon=species(903) if sid==903 else dict(raw_text='蚊香蛙皇',confidence=.99,resolution=dict(status='resolved',method='exact',species_id=186,confidence='strong'))
    return event('hud_observation',t,sid=sid,attrs=dict(slot='right',species=mon,**kwargs))


def test_unplaced_entry_later_popup_and_hud_no_backfill():
    e=engine();r=e.apply(event('send_out',1),sequence=1)
    assert r.application_status=='recorded_observation'
    pid=r.bindings['actor']['pokemon_instance_id']
    assert e.state.sides['self'].active_slots=={}
    assert e.state.pokemon[pid].location.value['kind']=='unplaced_entry'
    r=e.apply(event('visual_observation',2,fields={'ability':{'canonical_id':'pokeapi:ability:2'}}),sequence=2)
    assert r.application_status=='applied_candidate' and r.bindings['actor']['pokemon_instance_id']==pid
    assert e.state.weather.active.value is None
    e.apply(hud(3),sequence=3)
    assert e.state.sides['self'].active_slots['right']==pid
    assert e.history[0].bindings['admissibility']['slot'] is False
    e.retract('hud_observation:3',reason='independent source invalidated')
    assert e.state.sides['self'].active_slots=={}
    assert e.state.pokemon[pid].ability.current.value['canonical_id']=='pokeapi:ability:2'


def test_two_unplaced_same_species_remain_unbound_and_cross_battle_rejected():
    e=engine();e.apply(event('send_out',1),sequence=1);second=event('send_out',2);second.original_text='new sendout after a distinct announcement';e.apply(second,sequence=2)
    r=e.apply(event('visual_observation',3,fields={'ability':{'canonical_id':'pokeapi:ability:2'}}),sequence=3)
    assert r.reason=='visual_instance_unresolved'
    r=e.apply(event('visual_observation',4,fields={},bid='other'),sequence=4)
    assert r.application_status=='rejected'


def test_weak_name_supported_only_by_past_explicit_canonical_mention():
    from test_evidence_fusion import species
    e=engine();prior=event('stat_change',1,sid=903,attrs=dict(side_basis=['explicit_text'],stats=['attack'],change='increment',stages=1))
    e.apply(prior,sequence=1)  # unbound quantitative effect, but independently named actor
    e.apply(hud(2,903,species_unused=True),sequence=2)
    # Retest using a weak observation, no later evidence allowed.
    h=hud(2,903);h.attributes['species']=species(903,.815)
    e.correct(h.event_id,h,sequence=2,reason='weak source')
    assert e.history[-1].bindings['hud']['status']=='accepted'
    e.retract(prior.event_id,reason='bad announcement')
    assert e.history[-1].bindings['hud']['status']=='deferred'


def test_high_margin_nickname_is_opt_in_and_does_not_assert_form():
    mon=dict(raw_text='Bubba',confidence=1,resolution=dict(status='resolved',method='icon_only',species_id=354,canonical_identity='pokeapi:pokemon:354'))
    icon=dict(status='resolved',species_id=354,canonical_identity='pokeapi:pokemon:354',candidates=[dict(similarity=.91461),dict(similarity=.62712)])
    assert identity_evidence(mon,icon)[1]=='deferred'
    ref,status,reason=identity_evidence(mon,icon,reliability=True)
    assert status=='accepted' and 'provisional' in reason and 'canonical_identity' not in ref
    icon['candidates'][1]['similarity']=.85
    assert identity_evidence(mon,icon,reliability=True)[1]=='deferred'


def test_projection_is_read_only_time_safe_and_has_no_expiration_timer():
    e=engine();e.apply(hud(10),sequence=1);before=hash_state(e.state)
    p=e.evidence_projection(as_of=10)
    assert p['occupancy']['self']['right']['status']=='confirmed_current'
    assert e.evidence_projection(as_of=10.00001)['occupancy']['self']['right']['current_instance_id'] is None
    assert e.evidence_projection(as_of=100000)['occupancy']['self']['right']['last_observed_instance_id'] is not None
    p['pokemon'].clear();assert hash_state(e.state)==before
    with pytest.raises(ValueError):e.evidence_projection(as_of=9)
    for t in [True,float('nan'),-1]:
        with pytest.raises(ValueError):e.evidence_projection(as_of=t)


def test_visual_stage_is_absolute_not_delta_and_hidden_receipts_are_replayable():
    e=engine();e.apply(event('send_out',1),sequence=1)
    fields=dict(hp=dict(current=144,maximum=197),item=dict(canonical_id='pokeapi:item:234'),stages=dict(attack=-1,defense=1,special_attack=2))
    visual=event('visual_observation',2,fields=fields);visual.attributes['source_kind']='selected_detail_panel'
    r=e.apply(visual,sequence=2);pid=r.bindings['actor']['pokemon_instance_id']
    e.replay();assert e.state.pokemon[pid].stages['defense'].value.value==1
    hidden=HiddenEngine();payload=visual.to_dict();payload['attributes']['visual_receipt']=r.bindings['visual_receipt']
    hidden.apply(payload,instance_id=pid,side='self',sequence=2,application_status=r.application_status)
    assert hidden.state['pokemon'][pid]['fields']['max_hp']['value']==197
    assert e.state.pokemon[pid].moves.known_slots=={}
    e.retract(visual.event_id,reason='invalid source');assert e.state.pokemon[pid].stages['defense'].value.value is None


def test_visual_conflict_exposes_both_sources_without_silently_selecting():
    e=engine();e.apply(event('send_out',1),sequence=1)
    for t,id_ in [(2,2),(3,22)]:e.apply(event('visual_observation',t,fields={'ability':{'canonical_id':f'pokeapi:ability:{id_}'}}),sequence=t)
    pid=next(iter(e.state.pokemon));f=e.state.pokemon[pid].ability.current
    assert f.knowledge=='conflicting' and len(f.alternatives)==2
    assert e.history[-1].bindings['visual_receipt']['fields']=={}


def test_layout_without_species_cannot_admit_stage_artifacts():
    p=parse_detail({},dict(speed={'value':1}))
    row=dict(request=dict(kind='detail'),parsed=p)
    assert visual_events(row,selection={'side':'self'})==[]


def test_protect_low_confidence_concordance_is_not_a_move_revelation():
    readings=[dict(text='守住!',confidence=c,config_id=str(i),source_sha256='image') for i,c in enumerate([.8764416575,.8574109077])]
    r=resolve_move('',KnowledgeBase(),readings)
    assert r['canonical_id'] is None
    assert {r['canonical_id'] for r in r['alternatives']}=={'pokeapi:move:182'}
    readings.append(dict(text='精神强念',confidence=.99,config_id='other',source_sha256='image'))
    assert resolve_move('',KnowledgeBase(),readings)['canonical_id'] is None


def test_coverage_gap_withholds_current_occupancy_and_retains_last_observation():
    e=engine();e.apply(hud(1),sequence=1)
    e.apply(event('coverage_observation',2,attrs=dict(start=1,status='gap',fields=['occupancy','hp'])),sequence=2)
    p=e.evidence_projection(as_of=2);o=p['occupancy']['self']['right']
    assert o['current_instance_id'] is None and o['last_observed_instance_id']
    assert o['evidence']['intervening_transitions']


def test_same_announced_entry_persists_across_consecutive_frames():
    e=engine();e.apply(event('send_out',1),sequence=1);r=e.apply(event('send_out',2),sequence=2)
    assert len(e.state.pokemon)==1 and r.bindings['actor']['basis']=='consecutive_same_announcement'


def test_explicit_gap_blocks_stale_nickname_move_binding():
    from test_evidence_fusion import message
    e=engine();e.apply(hud(1),sequence=1)
    e.apply(event('coverage_observation',2,attrs=dict(start=1,status='gap',fields=['occupancy'])),sequence=2)
    r=e.apply(message(3,3,'蚊香蛙皇使出了守住！'),sequence=3)
    assert r.application_status=='deferred'
    assert not next(iter(e.state.pokemon.values())).moves.executed


def test_detail_field_presence_does_not_invent_durations_or_side_conditions():
    e=engine();e.apply(event('send_out',1),sequence=1)
    r=e.apply(event('visual_observation',2,fields={'field':{'rain':{'active':True},'grassy':{'active':True},'aurora_veil':{'active':True}}}),sequence=2)
    assert e.state.weather.kind.value=='rain' and e.state.terrain.kind.value=='grassy'
    assert e.state.weather.duration.remaining.value is None
    assert not e.state.sides['self'].conditions['aurora_veil'].active.known
    assert e.evidence_projection(as_of=2)['ui_field_observations']


def test_panel_field_negation_and_duplicate_config_cannot_create_confirmation():
    reads=[dict(text='没有下雨状态',confidence=.99,config_id=c) for c in ['native','double']]
    assert parse_detail({'field0':reads},{})['field']=={}
    reads=[dict(text='下雨状态',confidence=.99,config_id='native')]*2
    assert parse_detail({'field0':reads},{})['field']=={}


def test_projection_rejects_future_evidence_in_initial_state():
    e=engine();e.apply(hud(10),sequence=1)
    restored=StateEngine(e.state)
    with pytest.raises(ValueError):restored.evidence_projection(as_of=9)


@pytest.mark.local_artifacts('.cache/m234/visual-results.json')
def test_saved_visual_results_and_frozen_checkpoint_are_valid_without_recognition():
    import json
    from pathlib import Path
    from scripts.validate_m234 import audit
    from recognition.visual_adapter import selected_panel_side
    import cv2
    assert audit()['ocr_calls']==0
    data=json.loads(Path('.cache/m234/visual-results.json').read_text())
    for row in data['results']:
        if row['request']['kind']!='detail':continue
        selection=selected_panel_side(cv2.imread(row['request']['image']))
        events=visual_events(row,selection=selection)
        if row['request']['battle_id']=='sample_battle_3':
            assert events[0].attributes['fields']['ability']['canonical_id']=='pokeapi:ability:192'
            assert events[0].attributes['fields']['stages']==dict(attack=-1,defense=1,special_attack=2)
        else:assert not events


def test_visual_runner_reuses_serialized_layout_identity_without_ocr(tmp_path,monkeypatch):
    import hashlib
    import cv2
    import numpy as np
    import scripts.recover_m234 as runner
    monkeypatch.setattr(runner,'ROOT',tmp_path)
    for relative in ['recognition/visual_evidence.py','recognition/onnx_ocr.py','.cache/m15-onnx-medium/local-manifest.json']:
        p=tmp_path/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('pinned')
    image=tmp_path/'frame.png';cv2.imwrite(str(image),np.zeros((100,200,3),dtype='uint8'))
    # A layout tuple becomes a JSON list on disk; no uncached crop is requested.
    monkeypatch.setattr(runner,'line_boxes',lambda *args:[[1,2,10,15]])
    monkeypatch.setattr(runner,'variants',lambda *args:[])
    request=dict(battle_id='test',image='frame.png',sha256=hashlib.sha256(image.read_bytes()).hexdigest(),kind='message',timestamp=1)
    first=runner.run([request]);second=runner.run([request])
    assert first['results']==second['results'] and second['new_predictions']==0


def test_projection_preserves_priority_sources_without_asserting_speed_order():
    from test_evidence_fusion import message
    e=engine();e.apply(hud(1),sequence=1)
    m=message(2,2,'蚊香蛙皇使出了守住！')
    m.attributes.update(priority_evidence=[{'source':'reviewed action priority','value':4}],effective_priority=4)
    r=e.apply(m,sequence=2)
    assert r.application_status=='applied_partial'
    action=e.evidence_projection(as_of=2)['action_observations'][0]
    assert action['priority_context']['effective_priority']==4
    assert action['priority_evidence']==m.attributes['priority_evidence']
    assert not action['verified_action_order'] and not action['speed_comparison_admissible']
    assert action['instance_id']==r.bindings['actor']['pokemon_instance_id']


def test_slotless_entry_respects_verified_complete_party_and_existing_identity():
    from tracking.battle_state import PokemonState, Fact
    e=engine();p=PokemonState('known','self',species=Fact({'species_id':186},'observed'))
    e.initial.pokemon['known']=p;e.initial.sides['self'].party_instance_ids=['known'];e.initial.sides['self'].party_complete=Fact(True,'observed')
    r=e.apply(event('send_out',1),sequence=1)
    assert r.bindings['actor']['pokemon_instance_id']=='known'
    assert list(e.state.pokemon)==['known'] and not e.state.sides['self'].active_slots
    bad=event('send_out',2,sid=903);bad.original_text='different species'
    r=e.apply(bad,sequence=2)
    assert r.application_status=='rejected' and r.reason=='send_out_outside_complete_party'
