"""Read-only executed-action reconstruction over explicitly selected v2.2 evidence.

Source messages establish recognized execution announcements, not complete action
coverage. Current saved state and a verified queue snapshot are separate objects.
"""
from collections import Counter
from copy import deepcopy
from itertools import combinations
import re
from speed_inference.domains import digest
from speed_order.core import identity_key, knowledge, name
from .context import canonical, value
from .order_mechanics import priority_support, compare_priority

VERSION = 'real-executed-actions-v1'
NON_ACTIONS = {
    'switch_out': 'switching', 'send_out': 'sendout_or_forced_replacement',
    'transformation': 'transformation', 'ability_activation': 'ability_activation',
    'item_activation': 'item_activation', 'item_change': 'item_change',
    'weather_change': 'weather', 'terrain_change': 'terrain',
    'side_condition_change': 'side_condition', 'trick_room_change': 'trick_room',
    'stat_change': 'stat_change', 'status_change': 'status_change',
    'hp_change': 'hp_change_unattributed', 'faint': 'faint',
}


def action_priority(move, identity, ability, species):
    if identity or ability:
        result = priority_support(move, identity=identity, ability=ability)
    else:
        # Species-only identity does not select a base form. Union forms present
        # in the pinned Champions catalog (not unrelated PokéAPI Gmax forms).
        kb = knowledge(); entity = kb.entities.get(species)
        keys = [k for k,e in kb.entities.items() if e.kind == 'species' and entity and e.species_id == entity.species_id and k in kb.facts['pokemon']]
        parts = [priority_support(move, identity=k) for k in keys]
        result = priority_support(move)
        if parts and all(p['effective_priorities'] for p in parts):
            result.update(effective_priorities=sorted({v for p in parts for v in p['effective_priorities']}),
                hypotheses=[dict(form=k, **h) for k,p in zip(keys,parts) for h in p['hypotheses']],
                reasons=sorted({r for p in parts for r in p['reasons']}))
            result['status'] = 'supported' if len(result['effective_priorities'])==1 and not result['reasons'] else 'hypothesis_dependent'
            if any(p['status']=='special_action' for p in parts): result['status']='special_action'
        result['form_scope']='union of applicable pinned Champions catalog forms; unmodeled transformed/transferred abilities remain a numeric blocker'
    # Suppression remains possible without activation evidence. Native priority
    # changes therefore retain the base bracket, even in monotypic domains.
    if result.get('hypotheses') and result.get('base_priority') is not None:
        result['effective_priorities'] = sorted(set(result['effective_priorities']+[result['base_priority']]))
        if len(result['effective_priorities'])>1: result['status']='hypothesis_dependent'
    return result


def category(event):
    typ = event.get('source_event_type')
    if typ == 'move_execution':
        # Only the parser's live execution grammar, never menu/log selections.
        live = any(s.get('source_type') == 'video_message' for s in event.get('sources', []))
        text = re.sub(r'\s+', '', event.get('text') or '')
        return 'executed_move_announcement' if live and re.fullmatch(r'.+使出了.+[！!。.]', text) else 'unverified_move_announcement'
    if typ in NON_ACTIONS: return NON_ACTIONS[typ]
    text = event.get('text') or ''
    if any(s in text for s in ('畏缩', '无法动弹', '正在睡觉', '不能动', '动弹不得')):
        return 'prevented_action'
    if any(s in text for s in ('回复了', '恢复了', '受到了伤害')):
        return 'recovery_or_residual_unattributed'
    return 'other_' + str(typ or event.get('kind'))


