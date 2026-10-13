"""Fixed-layout recognizer for the supplied landscape doubles interface."""
from pathlib import Path
from dataclasses import replace
import re
import cv2
import numpy as np
from capture import Frame
from models import Observation, Pokemon, Move, Recognition
from recognition.ocr import OCR
from recognition.paddle_ocr import create_ocr
from recognition.icons import IconRecognizer, default_icons
from recognition.identity import combine_identity
from recognition.parsers import ratio, percentage
from recognition.entities import EntityResolver
from recognition.context import RecognitionContext


def box(image: np.ndarray, region: tuple[float,float,float,float]) -> tuple[int,int,int,int]:
    h, w = image.shape[:2]
    x1, y1, x2, y2 = region
    return (round(x1*w), round(y1*h), round(x2*w), round(y2*h))


def color_fraction(image: np.ndarray, region: tuple[float,float,float,float], color: str) -> float:
    x1, y1, x2, y2 = box(image, region)
    hsv = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    hue, sat, val = cv2.split(hsv)
    mask = (sat > 90) & (val > 65)
    if color == 'purple':
        mask &= (hue > 110) & (hue < 145)
    elif color == 'green':
        mask &= (hue > 20) & (hue < 45)
    else:
        mask &= (hue > 145) & (hue < 179)
    return float(np.mean(mask))


def classify(image: np.ndarray) -> tuple[str,float,list[str]]:
    # Ratios describe panel positions, never species or expected OCR outputs.
    h, w = image.shape[:2]
    if not 1.9 < w/h < 2.35:
        return 'unknown', 0.0, []
    cards = [color_fraction(image, (.23+x,.29+y,.31+x,.39+y), 'purple')
             for y in [0,.202,.404] for x in [0,.341]]
    background = image[round(h*.85):round(h*.9), round(w*.05):round(w*.1)]
    if min(cards) > .4 and float(np.mean(background)) > 150:
        return 'team_configuration', .8, ['team_configuration']
    preview = [color_fraction(image, (.14,.13+i*.117,.29,.20+i*.117), 'purple') for i in range(6)]
    opponents = [color_fraction(image, (.76,.13+i*.117,.88,.20+i*.117), 'pink') for i in range(6)]
    selected = [color_fraction(image, (.14,.13+i*.117,.29,.20+i*.117), 'green') for i in range(6)]
    confirmation = color_fraction(image, (.16,.83,.31,.87), 'purple')
    if all(p > .45 or g > .45 for p,g in zip(preview,selected)) and min(opponents) > .3 and confirmation > .4:
        return 'team_preview', .9, ['team_preview']
    own = color_fraction(image, (.15,.85,.24,.89), 'purple')
    enemy = color_fraction(image, (.64,.05,.72,.09), 'pink')
    if own > .3 and enemy > .3:
        moves = [color_fraction(image, (.70,.44+i*.118,.735,.49+i*.118), 'purple') for i in range(4)]
        if min(moves) > .35:
            return 'move_selection', .85, ['battle_screen', 'move_selection']
        return 'battle_screen', .8, ['battle_screen']
    return 'unknown', 0.0, []


