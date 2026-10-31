"""Source-bound own HP admission and a causal overlay on the existing replay."""
from bisect import bisect_right
from copy import deepcopy
import hashlib
import json
from time import perf_counter

from damage.joint import filter_joint, project_joint, concrete_ids
from .item_policy import apply_policy, filter_policy_joint, refine_revealed, rescue_from_speed
from knowledge.champions_stats import STATS, ChampionsStats
from speed_order.core import knowledge, name
from .hp import attribute_hp, REQUIRED
from .speed_replay_offline import file_hash
from .speed_replay_projection import _domain
from .speed_reviewed import projection
from knowledge.stat_feasibility import summary


def candidate_inventory(replay, states):
    """Temporal candidates only. Animation endpoints never self-certify damage."""
    actions=[e for e in replay['action_timeline'] if e['kind']=='executed_move']
    rows=[]
    for event in actions:
        if event.get('side')!='opponent':continue
        move=knowledge().facts['moves'].get(event.get('move'),{})
        if move.get('category') not in {'Physical','Special'}:continue
        time=event['timestamp'];following=next((a['timestamp'] for a in actions if a['timestamp']>time),time+15)
        candidates=[]
        for iid in sorted({h['instance_id'] for h in states['hp_samples']}):
            samples=[h for h in states['hp_samples'] if h['instance_id']==iid]
            before=[h for h in samples if time-40<=h['timestamp']<time]
            after=[h for h in samples if time<h['timestamp']<min(following,time+15)]
            if not before or not after:continue
            pre=max(before,key=lambda h:h['timestamp']);post=max(after,key=lambda h:h['timestamp'])
            if post['current']>=pre['current']:continue
            candidates.append(dict(target=iid,pre=deepcopy(pre),post=deepcopy(post),
                                   apparent_loss=pre['current']-post['current'],
                                   intermediate_readings=[dict(timestamp=h['timestamp'],hp=h['current']) for h in after]))
        snapshot=next((s for s in reversed(replay['snapshots']) if s['timestamp']<=time),{})
        actor=snapshot.get('opponents',{}).get(event['individual'],{})
        rows.append(dict(battle_id=replay['battle_id'],source_event_id=event['id'],attacker=event['individual'],
                         current_form=actor.get('current_form'),move=event['move'],timestamp=time,segment_id=event.get('segment_id'),
                         sources=deepcopy(event.get('sources',[])),hp_candidates=candidates,
                         field=deepcopy(snapshot.get('field',{})),admitted=False,
                         reasons=['target/complete HP-cause coverage/action-time modifiers require source review'] if candidates else ['exact bound pre/post own HP pair unavailable']))
    return rows


