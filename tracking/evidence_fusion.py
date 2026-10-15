"""Observation-only HUD fusion and prospective message context; no OCR or sampling."""
from copy import deepcopy
from functools import lru_cache
import math
from knowledge import KnowledgeBase, normalize
from battle_events.parser import EventParser, BattleContext
from .battle_state import PokemonState, Fact, fact


@lru_cache(maxsize=1)
def knowledge():
    return KnowledgeBase()


def identity_evidence(species, icon, previous=None, support=None, *, reliability=False):
    """Validate resolution semantics, not just the resolver's method label.

    Exact is a unique dictionary match, not an icon assertion. A high-confidence
    unique raw canonical name is direct species evidence; weaker exact readings
    need a past consistent reading. Form evidence has stricter requirements.
    """
    species = species or {}; icon = icon or {}
    resolution = species.get('resolution') or {}
    raw = species.get('raw_text') or ''
    confidence = species.get('confidence') or 0
    sid = resolution.get('species_id')
    if resolution.get('status') == 'conflict' or resolution.get('identity_status') == 'conflicting_variant':
        return None, 'conflicting', 'resolver_conflict'
    if resolution.get('status') != 'resolved' or not sid or confidence < .75:
        return None, 'deferred', 'unresolved_or_low_confidence_identity'
    if icon.get('status') == 'resolved' and icon.get('species_id') != sid:
        return None, 'conflicting', 'independent_icon_disagrees'
    if (icon.get('status') == 'resolved' and icon.get('canonical_identity')
            and resolution.get('canonical_identity')
            and icon['canonical_identity'] != resolution['canonical_identity']):
        return None, 'conflicting', 'independent_icon_form_disagrees'
    method = resolution.get('method')
    exact = knowledge().exact['species'].get(normalize(raw), [])
    species_ids = {e.species_id for e in exact}
    unique = species_ids == {sid}
    agreed = (method == 'text_icon_agreement' and icon.get('status') == 'resolved'
              and icon.get('species_id') == sid)
    strong_exact = (method == 'exact' and unique and resolution.get('confidence') == 'strong')
    repeated = (previous and previous.get('raw') == raw and previous.get('species_id') == sid
                and previous.get('status') != 'conflicting' and previous.get('confidence',0) >= .75)
    icon_candidates = icon.get('candidates') or []
    # Provisional high-margin icon corroboration, opt-in and never a form assertion.
    high_margin = (reliability and len(icon_candidates)>=2
        and icon_candidates[0].get('similarity',0)>=.90
        and icon_candidates[0].get('similarity',0)-icon_candidates[1].get('similarity',0)>=.20)
    nickname_icon = (method == 'icon_only' and not exact and confidence >= .95
        and icon.get('status') == 'resolved' and icon.get('species_id') == sid
        and icon_candidates and icon_candidates[0].get('similarity', 0) >= .85
        and (repeated or high_margin))
    corroborated = support and support.get('species_id') == sid and support.get('evidence')
    if not (agreed or nickname_icon or strong_exact and (confidence >= .95 or repeated or corroborated)):
        return None, 'deferred', 'identity_not_independently_supported'
    entity = knowledge().entities.get(f'pokeapi:species:{sid}')
    if entity is None:
        return None, 'deferred', 'unknown_canonical_species'
    ref = dict(canonical_id=entity.canonical_id, species_id=sid, kind='species',
               name=entity.names.get('zh-hans'), knowledge_snapshot=knowledge().snapshot_id,
               identity_status='species_only')
    # A bare name with multiple forms must not assert a default/native form.
    named_forms = {knowledge().identities.for_entity(e).get('canonical_identity') for e in exact}
    variant = resolution.get('canonical_identity')
    observed_form = (agreed or (nickname_icon and repeated)) and icon.get('canonical_identity') == variant
    if variant and (observed_form or named_forms == {variant}):
        ref.update(canonical_identity=variant, identity_status=resolution.get('identity_status'))
    return ref, 'accepted', ('text_icon_agreement' if agreed else 'high_margin_icon_nickname_provisional' if nickname_icon and high_margin and not repeated else 'stable_icon_nickname' if nickname_icon else 'exact_with_prior_named_observation' if corroborated and reliability else 'exact_with_prior_sendout' if corroborated else 'unique_raw_exact')


