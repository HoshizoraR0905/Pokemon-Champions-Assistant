"""Observed source endpoints supplement a projection, never persistent state.

An initial non-full reading during an action is not automatically its baseline.
Require a captured visibility onset with three unchanged high-rate readings
before a decrease. A full-scale onset can establish its own upper-bound value.
"""
from copy import deepcopy
import math


def full_hp_baseline(*,maximum=None,displayed_percent=None,proof):
    """No absolute HP is manufactured from a percentage with unknown maximum."""
    if maximum is not None:return dict(value=maximum,maximum=maximum,unit='absolute',knowledge='derived',provenance=deepcopy(proof))
    if displayed_percent==100:return dict(value=100,maximum=None,unit='displayed_percent',knowledge='derived',provenance=deepcopy(proof))
    return None


def repair_saved_endpoints(projection,records,contexts,aliases):
    """Scoped saved-evidence repairs; never insert or alter a source HUD receipt."""
    from .hp_causes import ADMITTED
    out=deepcopy(projection);audits=[]
    def event(r):return r.get('bindings',{}).get('resolved_event') or r['event']
    def time(r):return event(r).get('attributes',{}).get('observation_time',0)
    def actor(r):
        pid=r.get('bindings',{}).get('actor',{}).get('pokemon_instance_id')
        return aliases.get(pid,pid)
    admitted=[r for r in records if r.get('application_status') in ADMITTED]
    byid={r['event']['event_id']:r for r in records}
    for ep in out.get('episodes',[]):
        pid=ep.get('target_instance_id');canonical=aliases.get(pid,pid)
        source=byid.get(ep.get('source_event_id'))
        if not source or not (ep.get('cause') or {}).get('kind')=='move':continue
        start=time(source);proof=None;old=dict(before=ep.get('before'),after=ep.get('after'),reasons=deepcopy(ep.get('reasons')))
        if ep.get('before') is None:
            p=contexts.get(ep['source_event_id'],{}).get('pokemon',{}).get(pid,{})
            config=p.get('known_configuration') or {}
            if config.get('configuration_instance_id')!='own_team_6' or config.get('fields',{}).get('hp',{}).get('value')!=194:continue
            entries=[r for r in admitted if event(r)['event_type']=='send_out' and actor(r)==canonical and time(r)<=start]
            if len(entries)!=1:continue
            entry=entries[0]
            intervening=[r for r in admitted if time(entry)<time(r)<start and actor(r)==canonical and event(r)['event_type']=='hp_change']
            prior_damage=[e for e in out.get('episodes',[]) if e is not ep and aliases.get(e.get('target_instance_id'),e.get('target_instance_id'))==canonical
                and (e.get('source_event') or {}).get('time',float('inf'))<start and (e.get('source_event') or {}).get('time',0)>=time(entry)]
            numeric=[r for r in admitted if time(entry)<time(r)<start and actor(r)==canonical and event(r)['event_type']=='hud_observation'
                and isinstance(((event(r)['attributes'].get('hp') or {}).get('value')),dict)
                and ((event(r)['attributes'].get('hp') or {})['value'].get('current') not in (None,194))]
            if intervening or prior_damage or numeric:continue
            proof=dict(kind='verified_initial_full_hp',knowledge='derived',confirmed_by='user focused repair 2026-11-01',
                entry_event_id=entry['event']['event_id'],available_at=time(entry),maximum=194,
                configuration_instance_id='own_team_6',team_id=config['team_id'],continuity='first entry; no intervening HP-changing event',
                not_a_hud_observation=True)
            ep['before']=194;ep['endpoints']['before']=dict(event_id=entry['event']['event_id'],time=time(entry),event_type='derived_initial_full_hp',provenance=proof)
            for c in ep.get('components',[]):
                if c.get('before') is None:
                    c.update(before=194,baseline_basis='derived_verified_initial_full_hp',delta=c['after']-194)
                    c['endpoints']['before']=deepcopy(ep['endpoints']['before'])
                    c['reasons']=[r for r in c['reasons'] if r!='pre_action_hp_missing'];c['complete_endpoints']=not c['reasons']
            ep['reasons']=[r for r in ep['reasons'] if r!='pre_action_hp_missing']
        elif (ep.get('source_move') or {}).get('canonical_id')=='pokeapi:move:394' and ep.get('reasons')==['final_visible_plateau_unresolved']:
            boundary=(ep.get('resolution_end') or {}).get('time')
            notices=[r for r in admitted if actor(r)==canonical and time(r)==boundary and event(r)['event_type']=='hp_change'
                and '灼伤' in event(r).get('original_text','')]
            samples=[]
            for r in admitted:
                if event(r)['event_type']!='hud_observation' or actor(r)!=canonical or not start<time(r)<(boundary or start):continue
                hp=event(r)['attributes'].get('hp') or {};v=hp.get('value')
                if isinstance(v,dict) and hp.get('confidence',0)>=.95:samples.append((time(r),v.get('current'),r['event']['event_id']))
            tail=[]
            for s in reversed(samples):
                if s[1]!=ep['after']:break
                tail.append(s)
            if not notices or len(tail)<2 or tail[0][0]-tail[-1][0]<.4:continue
            proof=dict(kind='stable_direct_damage_plateau_before_separate_burn',knowledge='derived_causal_attribution',
                plateau_event_ids=[s[2] for s in reversed(tail)],plateau_start=tail[-1][0],plateau_end=tail[0][0],
                burn_event_id=notices[0]['event']['event_id'],burn_time=boundary,recoil_is_other_recipient=True,
                endpoint_knowledge='directly observed numeric HUD; causal separation derived')
            ep['reasons']=[]
            for c in ep['components']:c.update(reasons=[],complete_endpoints=True,delta=c['after']-c['before'])
        if proof:
            ep['complete_endpoints']=not ep['reasons'];ep['attribution_status']='supported' if not ep['reasons'] else 'ambiguous'
            ep['delta']=ep['after']-ep['before'] if ep['complete_endpoints'] else None
            ep['net_endpoint_delta']=ep['delta'];ep['endpoint_repair_provenance']=proof
            audits.append(dict(episode_id=ep['episode_id'],source_event_id=ep['source_event_id'],original=old,
                repaired=dict(before=ep['before'],after=ep['after'],delta=ep['delta'],status=ep['attribution_status']),provenance=proof))
    return out,audits


