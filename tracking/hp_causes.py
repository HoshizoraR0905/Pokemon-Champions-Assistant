"""Evidence-only enrichment of the existing HP ledger (never HP updates).

Named recipients can arrive after the HUD animation. Recompute links from the
processed replay prefix so later evidence, revision and retraction all agree.
"""
from copy import deepcopy


def battle_message(event):
    """Chronological message boundaries exclude HUD, animation and banners."""
    region=event['attributes'].get('source_region_type')
    if region is not None:return region=='battle_message'
    return any(s['source_type']=='video_message' for s in event['evidence'])


def grassy_recovery_context(state,event,recipient,records,kb):
    """Conditional field deduction, never a numeric heal or a Speed ranking."""
    a=event.attributes
    if a.get('cause') or a.get('direction')!='up':return
    prefix=[r for r in records if not r.retracted and r.ordering and r.application_status in ADMITTED]
    payload=lambda r:r.bindings.get('resolved_event') or r.event
    markers=[r for r in prefix if (payload(r)['event_type']=='phase_observation' and
        (payload(r)['attributes'].get('resolution_cycle_start') or payload(r)['attributes'].get('phase')=='end_of_turn'))
        or payload(r)['event_type']=='turn_boundary']
    if not markers:return
    boundary=markers[-1];start=prefix.index(boundary);cycle=prefix[start+1:];b=payload(boundary);ba=b['attributes']
    explicit_end=(b['event_type']=='turn_boundary' and ba.get('boundary')=='end' or ba.get('phase')=='end_of_turn')
    participants=set(boundary.bindings.get('resolution_active_instance_ids',[]))
    completed={r.bindings.get('actor',{}).get('pokemon_instance_id') for r in cycle
        if payload(r)['event_type'] in {'move_execution','switch_out','faint'}}
    if not explicit_end and not (len(participants)==4 and participants<=completed):return
    resolution_id=b['event_id'];pid=recipient.pokemon_instance_id
    recoveries=[r for r in cycle if payload(r)['event_type']=='hp_change' and
        payload(r)['attributes'].get('qualitative_only') and payload(r)['attributes'].get('direction')=='up']
    a.update(end_of_turn_resolution_id=resolution_id,recovery_order_index=len(recoveries),
        recovery_order_basis='observed_message_sequence_not_speed_stats')
    # Preserve an explicit source after the last move. A later turn-end banner
    # cannot be retroactively attached to an earlier, separate recovery notice.
    last_move=next((r for r in reversed(cycle) if payload(r)['event_type']=='move_execution'),None)
    after=cycle[cycle.index(last_move)+1:] if last_move else cycle
    for r in reversed(after):
        e=payload(r);kind=e['event_type'].split('_')[0]
        if e['event_type'] not in {'item_activation','ability_activation'}:continue
        ref=e.get('canonical_references',{}).get(kind) or {};rule=kb.resolution_effect(ref.get('canonical_id')) or {}
        following=after[after.index(r)+1:]
        consumed=any(payload(x)['event_type']=='hp_change' and payload(x)['attributes'].get('direction')=='up'
            and x.bindings.get('actor',{}).get('pokemon_instance_id')==pid for x in following)
        if not consumed and r.bindings.get('actor',{}).get('pokemon_instance_id')==pid and rule.get('direction')=='up' and rule.get('recipient')=='holder':
            a.update(cause=dict(kind=kind,source=ref,holder=recipient.species.value,holder_side=recipient.side_id),
                hp_cause_basis='explicit_activation_context',recovery_source_event_id=e['event_id']);return
    if a.get('effect_of'):return
    if last_move and last_move.bindings.get('actor',{}).get('pokemon_instance_id')==pid:
        ref=payload(last_move).get('canonical_references',{}).get('move') or {}
        rule=kb.resolution_effect(ref.get('canonical_id')) or {}
        if (kb.facts.get('moves',{}).get(ref.get('canonical_id'),{}).get('category')=='Status'
                or rule.get('direction')=='up' or rule.get('drain')):
            a['recovery_source_status']='current_status_move_not_excluded';return
    if not (state.terrain.active.known and state.terrain.active.value and state.terrain.kind.value=='grassy'):return
    used=[r for r in recoveries if r.bindings.get('actor',{}).get('pokemon_instance_id')==pid and
        (payload(r)['attributes'].get('cause') or {}).get('kind')=='grassy_terrain' and
        payload(r)['attributes'].get('end_of_turn_resolution_id')==resolution_id]
    if used:a['recovery_source_status']='duplicate_grassy_recovery_in_resolution';return
    a.update(cause=dict(kind='grassy_terrain',terrain='grassy'),hp_cause_basis='field_end_of_turn_resolution',
        recovery_source_status='derived',recovery_context_evidence=dict(cycle_event_id=resolution_id,
            basis='explicit_turn_end' if explicit_end else 'observed_command_and_all_participant_actions_resolved',
            action_event_ids=[payload(r)['event_id'] for r in cycle if payload(r)['event_type'] in {'move_execution','switch_out','faint'}],
            terrain_provenance=deepcopy(state.terrain.kind.provenance),
            rule=kb.resolution_effect('pokeapi:move:580')))


