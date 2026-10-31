"""Versioned knowledge and conservative action/result reconciliation (no inference)."""
from copy import deepcopy
import json
from pathlib import Path
from .battle_state import fact, Fact
from dataclasses import asdict

RULE_PATH = Path(__file__).resolve().parents[1] / 'data/move_mechanics_v1.json'


def attach_verified_profile(state, configuration, roster_review, *, root):
    """Opt-in existing user-confirmed exact-six build binding, not identity merging."""
    import hashlib
    expected = [m['species_id'] for m in configuration['members']]
    policy = configuration.get('binding_policy', {})
    if (not configuration.get('complete') or len(set(expected)) != 6
            or roster_review.get('battle_id') != state.battle_id
            or sorted(roster_review.get('species_ids', [])) != sorted(expected)
            or roster_review.get('matches_team7') is not True or not roster_review.get('reviewer')
            or policy.get('asserted_by') != 'user' or not policy.get('statement')):
        raise ValueError('Verified complete roster and user same-build policy required')
    image = Path(root) / roster_review['image']
    if hashlib.sha256(image.read_bytes()).hexdigest() != roster_review['sha256']:
        raise ValueError('Roster source fingerprint mismatch')
    state = deepcopy(state)
    state.knowledge['verified_team_profile'] = dict(configuration=deepcopy(configuration),
        roster_review=deepcopy(roster_review), binding_policy=deepcopy(policy))
    return state


def bind_attached_profile(state, p, event):
    """Attach only after an observed self entry; runtime needs no network/files."""
    attachment = state.knowledge.get('verified_team_profile')
    if (not attachment or p.side_id != 'self' or not p.original_identity.known
            or p.pokemon_instance_id in state.knowledge.get('team', {}).get('instances', {})
            or event.attributes.get('observation_time', float('-inf')) < attachment['roster_review']['observation_time']):
        return
    configuration = deepcopy(attachment['configuration'])
    candidates = [m for m in configuration['members'] if m['species_id'] == p.original_identity.value.get('species_id')]
    if len(candidates) != 1:
        return
    member = candidates[0]
    configuration['sources'].append(dict(roster_review=deepcopy(attachment['roster_review']),
        binding_policy=deepcopy(attachment['binding_policy']), entry_event_id=event.event_id))
    # initialize_team owns reconciliation and configured fields. Do not replace
    # the live state object or duplicate its facts in another build database.
    updated = initialize_team(state, configuration, bindings={member['instance_id']:p.pokemon_instance_id})
    state.knowledge['team'] = updated.knowledge['team']
    for name in ('moves', 'ability', 'item', 'hp'):
        setattr(p, name, getattr(updated.pokemon[p.pokemon_instance_id], name))
    from .form_stats import update_stats
    update_stats(state,p,event)


def attach_matching_roster_profile(state, roster, *, root):
    """Use already recognized complete self rows; do not add preview OCR."""
    from team_configuration.profiles import TeamProfiles
    rows={}
    for row in roster:
        if row.get('side')=='self':rows.setdefault(row['preview_row'],[]).append(row)
    reliable=(set(rows)==set(range(1,7)) and all(
        all(r.get('status')=='resolved' and r.get('species_id') and (r.get('species') or {}).get('confidence',0)>=.95 for r in group)
        and len({r['species_id'] for r in group})==1 for group in rows.values()))
    if not reliable:
        state.knowledge['team_profile_linkage']=dict(status='unbound',reason='complete_reliable_self_roster_not_available',self_rows=len(rows))
        return state
    members=sorted(group[0]['species_id'] for group in rows.values())
    profiles=TeamProfiles(Path(root)/'.cache/team-profiles')
    matching=[profiles.load(p['profile_id']).data for p in profiles.list()
              if sorted(m['species_id'] for m in profiles.load(p['profile_id']).data['members'])==members]
    if len(matching)!=1:
        state.knowledge['team_profile_linkage']=dict(status='unbound',reason='no_unique_verified_profile',matches=len(matching))
        return state
    evidence=next(iter(rows.values()))[0]['evidence']
    review=dict(battle_id=state.battle_id,species_ids=members,matches_team7=True,
        reviewer='existing structured self-roster recognition, not independent visual truth',
        image=evidence['image'],sha256=evidence['sha256'],observation_time=max(r['evidence']['timestamp'] for g in rows.values() for r in g))
    state=attach_verified_profile(state,matching[0],review,root=root)
    state.knowledge['team_profile_linkage']=dict(status='existing_complete_self_roster_bound',team_id=matching[0]['team_id'],review=review)
    return state

class MoveKnowledge:
    def __init__(self, path=RULE_PATH):
        self.data = json.loads(Path(path).read_text())
        self.rules = {r['move_id']: r for r in self.data['rules']}
        self.rules.update({r['trigger_id']:r for r in self.data.get('passive_rules',[])})

    def query(self, move_id, profile):
        rule = self.rules.get(move_id)
        return deepcopy(rule) if rule and profile in rule['profiles'] else None


