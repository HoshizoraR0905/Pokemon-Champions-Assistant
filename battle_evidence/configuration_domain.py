"""User-selected inference domains over the existing Champions stat calculator.

The default configuration assumption is distinct from mechanical legality and
never changes a known team's stats. No frequency weights or probability prior.
"""
from functools import lru_cache
from copy import deepcopy
from knowledge.champions_stats import STATS,alignment_patterns,adjustment_factors
from knowledge.stat_feasibility import champions_attainable_stats,summary

DEFAULT_RULE='user-default-down-zero-sp-v1'


def point_domain(factor,rule=None):
    if rule not in (None,DEFAULT_RULE):raise ValueError('Unknown inference configuration rule')
    return [0] if rule==DEFAULT_RULE and factor=='0.9' else list(range(33))


@lru_cache(maxsize=256)
def initial_domain(identity,rule=DEFAULT_RULE):
    return project_domain(identity,{},rule=rule)


def project_domain(identity,constraints,*,rule=DEFAULT_RULE):
    """Exact alignment/SP budget projection of supplied native stat sets.

    Delegate integer arithmetic, alignment dependencies and the 66-SP budget to
    champions_attainable_stats. Branch rows retain SP-to-stat correspondence.
    """
    if rule not in (None,DEFAULT_RULE):raise ValueError('Unknown inference configuration rule')
    branches=[];diagnostics=[]
    for pattern in alignment_patterns():
        factors=adjustment_factors(pattern)
        result=champions_attainable_stats(identity=identity,
            form='as_named' if ':pokemon:' in identity or ':form:' in identity else 'base',
            stat='speed',alignments=[pattern],
            point_domains={s:point_domain(factors[s],rule) for s in STATS},
            stat_constraints={s:{'allowed_values':v['values']} for s,v in constraints.items() if v is not None},
            retain_witnesses=False)
        if result['status']=='exact':branches.extend(result['configurations']['branches'])
        elif result['status'] not in {'empty'}:diagnostics.extend(result['diagnostics'])
    stats={s:summary(r['actual_stat'] for b in branches for r in b['stat_point_domains'][s]) for s in STATS}
    alignments={s:sorted({b['adjustments'][s] for b in branches}) for s in STATS}
    points={s:summary(r['training_points'] for b in branches for r in b['stat_point_domains'][s]) for s in STATS}
    return dict(rule=rule,status='unresolved' if diagnostics else 'exact' if branches else 'contradiction',
        stats=stats,alignment_modifiers=alignments,stat_points=points,
        configurations=dict(total_SP_max=66,branches=branches,
            semantics='One global alignment and one row per stat, with total SP <=66; lowered non-HP stat SP0 under user default'),
        diagnostics=diagnostics,fallback_used=False)