def confusion_hp_bindings(engine):
    """Resolve an unnamed self-hit only from one completed observed HP loss.

    This is a derived second-pass binding over the existing resolution view;
    raw events and HP observations remain immutable, and corrections rebuild it.
    """
    unresolved={r.event['event_id']:r.bindings.get('resolved_event') or r.event for r in engine.history
        if not r.retracted and r.ordering and r.application_status=='deferred'
        and r.event['attributes'].get('requires_confusion_context')}
    if not unresolved:return {}
    episodes=engine.hp_resolutions()['episodes'];result={}
    ordered=sorted((r for r in engine.history if r.ordering and not r.retracted),key=lambda r:tuple(r.ordering['key']))
    positions={r.event['event_id']:i for i,r in enumerate(ordered)}
    for eid,event in unresolved.items():
        groups={}
        for o in episodes:
            if (o['source_event_id']==eid and (o.get('candidate_cause') or {}).get('kind')=='confusion_self_damage'
                    and o['affected_instance_id'] in event['attributes'].get('confusion_active_instance_ids',[])):
                groups.setdefault(o['affected_instance_id'],[]).append(o)
        losses=[]
        for pid,group in groups.items():
            parts=[c for o in group for c in o['components']]
            first=min(parts,key=lambda c:positions.get((c['endpoints']['before'] or {}).get('event_id'),-1))
            last=max(parts,key=lambda c:positions.get(c['endpoints']['after']['event_id'],-1))
            if first['before'] is not None and last['after']<first['before']:
                losses.append((pid,group,first,last))
        if len(losses)!=1:continue
        pid,group,first,last=losses[0]
        if (any(not o['complete_endpoints'] or o['delta'] is None
                or set(o['reasons'])-{'effect_recipient_unresolved','effect_recipient_scope_conflict'} for o in group)
                or pid not in event['attributes'].get('confusion_active_instance_ids',[])):
            continue
        result[eid]=dict(instance_id=pid,
            evidence_event_ids=[first['endpoints']['before']['event_id'],last['endpoints']['after']['event_id']],
            resolution_end_event_id=group[-1]['resolution_end']['event_id'],
            before=first['before'],after=last['after'],unit=last['unit'])
    return result


def observed_change(engine, pokemon, event, unit, after):
    prior = next((x for x in reversed(pokemon.hp.observations) if 'unit' in x), None)
    result = dict(observed_before=None, delta=None, cause=None, cause_event_ids=[],
                  affected_instance_id=pokemon.pokemon_instance_id)
    explicit = event.attributes.get('before')
    if explicit is not None:
        result.update(observed_before=explicit, delta=after-explicit,
                      baseline_event_id=event.event_id, baseline_kind='explicit_endpoint_pair')
    if prior and prior['unit'] == unit and (explicit is None or prior['after'] == explicit):
        result.update(observed_before=prior['after'], delta=after-prior['after'],
                      baseline_event_id=prior['evidence']['event_id'])
    return result


