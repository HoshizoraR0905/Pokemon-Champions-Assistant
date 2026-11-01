"""Prepare source-only review pages; never reads production event predictions."""
import json
from pathlib import Path
import sys
from difflib import SequenceMatcher
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.evaluate_b24 import OWNER,RUN,EVAL,verify,sha
from recognition.video_sampling import atomic_json
from recognition.log_comparison import compact


def main():
    verify()
    raw=json.loads((EVAL/'auto-reference/reference.json').read_text());out=EVAL/'reference-pages';out.mkdir(exist_ok=True)
    # One representative of each distinct ordered visible row layout. Retain
    # novel/clipped layouts as well; assembly exclusions are not silent drops.
    pages=[]
    for view in raw['views']:
        text='|'.join(compact(r['raw_text']) for r in view['observations'])
        if any(p['turn']==view.get('turn') and len(p['observations'])==len(view['observations'])
            and abs(p['geometry']['scroll_top']-view['geometry']['scroll_top'])<=2
            and SequenceMatcher(None,p['_text'],text).ratio()>=.96 for p in pages):continue
        pages.append(dict(view,_text=text))
    import cv2
    index=[]
    for i,p in enumerate(pages,1):
        source=ROOT/p['image'];image=cv2.imread(str(source));x,y,X,Y=p['geometry']['panel']
        crop=image[y:Y,x:X];canvas=cv2.copyMakeBorder(crop,36,0,0,0,cv2.BORDER_CONSTANT,value=(255,255,255))
        cv2.putText(canvas,f'Page {i} / turn {p.get("turn")} / inspection {p["timestamp"]:.3f}s',(8,24),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,0,0),1,cv2.LINE_AA)
        dest=out/f'page-{i:03d}.png';cv2.imwrite(str(dest),canvas)
        index.append(dict(page=i,image=str(dest.relative_to(ROOT)),source_image=p['image'],source_sha256=sha(source),
            source_id=p['source_id'],inspection_timestamp=p['timestamp'],turn=p.get('turn'),geometry=p['geometry'],
            observations=p['observations']))
    atomic_json(out/'index.json',dict(pages=index,raw_views=len(raw['views']),assembly_issues=raw['assembly_issues'],
        policy='Reference-only source pixels; no production predictions. Human/agent review still required before use as truth.'))
    print(json.dumps(dict(raw_views=len(raw['views']),distinct_pages=len(index),output=str(out)),ensure_ascii=False))
if __name__=='__main__':main()