def admit_review(replay, review, builds, *, root):
    if review['battle_id']!=replay['battle_id'] or review['origin']!='recorded' or not review.get('reviewer'):
        raise ValueError('Same-battle recorded source review required')
    events={e['id']:e for e in replay['action_timeline']};frames={f['source_id']:f for f in replay['frames']}
    admitted=[]
    for r in review['events']:
        event=events[r['source_event_id']]
        if (event['kind']!='executed_move' or event['side']!='opponent' or event['individual']!=r['attacker']
                or event['move']!=r['move'] or event['timestamp']!=r['action_time'] or event.get('segment_id')!=r['segment_id']):
            raise ValueError('Review disagrees with executed source action')
        for source in r['sources'].values():
            saved=frames.get(source['source_id'])
            if (not saved or source['image']!=saved['image'] or source['sha256']!=saved['sha256']
                    or file_hash(root/source['image'])!=source['sha256'] or source['timestamp']>r['available_at']):
                raise ValueError('Missing, altered, future or mismatched damage source')
        at=next(s for s in reversed(replay['snapshots']) if s['timestamp']<=event['timestamp'])
        if at['opponents'][r['attacker']]['current_form']!=r['attacker_form']:
            raise ValueError('Attacker current form not confirmed at damage time')
        encounter=r.get('target_encounter',r['target'])
        if at.get('identity_aliases',{}).get(encounter,encounter)!=r['target']:
            raise ValueError('Reviewed target encounter does not map to the persistent target identity')
        build=builds[r['target']]
        own_changes=[e for e in replay['action_timeline'] if e['kind']=='mega_evolution' and e['individual']==r['target'] and e['timestamp']<=event['timestamp']]
        own_form=own_changes[-1]['resulting_form'] if own_changes else build['canonical_identity']
        if own_form!=r['target_form'] or build.get('available_at',0)>r['available_at']:
            raise ValueError('Own current form/build is not available at this damage epoch')
        stats=build['stats'];own_ability=build['ability']
        if own_changes:
            stats=ChampionsStats(own_form,form='as_named').calculate(build['training_points'],build['alignment'])['stats']
            own_ability=knowledge().facts['pokemon'][own_form]['ability_names'][0]
        if stats['hp']!=r['maximum_hp']:
            raise ValueError('Own target form/HP does not match bound build')
        def hp(value,which):
            source=r['sources'][r[which+'_source']]
            return dict(battle_id=replay['battle_id'],instance_id=r['target'],epoch=r['target_form'],
                        current=value,maximum=r['maximum_hp'],verified=True,sources=[source],
                        position=source['timestamp'],timestamp=source['timestamp'])
        pre=hp(r['pre_hp'],'pre');post=hp(r['post_hp'],'post')
        cause=dict(kind='attack',attacker=r['attacker'],receiver=r['target'],move=r['move'],
                   verified=True,sources=event['sources'],event_id=event['id'],position=event['timestamp'],
                   verification=dict.fromkeys(REQUIRED,True),resolution_snapshot_id=r['id']+':resolution',
                   target_instances=[r['target']],single_hit=True,substitute=False,multi_hit=False)
        attribution=attribute_hp(pre,post,[cause],coverage=dict(complete=True,sources=list(r['sources'].values()),
                      basis='manual reviewed complete single-hit bracket; action-time context conditional'))
        if not attribution['damage_inference_eligible']:raise ValueError(str(attribution['reasons']))
        from .damage_review_history import stage_history
        stage_audit=stage_history(r,replay)
        from .move_legality import move_legality
        legality=move_legality(r['attacker_form'],r['move'])
        if legality['status']!='confirmed_possible':raise ValueError('Observed move legality requires source review: '+str(legality))
        context=r['context'];attacker=dict(identity=r['attacker_form'],form='as_named' if knowledge().entities[r['attacker_form']].form_id else 'base',level=50,
            stats={s:None for s in STATS if s!='hp'},stat_basis='unmodified',stages=context['attacker_stages'],
            current_hp=None,maximum_hp=None,ability=None,item=None,status=context['attacker_status'],other_effects=[])
        defender=dict(identity=r['target_form'],form='as_named' if knowledge().entities[r['target_form']].form_id else 'base',level=50,stats={s:stats[s] for s in STATS if s!='hp'},
            stat_basis='unmodified',stages=context['defender_stages'],current_hp=r['pre_hp'],maximum_hp=stats['hp'],
            ability=name(own_ability,'ability'),item=name(build['item'],'item'),status=context['defender_status'],other_effects=[])
        if r.get('defender_item_transition'):
            change=r['defender_item_transition'];source=r['sources'][change['source']]
            if change['kind']!='consumed' or name(build['item'],'item')!=change['item'] or source['timestamp']>=r['action_time']:
                raise ValueError('Invalid reviewed defender item consumption')
            defender['item']='none'
        admitted.append(dict(id=r['id'],timestamp=r['available_at'],action_time=r['action_time'],
            source_event_id=event['id'],battle_id=replay['battle_id'],segment_id=r['segment_id'],attacker=r['attacker'],
            attacker_form=r['attacker_form'],target=r['target'],target_form=r['target_form'],target_side='self',
            move=r['move'],admitted=True,damage=attribution['exact_damage'],hp_attribution=attribution,
            sources=list(r['sources'].values()),assumptions=r['assumptions'],reviewer=review['reviewer'],
            field_alternatives=[dict(critical=c) for c in r['critical_alternatives']],
            input=dict(profile='showdown-champions-reference-v1',attacker=attacker,defender=defender,move=r['move'],field=context['field'])))
        if stage_audit:admitted[-1].update(move_legality=legality,stage_audit=stage_audit,unresolved_item_histories=stage_audit['unresolved_items'])
        if r.get('item_evidence_exclusions'):
            proof=r['item_exclusion_provenance']
            if proof.get('origin')!='user_source_review' or not proof.get('expected_activation') or not proof.get('coverage_complete') or not proof.get('statement'):
                raise ValueError('Explicit reviewed activation guarantee and complete relevant window required')
            admitted[-1].update(item_evidence_exclusions=r['item_evidence_exclusions'],item_exclusion_provenance=proof)
    return sorted(admitted,key=lambda o:o['timestamp'])