def supplement_endpoints(view,c,before,last,samples):
    pid=c['pid'];src=c['source'];start=view.trace(src['i'] if src else c['start'])['time']
    stop=view.trace(c['end']);stop=stop['time'] if stop else None
    eligible=[]
    for raw in view.endpoint_samples:
        if raw.get('pokemon_instance_id')!=pid or raw.get('unit')!=last['unit']:continue
        if raw.get('maximum')!=last['maximum'] or raw.get('confidence',0)<.95 or raw.get('sample_fps',0)<5:continue
        t=raw.get('time');value=raw.get('value');proof=raw.get('evidence',{})
        if type(t) not in (int,float) or not math.isfinite(t) or type(value) not in (int,float) or not math.isfinite(value):continue
        entry=raw.get('binding_entry_event_id');j=view.index.get(entry)
        if j is None or not view.admitted(j) or view.actor(j)!=pid:continue
        if not proof.get('source',{}).get('sha256') or not proof.get('observation'):continue
        if start is None or t<view.trace(j)['time'] or stop is not None and t>=stop:continue
        # Never bridge a switch, identity uncertainty, unknown event or coverage gap.
        if any(view.events[k]['event_type'] in {'switch_out','faint','unknown','coverage_observation'} and
               (view.actor(k)==pid or view.events[k]['event_type'] in {'unknown','coverage_observation'}) and
               view.trace(k)['time'] is not None and view.trace(j)['time']<view.trace(k)['time']<=t
               for k in range(j+1,len(view.events))):continue
        trace=dict(event_id=raw['event_id'],time=t,event_type='source_hp_observation',evidence=[deepcopy(proof)])
        eligible.append(dict(raw,i=c['start'],epoch=last['epoch'],trace=trace))
    eligible=sorted({s['event_id']:s for s in eligible}.values(),key=lambda s:s['time'])
    baseline=None
    # Directly observed before the source: do not let a later animation fragment
    # masquerade as a pre-action reading. Retain the exact source trace.
    earlier=[s for s in eligible if s['time']<start]
    if earlier:baseline=dict(earlier[-1],basis='observed_source_pre_action')
    if baseline is None and src and src['cause']['kind']=='move' and c['direction']=='down':
        onset=next((n for n,s in enumerate(eligible) if s.get('visibility_onset') and
                    start<=s['time']<=samples[0]['time']),None)
        if onset is not None:
            initial=eligible[onset];plateau=[];following=None
            for s in eligible[onset:]:
                if plateau and s['time']-plateau[-1]['time']>.25:break
                if s['value']!=initial['value']:following=s;break
                plateau.append(s)
            full=initial['value']==(initial['maximum'] if initial['unit']=='absolute' else 100)
            repeated=(len({s['time'] for s in plateau})>=3 and plateau[-1]['time']-initial['time']>=.1-1e-7)
            if following and following['value']<initial['value'] and (full or repeated and not view.multi(c['parent'])):
                baseline=dict(initial,basis='observed_full_scale_before_decrease' if full else 'observed_source_animation_onset')
    # Supplement a missing baseline or confirm/correct a derived carry. An
    # already observed pre-action baseline remains authoritative.
    replaced=False
    if baseline and (before is None or before.get('basis')=='derived_same_instance_carry'):
        before=baseline;replaced=True
    augmented=list(samples)
    for s in eligible:
        if s['time']>=samples[0]['time'] and s['time']>=start:augmented.append(s)
    augmented.sort(key=lambda s:s['time'])
    # Keep a trustworthy later reading even if it contradicts an earlier plateau.
    # The caller must establish stability/termination again; discarding this tail
    # would incorrectly keep an old animation fragment as a complete endpoint.
    final=augmented[-1]
    return before,final,augmented,dict(baseline_replaced=replaced,
        source_sample_event_ids=[s['event_id'] for s in eligible]) if eligible else None
