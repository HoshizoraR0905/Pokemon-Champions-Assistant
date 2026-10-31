"""Standalone explicit-state calculator. No OCR, inference, or network imports."""
from copy import deepcopy
from fractions import Fraction
import json
from .data import Diagnostic,database,resolve,pokemon_data
from .core import poke_round,chain_mods,stage_stat,base_damage,rolls,distribution
from .selectors import select_stats
from .abilities import contextual_neutrality, neutral_ability_names
from .items import hit_handler, candidate_applicable, effect_applicable

PROFILES={'champions-evidence-only-v1','showdown-champions-reference-v1'}
# Closed audited allowlist: other moves cannot accidentally use ordinary power.
DIRECT=set('Body Slam|Double-Edge|Quick Attack|Extreme Speed|Flamethrower|Fire Blast|Heat Wave|Fire Punch|Flare Blitz|Waterfall|Surf|Hydro Pump|Scald|Liquidation|Thunderbolt|Thunder|Thunder Punch|Volt Switch|Ice Beam|Ice Punch|Ice Fang|Blizzard|Psychic|Psyshock|Shadow Ball|Shadow Claw|Dark Pulse|Crunch|Bite|Dragon Claw|Dragon Pulse|Draco Meteor|Earthquake|Earth Power|Bulldoze|Rock Slide|Stone Edge|Power Gem|Close Combat|Superpower|Aura Sphere|Focus Blast|Flash Cannon|Iron Head|Bullet Punch|Meteor Mash|Moonblast|Dazzling Gleam|Play Rough|Energy Ball|Leaf Blade|Leaf Storm|Giga Drain|Sludge Bomb|Sludge Wave|Poison Jab|Bug Buzz|X-Scissor|U-turn|Air Slash|Air Cutter|Brave Bird|Hurricane|Hyper Voice|Hyper Beam|Armor Cannon|Sacred Sword|Body Press|Facade'.split('|'))
DIRECT.update({'Fake Out', 'Foul Play', 'Psystrike'})
FIXED={'Seismic Toss','Night Shade'}
AT_ABILITIES=set('none|Adaptability|Technician|Huge Power|Pure Power|Guts|Sniper|Overgrow|Blaze|Torrent|Swarm|Tough Claws|Iron Fist|Strong Jaw|Mega Launcher|Sharpness|Aerilate|Pixilate|Refrigerate|Mold Breaker|Teravolt|Turboblaze|Pressure|Frisk'.split('|'))
DF_ABILITIES=set('none|Levitate|Flash Fire|Water Absorb|Volt Absorb|Lightning Rod|Sap Sipper|Thick Fat|Heatproof|Fur Coat|Filter|Solid Rock|Multiscale|Marvel Scale|Grass Pelt|Shell Armor|Battle Armor|Pressure|Frisk'.split('|'))
# These callbacks affect accuracy, order or post-hit damage, not this connected
# hit's damage. Contact retaliation remains separate HP-event evidence.
AT_ABILITIES.update({'No Guard','Static','Lightning Rod','Rough Skin','Prankster','Intimidate','Stamina'})
DF_ABILITIES.update({'No Guard','Static','Rough Skin','Prankster','Intimidate','Stamina'})
TYPE_ITEMS=dict(zip('Silk Scarf|Charcoal|Mystic Water|Magnet|Miracle Seed|Never-Melt Ice|Black Belt|Poison Barb|Soft Sand|Sharp Beak|Twisted Spoon|Silver Powder|Hard Stone|Spell Tag|Dragon Fang|Black Glasses|Metal Coat|Fairy Feather'.split('|'),'Normal Fire Water Electric Grass Ice Fighting Poison Ground Flying Psychic Bug Rock Ghost Dragon Dark Steel Fairy'.split()))
BERRIES=dict(zip('Chilan Berry|Occa Berry|Passho Berry|Wacan Berry|Rindo Berry|Yache Berry|Chople Berry|Kebia Berry|Shuca Berry|Coba Berry|Payapa Berry|Tanga Berry|Charti Berry|Kasib Berry|Haban Berry|Colbur Berry|Babiri Berry|Roseli Berry'.split('|'),'Normal Fire Water Electric Grass Ice Fighting Poison Ground Flying Psychic Bug Rock Ghost Dragon Dark Steel Fairy'.split()))
ITEMS={'none','Life Orb','Expert Belt','Muscle Band','Wise Glasses','Leftovers','Sitrus Berry','White Herb'}|set(TYPE_ITEMS)|set(BERRIES)
STAT_NAMES={'attack','defense','special_attack','special_defense','speed'}
MON_KEYS={'identity','form','level','stats','stat_basis','stages','current_hp','maximum_hp','ability','item','status','other_effects'}
FIELD_KEYS={'format','weather','terrain','critical','reflect','light_screen','aurora_veil','targets_hit','attacker_grounded','defender_grounded','helping_hand','friend_guard','other_effects'}


