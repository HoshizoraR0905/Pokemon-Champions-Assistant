"""Read-only attribution of HUD name requests using frozen frames/OCR results.

This diagnostic replays name crop preprocessing against existing exact results;
missing crops fail instead of invoking a model. It does not replay recognition,
video decoding, HP, messages or state. Unique crop counts are inference upper
bounds: other baseline operations may have populated the same exact cache key.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition import box
from recognition.fast_video import CachedOCR, digest
from recognition.video_sampling import fingerprint, atomic_json
from recognition.command_checkpoint import SLOT_REGIONS


def measure(owner, run_id, target):
    import cv2
    folder=owner.cache('event-driven/'+run_id)
    data=json.loads((folder/'observations.json').read_text())
    counts=Counter(); keys={'ordinary':set(),'W_diagnostic':set()}; requests=[]
    backend=CachedOCR(folder,Counter()).backend
    identity=CachedOCR(folder,Counter()).identity
    category='ordinary'
    def predict(crops):
        result=[]
        for crop in crops:
            key=fingerprint(dict(shape=list(crop.shape),pixels=hashlib.sha256(crop.tobytes()).hexdigest(),**identity))
            path=folder/'reads'/f'{key}.json'
            if not path.exists():raise RuntimeError('Missing frozen OCR crop; no model fallback: '+key)
            keys[category].add(key);counts[category+'_prediction_requests']+=1
            result.append(json.loads(path.read_text()))
        return result
    backend.predict=predict
    started=time.monotonic()
    for row in data['observations']:
        full=[m for m in row.get('snapshot',{}).get('pokemon',[]) if '_active_' in m['slot'] and not m.get('identity_reused_from')]
        missing=[]
        if row.get('command_checkpoint',{}).get('inspection',{}).get('eligible'):
            snapshot={m['slot']:m for m in row.get('snapshot',{}).get('pokemon',[])}
            missing=[key for key in SLOT_REGIONS if not snapshot.get(key,{}).get('species') or snapshot[key].get('identity_reused_from')]
        if not full and not missing:continue
        image=cv2.imread(str(ROOT/row['image']))
        if image is None or digest(ROOT/row['image'])!=row['sha256']:raise ValueError('Frame integrity failure')
        reused={tuple(r['bounds']) for r in row.get('ocr_read_reuses',[])}
        for category,slots in [('ordinary',[m['slot'] for m in full]),('W_diagnostic',missing)]:
            for slot in slots:
                roi=SLOT_REGIONS[slot][2];bounds=box(image,roi)
                counts[category+'_name_read_requests']+=1
                if category=='ordinary' and tuple(bounds) in reused:
                    counts[category+'_region_reused_name_requests']+=1;continue
                before=counts[category+'_prediction_requests']
                backend.read(image,bounds,italic=True)
                requests.append(dict(source_id=row['source_id'],timestamp=row['timestamp'],slot=slot,
                                     category=category,prediction_requests=counts[category+'_prediction_requests']-before))
        counts['ordinary_icon_identify_requests']+=len(full)
    result=dict(counts=dict(counts),unique_name_crop_keys={k:len(v) for k,v in keys.items()},requests=requests,
                diagnostic_wall_seconds=time.monotonic()-started,actual_model_inferences=0,
                semantics='Exact name crop preprocessing requests, not total model inference savings. Unique name crop counts bound original identity inference work from above; cross-purpose exact-cache sharing is not attributed. Icon identify requests include region and exact-cache reuse; profile matching upper bound is twice these requests. W diagnostic remains independently optional.',
                observations_sha256=digest(folder/'observations.json'))
    baseline=json.loads((folder/'manifest.json').read_text())['counts']
    # In this baseline every prediction request inferred; no exact cache sharing
    # can make a name request cheaper than the observed inference count.
    if (not baseline.get('ocr_exact_cache_hits') and
            baseline['ocr_prediction_requests']==baseline['ocr_invocations_performed']):
        result['baseline_attributed_name_inferences']={
            k:counts[k+'_prediction_requests'] for k in keys}
    if not baseline.get('icon_region_reuses') and not baseline.get('icon_exact_cache_hits'):
        result['baseline_attributed_ordinary_icon_profile_inferences']=2*counts['ordinary_icon_identify_requests']
    result['identity_only_inference_seconds']='Not separately timed in untouched baseline'
    atomic_json(target/'identity-work.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='requests'},indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',required=True);p.add_argument('--run-id',required=True);p.add_argument('--evaluation-id',required=True)
    a=p.parse_args();owner=BattleArtifacts(a.battle);target=owner.cache('evaluation/'+a.evaluation_id);target.mkdir(parents=True,exist_ok=True)
    measure(owner,a.run_id,target)


if __name__=='__main__':main()
