"""Observed team-preview display names; internal side IDs are not trainer IDs."""
import cv2
from battle_events.schema import Participant
from battle_events.aliases import alias_key
from copy import deepcopy
import re


def recognize_matchmaking_trainer(image, backend, *, source, sha256, timestamp):
    """Explicit found-opponent dialog; geometry alone cannot establish a name.

    Call only for a scoped prebattle dialog candidate. The two complete lines
    identify the opponent; no self ID is displayed in this dialog.
    """
    h,w=image.shape[:2]
    bounds=tuple(round(v*(w if i%2==0 else h)) for i,v in enumerate((.40,.415,.60,.535)))
    o=backend.read(image,bounds,multiline=True)
    text=re.sub(r'\s+','',o.raw_text or '')
    match=re.fullmatch(r'已找到对战对手[。.]与(.+?)的对战即将开始[。.]',text)
    return [dict(raw_text=match[1] if match else '',display_name=None,ocr_confidence=o.confidence,
        side='opponent' if match else 'unknown',
        parse_status='supported' if match else 'unresolved',
        raw_dialog_text=o.raw_text,ui_region='matchmaking_opponent_dialog',
        evidence=[dict(source=source,sha256=sha256,timestamp=timestamp,box=bounds,
                       basis='complete_found_opponent_dialog_grammar')])]


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
        readings=[dict(raw_text=o.raw_text,ocr_confidence=o.confidence,box=box,method='panel')]
        # Excess background is particularly harmful to short labels. Read a
        # foreground crop as a separate observation, never rewrite glyphs (J/1).
        if len(alias_key(o.raw_text or '')) <= 2 or o.confidence < .95:
            import numpy as np
            white=(hsv[:,:,1]<90)&(hsv[:,:,2]>155)
            ys,xs=np.where(white)
            if len(xs)>=4:
                tight=(max(x1,x1+int(xs.min())-4),max(y1,y1+int(ys.min())-4),
                       min(x2,x1+int(xs.max())+5),min(y2,y1+int(ys.max())+5))
                retry=backend.read(image,tight)
                readings.append(dict(raw_text=retry.raw_text,ocr_confidence=retry.confidence,
                                     box=tight,method='foreground_crop'))
        observations[side]={'display_name':o.raw_text if o.confidence>=.75 and o.raw_text else None,
            'raw_text':o.raw_text,'unique_trainer_id':None,'ocr_confidence':o.confidence,
            'readings':readings,
            'ui_region':'team_preview_'+side+'_trainer_panel',
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


def aggregate_trainer(previous, observation):
    """Count distinct frames, retain alternatives, and abstain on strong ties.

    Multiple crops of one frame count once. Short IDs require two clear frames.
    Weak competing reads remain visible but cannot veto repeated clear evidence.
    """
    observations=deepcopy((previous or {}).get('observations',[]))
    if observation not in observations:observations.append(deepcopy(observation))
    candidates={}
    for obs in observations:
        proof=obs.get('evidence') or []
        if not proof:continue
        frame=proof[0].get('sha256') or proof[0].get('source')
        if not frame:continue
        for reading in obs.get('readings') or [obs]:
            raw=reading.get('raw_text') or '';key=alias_key(raw)
            if not key or any(c in raw for c in ('…','...','\ufffd')):continue
            item=candidates.setdefault(key,dict(display_name=raw,frames={},readings=[]))
            score=reading.get('ocr_confidence',0)
            item['frames'][frame]=max(score,item['frames'].get(frame,0))
            item['readings'].append(deepcopy(reading))
    qualified=[]
    for key,item in candidates.items():
        item['strong_frames']=sum(c>=.95 for c in item['frames'].values())
        if item['strong_frames'] >= (2 if len(key)<=2 else 1):qualified.append(key)
    # Strong but not yet repeated short alternatives still prevent certainty.
    strong=[k for k,v in candidates.items() if v['strong_frames']]
    winner=qualified[0] if len(qualified)==1 and len(strong)==1 else None
    result=deepcopy(observation)
    result.update(observations=observations,candidates=candidates,
        status='accepted' if winner else 'conflicting' if len(strong)>1 else 'unresolved',
        display_name=candidates[winner]['display_name'] if winner else None,
        normalized_matching_form=winner,policy='trainer-distinct-frame-consensus-v2',
        evidence=[deepcopy(p) for o in observations for p in o.get('evidence',[])])
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
            if (observation.get('evidence')
                    and observation['evidence'][0]['timestamp'] <= row['timestamp']):
                side=observation['side']
                self.trainers[side]=aggregate_trainer(self.trainers.get(side),observation)

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
