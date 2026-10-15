"""Bounded explicit-state Speed/order evaluation; no recognition or network."""
from functools import lru_cache
from copy import deepcopy
from pathlib import Path
import json
from knowledge import KnowledgeBase, normalize
from knowledge.champions_stats import ChampionsStats
from damage.core import stage_stat, poke_round, chain_mods

REFERENCE='showdown-champions-reference-v1'
PROFILES={REFERENCE,'champions-evidence-only-v1'}
ABILITIES={'none','Swift Swim','Chlorophyll','Sand Rush','Slush Rush','Unburden','Speed Boost','Surge Surfer','Quick Feet','Pressure','Blaze','Torrent','Overgrow'}
ITEMS={'none','Choice Scarf','Iron Ball','Leftovers','Life Orb','Sitrus Berry'}
PRIORITY_ABILITIES={'Prankster','Gale Wings','Triage','Stall','Quick Draw'}
ORDER_ITEMS={'Quick Claw','Custap Berry','Lagging Tail','Full Incense'}
MOVES=set('Body Slam|Flamethrower|Thunderbolt|Ice Beam|Earthquake|Close Combat|Moonblast|Psychic|Shadow Ball|Surf|Rock Slide|Quick Attack|Extreme Speed|Protect|Detect|Tailwind|Thunder Wave|Recover|Roost|Swords Dance|Dragon Claw|Air Slash|Waterfall|Iron Head|Bullet Punch|Mach Punch|Aqua Jet|Ice Shard|Trick Room'.split('|'))
ACTOR_KEYS={'identity','form','instance_id','actual_speed','stage','tailwind','ability','ability_active','item','status','unburden_active','activation_evidence','other_effects'}

class Issue(ValueError):
    def __init__(self,status,reason):super().__init__(reason);self.status=status


def need(condition,reason,status='insufficient_information'):
    if not condition:raise Issue(status,reason)


def shape(value,keys):
    need(isinstance(value,dict) and set(value)==set(keys),'Missing or unrecognized fields: '+','.join(sorted(keys)))


def text(value):return isinstance(value,str) and bool(value.strip())
def integer(value,lo,hi):
    need(type(value) is int and lo<=value<=hi,f'Expected integer {lo}..{hi}');return value

def boolean(value):need(type(value) is bool,'Explicit boolean required');return value


@lru_cache(maxsize=1)
def knowledge():return KnowledgeBase()


@lru_cache(maxsize=1)
def _source_provenance():return json.loads((Path(__file__).parent/'data/sources-v1.json').read_text())


def provenance():return deepcopy(_source_provenance())


def name(value,kind):
    need(text(value),'Unknown/conflicting '+kind+' requires explicit alternatives')
    if value=='none' and kind in ('ability','item'):return value
    kb=knowledge();rows=[kb.entities[value]] if value in kb.entities else kb.exact[kind].get(normalize(value),[])
    rows={r.canonical_id:r for r in rows if r.kind==kind}
    need(len(rows)==1,'Missing or ambiguous canonical '+kind)
    return next(iter(rows.values())).names['en']


@lru_cache(maxsize=512)
def identity_key(identity,form):
    # Resolve identities without requiring base stats: an explicit numerical
    # Speed domain must remain usable when legal training data is unavailable.
    kb=knowledge();need(text(identity),'Explicit species/form identity required')
    explicit=False
    if identity.startswith('pokeapi:pokemon:'):
        suffix=identity.rsplit(':',1)[-1]
        rows=kb.identities.by_pokemon.get(int(suffix),[]) if suffix.isdecimal() else []
        need(len(rows)==1,'Unknown or ambiguous Pokemon variant')
        row=rows[0];key=f"pokeapi:form:{row.get('source_form_id',row['form_id'])}"
        identity=key if key in kb.entities else f"pokeapi:species:{row['species_id']}";explicit=True
    def entity(value):
        need(text(value),'Explicit form identity required')
        matches=[kb.entities[value]] if value in kb.entities else kb.exact['species'].get(normalize(value),[])
        matches={e.canonical_id:e for e in matches if e.kind=='species'}
        need(len(matches)==1,'Unknown or ambiguous species/form');return next(iter(matches.values()))
    ref=entity(identity)
    if ref.form_id is not None or explicit:need(form in (None,'as_named'),'Variant already fixes its current form')
    elif form!='base':
        selected=entity(form);need(selected.species_id==ref.species_id and selected.form_id is not None,'Form does not belong to species');ref=selected
    return ref.canonical_id


