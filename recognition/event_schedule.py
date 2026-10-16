"""M2.3.8 scheduling observations. No authoritative Pokémon state lives here."""
from copy import deepcopy
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
import math
import re
import cv2
import numpy as np
from recognition import box
from recognition.fast_profile import FastConfig, normalized, difference, recognize_cards

VERSION = 'event-driven-v1'


@dataclass(frozen=True)
class EventConfig(FastConfig):
    version: str = VERSION
    command_loss_seconds: float = 2.0


def glyph_mask(image):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    return ((hsv[:, :, 1] < 90) & (hsv[:, :, 2] > 155)).astype('uint8') * 255


@lru_cache(maxsize=1)
def command_templates():
    root = Path(__file__).parent / 'assets'
    return [glyph_mask(cv2.resize(cv2.imread(str(root / f'command_label_{i}.png')), (87, 18)))
            for i in range(2)]


def command_label(image):
    """Search verified layout-dependent bands; template is UI text, not a model."""
    if image.shape[:2] != (603, 1311):
        return dict(visible=False, reason='unsupported_layout', countdown=None)
    candidates = []
    for layout, roi in [('overlay', (.755, .074, .852, .125)),
                        ('move_menu', (.775, .205, .875, .265))]:
        x, y, X, Y = box(image, roi); mask = glyph_mask(image[y:Y, x:X])
        for template in command_templates():
            scores = cv2.matchTemplate(mask, template, cv2.TM_CCOEFF_NORMED)
            _, score, _, (dx, dy) = cv2.minMaxLoc(scores)
            candidates.append((score, layout, [x+dx, y+dy, x+dx+87, y+dy+18]))
    score, layout, bounds = max(candidates)
    return dict(visible=score >= .60, score=score, layout=layout, bounds=bounds,
                countdown=None, reason='matched_COMMAND_label' if score >= .60 else 'no_verified_label')


class EventInspection:
    """Cheap monitoring always runs at 2 FPS, even while inspection is at 1 FPS."""
    def __init__(self, config=None):
        self.config = config or EventConfig(); self.next_time = 0.; self.boost_until = 0.
        self.last_command = None; self.command = False; self.transitions = []
        self.last_monitor = None

    def monitor(self, t, observation, message_visible=False):
        old = self.command
        if observation['visible']:
            self.last_command = t; self.command = True
        elif self.last_command is None or t-self.last_command > self.config.command_loss_seconds:
            self.command = False
        loss = self.command and not observation['visible']
        reason = ('COMMAND_visible' if observation['visible'] else 'COMMAND_temporary_loss'
                  if loss else 'default_live_monitoring')
        if old != self.command:
            self.transitions.append(dict(timestamp=t, command=self.command, reason=reason))
        self.last_monitor = dict(observation, active=self.command, temporary_loss=loss, reason=reason,
                                 message_override=bool(message_visible))
        return message_visible or not self.command or self.due(t)

    def due(self, t):
        return t+1e-7 >= self.next_time

    def advance(self, t, *, phase, message_visible, changed):
        fps = 1. if self.command and not message_visible else 2.
        self.next_time = (math.floor(t*fps+1e-7)+1)/fps
        return fps

    def dump(self):
        return dict(last_command=self.last_command, command=self.command, transitions=self.transitions)

    def restore(self, data):
        self.last_command=data['last_command']; self.command=data['command']; self.transitions=data['transitions']


def ordered_entries(text):
    """Keep literal references and titles; never use roster guesses to split names."""
    text = text.strip().replace('\n', '').replace('\r', '')
    if text.startswith('上吧'):
        body = re.sub(r'^上吧[！!，,]*', '', text)
        return [s.strip() for s in re.split('[！!]', body) if s.strip()]
    if '派出了' in text:
        body = text.split('派出了', 1)[1].rstrip('！!。.')
        # A conjunction inside a nickname remains ambiguous; no forced split.
        refs = [s.strip() for s in body.split('和')]
        return refs if len(refs) <= 2 else [body]
    return []


