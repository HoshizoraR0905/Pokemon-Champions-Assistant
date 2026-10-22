"""Source-bound adapter to M3.2.1 v2; no new arithmetic or action-order rules."""
from copy import deepcopy
from itertools import product

from knowledge.champions_stats import ChampionsStats
from speed_order import configuration_domain
from speed_order.core import ACTOR_KEYS, identity_key, knowledge, name
from speed_order.mechanics import effective_priority, move_fact
from .speed_replay import available_time, canonical_fact, current_identity
from .speed_items import item_classes, project_state_items, project_changes


def priority_alternatives(action, mon):
    """Ask the maintained handler for finite native ability/condition branches."""
    kb = knowledge(); catalog = kb.facts['moves'].get(action.get('move'), {})
    result = dict(base=catalog.get('priority'), values=[], status='unresolved', diagnostics=[])
    identity = current_identity(mon)
    ability = canonical_fact(mon.get('ability'))
    if not identity:
        result['diagnostics'] = ['current_form_unresolved']; return result
    abilities = [name(ability,'ability')] if ability else kb.facts['pokemon'].get(identity,{}).get('ability_names',[])
    if not abilities:
        result['diagnostics'] = ['native_ability_domain_missing']; return result
    try:
        label, _, fact = move_fact(action['move'])
        values = set()
        # These are explicit contextual possibilities, not probability weights.
        # Ground/HP fields matter only if the handler actually consults them.
        for a,active,hp,grounded,terrain in product(abilities,[False,True],[False,True],[False,True],['none','grassy']):
            p = dict(ability=a,ability_active=active,hp_full=hp,grounded=grounded)
            values.add(effective_priority(action,p,dict(terrain=terrain))['effective'])
        result.update(values=sorted(values),status='supported_native_alternatives')
    except (ValueError,KeyError,TypeError) as exc:
        result['diagnostics'] = [str(exc)]
    return result


def own_form_speed(build, current_form, *, timestamp=None):
    """Use configured full training for changed forms, never copy a base Speed."""
    if not build:
        return None, 'verified_own_individual_build_missing'
    if timestamp is not None and build.get('available_at',0)>timestamp:
        return None, 'own_build_binding_not_available_yet'
    if not current_form:
        return None, 'own_current_form_unresolved'
    if current_form == build['canonical_identity']:
        return build['stats']['speed'], None
    kb = knowledge()
    if kb.entities[current_form].species_id != kb.entities[build['canonical_identity']].species_id:
        return None, 'own_form_species_conflicts_with_build'
    fact = kb.facts['pokemon'].get(current_form,{})
    if not fact.get('required_item') or name(build['item'],'item') != fact['required_item']:
        return None, 'own_transformation_item_incompatible_or_unverified'
    if not build.get('training_points') or not build.get('alignment'):
        return None, 'own_transformed_training_configuration_missing'
    value = ChampionsStats(current_form,form='as_named').calculate(build['training_points'],build['alignment'])
    return value['stats']['speed'], None


def relevant_unknowns(participants, field, moves):
    """Only order-relevant fields; never demand defensive stats or unrelated HP."""
    reasons = []; weather = False; terrain = any(m == 'pokeapi:move:803' for m in moves.values())
    for iid,p in participants.items():
        ability = p.get('ability')
        abilities = ability if isinstance(ability,list) else [ability] if ability else []
        if not abilities:
            reasons.append(iid+':ability_domain_missing')
        labels = {name(a,'ability') for a in abilities}
        weather |= p.get('ability_active') is not False and bool(labels & {'Swift Swim','Chlorophyll','Sand Rush','Slush Rush'})
        terrain |= p.get('ability_active') is not False and 'Surge Surfer' in labels
        for field_name in ['stage','tailwind','status']:
            if p.get(field_name) is None:
                reasons.append(iid+':'+field_name+'_unknown')
        if labels & {'Unburden'} and p.get('unburden_active') is None:
            reasons.append(iid+':unburden_history_unknown')
        if labels & {'Gale Wings'} and p.get('hp_full') is None:
            # HP is only relevant for a Flying action by that participant.
            flying = knowledge().facts['moves'].get(moves.get(iid),{}).get('type')=='Flying'
            if flying:
                reasons.append(iid+':priority_HP_condition_unknown')
    if field.get('trick_room') is None:
        reasons.append('trick_room_unknown')
    if weather and field.get('weather') is None:
        reasons.append('relevant_weather_unknown')
    if terrain and field.get('terrain') is None:
        reasons.append('relevant_terrain_unknown')
    return reasons


