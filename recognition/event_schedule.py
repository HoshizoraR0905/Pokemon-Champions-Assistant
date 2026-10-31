"""M2.3.8 scheduling observations. No authoritative Pokémon state lives here."""
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
import math
import re
import cv2
from recognition import box

VERSION = 'event-driven-preview-bounded-v3'


@dataclass(frozen=True)
class EventConfig:
    version: str = VERSION
    active_fps: float = 2.
    region_difference: float = .015
    unknown_fallback_seconds: float = 3.
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
        self.hp_until = -1.

    def monitor(self, t, observation, message_visible=False, *, hud_changed=False, banner_visible=False):
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
        if message_visible or banner_visible:self.hp_until = t + 3.
        return message_visible or banner_visible or hud_changed or not self.command or self.due(t)

    def due(self, t):
        return t+1e-7 >= self.next_time

    def advance(self, t, *, phase, message_visible, changed):
        fps = 1. if self.command and not message_visible else self.config.active_fps
        self.next_time = (math.floor(t*fps+1e-7)+1)/fps
        return fps

    def dump(self):
        return dict(last_command=self.last_command, command=self.command, transitions=self.transitions, hp_until=self.hp_until)

    def restore(self, data):
        self.last_command=data['last_command']; self.command=data['command']; self.transitions=data['transitions']
        self.hp_until=data.get('hp_until', -1.)


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
        self.team = {'self': {}, 'opponent': {}}
        self.trainers = {}; self.trainer_attempts = {}; self.trainer_last_attempt = {}
        self.preview_reads = {}; self.preview_active = False

    def observe_phase(self, phase):
        # Reappearance is a fresh opportunity for unresolved rows, without
        # discarding successful identities or borrowing another row's prediction.
        active = phase == 'team_preview'
        entered = active and not self.preview_active
        if entered:
            for row in self.preview_reads.values():row['timestamp'] = -10.
        self.preview_active = active
        return entered

    def acquire_trainers(self, recognizer, frame, phase, confidence, battle_id, counts):
        from recognition.trainers import recognize_preview_trainers, trainer_observation, aggregate_trainer
        if phase != 'team_preview' or confidence < .9:return []
        sides = [side for side in ('self','opponent') if self.trainers.get(side,{}).get('status')!='accepted'
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
            self.trainers[side]=aggregate_trainer(self.trainers.get(side),observation)
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
        elif phase == 'team_preview':
            from recognition.fast_profile import normalized, difference
            import numpy as np
            result=Recognition(frame.source,frame.index,frame.timestamp,phase,.9,['team_preview'])
            result.capture_metadata=frame.metadata.copy()
            for i in range(6):
                key=str(i+1)
                y=.13+i*.117; bounds=box(frame.image,(.778,y-.01,.832,y+.095))
                signature=normalized(frame.image,bounds)
                old=self.preview_reads.get(key)
                changed=old is not None and difference(signature,np.asarray(old['signature'],dtype=np.uint8)) >= .20
                if old and not changed and (key in self.team['opponent'] or frame.timestamp-old['timestamp'] < 10.):
                    counts['preview_row_reads_suppressed']+=1
                    continue
                # A changed icon must not retain a successful earlier identity
                # if this independent attempt is now unresolved.
                self.team['opponent'].pop(key,None)
                self.preview_reads[key]=dict(timestamp=frame.timestamp,signature=signature.tolist())
                result.pokemon.append(Pokemon(f'opponent_team_{i+1}',Observation(region=bounds,provenance='unresolved_icon'),
                                               icon=recognizer.icons.identify(frame.image,bounds)))
                counts['preview_icon_requests']+=1
            if not result.pokemon:return rows
            recognizer.resolve_entities(result);recognizer.context.remember(result)
            rows=preview_rows(result,battle_id)
            for row in rows:
                if row['status']=='resolved':self.team['opponent'][str(row['preview_row'])]=row
            counts['opponent_preview_acquisitions']+=1
        return rows
