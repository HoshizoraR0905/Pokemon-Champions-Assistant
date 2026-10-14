"""Scoped acquisition/selection/OCR; no state replay. Sampling FPS defaults to 2."""
import argparse
from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import hashlib
import json
import math
from pathlib import Path
import resource
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import SamplingConfig,DEFAULT_SAMPLE_FPS,acquire,fingerprint,atomic_json
from recognition.message_selection import SelectionConfig,MessageSelector,ROI
from recognition.phases import classify_phase
from recognition import box


@contextmanager
def battle_lock(paths):
    p=paths.cache('m233b1/processing.lock');p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('a') as stream:
        try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Another B1 process owns this battle; resume it instead')
        try:yield
        finally:fcntl.flock(stream,fcntl.LOCK_UN)


def source_identity(paths):
    from scripts.validate_m232 import video_identity
    current=video_identity(paths.video())
    prior=paths.cache('m232/survey.json')
    if prior.exists() and current!=json.loads(prior.read_text())['video_fingerprint']:
        raise ValueError('Recording differs from existing cached evidence')
    return current


class CachedMessageOCR:
    def __init__(self,paths,identity):
        self.paths=paths;self.identity=identity;self.backend=None
        self.model=ROOT/'.cache/m15-onnx-medium';self.model_manifest=json.loads((self.model/'local-manifest.json').read_text())
        backend_hash=hashlib.sha256((ROOT/'recognition/onnx_ocr.py').read_bytes()).hexdigest()
        self.config=dict(model=self.model_manifest,backend_sha256=backend_hash,provider='cpu',batch_size=1,
            multiline=True,numeric=False,italic=False,roi=ROI,preprocessing='unchanged ONNXOCRBackend.read')
        self.config['asset_stats']={p.name:dict(size=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns) for p in self.model.iterdir() if p.name in self.model_manifest['files']}
        self.identity_hash=fingerprint(self.config)
        self.counts=dict(new_read_calls=0,predicted_crops=0,inference_batches=0,cache_hits=0,legacy_hits=0,inference_seconds=0.)
        self.legacy={}
        old_path=paths.cache('m232/observations.json');survey_path=paths.cache('m232/survey.json')
        if not old_path.exists() or not survey_path.exists():return
        old=json.loads(old_path.read_text());survey=json.loads(survey_path.read_text())
        from scripts.validate_m232 import digest
        adapter=digest({'version':1,'model':self.model_manifest,'video':survey['video_fingerprint'],
            'code':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['recognition/__init__.py','recognition/phases.py','recognition/battle_log.py','recognition/onnx_ocr.py','scripts/m232_observations.py']}})
        self.legacy={r['sha256']:r for r in old['observations'] if r.get('message')} if old['model']==self.model_manifest and old['adapter_hash']==adapter else {}

    def key(self,image):
        bounds=box(image,ROI);a,b,c,d=bounds;crop=image[b:d,a:c]
        return fingerprint(dict(video=self.identity,ocr=self.identity_hash,bounds=bounds,
            crop_shape=crop.shape,crop_sha256=hashlib.sha256(crop.tobytes()).hexdigest()))

    def read(self,row,image):
        key=self.key(image);p=self.paths.cache('m233b1/ocr/'+key+'.json')
        if p.exists():
            self.counts['cache_hits']+=1;return json.loads(p.read_text()),'b1_cache'
        bounds=box(image,ROI);prior=self.legacy.get(row['sha256'])
        if prior and list(prior['message']['box'])==list(bounds):
            value=dict(prior['message'],ocr_key=key,model_identity=self.identity_hash,origin='compatible_m232_raw_ocr')
            atomic_json(p,value);self.counts['legacy_hits']+=1;return value,'legacy_cache'
        if self.backend is None:
            from recognition.onnx_ocr import ONNXOCRBackend
            self.backend=ONNXOCRBackend(self.model,provider='cpu',batch_size=1)
            predict=self.backend.predict
            def counted(crops):
                self.counts['predicted_crops']+=len(crops);self.counts['inference_batches']+=len(crops)
                return predict(crops)
            self.backend.predict=counted
        started=time.perf_counter();obs=self.backend.read(image,bounds,multiline=True)
        elapsed=time.perf_counter()-started;self.counts['new_read_calls']+=1;self.counts['inference_seconds']+=elapsed
        value=dict(ocr_key=key,raw_text=obs.raw_text,confidence=obs.confidence,box=list(bounds),
            model_identity=self.identity_hash,origin='scoped_b1_new_ocr',elapsed_seconds=elapsed)
        atomic_json(p,value);return value,'new'


