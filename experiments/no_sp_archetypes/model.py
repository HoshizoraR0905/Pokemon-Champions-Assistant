"""Occurrence-weighted mixture of smoothed subset-conditional distributions.

A latent projection selects k with fixed weights and one of C(4,k) subsets
uniformly. Each component is a Dirichlet-shrunk categorical distribution of Z.
We average normalized conditionals, never multiply overlapping evidence.
These are empirical model weights, NOT calibrated opponent probabilities.
"""
from collections import Counter, defaultdict
from itertools import combinations
import math

LEVEL_WEIGHTS = {1: .1, 2: .2, 3: .3, 4: .4}
ALPHA = 5.


def moveset(values):
    if len(values) != 4 or any(not isinstance(v, str) or not v for v in values) or len(set(values)) != 4:
        raise ValueError('Exactly four distinct canonical moves required')
    return tuple(sorted(values))


class Predictor:
    def __init__(self, rows, labels, alpha=ALPHA):
        if not rows or len(rows) != len(labels) or not math.isfinite(alpha) or alpha <= 0:
            raise ValueError('Positive smoothing and equally sized nonempty observations/labels required')
        if any(type(z) is not int or z not in range(3) for z in labels) or set(labels) != {0, 1, 2}:
            raise ValueError('Three nonempty integer cluster labels required')
        self.alpha = alpha
        self.n = len(rows)
        self.sizes = [labels.count(z) for z in range(3)]
        self.prior = [n / self.n for n in self.sizes]
        self.counts = defaultdict(lambda: [0, 0, 0])
        self.joints = defaultdict(lambda: [0, 0, 0])
        self.items = defaultdict(lambda: [0, 0, 0])
        self.vocabulary = set()
        for row, z in zip(rows, labels):
            ms = moveset(row['configuration']['moves'])
            item = row.get('item')
            self.vocabulary.update(ms)
            if item is not None:
                self.items[item][z] += 1
            for k in LEVEL_WEIGHTS:
                for subset in combinations(ms, k):
                    self.counts[subset][z] += 1
                    if item is not None:
                        self.joints[(subset, item)][z] += 1

    def shrink(self, counts, prior):
        n = sum(counts)
        return [(c + self.alpha * p) / (n + self.alpha) for c, p in zip(counts, prior)]

    def predict(self, values, item=None):
        ms = moveset(values)
        zero = [0, 0, 0]
        item_counts = self.items.get(item, zero) if item is not None else zero
        item_prior = self.shrink(item_counts, self.prior) if item is not None else self.prior
        move_score, item_score = [0.] * 3, [0.] * 3
        support, levels = [], []
        for k, weight in LEVEL_WEIGHTS.items():
            subsets = list(combinations(ms, k))
            level = [0.] * 3
            for subset in subsets:
                counts = self.counts.get(subset, zero)
                joint = self.joints.get((subset, item), zero) if item is not None else zero
                pm = self.shrink(counts, self.prior)
                # Missing/unseen item adds no evidence, preserving moves-only.
                pi = self.shrink(joint, item_prior) if item is not None and sum(item_counts) else pm
                for z in range(3):
                    move_score[z] += weight * pm[z] / len(subsets)
                    item_score[z] += weight * pi[z] / len(subsets)
                    level[z] += pm[z] / len(subsets)
                support.append(dict(moves=list(subset), size=k, counts=list(counts),
                                    item_joint_counts=list(joint)))
            levels.append(dict(size=k, weight=weight, moves_only=level))
        def result(weights):
            weights = [max(0., p) / sum(weights) for p in weights]
            order = sorted(range(3), key=lambda z: (-weights[z], z))
            entropy = -sum(p * math.log(p) for p in weights if p)
            return dict(weights=weights, top=order[0], runner_up=order[1],
                        margin=weights[order[0]] - weights[order[1]], entropy=entropy,
                        prior_shift_l1=sum(abs(p-q) for p,q in zip(weights,self.prior)))
        exact = list(self.counts.get(ms, zero))
        unknown = sorted(set(ms) - self.vocabulary)
        best_subset = max((sum(s['counts']) for s in support if s['size'] >= 2), default=0)
        return dict(moves_only=result(move_score), moves_item=result(item_score) if item is not None else None,
                    item_known=item is not None, item_counts=list(item_counts), prior=self.prior,
                    exact_counts=exact, exact_support=sum(exact), supporting_subsets=support, levels=levels,
                    novelty=dict(unseen_moves=unknown, unseen_complete_set=sum(exact)==0,
                                 rare_complete_set=sum(exact)<3, max_pair_or_larger_support=best_subset,
                                 insufficient_support=best_subset<3,
                                 out_of_distribution=bool(unknown)),
                    weak_evidence=(best_subset<3 or result(move_score)['prior_shift_l1']<.1),
                    interpretation='Uncalibrated empirical cluster weights; no true SP inferred')
