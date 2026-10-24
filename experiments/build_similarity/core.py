"""Configurable dissimilarities and deterministic precomputed clustering.

Exponential absolute differences and cosine dissimilarity need not satisfy
triangle inequalities. Nothing here assumes Euclidean geometry.
"""
from dataclasses import dataclass, replace, asdict
from collections import Counter
import math
import numpy as np
from knowledge.champions_stats import STATS, validate_training_points


@dataclass(frozen=True)
class SPConfig:
    gamma: float = 2.
    bulk: float = 1.
    defense: float = .3
    attack: float = 1.
    special_attack: float = 1.
    speed: float = 1.2
    allocation: float = .3
    bulk_scale: float = 66.
    defense_scale: float = 48.  # sensitivity scale, NOT the legal per-stat cap
    offense_scale: float = 32.
    formulation: str = 'raw'

    def __post_init__(self):
        values = asdict(self)
        if self.formulation not in ('raw', 'proportion'):
            raise ValueError('Unknown defensive formulation')
        for key, value in values.items():
            if key != 'formulation' and (not math.isfinite(value) or value < 0):
                raise ValueError('Finite nonnegative parameters required')
        if min(self.gamma, self.bulk_scale, self.defense_scale, self.offense_scale) <= 0:
            raise ValueError('Positive gamma and sensitivity scales required')


def sp_array(rows):
    return np.array([[validate_training_points(r['training_points'])[s] for s in STATS]
                     for r in rows], dtype=float).reshape(-1, 6)


