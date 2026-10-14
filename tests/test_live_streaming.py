from dataclasses import replace
import threading
import time

import numpy as np
import pytest
from capture import Frame
from streaming import Limits, StreamingPipeline
from streaming.monitoring import MonitoringRates
from streaming.live import run_live
from streaming.replay import replay


class Planner:
    def plan(self,frame,phase,include_icons=False):
        return [{'kind':'ocr','label':'battle_message','priority':0,'required':True,'bounds':(0,0,10,10)}]


class Backend:
    def recognize(self,frame,region):return {'value':str(frame.index),'confidence':1.}


def pipeline(backend=None,**kwargs):
    return StreamingPipeline(backend or Backend(),planner=Planner(),
                             phase_classifier=lambda im:('move_selection',.8,[],[]),**kwargs)


def test_live_capture_and_monitor_continue_while_ocr_is_blocked():
    model_entered=threading.Event();release=threading.Event();acquired_all=threading.Event()
    rows=[];rows_lock=threading.Lock();counter=0;errors=[]
    shared=np.zeros((100,217,3),np.uint8)
    class Slow:
        def recognize(self,frame,region):
            model_entered.set();assert release.wait(3.)
            return {'value':int(frame.image[0,0,0])}
    def acquire():
        nonlocal counter
        if counter==8:
            acquired_all.set();return None
        shared[:]=counter
        result=Frame(shared,'live-test',counter,counter*.01)
        counter+=1
        return result
    def sink(row):
        with rows_lock:rows.append(row)
    p=pipeline(Slow(),limits=Limits(max_inflight_frames=1,queue_jobs=1))
    def run():
        try:run_live(acquire,p,sink,rates=MonitoringRates(acquisition_fps=100.,message_fps=100.),capacity=2)
        except BaseException as exc:errors.append(exc)
    worker=threading.Thread(target=run)
    worker.start()
    try:
        assert model_entered.wait(1.)
        assert acquired_all.wait(2.)  # acquire() did not wait for the OCR gate
        with rows_lock:
            monitors=[r for r in rows if r['type']=='capture_monitor']
            losses=[r for r in rows if r['type']=='capture_loss']
            controls=[r for r in rows if r['type']=='capture_candidate' and r['data']['label']=='controls']
        assert len(monitors)==8 and losses
        assert controls  # a brief decision interface must survive full-frame eviction
    finally:
        release.set();worker.join(3.)
    assert not worker.is_alive() and not errors
    assert p.closed and p.coverage_uncertain
    captures=[r['data']['phase_update'] for r in rows if r['type']=='capture_update']
    assert [c['frame_index'] for c in captures]==sorted(c['frame_index'] for c in captures)
    first=next(r['data'] for r in rows if r['type']=='observations')
    assert first['observations'][0]['observation']['value']==0  # reusable camera buffer was frozen
    final=rows[-1]['data']['metrics']
    assert final['max_capture_buffer']<=2 and final['dropped_frames']>0


def test_real_capture_clock_is_not_replaced_by_replay_dispatch_clock():
    p=pipeline(asynchronous=False);rows=[]
    captured=time.monotonic()-.5
    frame=Frame(np.zeros((10,10,3),np.uint8),'live-clock',0,0.,capture_monotonic=captured)
    replay([frame],p,rows.append)
    result=next(r['data'] for r in rows if r['type']=='observations')
    assert result['capture_monotonic']==captured
    assert result['ordered_availability_seconds']>=.5


def test_live_source_failure_is_uncertain_and_closes_pipeline():
    def acquire():raise RuntimeError('camera disconnected')
    p=pipeline(asynchronous=False)
    with pytest.raises(RuntimeError,match='camera disconnected'):
        run_live(acquire,p,lambda row:None)
    assert p.closed and p.coverage_uncertain