def known(value,path):
    if value is None:raise Diagnostic('incomplete_input',path,'Damage-relevant input is unknown; supply an explicit scenario')
    if isinstance(value,dict) and value.get('state')=='conflicting':raise Diagnostic('conflicting_input',path,'Resolve conflicting observations explicitly',value.get('values',[]))
    return value


def integer(value,path,low=1,high=65535):
    value=known(value,path)
    if type(value) is not int or not low<=value<=high:raise Diagnostic('invalid_input',path,f'Expected integer in [{low}, {high}]')
    return value


def boolean(value,path):
    value=known(value,path)
    if type(value) is not bool:raise Diagnostic('invalid_input',path,'Expected explicit true or false')
    return value


def choice(value,path,values):
    value=known(value,path)
    if value not in values:raise Diagnostic('unsupported',path,'Value not supported by selected profile',list(sorted(values)))
    return value


def object_keys(value,path,allowed):
    if not isinstance(value,dict):raise Diagnostic('invalid_input',path,'Expected object')
    extra=set(value)-allowed
    if extra:raise Diagnostic('invalid_input',path,'Unrecognized fields',sorted(extra))


def absent_other(value,path):
    value=known(value,path)
    if not isinstance(value,list):raise Diagnostic('invalid_input',path,'Explicitly declare [] when all other effects are absent')
    if value:raise Diagnostic('unsupported',path,'Additional effects require dedicated handlers',value)


def component(value,kind,path):
    value=known(value,path)
    return 'none' if value=='none' else resolve(value,kind,path)['name']


def prepare_mon(value,path):
    object_keys(value,path,MON_KEYS)
    identity,static=pokemon_data(value,path)
    if known(value.get('stat_basis'),path+'.stat_basis')!='unmodified':raise Diagnostic('unsupported',path+'.stat_basis','Supply actual unmodified combat stats; effective stats cannot safely have stages reapplied')
    integer(value.get('level'),path+'.level',1,100)
    object_keys(value.get('stats'),path+'.stats',STAT_NAMES)
    object_keys(value.get('stages'),path+'.stages',STAT_NAMES)
    for group in ['stats','stages']:
        for k,v in value[group].items():
            if v is not None and not isinstance(v,dict):integer(v,path+'.'+group+'.'+k,-6 if group=='stages' else 1,6 if group=='stages' else 65535)
    for name in ['current_hp','maximum_hp']:
        if value.get(name) is not None:integer(value[name],path+'.'+name,0 if name=='current_hp' else 1)
    if value.get('current_hp') is not None and value.get('maximum_hp') is not None and value['current_hp']>value['maximum_hp']:raise Diagnostic('invalid_input',path+'.current_hp','Current HP exceeds maximum HP')
    if value.get('current_hp')==0:raise Diagnostic('invalid_input',path+'.current_hp','Fainted participant cannot take this modeled active hit')
    ability=component(value.get('ability'),'ability',path+'.ability');item=component(value.get('item'),'item',path+'.item')
    choice(ability,path+'.ability',(AT_ABILITIES if path=='attacker' else DF_ABILITIES)|neutral_ability_names())
    form_id=identity['canonical_id']
    handler=hit_handler(item,form_id,path)
    if handler=='unresolved':raise Diagnostic('unsupported',path+'.item','Item mechanic/history lacks an audited connected-hit handler')
    if handler=='current_form_stone' and not candidate_applicable(item,form_id):raise Diagnostic('unsupported',path+'.item','Species/form incompatible Mega stone')
    status=choice(value.get('status'),path+'.status',{'none','burn','poison','toxic','paralysis','sleep','freeze'})
    absent_other(value.get('other_effects'),path+'.other_effects')
    return dict(input=value,identity=identity,static=static,ability=ability,item=item,status=status)


