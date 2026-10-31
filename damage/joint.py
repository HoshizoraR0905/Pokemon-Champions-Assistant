"""Exact compact SP filtering of the existing Speed configuration identities.

Each row remains one alignment, item, ability and budget-coupled Cartesian SP
domain. Damage restricts point domains inside that row; it never combines two
builds or substitutes independent marginal Speed and offensive-stat ranges.
"""
from collections import Counter
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from time import perf_counter, process_time

from knowledge.champions_stats import ChampionsStats, STATS, adjustment_factors
from knowledge.stat_feasibility import summary
from speed_order.core import knowledge, name, identity_key
from speed_order.forms import mega_base_form, published_ability
from .engine import calculate
from .selectors import select_stats
from .data import database
from .items import damage_equivalent


class FrozenPoints(list):
    """JSON-compatible immutable SP values shared by survivor snapshots."""
    def _immutable(self,*args,**kwargs):raise TypeError('SP values are immutable; replace the point domain')
    __setitem__=__delitem__=append=extend=insert=pop=remove=clear=sort=reverse=__iadd__=__imul__=_immutable
    def __deepcopy__(self,memo):return self


@lru_cache(maxsize=1)
def coverage():
    path=Path(__file__).parent/'data/offensive-coverage-v1.json'
    result=json.loads(path.read_text())
    facts=Path(__file__).resolve().parents[1]/'knowledge/data/champions_facts.json'
    if hashlib.sha256(facts.read_bytes()).hexdigest()!=result['knowledge_facts_sha256']:
        raise ValueError('Damage item/ability coverage requires re-audit')
    return result


def legal_damage_items():
    return list(coverage()['legal_items'])


def restrict_budget(training):
    domains=training['point_domains']
    if set(domains)!=set(STATS):raise ValueError('All six SP domains required')
    for values in domains.values():
        if not values or any(type(v) is not int or not 0<=v<=32 for v in values):
            raise ValueError('Invalid complete SP domain')
    minimum=sum(min(v) for v in domains.values())
    if minimum>66:return False
    for stat,values in domains.items():
        domains[stat]=FrozenPoints(sorted({v for v in values if minimum-min(values)+v<=66}))
    adjustment_factors(training['alignment'])
    return True


def allocation_count(training):
    """Count complete legal six-stat allocations without enumerating them."""
    return _allocation_count(tuple(tuple(training['point_domains'][s]) for s in STATS))


@lru_cache(maxsize=8192)
def _allocation_count(domains):
    counts={0:1}
    for values in domains:
        next_counts=Counter()
        for total,count in counts.items():
            for point in values:
                if total+point<=66:next_counts[total+point]+=count
        counts=next_counts
    return sum(counts.values())


@lru_cache(maxsize=256)
def stat_table(form,stat,up,down):
    model=ChampionsStats(form,form='as_named' if knowledge().entities[form].form_id else 'base')
    factor=adjustment_factors(dict(increase=up,decrease=down))[stat]
    return {r['training_points']:r['actual_stat'] for r in model.attainable(stat,adjustments=[factor])['configurations']}


def project_joint(configs, stat):
    values=set();speeds=set();allocations=0
    for c in configs:
        t=c['training'];a=t['alignment']
        table=stat_table(c['form'],stat,a['increase'],a['decrease'])
        speed=stat_table(c['form'],'speed',a['increase'],a['decrease'])
        values.update(table[v] for v in t['point_domains'][stat])
        speeds.update(speed[v] for v in t['point_domains']['speed'])
        allocations+=allocation_count(t)*len(c.get('item_options',[c['item']]))
    return dict(stat=stat,values=summary(values),speed=summary(speeds),
                configuration_classes=sum(len(c.get('item_options',[c['item']])) for c in configs),
                compact_rows=len(configs),joint_allocations=allocations,
                items=sorted({i for c in configs for i in c.get('item_options',[c['item']])}),abilities=sorted({c['ability'] for c in configs}),
                ids=[c['id'] for c in configs])


def concrete_ids(configs):
    """Stable hidden identities even when item groups split after a hit."""
    return {c.get('speed_parent_id',c['id'])+'@'+i if 'item_options' in c else c['id']
            for c in configs for i in c.get('item_options',[c['item']])}


def copy_training(training):
    # Shared value lists are read-only. restrict_budget replaces lists; it never
    # edits their contents. Narrowing a row copies this mapping first.
    return dict(training,alignment=dict(training['alignment']),point_domains=dict(training['point_domains']))


