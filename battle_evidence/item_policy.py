"""Candidate policy on existing persistent rows, never a third support layer.

Dormancy is a modeling omission. Positive item evidence must be source reviewed;
negative UI observations require a verified message guarantee before exclusion.
"""
from copy import deepcopy
from damage.items import rule,candidate_applicable,effect_applicable

PROFILES=('practical','comprehensive')
EVIDENCE_RESCUE_ITEMS=('Life Orb',)
RESCUE_ITEMS=('Life Orb','Iron Ball')
POLICY_VERSION='M3.4.5a'


def item_state(events, *, battle_id, individual, at):
    state=dict(confirmed_item=None,current_item=None,consumed=[],activations={},reviewed_negative=[],coverage='unreviewed')
    last=-1
    for e in events:
        if e['battle_id']!=battle_id or e['individual']!=individual:continue
        if e['timestamp']<last:raise ValueError('Item evidence must be chronological')
        last=e['timestamp']
        if e['available_at']>at:continue
        if e['available_at']<e['timestamp'] or not e.get('reviewer') or not e.get('sources'):
            raise ValueError('Source-reviewed item evidence and causal availability required')
        if not rule(e['item']):raise ValueError('Nonlegal item evidence')
        if e['kind']=='reviewed_negative':
            if not e.get('coverage_complete'):raise ValueError('Reviewed negative requires complete relevant window')
            state['reviewed_negative'].append(e);state['coverage']='reviewed_negative'
            # No verified Champions UI guarantee in this registry. Record only.
            continue
        if e['kind']=='initial_owner_options':
            state['initial_owner_options']=e['initial_owner_options'];continue
        if e['kind'] not in {'held','initial_held','activated','consumed','transferred_in','transferred_out','removed','replaced','restored','unresolved_transfer'}:raise ValueError('Unsupported item event')
        if e['kind']=='initial_held':
            state['initial_item']=e['item'];continue
        if e['kind']=='unresolved_transfer':
            state['current_item']=None;state['coverage']='unresolved_transition';continue
        if state['confirmed_item'] and state['current_item'] not in (None,e['item']) and e['kind'] not in {'transferred_in','replaced','restored'}:
            raise ValueError('Item continuity conflict; explicit transfer/loss required')
        state['confirmed_item']=e['item'];state['current_item']=e['item']
        if e['kind']=='activated':
            if e['item']=='Life Orb':
                basis=e.get('activation_basis')
                if basis not in {'reviewed_item_message','attributed_recoil'} or not e.get('action_id'):raise ValueError('Life Orb activation requires an attack-bound reviewed message or specific recoil')
                if e.get('exact_wording'):
                    from .life_orb import reviewed_message
                    message=reviewed_message(e['exact_wording'],actor_name=e.get('actor_name',''),individual=e['individual'],action_id=e['action_id'])
                    if not message or not message['confirms_life_orb']:raise ValueError('Generic recoil or another actor cannot confirm Life Orb')
                if basis=='attributed_recoil':
                    from .life_orb import expected_recoil
                    context=e.get('recoil_context',{})
                    recoil=expected_recoil(**context) if {'ability','move'}<=set(context) else None
                    if not e.get('exclusive_attribution') or not recoil or e.get('hp_before',0)-e.get('hp_after',0)!=recoil:raise ValueError('Life Orb recoil requires exclusive source attribution and a matching audited HP change')
            if e['item']=='Quick Claw' and not e.get('action_id'):raise ValueError('Quick Claw activation requires action identity')
            state['activations'][e.get('action_id',str(e['timestamp']))]=e['item']
        if e['kind'] in {'consumed','transferred_out','removed'}:
            state['current_item']='none';state['consumed'].append(e)
        state['coverage']='positive_observed'
    return state


def quick_claw_activation(state,action_id):
    # Possession never manufactures an activation. Unreviewed actions stay unknown.
    return 'activated' if state['activations'].get(action_id)=='Quick Claw' else 'unknown'