def speed_configuration_domain(replay, participant):
    """Consume persistent Speed rows, including joint binary Speed witnesses."""
    links=(replay['reviewed_inference'].get('review') or {}).get('identity_links',{})
    iid=participant['individual']
    for update in replay['reviewed_inference']['updates']:
        if len(update['after'])>1 and any(iid in links.get(actor,[]) for actor in update['after']):
            raise ValueError('Damage propagation through cross-individual Speed witnesses is unresolved; retain original support')
    full=replay['support_catalog'][participant['support_ref']]['full']
    ids=full.get('surviving_configuration_ids')
    surviving=set(ids) if ids is not None else None
    if participant.get('form_evidence'):
        rows=deepcopy(replay['form_configuration_support'][participant['form_evidence']['id']]['configurations'])
    else:
        form=participant.get('current_form')
        if not form:raise ValueError('Unresolved current form prevents damage-domain binding')
        rows,u=_domain(form)
        concrete=[]
        members_by_item={k['representative']:k['members'] for k in u['item_equivalence_classes']}
        for c in rows:
            if surviving is not None and c['id'] not in surviving:continue
            # Immutable item alternatives share one six-stat training domain.
            # The solver splits them only when their damage supports differ.
            members=members_by_item[c['item']]
            concrete.append(dict(c,speed_parent_id=c['id'],item_options=members))
        rows=concrete
    if surviving is not None:rows=[c for c in rows if c.get('speed_parent_id',c['id']) in surviving]
    # Cross-individual witness propagation is gated above rather than silently
    # replacing a binary relation with independent marginal sets.
    return rows


def observed_configuration_domain(replay, participant):
    support=replay['support_catalog'][participant['support_ref']]['observed'];rows=[]
    for key in support['builds']:
        source=replay['observed_builds'][key];mapping=support['ability_mappings'][key]
        rows.append(dict(id=key,form=participant['current_form'],ability=mapping['active_ability'],
            item=name(source['item'],'item'),speed=mapping['speed'],
            training=dict(alignment=deepcopy(source['alignment']),point_domains={s:[v] for s,v in source['training_points'].items()}),
            observed_build=deepcopy(source),ability_state=deepcopy(mapping)))
    return rows


def offensive_projections(configs, result):
    """Project both offenses from the same survivors, retaining per-stat evidence."""
    evidence={}
    for update in result['updates']:
        selector=update.get('selector')
        if selector and selector['constrains_opponent_offensive_stat']:
            evidence.setdefault(selector['offensive_stat'],[]).append(update['id'])
    unknown_ids={cid for issue in result['unresolved'] for cid in issue.get('configuration_ids',[issue.get('id')])}
    supported=[c for c in configs if not (concrete_ids([c]) & unknown_ids)]
    return {stat:dict(**project_joint(configs,stat),status=result['status'],
                evaluated_support=project_joint(supported,stat) if result['updates'] else None,
                evidence_ids=evidence.get(stat,[]),direct_constraint=bool(evidence.get(stat)),
                unresolved=issue_summary(result['unresolved']),requirements=result['requirements'])
            for stat in dict.fromkeys(['attack','special_attack',*evidence])}