def choose(rows,config):
    import cv2
    selector=MessageSelector(config);output=[];started=time.perf_counter()
    for row in rows:
        image=cv2.imread(str(ROOT/row['image']));phase= row.get('phase') or classify_phase(image)[0]
        decision=selector.select(image,phase,timestamp=row['timestamp'],log_visible=bool(row.get('log_geometry')))
        output.append(dict(row,phase=phase,selection=decision))
    return output,time.perf_counter()-started


def run(paths,sampling,start,end,selection,stage):
    import cv2
    if not math.isfinite(start) or not math.isfinite(end) or not 0<=start<end:
        raise ValueError('An explicit finite positive interval is required')
    identity=source_identity(paths)
    ocr=CachedMessageOCR(paths,identity) if stage=='ocr' else None
    run_key=fingerprint(dict(video=identity,sampling=asdict(sampling),sampler_identity=sampling.identity(identity),
                            ocr_identity=ocr.identity_hash if ocr else None,
                            phase_code={str(p):hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['recognition/phases.py','recognition/__init__.py']},start=float(start),end=float(end),
                            selection=asdict(selection),stage=stage,selection_code=hashlib.sha256((ROOT/'recognition/message_selection.py').read_bytes()).hexdigest()))
    manifest_path=paths.cache('m233b1/runs/'+run_key+'/manifest.json')
    if manifest_path.exists():
        prior=json.loads(manifest_path.read_text())
        target=ROOT/prior.get('observations','__missing__')
        if prior.get('status')=='complete' and target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==prior.get('observations_sha256'):
            saved=json.loads(target.read_text())
            if all((ROOT/r['image']).is_file() and hashlib.sha256((ROOT/r['image']).read_bytes()).hexdigest()==r['sha256'] for r in saved['frames']):
                return dict(prior,reused_complete_run=True,current_invocation_ocr_calls=0)
    value=dict(status='running',battle_id=paths.battle_id,video_fingerprint=identity,sampling=asdict(sampling),
               selection=asdict(selection),interval=[start,end],stage=stage)
    atomic_json(manifest_path,value)
    try:
        started=time.perf_counter();frames=acquire(paths,identity,sampling,start,end);acquisition=time.perf_counter()-started
        rows,selection_time=choose(frames,selection)
        for i,row in enumerate(rows):
            if ocr and row['selection']['selected']:
                row['message'],row['ocr_reuse']=ocr.read(row,cv2.imread(str(ROOT/row['image'])))
            if ocr and i%10==0:print(f'{paths.battle_id}: OCR progress {i}/{len(rows)} calls={ocr.counts["new_read_calls"]}',flush=True)
        output=manifest_path.parent/'observations.json';atomic_json(output,dict(battle_id=paths.battle_id,frames=rows))
        value.update(status='complete',frames=len(frames),ocr_candidates=sum(r['selection']['selected'] for r in rows),
            acquisition_seconds=acquisition,selection_seconds=selection_time,ocr_counts=ocr.counts if ocr else None,
            observations=str(output.relative_to(ROOT)),observations_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
            process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024))
        atomic_json(manifest_path,value);return value
    except Exception as exc:
        value.update(status='failed',error=f'{type(exc).__name__}: {exc}');atomic_json(manifest_path,value);raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--battle-id',required=True);parser.add_argument('--start',type=float,required=True)
    parser.add_argument('--duration',type=float,required=True);parser.add_argument('--sample-fps',type=float,default=DEFAULT_SAMPLE_FPS)
    parser.add_argument('--policy',choices=['baseline','reduced','temporal','hybrid'],default='hybrid')
    parser.add_argument('--selection-config',type=Path,help='JSON overrides of SelectionConfig thresholds')
    parser.add_argument('--stage',choices=['select','ocr'],default='select')
    args=parser.parse_args();paths=BattleArtifacts(args.battle_id).prepare()
    options=json.loads(args.selection_config.read_text()) if args.selection_config else {};options['policy']=args.policy
    with battle_lock(paths):
        print(json.dumps(run(paths,SamplingConfig(args.sample_fps),args.start,args.start+args.duration,SelectionConfig(**options),args.stage),ensure_ascii=False))
