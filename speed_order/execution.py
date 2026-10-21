"""Opt-in execution-order adapter; Speed arithmetic stays in core.effective_speed.

The conditional model handles one pair per decision (selected by the caller),
including an explicitly modeled Quick Claw Bernoulli activation. No item prior
or activation is supplied for an unresolved item domain.
"""
from copy import deepcopy
from itertools import product
from .core import effective_speed, name, knowledge, REFERENCE

VERSION = 'execution-order-reference-v1'
NEUTRAL_SPEED_ABILITIES = {'Prankster', 'Gale Wings', 'Triage', 'Stall'}
SPECIAL_MOVES = {'After You', 'Quash', 'Instruct', 'Round', 'Focus Punch',
                 'Beak Blast', 'Shell Trap', 'Counter', 'Mirror Coat',
                 'Metal Burst', 'Grassy Glide', 'Pursuit', 'Me First',
                 'Electro Shot', 'Solar Beam', 'Solar Blade', 'Dig', 'Fly',
                 'Dive', 'Phantom Force', 'Sky Attack', 'Skull Bash', 'Bounce'}


def priority(move, participant, *, hp_full=None, healing_verified=False):
    """A single fully specified ability branch; unknown activation stays unknown."""
    kb = knowledge()
    move_name = name(move, 'move')
    ids = [e.canonical_id for e in kb.by_kind['move'] if e.names.get('en') == move_name]
    fact = kb.facts['moves'].get(ids[0], {}) if len(ids) == 1 else {}
    base = fact.get('priority')
    if type(base) is not int or move_name in SPECIAL_MOVES:
        raise ValueError('missing_priority_or_special_move_context')
    ability = name(participant['ability'], 'ability')
    active = participant['ability_active']
    if type(active) is not bool:
        raise ValueError('ability_activation_unknown')
    if active and ability == 'Prankster' and fact['category'] == 'Status':
        base += 1
    if active and ability == 'Gale Wings' and fact['type'] == 'Flying':
        if type(hp_full) is not bool:
            raise ValueError('Gale_Wings_full_HP_unknown')
        base += int(hp_full)
    if active and ability == 'Triage':
        if not healing_verified:
            raise ValueError('Triage_move_eligibility_unverified')
        base += 3
    return base


def pair_likelihood(context, opponent_speed, first, evidence, profile):
    """Return (probability, diagnostics); an unsupported branch rejects the update."""
    if profile != REFERENCE:
        return None, {'reason': 'conditional_reference_profile_required'}
    try:
        if evidence.get('version') != VERSION or not evidence.get('sources'):
            raise ValueError('execution_model_version_and_sources_required')
        timing = context['timing']
        if not context['comparable'] or timing['state_at'] != 'order_decision' or timing['modifier_changes']:
            raise ValueError('queue_timing_or_continuity_unverified')
        if context['ordering_effects']:
            raise ValueError('interacting_ordering_effects_unsupported')
        priorities = {}
        for role in ('own', 'opponent'):
            action = context['actions'][role]
            if action['kind'] != 'move':
                raise ValueError('special_or_prevented_action')
            priorities[role] = priority(action['move'], context[role],
                **evidence.get('priority_context', {}).get(role, {}))
            if priorities[role] != action['effective_priority']:
                raise ValueError('effective_priority_disagrees_with_branch')
        if priorities['own'] != priorities['opponent']:
            return None, {'reason': 'not_speed_informative_different_priority', 'priorities': priorities}
        speeds = {}; branches = {}
        for role in ('own', 'opponent'):
            actor = deepcopy(context[role]); ability = name(actor['ability'], 'ability')
            item = name(actor['item'], 'item')
            activation = evidence.get('quick_claw', {}).get(role, {})
            if activation.get('state') == 'confirmed_active' and activation.get('sources') and item != 'Quick Claw':
                return 0., {'reason': 'configuration_incompatible_with_observed_Quick_Claw_activation'}
            branches[role] = [(0, 1.)]
            if ability == 'Stall' and actor['ability_active']:
                branches[role] = [(-1, 1.)]
            if item == 'Quick Claw':
                if branches[role] != [(0, 1.)]:
                    raise ValueError('interacting_Stall_Quick_Claw_unsupported')
                if not activation.get('sources'):
                    raise ValueError('Quick_Claw_state_provenance_required')
                state = activation.get('state')
                if state == 'confirmed_active': branches[role] = [(1, 1.)]
                elif state == 'confirmed_inactive': branches[role] = [(0, 1.)]
                elif state == 'unknown': branches[role] = [(1, .2), (0, .8)]
                else: raise ValueError('Quick_Claw_activation_state_required')
                actor['item'] = 'none'  # Order override handled above; no Speed multiplier.
            if ability in NEUTRAL_SPEED_ABILITIES:
                actor['ability'] = 'none'  # Priority/order effects handled above.
            result = effective_speed(actual_speed=actor['actual_speed'] if role == 'own' else opponent_speed,
                                     participant=actor, field=context['field'], profile=profile)
            if result['status'] != 'exact_reference':
                raise ValueError('; '.join(result['diagnostics']))
            speeds[role] = result['effective_speed']
        a, b = speeds['own'], speeds['opponent']
        ordinary = .5 if a == b else float(first == ('own' if (a > b) != context['field']['trick_room'] else 'opponent'))
        probability = 0.
        for (own_rank, own_p), (opp_rank, opp_p) in product(branches['own'], branches['opponent']):
            chance = ordinary if own_rank == opp_rank else float(first == ('own' if own_rank > opp_rank else 'opponent'))
            probability += own_p * opp_p * chance
        return probability, dict(effective_speeds=speeds, priorities=priorities, activation_branches=branches)
    except (ValueError, TypeError, KeyError) as exc:
        return None, {'reason': str(exc)}