def entry_slots(side, references):
    """Existing slots are screen-HUD left/right, verified on Battle 5 opening.

    This mapping never assigns a biological identity from a roster or 3D model.
    Single entries rely on StateEngine's established vacant-slot evidence.
    """
    if len(references)!=2 or side not in {'self','opponent'}:return [None]*len(references)
    return ['left','right'] if side=='self' else ['right','left']


class IdentitySchedule:
    """Recognition cache by HUD card episode, never a second battle-state ledger."""
    def __init__(self):
        self.known = {}; self.pending = {}; self.team = {'self': {}, 'opponent': {}}
        self.trainers = {}; self.trainer_attempts = {}; self.trainer_last_attempt = {}

    def acquire_trainers(self, recognizer, frame, phase, confidence, battle_id, counts):
        from recognition.trainers import recognize_preview_trainers, trainer_observation
        if phase != 'team_preview' or confidence < .9:return []
        sides = [side for side in ('self','opponent') if side not in self.trainers
                 and self.trainer_attempts.get(side,0) < 3
                 and frame.timestamp-self.trainer_last_attempt.get(side,float('-inf')) >= 2]
        if not sides:return []
        observed = recognize_preview_trainers(frame.image, recognizer.ocr, source=frame.source,
            sha256=frame.metadata['sha256'], timestamp=frame.timestamp, sides=sides)
        result = []
        for side in sides:
            self.trainer_attempts[side] = self.trainer_attempts.get(side,0)+1
            self.trainer_last_attempt[side] = frame.timestamp
            if side not in observed:continue
            counts['trainer_label_read_requests'] += 1
            observation = trainer_observation(observed[side], battle_id, side)
            observation['evidence'][0]['image'] = frame.metadata.get('image')
            result.append(observation)
            if observation['status'] == 'accepted':self.trainers[side] = observation
        return result

    def invalidate(self, event):
        if event['event_type'] not in {'send_out', 'switch_out', 'faint', 'transformation','position_change'}:
            return
        side = event['side']; t = event['attributes']['observation_time']
        actor=(event.get('actor') or {}).get('species_id')
        candidates=[key for key,v in self.known.items() if v.get('species_id')==actor and actor is not None
            and (side=='unknown' or key.startswith('own' if side=='self' else side))]
        if len(candidates)==1:
            self.known.pop(candidates[0]);self.pending[side]=dict(timestamp=t,slot=candidates[0],event_id=event['event_id'])
            return
        if event['event_type']=='send_out' and side in self.pending and self.pending[side].get('slot'):
            self.known.pop(self.pending.pop(side)['slot'],None)
            return
        for key in list(self.known):
            if side == 'unknown' or key.startswith('own' if side == 'self' else side):
                self.known.pop(key)
        self.pending[side] = dict(timestamp=t, event_id=event['event_id'], reason=event['event_type'])

    def recognize(self, recognizer, frame, cards, counts):
        from models import Observation
        from recognition.parsers import ratio, percentage
        full=[]; light=[]
        for card in cards:
            side, i, o, name = card; key=f'{side}_active_{i+1}'
            sig=normalized(frame.image, box(frame.image, name), text=True)
            icon_roi=(.080+o,.825,.137+o,.961) if side=='own' else (.563+o,.030,.623+o,.157)
            icon_sig=normalized(frame.image,box(frame.image,icon_roi))
            old=self.known.get(key)
            changed=(old is None or difference(sig,np.asarray(old['signature'],dtype=np.uint8))>=.015 or
                     difference(icon_sig,np.asarray(old['icon_signature'],dtype=np.uint8))>=.10)
            if changed or not old.get('resolved') and old.get('attempts',0)<2:
                full.append(card)
            else:
                # HP is a new observation; identity evidence keeps its original source.
                mon=dict(slot=key, species={}, icon=None, identity_reused_from=old['source_id'])
                if side == 'own':
                    a=recognizer.ocr.read(frame.image,box(frame.image,(.177+o,.915,.213+o,.955)),numeric=True,italic=True)
                    b=recognizer.ocr.read(frame.image,box(frame.image,(.220+o,.925,.243+o,.955)),numeric=True,italic=True)
                    hp=ratio(Observation(f'{a.value or ""}/{b.value or ""}',min(a.confidence,b.confidence),
                        (a.region[0],a.region[1],b.region[2],b.region[3]),f'{a.raw_text}/{b.raw_text}'))
                else:
                    hp=percentage(recognizer.ocr.read(frame.image,box(frame.image,(.681+o,.113,.727+o,.154)),numeric=True))
                mon['hp']=asdict(hp); light.append(mon); counts['identity_reads_reused']+=1
        result=recognize_cards(recognizer,frame,full).to_dict() if full else dict(pokemon=[])
        counts['full_identity_recognition_invocations']+=len(full)
        counts['hud_hp_reading_invocations']+=len(cards)
        for mon,card in zip(result['pokemon'],full):
            resolution=mon['species'].get('resolution') or {}
            # Existing admission remains in StateEngine; this cache only schedules work.
            side,i,o,name=card
            icon_roi=(.080+o,.825,.137+o,.961) if side=='own' else (.563+o,.030,.623+o,.157)
            old=self.known.get(mon['slot'])
            sig=normalized(frame.image,box(frame.image,name),text=True)
            same=old and difference(sig,np.asarray(old['signature'],dtype=np.uint8))<.015
            self.known[mon['slot']]=dict(signature=sig.tolist(),
                icon_signature=normalized(frame.image,box(frame.image,icon_roi)).tolist(),
                source_id=frame.source,species_id=resolution.get('species_id'),
                resolved=bool(resolution.get('species_id') and mon['species'].get('confidence',0)>=.9),
                attempts=old.get('attempts',0)+1 if same else 1)
        result['pokemon']+=light
        return result

    def acquire_team(self, recognizer, frame, phase, battle_id, counts):
        from models import Pokemon, Observation, Recognition
        from recognition.identity_flow import preview_rows
        rows=[]
        if phase == 'team_configuration':
            if len(self.team['self'])==6:
                return rows
            result=recognizer.recognize(frame)
            for mon in result.pokemon:
                if not mon.slot.startswith('own_team_'):continue
                n=int(mon.slot.rsplit('_',1)[1]); resolution=mon.species.resolution
                row=dict(battle_id=battle_id,side='self',preview_row=n,member_occurrence=f'{battle_id}:self:team:{n}',
                    species_id=resolution.species_id if resolution else None, species=asdict(mon.species),
                    configuration={k:asdict(v) for k,v in mon.configuration.items()},
                    status='resolved' if resolution and resolution.species_id else 'unresolved',
                    evidence={**frame.metadata, 'source':frame.source,'timestamp':frame.timestamp},
                    active_slot=None,nickname=None,persistent_instance_id=None)
                rows.append(row)
                if row['status']=='resolved':self.team['self'][str(n)]=row
            counts['player_team_acquisitions']+=1
        elif phase == 'team_preview' and len(self.team['opponent'])<6:
            result=Recognition(frame.source,frame.index,frame.timestamp,phase,.9,['team_preview'])
            result.capture_metadata=frame.metadata.copy()
            for i in range(6):
                if str(i+1) in self.team['opponent']:continue
                y=.13+i*.117; bounds=box(frame.image,(.778,y-.01,.832,y+.095))
                result.pokemon.append(Pokemon(f'opponent_team_{i+1}',Observation(region=bounds,provenance='unresolved_icon'),
                                               icon=recognizer.icons.identify(frame.image,bounds)))
            recognizer.resolve_entities(result);recognizer.context.remember(result)
            rows=preview_rows(result,battle_id)
            for row in rows:
                if row['status']=='resolved':self.team['opponent'][str(row['preview_row'])]=row
            counts['opponent_preview_acquisitions']+=1
        return rows