def project_irrelevant_fields(state, moves, ability_domain):
    """Represent irrelevant unknowns for the strict v2 shape, with explicit receipts.

    Placeholders are never assertions about actual battle weather or activation.
    Unknown fields that could change order are left unknown and will be gated.
    """
    result=deepcopy(state);receipts=[];all_labels=set();complete_domains=True
    active_dependent={'Swift Swim','Chlorophyll','Sand Rush','Slush Rush','Surge Surfer','Unburden','Quick Feet','Stall'}
    for iid,p in result['participants'].items():
        abilities=ability_domain.get(iid) or ([p['ability']] if p.get('ability') else [])
        labels={name(a,'ability') for a in abilities};all_labels.update(labels)
        complete_domains &= bool(labels)
        move=knowledge().facts['moves'].get(moves.get(iid),{})
        priority_dependent=('Prankster' in labels and move.get('category')=='Status'
            or 'Gale Wings' in labels and move.get('type')=='Flying'
            or 'Triage' in labels)
        if labels and not labels & active_dependent and not priority_dependent and p.get('ability_active') is None:
            p['ability_active']=True;receipts.append(iid+':ability_active irrelevant to this move/order')
        if labels and 'Unburden' not in labels and p.get('unburden_active') is None:
            p['unburden_active']=False;receipts.append(iid+':Unburden history inapplicable')
    if complete_domains and not all_labels & {'Swift Swim','Chlorophyll','Sand Rush','Slush Rush'} and result['field'].get('weather') is None:
        result['field']['weather']='none';receipts.append('weather irrelevant within supplied ability domain')
    if complete_domains and 'Surge Surfer' not in all_labels and 'pokeapi:move:803' not in moves.values() and result['field'].get('terrain') is None:
        result['field']['terrain']='none';receipts.append('terrain irrelevant within supplied moves/ability domain')
    return result,receipts