def effective(mon,stat,path,ignore_stage=False):
    value=integer(mon['input']['stats'].get(stat),path+'.stats.'+stat)
    stage=mon['input']['stages'].get(stat)
    if ignore_stage:return value
    stage=integer(stage,path+'.stages.'+stat,-6,6)
    return max(1,stage_stat(value,stage))


def calculate(request):
    """Return JSON-compatible diagnostics or a provisional exact distribution."""
    result=dict(schema_version=1,status='invalid_input',profile=request.get('profile') if isinstance(request,dict) and isinstance(request.get('profile'),str) else None,
        identities={},distribution=None,applied_modifiers=[],trace=[],assumptions=[],unresolved_inputs=[],unsupported_mechanics=[],provenance={})
    try:
        json.dumps(request,allow_nan=False)
        object_keys(request,'request',{'profile','mode','attacker','defender','move','field'})
        if request.get('mode','exact')!='exact':raise Diagnostic('invalid_input','mode','Use calculate_scenarios for explicit alternatives')
        profile=choice(request.get('profile'),'profile',PROFILES)
        kb,data,manifest=database();result['provenance']=dict(knowledge_snapshot=kb.snapshot_id,damage_data=manifest['files'],oracle=manifest['oracle'],verification='provisional community reference')
        attacker=prepare_mon(request.get('attacker'),'attacker');defender=prepare_mon(request.get('defender'),'defender');mref=resolve(request.get('move'),'move','move');move=data['moves'].get(mref['canonical_id'])
        result['identities']=dict(attacker=attacker['identity'],defender=defender['identity'],move=mref)
        if not move:raise Diagnostic('unsupported','move','No definition in pinned Champions-reference data')
        name=move['name'];category=move['category'];typ=move['type']
        if category=='Status':raise Diagnostic('unsupported','move','Status move is not direct damage')
        if move.get('multihit'):raise Diagnostic('unsupported','move','Multi-hit joint randomness and between-hit effects are not implemented')
        if name not in DIRECT|FIXED:raise Diagnostic('unsupported','move','Exceptional or unaudited move; never substitute its ordinary base power')
        for role,mon,handlers in [('attacker',attacker,AT_ABILITIES),('defender',defender,DF_ABILITIES)]:
            if mon['ability'] in handlers:continue
            audit=contextual_neutrality(mon['ability'],move,field=request.get('field'))
            if audit is None:raise Diagnostic('unsupported',role+'.ability','Ability context is outside its connected-hit neutrality audit')
            result['trace'].append(dict(role=role,ability_audit=audit))
            result['assumptions'].append(mon['ability']+': action-time state supplied explicitly; entry/residual/reflection effects are not simulated by this direct-hit calculator.')
        local=kb.facts['moves'].get(mref['canonical_id'])
        if local and (local['type']!=typ or local['category']!=category or (str(local['power']).isdigit() and name not in FIXED and int(local['power'])!=move['basePower'])):raise Diagnostic('conflicting_input','move','Pinned local Champions catalog and reference definition disagree')
        field=request.get('field');object_keys(field,'field',FIELD_KEYS)
        absent_other(field.get('other_effects'),'field.other_effects')
        weather=choice(field.get('weather'),'field.weather',{'none','sun','rain','sand','snow'});terrain=choice(field.get('terrain'),'field.terrain',{'none','electric','grassy','psychic','misty'});fmt=choice(field.get('format'),'field.format',{'singles','doubles'})
        critical=boolean(field.get('critical'),'field.critical')
        for key in ['reflect','light_screen','aurora_veil','helping_hand','friend_guard']:boolean(field.get(key),'field.'+key)
        for key in ['attacker_grounded','defender_grounded']:
            if field.get(key) is not None:boolean(field[key],'field.'+key)
        targets=integer(field.get('targets_hit'),'field.targets_hit',1,3)
        if fmt=='singles' and targets!=1:raise Diagnostic('invalid_input','field.targets_hit','Singles has one target')
        spread=move.get('target') in {'allAdjacent','allAdjacentFoes'}
        if fmt=='doubles' and spread and targets<2:raise Diagnostic('unsupported','field.targets_hit','Spread with a single remaining target needs separate oracle validation')
        if not spread and targets!=1:raise Diagnostic('invalid_input','field.targets_hit','Single-target move requires one target')
        if profile=='champions-evidence-only-v1':raise Diagnostic('unsupported','profile','No independently verified Champions formula/rounding evidence pinned; use explicitly provisional reference profile')
        result['assumptions']=['Conditional on this hit connecting, supplied critical flag, and explicit absence of unlisted effects; no accuracy/critical-chance inference.','Actual stats are unmodified and supplied by caller; no EV/IV/nature/SP or ability legality inferred.','Current form is supplied, not an evolution event; no automatic stat construction.', 'Rolls are potential direct damage; hp_loss_rolls separately caps damage at supplied current HP. Recoil, healing and post-hit effects are outside this one-hit distribution.']
        if defender['input'].get('current_hp') is None:result['assumptions'].append('Defender current HP unknown: damage distribution valid but KO probability unavailable unless required by ability.')
        aa=attacker['ability'];da=defender['ability'];ai=attacker['item'];di=defender['item'];mods=result['applied_modifiers']
        if aa in {'Mold Breaker','Teravolt','Turboblaze'}:da='none';mods.append(dict(stage='ability',name='defender ability ignored',reference_rule=aa))
        if da in {'Shell Armor','Battle Armor'} and critical:
            critical=False;mods.append(dict(stage='critical',name=da,effect='prevents_critical'))
        converted={'Aerilate':'Flying','Pixilate':'Fairy','Refrigerate':'Ice','Galvanize':'Electric'}
        ate=aa in converted and typ=='Normal'
        if ate:typ=converted[aa]
        if ai=='Normal Gem' and typ=='Normal':raise Diagnostic('unsupported','attacker.item','Normal Gem activation/consumption handler not implemented')
        result['trace'].append(dict(move_type=typ,category=category,source_move=move))
        def grounded(side,mon):
            supplied=boolean(field.get(side+'_grounded'),'field.'+side+'_grounded')
            natural='Flying' not in mon['static']['types'] and mon['ability']!='Levitate'
            if mon['item']=='Iron Ball':natural=True
            elif mon['item']=='Air Balloon':natural=False
            if supplied!=natural:raise Diagnostic('unsupported','field.'+side+'_grounded','Grounding overrides require explicit dedicated mechanics')
            return supplied
        if terrain!='none' and aa in {'Mold Breaker','Teravolt','Turboblaze'} and defender['ability']=='Levitate':raise Diagnostic('unsupported','field.defender_grounded','Suppressed Levitate/terrain interaction requires dedicated validation')
        ag=grounded('attacker',attacker) if terrain!='none' else False
        dg=grounded('defender',defender) if terrain!='none' else False
        effectiveness=Fraction(1)
        for dtype in defender['static']['types']:
            effectiveness*=Fraction(1) if typ=='Ground' and dtype=='Flying' and di=='Iron Ball' else Fraction(str(data['type_chart'][typ][dtype]))
        immunities={'Levitate':'Ground','Flash Fire':'Fire','Water Absorb':'Water','Storm Drain':'Water','Volt Absorb':'Electric','Lightning Rod':'Electric','Sap Sipper':'Grass'}
        if immunities.get(da)==typ and not (da=='Levitate' and di=='Iron Ball'):effectiveness=Fraction(0)
        if di=='Air Balloon' and typ=='Ground':effectiveness=Fraction(0)
        if effectiveness==0:
            mods.append(dict(stage='immunity',name='type_or_ability',multiplier=0))
            result.update(status='exact_reference',distribution=distribution([0],defender['input'].get('maximum_hp'),defender['input'].get('current_hp')));result['trace'].append(dict(immunity=True,type=typ,defender_ability=da));return result
        if name in FIXED:
            result.update(status='exact_reference',distribution=distribution([attacker['input']['level']],defender['input'].get('maximum_hp'),defender['input'].get('current_hp')));result['trace'].append(dict(handler='fixed_level_damage',randomness='deterministic; ordinary damage rolls inapplicable'));return result
        power=move['basePower'];bp=[]
        def push(stage,items,label,value):items.append(value);mods.append(dict(stage=stage,name=label,fixed_point=value,denominator=4096))
        if name=='Facade' and attacker['status'] in {'burn','paralysis','poison','toxic'}:push('power',bp,'Facade',8192)
        if field['helping_hand']:push('power',bp,'Helping Hand',6144)
        if ag and (terrain,typ) in {('electric','Electric'),('grassy','Grass'),('psychic','Psychic')}:push('power',bp,terrain,5325)
        if dg and ((terrain=='misty' and typ=='Dragon') or (terrain=='grassy' and name in {'Earthquake','Bulldoze'})):push('power',bp,terrain,2048)
        flags=move.get('flags',{})
        if (aa=='Technician' and power<=60) or any(aa==a and flags.get(f) for a,f in [('Mega Launcher','pulse'),('Strong Jaw','bite'),('Sharpness','slicing')]):push('power',bp,aa,6144)
        if aa=='Tough Claws' and flags.get('contact'):push('power',bp,aa,5325)
        if ate or aa=='Iron Fist' and flags.get('punch'):push('power',bp,aa,4915)
        if TYPE_ITEMS.get(ai)==typ:push('power',bp,ai,4915)
        elif ai=='Muscle Band' and category=='Physical' or ai=='Wise Glasses' and category=='Special':push('power',bp,ai,4505)
        power=max(1,poke_round(power*chain_mods(bp)))
        selector=select_stats(name,category)
        attack_source=attacker if selector['offensive_owner']=='attacker' else defender
        atstat=selector['offensive_stat'];dfstat=selector['defensive_stat']
        attack_path=selector['offensive_owner']
        astage=attack_source['input']['stages'].get(atstat);dstage=defender['input']['stages'].get(dfstat)
        # Critical may ignore a known disadvantageous stage, never an unknown one.
        integer(astage,attack_path+'.stages.'+atstat,-6,6)
        if name!='Sacred Sword':integer(dstage,'defender.stages.'+dfstat,-6,6)
        attack=effective(attack_source,atstat,attack_path,critical and astage<0)
        defense=effective(defender,dfstat,'defender',(critical and dstage>0) or name=='Sacred Sword')
        am=[];dm=[]
        if ai=='Light Ball' and effect_applicable(ai,attacker['identity']['canonical_id']) and atstat in {'attack','special_attack'} and selector['offensive_owner']=='attacker':push('attack',am,ai,8192)
        if aa=='Guts' and attacker['status']!='none' and category=='Physical':push('attack',am,aa,6144)
        elif aa in {'Overgrow','Blaze','Torrent','Swarm'} and typ=={'Overgrow':'Grass','Blaze':'Fire','Torrent':'Water','Swarm':'Bug'}[aa]:
            hp=integer(attacker['input'].get('current_hp'),'attacker.current_hp');maximum=integer(attacker['input'].get('maximum_hp'),'attacker.maximum_hp')
            if hp*3<=maximum:push('attack',am,aa,6144)
        elif aa in {'Huge Power','Pure Power'} and category=='Physical':push('attack',am,aa,8192)
        if da=='Thick Fat' and typ in {'Fire','Ice'} or da=='Heatproof' and typ=='Fire':push('attack',am,da,2048)
        attack=max(1,poke_round(attack*chain_mods(am)))%65536
        if weather=='sand' and 'Rock' in defender['static']['types'] and dfstat=='special_defense':defense=poke_round(defense*3,2)
        if weather=='snow' and 'Ice' in defender['static']['types'] and dfstat=='defense':defense=poke_round(defense*3,2)
        if da=='Marvel Scale' and defender['status']!='none' and dfstat=='defense' or da=='Grass Pelt' and terrain=='grassy' and dfstat=='defense':push('defense',dm,da,6144)
        elif da=='Fur Coat' and dfstat=='defense':push('defense',dm,da,8192)
        defense=max(1,poke_round(defense*chain_mods(dm)))%65536
        if attack==0 or defense==0:raise Diagnostic('unsupported','stats','16-bit effective stat overflow to zero')
        base=base_damage(attacker['input']['level'],power,attack,defense)
        sequence=[dict(step='base',value=base)]
        if spread and fmt=='doubles':base=poke_round(base*3072%(2**32));sequence.append(dict(step='spread',value=base));mods.append(dict(stage='base_damage',name='spread',numerator=3,denominator=4))
        if (weather,typ) in {('sun','Fire'),('rain','Water')}:base=poke_round(base*6144%(2**32));sequence.append(dict(step='weather',value=base));mods.append(dict(stage='base_damage',name=weather,numerator=3,denominator=2))
        elif (weather,typ) in {('sun','Water'),('rain','Fire')}:base=poke_round(base*2048%(2**32));sequence.append(dict(step='weather',value=base));mods.append(dict(stage='base_damage',name=weather,numerator=1,denominator=2))
        if critical:base=(base*3%(2**33))//2;sequence.append(dict(step='critical',value=base));mods.append(dict(stage='base_damage',name='critical',numerator=3,denominator=2))
        stab=8192 if aa=='Adaptability' and typ in attacker['static']['types'] else 6144 if typ in attacker['static']['types'] else 4096
        if stab!=4096:mods.append(dict(stage='after_random',name='STAB',fixed_point=stab,denominator=4096))
        if effectiveness!=1:mods.append(dict(stage='after_stab',name='type_effectiveness',numerator=effectiveness.numerator,denominator=effectiveness.denominator))
        final=[]
        if not critical and (field['aurora_veil'] or field['reflect'] and category=='Physical' or field['light_screen'] and category=='Special'):push('final',final,'screen',2732 if fmt=='doubles' else 2048)
        if aa=='Sniper' and critical:push('final',final,aa,6144)
        if da=='Multiscale':
            hp=integer(defender['input'].get('current_hp'),'defender.current_hp');maximum=integer(defender['input'].get('maximum_hp'),'defender.maximum_hp')
            if hp==maximum:push('final',final,da,2048)
        if da in {'Filter','Solid Rock'} and effectiveness>1:push('final',final,da,3072)
        if field['friend_guard']:push('final',final,'Friend Guard',3072)
        if ai=='Expert Belt' and effectiveness>1:push('final',final,ai,4915)
        elif ai=='Life Orb':push('final',final,ai,5324)
        if BERRIES.get(di)==typ and (effectiveness>1 or typ=='Normal'):push('final',final,di,2048)
        burned=attacker['status']=='burn' and category=='Physical' and aa!='Guts' and name!='Facade'
        if burned:mods.append(dict(stage='after_type',name='burn',numerator=1,denominator=2))
        values,steps=rolls(base,stab,effectiveness,burned,chain_mods(final))
        result['trace'].append(dict(effective_power=power,attack_stat=atstat,attack_owner=attack_path,selector=selector,effective_attack=attack,defense_stat=dfstat,effective_defense=defense,base_sequence=sequence,stab_fixed=stab,type_effectiveness=str(effectiveness),burn=burned,final_modifier=chain_mods(final),rolls=steps))
        result['assumptions'].append('Unused stats/stages do not enter this audited move handler; they may remain unknown. Missing HP only omits percentages/KO unless an HP-dependent ability requires it.')
        result.update(status='exact_reference',distribution=distribution(values,defender['input'].get('maximum_hp'),defender['input'].get('current_hp')))
    except Diagnostic as exc:
        result['status']=exc.status;target='unsupported_mechanics' if exc.status=='unsupported' else 'unresolved_inputs';result[target].append(exc.as_dict())
    except (TypeError,KeyError,ValueError) as exc:
        result['status']='invalid_input';result['unresolved_inputs'].append(dict(path='request',reason=str(exc),candidates=[]))
    return result