def apply_policy(rows, profile='practical', *, confirmed=(), enabled=(), rescue_iron_ball=True):
    if profile not in PROFILES:raise ValueError('Unknown item policy profile')
    confirmed=set(confirmed);enabled=set(enabled)|confirmed
    applicable=[];inapplicable=set();dormant=set();retained=set()
    ordinary=any(any(candidate_applicable(i,c['form']) and i!='Iron Ball' for i in c.get('item_options',[c['item']])) for c in rows)
    for c in rows:
        options=[]
        for i in c.get('item_options',[c['item']]):
            if not candidate_applicable(i,c['form']):inapplicable.add(i);continue
            r=rule(i)
            active=(profile=='comprehensive' or i=='none' or i in enabled or
                    (i not in EVIDENCE_RESCUE_ITEMS and r['category'] in {'standard','species_specific'} and effect_applicable(i,c['form'])) or
                    (i=='Iron Ball' and rescue_iron_ball and not ordinary))
            if active:options.append(i);retained.add(i)
            else:dormant.add(i)
        if options:
            row=dict(c,item=options[0])
            if 'item_options' in c:row['item_options']=options
            applicable.append(row)
    return applicable,dict(version=POLICY_VERSION,evidence_rescue_items=list(EVIDENCE_RESCUE_ITEMS),profile=profile,exhaustive_legal_items=profile=='comprehensive',
        retained=sorted(retained),dormant=sorted(dormant),inapplicable_stones=sorted(inapplicable),activated=sorted(confirmed),
        policy_omissions_are_not_evidence_exclusions=True,
        iron_ball_rescue=not ordinary and 'Iron Ball' in retained,
        assumption='Practical utility-item whitelist; no usage-frequency prior. Dormant names remain legally possible; equivalent rows retain concrete item_options.')


def split_identity(rows,item):
    """Reveal an item by intersecting old rows, preserving all prior SP limits."""
    result=[]
    for c in rows:
        if item not in c.get('item_options',[c['item']]):continue
        r=deepcopy(c);r['item']=item
        if 'item_options' in c:r['item_options']=[item]
        result.append(r)
    return result


def action_item(initial, events, *, battle_id, individual, at, available_at):
    """Apply a reviewed ledger to a hypothesis at action time, not frame time.

    Returns None for positive-evidence contradiction. Negative message windows
    do not establish absence. Consumption preserves the original hidden identity.
    """
    current=initial
    for e in events:
        if e['battle_id']!=battle_id or e['individual']!=individual or e['available_at']>available_at:continue
        if e['kind']=='initial_held':
            if initial!=e['item']:return None
            continue
        if e['kind']=='initial_owner_options':continue
        if e['timestamp']>at:continue
        if e['kind']=='reviewed_negative':continue
        if e.get('compatible_initial_items'):
            if initial not in e['compatible_initial_items']:return None
            if initial!=e['item']:
                current='unknown' if at==e['timestamp'] else e['item']
            continue
        if e['kind']=='unresolved_transfer':
            # Unknown history must not identify the original item. Numerical
            # use of this current item is separately marked unresolved.
            current=None;continue
        if e['kind'] in {'transferred_in','replaced','restored'}:
            if e['timestamp']<at or e.get('phase')=='before_action':current=e['item']
            continue
        if current is None:
            if e['kind'] in {'held','activated'}:current=e['item']
            continue
        if current!=e['item']:return None
        if e['kind'] in {'consumed','transferred_out','removed'} and (e['timestamp']<at or e.get('phase')=='before_action'):current='none'
    return current if current is not None else 'unknown'


