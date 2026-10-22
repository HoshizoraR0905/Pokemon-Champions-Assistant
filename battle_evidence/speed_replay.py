"""Causal selection and compact deterministic domains, without video or Bayesian work."""
from bisect import bisect_right
from copy import deepcopy
from functools import lru_cache
import json
import math

from knowledge.stat_feasibility import champions_attainable_stats
from speed_order.core import ABILITIES, ITEMS, identity_key, knowledge, name
from speed_order.mechanics import NEUTRAL_ABILITIES, mega_stones
from speed_order import infer_speed
from knowledge.stat_feasibility import summary
from .speed_items import item_classes

VERSION = 'real-speed-replay-v1'


def available_time(row):
    """Use the latest required source/uncertainty bound, never an invented early time."""
    values = [row.get('timestamp')]
    if row.get('time_interval') is not None:
        interval = row['time_interval']
        if len(interval) != 2 or interval[0] > interval[1]:
            raise ValueError('Invalid evidence time interval')
        values.append(interval[1])
    if row.get('available_at') is not None:
        values.append(row['available_at'])
    values += [s['timestamp'] for s in row.get('sources', []) if s.get('timestamp') is not None]
    values = [v for v in values if v is not None]
    if not values:
        return None
    if any(type(v) not in (int,float) or not math.isfinite(v) or v < 0 for v in values):
        raise ValueError('Finite nonnegative evidence times required')
    return max(values)


class TimeIndex:
    """Immutable indexed rows; equal-time rows use stable input order."""
    def __init__(self, rows, *, key='timestamp'):
        self.rows = sorted(deepcopy(rows), key=lambda r:r[key])
        self.times = [r[key] for r in self.rows]
        if any(type(t) not in (int,float) or not math.isfinite(t) or t < 0 for t in self.times):
            raise ValueError('Invalid timeline timestamp')

    def at(self, timestamp):
        if type(timestamp) not in (int,float) or not math.isfinite(timestamp):
            raise ValueError('Finite seek timestamp required')
        i = bisect_right(self.times, timestamp) - 1
        return deepcopy(self.rows[i]) if i >= 0 else None


def causal_state(snapshot, timestamp, event_times):
    """Saved StateEngine facts are reusable only with contemporaneous source IDs."""
    if snapshot.get('timestamp') is not None and snapshot['timestamp'] > timestamp:
        raise ValueError('A future saved state is not a historical snapshot')
    def visit(obj):
        if isinstance(obj, list):
            return [visit(v) for v in obj]
        if not isinstance(obj, dict):
            return deepcopy(obj)
        if 'known' in obj:
            ids = obj.get('event_ids', [])
            valid = bool(ids) and all(eid in event_times and event_times[eid] is not None
                                      and event_times[eid] <= timestamp for eid in ids)
            if not obj['known'] or not valid:
                return dict(known=False,value=None,event_ids=[],knowledge='unknown',
                            continuity='No certified fact with complete provenance at this time')
        return {k:visit(v) for k,v in obj.items()}
    result = visit(snapshot.get('observable', {}))
    # Never expose a not-yet-observed individual merely because a later saved
    # state allocated an instance record for it.
    def known(obj):
        if isinstance(obj,dict):
            return obj.get('known') is True or any(known(v) for v in obj.values())
        if isinstance(obj,list):
            return any(known(v) for v in obj)
        return False
    result['pokemon'] = {iid:p for iid,p in result.get('pokemon', {}).items() if known(p)}
    return result


@lru_cache(maxsize=256)
def _legal(identity):
    entity = knowledge().entities[identity]
    result = champions_attainable_stats(identity=identity, form='as_named' if entity.form_id else 'base', stat='speed')
    if result['joint_feasible'] is None:
        raise ValueError(str(result['diagnostics']))
    return result


def legal_projection(identity):
    return deepcopy(_legal(identity))


@lru_cache(maxsize=512)
def _universe(identity, ability, item, max_configurations):
    kb = knowledge(); fact = kb.facts['pokemon'].get(identity, {})
    legal = _legal(identity)
    native = fact.get('ability_names', [])
    abilities = [name(ability,'ability')] if ability else sorted(set(native))
    items = [name(item,'item')] if item else ([fact['required_item']] if fact.get('required_item') else
            ['none'] + sorted({name(i,'item') for i in kb.facts['items']}))
    training_count = sum(len(b['stat_point_domains']['speed']) for b in legal['configurations']['branches'])
    classes=item_classes(identity,items)
    representatives=[c['representative'] for c in classes]
    count = training_count * len(abilities) * len(classes)
    reasons = []
    if not abilities:
        reasons.append('native_ability_catalog_missing')
    if not set(abilities) <= set(native):
        reasons.append('observed_ability_replacement_requires_history')
    if fact.get('required_item') and items != [fact['required_item']]:
        reasons.append('current_form_item_conflict')
    from speed_order.mechanics import ordering_coverage
    unsupported_abilities = sorted(set(abilities) - ABILITIES - NEUTRAL_ABILITIES - set(ordering_coverage()['neutral_abilities']))
    unsupported_items = sorted(set(representatives) - ITEMS - mega_stones() - {'Focus Sash','Quick Claw'})
    if unsupported_abilities:
        reasons.append('legal_ability_branches_outside_v2_subset')
    if unsupported_items:
        reasons.append('legal_item_branches_outside_v2_subset')
    if count > max_configurations:
        reasons.append('configuration_product_exceeds_v2_limit')
    return dict(identity=identity, legal_unmodified_speed=deepcopy(legal['joint_feasible']),
                configuration_count=count, training_projection_count=training_count,
                underlying_item_configuration_count=training_count*len(abilities)*len(items),
                item_equivalence_classes=classes,item_representatives=representatives,
                abilities=abilities, items=items, supported_enumeration=not reasons,
                unresolved_reasons=reasons, unsupported_abilities=unsupported_abilities,
                unsupported_items=unsupported_items, training_domain_ref=identity,
                scope='Complete factorized SP/alignment/native-ability/catalog-item projection with exact Speed/order item equivalence; '
                      'ability suppression/transfer and action-time modifiers remain separate, not neutral',
                legality_scope=legal['provenance']['legality_scope'])


