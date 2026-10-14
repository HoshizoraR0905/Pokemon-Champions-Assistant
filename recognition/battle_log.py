"""Battle Log adapter: geometric detection, line OCR, scroll sequence assembly.

No reference transcription is imported by this recognizer. Coordinates are
normalized to the observed UI layout; unsupported layouts remain undetected.
"""
import hashlib
from difflib import SequenceMatcher
import cv2
import numpy as np


def digest(value): return hashlib.sha256(value.encode()).hexdigest()[:24]
def compact(text): return ''.join(text.split())

def runs(mask):
    edges=np.diff(np.r_[False,mask,False].astype('int8'))
    return [(int(a),int(b)) for a,b in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1))]


def detect_log(image):
    h,w=image.shape[:2];sx=w/1311;sy=h/603
    # Distinct wide blue-purple panel; party/detail/target panels are smaller.
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    blue=((hsv[:,:,0]>=110)&(hsv[:,:,0]<=135)&(hsv[:,:,1]>100)&(hsv[:,:,2]>65)).astype('uint8')
    roi=blue[round(55*sy):round(510*sy),round(205*sx):round(1100*sx)]
    if roi.mean()<.85:return None
    x1,x2=round(220*sx),round(1050*sx)
    profile=np.median(image[round(50*sy):round(520*sy),x1:x2,0],axis=1)
    # Divider brightness changes with the scene behind the translucent panel.
    # Local prominence finds the thin lines without joining adjacent entries.
    window=max(3,round(11*sy)) | 1
    baseline=cv2.medianBlur(profile.astype('uint8')[:,None],window)[:,0]
    peaks=[round(50*sy)+(a+b)//2 for a,b in runs(profile-baseline>18)]
    if len(peaks)<3:return None
    gaps=np.diff(peaks)
    if np.median(gaps)<60*sy or np.median(gaps)>90*sy:return None
    # Bright narrow scroll thumb is distinct from its dim track.
    strip=image[round(57*sy):round(522*sy),round(1076*sx):round(1086*sx)]
    white=(strip.min(axis=2)>210).sum(axis=1)>=max(1,round(2*sx))
    thumbs=[(a,b) for a,b in runs(white) if b-a>20*sy]
    if not thumbs:return None
    a,b=max(thumbs,key=lambda r:r[1]-r[0])
    return {'panel':[round(200*sx),round(5*sy),round(1111*sx),round(534*sy)],
            'separators':peaks,'scroll_top':round(57*sy)+a,'scroll_height':b-a,
            'scale':[sx,sy],'score':float(roi.mean())}


def extract_view(image, backend, source_id, timestamp, sha256):
    geometry=detect_log(image)
    if not geometry:return {'source_id':source_id,'timestamp':timestamp,'detected':False,'observations':[]}
    sx,sy=geometry['scale'];bounds=[round(49*sy)]+geometry['separators']+[round(521*sy)]
    observations=[]
    for top,bottom in zip(bounds,bounds[1:]):
        # Skip clipped rows with insufficient height; never invent their text.
        if bottom-top<36*sy:continue
        x1,x2=round(508*sx),round(1035*sx)
        crop=image[top+round(3*sy):bottom-round(3*sy),x1:x2]
        # Only white message characters, not purple labels/icons/scrollbar.
        hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
        mask=(hsv[:,:,1]<85)&(hsv[:,:,2]>175)
        segments=[(a,b) for a,b in runs(mask.sum(axis=1)>3*sx) if b-a>=5*sy]
        lines=[]
        for a,b in segments:
            ya=top+round(3*sy)+max(0,a-round(2*sy));yb=top+round(3*sy)+min(crop.shape[0],b+round(2*sy))
            # Tighten to actual text width, while retaining 3px padding.
            active=np.flatnonzero(mask[a:b].sum(axis=0)>0)
            if not len(active):continue
            xa=x1+max(0,int(active[0])-round(3*sx));xb=x1+min(crop.shape[1],int(active[-1])+round(4*sx))
            obs=backend.read(image,(xa,ya,xb,yb))
            lines.append({'raw_text':obs.raw_text,'confidence':obs.confidence,'box':[xa,ya,xb,yb],
                          'tokens':obs.raw_ocr.tokens if obs.raw_ocr else []})
        if not lines:continue
        # Row label color is corroborating side evidence after preview calibration.
        label=image[top:bottom,round(330*sx):round(470*sx)]
        lh=cv2.cvtColor(label,cv2.COLOR_BGR2HSV)
        red=((lh[:,:,0]>165)|(lh[:,:,0]<10))&(lh[:,:,1]>110)&(lh[:,:,2]>110)
        purple=(lh[:,:,0]>=115)&(lh[:,:,0]<=145)&(lh[:,:,2]>150)&(lh[:,:,1]>80)
        color='red' if red.mean()>.15 else ('purple' if purple.mean()>.15 else None)
        raw='\n'.join(l['raw_text'] for l in lines)
        conf=sum(len(l['raw_text'])*l['confidence'] for l in lines)/max(1,sum(len(l['raw_text']) for l in lines))
        key=f'{sha256}:{top}:{bottom}'
        observations.append({'observation_id':'log-row:'+digest(key),'source_id':source_id,'timestamp':timestamp,
            'frame_sha256':sha256,'box':[x1,top,x2,bottom],'raw_text':raw,'ocr_confidence':conf,
            'lines':lines,'color':color,'partial':(top==bounds[0] or bottom==bounds[-1]) and bottom-top<65*sy})
    # Header OCR validates geometry and supplies observed turn; no fixed Turn 2.
    header=backend.read(image,(round(618*sx),round(12*sy),round(708*sx),round(42*sy)))
    import re
    m=re.search(r'回合\s*(\d+)',header.raw_text)
    return {'source_id':source_id,'timestamp':timestamp,'detected':bool(m and header.confidence>=.75),'geometry':geometry,
            'turn':int(m[1]) if m else None,'header_ocr':{'raw_text':header.raw_text,'confidence':header.confidence},
            'observations':observations,'detection_uncertainty':[] if m and header.confidence>=.75 else ['unverified_turn_heading']}


def assemble_views(views, *, ignore_partial_overlap=False):
    """Align ordered scroll overlaps; repeated text at distinct positions survives.

    Requires at least two consecutive matching rows for an overlap. Ambiguous
    overlaps are reported, never globally deduplicated by species or text.
    """
    groups={};issues=[]
    for v in views:
        if v.get('detected'):
            if any('COMMANDTIME' in compact(r['raw_text']) for r in v['observations']):
                issues.append({'source_id':v['source_id'],'reason':'countdown_overlay','rows':[r['observation_id'] for r in v['observations']]})
                continue
            groups.setdefault(v['turn'],[]).append(v)
    entries=[]
    for turn,group in sorted(groups.items(),key=lambda x:(x[0] is None,x[0] or 0)):
        assembled=[]
        for v in sorted(group,key=lambda v:(v['geometry']['scroll_top'],v['timestamp'],v['source_id'])):
            rows=v['observations']
            if not rows:continue
            if not assembled:assembled=[[r] for r in rows];continue
            candidates=[]
            for offset in range(-len(rows)+2,len(assembled)-1):
                comparisons=[]
                for j,r in enumerate(rows):
                    k=offset+j
                    complete=[a for a in assembled[k] if not ignore_partial_overlap or not a['partial']] if 0<=k<len(assembled) else []
                    if complete and (not ignore_partial_overlap or not r['partial']):
                        score=max(SequenceMatcher(None,compact(r['raw_text']),compact(a['raw_text'])).ratio() for a in complete)
                        comparisons.append(score)
                if len(comparisons)>=2 and all(s>=.78 for s in comparisons):
                    candidates.append((sum(comparisons),len(comparisons),offset))
            if not candidates:
                issues.append({'source_id':v['source_id'],'reason':'no_reliable_scroll_overlap','rows':[r['observation_id'] for r in rows]});continue
            candidates.sort(reverse=True)
            if len(candidates)>1 and candidates[0][:2]==candidates[1][:2]:
                issues.append({'source_id':v['source_id'],'reason':'ambiguous_scroll_overlap'});continue
            offset=candidates[0][2]
            if offset<0:assembled=[[] for _ in range(-offset)]+assembled;offset=0
            for j,r in enumerate(rows):
                k=offset+j
                if k>=len(assembled):assembled.append([])
                assembled[k].append(r)
        for order,observations in enumerate(assembled,1):
            # Deterministic selection from complete/high-confidence observations.
            best=max(observations,key=lambda r:(not r['partial'],r['ocr_confidence'],len(compact(r['raw_text'])),r['observation_id']))
            entries.append({'entry_id':'log-entry:'+digest(f'{best["source_id"].split("#")[0]}:{turn}:{order}'),
                 'turn':turn,'log_order':order,'source_id':best['source_id'],'raw_text':best['raw_text'],
                 'ocr_confidence':best['ocr_confidence'],'color':best['color'],
                 'observation_ids':[r['observation_id'] for r in observations],
                 'selected_observation_id':best['observation_id'],'text_variants':sorted({r['raw_text'] for r in observations})})
    return entries,issues
