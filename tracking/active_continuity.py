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
        and state.pokemon[pid].species.known and state.pokemon[pid].species.value.get('species_id')==p.species.value.get('species_id')
        and pid not in state.sides[p.side_id].active_slots.values()
        and not (state.pokemon[pid].fainted.known and state.pokemon[pid].fainted.value)]
    ep=dict(episode_id=stable_id(state.battle_id,'active-entry:'+event.event_id+':'+p.pokemon_instance_id),
        instance_id=p.pokemon_instance_id,side=p.side_id,species_id=p.species.value.get('species_id'),
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
    if ep:ep['departure']=deepcopy(departure);record.bindings['active_episode_id']=ep['episode_id']
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
