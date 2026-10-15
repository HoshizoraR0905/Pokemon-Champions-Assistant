"""Offline Champions stat construction, independent of the damage engine.

Adjustment strings are exact decimal labels, never binary floating point.
Marginal stat sets are projections, not jointly attainable six-stat builds.
"""
from copy import deepcopy
from functools import lru_cache
from itertools import product
import hashlib
import json
from math import prod
from pathlib import Path

from . import KnowledgeBase, normalize

STATS = ('hp', 'attack', 'defense', 'special_attack', 'special_defense', 'speed')
NON_HP = STATS[1:]
BASE_KEYS = dict(zip(STATS, ('hp', 'at', 'df', 'sa', 'sd', 'sp')))
FACTORS = {'0.9': 9, '1.0': 10, '1.1': 11}
PROFILE = '52poke-champions-stats-v1'


@lru_cache(maxsize=1)
def _knowledge():
    return KnowledgeBase()


@lru_cache(maxsize=1)
def _rules():
    path = Path(__file__).parent / 'data' / 'champions_stat_rules.json'
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{label} must be an integer in [{low}, {high}]')
    return value


def validate_training_points(points):
    """Require a complete allocation; unspent points are legal."""
    if not isinstance(points, dict) or set(points) != set(STATS):
        raise ValueError('Supply all six training point values explicitly')
    for stat in STATS:
        _integer(points[stat], 0, 32, stat)
    if sum(points.values()) > 66:
        raise ValueError('Training point total exceeds 66')
    return dict(points)


def adjustment_factors(alignment):
    """One increased and one distinct decreased non-HP stat, or explicit neutral.

    Neutral denotes the single numerical pattern, not five interchangeable
    selectable labels: 52Poké says four neutral nature labels cannot be selected.
    """
    if not isinstance(alignment, dict) or set(alignment) != {'increase', 'decrease'}:
        raise ValueError('Specify increase and decrease, both null for neutral')
    up, down = alignment['increase'], alignment['decrease']
    if up is None and down is None:
        return {s: '1.0' for s in STATS}
    if not isinstance(up, str) or not isinstance(down, str) or up not in NON_HP or down not in NON_HP or up == down:
        raise ValueError('Alignment requires two distinct non-HP stats')
    return {s: '1.1' if s == up else '0.9' if s == down else '1.0' for s in STATS}


def alignment_patterns():
    """All 21 distinct numerical patterns; no usage weights or inferred choice."""
    return [{'increase': None, 'decrease': None}] + [
        {'increase': up, 'decrease': down} for up in NON_HP for down in NON_HP if up != down]


def _stat_value(base, stat, points, adjustment):
    return base + points + 75 if stat == 'hp' else (base + points + 20) * FACTORS[adjustment] // 10


def legal_allocations(point_domains, *, max_combinations=1000000):
    """Enumerate caller-bounded point domains, rejecting excessive work upfront.

    Every yielded complete allocation obeys the total budget. Never silently
    truncates; the work limit is on the Cartesian domain before budget filtering.
    """
    _integer(max_combinations, 1, 10000000, 'max_combinations')
    if not isinstance(point_domains, dict) or set(point_domains) != set(STATS):
        raise ValueError('Explicit finite domains for all six stats are required')
    domains = []
    for stat in STATS:
        values = _domain(point_domains[stat], stat)
        domains.append(values)
    if prod(map(len, domains)) > max_combinations:
        raise ValueError('Allocation work limit exceeded; narrow point_domains')
    return (dict(zip(STATS, row)) for row in product(*domains) if sum(row) <= 66)


def _domain(values, label):
    # Bounded materialization also rejects infinite iterables without hanging.
    from itertools import islice
    try:
        values = list(islice(iter(values), 34))
    except TypeError as exc:
        raise ValueError(f'{label} requires a finite integer domain') from exc
    if not values or len(values) > 33:
        raise ValueError(f'{label} requires 1..33 domain entries')
    for value in values:
        _integer(value, 0, 32, label)
    return sorted(set(values))