def filter_joint(configurations, observations, *, max_evaluations=100000,
                 exhaustive_legal_alternatives=False, progress=None, on_update=None, prior=None, item_events=(), evaluation_cache=None):
    start=perf_counter();configs=[];memo={} if evaluation_cache is None else evaluation_cache;updates=[];work=0;cache_hits=0;outcome_hits=0;unresolved=[];last_time=-1;unknown_ids=set()
    if prior:
        previous=prior['updates']
        if [u['id'] for u in previous]!=[o['id'] for o in observations[:len(previous)]]:
            raise ValueError('Checkpoint does not match observation prefix')
        if any(u.get('observation_fingerprint')!=hashlib.sha256(json.dumps(o,sort_keys=True).encode()).hexdigest()
               for u,o in zip(previous,observations)):
            raise ValueError('Checkpoint observation inputs changed')
        configurations=prior['configurations'];updates=list(previous);unresolved=list(prior['unresolved'])
        unknown_ids={cid for issue in unresolved for cid in issue.get('configuration_ids',[issue['id']])}
        observations=observations[len(previous):]
        last_time=previous[-1]['timestamp'] if previous else -1
    for original in configurations:
        c=dict(original,training=copy_training(original['training']))
        if not restrict_budget(c['training']):raise ValueError('One feasible persistent six-stat training domain required')
        if any(i!='none' and i not in legal_damage_items() for i in c.get('item_options',[c['item']])):
            raise ValueError('Configuration contains a nonlegal pinned Champions item')
        fact=knowledge().facts['pokemon'][c['form']]
        if c['ability'] not in fact['ability_names']:raise ValueError('Active ability must be native to the current form')
        if fact.get('required_item') and c.get('item_options',[c['item']])!=[fact['required_item']]:
            raise ValueError('Mega configuration and held stone conflict')
        if mega_base_form(c['form']):
            base=mega_base_form(c['form'])
            if c.get('original_form',base)!=base:raise ValueError('Original and Mega form conflict')
            if c.get('original_ability') is not None and c['original_ability'] not in knowledge().facts['pokemon'][base]['ability_names']:
                raise ValueError('Illegal original pre-Mega ability')
        source=c.get('observed_build')
        if source and published_ability(source['species'],source['ability'],c['form'])['active_ability']!=c['ability']:
            raise ValueError('Published/current ability mapping conflict')
        configs.append(c)
    if len({c['id'] for c in configs})!=len(configs):raise ValueError('Persistent configuration IDs must be unique')

    result=None
    for obs in observations:
        hit_start=perf_counter();hit_cpu=process_time();hit_work=work;hit_cache=cache_hits;hit_outcome=outcome_hits
        if obs['timestamp']<last_time:raise ValueError('Observations must be chronological')
        last_time=obs['timestamp']
        if obs.get('target_side')!='self' or obs.get('admitted') is not True:raise ValueError('Only admitted own received damage can filter configurations')
        if type(obs.get('damage')) is not int or obs['damage']<=0:raise ValueError('Exact positive integer uncensored damage required')
        template=obs['input'];form=identity_key(template['attacker']['identity'],template['attacker']['form'])
        if any(c['form']!=form for c in configs):raise ValueError('Damage epoch/form mismatch; explicit transformation transport required')
        alternatives=obs.get('field_alternatives',[{}])
        if not isinstance(alternatives,list) or not 1<=len(alternatives)<=64:raise ValueError('Supply 1..64 explicit field alternatives')
        if template['attacker']['level']!=50 or template['defender']['level']!=50:raise ValueError('This Champions integration requires level 50')
        if template['profile']!='showdown-champions-reference-v1':raise ValueError('Explicit provisional Champions damage reference required')
        request_epoch=hashlib.sha256(json.dumps([template,alternatives],sort_keys=True).encode()).hexdigest()
        _,data,_=database();move_name=name(template['move'],'move')
        move=next((m for m in data['moves'].values() if m['name']==move_name),None)
        selector=select_stats(move_name,move['category']) if move else None
        stat=selector['offensive_stat'] if selector else 'attack';constrains=bool(selector and selector['constrains_opponent_offensive_stat'])
        projection_start=perf_counter()
        before=project_joint(configs,stat) if constrains else None
        before_stats={s:project_joint(configs,s) for s in ('attack','special_attack')}
        before_projection_seconds=perf_counter()-projection_start;loop_start=perf_counter()
        kept=[];excluded=[];membership_excluded=[];item_evidence_excluded=[];team_excluded=[];issues=[];issue_groups={};outcomes={};critical=set();witnesses={}
        from battle_evidence.team_items import exclusions
        forbidden=exclusions(item_events,battle_id=obs.get('battle_id'),individual=obs.get('attacker'),at=obs['timestamp'])
        orb=obs.get('life_orb',{})
        if orb.get('attack_event_id') not in (None,obs['source_event_id']):raise ValueError('Life Orb evidence belongs to a different attack')

        def evaluate(c,item):
            nonlocal work,cache_hits,outcome_hits
            training=c['training'];a=training['alignment']
            table=stat_table(c['form'],stat,a['increase'],a['decrease']) if constrains else {}
            points=training['point_domains'][stat] if constrains else [None]
            history=c.get('consumed_items',{})
            # This cache is local to one observation, including its complete
            # request, alternatives and recoil evidence. Other epochs never reuse it.
            cid=c.get('speed_parent_id',c['id'])+'@'+item if 'item_options' in c else c['id']
            from battle_evidence.item_policy import action_item
            current_item=action_item(item,item_events,battle_id=obs.get('battle_id'),individual=obs.get('attacker'),at=obs.get('action_time',obs['timestamp']),available_at=obs['timestamp'])
            if current_item is None:return ((),None,False,{},set(),False)
            if current_item=='unknown':return (tuple(points),dict(reason='Unresolved item transfer history',item=item),False,{},set(),False)
            compute_item=damage_equivalent(current_item,c['form'],c['ability'],move) if move else current_item
            key=(c['form'],c['ability'],compute_item,tuple((p,table[p]) for p in points) if constrains else (),tuple(sorted(history.items())),cid in unknown_ids)
            if key in outcomes:
                outcome_hits+=1;return outcomes[key]
            allowed=[];matches_by_point={};boosts=set();no_boost=False;berry=False;problem=None
            if item in obs.get('unresolved_item_histories',[]):problem=dict(reason='Reviewed stage history has an unresolved item-dependent reset/consumption; retain prior configurations',item=item)
            elif not move:problem=dict(reason='Move definition absent from pinned Champions reference; configuration retained')
            elif cid in unknown_ids:problem=dict(reason='earlier unsupported damage history; configuration retained')
            elif type(template['defender'].get('current_hp')) is not int or obs['damage']>=template['defender']['current_hp']:
                problem=dict(reason='unknown or censored recipient HP')
            for point in ([] if problem else points):
                request=deepcopy(template)
                request['attacker'].update(identity=c['form'],form='as_named' if knowledge().entities[c['form']].form_id else 'base',item=current_item,ability=c['ability'])
                if constrains:
                    request['attacker']['stats']={s:None for s in STATS if s!='hp'}
                    request['attacker']['stats'][stat]=table[point]
                if obs['target'] in history:
                    if request['defender']['item'] not in ('none',history[obs['target']]):raise ValueError('Consumed-item history conflicts with supplied target item')
                    request['defender']['item']='none'
                results=[]
                for alternative_index,alternative in enumerate(alternatives):
                    branch=deepcopy(request);branch['field'].update(alternative)
                    # The epoch covers every unchanged request/field input. These
                    # are precisely the fields varied below; no trace/provenance
                    # trees need to be retained for tens of thousands of rolls.
                    memo_key=(request_epoch,c['form'],c['ability'],compute_item,
                              table[point] if constrains else None,request['defender']['item'],alternative_index)
                    if memo_key not in memo:
                        if work>=max_evaluations:problem=dict(reason='forward evaluation limit; configuration retained');break
                        compute_branch=deepcopy(branch);compute_branch['attacker']['item']=compute_item
                        value=calculate(compute_branch)
                        memo[memo_key]={k:value[k] for k in ('status','applied_modifiers','unsupported_mechanics','unresolved_inputs')}
                        memo[memo_key]['distribution']={'rolls':value['distribution']['rolls']} if value['distribution'] else None
                        work+=1
                    else:cache_hits+=1
                    result=memo[memo_key]
                    if result['status']!='exact_reference':
                        problem=dict(reason=result['status'],diagnostics=result['unsupported_mechanics']+result['unresolved_inputs']);break
                    if obs['damage'] in result['distribution']['rolls']:results.append((branch,result))
                if problem:break
                if results:
                    allowed.append(point);hypotheses=[];triggers=[]
                    for branch,result in results:
                        modifiers={m['name'] for m in result['applied_modifiers'] if m['name'] in {item,c['ability']} and m.get('fixed_point',0)>4096}
                        if c['ability']=='Adaptability' and any(m['name']=='STAB' and m.get('fixed_point')==8192 for m in result['applied_modifiers']):modifiers.add('Adaptability')
                        boosts.update(modifiers);no_boost |= not modifiers
                        triggers.append(any(m['name']==request['defender']['item'] and m['stage']=='final' for m in result['applied_modifiers']))
                        hypotheses.append(dict(critical=branch['field']['critical'],rolls=[85+i for i,d in enumerate(result['distribution']['rolls']) if d==obs['damage']]))
                    if len(set(triggers))>1:problem=dict(reason='berry consumption differs across unresolved state alternatives');break
                    berry |= any(triggers);matches_by_point[point]=hypotheses
            answer=(tuple(allowed),problem,berry,matches_by_point,boosts,no_boost);outcomes[key]=answer;return answer

        for index,c in enumerate(configs):
            # Published move slots are templates, not hard constraints on training.
            groups={}
            for item in c.get('item_options',[c['item']]):
                if item in forbidden:
                    cid=c.get('speed_parent_id',c['id'])+'@'+item if 'item_options' in c else c['id']
                    excluded.append(cid);team_excluded.append(cid);continue
                from battle_evidence.item_policy import action_item
                from battle_evidence.life_orb import evidence_allows
                current_item=action_item(item,item_events,battle_id=obs.get('battle_id'),individual=obs.get('attacker'),at=obs.get('action_time',obs['timestamp']),available_at=obs['timestamp'])
                if item in obs.get('item_evidence_exclusions',[]) or current_item is None or not evidence_allows(orb,item=current_item,ability=c['ability'],move=move or {},attack_event_id=obs['source_event_id']):
                    cid=c.get('speed_parent_id',c['id'])+'@'+item if 'item_options' in c else c['id']
                    excluded.append(cid);item_evidence_excluded.append(cid);continue
                allowed,problem,berry,hypotheses,boosts,no_boost=evaluate(c,item)
                cid=c.get('speed_parent_id',c['id'])+'@'+item if 'item_options' in c else c['id']
                if not problem and not allowed:excluded.append(cid);continue
                group_key=(allowed,json.dumps(problem,sort_keys=True),berry)
                group=groups.setdefault(group_key,dict(items=[],problem=problem,allowed=allowed,berry=berry,hypotheses={},boosts=set(),no_boost=False))
                group['items'].append(item);group['boosts'].update(boosts);group['no_boost']|=no_boost
                for point,hs in hypotheses.items():
                    critical.update(h['critical'] for h in hs)
                    if not problem:
                        a=c['training']['alignment']
                        value=stat_table(c['form'],stat,a['increase'],a['decrease'])[point] if constrains else None
                        witness_key=(item,c['ability'],value)
                        if witness_key not in witnesses:
                            witnesses[witness_key]=dict(item=item,ability=c['ability'],stat=stat,value=value,hypotheses=deepcopy(hs))
                        else:
                            merged={h['critical']:set(h['rolls']) for h in witnesses[witness_key]['hypotheses']}
                            for h in hs:merged.setdefault(h['critical'],set()).update(h['rolls'])
                            witnesses[witness_key]['hypotheses']=[dict(critical=k,rolls=sorted(v)) for k,v in sorted(merged.items())]
                if problem:
                    issue_groups.setdefault(json.dumps(problem,sort_keys=True),dict(**problem,configuration_ids=[]))['configuration_ids'].append(cid)
                    unknown_ids.add(cid)
            for group in groups.values():
                row=dict(c)
                if 'item_options' in c:
                    options=group['items'];parent=c['speed_parent_id']
                    row.update(item=options[0],item_options=options,id=parent+'@group:'+hashlib.sha256(json.dumps(options).encode()).hexdigest()[:16])
                if not group['problem'] and constrains:
                    t=copy_training(c['training']);t['point_domains'][stat]=list(group['allowed'])
                    if not restrict_budget(t):continue
                    row['training']=t
                if group['berry']:
                    row['consumed_items']=dict(c.get('consumed_items',{}),**{obs['target']:template['defender']['item']})
                if not group['problem']:
                    row['offensive_modifiers']=sorted(group['boosts']);row['without_offensive_boost']=group['no_boost']
                kept.append(row)
            if progress and index%250==0:progress(dict(observation=obs['id'],rows_done=index,rows_total=len(configs),forward_evaluations=work))
        loop_seconds=perf_counter()-loop_start;projection_start=perf_counter()
        issues=[dict(v,id=v['configuration_ids'][0],configuration_count=len(v['configuration_ids'])) for v in issue_groups.values()]
        configs=kept;unresolved+=issues
        supported=[c for c in configs if not (concrete_ids([c]) & unknown_ids)];unknown=[c for c in configs if concrete_ids([c]) & unknown_ids]
        after=project_joint(configs,stat) if constrains else None
        nonnumerical=set(membership_excluded+item_evidence_excluded+team_excluded)
        updates.append(dict(forward_evaluations=work-hit_work,id=obs['id'],timestamp=obs['timestamp'],selector=selector,before=before,after=after,
            observation_fingerprint=hashlib.sha256(json.dumps(obs,sort_keys=True).encode()).hexdigest(),
            supported_after=project_joint(supported,stat) if constrains else None,
            unresolved_after=project_joint(unknown,stat) if constrains else None,
            before_offensive_stats=before_stats,
            after_offensive_stats={s:project_joint(configs,s) for s in ('attack','special_attack')},
            critical_hypotheses=sorted(critical),excluded_ids=excluded,unresolved=issues,
            damage_witnesses=list(witnesses.values()),
            move_membership_excluded_ids=membership_excluded,item_evidence_excluded_ids=item_evidence_excluded,
            team_item_excluded_ids=team_excluded,team_item_excluded_items=sorted(forbidden),
            numerical_excluded_ids=[i for i in excluded if i not in nonnumerical],
            consumed_items={c['id']:c['consumed_items'] for c in configs if c.get('consumed_items')},
            offensive_stat_information='conditional exact set' if constrains else 'Foul Play uses our Attack; no direct opponent Attack constraint'))
        result=_joint_result(configs,updates,unresolved,unknown_ids,exhaustive_legal_alternatives,work,len(memo),start)
        updates[-1]['projection_seconds']=before_projection_seconds+perf_counter()-projection_start
        updates[-1]['filter_loop_seconds']=loop_seconds
        updates[-1]['incremental_cpu_seconds']=process_time()-hit_cpu
        updates[-1]['cache_hits']=cache_hits-hit_cache
        updates[-1]['outcome_cache_hits']=outcome_hits-hit_outcome
        updates[-1]['incremental_seconds']=perf_counter()-hit_start
        if on_update:on_update(result)
    return result if result is not None else _joint_result(configs,updates,unresolved,unknown_ids,exhaustive_legal_alternatives,work,len(memo),start)


