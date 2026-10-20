"""Read-only offline inspection with explicit unavailable-joint-data guards."""
import json
import time
from .identity import Names
from .sources import SOURCE, SOURCE_ID
from .store import Store

UNAVAILABLE = dict(status='unavailable_joint_data', estimate=None, numerator=None,
    denominator=None, effective_sample_size=None,
    reason='The source supplies separate marginals and ordered teammates, not joint counts or full team/build records')
JOINT_TARGETS = ('two_teammates_given_species', 'move_given_teammate', 'item_given_teammate',
    'ability_given_teammate', 'nature_given_teammate', 'sp_given_teammate',
    'item_given_move', 'two_moves_given_species', 'archetype_given_context', 'complete_moveset')


def query(root, species, *, teammate=None, source=SOURCE_ID, battle_format='Doubles', max_age_seconds=86400., names=None):
    if source != SOURCE_ID:
        raise ValueError('Select an enabled source population explicitly')
    names = names or Names()
    resolved = names.resolve(species)
    db = Store(root, readonly=True)
    try:
        if resolved['canonical_id']:
            rows = db.db.execute('''SELECT s.*,t.* FROM snapshots s JOIN subjects t ON s.id=t.snapshot_id
                WHERE s.source_id=? AND t.canonical_id=? AND json_extract(s.metadata,'$.battle_format')=?
                ORDER BY s.checked_epoch DESC''',
                (source,resolved['canonical_id'],battle_format)).fetchall()
        else:
            rows = db.db.execute('''SELECT s.*,t.* FROM snapshots s JOIN subjects t ON s.id=t.snapshot_id
                WHERE s.source_id=? AND (t.source_species=? OR t.source_name=?)
                AND json_extract(s.metadata,'$.battle_format')=? ORDER BY s.checked_epoch DESC''',
                (source,species,species,battle_format)).fetchall()
        if not rows:
            return dict(status='not_cached', species=species, source=SOURCE, estimate=None)
        if len({r['source_species'] for r in rows}) != 1:
            raise ValueError('Multiple source forms match; query an exact indexed identifier')
        row = rows[0]
        records = [json.loads(r[0]) for r in db.db.execute(
            'SELECT record FROM metrics WHERE snapshot_id=? ORDER BY ordinal', (row['id'],))]
        distributions = {k: [] for k in ('move','item','ability','nature','spread','teammate')}
        for rec in records:
            distributions[rec['category']].append(rec)
        metadata = json.loads(row['metadata'])
        age = max(0., time.time()-row['checked_epoch'])
        result = dict(schema_version=1, status='current_cache' if age <= max_age_seconds else 'stale_cache',
            source=SOURCE, source_population=SOURCE['population'],
            snapshot_id=row['id'], raw_sha256=row['raw_sha256'], parser_version=row['parser_version'],
            knowledge_snapshot=row['knowledge_snapshot'], checked_at=row['checked_at'],
            age_seconds=age, identity=json.loads(row['identity']), source_species=row['source_species'],
            metadata=metadata,
            species_usage=dict(status='rank_only', rank=row['usage_rank'], estimate=None,
                numerator=None,denominator=None,sample_count=None,
                denominator_definition='ranking position; not a species usage percentage'),
            distributions=distributions,
            unavailable={k: dict(UNAVAILABLE) for k in JOINT_TARGETS},
            additional_metrics={k: dict(status='unavailable_source_data', estimate=None)
                for k in ('registered_team_usage','selected_usage','lead_usage','observed_usage','win_rate',
                          'teammate_probability','cooccurrence_probability','lift','final_stat_distribution')},
            uncertainty=dict(sample_count=None,effective_sample_size=None,confidence_interval=None,
                smoothing='none; source-reported rounded percentages without documented counts'),
            stat_marginals=_stat_marginals(distributions['spread']))
        if teammate:
            mate = names.resolve(teammate)
            supported = [r for r in distributions['teammate'] if
                mate['canonical_id'] is not None and (r.get('identity') or {}).get('canonical_id')==mate['canonical_id']]
            result['teammate_context'] = dict(requested=teammate, identity=mate,
                listed_teammate_rows=supported,
                relation_status='listed_by_source' if supported else 'not_in_published_leading_entries; absence_unknown',
                conditioned_estimates={k:dict(UNAVAILABLE) for k in
                    ('move','item','ability','nature','spread','speed_sp','final_speed')},
                marginals_are_conditioned=False)
        return result
    finally:
        db.close()


