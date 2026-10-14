"""M2.2 evidence-backed state; unknown differs from zero, false and absence."""
from dataclasses import dataclass, field, asdict
from typing import Any

KNOWLEDGE = {'unknown','observed','derived','conflicting','hypothesis'}
STATS = ('attack','defense','special_attack','special_defense','speed','accuracy','evasion')
WEATHER = {'none','sun','rain','sandstorm','snow','unknown','disabled'}
TERRAIN = {'none','electric','grassy','psychic','misty','unknown'}
MAJOR_STATUS = {'none','burn','paralysis','sleep','freeze','poison','bad_poison','unknown'}

@dataclass
class Fact:
    value: Any = None
    knowledge: str = 'unknown'
    provenance: list[dict] = field(default_factory=list)
    alternatives: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if self.knowledge not in KNOWLEDGE: raise ValueError('Invalid knowledge category')
        if self.knowledge=='unknown' and self.value is not None: raise ValueError('Unknown fact cannot carry a concrete value')

    @property
    def known(self): return self.knowledge in {'observed','derived'}

@dataclass
class Duration:
    remaining: Fact = field(default_factory=Fact)
    expires_at_turn: Fact = field(default_factory=Fact)
    timing: Fact = field(default_factory=Fact)
    modifiers: Fact = field(default_factory=Fact)
    last_tick: Fact = field(default_factory=Fact)

@dataclass
class Effect:
    active: Fact = field(default_factory=Fact)
    kind: Fact = field(default_factory=Fact)
    duration: Duration = field(default_factory=Duration)
    initiated_by: Fact = field(default_factory=Fact)

@dataclass
class HPState:
    current: Fact = field(default_factory=Fact)
    maximum: Fact = field(default_factory=Fact)
    displayed_percent: Fact = field(default_factory=Fact)
    percent_interval: Fact = field(default_factory=Fact)
    unit: Fact = field(default_factory=Fact)
    observations: list[dict] = field(default_factory=list)

@dataclass
class Stage:
    value: Fact = field(default_factory=Fact)
    interval: Fact = field(default_factory=Fact)
    changes: list[dict] = field(default_factory=list)

@dataclass
class ItemState:
    identity: Fact = field(default_factory=Fact)
    status: Fact = field(default_factory=Fact)
    revealed: list[dict] = field(default_factory=list)
    activations: list[dict] = field(default_factory=list)
    changes: list[dict] = field(default_factory=list)

@dataclass
class AbilityState:
    current: Fact = field(default_factory=Fact)
    suppressed: Fact = field(default_factory=Fact)
    revealed: list[dict] = field(default_factory=list)
    modifications: list[dict] = field(default_factory=list)

@dataclass
class MoveState:
    executed: list[dict] = field(default_factory=list)
    known_slots: dict[str, Fact] = field(default_factory=dict)
    pp: dict[str, Fact] = field(default_factory=dict)
    unrevealed_slots: Fact = field(default_factory=Fact)
    hit_observations: list[dict] = field(default_factory=list)

@dataclass
class PokemonState:
    pokemon_instance_id: str
    side_id: str
    species: Fact = field(default_factory=Fact)
    current_variant: Fact = field(default_factory=Fact)
    original_identity: Fact = field(default_factory=Fact)
    location: Fact = field(default_factory=Fact)
    fainted: Fact = field(default_factory=Fact)
    hp: HPState = field(default_factory=HPState)
    major_status: Fact = field(default_factory=Fact)
    status_counters: dict[str, Fact] = field(default_factory=dict)
    stages: dict[str, Stage] = field(default_factory=lambda:{s:Stage() for s in STATS})
    item: ItemState = field(default_factory=ItemState)
    ability: AbilityState = field(default_factory=AbilityState)
    moves: MoveState = field(default_factory=MoveState)
    volatile: dict[str, Effect] = field(default_factory=dict)
    transformations: list[dict] = field(default_factory=list)
    # Reserved, never populated with invented configurations or probabilities.
    hidden_configuration: dict[str, Fact] = field(default_factory=lambda:{s:Fact() for s in
        ('held_item','ability','moveset','ev_allocation','nature','ivs','possible_transformation')})

@dataclass
class SideState:
    side_id: str
    trainer: dict = field(default_factory=dict)
    party_instance_ids: list[str] = field(default_factory=list)
    party_complete: Fact = field(default_factory=Fact)
    active_slots: dict[str,str] = field(default_factory=dict)
    vacant_slots: list[str] = field(default_factory=list)
    fainted_instance_ids: list[str] = field(default_factory=list)
    remaining_available: Fact = field(default_factory=Fact)
    conditions: dict[str, Effect] = field(default_factory=lambda:{n:Effect() for n in
        ('tailwind','reflect','light_screen','aurora_veil')})
    hazards: dict[str, Fact] = field(default_factory=dict)
    temporary_effects: dict[str, Effect] = field(default_factory=dict)
    resources: dict[str, Fact] = field(default_factory=lambda:{'mega_evolution':Fact()})

@dataclass
class BattleState:
    battle_id: str
    turn: Fact = field(default_factory=Fact)
    phase: Fact = field(default_factory=Fact)
    weather: Effect = field(default_factory=Effect)
    terrain: Effect = field(default_factory=Effect)
    trick_room: Effect = field(default_factory=Effect)
    global_effects: dict[str, Effect] = field(default_factory=dict)
    sides: dict[str, SideState] = field(default_factory=lambda:{s:SideState(s) for s in ('self','opponent')})
    pokemon: dict[str, PokemonState] = field(default_factory=dict)
    observations: list[dict] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)

    def to_dict(self): return asdict(self)


def fact(value, provenance, knowledge='observed'):
    return Fact(value,knowledge,[provenance])


def from_dict(payload):
    """Round-trip through a fresh dataclass instance, including nested facts."""
    from typing import get_type_hints, get_origin, get_args
    from dataclasses import fields, is_dataclass
    def restore(cls,value):
        origin=get_origin(cls)
        if origin is list:return [restore(get_args(cls)[0],v) for v in value]
        if origin is dict:return {k:restore(get_args(cls)[1],v) for k,v in value.items()}
        if is_dataclass(cls):
            hints=get_type_hints(cls)
            return cls(**{f.name:restore(hints[f.name],value[f.name]) for f in fields(cls) if f.name in value})
        return value
    return restore(BattleState,payload)
