"""Compact knowledge-state projection; no history scan or hidden belief inference."""
from dataclasses import asdict
from copy import deepcopy
from fractions import Fraction
from .battle_state import Fact
from .pokemon_knowledge import pokemon_knowledge
from .mechanics import read, ability, active, PROTEAN, item_presence


def protection_probability(pokemon, rules):
    m = pokemon.mechanics.get('protect_chain')
    count = read(m, 'success_count') if m else Fact()
    pending = read(m, 'pending') if m else Fact()
    result = {'knowledge': 'unknown', 'probability': None, 'range': [0, 1],
              'rule_profile': rules.profile_id, 'rule_verification': rules.verification,
              'success_count': asdict(count), 'pending_outcome': asdict(pending),
              'conditional_on': ['eligible protection move', 'other move failure checks satisfied']}
    if rules.protect_divisor is None or rules.protect_counter_cap is None:
        result['reason'] = 'Champions probability rules not verified/enabled'
        return result
    if pending.known and pending.value or count.knowledge == 'conflicting':
        result['reason'] = 'Pending outcome or conflicting chain history'
        result['range'] = [float(Fraction(1, rules.protect_counter_cap)), 1]
        return result
    if not count.known:
        result['range'] = [float(Fraction(1, rules.protect_counter_cap)), 1]
        result['reason'] = 'Initial/consecutive history unresolved'
        return result
    if not isinstance(count.value,int) or isinstance(count.value,bool) or count.value < 0:
        raise ValueError('Invalid established Protect count')
    denominator = 1
    for _ in range(min(count.value, 64)):
        denominator = min(rules.protect_counter_cap, denominator * rules.protect_divisor)
        if denominator == rules.protect_counter_cap:
            break
    value = Fraction(1, denominator)
    result.update(knowledge='derived', probability={'numerator': value.numerator,'denominator':value.denominator},
                  range=[float(value),float(value)], provenance=deepcopy(count.provenance),
                  authoritative_champions=False)
    return result


def decision_state(state, rules, *, hidden_engine=None):
    """State of implemented mechanics, not a claim of complete game Markov sufficiency."""
    pokemon = {}
    for pid,p in state.pokemon.items():
        # Mechanic records carry only their compact current facts/conditions, not trigger ledgers.
        mechanics = {key: {'scope':m.scope,'current':{k:asdict(v) for k,v in m.current.items()},
                    'activation_conditions':m.activation_conditions,'persistence_conditions':m.persistence_conditions,
                    'reset_conditions':m.reset_conditions,
                    'expiration':asdict(m.expiration)} for key,m in p.mechanics.items()}
        protean = p.mechanics.get('protean')
        pokemon[pid] = {'side':p.side_id,'species':asdict(p.species),'variant':asdict(p.current_variant),
            'location':asdict(p.location),'fainted':asdict(p.fainted),'hp':{k:asdict(getattr(p.hp,k)) for k in
                ('current','maximum','displayed_percent','percent_interval','unit')},
            'current_types':asdict(p.current_types),'status':asdict(p.major_status),
            'status_counters':{k:asdict(v) for k,v in p.status_counters.items()},
            'stages':{k:{'value':asdict(v.value),'interval':asdict(v.interval)} for k,v in p.stages.items()},
            'item':{'identity':asdict(p.item.identity),'status':asdict(p.item.status),'has_item':asdict(item_presence(p))},
            'ability':{'identity':asdict(p.ability.current),'suppressed':asdict(p.ability.suppressed)},
            'moves':{'known_slots':{k:asdict(v) for k,v in p.moves.known_slots.items()},
                     'pp':{k:asdict(v) for k,v in p.moves.pp.items()},'unrevealed_slots':asdict(p.moves.unrevealed_slots)},
            'volatile':{k:asdict(v) for k,v in p.volatile.items()},'mechanics':mechanics,
            'action_constraints':{'active':active(p),'fainted':asdict(p.fainted),
                'protect':protection_probability(p,rules),
                'protean_eligible':asdict(read(protean,'eligibility') if protean else Fact())}}
    for pid,configuration in state.knowledge.get('team',{}).get('instances',{}).items():
        if pid in pokemon: pokemon[pid]['known_configuration']=deepcopy(configuration)
    result = {'schema_version':1,'battle_id':state.battle_id,'turn':asdict(state.turn),'phase':asdict(state.phase),
            'field':{k:asdict(getattr(state,k)) for k in ('weather','terrain','trick_room')},
            'global_effects':{k:asdict(v) for k,v in state.global_effects.items()},
            'mechanics':{k:asdict(v) for k,v in state.mechanics.items()},
            'sides':{sid:{'active_slots':deepcopy(s.active_slots),'party_instance_ids':list(s.party_instance_ids),
                     'party_complete':asdict(s.party_complete),'remaining_available':asdict(s.remaining_available),
                     'conditions':{k:asdict(v) for k,v in s.conditions.items()},'hazards':{k:asdict(v) for k,v in s.hazards.items()},
                     'temporary_effects':{k:asdict(v) for k,v in s.temporary_effects.items()},
                     'resources':{k:asdict(v) for k,v in s.resources.items()},
                     'mechanics':{k:asdict(v) for k,v in s.mechanics.items()}} for sid,s in state.sides.items()},
            'pokemon':pokemon,'rule_profile':rules.to_dict(),
            'hidden_state_belief':{'status':'unimplemented','distribution':None},
            'limitations':['Opponent hidden configuration unresolved','Only registered/implemented mechanics represented',
                           'Action eligibility incomplete; this is not a legal-action or recommendation engine']}

    if hidden_engine is not None:
        result['hidden_configuration']=hidden_engine.decision_projection()
        views=pokemon_knowledge(pokemon,hidden_engine.projection())
        for pid,view in views.items():
            pokemon[pid]['knowledge']=view
        result['hidden_state_belief']={'status':'deterministic_constraints_only','distribution':None}
    return result
