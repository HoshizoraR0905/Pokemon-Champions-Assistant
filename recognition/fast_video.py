"""Cold/resumable video analysis for the standard CLI's fast profile.

Separate, recording-owned run namespaces; never consumes baseline predictions.
Shared immutable OCR/icon assets are allowed; crop predictions start empty.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time
import cv2
import numpy as np
from battle_artifacts import BattleArtifacts, canonical_id
from capture import Frame
from recognition.fast_profile import (VERSION, FastConfig, AdaptiveInspection, RegionGate,
    inspect, normalized, difference, recognize_cards, MENUS)
from recognition.video_sampling import atomic_json, fingerprint

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def decoded_frames(video,log,*,start=0.,end=None):
    """FFmpeg decodes source frames; materialize first source PTS per 0.5s cell.

    Count source-decoded frames with a pre-select showinfo, independently of
    the selected raw frames. Drain logs concurrently; preserve integer PTS.
    """
    import imageio_ffmpeg
    command=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','info','-threads','2']
    if start:command+=['-ss',str(start)]
    command+=['-i',str(video)]
    if end is not None:command+=['-t',str(end-start)]
    expr=f'isnan(prev_selected_t)+gt(floor((t+{start})*2+0.000000001),floor((prev_selected_t+{start})*2+0.000000001))'
    command+=['-an','-vf',f"showinfo@source=checksum=0,select='{expr}',scale=1311:603,showinfo@sample=checksum=0",
              '-fps_mode','vfr','-pix_fmt','bgr24','-f','rawvideo','pipe:1']
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=1024*1024)
    samples=queue.Queue();metadata={'source_decoded_frames':0,'command':command};base=None
    def drain():
        nonlocal base
        with Path(log).open('w') as stream:
            for raw in iter(process.stderr.readline,b''):
                line=raw.decode('utf-8','replace');stream.write(line)
                duration=re.search(r'Duration: (\d+):(\d+):([\d.]+)',line)
                if duration:metadata['container_duration_seconds']=int(duration[1])*3600+int(duration[2])*60+float(duration[3])
                if 'showinfo@source' in line and re.search(r'\bn:\s*\d+\s+pts:',line):metadata['source_decoded_frames']+=1
                if 'showinfo@sample' not in line:continue
                m=re.search(r'config in time_base:\s*(\d+)/(\d+)',line)
                if m:base=Fraction(int(m[1]),int(m[2]))
                m=re.search(r'\bn:\s*\d+\s+pts:\s*(-?\d+)\s+pts_time:',line)
                if m and base:samples.put((int(m[1]),base))
        samples.put(None)
    thread=threading.Thread(target=drain,daemon=True);thread.start()
    size=1311*603*3
    try:
        while True:
            data=bytearray()
            while len(data)<size:
                part=process.stdout.read(size-len(data))
                if not part:break
                data.extend(part)
            if not data:break
            if len(data)!=size:raise RuntimeError('Truncated decoded frame')
            pts=samples.get(timeout=60)
            if pts is None:raise RuntimeError('Missing source PTS')
            ticks,base=pts;t=float(Fraction(str(start))+ticks*base)
            yield np.frombuffer(data,dtype=np.uint8).reshape(603,1311,3),dict(timestamp=t,source_pts=ticks,
                source_time_base=str(base),seek_origin_seconds=start,target_timestamp=math.floor(t*2+1e-7)/2)
        if process.wait()!=0:raise RuntimeError(f'FFmpeg failed; see {log}')
        thread.join();return
    finally:
        if process.poll() is None:process.terminate()
        process.stdout.close();thread.join(timeout=5)
        process.stderr.close()
        decoded_frames.last_metadata=metadata


class CachedOCR:
    def __init__(self,folder,counts):
        from recognition.onnx_ocr import ONNXOCRBackend
        self.folder=folder;self.counts=counts;self.real=None
        self.identity=dict(model=digest(ROOT/'.cache/m15-onnx-medium/local-manifest.json'),
                           implementation=digest(ROOT/'recognition/onnx_ocr.py'),provider='cpu',batch_size=1)
        self.backend=ONNXOCRBackend.__new__(ONNXOCRBackend)
        self.backend.threshold=.75;self.backend.language='zh-Hans+en';self.backend.model_name='PP-OCRv6_medium_rec-onnx-cpu';self.backend.warnings=[]
        self.backend.predict=self.predict;self.warnings=[]
        self.read_costs={};self.gate=RegionGate(.004);self.source='';self.timestamp=0.;self.reuses=[]
    def predict(self,crops):
        from recognition.onnx_ocr import ONNXOCRBackend
        self.counts['ocr_prediction_requests']+=len(crops)
        output=[]
        for crop in crops:
            key=fingerprint(dict(shape=list(crop.shape),pixels=hashlib.sha256(crop.tobytes()).hexdigest(),**self.identity))
            path=self.folder/'reads'/f'{key}.json'
            if path.exists():self.counts['ocr_exact_cache_hits']+=1;result=json.loads(path.read_text())
            else:
                self.counts['ocr_invocations_attempted']+=1
                if self.real is None:self.real=ONNXOCRBackend(ROOT/'.cache/m15-onnx-medium',provider='cpu',batch_size=1)
                began=time.monotonic();result=self.real.predict([crop])[0]
                self.counts['ocr_seconds']+=time.monotonic()-began
                self.counts['ocr_invocations_performed']+=1;atomic_json(path,result)
            output.append(result)
        return output
    def read(self,image,bounds,numeric=False,multiline=False,italic=False):
        self.counts['ocr_read_requests']+=1
        kwargs=dict(numeric=numeric,multiline=multiline,italic=italic)
        key=str((tuple(bounds),tuple(sorted(kwargs.items()))));sig=normalized(image,bounds,text=True)
        selected,reason,old=self.gate.choose(key,sig,True,self.timestamp)
        if not selected:
            self.counts['ocr_region_reads_reused']+=1
            self.counts['ocr_invocations_avoided_unchanged']+=self.read_costs.get(key,1)
            self.reuses.append(dict(bounds=bounds,original_source_id=old['source_id'],original_timestamp=old['timestamp']))
            return deepcopy(old['value'])
        before=self.counts['ocr_prediction_requests']
        obs=self.backend.read(image,bounds,**kwargs)
        self.read_costs[key]=self.counts['ocr_prediction_requests']-before
        self.gate.store(key,sig,self.timestamp,obs,self.source,obs.confidence>=.9)
        return obs


class CachedIcons:
    def __init__(self,folder,counts,enabled=True):
        from recognition.icons import IconRecognizer
        self.base=IconRecognizer() if enabled else None;self.enabled=enabled
        self.folder=folder;self.counts=counts;self.source=self.base.source if self.base else None
        self.gate=RegionGate(.01);self.timestamp=0.;self.frame_source=''
    def identify(self,image,bounds):
        from models import IconEvidence,IconCandidate
        from recognition.sprite_shape import identify_shape
        if not self.enabled:return IconEvidence(region=bounds,status='unresolved',reason='icons_disabled')
        key=str(tuple(bounds));sig=normalized(image,bounds)
        selected,reason,old=self.gate.choose(key,sig,True,self.timestamp)
        if not selected:
            self.counts['icon_region_reuses']+=1;return deepcopy(old['value'])
        x,y,X,Y=bounds;results=[]
        for profile in ['default','silhouette']:
            identity=fingerprint(dict(pixels=hashlib.sha256(image[y:Y,x:X].tobytes()).hexdigest(),shape=list(image[y:Y,x:X].shape),source=self.source,profile=profile))
            path=self.folder/'icons'/f'{identity}.json'
            if path.exists():data=json.loads(path.read_text());self.counts['icon_exact_cache_hits']+=1
            else:
                self.counts['icon_invocations_attempted']+=1;began=time.monotonic()
                result=self.base.identify(image,bounds) if profile=='default' else identify_shape(self.base,image,bounds)
                self.counts['icon_seconds']+=time.monotonic()-began;self.counts['icon_invocations_performed']+=1
                data=asdict(result);atomic_json(path,data)
            data['region']=bounds;data['candidates']=[IconCandidate(**c) for c in data['candidates']];results.append(IconEvidence(**data))
        a,b=results
        result=(IconEvidence(region=bounds,status='ambiguous',reason='independent_profiles_disagree',candidates=a.candidates)
                if a.status==b.status=='resolved' and a.species_id!=b.species_id else a if a.status=='resolved' or b.status!='resolved' else b)
        result.independent_profiles=[asdict(v) for v in results]
        self.gate.store(key,sig,self.timestamp,result,self.frame_source,result.status=='resolved')
        return result


def cached_frames(manifest,paths,video,*,start=0.,end=None):
    """Read acquisition metadata and pixels only; no historical OCR or labels."""
    from scripts.validate_m232 import video_identity
    manifest=Path(manifest).resolve()
    if not manifest.is_relative_to(paths.cache_dir.resolve()):raise ValueError('Frame cache belongs outside this battle namespace')
    data=json.loads(manifest.read_text());media=video_identity(video)
    prior=data['video'];paths.check_identity(prior['battle_id'])
    for key in ['size_bytes','sampled_sha256']:
        if prior[key]!=media[key]:raise ValueError('Cached video fingerprint mismatch: '+key)
    cells={}
    for row in data['frames']:
        target=row['target_timestamp'];cell=round(target*2)
        if abs(target*2-cell)>1e-6 or not start<=target or end is not None and target>=end:continue
        if cell not in cells or row['timestamp']<cells[cell]['timestamp']:cells[cell]=row
    try:
        for cell,row in sorted(cells.items()):
            path=(paths.root/row['image']).resolve()
            if not path.is_relative_to(paths.cache_dir.resolve()) or digest(path)!=row['sha256']:
                raise ValueError('Invalid owned cached frame: '+row['image'])
            image=cv2.imread(str(path))
            if image is None or image.shape[:2]!=(603,1311):raise ValueError('Unsupported cached frame scale')
            yield image,{k:row[k] for k in ['timestamp','target_timestamp','source_pts','source_time_base']}
    finally:
        decoded_frames.last_metadata=dict(source_decoded_frames=0,reused_frame_cache=str(manifest),
            container_duration_seconds=prior['metadata']['duration_seconds'])


def analyze(video,*,run_id='fast-v1',resume=False,end=None,max_frames=None,diagnostic_menus=False,icons=True,event_driven=False,frame_cache=None,recognition_caches=None,reconstruct_from=None):
    from recognition import Recognizer,box
    from recognition.ui_regions import read_message
    from recognition.identity_flow import preview_rows
    from recognition.message_occurrences import MessageOccurrences
    from recognition.visual_evidence import variants,parse_popup,DETAIL_ROIS,parse_detail,stage_arrows,detail_layout
    from recognition.visual_adapter import selected_panel_side
    from scripts.process_m237 import context_dump,context_restore
    if end is not None and (not math.isfinite(end) or end<=0):raise ValueError('end must be positive and finite')
    if max_frames is not None and max_frames<1:raise ValueError('max_frames must be positive')
    if frame_cache and not event_driven:raise ValueError('--frame-cache requires --profile event-driven')
    if recognition_caches and not event_driven:raise ValueError('--recognition-cache requires --profile event-driven')
    if reconstruct_from and (not event_driven or frame_cache or recognition_caches or end or max_frames):
        raise ValueError('--reconstruct-from requires event-driven and cannot be combined with acquisition options')
    started=time.monotonic();video=Path(video).resolve()
    paths=BattleArtifacts.select(video=video).prepare();run_id=canonical_id(run_id)
    namespace='event-driven' if event_driven else 'fast'
    folder=paths.cache(f'{namespace}/{run_id}');report=paths.report(f'{namespace}/{run_id}')
    manifest_path=folder/'manifest.json'
    if manifest_path.exists() and not resume:raise ValueError(f'Run exists: {folder}; use --resume or a new --run-id')
    folder.mkdir(parents=True,exist_ok=True)
    config=FastConfig(diagnostic_menus=diagnostic_menus)
    controller=None
    if event_driven:
        from recognition.event_schedule import EventConfig,EventInspection,IdentitySchedule,command_label
        config=EventConfig();controller=IdentitySchedule()
    sources={str(p.relative_to(ROOT)):digest(p) for directory in ['recognition','tracking','battle_events','models','knowledge','capture']
             for p in (ROOT/directory).rglob('*') if p.suffix in {'.py','.json','.yaml','.yml'} and '__pycache__' not in p.parts}
    for p in [Path(__file__),ROOT/'main.py',ROOT/'scripts/report_m237.py',ROOT/'scripts/process_m237.py',ROOT/'recognition/fast_report.py',ROOT/'scripts/templates/fast_review.html',ROOT/'battle_artifacts.py',ROOT/'scripts/benchmark_fast.py']:
        if p.exists():sources[str(p.relative_to(ROOT))]=digest(p)
    if event_driven:
        for p in [ROOT/'scripts/templates/event_review.html',*sorted((ROOT/'recognition/assets').glob('command_label_*.png'))]:
            sources[str(p.relative_to(ROOT))]=digest(p)
    identity=dict(version=config.version,config=asdict(config),video_path=str(video),video_sha256=digest(video),sources=sources,
                  ocr_manifest=digest(ROOT/'.cache/m15-onnx-medium/local-manifest.json'),icon_index=digest(ROOT/'.cache/champions-icons/index.json'),
                  end=end,max_frames=max_frames,icons=icons)
    if frame_cache:identity['frame_cache']=dict(path=str(Path(frame_cache).resolve()),sha256=digest(frame_cache))
    cache_sources=[]
    for source in recognition_caches or []:
        source=Path(source).resolve()
        if not source.is_relative_to(paths.cache_dir.resolve()) or source==folder.resolve():
            raise ValueError('Prediction cache must belong to another run of the same battle')
        old=json.loads((source/'manifest.json').read_text())['identity']
        dependencies=['recognition/onnx_ocr.py','recognition/icons.py','recognition/sprite_shape.py']
        if any(old.get(k)!=identity[k] for k in ['ocr_manifest','icon_index']) or any(old['sources'].get(k)!=sources[k] for k in dependencies):
            raise ValueError('Prediction cache model/implementation mismatch')
        cache_sources.append(dict(path=str(source),ocr_manifest=old['ocr_manifest'],icon_index=old['icon_index'],
                                  dependencies={k:old['sources'][k] for k in dependencies}))
    if recognition_caches:identity['recognition_caches']=cache_sources
    if reconstruct_from:
        source=Path(reconstruct_from).resolve()
        if not source.is_relative_to(paths.cache_dir.resolve()) or source==folder.resolve():
            raise ValueError('Reconstruction source must be another owned run')
        identity['recognition_stage_source']=dict(path=str(source),observations_sha256=digest(source/'observations.json'))
    prior=json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    if prior and prior['identity']!=identity:raise ValueError('Run identity changed; preserve it and choose a new --run-id')
    if prior and prior['status']=='complete':return prior
    if not prior:
        for name in sources:
            target=folder/'source'/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((ROOT/name).read_bytes())
        import shutil
        for source in cache_sources:
            for category in ['reads','icons']:
                for path in (Path(source['path'])/category).glob('*.json'):
                    target=folder/category/path.name;target.parent.mkdir(parents=True,exist_ok=True)
                    if not target.exists():shutil.copy2(path,target)
    if reconstruct_from:
        from recognition.event_report import reconstruct_cached
        return reconstruct_cached(paths,folder,report,source,identity)
    counts=Counter({'ocr_invocations_performed':0,'icon_invocations_performed':0});rows=[];roster=[];scheduler=AdaptiveInspection(config);gate=RegionGate(config.region_difference)
    if event_driven:scheduler=EventInspection(config)
    ocr=CachedOCR(folder,counts);icon=CachedIcons(folder,counts,icons);recognizer=Recognizer(ocr,icons=icon)
    occurrences=MessageOccurrences(paths.battle_id,source_occurrence_ids=event_driven);previous_visible=set();last_phase=None;last_fallback=-math.inf
    # A resume reconstructs scheduling/context from persisted prefix images and
    # cached reads, then seeks directly to the first incomplete acquisition cell.
    checkpoint=folder/'checkpoint.json'
    if prior and checkpoint.exists():
        saved=json.loads(checkpoint.read_text());counts.update(saved['counts']);roster=saved['roster']
        rows=[json.loads(p.read_text()) for p in sorted((folder/'observations').glob('*.json'))]
        if len(rows)!=saved['row_count']:raise ValueError('Checkpoint/row mismatch; incomplete tail must be inspected, not silently discarded')
        for row in rows:
            occurrences.observe(row)
        context_restore(recognizer.context,saved['context']);scheduler.next_time=saved['next_time'];scheduler.boost_until=saved['boost_until']
        if event_driven:
            scheduler.restore(saved['event_scheduler'])
            controller.__dict__.update(saved['identity_schedule'])
        last_phase=saved['last_phase'];previous_visible=set(saved['previous_visible']);last_fallback=saved['last_fallback']
        for key,old in saved['gate'].items():old['signature']=np.asarray(old['signature'],dtype=np.uint8);gate.regions[key]=old
        # OCR/icon fuzzy caches intentionally start empty on resume. Exact crop
        # caches remain available; additional calls are recorded as resumed cost.
    initial_counts=dict(counts);manifest=dict(status='running',identity=identity,cold_run=not bool(prior) and not bool(frame_cache) and not bool(recognition_caches),
        prior_active_seconds=prior.get('active_seconds',0) if prior else 0,completed_stages=[],report=str(report),counts=dict(counts))
    atomic_json(manifest_path,manifest)
    def save(status='running',error=None):
        serialgate={k:{**v,'signature':v['signature'].tolist()} for k,v in gate.regions.items()}
        atomic_json(checkpoint,dict(row_count=len(rows),roster=roster,context=context_dump(recognizer.context),counts=dict(counts),
            next_time=scheduler.next_time,boost_until=scheduler.boost_until,last_phase=last_phase,previous_visible=sorted(previous_visible),
            last_fallback=last_fallback,gate=serialgate,last_sample=rows[-1]['timestamp'] if rows else None,
            event_scheduler=scheduler.dump() if event_driven else None,
            identity_schedule=controller.__dict__ if event_driven else None))
        manifest.update(status=status,active_seconds=manifest['prior_active_seconds']+time.monotonic()-started,counts=dict(counts),
            last_timestamp=rows[-1]['timestamp'] if rows else None,error=error)
        atomic_json(manifest_path,manifest)
    start_cell=(math.floor(rows[-1]['timestamp']*2)+1)/2 if rows else 0.
    try:
        decoder=(cached_frames(frame_cache,paths,video,start=start_cell,end=end) if frame_cache else
                 decoded_frames(video,folder/('decode-resume.log' if prior else 'decode.log'),start=start_cell,end=end))
        for image,raw in decoder:
            counts['frames_materialized_at_2fps']+=1
            t=raw['timestamp']
            ui=None
            if event_driven:
                ui=inspect(image)
                # Verified six-row / six-card team layouts own these pixels;
                # apparent HP/name panels here are roster rows, not active HUDs.
                # The live-message region remains independently eligible.
                if ui['phase'] in {'team_configuration','team_preview'} and ui['confidence']>=.9:
                    ui['cards']=[]
                    for region in ui['regions']:
                        if region['region_type']=='active_hud':
                            region.update(visibility='occluded',routing_reason='verified_team_layout_owns_card_pixels')
                eligible=scheduler.monitor(t,command_label(image),ui['message_visible'])
                counts['cheap_monitor_frames']+=1
                # Persist every candidate decision, including unscheduled frames.
                atomic_json(folder/'monitor'/f'{round(raw["target_timestamp"]*2):06d}.json',
                    dict(**raw,command=deepcopy(scheduler.last_monitor),inspected=eligible))
            else:eligible=scheduler.due(t)
            if not eligible:counts['frames_not_inspected_adaptive_1fps']+=1;continue
            counts['frames_sampled']+=1;counts['frames_classified']+=1
            ui=ui or inspect(image);counts['phase:'+ui['phase']]+=1
            frame_hash=hashlib.sha256(image.tobytes()).hexdigest()
            imagepath=folder/'frames'/f'{counts["frames_sampled"]:06d}.png';imagepath.parent.mkdir(parents=True,exist_ok=True)
            cv2.imwrite(str(imagepath),image,[cv2.IMWRITE_PNG_COMPRESSION,1])
            raw.update(image=str(imagepath.relative_to(ROOT)),sha256=digest(imagepath),pixel_sha256=frame_hash,
                       source_id=str(video.relative_to(ROOT) if video.is_relative_to(ROOT) else video)+'#'+str(t))
            ocr.source=raw['source_id'];ocr.timestamp=t;ocr.reuses=[];icon.timestamp=t;icon.frame_source=raw['source_id']
            before=counts['ocr_invocations_performed'];before_requests=counts['ocr_read_requests']+counts['ocr_prediction_requests'];visible=set();changed=False;decisions=[]
            row=dict(**raw,ui={k:v for k,v in ui.items() if k not in {'message_mask','cards','message_visible','flash'}},
                message=dict(selected=False,raw_text='',confidence=0.),snapshot={},visual=dict(readings={},parsed=[]),region_decisions=decisions,
                window=[0,end],ocr_read_reuses=ocr.reuses)
            selected_cards=[]
            if event_driven:
                row['command']=deepcopy(scheduler.last_monitor)
                trainer_frame=Frame(image,raw['source_id'],counts['frames_sampled'],t,raw)
                row['trainer_observations']=controller.acquire_trainers(recognizer,trainer_frame,
                    ui['phase'],ui['confidence'],paths.battle_id,counts)
                if row['command']['visible']:
                    x,y,X,Y=row['command']['bounds']
                    countdown=ocr.read(image,(X+2,max(0,y-3),min(image.shape[1],X+56),min(image.shape[0],Y+4)),numeric=True)
                    literal=str(countdown.value or '').strip()
                    row['command']['countdown']=int(literal) if literal.isdigit() and countdown.confidence>=.75 else None
                    row['command']['countdown_ocr']=asdict(countdown)
            for region in ui['regions']:
                key=region['region_id'];typ=region['region_type'];vis=region['visibility'];isvisible=vis in {'visible','partial'}
                if typ=='battle_message':isvisible=vis=='visible'
                if not isvisible:
                    if typ=='battle_message' and vis=='partial':
                        # Uncertain geometry is not a proven disappearance. Hold
                        # the occurrence open, without fabricating an OCR reading.
                        row['message']['visibility']='partial';decisions.append(dict(region=key,reason='uncertain_visibility',selected=False));continue
                    gate.choose(key,np.zeros((24,128),np.uint8),False,t)
                    decisions.append(dict(region=key,reason='not_visible',selected=False));continue
                visible.add(key)
                if typ=='battle_message':
                    sig=cv2.resize(ui['message_mask'],(128,24),interpolation=cv2.INTER_AREA)
                else:sig=normalized(image,region['bounds'],text=typ!='active_hud')
                threshold=gate.threshold;gate.threshold=.008 if typ=='active_hud' else config.region_difference
                selected,reason,old=gate.choose(key,sig,True,t);gate.threshold=threshold
                decisions.append(dict(region=key,reason=reason,selected=selected))
                if not selected:
                    counts['region_rejected:'+reason]+=1
                    if typ=='battle_message':
                        row['message']=deepcopy(old['value']);row['message']['reading_reused_from']=dict(timestamp=old['timestamp'],source_id=old['source_id'])
                        avoided=max(1,len(row['message'].get('rows',[])))
                        counts['message_ocr_invocations_avoided_unchanged']+=avoided
                        counts['ocr_invocations_avoided_unchanged']+=avoided
                    continue
                changed=True;counts['region_selected:'+reason]+=1;region['selected_for_ocr']=True
                if typ=='battle_message':
                    category_before=counts['ocr_invocations_performed']
                    msg=read_message(image,ocr,region);row['message']=msg
                    if event_driven:counts['battle_message_ocr_invocations']+=counts['ocr_invocations_performed']-category_before
                    gate.store(key,sig,t,msg,raw['source_id'],msg['confidence']>=.9)
                elif typ=='active_hud':
                    fields=region['fields'];selected_cards.append((fields['side'],fields['card_index'],fields['offset'],fields['name_roi']))
                    gate.store(key,sig,t,{},raw['source_id'])
                elif typ=='ability_banner':
                    counts['ability_banner_reading_invocations']+=1
                    readings={k:[dict(**ocr.predict([crop])[0],config_id=k+':'+name,box=bounds) for name,crop in variants(image,bounds)]
                        for k,bounds in zip(['species','ability'],region['fields']['lines'])}
                    parsed=parse_popup(readings);region['ocr']=readings
                    row['visual']['parsed'].append(dict(kind='popup',screen_edge=key,battle_side=None,**parsed))
                    row['visual']['readings'].update({key+':'+k:v for k,v in readings.items()})
                    gate.store(key,sig,t,parsed,raw['source_id'],parsed.get('status')=='supported')
                elif typ=='field_indicator':
                    counts['field_condition_reading_invocations']+=1
                    readings={k:asdict(ocr.read(image,box(image,roi))) for k,roi in [('label',(.205,.045,.30,.095)),('counter',(.39,.045,.424,.095))]}
                    region['ocr']=readings;label=readings['label']['raw_text'].strip()
                    if readings['label']['confidence']>=.9 and label in {'沙暴状态','晴天','雨天','下雪','精神场地','青草场地','戏法空间'}:
                        region['canonical']=dict(literal_label=label,literal_counter=readings['counter']['raw_text'].strip(),trigger_time=None,counter_meaning='unverified')
                    gate.store(key,sig,t,readings,raw['source_id'],bool(region.get('canonical')))
            for key in previous_visible-visible:
                # Preserve uncertain message occlusion; otherwise a reappearance
                # is a fresh occurrence/evidence opportunity, including HUDs.
                if key=='message' and row['message'].get('visibility')=='partial':continue
                gate.regions.pop(key,None)
            previous_visible=visible
            if selected_cards:
                frame=Frame(image,raw['source_id'],counts['frames_sampled'],t,raw)
                if event_driven:row['snapshot']=controller.recognize(recognizer,frame,selected_cards,counts)
                else:row['snapshot']=recognize_cards(recognizer,frame,selected_cards).to_dict()
            if event_driven:
                if ui['phase'] in {'team_configuration','team_preview'}:
                    key='team:'+ui['phase'];sig=normalized(image,box(image,(.08,.04,.95,.97)),text=True)
                    choose,reason,_=gate.choose(key,sig,True,t)
                    if choose:
                        roster+=controller.acquire_team(recognizer,Frame(image,raw['source_id'],counts['frames_sampled'],t,raw),ui['phase'],paths.battle_id,counts)
                        gate.store(key,sig,t,{},raw['source_id'])
            elif ui['phase']=='team_preview' or (diagnostic_menus and ui['phase'] in MENUS|{'team_configuration'}):
                key='preview' if ui['phase']=='team_preview' else 'diagnostic_menu';sig=normalized(image,box(image,(.08,.04,.95,.97)),text=True)
                choose,reason,_=gate.choose(key,sig,True,t)
                if choose:
                    snapshot=recognizer.recognize(Frame(image,raw['source_id'],counts['frames_sampled'],t,raw));row['snapshot']=snapshot.to_dict()
                    roster+=preview_rows(snapshot,paths.battle_id);gate.store(key,sig,t,{},raw['source_id'])
            elif ui['phase'] in MENUS|{'team_configuration'}:counts['menu_detailed_recognition_suppressed']+=1
            # Selected detail overlays are relevant observations; actual selection
            # corroboration avoids the baseline's animation-as-status false gate.
            selection=selected_panel_side(image) if detail_layout(image) else None
            if selection:
                sig=normalized(image,box(image,(.25,.18,.66,.53)),text=True)
                choose,reason,_=gate.choose('detail',sig,True,t)
                if choose:
                    readings={k:[dict(**ocr.predict([crop])[0],box=box(image,roi),config_id=k+':'+name) for name,crop in variants(image,box(image,roi))] for k,roi in DETAIL_ROIS.items()}
                    parsed=parse_detail(readings,stage_arrows(image));row['visual'].update(readings=readings,parsed=[dict(kind='detail',**parsed)],selection=selection)
                    gate.store('detail',sig,t,parsed,raw['source_id'],parsed.get('status')=='supported')
            else:gate.regions.pop('detail',None)
            if ui['phase']=='unknown':
                counts['unknown_inspection_frames']+=1
                if t-last_fallback>=config.unknown_fallback_seconds:
                    row['unknown_fallback']=dict(status='insufficient_coverage',reason='No locally qualified expensive-recognition region; image retained for review')
                    last_fallback=t;counts['unknown_fallback_checkpoints']+=1
            result=occurrences.observe(row)
            row['occurrence_decision']=dict(events=result['events'],reason=result['reason'])
            if event_driven:
                for event in row['occurrence_decision']['events']:
                    controller.invalidate(event)
                    if event['event_type'] in {'send_out','switch_out','faint','transformation','position_change'}:
                        for key in list(gate.regions):
                            if '_active_' in key:gate.regions.pop(key,None)
            changed=changed or last_phase!=ui['phase']
            row['inspection_fps']=scheduler.advance(t,phase=ui['phase'],message_visible=ui['message_visible'],changed=changed)
            if event_driven:counts[f'inspected_frames_at_{int(row["inspection_fps"])}fps']+=1
            last_phase=ui['phase']
            if counts['ocr_invocations_performed']==before:counts['frames_without_model_ocr']+=1
            if counts['ocr_read_requests']+counts['ocr_prediction_requests']==before_requests:
                counts['frames_rejected_before_ocr']+=1
                why='unchanged_regions' if any(d['reason']=='unchanged_region' for d in decisions) else 'empty_or_animation_or_menu'
                if ui['flash']:why='full_screen_flash'
                counts['frame_rejected:'+why]+=1
            row['context_after']=context_dump(recognizer.context)
            atomic_json(folder/'observations'/f'{len(rows):06d}.json',row);rows.append(row)
            if len(rows)%10==0:
                save();print(f'{paths.battle_id} {run_id}: {t:.1f}s, {len(rows)} inspections, {counts["ocr_invocations_performed"]} OCR, {time.monotonic()-started:.1f}s wall',flush=True)
            if max_frames is not None and len(rows)>=max_frames:
                decoder.close();break
        counts['source_decoded_frames']+=decoded_frames.last_metadata['source_decoded_frames']
        manifest['decoder']=decoded_frames.last_metadata
        atomic_json(folder/'observations.json',dict(battle_id=paths.battle_id,observations=rows,roster=roster,occurrences=occurrences.groups,
            prefix_decisions=[dict(source_id=r['source_id'],**r['occurrence_decision']) for r in rows],independent_manual_review=False))
        manifest['completed_stages']=['recognition'];save()
        if event_driven:
            from recognition.event_report import reconstruct_and_package
        else:
            from recognition.fast_report import reconstruct_and_package
        result=reconstruct_and_package(paths,folder,report,rows,roster,occurrences.groups)
        manifest['completed_stages']+=['reconstruction','viewer_packaging'];manifest['results']=result
        save('complete')
        result['video_duration']=manifest['decoder'].get('container_duration_seconds',result['video_duration'])
        manifest['cold_end_to_end_wall_seconds']=time.monotonic()-started if manifest['cold_run'] else None
        manifest['performance_target_seconds']=result['video_duration']+5
        manifest['performance_target_met']=(manifest['cold_end_to_end_wall_seconds']<=manifest['performance_target_seconds']) if manifest['cold_run'] and end is None and max_frames is None else None
        manifest['outputs']={str(p.relative_to(ROOT)):digest(p) for p in [folder/'observations.json',folder/'replay.json',report/'review.html',report/'summary.json']}
        atomic_json(manifest_path,manifest)
        return manifest
    except BaseException as exc:
        if 'decoder' in locals():decoder.close()
        save('failed',repr(exc));raise
