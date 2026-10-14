from dataclasses import asdict
import json
from pathlib import Path
import threading
import time

import cv2
import numpy as np
import pytest

from capture import Frame, load_image
from models import Observation
from streaming import Limits, StreamingPipeline
from streaming.recognition import RegionBackend, RegionPlanner
from streaming.replay import cached_frames, replay

FIXTURES=Path(__file__).parent/'fixtures'


class Backend:
    def __init__(self):self.calls=[]
    def recognize(self,frame,region):
        self.calls.append((frame.index,region['label']))
        return {'value':str(frame.index), 'confidence':1.,'provenance':'test_visible_region'}


class Planner:
    def __init__(self,kinds=('ocr',)):self.kinds=kinds
    def plan(self,frame,phase,include_icons=True):
        return [{'label':'message' if k=='ocr' else 'identity','bounds':(0,0,10,10),
                 'kind':k,'priority':0 if k=='ocr' else 2,'required':True} for k in self.kinds]


def frames(count=3):
    return [Frame(np.full((10,10,3),i,dtype='uint8'),'test',i,i*.1) for i in range(count)]


def pipeline(backend=None,**kwargs):
    return StreamingPipeline(backend or Backend(),planner=Planner(),icons=False,
                             phase_classifier=lambda image:('move_selection',.8,['visible'],[]),**kwargs)


def test_incremental_order_and_online_segments():
    p=pipeline(asynchronous=False)
    first=p.process_frame(frames()[0]);assert first['completed'][0]['frame_index']==0
    assert first['phase_update']['segment_update']['finalized'] is False
    assert first['readiness']['status']=='ready'
    second=p.process_frame(frames()[1]);assert second['phase_update']['segment_update']['sample_count']==2
    assert len(p.pending)==0
    p.close()


def test_exact_repeat_coalesces_but_reappearance_does_not():
    backend=Backend();p=pipeline(backend,asynchronous=False)
    fs=frames();fs[1].image=fs[0].image.copy()
    p.process_frame(fs[0]);second=p.process_frame(fs[1])
    assert second['phase_update']['coalesced_regions']
    assert len(backend.calls)==1
    # A one-pixel change is significant, even with near-identical scene signatures.
    fs[2].image=fs[1].image.copy();fs[2].image[0,0,0]=1
    last=p.process_frame(fs[2]);assert len(backend.calls)==2
    assert last['completed'][0]['observations'][0]['observation_id'] != second['phase_update']['coalesced_regions'][0]['evidence_observation_id']
    p.close()


def test_duplicate_capture_protection_and_conflict():
    p=pipeline(asynchronous=False);frame=frames()[0]
    p.process_frame(frame)
    assert p.process_frame(frame)['duplicate']
    changed=Frame(np.ones_like(frame.image),'test',0,0.)
    with pytest.raises(ValueError):p.process_frame(changed)
    assert p.coverage_uncertain
    p.close()


def test_delayed_job_running_is_pending_even_when_queue_empty():
    entered=threading.Event();release=threading.Event()
    class Slow(Backend):
        def recognize(self,f,r):
            entered.set();assert release.wait(2);return super().recognize(f,r)
    p=pipeline(Slow())
    result=p.process_frame(frames()[0]);assert entered.wait(1)
    assert p.queues['ocr'].empty()
    assert result['readiness']['status']=='pending'
    assert p.readiness()['pending_jobs']==1
    release.set();final=p.finish()
    assert final['readiness']['status']=='ready'
    assert len(p.decision_updates())==1
    p.close()


def test_out_of_order_completion_is_collected_in_capture_order():
    gate=threading.Event();entered=threading.Event()
    class SlowIcon(Backend):
        def recognize(self,f,r):
            if r['kind']=='icon' and f.index==0:
                entered.set();assert gate.wait(2)
            return super().recognize(f,r)
    p=StreamingPipeline(SlowIcon(),planner=Planner(('ocr','icon')),icons=True,
                        phase_classifier=lambda image:('move_selection',.8,[],[]))
    p.process_frame(frames()[0]);assert entered.wait(1)
    second=p.process_frame(frames()[1]);time.sleep(.02)
    assert not second['completed'] and not p.poll()
    gate.set();final=p.finish();assert [r['frame_index'] for r in final['completed']]==[0,1]
    early=final['completed'][0]['observations'];later=final['completed'][1]['observations']
    assert max(o['completed_monotonic'] for o in early)>min(o['completed_monotonic'] for o in later)
    p.close()


