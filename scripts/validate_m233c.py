"""Frozen C validation only: bounded acquisition/OCR, review aids and replay."""
import argparse,hashlib,json,sys,time,resource
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import SamplingConfig,acquire,atomic_json,fingerprint
from recognition.message_selection import SelectionConfig
from scripts.validate_m233b1 import run,source_identity,battle_lock

INTERVALS={'sample_battle_2':(292,304),'sample_battle_4':(450,458)}

class ValidationPaths:
    def __init__(self,bid,kind='measurement'):
        self.base=BattleArtifacts(bid);self.battle_id=bid;self.root=self.base.root;self.kind=kind
    def cache(self,name):
        if str(name).startswith('m233b1/'):
            return self.base.cache('m233c/'+self.kind+'/'+str(name).removeprefix('m233b1/'))
        return self.base.cache(name)
    def video(self):return self.base.video()


def preserve(check=False):
    target=ROOT/'.cache/m233c/prior-artifacts.json'
    if check:
        saved=json.loads(target.read_text())
        for p,h in saved.items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
        print('Prior artifacts unchanged:',len(saved));return
    if target.exists():preserve(True);return
    files=set()
    for root in (ROOT/'.cache/battles').glob('sample_battle_*'):
        for stage in ['m232','m233a']:
            p=root/stage/'pipeline-manifest.json';files.add(p);d=json.loads(p.read_text())
            outputs=d['stages']['replay']['outputs'] if stage=='m232' else d['outputs']
            files.update(ROOT/q for q in outputs)
        for pattern in ['m233b1/**/frames.json','m233b1/runs/*/*.json','m233b1/experiment/*.json','m233b2/replay/*.json','m233b2/ocr/*.json']:
            files.update(root.glob(pattern))
    files.update((ROOT/'reports').glob('M2.3.3-*.md'))
    atomic_json(target,{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)})
    print('Preserved prior file identities:',len(files))


def prepare(bid,stage):
    start,end=INTERVALS[bid];paths=ValidationPaths(bid);identity=source_identity(paths)
    if stage=='reference':
        target=paths.base.cache('m233c/reference.json')
        if target.exists():
            d=json.loads(target.read_text());assert all(hashlib.sha256((ROOT/r['image']).read_bytes()).hexdigest()==r['sha256'] for r in d['frames']);print('Reused reference',bid);return
        began=time.perf_counter()
        with battle_lock(paths.base):rows=acquire(ValidationPaths(bid,'reference'),identity,SamplingConfig(10),start,end)
        atomic_json(target,dict(battle_id=bid,interval=[start,end],reference_fps=10,frames=rows,seconds=time.perf_counter()-began,
            limitation='10 FPS reference census; sub-0.1-second observations not exhaustively verified'))
    else:
        with battle_lock(paths.base):value=run(paths,SamplingConfig(2),start,end,SelectionConfig(),stage)
        target=paths.base.cache('m233c/'+stage+'-manifest.json')
        if not target.exists():atomic_json(target,value)
        print(json.dumps(value,ensure_ascii=False))


def contacts(bid):
    import cv2,numpy as np
    data=json.loads(BattleArtifacts(bid).cache('m233c/reference.json').read_text());rows=data['frames']
    # Each cell preserves the message ROI; sparse full-screen reference is separate.
    for offset in range(0,len(rows),48):
        sheet=np.full((16*90,3*551,3),240,np.uint8)
        for j,r in enumerate(rows[offset:offset+48]):
            im=cv2.imread(str(ROOT/r['image']));h,w=im.shape[:2]
            crop=cv2.resize(im[int(.685*h):int(.797*h),int(.22*w):int(.64*w)],(551,68))
            y=j//3*90;x=j%3*551;sheet[y:y+68,x:x+551]=crop
            cv2.putText(sheet,f'{offset+j} {r["timestamp"]:.3f}s',(x+3,y+84),0,.48,(0,0,0),1)
        out=BattleArtifacts(bid).cache(f'm233c/review/messages-{offset//48}.jpg');out.parent.mkdir(parents=True,exist_ok=True);cv2.imwrite(str(out),sheet)
    print(bid,'contact pages',(len(rows)+47)//48)

def seal(check=False):
    target=ROOT/'.cache/m233c/completion-manifest.json'
    if check:
        d=json.loads(target.read_text())
        for name,digest in d['outputs'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
        for name,digest in d['code'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
        print('C completion manifest valid:',len(d['outputs']),'outputs');return
    files=set((ROOT/'.cache/m233c').glob('*.json'))-{target}
    for i in range(5):files.update((ROOT/f'.cache/battles/sample_battle_{i}/m233c').glob('*.json'))
    code=['scripts/validate_m233c.py','scripts/evaluate_m233c.py','scripts/summarize_m233c.py',
        'recognition/video_sampling.py','recognition/message_selection.py','recognition/onnx_ocr.py',
        'battle_events/parser.py','tracking/evidence_fusion.py','tracking/state_engine.py','tracking/hidden_state.py',
        'tests/fixtures/battles/m233c_semantic_review.json','tests/fixtures/battles/m233c_secondary_review.json']
    atomic_json(target,dict(status='complete',scope='frozen independent C validation; no production changes',
        code={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in code},
        outputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}))
    print('Sealed C results')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',required=True,choices=['preserve','check','reference','select','ocr','contacts','seal','verify']);p.add_argument('--battle-id',choices=list(INTERVALS));a=p.parse_args()
    if a.stage in ['seal','verify']:seal(a.stage=='verify')
    elif a.stage in ['preserve','check']:preserve(a.stage=='check')
    elif not a.battle_id:p.error('--battle-id required')
    elif a.stage=='contacts':contacts(a.battle_id)
    else:prepare(a.battle_id,a.stage)