def reconstruct(payload, snapshots, *, source_events=None, reviews=None):
    """No default promotion of OCR confidence to human/mechanical verification."""
    if payload.get('schema') != 'normal-screen-three-hud-v2.2':
        raise ValueError('Explicit frozen v2.2 input required')
    bid = payload['battle_id']; reconstruction = payload['reconstruction']
    events = reconstruction['ledger']; assignments = reconstruction['assignment']
    source_events = source_events or {}; reviews = reviews or {}
    if set(reviews) - {e['id'] for e in events}: raise ValueError('Unknown reviewed source ID')
    segments = {s['id']: s for s in payload['visual']['segments']}
    actions = []; non_actions = []; duplicates = []; seen = {}; order_observations=[]
    for e in sorted(events, key=lambda e: (e.get('timestamp') is None, e.get('timestamp') or 0, e['position'])):
        if e['battle_id'] != bid: raise ValueError('Cross-battle source')
        cat = category(e)
        if e.get('source_retracted') or e.get('source_revision_requires_review') or e['kind'] == 'inactive_source_observation':
            non_actions.append(dict(event_id=e['id'], category='retracted_or_revised', sources=e.get('sources', []))); continue
        if cat != 'executed_move_announcement':
            raw=source_events.get(e['id'],{})
            non_actions.append(dict(event_id=e['id'], timestamp=e.get('timestamp'), category=cat,
                instance_id=e.get('instance_id'),sources=e.get('sources', []), text=e.get('text'),
                canonical_references=deepcopy(raw.get('canonical_references',{}))))
            for kind in ('item','ability'):
                reference=(raw.get('canonical_references',{}).get(kind) or {}).get('canonical_id')
                if reference:
                    try: label=name(reference,kind)
                    except ValueError:continue
                    if label in {'Quick Claw','Custap Berry','Lagging Tail','Full Incense','Stall','Quick Draw','Mycelium Might','Prankster','Choice Scarf'}:
                        order_observations.append(dict(event_id=e['id'],timestamp=e.get('timestamp'),
                            instance_id=e.get('instance_id'),kind=kind,identity=reference,name=label,
                            interpretation='recognized_explicit_activation' if cat==kind+'_activation' else 'revealed_or_mentioned; activation_unknown',
                            source_status=e.get('source_status'),sources=deepcopy(e.get('sources',[]))))
            continue
        occurrence = e.get('underlying_action_id', e['id'])
        if occurrence in seen:
            duplicates.append(dict(event_id=e['id'], duplicate_of=seen[occurrence], occurrence_id=occurrence)); continue
        seen[occurrence] = e['id']
        review = reviews.get(e['id'], {})
        if review and (review.get('verified') is not True or not review.get('sources')):
            raise ValueError('Review requires verified provenance')
        before = deepcopy(snapshots.get(e['id'], {}).get('before', {}))
        state = before.get('observable', {}); mon = state.get('pokemon', {}).get(e.get('instance_id'), {})
        raw = source_events.get(e['id'], {}); assignment = deepcopy(assignments.get(e['id'], {}))
        identity = value(mon.get('form'))
        current_form_verified = bool(identity)
        if identity:
            try: identity = identity_key(identity, 'as_named')
            except ValueError: identity = None; current_form_verified = False
        ability = canonical(mon.get('ability'))
        move_resolution = raw.get('attributes', {}).get('move_resolution', {})
        move_reliable = bool(e.get('move') and (e.get('move_verified') or
            (move_resolution.get('status') == 'confirmed' and move_resolution.get('canonical_id') == e['move'])))
        actor_reliable = bool(e.get('instance_id') and e.get('side') in ('self', 'opponent') and
                              e.get('binding', {}).get('pokemon_instance_id') == e['instance_id'] and
                              not any('conflict' in u for u in e.get('uncertainty', [])))
        pr = action_priority(e.get('move'), identity, ability, canonical(mon.get('identity')) or (raw.get('actor') or {}).get('canonical_id'))
        # Native alternatives assume no transferred/suppressed priority abilities.
        pr['scope'] = 'conditional native current-form ability domain; suppression/transfer unresolved'
        action = dict(id='action:' + digest([bid, occurrence]), event_id=e['id'], occurrence_id=occurrence,
            battle_id=bid, origin=e.get('origin','recorded'), timestamp=e.get('timestamp'), side=e.get('side'), instance_id=e.get('instance_id'),
            active_slot=(value(mon.get('location')) or {}).get('slot'), identity=identity,
            observed_species=canonical(mon.get('identity')) or (raw.get('actor') or {}).get('canonical_id'), current_form_verified=current_form_verified,
            move=e.get('move'), move_identity_reliable=move_reliable, actor_identity_reliable=actor_reliable,
            category=cat, outcome='not_established_by_announcement', priority=pr, membership=assignment,
            turn_id=assignment.get('turn_id'), local_index=assignment.get('local_segment_index'),
            source_position=e['position'], sources=deepcopy(e['sources']), text=e.get('text'),
            confidence=dict(source_status=e.get('source_status'), uncertainty=e.get('uncertainty', []),
                            interpretation='recognized live parser execution announcement, not curated ground truth'),
            current_state_before=before, order_decision_snapshot=deepcopy(review.get('order_decision_snapshot')),
            review=deepcopy(review), unknowns=[])
        if not actor_reliable: action['unknowns'].append('actor_individual_unreliable')
        if not move_reliable: action['unknowns'].append('move_identity_unreliable')
        if not current_form_verified: action['unknowns'].append('current_form_unresolved')
        if not action['order_decision_snapshot']: action['unknowns'].append('order_decision_state_unverified')
        if assignment.get('turn_id') not in segments: action['unknowns'].append('local_turn_membership_unresolved')
        actions.append(action)
    groups = []; relations = []
    for sid, segment in segments.items():
        seq = [a for a in actions if a['turn_id'] == sid]
        for i, a in enumerate(seq, 1): a['resolution_position'] = i
        group = dict(id='order-group:' + digest([bid, sid, [a['id'] for a in seq]]), turn_id=sid,
            local_index=segment['local_index'], membership_status=segment['status'],
            action_ids=[a['id'] for a in seq], partial=True,
            completeness='Missing or prevented actions are not invented', same_priority_groups=[])
        brackets = {}
        for a in seq:
            if a['priority']['status'] == 'supported':
                brackets.setdefault(a['priority']['effective_priorities'][0], []).append(a['id'])
        group['same_priority_groups'] = [dict(priority=k, action_ids=v) for k,v in brackets.items() if len(v)>1]
        for a,b in combinations(seq,2):
            status = compare_priority(a,b); reasons=[]
            if not a['actor_identity_reliable'] or not b['actor_identity_reliable']: reasons.append('actor_identity_unreliable')
            if not a['move_identity_reliable'] or not b['move_identity_reliable']: reasons.append('move_identity_unreliable')
            if a['instance_id'] == b['instance_id']: reasons.append('same_individual_repeated_action_needs_handler')
            if a['timestamp'] is None or b['timestamp'] is None or a['timestamp'] >= b['timestamp']: reasons.append('chronology_ambiguous')
            if segment['status'] != 'confirmed': reasons.append('incomplete_local_membership')
            changes = [e['id'] for e in events if a['source_position'] < e['position'] < b['source_position']
                       and e.get('source_event_type') in NON_ACTIONS]
            if changes: reasons.append('intervening_state_or_special_action_requires_queue_context')
            if not a['order_decision_snapshot'] or not b['order_decision_snapshot']: reasons.append('modifier_and_queue_snapshot_unverified')
            if status != 'same_supported_priority': reasons.append(status)
            relations.append(dict(id='order-relation:' + digest([bid,sid,a['id'],b['id']]), turn_id=sid,
                action_ids=[a['id'],b['id']], event_ids=[a['event_id'],b['event_id']],
                instance_ids=[a['instance_id'],b['instance_id']], observed_relation='announced_before',
                conditional_speed_relation='effective_speed_first >= effective_speed_second (ties possible); reverse under Trick Room' if status=='same_supported_priority' else None,
                priority_status=status, intervening_event_ids=changes, reasons=sorted(set(reasons)),
                status='retained_symbolic' if status=='same_supported_priority' else 'excluded_from_speed',
                quantitative_status='deferred', sources=a['sources']+b['sources'],
                dependence_group=group['id'], inference_selected=False))
        groups.append(group)
    counts=dict(local_turns=len(segments), recognized_executed_actions=len(actions),
        reliable_actor_actions=sum(a['actor_identity_reliable'] for a in actions),
        reliable_move_actions=sum(a['move_identity_reliable'] for a in actions),
        supported_priority_actions=sum(a['priority']['status']=='supported' for a in actions),
        same_priority_groups=sum(len(g['same_priority_groups']) for g in groups),
        reliable_order_modifier_groups=sum(bool(g['action_ids']) and all(not r['reasons'] for r in relations if r['turn_id']==g['turn_id']) and any(r['turn_id']==g['turn_id'] for r in relations) for g in groups),
        symbolic_relations=sum(r['status']=='retained_symbolic' for r in relations),
        excluded_relations=sum(r['status']=='excluded_from_speed' for r in relations),
        duplicate_announcements=len(duplicates),direct_order_item_ability_observations=len(order_observations),
        categories=dict(Counter(e['category'] for e in non_actions)))
    return dict(version=VERSION,battle_id=bid,visual_version=payload['schema'],actions=actions,groups=groups,
        relations=relations,non_actions=non_actions,order_observations=order_observations,duplicates=duplicates,counts=counts,
        evidence_policy='All pairwise relations retained; at most ONE pair per whole local turn is selected for numeric likelihood. No transitive/duplicate likelihood multiplication.')
