"""Targeted cached-image recognition; no video access or runtime ground truth."""
import argparse,hashlib,json,sys
from pathlib import Path
import cv2
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from recognition.visual_evidence import (line_boxes,normalized_box,variants,popup_regions,detail_layout,DETAIL_ROIS,stage_arrows,parse_detail,parse_popup)
from recognition.move_resolution import resolve_move
from knowledge import KnowledgeBase
from recognition.video_sampling import atomic_json,fingerprint
from battle_artifacts import BattleArtifacts


def run(requests, *, allow_new_ocr=False, max_new_predictions=16):
    backend=None;calls=0;outputs=[]
    for request in requests:
        bid=request['battle_id'];source=ROOT/request['image'];digest=hashlib.sha256(source.read_bytes()).hexdigest()
        assert digest==request['sha256'];image=cv2.imread(str(source));kind=request['kind']
        layout=[]
        if kind=='message':
            layout=[(f'line{i}',b) for i,b in enumerate(line_boxes(image,normalized_box(image,(.22,.685,.64,.797))))]
        elif kind=='popup':
            for region in popup_regions(image):
                layout.extend([(region['side']+':species',region['lines'][0]),(region['side']+':ability',region['lines'][1])])
        elif kind=='detail' and detail_layout(image):
            layout=[(name,normalized_box(image,b)) for name,b in DETAIL_ROIS.items()]
        identity=dict(source_sha256=digest,kind=kind,layout=layout,
            code=hashlib.sha256((ROOT/'recognition/visual_evidence.py').read_bytes()).hexdigest(),
            backend=hashlib.sha256((ROOT/'recognition/onnx_ocr.py').read_bytes()).hexdigest(),
            model=hashlib.sha256((ROOT/'.cache/m15-onnx-medium/local-manifest.json').read_bytes()).hexdigest())
        identity=json.loads(json.dumps(identity))  # JSON canonicalizes layout tuples to lists.
        target=BattleArtifacts(bid,ROOT).cache(f'm234/visual/{fingerprint(identity)}.json')
        if target.exists():out=json.loads(target.read_text());assert out['identity']==identity
        else:
            readings={}
            for label,bounds in layout[:8]:
                readings[label]=[]
                for config,crop in variants(image,bounds):
                    crop_key=fingerprint(dict(crop_sha256=hashlib.sha256(crop.tobytes()).hexdigest(),backend=identity['backend'],model=identity['model']))
                    crop_path=BattleArtifacts(bid,ROOT).cache(f'm234/reads/{crop_key}.json')
                    if crop_path.exists():
                        reading=json.loads(crop_path.read_text())
                        if not isinstance(reading.get('text'),str) or not 0<=reading['confidence']<=1:raise ValueError('Invalid crop cache '+str(crop_path))
                        readings[label].append(dict(**reading,box=bounds,config_id=label+':'+config,source_sha256=digest))
                        continue
                    if not allow_new_ocr:raise RuntimeError('Missing crop cache; OCR disabled: '+str(crop_path))
                    if calls>=max_new_predictions:raise RuntimeError('New prediction budget exhausted; completed crops are saved')
                    if backend is None:
                        from recognition.onnx_ocr import ONNXOCRBackend
                        backend=ONNXOCRBackend(ROOT/'.cache/m15-onnx-medium',provider='cpu',batch_size=1)
                    reading=backend.predict([crop])[0];calls+=1
                    atomic_json(crop_path,reading)
                    readings[label].append(dict(**reading,box=bounds,config_id=label+':'+config,source_sha256=digest))
            if kind=='popup':
                parsed=[dict(side=side,**parse_popup({name:readings.get(side+':'+name,[]) for name in ['species','ability']})) for side in ['self','opponent'] if side+':species' in readings]
            elif kind=='detail':parsed=parse_detail(readings,stage_arrows(image)) if layout else dict(status='not_detail_layout')
            else:
                alternatives=[v for key,rows in readings.items() if key!='line0' for v in rows]
                parsed=resolve_move(request.get('original_move_text',''),KnowledgeBase(),alternatives)
            out=dict(status='complete',identity=identity,readings=readings,parsed=parsed);atomic_json(target,out)
        row=dict(request=request,artifact=str(target.relative_to(ROOT)),**out);outputs.append(row)
        atomic_json(ROOT/'.cache/m234/visual-progress.json',dict(status='partial',results=outputs,new_predictions=calls))
        print(bid,request['timestamp'],kind,json.dumps(out['parsed'],ensure_ascii=False)[:650],flush=True)
    result=dict(status='complete',new_predictions=calls,results=outputs)
    atomic_json(ROOT/'.cache/m234/visual-progress.json',result)
    atomic_json(ROOT/'.cache/m234/visual-results.json',result);print('New targeted predictions',calls,flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--requests',required=True)
    p.add_argument('--allow-new-ocr',action='store_true');p.add_argument('--max-new-predictions',type=int,default=16)
    a=p.parse_args()
    if a.max_new_predictions<0:p.error('Prediction budget must be nonnegative')
    request_path=Path(a.requests)
    identity=dict(requests_sha256=hashlib.sha256(request_path.read_bytes()).hexdigest(),
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        adapter_sha256=hashlib.sha256((ROOT/'recognition/visual_evidence.py').read_bytes()).hexdigest())
    manifest=ROOT/'.cache/m234/recognition-manifest.json'
    atomic_json(manifest,dict(status='running',identity=identity,allow_new_ocr=a.allow_new_ocr,max_new_predictions=a.max_new_predictions))
    try:
        result=run(json.loads(request_path.read_text()),allow_new_ocr=a.allow_new_ocr,max_new_predictions=a.max_new_predictions)
        output=ROOT/'.cache/m234/visual-results.json'
        atomic_json(manifest,dict(status='complete',identity=identity,new_predictions=result['new_predictions'],output=str(output.relative_to(ROOT)),sha256=hashlib.sha256(output.read_bytes()).hexdigest()))
    except Exception as exc:
        atomic_json(manifest,dict(status='error',identity=identity,error=repr(exc),resume='Repeat scoped request; completed individual crop caches are retained.'))
        raise
