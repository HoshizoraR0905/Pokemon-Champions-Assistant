"""Bounded live acquisition/monitoring independent of OCR backpressure.

Supply acquire() returning an owned or reusable Frame (None means source end).
Supply a prompt, thread-safe evidence sink; slow capture/sink callbacks themselves
can miss deadlines and are diagnosed. No phone transport or game control here.
"""
from dataclasses import replace
import hashlib
import queue
import threading
import time

from recognition import box
from streaming.monitoring import MonitoringRates, ROIMonitor, ROIS
from streaming.replay import replay


class LiveCapture:
    def __init__(self, acquire, sink, *, rates=None, capacity=4,
                 max_frame_pixels=3840*2160):
        if capacity < 1 or max_frame_pixels < 1:
            raise ValueError('Live capture buffer limits must be positive')
        self.acquire, self.sink = acquire, sink
        self.monitor = ROIMonitor(rates or MonitoringRates())
        self.buffer = queue.Queue(capacity)
        self.stop_event, self.done = threading.Event(), threading.Event()
        self.lock = threading.Lock()
        self.sink_lock = threading.Lock()
        self.max_frame_pixels = max_frame_pixels
        self.error = None
        self.loss_count = 0
        self.metrics = {'acquired_frames':0,'dropped_frames':0,'max_capture_buffer':0,
                        'monitor_checks':0,'deadline_misses':0}
        self.worker = threading.Thread(target=self._produce,daemon=True,name='live-capture-monitor')

    def emit(self, row):
        with self.sink_lock:
            self.sink(row)

    def _loss(self, reason, frame=None):
        with self.lock:
            self.loss_count += 1
            self.metrics['dropped_frames'] += int(frame is not None)
        self.emit({'type':'capture_loss','data':{'reason':reason,
            'frame_index':frame.index if frame else None,
            'timestamp':frame.timestamp if frame else None,'coverage_uncertain':True}})

    def _produce(self):
        period = 1/self.monitor.rates.acquisition_fps
        origin = target = time.monotonic()
        try:
            while not self.stop_event.is_set():
                self.stop_event.wait(max(0,target-time.monotonic()))
                if self.stop_event.is_set():break
                frame = self.acquire()
                if frame is None:break
                captured = frame.capture_monotonic if frame.capture_monotonic is not None else time.monotonic()
                self.metrics['acquired_frames'] += 1
                if frame.image.shape[0]*frame.image.shape[1] > self.max_frame_pixels:
                    self._loss('live_frame_exceeds_memory_limit',frame)
                    target += period
                    continue
                frame = replace(frame,image=frame.image.copy(),capture_monotonic=captured,
                    timestamp=frame.timestamp if frame.timestamp is not None else captured-origin,
                    metadata={**frame.metadata,'capture_adapter':'live_acquisition'})
                monitoring = self.monitor.inspect(frame)
                self.metrics['monitor_checks'] += 1
                self.emit({'type':'capture_monitor','data':{'source':frame.source,
                    'frame_index':frame.index,'timestamp':frame.timestamp,
                    'capture_monotonic':captured,'monitoring':monitoring}})
                # Preserve changed message/HUD/condition crops before admission.
                # A dropped full frame can then still carry reviewable evidence;
                # no cropped ROI is interpreted as a gameplay event.
                for label in monitoring['changed_rois']:
                    region={'label':label,'bounds':box(frame.image,ROIS[label])}
                    candidate, _ = self.monitor.preserve_candidate(frame,region,'capture_candidate_pending')
                    candidate['candidate_id'] = hashlib.sha256(
                        f'{frame.source}:{frame.index}:{label}:{candidate["sha256"]}'.encode()).hexdigest()
                    self.emit({'type':'capture_candidate','data':candidate})
                try:
                    self.buffer.put_nowait(frame)
                except queue.Full:
                    try:
                        dropped = self.buffer.get_nowait()
                    except queue.Empty:
                        dropped = None  # consumer drained between admission and eviction
                    if dropped is not None:
                        self._loss('live_capture_buffer_overflow',dropped)
                    self.buffer.put_nowait(frame)
                self.metrics['max_capture_buffer'] = max(self.metrics['max_capture_buffer'],self.buffer.qsize())
                target += period
                if time.monotonic() > target+period:
                    self.metrics['deadline_misses'] += 1
                    self._loss('capture_or_sink_deadline_miss')
                    target = time.monotonic()
        except BaseException as exc:
            self.error = exc
        finally:
            self.done.set()

    def frames(self, pipeline):
        self.worker.start()
        reported_losses = 0
        try:
            while not self.done.is_set() or not self.buffer.empty():
                with self.lock:
                    count = self.loss_count
                if count != reported_losses:
                    pipeline.mark_interruption('live_capture_evidence_loss',
                        evidence={'new_losses':count-reported_losses,'total_losses':count})
                    reported_losses = count
                try:
                    frame = self.buffer.get(timeout=.01)
                except queue.Empty:
                    continue
                yield frame
            with self.lock:
                count = self.loss_count
            if count != reported_losses:
                pipeline.mark_interruption('live_capture_evidence_loss',evidence={'total_losses':count})
            if self.error:
                pipeline.mark_interruption('live_capture_or_sink_failure')
                raise self.error
        finally:
            self.stop_event.set()
            self.worker.join(timeout=1.)
            if self.worker.is_alive():
                pipeline.mark_interruption('capture_callback_did_not_stop')


def run_live(acquire, pipeline, sink, *, rates=None, capacity=4):
    """Same recognition/order/readiness path; acquisition is never queued behind OCR."""
    capture = LiveCapture(acquire,sink,rates=rates,capacity=capacity,
                          max_frame_pixels=pipeline.limits.max_frame_pixels)
    try:
        replay(capture.frames(pipeline),pipeline,capture.emit)
    finally:
        capture.stop_event.set()
        if capture.worker.ident is not None:
            capture.worker.join(timeout=1.)
    capture.emit({'type':'live_capture_end','data':{
        'metrics':capture.metrics,'monitoring_metrics':capture.monitor.metrics}})
    return capture.metrics