def _stat_marginals(spreads):
    # Exact frequencies of listed vectors can be aggregated, never completed to
    # 100%, renormalized, or coupled to the independently reported nature table.
    axes = ['HP','Attack','Defense','Special Attack','Special Defense','Speed']
    eligible = [r for r in spreads if r['proportion'] is not None and
        r.get('stat_vector', {}).get('validation')=='valid_under_pinned_profile']
    result = dict(status='partial_listed_spreads', scope='published leading spread rows only',
        sample_count=None, covered_reported_mass=sum(r['proportion'] for r in eligible),
        medians=None, quantiles=None,
        limitation='Missing tail, rounded percentages and unknown sample counts; no population quantiles or final-stat distribution', axes={})
    for i, axis in enumerate(axes):
        masses = {}
        for r in eligible:
            value = r['stat_vector']['values'][i]
            masses[value] = masses.get(value, 0.)+r['proportion']
        result['axes'][axis] = [dict(points=k, source_reported_mass=v) for k,v in sorted(masses.items())]
    return result


def completeness(root):
    db = Store(root, readonly=True)
    try:
        rows = db.db.execute('''SELECT s.*,t.source_species FROM snapshots s JOIN subjects t ON t.snapshot_id=s.id
            ORDER BY s.checked_epoch DESC''').fetchall()
        seen, current = set(), []
        for row in rows:
            if row['source_species'] in seen:
                continue
            seen.add(row['source_species'])
            recs = [json.loads(r[0]) for r in db.db.execute('SELECT record FROM metrics WHERE snapshot_id=?',(row['id'],))]
            counts = {k:sum(r['category']==k for r in recs) for k in ('move','item','ability','nature','spread','teammate')}
            issues = [r for r in recs if (r.get('identity') or {}).get('resolution') in ('ambiguous','unresolved')]
            current.append(dict(source_species=row['source_species'], row_counts=counts,
                unresolved_entities=[dict(category=r['category'],name=r['original_name']) for r in issues],
                invalid_or_incomplete_spreads=sum(r.get('stat_vector',{}).get('validation') in
                    ('incomplete','invalid_under_pinned_profile') for r in recs),
                metadata=json.loads(row['metadata'])))
        return dict(source=SOURCE, cached_species=len(current), species=current,
            correlations={k:dict(UNAVAILABLE) for k in JOINT_TARGETS},
            sample_count=None, full_teams=0, individual_joint_builds=0,
            limitation='Cache coverage is not source capture accuracy, full ruleset availability, or statistical completeness')
    finally:
        db.close()


def table(result, top=5):
    if result.get('status')=='not_cached':
        return 'Not cached: '+result['species']
    lines = [SOURCE['attribution']+' — '+SOURCE['homepage'],
        f"Population: {SOURCE['population']}; {result['status']}",
        f"{result['source_species']} | usage rank #{result['species_usage']['rank']} | season {result['metadata']['season']}",
        f"Source checked: {result['checked_at']} | sample size: unknown",
        'Category | Published name/vector | Rank | Source-reported %',
        '--- | --- | ---: | ---:']
    for category, recs in result['distributions'].items():
        for rec in recs[:top]:
            name = '/'.join('?' if v is None else str(v) for v in rec['stat_vector']['values']) if category=='spread' else rec['original_name']
            value = str(rec['reported_percentage']) if rec['reported_percentage'] is not None else 'unavailable'
            lines.append(f"{category} | {name} | {rec['rank']} | {value}")
    if result.get('teammate_context'):
        lines.append('Teammate-conditioned estimates: unavailable_joint_data (displayed distributions remain marginals).')
    lines.append('No published denominators/effective sample sizes; no inferred confidence intervals, joint builds, or lift.')
    return '\n'.join(lines)