def issue_summary(issues):
    return [{k:v for k,v in issue.items() if k!='configuration_ids'} for issue in issues]


def full_damage_projection(configs):
    branches={}
    for c in configs:
        items=tuple(c.get('item_options',[c['item']]))
        branches.setdefault((items,c['ability'],c['form']),[]).append(c['speed'])
    return dict(configuration_count=sum(len(c.get('item_options',[c['item']])) for c in configs),
        items=sorted({i for items,_,_ in branches for i in items}),abilities=sorted({c['ability'] for c in configs}),
        branches=[dict(item=items[0],concrete_items=list(items),ability=ability,form=form,speed=summary(speeds))
                  for (items,ability,form),speeds in branches.items()])


def compact_offensive_storage(replay):
    """Encode shared training/issue sets once; checkpoints retain solver schema."""
    inference=replay['offensive_inference'];domains={};id_sets={}
    def intern(catalog,value):
        key=hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()[:24]
        catalog.setdefault(key,value);return key
    for update in inference['updates']:
        for layer in ('full','observed'):
            result=update[layer]
            result['configurations']=[dict({k:v for k,v in c.items() if k!='training'},
                training_ref=intern(domains,c['training'])) for c in result['configurations']]
            for issue in [*result['unresolved'],*(i for u in result['updates'] for i in u['unresolved'])]:
                if 'configuration_ids' in issue:
                    issue['configuration_ids_ref']=intern(id_sets,issue.pop('configuration_ids'))
    inference.update(version='own-hp-offensive-v2',configuration_training_domains=domains,configuration_id_sets=id_sets,
        storage='Configuration training_ref and issue configuration_ids_ref resolve in this object; concrete member IDs remain speed_parent_id@item. Checkpoints retain inline training.')
    return replay


