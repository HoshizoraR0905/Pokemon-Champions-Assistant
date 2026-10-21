"""Compact immutable projections of the existing authoritative StateEngine."""
from copy import deepcopy
from speed_inference.domains import digest


def fact(value):
    return dict(value=deepcopy(value.value),known=value.known,knowledge=value.knowledge,
        event_ids=[p.get('event_id') for p in value.provenance if isinstance(p,dict)],
        continuity='last_observed_fact; action-time continuity requires separate evidence')


def project(state):
    pokemon={}
    for pid,p in state.pokemon.items():
        pokemon[pid]=dict(instance_id=pid,side=p.side_id,identity=fact(p.species),form=fact(p.current_variant),
            location=fact(p.location),hp=dict(current=fact(p.hp.current),maximum=fact(p.hp.maximum)),
            status=fact(p.major_status),stages={k:fact(v.value) for k,v in p.stages.items()},
            ability=fact(p.ability.current),item=fact(p.item.identity),item_status=fact(p.item.status))
    def effect(x):return dict(active=fact(x.active),kind=fact(x.kind))
    return dict(battle_id=state.battle_id,turn=fact(state.turn),pokemon=pokemon,
        occupancy={side:deepcopy(team.active_slots) for side,team in state.sides.items()},
        weather=effect(state.weather),terrain=effect(state.terrain),trick_room=effect(state.trick_room),
        side_conditions={side:{name:effect(v) for name,v in team.conditions.items()} for side,team in state.sides.items()})


def snapshot(event,when,state,durations,assignment,*,annotation=None,builds=None):
    body=dict(event_id=event['id'],when=when,timestamp=event.get('timestamp'),turn=deepcopy(assignment),
        observable=deepcopy(state),effects=durations.snapshot(),
        quality='Saved/replayed observed facts; no continuity or ordering snapshot is certified by delivery order',
        provenance=deepcopy(event.get('sources',[])),unknowns=['battle-time continuity','unobserved modifiers','unverified own build'])
    if annotation:
        if annotation.get('verified') is not True or not annotation.get('sources'):raise ValueError('Snapshot annotation requires verified provenance')
        body['annotation']=deepcopy(annotation)
    body['own_stats']={}
    if builds:
        for pid,mon in state.get('pokemon',{}).items():
            if mon['side']!='self':continue
            current=mon['form']['value'] if mon['form']['known'] else None
            actor=dict(identity=current,form='as_named',instance_id=pid,actual_speed=None,stage=mon['stages'].get('speed',{}).get('value'),
                stages={k:f['value'] if f['known'] else None for k,f in mon['stages'].items()},tailwind=None,ability=None,ability_active=None,
                item=None,status=None,unburden_active=None,activation_evidence=None,other_effects=None)
            context=(annotation or {}).get('decision_context',{})
            if context.get('own',{}).get('instance_id')==pid:actor.update(deepcopy(context['own']))
            body['own_stats'][pid]=builds.projection(event['battle_id'],pid,actor,context.get('field',{}),profile='champions-evidence-only-v1')
    body['id']='snapshot:'+digest(body)
    return body
