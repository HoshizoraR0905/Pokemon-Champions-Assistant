"""Opt-in fast/diagnostic scheduling; not used by event-driven production.

Shared pixel gates/detection stay in fast_profile. This module does not update
battle state or provide an alternate semantic parser.
"""
from dataclasses import dataclass
import math
from recognition.fast_profile import VERSION


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
