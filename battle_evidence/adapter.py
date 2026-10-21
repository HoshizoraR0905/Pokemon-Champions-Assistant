"""Reconstructed evidence to existing M3.4.1; no likelihood implementation here."""
from copy import deepcopy
from speed_inference import BeliefBank,configuration_space
from speed_inference.likelihood import VERIFICATIONS
from speed_inference.domains import digest,encoded
from speed_order.core import identity_key
from .context import order_context


def compare_actions(first,second,turns,snapshots,builds,bank,*,profile='champions-evidence-only-v1'):
    reasons=[];a=turns.assignment[first['id']];b=turns.assignment[second['id']]
    local=(a.get('status')==b.get('status')=='confirmed_local_membership' and a.get('turn_id')==b.get('turn_id'))
    if not local and (a.get('number') is None or a.get('turn_id')!=b.get('turn_id')):reasons.append('same_confirmed_turn_missing')
    if local:reasons.append('absolute_turn_timing_unverified')
    if not a.get('decision_id') or a.get('decision_id')!=b.get('decision_id'):reasons.append('same_order_decision_missing')
    if not a.get('order_verified') or not b.get('order_verified') or a.get('execution_order')==b.get('execution_order'):reasons.append('execution_order_unverified')
    if a.get('order_verified') and b.get('order_verified') and a['execution_order']>=b['execution_order']:reasons.append('source_sequence_disagrees_with_verified_execution_order')
    if first.get('origin')!=second.get('origin'):reasons.append('mixed_synthetic_and_recorded_evidence')
    roles={e.get('side'):e for e in (first,second)}
    if set(roles)!={'self','opponent'}:reasons.append('opposite_sides_unverified')
    for e in (first,second):
        if not e.get('instance_id'):reasons.append('actor_instance_missing')
        if not e.get('move') or e.get('move_verified') is not True:reasons.append('executed_move_unverified')
        if type(e.get('priority')) is not int or e.get('priority_verified') is not True:reasons.append('priority_unverified')
    s=snapshots.get(first['id'],{}).get('before',{});annotation=s.get('annotation',{})
    if not (annotation.get('decision_context') or s.get('observable')) or annotation.get('decision_id')!=a.get('decision_id'):reasons.append('verified_order_decision_snapshot_missing')
    if annotation.get('continuity_verified') is not True:reasons.append('contemporaneous_modifier_continuity_unverified')
    if any(e['kind'] in ('effect','switch','forced_replacement','state_change') for e in turns.ledger
           if first['position']<e['position']<second['position']):reasons.append('intervening_change_needs_dedicated_order_model')
    own=roles.get('self',{});key=(first['battle_id'],own.get('instance_id'));build=builds.records.get(key)
    if not build or build['stats']['speed'] is None:reasons.append('known_own_unmodified_speed_missing')
    record=dict(action_ids=[first['id'],second['id']],status='ineligible',reasons=sorted(set(reasons)))
    if reasons:return record
    c=deepcopy(annotation['decision_context']) if annotation.get('decision_context') else order_context(s,own['instance_id'],roles['opponent']['instance_id'])
    c['own']['actual_speed']=build['stats']['speed']
    if c['own']['instance_id']!=own['instance_id'] or c['opponent']['instance_id']!=roles['opponent']['instance_id']:
        record['reasons']=['snapshot_individual_binding_mismatch'];return record
    try:own_identity=identity_key(c['own']['identity'],c['own']['form'])
    except (ValueError,TypeError,KeyError):
        record['reasons']=['own_current_form_unverified'];return record
    if own_identity!=build['canonical_identity']:
        record['reasons']=['own_current_form_does_not_match_verified_build'];return record
    c['actions']={role:dict(kind='move',move=e['move'],effective_priority=e['priority'],evidence=encoded(e['sources'])) for role,e in [('own',own),('opponent',roles['opponent'])]}
    c['timing']=dict(turn=a['number'],decision_id=a['decision_id'],state_at='order_decision',modifier_changes=[])
    # Context still passes all existing M3.4.1/native identity/hidden modifier gates.
    epoch=annotation.get('stat_epoch')
    if not isinstance(epoch,str) or not epoch:
        record['reasons']=['explicit_opponent_stat_epoch_missing'];return record
    o=dict(id='comparison:'+digest([first['battle_id'],first['id'],second['id'],s['id']]),battle_id=first['battle_id'],
        stat_epoch=epoch,evidence_kind='verified_action_order',origin=first['origin'],context=c,
        sequence=['own','opponent'] if own is first else ['opponent','own'],
        verification={k:annotation.get('verification',{}).get(k) is True for k in VERIFICATIONS},
        provenance=deepcopy(first['sources']+second['sources']+annotation['sources']),
        action_ids=dict(own=own.get('underlying_action_id',own['id']),opponent=roles['opponent'].get('underlying_action_id',roles['opponent']['id'])))
    bk=(first['battle_id'],roles['opponent']['instance_id'],epoch)
    if bk not in bank.beliefs:
        try:bank.register(configuration_space(identity=c['opponent']['identity'],form=c['opponent']['form']),
            battle_id=bk[0],instance_id=bk[1],stat_epoch=bk[2],profile=profile)
        except ValueError as exc:record['reasons']=[str(exc)];return record
    if bank.beliefs[bk].profile!=profile:
        record['reasons']=['belief_rule_profile_mismatch_requires_explicit_replay'];return record
    update=bank.update(o);record.update(status=update['status'],reasons=update.get('reasons',[]),observation=o,update=update)
    return record


def speed_audit(turns,snapshots,builds,*,profile='champions-evidence-only-v1'):
    bank=BeliefBank();actions=[e for e in turns.ledger if e['kind']=='action'];comparisons=[]
    for first,second in zip(actions,actions[1:]):
        if {first.get('side'),second.get('side')}=={'self','opponent'}:
            comparisons.append(compare_actions(first,second,turns,snapshots,builds,bank,profile=profile))
    return dict(comparisons=comparisons,eligible_updates=sum(c['status']=='updated' for c in comparisons),
        posteriors=[b.export() for b in bank.beliefs.values()],
        information_gain_nats=sum(b.summary()['information_gain_nats'] for b in bank.beliefs.values()))
