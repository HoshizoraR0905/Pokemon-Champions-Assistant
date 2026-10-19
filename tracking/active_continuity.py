"""Versioned entry/departure provenance around authoritative PokemonState slots.

Episode records never establish biological continuity from a species match.
Existing explicit instance evidence / verified complete parties own that decision.
"""
from copy import deepcopy
from dataclasses import asdict
from battle_events.schema import stable_id


def enabled(state):return bool(state.knowledge.get('active_continuity_v1'))


def current_episode(state,pid):
    return next((x for x in reversed(state.knowledge.get('active_entry_episodes',[]))
                 if x['instance_id']==pid and x.get('departure') is None),None)


def enter(state,p,event,record,*,slot=None,observed=False):
    from .state_engine import evidence_link
    episodes=state.knowledge.setdefault('active_entry_episodes',[])
    previous=[x for x in episodes if x['instance_id']==p.pokemon_instance_id]
    explicit=bool(event.attributes.get('actor_instance_id') or (event.attributes.get('continuity') or {}).get('evidence'))
    complete=state.sides[p.side_id].party_complete
    supported=explicit or complete.known and complete.value
    candidates=[pid for pid in state.sides[p.side_id].party_instance_ids if pid!=p.pokemon_instance_id
        and state.pokemon[pid].species.known and state.pokemon[pid].species.value.get('species_id')==(p.species.value or {}).get('species_id')
        and pid not in state.sides[p.side_id].active_slots.values()
        and not (state.pokemon[pid].fainted.known and state.pokemon[pid].fainted.value)]
    ep=dict(episode_id=stable_id(state.battle_id,'active-entry:'+event.event_id+':'+p.pokemon_instance_id),
        instance_id=p.pokemon_instance_id,side=p.side_id,species_id=(p.species.value or {}).get('species_id'),
        start=event.attributes.get('observation_time'),entry_event_id=event.event_id,entry_evidence=evidence_link(event),
        start_kind='observed_occupancy' if observed else 'send_out',slot=slot,placements=[],departure=None,
        persistent_identity_status='independently_supported' if supported else 'unproven' if candidates else 'first_observed_no_historical_merge',
        possible_prior_instance_ids=[] if supported else candidates,
        distinct_biological_individual_asserted=False)
    if previous and supported:
        from .battle_state import HPState,Fact
        # Old readings remain evidence, rather than the current episode's HP.
        p.hp=HPState(observations=deepcopy(p.hp.observations))
        for stage in p.stages.values():
            stage.value=Fact(provenance=[evidence_link(event)]);stage.interval=Fact(provenance=[evidence_link(event)])
    if not observed:
        from .entry_hud import ENTRY_WINDOW_SECONDS,CONFIRM_SECONDS,POLICY
        refs=event.attributes.get('ordered_display_references',[])
        ep['entry_display_reference']=(event.attributes.get('display_reference') or
            (refs[0] if len(refs)==1 else None) or event.attributes.get('actor_display_reference') or (event.actor or {}).get('name'))
        ep['species_known_at_entry']=p.species.known
        ep['hud_binding']=dict(policy=POLICY,status='pending',entry_deadline=ep['start']+ENTRY_WINDOW_SECONDS,
            confirmation_seconds=CONFIRM_SECONDS,first_candidate_time=None,first_eligible_time=None,candidates=[])
    episodes.append(ep);record.bindings['entry_episode']=deepcopy(ep)
    return ep


def placed(state,p,event,record,slot):
    from .state_engine import evidence_link
    ep=current_episode(state,p.pokemon_instance_id)
    if ep is None:ep=enter(state,p,event,record,slot=slot,observed=True)
    if ep['slot']!=slot or not ep['placements']:
        ep['slot']=slot;ep['placements'].append(dict(slot=slot,timestamp=event.attributes.get('observation_time'),evidence=evidence_link(event)))
    record.bindings['active_episode_id']=ep['episode_id']
    return ep


def depart(state,p,event,record,slots):
    from .state_engine import evidence_link
    ep=current_episode(state,p.pokemon_instance_id)
    departure=dict(reason=event.event_type,event_id=event.event_id,timestamp=event.attributes.get('observation_time'),
        slot=slots[0] if len(slots)==1 else None,evidence=evidence_link(event),
        historical_hp=asdict(p.hp),historical_status=asdict(p.major_status),historical_moves=deepcopy(p.moves.executed))
    if ep:
        ep['departure']=deepcopy(departure);record.bindings['active_episode_id']=ep['episode_id']
        if ep.get('hud_binding',{}).get('status') in {'pending','expired'}:
            ep['hud_binding'].update(status='ended_unresolved',reason='episode_departed_before_identity')
    record.bindings['departure']=departure


