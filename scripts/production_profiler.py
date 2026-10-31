"""Transparent opt-in timing of the canonical event-driven acquisition.

Only the calling thread is timed. FFmpeg runs concurrently; decoder-next wait is
not FFmpeg CPU time. Leaf counters and exclusive spans prevent nested double
counting. Source time is retained separately from monotonic execution time.
"""
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from functools import wraps
import json
import time


class Recorder:
    def __init__(self, folder, clock=time.perf_counter):
        self.folder=folder;folder.mkdir(parents=True,exist_ok=True)
        self.clock=clock;self.origin=clock();self.stack=[];self.source=None
        self.purpose='unclassified';self.stage='startup';self.overhead=0.;self.operations=0
        self.stream=(folder/'operations.jsonl').open('x',buffering=1)
        self.frames=(folder/'frames.jsonl').open('x',buffering=1)
        self.frame=None;self.frame_began=None;self.record_scope=None;self.adapt_scope=None
        self.in_replay=False;self.in_adaptation=False;self.restores=[]

    def begin(self,name,source=None,metadata=None):
        node=dict(name=name,start=self.clock(),child=0.,source=deepcopy(self.source if source is None else source),
                  purpose=self.purpose,stage=self.stage,metadata=metadata or {})
        self.stack.append(node);return node

    def end(self,node,counters=None):
        end=self.clock();assert self.stack[-1] is node,node['name'];self.stack.pop()
        inclusive=end-node['start'];exclusive=inclusive-node['child']
        row=dict(operation_id=self.operations,module=node['name'],source=node['source'],purpose=node['purpose'],
                 stage=node['stage'],execution_start=node['start']-self.origin,execution_end=end-self.origin,
                 inclusive_seconds=inclusive,exclusive_seconds=max(0.,exclusive),counters=counters or {},**node['metadata'])
        self.operations+=1;self.stream.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
        finished=self.clock();self.overhead+=finished-end
        if self.stack:self.stack[-1]['child']+=finished-node['start']
        return row

    @contextmanager
    def span(self,name,**kwargs):
        node=self.begin(name,**kwargs)
        try:yield node
        finally:self.end(node)

    def patch(self,obj,name,label,*,purpose=None,counter_keys=(),source=None,after=None):
        original=getattr(obj,name)
        @wraps(original)
        def wrapped(*args,**kwargs):
            entry=self.clock();old_source=self.source;old_purpose=self.purpose
            if source:self.source=source(args,kwargs)
            if purpose:self.purpose=purpose(args,kwargs) if callable(purpose) else purpose
            counts=getattr(args[0],'counts',{}) if args else {}
            before={k:counts.get(k,0) for k in counter_keys}
            metadata={}
            if label=='ocr_read':
                bounds=tuple(args[2] if len(args)>2 else kwargs['bounds'])
                metadata['bounds']=list(bounds)
                if self.purpose=='active_hud':
                    from recognition.command_checkpoint import SLOT_REGIONS
                    from recognition import box
                    metadata['slot']=next((slot for slot,(_,_,roi) in SLOT_REGIONS.items()
                                            if box(args[1],roi)==bounds),None)
                    self.purpose='hud_identity_name' if metadata['slot'] else 'hud_hp'
            node=self.begin(label,metadata=metadata);self.overhead+=node['start']-entry
            result=None
            try:
                result=original(*args,**kwargs)
                return result
            finally:
                delta={k:counts.get(k,0)-before[k] for k in counter_keys}
                if label=='ocr_read' and result is not None:
                    node['metadata']['raw_text']=getattr(result,'raw_text',None)
                if after and result is not None:after(result,args,kwargs)
                self.end(node,delta)
                self.source=old_source;self.purpose=old_purpose
        setattr(obj,name,wrapped);self.restores.append((obj,name,original))

    def start_frame(self,raw):
        self.source=dict(timestamp=raw['timestamp'],source_id=raw['source_id'],source_pts=raw['source_pts'],
                         source_time_base=raw['source_time_base'])
        self.frame=dict(**self.source,target_timestamp=raw['target_timestamp'])
        self.frame_began=self.clock()

    def finish_frame(self):
        if self.frame is None:return
        self.frame['processing_wall_seconds']=self.clock()-self.frame_began
        started=self.clock();self.frames.write(json.dumps(self.frame,separators=(',',':'))+'\n');self.overhead+=self.clock()-started
        self.frame=None;self.frame_began=None;self.source=None

    def finish_record(self):
        if self.record_scope:
            self.end(self.record_scope);self.record_scope=None;self.source=None

    def finish_adapt(self):
        if self.adapt_scope:
            self.end(self.adapt_scope);self.adapt_scope=None;self.source=None

    def install(self):
        import recognition.identity_modes as modes
        import recognition.fast_video as video
        import recognition.event_report as report
        import recognition.command_checkpoint as command
        import recognition.event_schedule as schedule
        import recognition.ui_regions as ui
        import recognition.onnx_ocr as onnx
        import recognition.icons as icons
        import recognition.sprite_shape as shape
        import recognition.message_occurrences as occurrences
        import tracking.command_reconciliation as reconciliation
        import tracking.state_engine as state
        from battle_events.parser import EventParser
        self.patch(modes,'read_hp','hud_hp_reading',purpose='hud_hp')
        self.patch(modes.EntryVerifier,'verify','identity_verification',purpose='development_identity_verification')
        self.patch(modes.EntryVerifier,'observe_prefix','verification_prefix_reconstruction',purpose='development_identity_verification')
        self.patch(video,'analyze','pipeline')
        self.patch(video.CachedOCR,'__init__','ocr_adapter_init')
        self.patch(video.CachedIcons,'__init__','icon_adapter_init')
        self.patch(onnx.ONNXOCRBackend,'__init__','ocr_model_load')
        self.patch(onnx.ONNXOCRBackend,'predict','ocr_inference')
        self.patch(icons.IconRecognizer,'__init__','icon_model_load')
        self.patch(icons.IconRecognizer,'identify','icon_default_inference')
        self.patch(shape,'identify_shape','icon_silhouette_inference')
        self.patch(video.CachedOCR,'read','ocr_read',counter_keys=('ocr_read_requests','ocr_region_reads_reused'))
        self.patch(video.CachedOCR,'predict','ocr_predict',counter_keys=('ocr_prediction_requests','ocr_exact_cache_hits','ocr_invocations_attempted','ocr_invocations_performed','ocr_seconds'))
        self.patch(video.CachedIcons,'identify','icon_identify',counter_keys=('icon_region_reuses','icon_exact_cache_hits','icon_invocations_attempted','icon_invocations_performed','icon_seconds'))
        def inspected(result,*unused):
            if self.frame is not None:
                self.frame['ui']=dict(phase=result['phase'],confidence=result['confidence'],message_visible=result['message_visible'])
        self.patch(video,'inspect','ui_detection',after=inspected)
        self.patch(schedule,'command_label','command_label_detection',after=lambda r,*_:self.frame.update(command_label=r) if self.frame is not None else None)
        self.patch(schedule.EventInspection,'monitor','inspection_schedule',after=lambda r,*_:self.frame.update(inspected=bool(r)) if self.frame is not None else None)
        self.patch(schedule.IdentitySchedule,'acquire_trainers','trainer_acquisition',purpose='trainer_ids')
        self.patch(schedule.IdentitySchedule,'acquire_team','team_acquisition',purpose='team_roster_configuration')
        self.patch(modes,'read_hp','hud_acquisition',purpose='active_hud')
        self.patch(ui,'read_message','message_reading',purpose='battle_message')
        self.patch(occurrences.MessageOccurrences,'observe','message_occurrences',purpose='battle_message')
        self.patch(EventParser,'parse','event_parsing')
        self.patch(command,'inspect_command','w_detection',after=lambda r,*_:self.frame.update(w_detection=r) if self.frame is not None else None)
        self.patch(command.CommandCheckpointSchedule,'observe','w_schedule')
        self.patch(command,'capture_checkpoint_huds','w_capture',purpose='w_independent_names')
        self.patch(command,'schedule_checkpoint','w_schedule_capture')
        self.patch(reconciliation,'transition','w_reconciliation')
        self.patch(state,'hash_state','state_hash')
        self.patch(state.StateEngine,'_transition','state_transition')
        self.patch(report,'write_viewer','viewer_export')
        # These scopes separate delayed execution time from the originating frame.
        original_replay=state.StateEngine.replay
        @wraps(original_replay)
        def replay(engine,*,snapshot_callback=None):
            previous=(self.source,self.stage);self.source=None;self.stage='reconstruction';self.in_replay=True
            node=self.begin('state_reconstruction')
            def callback(record,battle):
                self.finish_record()
                if snapshot_callback:snapshot_callback(record,battle)
            try:return original_replay(engine,snapshot_callback=callback)
            finally:
                self.finish_record();self.end(node);self.in_replay=False;self.source,self.stage=previous
        state.StateEngine.replay=replay;self.restores.append((state.StateEngine,'replay',original_replay))
        original_event=state.event_from_dict
        @wraps(original_event)
        def event_from_dict(value):
            if self.in_replay:
                self.finish_record();self.source=event_source(value)
                self.record_scope=self.begin('state_event',metadata=dict(event_id=value['event_id']))
            return original_event(value)
        state.event_from_dict=event_from_dict;self.restores.append((state,'event_from_dict',original_event))
        original_adapt=report.video_events
        @wraps(original_adapt)
        def adapt(*args,**kwargs):
            previous=(self.source,self.stage);self.source=None;self.stage='adaptation';self.in_adaptation=True
            node=self.begin('event_adaptation')
            try:return original_adapt(*args,**kwargs)
            finally:
                self.finish_adapt();self.end(node);self.in_adaptation=False;self.source,self.stage=previous
        report.video_events=adapt;self.restores.append((report,'video_events',original_adapt))
        original_checkpoint=command.checkpoint_event
        @wraps(original_checkpoint)
        def checkpoint(row,*args,**kwargs):
            if self.in_adaptation:
                self.finish_adapt();self.source=row_source(row);self.adapt_scope=self.begin('adapt_frame')
            return original_checkpoint(row,*args,**kwargs)
        command.checkpoint_event=checkpoint;self.restores.append((command,'checkpoint_event',original_checkpoint))
        # video_events' final sort is batch work, not the final frame's cost.
        report.sorted=lambda *a,**k:self._shared_sort(*a,**k)
        self.restores.append((report,'sorted',None))
        original_package=report.reconstruct_and_package
        @wraps(original_package)
        def package(*args,**kwargs):
            previous=(self.source,self.stage);self.source=None;self.stage='postprocessing'
            try:
                with self.span('reconstruction_exports'):return original_package(*args,**kwargs)
            finally:self.source,self.stage=previous
        report.reconstruct_and_package=package;self.restores.append((report,'reconstruct_and_package',original_package))
        original_decoder=video.decoded_frames
        @wraps(original_decoder)
        def decoded(path,*args,**kwargs):
            iterator=original_decoder(path,*args,**kwargs);self.stage='acquisition'
            try:
                while True:
                    self.finish_frame();node=self.begin('decode_sampling_wait')
                    try:
                        image,raw=next(iterator)
                    except StopIteration:
                        self.end(node);break
                    except BaseException:
                        self.end(node);raise
                    raw_source=dict(raw,source_id=str(path.relative_to(video.ROOT))+'#'+str(raw['timestamp']))
                    node['source']=row_source(raw_source);self.end(node)
                    self.start_frame(raw_source)
                    yield image,raw
            finally:
                self.finish_frame();iterator.close();self.source=None;self.stage='post_acquisition'
        video.decoded_frames=decoded;self.restores.append((video,'decoded_frames',original_decoder))

    def _shared_sort(self,*args,**kwargs):
        self.finish_adapt()
        with self.span('event_batch_sort'):return sorted(*args,**kwargs)

    def close(self,status):
        from recognition.video_sampling import atomic_json
        self.finish_frame();self.stream.close();self.frames.close()
        for obj,name,original in reversed(self.restores):
            if original is None:delattr(obj,name)
            else:setattr(obj,name,original)
        atomic_json(self.folder/'profiler.json',dict(status=status,operations=self.operations,
            child_elapsed_seconds=self.clock()-self.origin,measured_recording_overhead_seconds=self.overhead,
            overhead_limit='Measured wrapper setup/record serialization only; clock-call/stack/callback perturbation and OS scheduling overhead are not fully isolated.',
            units='Monotonic seconds; exclusive body removes child full spans including measured child instrumentation overhead. Frame consumer wall includes instrumentation.',
            asynchronous='Only main-thread waits measured. FFmpeg source decode counts/timestamps are recovered from its log, not attributed CPU timings.'))


def row_source(row):
    return {k:row[k] for k in ('timestamp','source_id','source_pts','source_time_base','image','sha256') if k in row}


def event_source(event):
    evidence=event.get('evidence',[]);sources=[dict(source_id=e['source_id'],timestamp=e.get('details',{}).get('timestamp'),
                observation_ids=e.get('observation_ids',[])) for e in evidence]
    times={e['timestamp'] for e in sources if e['timestamp'] is not None}
    timestamp=event.get('attributes',{}).get('observation_time')
    if len(times)>1:
        return dict(timestamp=None,source_id=None,evidence=sources,attribution='shared_evidence_interval',interval=[min(times),max(times)])
    return dict(timestamp=timestamp,source_id=sources[0]['source_id'] if sources else None,evidence=sources,event_id=event['event_id'])
