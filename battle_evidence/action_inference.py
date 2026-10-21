"""Deterministic reanalysis of retained comparisons; no recognition dependency."""
from copy import deepcopy
from speed_inference import BeliefBank, SpeedBelief, configuration_space
from speed_inference.domains import digest
from speed_inference.likelihood import VERIFICATIONS
from speed_order.core import identity_key


def analyse(result, builds, *, profile='champions-evidence-only-v1', comparisons=None):
    """Explicit reviewed decision contexts may be attached after build binding.

    comparisons is keyed by stable relation ID. It contains context, verification,
    provenance, stat_epoch, and optionally explicit conditional modifier domains.
    Only one pair per WHOLE local turn enters any posterior: shared tie draws,
    activation draws and transitive relations are never multiplied separately.
    """
    out = deepcopy(result); bid = out['battle_id']; bank = BeliefBank(); used_turns = set()
    actions = {a['id']: a for a in out['actions']}; comparisons = comparisons or {}
    if set(comparisons)-{r['id'] for r in out['relations']}:
        raise ValueError('Comparison review references unknown retained evidence')
    for a in actions.values():
        b = builds.records.get((bid,a['instance_id']))
        a['configured_build'] = deepcopy(b)
        a['configured_speed'] = b['stats']['speed'] if b else None
        a['configured_speed_scope'] = 'base configured form only; current form, transformation and battle modifiers require independent evidence'
    for r in out['relations']:
        a,b = [actions[k] for k in r['action_ids']]; roles={a['side']:a,b['side']:b}
        r['numeric_reasons'] = list(r['reasons'])
        if set(roles) != {'self','opponent'}:
            r['numeric_reasons'].append('joint_hidden_actor_model_required'); continue
        own = roles['self']; opp = roles['opponent']; build = builds.records.get((bid,own['instance_id']))
        if not build or build['stats']['speed'] is None:
            r['numeric_reasons'].append('verified_own_speed_missing'); continue
        review = comparisons.get(r['id'])
        if not review:
            r['numeric_reasons'].append('verified_comparison_context_missing'); continue
        if r['turn_id'] in used_turns:
            r['quantitative_status']='dependent_relation_omitted'; continue
        # Context admission belongs to existing inference engine; never turn
        # incomplete modifiers into neutral assignments in this adapter.
        if review.get('verified') is not True or not review.get('sources'):
            raise ValueError('Verified comparison provenance required')
        if a['origin']!=b['origin'] or review.get('origin','recorded')!=a['origin']:
            raise ValueError('Mixed synthetic and recorded evidence')
        reviewed_changes=review.get('intervening_event_review',{})
        if any(not reviewed_changes.get(eid,{}).get('sources') or
               reviewed_changes.get(eid,{}).get('order_relevance')!='verified_no_order_change'
               for eid in r['intervening_event_ids']):
            r['numeric_reasons'].append('intervening_event_order_relevance_unverified');continue
        c=deepcopy(review['context'])
        if (c['own']['instance_id'],c['opponent']['instance_id']) != (own['instance_id'],opp['instance_id']):
            raise ValueError('Reviewed context individual mismatch')
        if identity_key(c['own']['identity'],c['own']['form']) != build['canonical_identity']:
            r['numeric_reasons'].append('configured_form_differs_from_current_form'); continue
        if a['timestamp'] is None or b['timestamp'] is None or a['timestamp']>=b['timestamp']:
            r['numeric_reasons'].append('chronology_ambiguous'); continue
        if not (a['actor_identity_reliable'] and b['actor_identity_reliable'] and
                a['move_identity_reliable'] and b['move_identity_reliable']):
            r['numeric_reasons'].append('action_identity_evidence_incomplete'); continue
        if any(x['membership'].get('status')!='confirmed_local_membership' for x in (a,b)):
            r['numeric_reasons'].append('local_membership_incomplete'); continue
        for role,action in [('own',own),('opponent',opp)]:
            if c['actions'][role]['move'] != action['move']:
                raise ValueError('Review cannot replace executed move')
        c['own']['actual_speed']=build['stats']['speed']
        c['timing']['turn']=own['local_index'];c['timing']['decision_id']=r['turn_id']
        epoch=review['stat_epoch'];key=(bid,opp['instance_id'],epoch)
        if key not in bank.beliefs:
            model=configuration_space(identity=c['opponent']['identity'],form=c['opponent']['form'],
                **review.get('model_domains',{}))
            bank.register(model,battle_id=bid,instance_id=key[1],stat_epoch=epoch,profile=profile)
        observation=dict(id=r['id'],battle_id=bid,stat_epoch=epoch,evidence_kind='verified_action_order',
            origin=review.get('origin','recorded'),context=c,
            sequence=['own','opponent'] if a['side']=='self' else ['opponent','own'],
            verification={k:review.get('verification',{}).get(k) is True for k in VERIFICATIONS},
            provenance=r['sources']+review['sources'],
            action_ids=dict(own=own['occurrence_id'],opponent=opp['occurrence_id']))
        if 'execution_model' in review: observation['execution_model']=deepcopy(review['execution_model'])
        update=bank.update(observation);r['update']=update;r['quantitative_status']=update['status']
        r['numeric_reasons']=update.get('reasons',[])
        if update['status'] in ('updated','contradiction'):
            used_turns.add(r['turn_id']);r['inference_selected']=True
    posteriors=[]
    for belief in bank.beliefs.values():
        summary=belief.summary();weights={}
        for row in summary['configurations']:
            for kind in ('item','ability'):
                v=row['configuration'][kind];k=kind+':'+str(v)
                weights[k]=weights.get(k,0.)+row['probability']
        posteriors.append(dict(summary=summary,hypothesis_weights=weights,model=belief.model,history=belief.history))
    out['speed']=dict(profile=profile,posteriors=posteriors,
        eligible_updates=sum(r['quantitative_status']=='updated' for r in out['relations']),
        information_gain_nats=sum(b.summary()['information_gain_nats'] for b in bank.beliefs.values()),
        comparison_selection='one admitted pair per complete local turn across all individuals; remaining relations retained')
    priors=[];seen_forms=set()
    for a in actions.values():
        key=(a['instance_id'],a['identity'])
        if a['side']!='opponent' or not a['actor_identity_reliable'] or not a['identity'] or key in seen_forms:continue
        seen_forms.add(key)
        try:
            model=configuration_space(identity=a['identity'],form='as_named' if a['identity'].startswith('pokeapi:form:') else 'base')
            prior=SpeedBelief(model,battle_id=bid,instance_id=a['instance_id'],
                stat_epoch='conditional-observed-form:'+a['identity'],profile=profile).summary(include_configurations=False)
            priors.append(dict(instance_id=a['instance_id'],identity=a['identity'],summary=prior,
                status='prior_only_not_a_posterior_update',modifier_domains=model['modifier_domains'],
                model_fingerprint=model['fingerprint'],provenance=model['provenance']))
        except (ValueError,NotImplementedError) as exc:
            priors.append(dict(instance_id=a['instance_id'],identity=a['identity'],status='legal_support_unavailable',reason=str(exc)))
    out['speed']['legal_speed_priors']=priors
    out['counts']['known_configured_speed_actions']=sum(a['configured_speed'] is not None for a in actions.values())
    out['counts']['numeric_blockers']=dict(__import__('collections').Counter(x for r in out['relations'] for x in r.get('numeric_reasons',[])))
    return out
