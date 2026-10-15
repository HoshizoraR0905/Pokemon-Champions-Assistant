"""Read-only evidence contract for future adapters, deliberately disconnected from M3."""
from copy import deepcopy
from dataclasses import asdict
import math


def source_times(provenance):
    return [s['details']['timestamp'] for p in provenance if isinstance(p,dict) for s in p.get('sources',[]) if isinstance(s,dict)
            if type(s.get('details',{}).get('timestamp')) in (int,float)
            and math.isfinite(s['details']['timestamp'])]


def evidence_projection(engine, *, as_of):
    if type(as_of) not in (int,float) or not math.isfinite(as_of) or as_of<0:
        raise ValueError('as_of must be a finite nonnegative timestamp')
    state=engine.state
    def all_fact_times(value):
        if isinstance(value,dict):
            if isinstance(value.get('provenance'),list):yield from source_times(value['provenance'])
            for child in value.values():yield from all_fact_times(child)
        elif isinstance(value,list):
            for child in value:yield from all_fact_times(child)
    if any(t>as_of for t in all_fact_times(state.to_dict())):
        raise ValueError('State contains future evidence; replay a prefix')
    applied=[r for r in engine.history if not r.retracted and r.application_status not in {'deferred','rejected','retracted'}]
    times=[r.event['attributes'].get('observation_time') for r in applied]
    times=[t for t in times if type(t) in (int,float)]
    if times and max(times)>as_of:
        raise ValueError('Replay a chronological prefix before projecting an earlier time')
    gaps=[deepcopy(o) for o in state.observations if o.get('kind')=='coverage_gap']
    def view(f, *, persistent=False, side=None):
        ts=source_times(f.provenance);last=max(ts) if ts else None
        transitions=[g for g in gaps if g.get('side',side) in {side,'field','unknown'}
                     and (last is None or g.get('end',as_of)>last)]
        current=f.known and last is not None and (persistent or last==as_of) and not transitions
        if f.knowledge=='conflicting':status='conflicting'
        elif not f.known:status='unresolved'
        elif current:status=('deterministically_derived' if f.knowledge=='derived' else 'directly_observed') if last==as_of else 'persistent_revelation'
        else:status='continuity_unverified' if last is not None else 'historical_time_unknown'
        return dict(value=deepcopy(f.value),knowledge=f.knowledge,last_confirmed_time=last,
                    provenance=deepcopy(f.provenance),resolution_status=status,current_supported=current,
                    confidence=dict(ocr=[p.get('ocr_confidence') for p in f.provenance],parsing=[p.get('parsing_confidence') for p in f.provenance],aggregate=None),
                    intervening_transitions=transitions,alternatives=deepcopy(f.alternatives))
    pokemon={}
    for pid,p in state.pokemon.items():
        pokemon[pid]=dict(instance_id=pid,side=p.side_id,
            identity=view(p.species,persistent=True,side=p.side_id),form=view(p.current_variant,side=p.side_id),
            location=view(p.location,side=p.side_id),fainted=view(p.fainted,side=p.side_id),types=view(p.current_types,side=p.side_id),instance_identity_status='observed_episode; biological continuity requires explicit evidence',hp={k:view(getattr(p.hp,k),side=p.side_id) for k in ('current','maximum','displayed_percent','unit')},
            stages={k:view(v.value,side=p.side_id) for k,v in p.stages.items()},
            ability=view(p.ability.current,side=p.side_id),ability_revelations=deepcopy(p.ability.revealed),
            item=view(p.item.identity,side=p.side_id),item_revelations=deepcopy(p.item.revealed),
            major_status=view(p.major_status,side=p.side_id),moves=deepcopy(asdict(p.moves)))
    occupancy={}
    for side,team in state.sides.items():
        occupancy[side]={}
        for slot in ('left','right'):
            pid=team.active_slots.get(slot);p=state.pokemon.get(pid)
            last=state.knowledge.get('hud_fusion',{}).get('slots',{}).get(side+':'+slot,{})
            loc=view(p.location,side=side) if p else None
            conflicting=last.get('status')=='conflicting'
            unresolved=last.get('status')=='deferred' or any(x['side']==side and state.pokemon[x['instance_id']].location.value=={'kind':'unplaced_entry','slot':None} for x in state.knowledge.get('unplaced_entries',[]))
            supported=bool(loc and loc['current_supported'] and not conflicting and not unresolved)
            occupancy[side][slot]=dict(last_observed_instance_id=pid,
                current_instance_id=pid if supported else None,
                status='conflicting' if conflicting else 'confirmed_current' if supported else 'unresolved_current',
                evidence=loc,latest_hud=deepcopy(last))
    def effect(e):return dict(active=view(e.active),kind=view(e.kind),duration=deepcopy(asdict(e.duration)))
    actions=[]
    for r in applied:
        e=r.bindings.get('resolved_event',r.event)
        if e['event_type']!='move_execution':continue
        actions.append(dict(event_id=e['event_id'],instance_id=r.bindings.get('actor',{}).get('pokemon_instance_id'),
            target=deepcopy(e.get('target')),target_binding=deepcopy(r.bindings.get('target')),admissibility=deepcopy(r.bindings.get('admissibility')),
            timestamp=e['attributes'].get('observation_time'),move=deepcopy(e['canonical_references'].get('move')),
            priority_evidence=deepcopy(e['attributes'].get('priority_evidence')),
            priority_context={k:deepcopy(e['attributes'][k]) for k in ('priority','effective_priority','priority_modifiers') if k in e['attributes']},
            timing={k:deepcopy(e['attributes'][k]) for k in ('turn','decision_id','state_at','modifier_changes') if k in e['attributes']},
            source_ordering=deepcopy(r.ordering),
            evidence=deepcopy(e['evidence']),uncertainty=deepcopy(e['uncertainty']),
            application_status=r.application_status,evidence_kind='animation_or_message_order',
            verified_action_order=False,speed_comparison_admissible=False))
    return dict(schema_version=1,profile='m234-conservative-evidence-v1',battle_id=state.battle_id,as_of=as_of,
        rule_profile=engine.mechanic_rules.profile_id,turn=view(state.turn),phase=view(state.phase),
        continuity_contract='No complete observation coverage is asserted; dynamic values between observations require independent continuity evidence. No expiration timer.',
        pokemon=pokemon,occupancy=occupancy,weather=effect(state.weather),terrain=effect(state.terrain),
        trick_room=effect(state.trick_room),side_conditions={s:{k:effect(e) for k,e in t.conditions.items()} for s,t in state.sides.items()},
        ui_field_observations=[deepcopy(o) for o in state.observations if o.get('kind')=='visual_observation' and o.get('fields',{}).get('field')],
        action_observations=actions,coverage=gaps,conflicts=deepcopy(state.conflicts),
        adapter_readiness='evidence_only_requires_explicit_admission',calculation_connected=False)
