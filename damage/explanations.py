"""Exact item pushforwards and reconstructible witnesses of persistent rows.

This projects existing survivors. It never solves each item's marginals in
isolation, creates item identities, or assigns probability to legal branches.
"""
from collections import defaultdict
from copy import deepcopy
import json
from time import perf_counter
from knowledge.champions_stats import STATS,ChampionsStats
from knowledge.stat_feasibility import summary
from speed_order.core import knowledge,name
from .joint import concrete_ids,project_joint,stat_table
from .items import damage_equivalent
from .data import database
from .engine import calculate


def item_id(c,item):
    return c.get('speed_parent_id',c['id'])+'@'+item if 'item_options' in c else c['id']


def reconstruct(c,stat,value,observations,*,item_events=()):
    """Select one full SP extension and independently forward-replay ALL hits."""
    from battle_evidence.item_policy import action_item
    t=c['training'];a=t['alignment'];table=stat_table(c['form'],stat,a['increase'],a['decrease'])
    matching=[p for p in t['point_domains'][stat] if table[p]==value]
    if not matching:return None
    points={s:min(t['point_domains'][s]) for s in STATS};points[stat]=matching[0]
    if sum(points.values())>66:return None
    model=ChampionsStats(c['form'],form='as_named' if knowledge().entities[c['form']].form_id else 'base')
    hp_table=stat_table(c['form'],'hp',a['increase'],a['decrease'])
    maximums={o['input']['attacker'].get('maximum_hp') for o in observations if o['input']['attacker'].get('maximum_hp') is not None}
    currents=[o['input']['attacker'].get('current_hp') for o in observations if o['input']['attacker'].get('current_hp') is not None]
    hp_points=[p for p in t['point_domains']['hp'] if (not maximums or maximums=={hp_table[p]}) and (not currents or max(currents)<=hp_table[p]) and sum(points.values())-points['hp']+p<=66]
    if not hp_points:return None
    points['hp']=min(hp_points)
    stats=model.calculate(points,a)['stats']
    if c.get('speed') is not None and stats['speed']!=c['speed']:return None
    consumed={};hits=[]
    for obs in observations:
        current=action_item(c['item'],item_events,battle_id=obs.get('battle_id'),individual=obs.get('attacker'),at=obs.get('action_time',obs['timestamp']),available_at=obs['timestamp'])
        if current is None or c['item'] in obs.get('item_evidence_exclusions',[]):return None
        request=deepcopy(obs['input']);request['attacker'].update(identity=c['form'],form='as_named' if knowledge().entities[c['form']].form_id else 'base',item=current,ability=c['ability'],stats={s:stats[s] for s in STATS if s!='hp'},maximum_hp=stats['hp'])
        if obs['target'] in consumed:request['defender']['item']='none'
        matched=None
        for alt in obs.get('field_alternatives',[{}]):
            branch=deepcopy(request);branch['field'].update(alt);result=calculate(branch)
            if result['status']!='exact_reference':continue
            rolls=[85+i for i,d in enumerate(result['distribution']['rolls']) if d==obs['damage']]
            if rolls:
                matched=dict(observation=obs['id'],critical=branch['field']['critical'],roll=rolls[0],predicted_damage=obs['damage'],forward_input=branch,modifiers=result['applied_modifiers']);break
        if matched is None:return None
        item=request['defender']['item']
        if any(m['name']==item and m['stage']=='final' for m in result['applied_modifiers']):consumed[obs['target']]=item
        hits.append(matched)
    return dict(configuration_id=c['id'],source_speed_parent=c.get('speed_parent_id',c['id']),form=c['form'],initial_item=c['item'],ability=c['ability'],original_ability=c.get('original_ability'),alignment=a,nature=c.get('observed_build',{}).get('nature'),training_points=points,total_sp=sum(points.values()),stats=stats,stat=stat,value=value,hits=hits,scope='One complete joint SP extension of an existing persistent survivor; rolls/criticals are independent per hit')


