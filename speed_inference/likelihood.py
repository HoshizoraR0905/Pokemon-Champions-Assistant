"""Evidence admission and pairwise likelihood through the existing M3.2 API."""
from copy import deepcopy
from functools import lru_cache
from knowledge.champions_stats import ChampionsStats
from speed_order.core import evaluate_order,identity_key,name,knowledge,PROFILES,REFERENCE

VERIFICATIONS={'actor_identity','move_identity','turn_membership','chronology','priority',
               'state_at_decision','order_exceptions','continuity','own_unmodified_speed'}


@lru_cache(maxsize=64)
def legal_speeds(identity,form):
    return frozenset(ChampionsStats(identity,form=form).attainable('speed',adjustments=['0.9','1.0','1.1'])['values'])


def admission(observation,key,identity):
    problems=[]
    if observation.get('evidence_kind')!='verified_action_order':problems.append('action_order_not_verified')
    if observation.get('origin') not in ('recorded','synthetic'):problems.append('evidence_origin_not_declared')
    verified=observation.get('verification',{})
    for field in sorted(VERIFICATIONS):
        if not isinstance(verified,dict) or verified.get(field) is not True:problems.append(field+'_unverified')
    if not isinstance(observation.get('provenance'),list) or not observation['provenance']:problems.append('source_provenance_missing')
    try:
        context=observation['context'];p=context['opponent'];own=context['own']
        if (observation['battle_id'],p['instance_id'],observation['stat_epoch'])!=key:problems.append('different_battle_individual_or_stat_epoch')
        if identity_key(p['identity'],p['form'])!=identity:problems.append('opponent_current_form_changed')
        if own['instance_id']==p['instance_id']:problems.append('same_actor_in_both_roles')
        if observation.get('sequence') not in (['own','opponent'],['opponent','own']):problems.append('chronological_sequence_missing')
        ids=observation['action_ids']
        if set(ids)!= {'own','opponent'} or any(not isinstance(v,str) or not v for v in ids.values()) or ids['own']==ids['opponent']:
            problems.append('distinct_underlying_action_ids_required')
        if type(context['timing']['turn']) is not int or context['timing']['turn']<1 or not context['timing']['decision_id']:
            problems.append('ordering_decision_identity_missing')
        if any(context['actions'][side]['kind']!='move' for side in ('own','opponent')):problems.append('not_two_ordinary_move_actions')
        if not context['comparable'] or context['timing']['state_at']!='order_decision' or context['timing']['modifier_changes']:
            problems.append('unverified_ordering_snapshot_or_mid_turn_modifier_changes')
        actual=own['actual_speed']
        if type(actual) is not int or actual not in legal_speeds(own['identity'],own['form']):problems.append('own_unmodified_speed_unavailable_or_outside_legal_projection')
        for side in ('own','opponent'):
            participant=context[side];current_identity=identity_key(participant['identity'],participant['form'])
            fact=knowledge().facts['pokemon'].get(current_identity,{})
            ability=participant['ability']
            if ability is not None and name(ability,'ability') not in fact.get('ability_names',[]):
                problems.append(side+'_native_ability_not_in_pinned_form_catalog; transfer_or_suppression_needs_explicit_model')
            item=participant['item']
            if item is not None and fact.get('required_item') and name(item,'item')!=fact['required_item']:
                problems.append(side+'_item_conflicts_with_required_current_form_item')
    except (ValueError,TypeError,KeyError,NotImplementedError) as exc:problems.append('incomplete_or_invalid_context:'+str(exc))
    return sorted(set(problems))


def likelihoods(model,observation,alive,profile):
    if profile not in PROFILES:return None,['unsupported_rules_profile'],[]
    if profile!=REFERENCE:
        return None,['Champions-specific ordinary ordering, tie probability and modifier rounding are not independently certified; strict profile declines update'],[]
    context=observation['context'];first=observation['sequence'][0]
    values=[];details=[];problems=[];memo={}
    for candidate,positive in zip(model['candidates'],alive):
        if not positive:values.append(0.);continue
        c=deepcopy(context);incompatible=False
        for kind in ('ability','item'):
            assignment=candidate[kind];current=c['opponent'][kind]
            if current is not None:
                try:current=name(current,kind)
                except ValueError as exc:problems.append(str(exc));continue
                if assignment is not None and assignment!=current:incompatible=True
            else:current=assignment
            c['opponent'][kind]=current
            if kind=='ability' and current is not None and current not in knowledge().facts['pokemon'][model['identity']]['ability_names']:
                problems.append('Observed native ability not supported for the form; changed/transferred abilities need a dedicated model')
        if incompatible:
            values.append(0.);details.append(dict(candidate_id=candidate['id'],likelihood=0.,reason='incompatible_known_persistent_configuration'));continue
        if c['opponent']['actual_speed'] is not None:
            problems.append('Opponent unmodified Speed must be inferred, not substituted in the observation')
        speed=candidate['unmodified_speed']
        memo_key=(speed,c['opponent']['ability'],c['opponent']['item'])
        if memo_key not in memo:memo[memo_key]=evaluate_order(context=c,opponent_speed=speed,profile=profile)
        outcome=memo[memo_key]
        if outcome['status']!='assessed' or outcome['kind']!='speed':
            problems.append(outcome['reason']);values.append(None);continue
        probability=.5 if outcome['tie'] else 1. if first in outcome['orders'] else 0.
        values.append(probability);details.append(dict(candidate_id=candidate['id'],likelihood=probability,
            own_effective_speed=outcome['own']['effective_speed'],opponent_effective_speed=outcome['opponent']['effective_speed'],tie=outcome['tie']))
    # Never drop an unsupported positive-prior branch to produce a posterior.
    return (None if problems else values),sorted(set(problems)),details
