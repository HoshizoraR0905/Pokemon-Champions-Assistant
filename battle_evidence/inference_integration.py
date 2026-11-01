"""Narrow saved-state adapters to the existing M3 engines, without priors."""
from copy import deepcopy
from functools import lru_cache
from itertools import product

from damage.data import database
from damage.engine import DIRECT, FIXED
from damage.inverse import infer_attack_stat
from damage.items import candidate_applicable, damage_equivalent
from damage.joint import legal_damage_items
from knowledge.champions_stats import ChampionsStats
from knowledge.stat_feasibility import summary
from speed_order.core import knowledge, name
from speed_order import infer_speed

PROFILE = 'showdown-champions-reference-v1'
STATS = ('attack','defense','special_attack','special_defense','speed')


def value(f):
    return f.get('value') if isinstance(f,dict) and f.get('knowledge') in {'observed','derived'} else None


def forms(p):
    current=value(p.get('variant'))
    if current:
        try:return [ChampionsStats(current,form='base' if current.startswith('pokeapi:species:') else 'as_named').identity]
        except (ValueError,NotImplementedError):return []
    species=value(p.get('species')) or {}
    sid=species.get('species_id')
    ability=value(p.get('ability',{}).get('identity'))
    ability=ability.get('canonical_id') if isinstance(ability,dict) else ability
    known=name(ability,'ability') if ability else None
    # A species-only observation keeps every applicable form. An observed
    # current native ability can rule out a form with a different ability.
    return sorted(k for k,f in knowledge().facts['pokemon'].items()
                  if knowledge().entities[k].species_id==sid
                  and (known is None or known in f['ability_names']))


@lru_cache(maxsize=2048)
def stat_pairs(native, current, stat, configuration_rule=None):
    a=ChampionsStats(native,form='base' if native.startswith('pokeapi:species:') else 'as_named')
    b=ChampionsStats(current,form='base' if current.startswith('pokeapi:species:') else 'as_named')
    pairs=set()
    for factor in ('0.9','1.0','1.1'):
        from .configuration_domain import point_domain
        points=point_domain(factor,configuration_rule)
        x=a.attainable(stat,adjustments=[factor],point_domain=points)['configurations']
        y=b.attainable(stat,adjustments=[factor],point_domain=points)['configurations']
        bypoint={r['training_points']:r['actual_stat'] for r in y}
        pairs.update((r['actual_stat'],bypoint[r['training_points']]) for r in x)
    return sorted(pairs)


def invert_saved_order(first, second, context, *, subject, native, retained, battle_id, proof, configuration_rule=None):
    """Default preference over one observation; accumulated callers use the ledger."""
    from .speed_preference import infer_saved_speed
    return infer_saved_speed([dict(first=first,second=second,context=context,subject=subject,proof=proof)],
        native=native,stat_constraints={'speed':summary(retained)},battle_id=battle_id,
        configuration_rule=configuration_rule)


def _order_form_union(first, second, context, *, subject, native, retained, battle_id, proof, configuration_rule=None, allowed_items=None):
    """Union supported current-form alternatives without choosing a hidden form.

    A branch that cannot be evaluated prevents an unconditional projection.
    Native/current stat correspondence still uses identical SP and alignment.
    """
    options=forms(context.get('pokemon',{}).get(subject,{}))
    if len(options)<=1:
        return _invert_saved_order(first,second,context,subject=subject,native=native,
            retained=retained,battle_id=battle_id,proof=proof,configuration_rule=configuration_rule,allowed_items=allowed_items)
    branches=[]
    for form in options:
        branch=deepcopy(context)
        branch['pokemon'][subject]['variant']=dict(value=form,knowledge='derived',
            provenance=[dict(rule='explicit form alternative, not observed form')])
        required=knowledge().facts['pokemon'][form].get('required_item')
        held=value(branch['pokemon'][subject].get('item',{}).get('identity'))
        if isinstance(held,dict):held=held.get('canonical_id')
        if value(branch['pokemon'][subject].get('item',{}).get('status')) in {'consumed','none','lost','transferred'}:
            held='none'
        if required and held is not None and name(held,'item')!=required:
            branches.append(dict(form=form,result=dict(status='contradiction',blockers=[],
                feasible=summary([]),reason='observed item excludes required form item')))
            continue
        result=_invert_saved_order(first,second,branch,subject=subject,native=native,
            retained=retained,battle_id=battle_id,proof=proof,configuration_rule=configuration_rule,allowed_items=allowed_items)
        branches.append(dict(form=form,result=result))
    unresolved=[b for b in branches if b['result']['status'] not in {'exact','contradiction'}]
    feasible=summary(v for b in branches if b['result']['feasible'] for v in b['result']['feasible']['values'])
    return dict(status='unresolved' if unresolved else 'exact' if feasible['values'] else 'contradiction',
        blockers=sorted({x for b in unresolved for x in b['result'].get('blockers',[])+b['result'].get('diagnostics',[])}),
        feasible=None if unresolved else feasible,proof=proof,form_branches=branches,
        tie_compatible=any(b['result'].get('tie_compatible',False) for b in branches))