def offensive_overlay(replay, observations, *, progress=None, checkpoint=None, resume=None, item_profile="practical", item_events=()):
    """Offline only: no solver work is performed by timeline navigation."""
    initialization_start=perf_counter();domain_seconds=[0.]
    def load_domain(participant):
        start=perf_counter();rows=speed_configuration_domain(replay,participant);domain_seconds[0]+=perf_counter()-start;return rows
    output=deepcopy(replay);updates=[];results={};original_domains={};originals=replay['snapshots']
    # Published joint builds already determine both offenses before any admitted
    # hit. Project them at their existing causal support refs, without inventing
    # a damage observation or filling an unresolved current form.
    projected=set()
    for snapshot in originals:
        for participant in snapshot['opponents'].values():
            ref=participant.get('support_ref')
            if not participant.get('current_form') or not ref or ref in projected:continue
            configs=observed_configuration_domain(replay,participant)
            output['support_catalog'][ref]['observed']['offensive_stats']=offensive_projections(configs,
                dict(updates=[],status='configuration_support',unresolved=[],requirements={}))
            projected.add(ref)
    # Apply the selected policy to causal pre-hit references too; each domain
    # uses ONLY the Speed evidence already present at that support_ref.
    policy_refs=set()
    affected={o['attacker'] for o in observations}|{e['individual'] for e in item_events}
    for snapshot in originals:
        for actor in affected:
            participant=snapshot['opponents'].get(actor,{})
            ref=participant.get('support_ref')
            if not participant.get('current_form') or not ref or (actor,ref) in policy_refs:continue
            initial=load_domain(participant)
            domain,receipt=apply_policy(initial,item_profile)
            section=output['support_catalog'][ref]['full']
            section.update(full_damage_projection(domain))
            section['item_policy']=receipt
            policy_refs.add((actor,ref))
    initial_projection_seconds=perf_counter()-initialization_start-domain_seconds[0]
    for actor in sorted(affected):
        events=[o for o in observations if o['attacker']==actor]
        first_time=events[0]['timestamp'] if events else min(e['available_at'] for e in item_events if e['individual']==actor)
        first=next(s for s in reversed(originals) if s['timestamp']<=first_time)['opponents'][actor]
        if any(e['attacker_form']!=first['current_form'] for e in events):
            raise ValueError('Explicit cross-form damage-domain transport required')
        full=load_domain(first);observed=observed_configuration_domain(replay,first)
        original_domains[actor]=full
        _,policy_receipt=apply_policy(full,item_profile)
        actor_results=[]
        full_prefixes=resume(actor,'full',events) if resume else []
        observed_prefixes=resume(actor,'observed',events) if resume else []
        def save_prefix(layer,target):
            def save(result):
                if layer=='full':
                    from damage.explanations import explain_items
                    result['item_explanations']=explain_items(result,events[:len(result['updates'])],original_configurations=full,item_events=item_events)
                target.append(result)
                if checkpoint:checkpoint(actor,layer,result)
            return save
        filter_policy_joint(full,events,profile=item_profile,item_events=item_events,exhaustive_legal_alternatives=item_profile=='comprehensive',progress=progress,
                     on_update=save_prefix('full',full_prefixes),prior=full_prefixes[-1] if full_prefixes else None)
        filter_joint(observed,events,exhaustive_legal_alternatives=False,item_events=item_events,
                     on_update=save_prefix('observed',observed_prefixes),prior=observed_prefixes[-1] if observed_prefixes else None)
        for event,f,e in zip(events,full_prefixes,observed_prefixes):
            update=dict(id=event['id'],timestamp=event['timestamp'],attacker=actor,observation=event,
                        full=f,observed=e,item_policy=f.get('item_policy',policy_receipt))
            actor_results.append(update);updates.append(update)
        # Item-only evidence is causal even when it arrives after the last hit.
        # Rebuild the same original domain with all PREVIOUS hits before reveal;
        # the expensive path is only used for actual reviewed late evidence.
        for time in sorted({e['available_at'] for e in item_events if e['individual']==actor}):
            prefix=[o for o in events if o['timestamp']<=time]
            ledger=[e for e in item_events if e['available_at']<=time]
            if prefix:
                f=filter_policy_joint(full,prefix,profile=item_profile,item_events=ledger,available_at=time,progress=progress)
                e=filter_joint(observed,prefix,item_events=ledger)
                context=prefix[-1]
            else:
                at=next(s for s in reversed(originals) if s['timestamp']<=time)['opponents'][actor]
                initial=load_domain(at)
                enabled=[i for x in ledger if x['individual']==actor and x['kind']!='reviewed_negative' for i in [x['item'],*x.get('compatible_initial_items',[])]]
                confirmed=[x['item'] for x in ledger if x['individual']==actor and x['kind'] in {'held','activated','initial_held'}]
                domain,receipt=apply_policy(initial,item_profile,confirmed=confirmed,enabled=enabled)
                f=filter_joint(domain,[]);f['item_policy']=receipt
                e=filter_joint(observed_configuration_domain(replay,at),[])
                context=dict(attacker_form=at['current_form'],assumptions=[])
            f=refine_revealed(f,ledger,battle_id=replay['battle_id'],individual=actor,at=time)
            e=refine_revealed(e,ledger,battle_id=replay['battle_id'],individual=actor,at=time)
            actor_results.append(dict(id='item:'+actor+':'+str(time),timestamp=time,attacker=actor,
                observation=context,full=f,observed=e,item_policy=f['item_policy']))
        actor_results.sort(key=lambda u:u['timestamp'])
        results[actor]=actor_results
    times=sorted({s['timestamp'] for s in originals}|{o['timestamp'] for o in observations}|{e['available_at'] for e in item_events});old_times=[s['timestamp'] for s in originals]
    snapshots=[]
    configuration_catalog={}
    for time in times:
        snap=deepcopy(originals[bisect_right(old_times,time)-1]);snap['timestamp']=time
        for actor,history in results.items():
            available=[u for u in history if u['timestamp']<=time]
            if not available or actor not in snap['opponents']:continue
            update=available[-1];p=snap['opponents'][actor]
            if p['current_form']!=update['observation']['attacker_form']:
                raise ValueError('Later form transition requires explicit configuration transport')
            key='damage:'+update['id']+':'+p['support_ref']
            if key not in output['support_catalog']:
                support=deepcopy(replay['support_catalog'][p['support_ref']])
                for layer in ('full','observed'):
                    result=update[layer];configs=result['configurations']
                    if layer=='observed':
                        support[layer]['unresolved_record_ids']=sorted({cid for issue in result['unresolved'] for cid in issue.get('configuration_ids',[issue['id']])})
                        ids=set(support[layer]['builds']);configs=[c for c in configs if c['id'] in ids]
                        support[layer]['builds']=[c['id'] for c in configs]
                        support[layer]['ability_mappings']={c['id']:support[layer]['ability_mappings'][c['id']] for c in configs}
                        support[layer]['complete_after']=len(configs)
                        membership=sum(len(u['move_membership_excluded_ids']) for u in result['updates'])
                        numerical=sum(len(u.get('numerical_excluded_ids',u['excluded_ids'])) for u in result['updates'])
                        item_exclusions=sum(len(u.get('item_evidence_excluded_ids',[])) for u in result['updates'])
                        team_exclusions=sum(len(u.get('team_item_excluded_ids',[])) for u in result['updates'])
                        support[layer]['damage_exclusions']=dict(move_membership=membership,numerical=numerical,item_evidence=item_exclusions,team_uniqueness=team_exclusions)
                        if not configs:support[layer]['exhaustion_reason']='numerical_damage_incompatibility' if numerical else 'hard_evidence_incompatibility'
                    else:
                        later_ids=support[layer].get('surviving_configuration_ids')
                        if later_ids is not None:
                            later_set=set(later_ids);configs=[c for c in configs if c.get('speed_parent_id',c['id']) in later_set]
                            if not configs and item_profile=='practical':
                                prior_events=[e for e in observations if e['attacker']==actor and e['timestamp']<=time]
                                ledger=[e for e in item_events if e['available_at']<=time]
                                rescued=rescue_from_speed(original_domains[actor],later_set,prior_events,item_events=ledger)
                                if rescued is not None:result=rescued;configs=result['configurations']
                        support[layer].update(full_damage_projection(configs))
                    stat=result['updates'][-1]['selector']['offensive_stat'] if result['updates'] else 'attack'
                    info=project_joint(configs,stat)
                    support[layer]['speed']=info['speed']
                    support[layer]['offensive']=dict(**info,status=result['status'],evidence_ids=[u['id'] for u in result['updates']],
                        direct_constraint=bool(result['updates'] and result['updates'][-1]['selector']['constrains_opponent_offensive_stat']),
                        unresolved=issue_summary(result['unresolved']),requirements=result['requirements'])
                    support[layer]['offensive_stats']=offensive_projections(configs,result)
                    configuration_catalog[(key,layer)]=(configs,result)
                    if layer=='full':
                        support[layer]['item_policy']=result.get('item_policy',update['item_policy'])
                        explanation=result.get('item_explanations')
                        if explanation and concrete_ids(configs)==concrete_ids(result['configurations']):support[layer]['item_explanations']=explanation
                        else:
                            from damage.explanations import explain_items
                            prefix=[o for o in observations if o['attacker']==actor and o['timestamp']<=time]
                            if prefix:support[layer]['item_explanations']=explain_items(dict(result,configurations=configs),prefix,original_configurations=original_domains[actor],item_events=item_events)

                support['conditions']=sorted(set(support['conditions']+update['observation']['assumptions']))
                output['support_catalog'][key]=support
            p['support_ref']=key;p['legal_unmodified_speed']=output['support_catalog'][key]['full']['speed']
            p['configuration_count']=output['support_catalog'][key]['full']['configuration_count']
        snapshots.append(snap)
    output['snapshots']=snapshots;output['offensive_inference']=dict(version='own-hp-offensive-v1',updates=updates,item_profile=item_profile,item_events=list(item_events),initialization_metrics=dict(speed_domain_load_build_seconds=domain_seconds[0],pre_hit_projection_initialization_seconds=initial_projection_seconds))
    if any(e['kind'] in {'initial_held','initial_owner_options'} for e in item_events):
        project_team_items(output,configuration_catalog,item_profile,item_events,original_domains=original_domains)
    return output