def initialize_team(state, opening, *, saved=None, bindings=None, saved_match_verified=False):
    """Reuse TeamConfiguration v2 fields; only explicit verified instance bindings.

    Species/roster coincidence is insufficient to identify an individual build.
    Opening conflicts remain visible; immutable fields never follow battle changes.
    """
    state = deepcopy(state)
    bindings = bindings or {}
    metadata = state.knowledge.setdefault('team', {'instances': {}, 'reconciliation': []})
    metadata['policy'] = 'Explicit same-individual bindings only; opening direct evidence wins conflicts visibly; verified saved fields fill gaps; battle observations update dynamic facts only.'
    metadata['preview_roster'] = deepcopy(opening['members'])
    metadata['selected_instance_ids'] = list(state.sides['self'].party_instance_ids)
    if saved and not saved_match_verified:
        metadata['reconciliation'].append({'kind': 'saved_configuration_unmatched', 'team_id': saved['team_id'],
            'reason': 'No verified same-individual binding; saved values not imported'})
    saved_by_id = {m['instance_id']: m for m in (saved or {}).get('members', [])}
    for member in opening['members']:
        pid = bindings.get(member['instance_id'])
        if pid is None:
            continue
        p = state.pokemon[pid]
        if p.side_id != 'self' or member.get('species_id') != p.species.value.get('species_id'):
            raise ValueError('configuration_instance_mismatch')
        fields = deepcopy(member['fields'])
        saved_member = saved_by_id.get(member.get('saved_instance_id')) if saved_match_verified else None
        if saved_member:
            if saved_member.get('canonical_identity') != member.get('canonical_identity'):
                raise ValueError('saved_identity_mismatch')
            for name, old in saved_member['fields'].items():
                new = fields.get(name, {})
                if new.get('value') is not None and old.get('value') is not None and (new.get('canonical_id') or new['value']) != (old.get('canonical_id') or old['value']):
                    state.conflicts.append({'kind': 'configuration_conflict', 'instance_id': pid, 'field': name,
                                           'opening': new, 'saved': old})
                elif new.get('value') is None and old.get('status') in {'manual_verified','knowledge_resolved','observed'}:
                    fields[name] = deepcopy(old)
                    fields[name]['reconciliation_source'] = {'team_id':saved['team_id'], 'sources':deepcopy(saved.get('sources',[]))}
        metadata['instances'][pid] = {'configuration_instance_id': member['instance_id'], 'team_id':opening['team_id'], 'fields': fields,
            'stat_alignment':deepcopy(member.get('reviewed_stat_alignment')),
            'canonical_identity': member.get('canonical_identity'), 'sources': deepcopy(opening.get('sources', [])),
            'species_reference': deepcopy(member.get('species_reference', {}))}
        source = {'source_type': 'known_team_configuration', 'instance_id': member['instance_id'],
                  'sources': deepcopy(opening.get('sources', []))}
        for slot in range(1, 5):
            f = fields.get(f'move_{slot}', {})
            if f.get('canonical_id') and f.get('status') in {'observed','manual_verified','knowledge_resolved'} and not f.get('conflicts'):
                previous=p.moves.known_slots.get(str(slot))
                if previous and previous.known and previous.value.get('canonical_id') != f['canonical_id']:
                    state.conflicts.append({'kind':'opening_move_conflict','instance_id':pid,'slot':slot})
                else:
                    p.moves.known_slots[str(slot)] = configured_fact({'canonical_id': f['canonical_id'], 'name': f['value']}, source, previous)
        if len(p.moves.known_slots)==4:
            p.moves.unrevealed_slots=fact(0,source)
        for key, obj, attr in [('ability', p.ability, 'current'), ('held_item', p.item, 'identity')]:
            f = fields.get(key, {})
            if f.get('canonical_id') and f.get('status') in {'observed','manual_verified','knowledge_resolved'} and not f.get('conflicts'):
                existing = getattr(obj, attr)
                if existing.known and (existing.value or {}).get('canonical_id') != f['canonical_id']:
                    state.conflicts.append({'kind': 'opening_dynamic_conflict', 'instance_id': pid, 'field': key})
                else:
                    setattr(obj, attr, configured_fact({'canonical_id': f['canonical_id'], 'name': f['value']}, source, existing))
        hp = fields.get('hp', {})
        if hp.get('value') is not None and hp.get('status') in {'observed','manual_verified','knowledge_resolved'} and not hp.get('conflicts'):
            if p.hp.maximum.known and p.hp.maximum.value != hp['value']:
                state.conflicts.append({'kind': 'configuration_hp_conflict', 'instance_id': pid})
            else:
                p.hp.maximum = configured_fact(hp['value'], source, p.hp.maximum)
    return state


def configured_fact(value, source, previous):
    result=fact(value,source)
    if previous: result.provenance=deepcopy(previous.provenance)+result.provenance
    return result


