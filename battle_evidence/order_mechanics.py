"""Priority evidence over the maintained Champions catalog; no stat arithmetic.

Unknown native abilities remain alternatives, never a neutral assignment. This
module classifies order eligibility; the maintained M3.2 calculator owns Speed.
"""
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import json
from speed_order.core import knowledge,name,ABILITIES
from speed_inference.domains import digest

VERSION='real-action-order-v1'
SPECIAL_MOVES={'After You','Quash','Instruct','Round','Focus Punch','Beak Blast','Shell Trap',
               'Counter','Mirror Coat','Metal Burst','Grassy Glide','Pursuit','Me First',
               'Electro Shot','Solar Beam','Solar Blade','Dig','Fly','Dive','Phantom Force','Sky Attack','Skull Bash','Bounce'}
PRIORITY_CHANGERS={'Prankster','Gale Wings','Triage'}
ORDER_ABILITIES={'Stall','Quick Draw','Mycelium Might'}
ORDER_ITEMS={'Quick Claw','Custap Berry','Lagging Tail','Full Incense'}


@lru_cache(maxsize=1)
def audit():
    return json.loads(Path(__file__).with_name('order-mechanics-v1.json').read_text())


def native_abilities(identity):
    return knowledge().facts['pokemon'].get(identity,{}).get('ability_names',[])


def priority_support(move, *, identity=None, ability=None, ability_active=None, hp_full=None,
                     healing_verified=False):
    kb=knowledge();fact=kb.facts['moves'].get(move,{})
    result=dict(base_priority=fact.get('priority'),effective_priorities=[],hypotheses=[],
                status='unknown',reasons=[],source='maintained KnowledgeBase Champions move catalog',
                knowledge_snapshot=kb.manifest['files'].get('champions_facts.json'))
    if type(fact.get('priority')) is not int:return dict(result,reasons=['move_priority_missing'])
    try:move_name=name(move,'move')
    except ValueError:return dict(result,reasons=['move_identity_missing'])
    if move_name in SPECIAL_MOVES:
        return dict(result,status='special_action',reasons=['conditional_or_special_move_order_requires_dedicated_context'])
    if ability is None:
        abilities=native_abilities(identity)
        if not abilities:return dict(result,reasons=['native_ability_domain_missing'])
    else:
        try:abilities=[name(ability,'ability')]
        except ValueError:return dict(result,reasons=['ability_identity_missing'])
    base=fact['priority'];values=[]
    for a in sorted(set(abilities)):
        p=base;reason=None
        active=ability_active is not False
        if active and a=='Prankster' and fact['category']=='Status':
            if ability is not None and ability_active is None:
                values.append(base)
            p+=1
        elif active and a=='Gale Wings' and fact['type']=='Flying':
            if hp_full is None or (ability is not None and ability_active is None):
                values.append(base);p+=1
            elif hp_full:p+=1
        elif active and a=='Triage':
            if healing_verified:p+=3
            else:reason='Triage_healing_eligibility_not_verified'
        if reason:result['reasons'].append(reason)
        else:values.append(p)
        result['hypotheses'].append(dict(ability=a,effective_priority=p if not reason else None,
                                         basis='known_ability' if ability is not None else 'legal_native_ability_alternative'))
    result['effective_priorities']=sorted(set(values))
    result['status']='supported' if len(result['effective_priorities'])==1 and not result['reasons'] else 'hypothesis_dependent'
    return result


def compare_priority(first,second):
    a=first['priority'];b=second['priority']
    x=a.get('effective_priorities',[]);y=b.get('effective_priorities',[])
    if a['status']=='special_action' or b['status']=='special_action':return 'special_action_not_speed_informative'
    if not x or not y:return 'priority_unresolved'
    if len(x)==len(y)==1 and x==y:return 'same_supported_priority'
    if set(x).isdisjoint(y):return 'not_speed_informative_different_priority'
    return 'priority_hypotheses_unresolved'
