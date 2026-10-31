"""Observed source endpoints supplement a projection, never persistent state.

An initial non-full reading during an action is not automatically its baseline.
Require a captured visibility onset with three unchanged high-rate readings
before a decrease. A full-scale onset can establish its own upper-bound value.
"""
from copy import deepcopy
import math


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
