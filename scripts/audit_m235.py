"""Read-only recovery audit; no OCR backend or video decoder is instantiated."""
import hashlib
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.process_m235 import sha
from recognition.video_sampling import atomic_json,fingerprint
P=ROOT/'.cache/battles/sample_battle_5/m235'


def audit():
    import cv2
    import numpy as np
    from recognition.visual_evidence import variants,normalized_box
    from recognition.message_recovery import message_layout,context_variants
    from recognition.party_panel import layout
    seal=json.loads((P/'baseline-seal.json').read_text())
    assert all(sha(ROOT/k)==v for k,v in seal['outputs'].items()),'Baseline seal mismatch'
    review=json.loads((P/'review-seal.json').read_text())
    assert sha(ROOT/review['fixture'])==review['sha256']
    assert sha(P/'baseline-seal.json')==review['baseline_seal_sha256']
    labels=json.loads((ROOT/review['fixture']).read_text());groups={}
    for r in labels['examples']:groups.setdefault(r['occurrence_group'],set()).add(r['split'])
    assert all(len(v)==1 for v in groups.values())
    pre=json.loads((P/'prechange.json').read_text())
    assert all(sha(ROOT/k)==v for k,v in pre['preserve'].items())
    assert all(sha(P/'frozen-code'/k)==v for k,v in seal['code'].items())
    media=json.loads((P/'media.json').read_text());video=ROOT/media['identity']['path'];h=hashlib.sha256()
    with video.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024),b''):h.update(chunk)
    assert h.hexdigest()==media['full_sha256']
    model=ROOT/'.cache/m15-onnx-medium';manifest=json.loads((model/'local-manifest.json').read_text())
    assert all(sha(model/k)==v for k,v in manifest['files'].items())
    baseline=json.loads((P/'baseline-observations.json').read_text());final=json.loads((P/'final-observations.json').read_text())
    bm=json.loads((P/'baseline-recognition-manifest.json').read_text())
    identity=bm['identity']['ocr'];assert identity['backend']==sha(ROOT/'recognition/onnx_ocr.py') and identity['model']==sha(model/'local-manifest.json')
    assert sha(P/'baseline-observations.json')==bm['sha256']
    em=json.loads((P/'enhance-manifest.json').read_text());assert sha(P/'final-observations.json')==em['output_sha256']
    assert em['recipe']==fingerprint({k:sha(ROOT/k) for k in ['recognition/message_recovery.py','recognition/party_panel.py','recognition/hud_reuse.py']})
    acquisition=json.loads((P/'acquisition.json').read_text());survey=json.loads((P/'survey.json').read_text())
    frames={r['sha256']:r for r in acquisition['frames']+survey['frames']}
    for digest,r in frames.items():assert sha(ROOT/r['image'])==digest
    assert [r['sha256'] for r in baseline['observations']]==[r['sha256'] for r in final['observations']]
    assert all(r['sha256'] in frames for r in labels['examples'])
    reads={p.stem:json.loads(p.read_text()) for p in (P/'reads').glob('*.json')}
    assert len(reads)==450
    for key,r in reads.items():
        assert len(key)==64 and isinstance(r['text'],str) and type(r['confidence']) in (float,int) and math.isfinite(r['confidence']) and 0<=r['confidence']<=1
    reachable=set();references=0
    def crop_key(crop):return fingerprint(dict(shape=list(crop.shape),pixels=hashlib.sha256(crop.tobytes()).hexdigest(),**identity))
    def visit_crop(crop,expected=None):
        nonlocal references
        if not crop.size:return
        key=crop_key(crop)
        if key in reads:
            reachable.add(key)
            if expected is not None:
                assert reads[key]['text']==expected['text'] and abs(reads[key]['confidence']-expected['confidence'])<1e-10
                references+=1
    def visit_raw(value,image):
        if isinstance(value,dict):
            if value.get('engine','').startswith('PP-OCR') and value.get('region'):
                x,y,X,Y=value['region'];crop=image[y:Y,x:X];visit_crop(crop)
                gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY);active=(gray>190).sum(axis=1)>max(2,crop.shape[1]*.012)
                transitions=np.diff(np.r_[False,active,False].astype('int8'))
                pieces=[crop[max(0,a-2):min(crop.shape[0],b+2)] for a,b in zip(np.where(transitions==1)[0],np.where(transitions==-1)[0]) if b-a>=5]
                for c in pieces:visit_crop(c)
                for token in value.get('tokens',[]):
                    assert any(v['text']==token['text'] and v['confidence']==token['confidence'] for v in reads.values())
            for v in value.values():visit_raw(v,image)
        elif isinstance(value,list):
            for v in value:visit_raw(v,image)
    def readings(group,image):
        for rs in group.values():
            for r in rs:
                config=r['config_id'].rsplit(':',1)[-1].removeprefix('context_')
                visit_crop(dict(variants(image,r['box']))[config],r)
    for row in final['observations']:
        image=cv2.imread(str(ROOT/row['image']));visit_raw(row,image)
        if row.get('message'):
            visit_raw(dict(engine='PP-OCR',region=row['message']['box']),image)
        for bounds in row.get('snapshot',{}).get('regions',{}).values():
            visit_raw(dict(engine='PP-OCR',region=bounds),image)
        for group in [row['visual']['readings'],row.get('recovery',{}).get('readings',{}),row.get('party_panel',{}).get('readings',{})]:readings(group,image)
        # Some completed predictions predate the latest per-frame checkpoint.
        for i,bounds in enumerate(message_layout(image,row['visual_phase'])):
            for _,crop,_ in context_variants(image,bounds,normalized_box(image,(.22,.685,.64,.797))[2]):visit_crop(crop)
        selection=layout(image)
        if selection:
            for roi in selection['rois'].values():
                for _,crop in variants(image,normalized_box(image,roi)):visit_crop(crop)
    if len(reachable)!=len(reads):
        print('Unverified predictions',len(reads)-len(reachable),[(reads[k]['text'],round(reads[k]['confidence'],3)) for k in sorted(set(reads)-reachable)][:12])
    assert len(reachable)==len(reads),'Some saved predictions lack reconstructed pixel keys'
    replay=json.loads((P/'final-replay.json').read_text())
    replay_identity=replay.get('identity')
    if replay_identity:
        assert replay_identity['observations_sha256']==sha(P/'final-observations.json')
    # The interrupted session wrote a complete replay without dependency identity.
    # Retain it as evidence; use a separately sealed cache-only revision for scoring.
    result=dict(status='complete',ocr_predictions=0,video_sha256=h.hexdigest(),survey_frames=len(survey['frames']),acquired_frames=len(acquisition['frames']),baseline_frames=len(baseline['observations']),baseline_predictions=bm['total_cached_predictions'],baseline_events=len(json.loads((P/'baseline-replay.json').read_text())['engine']['history']),cached_predictions=len(reads),pixel_verified_predictions=len(reachable),reading_references=references,baseline_seal_sha256=sha(P/'baseline-seal.json'),review_seal_sha256=sha(P/'review-seal.json'),preserved_files=len(pre['preserve']),pre_interrupt_replay_events=len(replay['engine']['history']),budget_gaps=em['budget_gaps'],stages=dict(survey='complete',acquisition='complete',baseline='frozen',review='frozen',enhancement='complete_with_budget_gaps',replay='complete',color_matching='recovery_revision_pending',independent_scoring='pending',regressions='pending',report='pending'),outputs={str(p.relative_to(ROOT)):sha(p) for p in P.glob('*.json') if p.name not in {'recovery-audit.json','milestone-manifest.json'}})
    result['pre_interrupt_replay_compatibility']='identity_missing; preserved, superseded by sealed recovery revision' if not replay_identity else 'input_verified'
    atomic_json(P/'recovery-audit.json',result);print(json.dumps({k:v for k,v in result.items() if k!='outputs'},indent=2));return result

if __name__=='__main__':audit()
