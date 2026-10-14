"""Incremental evidence pipeline. No gameplay events or future-frame smoothing."""
from collections import deque
from dataclasses import dataclass, field
import hashlib
import math
import queue
import threading
import time

from recognition import color_fraction
from recognition.phases import classify_phase
from streaming.recognition import RegionPlanner


@dataclass
class Limits:
    max_inflight_frames: int = 4
    queue_jobs: int = 64
    diagnostic_records: int = 128
    max_frame_pixels: int = 3840 * 2160
    max_regions_per_frame: int = 128
    field_recheck_seconds: float = 1.
    max_capture_gap: float = .5
    readiness_target_seconds: float = 1.
    def __post_init__(self):
        if min(self.max_inflight_frames,self.queue_jobs,self.diagnostic_records,self.max_frame_pixels,self.max_regions_per_frame) < 1:
            raise ValueError('Buffer limits must be positive')
        if not math.isfinite(self.field_recheck_seconds) or self.field_recheck_seconds <= 0:
            raise ValueError('Field recheck interval must be positive and finite')
        if not math.isfinite(self.max_capture_gap) or self.max_capture_gap <= 0:
            raise ValueError('Capture gap limit must be finite and positive')
        if not math.isfinite(self.readiness_target_seconds) or self.readiness_target_seconds <= 0:
            raise ValueError('Readiness target must be finite and positive')


@dataclass
class PendingFrame:
    sequence: int
    evidence: dict
    remaining: int
    observations: list = field(default_factory=list)
    uncertainty: list = field(default_factory=list)
    message_remaining: int = 0


def digest_region(image, bounds):
    x1,y1,x2,y2 = bounds
    crop = image[y1:y2,x1:x2]
    return hashlib.sha256(str(crop.shape).encode()+crop.tobytes()).hexdigest()


def recognition_signature(image, region):
    raw = digest_region(image,region['bounds'])
    if region.get('cache_policy') != 'white_glyphs' or region['priority'] == 0:
        return raw,raw,'raw_pixels'
    import cv2
    import numpy as np
    x1,y1,x2,y2 = region['bounds']
    hsv = cv2.cvtColor(image[y1:y2,x1:x2],cv2.COLOR_BGR2HSV)
    white = (hsv[:,:,1] < 100) & (hsv[:,:,2] > 150)
    # Only the known light-text battle/PP/name regions use this policy. Dark
    # configuration text and insufficient/bright scenery fall back to raw pixels.
    if 5 < int(white.sum()) < white.size*.5:
        glyph = hashlib.sha256(str(white.shape).encode()+np.packbits(white).tobytes()).hexdigest()
        return glyph,raw,'exact_white_glyph_mask'
    return raw,raw,'raw_pixels'


def decision_visible(image, phase):
    if phase == 'move_selection':
        return True
    # A battle HUD alone can appear during resolution. Require command controls.
    return phase == 'battle_screen' and min(color_fraction(image,r,'purple') for r in
        [(.84,.54,.88,.63), (.81,.74,.86,.83)]) > .25


