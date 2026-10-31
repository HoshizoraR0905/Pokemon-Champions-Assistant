"""Read-only adaptation of the established canonical population; no collection."""
from copy import deepcopy
import hashlib
from battle_evidence.vgc_population import load_vgc
from battle_evidence.empirical_measure import catalog, template, full_record_signature, digest
from .core import sp_array, moves

SPECIES = {'Hatterene': 'pokeapi:species:858', 'Incineroar': 'pokeapi:species:727',
           'Mega Raichu Y': 'pokeapi:form:10530'}


def prepare(database_root):
    population = load_vgc(database_root)
    training, exclusions = [], []
    # Own-form selection prevents base/Mega adapters counting an occurrence twice
    # in the global association population. Context pooling is only for targets.
    for form in sorted(population['by_form']):
        c = catalog(population, form)
        exclusions.extend(dict(context=form, **e) for e in c['core_ineligible'])
        for row in c['frequency_rows']:
            if row['species'] == form and template(row)['complete']:
                sp_array([row]); moves(row)
                training.append(deepcopy(row))
    targets, audit = {}, {}
    for label, form in SPECIES.items():
        c = catalog(population, form)
        targets[label] = [deepcopy(r) for r in c['frequency_rows'] if template(r)['complete']]
        audit[label] = dict(form=form, occurrences=len(targets[label]),
                            excluded_cores=c['core_ineligible'],
                            incomplete_moves_excluded=sum(not template(r)['complete'] for r in c['frequency_rows']),
                            compatible_form_policy=c['grouping'])
    # Include compatible base→Mega observations if absent from own-form eligible
    # pool; still exactly once by immutable occurrence ID, with no field mutation.
    ids = {r['empirical_record_id'] for r in training}
    for rows in targets.values():
        for row in rows:
            if row['empirical_record_id'] not in ids:
                training.append(deepcopy(row)); ids.add(row['empirical_record_id'])
    training.sort(key=lambda r: r['empirical_record_id'])
    if len(training) != len({r['empirical_record_id'] for r in training}):
        raise ValueError('An occurrence entered the population twice')
    groups = source_groups(training)
    for row in training:
        row['evaluation_group'] = groups[row['empirical_record_id']]
    for rows in targets.values():
        for row in rows:
            row['evaluation_group'] = groups[row['empirical_record_id']]
    return training, targets, dict(source_scope=population['scope'], targets=audit,
                                  association_occurrences=len(training),
                                  evaluation_groups=len(set(groups.values())),
                                  core_exclusions=exclusions,
                                  association_filter='complete compatible joint core and exactly four uncontested moves; one entry per immutable occurrence ID')


def source_groups(rows):
    """Conservative connected groups across publication, URL, key and full team.

    Equality groups are evaluation-only: empirical observations are never removed.
    Exact complete team equality is useful protection against reposted teams.
    Incomplete team composition signatures can overgroup: disclose this limit.
    """
    parent = list(range(len(rows)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    seen = {}
    for i, row in enumerate(rows):
        keys = [('team', row['observed_team_signature'])]
        for p in row['publications']:
            keys.extend((field, p[field]) for field in ('id', 'source_key', 'url') if p.get(field))
        for key in keys:
            if key in seen:
                a, b = find(i), find(seen[key]); parent[max(a, b)] = min(a, b)
            else:
                seen[key] = i
    members = {}
    for i, row in enumerate(rows):
        members.setdefault(find(i), []).append(row['empirical_record_id'])
    names = {root: digest(sorted(ids)) for root, ids in members.items()}
    return {r['empirical_record_id']: names[find(i)] for i, r in enumerate(rows)}


def fold(group, folds=3):
    return int(hashlib.sha256(('m351:'+group).encode()).hexdigest(), 16) % folds


def core_signature(row):
    return digest({k: v for k, v in row['configuration'].items() if k != 'moves'})