def _joint_result(configs,updates,unresolved,unknown_ids,exhaustive_legal_alternatives,work,cached_inputs,start):
    items=sorted({i for c in configs for i in c.get('item_options',[c['item']])});abilities=sorted({c['ability'] for c in configs})
    unresolved_configs=[c for c in configs if concrete_ids([c]) & unknown_ids];supported=[c for c in configs if not (concrete_ids([c]) & unknown_ids)]
    modifiers=sorted({m for c in supported for m in c.get('offensive_modifiers',[])})
    exhaustive=bool(exhaustive_legal_alternatives and not unresolved_configs)
    return dict(status='partial_reference' if unresolved_configs else 'conditional_reference',certified_champions_eliminations=False,
        configurations=configs,updates=list(updates),unresolved=list(unresolved),
        consumed_items={c['id']:c['consumed_items'] for c in configs if c.get('consumed_items')},
        requirements=dict(items=items,abilities=abilities,
            necessary_item=items[0] if len(items)==1 and configs and exhaustive else None,
            without_offensive_boost_possible=any(c.get('without_offensive_boost') for c in supported) if supported else None,
            possible_offensive_modifiers=modifiers,
            required_modifier_choices=modifiers if exhaustive and supported and all(not c.get('without_offensive_boost') for c in supported) else [],
            unresolved_items=sorted({i for c in unresolved_configs for i in c.get('item_options',[c['item']])}),
            supported_items=sorted({i for c in supported for i in c.get('item_options',[c['item']])}),
            scope='Only exhaustive supported supplied alternatives; never a Bayesian probability',exhaustive=exhaustive),
        work=dict(forward_evaluations=work,cached_inputs=cached_inputs,seconds=perf_counter()-start))