def audit_pair(relation, actions, observable, builds, *, review=None):
    """Audit actual evidence; never promote an announcement count to queue closure.

    A sourced review may attach a complete pending set and action-time contexts.
    It cannot replace recognized move/actor IDs or use a future pending action at
    an earlier cutoff. Returns a prepared v2 observation only after these checks.
    """
    a,b = [actions[aid] for aid in relation['action_ids']]
    result = dict(id=relation['id'], action_ids=[a['id'],b['id']], event_ids=[a['event_id'],b['event_id']],
                  timestamp=max(available_time(a),available_time(b)), status='deferred', blockers=[],
                  model_blockers=[], observation=None, configurations=None, priorities={},
                  required_fields=['stable identities','current forms','complete pending coverage',
                                   'own current-form Speed','order-relevant modifiers'],
                  not_required=['opponent HP except applicable Gale Wings','defensive/offensive stats',
                                'move damage','unrelated stat stages','absolute game turn number'],
                  sources=deepcopy(a['sources']+b['sources']))
    if {a['side'],b['side']} != {'self','opponent'}:
        result.update(status='rejected',blockers=['comparison_requires_one_verified_own_actor']);return result
    if a['instance_id']==b['instance_id']:
        result.update(status='rejected',blockers=['same_individual_repeated_action_requires_handler']);return result
    if not all(x['actor_identity_reliable'] and x['move_identity_reliable'] for x in [a,b]):
        result['blockers'].append('actor_or_move_identity_unreliable')
    if a['timestamp'] is None or b['timestamp'] is None or a['timestamp']>=b['timestamp']:
        result['blockers'].append('chronology_unverified')
    if (a.get('turn_id')!=b.get('turn_id') or a['membership'].get('status')!='confirmed_local_membership'
            or b['membership'].get('status')!='confirmed_local_membership'):
        result['blockers'].append('compatible_local_decision_unverified')
    mons = observable.get('pokemon',{})
    for x in [a,b]:
        mon=mons.get(x['instance_id'],{})
        result['priorities'][x['id']]=priority_alternatives(x,mon)
        if not current_identity(mon):
            result['blockers'].append(('own' if x['side']=='self' else 'opponent')+'_current_form_unresolved')
        if result['priorities'][x['id']]['status']=='unresolved':
            diagnostics=result['priorities'][x['id']]['diagnostics']
            if not any(d in {'current_form_unresolved','native_ability_domain_missing'} for d in diagnostics):
                result['model_blockers'].append(dict(action_id=x['id'],kind='v2_move_or_priority_handler_unsupported',
                    detail=diagnostics,catalog_base=result['priorities'][x['id']]['base']))
    priorities=[result['priorities'][x['id']]['values'] or
                (x.get('priority',{}).get('effective_priorities',[]) if
                 x.get('priority',{}).get('status')!='special_action' else []) for x in [a,b]]
    if all(priorities) and set(priorities[0]).isdisjoint(priorities[1]):
        result.update(status='rejected',blockers=['different_effective_priority_brackets'],
                      priority_scope='supplied native-form catalog alternatives; no Speed inequality');return result
    own=next(x for x in [a,b] if x['side']=='self')
    speed,reason=own_form_speed(builds.get(own['instance_id']),current_identity(mons.get(own['instance_id'],{})),
                               timestamp=available_time(own))
    result['own_current_form_speed']=speed
    if reason:
        result['blockers'].append(reason)
    if review is None:
        result['blockers'].append('pending_action_coverage_not_certified')
        finite={}
        for x in [a,b]:
            mon=mons.get(x['instance_id'],{})
            for label, fact in [('speed_stage',mon.get('stages',{}).get('speed')),
                                ('status',mon.get('status'))]:
                if canonical_fact(fact) is None:
                    result['blockers'].append(x['side']+':'+label+'_unknown')
                    finite[x['instance_id']+':'+label]=list(range(-6,7)) if label=='speed_stage' else [
                        'none','burn','poison','toxic','paralysis','sleep','freeze']
        if canonical_fact(observable.get('trick_room',{}).get('active')) is None:
            result['blockers'].append('trick_room_unknown')
            finite['trick_room']=[False,True]
        result['finite_state_possibilities']=finite
        result['unknown_state_policy']='Can be explicit finite alternatives; exact state is not mandatory. '
        result['unknown_state_policy']+='Coverage/handler certification is required before submitting their full product; no neutral choice made.'
        result['blockers'].append('action_time_modifier_continuity_not_certified')
        result['blockers']=sorted(set(result['blockers']))
        return result
    return prepare_review(result, relation, actions, builds, review)