def test_backpressure_timeout_is_explicit_and_bounded():
    entered=threading.Event();gate=threading.Event()
    class Slow(Backend):
        def recognize(self,f,r):entered.set();gate.wait(2);return super().recognize(f,r)
    p=pipeline(Slow(),limits=Limits(max_inflight_frames=1,queue_jobs=1))
    p.process_frame(frames()[0]);assert entered.wait(1)
    denied=p.process_frame(frames()[1],timeout=0.)
    assert not denied['accepted']
    assert len(p.pending)==1 and p.metrics['rejected_frames']==1
    assert p.diagnostics[-1]['affected_regions']==['all']
    gate.set();final=p.finish();assert final['readiness']['status']=='uncertain'
    p.close()


def test_gaps_and_interruption_prevent_complete_coverage_claim():
    p=pipeline(asynchronous=False)
    p.process_frame(frames()[0]);frame=frames()[1];frame.timestamp=3.
    p.process_frame(frame);assert p.metrics['timestamp_gaps']==1
    final=p.finish(interrupted=True)
    assert final['readiness']['status']=='uncertain'
    assert len(final['diagnostics'])>=2
    p.close()


def test_recognition_failure_preserves_order_and_uncertainty():
    class Broken(Backend):
        def recognize(self,f,r):raise RuntimeError('backend failure')
    p=pipeline(Broken(),asynchronous=False)
    row=p.process_frame(frames()[0]);assert row['completed'][0]['uncertainty']
    assert row['readiness']['status']=='uncertain'
    p.close()


@pytest.mark.local_artifacts('reports/M1.4-evidence/m14_boundary_270.jpg','reports/M1.4-evidence/m14_boundary_282.jpg')
def test_real_m14_workflow_matches_online_without_future_frames():
    backend=Backend();p=StreamingPipeline(backend,asynchronous=False,icons=False)
    root=FIXTURES.parent.parent
    expected=['move_selection','pokemon_selection','switch_selection','battle_animation']
    for i,(second,phase) in enumerate(zip([268,270,280,282],expected)):
        f=load_image(root/'reports/M1.4-evidence'/f'm14_boundary_{second}.jpg')
        f.source='workflow';f.index=i;f.timestamp=float(second)
        update=p.process_frame(f)['phase_update'];assert update['phase']==phase
        if i:assert update['transition']['to']==phase
    p.close()


def test_real_message_roi_small_change_schedules_new_read():
    class RecordingOCR:
        warnings=[]
        def read(self,image,bounds,*args,**kwargs):return Observation('test message',.9,bounds)
    image=load_image(FIXTURES/'battle_message.png').image
    backend=RegionBackend(RecordingOCR());p=StreamingPipeline(backend,asynchronous=False,icons=False)
    one=p.process_frame(Frame(image,'message',0,0.))
    different=image.copy()
    x1,y1,x2,y2=next(o['region'] for o in one['completed'][0]['observations'] if o['label']=='battle_message')
    different[y1+20:y1+24,x1+20:x1+24]=255-different[y1+20:y1+24,x1+20:x1+24]
    two=p.process_frame(Frame(different,'message',1,.1))
    assert any(o['label']=='battle_message' for o in two['completed'][0]['observations'])
    assert 'events' not in two['completed'][0]
    p.close()


def test_replay_uses_same_incremental_path_and_closes():
    p=pipeline(asynchronous=False);trace=[]
    replay(frames(),p,trace.append)
    assert [r['data']['frame_index'] for r in trace if r['type']=='observations']==[0,1,2]
    assert any(r['type']=='decision_settled' for r in trace)
    assert p.closed


def test_frame_is_frozen_before_async_return():
    gate=threading.Event();entered=threading.Event()
    class Pixel(Backend):
        def recognize(self,f,r):entered.set();gate.wait(2);return {'value':int(f.image[0,0,0])}
    p=pipeline(Pixel());frame=frames()[0];p.process_frame(frame);assert entered.wait(1)
    frame.image[:]=255;gate.set();result=p.finish()
    assert result['completed'][0]['observations'][0]['observation']['value']==0
    p.close()