def actor(value):
    shape(value,ACTOR_KEYS);need(text(value['instance_id']),'Instance ID required')
    identity=identity_key(value['identity'],value['form'])
    # Actual Speed is explicit: construction is optional and separate.
    integer(value['stage'],-6,6);boolean(value['tailwind']);boolean(value['ability_active']);boolean(value['unburden_active'])
    need(value['status'] in ('none','burn','poison','toxic','paralysis','sleep','freeze'),'Unknown/conflicting or unsupported status')
    need(isinstance(value['other_effects'],list),'Explicit other_effects [] required')
    need(not value['other_effects'],'Other Speed effects lack audited handlers','unsupported')
    return dict(identity=identity,ability=name(value['ability'],'ability'),item=name(value['item'],'item'))


def _effective_uncached(actual_speed,participant,field,profile):
    need(isinstance(profile,str) and profile in PROFILES,'Explicit rules profile required')
    ref=actor(participant);integer(actual_speed,1,4095)
    shape(field,{'weather','terrain','trick_room','other_effects'})
    need(field['weather'] in ('none','sun','rain','sand','snow'),'Unknown or unsupported weather')
    need(field['terrain'] in ('none','electric','grassy','psychic','misty'),'Unknown or unsupported terrain')
    boolean(field['trick_room']);need(isinstance(field['other_effects'],list),'Explicit field other_effects [] required')
    need(not field['other_effects'],'Other field effects unsupported','unsupported')
    need(profile==REFERENCE,'Champions effective-Speed rounding/order is not independently verified; reference profile required','unsupported')
    ability=ref['ability'] if participant['ability_active'] else 'none';item=ref['item']
    need(ref['ability'] in ABILITIES,'Ability not in audited effective-Speed subset','unsupported')
    need(item in ITEMS,'Item has unaudited Speed/order mechanics','unsupported')
    active=participant['unburden_active']
    if active:need(ability=='Unburden' and item=='none','Active Unburden requires unsuppressed ability and evidenced item loss')
    if ability=='Unburden':need(text(participant['activation_evidence']),'Unburden requires evidenced active/inactive history')
    mods=[];labels=[]
    def add(label,value):mods.append(value);labels.append(label)
    if participant['tailwind']:add('Tailwind',8192)
    weather=field['weather'];terrain=field['terrain']
    if (ability=='Unburden' and active) or (ability,weather) in {('Swift Swim','rain'),('Chlorophyll','sun'),('Sand Rush','sand'),('Slush Rush','snow')} or (ability=='Surge Surfer' and terrain=='electric'):
        add(ability,8192)
    elif ability=='Quick Feet' and participant['status']!='none':add('Quick Feet',6144)
    if not (ability=='Unburden' and active):
        if item=='Choice Scarf':add(item,6144)
        elif item=='Iron Ball':add(item,2048)
    staged=stage_stat(actual_speed,participant['stage'])
    modified=poke_round(staged*chain_mods(mods))
    result=modified//2 if participant['status']=='paralysis' and ability!='Quick Feet' else modified
    need(result<=999,'Reference discrepancy above effective Speed 999: calc Champions caps 999 while simulator caps 10000','unsupported')
    return dict(effective_speed=max(0,min(10000,result)),stage_speed=staged,modifier_fixed=chain_mods(mods),modifiers=labels,
                paralysis_applied=participant['status']=='paralysis' and ability!='Quick Feet',identity=ref['identity'])


@lru_cache(maxsize=8192)
def _cached_speed(actual_speed,participant_json,field_json,profile):
    return _effective_uncached(actual_speed,json.loads(participant_json),json.loads(field_json),profile)


def _effective(actual_speed,participant,field,profile):
    integer(actual_speed,1,4095)
    return deepcopy(_cached_speed(actual_speed,json.dumps(participant,sort_keys=True,allow_nan=False),json.dumps(field,sort_keys=True,allow_nan=False),profile))


def effective_speed(*,actual_speed,participant,field,profile='champions-evidence-only-v1'):
    result=dict(schema_version=1,status='insufficient_information',effective_speed=None,diagnostics=[],provenance=provenance())
    try:result.update(_effective(actual_speed,participant,field,profile),status='exact_reference')
    except (Issue,ValueError,TypeError,KeyError,NotImplementedError) as exc:result.update(status=getattr(exc,'status','insufficient_information'),diagnostics=[str(exc)])
    return result


