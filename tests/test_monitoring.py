import base64
from dataclasses import replace
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from capture import Frame, load_image
from streaming import StreamingPipeline
from streaming.monitoring import MonitoringRates, ROIMonitor, ROIS
from streaming.recognition import RegionPlanner
from streaming.replay import acquire_at_rate, replay
from recognition import box


class MessagePlanner:
    def plan(self,frame,phase,include_icons=False):
        return [{'label':'battle_message','bounds':box(frame.image,ROIS['message']),
                 'kind':'ocr','priority':0,'required':True}]


class Backend:
    def __init__(self):self.calls=[]
    def recognize(self,frame,region):
        self.calls.append((frame.index,region['label']))
        return {'value':str(frame.index),'confidence':1.}


def frames(count=3):
    result=[]
    for i in range(count):
        image=np.zeros((100,217,3),dtype=np.uint8)
        image[70,50+i]=255
        result.append(Frame(image,'monitor',i,i*.2))
    return result


def pipeline(backend=None,**kwargs):
    return StreamingPipeline(backend or Backend(),planner=MessagePlanner(),asynchronous=False,
                             monitoring=ROIMonitor(),
                             phase_classifier=lambda image:('battle_animation',.8,[],[]),**kwargs)


def test_one_pixel_short_and_similar_messages_are_not_coalesced():
    backend=Backend();p=pipeline(backend)
    observations=[]
    for frame in frames():observations.extend(p.process_frame(frame)['completed'])
    assert len(backend.calls)==3
    ids=[b['observations'][0]['observation_id'] for b in observations]
    assert len(set(ids))==3
    assert [m['timestamp'] for m in p.poll_messages()]==[0.,.2,.4]
    p.close()


def test_roi_guard_sees_brief_control_and_hp_changes_between_phase_deadlines():
    monitor=ROIMonitor(MonitoringRates(phase_fps=1.))
    frame=frames()[0];monitor.inspect(frame)
    unchanged=replace(frame,index=1,timestamp=.2)
    assert not monitor.inspect(unchanged)['phase_check']
    image=frame.image.copy();x1,y1,x2,y2=box(image,ROIS['own_hud_0']);image[y1,x1]=255
    changed=monitor.inspect(Frame(image,'monitor',2,.4))
    assert 'own_hud_0' in changed['changed_rois'] and changed['phase_check']
    image=frame.image.copy();x1,y1,x2,y2=box(image,ROIS['controls']);image[y1,x1]=255
    changed=monitor.inspect(Frame(image,'monitor',3,.6))
    assert 'controls' in changed['changed_rois'] and changed['phase_check']


def test_message_roi_is_monitored_even_during_decision_phase():
    p=StreamingPipeline(Backend(),monitoring=ROIMonitor(),asynchronous=False)
    frame=load_image(Path(__file__).parent/'fixtures/move_selection.png');frame.timestamp=0.
    result=p.process_frame(frame)
    assert result['phase_update']['monitoring']['message_check']
    assert any(o['label']=='battle_message' for o in result['completed'][0]['observations'])
    p.close()


def test_budgeted_versions_preserve_exact_crop_and_uncertainty():
    backend=Backend();p=StreamingPipeline(backend,planner=MessagePlanner(),asynchronous=False,
        monitoring=ROIMonitor(MonitoringRates(message_ocr_fps=2.5,candidate_capacity=1)),
        phase_classifier=lambda im:('move_selection',.8,[],[]))
    fs=frames(4);p.process_frame(fs[0]);result=p.process_frame(fs[1])
    assert result['readiness']['status']=='uncertain'
    candidate=result['phase_update']['candidate_evidence'][0]
    assert candidate['timestamp']==.2 and candidate['observation_id']
    assert candidate['reason']=='message_ocr_budget'
    assert result['completed'][0]['uncertainty']
    lane=p.poll_messages()
    assert [m['timestamp'] for m in lane]==[0.,.2]
    assert lane[-1]['category']=='candidate' and lane[-1]['observation']['value'] is None
    crop=cv2.imdecode(np.frombuffer(base64.b64decode(candidate['png_base64']),np.uint8),cv2.IMREAD_COLOR)
    x1,y1,x2,y2=candidate['region'];assert np.array_equal(crop,fs[1].image[y1:y2,x1:x2])
    p.process_frame(fs[2]);p.process_frame(fs[3])
    assert len(backend.calls)==2
    assert p.monitoring.metrics['candidate_evictions']==1
    assert p.coverage_uncertain
    p.close()


