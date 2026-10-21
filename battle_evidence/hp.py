"""Exact observations and causal hypotheses are separate from damage eligibility."""
from copy import deepcopy

REQUIRED=('attacker_identity','move_identity','receiver_identity','targeting','resolution_state','single_cause','coverage','no_redirection','single_hit')


def attribute_hp(before,after,causes,*,coverage=None):
    """Inputs are verified readings, not interpolated HUD bars or percentages."""
    reasons=[]
    for label,p in [('before',before),('after',after)]:
        if p.get('verified') is not True:reasons.append(label+'_reading_not_verified')
        if type(p.get('current')) is not int or p['current']<0:reasons.append(label+'_exact_integer_hp_missing')
        if type(p.get('maximum')) is not int or p['maximum']<1:reasons.append(label+'_max_hp_missing')
        if type(p.get('current')) is int and type(p.get('maximum')) is int and p['current']>p['maximum']:reasons.append(label+'_hp_exceeds_maximum')
        if not p.get('sources'):reasons.append(label+'_provenance_missing')
    if not before.get('instance_id') or before.get('instance_id')!=after.get('instance_id'):reasons.append('individual_identity_unresolved_or_changed')
    if not before.get('battle_id') or before.get('battle_id')!=after.get('battle_id'):reasons.append('cross_battle_readings')
    if before.get('maximum')!=after.get('maximum'):reasons.append('max_hp_changed')
    if not before.get('epoch') or before.get('epoch')!=after.get('epoch'):reasons.append('form_or_identity_continuity_gap')
    if before.get('position',-1)>=after.get('position',-1):reasons.append('reading_order_not_established')
    if not coverage or coverage.get('complete') is not True or not coverage.get('sources'):reasons.append('intervening_hp_cause_coverage_unverified')
    exact=all(type(p.get('current')) is int for p in (before,after))
    delta=after['current']-before['current'] if exact else None
    if len(causes)!=1:reasons.append('multiple_candidate_causes' if causes else 'cause_unknown')
    cause=causes[0] if len(causes)==1 else {};kind=cause.get('kind','unknown')
    if cause.get('verified') is not True or not cause.get('sources'):reasons.append('cause_not_verified')
    for field in REQUIRED:
        if kind=='attack' and cause.get('verification',{}).get(field) is not True:reasons.append(field+'_unverified')
    if cause and cause.get('receiver')!=after.get('instance_id'):reasons.append('cause_receiver_unverified')
    if cause and (not cause.get('event_id') or type(cause.get('position')) not in (int,float) or not before.get('position',0)<cause['position']<after.get('position',0)):
        reasons.append('cause_resolution_not_established_between_readings')
    if kind=='attack':
        from speed_order.core import knowledge,name
        from knowledge import normalize
        try:
            canonical_name=name(cause.get('move'),'move');kb=knowledge()
            rows={r.canonical_id:r for r in kb.exact['move'].get(normalize(canonical_name),[]) if r.kind=='move'}
            category=kb.facts['moves'][next(iter(rows))]['category'] if len(rows)==1 else None
            if category not in ('Physical','Special'):reasons.append('move_not_cataloged_as_damaging_attack')
        except (ValueError,KeyError,TypeError):reasons.append('damaging_move_identity_unresolved')
        if not cause.get('attacker') or not cause.get('move') or cause.get('receiver')!=after.get('instance_id'):reasons.append('attack_actor_move_or_receiver_missing')
        if not cause.get('resolution_snapshot_id'):reasons.append('resolution_snapshot_missing')
        if after.get('instance_id') not in cause.get('target_instances',[]):reasons.append('receiving_target_not_established')
        if cause.get('substitute') is True:reasons.append('substitute_hp_is_not_recipient_hp_damage')
        if cause.get('spread') is True and not cause.get('per_target_resolution'):reasons.append('spread_target_resolution_missing')
        if cause.get('multi_hit') is True:reasons.append('multi_hit_not_single_damage_measurement')
        if delta is None or delta>=0:reasons.append('not_positive_hp_loss')
        if after.get('current')==0 and not cause.get('uncensored_damage_verified'):reasons.append('fainting_hp_loss_censors_actual_damage')
    if kind not in ('attack','residual','healing','recoil','self_damage'):reasons.append('unsupported_cause')
    if kind=='healing' and (delta is None or delta<=0):reasons.append('healing_direction_conflict')
    if kind in ('residual','recoil','self_damage') and (delta is None or delta>=0):reasons.append('loss_direction_conflict')
    reasons=sorted(set(reasons));eligible=kind=='attack' and not reasons
    return dict(instance_id=after.get('instance_id'),battle_id=after.get('battle_id'),before=deepcopy(before),after=deepcopy(after),
        raw_delta=delta,classification=kind if not reasons else 'multiple_causes' if len(causes)>1 else 'unknown',
        candidate_causes=deepcopy(causes),coverage=deepcopy(coverage),cause_confirmed=not reasons,
        damage_inference_eligible=eligible,exact_damage=-delta if eligible else None,reasons=reasons)