def test_real_two_message_layouts_have_distinct_observations():
    p=StreamingPipeline(Backend(),asynchronous=False,icons=False)
    ids=[]
    for i,name in enumerate(['m15_message_transformation.png','m15_message_move.png']):
        image=load_image(FIXTURES/name).image
        row=p.process_frame(Frame(image,'two-real-messages',i,i*.2))
        message=next(o for o in row['completed'][0]['observations'] if o['label']=='battle_message')
        ids.append(message['observation_id'])
    assert ids[0]!=ids[1]
    p.close()


def test_new_decision_waits_for_prior_resolution_message():
    gate=threading.Event();entered=threading.Event()
    class Delayed(Backend):
        def recognize(self,f,r):
            if f.index==0:entered.set();gate.wait(2)
            return super().recognize(f,r)
    p=StreamingPipeline(Delayed(),planner=Planner(),icons=False,
                        phase_classifier=lambda image:('battle_message' if image[0,0,0]==0 else 'move_selection',.8,[],[]))
    p.process_frame(frames()[0]);assert entered.wait(1)
    decision=p.process_frame(frames()[1]);assert decision['readiness']['status']=='pending'
    assert decision['readiness']['capture_watermark']==1
    gate.set();p.finish();updates=p.decision_updates()
    assert len(updates)==1 and updates[0]['status']=='ready'
    p.close()


def test_message_priority_before_queued_routine_fields():
    entered=threading.Event();gate=threading.Event();calls=[]
    class Prioritized(Backend):
        def recognize(self,f,r):
            calls.append(r['label'])
            if len(calls)==1:entered.set();gate.wait(2)
            return {'value':'accepted'}
    class Plan:
        def plan(self,f,phase,include_icons):
            labels=['running','routine'] if f.index==0 else ['battle_message']
            return [{'label':label,'bounds':(0,0,10,10),'kind':'ocr',
                     'priority':0 if label=='battle_message' else 1,'required':True} for label in labels]
    p=StreamingPipeline(Prioritized(),planner=Plan(),icons=False,
                        phase_classifier=lambda im:('move_selection',.8,[],[]))
    p.process_frame(frames()[0]);assert entered.wait(1)
    p.process_frame(frames()[1]);gate.set();p.finish()
    assert calls==['running','battle_message','routine']
    p.close()


def test_memory_limits_and_bounded_diagnostics():
    p=pipeline(asynchronous=False,limits=Limits(max_frame_pixels=50,diagnostic_records=2))
    for f in frames():assert not p.process_frame(f)['accepted']
    assert len(p.diagnostics)==2 and p.metrics['diagnostic_overflow']==1
    assert p.coverage_uncertain
    p.close()


def test_message_lane_is_available_before_slow_icon_bundle():
    gate=threading.Event();entered=threading.Event()
    class DelayedIcon(Backend):
        def recognize(self,f,r):
            if r['kind']=='icon':entered.set();gate.wait(2)
            return {'value':'real visible message'}
    class MessagePlan:
        def plan(self,f,phase,include_icons=True):
            return [{'label':'battle_message','bounds':(0,0,10,10),'kind':'ocr','priority':0,'required':True},
                    {'label':'identity','bounds':(0,0,10,10),'kind':'icon','priority':2,'required':True}]
    p=StreamingPipeline(DelayedIcon(),planner=MessagePlan(),icons=True,phase_classifier=lambda im:('battle_message',.8,[],[]))
    p.process_frame(frames()[0]);assert entered.wait(1)
    messages=[]
    deadline=time.monotonic()+1
    while not messages and time.monotonic()<deadline:
        assert not p.poll();messages=p.poll_messages();time.sleep(.001)
    assert len(messages)==1 and len(p.pending)==1
    gate.set();full=p.finish()['completed'][0]
    assert messages[0]['observation_id'] in {o['observation_id'] for o in full['observations']}
    assert not p.poll_messages()  # once per message lane, stable ID across bundle reference
    p.close()