def _invert_saved_order(first, second, context, *, subject, native, retained, battle_id, proof, configuration_rule=None, allowed_items=None):
    """Same-decision two-action projection; ties and Quick Claw remain possible."""
    from damage.items import registry
    from speed_order.core import identity_key
    ids=[r['bindings']['actor']['pokemon_instance_id'] for r in (first,second)]
    ps=context.get('pokemon',{});participants={};configurations=[];blockers=[]
    from speed_order.mechanics import ordering_coverage
    first_move=first['event']['canonical_references']['move']['canonical_id']
    if ordering_coverage()['moves'].get(name(first_move,'move'),{}).get('speed_side_effect'):
        blockers.append('first move Speed effects require explicit pending-queue transitions')
    field=context.get('field',{})
    fv=dict(weather=value(field.get('weather',{}).get('kind')),terrain=value(field.get('terrain',{}).get('kind')),
        trick_room=value(field.get('trick_room',{}).get('active')),other_effects=[])
    if fv['weather']=='sandstorm':fv['weather']='sand'
    if any(fv[k] is None for k in ('weather','terrain','trick_room')):blockers.append('field modifiers unresolved')
    evidence=dict(sources=proof['action_event_ids']+[proof['command_source']],basis='deduced',confidence='saved semantic four-opportunity certification')
    forms_for_subject=[]
    for pid in ids:
        p=ps.get(pid,{});options=forms(p)
        if len(options)!=1:
            blockers.append('current form unresolved for '+pid);continue
        form=options[0];fact=knowledge().facts['pokemon'][form]
        if p.get('copied_appearance'):
            blockers.append('copied Speed is not native Speed');continue
        def component(kind):
            x=value(p.get(kind,{}).get('identity'))
            return x.get('canonical_id') if isinstance(x,dict) else x
        ability=component('ability');item=component('item')
        # A consumed/removed slot is known empty, even though identity is unset.
        # Reuse the same explicit statuses as the damage adapter.
        if value(p.get('item',{}).get('status')) in {'consumed','none','lost','transferred'}:
            item='none'
        if item is not None:
            label=name(item,'item') if item!='none' else 'none'
            item_options=[label if registry()['items'].get(label,{}).get('speed_order') or label==fact.get('required_item') else 'none']
        elif fact.get('required_item'):item_options=[fact['required_item']]
        else:item_options=['none','Choice Scarf','Iron Ball','Quick Claw']
        if pid==subject and allowed_items is not None:
            item_options=[it for it in item_options if it in allowed_items]
        ability_options=[name(ability,'ability')] if ability else fact['ability_names']
        stats=p.get('mechanics',{}).get('battle_stats',{}).get('current',{})
        actual=value(stats.get('speed')) if pid!=subject else None
        if pid!=subject and actual is None:blockers.append('known comparison Speed unavailable')
        tailwind=value(context.get('sides',{}).get(p.get('side'),{}).get('conditions',{}).get('tailwind',{}).get('active'))
        stage=value(p.get('stages',{}).get('speed',{}).get('value'));status=value(p.get('status'))
        if any(x is None for x in (tailwind,stage,status)):blockers.append('Speed stage/status/Tailwind unresolved')
        participants[pid]=dict(identity=form,form='base' if form.startswith('pokeapi:species:') else 'as_named',
            instance_id=pid,actual_speed=actual,stage=stage,tailwind=tailwind,ability=ability_options[0] if pid!=subject else None,
            ability_active=True,item=item_options[0] if pid!=subject else None,status=status,
            unburden_active=False,activation_evidence=None,other_effects=[])
        if 'Unburden' in ability_options:blockers.append('Unburden activation history unresolved')
        if pid!=subject and (len(ability_options)>1 or len(item_options)>1):blockers.append('known comparison item/ability unresolved')
        if pid==subject:
            pairs=stat_pairs(native,form,'speed',configuration_rule)
            for speed in sorted({c for n,c in pairs if n in retained}):
                for ab in ability_options:
                    for it in item_options:
                        configurations.append(dict(id=f'{speed}:{ab}:{it}',speed=speed,ability=ab,item=it,training=None))
    result=dict(status='unresolved',blockers=sorted(set(blockers)),feasible=None,proof=proof)
    if blockers:return result
    if not configurations:
        return dict(result,status='contradiction',feasible=summary([]),compatible_configurations=[])
    actions=[]
    for rec,pid in zip((first,second),ids):
        e=rec['bindings'].get('resolved_event') or rec['event']
        actions.append(dict(id=e['event_id'],individual=pid,kind='move',move=e['canonical_references']['move']['canonical_id'],
            outcome='completed',activation=dict(state='unknown',coverage_complete=False,evidence=evidence),changes=[],evidence=evidence))
    obs=dict(id=proof['command_source']+':'+subject,battle_id=battle_id,decision_id=proof['command_source'],subject=subject,
        state=dict(participants=participants,field=fv),actions=actions,sequence=[a['id'] for a in actions],
        initial_changes=[],alternatives=[],strict_speed=[],evidence=evidence)
    solved=infer_speed(schema_version=2,observations=[obs],configurations=configurations,profile=PROFILE,max_evaluations=1000000)
    result.update(solver_status=solved['status'],diagnostics=solved.get('diagnostics'),observation=obs,
        configurations=configurations,compatible_configurations=solved.get('compatible_configurations'),
        reference_scope='accepted reconstruction, native abilities; no unobserved suppression/transfer; legal order-item alternatives')
    if solved.get('feasible') is not None:
        current=set(solved['feasible']['values']);form=forms(ps[subject])[0]
        priorities=[]
        for survivor in solved.get('compatible_configurations',[]):
            for history in survivor['histories']:
                metrics=history[obs['id']]['decisions'][0]['metrics']
                priorities.append(len({metrics[a['id']]['priority']['effective'] for a in actions})==1)
        result.update(status='exact' if current else 'contradiction',
            feasible=summary({n for n,c in stat_pairs(native,form,'speed',configuration_rule) if c in current and n in retained}),
            tie_compatible=solved.get('tie_compatible'),current_form_feasible=solved['feasible'],
            same_effective_priority_supported=any(priorities),all_supported_branches_same_priority=bool(priorities) and all(priorities))
    return result


