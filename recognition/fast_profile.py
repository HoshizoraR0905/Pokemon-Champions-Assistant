"""Versioned, causal useful-region selection. These are observations, not Battle State.

The baseline UI contract remains immutable. This adapter deliberately avoids its
whole-screen overlay precedence: each ROI must establish its own visibility.
"""
from copy import deepcopy
from dataclasses import dataclass, asdict, replace
import hashlib
import math
import cv2
import numpy as np
from recognition import box, color_fraction
from recognition.message_selection import features, SelectionConfig, ROI
from recognition.ui_regions import message_rows, read_message
from recognition.phases import classify_phase
from recognition.visual_evidence import line_boxes, popup_regions

VERSION = 'fast-regions-v2'
MENUS = {'move_selection','pokemon_selection','switch_selection','move_target_selection'}


def normalized(image, bounds, *, text=False):
    x,y,X,Y = bounds
    crop = image[y:Y,x:X]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if text:
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        top = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, np.ones((9,13),np.uint8))
        gray = ((hsv[:,:,1]<110)&(gray>125)&(top>25)).astype('uint8')*255
    return cv2.resize(gray,(128,24),interpolation=cv2.INTER_AREA)


def difference(a,b):
    # Normalize by visible signal, so background area cannot hide a changed
    # character. Empty/identical crops have distance zero.
    return float(np.abs(a.astype(float)-b.astype(float)).sum())/max(1.,float(np.maximum(a,b).sum()))


@dataclass(frozen=True)
class FastConfig:
    version: str = VERSION
    stable_fps: float = 1.
    active_fps: float = 2.
    transition_hold_seconds: float = 1.5
    region_difference: float = .015
    diagnostic_menus: bool = False
    unknown_fallback_seconds: float = 3.


class AdaptiveInspection:
    def __init__(self, config=None):
        self.config=config or FastConfig(); self.next_time=0.; self.boost_until=-math.inf
    def due(self,t):return t+1e-7>=self.next_time
    def advance(self,t,*,phase,message_visible,changed):
        if changed:self.boost_until=t+self.config.transition_hold_seconds
        active=message_visible or phase=='unknown' or t<self.boost_until
        fps=self.config.active_fps if active else self.config.stable_fps
        # Global half-second cells; source PTS remains separate from target time.
        self.next_time=(math.floor(t*fps+1e-7)+1)/fps
        return fps


class RegionGate:
    """Compare against last recognized crop, never against future/whole frames.

    Visibility resets reuse. An unreliable unchanged crop gets at most one retry;
    a genuinely improved/changed crop can always be recognized again.
    """
    def __init__(self,threshold=.025):self.threshold=threshold;self.regions={}
    def choose(self,key,signature,visible,t,reliable=True):
        old=self.regions.get(key)
        if not visible:
            self.regions.pop(key,None)
            return False,'not_visible',None
        if old is None:return True,'newly_visible',None
        delta=difference(signature,old['signature'])
        if delta>=self.threshold:return True,'changed_region',old
        if not old['reliable'] and old['retries']<1:return True,'retry_unreliable',old
        return False,'unchanged_region',old
    def store(self,key,signature,t,value,source,reliable=True):
        old=self.regions.get(key)
        retries=(old['retries']+1 if old and difference(signature,old['signature'])<self.threshold else 0)
        self.regions[key]=dict(signature=signature.copy(),timestamp=t,value=deepcopy(value),source_id=source,
                               reliable=bool(reliable),retries=retries)


def independent_cards(image):
    """Existing name-panel + HP-bar contract without global menu/overlay veto."""
    cards=[]
    for side,offsets in [('own',[0,.168]),('opponent',[0,.166])]:
        for i,o in enumerate(offsets):
            name=(.139+o,.847,.226+o,.887) if side=='own' else (.624+o,.051,.722+o,.084)
            bar=(.177+o,.898,.232+o,.920) if side=='own' else (.650+o,.094,.713+o,.117)
            x,y,X,Y=box(image,bar);hsv=cv2.cvtColor(image[y:Y,x:X],cv2.COLOR_BGR2HSV)
            colored=((hsv[:,:,1]>100)&(hsv[:,:,2]>90)&((hsv[:,:,0]<85)|(hsv[:,:,0]>175))).mean()
            empty=float((hsv[:,:,2]<70).mean())>.4
            if color_fraction(image,name,'purple' if side=='own' else 'pink')>.30 and (colored>.15 or empty):
                cards.append((side,i,o,name))
    return cards