def hud_transition(engine, state, event, record):
    """Update observed occupancy/HP without asserting a switch, entry, or faint."""
    from .state_engine import Deferred, Contradiction, evidence_link
    a = event.attributes
    if a.get('battle_id') != state.battle_id:
        raise Contradiction('hud_battle_ownership_mismatch')
    if event.side not in state.sides or a.get('slot') not in {'left', 'right'}:
        raise Contradiction('invalid_hud_slot')
    timestamp = a.get('observation_time')
    if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool) or not math.isfinite(timestamp) or timestamp < 0:
        raise Contradiction('invalid_hud_timestamp')
    fusion = state.knowledge.setdefault('hud_fusion', dict(slots={}, aliases={}))
    key = event.side + ':' + a['slot']; previous = fusion['slots'].get(key)
    if previous and timestamp < previous['timestamp']:
        raise Contradiction('hud_time_reversal')
    species = a.get('species') or {}; icon = a.get('icon') or {}
    # A preceding explicit announcement can independently support a weaker exact
    # HUD name. A deferred slot transition does not invalidate its named species.
    support = None
    sid = (species.get('resolution') or {}).get('species_id')
    for earlier in engine.history:
        if state.knowledge.get('reliability_v1') and earlier.application_status=='rejected':continue
        candidate = earlier.bindings.get('resolved_event', earlier.event)
        t = candidate.get('attributes',{}).get('observation_time')
        if (earlier.retracted or not earlier.ordering or not record.ordering
                or earlier.ordering['domain'] != record.ordering['domain']
                or tuple(earlier.ordering['key']) >= tuple(record.ordering['key'])):
            continue
        if ((candidate['event_type']=='send_out' or state.knowledge.get('reliability_v1') and candidate['event_type'] in {'stat_change','ability_activation','move_execution'}) and candidate['side']==event.side
                and (candidate.get('actor') or {}).get('species_id')==sid
                and candidate.get('ocr_confidence') is not None
                and candidate['ocr_confidence']>=(.90 if state.knowledge.get('reliability_v1') and candidate['event_type']!='send_out' else .95)
                and 'explicit_text' in candidate['attributes'].get('side_basis',[])
                and t is not None and 0<=timestamp-t<=30
                and not set(candidate['uncertainty'])-({'actor_variant_unresolved','active_identity_context_unresolved'} if state.knowledge.get('reliability_v1') else {'actor_variant_unresolved'})):
            support = dict(species_id=sid,event_id=candidate['event_id'],
                           evidence=deepcopy(candidate['evidence']),timestamp=t)
    ref, status, reason = identity_evidence(species, icon,
        previous if previous and previous['timestamp'] < timestamp else None, support, reliability=bool(state.knowledge.get('reliability_v1')))

    if (ref and previous and previous['timestamp'] == timestamp
            and previous.get('status') == 'accepted' and previous.get('species_id') != ref['species_id']):
        ref, status, reason = None, 'conflicting', 'simultaneous_slot_identity_disagreement'
    raw_sid = (species.get('resolution') or {}).get('species_id')
    observed = dict(event_id=event.event_id, timestamp=timestamp, raw=species.get('raw_text'),
                    species_id=raw_sid, confidence=species.get('confidence') or 0, status=status, reason=reason, evidence=evidence_link(event), hp=deepcopy(a.get('hp')))
    if support:observed['corroboration'] = support
    fusion['slots'][key] = observed
    outcome = dict(kind='hud_observation', **deepcopy(observed), side=event.side, slot=a['slot'])
    state.observations.append(outcome)
    record.bindings['hud'] = outcome
    if status != 'accepted':
        if status == 'conflicting':
            state.conflicts.append(dict(event_id=event.event_id, reason=reason, proposed_event=event.to_dict(), state_unchanged=True))
        return True
    team = state.sides[event.side]; old_pid = team.active_slots.get(a['slot'])
    current = state.pokemon.get(old_pid)
    if current and state.knowledge.get('reliability_v2'):
        from .evidence_projection import source_times
        last_location=max(source_times(current.location.provenance),default=float('-inf'))
        if any(o.get('kind')=='coverage_gap' and o.get('side') in {event.side,'field','unknown'}
               and o['end']>last_location for o in state.observations):
            # Re-observing the same species after missing coverage does not prove
            # it is the same biological individual. Keep historical revelations.
            current=None
    continuity = a.get('continuity') or {}
    explicit = continuity.get('instance_id') if continuity.get('evidence') else None
    pending = [state.pokemon[x['instance_id']] for x in state.knowledge.get('unplaced_entries',[])
        if x['side']==event.side and x['species_id']==ref['species_id']
        and x.get('timestamp') is not None and x['timestamp']<=timestamp
        and state.pokemon[x['instance_id']].location.value=={'kind':'unplaced_entry','slot':None}]
    if state.knowledge.get('reliability_v2'):
        from .evidence_projection import source_times
        pending=[p for p in pending if not any(o.get('kind')=='coverage_gap'
            and o.get('side') in {event.side,'field','unknown'} and o['end']<=timestamp
            and o['end']>max(source_times(p.location.provenance),default=float('-inf'))
            for o in state.observations)]
    if explicit:
        if explicit not in team.party_instance_ids or state.pokemon[explicit].species.value.get('species_id') != ref['species_id']:
            raise Contradiction('unsupported_hud_continuity_relation')
        p = state.pokemon[explicit]; basis = 'explicit_evidenced_instance_relation'
    elif len(pending)==1:
        p=pending[0];basis='unique_prior_unplaced_entry'
    elif current and current.species.known and current.species.value.get('species_id') == ref['species_id']:
        p = current; basis = 'same_observed_slot_and_species_episode'
    else:
        # team_instance_id from OCR is species matching, not individual proof.
        pid = state.battle_id + ':' + event.side + ':hud:' + event.event_id.rsplit(':', 1)[-1]
        p = PokemonState(pid, event.side); state.pokemon[pid] = p
        team.party_instance_ids.append(pid); basis = 'new_observed_occupancy_episode'
        original = {k:v for k,v in ref.items() if k != 'canonical_identity'}
        original['identity_status'] = 'species_only'
        engine._assign(p, 'original_identity', original, event)
    if p.fainted.known and p.fainted.value:
        raise Contradiction('hud_continuity_to_confirmed_fainted_instance')
    if old_pid != p.pokemon_instance_id:
        if current:
            # We observed a different occupant, not a withdrawal/faint cause.
            current.location = Fact(provenance=[evidence_link(event)])
        for position, pid in list(team.active_slots.items()):
            if pid == p.pokemon_instance_id:
                del team.active_slots[position]
        if old_pid and old_pid!=p.pokemon_instance_id and old_pid in state.pokemon:
            state.pokemon[old_pid].location=Fact(provenance=[evidence_link(event)])
        team.active_slots[a['slot']] = p.pokemon_instance_id
        interval = dict(after=previous['timestamp'] if previous else None, at_or_before=timestamp,
                        action_time=None, cause=None, previous_instance_id=old_pid,
                        current_instance_id=p.pokemon_instance_id)
        outcome['occupancy_change'] = interval
        # The previous HUD bounds a transition only if it actually identified the old occupant.
        if not previous or previous.get('status') != 'accepted':
            interval['after'] = None
    if a['slot'] in team.vacant_slots:
        team.vacant_slots.remove(a['slot'])
    engine._assign(p, 'species', ref, event)
    if ref.get('canonical_identity'):
        engine._assign(p, 'current_variant', ref['canonical_identity'], event)
    engine._assign(p, 'location', dict(kind='active', slot=a['slot']), event)
    record.bindings['actor'] = dict(pokemon_instance_id=p.pokemon_instance_id, basis=basis)
    record.bindings['identity'] = deepcopy(ref)
    # A nickname binding needs explicit raw-name/icon agreement on this frame.
    raw = species.get('raw_text') or ''.strip()
    if raw and not knowledge().exact['species'].get(normalize(raw)) and icon.get('status') == 'resolved':
        alias_key = event.side + ':' + raw
        fusion['aliases'][alias_key] = dict(identity=deepcopy(ref), evidence=[evidence_link(event)],
            instance_id=p.pokemon_instance_id, side=event.side)
    hp = a.get('hp') or {}; value = hp.get('value')
    outcome['hp_status'] = 'deferred'
    if hp.get('confidence', 0) >= .75 and isinstance(value, dict):
        current_hp = value.get('current'); maximum = value.get('maximum')
        if (type(current_hp) is int and type(maximum) is int and maximum > 0 and 0 <= current_hp <= maximum):
            if (previous and previous['timestamp'] == timestamp and previous.get('hp')
                    and previous['hp'].get('confidence',0) >= .75 and previous['hp'].get('value') != value):
                outcome.update(hp_status='conflicting', hp_reason='simultaneous_hp_disagreement')
                state.conflicts.append(dict(event_id=event.event_id, reason='simultaneous_hp_disagreement', proposed_value=value))
            elif p.hp.maximum.known and p.hp.maximum.value != maximum:
                outcome.update(hp_status='conflicting', hp_reason='maximum_hp_disagreement')
                state.conflicts.append(dict(event_id=event.event_id, reason='maximum_hp_disagreement', proposed_value=value))
            else:
                hp_event = deepcopy(event)
                hp_event.attributes = dict(unit='absolute', after=current_hp, maximum=maximum)
                engine._hp(p, hp_event); outcome['hp_status'] = 'accepted'
        else:
            outcome.update(hp_status='conflicting', hp_reason='invalid_absolute_hp_reading')
    elif hp.get('confidence', 0) >= .75 and type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 100:
        # Retain the unit explicitly. Never turn opponent percentages into absolute HP.
        hp_event = deepcopy(event); hp_event.attributes = dict(unit='displayed_percent', after=value)
        engine._hp(p, hp_event); outcome['hp_status'] = 'accepted_percent'
    record.bindings['hud'] = deepcopy(outcome)
    return False


