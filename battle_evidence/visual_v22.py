"""Scoped three-card command reconciliation over the unchanged v2 estimator.

Native controls, a timer reset, a previously observed four-slot command and live
resolution after a faint can supersede a stale replacement wait. This establishes
command availability, not why a team has no replacement. Battle Log is never read.
"""
from copy import deepcopy
from speed_inference.domains import digest
from .visual import VisualPhaseEstimator

VERSION = 'normal-screen-three-hud-v2.2'


class VisualPhaseEstimatorV22(VisualPhaseEstimator):
    def __init__(self, battle_id, *, max_gap=1.6):
        super().__init__(battle_id, profile='v2')
        self.faint_time = None
        self.pivot_wait = False
        self.previous_slots = set()
        self.last_command_timer = None
        self.trial = None
        self.reconciliations = []
        self.original_seen = {}

    def consume(self, observation):
        # Preserve base duplicate/revision and cross-battle validation before
        # changing contextual state.
        if observation['battle_id'] != self.battle_id:
            raise ValueError('Cross-battle observation')
        original_fp = digest(observation)
        if observation['id'] in self.original_seen:
            if self.original_seen[observation['id']] != original_fp:
                raise ValueError('Visual evidence revision requires replay')
            return dict(status='duplicate_ignored')
        if observation['id'] in self.seen:
            return super().consume(observation)
        if self.last and observation['timestamp'] <= self.last['timestamp']:
            return super().consume(observation)
        o = deepcopy(observation)
        s = o.get('signals', {})
        t = o['timestamp']
        if s.get('pivot_action'):
            self.pivot_wait = True
        if s.get('sendout'):
            self.pivot_wait = False
            self.faint_time = None
        if s.get('faint'):
            self.faint_time = t
        slots = set(s.get('hud_slots', []))
        timer = s.get('command_timer')
        timer_known = type(timer) is int and 0 <= timer <= 90
        both_sides = (any(x.startswith('own_active_') for x in slots)
                      and any(x.startswith('opponent_active_') for x in slots))
        clean = (not s.get('menu') and s.get('overlay') is None
                 and not any(s.get(k) for k in ('missing_image', 'faint', 'pivot_action', 'pre_battle', 'battle_end'))
                 and not o.get('actions'))
        layout = (s.get('hud_cards') == 3 and len(slots) == 3 and both_sides
                  and len(self.previous_slots) == 4 and slots < self.previous_slots)
        native = s.get('native_dual_controls') is True and s.get('normal_controls') is True
        reset = timer_known and self.last_command_timer is not None and timer > self.last_command_timer
        resolution = (self.open and len({a['event_id'] for a in self.resolution}) >= 2)
        after_faint = (self.faint_time is not None
                       and any(a['timestamp'] > self.faint_time for a in self.resolution))
        interruption_ok = not self.interruptions or self.resumed
        if (self.trial is None and self.pending and not self.pivot_wait and resolution
                and after_faint and interruption_ok and layout and clean and native
                and timer_known and s.get('command_label') and reset):
            self.trial = dict(frame_id=o['id'],timestamp=t,slots=sorted(slots),timer=timer,
                              faint_time=self.faint_time,
                              basis='native_dual_controls; reset_command_timer; previous_four_slots_minus_one; '
                                    'multiple_live_actions; resolution_continued_after_faint; no_unresolved_pivot')
        if self.trial:
            # The ordinary v2 three-sample hysteresis still must complete. A
            # submenu/overlay cannot bootstrap this exception, and interruption
            # or disappearance cancels the trial and restores the pending wait.
            continuous = (layout and slots == set(self.trial['slots']) and clean
                          and timer_known and s.get('command_label') and timer <= self.trial['timer']
                          and (self.last is None or t-self.last['timestamp'] <= self.max_gap))
            if continuous:
                self.pending = False
                if native:
                    s['battle_view'] = True
                    s['v22_geometry_basis'] = 'native_dual_controls_and_stable_three_HUD_slots'
                s['v22_replacement_reconciliation'] = deepcopy(self.trial)
            else:
                self.pending = True
                self.candidate = []
                self.trial = None
        before = len(self.segments)
        result = super().consume(o)
        self.original_seen[observation['id']] = original_fp
        if self.trial:
            if len(self.segments) > before:
                self.reconciliations.append(dict(self.trial,confirmed_at=t,
                                                 segment=self.segments[-1]['id']))
                self.trial = None
                self.faint_time = None
            elif not self.candidate:
                self.pending = True
                self.trial = None
        if self.open and not self.resolution and s.get('command_label') and timer_known:
            self.last_command_timer = timer
            if len(slots) == 4:
                self.previous_slots = slots
        return result

    def export(self):
        result = super().export()
        result.update(profile='v2.2',reconciliations=deepcopy(self.reconciliations))
        return result


def replay_observations(prediction):
    """Lossless temporal inputs from sealed sidecar history and immutable actions."""
    visual = prediction['visual']
    by_frame = {}
    for a in [a for s in visual['segments'] for a in s['actions']] + visual['unclosed_resolution_actions']:
        by_frame.setdefault(a['frame_id'], {})[a['event_id']] = a
    for h in visual['phase_history']:
        yield dict(id=h['frame_id'],battle_id=prediction['battle_id'],timestamp=h['timestamp'],
                   source_id=h['source_id'],signals=deepcopy(h['signals']),
                   actions=[{k:v for k,v in a.items() if k not in ('frame_id','timestamp')}
                            for a in by_frame.get(h['frame_id'], {}).values()])
