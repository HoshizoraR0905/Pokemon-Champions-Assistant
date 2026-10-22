"""Additive M3.2.1 contracts; these inputs never require recognition or replay."""
from typing import Any, Literal, TypedDict


class Evidence(TypedDict):
    sources: list[str]
    basis: Literal['direct', 'deduced', 'user_requirement', 'synthetic', 'reference']
    confidence: str


class Activation(TypedDict):
    state: Literal['activated', 'not_activated', 'unknown']
    coverage_complete: bool
    evidence: Evidence


class StateChange(TypedDict):
    kind: Literal['set', 'transform', 'cancel']
    target: str
    values: dict[str, Any]
    evidence: Evidence


class PendingAction(TypedDict):
    id: str
    individual: str
    kind: Literal['move', 'voluntary_switch', 'mega_evolution']
    move: str | None
    outcome: Literal['completed', 'flinched']
    activation: Activation
    changes: list[StateChange]
    evidence: Evidence


class PriorityAction(PendingAction):
    effective_priorities: list[int]


class OrderObservation(TypedDict):
    id: str
    battle_id: str
    decision_id: str
    subject: str
    state: dict[str, Any]
    actions: list[PendingAction]
    sequence: list[str]
    initial_changes: list[StateChange]
    alternatives: list[dict[str, Any]]
    strict_speed: list[list[str]]
    evidence: Evidence


class ConfigurationFields(TypedDict):
    id: str
    speed: int
    ability: str
    item: str
    training: dict[str, Any] | None


class HiddenConfiguration(ConfigurationFields, total=False):
    form: str
    persistent: dict[str, Any]


def require_evidence(value):
    if (not isinstance(value, dict) or set(value) != {'sources', 'basis', 'confidence'}
            or not isinstance(value['sources'], list) or not value['sources']
            or not all(isinstance(s, str) and s.strip() for s in value['sources'])
            or value['basis'] not in {'direct', 'deduced', 'user_requirement', 'synthetic', 'reference'}
            or not isinstance(value['confidence'], str) or not value['confidence'].strip()):
        raise ValueError('Explicit source, basis and confidence provenance required')
