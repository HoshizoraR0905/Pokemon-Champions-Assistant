"""Scoped geometry-first visual evidence; no labels, timestamp rules or moveset priors."""
from collections import defaultdict
import re
import cv2
import numpy as np
from knowledge import KnowledgeBase,normalize
from functools import lru_cache
from .move_resolution import resolve_move

@lru_cache(maxsize=1)
def knowledge():return KnowledgeBase()


def line_boxes(image,region):
    """Join vertically fractured glyphs, then find coherent left-anchored lines."""
    x,y,X,Y=region;roi=image[y:Y,x:X]
    if not roi.size:return []
    gray=cv2.cvtColor(roi,cv2.COLOR_BGR2GRAY);hsv=cv2.cvtColor(roi,cv2.COLOR_BGR2HSV)
    mask=((gray>165)&(hsv[:,:,1]<115)).astype('uint8')*255
    count,_,stats,_=cv2.connectedComponentsWithStats(mask)
    clean=np.zeros_like(mask)
    for a,b,w,h,area in stats[1:]:
        if 2<=h<=max(32,roi.shape[0]*.55) and 1<=w<=45 and area>=3:
            clean[b:b+h,a:a+w]=mask[b:b+h,a:a+w]
    closed=cv2.morphologyEx(clean,cv2.MORPH_CLOSE,np.ones((5,1),np.uint8))
    active=(closed>0).sum(axis=1)>=3
    spans=[];begin=None
    for i,v in enumerate(np.r_[active,False]):
        if v and begin is None:begin=i
        if not v and begin is not None:
            if i-begin>=7:spans.append((begin,i))
            begin=None
    boxes=[]
    for a,b in spans:
        columns=(closed[a:b]>0).sum(axis=0)>0;positions=np.where(columns)[0]
        if len(positions)<6:continue
        # Keep the first text chain; a distant menu/background is not a suffix.
        starts=np.r_[0,np.where(np.diff(positions)>max(20,(b-a)*2))[0]+1]
        ends=np.r_[starts[1:],len(positions)]
        chains=[positions[s:e] for s,e in zip(starts,ends) if e-s>=6]
        if not chains:continue
        p=chains[0]
        boxes.append([x+max(0,int(p[0])-3),y+max(0,a-3),x+min(roi.shape[1],int(p[-1])+4),y+min(roi.shape[0],b+3)])
    return boxes


def variants(image,bounds):
    x,y,X,Y=bounds;crop=image[y:Y,x:X]
    if not crop.size:return []
    return [('native',crop),('double',cv2.resize(crop,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC))]


def exact(text,kind):
    rows=knowledge().exact[kind].get(normalize(text),[]);rows={r.canonical_id:r for r in rows}
    if len(rows)!=1:return None
    r=next(iter(rows.values()))
    return dict(canonical_id=r.canonical_id,species_id=r.species_id,form_id=r.form_id,name=r.names.get('zh-hans'),knowledge_snapshot=knowledge().snapshot_id)


def consensus(readings,kind,*,suffix=''):
    accepted=[]
    for r in readings:
        text=r['text'].strip().rstrip('！!。')
        if suffix and text.endswith(suffix):text=text[:-len(suffix)]
        ref=exact(text,kind)
        if ref and r['confidence']>=.9:accepted.append((ref,r['config_id']))
    ids={r['canonical_id'] for r,_ in accepted}
    return accepted[0][0] if len(ids)==1 and len({c for _,c in accepted})>=2 else None


def normalized_box(image,roi):
    h,w=image.shape[:2];return [round(roi[0]*w),round(roi[1]*h),round(roi[2]*w),round(roi[3]*h)]


