"""Configuration-correlated deterministic inference over v2 action evidence."""
from copy import deepcopy
from .contracts import OrderObservation, HiddenConfiguration, require_evidence
from .core import identity_key, integer, name, knowledge, REFERENCE
from .dynamic import simulate_action_order, PARTICIPANT_CHANGES, FIELD_CHANGES
from .mechanics import sources
from .solver import domain
from knowledge.stat_feasibility import summary


def infer_action_speed(*, observations: list[OrderObservation], configurations: list[HiddenConfiguration],
                       profile='champions-evidence-only-v1', max_evaluations=100000,
                       max_branches=4096):
    """Intersect whole observations per shared configuration, then union supports.

    Inputs explicitly describe a complete finite configuration universe. No
    probability or point in an interval is invented. Per-observation alternatives
    are finite temporal states; persistent subject state flows between turns.
    """
    result = dict(schema_version=2, status='unresolved', feasible=None, compatible_configurations=None,
                  remaining_abilities=None, remaining_items=None, tie_compatible=None,
                  per_form=None, observations=[], exclusions=[], conflict=None, diagnostics=[],
                  work=dict(evaluations=0, nodes=0), provenance=sources())
    try:
        integer(max_evaluations, 1, 1000000); integer(max_branches, 1, 100000)
        if profile != REFERENCE:
            raise ValueError('Numerical inference requires provisional reference profile')
        if not isinstance(observations, list) or not observations or len(observations) > 128:
            raise ValueError('Supply 1..128 observations')
        if not isinstance(configurations, list) or not configurations or len(configurations) > 100000:
            raise ValueError('Explicit finite nonempty configuration universe required')
        ids = set(); binding = set()
        for obs in observations:
            require_evidence(obs['evidence'])
            required = {'id','battle_id','decision_id','subject','state','actions','sequence',
                        'initial_changes','alternatives','strict_speed','evidence'}
            if set(obs) != required or not isinstance(obs['alternatives'], list) or len(obs['alternatives']) > 128:
                raise ValueError('Invalid v2 observation contract')
            action_ids = {a['id'] for a in obs['actions']}
            for pair in obs['strict_speed']:
                if (not isinstance(pair, list) or len(pair) != 2 or pair[0] == pair[1]
                        or set(pair) - action_ids):
                    raise ValueError('Invalid certified strict effective-Speed pair')
            if (obs['id'] in ids or not all(isinstance(obs[k], str) and obs[k]
                    for k in ('id', 'battle_id', 'decision_id', 'subject')) or not obs['sequence']):
                raise ValueError('Unique sourced observations, battle and decision IDs required')
            ids.add(obs['id']); binding.add((obs['battle_id'], obs['subject']))
        if len(binding) != 1:
            raise ValueError('Cannot combine different battles or individuals')
        configurations = deepcopy(configurations)
        config_ids = set()
        for config in configurations:
            if not isinstance(config['id'], str) or not config['id'] or config['id'] in config_ids:
                raise ValueError('Unique configuration IDs required')
            config_ids.add(config['id']); domain([config['speed']])
            config['ability'] = name(config['ability'], 'ability')
            config['item'] = name(config['item'], 'item')
        preflight = len(configurations) * sum(max(1, len(o['alternatives'])) for o in observations)
        if preflight > max_evaluations:
            raise ValueError('Evaluation limit exceeded; no configurations truncated')
        survivors = []; ties = []; by_form = {}; final_abilities = set(); final_items = set()
        applied = {o['id']:set() for o in observations}
        for config in configurations:
            # Persistent states branch only on explicit evidence, ties and finite
            # temporal alternatives. They are carried, never reselected per turn.
            histories = [(None, {}, False, {})]
            failed = []
            for obs in observations:
                next_histories = []
                for persistent, details, had_tie, forms in histories:
                    base = deepcopy(obs['state']); p = base['participants'][obs['subject']]
                    current_key = identity_key(p['identity'], p['form'])
                    if persistent is None:
                        native = knowledge().facts['pokemon'].get(current_key, {}).get('ability_names', [])
                        if config['ability'] not in native:
                            raise ValueError('Initial hidden ability is not native to current form; supply sourced replacement as a state change')
                        if config.get('form') is not None and config['form'] != current_key:
                            failed.append((obs['id'], 'Current form conflicts with configuration')); continue
                        fixed = dict(ability=config['ability'], item=config['item'], actual_speed=config['speed'])
                        persistent_input = config.get('persistent', {})
                        if set(persistent_input) - {'unburden_active','activation_evidence'}:
                            raise ValueError('Unsupported persistent activation history')
                        fixed.update(deepcopy(persistent_input))
                        if config.get('training') is not None:
                            fixed['training'] = deepcopy(config['training'])
                    else:
                        if persistent['_current_form'] != current_key:
                            failed.append((obs['id'], 'Form continuity requires an evidenced transformation')); continue
                        fixed = {k:deepcopy(persistent[k]) for k in ('ability','item','actual_speed','configuration_speed',
                                                                   'unburden_active','activation_evidence')}
                        if persistent.get('training') is not None:
                            fixed['training'] = deepcopy(persistent['training'])
                    # Non-null observation fields are evidence, not overwritten hypotheses.
                    if any(p.get(k) is not None and (name(p[k], k) if k in {'ability','item'} else p[k]) != v for k,v in fixed.items()
                           if k in {'ability','item','actual_speed','unburden_active'}):
                        failed.append((obs['id'], 'Known Speed/item/ability excludes configuration')); continue
                    p.update(fixed)
                    for alternative in obs['alternatives'] or [dict(id='specified', participants={}, field={})]:
                        state = deepcopy(base)
                        if set(alternative) != {'id','participants','field'}:
                            raise ValueError('Invalid per-action state alternative')
                        if set(alternative['field']) - FIELD_CHANGES:
                            raise ValueError('Unsupported field alternative')
                        state['field'].update(deepcopy(alternative['field']))
                        for iid, patch in alternative['participants'].items():
                            if set(patch) - (PARTICIPANT_CHANGES - {'item','ability'}):
                                raise ValueError('Persistent item/ability alternatives belong in configurations')
                            state['participants'][iid].update(deepcopy(patch))
                        result['work']['evaluations'] += 1
                        if result['work']['evaluations'] > max_evaluations:
                            raise ValueError('Evaluation limit exceeded; complete result withheld')
                        simulation = simulate_action_order(state=state, actions=obs['actions'],
                            observed_order=obs['sequence'], initial_changes=obs['initial_changes'],
                            profile=profile, max_branches=max_branches,
                            max_nodes=max(1, max_evaluations-result['work']['nodes']))
                        result['work']['nodes'] += simulation['work']['nodes']
                        if simulation['status'] == 'unresolved':
                            raise ValueError(f"{config['id']}/{obs['id']}: " + '; '.join(simulation['diagnostics']))
                        accepted = False
                        for trace in simulation['traces']:
                            comparisons = {}; strict_ok = True; tie = False; trace_forms = deepcopy(forms)
                            for step in trace['steps']:
                                for pair in obs['strict_speed']:
                                    if (not isinstance(pair, list) or len(pair) != 2 or pair[0] == pair[1]
                                            or set(pair) - {a['id'] for a in obs['actions']}):
                                        raise ValueError('Invalid certified strict effective-Speed pair')
                                    key = tuple(pair)
                                    if key not in comparisons and all(a in step['metrics'] for a in pair):
                                        comparisons[key] = True
                                        strict_ok &= step['metrics'][pair[0]]['speed']['effective_speed'] > step['metrics'][pair[1]]['speed']['effective_speed']
                                subject_actions = {a['id'] for a in obs['actions'] if a['individual']==obs['subject']}
                                tie |= bool(subject_actions & set(step['tied_actions']))
                                subject = step['before']['participants'][obs['subject']]
                                trace_forms.setdefault(subject['_current_form'], set()).add(subject['actual_speed'])
                            if len(comparisons) != len({tuple(p) for p in obs['strict_speed']}):
                                raise ValueError('Certified strict pair lacks a simultaneous pending decision')
                            if not strict_ok:
                                continue
                            final = trace['final_state']['participants'][obs['subject']]
                            trace_forms.setdefault(final['_current_form'], set()).add(final['actual_speed'])
                            info = dict(alternative=alternative['id'], sequence=trace['sequence'],
                                        activation_assignments=trace['activations'], tie_possible=tie,
                                        decisions=[dict(index=s['decision_index'], action_id=s['action_id'],
                                                        metrics=s['metrics']) for s in trace['steps']])
                            next_histories.append((deepcopy(final), dict(details, **{obs['id']:info}), had_tie or tie, trace_forms))
                            accepted = True; applied[obs['id']].add(config['id'])
                        if not accepted:
                            failed.append((obs['id'], 'No pending-action sequence satisfies order/strict-Speed evidence'))
                if len(next_histories) > max_branches:
                    raise ValueError('Cross-observation branch limit exceeded; complete result withheld')
                histories = next_histories
                if not histories:
                    break
            if histories:
                survivors.append(dict(configuration=deepcopy(config), histories=[h[1] for h in histories]))
                if any(h[2] for h in histories):
                    ties.append(config['id'])
                for persistent, _, _, forms in histories:
                    final_abilities.add(persistent['ability']); final_items.add(persistent['item'])
                    for key, values in forms.items():
                        by_form.setdefault(key, set()).update(values)
            else:
                result['exclusions'].append(dict(configuration_id=config['id'], observations=[
                    dict(id=oid, reason=reason) for oid,reason in sorted(set(failed))]))
        feasible = summary(c['configuration']['speed'] for c in survivors)
        survivor_ids = {c['configuration']['id'] for c in survivors}
        result.update(status='exact' if survivors else 'empty', feasible=feasible,
                      compatible_configurations=survivors, remaining_abilities=sorted({c['configuration']['ability'] for c in survivors}),
                      remaining_items=sorted({c['configuration']['item'] for c in survivors}),
                      current_abilities=sorted(final_abilities), current_items=sorted(final_items),
                      tie_compatible=ties, per_form={k:summary(v) for k,v in sorted(by_form.items())},
                      observations=[dict(id=o['id'], applied_configuration_ids=sorted(applied[o['id']]),
                                         compatible_configuration_ids=sorted(applied[o['id']] & survivor_ids),
                                         evidence=deepcopy(o['evidence'])) for o in observations])
        if not survivors:
            result['conflict'] = dict(observation_ids=[o['id'] for o in observations], minimal=False,
                                     reason='No shared configuration/history satisfies all supplied evidence; see exclusions.')
    except (ValueError, TypeError, KeyError, NotImplementedError) as exc:
        result.update(status='unresolved', diagnostics=[str(exc)])
    return result