def test_absent_white_foreground_is_unresolved_evidence_not_message_absence():
    p=pipeline();frame=frames()[0];frame.image[:]=0
    result=p.process_frame(frame)
    assert result['completed'][0]['observations'][0]['category']=='candidate'
    assert result['phase_update']['candidate_evidence'][0]['status']=='unresolved_candidate'
    assert p.coverage_uncertain
    p.close()


def test_rate_adapter_reports_missing_samples_to_readiness():
    backend=Backend();p=pipeline(backend);rows=[]
    replay(acquire_at_rate(frames(6),2.),p,rows.append)
    assert any(d['kind']=='potentially_missed_observations' for d in p.diagnostics)
    assert p.coverage_uncertain
    assert p.metrics['captured_frames']<6


def test_monitor_gap_is_explicit_even_when_less_than_old_gap_threshold():
    p=pipeline();fs=frames();fs[1].timestamp=.4
    p.process_frame(fs[0]);p.process_frame(fs[1])
    assert p.monitoring.metrics['message_monitor_gaps']==1
    assert any(d.get('reason')=='message_monitor_cadence_gap' for d in p.diagnostics)
    p.close()


@pytest.mark.parametrize('phase,file', [('pokemon_selection','../reports/M1.4-evidence/m14_boundary_270.jpg'),
                                      ('move_target_selection','fixtures/m14_target_selection_380.png')])
def test_extra_decision_rois_are_inside_reviewed_images(phase,file):
    path=Path(__file__).parent/file
    frame=load_image(path)
    regions=RegionPlanner(decision_regions=True).plan(frame,phase,include_icons=False)
    extra=[r for r in regions if r['label'].startswith(('party_','target_'))]
    assert extra
    h,w=frame.image.shape[:2]
    for r in extra:
        x1,y1,x2,y2=r['bounds'];assert 0<=x1<x2<=w and 0<=y1<y2<=h


@pytest.mark.parametrize('value',[0,-1,float('nan'),float('inf')])
def test_invalid_monitoring_rate(value):
    with pytest.raises(ValueError):MonitoringRates(message_fps=value)


@pytest.mark.parametrize('phase',['move_target_selection','pokemon_selection','switch_selection'])
def test_all_decision_interfaces_get_processing_watermarks(phase):
    p=StreamingPipeline(Backend(),planner=MessagePlanner(),asynchronous=False,
                        phase_classifier=lambda image:(phase,.8,[],[]))
    result=p.process_frame(frames()[0])
    assert result['readiness']['status']=='ready'
    assert result['readiness']['capture_watermark']==0
    assert len(p.decision_updates())==1
    p.close()


def test_source_end_unsampled_frames_are_explicit():
    gaps=[]
    selected=list(acquire_at_rate(frames(5),2.,on_gap=gaps.append))
    assert selected[-1].timestamp==pytest.approx(.6)
    assert gaps==[{'unsampled_input_frames':1,'position':'source_end'}]


def test_exact_repeated_message_does_not_become_unresolved_due_to_budget():
    backend=Backend();p=StreamingPipeline(backend,planner=MessagePlanner(),asynchronous=False,
        monitoring=ROIMonitor(MonitoringRates(message_ocr_fps=2.5)),
        phase_classifier=lambda im:('move_selection',.8,[],[]))
    frame=frames()[0];p.process_frame(frame)
    result=p.process_frame(replace(frame,index=1,timestamp=.2))
    assert result['readiness']['status']=='ready'
    assert not result['phase_update']['candidate_evidence']
    assert len(backend.calls)==1
    p.close()