def ground_event(engine, state, p, event, record):
    """Only confirmed outcomes apply rules; announcements queue expectations.

    Auto association is limited to the latest uninterrupted move action. Explicit
    effect_of links disambiguate more complex sequences; duplicate results require
    an explicit link. Separate unlinked result messages are never guessed duplicates.
    """
    if not state.knowledge.get('move_grounding'):
        return False
    from .state_engine import evidence_link
    ledger = state.knowledge.setdefault('causal_actions', [])
    kind, a = event.event_type, event.attributes
    if kind in {'ability_activation','item_activation','switch_out','send_out','faint'}:
        state.knowledge['association_boundary'] = len(ledger)
    if kind in {'move_execution','ability_activation'}:
        reference_kind = 'move' if kind=='move_execution' else 'ability'
        rule = MoveKnowledge().query(event.canonical_references.get(reference_kind, {}).get('canonical_id'), engine.mechanic_rules.profile_id)
        action = {'event_id': event.event_id, 'instance_id': p.pokemon_instance_id, 'rule': rule,
                  'trigger_kind': kind, 'outcome': a.get('effect_outcome', 'uncertain'), 'effects': {}, 'evidence': evidence_link(event)}
        ledger.append(action)
        if rule and rule['effect_target'] == 'self' and action['outcome'] == 'confirmed' and a.get('interaction_checked') is True:
            for stat, delta in rule['stage_changes'].items():
                apply_effect(engine, state, p, event, record, action, stat, delta)
        return False
    if kind != 'stat_change' or a.get('change') in {'replace','reset'}:
        return False
    explicit = a.get('effect_of')
    candidates = [x for x in ledger if x['event_id'] == explicit] if explicit else ledger[-1:]
    if not explicit and state.knowledge.get('association_boundary', -1) >= len(ledger):
        candidates = []
    action = candidates[0] if len(candidates) == 1 else None
    rule = action.get('rule') if action else None
    stats = a.get('stats', [])
    direction = -1 if a.get('direction') == 'down' or a.get('change') == 'decrement' else 1
    if not rule or action['instance_id'] != p.pokemon_instance_id or rule['effect_target'] != 'self' or any(s not in rule['stage_changes'] or rule['stage_changes'][s]*direction <= 0 for s in stats):
        record.bindings['mechanics'] = {'resolution': 'unresolved', 'reason': 'no_unique_supported_action_rule'}
        return False
    if action['outcome'] in {'failed','blocked','selected'}:
        state.conflicts.append({'event_id': event.event_id, 'kind': 'result_after_failed_action', 'action_id': action['event_id']})
        return False  # Direct observation remains recordable, without rule inference.
    if not stats:
        return False
    if not explicit and any(s in action['effects'] for s in stats):
        record.bindings['mechanics'] = {'resolution': 'unresolved', 'reason': 'independent_or_duplicate_result'}
        state.observations.append({'event_id':event.event_id,'kind':'ambiguous_effect_association','evidence':evidence_link(event)})
        for stat in stats:
            stage=p.stages[stat]
            bounds=deepcopy(stage.interval.value) if stage.interval.known else [-6,6]
            if stage.value.known: bounds=[stage.value.value,stage.value.value]
            # Could corroborate the existing effect or represent another change.
            stage.value=Fact(provenance=[evidence_link(event)])
            stage.interval=fact([bounds[0],6] if direction>0 else [-6,bounds[1]],evidence_link(event),'derived')
        return True
    for stat in stats:
        delta = rule['stage_changes'][stat]
        if a.get('stages') is not None and a['stages'] != abs(delta):
            state.conflicts.append({'event_id': event.event_id, 'kind': 'observed_rule_delta_conflict', 'rule': rule, 'observed': a})
            # Retract the associated generated effect before recording the direct
            # replacement magnitude; it is not a second independent boost.
            for affected in stats:
                receipt=action['effects'].get(affected)
                if receipt:
                    before=receipt['before_stage'];stage=p.stages[affected]
                    stage.value=Fact(**deepcopy(before['value']));stage.interval=Fact(**deepcopy(before['interval']))
                    stage.changes=deepcopy(before['changes'])
                    receipt['resolution']='conflicting_direct_result'
            return False
    for stat in stats:
        if stat in action['effects']:
            action['effects'][stat]['corroborating_evidence'].append(evidence_link(event))
        else:
            apply_effect(engine, state, p, event, record, action, stat, rule['stage_changes'][stat])
    action['outcome'] = 'confirmed'
    record.bindings['mechanics'] = {'action_id': action['event_id'], 'rule_id': rule['rule_id'], 'resolution': 'associated_once'}
    return True


def apply_effect(engine, state, p, event, record, action, stat, delta):
    from .state_engine import evidence_link
    derived = deepcopy(event)
    derived.attributes = {'stats': [stat], 'change': 'increment' if delta > 0 else 'decrement', 'stages': abs(delta)}
    before_stage=asdict(p.stages[stat])
    engine._stats(p, derived)
    stage = p.stages[stat]
    provenance = {'rule': deepcopy(action['rule']), 'rules_profile': engine.mechanic_rules.profile_id,
        'observations': [action['evidence'], evidence_link(event)],
        'resolution': 'exact' if stage.value.known else 'bounded', 'action_id': action['event_id']}
    stage.changes[-1]['mechanics'] = provenance
    stage.value.provenance.append(provenance)
    stage.interval.provenance.append(provenance)
    action['effects'][stat] = {'delta': delta, 'before_stage':before_stage, 'provenance': provenance, 'corroborating_evidence': []}