def filter_policy_joint(rows, observations, *, profile='practical', item_events=(), available_at=None, **kwargs):
    """Activate ONLY original rows, replaying the entire prefix for a rescue.

    Rescue is a hypothesis, not confirmation. A still-supported ordinary domain
    or retained unsupported domain never triggers an infeasibility rescue.
    """
    from damage.joint import filter_joint
    actor=observations[0].get('attacker') if observations else None
    battle=observations[0].get('battle_id') if observations else None
    callback=kwargs.pop('on_update',None);current=kwargs.pop('prior',None)
    memo=kwargs.pop('evaluation_cache',None)
    if memo is None:memo={}
    rescued=set(current.get('item_policy',{}).get('rescued',[])) if current else set()
    rescue_history=list(current.get('item_policy',{}).get('rescue_history',[])) if current else []
    done=len(current['updates']) if current else 0
    if done>len(observations):raise ValueError('Policy checkpoint exceeds observation prefix')
    if current:
        import hashlib,json
        if any(u['id']!=o['id'] or u.get('observation_fingerprint')!=hashlib.sha256(json.dumps(o,sort_keys=True).encode()).hexdigest() for u,o in zip(current['updates'],observations)):raise ValueError('Policy checkpoint observation inputs changed')
    for index,obs in enumerate(observations):
        if index<done:continue
        at=available_at if available_at is not None else obs['timestamp']
        ledger=[e for e in item_events if e['available_at']<=at]
        positive={e['item'] for e in ledger if e['battle_id']==battle and e['individual']==actor and e['kind']!='reviewed_negative'}
        domain,receipt=apply_policy(rows,profile,confirmed=positive,enabled=rescued)
        prefix=observations[:index+1]
        # An evidence/policy expansion must never graft an item onto survivors.
        previous_enabled=set(current.get('item_policy',{}).get('activated',[])) if current else set()
        resume=current if current and previous_enabled==positive else None
        result=filter_joint(domain,prefix,prior=resume,item_events=ledger,evaluation_cache=memo,**kwargs)
        if profile=='practical' and not result['configurations']:
            for item in RESCUE_ITEMS:
                if item in positive|rescued:continue
                candidate,expanded=apply_policy(rows,profile,confirmed=positive,enabled=rescued|{item})
                if not any(item in c.get('item_options',[c['item']]) for c in candidate):continue
                trial=filter_joint(candidate,prefix,item_events=ledger,evaluation_cache=memo,**kwargs)
                viable=item in trial['requirements']['supported_items']
                unresolved=item in trial['requirements']['unresolved_items']
                rescue_history.append(dict(item=item,timestamp=obs['timestamp'],observation=obs['id'],status='viable_rescue' if viable else 'unresolved_rescue' if unresolved else 'no_rescue',replayed_observations=[o['id'] for o in prefix],confirmation=False))
                if viable or unresolved:
                    rescued.add(item);result=trial;receipt=expanded
        receipt.update(rescued=sorted(rescued),rescue_history=list(rescue_history))
        from .team_items import exclusions
        forbidden=exclusions(ledger,battle_id=battle,individual=actor,at=at)
        for key in ('dormant','retained','rescued'):
            receipt[key]=[i for i in receipt.get(key,[]) if i not in forbidden]
        if forbidden:result['team_item_constraint']=dict(excluded_items=sorted(forbidden),reason='Excluded by team-wide item uniqueness evidence.')
        result['item_policy']=receipt;current=result
        if callback:callback(result)
    if current is not None:return current
    domain,receipt=apply_policy(rows,profile)
    result=filter_joint(domain,[],**kwargs);receipt.update(rescued=[],rescue_history=[]);result['item_policy']=receipt
    return result


