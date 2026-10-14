"""Bounded OCR alternatives for four cached move crops; no video access."""
import hashlib,json,sys
from pathlib import Path
import cv2
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from recognition.video_sampling import atomic_json,fingerprint
from recognition.onnx_ocr import ONNXOCRBackend

CASES=[('sample_battle_0',262),('sample_battle_0',338),('sample_battle_1',450),('sample_battle_1',504)]

def run():
    backend=None;calls=0;results=[]
    for bid,t in CASES:
        data=json.loads((ROOT/f'.cache/battles/{bid}/m232/observations.json').read_text())
        row=min(data['observations'],key=lambda r:abs(r['timestamp']-t))
        source=ROOT/row['image'];assert hashlib.sha256(source.read_bytes()).hexdigest()==row['sha256']
        im=cv2.imread(str(source));x,y,X,Y=row['message']['box'];roi=im[y:Y,x:X]
        # Fixed UI line bands and left text region, shared across all examples.
        # No expected move, battle timestamp or evaluation label enters OCR.
        for config in ['line2-native','line2-double','line2-gray']:
            crop=roi[32:62,:260].copy()
            if config=='line2-double':crop=cv2.resize(crop,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC)
            if config=='line2-gray':crop=cv2.cvtColor(cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY),cv2.COLOR_GRAY2BGR)
            identity=dict(source_sha256=row['sha256'],source_id=row['source_id'],config_id=config,
                crop_sha256=hashlib.sha256(crop.tobytes()).hexdigest(),
                code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                backend_sha256=hashlib.sha256((ROOT/'recognition/onnx_ocr.py').read_bytes()).hexdigest(),
                model_manifest_sha256=hashlib.sha256((ROOT/'.cache/m15-onnx-medium/local-manifest.json').read_bytes()).hexdigest())
            target=ROOT/f'.cache/battles/{bid}/m233b2/ocr/{fingerprint(identity)}.json'
            if target.exists():out=json.loads(target.read_text());assert out['identity']==identity
            else:
                if backend is None:backend=ONNXOCRBackend(ROOT/'.cache/m15-onnx-medium',provider='cpu',batch_size=1)
                value=backend.predict([crop])[0];calls+=1
                out=dict(status='complete',identity=identity,reading=value);atomic_json(target,out)
            results.append(dict(battle_id=bid,timestamp=row['timestamp'],image=row['image'],source_sha256=row['sha256'],config_id=config,**out['reading']))
            print(bid,t,config,out['reading'],flush=True)
    atomic_json(ROOT/'.cache/m233b2/recovery.json',dict(status='complete',current_invocation_calls=calls,results=results))
    print('New bounded crop predictions:',calls)
if __name__=='__main__':run()
