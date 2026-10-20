"""Versioned observed configurations: equality is not proof of Exact Build equality."""
from collections import Counter
from itertools import combinations
import json
from pathlib import Path

from metagame.common import encode, sha

VERSION = 'observed-configuration-v3'
FIELDS = ('moves', 'item', 'ability', 'nature', 'sp')
STATS = ('hp', 'atk', 'def', 'spa', 'spd', 'spe')


def definition_digest():
    return sha(encode({p:sha(Path(__file__).with_name(p).read_bytes())
                       for p in ('observed.py','publication_families.py')}).encode())


def eligibility(member):
    n = member['normalized']
    issues = member['issues']
    def uncontested(field):
        return not any(field in issue or 'build_export_disagreement' in issue for issue in issues)
    result = {f: bool(n[f]) and uncontested(f) for f in ('item', 'ability', 'nature')}
    result['moves'] = (len(n['moves']) == 4 and None not in n['moves']
                       and len(set(n['moves'])) == 4 and uncontested('move'))
    valid_sp = (n['sp']['kind'] == 'champions_sp' and uncontested('sp')
                and member['stat_validation'].get('validation') not in ('invalid', 'invalid_under_pinned_profile'))
    result['sp'] = valid_sp and all(v is not None for v in n['sp']['values'])
    for i, stat in enumerate(STATS):
        result['sp_' + stat] = valid_sp and n['sp']['values'][i] is not None
    return result


def observation(canonical):
    members = []
    for m in canonical['members']:
        # Retain unresolved assertions in identity: different unknown names must
        # not collapse simply because both fail canonical name resolution.
        members.append(dict(configuration=m['normalized'], eligible=eligibility(m),
            missing=sorted(m['missing']), issues=sorted(m['issues']),
            unresolved={k: m['original'].get(k) for k in ('species', 'item', 'ability', 'nature', 'moves')
                        if m['normalized'].get(k) is None or k == 'moves' and None in m['normalized']['moves']},
            unsupported=m['original'].get('unsupported_fields', [])))
    payload = dict(version=VERSION, strict_identity_version=canonical['version'],
                   members=sorted(members, key=encode), conflicts=sorted(canonical['conflicts']))
    return dict(signature=sha(encode(payload).encode()), version=VERSION, payload=payload)


def distinct(rows, *, with_audit=False):
    from .publication_families import families
    groups = {}
    roster_eligible=[]
    for r in rows:
        c = json.loads(r['canonical'])
        if not 1<=len(c['members'])<=6 or c.get('composition_conflicting'):
            continue
        roster_eligible.append(r)
    resolved,audit=families(roster_eligible)
    for representative,publications in resolved:
        c=json.loads(representative['canonical'])
        groups.setdefault(observation(c)['signature'], []).extend(publications)
    return (groups,audit) if with_audit else groups


