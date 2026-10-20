"""Validate documented current battle rows without manufacturing probabilities."""
import json
from pathlib import Path
from . import STAT_KINDS
from .common import sha
from .statistics import probability

CATEGORIES = {'move':'move', 'held_item':'item', 'ability':'ability',
              'stat_alignment':'nature', 'stat_points':'spread', 'teammate':'teammate'}
POINT_COLUMNS = ('hp_points', 'attack_points', 'defense_points',
                 'sp_atk_points', 'sp_def_points', 'speed_points')
RULES_PATH = Path(__file__).resolve().parents[1]/'knowledge/data/champions_stat_rules.json'


def stat_vector(kind, values):
    if kind not in STAT_KINDS or len(values) != 6:
        raise ValueError('Explicit stat kind and ordered six-dimensional vector required')
    if any(v is not None and (type(v) is not int or v < 0) for v in values):
        raise ValueError('Stat components must be nonnegative integers or unknown')
    result = dict(kind=kind, values=values, order=['HP','Attack','Defense','Special Attack','Special Defense','Speed'])
    if kind == 'champions_sp':
        # Existing maintained rule implementation, never an EV conversion.
        from knowledge.champions_stats import STATS, validate_training_points
        result['rule_profile'] = '52poke-champions-stats-v1'
        result['rule_sha256'] = sha(RULES_PATH.read_bytes())
        if None in values:
            result['validation'] = 'incomplete'
        else:
            try:
                validate_training_points(dict(zip(STATS, values)))
                result['validation'] = 'valid_under_pinned_profile'
            except ValueError as exc:
                result.update(validation='invalid_under_pinned_profile', diagnostic=str(exc))
    return result


def parse_index(data):
    if not isinstance(data, dict) or not isinstance(data.get('pokemon'), list) or not isinstance(data.get('generatedAt'), str):
        raise ValueError('Index schema changed: expected pokemon list and generatedAt')
    entries = {}
    for entry in data['pokemon']:
        sid = entry.get('showdownId')
        if not isinstance(sid, str) or not sid.isascii() or not sid.isalnum() or sid != sid.lower() or sid in entries:
            raise ValueError('Invalid/duplicate indexed identifier')
        if not isinstance(entry.get('name'), str) or not isinstance(entry.get('showdownName'), str) or not isinstance(entry.get('battleDataCsvs'), list):
            raise ValueError('Index entity schema changed')
        entries[sid] = entry
    return entries


def parse_battle(data, expected_id, battle_format):
    if not isinstance(data, dict) or data.get('showdownId') != expected_id or data.get('format') != battle_format or data.get('season') != 'Current':
        raise ValueError('Battle source identity/format/current-population mismatch')
    if not isinstance(data.get('rows'), list) or not isinstance(data.get('source'), str):
        raise ValueError('Battle response schema changed')
    columns = data.get('columns')
    if not isinstance(columns, list) or not {'category','rank','name','percentage',*POINT_COLUMNS} <= set(columns):
        raise ValueError('Battle columns changed; parser review required')
    records, warnings = [], []
    for ordinal, raw in enumerate(data['rows']):
        if not isinstance(raw, dict) or raw.get('category') not in CATEGORIES:
            raise ValueError('Unknown battle row category; parser review required')
        if type(raw.get('rank')) is not int or raw['rank'] <= 0 or not isinstance(raw.get('name'), str):
            raise ValueError('Invalid battle row identity/rank')
        if raw.get('pokemon') != data.get('pokemon'):
            raise ValueError('Row belongs to a different source Pokémon')
        percent = raw.get('percentage_value')
        if percent is not None:
            if isinstance(percent, bool) or not isinstance(percent, (int, float)):
                raise ValueError('Invalid source percentage')
            p = probability(percent/100)
        else:
            p = None
        literal = raw.get('percentage', '')
        if not isinstance(literal, str):
            raise ValueError('Invalid literal percentage')
        if literal:
            try:
                if not literal.endswith('%') or percent is None or abs(float(literal[:-1])-percent) > 1e-9:
                    raise ValueError('Literal and numeric percentages disagree')
            except ValueError as exc:
                raise ValueError('Inconsistent published percentage') from exc
        rec = dict(ordinal=ordinal, category=CATEGORIES[raw['category']], source_category=raw['category'],
            rank=raw['rank'], original_name=raw['name'], proportion=p, reported_percentage=percent,
            numerator=None, denominator=None, sample_count=None, effective_sample_size=None,
            denominator_definition='source-reported within-species percentage; exact eligible unit unknown' if p is not None else 'not supplied',
            weighting=None, confidence_interval=None, smoothing='none', raw=raw,
            completeness='published leading entries; omitted values unknown',
            flags=['sample_count_unknown', 'denominator_unknown', 'provider_provenance_unverified'])
        if rec['category'] == 'spread':
            values = [raw.get(k) if raw.get(k) != '' else None for k in POINT_COLUMNS]
            rec['stat_vector'] = stat_vector('champions_sp', values)
            rec['stat_vector']['semantics_evidence'] = 'source category stat_points and six named *_points columns; source assertion, not independent game verification'
            rec['nature'] = None  # Separate nature marginal is not joint evidence.
            if rec['stat_vector']['validation'] != 'valid_under_pinned_profile':
                rec['flags'].append('spread_not_validated')
        elif rec['category'] == 'nature':
            rec['alignment'] = dict(increase=raw.get('stat_up') or None, decrease=raw.get('stat_down') or None)
        if p is None:
            rec['flags'].append('proportion_unavailable')
        records.append(rec)
    if not records:
        warnings.append('empty_source_rows')
    return records, warnings