def enrich(engine, records):
    """Only admitted receipts in a single ordered prefix are causal evidence."""
    events = [r.bindings.get('resolved_event') or r.event for r in records]
    index = {e['event_id']:i for i,e in enumerate(events)}
    valid = {'applied_candidate', 'applied_confirmed', 'applied_partial', 'recorded_observation'}

    def actor(i):
        return records[i].bindings.get('actor', {}).get('pokemon_instance_id')

    def time(i):
        e = events[i]
        return e['attributes'].get('observation_time', next(
            (s['details']['timestamp'] for s in e['evidence'] if 'timestamp' in s['details']), None))

    def candidate(i, cause, source=None, evidence_ids=None):
        return dict(cause=deepcopy(cause), source_instance_id=source,
                    cause_event_ids=evidence_ids or [events[i]['event_id']],
                    evidence=[deepcopy(events[j]['evidence']) for j in range(len(events))
                              if events[j]['event_id'] in (evidence_ids or [events[i]['event_id']])])

    for pid, mon in engine.state.pokemon.items():
        numeric = [o for o in mon.hp.observations if 'unit' in o]
        for o in numeric:
            o.update(cause=None, cause_event_ids=[], candidate_causes=[], attribution_status='unknown',
                     attribution_reasons=[])
            o.pop('source_instance_id', None)
            if not o.get('delta'):
                o['attribution_reasons'] = ['no_numeric_change_or_baseline'];continue
            b = index.get(o.get('baseline_event_id')); end = index.get(o['evidence']['event_id'])
            if b is None or end is None or b >= end:
                o['attribution_reasons'] = ['missing_ordered_endpoint_pair'];continue
            reasons = []; candidates = []; recipient_end = end
            # The same instance must remain in one encounter. Explicit endpoints
            # without a prior encounter observation do not establish an action window.
            confusion_boundary=max((i for i in range(end) if events[i]['event_type']=='volatile_change'
                and events[i]['attributes'].get('condition')=='confusion' and records[i].application_status in valid),default=-1)
            moves = [i for i in range(confusion_boundary+1,end) if events[i]['event_type']=='move_execution']
            inside = [i for i in moves if b < i < end]
            move = inside[-1] if inside else (moves[-1] if moves else None)
            notices = [i for i in range(b+1,end) if events[i]['event_type']=='hp_change'
                       and actor(i)==pid and events[i]['attributes'].get('qualitative_only')]
            prior_notice = None
            if not notices and not inside:
                # An explicit residual/recoil/recovery occurrence starts its own
                # effect window. HUD animation endpoints may both follow it.
                boundaries={'move_execution','hp_change','switch_out','send_out','faint',
                            'item_activation','ability_activation','turn_boundary',
                            'command_checkpoint','coverage_observation','unknown'}
                for i in range(b-1,-1,-1):
                    e=events[i];a=e['attributes']
                    if e['event_type'] not in boundaries:continue
                    if (e['event_type']=='hp_change' and actor(i)==pid and
                        a.get('hp_cause_basis') in {'explicit_literal_message','field_end_of_turn_resolution','explicit_activation_context'} and a.get('cause')):
                        prior_notice=i;notices=[i]
                    break
            for i in notices:
                a = events[i]['attributes']
                if a.get('cause') and a.get('hp_cause_basis') in {'explicit_literal_message','field_end_of_turn_resolution','explicit_activation_context'} and records[i].application_status in valid:
                    notice = next((x for x in mon.hp.observations if x.get('event_id')==events[i]['event_id']), {})
                    source = notice.get('source_instance_id')
                    if a['cause'].get('holder') and source is None:reasons.append('source_holder_instance_unresolved')
                    if a['cause']['kind'] in {'move_recoil','self_hp_cost','confusion_self_damage','struggle_recoil'}:source=pid
                    candidates.append(candidate(i,a['cause'],source))
                elif a.get('cause'):reasons.append('unresolved_hp_occurrence')
            if (not notices and move is not None and records[move].application_status in valid
                    and actor(move)==pid and o['delta']<0
                    and events[move]['canonical_references'].get('move',{}).get('canonical_id')=='pokeapi:move:165'
                    and events[move]['attributes'].get('effect_outcome') not in {'failed','blocked','selected'}):
                target_changes=[x['evidence']['event_id'] for other,p in engine.state.pokemon.items() if other!=pid
                    for x in p.hp.observations if x.get('delta',0) is not None and x.get('delta',0)<0
                    and move<index.get(x['evidence']['event_id'],-1)<end]
                if target_changes:
                    candidates.append(candidate(move,dict(kind='struggle_recoil',source=events[move]['canonical_references']['move']),
                        pid,[events[move]['event_id']]+target_changes))
            isolated_self=any(c['cause']['kind'] in {'confusion_self_damage','struggle_recoil','grassy_terrain'} for c in candidates)
            # Recipient notices belong to the uninterrupted action, including
            # messages emitted after its numeric animation. No move-name targeting.
            if not isolated_self and prior_notice is None and move is not None and records[move].application_status in valid and actor(move):
                if events[move]['attributes'].get('effect_outcome') in {'failed','blocked','selected'}:
                    reasons.append('move_outcome_not_successful')
                stop = next((i for i in range(move+1,len(events)) if events[i]['event_type'] in
                             {'move_execution','switch_out','send_out','turn_boundary'}),len(events))
                recipients=[]
                for i in range(move+1,stop):
                    e=events[i];a=e['attributes']
                    if records[i].application_status not in valid:continue
                    if o['delta']<0 and e['event_type']=='effectiveness' and a.get('effect') in {'super_effective','not_very_effective'}:
                        target=e.get('target') or {}; species=mon.species.value or {}
                        # A unique active encounter, not just matching a party species.
                        if (a.get('target_side',e['side'])==mon.side_id and
                            target.get('species_id')==species.get('species_id')):
                            # Binding captured when the named outcome was observed.
                            if records[i].bindings.get('hp_recipient_instance_id')==pid:recipients.append(i)
                    if e['event_type']=='hp_change' and actor(i)==pid and a.get('qualitative_only') and not a.get('cause'):
                        if (a.get('direction')=='up' and o['delta']>0 and a.get('effect_of')==events[move]['event_id'] or
                            a.get('direction') in {'down','zero'} and o['delta']<0):recipients.append(i)
                e=events[move];a=e['attributes']
                explicit_target = (a.get('target_instance_id')==pid and not a.get('target_basis'))
                if end < stop and (recipients or explicit_target) and (o['delta']<0 or any(events[i]['attributes'].get('direction')=='up' for i in recipients)):
                    ids=[e['event_id']]+[events[i]['event_id'] for i in recipients]
                    candidates.append(candidate(move,dict(kind='move',source=e['canonical_references'].get('move'),
                                                         effect='healing' if o['delta']>0 else 'damage'),
                                                actor(move),ids))
                    recipient_end=max([end]+[i+1 for i in recipients])
                elif not candidates:
                    candidates.append(candidate(move,dict(kind='move',source=e['canonical_references'].get('move')),actor(move)))
                    reasons.append('no_unique_named_recipient_in_action_window')
            if len(inside)>1:
                reasons.append('multiple_actions_between_endpoints')
                for i in ([] if isolated_self else inside[:-1]):
                    if records[i].application_status in valid:
                        candidates.append(candidate(i,dict(kind='move',source=events[i]['canonical_references'].get('move')),actor(i)))
            scan_start=prior_notice if prior_notice is not None else (min(b,move) if move is not None and not notices else b)
            for i in range(scan_start+1,recipient_end):
                e=events[i];k=e['event_type'];a=e['attributes']
                if records[i].application_status not in valid and k not in {'phase_observation','command_checkpoint'}:
                    reasons.append('unresolved_event_in_window')
                if k in {'switch_out','send_out','coverage_observation','unknown'}:reasons.append('identity_or_coverage_gap')
                if k=='faint' and actor(i)==pid and i<end:reasons.append('faint_before_endpoint')
                if k in {'item_activation','ability_activation'}:reasons.append('activation_without_scoped_hp_effect')
                if k=='move_effect' and (a.get('outcome') in {'failed','blocked','uncertain'} or
                        a.get('effect') in {'protected_from_attack','wide_guard_received'} and actor(i)==pid):
                    reasons.append('blocked_or_unresolved_action_outcome')
                if k=='move_miss' and records[i].bindings.get('target',{}).get('pokemon_instance_id')==pid:
                    reasons.append('blocked_or_unresolved_action_outcome')
                if k=='hud_observation' and actor(i) in {None,pid} and (a.get('hp') or {}).get('value') is None:
                    reasons.append('missing_hp_observation')
                if k=='hp_change' and actor(i) in {None,pid} and i not in notices and (a.get('cause') or not a.get('qualitative_only')):
                    reasons.append('unresolved_hp_occurrence')
            if candidates and any(events[i]['attributes'].get('cause') for i in notices) and inside:
                # Only a matching self-action is corroboration of an explicit cost;
                # other actions could contribute to the observed aggregate delta.
                c=candidates[0]['cause'];ref=c.get('source') or {}
                source_actor=candidates[0]['source_instance_id']
                if not (len(inside)==1 and (
                        c['kind'] in {'move_recoil','self_hp_cost','struggle_recoil'} and actor(inside[0])==pid or
                        c['kind']=='move' and source_actor is not None and actor(inside[0])==source_actor)
                        and ref.get('canonical_id')==
                        events[inside[0]]['canonical_references'].get('move',{}).get('canonical_id')):
                    reasons.append('competing_action_and_effect')
            if time(b) is not None and time(end) is not None and time(b)>=time(end):reasons.append('endpoint_time_tie')
            for c in candidates:
                for eid in c['cause_event_ids']:
                    i=index[eid]
                    if time(i) is not None and time(b) is not None and time(i)==time(b):reasons.append('cause_baseline_time_tie')
                kind=c['cause']['kind']
                if kind=='instant_faint' and o['after']!=0:reasons.append('direction_mismatch')
                if kind=='struggle_recoil' and events[index[c['cause_event_ids'][0]]]['event_type']=='move_execution':
                    if o['delta']>=0:reasons.append('direction_mismatch')
                elif kind not in {'move','instant_faint'}:
                    notice_i=index[c['cause_event_ids'][0]];direction=events[notice_i]['attributes'].get('direction')
                    if not (direction=='up' and o['delta']>0 or direction=='down' and o['delta']<0 or direction=='zero' and o['after']==0):
                        reasons.append('direction_mismatch')
            o['candidate_causes']=candidates
            o['attribution_reasons']=sorted(set(reasons))
            if len(candidates)==1 and not reasons:
                c=candidates[0];o.update(cause=deepcopy(c['cause']),cause_event_ids=c['cause_event_ids'],
                                       source_instance_id=c['source_instance_id'],attribution_status='supported')
            elif candidates:o['attribution_status']='ambiguous'
            else:o['attribution_reasons'].append('no_supported_cause_event')


