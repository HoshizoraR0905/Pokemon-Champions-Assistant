"""Versioned, causal useful-region selection. These are observations, not Battle State.

The baseline UI contract remains immutable. This adapter deliberately avoids its
whole-screen overlay precedence: each ROI must establish its own visibility.
"""
from recognition.regions import hud_roi, FIELD_ROI
from copy import deepcopy
from dataclasses import asdict, replace
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
            name=hud_roi('own',o,'name') if side=='own' else hud_roi('opponent',o,'name')
            bar=hud_roi('own',o,'bar') if side=='own' else hud_roi('opponent',o,'bar')
            x,y,X,Y=box(image,bar);hsv=cv2.cvtColor(image[y:Y,x:X],cv2.COLOR_BGR2HSV)
            colored=((hsv[:,:,1]>100)&(hsv[:,:,2]>90)&((hsv[:,:,0]<85)|(hsv[:,:,0]>175))).mean()
            empty=float((hsv[:,:,2]<70).mean())>.4
            # At displayed zero the name panel loses its trainer color. Admit
            # its gray panel + white label + empty bar for reading, never as an
            # HP-zero assertion. Numeric OCR and normal instance binding follow.
            x,y,X,Y=box(image,name);panel=cv2.cvtColor(image[y:Y,x:X],cv2.COLOR_BGR2HSV)
            gray=((panel[:,:,1]<65)&(panel[:,:,2]>45)&(panel[:,:,2]<160)).mean()
            glyphs=((panel[:,:,1]<100)&(panel[:,:,2]>170)).mean()
            gray_candidate=empty and gray>.70 and .04<glyphs<.25
            if (color_fraction(image,name,'purple' if side=='own' else 'pink')>.30 or gray_candidate) and (colored>.15 or empty):
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
        card=hud_roi('own',o,'card') if side=='own' else hud_roi('opponent',o,'card')
        regions.append(dict(region_id=f'{side}_active_{i+1}',region_type='active_hud',visibility='visible',
            bounds=list(box(image,card)),fields=dict(side=side,card_index=i,offset=o,name_roi=name),semantics='UI_card_not_departure'))
    for b in popup_regions(image):
        regions.append(dict(region_id='ability:'+('left' if b['side']=='self' else 'right'),region_type='ability_banner',visibility='visible',bounds=b['box'],
            fields=dict(lines=b['lines'],battle_side=None,instance_id=None),semantics='screen_edge_not_battle_side'))
    fb=box(image,FIELD_ROI)
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
            a=recognizer.ocr.read(image,box(image,hud_roi('own',o,'current')),numeric=True,italic=True)
            b=recognizer.ocr.read(image,box(image,hud_roi('own',o,'maximum')),numeric=True,italic=True)
            hp=ratio(Observation(f'{a.value if a.value is not None else ""}/{b.value if b.value is not None else ""}',min(a.confidence,b.confidence),
                (a.region[0],a.region[1],b.region[2],b.region[3]),f'{a.raw_text}/{b.raw_text}'))
            roi=hud_roi('own',o,'icon')
        else:
            hp=percentage(recognizer.ocr.read(image,box(image,hud_roi('opponent',o,'percent')),numeric=True))
            roi=hud_roi('opponent',o,'icon')
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
