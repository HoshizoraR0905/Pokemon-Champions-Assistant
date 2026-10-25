"""Observable-only, nonexclusive capability features; no SP inputs accepted."""
from collections import Counter
import json
from pathlib import Path

from knowledge import KnowledgeBase
from speed_order.forms import mega_base_form, published_ability

DESIGN=json.loads(Path(__file__).with_name('preregistered.json').read_text())
FAMILIES=DESIGN['context_families']
FEATURES=[name for family in FAMILIES.values() for name in family]
FIELDS=('species','moves','ability','item','nature')


def presence(values):
    if 1 in values:return 1.
    return None if None in values else 0.


def count_known(values):
    return None if None in values else float(sum(values))


def conjunction(a,b):
    if a==0 or b==0:return 0.
    return None if a is None or b is None else 1.


def observed(member):
    n=member.get('normalized',member)
    return {**{k:n.get(k) for k in FIELDS},'issues':list(member.get('issues',[])),
            'ordinal':member.get('ordinal'),'source_url':member.get('source_url')}


class Mechanisms:
    def __init__(self):
        self.kb=KnowledgeBase()
        self.names={cid:e.names.get('en',cid) for cid,e in self.kb.entities.items()}
        self.ids={value:key for key,value in self.names.items()}
        self.facts=self.kb.facts

    def move(self, member, move):
        if any('move' in i or 'build_export_disagreement' in i for i in member['issues']):return None
        moves=member.get('moves') or []
        if self.ids[move] in moves:return 1.
        return 0. if len(set(moves))==4 and None not in moves else None

    def profiles(self, member):
        """Supported ability alternatives, never infer unknown base abilities.

        A Mega's fixed ability is a conditional option under observed compatible
        stone evidence; explicit original ability can also operate before Mega.
        """
        species=member['species'];ability=member['ability'];item=member['item']
        if not species or not ability or any('ability' in i or 'species' in i or 'item' in i or 'build_export_disagreement' in i for i in member['issues']):
            return [],True
        try:state=published_ability(species,ability,species)
        except (ValueError,KeyError,NotImplementedError):return [],True
        fact=self.facts['pokemon'].get(species,{})
        required=fact.get('required_item')
        profiles=[]
        if required:
            if not item or self.names.get(item)!=required:return [],True
            profiles.append(dict(ability=state['active_ability'],mega=True))
            if state.get('original_ability'):profiles.append(dict(ability=state['original_ability'],mega=False))
            # Post-Mega source assertion does not reveal original ability.
            unknown=state.get('original_ability') is None
        else:
            profiles.append(dict(ability=state['active_ability'],mega=False));unknown=False
            # Required stone plus fixed native Mega ability establishes an option,
            # not selection. Never add arbitrary legal base-ability alternatives.
            if item:
                sid=self.kb.entities[species].species_id
                for form,mega in self.facts['pokemon'].items():
                    if mega.get('required_item')==self.names.get(item) and self.kb.entities[form].species_id==sid and len(mega.get('ability_names',[]))==1:
                        profiles.append(dict(ability=mega['ability_names'][0],mega=True))
        return profiles,unknown

    def ability_flag(self, member, profile, ability):
        options,unknown=profile
        if any(p['ability']==ability for p in options):return 1.
        if not unknown:return 0.
        # A missing choice remains unknown; a pinned native domain can rule
        # out an ability without selecting another legal ability as observed.
        species=member['species']
        if species in self.facts['pokemon']:
            try:base=mega_base_form(species) or species
            except (ValueError,KeyError):return None
            possible=set(self.facts['pokemon'].get(base,{}).get('ability_names',[]))
            possible.update(self.facts['pokemon'].get(species,{}).get('ability_names',[]))
            if possible and ability not in possible:return 0.
        return None

    def natural_fast(self, member):
        species=member['species']
        if not species or any('species' in i or 'form' in i or 'build_export_disagreement' in i for i in member['issues']):return None
        try:base=mega_base_form(species) or species
        except (ValueError,KeyError):return None
        stat=self.facts['pokemon'].get(base,{}).get('stats',{}).get('sp')
        return float(stat>=DESIGN['natural_speed_threshold']) if stat is not None else None

    def extract(self, teammates):
        if len(teammates)!=5:raise ValueError('Exactly five original teammate slots required')
        members=[observed(m) for m in teammates]
        profiles=[self.profiles(m) for m in members]
        def ability_option(name):
            return presence([self.ability_flag(member,profile,name) for member,profile in zip(members,profiles)])
        def setter(name,manual):
            options=ability_option(name)
            # Recognize an unverified manual enabler as unresolved, not absent.
            if options!=1 and presence([self.move(m,manual) for m in members])!=0:return None
            return options
        sun=setter('Drought','Sunny Day');rain=setter('Drizzle','Rain Dance')
        chloro=ability_option('Chlorophyll');swim=ability_option('Swift Swim')
        def pair(setter_name,receiver_name,setter_value,receiver_value):
            base=conjunction(setter_value,receiver_value)
            if base!=1:return base
            uncertain=False
            for i,(a,_) in enumerate(profiles):
                for j,(b,_) in enumerate(profiles):
                    if i==j:continue
                    for x in a:
                        for y in b:
                            if x['ability']==setter_name and y['ability']==receiver_name:
                                if not (x['mega'] and y['mega']):return 1.
                                uncertain=True
            return None if uncertain or base==1 else 0.
        priorities=[]
        for member,(ps,unknown) in zip(members,profiles):
            support=presence([self.move(member,m) for m in DESIGN['priority_support_moves']])
            if support==1:priorities.append(1.);continue
            has_status=False;status_unknown=False
            for move in member['moves'] or []:
                fact=self.facts['moves'].get(move)
                if fact and fact.get('category')=='Status' and fact.get('priority',-99)>=0:has_status=True
                if not fact:status_unknown=True
            prankster=any(p['ability']=='Prankster' for p in ps)
            if prankster and has_status:priorities.append(1.)
            elif support is None or self.ability_flag(member,(ps,unknown),'Prankster') is None or status_unknown:priorities.append(None)
            else:priorities.append(0.)
        features=dict(tailwind_count=count_known([self.move(m,'Tailwind') for m in members]),
            trick_room_count=count_known([self.move(m,'Trick Room') for m in members]),
            sun_setter_option=sun,rain_setter_option=rain,chlorophyll_option=chloro,swift_swim_option=swim,
            sun_pair_option=pair('Drought','Chlorophyll',sun,chloro),
            rain_pair_option=pair('Drizzle','Swift Swim',rain,swim),
            natural_fast_count=count_known([self.natural_fast(m) for m in members]),
            priority_support_option=presence(priorities),taunt_count=count_known([self.move(m,'Taunt') for m in members]))
        evidence=dict(teammates=[dict(ordinal=m['ordinal'],species=m['species'],profiles=ps,
                                     unknown_ability=unknown,natural_fast=self.natural_fast(m)) for m,(ps,unknown) in zip(members,profiles)],
                      conditional_mega_options=sum(any(p['mega'] for p in ps) for ps,u in profiles),
                      no_activation_or_bring_assumption=True)
        return features,evidence

    def interaction(self, own, context, name):
        if name=='taunt_tailwind':own_flag=float(self.ids['Taunt'] in own['moves']);feature='tailwind_count'
        elif name=='close_combat_trick_room':own_flag=float(self.ids['Close Combat'] in own['moves']);feature='trick_room_count'
        elif name=='named_item_trick_room':own_flag=float(self.names.get(own['item']) in ('Life Orb','White Herb'));feature='trick_room_count'
        else:raise ValueError('Unregistered interaction')
        value=context[feature]
        return conjunction(own_flag,None if value is None else float(value>0))