def bind_recipient(state, event, record):
    """Resolve a named outcome at its own prefix; never use final occupancy."""
    if event.event_type not in {'effectiveness','move_miss'} or not event.target:return
    side=state.sides.get(event.attributes.get('target_side',event.side))
    if not side:return
    matches=[pid for pid in side.active_slots.values() if state.pokemon[pid].species.known
             and state.pokemon[pid].species.value.get('species_id')==event.target.get('species_id')]
    if len(matches)==1:record.bindings['hp_recipient_instance_id']=matches[0]


import math

ADMITTED = {'applied_candidate', 'applied_confirmed', 'applied_partial', 'recorded_observation'}


def event_time(event):
    value = event['attributes'].get('observation_time', next(
        (s['details']['timestamp'] for s in event['evidence'] if 'timestamp' in s['details']), None))
    return value if type(value) in (int,float) and math.isfinite(value) else None


def resolve_hits(samples, *, sampling_fps=2., capability=None, hit_count=None,
                 critical_events=(), plateau_seconds=.4, baseline_carry_supported=False):
    """Resolve *candidates* from dense observed HP, never from damage formulas.

    A plateau alone does not establish a hit. Even a verified multi-hit mechanic
    permits missing/merged hits: authoritative per-hit deltas additionally need
    an independent count matching the observed decrease runs. Count evidence is
    a caller-scoped admitted hit message, not a count calculated from plateaus.
    """
    values = sorted(samples, key=lambda x:x['time'])
    result = dict(hit_count=hit_count, per_hit_damage=None, hits=None,
                  per_hit_status='unknown', hit_candidates=[], critical_hit=None,
                  reasons=[])
    if not values:return result
    if any(b['time']<=a['time'] or b['value']>a['value'] for a,b in zip(values,values[1:])):
        result['reasons']=['non_monotonic_or_tied_hit_samples'];return result
    if (hit_count is None and capability and capability.get('verification') in {'champions_verified','52poke_champions_documented'}
            and capability.get('sources') and capability.get('hit_range')==[1,1]):
        hit_count=1;result['hit_count']=1
    if hit_count == 1:
        critical=True if any(c.get('hit_index') in (None,1) for c in critical_events) else None
        if any(c.get('hit_index') not in (None,1) for c in critical_events):
            result['reasons'].append('critical_hit_index_conflicts_with_single_hit')
        damage=values[0]['value']-values[-1]['value']
        result.update(hits=[dict(index=1,before=values[0]['value'],after=values[-1]['value'],
            damage=damage,critical_hit=critical,evidence_ids=[x['event_id'] for x in values],
            damage_begin_time=next((b['time'] for a,b in zip(values,values[1:]) if b['value']<a['value']),None),
            end_time=max((b['time'] for a,b in zip(values,values[1:]) if b['value']<a['value']),default=values[-1]['time']))],
            per_hit_damage=[damage],per_hit_status='supported',critical_hit=critical)
        return result
    verified = bool(capability and capability.get('verification') in {'champions_verified','52poke_champions_documented'}
                    and capability.get('sources'))
    if not verified and not (hit_count and hit_count>1):
        result['reasons']=['no_verified_multi_hit_mechanic_or_independent_count'];return result
    gaps=[b['time']-a['time'] for a,b in zip(values,values[1:])]
    if baseline_carry_supported:
        # The existing action projection can certify a same-instance pre-action
        # baseline while the HUD is hidden. This permits no gap *inside* a hit
        # sequence: only the leading baseline/first-decrease edge is exempt.
        first_drop=next((i for i in range(1,len(values)) if values[i]['value']<values[i-1]['value']),0)
        gaps=gaps[first_drop:]
    # The targeted profile starts at 3 FPS. Actual PTS gaps still have to match
    # that cadence; requesting a rate is not proof that frames were observed.
    if sampling_fps<3 or gaps and max(gaps)>1/sampling_fps+.05:
        result['reasons']=['dense_sampling_required'];return result
    # A run may pause briefly during a single animation. Only a configured
    # stable plateau splits candidate runs; the final plateau closes the last.
    start=0;falling=False;plateau_start=None;parts=[]
    for i in range(1,len(values)):
        if values[i]['value']<values[i-1]['value']:
            falling=True;plateau_start=i
        elif falling and plateau_start is not None and values[i]['time']-values[plateau_start]['time']>=plateau_seconds-1e-7:
            parts.append((start,plateau_start,i));start=plateau_start;falling=False
    if falling:result['reasons'].append('final_hit_plateau_unresolved')
    for number,(a,b,settled) in enumerate(parts,1):
        relevant=[c for c in critical_events if c.get('hit_index')==number]
        result['hit_candidates'].append(dict(index=number,before=values[a]['value'],after=values[b]['value'],
            damage=values[a]['value']-values[b]['value'],critical_hit=True if relevant else None,
            evidence_ids=[v['event_id'] for v in values[a:settled+1]],
            plateau_evidence_ids=[v['event_id'] for v in values[b:settled+1]],
            critical_event_ids=[c['event_id'] for c in relevant],
            damage_begin_time=next((values[j]['time'] for j in range(a+1,b+1) if values[j]['value']<values[j-1]['value']),None),
            end_time=values[b]['time']))
    if not hit_count or len(parts)!=hit_count or falling:
        result['reasons'].append('independent_hit_count_and_boundaries_not_both_resolved')
        return result
    if capability and capability.get('hit_range'):
        lo,hi=capability['hit_range']
        if not lo<=hit_count<=hi:
            result['reasons'].append('hit_count_mechanic_conflict');return result
    result.update(hits=deepcopy(result['hit_candidates']),
                  per_hit_damage=[h['damage'] for h in result['hit_candidates']],per_hit_status='supported')
    if any(c.get('hit_index') is None for c in critical_events):
        result['reasons'].append('critical_hit_hit_index_unknown')
    return result


def action_resolutions(engine, *, stable_seconds=.4, dense_samples=None, mechanics=None, endpoint_samples=None):
    """Sequential parent/immediate-cause projection over existing state receipts."""
    from .resolution_context import sequential_resolutions
    return sequential_resolutions(engine,stable_seconds=stable_seconds,
                                  dense_samples=dense_samples,mechanics=mechanics,endpoint_samples=endpoint_samples)