class ChampionsStats:
    """Current-form base stats from the existing canonical KnowledgeBase.

    Does not certify roster/regulation legality, construct battle-modified stats,
    or infer a level, nature, training allocation, or opponent configuration.
    """
    def __init__(self, identity, *, form=None, knowledge=None):
        kb = knowledge if knowledge is not None else _knowledge()
        if not isinstance(identity, str):
            raise ValueError('Explicit canonical identity or exact name required')
        explicit_variant = False
        if identity.startswith('pokeapi:pokemon:'):
            parts = identity.split(':')
            if not parts[-1].isdigit():
                raise ValueError('Invalid Pokemon identity')
            rows = kb.identities.by_pokemon.get(int(parts[-1]), [])
            if len(rows) != 1:
                raise ValueError('Unknown or ambiguous Pokemon variant')
            row = rows[0]
            key = f"pokeapi:form:{row.get('source_form_id', row['form_id'])}"
            identity = key if key in kb.entities else f"pokeapi:species:{row['species_id']}"
            explicit_variant = True
        def resolve(value):
            if not isinstance(value, str):
                raise ValueError('Explicit form identity required')
            matches = [kb.entities[value]] if value in kb.entities else kb.exact['species'].get(normalize(value), [])
            matches = {e.canonical_id: e for e in matches if e.kind == 'species'}
            if len(matches) != 1:
                raise ValueError('Unknown or ambiguous species/form')
            return next(iter(matches.values()))
        entity = resolve(identity)
        if entity.form_id is not None or explicit_variant:
            if form not in (None, 'as_named'):
                raise ValueError('Variant identity already fixes form; use as_named or omit')
        elif form == 'base':
            pass
        elif form is not None:
            chosen = resolve(form)
            if chosen.species_id != entity.species_id or chosen.form_id is None:
                raise ValueError('Form does not belong to supplied species')
            entity = chosen
        else:
            raise ValueError('Specify base or an explicit form; species alone is insufficient')
        entry = kb.facts.get('pokemon', {}).get(entity.canonical_id)
        if not entry or set(entry.get('stats', {})) != set(BASE_KEYS.values()):
            raise ValueError('No complete pinned base stats for this form')
        self.identity = entity.canonical_id
        self._base_stats = {s: _integer(entry['stats'][k], 1, 255, 'base ' + s) for s, k in BASE_KEYS.items()}
        if self._base_stats['hp'] == 1:
            raise NotImplementedError('Exceptional fixed-HP species requires Champions-specific verification')
        rules, digest = _rules()
        self._provenance = dict(profile=PROFILE, rule_sha256=digest,
            sources=rules['sources'], documented_rules=rules['documented_rules'],
            limitations=rules['limitations'], base_stats_source=kb.facts['source'],
            knowledge_snapshot=kb.snapshot_id,
            facts_sha256=kb.manifest['files']['champions_facts.json'])

    @property
    def base_stats(self):
        return dict(self._base_stats)

    @property
    def provenance(self):
        return deepcopy(self._provenance)

    def calculate(self, training_points, alignment):
        points = validate_training_points(training_points)
        factors = adjustment_factors(alignment)
        return dict(identity=self.identity, stat_basis='unmodified',
            stats={s: _stat_value(self._base_stats[s], s, points[s], factors[s]) for s in STATS},
            training_points=points, alignment=dict(alignment), adjustments=factors,
            unused_points=66-sum(points.values()), provenance=self.provenance)

    def attainable(self, stat, *, adjustments, point_domain=range(33), allocated_other=None):
        """Exact marginal projection; explicit allowed adjustments, no prior.

        allocated_other fixes points already spent on other stats; omitted stats
        are unconstrained and may use zero points. A non-neutral factor implies
        a compensating opposite adjustment on another non-HP stat.
        """
        if stat not in STATS:
            raise ValueError('Unknown stat')
        if not isinstance(adjustments, (tuple, list)) or not adjustments or any(type(a) is not str or a not in FACTORS for a in adjustments):
            raise ValueError('Specify adjustment alternatives as exact strings: 0.9, 1.0, 1.1')
        if stat == 'hp' and set(adjustments) != {'1.0'}:
            raise ValueError('HP cannot have an adjustment')
        other = {} if allocated_other is None else allocated_other
        if not isinstance(other, dict) or set(other) - (set(STATS) - {stat}):
            raise ValueError('allocated_other may contain only other stats')
        for s, p in other.items():
            _integer(p, 0, 32, s)
        if sum(other.values()) > 66:
            raise ValueError('Training point total exceeds 66')
        configurations = [dict(training_points=p, adjustment=a,
            actual_stat=_stat_value(self._base_stats[stat], stat, p, a))
            for p in _domain(point_domain, stat) if p + sum(other.values()) <= 66
            for a in sorted(set(adjustments))]
        values = sorted({r['actual_stat'] for r in configurations})
        return dict(identity=self.identity, stat=stat, values=values,
            minimum=min(values) if values else None, maximum=max(values) if values else None,
            count=len(values), has_gaps=bool(values and len(values) != values[-1]-values[0]+1),
            configurations=configurations, allocated_other=dict(other),
            scope='single-stat projection; extrema across stats need not coexist', provenance=self.provenance)

    def reverse_lookup(self, stat, actual_stat, *, adjustments, **kwargs):
        _integer(actual_stat, 1, 65535, 'actual_stat')
        result = self.attainable(stat, adjustments=adjustments, **kwargs)
        return dict(identity=self.identity, stat=stat, actual_stat=actual_stat,
            configurations=[r for r in result['configurations'] if r['actual_stat'] == actual_stat],
            scope=result['scope'], allocated_other=result['allocated_other'], provenance=self.provenance)

    def reverse_configurations(self, actual_stats, *, alignments, point_domains, max_combinations=1000000):
        """Joint reverse lookup over explicit, bounded full configurations."""
        _integer(max_combinations, 1, 10000000, 'max_combinations')
        if not isinstance(actual_stats, dict) or not actual_stats or set(actual_stats) - set(STATS):
            raise ValueError('Supply one or more known actual stats')
        for s, v in actual_stats.items():
            _integer(v, 1, 65535, s)
        if not isinstance(alignments, (list, tuple)) or not 1 <= len(alignments) <= 21:
            raise ValueError('Supply 1..21 explicit alignment alternatives')
        factors = [adjustment_factors(a) for a in alignments]
        # Validate the domain/work bound before any enumeration.
        allocations = legal_allocations(point_domains, max_combinations=max_combinations // len(alignments))
        rows = []
        for points in allocations:
            for alignment, factor in zip(alignments, factors):
                if all(_stat_value(self._base_stats[s], s, points[s], factor[s]) == v for s, v in actual_stats.items()):
                    rows.append(dict(training_points=dict(points), alignment=dict(alignment)))
        return dict(identity=self.identity, configurations=rows, count=len(rows), provenance=self.provenance)