def validate_item_review(events,replay,*,root):
    """Source-bound adapter, deliberately no new OCR/message detector."""
    from .speed_replay_offline import file_hash
    frames={f['source_id']:f for f in replay['frames']}
    actors={i for s in replay['snapshots'] for i in s['opponents']}
    for e in events:
        if e['battle_id']!=replay['battle_id'] or e['individual'] not in actors:raise ValueError('Item evidence identity/battle mismatch')
        if e['kind'] in {'initial_held','initial_owner_options'}:
            from .team_items import original_assignments
            if e['kind']=='initial_held':original_assignments([e],battle_id=e['battle_id'],individual=e['individual'],at=e['available_at'])
            else:
                from .team_items import owner_constraints
                owner_constraints([e],battle_id=e['battle_id'],individual=e['individual'],at=e['available_at'])
            proof=e['initial_ownership_review']
            if proof.get('basis')=='first_action_named_activation':
                a=next((a for a in replay['action_timeline'] if a['id']==proof['action_id']),None)
                moves=[a for a in replay['action_timeline'] if a['kind']=='executed_move' and a['timestamp']<=e['timestamp']]
                if not a or a['individual']!=e['individual'] or len(moves)!=1 or moves[0]['id']!=a['id']:
                    raise ValueError('Original ownership first-action continuity mismatch')
        item_state([e],battle_id=e['battle_id'],individual=e['individual'],at=e['available_at'])
        for s in e['sources']:
            f=frames.get(s['source_id'])
            if not f or any(f[k]!=s[k] for k in ('image','sha256')) or f['timestamp']>e['available_at'] or file_hash(root/s['image'])!=s['sha256']:
                raise ValueError('Missing, altered or future item source')
        if e['item'] in {'Quick Claw','Life Orb'} and e['kind']=='activated':
            a=next((a for a in replay['action_timeline'] if a['id']==e['action_id']),None)
            if not a or a['individual']!=e['individual'] or a['timestamp']!=e['timestamp']:raise ValueError('Item activation source action mismatch')


def refine_revealed(result,events,*,battle_id,individual,at):
    """Intersect current evidence without discarding original item identities."""
    from damage.joint import concrete_ids,_joint_result
    from time import perf_counter
    rows=[]
    from .team_items import exclusions
    forbidden=exclusions(events,battle_id=battle_id,individual=individual,at=at)
    for c in result['configurations']:
        items=[i for i in c.get('item_options',[c['item']]) if i not in forbidden and action_item(i,events,battle_id=battle_id,individual=individual,at=at,available_at=at) is not None]
        if items:
            r=dict(c,item=items[0])
            if 'item_options' in c:r['item_options']=items
            rows.append(r)
    unknown={cid for u in result['unresolved'] for cid in u.get('configuration_ids',[u['id']])}
    refined=_joint_result(rows,result['updates'],result['unresolved'],unknown,False,
                          result['work']['forward_evaluations'],result['work']['cached_inputs'],perf_counter())
    refined['work']=result['work']
    if 'item_policy' in result:refined['item_policy']=result['item_policy']
    refined['item_evidence']=item_state(events,battle_id=battle_id,individual=individual,at=at)
    if forbidden:
        from .team_items import restrict_result
        refined=restrict_result(refined,{i for c in rows for i in c.get('item_options',[c['item']])},reasons=forbidden)
    return refined


def reviewed_order_activation(events,*,battle_id,individual,action_id,at):
    state=item_state(events,battle_id=battle_id,individual=individual,at=at)
    positives=[e for e in events if e['battle_id']==battle_id and e['individual']==individual and e.get('action_id')==action_id and e['available_at']<=at and e['kind']=='activated' and e['item']=='Quick Claw']
    return dict(state=quick_claw_activation(state,action_id),coverage_complete=False,
                evidence=dict(sources=[s['source_id'] for e in positives for s in e['sources']] or ['item-policy:unreviewed'],
                              basis='direct' if positives else 'reference',confidence='source-reviewed' if positives else 'unknown'))


def rescue_from_speed(original_rows,parent_ids,observations,*,item_events=()):
    """Use only original IDs surviving new Speed, then replay all damage.

    No item is grafted onto an already narrowed row of another identity.
    """
    ids=set(parent_ids)
    rows=[r for r in original_rows if r.get('speed_parent_id',r['id']) in ids]
    if not rows:return None
    result=filter_policy_joint(rows,observations,profile='practical',item_events=item_events)
    return result if result['configurations'] and (result['item_policy'].get('rescued') or result['item_policy'].get('iron_ball_rescue')) else None