def inspect(image):
    phase,confidence,components,warnings=classify_phase(image)
    if image.shape[:2]!=(603,1311):
        return dict(phase='unknown',confidence=0,components=components,warnings=['Unvalidated UI scale'],regions=[],cards=[],message_visible=False)
    f=features(image,SelectionConfig());geometry=message_rows(image)
    # Historical log text is not a live message. Other panels cannot veto a
    # locally supported message: old status geometry also matches rain/animations.
    from recognition.battle_log import detect_log
    log=detect_log(image)
    x,y,X,Y=f['bounds'];gray=cv2.cvtColor(image[y:Y,x:X],cv2.COLOR_BGR2GRAY)
    flash=float((gray>240).mean())>.97 and gray.std()<8
    visible=bool(f['text_geometry'] and geometry['rows'] and not log and not flash)
    message=dict(region_id='message',region_type='battle_message',bounds=list(f['bounds']),
        visibility='visible' if visible else 'absent' if not geometry['fragments'] or flash or log else 'partial',
        fields=geometry,semantics='live_message_candidate',evidence=['Independent coherent message baselines'])
    cards=independent_cards(image)
    regions=[message]
    for side,i,o,name in cards:
        card=(.08+o,.825,.244+o,.961) if side=='own' else (.563+o,.030,.727+o,.157)
        regions.append(dict(region_id=f'{side}_active_{i+1}',region_type='active_hud',visibility='visible',
            bounds=list(box(image,card)),fields=dict(side=side,card_index=i,offset=o,name_roi=name),semantics='UI_card_not_departure'))
    for b in popup_regions(image):
        regions.append(dict(region_id='ability:'+('left' if b['side']=='self' else 'right'),region_type='ability_banner',visibility='visible',bounds=b['box'],
            fields=dict(lines=b['lines'],battle_side=None,instance_id=None),semantics='screen_edge_not_battle_side'))
    fb=box(image,(.204,.043,.424,.095))
    regions.append(dict(region_id='field',region_type='field_indicator',visibility='partial' if line_boxes(image,fb) else 'absent',bounds=list(fb),
        fields=dict(counter_meaning='unverified',trigger_time=None),semantics='presence_not_trigger'))
    return dict(profile=VERSION,phase=phase,confidence=confidence,components=components,warnings=warnings,
        overlay='battle_log_overlay' if log else None,regions=regions,cards=cards,message_visible=visible,
        message_mask=f['mask'],flash=bool(flash))


def recognize_cards(recognizer,frame,cards):
    """Use existing model, parsers, resolution and context for selected cards."""
    from models import Recognition, Pokemon, Observation, EntityResolution
    from recognition.parsers import percentage,ratio
    from recognition.identity import combine_identity
    from recognition.sprite_shape import roster_ranking
    result=Recognition(frame.source,frame.index,frame.timestamp,'partial_battle_hud',.8,['battle_hud'])
    result.capture_metadata=frame.metadata.copy();recognizer.context.begin_frame(frame.source,frame.index)
    image=frame.image
    for side,i,o,name_roi in cards:
        name=recognizer.ocr.read(image,box(image,name_roi),italic=True)
        if side=='own':
            a=recognizer.ocr.read(image,box(image,(.177+o,.915,.213+o,.955)),numeric=True,italic=True)
            b=recognizer.ocr.read(image,box(image,(.220+o,.925,.243+o,.955)),numeric=True,italic=True)
            hp=ratio(Observation(f'{a.value or ""}/{b.value or ""}',min(a.confidence,b.confidence),
                (a.region[0],a.region[1],b.region[2],b.region[3]),f'{a.raw_text}/{b.raw_text}'))
            roi=(.080+o,.825,.137+o,.961)
        else:
            hp=percentage(recognizer.ocr.read(image,box(image,(.681+o,.113,.727+o,.154)),numeric=True))
            roi=(.563+o,.030,.623+o,.157)
        bounds=box(image,roi);icon=recognizer.icons.identify(image,bounds)
        result.pokemon.append(Pokemon(f'{side}_active_{i+1}',name,hp,icon=icon));result.regions[f'{side}_icon_{i}']=bounds
    recognizer.resolve_entities(result)
    for mon in result.pokemon:
        if mon.slot.startswith('opponent'):
            text=mon.species;independent=asdict(text.resolution) if text.resolution else None
            mon.species=combine_identity(replace(text,value=None,resolution=None),mon.icon,recognizer.resolver.knowledge)
            if mon.species.resolution:mon.species.resolution.independent_text=independent
            else:mon.species.resolution=EntityResolution(method='literal_display_name_unidentified',independent_text=independent)
            mon.icon.conditioned=roster_ranking(mon.icon,recognizer.context.preview_observations)
    recognizer.context.remember(result)
    return result
