"""Observed team-preview display names; internal side IDs are not trainer IDs."""
import cv2
from battle_events.schema import Participant
from battle_events.aliases import alias_key
from copy import deepcopy
import re


def recognize_preview_trainers(image, backend, *, source, sha256, timestamp=None, timestamp_uncertainty=None, sides=('self','opponent')):
    h,w=image.shape[:2];observations={}
    for side,bounds,color in [('self',(.165,.058,.305,.11),'purple'),('opponent',(.745,.058,.888,.11),'red')]:
        if side not in sides:continue
        box=tuple(round(v*(w if i%2==0 else h)) for i,v in enumerate(bounds))
        x1,y1,x2,y2=box;hsv=cv2.cvtColor(image[y1:y2,x1:x2],cv2.COLOR_BGR2HSV)
        colored=((hsv[:,:,0]>165)|(hsv[:,:,0]<10))&(hsv[:,:,1]>100) if color=='red' else (hsv[:,:,0]>=110)&(hsv[:,:,0]<=145)&(hsv[:,:,1]>70)
        # Unrecognized preview layout must not calibrate ownership colors.
        if colored.mean()<.35:continue
        o=backend.read(image,box)
        observations[side]={'display_name':o.raw_text if o.confidence>=.75 and o.raw_text else None,
            'raw_text':o.raw_text,'unique_trainer_id':None,'ocr_confidence':o.confidence,
            'evidence':[{'source':source,'sha256':sha256,'box':box,'timestamp':timestamp,
                         'timestamp_uncertainty_seconds':timestamp_uncertainty,'color':color,
                         'basis':'visible_team_preview_panel'}]}
    return observations


def trainer_observation(observation, battle_id, side):
    """A UI trainer label is not a Pokémon identity or a unique account ID."""
    result = deepcopy(observation)
    raw = result['raw_text']
    matching = alias_key(raw)
    complete = bool(matching and not any(c in raw for c in ('…', '...', '\ufffd'))
                    and not any(ord(c) < 32 and not c.isspace() for c in raw))
    result.update(battle_id=battle_id, side=side, normalized_matching_form=matching,
                  status='accepted' if complete and result['ocr_confidence'] >= .95 else 'unresolved',
                  entity_kind='trainer', unique_trainer_id=None,
                  policy='champions-six-to-four-trainer-label-v1')
    return result


class OpeningSequence:
    """User-reviewed UI convention; order supports matching, never replaces ID proof."""
    def __init__(self):
        self.preview = None
        self.trainers = {}
        self.opponent_first = None
        self.closed = False
        self.last_timestamp = None

    def observe(self, row):
        if self.last_timestamp is not None and row['timestamp'] <= self.last_timestamp:
            raise ValueError('Opening evidence must be strictly chronological')
        self.last_timestamp = row['timestamp']
        ui = row.get('ui', {})
        if (self.preview and self.opponent_first is None and ui.get('confidence',0) >= .9
                and ui.get('phase') in {'battle_screen','move_selection','move_target_selection','switch_selection'}):
            self.closed = True
        if not self.closed and ui.get('phase') == 'team_preview' and ui.get('confidence', 0) >= .9:
            self.preview = dict(source_id=row['source_id'], timestamp=row['timestamp'], sha256=row['sha256'])
        for observation in row.get('trainer_observations', []):
            if (observation['status'] == 'accepted' and observation.get('evidence')
                    and observation['evidence'][0]['timestamp'] <= row['timestamp']):
                old = self.trainers.get(observation['side'])
                if old and old['normalized_matching_form'] != observation['normalized_matching_form']:
                    self.trainers[observation['side']] = dict(observation, status='conflicting')
                elif not old:
                    self.trainers[observation['side']] = deepcopy(observation)

    def qualify(self, event, refs):
        t = event['attributes']['observation_time']
        if not self.preview or self.closed:
            return dict(confirmed=False, reason='opening_context_not_established')
        if event['event_type'] != 'send_out':
            if event['event_type'] in {'move_execution','switch_out','faint','transformation'}:self.closed = True
            return dict(confirmed=False, reason='non_entry_action_closes_opening')
        if len(refs) != 2:
            self.closed = True
            return dict(confirmed=False, reason='double_entry_required_for_opening')
        text = re.sub(r'\s+', '', event['original_text'])
        match = re.fullmatch(r'(.+?)派出了.+', text)
        if match:
            observation = self.trainers.get('opponent', {})
            valid = (observation.get('status') == 'accepted'
                     and observation['evidence'][0]['timestamp'] <= t
                     and alias_key(match[1]) == observation['normalized_matching_form'])
            own = self.trainers.get('self', {})
            collision = (own.get('status') == 'accepted' and own['normalized_matching_form'] == alias_key(match[1]))
            if valid and not collision and self.opponent_first is None:
                self.opponent_first = dict(event_id=event['event_id'], timestamp=t)
                return dict(confirmed=True, side='opponent', basis='explicit_preview_trainer_id_match',
                            trainer_evidence=deepcopy(observation), preview=self.preview,
                            ordering_support='opponent_first_in_confirmed_preview_to_opening_sequence')
            return dict(confirmed=False, reason='trainer_id_absent_uncertain_or_mismatched')
        if text.startswith('上吧'):
            support = self.opponent_first is not None
            self.closed = True
            return dict(confirmed=support, side='self', basis='literal_self_entry',
                        ordering_support='self_follows_matched_opponent' if support else 'missing_first_opening_message')
        return dict(confirmed=False, reason='opening_format_unresolved')
