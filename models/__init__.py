"""JSON-compatible observations. No hidden-state inference."""
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RawOCR:
    text: str
    confidence: float
    region: tuple[int,int,int,int] | None = None
    language: str = ''
    engine: str = 'tesseract'
    tokens: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EntityCandidate:
    canonical_id: str
    kind: str
    names: dict[str,str]
    species_id: int | None
    form_id: int | None
    matched_name: str
    edit_distance: int
    similarity: float
    ranking_score: float
    evidence: list[str] = field(default_factory=list)
    availability: dict[str, Any] | None = None


@dataclass
class EntityResolution:
    canonical_id: str | None = None
    species_id: int | None = None
    form_id: int | None = None
    status: str = 'unresolved'
    method: str = 'unknown'
    confidence: str = 'none'
    verification_status: str = 'unverified'
    score_semantics: str = 'heuristic scores, not probabilities'
    normalized_text: str = ''
    candidates: list[EntityCandidate] = field(default_factory=list)
    debug_candidates: list[EntityCandidate] = field(default_factory=list)
    filtered_zero_similarity_count: int = 0
    evidence: list[str] = field(default_factory=list)


@dataclass
class Observation:
    value: Any = None
    confidence: float = 0.0
    region: tuple[int, int, int, int] | None = None
    raw_text: str = ""
    provenance: str = "visible_ocr"
    raw_ocr: RawOCR | None = None
    resolution: EntityResolution | None = None


@dataclass
class Pokemon:
    slot: str
    species: Observation = field(default_factory=Observation)
    hp: Observation = field(default_factory=Observation)
    configuration: dict[str, Observation] = field(default_factory=dict)
    team_instance_id: str | None = None
    icon: 'IconEvidence | None' = None


@dataclass
class IconCandidate:
    canonical_id: str | None
    species_id: int | None
    form_id: int | None
    asset: str
    similarity: float
    scale: float
    location: tuple[int, int]


@dataclass
class IconEvidence:
    status: str = 'unresolved'
    species_id: int | None = None
    form_id: int | None = None
    canonical_id: str | None = None
    region: tuple[int, int, int, int] | None = None
    candidates: list[IconCandidate] = field(default_factory=list)
    method: str = 'masked_multiscale_template'
    score_semantics: str = 'masked color correlation, not calibrated probability'
    latency_ms: float = 0.0
    source_commit: str = ''
    reason: str = ''


@dataclass
class Move:
    slot: int
    name: Observation
    pp: Observation


@dataclass
class Recognition:
    source: str
    frame_index: int
    timestamp: float | None
    screen: str = "unknown"
    confidence: float = 0.0
    components: list[str] = field(default_factory=list)
    pokemon: list[Pokemon] = field(default_factory=list)
    moves: list[Move] = field(default_factory=list)
    conditions: dict[str, Observation] = field(default_factory=dict)
    message: Observation = field(default_factory=Observation)
    regions: dict[str, tuple[int, int, int, int]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    capture_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BattleEvent:
    timestamp: float | None
    frame_index: int
    kind: str
    subject: str
    before: Any
    after: Any
    confidence: float
    provenance: str = "observed_change"
    evidence: Observation | None = None