def current_aliases(state,timestamp):
    """Inactive claims remain in the ledger but cannot name a current actor."""
    from .evidence_fusion import context_supported
    from .evidence_projection import source_times
    aliases=[]
    for claim in state.knowledge.get('identity_ledger',{}).get('aliases',[]):
        side=claim['side'];pid=claim.get('instance_id');p=state.pokemon.get(pid)
        if not p or side not in state.sides or max(source_times(claim.get('evidence',[])),default=float('-inf'))>timestamp:continue
        slots=[slot for slot,v in state.sides[side].active_slots.items() if v==pid]
        if any(context_supported(state,side,slot,timestamp) for slot in slots):aliases.append(claim)
        elif p.location.value==dict(kind='unplaced_entry',slot=None) and current_episode(state,pid):aliases.append(claim)
    return aliases


def occupancy(state,side,slot):
    """Derived occupancy, never a second authoritative slot ledger."""
    team=state.sides[side];p=state.pokemon.get(team.active_slots.get(slot))
    if p:return 'occupied_identified' if p.species.known else 'occupied_unidentified'
    pending=[p for p in state.pokemon.values() if p.side_id==side
             and p.location.value==dict(kind='unplaced_entry',slot=None) and current_episode(state,p.pokemon_instance_id)]
    if pending:return 'placement_unresolved'
    return 'vacant' if slot in team.vacant_slots else 'placement_unresolved'


def prepare_unidentified(state,event):
    """Admit observed arrival/departure independently of species resolution."""
    import math
    from battle_events.aliases import alias_key
    if not enabled(state) or not state.knowledge.get('identity_v1') or event.side not in state.sides:return event
    a=event.attributes;t=a.get('observation_time');confidence=event.ocr_confidence
    if (event.event_type=='send_out' and event.actor and a.get('display_reference')
            and a.get('source_region_type')=='battle_message'
            and any(source.source_type=='video_message' for source in event.evidence)):
        # Saved pre-policy ordered children may have classified a species solely
        # from a trailing substring. Keep their immutable raw events, but revoke
        # that unsupported derived actor in the replay's resolved event.
        from battle_events.parser import EventParser
        from .evidence_fusion import knowledge
        literal=EventParser(knowledge()).identity(a['display_reference'],'species')
        if not literal or literal.get('species_id')!=event.actor.get('species_id'):
            event=deepcopy(event);event.actor=None
            if 'actor_unresolved' not in event.uncertainty:event.uncertainty.append('actor_unresolved')
            event.attributes['legacy_substring_identity_withheld']=True
    if (a.get('source_region_type')!='battle_message' or type(confidence) not in (int,float)
            or not math.isfinite(confidence) or confidence<.95 or type(t) not in (int,float) or not math.isfinite(t)
            or not any(s.source_type=='video_message' and s.observation_ids and s.details.get('timestamp')==t for s in event.evidence)):
        return event
    # Raw parser evidence must establish complete live grammar and side. Species
    # uncertainty alone may be waived; all other policy checks remain in place.
    basis=set(a.get('side_basis',[]))
    if event.event_type=='send_out' and not (event.actor or {}).get('species_id'):
        import re
        from recognition.event_schedule import ordered_entries
        text=event.original_text.strip().replace('\n','').replace('\r','')
        if not re.fullmatch(r'(?:.+派出了.+|上吧[！!，,].+)[！!。.]',text):return event
        refs=a.get('ordered_display_references') or ordered_entries(event.original_text)
        raw=a.get('display_reference') or (refs[0] if len(refs)==1 else None)
        if raw and basis&{'observed_trainer_display_name','explicit_preview_trainer_id_match','explicit_text'}:
            event=deepcopy(event);event.attributes['unidentified_entry_reference']=raw
            event.uncertainty=[u for u in event.uncertainty if u!='actor_unresolved']
    elif event.event_type in {'switch_out','faint'} and a.get('actor_display_reference'):
        raw=alias_key(a['actor_display_reference'])
        candidates=[ep for ep in state.knowledge.get('active_entry_episodes',[]) if ep['side']==event.side
                    and ep['departure'] is None and ep.get('display_reference')
                    and alias_key(ep['display_reference'])==raw and not state.pokemon[ep['instance_id']].species.known]
        if len(candidates)==1 and basis&{'complete_withdrawal_grammar','complete_live_faint_grammar'}:
            event=deepcopy(event);event.attributes['actor_instance_id']=candidates[0]['instance_id']
            event.attributes['unidentified_departure']=True
            event.uncertainty=[u for u in event.uncertainty if u not in {'actor_unresolved','active_identity_context_unresolved'}]
    return event


