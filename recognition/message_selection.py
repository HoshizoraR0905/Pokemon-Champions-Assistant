"""Lightweight, configurable message-ROI selection; not an OCR/text classifier."""
from dataclasses import dataclass, asdict
import hashlib
import cv2
import numpy as np
from recognition import box
from recognition.phases import _message_glyphs
from .video_sampling import fingerprint

from recognition.regions import MESSAGE_ROI as ROI


@dataclass(frozen=True)
class SelectionConfig:
    policy: str = 'hybrid'
    glyph_threshold: int = 8
    reduced_threshold: int = 3
    stroke_value: int = 120
    stroke_contrast: int = 25
    minimum_strokes: int = 2
    maximum_gap: int = 40
    minimum_span: int = 38
    left_anchor: int = 45
    temporal_mae: float = 8.0
    repeat_similarity: float = .9
    repeat_window_seconds: float = 2.0

    def __post_init__(self):
        if self.policy not in {'baseline','reduced','temporal','hybrid'}:raise ValueError('Unknown selection policy')
        if (self.minimum_strokes<1 or self.glyph_threshold<0 or self.reduced_threshold<0
                or not 0<self.repeat_similarity<=1 or not 0<=self.stroke_value<=255
                or not 0<=self.stroke_contrast<=255 or self.temporal_mae<0
                or self.maximum_gap<0 or self.minimum_span<=0 or self.left_anchor<0 or self.repeat_window_seconds<=0):
            raise ValueError('Invalid selection threshold')

    @property
    def fingerprint(self):return fingerprint(dict(version=1,roi=ROI,configuration=asdict(self)))


def features(image,config):
    bounds=box(image,ROI);x1,y1,x2,y2=bounds;crop=image[y1:y2,x1:x2]
    gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY);hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
    top=cv2.morphologyEx(gray,cv2.MORPH_TOPHAT,cv2.getStructuringElement(cv2.MORPH_RECT,(13,9)))
    mask=((hsv[:,:,1]<100)&(gray>config.stroke_value)&(top>config.stroke_contrast)).astype('uint8')*255
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    strokes=[]
    for c in contours:
        x,y,w,h=cv2.boundingRect(c)
        if 4<=h<=crop.shape[0]*.45 and 1<=w<=30 and cv2.contourArea(c)>=3:
            # Message baselines have two known row bands. Arena clutter outside them is not text evidence.
            if .01<=y/crop.shape[0]<=.32 or .50<=y/crop.shape[0]<=.84:strokes.append((x,y,w,h))
    # Require coherent character-height baselines starting near the message's
    # left edge; isolated bright arena contours and right-side menu labels fail.
    characters=[p for p in strokes if p[3]>=9 and p[2]>=2]
    groups=[]
    for _,y,_,h in characters:
        aligned=sorted([p for p in characters if abs(p[1]+p[3]-y-h)<=3])
        chain=[]
        for p in aligned:
            if chain and p[0]-(chain[-1][0]+chain[-1][2])>config.maximum_gap:
                if chain[0][0]<config.left_anchor:groups.append(chain)
                chain=[]
            chain.append(p)
        if chain and chain[0][0]<config.left_anchor:groups.append(chain)
    coherent=[g for g in groups if len(g)>=config.minimum_strokes
              and max(p[0]+p[2] for p in g)-g[0][0]>=config.minimum_span]
    text_mask=np.zeros_like(mask)
    for group in groups:
        for x,y,w,h in group:text_mask[y:y+h,x:x+w]=mask[y:y+h,x:x+w]
    return dict(glyphs=_message_glyphs(image),strokes=len(strokes),text_geometry=bool(coherent),bounds=bounds,
                gray=gray,mask=text_mask,roi_sha256=hashlib.sha256(crop.tobytes()).hexdigest())



class MessageSelector:
    def __init__(self,config=None):
        self.config=config or SelectionConfig();self.previous=None;self.last_selected=None;self.last_selected_time=None

    def select(self,image,phase,*,timestamp=0,log_visible=False):
        config=self.config;f=features(image,config)
        allowed=phase in {'battle_message','battle_animation','unknown','battle_screen'} and not log_visible
        legacy=phase in {'battle_message','battle_animation','unknown'} and timestamp>30 and not log_visible
        delta=float(np.mean(cv2.absdiff(f['gray'],self.previous['gray']))) if self.previous is not None else None
        similarity=0.
        if self.last_selected is not None and self.last_selected_time is not None and 0<=timestamp-self.last_selected_time<=config.repeat_window_seconds:
            a=f['mask']>0;b=self.last_selected['mask']>0
            union=np.count_nonzero(a|b)
            similarity=float(np.count_nonzero(a&b)/union) if union else 1.
        if config.policy=='baseline':selected=legacy and f['glyphs']>=config.glyph_threshold
        elif config.policy=='reduced':selected=legacy and f['glyphs']>=config.reduced_threshold
        elif config.policy=='temporal':selected=allowed and (delta is None or delta>=config.temporal_mae)
        else:
            selected=allowed and f['text_geometry'] and similarity<config.repeat_similarity
        reason='selected' if selected else 'phase_or_log_excluded' if not allowed else 'unchanged_text_mask' if similarity>=config.repeat_similarity else 'insufficient_message_evidence'
        self.previous=f
        if selected:
            self.last_selected=f;self.last_selected_time=timestamp
        elif not allowed or not f['text_geometry']:
            self.last_selected=None;self.last_selected_time=None
        # No glyph threshold is used as a fallback veto in the hybrid.
        return dict(selected=bool(selected),reason=reason,glyphs=f['glyphs'],strokes=f['strokes'],
                    text_geometry=f['text_geometry'],temporal_mae=delta,repeat_similarity=similarity,roi_sha256=f['roi_sha256'],bounds=f['bounds'])
