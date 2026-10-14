"""Events describe evidence-supported outcomes, independently of their adapter."""
from dataclasses import dataclass, field, asdict
from typing import Literal
import hashlib

Side = Literal['self', 'opponent', 'unknown', 'field']
EVENT_TYPES = {'switch_out','send_out','move_execution','hp_change','ability_activation',
               'item_activation','weather_change','terrain_change','stat_change','faint',
               'status_change','critical_hit','multi_hit','effectiveness','move_effect','unknown'}

@dataclass
class Participant:
    side_id: str
    display_name: str | None = None
    unique_trainer_id: str | None = None
    evidence: list[dict] = field(default_factory=list)

@dataclass
class Evidence:
    source_type: str
    source_id: str
    observation_ids: list[str]
    details: dict = field(default_factory=dict)

@dataclass
class BattleEvent:
    event_id: str
    event_type: str
    side: Side
    actor: dict | None
    target: dict | None
    original_text: str
    canonical_references: dict
    log_order: int | None
    evidence: list[Evidence]
    ocr_confidence: float | None
    parsing_confidence: str
    uncertainty: list[str]
    attributes: dict = field(default_factory=dict)
    status: str = 'candidate'
    associated_video_evidence: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if self.event_type not in EVENT_TYPES: raise ValueError('Unsupported event type')
        if self.side not in {'self','opponent','unknown','field'}: raise ValueError('Invalid side')

    def to_dict(self): return asdict(self)


def stable_id(battle_id, source_key):
    # Identity is stable within a source/battle; cross-source fusion is a future task.
    return 'event:'+hashlib.sha256((battle_id+'\0'+source_key).encode()).hexdigest()[:24]