def universe(identity, *, ability=None, item=None, max_configurations=100000):
    if type(max_configurations) is not int or not 1 <= max_configurations <= 100000:
        raise ValueError('v2 supports at most 100000 configurations')
    return deepcopy(_universe(identity, ability, item, max_configurations))


def current_identity(mon):
    fact = mon.get('form', {})
    if fact.get('known') is not True:
        return None
    identity = fact['value']
    if not isinstance(identity,str):
        return None
    # Unlike an arbitrary species-only alias, this field is an observed form
    # contract from the saved StateEngine, not a roster inferred as base form.
    return identity_key(identity, 'as_named' if identity.startswith(('pokeapi:pokemon:','pokeapi:form:')) else 'base')


def canonical_fact(fact):
    if not isinstance(fact,dict) or fact.get('known') is not True:
        return None
    value = fact.get('value')
    return value.get('canonical_id') if isinstance(value,dict) else value


def possible_forms(mon):
    """Retain catalog form alternatives when observed species does not fix form."""
    current=current_identity(mon)
    if current:
        return [current]
    species=canonical_fact(mon.get('identity'))
    entity=knowledge().entities.get(species)
    if entity is None or entity.kind!='species':
        return []
    return sorted(key for key in knowledge().facts['pokemon'] if key in knowledge().entities
                  and knowledge().entities[key].species_id==entity.species_id)


class DeterministicHistory:
    """Chronological calls to the existing solver, retaining last certified information.

    This ledger does not implement inference itself. Original configurations and
    admitted whole observations are resubmitted to v2 to retain all correlations.
    """
    def __init__(self, configurations, *, profile, max_evaluations=100000, max_branches=4096):
        self.configurations = deepcopy(configurations)
        self.profile = profile; self.max_evaluations = max_evaluations; self.max_branches = max_branches
        self.observations = []; self.seen = {}; self.semantic_seen = {}; self.rows = []; self.last_time = -1
        self.certified = dict(feasible=summary(c['speed'] for c in configurations),
                              configuration_count=len(configurations), status='declared_initial_universe',
                              remaining_abilities=sorted({c['ability'] for c in configurations}),
                              remaining_items=sorted({c['item'] for c in configurations}), tie_compatible=None)

    def submit(self, observation, timestamp):
        if available_time(dict(timestamp=timestamp)) != timestamp or timestamp < self.last_time:
            raise ValueError('Observations must arrive in explicit chronological order')
        token = json.dumps(observation, sort_keys=True, allow_nan=False)
        def constraint_content(value):
            if isinstance(value,dict):
                return {k:constraint_content(v) for k,v in value.items() if k!='evidence'}
            if isinstance(value,list):
                return [constraint_content(v) for v in value]
            return value
        content=constraint_content({k:v for k,v in observation.items() if k!='id'})
        semantic=json.dumps(content,sort_keys=True,allow_nan=False)
        if observation['id'] in self.seen:
            if self.seen[observation['id']] != token:
                raise ValueError('Revised evidence requires a new fingerprinted replay')
            self.last_time=timestamp
            return dict(status='duplicate_ignored', timestamp=timestamp, certified=deepcopy(self.certified))
        if semantic in self.semantic_seen:
            self.seen[observation['id']]=token;self.last_time=timestamp
            return dict(status='duplicate_ignored',timestamp=timestamp,duplicate_of=self.semantic_seen[semantic],
                        certified=deepcopy(self.certified),evidence=deepcopy(observation['evidence']))
        previous = deepcopy(self.certified)
        attempted = self.observations + [deepcopy(observation)]
        result = infer_speed(schema_version=2, observations=attempted, configurations=self.configurations,
                             profile=self.profile,max_evaluations=self.max_evaluations,max_branches=self.max_branches)
        accepted = result['status'] in {'exact','empty'}
        if accepted:
            self.observations = attempted
            self.certified = dict(feasible=deepcopy(result['feasible']),
                configuration_count=len(result['compatible_configurations']),status=result['status'],
                remaining_abilities=result['remaining_abilities'],remaining_items=result['remaining_items'],
                tie_compatible=result['tie_compatible'])
        self.seen[observation['id']] = token; self.semantic_seen[semantic]=observation['id'];self.last_time = timestamp
        row = dict(timestamp=timestamp, observation_id=observation['id'], admitted=accepted,
                   status=result['status'], previous=previous, certified=deepcopy(self.certified),
                   narrowed=accepted and (self.certified['feasible']['values'] != previous['feasible']['values']
                                         or self.certified['configuration_count'] < previous['configuration_count']),
                   exclusions=result.get('exclusions',[]), conflict=result.get('conflict'),
                   diagnostics=result.get('diagnostics',[]), work=result.get('work',{}))
        self.rows.append(deepcopy(row))
        return row

    def at(self, timestamp):
        row = TimeIndex(self.rows).at(timestamp)
        return row