def query(root, species, *, source, population, regulation, battle_format='Doubles',
          teammates=(), exclude_teammates=(), given_move=None, move_pair=None,
          version=None, min_multiple_context=5):
    from .canonical import Canonicalizer
    from .store import Teams
    from .query import ratio, _links
    from . import VERSION as STRICT_VERSION
    if not source:
        raise ValueError('Observed-configuration statistics require an explicit source')
    c = Canonicalizer()
    def resolve(name, kind='species'):
        value = c.names.resolve(name, kind)['canonical_id']
        if value is None: raise ValueError('Unknown/ambiguous ' + kind + ': ' + name)
        return value
    target = resolve(species)
    mates = [resolve(t) for t in teammates]
    excluded = [resolve(t) for t in exclude_teammates]
    if target in mates or target in excluded or len(set(mates)) != len(mates) or set(mates) & set(excluded):
        raise ValueError('Invalid teammate context')
    move = resolve(given_move, 'move') if given_move else None
    pair = [resolve(v, 'move') for v in move_pair] if move_pair else None
    if pair and (len(pair) != 2 or pair[0] == pair[1]): raise ValueError('Two distinct moves required')
    db = Teams(root, readonly=True)
    try: rows = [r for r in db.scoped(population, regulation, battle_format, version or STRICT_VERSION) if r['source_id'] == source]
    finally: db.close()
    groups, family_audit = distinct(rows,with_audit=True)
    containing = []; selected = []
    for signature, publications in groups.items():
        data = json.loads(publications[0]['canonical'])
        roster = [m['normalized']['species'] for m in data['members'] if m['normalized']['species']]
        if target not in roster: continue
        containing.append(signature)
        if (mates or excluded) and not data['composition_complete']:continue
        if all(t in roster for t in mates) and not any(t in roster for t in excluded):
            selected.append((signature, publications, data))
    result = dict(source=source, population=population, regulation=regulation, format=battle_format,
        observation_unit='distinct_observed_configuration', observation_version=VERSION,
        algorithm_version=version or STRICT_VERSION, total_eligible_designs=len(groups),
        species_designs=len(containing), context_designs=len(selected), species=target,
        conditioning_teammates=mates, excluded_teammates=excluded, given_move=move,
        source_publications=len({r['source_key'] for r in rows}),
        publication_family_audit=family_audit,
        incomplete_roster_publication_revisions=sum(not json.loads(r['canonical'])['composition_id'] or
            json.loads(r['canonical']).get('composition_conflicting', False) for r in rows),
        context_requires_complete_roster=bool(mates or excluded),
        incomplete_roster_context_exclusions=sum(1 for group in groups.values()
            if (mates or excluded) and not json.loads(group[0]['canonical'])['composition_complete'] and
            any(m['normalized']['species']==target for m in json.loads(group[0]['canonical'])['members'])),
        signatures=[dict(signature=s, represented_publications=len(p), source_links=_links(p)) for s,p,d in selected],
        source_links=_links([r for s,p,d in selected for r in p]),
        field_distributions={}, field_eligibility={},
        interpretation='Observed-configuration diversity; SP-unknown signatures may conceal different Exact Builds. Publication counts are not weights.',
        status='observed_design_frequencies' if selected else 'insufficient_data')
    if len(mates) > 1 and len(selected) < min_multiple_context:
        result.update(status='insufficient_multiple_teammate_sample', minimum_required=min_multiple_context)
        return result
    targets = []
    for signature, publications, data in selected:
        mons = [m for m in data['members'] if m['normalized']['species'] == target]
        if len(mons) == 1: targets.append((signature, mons[0]))
    result['multiple_target_instances_excluded'] = len(selected) - len(targets)
    fields = FIELDS + tuple('sp_' + s for s in STATS)
    for field in fields:
        eligible = [(s,m) for s,m in targets if eligibility(m)[field] and
                    (not move or eligibility(m)['moves'] and move in m['normalized']['moves'])]
        n = len(eligible)
        result['field_eligibility'][field] = dict(eligible_distinct_records=n,
            excluded_or_incomplete_records=len(selected)-n, context_records=len(selected))
        count = Counter()
        for s,m in eligible:
            mon = m['normalized']
            values = mon['moves'] if field == 'moves' else [mon['sp']['values'][STATS.index(field[3:])]] if field.startswith('sp_') else [mon[field]]
            count.update(set(encode(v) for v in values))
        result['field_distributions'][field] = [dict(value=json.loads(v), **ratio(k,n),
            **result['field_eligibility'][field]) for v,k in sorted(count.items(),key=lambda x:(-x[1],x[0]))]
    moves_eligible = [m['normalized']['moves'] for s,m in targets if eligibility(m)['moves'] and
                      (not move or move in m['normalized']['moves'])]
    result['move_move_associations'] = [dict(moves=list(p), **ratio(k,len(moves_eligible)))
        for p,k in sorted(Counter(p for moves in moves_eligible for p in combinations(moves,2)).items())]
    if pair: result['requested_move_pair'] = dict(moves=pair, **ratio(sum(all(v in m for v in pair) for m in moves_eligible),len(moves_eligible)))
    return result