class Recognizer:
    def __init__(self, ocr: OCR | None = None, *, knowledge: bool = True,
                 resolver: EntityResolver | None = None, context: RecognitionContext | None = None,
                 icons: IconRecognizer | bool | None = None):
        self.ocr = ocr if ocr is not None else create_ocr('auto')
        self.resolver = (resolver or EntityResolver()) if knowledge else None
        self.context = context or RecognitionContext(self.resolver.knowledge if self.resolver else None)
        self.icons = (default_icons() if icons is True or (icons is None and ocr is None)
                      else None if icons is False or icons is None else icons)

    def recognize(self, frame: Frame) -> Recognition:
        self.context.begin_frame(frame.source,frame.index)
        image = frame.image
        screen, confidence, components = classify(image)
        result = Recognition(frame.source, frame.index, frame.timestamp,
                             screen, confidence, components)
        result.capture_metadata = frame.metadata.copy()

        def read(label: str, region: tuple[float,float,float,float], numeric: bool = False,
                 multiline: bool = False, italic: bool = False) -> Observation:
            bounds = box(image, region)
            result.regions[label] = bounds
            return self.ocr.read(image, bounds, numeric, multiline, italic=italic)

        def read_ratio(label: str, current_roi: tuple[float,float,float,float],
                       maximum_roi: tuple[float,float,float,float]) -> Observation:
            current = read(label+'_current',current_roi,True,italic=True)
            maximum = read(label+'_maximum',maximum_roi,True,italic=True)
            text_a, text_b = str(current.value or ''), str(maximum.value or '')
            bounds = (min(current.region[0],maximum.region[0]),min(current.region[1],maximum.region[1]),
                      max(current.region[2],maximum.region[2]),max(current.region[3],maximum.region[3]))
            combined = Observation(f'{text_a}/{text_b}',min(current.confidence,maximum.confidence),
                                   bounds,f'{current.raw_text}/{maximum.raw_text}')
            return ratio(combined)

        def gender(label: str, region: tuple[float,float,float,float]) -> Observation:
            bounds = box(image,region)
            result.regions[label] = bounds
            x1,y1,x2,y2 = bounds
            hsv = cv2.cvtColor(image[y1:y2,x1:x2],cv2.COLOR_BGR2HSV)
            saturated = (hsv[:,:,1] > 170) & (hsv[:,:,2] > 150)
            red = float(np.mean(saturated & ((hsv[:,:,0] < 10) | (hsv[:,:,0] > 170))))
            blue = float(np.mean(saturated & (hsv[:,:,0] > 95) & (hsv[:,:,0] < 125)))
            value = 'female' if red > .12 and blue < .05 else 'male' if blue > .12 and red < .05 else None
            return Observation(value,.8 if value else 0.0,bounds,provenance='visible_gender_icon')

        if screen == 'team_configuration':
            # Green selected tab distinguishes the summary's two visible pages.
            x1,y1,x2,y2 = box(image, (.52,.185,.62,.21))
            tab = cv2.cvtColor(image[y1:y2,x1:x2], cv2.COLOR_BGR2HSV)
            stats_page = float(np.mean((tab[:,:,0] > 20) & (tab[:,:,0] < 45)
                                      & (tab[:,:,1] > 160))) > .5
            result.components.append('configuration_stats' if stats_page else 'configuration_moves')
            fields = ['form','level','gender','ability','held_item','nature','evs','ivs',
                      'hp','attack','defense','special_attack','special_defense','speed']
            for row in range(3):
                for col in range(2):
                    x, y = col*.341, row*.202
                    p = Pokemon(f'own_team_{row*2+col+1}',
                        read(f'config_name_{row}_{col}',(.204+x,.252+y,.3+x,.289+y)))
                    result.regions[f'config_icon_{row}_{col}'] = box(image,(.167+x,.21+y,.207+x,.29+y))
                    p.configuration = {f:Observation() for f in fields}
                    p.configuration['gender'] = gender(f'config_gender_{row}_{col}',
                                                        (.304+x,.253+y,.32+x,.284+y))
                    if stats_page:
                        for j, stat in enumerate(['hp','attack','defense','special_attack','special_defense','speed']):
                            sx, sy = x+(0 if j < 3 else .15), y+(j%3)*.042
                            obs = read(f'config_{row}_{col}_{stat}',(.261+sx,.298+sy,.286+sx,.328+sy), True)
                            text = str(obs.value or '').strip()
                            p.configuration[stat] = replace(obs,value=int(text) if re.fullmatch(r'\d{1,3}',text) else None)
                            allocation = read(f'allocation_{row}_{col}_{stat}',
                                              (.306+sx,.298+sy,.318+sx,.328+sy),True)
                            text = str(allocation.value or '').strip()
                            p.configuration[f'allocation_{stat}_display'] = replace(allocation,
                                value=int(text) if re.fullmatch(r'\d{1,2}',text) else None)
                        # Allocation units and nature arrows are not validated as EVs/nature.
                    else:
                        p.configuration['ability'] = read(f'ability_{row}_{col}',(.208+x,.3+y,.348+x,.329+y))
                        p.configuration['held_item'] = read(f'item_{row}_{col}',(.208+x,.343+y,.348+x,.373+y))
                        for j in range(4):
                            p.configuration[f'move_{j+1}'] = read(f'config_move_{row}_{col}_{j}',
                                (.382+x,.257+y+j*.042,.464+x,.29+y+j*.042))
                    result.pokemon.append(p)

        if screen == 'team_preview':
            for i in range(6):
                y = .13 + i*.117
                p = Pokemon(f'own_team_{i+1}', read(f'team_name_{i}', (.151,y,.263,y+.034)))
                result.regions[f'own_icon_{i}'] = box(image,(.301,y-.01,.349,y+.095))
                p.configuration['held_item'] = read(f'team_item_{i}', (.17,y+.047,.293,y+.079))
                p.configuration['gender'] = gender(f'team_gender_{i}',(.275,y+.003,.29,y+.035))
                result.pokemon.append(p)
                bounds = box(image, (.778,y-.01,.832,y+.095))
                result.regions[f'opponent_icon_{i}'] = bounds
                result.pokemon.append(Pokemon(f'opponent_team_{i+1}',
                    Observation(region=bounds, provenance='unresolved_icon')))
        if 'battle_screen' in components:
            for side, offsets in [('own', [0,.168]), ('opponent',[0,.166])]:
                for i, offset in enumerate(offsets):
                    if side == 'own':
                        name_roi = (.139+offset,.847,.226+offset,.887)
                        hp_roi = (.176+offset,.915,.243+offset,.955)
                    else:
                        name_roi = (.624+offset,.051,.722+offset,.084)
                        hp_roi = (.681+offset,.113,.727+offset,.154)
                    name = read(f'{side}_name_{i}', name_roi,italic=True)
                    if side == 'own':
                        icon_roi=(.084+offset,.854,.135+offset,.959)
                    else:
                        icon_roi=(.567+offset,.061,.621+offset,.154)
                    result.regions[f'{side}_icon_{i}'] = box(image,icon_roi)
                    if side == 'own':
                        hp = read_ratio(f'{side}_hp_{i}',(.177+offset,.915,.213+offset,.955),
                                        (.220+offset,.925,.243+offset,.955))
                    else:
                        hp = percentage(read(f'{side}_hp_{i}',hp_roi,True))
                    result.pokemon.append(Pokemon(f'{side}_active_{i+1}', name, hp))
            condition = read('condition_banner', (.21,.052,.43,.09))
            if condition.value:
                result.conditions['banner_text'] = condition
        if screen == 'move_selection':
            for i in range(4):
                y = .444+i*.118
                name = read(f'move_name_{i}', (.75,y,.859,y+.048))
                pp = read_ratio(f'move_pp_{i}',(.875,y-.006,.903,y+.031),
                                (.897,y+.032,.910,y+.06))
                result.moves.append(Move(i+1, name, pp))
        if screen == 'unknown':
            # The battle message uses white text over a translucent lower-left band.
            bounds = box(image, (.22,.685,.64,.797))
            x1,y1,x2,y2 = bounds
            crop = image[y1:y2,x1:x2]
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            white = ((hsv[:,:,1] < 70) & (hsv[:,:,2] > 200)).astype('uint8')*255
            contours,_ = cv2.findContours(white,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            glyphs = sum(1 for c in contours if 8 < cv2.boundingRect(c)[3] < crop.shape[0]*.55
                         and cv2.contourArea(c) > 10)
            if glyphs >= 8:
                message = read('battle_message',(.22,.685,.64,.797),multiline=True)
                if message.value and message.confidence >= .8 and len(re.findall(r'[\u4e00-\u9fff]',message.value)) >= 5:
                    result.message = message
                    result.screen, result.confidence = 'battle_message', message.confidence
                    result.components = ['battle_message']
        if self.icons and self.resolver:
            for p in result.pokemon:
                if p.slot.startswith('own_team_') and screen=='team_preview':
                    label=f'own_icon_{int(p.slot.split("_")[-1])-1}'
                elif p.slot.startswith('opponent_team_') and screen=='team_preview':
                    label=f'opponent_icon_{int(p.slot.split("_")[-1])-1}'
                elif p.slot.startswith('own_team_') and screen=='team_configuration':
                    n=int(p.slot.split('_')[-1])-1;label=f'config_icon_{n//2}_{n%2}'
                elif '_active_' in p.slot:
                    side,n=p.slot.split('_active_');label=f'{side}_icon_{int(n)-1}'
                else:continue
                bounds=result.regions.get(label)
                if bounds:p.icon=self.icons.identify(image,bounds)
        if self.resolver:
            self.resolve_entities(result)
            self.context.remember(result)
        result.warnings = list(self.ocr.warnings)
        if result.screen == 'unknown':
            result.warnings.append('No supported layout matched; no field extraction attempted')
        return result

    def resolve_entities(self, result: Recognition) -> None:
        """Names only; leave HP, status text, numeric values and unknown icons alone."""
        resolver = self.resolver
        if resolver is None:
            return
        for p in result.pokemon:
            field_context=self.context.for_field(p.slot,'species')
            if p.species.provenance!='unresolved_icon':
                p.species = resolver.resolve(p.species,'species',field_context,region_kind='species')
            if p.icon:
                p.species=combine_identity(p.species,p.icon,resolver.knowledge,field_context)
            if p.species.provenance=='unresolved_icon':
                continue
            identity = p.species.resolution.canonical_id if p.species.resolution else None
            if p.slot.startswith('own_team_'):
                p.team_instance_id = p.slot
            elif p.slot.startswith('own_active_') and identity:
                members = self.context.observed_team | self.context.verified_team
                matches = [m.instance_id for m in members.values() if m.species_id==identity]
                if len(matches)==1:
                    p.team_instance_id = matches[0]
            member_slot = p.team_instance_id or p.slot
            relations = resolver.knowledge.relationships.get(identity,{})
            for field_name, observation in list(p.configuration.items()):
                kind = 'move' if field_name.startswith('move_') else {'ability':'ability','held_item':'item'}.get(field_name)
                if kind:
                    ctx = self.context.for_field(member_slot,kind,field_name)
                    if kind in ('move','ability'):
                        ctx.preferred_ids |= set(relations.get('moves' if kind=='move' else 'abilities',[]))
                        ctx.source += '+source_relationships_soft_only'
                    p.configuration[field_name] = resolver.resolve(observation,kind,ctx,region_kind=kind)
        for move in result.moves:
            # The selected actor isn't established reliably; prefer the observed team's union.
            ctx = self.context.for_field('own_move_menu','move',f'move_{move.slot}')
            move.name = resolver.resolve(move.name,'move',ctx,region_kind='move')


def annotate(frame: Frame, result: Recognition, path: str | Path) -> None:
    image = frame.image.copy()
    for label, (x1,y1,x2,y2) in result.regions.items():
        cv2.rectangle(image,(x1,y1),(x2,y2),(0,255,255),2)
        cv2.putText(image,label,(x1,max(15,y1-5)),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,255,255),1)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path),image):
        raise ValueError(f'Cannot save annotation: {path}')
