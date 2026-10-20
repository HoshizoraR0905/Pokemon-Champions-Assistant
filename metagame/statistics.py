"""Explicit-denominator descriptive methods; no invented effective counts."""
import math


def number(value, label='value'):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid nonnegative finite ' + label)
    return value


def probability(value):
    number(value, 'proportion')
    if value > 1:
        raise ValueError('Proportion outside [0, 1]')
    return value


def wilson(successes, trials):
    if type(trials) is not int or type(successes) is not int or not 0 <= successes <= trials or trials <= 0:
        raise ValueError('Wilson requires positive independent unweighted binomial counts')
    z = 1.959963984540054
    p = successes / trials
    den = 1 + z*z/trials
    center = (p + z*z/(2*trials)) / den
    half = z * math.sqrt(p*(1-p)/trials + z*z/(4*trials*trials)) / den
    return [max(0., center-half), min(1., center+half)]


def hierarchical_smooth(counts, parent_counts, strength, *, count_basis):
    """Dirichlet posterior mean with explicit parent and prior strength.

    Only caller-verified disjoint/appropriate count populations are admissible.
    This is an opt-in descriptive estimator, never applied to weighted masses.
    """
    if count_basis != 'independent_unweighted_counts':
        raise ValueError('Weighted masses and rounded percentages are not independent counts')
    if set(counts) != set(parent_counts) or not counts or not math.isfinite(strength) or strength <= 0:
        raise ValueError('Same explicit categories and positive finite strength required')
    for value in [*counts.values(), *parent_counts.values()]:
        if type(value) is not int or value < 0:
            raise ValueError('Nonnegative integer counts required')
    total, parent = sum(counts.values()), sum(parent_counts.values())
    if not parent:
        raise ValueError('Nonempty documented parent counts required')
    return dict(method='hierarchical_dirichlet_mean', strength=strength, sample_count=total,
        parent_sample_count=parent,
        estimates={k: (counts[k] + strength*parent_counts[k]/parent)/(total+strength) for k in counts},
        uncertainty='interval_not_computed; independence and parent applicability require caller evidence')


def pair_summary(conditional, baseline):
    probability(conditional)
    probability(baseline)
    return dict(conditional_teammate_usage=conditional,
        lift=conditional/baseline if baseline > 0 else None,
        interpretation='descriptive six-member-team baseline; not causal',
        uncertainty_interval=None, effective_sample_size=None)


def joint_from_counts(ab, a, b, total, *, count_basis):
    if count_basis != 'independent_unweighted_team_counts':
        raise ValueError('Explicit same-population team counts required')
    if any(type(v) is not int for v in (ab, a, b, total)) or not 0 < total or not 0 < a <= total or not 0 <= b <= total or not max(0, a+b-total) <= ab <= min(a, b):
        raise ValueError('Inconsistent joint counts')
    return dict(cooccurrence=ab/total, numerator=ab, denominator=total,
        conditional_interval=wilson(ab, a), **pair_summary(ab/a, b/total))
