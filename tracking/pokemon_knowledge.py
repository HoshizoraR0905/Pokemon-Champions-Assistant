"""Read-only decision view. Hidden move membership remains the authoritative ledger."""
from copy import deepcopy
from functools import lru_cache


@lru_cache(maxsize=1)
def move_labels():
    from knowledge import KnowledgeBase
    return {cid: entity.names.get("zh-hans", entity.names.get("en", cid))
            for cid, entity in KnowledgeBase().entities.items() if entity.kind == "move"}


def pokemon_knowledge(pokemon, hidden=None, *, labels=None):
    hidden = hidden or {}
    labels = labels or hidden.get('labels', {})
    labels = {**move_labels(), **labels}
    result = {}
    for pid, mon in pokemon.items():
        domain = hidden.get('pokemon', {}).get(pid, {}).get('fields', {}).get('moves', {})
        slots = deepcopy(domain.get('slots', {}))
        members = list(domain.get('members', []))
        # Observable exact slots are evidence of identity, never guessed positions.
        for slot, fact in mon.get('moves', {}).get('known_slots', {}).items():
            if fact.get('knowledge') not in ('observed', 'derived'):
                continue
            value = fact.get('value')
            identity = value.get('canonical_id') if isinstance(value, dict) else value
            if identity:
                slots.setdefault(str(slot), identity)
                if identity not in members:
                    members.append(identity)
        capacity = hidden.get('move_capacity')
        result[pid] = {'revealed_moves': [{'canonical_id': cid, 'name': labels.get(cid, cid)} for cid in members],
                       'exact_slots': slots,
                       'exact_slot_evidence': deepcopy(mon.get('moves', {}).get('known_slots', {})),
                       'unrevealed_count': None if capacity is None else max(0, capacity - len(members)),
                       'capacity_rule': deepcopy(hidden.get('move_capacity_rule')),
                       'status': domain.get('status', 'unknown'),
                       'provenance': deepcopy(domain.get('constraints', [])),
                       'uncertainty': deepcopy(domain.get('unresolved', [])),
                       'conflicts': deepcopy(domain.get('conflicts', [])),
                       'source': 'hidden_configuration.moves + observable exact slots'}
    return result
