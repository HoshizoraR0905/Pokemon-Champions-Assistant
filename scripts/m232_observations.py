"""Selective cached OCR, reusing existing log/message/HUD recognition adapters."""
from pathlib import Path
import hashlib
import json
import time
from scripts.validate_m232 import ROOT, save, digest


def recognize(paths,survey):
    import cv2
    from capture import Frame
    from recognition import Recognizer, box
    from recognition.phases import classify_phase, _message_glyphs
    from recognition.battle_log import extract_view
    from recognition.onnx_ocr import ONNXOCRBackend
    model=ROOT/'.cache/m15-onnx-medium'
    model_manifest=json.loads((model/'local-manifest.json').read_text())
    adapter=digest({'version':1,'model':model_manifest,'video':survey['video_fingerprint'],
                    'code':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['recognition/__init__.py','recognition/phases.py','recognition/battle_log.py','recognition/onnx_ocr.py','scripts/m232_observations.py']}})
    destination=paths.cache('m232/observations.json');start=time.monotonic()
    if destination.exists():
        prior=json.loads(destination.read_text())
        if prior['adapter_hash']==adapter:return prior,True
    # Raw M2.2.3 OCR caches are recording-owned. They are parsed again downstream.
    reused={}
    for source in sorted(paths.cache_dir.glob('m223-ocr-*/observations.json')):
        data=json.loads(source.read_text())
        for obs in data['observations']:reused[obs['sha256']]=obs
    backend=recognizer=None;metrics={'read_calls':0,'ocr_crops':0,'inference_batches':0,'new_frames':0,'reused_frames':0,'snapshot_frames':0,'message_frames':0,'log_frames':0}
    def load_backend():
        nonlocal backend,recognizer
        if backend is None:
            backend=ONNXOCRBackend(model,provider='cpu',batch_size=1)
            predict=backend.predict;read=backend.read
            def counted_predict(crops):
                metrics['ocr_crops']+=len(crops);metrics['inference_batches']+=len(crops)
                return predict(crops)
            def counted_read(*a,**kw):metrics['read_calls']+=1;return read(*a,**kw)
            backend.predict=counted_predict;backend.read=counted_read
            recognizer=Recognizer(backend,icons=True)
        return backend
    # Select every geometrically visible log and message crop, plus sparse stable HUDs.
    observations=[];last_hud=-100;preview_done=False;config_done=False;previous_message=None
    for index,f in enumerate(survey['frames']):
        image=cv2.imread(str(ROOT/f['image']));phase,confidence,labels,warnings=classify_phase(image)
        record=dict(f,visual_phase=phase,visual_phase_confidence=confidence,visual_phase_labels=labels,visual_phase_warnings=warnings)
        log=bool(f['log_geometry']);glyphs=_message_glyphs(image)
        message=(glyphs>=8 and phase in {'battle_message','battle_animation','unknown'} and f['timestamp']>30)
        snapshot=((f['phase']=='team_preview' and not preview_done) or (f['phase']=='team_configuration' and not config_done) or
                  (f['phase'] in {'battle_screen','move_selection'} and f['timestamp']-last_hud>=18))
        if snapshot:
            if f['phase']=='team_preview':preview_done=True
            elif f['phase']=='team_configuration':config_done=True
            else:last_hud=f['timestamp']
        key=f['sha256']+':'+str((log,message,snapshot))
        path=paths.cache('m232/ocr/'+hashlib.sha256(key.encode()).hexdigest()[:24]+'.json')
        if path.exists():
            cached=json.loads(path.read_text())
            if cached['adapter_hash']==adapter:
                observations.append(cached);metrics['reused_frames']+=1;continue
        if log or message or snapshot:
            if f['sha256'] in reused:
                old=reused[f['sha256']]
                for k in ('log','message','backend','log_segmentation_version'):
                    if k in old:record[k]=old[k]
                metrics['reused_frames']+=1
            else:
                if log:record['log']=extract_view(image,load_backend(),f['source_id'],f['timestamp'],f['sha256']);record['log']['path']=f['image'];metrics['log_frames']+=1
                elif message:
                    # Keep text observations independent of any synthetic log.
                    bounds=box(image,(.22,.685,.64,.797));x1,y1,x2,y2=bounds
                    hsv=cv2.cvtColor(image[y1:y2,x1:x2],cv2.COLOR_BGR2HSV)
                    foreground=((hsv[:,:,1]<70)&(hsv[:,:,2]>200)).astype('uint8')
                    signature=hashlib.sha256(foreground.tobytes()).hexdigest()
                    if signature!=previous_message:
                        obs=load_backend().read(image,bounds,multiline=True)
                        record['message']={'raw_text':obs.raw_text,'confidence':obs.confidence,'box':bounds,'origin':'automatic_video_message_ocr'}
                        metrics['message_frames']+=1
                    else:record['message_duplicate_foreground']=True
                    previous_message=signature
                metrics['new_frames']+=1
            if snapshot and paths.battle_id!='sample_battle_3':
                load_backend()
                record['snapshot']=recognizer.recognize(Frame(image,f['source_id'],index=index,timestamp=f['timestamp'],metadata=f)).to_dict()
                metrics['snapshot_frames']+=1
        record['adapter_hash']=adapter;save(path,record);observations.append(record)
        if index%30==0:print(f"{paths.battle_id}: OCR checkpoint {index}/{len(survey['frames'])}; calls={metrics['read_calls']}",flush=True)
    # Preserve dense historical observations as reusable raw input, never validated current states.
    extra=list(reused.values())
    result={'schema_version':1,'battle_id':paths.battle_id,'adapter_hash':adapter,'model':model_manifest,
            'observations':observations,'additional_cached_observations':extra,'metrics':dict(metrics,elapsed_seconds=round(time.monotonic()-start,3)),
            'policy':'Single CPU OCR backend; batch_size=1; messages/logs only plus ~18s stable HUD checkpoints; no corrected text is imported'}
    save(destination,result);return result,False
