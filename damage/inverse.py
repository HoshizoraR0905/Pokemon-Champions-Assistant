"""Exact bounded inverse constraints over the existing forward engine.

No formula, priors, implicit build construction, video or network dependencies.
"""
from copy import deepcopy
from itertools import islice, product
import json
from math import prod

from .engine import calculate, stat_dependencies, PROFILES
from .data import Diagnostic, pokemon_data

DEFAULT_LIMITS = {'max_candidates': 4096, 'max_assignments': 128, 'max_evaluations': 100000,
                  'max_conflict_checks': 128}


class InputError(ValueError):
    pass


def _require(condition, reason):
    if not condition:
        raise InputError(reason)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _keys(value, required, optional=()):
    _require(isinstance(value, dict), 'Expected object')
    _require(set(required) <= set(value) <= set(required) | set(optional),
             'Missing or unrecognized fields: ' + ', '.join(required))


def _int(value, low=0, high=65535):
    _require(type(value) is int and low <= value <= high, f'Expected integer in [{low}, {high}]')
    return value


def _domain(values, limit):
    try:
        rows = list(islice(iter(values), limit + 1))
    except TypeError as exc:
        raise InputError('Explicit finite candidate_stats domain required') from exc
    _require(0 < len(rows) <= limit, 'Empty candidate domain or max_candidates exceeded')
    for value in rows:
        _int(value, 1)
    return sorted(set(rows))


def _constraint(value):
    if type(value) is int:
        _int(value)
        return {'minimum': value, 'maximum': value}
    _require(isinstance(value, dict), 'Damage requires an exact integer, range or allowed_values')
    if set(value) == {'minimum', 'maximum'}:
        _int(value['minimum']); _int(value['maximum'])
        _require(value['minimum'] <= value['maximum'], 'Reversed damage range')
        return dict(value)
    _require(set(value) == {'allowed_values'} and isinstance(value['allowed_values'], list)
             and 0 < len(value['allowed_values']) <= 65536, 'Invalid allowed damage values')
    for v in value['allowed_values']:
        _int(v)
    return {'allowed_values': sorted(set(value['allowed_values']))}


def _matches(value, constraint):
    return value in constraint['allowed_values'] if 'allowed_values' in constraint else constraint['minimum'] <= value <= constraint['maximum']


def _set_summary(values):
    values = sorted(values)
    intervals = []
    for v in values:
        if intervals and v == intervals[-1][1] + 1:
            intervals[-1][1] = v
        else:
            intervals.append([v, v])
    return dict(values=values, minimum=values[0] if values else None,
                maximum=values[-1] if values else None, count=len(values),
                hull=[values[0], values[-1]] if values else None,
                has_gaps=len(intervals) > 1, intervals=intervals)


def _patch(request, path, value):
    parts = path.split('.')
    current = request
    for part in parts[:-1]:
        _require(isinstance(current, dict) and part in current, 'Scenario path does not exist: ' + path)
        current = current[part]
    _require(isinstance(current, dict) and parts[-1] in current, 'Scenario path does not exist: ' + path)
    current[parts[-1]] = deepcopy(value)


def _variables(variables, ids, stat, limits, observations):
    _require(isinstance(variables, list), 'variables must be an explicit finite list')
    dimensions = []; seen = set(); occupied = set()
    for variable in variables:
        _keys(variable, ('id','scope','observation_ids','path','values'))
        name, scope, targets, path, values = (variable[k] for k in ('id','scope','observation_ids','path','values'))
        _require(_text(name) and name not in seen, 'Unique variable IDs required'); seen.add(name)
        _require(scope in ('shared','observation'), 'Variable scope must be shared or observation')
        _require(isinstance(targets,list) and targets and all(_text(t) and t in ids for t in targets)
                 and len(set(targets)) == len(targets), 'Invalid variable observation_ids')
        _require(_text(path), 'Scenario path required')
        # Only leaf context fields may vary. Instance/form/level/stat basis stay fixed.
        parts = path.split('.')
        _require(len(parts) in (2,3) and parts[0] in ('attacker','defender','field'), 'Invalid scenario path')
        _require((len(parts) == 3 and parts[1] in ('stats','stages')) or
                 (len(parts) == 2 and parts[1] not in ('stats','stages')), 'Use leaf scenario paths')
        _require(path not in {'attacker.identity','attacker.form','attacker.level','attacker.stat_basis',
                             'attacker.stats.' + stat}, 'Scenario cannot redefine the inferred stat subject')
        _require(isinstance(values,list) and 0 < len(values) <= limits['max_assignments'], 'Finite variable values required')
        encoded = [json.dumps(v,sort_keys=True,allow_nan=False) for v in values]
        _require(len(set(encoded)) == len(values), 'Duplicate variable alternatives')
        for target in targets:
            _require((target,path) not in occupied, 'Overlapping scenario variables'); occupied.add((target,path))
            _patch(deepcopy(observations[ids.index(target)]['input']),path,values[0])
        if scope == 'shared':
            dimensions.append((name, targets, path, values))
        else:
            dimensions.extend((name + ':' + target, [target], path, values) for target in targets)
    _require(len({d[0] for d in dimensions}) == len(dimensions), 'Expanded variable IDs collide')
    _require(prod(len(d[3]) for d in dimensions) <= limits['max_assignments'], 'max_assignments exceeded')
    return dimensions