def dictionary(rows):
    definitions={
        'tailwind_count':'Number of teammates explicitly carrying Tailwind',
        'trick_room_count':'Number of teammates explicitly carrying Trick Room',
        'sun_setter_option':'Compatible Drought option; conditional Mega options remain conditional',
        'rain_setter_option':'Compatible Drizzle option; conditional Mega options remain conditional',
        'chlorophyll_option':'Compatible observed Chlorophyll option, never a species-legal guess',
        'swift_swim_option':'Compatible observed Swift Swim option, never a species-legal guess',
        'sun_pair_option':'Drought option and observed Chlorophyll on distinct compatible teammate roles',
        'rain_pair_option':'Drizzle option and observed Swift Swim on distinct compatible teammate roles',
        'natural_fast_count':'Number of teammates with pinned native/pre-Mega base Speed >=100',
        'priority_support_option':'Observed specified priority-support move or supported Prankster + eligible Status move',
        'taunt_count':'Number of teammates explicitly carrying Taunt'}
    result=[]
    for feature in FEATURES+[i['name'] for i in DESIGN['interactions']]:
        values=[r['context'][feature] if feature in FEATURES else r['interactions'][feature] for r in rows]
        positive=[r for r,v in zip(rows,values) if v is not None and v>0]
        missing=[r for r,v in zip(rows,values) if v is None]
        result.append(dict(name=feature,definition=definitions.get(feature,'Predefined own-field × teammate-context conjunction'),
            family=next((k for k,v in FAMILIES.items() if feature in v),'interaction'),
            source_fields=['teammates.species','teammates.moves','teammates.ability','teammates.item']+(['own.moves','own.item'] if feature not in FEATURES else []),
            positives=len(positive),positive_groups=len({r['group'] for r in positive}),missing=len(missing),missing_groups=len({r['group'] for r in missing}),
            value_counts=dict(Counter('unknown' if v is None else str(v) for v in values)),selected_a_priori=True,
            assumptions='Observed/compatible conditional option, not chosen battle mode; unknowns remain null; pinned reference is not official certification'))
    return result
