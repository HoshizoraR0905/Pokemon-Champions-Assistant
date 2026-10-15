"""Opt-in palette-invariant sprite silhouettes, using pinned RGBA assets.

This compares UI silhouettes, never rendered scene models. Scores are geometric
overlap, not probabilities. A chromatic panel must be observable around a sprite.
"""
from dataclasses import replace
import cv2
import numpy as np
from models import IconCandidate, IconEvidence


def silhouette(image):
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    border=np.concatenate([hsv[:2].reshape(-1,3),hsv[-2:].reshape(-1,3),
                           hsv[:,:2].reshape(-1,3),hsv[:,-2:].reshape(-1,3)])
    chromatic=border[border[:,1]>100]
    if len(chromatic)<len(border)*.4:return None
    hist=np.bincount(chromatic[:,0],minlength=180);hue=int(hist.argmax())
    delta=np.abs(hsv[:,:,0].astype(int)-hue);delta=np.minimum(delta,180-delta)
    mask=((delta>14)|(hsv[:,:,1]<65)|(hsv[:,:,2]<45)).astype('uint8')
    panel=((delta<10)&(hsv[:,:,1]>100)&(hsv[:,:,2]>65)).astype('uint8')
    contours,_=cv2.findContours(panel,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        # Sloping HUD cards expose arena outside the panel. Restrict segmentation
        # to the observed colored panel's hull; no scene object is a candidate.
        interior=np.zeros_like(panel)
        cv2.fillConvexPoly(interior,cv2.convexHull(max(contours,key=cv2.contourArea)),1)
        interior=cv2.erode(interior,np.ones((3,3),np.uint8))
        mask &= interior
    count,labels,stats,_=cv2.connectedComponentsWithStats(mask)
    if count<2:return None
    largest=1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]))
    mask=(labels==largest).astype('uint8')
    x,y,w,h=cv2.boundingRect(mask)
    if w<8 or h<12 or mask.sum()<60 or mask.sum()>image.shape[0]*image.shape[1]*.8:return None
    # A clipped contour cannot safely identify a differently colored sprite.
    if x==0 or y==0 or x+w==mask.shape[1] or y+h==mask.shape[0]:return None
    return mask[y:y+h,x:x+w]


def shape_score(query,template):
    q=cv2.resize(query,(48,64),interpolation=cv2.INTER_NEAREST)>0
    t=cv2.resize(template,(48,64),interpolation=cv2.INTER_NEAREST)>0
    overlap=float((q&t).sum())/max(1,int((q|t).sum()))
    aspect=min(query.shape[1]/query.shape[0],template.shape[1]/template.shape[0])/max(query.shape[1]/query.shape[0],template.shape[1]/template.shape[0])
    return float(np.sqrt(overlap*aspect))


def identify_shape(recognizer,image,region,*,minimum=.86,margin=.10):
    x,y,X,Y=region;mask=silhouette(image[y:Y,x:X])
    result=IconEvidence(region=region,source_commit=recognizer.source['commit'],
        method='registered_silhouette_v1',score_semantics='sqrt(silhouette IoU times aspect similarity); not probability')
    if mask is None:result.reason='panel_or_complete_contour_unavailable';return result
    candidates=[]
    for ref,rgba in recognizer.templates:
        shape=(rgba[:,:,3]>80).astype('uint8');score=shape_score(mask,shape)
        identity=recognizer.identities.for_form(ref.get('source_form_id',ref.get('form_id')))
        candidates.append(IconCandidate(ref['canonical_id'],ref['species_id'],identity['form_id'],ref['file'],
            round(score,5),1.,(0,0),identity['pokemon_id'],identity['canonical_identity']))
    candidates.sort(key=lambda c:c.similarity,reverse=True);result.candidates=candidates[:8]
    top=candidates[0];near=[c for c in candidates if top.similarity-c.similarity<margin]
    if top.similarity<minimum:result.reason='below_shape_threshold'
    elif len({c.species_id for c in near})!=1:result.status='ambiguous';result.reason='small_shape_margin'
    elif not top.canonical_id:result.reason='unmapped_visual_identity'
    else:
        result.status='resolved';result.species_id=top.species_id;result.canonical_id=f'pokeapi:species:{top.species_id}'
        # Silhouette cannot distinguish a palette or an otherwise identical form.
        result.identity_status='species_only';result.reason='independent_complete_silhouette'
    return result


def roster_ranking(icon,roster):
    """Dependent ranking only. It never changes the independent admission."""
    supported={r['species_id'] for r in roster if r.get('status')=='resolved'}
    return dict(method='preview_conditioned_ranking',independent_observation=False,
        roster_evidence=[r.get('evidence') for r in roster if r.get('status')=='resolved'],
        candidates=[c.__dict__.copy() for c in icon.candidates if c.species_id in supported],
        admission='ranking_only')
