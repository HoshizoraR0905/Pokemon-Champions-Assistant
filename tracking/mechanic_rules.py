"""Explicit, serialized rule profiles. Simulator evidence is not game verification."""
from dataclasses import dataclass, field, asdict

COMMIT = '3a766f2cfb5e51c1e428cfe87d0dba91a8f01640'
SOURCE = f'https://github.com/smogon/pokemon-showdown/blob/{COMMIT}/data/'

@dataclass
class MechanicRules:
    profile_id: str = 'champions-evidence-only-v1'
    verification: str = 'champions_rules_unverified'
    protect_move_ids: list[str] = field(default_factory=lambda: ['pokeapi:move:182'])
    protect_divisor: int | None = None
    protect_counter_cap: int | None = None
    protect_resets: bool = False
    protean_once_per_entry: bool = False
    unburden_item_loss: bool = False
    sources: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    def __post_init__(self):
        if self.protect_divisor is not None and self.protect_divisor < 2:
            raise ValueError('Invalid Protect divisor')
        if self.protect_counter_cap is not None and self.protect_counter_cap < 1:
            raise ValueError('Invalid Protect cap')


def showdown_champions_reference():
    """Opt-in software reference; never labeled authoritative Champions truth.

    Restrict family to Protect, Detect, Endure, Baneful Bunker, King's Shield,
    and Spiky Shield, whose stall-counter implementation was inspected.
    Eligibility/availability is not inferred for any Pokémon.
    """
    return MechanicRules(
        profile_id='showdown-champions-reference-v1', verification='simulator_reference_only',
        protect_move_ids=[f'pokeapi:move:{n}' for n in (182, 197, 203, 661, 588, 596)],
        protect_divisor=3, protect_counter_cap=729, protect_resets=True,
        protean_once_per_entry=True, unburden_item_loss=True,
        sources=[SOURCE+n for n in ('conditions.ts', 'moves.ts', 'abilities.ts',
                                   'mods/champions/scripts.ts', 'mods/champions/moves.ts',
                                   'mods/champions/abilities.ts')])
