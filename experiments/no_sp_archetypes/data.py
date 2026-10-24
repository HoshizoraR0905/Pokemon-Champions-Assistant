"""Read-only partial observations and connected provenance groups.

Reuse canonical IDs, eligibility, stat validation and native-ability checks.
Missing fields stay unknown; SP is retained as source evidence, never imputed.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import re
from pathlib import Path

from knowledge.champions_stats import ChampionsStats, STATS, validate_training_points
from metagame.common import encode, sha
from metagame.published import VERSION
from metagame.published.observed import eligibility
from metagame.published.speed_support import alignment
from metagame.published.store import Teams
from speed_order.core import knowledge, name
from speed_order.forms import published_ability

TARGET = 'pokeapi:species:727'


def sp_status(member):
    n = member['normalized']; sp = n['sp']; values = sp.get('values', [])
    validation = member.get('stat_validation', {}).get('validation')
    issues = member.get('issues', [])
    if validation in ('invalid', 'invalid_under_pinned_profile') or any('invalid_stat' in i or 'invalid_sp' in i for i in issues):
        return 'invalid_sp'
    if any(re.search(r'(^|[_:])sp([_:]|$)', i) or 'build_export_disagreement' in i for i in issues):
        return 'conflicting_sp'
    if not values or all(v is None for v in values):
        return 'missing_sp'
    if sp.get('kind') != 'champions_sp':
        return 'unsupported_sp_kind'
    if len(values) != 6 or any(v is None for v in values):
        return 'partial_sp'
    try:
        validate_training_points(dict(zip(STATS, values)))
    except ValueError:
        return 'invalid_sp'
    return 'valid_sp'


def compatibility(member):
    """Assess known identity, ability and required-stone assertions without SP.

    This does not certify learnsets or general item availability. Canonical data
    and the existing native-ability/required-item facts set the supported scope.
    """
    n = member['normalized']; issues = []
    kb = knowledge(); species = n['species']
    if not species or species not in kb.entities:
        return ['unresolved_species_form']
    if n.get('ability') and eligibility(member)['ability']:
        try:
            published_ability(species, n['ability'], species)
        except (ValueError, KeyError, NotImplementedError):
            issues.append('form_ability_incompatibility')
    if n.get('item') and eligibility(member)['item']:
        try:
            item = name(n['item'], 'item')
        except ValueError:
            return issues + ['unresolved_item']
        required = kb.facts['pokemon'].get(species, {}).get('required_item')
        stone_forms = [f for f, fact in kb.facts['pokemon'].items() if fact.get('required_item') == item]
        # Same species/form required-stone policy as complete-core compatibility.
        if (required and item != required) or (stone_forms and not any(kb.entities[f].species_id == kb.entities[species].species_id for f in stone_forms)):
            issues.append('form_item_incompatibility')
    return issues


def reasons(member):
    result = []
    status = sp_status(member)
    if status != 'valid_sp': result.append(status)
    valid = eligibility(member)
    for field, key in [('moves', 'missing_or_conflicting_moves'), ('item', 'missing_or_conflicting_item'),
                       ('nature', 'missing_or_conflicting_nature'), ('ability', 'missing_or_conflicting_ability')]:
        if not valid[field]: result.append(key)
    result += compatibility(member)
    for issue in member['issues']:
        if not any(key in issue for key in ('sp', 'stat_vector', 'move', 'item', 'nature', 'ability', 'species')):
            result.append('other_adapter_conflict')
    return sorted(set(result))


def application_eligible(member):
    n = member['normalized']
    if n['species'] != TARGET or sp_status(member) == 'valid_sp' or not eligibility(member)['moves'] or compatibility(member):
        return False
    # SP defects are the application condition; other contradictory assertions
    # cannot be resolved by dropping them. Missing item/nature/ability is allowed.
    return not any(not (re.search(r'(^|[_:])sp([_:]|$)', i) or 'stat_vector' in i) for i in member['issues'])


def publications(database):
    db = Teams(database, readonly=True)
    try:
        return sorted((dict(p) for p in db.scoped('tournament_published', 'M-C', 'Doubles', VERSION)
                       if p['source_id'] == 'vgcmulticalc'), key=lambda p: p['id'])
    finally:
        db.close()


def observable_team_signature(canonical):
    members = canonical['members']
    if len(members) != 6 or not all(m['normalized']['species'] and eligibility(m)['moves'] for m in members):
        return None
    # Deliberately excludes SP: identical observed team exports can occur once
    # with SP and once without it. Unknown optional fields do not become wildcards.
    return sha(encode(sorted(({k: m['normalized'][k] for k in ('species', 'moves', 'item', 'ability', 'nature')}
                            for m in members), key=encode)).encode())


def publication_keys(p, c):
    keys = [(k, p[k]) for k in ('id', 'source_key', 'source_url', 'record_sha256') if p.get(k)]
    if c.get('exact_build_id'): keys.append(('exact_team', c['exact_build_id']))
    signature = observable_team_signature(c)
    if signature: keys.append(('observable_team_without_sp', signature))
    return keys


def connected_groups(keys_by_id):
    parent = {pid: pid for pid in keys_by_id}
    def find(pid):
        while parent[pid] != pid:
            parent[pid] = parent[parent[pid]]; pid = parent[pid]
        return pid
    seen = {}
    for pid, keys in sorted(keys_by_id.items()):
        for key in keys:
            if key in seen:
                a, b = find(pid), find(seen[key]); parent[max(a, b)] = min(a, b)
            else: seen[key] = pid
    groups = defaultdict(list)
    for pid in parent: groups[find(pid)].append(pid)
    ids = {root: sha(encode(sorted(pids)).encode())[:24] for root, pids in groups.items()}
    return {pid: ids[find(pid)] for pid in parent}


def adapt_publications(pubs):
    all_rows, keys, source_audit, team_sp = [], {}, Counter(), Counter()
    for p in pubs:
        c = json.loads(p['canonical']); keys[p['id']] = publication_keys(p, c)
        statuses = [sp_status(m) for m in c['members']]
        team_sp['all_six_valid_sp' if len(statuses)==6 and all(s=='valid_sp' for s in statuses)
                else 'all_six_missing_sp' if len(statuses)==6 and all(s=='missing_sp' for s in statuses)
                else 'mixed_partial_or_invalid'] += 1
        for ordinal, m in enumerate(c['members']):
            n = m['normalized']; valid = eligibility(m); status = sp_status(m)
            original_id = f"{p['id']}:{p['extraction_id']}:member:{ordinal}"
            why = reasons(m)
            points = dict(zip(STATS, n['sp']['values'])) if status == 'valid_sp' else None
            calculated = None
            if points is not None and valid['nature'] and n['species']:
                try:
                    calculated = ChampionsStats(n['species'], form='as_named' if knowledge().entities[n['species']].form_id else 'base').calculate(points, alignment(n['nature']))
                except (ValueError, KeyError, NotImplementedError):
                    why.append('unsupported_stat_calculation')
            complete = bool(m['exact_complete'] and calculated is not None)
            source_audit['member_records'] += 1
            source_audit[status] += 1
            source_audit['complete_adapter' if complete else 'incomplete_adapter'] += 1
            for reason in why: source_audit['reason:'+reason] += 1
            all_rows.append(dict(empirical_record_id='vgc-occurrence:'+original_id,
                original_record_ids=[original_id], publication_id=p['id'], member_ordinal=ordinal,
                extraction_id=p['extraction_id'], source_url=p['source_url'], source_key=p['source_key'],
                source_title=p['title'], record_sha256=p.get('record_sha256'),
                species=n['species'], configuration=deepcopy(n), original=deepcopy(m['original']),
                training_points=points, item=n['item'] if valid['item'] else None,
                ability=n['ability'] if valid['ability'] else None, nature=n['nature'] if valid['nature'] else None,
                sp_status=status, complete=complete, reasons=why, issues=m['issues'],
                application_eligible=application_eligible(m),
                observed_team_signature=c.get('exact_build_id'),
                observable_team_signature=observable_team_signature(c),
                team_composition=c.get('composition'),
                teammates=[dict(ordinal=j,normalized=deepcopy(t['normalized']),original=deepcopy(t['original']),
                                issues=t['issues'], source_url=p['source_url']) for j,t in enumerate(c['members']) if j != ordinal]))
    groups = connected_groups(keys)
    for row in all_rows: row['evaluation_group'] = groups[row['publication_id']]
    return all_rows, dict(counts=dict(source_audit), teams_by_sp_status=dict(team_sp),
                          publications=len(pubs), connected_publication_groups=len(set(groups.values())))


def split_application(rows, training):
    train_groups = {r['evaluation_group'] for r in training}
    train_keys = defaultdict(set)
    for r in training:
        for field in ('publication_id', 'source_url', 'source_key', 'record_sha256', 'observed_team_signature', 'observable_team_signature'):
            if r.get(field): train_keys[(field, r[field])].add(r['empirical_record_id'])
    application = []
    for r in rows:
        if not r['application_eligible']: continue
        r = deepcopy(r)
        matches = {field: sorted(train_keys[(field,r[field])]) for field in ('publication_id','source_url','source_key','record_sha256','observed_team_signature','observable_team_signature') if r.get(field) and (field,r[field]) in train_keys}
        r['source_overlap'] = dict(direct=matches, connected=r['evaluation_group'] in train_groups)
        r['primary_independent_pool'] = not r['source_overlap']['connected']
        application.append(r)
    return application
