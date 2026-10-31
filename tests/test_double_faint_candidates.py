"""Deferred send-out candidates need independent command-HUD verification."""
from copy import deepcopy
import pytest
from tests.test_double_faint import scenario,confirmation
from tests.test_evidence_fusion import species
from tracking.double_faint import pending_pair
from tracking.active_continuity import current_episode


def candidate_scenario(both=False):
    e=scenario()
    arrivals=[r for r in e.history if r.event['event_type']=='send_out'][-2:]
    for r in arrivals if both else arrivals[-1:]:r.event['ocr_confidence']=.9471875
    e.replay();return e,arrivals


def proof():
    h=confirmation()
    for slot,sid in [('left',373),('right',903)]:
        h.attributes['double_faint_hud']['slots'][slot]['icon']=dict(status='resolved',species_id=sid,
            canonical_identity=f'pokeapi:pokemon:{sid}')
    return h


@pytest.mark.parametrize('both',[False,True])
def test_candidate_retained_without_encounter_or_placement_then_confirmed(both):
    e,arrivals=candidate_scenario(both)
    pair=pending_pair(e.state,'opponent');assert pair and len(pair)==2
    assert e.state.sides['opponent'].active_slots=={}
    candidates=e.state.knowledge['double_faint_candidates']
    assert len(candidates)==(2 if both else 1)
    assert all(c['status']=='pending' and 'instance_id' not in c for c in candidates)
    assert all(r.application_status=='deferred' for r in arrivals if r.event['ocr_confidence']<.95)
    assert len(e.state.pokemon)==(2 if both else 3)
    before=deepcopy(e.to_dict()['history'])
    r=e.apply(proof(),sequence=len(e.history)+1);assert not r.reason,r.reason
    assert len(e.state.pokemon)==4
    left=e.state.sides['opponent'].active_slots['left'];right=e.state.sides['opponent'].active_slots['right']
    assert e.state.pokemon[left].species.value['species_id']==373
    assert e.state.pokemon[right].species.value['species_id']==903
    assert e.to_dict()['history'][:-1]==before
    ep=current_episode(e.state,left)
    assert ep['start']==6 and ep['species_resolution_time']==7 and ep['placements'][0]['timestamp']==7
    e.replay();assert len(e.state.pokemon)==4
    e.retract('hud:100',reason='withdraw independent proof')
    assert e.state.sides['opponent'].active_slots=={}
    assert len(e.state.pokemon)==(2 if both else 3)


@pytest.mark.parametrize('case',['no_icon','no_text','conflict','wrong_species','partial','reused','wrong_source'])
def test_candidate_never_admitted_from_incomplete_or_conflicting_proof(case):
    e,_=candidate_scenario();h=proof();read=h.attributes['double_faint_hud']['slots']['left']
    if case=='no_icon':read['icon']={}
    elif case=='no_text':read['species']['resolution']['status']='unresolved'
    elif case=='conflict':read['icon']['species_id']=530
    elif case=='wrong_species':read.update(species=species(823),icon=dict(status='resolved',species_id=823))
    elif case=='partial':h.attributes['double_faint_hud']['slots'].pop('right')
    elif case=='reused':read['identity_reused_from']='earlier'
    elif case=='wrong_source':h.attributes['double_faint_hud']['source_id']='other-frame'
    r=e.apply(h,sequence=len(e.history)+1)
    assert r.reason=='message_episode_occupancy_unresolved'
    assert e.state.sides['opponent'].active_slots=={} and len(e.state.pokemon)==3


def test_single_replacement_and_global_message_threshold_are_unchanged():
    e=scenario()
    # Even after two valid faints, an incomplete low-confidence announcement is
    # not a retained canonical candidate.
    last=next(r for r in reversed(e.history) if r.event['event_type']=='send_out')
    last.event['original_text']='Guest派出了暴飞龙';last.event['ocr_confidence']=.9471875
    e.replay();assert pending_pair(e.state,'opponent') is None
    assert not e.state.knowledge.get('double_faint_candidates')


def test_low_confidence_single_replacement_stays_deferred_and_unplaced():
    from tests.test_identity_modes import mode_engine
    from tests.test_switch_continuity import apply_text
    from recognition.event_report import video_events
    from tests.test_scrolling_semantics import row
    from tracking.state_engine import event_from_dict
    e=mode_engine();apply_text(e,1,'Guest派出了钢铠鸦！',slot='left')
    apply_text(e,2,'Guest派出了龙头地鼠！',slot='right')
    apply_text(e,3,'对手的钢铠鸦倒下了！')
    for event in video_events([row(4,'Guest派出了暴飞龙！')],[],'test'):
        if event['event_type']=='send_out':event['ocr_confidence']=.9471875
        r=e.apply(event_from_dict(event),sequence=len(e.history)+1)
    assert r.application_status=='deferred'
    assert not e.state.knowledge.get('double_faint_candidates')
    assert set(e.state.sides['opponent'].active_slots)=={'right'}
    assert len(e.state.pokemon)==2


def test_recognition_waits_for_independently_detected_normal_command_ui():
    from recognition.double_faint import DoubleFaintVerifier
    from types import SimpleNamespace
    e,_=candidate_scenario();v=DoubleFaintVerifier('test')
    v.pending={'opponent':pending_pair(e.state,'opponent')}
    # No recognizer is supplied: an animation/selection HUD must not trigger reads.
    v.verify(None,SimpleNamespace(timestamp=7),[],{},dict(command_inspection=dict(eligible=False)))
    assert 'opponent' in v.pending


def test_unresolved_candidate_icon_keeps_verifier_pending_for_later_retry():
    from recognition.double_faint import DoubleFaintVerifier
    from collections import Counter
    from types import SimpleNamespace
    from models import Observation,IconEvidence
    import numpy as np
    e,_=candidate_scenario();v=DoubleFaintVerifier('test');v.pending={'opponent':pending_pair(e.state,'opponent')}
    calls=dict(names=0,icons=0);retry=False
    def read(image,bounds,**kw):
        assert kw['independent'] is True
        name=['暴飞龙','大狃拉'][calls['names']%2];calls['names']+=1
        return Observation(name,.999,bounds,name)
    def icon(image,bounds):
        sid=[373,903][calls['icons']%2];calls['icons']+=1
        if sid==373 and not retry:return IconEvidence()
        return IconEvidence(status='resolved',species_id=sid,canonical_id=f'pokeapi:species:{sid}',
            canonical_identity=f'pokeapi:pokemon:{sid}',identity_status='resolved_unique')
    recognizer=SimpleNamespace(ocr=SimpleNamespace(read=read),icons=SimpleNamespace(identify=icon))
    frame=SimpleNamespace(image=np.zeros((603,1311,3),dtype=np.uint8),timestamp=7,source='frame7')
    cards=[('opponent',0,0,(.6,.05,.7,.08)),('opponent',1,.16,(.8,.05,.9,.08))]
    ui=dict(normal_controls=True,eligible=True,reason='normal_four_hud_command',
        visible_slots=['own_active_1','own_active_2','opponent_active_1','opponent_active_2'],
        control_bounds=[[[0,0,1,1]],[[0,0,1,1]]])
    v.verify(recognizer,frame,cards,Counter(),dict(command_inspection=ui))
    assert 'opponent' in v.pending and not e.state.sides['opponent'].active_slots
    retry=True;frame.timestamp=10;frame.source='frame10'
    v.verify(recognizer,frame,cards,Counter(),dict(command_inspection=ui))
    assert not v.pending and calls==dict(names=4,icons=4)
