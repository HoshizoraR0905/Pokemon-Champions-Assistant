"""Bounded exhaustive pending-action evaluation under the M3.2.1 contract.

No turn detection, recognition, random tie winner, or activation probability.
Effects are supplied evidence, not inferred move effects (avoids double use).
"""
from copy import deepcopy
from itertools import product
from .contracts import Evidence, PendingAction, StateChange, require_evidence
from .core import ACTOR_KEYS, actor, identity_key, integer, REFERENCE, knowledge, name
from .forms import training_stats, transform
from .mechanics import IncompatibleEvidence, action_metrics, override_options, sources

VERSION = 'dynamic-action-order-v2'
PARTICIPANT_CHANGES = {'stage', 'tailwind', 'status', 'ability', 'ability_active', 'item',
                       'unburden_active', 'activation_evidence', 'hp_full', 'grounded'}
FIELD_CHANGES = {'weather', 'terrain', 'trick_room'}


def prepare_state(state):
    result = deepcopy(state)
    if set(result) != {'participants', 'field'} or not result['participants']:
        raise ValueError('Explicit participants and field required')
    field = result['field']
    if (set(field) != {'weather','terrain','trick_room','other_effects'}
            or field['weather'] not in {'none','sun','rain','sand','snow'}
            or field['terrain'] not in {'none','electric','grassy','psychic','misty'}
            or type(field['trick_room']) is not bool or field['other_effects'] != []):
        raise ValueError('Unknown or unsupported field/order effects')
    for iid, p in result['participants'].items():
        if set(p) - (ACTOR_KEYS | {'training','hp_full','grounded','_current_form',
                                   'configuration_speed','form_stat_domains'}):
            raise ValueError('Unsupported participant state fields')
        if iid != p['instance_id']:
            raise ValueError('Participant key must equal stable individual ID')
        actor({k: p[k] for k in (
            'identity', 'form', 'instance_id', 'actual_speed', 'stage', 'tailwind', 'ability',
            'ability_active', 'item', 'status', 'unburden_active', 'activation_evidence', 'other_effects')})
        integer(p['actual_speed'], 1, 4095)
        p['ability'] = name(p['ability'], 'ability'); p['item'] = name(p['item'], 'item')
        p['_current_form'] = identity_key(p['identity'], p['form'])
        required = knowledge().facts['pokemon'].get(p['_current_form'], {}).get('required_item')
        if required and name(p['item'], 'item') != required:
            raise ValueError('Current form requires its compatible held item')
        p.setdefault('configuration_speed', p['actual_speed'])
        if p.get('training') is not None:
            stats = training_stats(p['_current_form'], p['training'])
            if stats['speed'] != [p['actual_speed']]:
                raise ValueError('Supplied Speed conflicts with training/current form')
            p['form_stat_domains'] = stats
    return result


def apply_changes(state, pending, changes: list[StateChange], max_variants=4096):
    """Return all compatible branches. No branch is discarded for missing mechanics."""
    if not isinstance(changes, list) or len(changes) > 128:
        raise ValueError('Supply at most 128 explicit state changes')
    variants = [(deepcopy(state), list(pending), [])]
    for change in changes:
        if set(change) != {'kind', 'target', 'values', 'evidence'}:
            raise ValueError('Invalid state-change contract')
        require_evidence(change['evidence'])
        next_variants = []
        for s, queue, receipts in variants:
            kind, target, values = change['kind'], change['target'], change['values']
            if kind == 'cancel':
                if values or target not in queue:
                    raise ValueError('Cancellation must reference a pending action')
                next_variants.append((s, [a for a in queue if a != target], receipts + [deepcopy(change)]))
            elif kind == 'set':
                allowed = FIELD_CHANGES if target == 'field' else PARTICIPANT_CHANGES
                if not isinstance(values, dict) or not values or set(values) - allowed:
                    raise ValueError('Unsupported state update')
                obj = s['field'] if target == 'field' else s['participants'][target]
                if values.get('item') == 'Quick Claw' and obj.get('item') != 'Quick Claw':
                    raise ValueError('Mid-queue Quick Claw acquisition unresolved')
                obj.update(deepcopy(values))
                next_variants.append((prepare_state(s), queue, receipts + [deepcopy(change)]))
            elif kind == 'transform':
                if (set(values) != {'forms'} or not isinstance(values['forms'], list)
                        or not 1 <= len(values['forms']) <= 128 or len(set(values['forms'])) != len(values['forms'])):
                    raise ValueError('Explicit finite Mega form alternatives required')
                for form in values['forms']:
                    changed = transform(s['participants'][target], form)
                    if changed is None:
                        continue
                    branch = deepcopy(s); branch['participants'][target] = changed
                    # Only this closed set of automatic weather starts is modeled.
                    weather = {'Drought': 'sun', 'Drizzle': 'rain', 'Sand Stream': 'sand', 'Snow Warning': 'snow'}
                    if changed['ability_active'] and changed['ability'] in weather:
                        branch['field']['weather'] = weather[changed['ability']]
                    next_variants.append((branch, queue, receipts + [dict(deepcopy(change), selected_form=form)]))
                    if len(next_variants) > max_variants:
                        raise ValueError('State-change branch limit exceeded')
            else:
                raise ValueError('Forced/interrupted/unresolved change requires a dedicated handler')
        variants = next_variants
    return variants