def unidentified_entry(engine,state,event,record):
    """Create a named encounter, with unresolved identity and optional placement."""
    import hashlib
    from .battle_state import PokemonState
    from .state_engine import Contradiction,evidence_link
    from recognition.event_schedule import entry_slots
    a=event.attributes;team=state.sides[event.side];raw=a['unidentified_entry_reference']
    # Identical source occurrences are one arrival; equal nicknames on a later
    # source occurrence do not prove biological continuity.
    occurrence=a.get('occurrence_id',event.event_id)
    prior=[ep for ep in state.knowledge.get('active_entry_episodes',[]) if ep.get('arrival_occurrence')==occurrence
           and ep['side']==event.side and ep.get('display_reference')==raw and ep['departure'] is None]
    if len(prior)==1:
        record.bindings['actor']=dict(pokemon_instance_id=prior[0]['instance_id'],basis='same_entry_occurrence')
        return True
    vacant=set(team.vacant_slots)-set(team.active_slots);slot=next(iter(vacant)) if len(vacant)==1 else None
    refs=a.get('ordered_display_references',[]);mapping=entry_slots(event.side,refs)
    placements=[s for ref,s in zip(refs,mapping) if ref==raw and s is not None]
    if len(placements)==1 and a.get('slot')==placements[0]:slot=placements[0]
    if slot in team.active_slots:raise Contradiction('occupied_active_slot')
    pid=f'{state.battle_id}:{event.side}:encounter:'+hashlib.sha256(event.event_id.encode()).hexdigest()[:16]
    p=PokemonState(pid,event.side);state.pokemon[pid]=p;team.party_instance_ids.append(pid)
    engine._assign(p,'location',dict(kind='active' if slot else 'unplaced_entry',slot=slot),event)
    ep=enter(state,p,event,record,slot=slot)
    ep.update(display_reference=raw,arrival_occurrence=occurrence,trainer_display_text=a.get('trainer_display_text'),
              trainer_evidence=deepcopy(a.get('trainer_side_evidence') or team.trainer),
              species_resolution_time=None,persistent_identity_status='unproven')
    from .entry_hud import ENTRY_WINDOW_SECONDS,CONFIRM_SECONDS,POLICY
    ep['hud_binding']=dict(policy=POLICY,status='pending',entry_deadline=ep['start']+ENTRY_WINDOW_SECONDS,
        confirmation_seconds=CONFIRM_SECONDS,first_candidate_time=None,first_eligible_time=None,candidates=[])
    if slot:
        team.active_slots[slot]=pid
        if slot in team.vacant_slots:team.vacant_slots.remove(slot)
        placed(state,p,event,record,slot)
    else:
        state.knowledge.setdefault('unplaced_entries',[]).append(dict(instance_id=pid,side=event.side,
            species_id=None,event_id=event.event_id,timestamp=a['observation_time'],raw_nickname=raw))
    record.bindings['actor']=dict(pokemon_instance_id=pid,basis='observed_named_arrival_identity_unknown')
    record.bindings['entry_episode']=deepcopy(ep)
    record.bindings['admissibility']=dict(occupancy=slot is not None,identity=False,slot=slot is not None,continuity=False)
    return False


def resolve_identity(engine,state,p,ref,event,record,*,basis):
    """Resolve only the current episode, at the actual evidence time."""
    from .state_engine import Contradiction,evidence_link
    ep=current_episode(state,p.pokemon_instance_id)
    if ep is None:raise Contradiction('identity_episode_ended')
    if p.species.known and p.species.value.get('species_id')!=ref['species_id']:
        raise Contradiction('provisional_identity_conflict')
    if not p.species.known:
        engine._assign(p,'species',ref,event);engine._assign(p,'original_identity',ref,event)
        if ref.get('canonical_identity'):engine._assign(p,'current_variant',ref['canonical_identity'],event)
        ep.update(species_id=ref['species_id'],species_resolution_time=event.attributes['observation_time'])
        if ep.get('hud_binding',{}).get('status') not in {'resolved','resolved_prospectively'}:
            ep.setdefault('hud_binding',{}).update(status='resolved_via_auxiliary',resolved_at=event.attributes['observation_time'],reason=basis)
        ep['identity_resolution']=dict(timestamp=event.attributes['observation_time'],basis=basis,evidence=evidence_link(event))
        if ep.get('display_reference'):
            from .identity_ledger import remember_alias
            remember_alias(state,ep['display_reference'],ref,[ep['entry_evidence'],evidence_link(event)],
                           side=p.side_id,instance_id=p.pokemon_instance_id,source='prospective_entry_identity')
            if ep.get('hud_display_name'):
                remember_alias(state,ep['hud_display_name']['value'],ref,ep['hud_display_name']['evidence'],
                    side=p.side_id,instance_id=p.pokemon_instance_id,source='confirmed_hud_display_name')
        record.bindings['identity_resolution']=dict(instance_id=p.pokemon_instance_id,episode_id=ep['episode_id'],
            arrival_timestamp=ep['start'],**deepcopy(ep['identity_resolution']))
    return ep