def stat_dependencies(result):
    """Authoritative stat dependencies of a successful executed handler.

    Does not predict dependencies for an unsupported or unresolved request.
    Fixed damage and immunity have no numerical attacking-stat dependency.
    """
    if result.get('status') != 'exact_reference':
        return None
    for step in reversed(result['trace']):
        if 'attack_stat' in step:
            return {'attacker': [step['attack_stat']] if step.get('attack_owner','attacker')=='attacker' else [], 'defender': sorted({step['defense_stat']} | ({step['attack_stat']} if step.get('attack_owner')=='defender' else set())),
                    'handler': 'ordinary_damage'}
        if step.get('immunity') or step.get('handler') == 'fixed_level_damage':
            return {'attacker': [], 'defender': [],
                    'handler': 'immunity' if step.get('immunity') else step['handler']}
    return None


def calculate_scenarios(request):
    """No probabilities or implicit builds: each caller-supplied scenario stands alone."""
    if not isinstance(request,dict) or set(request)!={'scenarios'} or not isinstance(request['scenarios'],list) or not 1<=len(request['scenarios'])<=64:
        return dict(status='invalid_input',reason='Supply 1..64 explicit scenarios; no automatic enumeration')
    rows=[];seen=set()
    for scenario in request['scenarios']:
        if not isinstance(scenario,dict) or set(scenario)!={'id','input'} or not isinstance(scenario['id'],str) or scenario['id'] in seen:return dict(status='invalid_input',reason='Unique string scenario IDs and explicit input required')
        seen.add(scenario['id']);rows.append(dict(id=scenario['id'],result=calculate(scenario['input'])))
    return dict(status='conditional_scenarios',scenario_probabilities=None,scenarios=rows)