def popup_regions(image):
    """Candidates only: exact two-line content and phase gate confirm semantics."""
    out=[]
    # A blue rain-lit battlefield can satisfy the broad detail color heuristic.
    # Only the local two-line banner structure and literal possessive text own
    # this region; a global color estimate cannot veto its acquisition.
    # Right text ends before the holder sprite. Including that sprite joins
    # the two baselines and suppresses otherwise perfectly readable banners.
    for side,roi,text_roi in [('self',(.08,.31,.36,.46),(.135,.345,.32,.423)),('opponent',(.64,.31,.94,.46),(.70,.345,.866,.423))]:
        bounds=normalized_box(image,roi);x,y,X,Y=bounds;crop=image[y:Y,x:X]
        hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
        dark_blue=((hsv[:,:,0]>95)&(hsv[:,:,0]<135)&(hsv[:,:,2]<115)).mean()
        boxes=line_boxes(image,normalized_box(image,text_roi))
        if dark_blue>.12 and len(boxes)==2:out.append(dict(side=side,box=bounds,lines=boxes,layout='battle-ability-banner-v1'))
    return out


def detail_layout(image):
    bounds=normalized_box(image,(.15,.16,.86,.85));x,y,X,Y=bounds
    hsv=cv2.cvtColor(image[y:Y,x:X],cv2.COLOR_BGR2HSV)
    return float(((hsv[:,:,0]>=105)&(hsv[:,:,0]<=150)&(hsv[:,:,1]>70)).mean())>.48


from recognition.regions import DETAIL_ROIS


def stage_arrows(image):
    if not detail_layout(image):return {}
    values={}
    for stat,center in zip(['attack','defense','special_attack','special_defense','speed','accuracy','evasion'],[.513,.558,.600,.645,.688,.754,.801]):
        x,y,X,Y=normalized_box(image,(.245,center-.018,.39,center+.018));hsv=cv2.cvtColor(image[y:Y,x:X],cv2.COLOR_BGR2HSV)
        counts={}
        for direction,lo,hi in [('up',35,90),('down',8,34)]:
            mask=((hsv[:,:,0]>=lo)&(hsv[:,:,0]<=hi)&(hsv[:,:,1]>120)&(hsv[:,:,2]>130)).astype('uint8')*255
            contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            triangles=[]
            for c in contours:
                _,_,w,h=cv2.boundingRect(c);poly=cv2.approxPolyDP(c,.08*cv2.arcLength(c,True),True)
                if 7<=w<=28 and 7<=h<=25 and cv2.contourArea(c)>=25 and len(poly)==3:triangles.append(c)
            counts[direction]=len(triangles)
        n=counts['up']-counts['down']
        if 0<abs(n)<=6 and not all(counts.values()):values[stat]=dict(value=n,basis='direct colored triangle count on validated detail layout',box=[x,y,X,Y])
    return values


def parse_popup(readings):
    # Two source-specific line groups; never deduce an ability from weather.
    species=consensus([r for r in readings.get('species',[]) if r['text'].strip().rstrip('！!。').endswith('的')],
        'species',suffix='的')
    label=readings.get('ability',[])  # Legacy key names the second banner row, not its semantics.
    ability=consensus(label,'ability')
    item=consensus(label,'item')
    supported=bool(species and bool(ability)!=bool(item))
    return dict(species=species,ability=ability,item=item,status='supported' if supported else 'unresolved',readings=readings)


def parse_detail(readings,arrows):
    result=dict(species=consensus(readings.get('species',[]),'species'),ability=consensus(readings.get('ability',[]),'ability'),
                item=consensus(readings.get('item',[]),'item'),hp=None,stages=arrows,field={},readings=readings)
    values=[]
    for r in readings.get('hp',[]):
        m=re.fullmatch(r'\s*(\d{1,4})\s*/\s*(\d{1,4})\s*',r['text'])
        if m and r['confidence']>=.9 and 0<=int(m[1])<=int(m[2]):values.append((int(m[1]),int(m[2])))
    if len(values)>=2 and len(set(values))==1:result['hp']=dict(current=values[0][0],maximum=values[0][1])
    for text,name in [('下雨状态','rain'),('极光幕状态','aurora_veil'),('青草场地状态','grassy')]:
        if len({r['config_id'] for key,rows in readings.items() if key.startswith('field') for r in rows if r['text'].strip().rstrip('！!。')==text and r['confidence']>=.9})>=2:result['field'][name]=dict(active=True,basis='direct labeled detail UI indicator')
    result['status']='supported' if result['species'] else 'unresolved'
    return result
