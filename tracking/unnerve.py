"""Observed berry restriction and active-source consistency; no item effects."""
from copy import deepcopy

from .battle_state import Effect, Fact, fact
from .mechanics import ability, active

KEY = 'berry_consumption_prevention'
UNNERVE = 'pokeapi:ability:127'


def sources(state, side):
    return [p for p in state.pokemon.values() if p.side_id != side and active(p)
            and ability(p) == UNNERVE and p.ability.suppressed.value is not True
            and p.ability.suppressed.knowledge != 'conflicting']


def observe(state, event, record):
    from .state_engine import evidence_link
    effect = state.sides[event.side].temporary_effects.setdefault(KEY, Effect())
    effect.kind = fact('unnerve', evidence_link(event))
    effect.active = fact(True, evidence_link(event))
    owners = sources(state, event.side)
    effect.initiated_by = (fact([p.pokemon_instance_id for p in owners], evidence_link(event), 'derived')
                           if owners else Fact(provenance=[evidence_link(event)]))
    record.bindings['ability_sources'] = [dict(instance_id=p.pokemon_instance_id,
        ability=deepcopy(p.ability.current.value), evidence=deepcopy(p.ability.current.provenance)) for p in owners]
    state.observations.append(dict(event_id=event.event_id, event_type=event.event_type,
        affected_side=event.side, attributes=deepcopy(event.attributes), evidence=evidence_link(event)))


def refresh(state, event):
    from .state_engine import evidence_link
    for side, team in state.sides.items():
        owners = sources(state, side)
        effect = team.temporary_effects.get(KEY)
        if not owners and effect is None:
            continue
        if effect is None:
            effect = team.temporary_effects.setdefault(KEY, Effect())
        ids = [p.pokemon_instance_id for p in owners]
        if ids:
            if effect.initiated_by.value != ids or effect.active.value is not True:
                proof = dict(**evidence_link(event), rule='active_opposing_unnerve',
                             ability_evidence={p.pokemon_instance_id:deepcopy(p.ability.current.provenance) for p in owners})
                effect.active = fact(True, proof, 'derived')
                effect.kind = fact('unnerve', proof, 'derived')
                effect.initiated_by = fact(ids, proof, 'derived')
        elif effect.initiated_by.known and effect.initiated_by.value:
            if effect.active.value is not False:
                effect.active = fact(False, dict(**evidence_link(event), rule='all_identified_unnerve_sources_inactive'), 'derived')
        elif (effect.active.value is True and event.side != side
              and event.event_type in {'switch_out', 'faint', 'ability_change', 'transformation'}):
            # Keep the observation, but an unidentified source cannot be tracked
            # through a subsequent departure/change as a current certainty.
            effect.active = Fact(provenance=[evidence_link(event)])
