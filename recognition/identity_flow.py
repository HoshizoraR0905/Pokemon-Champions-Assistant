"""Opt-in Champions HUD scheduling and entry windows, independent of message OCR."""
from dataclasses import asdict, replace
import hashlib
import cv2
from models import Recognition, Pokemon, Observation,EntityResolution
from recognition import box, color_fraction
from recognition.parsers import percentage,ratio
from recognition.identity import combine_identity
from recognition.sprite_shape import identify_shape, roster_ranking


def hud_cards(image):
    from recognition import classify
    screen,_,components=classify(image)
    if screen in {'team_configuration','team_preview','pokemon_selection','switch_selection','move_target_selection'} or 'ambiguous_target_panel' in components:return []
    cards=[]
    for side,offsets in [('own',[0,.168]),('opponent',[0,.166])]:
        for i,o in enumerate(offsets):
            name=(.139+o,.847,.226+o,.887) if side=='own' else (.624+o,.051,.722+o,.084)
            bar=(.177+o,.898,.232+o,.920) if side=='own' else (.650+o,.094,.713+o,.117)
            x,y,X,Y=box(image,bar);hsv=cv2.cvtColor(image[y:Y,x:X],cv2.COLOR_BGR2HSV)
            colored=((hsv[:,:,1]>100)&(hsv[:,:,2]>90)&((hsv[:,:,0]<85)|(hsv[:,:,0]>175))).mean()
            empty_bar=float((hsv[:,:,2]<70).mean())>.40
            if color_fraction(image,name,'purple' if side=='own' else 'pink')>.30 and (colored>.15 or empty_bar):
                cards.append((side,i,o,name))
    return cards


class EntryWindows:
    """Literal announcements open bounded follow-up work, never slot transitions."""
    def __init__(self,duration=8):self.duration=duration;self.windows=[]
    def observe(self,text,timestamp,source):
        if '派出了' in text or text.startswith('上吧'):
            self.windows.append(dict(start=timestamp,end=timestamp+self.duration,source=source,
                text=text,slot=None,status='pending_stable_hud'))
        return [w for w in self.windows if w['start']<=timestamp<=w['end']]
    def seen_hud(self,timestamp,cards):
        for w in self.windows:
            if w['start']<=timestamp<=w['end'] and cards:w['status']='hud_observed';w['hud_time']=timestamp
            elif timestamp>w['end'] and w['status']=='pending_stable_hud':w['status']='expired_unresolved'


def recognize_hud(recognizer,frame):
    image=frame.image;result=Recognition(frame.source,frame.index,frame.timestamp,
        'partial_battle_hud',.8,['battle_hud']);result.capture_metadata=frame.metadata.copy()
    recognizer.context.begin_frame(frame.source,frame.index)
    for side,i,o,name_roi in hud_cards(image):
        name=recognizer.ocr.read(image,box(image,name_roi),italic=True)
        if side=='own':
            # Same numeric layout/ratio semantics as the existing Recognizer.
            current=recognizer.ocr.read(image,box(image,(.177+o,.915,.213+o,.955)),numeric=True,italic=True)
            maximum=recognizer.ocr.read(image,box(image,(.220+o,.925,.243+o,.955)),numeric=True,italic=True)
            bounds=(current.region[0],current.region[1],maximum.region[2],maximum.region[3])
            hp=ratio(Observation(f'{current.value or ""}/{maximum.value or ""}',min(current.confidence,maximum.confidence),
                bounds,f'{current.raw_text}/{maximum.raw_text}'))
            icon_roi=(.080+o,.825,.137+o,.961)
        else:
            hp=percentage(recognizer.ocr.read(image,box(image,(.681+o,.113,.727+o,.154)),numeric=True))
            icon_roi=(.563+o,.030,.623+o,.157)
        bounds=box(image,icon_roi);icon=recognizer.icons.identify(image,bounds)
        mon=Pokemon(f'{side}_active_{i+1}',name,hp,icon=icon);result.pokemon.append(mon)
        result.regions[f'{side}_icon_{i}']=bounds
    recognizer.resolve_entities(result)
    # Opponent HUD strings are literal display labels, not species declarations.
    for mon in result.pokemon:
        if mon.slot.startswith('opponent'):
            text=mon.species;independent=asdict(text.resolution) if text.resolution else None
            mon.species=combine_identity(replace(text,value=None,resolution=None),mon.icon,recognizer.resolver.knowledge)
            if mon.species.resolution:mon.species.resolution.independent_text=independent
            else:mon.species.resolution=EntityResolution(method='literal_display_name_unidentified',independent_text=independent)
            mon.icon.conditioned=roster_ranking(mon.icon,recognizer.context.preview_observations)
    recognizer.context.remember(result)
    return result


def preview_rows(result,battle_id):
    rows=[]
    for mon in result.pokemon:
        if not mon.slot.startswith('opponent_team_'):continue
        icon=mon.icon;row=int(mon.slot.rsplit('_',1)[1])
        rows.append(dict(battle_id=battle_id,side='opponent',preview_row=row,
            member_occurrence=f'{battle_id}:opponent:preview:{row}',
            species_id=icon.species_id if icon and icon.status=='resolved' else None,
            status=icon.status if icon else 'unresolved',icon=asdict(icon) if icon else None,
            evidence={**result.capture_metadata,'source':result.source,'timestamp':result.timestamp},
            active_slot=None,nickname=None,persistent_instance_id=None))
    return rows