def sp_distances(x, y, config=SPConfig()):
    """Inputs are validated by sp_array, or directly as six legal SP columns."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    for arr in (x, y):
        if arr.ndim != 2 or arr.shape[1] != 6 or not np.isfinite(arr).all():
            raise ValueError('Expected finite n-by-six SP arrays')
        if (arr < 0).any() or (arr > 32).any() or (arr != np.floor(arr)).any() or (arr.sum(1) > 66).any():
            raise ValueError('Illegal Champions SP allocation')
    delta = np.abs(x[:, None, :] - y[None, :, :])
    bx, by = x[:, [0, 2, 4]].sum(1), y[:, [0, 2, 4]].sum(1)
    phi = lambda t: np.expm1(config.gamma * t)
    result = config.bulk * phi(np.abs(bx[:, None] - by[None, :]) / config.bulk_scale)
    if config.formulation == 'raw':
        result += config.defense * phi(delta[:, :, [0, 2, 4]] / config.defense_scale).sum(2)
    else:
        qx = np.divide(x[:, [0, 2, 4]], bx[:, None], out=np.zeros((len(x), 3)), where=bx[:, None] > 0)
        qy = np.divide(y[:, [0, 2, 4]], by[:, None], out=np.zeros((len(y), 3)), where=by[:, None] > 0)
        result += config.allocation * np.minimum(bx[:, None], by[None, :]) / config.bulk_scale * np.abs(qx[:, None] - qy[None, :]).sum(2)
    for col, weight in ((1, config.attack), (3, config.special_attack), (5, config.speed)):
        result += weight * phi(delta[:, :, col] / config.offense_scale)
    return result


def moves(row):
    result = tuple(sorted(set(row['configuration']['moves'])))
    if len(result) != 4 or any(not m for m in result):
        raise ValueError('Four distinct known canonical moves required')
    return result


class MoveModel:
    """Shrinkage PPMI of binary move incidence, then U sqrt(S) mean pooling.

    Add alpha pseudo-observations independently to each Bernoulli cell:
    p_i=(f_i+2a)/(N+4a), p_ij=(c_ij+a)/(N+4a).
    Association = min(cap, max(0, log(p_ij/(p_i*p_j)))) * c/(c+shrink).
    Diagonal is zero: self-cooccurrence is not pair evidence.
    """
    def __init__(self, dimension=16, alpha=.5, shrink=5., cap=3., pooling='mean'):
        if pooling not in ('mean', 'unit-mean'):
            raise ValueError('Unknown pooling procedure')
        self.pooling = pooling
        if type(dimension) is not int or dimension < 1 or not all(math.isfinite(v) and v > 0 for v in (alpha, shrink, cap)):
            raise ValueError('Positive dimension, smoothing, shrinkage and cap required')
        self.dimension, self.alpha, self.shrink, self.cap = dimension, alpha, shrink, cap

    def fit(self, rows):
        if not rows:
            raise ValueError('Empty training population')
        self.vocabulary = sorted({m for r in rows for m in moves(r)})
        self.index = {m: i for i, m in enumerate(self.vocabulary)}
        incidence = np.zeros((len(rows), len(self.index)))
        for i, row in enumerate(rows):
            incidence[i, [self.index[m] for m in moves(row)]] = 1
        self.n = len(rows)
        self.frequency = incidence.sum(0)
        self.counts = incidence.T @ incidence
        p = (self.frequency + 2*self.alpha) / (self.n + 4*self.alpha)
        joint = (self.counts + self.alpha) / (self.n + 4*self.alpha)
        self.association = np.minimum(self.cap, np.maximum(0, np.log(joint / np.outer(p, p)))) * self.counts / (self.counts + self.shrink)
        np.fill_diagonal(self.association, 0)
        u, s, _ = np.linalg.svd(self.association, full_matrices=False)
        k = min(self.dimension, len(s))
        self.embedding = u[:, :k] * np.sqrt(s[:k])
        # Canonicalize signs for saved artifacts (distances are sign invariant).
        for j in range(k):
            pivot = np.argmax(np.abs(self.embedding[:, j]))
            if self.embedding[pivot, j] < 0:
                self.embedding[:, j] *= -1
        self.singular_values = s
        self.training_ids = [r['empirical_record_id'] for r in rows]
        return self

    def transform(self, rows):
        out = np.zeros((len(rows), self.embedding.shape[1]))
        for i, row in enumerate(rows):
            # Unknown moves contribute zero; fixed denominator four exposes OOV loss.
            for move in moves(row):
                if move in self.index:
                    vector = self.embedding[self.index[move]]
                    if self.pooling == 'unit-mean':
                        norm = np.linalg.norm(vector)
                        vector = vector / norm if norm > 1e-15 else np.zeros_like(vector)
                    out[i] += vector / 4
        return out

    def distances(self, left, right):
        x, y = self.transform(left), self.transform(right)
        norm = np.linalg.norm(x, axis=1)[:, None] * np.linalg.norm(y, axis=1)[None, :]
        result = 1 - np.divide(x @ y.T, norm, out=np.zeros((len(x), len(y))), where=norm > 1e-15)
        # No embedding evidence: zero only for the same exact set; otherwise one.
        for i, r in enumerate(left):
            for j, s in enumerate(right):
                if moves(r) == moves(s):
                    result[i, j] = 0
        return np.clip(result, 0, 2)

    def diagnostics(self):
        pairs = []
        for i, a in enumerate(self.vocabulary):
            for j in range(i+1, len(self.vocabulary)):
                if self.counts[i, j]:
                    pairs.append(dict(moves=[a, self.vocabulary[j]], count=int(self.counts[i, j]),
                                      association=float(self.association[i, j]), shrink_factor=float(self.counts[i, j]/(self.counts[i, j]+self.shrink))))
        return dict(observations=self.n, equal_weight_kish_ess=self.n,
                    independent_sample_size='unknown; source/team dependence remains',
                    vocabulary=self.vocabulary, frequencies=self.frequency.astype(int).tolist(),
                    pair_counts_and_associations=pairs,
                    rare_pairs_at_most_two=sum(p['count'] <= 2 for p in pairs),
                    parameters=dict(dimension=self.dimension, alpha=self.alpha, shrink=self.shrink, cap=self.cap, pooling=self.pooling),
                    singular_values=self.singular_values.tolist(), embedding=self.embedding.tolist())


def distribution(values):
    arr = np.asarray(values, float)
    if not arr.size:
        return dict(n=0, median=None, iqr=None, p90=None, p95=None, max=None)
    q = np.quantile(arr, [.25, .5, .75, .9, .95])
    return dict(n=int(arr.size), median=float(q[1]), iqr=float(q[2]-q[0]),
                p90=float(q[3]), p95=float(q[4]), max=float(arr.max()))


class BuildDistance:
    def __init__(self, model, *, sp=SPConfig(), move='learned', weights=(1., 1., 0., 0.)):
        if move not in ('learned', 'jaccard') or len(weights) != 4 or any(not math.isfinite(w) or w < 0 for w in weights):
            raise ValueError('Invalid distance configuration')
        self.model, self.sp, self.move, self.weights = model, sp, move, tuple(weights)

    def components(self, left, right):
        if self.move == 'learned':
            md = self.model.distances(left, right)
        else:
            md = np.array([[1-len(set(moves(a)) & set(moves(b)))/len(set(moves(a)) | set(moves(b))) for b in right] for a in left])
        return [sp_distances(sp_array(left), sp_array(right), self.sp), md,
                np.array([[a['item'] != b['item'] for b in right] for a in left], float),
                np.array([[a['nature'] != b['nature'] for b in right] for a in left], float)]

    def fit(self, rows):
        cs = self.components(rows, rows)
        triangle = np.triu_indices(len(rows), 1)
        self.scales, self.diagnostics = [], []
        for c, weight in zip(cs, self.weights):
            v = c[triangle]
            positive = v[v > 1e-12]
            # Median positive distances avoids zero-division with repeated builds.
            scale = float(np.median(positive)) if len(positive) else 1.
            self.scales.append(scale)
            self.diagnostics.append(dict(raw=distribution(v), positive_pairs=len(positive), scale=scale,
                                         weighted_contribution=distribution(v / scale * weight)))
        return self

    def distances(self, left, right):
        return sum(w*c/s for w, c, s in zip(self.weights, self.components(left, right), self.scales))


def validate_matrix(d):
    d = np.asarray(d, float)
    if d.ndim != 2 or d.shape[0] != d.shape[1] or not np.isfinite(d).all() or (d < -1e-10).any() or not np.allclose(d, d.T) or not np.allclose(np.diag(d), 0):
        raise ValueError('Finite symmetric nonnegative zero-diagonal dissimilarity required')
    return d


def assign(d, medoids):
    labels = np.argmin(d[:, medoids], axis=1)
    # Duplicate observed medoids still own themselves, making K clusters nonempty.
    for z, m in enumerate(medoids):
        labels[m] = z
    return labels


def kmedoids(d, k, max_iter=100):
    """Deterministic PAM BUILD + best SWAP; unit mass per occurrence."""
    d = validate_matrix(d)
    n = len(d)
    if type(k) is not int or not 1 <= k <= n:
        raise ValueError('Invalid K')
    medoids = [int(np.argmin(d.sum(0)))]
    while len(medoids) < k:
        best = min((float(np.minimum(d[:, medoids].min(1), d[:, i]).sum()), i) for i in range(n) if i not in medoids)
        medoids.append(best[1])
    cost = float(d[:, medoids].min(1).sum())
    for iteration in range(max_iter):
        best = (cost, None)
        # Recompute small K minima; avoids assuming a metric or triangle pruning.
        for z in range(k):
            others = medoids[:z] + medoids[z+1:]
            base = d[:, others].min(1) if others else np.full(n, np.inf)
            costs = np.minimum(base[:, None], d).sum(0)
            for candidate in range(n):
                if candidate not in medoids and costs[candidate] < best[0]-1e-10:
                    best = (float(costs[candidate]), (z, candidate))
        if best[1] is None:
            break
        medoids[best[1][0]] = best[1][1]
        cost = best[0]
    medoids = sorted(medoids)
    return dict(medoids=medoids, labels=assign(d, medoids).tolist(), cost=cost, iterations=iteration+1)


def hierarchical(d):
    """Average linkage using occurrence-weighted Lance-Williams updates."""
    d = validate_matrix(d)
    n = len(d)
    matrix = np.full((2*n-1, 2*n-1), np.inf)
    matrix[:n, :n] = d
    np.fill_diagonal(matrix, np.inf)
    active = list(range(n)); size = {i: 1 for i in active}; merges = []
    for node in range(n, 2*n-1):
        sub = matrix[np.ix_(active, active)]
        a, b = np.unravel_index(np.argmin(sub), sub.shape)
        a, b = sorted((active[a], active[b]))
        height = float(matrix[a, b]); count = size[a]+size[b]
        others = [i for i in active if i not in (a, b)]
        for c in others:
            matrix[node, c] = matrix[c, node] = (size[a]*matrix[a, c] + size[b]*matrix[b, c])/count
        merges.append([a, b, height, count]); size[node] = count
        active = others+[node]
    return merges


def cut_tree(n, merges, *, k=None, threshold=None):
    if (k is None) == (threshold is None) or (k is not None and not 1 <= k <= n):
        raise ValueError('Specify K or threshold')
    clusters = {i: [i] for i in range(n)}
    for j, (a, b, height, _) in enumerate(merges):
        if (k is not None and len(clusters) <= k) or (threshold is not None and height > threshold):
            break
        clusters[n+j] = clusters.pop(a) + clusters.pop(b)
    labels = np.zeros(n, int)
    for z, members in enumerate(sorted(clusters.values(), key=min)):
        labels[members] = z
    return labels.tolist()


def silhouette(d, labels):
    labels = np.asarray(labels); groups = sorted(set(labels))
    if len(groups) < 2 or len(groups) == len(labels):
        return None
    result = []
    for i, z in enumerate(labels):
        own = np.where(labels == z)[0]; own = own[own != i]
        if not len(own):
            result.append(0.); continue
        a = float(d[i, own].mean())
        b = min(float(d[i, labels == other].mean()) for other in groups if other != z)
        result.append((b-a)/max(a, b) if max(a, b) > 0 else 0.)
    return float(np.mean(result))


def adjusted_rand(a, b):
    if len(a) != len(b):
        raise ValueError('Unmatched anchors')
    n = len(a)
    if n < 2:
        return None
    choose = lambda v: v*(v-1)/2
    table = Counter(zip(a, b)); ca, cb = Counter(a), Counter(b)
    index = sum(choose(v) for v in table.values())
    expected = sum(choose(v) for v in ca.values()) * sum(choose(v) for v in cb.values()) / choose(n)
    upper = (sum(choose(v) for v in ca.values()) + sum(choose(v) for v in cb.values()))/2
    return float((index-expected)/(upper-expected)) if upper != expected else 1.


def soft_membership(distances, sizes, temperature=1.):
    """Similarity-derived scores, NOT posterior probabilities."""
    distances, sizes = np.asarray(distances, float), np.asarray(sizes, float)
    if not math.isfinite(temperature) or temperature <= 0 or (sizes <= 0).any() or not np.isfinite(sizes).all() or not np.isfinite(distances).all() or (distances < 0).any() or distances.ndim != 2 or distances.shape[1] != len(sizes):
        raise ValueError('Positive finite temperature/sizes and valid distances required')
    logits = np.log(sizes/sizes.sum())[None, :] - distances/temperature
    scores = np.exp(logits-logits.max(1, keepdims=True))
    return scores/scores.sum(1, keepdims=True)