def prepare_review(result, relation, actions, builds, review):
    """Small correction/attachment contract; source IDs and chronology are immutable."""
    from speed_order.contracts import require_evidence
    try:
        require_evidence(review['evidence'])
        if {'actor_or_move_identity_unreliable','chronology_unverified'} & set(result['blockers']):
            raise ValueError('Review cannot replace immutable actor/move chronology')
        if review.get('verified') is not True or review.get('pending_coverage_complete') is not True:
            raise ValueError('Verified complete pending coverage required')
        selected=[actions[aid] for aid in review['pending_action_ids']]
        if len({a['id'] for a in selected})!=len(selected) or not set(relation['action_ids']) <= {a['id'] for a in selected}:
            raise ValueError('Comparison must belong to the explicit unique pending set')
        if (len({a['battle_id'] for a in selected})!=1 or len({a['turn_id'] for a in selected})!=1
                or not selected[0]['turn_id']):
            raise ValueError('Cross-battle/turn pending coverage rejected')
        if any(a['origin']!=review['origin'] for a in selected):
            raise ValueError('Synthetic/recorded provenance mismatch')
        if any(not a['actor_identity_reliable'] or not a['move_identity_reliable'] for a in selected):
            raise ValueError('Unreliable actor/move cannot be replaced by review')
        timestamp=max([result['timestamp'],review['available_at']] + [available_time(a) for a in selected])
        if review['origin']=='recorded' and review['evidence']['basis']=='synthetic':
            raise ValueError('A synthetic attachment cannot certify recorded coverage')
        state=deepcopy(review['state']); pending=[]
        for a in selected:
            p=state['participants'][a['instance_id']]
            if p['instance_id']!=a['instance_id']:
                raise ValueError('Reviewed participant identity mismatch')
            reviewed_identity=identity_key(p['identity'],p['form'])
            observed=a.get('observed_species')
            if observed and knowledge().entities[observed].species_id!=knowledge().entities[reviewed_identity].species_id:
                raise ValueError('Review cannot replace recognized actor species')
            if a['side']=='self':
                speed,reason=own_form_speed(builds.get(a['instance_id']),reviewed_identity,timestamp=timestamp)
                if reason:
                    raise ValueError(reason)
                if p['actual_speed'] is not None and p['actual_speed']!=speed:
                    raise ValueError('Review cannot replace configured/current-form own Speed')
                p['actual_speed']=speed
                build=builds[a['instance_id']]
                if build.get('training_points') is not None and build.get('alignment') is not None:
                    p['training']=dict(alignment=deepcopy(build['alignment']),
                        point_domains={s:[v] for s,v in build['training_points'].items()})
            if review['outcomes'].get(a['id'])!='completed':
                raise ValueError('Executed outcome/pending coverage not established')
            pending.append(dict(id=a['id'],individual=a['instance_id'],kind='move',move=a['move'],
                outcome='completed',activation=deepcopy(review['activation'][a['id']]),
                changes=deepcopy(review['changes'].get(a['id'],[])),evidence=deepcopy(review['evidence'])))
        subject=review['subject']
        if subject not in {a['instance_id'] for a in selected if a['side']=='opponent'}:
            raise ValueError('Subject must be an observed opposing individual')
        if set(state['participants']) != {a['instance_id'] for a in selected}:
            raise ValueError('State/pending participant mismatch')
        specification=deepcopy(review['configuration_domain'])
        if specification.pop('complete_given_evidence',False) is not True:
            raise ValueError('Exhaustive configuration domain evidence required')
        require_evidence(specification.pop('evidence'))
        # Domain facts must be usable now, independently of later item reveals.
        timestamp=max(timestamp,specification.pop('available_at'))
        current_form=identity_key(specification['identity'],specification['form'])
        classes=item_classes(current_form,specification['items'])
        solver_specification=deepcopy(specification)
        solver_specification['items']=[c['representative'] for c in classes]
        domain=configuration_domain(**solver_specification)
        source_state=deepcopy(state)
        state,item_receipts=project_state_items(state)
        for action in pending:
            action['changes']=project_changes(action['changes'],source_state)
        state,projections=project_irrelevant_fields(state,{a['instance_id']:a['move'] for a in selected},
            {subject:specification['abilities']})
        observation=dict(id=relation['id'],battle_id=selected[0]['battle_id'],decision_id=selected[0]['turn_id'],
            subject=subject,state=state,actions=pending,sequence=[a['id'] for a in sorted(selected,key=lambda a:a['timestamp'])],
            initial_changes=project_changes(review['initial_changes'],source_state),alternatives=deepcopy(review['alternatives']),
            strict_speed=[],evidence=deepcopy(review['evidence']))
        result.update(timestamp=timestamp,status='prepared',blockers=[],model_blockers=[],
                      observation=observation,configurations=domain['configurations'],irrelevant_field_projections=projections,
                      item_equivalence_classes=classes,item_state_projections=item_receipts,
                      review_provenance=dict(origin=review['origin'],reviewer=deepcopy(review.get('reviewer')),
                          available_at=timestamp,evidence=deepcopy(review['evidence'])))
    except (ValueError,KeyError,TypeError,NotImplementedError) as exc:
        result['blockers']=sorted(set(result['blockers']+[str(exc)]))
    return result