def context_supported(state, side, slot, timestamp):
    """Explicit intervening uncertainty blocks aliases and actor binding."""
    if not state.knowledge.get('reliability_v1'):return True
    pending=[x for x in state.knowledge.get('unplaced_entries',[]) if x['side']==side
        and state.pokemon[x['instance_id']].location.value=={'kind':'unplaced_entry','slot':None}]
    if pending:return False
    last=state.knowledge.get('hud_fusion',{}).get('slots',{}).get(side+':'+slot,{})
    return not any(o.get('kind')=='coverage_gap' and o.get('side') in {side,'field','unknown'}
        and o['end']<=timestamp and o['end']>last.get('timestamp',float('-inf')) for o in state.observations)


def prepare_message(state, event):
    """Reparse only opt-in fusion messages against this replay prefix."""
    if not event.attributes.get('fusion_context'):
        return event
    if event.attributes.get('actor_instance_id'):
        # Explicit correction still passes normal policy and instance ownership checks.
        return event
    context = BattleContext()
    timestamp = event.attributes.get('observation_time', float('-inf'))
    for side, team in state.sides.items():
        for slot, pid in team.active_slots.items():
            last = state.knowledge.get('hud_fusion', {}).get('slots', {}).get(side + ':' + slot)
            if last and (last['status'] != 'accepted' or last['timestamp'] > timestamp):
                continue
            if not context_supported(state,side,slot,timestamp):continue
            mon = state.pokemon[pid]
            if mon.species.known:
                context.active[side].add(mon.species.value['canonical_id'])
    aliases = state.knowledge.get('hud_fusion', {}).get('aliases', {})
    for binding in aliases.values():
        side = binding['side']; pid = binding['instance_id']
        slots=[s for s,p in state.sides[side].active_slots.items() if p==pid]
        if not slots or not context_supported(state,side,slots[0],timestamp):
            continue
        name = next(k.split(':', 1)[1] for k, v in aliases.items() if v is binding)
        alternatives = [b for k, b in aliases.items() if k.split(':', 1)[1] == name]
        if len({b['identity']['canonical_id'] for b in alternatives}) == 1:
            context.display_aliases[name] = binding
    entry = dict(entry_id=event.event_id, source_id=event.evidence[0].source_id,
                 raw_text=event.original_text, ocr_confidence=event.ocr_confidence,
                 move_ocr_alternatives=[a for a in event.attributes.get('move_ocr_alternatives',[])
                    if a.get('source_sha256') in {oid for source in event.evidence for oid in source.observation_ids}])
    parsed = EventParser(knowledge()).parse(entry, context, state.battle_id)
    parsed.event_id = event.event_id; parsed.evidence = deepcopy(event.evidence)
    parsed.attributes.update({k:deepcopy(v) for k,v in event.attributes.items() if k not in {'side_basis','display_alias_evidence','move_resolution'}})
    parsed.status = event.status
    # Capture exact prefix-local instance bindings; no future roster is consulted.
    if parsed.actor and parsed.side in state.sides:
        matches = []
        for slot, pid in state.sides[parsed.side].active_slots.items():
            if not context_supported(state,parsed.side,slot,timestamp):continue
            mon = state.pokemon[pid]
            last = state.knowledge.get('hud_fusion', {}).get('slots', {}).get(parsed.side + ':' + slot)
            if last and (last['status'] != 'accepted' or last['timestamp'] > timestamp):
                continue
            if mon.species.known and mon.species.value.get('species_id') == parsed.actor.get('species_id'):
                matches.append(pid)
        if len(matches) == 1:
            parsed.attributes['actor_instance_id'] = matches[0]
            parsed.attributes['binding_basis'] = 'observed_active_identity_at_message_prefix'
            parsed.attributes['binding_sources'] = [deepcopy(v['evidence']) for k,v in
                state.knowledge.get('hud_fusion',{}).get('slots',{}).items()
                if k.startswith(parsed.side+':') and v.get('species_id')==parsed.actor.get('species_id')
                and v['timestamp'] <= timestamp and v['status']=='accepted']
        elif parsed.event_type not in {'effectiveness','move_effect','unknown','send_out'}:
            parsed.uncertainty.append('active_identity_context_unresolved')
    return parsed


def move_revelation(engine, state, event, record):
    """Apply the independently admitted actor+move slice, never its effects."""
    from .state_engine import Deferred, evidence_link
    safe = deepcopy(event)
    if safe.attributes.get('execution_status','executed') != 'executed' or safe.attributes.get('effect_outcome') == 'selected':
        raise Deferred('move_not_observed_as_executed')
    safe.uncertainty = [u for u in safe.uncertainty if u not in {'target_not_in_entry', 'target_variant_unresolved'}]
    engine.policy.check(safe)
    if not safe.attributes.get('actor_instance_id'):
        raise Deferred('move_actor_not_bound_to_observed_prefix')
    p = engine._resolve(state, safe, record)
    move = safe.canonical_references.get('move')
    if not move or not move.get('canonical_id'):
        raise Deferred('move_identity_unknown')
    p.moves.executed.append(dict(event_id=event.event_id, move=deepcopy(move),
        evidence=evidence_link(event), admission='revealed_move_only', target=None))
    record.bindings['admissibility'] = dict(actor=True, move=True, target=False, effects=False,
                                           reason='target_and_effects_not_established')
    record.bindings['resolved_event'] = event.to_dict()