def project_team_items(replay,configuration_catalog,item_profile,item_events,*,original_domains=None):
    """Shared matching relation at each causal support, including pre-hit refs.

    VGC records are individual training occurrences, not sampled whole teams.
    Each is checked for an extension in the legal reference team domain; records
    are never deduplicated or forced into an invented published-team product.
    """
    from .team_items import RULE_ID,original_assignments,owner_constraints,propagate,restrict_result,restrict_rows
    from damage.explanations import explain_items
    from .item_policy import action_item
    prepared={};projected={};relations={}
    for snap in replay['snapshots']:
        time=snap['timestamp'];actors=snap['opponents']
        claims=original_assignments(item_events,battle_id=replay['battle_id'],
            individual=next(iter(actors)),at=time) if actors else {}
        reservations=owner_constraints(item_events,battle_id=replay['battle_id'],individual=next(iter(actors)),at=time) if actors else {}
        signature=(tuple((a,p['support_ref']) for a,p in sorted(actors.items())),tuple(sorted(claims.items())),tuple((i,tuple(sorted(v))) for i,v in sorted(reservations.items())))
        if signature in projected:
            for a,ref in projected[signature].items():
                actors[a]['support_ref']=ref
                actors[a]['configuration_count']=replay['support_catalog'][ref]['full']['configuration_count']
                actors[a]['legal_unmodified_speed']=replay['support_catalog'][ref]['full']['speed']
            continue
        candidates={};domains={}
        for actor,p in actors.items():
            if not p.get('current_form'):continue
            ref=p['support_ref']
            team_enabled={i for i,owners in reservations.items() if actor in owners}
            for layer in ('full','observed'):
                cache_key=(actor,ref,layer,tuple(sorted(team_enabled)))
                if cache_key not in prepared:
                    if (ref,layer) in configuration_catalog:
                        rows,result=configuration_catalog[(ref,layer)]
                        result=dict(result,configurations=rows)
                    else:
                        rows=speed_configuration_domain(replay,p) if layer=='full' else observed_configuration_domain(replay,p)
                        if layer=='full':rows,receipt=apply_policy(rows,item_profile)
                        result=filter_joint(rows,[])
                        if layer=='full':result['item_policy']=receipt
                    prepared[cache_key]=result
                result=prepared[cache_key]
                if layer=='full' and team_enabled-set(result['requirements']['items']):
                    # Positive team provenance can require a dormant alternative
                    # on either possible original owner, without confirming it.
                    raw=speed_configuration_domain(replay,p)
                    expanded,receipt=apply_policy(raw,item_profile,enabled=team_enabled)
                    prefix=[u['observation'] for u in replay['offensive_inference']['updates'] if u['attacker']==actor and u['timestamp']<=time]
                    result=filter_joint(expanded,prefix,item_events=[e for e in item_events if e['available_at']<=time])
                    result['item_policy']=receipt;result['team_candidate_enabled']=sorted(team_enabled)
                    prepared[cache_key]=result
                from .team_items import ownership_rows
                result=dict(result,configurations=ownership_rows(result['configurations'],item_events,battle_id=replay['battle_id'],individual=actor,at=time))
                items={i for c in result['configurations'] for i in c.get('item_options',[c['item']])}
                if actor in claims:items&={claims[actor]}
                candidates[(actor,layer)]=(result,items)
                if layer=='full':domains[actor]=items
        # Reserve claims even if their owner is not yet in the visible snapshot.
        for actor,item in claims.items():domains[actor]={item}
        allowed=propagate(domains,enabled=True,reservations=reservations)
        # Practical dormancy is not a hard exclusion of VGC occurrences. Their
        # own damage constraints are already evaluated; other members may use
        # unevaluated dormant legal alternatives in a complete assignment.
        empirical_domains={a:set(v) for a,v in domains.items()}
        for actor in actors:
            if (actor,'observed') not in candidates:continue
            empirical_domains[actor].update(candidates[(actor,'observed')][1])
            empirical_domains[actor].update(candidates[(actor,'full')][0].get('item_policy',{}).get('dormant',[]))
        for actor,item in claims.items():empirical_domains[actor]={item}
        relation_id='team-items:'+hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()[:20]
        relations[relation_id]=dict(rule=RULE_ID,battle_id=replay['battle_id'],side='opponent',
            domains={a:sorted(v) for a,v in allowed.items()},confirmed_initial_items=claims,
            initial_owner_options={i:sorted(v) for i,v in reservations.items()},
            owner_requirements=[e.get('owner_requirements',{}) for e in item_events if e['kind']=='initial_owner_options' and e['available_at']<=time],
            combination_rule='all_different_except_none; require a complete bipartite matching; marginals cannot be freely combined')
        refs={}
        for actor,p in actors.items():
            if (actor,'full') not in candidates:continue
            old=p['support_ref'];new=relation_id+':'+actor
            support=deepcopy(replay['support_catalog'][old]);support['team_item_relation']=relation_id
            for layer in ('full','observed'):
                result,items=candidates[(actor,layer)]
                # A concrete empirical core must admit a legal full-team extension.
                from .team_items import matching
                permitted=allowed[actor] if layer=='full' else [i for i in items if matching(empirical_domains,(actor,i),reservations=reservations) is not None]
                excluded=items-set(permitted)
                excluded|={i for a,i in claims.items() if a!=actor and i!='none'}
                excluded|={i for i,owners in reservations.items() if actor not in owners}
                refined=restrict_result(result,permitted,reasons=excluded)
                rows=refined['configurations'];section=support[layer]
                section['team_item_constraint']=refined['team_item_constraint']
                section['speed']=project_joint(rows,'speed')['values']
                section['offensive_stats']=offensive_projections(rows,refined)
                if 'offensive' in section:
                    section['offensive'].update(project_joint(rows,section['offensive']['stat']),requirements=refined['requirements'])
                if layer=='full':
                    section.update(full_damage_projection(rows));section['item_policy']=refined.get('item_policy',{})
                    prefix=[o['observation'] for o in replay['offensive_inference']['updates'] if o['attacker']==actor and o['timestamp']<=time]
                    if prefix:
                        section['item_explanations']=explain_items(refined,prefix,original_configurations=(original_domains or {}).get(actor,result['configurations']),item_events=item_events)
                else:
                    ids={c['id'] for c in rows};section['builds']=[i for i in section['builds'] if i in ids]
                    section['ability_mappings']={i:v for i,v in section['ability_mappings'].items() if i in ids}
                    section['complete_after']=len(ids)
            replay['support_catalog'][new]=support;refs[actor]=new;p['support_ref']=new
            p['configuration_count']=support['full']['configuration_count'];p['legal_unmodified_speed']=support['full']['speed']
        projected[signature]=refs
    replay['team_item_relations']=relations