def invert_saved_hit(ep, context, *, native, retained, stat, battle_id, configuration_rule=None):
    """Union all supported legal branches; withhold reduction if any is unknown.

    No later item observations are read. Current-form and native stats remain
    linked through the existing SP/alignment calculator, including Mega forms.
    """
    ps=context.get('pokemon',{});a=ps.get(ep.get('actor_instance_id'),{})
    d=ps.get(ep.get('target_instance_id'),{})
    blocked=[];result=dict(status='unresolved',blockers=blocked,branches=[],feasible=None)
    if ep.get('attribution_status')!='supported' or not ep.get('complete_endpoints') or ep.get('unit')!='absolute':
        blocked.append('direct absolute HP endpoints not supported')
    if a.get('copied_appearance'):blocked.append('copied stats do not constrain native offense')
    move_id=(ep.get('source_move') or {}).get('canonical_id')
    move=database()[1]['moves'].get(move_id,{})
    multi=move.get('name')=='Dual Wingbeat'
    hit=ep.get('hit_resolution') or {}
    if multi and (hit.get('per_hit_status')!='supported' or len(hit.get('per_hit_damage') or [])!=2
            or sum(hit['per_hit_damage'])!=abs(ep.get('delta') or 0)):
        blocked.append('two independently supported hit damages and consistent aggregate required')
    if move.get('name') not in DIRECT|FIXED:blocked.append('existing forward move handler unavailable')
    df=d.get('mechanics',{}).get('battle_stats',{}).get('current',{})
    defense_stats={s:value(df.get(s)) for s in STATS}
    if value(df.get('form_verified')) is not True:blocked.append('verified current-form defender stats unavailable')
    stage={role:{s:value(p.get('stages',{}).get(s,{}).get('value')) for s in STATS} for role,p in [('attacker',a),('defender',d)]}
    for role in stage:
        if any(v is None for v in stage[role].values()):blocked.append(role+' stat stages unresolved')
    field=context.get('field',{})
    weather=value(field.get('weather',{}).get('kind'));terrain=value(field.get('terrain',{}).get('kind'))
    if weather=='sandstorm':weather='sand'
    if weather is None or terrain is None:blocked.append('weather/terrain unresolved')
    conditions=context.get('sides',{}).get(d.get('side'),{}).get('conditions',{})
    screens={s:value(conditions.get(s,{}).get('active')) for s in ('reflect','light_screen','aurora_veil')}
    if any(v is None for v in screens.values()):blocked.append('defender screens unresolved')
    af=forms(a);dfm=forms(d)
    if not af or len(dfm)!=1:blocked.append('current form alternatives unavailable')
    statuses={role:value(p.get('status')) for role,p in [('attacker',a),('defender',d)]}
    if any(v is None for v in statuses.values()):blocked.append('major status unresolved')
    if blocked:return result
    damage_constraint=dict(minimum=ep['before'],maximum=65535) if ep.get('after')==0 else abs(ep['delta'])
    result['observed_damage_constraint']=damage_constraint
    result['ko_censored']=ep.get('after')==0
    union=set();worked=None;item_support={}
    effective_move=dict(move)
    if move.get('name')=='Weather Ball':effective_move['type']={'none':'Normal','sun':'Fire','rain':'Water','sand':'Rock','snow':'Ice'}[weather]
    for form in af:
        pairs=stat_pairs(native,form,stat,configuration_rule)
        candidates=sorted({c for n,c in pairs if n in retained})
        fact=knowledge().facts['pokemon'][form]
        def component(p,kind):
            x=value(p.get(kind,{}).get('identity'))
            return x.get('canonical_id') if isinstance(x,dict) else x
        ab=component(a,'ability');db=component(d,'ability');di=component(d,'item')
        if db is None:
            native_defender_abilities=knowledge().facts['pokemon'][dfm[0]]['ability_names']
            if len(native_defender_abilities)==1:db=native_defender_abilities[0]
        # A supported removal/consumption is a known empty slot even when the
        # old item identity has been cleared. Resolve absence before checking
        # unknown identity or falling back to a form's required stone.
        if value(d.get('item',{}).get('status')) in {'consumed','none','lost','transferred'}:di='none'
        elif di is None:di=knowledge().facts['pokemon'][dfm[0]].get('required_item')
        if db is None or di is None:
            blocked.append('defender current ability/item unresolved');continue
        if multi and name(db,'ability') not in {'Drizzle','Prankster','Levitate','none'}:
            blocked.append('between-hit defender ability state requires explicit per-hit contexts');continue
        abilities=[name(ab,'ability')] if ab else fact['ability_names']
        if multi:
            from damage.engine import BERRIES
            if name(di,'item') in set(BERRIES)|{'Sitrus Berry','Focus Sash','Focus Band'} and set(abilities)!={'Unnerve'}:
                blocked.append('between-hit defender item activation requires explicit per-hit contexts');continue
        item=component(a,'item')
        item_status=value(a.get('item',{}).get('status'))
        if item_status in {'consumed','none','lost','transferred'}:item='none'
        items=[name(item,'item') if item!='none' else 'none'] if item else (
            [fact['required_item']] if fact.get('required_item') else
            ['none']+[i for i in legal_damage_items() if candidate_applicable(i,form)])
        equivalents=sorted({damage_equivalent(i,form,ability,effective_move) for i in items for ability in abilities})
        def mon(p,ident,stats,ability,item,role):
            hp=p.get('hp',{})
            return dict(identity=ident,form='base' if ident.startswith('pokeapi:species:') else 'as_named',level=50,stats=stats,stat_basis='unmodified',
                stages=stage[role],current_hp=value(hp.get('current')) if value(hp.get('unit'))=='absolute' else None,
                maximum_hp=value(hp.get('maximum')) if value(hp.get('unit'))=='absolute' else None,
                ability=ability,item=item,status='toxic' if statuses[role]=='bad_poison' else statuses[role],other_effects=[])
        attacker=mon(a,form,{s:None for s in STATS},abilities[0],equivalents[0],'attacker')
        attacker['stats'][stat]=candidates[0];attacker['metronome_count']=0
        percent=value(a.get('hp',{}).get('displayed_percent'))
        low_options=[True] if percent is not None and percent<=32 else [False] if percent is not None and percent>=34 else [False,True]
        ahp=value(a.get('hp',{}).get('current'));amax=value(a.get('hp',{}).get('maximum'))
        if value(a.get('hp',{}).get('unit'))=='absolute' and ahp is not None and amax is not None:low_options=[ahp*3<=amax]
        attacker['low_hp_ability_active']=low_options[0]
        defender=mon(d,dfm[0],defense_stats,db,di,'defender')
        defender['current_hp']=ep['before']
        # Grounding is only required by the existing engine under active terrain.
        def grounded(ident,ability,item):
            return item=='Iron Ball' or ('Flying' not in knowledge().facts['pokemon'][ident]['types'] and ability!='Levitate' and item!='Air Balloon')
        spread=move.get('target') in {'allAdjacent','allAdjacentFoes'}
        request=dict(profile=PROFILE,attacker=attacker,defender=defender,move=move_id,
            field=dict(format='doubles',weather='sand' if weather=='sandstorm' else weather,terrain=terrain,
                critical=False,**screens,targets_hit=2 if spread else 1,
                attacker_grounded=grounded(form,abilities[0],equivalents[0]),
                defender_grounded=grounded(dfm[0],name(db,'ability'),name(di,'item')),
                helping_hand=False,friend_guard=False,other_effects=[]))
        # These exclusions are explicit reference-reconstruction conditions, not
        # facts invented from an unknown slot. Preserve them in every result.
        assumptions=['accepted event reconstruction from reviewed opening; no genuine coverage gap',
            'no unobserved Helping Hand, Friend Guard, grounding override, suppression or additional damage effect',
            'level 50 pinned Champions profile; native ability alternatives, no unobserved ability transfer']
        oid=ep['episode_id']
        obs=dict(id=oid,battle_id=battle_id,attacker_instance_id=ep['actor_instance_id'],
            target_instance_id=ep['target_instance_id'],stat_epoch=form,damage=damage_constraint,
            damage_kind='direct_move_damage',evidence='saved supported action-target HP resolution '+oid,input=request)
        variables=[]
        for path,values in [('attacker.item',equivalents),('attacker.ability',abilities),
                            ('field.critical',[ep['critical_hit']] if ep.get('critical_hit') is not None else [False,True]),
                            ('attacker.metronome_count',list(range(6)) if 'Metronome' in equivalents else [0])]:
            if len(values)>1:variables.append(dict(id=path,scope='observation',observation_ids=[oid],path=path,values=values))
            else:
                parent,key=path.split('.');request[parent][key]=values[0]
        # Grounding belongs to the chosen item/ability, not an independent coin.
        if any(ab in {'Overgrow','Blaze','Torrent','Swarm'} for ab in abilities) and len(low_options)>1:
            variables.append(dict(id='low_hp_ability',scope='observation',observation_ids=[oid],path='attacker.low_hp_ability_active',values=low_options))
        # Split correlated branches outside the existing Cartesian leaf API.
        solves=[]
        correlated=terrain!='none' and (len(equivalents)>1 or len(abilities)>1)
        for ability,item_choice in ([(ab,it) for ab in abilities for it in equivalents] if correlated else [(None,None)]):
            local=deepcopy(obs);local_variables=deepcopy(variables)
            if correlated:
                local['input']['attacker'].update(ability=ability,item=item_choice)
                local['input']['field']['attacker_grounded']=grounded(form,ability,item_choice)
                local_variables=[v for v in local_variables if v['path'] not in {'attacker.item','attacker.ability'}]
                if item_choice!='Metronome':local_variables=[v for v in local_variables if v['path']!='attacker.metronome_count']
            observations=[local]
            if multi:
                observations=[];hp_before=ep['before']
                for i,amount in enumerate(hit['per_hit_damage'],1):
                    one=deepcopy(local);one['id']=oid+f':hit:{i}';one['damage']=amount
                    one['input']['hit_index']=i;one['input']['defender']['current_hp']=hp_before
                    observations.append(one);hp_before-=amount
                for v in local_variables:
                    v['observation_ids']=[o['id'] for o in observations]
                    v['scope']='observation' if v['path']=='field.critical' else 'shared'
            patterns=[None]
            if multi:
                known_hits=hit.get('hits') or [{},{}]
                patterns=list(product(*[[h['critical_hit']] if type(h.get('critical_hit')) is bool else [False,True] for h in known_hits]))
                if ep.get('critical_hit') is True:patterns=[p for p in patterns if any(p)]
                if ep.get('critical_hit') is False:patterns=[p for p in patterns if not any(p)]
                local_variables=[v for v in local_variables if v['path']!='field.critical']
            for pattern in patterns:
                if pattern is not None:
                    for one,critical in zip(observations,pattern):one['input']['field']['critical']=critical
                solved=infer_attack_stat(observations=observations,candidate_stats=candidates,stat=stat,ruleset=PROFILE,
                    variables=local_variables,limits=dict(max_assignments=4096,max_evaluations=1000000))
                solved['critical_pattern']=pattern
                solves.append((deepcopy(local),local_variables,solved))
        bad=[s for _,_,s in solves if s['status'] not in {'exact','conditional','empty'}]
        if bad:
            solved=bad[0]
        elif len(solves)>1:
            solved=dict(status='conditional',feasible=summary({v for _,_,s in solves for v in s['feasible']['values']}),
                diagnostics=[],work={k:sum(s['work'][k] for _,_,s in solves) for k in solves[0][2]['work']},
                scenarios=[dict(assignment=dict(ability=o['input']['attacker']['ability'],item=o['input']['attacker']['item'],grounded=o['input']['field']['attacker_grounded'],critical_hits=s.get('critical_pattern'),**sc['assignment']),feasible=sc['feasible'])
                    for o,_,s in solves for sc in s['scenarios']])
        else:solved=solves[0][2]
        result['branches'].append(dict(form=form,legal_items=items,item_effect_classes=equivalents,
            abilities=abilities,status=solved['status'],feasible=solved.get('feasible'),
            diagnostics=solved['diagnostics'],work=solved['work'],assumptions=assumptions,
            scenarios=[dict(assignment=s['assignment'],feasible=s['feasible']) for s in solved['scenarios']]))
        if solved['status'] not in {'exact','conditional','empty'}:
            blocked.append('solver retains unsupported alternatives: '+str(solved['diagnostics']));continue
        feasible=set(solved['feasible']['values'])
        union.update(n for n,c in pairs if c in feasible and n in retained)
        for scenario in solved['scenarios']:
            assignment=scenario['assignment']
            effect=next((v for k,v in assignment.items() if k.startswith('attacker.item')),assignment.get('item',request['attacker']['item']))
            ability=next((v for k,v in assignment.items() if k.startswith('attacker.ability')),assignment.get('ability',request['attacker']['ability']))
            native_values={n for n,c in pairs if c in scenario['feasible']['values'] and n in retained}
            for actual_item in items:
                if damage_equivalent(actual_item,form,ability,effective_move)==effect:
                    item_support.setdefault(actual_item,set()).update(native_values)
        if worked is None:worked=dict(observation=obs,variables=variables,result=solved,
            per_hit_damage=hit.get('per_hit_damage') if multi else None,aggregate_is_not_an_additional_observation=multi)
    if blocked:return result
    result.update(status='exact' if union else 'contradiction',feasible=summary(union),
                  worked_example=worked,observation_count=2 if multi else 1,
                  item_support={item:summary(values) for item,values in item_support.items()})
    return result