def explain_items(result,observations,*,original_configurations=(),item_events=(),requested_values=(140,160,180,206)):
    start=perf_counter();stat=result['updates'][-1]['selector']['offensive_stat'];unknown={cid for u in result['unresolved'] for cid in u.get('configuration_ids',[u['id']])}
    by=defaultdict(list);unknown_by=defaultdict(list);supported_by=defaultdict(list)
    for c in result['configurations']:
        for item in c.get('item_options',[c['item']]):
            row=dict(c,item=item,item_options=[item]) if 'item_options' in c else c
            by[item].append(row);(unknown_by if item_id(c,item) in unknown else supported_by)[item].append(row)
    original_ids={item_id(c,i):i for c in original_configurations for i in c.get('item_options',[c['item']])}
    numerical=defaultdict(int);direct=defaultdict(int)
    for u in result['updates']:
        for cid in u['numerical_excluded_ids']:
            if cid in original_ids:numerical[original_ids[cid]]+=1
        for cid in u['item_evidence_excluded_ids']:
            if cid in original_ids:direct[original_ids[cid]]+=1
    policy=result.get('item_policy',{});items=sorted(set(by)|set(policy.get('retained',[]))|set(policy.get('dormant',[]))|set(original_ids.values()))
    team_excluded=set(result.get('team_item_constraint',{}).get('excluded_items',[]))
    team_excluded.update(i for u in result['updates'] for i in u.get('team_item_excluded_items',[]))
    items=sorted(set(items)|team_excluded)
    _,data,_=database();move=next(m for m in data['moves'].values() if m['name']==name(observations[-1]['input']['move'],'move'))
    catalogs=[];all_supported=set();all_unknown=set()
    from battle_evidence.item_policy import item_state
    state=item_state(item_events,battle_id=observations[-1].get('battle_id'),individual=observations[-1].get('attacker'),at=observations[-1]['timestamp'])
    for item in items:
        evaluated=project_joint(supported_by[item],stat);unresolved=project_joint(unknown_by[item],stat);overall=project_joint(by[item],stat)
        all_supported.update(evaluated['values']['values']);all_unknown.update(unresolved['values']['values'])
        states=[]
        if evaluated['configuration_classes']:states.append('supported')
        if unresolved['configuration_classes']:states.append('unresolved')
        if item in team_excluded:states.append('excluded_by_team_uniqueness')
        elif item in policy.get('dormant',[]):states.append('policy_dormant')
        if item in policy.get('rescued',[]):states.append('rescue_hypothesis')
        if state['confirmed_item']==item:states.append('source_confirmed')
        if not by[item] and item not in policy.get('dormant',[]) and item not in team_excluded:
            if direct[item]:states.append('excluded_by_item_evidence')
            elif numerical[item]:states.append('excluded_by_damage')
            else:states.append('not_in_active_domain')
        # Critical supports intersect the final persistent survivors, not the
        # union of independently feasible item/stat/critical marginals.
        pairs={(c['ability'],stat_table(c['form'],stat,c['training']['alignment']['increase'],c['training']['alignment']['decrease'])[p]) for c in supported_by[item] for p in c['training']['point_domains'][stat]}
        critical=[]
        for update in result['updates']:
            values=defaultdict(set)
            for w in update['damage_witnesses']:
                if w['item']==item and (w['ability'],w['value']) in pairs:
                    for h in w['hypotheses']:values[h['critical']].add(w['value'])
            critical.append(dict(observation=update['id'],states=[dict(critical=crit,values=summary(v)) for crit,v in sorted(values.items())]))
        for projection in (overall,evaluated,unresolved):projection.pop('ids',None)
        neutral=bool(supported_by[item]) and all(damage_equivalent(item,c['form'],c['ability'],move)=='none' for c in supported_by[item])
        catalogs.append(dict(item=item,states=states,overall=overall,evaluated=evaluated,unresolved=unresolved,critical=critical,numerical_exclusions=numerical[item],direct_item_exclusions=direct[item],evidence_ids=[o['id'] for o in observations],audited_direct_hit_neutral=neutral))
    expected=project_joint([c for c in result['configurations'] if not (concrete_ids([c])&unknown)],stat)['values']['values']
    assert set(expected)==all_supported,'Evaluated item union differs from joint support'
    groups={}
    for row in catalogs:
        # Group only equal audited neutral projections; preserve concrete items.
        key=json.dumps([row['states'],row['evaluated']['values'],row['unresolved']['values'],row['critical']],sort_keys=True) if row['audited_direct_hit_neutral'] else row['item']
        group=groups.setdefault(key,dict(label='No held item / audited direct-hit-neutral items' if row['audited_direct_hit_neutral'] else row['item'],items=[],states=row['states'],evaluated=row['evaluated']['values'],unresolved=row['unresolved']['values'],overall=row['overall']['values'],critical=row['critical'],configuration_classes=0))
        group['items'].append(row['item']);group['configuration_classes']+=row['overall']['configuration_classes']
    wanted=set(requested_values)
    values=sorted(all_supported)
    if values:wanted.update([values[0],values[len(values)//2],values[-1]])
    witnesses=[]
    for value in sorted(wanted):
        witness=None
        for item,rows in supported_by.items():
            for c in rows:
                witness=reconstruct(c,stat,value,observations,item_events=item_events)
                if witness:break
            if witness:break
        witnesses.append(dict(value=value,status='evaluated_witness' if witness else 'evaluated_witness_unavailable' if value in all_supported else 'unresolved_only' if value in all_unknown else 'not_supported',witness=witness))
    return dict(stat=stat,observations=[o['id'] for o in observations],overall=project_joint(result['configurations'],stat)['values'],evaluated_union=summary(all_supported),unresolved_union=summary(all_unknown),items=catalogs,groups=list(groups.values()),witnesses=witnesses,seconds=perf_counter()-start,definition='S_i(t) is an existential projection of the same complete persistent joint survivors; unresolved rows are excluded from evaluated unions',critical_scope='Each per-hit critical support intersects the final surviving item/ability/stat tuples; concrete witnesses replay the entire prefix')