def _context(context,profile):
    shape(context,{'own','opponent','field','actions','ordering_effects','timing','comparable','evidence'})
    need(text(context['evidence']),'Order/source evidence required');boolean(context['comparable'])
    shape(context['timing'],{'turn','decision_id','state_at','modifier_changes'})
    timing=context['timing'];integer(timing['turn'],1,100000);need(text(timing['decision_id']),'Order decision identity required')
    need(isinstance(timing['modifier_changes'],list),'Explicit modifier-change history required')
    if not context['comparable'] or timing['state_at']!='order_decision' or timing['modifier_changes']:
        return dict(kind='non_informative',reason='Not an established comparable pair at one ordering decision; mid-turn recalculation is unverified.')
    refs={side:actor(context[side]) for side in ('own','opponent')}
    need(context['own']['instance_id']!=context['opponent']['instance_id'],'Distinct participant instances required')
    shape(context['field'],{'weather','terrain','trick_room','other_effects'});boolean(context['field']['trick_room'])
    need(context['field']['weather'] in ('none','sun','rain','sand','snow'),'Unknown or unsupported weather')
    need(context['field']['terrain'] in ('none','electric','grassy','psychic','misty'),'Unknown or unsupported terrain')
    need(isinstance(context['field']['other_effects'],list),'Explicit field other_effects [] required')
    need(not context['field']['other_effects'],'Unlisted field ordering effects require handlers','unsupported')
    need(isinstance(context['ordering_effects'],list),'Explicit ordering_effects [] required')
    if context['ordering_effects']:
        for effect in context['ordering_effects']:
            shape(effect,{'effect','actor','active','evidence'})
            need(text(effect['effect']) and effect['actor'] in ('own','opponent') and text(effect['evidence']),'Ordering effect provenance required')
            boolean(effect['active'])
            need(effect['effect'] in {'Quick Claw','Custap Berry','Lagging Tail','Full Incense','Stall','After You','Quash','Quick Draw'},'Unknown ordering exception','unsupported')
        if any(e['active'] for e in context['ordering_effects']):
            return dict(kind='non_speed_ordering',reason='Evidenced forced/triggered ordering requires dedicated interaction handling; no Speed inequality.')
        raise Issue('unsupported','Nonempty exception histories require dedicated inactive/interaction validation')
    shape(context['actions'],{'own','opponent'});priorities={}
    for side in ('own','opponent'):
        action=context['actions'][side];shape(action,{'kind','move','effective_priority','evidence'})
        need(text(action['evidence']),'Action/priority evidence required')
        if action['kind']!='move':return dict(kind='non_informative',reason='Switch, unable, entered-mid-turn, repeated or forced action is not an ordinary move pair.')
        need(refs[side]['ability'] not in PRIORITY_ABILITIES,'Priority-changing ability requires dedicated validation','unsupported')
        need(refs[side]['ability'] in ABILITIES,'Unknown ability effects cannot be assumed neutral','unsupported')
        need(refs[side]['item'] not in ORDER_ITEMS,'Triggered/late-order item state is not established by item presence alone','unsupported')
        need(refs[side]['item'] in ITEMS,'Unknown item ordering effects cannot be assumed absent','unsupported')
        move_name=name(action['move'],'move');need(move_name in MOVES,'Conditional/special or unaudited action priority','unsupported')
        kb=knowledge();row=next(e for e in kb.exact['move'][normalize(move_name)] if e.kind=='move')
        priority=kb.facts.get('moves',{}).get(row.canonical_id,{}).get('priority')
        need(type(priority) is int,'No pinned Champions priority definition','unsupported')
        integer(action['effective_priority'],-7,7)
        need(action['effective_priority']==priority,'Effective priority disagrees with audited base bracket; overrides need handlers','unsupported')
        priorities[side]=priority
    if priorities['own']!=priorities['opponent']:
        winner='own' if priorities['own']>priorities['opponent'] else 'opponent'
        return dict(kind='priority',winner=winner,reason='Different effective priority brackets determine order, independently of Speed.')
    need(profile==REFERENCE,'Ordinary ordering/rounding supported only under provisional reference profile','unsupported')
    return dict(kind='speed',reason='Same audited priority and one established ordering decision.')


def evaluate_order(*,context,opponent_speed,profile='champions-evidence-only-v1'):
    try:
        need(isinstance(profile,str) and profile in PROFILES,'Explicit supported profile required')
        assessed=_context(context,profile)
        if assessed['kind']!='speed':return dict(status='assessed',**assessed)
        own=_effective(context['own']['actual_speed'],context['own'],context['field'],profile)
        opponent=_effective(opponent_speed,context['opponent'],context['field'],profile)
        a,b=own['effective_speed'],opponent['effective_speed']
        if a==b:orders=['own','opponent']
        else:orders=['own' if (a>b)!=context['field']['trick_room'] else 'opponent']
        return dict(status='assessed',kind='speed',orders=orders,tie=a==b,own=own,opponent=opponent,reason=assessed['reason'])
    except (Issue,ValueError,TypeError,KeyError,StopIteration,NotImplementedError) as exc:
        return dict(status=getattr(exc,'status','insufficient_information'),kind='unresolved',reason=str(exc))
