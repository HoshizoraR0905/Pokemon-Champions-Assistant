"""Translate known snapshot facts to M3.2 input; missing modifiers stay null."""
from speed_inference.domains import encoded


def value(f):return f.get('value') if isinstance(f,dict) and f.get('known') is True else None


def canonical(f):
    v=value(f)
    return v.get('canonical_id') if isinstance(v,dict) else v


def order_context(snapshot,own_id,opponent_id):
    annotation=snapshot.get('annotation',{});state=snapshot.get('observable',{})
    actors={}
    for role,pid,side in [('own',own_id,'self'),('opponent',opponent_id,'opponent')]:
        mon=state.get('pokemon',{}).get(pid,{})
        identity=value(mon.get('form'))
        explicit_variant=isinstance(identity,str) and identity.startswith(('pokeapi:pokemon:','pokeapi:form:'))
        item_status=value(mon.get('item_status'));item='none' if item_status in ('none','consumed','transferred') else canonical(mon.get('item'))
        tailwind=next((r['active'] for r in snapshot.get('effects',[]) if r['scope']==side and r['effect']=='tailwind'),None)
        actor=dict(identity=identity,form='as_named' if explicit_variant else None,instance_id=pid,actual_speed=None,
            stage=value(mon.get('stages',{}).get('speed')),tailwind=tailwind,ability=canonical(mon.get('ability')),
            ability_active=None,item=item,status=value(mon.get('status')),unburden_active=None,activation_evidence=None,other_effects=None)
        # These dynamic facts require explicit contemporary evidence; absence is not false.
        modifiers=annotation.get('actor_modifiers',{}).get(pid,{})
        for key in ('tailwind','ability_active','unburden_active','activation_evidence','other_effects'):
            if key in modifiers:actor[key]=modifiers[key]
        actors[role]=actor
    weather=value(state.get('weather',{}).get('kind'));weather='sand' if weather=='sandstorm' else weather
    field=dict(weather=weather,terrain=value(state.get('terrain',{}).get('kind')),
        trick_room=value(state.get('trick_room',{}).get('active')),other_effects=annotation.get('field_other_effects'))
    return dict(**actors,field=field,actions={},ordering_effects=annotation.get('ordering_effects'),timing={},
        comparable=annotation.get('comparable') is True,evidence=encoded(snapshot.get('provenance',[])+annotation.get('sources',[])))