def simulate_action_order(*, state, actions: list[PendingAction], observed_order=None,
                          initial_changes=None, profile='champions-evidence-only-v1',
                          max_branches=4096, max_nodes=100000):
    """Evaluate an explicitly supplied decision's pending set, including tie branches.

    An observed prefix prunes incompatible choices only after computing each
    decision's full metrics. On any unsupported branch the complete result is
    null, even if another branch succeeded. Limits return no partial feasible set.
    """
    result = dict(schema_version=2, version=VERSION, status='unresolved', traces=None,
                  diagnostics=[], work=dict(nodes=0, completed_branches=0), provenance=sources())
    try:
        integer(max_branches, 1, 100000); integer(max_nodes, 1, 1000000)
        if profile != REFERENCE:
            raise ValueError('Numerical ordering requires provisional reference profile')
        prepared = prepare_state(state)
        if not isinstance(actions, list) or not 1 <= len(actions) <= 16:
            raise ValueError('Supply 1..16 pending actions')
        by_id = {}; individuals = set()
        for action in actions:
            required = {'id','individual','kind','move','outcome','activation','changes','evidence'}
            if not required <= set(action) <= required | {'effective_priorities', 'selection_evidence', 'timing_evidence'}:
                raise ValueError('Invalid pending-action contract')
            require_evidence(action['evidence'])
            if action['kind'] not in {'move', 'voluntary_switch', 'mega_evolution'} or action['individual'] not in prepared['participants']:
                raise ValueError('Interrupted/skipped/forced actions do not establish ordinary order')
            if action['outcome'] == 'flinched' and action['kind'] == 'move':
                require_evidence(action.get('selection_evidence'))
                require_evidence(action.get('timing_evidence'))
                if not action['move'] or action['changes']:
                    raise ValueError('Flinch needs an intended move and cannot execute move effects')
            elif action['outcome'] != 'completed':
                raise ValueError('Unaudited prevention timing; no ordering deduction')
            if action['kind'] != 'move' and action['move'] is not None:
                raise ValueError('Switch/Mega is a distinct phase without a move')
            if (not isinstance(action['id'], str) or not action['id'] or action['id'] in by_id
                    or (action['individual'], action['kind']) in individuals):
                raise ValueError('Unique actions and one action per individual per phase required')
            if not isinstance(action['changes'], list):
                raise ValueError('Explicit post-action changes required')
            if 'effective_priorities' in action:
                values = action['effective_priorities']
                if not isinstance(values, list) or not values:
                    raise ValueError('Finite effective-priority alternatives required')
                for value in values:
                    integer(value, -7, 7)
            by_id[action['id']] = action; individuals.add((action['individual'], action['kind']))
        for iid, kind in individuals:
            if kind == 'voluntary_switch' and any(actor == iid and phase != kind for actor,phase in individuals):
                raise ValueError('A selected voluntary switch replaces that individual\'s Mega/move action')
        order = observed_order
        if order is not None and (not isinstance(order, list) or len(set(order)) != len(order)
                                  or set(order) - set(by_id)):
            raise ValueError('Observed order must be a unique pending-action prefix')
        traces = []

        def spend():
            result['work']['nodes'] += 1
            if result['work']['nodes'] > max_nodes:
                raise ValueError('Node limit exceeded; complete result withheld')

        def visit(s, pending, history, initial_receipts, activations):
            spend()
            if not pending:
                sequence = [r['action_id'] for r in history]
                if order is not None and sequence[:len(order)] != order:
                    return
                if len(traces) >= max_branches:
                    raise ValueError('Branch limit exceeded; complete result withheld')
                traces.append(dict(sequence=sequence, steps=history, final_state=deepcopy(s),
                                   initial_changes=initial_receipts, activations=dict(activations)))
                return
            try:
                metrics = {aid: action_metrics(by_id[aid], s['participants'][by_id[aid]['individual']],
                                               s['field'], activations[aid], profile) for aid in pending}
            except IncompatibleEvidence:
                return
            best = max(m['key'] for m in metrics.values())
            choices = [aid for aid in pending if metrics[aid]['key'] == best]
            for aid in choices:
                if order is not None and len(history) < len(order) and order[len(history)] != aid:
                    continue
                remaining = [a for a in pending if a != aid]
                for after, queue, changes in apply_changes(s, remaining, by_id[aid]['changes'], max_branches):
                    row = dict(action_id=aid, decision_index=len(history), pending_before=list(pending),
                               before=deepcopy(s), after=deepcopy(after), metrics=deepcopy(metrics),
                               tied_actions=choices if len(choices) > 1 else [], changes=changes)
                    visit(after, queue, history + [row], initial_receipts, activations)

        pending = list(by_id)
        for initial, queue, receipts in apply_changes(prepared, pending, initial_changes or [], max_branches):
            options = [override_options(by_id[aid], initial['participants'][by_id[aid]['individual']]) for aid in queue]
            # Bound the product before constructing all action-level activation assignments.
            count = 1
            for values in options:
                count *= len(values)
            if count > max_nodes:
                raise ValueError('Activation assignment limit exceeded')
            for choices in product(*options):
                visit(initial, queue, [], receipts, dict(zip(queue, choices)))
        result.update(status='exact' if traces else 'empty', traces=traces)
        result['work']['completed_branches'] = len(traces)
    except (ValueError, TypeError, KeyError, NotImplementedError) as exc:
        result.update(status='unresolved', traces=None, diagnostics=[str(exc)])
    return result
