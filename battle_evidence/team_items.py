"""Initial-loadout all-different constraint; current possession is separate.

Domains are correlated by a bipartite matching relation, never by a product of
per-member marginals. `none` has unlimited capacity. Scope is (battle, side).
Only explicitly reviewed original assignments reserve an item for an actor.
"""
from copy import deepcopy

RULE_ID = 'champions-reviewed-item-clause-v1'


def scope(battle_id, individual):
    prefix = battle_id + ':'
    if not individual.startswith(prefix):
        raise ValueError('Team actor must have a battle-scoped stable identity')
    side = individual[len(prefix):].split(':')[0]
    if side not in {'self', 'opponent'}:
        raise ValueError('Unknown team side')
    return battle_id, side


def original_assignments(events, *, battle_id, individual, at):
    if not any(e['kind'] == 'initial_held' and e['battle_id'] == battle_id for e in events):
        return {}
    target = scope(battle_id, individual)
    claims = {}
    for e in events:
        if e['kind'] != 'initial_held' or e['battle_id'] != battle_id or e['available_at'] > at:
            continue
        if scope(e['battle_id'], e['individual']) != target:
            continue
        if (e.get('team_rule') != RULE_ID or not e.get('reviewer') or not e.get('sources')
                or not e.get('initial_ownership_review', {}).get('unchanged_since_start')
                or e['available_at'] < e['timestamp']):
            raise ValueError('Original ownership requires source-reviewed continuity and a scoped rule')
        actor = e['individual']
        if actor in claims and claims[actor] != e['item']:
            raise ValueError('Conflicting original item assignment')
        claims[actor] = e['item']
    return claims


def exclusions(events, *, battle_id, individual, at):
    claims = original_assignments(events, battle_id=battle_id, individual=individual, at=at)
    excluded={item for actor, item in claims.items() if actor != individual and item != 'none'}
    for item,owners in owner_constraints(events,battle_id=battle_id,individual=individual,at=at).items():
        if individual not in owners:excluded.add(item)
    return excluded


def owner_constraints(events, *, battle_id, individual, at):
    constraints={}
    for e in events:
        if e['kind']!='initial_owner_options' or e['battle_id']!=battle_id or e['available_at']>at:continue
        if scope(battle_id,e['individual'])!=scope(battle_id,individual):continue
        owners=set(e['initial_owner_options'])
        if not owners or e.get('team_rule')!=RULE_ID or not e.get('sources') or not e.get('reviewer'):
            raise ValueError('Reviewed initial owner alternatives required')
        if any(scope(battle_id,a)!=scope(battle_id,individual) for a in owners):raise ValueError('Owner alternative crosses team scope')
        constraints[e['item']]=owners & constraints.get(e['item'],owners)
    return constraints


def matching(domains, fixed=None, *, reservations=None):
    """One complete legal extension, or None; augmenting paths, not enumeration."""
    domains = {a: set(v) for a, v in domains.items()}
    reservations=reservations or {}
    for item,actors in reservations.items():
        for actor in domains:
            if actor not in actors:domains[actor].discard(item)
    if fixed:
        actor, item = fixed
        if item not in domains.get(actor, set()):
            return None
        domains[actor] = {item}
    # First cover mandatory item vertices with distinct allowed actors, then
    # augment unmatched actors. Augmentation cannot unmatch a mandatory item.
    assigned={}
    def reserve(item,seen):
        for actor in sorted(domains):
            if actor in seen or item not in domains[actor]:continue
            seen.add(actor)
            if actor not in assigned or reserve(assigned[actor],seen):
                assigned[actor]=item;return True
        return False
    for item in sorted(reservations):
        if not reserve(item,set()):return None
    owners = {item:actor for actor,item in assigned.items()}

    def visit(actor, seen):
        for item in sorted(domains[actor]):
            key = ('none', actor) if item == 'none' else item
            if key in seen:
                continue
            seen.add(key)
            if key not in owners or visit(owners[key], seen):
                owners[key] = actor
                return True
        return False

    for actor in sorted(domains, key=lambda a: len(domains[a])):
        if actor in owners.values():continue
        if not visit(actor, set()):
            return None
    return {actor: 'none' if isinstance(item, tuple) else item for item, actor in owners.items()}


def propagate(domains, *, enabled, reservations=None):
    """Each retained edge has a complete matching; keep this shared relation.

    Consumers selecting multiple members MUST call matching with the restricted
    domains; surviving marginal edges cannot be freely combined.
    """
    if not enabled:
        return {a: sorted(set(v)) for a, v in domains.items()}
    return {a: [i for i in sorted(set(v)) if matching(domains, (a, i),reservations=reservations) is not None]
            for a, v in domains.items()}


def restrict_rows(rows, allowed):
    allowed = set(allowed); result = []
    for c in rows:
        items = [i for i in c.get('item_options', [c['item']]) if i in allowed]
        if not items:
            continue
        row = dict(c, item=items[0])
        if 'item_options' in c:
            row['item_options'] = items
        result.append(row)
    return result


def ownership_rows(rows,events,*,battle_id,individual,at):
    """Conditional transfer-source ability, not an observed ability assertion."""
    result=[]
    for c in rows:
        allowed=set(c.get('item_options',[c['item']]))
        for e in events:
            if e['kind']!='initial_owner_options' or e['battle_id']!=battle_id or e['available_at']>at:continue
            required=e.get('owner_requirements',{}).get(individual,{})
            if required.get('ability') and c['ability']!=required['ability']:allowed.discard(e['item'])
        result.extend(restrict_rows([c],allowed))
    return result


def restrict_result(result, allowed, *, reasons):
    from damage.joint import _joint_result
    from time import perf_counter
    rows = restrict_rows(result['configurations'], allowed)
    unknown = {cid for u in result['unresolved'] for cid in u.get('configuration_ids', [u['id']])}
    refined = _joint_result(rows, result['updates'], result['unresolved'], unknown,
                            result['requirements'].get('exhaustive', False),
                            result['work']['forward_evaluations'], result['work']['cached_inputs'], perf_counter())
    for key in ('work', 'item_policy', 'item_evidence'):
        if key in result:
            refined[key] = deepcopy(result[key])
    refined['team_item_constraint'] = dict(rule=RULE_ID, excluded_items=sorted(reasons),
        reason='Excluded by team-wide item uniqueness evidence.', initial_loadout=True)
    if 'item_policy' in refined:
        for key in ('dormant', 'retained', 'rescued'):
            refined['item_policy'][key] = [i for i in refined['item_policy'].get(key, []) if i not in reasons]
    return refined