def test_text_mask_cache_preserves_glyph_changes_and_periodic_rechecks():
    class TextPlan:
        def plan(self,f,phase,include_icons=True):
            return [{'label':'own_hp_0_current','kind':'ocr','priority':1,'bounds':(0,0,10,10),
                     'required':True,'cache_policy':'white_glyphs'}]
    backend=Backend();p=StreamingPipeline(backend,planner=TextPlan(),asynchronous=False,
        limits=Limits(max_capture_gap=2.),phase_classifier=lambda im:('move_selection',.8,[],[]))
    base=np.zeros((10,10,3),dtype='uint8');base[2,1:9]=255
    p.process_frame(Frame(base,'text',0,0.))
    background=base.copy();background[0,0]=(255,0,0)
    result=p.process_frame(Frame(background,'text',1,.1))
    assert len(backend.calls)==1
    assert result['phase_update']['coalesced_regions'][0]['cache_method']=='exact_white_glyph_mask'
    glyph=background.copy();glyph[2,1]=0
    p.process_frame(Frame(glyph,'text',2,.2));assert len(backend.calls)==2
    p.process_frame(Frame(glyph,'text',3,1.3));assert len(backend.calls)==3
    p.close()


@pytest.mark.parametrize('text', ['击掌奇袭！', '龙之舞！', '对手的', 'Go!'])
def test_short_visible_text_is_preserved_without_length_or_language_gate(text):
    # Synthetic OCR responses; these are not new manually reviewed game labels.
    class OCR:
        warnings = []
        def read(self, *args, **kwargs):
            return Observation(value=text, confidence=.95)
    result = RegionBackend(OCR()).recognize(frames()[0],
        {'kind':'ocr', 'label':'battle_message', 'bounds':(0,0,10,10)})
    assert result['value'] == result['raw_text'] == text
    assert result['message_validation']['status'] == 'accepted'


def test_low_confidence_short_message_keeps_raw_evidence_and_uncertain_readiness():
    class OCR:
        warnings = []
        def read(self, *args, **kwargs):
            return Observation(value='对手的', confidence=.715)
    class Plan:
        def plan(self, *args, **kwargs):
            return [{'kind':'ocr', 'label':'battle_message', 'bounds':(0,0,10,10),
                     'priority':0, 'required':True}]
    p = StreamingPipeline(RegionBackend(OCR()), planner=Plan(), asynchronous=False,
                          phase_classifier=lambda im: ('move_selection', .8, [], []))
    result = p.process_frame(frames()[0])
    observation = result['completed'][0]['observations'][0]['observation']
    assert observation['value'] is None and observation['raw_text'] == '对手的'
    assert observation['message_validation']['reason'] == 'low_confidence'
    assert result['readiness']['status'] == 'uncertain'
    assert result['readiness']['pending_jobs'] == 0
    p.close()


@pytest.mark.parametrize('status', ['unresolved', 'ambiguous', 'unavailable'])
def test_unresolved_required_icons_do_not_become_ready(status):
    class IconBackend:
        def recognize(self, frame, region): return {'status':status}
    p = StreamingPipeline(IconBackend(), planner=Planner(('icon',)), icons=True,
                          asynchronous=False,
                          phase_classifier=lambda im: ('move_selection', .8, [], []))
    result = p.process_frame(frames()[0])
    assert result['readiness']['status'] == 'uncertain'
    assert p.decision_updates()[0]['status'] == 'uncertain'
    p.close()


@pytest.mark.local_artifacts('reports/m15-message-first-paced.jsonl')
def test_existing_replay_traces_preserve_reviewed_messages_in_capture_order():
    root = FIXTURES.parent.parent
    truth = json.loads((FIXTURES/'m15_message_ground_truth.json').read_text())['messages']
    for path in sorted((root/'reports').glob('m15-*.jsonl')):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        bundles = [r['data'] for r in rows if r['type'] == 'observations']
        assert len(bundles) == 110
        assert [b['capture_sequence'] for b in bundles] == list(range(110))
        messages = [o for b in bundles for o in b['observations'] if o['label']=='battle_message']
        assert [m['timestamp'] for m in messages] == sorted(m['timestamp'] for m in messages)
        assert len({m['observation_id'] for m in messages}) == len(messages)
        reviewed = []
        for expected in truth:
            observation = next(m for m in messages if m['timestamp']==expected['timestamp'])
            assert ''.join(observation['observation']['value'].split()) == ''.join(expected['expected_text'].split())
            reviewed.append(observation['timestamp'])
        assert reviewed == [178., 180.]
        lane = [r['data'] for r in rows if r['type']=='message_available']
        if lane:
            assert [m['observation_id'] for m in lane] == [m['observation_id'] for m in messages]
        assert rows[-1]['data']['readiness']['status'] == 'uncertain'
