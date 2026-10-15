"""Bounded orchestration over existing sampling, OCR and replay adapters."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import SamplingConfig, acquire, atomic_json, fingerprint


class ScopedArtifacts(BattleArtifacts):
    def cache(self,name):
        name=str(name)
        if name.startswith('m233b1/'):
            return super().cache('m235/acquisition/'+name[len('m233b1/'):])
        return super().cache(name)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def survey(paths):
    import cv2,numpy as np
    from recognition.phases import classify_phase
    media=json.loads(paths.cache('m235/media.json').read_text());identity=media['identity']
    target=paths.cache('m235/survey.json')
    if target.exists():
        data=json.loads(target.read_text());assert data['video_fingerprint']==identity
        assert all(sha(ROOT/r['image'])==r['sha256'] for r in data['frames']);print('Reused survey');return
    rows=[]
    for t in range(0,int(identity['metadata']['duration_seconds']),20):
        frames=acquire(paths,identity,SamplingConfig(),t,t+.5)
        for r in frames:r['phase']=classify_phase(cv2.imread(str(ROOT/r['image'])))[0]
        rows+=frames;atomic_json(paths.cache('m235/survey-progress.json'),dict(status='partial',frames=rows))
    atomic_json(target,dict(status='complete',video_fingerprint=identity,policy='one 2-FPS grid cell per 20 seconds; phase survey only',frames=rows))
    for offset in range(0,len(rows),12):
        group=rows[offset:offset+12];sheet=np.full((4*295,3*600,3),245,np.uint8)
        for j,r in enumerate(group):
            image=cv2.imread(str(ROOT/r['image']));image=cv2.resize(image,(600,276));y=j//3*295;x=j%3*600
            sheet[y:y+276,x:x+600]=image;cv2.putText(sheet,f"{r['timestamp']:.3f}s {r['phase']}",(x+5,y+290),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,0,0),1)
        cv2.imwrite(str(paths.cache(f'm235/survey-{offset//12}.jpg')),sheet)
    print('Survey complete',len(rows),'frames; zero OCR',flush=True)



class PredictionBudgetExceeded(RuntimeError):pass


class CropCache:
    """Existing ONNX read/predict behavior with bounded, pixel-addressed persistence."""
    def __init__(self,paths,budget,*,cache_only=True):
        self.paths=paths;self.budget=budget;self.backend=None;self.new=0;self.hits=0
        self.cache_only=cache_only
        self.identity=dict(backend=sha(ROOT/'recognition/onnx_ocr.py'),model=sha(ROOT/'.cache/m15-onnx-medium/local-manifest.json'),provider='cpu',batch_size=1)
    def load(self):
        if self.backend is None:
            from recognition.onnx_ocr import ONNXOCRBackend
            # Reuse read()'s crop geometry and serialization without loading a
            # model or allowing inference in the recovery/evaluation workflow.
            self.backend=ONNXOCRBackend.__new__(ONNXOCRBackend)
            self.backend.threshold=.75;self.backend.language='zh-Hans+en'
            self.backend.model_name='PP-OCRv6_medium_rec-onnx-cpu';self.backend.warnings=[]
            inference=None
            def cached(crops):
                output=[]
                for crop in crops:
                    key=fingerprint(dict(shape=list(crop.shape),pixels=hashlib.sha256(crop.tobytes()).hexdigest(),**self.identity))
                    path=self.paths.cache('m235/reads/'+key+'.json')
                    if path.exists():
                        self.hits+=1;output.append(json.loads(path.read_text()));continue
                    if self.cache_only:raise PredictionBudgetExceeded('Cached prediction unavailable; inference disabled')
                    used=len(list(self.paths.cache('m235/reads').glob('*.json')))
                    if used>=self.budget:raise PredictionBudgetExceeded('Prediction budget exhausted; individual successful reads are retained')
                    nonlocal inference
                    if inference is None:inference=ONNXOCRBackend(ROOT/'.cache/m15-onnx-medium',provider='cpu',batch_size=1)
                    reading=inference.predict([crop])[0];atomic_json(path,reading);self.new+=1;output.append(reading)
                return output
            self.backend.predict=cached
        return self.backend
    @property
    def warnings(self):return self.load().warnings
    def read(self,*args,**kwargs):return self.load().read(*args,**kwargs)
    def predict(self,*args,**kwargs):return self.load().predict(*args,**kwargs)


def acquire_plan(paths):
    media=json.loads(paths.cache('m235/media.json').read_text());plan=json.loads(paths.cache('m235/plan.json').read_text());frames=[]
    for a,b in plan['windows']:frames+=acquire(paths,media['identity'],SamplingConfig(plan['sample_fps']),a,b)
    context=json.loads(paths.cache('m235/survey.json').read_text())['frames']
    frames += [r for r in context if round(r['target_timestamp']) in plan['context_times']]
    frames={r['sha256']:r for r in frames}
    atomic_json(paths.cache('m235/acquisition.json'),dict(status='complete',frames=sorted(frames.values(),key=lambda r:r['timestamp']),plan=plan,video_fingerprint=media['identity']))


def recognize_baseline(paths):
    import cv2
    from capture import Frame
    from recognition import Recognizer, classify, box
    from recognition.phases import classify_phase
    from recognition.message_selection import SelectionConfig,MessageSelector,ROI
    from recognition.visual_evidence import popup_regions,detail_layout,DETAIL_ROIS,normalized_box,variants,parse_popup,parse_detail,stage_arrows
    pre=json.loads(paths.cache('m235/prechange.json').read_text())
    assert all(sha(ROOT/p)==h for p,h in pre['code'].items()), 'Prechange implementation changed before baseline freeze'
    plan=json.loads(paths.cache('m235/plan.json').read_text());frames=json.loads(paths.cache('m235/acquisition.json').read_text())['frames']
    cache=CropCache(paths,plan['prediction_budget']);selector=MessageSelector(SelectionConfig());recognizer=Recognizer(cache,icons=True)
    identity=dict(video=json.loads(paths.cache('m235/media.json').read_text()),plan=plan,code=pre['code'],ocr=cache.identity,selection=SelectionConfig().__dict__)
    manifest=paths.cache('m235/baseline-recognition-manifest.json');target=paths.cache('m235/baseline-observations.json')
    if manifest.exists():
        old=json.loads(manifest.read_text())
        if old['status']=='complete' and old['identity']==identity and sha(target)==old['sha256']:print('Reused complete baseline recognition');return
    atomic_json(manifest,dict(status='running',identity=identity));rows=[];began=time.perf_counter();hud_count=0;previous_detail=False;previous_t=None
    try:
        for i,r in enumerate(frames):
            image=cv2.imread(str(ROOT/r['image']));phase=classify_phase(image)[0];decision=selector.select(image,phase,timestamp=r['timestamp'])
            per=paths.cache('m235/baseline-frames/'+r['sha256']+'.json')
            is_detail=detail_layout(image)
            trigger_detail=is_detail and (not previous_detail or previous_t is None or r['target_timestamp']-previous_t>.500001)
            previous_detail=is_detail;previous_t=r['target_timestamp']
            if per.exists():rows.append(json.loads(per.read_text()));continue
            row=dict(r,visual_phase=phase,selection=decision)
            if decision['selected']:
                read=cache.read(image,box(image,ROI),multiline=True)
                row['message']=dict(raw_text=read.raw_text,confidence=read.confidence,box=list(read.region))
            # Sparse snapshots only, not recognition on every sampled frame.
            anchor=any(abs(r['target_timestamp']-a)<1e-6 or abs(r['target_timestamp']-(b-.5))<1e-6 for a,b in plan['windows']) or r['target_timestamp'] in plan['context_times']
            if anchor and classify(image)[0] in {'battle_screen','move_selection'}:
                row['snapshot']=recognizer.recognize(Frame(image,r['source_id'],index=i,timestamp=r['timestamp'],metadata=r)).to_dict();hud_count+=1
            layout=[]
            for region in popup_regions(image):layout += [(region['side']+':species',region['lines'][0]),(region['side']+':ability',region['lines'][1])]
            if trigger_detail:layout += [(k,normalized_box(image,v)) for k,v in DETAIL_ROIS.items()]
            readings={}
            for label,bounds in layout[:8]:
                readings[label]=[dict(**cache.predict([crop])[0],box=bounds,config_id=label+':'+config,source_sha256=r['sha256']) for config,crop in variants(image,bounds)]
            parsed=[]
            for side in ['self','opponent']:
                if side+':species' in readings:parsed.append(dict(kind='popup',side=side,**parse_popup({k:readings.get(side+':'+k,[]) for k in ['species','ability']})))
            if 'species' in readings:parsed.append(dict(kind='detail',**parse_detail(readings,stage_arrows(image))))
            row['visual']=dict(readings=readings,parsed=parsed,layout=layout)
            atomic_json(per,row);rows.append(row)
            atomic_json(paths.cache('m235/baseline-progress.json'),dict(status='partial',completed=len(rows),total=len(frames),new_predictions=cache.new))
            print('Baseline',i+1,'/',len(frames),'predictions',cache.new,'hits',cache.hits,flush=True)
        atomic_json(target,dict(status='complete',battle_id=paths.battle_id,observations=rows,additional_cached_observations=[]))
        atomic_json(manifest,dict(status='complete',identity=identity,sha256=sha(target),new_predictions=cache.new,total_cached_predictions=len(list(paths.cache('m235/reads').glob('*.json'))),cache_hits=cache.hits,seconds=time.perf_counter()-began))
    except Exception as exc:
        atomic_json(manifest,dict(status='error',identity=identity,error=repr(exc),completed=len(rows),new_predictions=cache.new));raise


def replay(paths,variant,*,observations_name=None,output_name=None):
    if variant=='baseline' and paths.cache('m235/baseline-seal.json').exists():
        seal=json.loads(paths.cache('m235/baseline-seal.json').read_text())
        assert all(sha(ROOT/p)==h for p,h in seal['outputs'].items())
        print('Reused frozen baseline replay; no writes');return
    from scripts.replay_m233a import events_from_cache
    from recognition.visual_adapter import visual_events,selected_panel_side
    from tracking.state_engine import StateEngine,EventRecord,event_from_dict,ordering
    from tracking.battle_state import BattleState
    from tracking.hidden_state import HiddenEngine
    from dataclasses import asdict
    import cv2
    observations_name=observations_name or ('baseline' if variant=='baseline' else 'final')+'-observations.json'
    data=json.loads(paths.cache('m235/'+observations_name).read_text());events=events_from_cache(data,[],paths.battle_id)
    byhash={r['sha256']:r for r in data['observations']}
    if variant!='baseline':
        for e in events:
            source=next((byhash[oid] for s in e['evidence'] for oid in s['observation_ids'] if oid in byhash),None)
            if source and source.get('recovery') and e['event_type']!='hud_observation':e['attributes']['move_ocr_alternatives']=source['recovery']['alternatives']
            if source and source.get('exact_crop_reuse') and e['event_type']=='hud_observation':
                e['attributes']['display_equivalence']=[p['sample_equivalence'] for p in source['snapshot']['pokemon'] if p.get('sample_equivalence')]
                e['evidence'][0]['details']['display_equivalence']=deepcopy(e['attributes']['display_equivalence'])
        from battle_events.schema import BattleEvent,Evidence,stable_id
        previous=None
        for row in data['observations']:
            if previous and abs(row['target_timestamp']-previous['target_timestamp']-.5)>1e-6:
                attrs=dict(battle_id=paths.battle_id,start=previous['timestamp'],observation_time=row['timestamp'],status='gap',fields=['occupancy','hp','stages','ability','item','form'])
                events.append(BattleEvent(stable_id(paths.battle_id,'coverage:'+row['sha256']),'coverage_observation','field',None,None,'missing sampled cells',{},None,[Evidence('sampling_manifest',str(paths.cache('m235/acquisition.json').relative_to(ROOT)),[row['sha256']],dict(timestamp=row['timestamp'],previous_sha256=previous['sha256'],basis='missing 2-FPS target cells; no interval continuity asserted'))],None,'supported',[],attrs).to_dict())
            previous=row
    for row in data['observations']:
        for parsed in row['visual']['parsed']:
            kind=parsed['kind'];r=dict(request=dict(battle_id=paths.battle_id,kind=kind,image=row['image'],sha256=row['sha256'],timestamp=row['timestamp']),parsed=[parsed] if kind=='popup' else parsed,readings=row['visual']['readings'],identity=dict(layout=row['visual']['layout']))
            selection=selected_panel_side(cv2.imread(str(ROOT/row['image']))) if kind=='detail' else None
            events += [e.to_dict() for e in visual_events(r,selection=selection)]
    if variant!='baseline':
        for row in data['observations']:
            panel=row.get('party_panel')
            if not panel:continue
            r=dict(request=dict(battle_id=paths.battle_id,kind='party_panel',image=row['image'],sha256=row['sha256'],timestamp=row['timestamp']),parsed=panel['parsed'],readings=panel['readings'],identity=dict(layout=panel['selection']))
            events += [e.to_dict() for e in visual_events(r,selection=panel['selection'])]
    events.sort(key=lambda e:(e['attributes']['observation_time'],-1 if e['event_type']=='coverage_observation' else 0 if e['event_type']=='hud_observation' else 1,e['event_id']))
    engine=StateEngine(BattleState(paths.battle_id,knowledge={'reliability_v1':True,**({'reliability_v2':True} if variant!='baseline' else {})}));hidden=HiddenEngine();hidden.seed(engine.initial.to_dict());snapshots=[]
    for i,e in enumerate(events,1):e['attributes']['sequence']=i;engine.history.append(EventRecord(e,i,ordering(event_from_dict(e))))
    def capture(r,state):
        e=deepcopy(r.bindings.get('resolved_event',r.event))
        if r.bindings.get('identity'):e['actor']=r.bindings['identity']
        if r.bindings.get('visual_receipt'):e['attributes']['visual_receipt']=r.bindings['visual_receipt']
        hidden.apply(e,instance_id=r.bindings.get('actor',{}).get('pokemon_instance_id'),side=e['side'],sequence=r.delivery_index,application_status=r.application_status)
        snapshots.append(dict(timestamp=r.event['attributes']['observation_time'],event_id=r.event['event_id'],state=state.to_dict()))
    engine.replay(snapshot_callback=capture)
    queries=[row['timestamp'] for row in data['observations']]
    # Build an as-of projection from each completed timestamp group, without future state.
    projections={}
    from tracking.battle_state import from_dict
    for t in queries:
        candidates=[s for s in snapshots if s['timestamp']<=t]
        prefix=StateEngine(from_dict(candidates[-1]['state']) if candidates else engine.initial)
        prefix.history=deepcopy([r for r in engine.history if r.event['attributes'].get('observation_time',float('inf'))<=t])
        projections[str(t)]=prefix.evidence_projection(as_of=t)
    result=dict(status='complete',identity=dict(observations_sha256=sha(paths.cache('m235/'+observations_name)),code={p:sha(ROOT/p) for p in json.loads(paths.cache('m235/prechange.json').read_text())['code']}),engine=engine.to_dict(),hidden=hidden.to_dict(),snapshots=snapshots,projections=projections)
    output=paths.cache('m235/'+(output_name or variant+'-replay.json'));atomic_json(output,result)
    if variant=='baseline':
        pre=json.loads(paths.cache('m235/prechange.json').read_text());assert all(sha(ROOT/p)==h for p,h in pre['code'].items())
        outputs=[paths.cache('m235/'+name) for name in ['media.json','plan.json','acquisition.json','baseline-observations.json','baseline-recognition-manifest.json','baseline-replay.json']]
        atomic_json(paths.cache('m235/baseline-seal.json'),dict(status='frozen',code=pre['code'],outputs={str(p.relative_to(ROOT)):sha(p) for p in outputs},orchestrator_sha256=sha(__file__)))
    print(variant,'replay complete',len(events),'events',flush=True)


def enhance(paths):
    import cv2
    from recognition.visual_evidence import variants,normalized_box
    from recognition.message_recovery import message_layout,context_variants,execution_prefix
    from recognition.party_panel import layout as party_layout,parse as parse_party
    from recognition.hud_reuse import reuse
    seal=json.loads(paths.cache('m235/baseline-seal.json').read_text())
    assert all(sha(ROOT/p)==h for p,h in seal['outputs'].items()),'Frozen baseline modified'
    rows=json.loads(paths.cache('m235/baseline-observations.json').read_text())['observations']
    cache=CropCache(paths,450);output=[];prior=None;prior_image=None;started=time.perf_counter()
    recipe=fingerprint({p:sha(ROOT/p) for p in ['recognition/message_recovery.py','recognition/party_panel.py','recognition/hud_reuse.py']})
    for row in rows:
        image=cv2.imread(str(ROOT/row['image']));target=paths.cache('m235/enhanced-frames/'+recipe+'/'+row['sha256']+'.json')
        if target.exists():out=json.loads(target.read_text())
        else:
            out=deepcopy(row);out['recognition_gaps']=[]
            def read_variants(variants_,label):
                reads=[]
                for name,crop,bounds in variants_:
                    try:reading=cache.predict([crop])[0]
                    except PredictionBudgetExceeded:
                        out['recognition_gaps'].append(dict(label=label,config_id=name,box=bounds,reason='prediction_budget_exhausted'));continue
                    reads.append(dict(**reading,box=bounds,config_id=label+':'+name,source_sha256=row['sha256']))
                return reads
            boxes=message_layout(image,row['visual_phase']);readings={}
            for index,bounds in enumerate(boxes):
                variants_=[(n,c,bounds) for n,c in variants(image,bounds)] if index==0 else context_variants(image,bounds,normalized_box(image,(.22,.685,.64,.797))[2])
                readings['line'+str(index)]=read_variants(variants_,'line'+str(index))
            if readings:
                prefix=execution_prefix(readings['line0'])
                out['recovery']=dict(readings=readings,prefix=prefix,alternatives=readings.get('line1',[]))
                # Never bypass move confidence by inserting a low-confidence suffix
                # into the parser's primary exact-dictionary path.
                if prefix and not out.get('message'):
                    out['message']=dict(raw_text=prefix,confidence=min(r['confidence'] for r in readings['line0']),box=normalized_box(image,(.22,.685,.64,.797)))
            selection=party_layout(image)
            if selection:
                panel_reads={}
                for key,roi in selection['rois'].items():
                    bounds=normalized_box(image,roi)
                    panel_reads[key]=read_variants([(name,crop,bounds) for name,crop in variants(image,bounds)],key)
                out['party_panel']=dict(parsed=parse_party(panel_reads,selection),readings=panel_reads,selection=selection)
            atomic_json(target,out)
        if out.get('snapshot'):prior=out;prior_image=image
        elif prior:
            snap=reuse(prior,prior_image,out,image)
            if snap:out['snapshot']=snap;out['exact_crop_reuse']=True
        output.append(out)
        atomic_json(paths.cache('m235/enhance-progress.json'),dict(status='partial',completed=len(output),new_predictions=cache.new))
        print('Enhance',len(output),'/',len(rows),'new',cache.new,'hits',cache.hits,flush=True)
    atomic_json(paths.cache('m235/final-observations.json'),dict(status='complete',battle_id=paths.battle_id,observations=output,additional_cached_observations=[]))
    atomic_json(paths.cache('m235/enhance-manifest.json'),dict(status='complete_with_budget_gaps' if any(r.get('recognition_gaps') for r in output) else 'complete',recipe=recipe,budget_gaps=sum(len(r.get('recognition_gaps',[])) for r in output),new_predictions=cache.new,cache_hits=cache.hits,total_predictions=len(list(paths.cache('m235/reads').glob('*.json'))),seconds=time.perf_counter()-started,output_sha256=sha(paths.cache('m235/final-observations.json'))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--battle-id',required=True);p.add_argument('--stage',required=True,choices=['survey','acquire','baseline-ocr','baseline-replay','enhance','final-replay']);a=p.parse_args()
    paths=ScopedArtifacts(a.battle_id).prepare()
    manifest=paths.cache('m235/stages/'+a.stage+'.json')
    atomic_json(manifest,dict(status='running',stage=a.stage,runner_sha256=sha(__file__)))
    try:
        if a.stage in {'survey','acquire','baseline-ocr'}:
            from scripts.validate_m232 import video_identity
            assert video_identity(paths.video())==json.loads(paths.cache('m235/media.json').read_text())['identity'],'Recording changed'
        if a.stage=='survey':survey(paths)
        elif a.stage=='acquire':acquire_plan(paths)
        elif a.stage=='baseline-ocr':recognize_baseline(paths)
        elif a.stage=='enhance':enhance(paths)
        elif a.stage=='final-replay':replay(paths,'final')
        else:replay(paths,'baseline')
        atomic_json(manifest,dict(status='complete',stage=a.stage,runner_sha256=sha(__file__)))
    except Exception as exc:
        atomic_json(manifest,dict(status='error',stage=a.stage,runner_sha256=sha(__file__),error=repr(exc),resume='Repeat this scoped stage; atomic crop predictions and frame results are retained.'))
        raise