def infer_attack_stat(*, observations, candidate_stats, stat='attack', ruleset='champions-evidence-only-v1',
                      variables=None, continuity=None, limits=None, domain_provenance=None):
    """Enumerate exact feasible unmodified Attack/Special Attack integers.

    Each observation explicitly labels justified direct damage and an immutable
    stat_epoch. Finite variables have shared or independently per-observation scope.
    All branches must be supported to publish a complete feasible set.
    """
    output = dict(schema_version=1, status='insufficient_information', stat=stat if isinstance(stat,str) else None,
                  ruleset=ruleset if isinstance(ruleset,str) else None, attacker=None, candidate_domain=[],
                  feasible=None, scenarios=[], per_observation=[], inconsistency=None,
                  unconstrained=None, diagnostics=[], provenance={},
                  assumptions=['Exact feasibility conditional on the supplied finite domain, direct-damage evidence, identity continuity and complete modeled context.',
                               'No prior probabilities; interval hull is only a summary of the exact integer set.',
                               'Underlying stat is constant within the explicitly supplied stat epoch; stages remain observation-specific.'],
                  work={'forward_evaluations':0,'memo_hits':0,'assignments':0})
    try:
        _require(stat in ('attack','special_attack'), 'Infer attack or special_attack separately')
        _require(isinstance(ruleset,str) and ruleset in PROFILES, 'Explicit supported ruleset required')
        settings = dict(DEFAULT_LIMITS)
        if limits is not None:
            _keys(limits, (), DEFAULT_LIMITS)
            for k,v in limits.items():
                settings[k] = _int(v,1,1000000)
        domain = _domain(candidate_stats, settings['max_candidates']); output['candidate_domain'] = domain
        output['assumptions'].append('attacker.stats.' + stat + ' is the designated unknown: each candidate replaces its template entry; that entry is not an additional observed constraint.')
        _require(isinstance(observations,list) and observations, 'At least one observation required')
        _require(len(observations) <= settings['max_evaluations'], 'Observation work limit exceeded')
        json.dumps([observations,variables,continuity,domain_provenance],allow_nan=False)
        output['provenance'] = dict(observations=deepcopy(observations),variables=deepcopy(variables or []),
                                    domain=deepcopy(domain_provenance))
        ids = []; subjects = []; constraints = []
        canonical = []
        for obs in observations:
            _keys(obs, ('id','battle_id','attacker_instance_id','target_instance_id','stat_epoch',
                        'damage','damage_kind','evidence','input'))
            _require(all(_text(obs[k]) for k in ('id','battle_id','attacker_instance_id','target_instance_id','stat_epoch','evidence')),
                     'Stable identities, stat_epoch and evidence justification required')
            _require(obs['damage_kind'] == 'direct_move_damage', 'HP change is not automatically direct move damage; justify attribution and censoring explicitly')
            _require(obs['id'] not in ids, 'Duplicate observation ID'); ids.append(obs['id'])
            _require(isinstance(obs['input'],dict) and obs['input'].get('profile') == ruleset, 'Observation profile must match ruleset')
            # Damage identities use the shared canonical name/form resolver.
            ref,_ = pokemon_data(obs['input'].get('attacker',{}),'attacker')
            canonical.append((ref['canonical_id'],obs['input']['attacker'].get('level')))
            subjects.append((obs['battle_id'],obs['attacker_instance_id'],obs['stat_epoch']))
            constraints.append(_constraint(obs['damage']))
        if continuity is not None:
            _keys(continuity, ('subject_id','observation_ids','evidence','unchanged_stat'))
            _require(_text(continuity['subject_id']) and _text(continuity['evidence']) and continuity['unchanged_stat'] is True,
                     'Continuity must explicitly evidence one unchanged underlying stat')
            _require(isinstance(continuity['observation_ids'],list) and len(continuity['observation_ids']) == len(ids)
                     and set(continuity['observation_ids']) == set(ids), 'Continuity must cover exactly all observations')
        _require((len(set(subjects)) == 1 and len(set(canonical)) == 1) or continuity is not None,
                 'Different instances, forms, levels or stat epochs require explicit evidenced continuity of the unchanged stat')
        output['attacker'] = dict(instances=[dict(battle_id=s[0],instance_id=s[1],stat_epoch=s[2]) for s in sorted(set(subjects))],
                                  identities=sorted({c[0] for c in canonical}), continuity=deepcopy(continuity))
        dimensions = _variables([] if variables is None else variables, ids, stat, settings, observations)
        assignments = prod(len(d[3]) for d in dimensions)
        _require(assignments * len(domain) * len(ids) <= settings['max_evaluations'], 'max_evaluations exceeded; narrow explicit domains')
        output['work']['assignments'] = assignments
        memo = {}; scenario_sets = []; individual = [set() for _ in ids]; dependencies = [set() for _ in ids]
        all_provenance = {}; forward_assumptions = set()
        for index, choices in enumerate(product(*(d[3] for d in dimensions))):
            inputs = [deepcopy(obs['input']) for obs in observations]
            assignment = {}
            for (name, targets, path, _), value in zip(dimensions, choices):
                assignment[name] = value
                for target in targets:
                    _patch(inputs[ids.index(target)], path, value)
            rows = []; sets = []
            for i,(obs,request,constraint) in enumerate(zip(observations,inputs,constraints)):
                compatible = []; values = set(); dependency_rows = {}
                for candidate in domain:
                    request['attacker'].setdefault('stats',{})[stat] = candidate
                    key = json.dumps(request,sort_keys=True,separators=(',',':'),allow_nan=False)
                    if key not in memo:
                        result = calculate(request); output['work']['forward_evaluations'] += 1
                        if result['status'] != 'exact_reference':
                            output['status'] = 'unsupported' if result['status'] == 'unsupported' else 'insufficient_information'
                            output['diagnostics'].append(dict(observation_id=obs['id'],assignment=assignment,candidate=candidate,
                                forward_status=result['status'],unresolved_inputs=result['unresolved_inputs'],unsupported_mechanics=result['unsupported_mechanics']))
                            output['provenance']['forward'] = result['provenance']
                            return output
                        dep = stat_dependencies(result)
                        _require(dep is not None, 'Forward handler has no published stat dependencies')
                        memo[key] = (result['distribution']['rolls'],dep)
                        if not all_provenance:
                            all_provenance = result['provenance']
                        forward_assumptions.update(result['assumptions'])
                    else:
                        output['work']['memo_hits'] += 1
                    rolls, dep = memo[key]
                    dependency_rows[json.dumps(dep,sort_keys=True)] = dep
                    dependencies[i].add(stat in dep['attacker'])
                    matching = sorted({r for r in rolls if _matches(r,constraint)})
                    if matching:
                        values.add(candidate)
                        compatible.append(dict(candidate=candidate,compatible_rolls=matching,supported_rolls=list(rolls)))
                individual[i].update(values); sets.append(values)
                rows.append(dict(id=obs['id'],constraint=constraint,evidence=obs['evidence'],
                                 feasible=_set_summary(values),compatibility=compatible,
                                 dependencies=list(dependency_rows.values()),
                                 informative_dependency=any(stat in d['attacker'] for d in dependency_rows.values())))
            joint = set.intersection(*sets)
            scenario_sets.append(sets)
            output['scenarios'].append(dict(id=str(index),assignment=assignment,feasible=_set_summary(joint),per_observation=rows))
        feasible = set().union(*(set(s['feasible']['values']) for s in output['scenarios']))
        output['feasible'] = _set_summary(feasible)
        output['unconstrained'] = feasible == set(domain)
        output['status'] = 'empty' if not feasible else 'conditional' if dimensions else 'exact'
        output['per_observation'] = [dict(id=oid,feasible=_set_summary(values),
            informative_dependency=True in deps, dependency_varies_by_scenario=len(deps)>1,
            individually_feasible=bool(values)) for oid,values,deps in zip(ids,individual,dependencies)]
        output['provenance'] = dict(forward=all_provenance,mechanics_verification='provisional community reference; not official Champions-exact',
                                   domain=deepcopy(domain_provenance),observations=deepcopy(observations),variables=deepcopy(variables or []))
        output['assumptions'].extend(sorted(forward_assumptions))
        if not feasible:
            # Deletion-minimal conflict in the joint (assignment, candidate) model.
            # O(n^2 * assignments) set operations; no new forward evaluations.
            core = list(range(len(ids)))
            def inconsistent(indices):
                return not any(set.intersection(*(s[i] for i in indices)) if indices else set(domain) for s in scenario_sets)
            checks = 0
            for i in list(core):
                if checks >= settings['max_conflict_checks']:
                    break
                trial = [j for j in core if j != i]
                checks += 1
                if inconsistent(trial): core = trial
            output['inconsistency'] = dict(conflicting_observation_ids=[ids[i] for i in core],
                subset_kind='deletion-minimal' if checks == len(ids) else 'explanatory conflict; minimization work limit reached',
                subset_scope='under supplied shared/local assignments; not necessarily minimum cardinality',
                individually_feasible={oid:bool(v) for oid,v in zip(ids,individual)},
                review=['Underlying stat may have changed: verify stat_epoch and continuity evidence.',
                        'Check instance identity, direct-damage attribution, KO censoring, residual damage/recovery and explicit finite mechanics alternatives.',
                        'No observation was dropped and no domain or damage constraint was widened.'])
        return output
    except (InputError, Diagnostic, TypeError, ValueError, KeyError) as exc:
        if isinstance(exc, Diagnostic) and exc.status == 'unsupported':
            output['status'] = 'unsupported'
        output['diagnostics'].append(dict(reason=str(exc),input_status=getattr(exc,'status','invalid_or_missing_input')))
        return output
