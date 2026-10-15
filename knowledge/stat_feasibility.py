"""Exact Champions stat feasibility using the existing stat-construction utility.

Branches denote Cartesian point domains intersected with sum(points) <= 66;
they are complete constraints, not independent-build assertions or sampled builds.
"""
from copy import deepcopy
from .champions_stats import ChampionsStats, STATS, FACTORS, alignment_patterns, adjustment_factors, _domain


def summary(values):
    values=sorted(set(values));intervals=[]
    for v in values:
        if intervals and v==intervals[-1][1]+1: intervals[-1][1]=v
        else: intervals.append([v,v])
    return dict(values=values,minimum=values[0] if values else None,maximum=values[-1] if values else None,
                hull=[values[0],values[-1]] if values else None,count=len(values),has_gaps=len(intervals)>1,intervals=intervals)


def allowed(value, constraint):
    if type(constraint) is int: return value==constraint
    if 'allowed_values' in constraint: return value in constraint['allowed_values']
    return constraint['minimum'] <= value <= constraint['maximum']


def validate_constraint(constraint):
    def integer(v):
        if type(v) is not int or not 1<=v<=65535: raise ValueError('Actual stat constraints require integers 1..65535')
    if type(constraint) is int: integer(constraint);return
    if not isinstance(constraint,dict): raise ValueError('Explicit actual stat integer, range or set required')
    if set(constraint)=={'minimum','maximum'}:
        integer(constraint['minimum']);integer(constraint['maximum'])
        if constraint['minimum']>constraint['maximum']:raise ValueError('Reversed stat constraint')
    elif set(constraint)=={'allowed_values'} and isinstance(constraint['allowed_values'],list) and len(constraint['allowed_values'])<=65535:
        for v in constraint['allowed_values']:integer(v)
    else:raise ValueError('Invalid actual stat constraint')


def _mapping(value):
    if not isinstance(value,dict) or set(value)-set(STATS):raise ValueError('Expected mapping with canonical stat names')
    return value


def champions_attainable_stats(*, identity, stat, form=None, known_training_points=None,
                               point_domains=None, adjustments=None, alignments=None,
                               stat_constraints=None, retain_witnesses=True):
    """Exact selected-stat projection and full joint configuration constraints.

    Unspecified allocations/alignments enumerate every documented alternative.
    Explicit null values within constraints are invalid, never treated as neutral.
    """
    result=dict(schema_version=1,status='insufficient_information',identity=None,stat=stat if isinstance(stat,str) else None,
                attainable=None,joint_feasible=None,configurations=None,witnesses=[],diagnostics=[],provenance={})
    try:
        if stat not in STATS:raise ValueError('Unknown selected stat')
        if type(retain_witnesses) is not bool:raise ValueError('retain_witnesses must be boolean')
        model=ChampionsStats(identity,form=form);result['identity']=model.identity;result['provenance']=model.provenance
        points={s:list(range(33)) for s in STATS}
        if point_domains is not None:
            for s,v in _mapping(point_domains).items():points[s]=_domain(v,s)
        normalized_domains=deepcopy(points)
        if known_training_points is not None:
            for s,v in _mapping(known_training_points).items():
                if type(v) is not int or not 0<=v<=32:raise ValueError('Known training points must be integers 0..32')
                points[s]=[v] if v in points[s] else []
        patterns=alignment_patterns() if alignments is None else deepcopy(alignments)
        if not isinstance(patterns,list) or not 1<=len(patterns)<=21:raise ValueError('Supply 1..21 legal alignment alternatives')
        for p in patterns:adjustment_factors(p)
        # Deduplicate numerical patterns deterministically.
        import json
        patterns=list({json.dumps(p,sort_keys=True):p for p in patterns}.values())
        factors_known={}
        if adjustments is not None:
            for s,options in _mapping(adjustments).items():
                options=[options] if isinstance(options,str) else options
                if not isinstance(options,list) or not options or any(type(a) is not str or a not in FACTORS for a in options):
                    raise ValueError('Adjustment constraints require explicit 0.9/1.0/1.1 strings')
                if s=='hp' and set(options)!={'1.0'}:raise ValueError('HP has no non-neutral adjustment')
                factors_known[s]=options
        constraints={} if stat_constraints is None else deepcopy(_mapping(stat_constraints))
        for c in constraints.values():validate_constraint(c)
        marginal=set();joint=set();branches=[];witnesses={}
        for pattern in patterns:
            factors=adjustment_factors(pattern)
            if any(factors[s] not in values for s,values in factors_known.items()):continue
            if any(not points[s] for s in STATS):continue
            # Reuse authoritative calculation; never reconstruct its formula here.
            domains={s:model.attainable(s,adjustments=[factors[s]],point_domain=points[s])['configurations'] for s in STATS}
            if sum(min(r['training_points'] for r in domains[s]) for s in STATS)<=66:
                other_min=sum(min(r['training_points'] for r in domains[s]) for s in STATS if s!=stat)
                marginal.update(r['actual_stat'] for r in domains[stat] if r['training_points']+other_min<=66)
            filtered={s:[r for r in rows if s not in constraints or allowed(r['actual_stat'],constraints[s])] for s,rows in domains.items()}
            if any(not filtered[s] for s in STATS):continue
            minima={s:min(r['training_points'] for r in filtered[s]) for s in STATS}
            total=sum(minima.values())
            if total>66:continue
            # Remove values that have no completion, preserving the sum constraint.
            filtered={s:[r for r in rows if total-minima[s]+r['training_points']<=66] for s,rows in filtered.items()}
            branches.append(dict(alignment=pattern,adjustments=factors,stat_point_domains=filtered))
            for row in filtered[stat]:
                value=row['actual_stat'];joint.add(value)
                if retain_witnesses and value not in witnesses:
                    allocation=dict(minima);allocation[stat]=row['training_points']
                    built=model.calculate(allocation,pattern)
                    witnesses[value]=dict(value=value,training_points=allocation,alignment=pattern,stats=built['stats'])
        result.update(status='exact' if joint else 'empty',attainable=summary(marginal),joint_feasible=summary(joint),
                      configurations=dict(representation='alignment-point-domains-budget-v1',total_training_points_max=66,
                          semantics='Union of branches. In one branch choose one row per stat under its single alignment, with sum(training_points) <= 66.',
                          branches=branches),witnesses=[witnesses[v] for v in sorted(witnesses)])
        result['provenance']['constraints']=dict(known_training_points=deepcopy(known_training_points),point_domains=normalized_domains,
            adjustments=deepcopy(adjustments),alignments=deepcopy(alignments),stat_constraints=constraints)
        result['provenance']['legality_scope']='Exact under pinned community-documented Champions stat rules; not roster legality or official mechanics certification.'
        if not joint:result['diagnostics'].append(dict(reason='No single alignment and allocation under the 66-point budget satisfies all supplied stat constraints.'))
    except (ValueError,TypeError,KeyError,NotImplementedError) as exc:
        result.update(status='insufficient_information',attainable=None,joint_feasible=None,configurations=None,witnesses=[])
        result['diagnostics'].append(dict(reason=str(exc)))
    return result
