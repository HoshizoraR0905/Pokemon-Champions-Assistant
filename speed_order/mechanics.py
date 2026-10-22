"""Deterministic reference priority/override handlers, separate from Speed."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
from .core import ACTOR_KEYS, MOVES, REFERENCE, effective_speed, knowledge, name
from .contracts import require_evidence

AUDITED_MOVES = MOVES | {'Fake Out', 'Grassy Glide', 'Giga Drain', 'Draining Kiss'}
PRIORITY_ABILITIES = {'Prankster', 'Gale Wings', 'Triage'}
# These have no Speed or queue-order effect in the pinned reference subset.
NEUTRAL_ABILITIES = PRIORITY_ABILITIES | {
    'Stall', 'Infiltrator', 'Tough Claws', 'Drought', 'Solar Power',
    'Static', 'Lightning Rod', 'Thick Fat', 'Drizzle', 'Sand Stream', 'Snow Warning',
}
HEAL_MOVES = {'Recover', 'Roost', 'Giga Drain', 'Draining Kiss'}
UNAVAILABLE_ITEMS = {'Custap Berry', 'Lagging Tail', 'Full Incense'}


@lru_cache(maxsize=1)
def ordering_coverage():
    return json.loads((Path(__file__).parent / 'data/ordering-coverage-v1.json').read_text())


class IncompatibleEvidence(ValueError):
    """Supported mechanics disagree with a supplied constraint, not a rules gap."""


@lru_cache(maxsize=1)
def _sources():
    return json.loads((Path(__file__).parent / 'data/sources-v2.json').read_text())


def sources():
    return deepcopy(_sources())


@lru_cache(maxsize=1)
def mega_stones():
    return {r.get('required_item') for r in knowledge().facts['pokemon'].values()
            if r.get('required_item') and r.get('upstream_name', '').startswith('Mega ')}


@lru_cache(maxsize=512)
def move_fact(move):
    label = name(move, 'move')
    if ordering_coverage()['moves'].get(label, {}).get('priority_conflict'):
        raise ValueError('Conflicting Champions catalog/reference priority: ' + label)
    if label not in AUDITED_MOVES and not ordering_coverage()['moves'].get(label, {}).get('supported'):
        raise ValueError('Unaudited or special move: ' + label)
    kb = knowledge()
    row = next(e for e in kb.by_kind['move'] if e.names.get('en') == label)
    fact = kb.facts['moves'].get(row.canonical_id, {})
    if type(fact.get('priority')) is not int:
        raise ValueError('No Champions catalog priority')
    return label, row.canonical_id, fact


def effective_priority(action, participant, field):
    label, canonical, fact = move_fact(action['move'])
    ability = name(participant['ability'], 'ability')
    active = participant['ability_active']
    if type(active) is not bool:
        raise ValueError('Explicit ability suppression/activation required')
    value = fact['priority']; modifiers = []
    if active and ability == 'Prankster' and fact['category'] == 'Status':
        value += 1; modifiers.append('Prankster')
    if active and ability == 'Gale Wings' and fact['type'] == 'Flying':
        if type(participant.get('hp_full')) is not bool:
            raise ValueError('Gale Wings full HP unresolved')
        if participant['hp_full']:
            value += 1; modifiers.append('Gale Wings')
    if active and ability == 'Triage' and (label in HEAL_MOVES or
            'heal' in ordering_coverage()['moves'].get(label, {}).get('flags', [])):
        value += 3; modifiers.append('Triage')
    if label == 'Grassy Glide' and field['terrain'] == 'grassy':
        if type(participant.get('grounded')) is not bool:
            raise ValueError('Grassy Glide grounded state unresolved')
        if participant['grounded']:
            value += 1; modifiers.append('Grassy Glide')
    supplied = action.get('effective_priorities')
    if supplied is not None and value not in supplied:
        raise IncompatibleEvidence('Priority evidence conflicts with configuration')
    return dict(move=canonical, base=fact['priority'], effective=value, modifiers=modifiers)


def override_options(action, participant):
    """Activation is a persistent action-level choice, with no probability."""
    item = name(participant['item'], 'item')
    ability = name(participant['ability'], 'ability')
    if action['kind'] in {'voluntary_switch', 'mega_evolution'}:
        return [0]  # Move-order items and Stall do not order these phases.
    if item in UNAVAILABLE_ITEMS:
        raise ValueError('Item not current in pinned Champions reference: ' + item)
    activation = action['activation']
    if set(activation) != {'state', 'coverage_complete', 'evidence'}:
        raise ValueError('Explicit activation evidence required')
    require_evidence(activation['evidence'])
    if type(activation['coverage_complete']) is not bool:
        raise ValueError('Explicit activation coverage required')
    state = activation['state']
    if state not in {'activated', 'not_activated', 'unknown'}:
        raise ValueError('Unknown activation state')
    if state == 'not_activated' and not activation['coverage_complete']:
        raise ValueError('Nonactivation requires complete observation coverage')
    if item != 'Quick Claw':
        if state == 'activated':
            return []  # Confirmed activation excludes incompatible item hypothesis.
        return [-1 if ability == 'Stall' and participant['ability_active'] else 0]
    if ability == 'Stall' and participant['ability_active']:
        raise ValueError('Combined Stall and Quick Claw interaction unsupported')
    return [1] if state == 'activated' else [0] if state == 'not_activated' else [0, 1]


def action_metrics(action, participant, field, activation_rank, profile):
    if profile != REFERENCE:
        raise ValueError('Numerical ordering requires provisional reference profile')
    phase = {'voluntary_switch': 2, 'mega_evolution': 1, 'move': 0}[action['kind']]
    priority = (effective_priority(action, participant, field) if phase == 0 else
                dict(move=None, base=None, effective=0, modifiers=[], phase=action['kind']))
    p = {key: deepcopy(participant[key]) for key in ACTOR_KEYS}
    ability = name(p['ability'], 'ability'); item = name(p['item'], 'item')
    rank = activation_rank
    if ability in NEUTRAL_ABILITIES or ability in ordering_coverage()['neutral_abilities']:
        p['ability'] = 'none'  # Its priority/order handler was evaluated separately.
    # Canonical catalog-required Mega stones and Focus Sash are Speed-neutral.
    fact = knowledge().facts['pokemon'].get(participant['_current_form'], {})
    stone = fact.get('required_item')
    if item == 'Quick Claw' or item == 'Focus Sash' or item == stone or item in mega_stones():
        p['item'] = 'none'
    result = effective_speed(actual_speed=p['actual_speed'], participant=p, field=field, profile=profile)
    if result['status'] != 'exact_reference':
        raise ValueError('; '.join(result['diagnostics']))
    speed = result['effective_speed']
    return dict(priority=priority, override=rank, speed=result,
                key=(phase, priority['effective'], rank, -speed if field['trick_room'] else speed))