class StreamingPipeline:
    """Single producer; one OCR worker and optionally one icon worker.

    process_frame returns completed capture-ordered bundles plus an immediate
    provisional UI update and a readiness snapshot. poll() drains bounded results.
    Default backpressure blocks and drains; timeout rejection is explicit loss.
    The producer/capture adapter must report upstream loss via mark_interruption.
    """
    def __init__(self, backend, *, asynchronous=True, icons=False, limits=None,
                 planner=None, phase_classifier=classify_phase, clock=time.monotonic):
        self.backend, self.asynchronous, self.icons = backend, asynchronous, icons
        self.limits = limits or Limits()
        self.planner = planner or RegionPlanner()
        self.classifier, self.clock = phase_classifier, clock
        self.lock = threading.Condition()
        self.queues = {kind:queue.PriorityQueue(self.limits.queue_jobs) for kind in
                       (['ocr','icon'] if icons else ['ocr'])}
        self.pending = {}
        self.sequence, self.next_output = 0,0
        self.next_message_output = 0
        self.message_output = deque(maxlen=self.limits.diagnostic_records)
        self.job_sequence = 0
        self.last_source, self.last_index, self.last_timestamp = None,None,None
        self.previous_phase, self.previous_evidence = None,None
        self.segment = None
        self.last_full_digest = None
        self.previous_decision = False
        self.region_cache = {}
        self.last_regions = set()
        self.decision = None
        self.decision_tickets = deque()
        self.settled_decisions = deque(maxlen=self.limits.diagnostic_records)
        self.coverage_uncertain = False
        self.diagnostics = deque(maxlen=self.limits.diagnostic_records)
        self.metrics = {'captured_frames':0,'accepted_frames':0,'duplicate_frames':0,
                        'rejected_frames':0,'coalesced_regions':0,'submitted_jobs':0,
                        'completed_jobs':0,'max_inflight_frames':0,'max_queue_depth':0,
                        'timestamp_gaps':0,'diagnostic_overflow':0}
        self.closed = False
        self.threads = []
        if asynchronous:
            for kind in self.queues:
                worker = threading.Thread(target=self._worker,args=(kind,),daemon=True,
                                          name=f'recognition-{kind}')
                worker.start(); self.threads.append(worker)

    def _diagnose(self, kind, **details):
        if len(self.diagnostics) == self.diagnostics.maxlen:
            self.metrics['diagnostic_overflow'] += 1
        self.diagnostics.append({'kind':kind,'processing_monotonic':self.clock(),**details})

    def mark_interruption(self, reason, *, affected_regions=('all',), evidence=None):
        with self.lock:
            self.coverage_uncertain = True
            self._diagnose('potentially_missed_observations',reason=reason,
                           affected_regions=list(affected_regions),evidence=evidence)
            self.region_cache.clear(); self.last_regions.clear()

    def _worker(self, kind):
        jobs = self.queues[kind]
        while True:
            item = jobs.get()
            try:
                if item[2] is None:
                    return
                self._execute(item[2])
            finally:
                jobs.task_done()

    def _execute(self, job):
        seq, frame, region, observation_id, captured = job
        started = self.clock()
        try:
            observation = self.backend.recognize(frame,region)
            failure = None
        except Exception as exc:
            observation = {'value':None,'provenance':'recognition_failure','error':str(exc)}
            failure = str(exc)
        completed = self.clock()
        row = {'observation_id':observation_id,'source':frame.source,'frame_index':frame.index,
               'timestamp':frame.timestamp,'capture_monotonic':captured,
               'started_monotonic':started,'completed_monotonic':completed,
               'recognition_seconds':completed-started, 'availability_seconds':completed-captured,
               'region':region['bounds'],'category':region['kind'],'label':region['label'],
               'observation':observation,'provenance':'direct_visible_region_recognition'}
        with self.lock:
            state = self.pending[seq]
            state.observations.append(row)
            state.remaining -= 1
            if region['priority'] == 0:
                state.message_remaining -= 1
            self.metrics['completed_jobs'] += 1
            unresolved = (observation.get('status') in {'unresolved','ambiguous','unavailable'}
                          if region['kind']=='icon' else observation.get('value') is None)
            if failure or (unresolved and (region.get('required') or observation.get('raw_text'))):
                state.uncertainty.append({'label':region['label'],'reason':failure or 'unresolved_recognition'})
                self.coverage_uncertain = True
            self.lock.notify_all()

    def _collect_locked(self):
        output = []
        self._messages_locked()
        while self.next_output in self.pending and self.pending[self.next_output].remaining == 0:
            state = self.pending.pop(self.next_output)
            available = self.clock()
            bundle = {**state.evidence,'observations':sorted(state.observations,key=lambda o:o['observation_id']),
                      'uncertainty':state.uncertainty,'ordered_available_monotonic':available,
                      'ordered_availability_seconds':available-state.evidence['capture_monotonic']}
            output.append(bundle); self.next_output += 1
        while self.decision_tickets and self.decision_tickets[0]['capture_watermark'] < self.next_output:
            ticket = self.decision_tickets.popleft()
            ticket['settled_monotonic'] = self.clock()
            latency = ticket['settled_monotonic']-ticket['capture_monotonic']
            snapshot = {**ticket,'status':'uncertain' if self.coverage_uncertain else 'ready',
                        'pending_jobs':0,'coverage_uncertain':self.coverage_uncertain,
                        'readiness_latency_seconds':latency,
                        'processing_target_met':latency <= self.limits.readiness_target_seconds}
            if len(self.settled_decisions) == self.settled_decisions.maxlen:
                self._diagnose('decision_output_overflow',decision_id=ticket['decision_id'])
                self.coverage_uncertain = True
            self.settled_decisions.append(snapshot)
        return output

    def _messages_locked(self):
        # Independent event-time lane: fields/icons cannot hold up completed
        # messages. IDs also occur in full bundles; they identify the same evidence.
        while (self.next_message_output in self.pending and
               self.pending[self.next_message_output].message_remaining == 0):
            message_state = self.pending[self.next_message_output]
            for row in message_state.observations:
                if row['label'] != 'battle_message':
                    continue
                available = self.clock()
                message = {**row,'message_ordered_available_monotonic':available,
                           'message_availability_seconds':available-row['capture_monotonic']}
                if len(self.message_output) == self.message_output.maxlen:
                    self.coverage_uncertain = True
                    self._diagnose('message_lane_output_overflow',observation_id=row['observation_id'],
                                   reason='Consumer did not drain messages; evidence still in full bundles')
                self.message_output.append(message)
            self.next_message_output += 1

    def poll_messages(self):
        with self.lock:
            self._messages_locked()
            messages = list(self.message_output)
            self.message_output.clear()
            return messages

    def decision_updates(self):
        with self.lock:
            updates = list(self.settled_decisions)
            self.settled_decisions.clear()
            return updates

    def poll(self):
        with self.lock:
            return self._collect_locked()

    def readiness(self):
        with self.lock:
            if self.decision is None:
                return {'status':'no_decision','capture_watermark':self.sequence-1,
                        'pending_jobs':sum(s.remaining for s in self.pending.values()),
                        'processing_watermark_sequence':self.next_output-1,
                        'captured_frame_count':self.metrics['captured_frames'],
                        'coverage_uncertain':self.coverage_uncertain}
            watermark = self.decision['capture_watermark']
            remaining = sum(s.remaining for seq,s in self.pending.items() if seq<=watermark)
            unordered = sum(1 for seq in self.pending if seq<=watermark)
            pending = remaining > 0 or unordered > 0
            status = 'pending' if pending else 'uncertain' if self.coverage_uncertain else 'ready'
            settled = self.decision.get('settled_monotonic')
            latency = settled-self.decision['capture_monotonic'] if settled is not None else None
            return {**self.decision,'status':status,'pending_jobs':remaining,
                    'unordered_frames':unordered,'coverage_uncertain':self.coverage_uncertain,
                    'processing_watermark_sequence':self.next_output-1,
                    'captured_frame_count':self.metrics['captured_frames'],
                    'readiness_latency_seconds':latency,
                    'target_seconds':self.limits.readiness_target_seconds,
                    'processing_target_met':latency <= self.limits.readiness_target_seconds if latency is not None else None,
                    'semantics':'ready covers captured evidence through this watermark, not all gameplay events'}

    def process_frame(self, frame, *, timeout=None):
        if self.closed:
            raise ValueError('Stream is closed')
        if timeout is not None and (not math.isfinite(timeout) or timeout < 0):
            raise ValueError('Backpressure timeout must be nonnegative and finite')
        if frame.timestamp is None or not math.isfinite(frame.timestamp) or frame.timestamp < 0:
            raise ValueError('Streaming frames require finite nonnegative source timestamps')
        if self.last_source is not None and frame.source != self.last_source:
            raise ValueError('Use a new pipeline for a new source/session')
        if self.last_index is not None and frame.index == self.last_index:
            if hashlib.sha256(frame.image.tobytes()).hexdigest() != self.last_full_digest:
                self.mark_interruption('conflicting_duplicate_capture_id',evidence={'index':frame.index})
                raise ValueError('Duplicate capture ID has different image payload')
            self.metrics['duplicate_frames'] += 1
            return {'accepted':False,'duplicate':True,'completed':self.poll(),'readiness':self.readiness()}
        if self.last_index is not None and (frame.index < self.last_index or frame.timestamp <= self.last_timestamp):
            raise ValueError('Capture sequence and timestamps must increase')
        captured = frame.capture_monotonic if frame.capture_monotonic is not None else self.clock()
        if not math.isfinite(captured) or captured > self.clock()+.001:
            raise ValueError('Capture monotonic timestamp must use the pipeline clock')
        self.metrics['captured_frames'] += 1
        if frame.image.shape[0]*frame.image.shape[1] > self.limits.max_frame_pixels:
            self.metrics['rejected_frames'] += 1
            self.mark_interruption('image_exceeds_frame_memory_limit',evidence={'index':frame.index})
            return {'accepted':False,'completed':self.poll(),'readiness':self.readiness()}
        # A blocked producer does not accumulate images internally. The adapter
        # owns at most this one additional raw frame and must report upstream loss.
        deadline = None if timeout is None else self.clock()+timeout
        completed = []
        with self.lock:
            while len(self.pending) >= self.limits.max_inflight_frames:
                completed.extend(self._collect_locked())
                if len(self.pending) < self.limits.max_inflight_frames:
                    break
                if deadline is not None and self.clock() >= deadline:
                    self.metrics['rejected_frames'] += 1; self.coverage_uncertain = True
                    self._diagnose('rejected_frame',source=frame.source,index=frame.index,
                                   timestamp=frame.timestamp,affected_regions=['all'],reason='backpressure_timeout',
                                   image_sha256=hashlib.sha256(frame.image.tobytes()).hexdigest())
                    return {'accepted':False,'completed':completed,'readiness':self.readiness()}
                self.lock.wait(.01)
        began = self.clock()
        phase, confidence, evidence, warnings = self.classifier(frame.image)
        regions = self.planner.plan(frame,phase,include_icons=self.icons)
        if len(regions) > self.limits.max_regions_per_frame:
            self.metrics['rejected_frames'] += 1
            self.mark_interruption('region_plan_exceeds_limit',evidence={'index':frame.index})
            return {'accepted':False,'completed':completed+self.poll(),'readiness':self.readiness()}
        decision = decision_visible(frame.image,phase)
        seq = self.sequence
        info = {'source':frame.source,'frame_index':frame.index,'timestamp':frame.timestamp,
                'capture_sequence':seq,'capture_monotonic':captured,'phase':phase,
                'image_sha256':hashlib.sha256(frame.image.tobytes()).hexdigest(),
                'phase_confidence':confidence,'phase_evidence':evidence,'phase_warnings':warnings,
                'classification_seconds':self.clock()-began,
                'capture_to_classification_seconds':self.clock()-captured,
                'capture_metadata':frame.metadata.copy(),'coalesced_regions':[],
                'recognition_scope':{'ocr':'existing supported text regions plus high-recall message probes',
                                     'icons_enabled':self.icons,'gameplay_events':False}}
        with self.lock:
            if self.last_timestamp is not None and frame.timestamp-self.last_timestamp > self.limits.max_capture_gap:
                self.metrics['timestamp_gaps'] += 1; self.coverage_uncertain = True
                self._diagnose('timestamp_gap',earliest=self.last_timestamp,latest=frame.timestamp,
                               affected_regions=['messages','hp','status','ui_transitions'])
                self.region_cache.clear()
            if phase == 'unknown':
                self.coverage_uncertain = True
            if self.previous_phase is not None and phase != self.previous_phase:
                info['transition'] = {'from':self.previous_phase,'to':phase,
                    'earliest_timestamp':self.previous_evidence['timestamp'],'latest_timestamp':frame.timestamp,
                    'supporting_frame_indices':[self.previous_evidence['frame_index'],frame.index],
                    'provenance':'observed_adjacent_frames' if frame.index-self.previous_evidence['frame_index']==1
                                 else 'inferred_across_captured_samples',
                    'provisional':phase=='unknown' or self.previous_phase=='unknown'}
            if self.segment is None or self.segment['phase'] != phase:
                if self.segment is not None:
                    info['finalized_segment'] = {**self.segment,'finalized':True,
                        'end_earliest_timestamp':self.segment['last_observed_timestamp'],
                        'end_latest_timestamp':frame.timestamp}
                self.segment = {'segment_id':f'{frame.source}:{frame.index}', 'phase':phase,
                    'start_timestamp':frame.timestamp,'start_frame_index':frame.index,'sample_count':0,
                    'confidence_sum':0.,'provisional':phase=='unknown'}
            self.segment['sample_count'] += 1
            self.segment['confidence_sum'] += confidence
            self.segment['last_observed_timestamp'] = frame.timestamp
            self.segment['last_frame_index'] = frame.index
            info['segment_update'] = {**self.segment,'finalized':False}
            current_keys = {(r['kind'],r['label']) for r in regions}
            for absent in self.last_regions-current_keys:
                self.region_cache.pop(absent,None)  # message clear/reappearance creates a new observation
            jobs = []
            for region in regions:
                key = region['kind'],region['label']
                digest,raw_digest,cache_method = recognition_signature(frame.image,region)
                previous = self.region_cache.get(key)
                if (previous and previous[0]==digest and phase==self.previous_phase
                        and (cache_method=='raw_pixels' or frame.timestamp-previous[2]<self.limits.field_recheck_seconds)):
                    info['coalesced_regions'].append({'label':region['label'],'evidence_observation_id':previous[1],
                                                       'cache_method':cache_method,'raw_region_sha256':raw_digest})
                    self.metrics['coalesced_regions'] += 1
                    continue
                oid = hashlib.sha256(f'{frame.source}:{frame.index}:{key}:{digest}'.encode()).hexdigest()
                self.region_cache[key] = digest,oid,frame.timestamp
                jobs.append((seq,frame,region,oid,captured))
            self.pending[seq] = PendingFrame(seq,info,len(jobs),message_remaining=sum(j[2]['priority']==0 for j in jobs))
            self.sequence += 1
            self.metrics['accepted_frames'] += 1
            self.metrics['max_inflight_frames'] = max(self.metrics['max_inflight_frames'],len(self.pending))
            self.last_source,self.last_index,self.last_timestamp = frame.source,frame.index,frame.timestamp
            self.previous_phase,self.previous_evidence = phase,info
            self.last_full_digest = hashlib.sha256(frame.image.tobytes()).hexdigest()
            self.last_regions = current_keys
            if decision and not self.previous_decision:
                self.decision = {'decision_id':f'{frame.source}:{frame.index}',
                                 'capture_watermark':seq,'timestamp':frame.timestamp,'capture_monotonic':captured}
                self.decision_tickets.append(self.decision)
            self.previous_decision = decision
        # Freeze ownership before returning to a capture adapter with reusable buffers.
        if jobs:
            from dataclasses import replace
            frozen = replace(frame,image=frame.image.copy())
            jobs = [(s,frozen,r,oid,c) for s,_,r,oid,c in jobs]
        for job in jobs:
            self.metrics['submitted_jobs'] += 1
            if not self.asynchronous:
                self._execute(job)
            else:
                kind = job[2]['kind']
                self.job_sequence += 1
                # Queue admission blocks rather than deleting a message/HP job.
                self.queues[kind].put((job[2]['priority'],self.job_sequence,job))
                self.metrics['max_queue_depth'] = max(self.metrics['max_queue_depth'],
                                                     sum(q.qsize() for q in self.queues.values()))
        completed.extend(self.poll())
        return {'accepted':True,'phase_update':info,'completed':completed,'readiness':self.readiness()}

    def finish(self, *, interrupted=False):
        if interrupted:
            self.mark_interruption('stream_interrupted_before_complete_capture')
        if self.asynchronous:
            for jobs in self.queues.values():
                jobs.join()
        result = self.poll()
        return {'completed':result,'readiness':self.readiness(),'metrics':dict(self.metrics),
                'diagnostics':list(self.diagnostics),
                'final_segment':{**self.segment,'finalized':True,'end_reason':'source_end'} if self.segment else None}

    def close(self):
        if self.closed:
            return
        self.finish()
        if self.asynchronous:
            for jobs in self.queues.values():
                jobs.put((99,0,None))
            for worker in self.threads:
                worker.join()
        self.closed = True
