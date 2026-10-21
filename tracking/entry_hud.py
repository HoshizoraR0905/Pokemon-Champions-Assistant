"""Episode-local, causal HUD confirmation. No recognition or scene inference.

Thirty seconds bounds entry association (the existing named-message support
horizon); three seconds bounds corroboration across nearby independent frames.
After expiry a fresh pair requires independently supported current continuity
and is labelled prospective, never timely entry identification.
"""
import math
from copy import deepcopy
from battle_events.aliases import alias_key

POLICY = 'entry-hud-v2'
ENTRY_WINDOW_SECONDS = 30
CONFIRM_SECONDS = 3


def message_reference(episode):
    """The complete message reference is immutable, including apparent titles."""
    return episode.get('display_reference') or episode.get('entry_display_reference') or ''


def display_name(episode):
    return (episode.get('hud_display_name') or {}).get('value') or message_reference(episode)


def name_relation(state, episode, raw, event):
    """A suffix is only a candidate relation anchored by independent entry proof.

    Two fresh, agreeing HUD frames must still confirm this candidate. No title
    vocabulary or substring such as 的 is interpreted here.
    """
    from .evidence_fusion import context_supported
    a=event.attributes;side=event.side;slot=a.get('slot');t=a['observation_time']
    p=state.pokemon.get(episode['instance_id'])
    if (not raw or not p or episode.get('departure') or episode.get('slot')!=slot
            or state.sides[side].active_slots.get(slot)!=episode['instance_id']
            or p.location.value!=dict(kind='active',slot=slot)
            or not context_supported(state,side,slot,t) or t<=episode['start']):return None
    established=episode.get('hud_display_name')
    if established and alias_key(raw)!=alias_key(established['value']):return None
    reference=message_reference(episode);key=alias_key(raw);reference_key=alias_key(reference)
    if reference_key==key:
        return dict(kind='exact',message_reference=reference,hud_display_name=raw,possible_title_segment=None,
                    basis='same_active_episode_and_literal_name')
    if not reference_key.endswith(key) or not key:return None
    evidence=episode['entry_evidence']
    if (episode.get('start_kind')!='send_out' or (evidence.get('ocr_confidence') or 0)<.95
            or not any(source.get('source_type')=='video_message' and source.get('observation_ids')
                       and source.get('details',{}).get('timestamp')==episode['start']
                       for source in evidence.get('sources',[]))
            or not any(x.get('slot')==slot and episode['start']<=x.get('timestamp',-1)<=t
                       for x in episode.get('placements',[]))):return None
    competing=[ep for ep in state.knowledge.get('active_entry_episodes',[]) if ep['side']==side
               and ep.get('departure') is None and ep['instance_id']!=episode['instance_id']
               and ep['instance_id'] in state.sides[side].active_slots.values()
               and alias_key(message_reference(ep)).endswith(key)]
    if competing:return None
    boundary=next((i for i in range(len(reference)) if alias_key(reference[i:])==key),None)
    if boundary is None:return None
    return dict(kind='possible_title_prefix',message_reference=reference,hud_display_name=raw,
                possible_title_segment=reference[:boundary],
                basis='supported_sendout_slot_continuity_and_independent_hud_pair_required')


def observe(state, event):
    if state.knowledge.get('message_identity_v1'):return
    from .active_continuity import enabled, current_episode
    from .state_engine import evidence_link
    a=event.attributes;t=a.get('observation_time')
    if not enabled(state) or type(t) not in (int,float) or not math.isfinite(t):return
    if a.get('battle_id',state.battle_id)!=state.battle_id:return
    for ep in state.knowledge.get('active_entry_episodes',[]):
        audit=ep.get('hud_binding')
        if audit and not ep.get('departure'):
            deadline=min(ep['start']+ENTRY_WINDOW_SECONDS,
                         audit['first_eligible_time']+CONFIRM_SECONDS if audit.get('first_eligible_time') is not None else float('inf'))
            if t>deadline and audit['status']=='pending':
                audit.update(status='expired',expired_at=deadline,reason='entry_or_confirmation_window_expired')
    if event.event_type!='hud_observation' or event.side not in state.sides:return
    pid=state.sides[event.side].active_slots.get(a.get('slot'));ep=current_episode(state,pid)
    if not ep or not ep.get('hud_binding') or ep['hud_binding']['status'] in {'resolved','resolved_prospectively','resolved_via_auxiliary','known_identity_verified'} or t<=ep['start']:return
    audit=ep.setdefault('hud_binding',dict(policy=POLICY,status='pending',
        entry_deadline=ep['start']+ENTRY_WINDOW_SECONDS,confirmation_seconds=CONFIRM_SECONDS,
        first_candidate_time=t,first_eligible_time=None,candidates=[]))
    if audit['first_candidate_time'] is None:audit['first_candidate_time']=t
    species=a.get('species') or {};icon=a.get('icon') or {};sid=icon.get('species_id')
    reasons=[]
    if a.get('source_region_type') not in (None,'battle_hud') or not any(s.source_type=='video_hud' and s.details.get('timestamp')==t for s in event.evidence):reasons.append('not_genuine_battle_hud')
    if a.get('identity_reused_from'):reasons.append('reused_identity')
    relation=name_relation(state,ep,species.get('raw_text') or '',event)
    if relation is None:reasons.append('episode_name_unassociated')
    if ep.get('species_known_at_entry') and sid and sid!=ep['species_id']:reasons.append('message_hud_species_conflict')
    if species.get('confidence',0)<.95:reasons.append('name_unreliable')
    resolution=species.get('resolution') or {}
    if (icon.get('status')!='resolved' or not sid or not icon.get('candidates')
            or icon['candidates'][0].get('species_id')!=sid or resolution.get('species_id')!=sid):reasons.append('independent_icon_unresolved_or_conflicting')
    roster=state.knowledge.get('identity_ledger',{}).get('roster',[])
    rows={}
    for r in roster:
        if r['side']==event.side:rows.setdefault(r['preview_row'],[]).append(r)
    reliable=set(rows)==set(range(1,7)) and all(all(r.get('status')=='resolved' and r.get('species_id') for r in rs) and len({r['species_id'] for r in rs})==1 for rs in rows.values())
    if reliable and sid and sid not in {r['species_id'] for rs in rows.values() for r in rs}:reasons.append('outside_reliable_preview')
    frames=tuple(oid for s in event.evidence for oid in s.observation_ids)
    if not frames:reasons.append('missing_source_frame')
    candidate=dict(event_id=event.event_id,timestamp=t,frames=list(frames),raw=species.get('raw_text'),
        species_id=sid,ocr_confidence=species.get('confidence'),name_relation=relation,
        eligible=not reasons,reasons=reasons,evidence=evidence_link(event))
    if any(c['event_id']==event.event_id for c in audit['candidates']):return
    audit['candidates'].append(candidate)
    if not reasons and audit['first_eligible_time'] is None:
        audit['first_eligible_time']=t;audit['first_eligible_evidence']=deepcopy(candidate)
    if t>audit['entry_deadline'] and audit['status']=='pending':
        audit.update(status='expired',expired_at=audit['entry_deadline'],reason='entry_window_expired')


def support(state,event):
    from .active_continuity import current_episode
    from .evidence_fusion import knowledge, context_supported
    a=event.attributes;t=a['observation_time'];pid=state.sides[event.side].active_slots.get(a['slot']);ep=current_episode(state,pid)
    if not ep or not message_reference(ep):return None
    audit=ep.get('hud_binding',{});candidates=audit.get('candidates',[])
    now=next((c for c in reversed(candidates) if c['event_id']==event.event_id),None)
    if not now or not now['eligible']:return None
    timely=audit['status']=='pending' and t<=audit['entry_deadline']
    if not timely and not context_supported(state,event.side,a['slot'],t):return None
    # A contradictory icon breaks corroboration; inconclusive candidates stay
    # in the audit but contribute no proof. Repeated
    # recognition of identical source pixels cannot supply a second proof.
    nearby=[]
    for c in reversed(candidates):
        if t-c['timestamp']>CONFIRM_SECONDS:break
        if c['species_id'] and c['species_id']!=now['species_id']:break
        if c['eligible'] and alias_key(c['raw'])!=alias_key(now['raw']):break
        if c['eligible']:nearby.append(c)
    if not any(set(c['frames']).isdisjoint(now['frames']) for c in nearby):return None
    if timely and any(c['species_id']!=now['species_id'] or alias_key(c['raw'])!=alias_key(now['raw']) for c in candidates if c['eligible']):return None
    entity=knowledge().entities.get(f"pokeapi:species:{now['species_id']}")
    if entity is None:return None
    first=min(nearby,key=lambda c:c['timestamp'])
    known=state.pokemon[pid].species.known
    audit.update(status='known_identity_verified' if known else 'resolved' if timely else 'resolved_prospectively',resolved_at=t,
                 timely_entry_identification=timely,corroborating_observation=deepcopy(now),identity_source=deepcopy(first))
    if not ep.get('hud_display_name'):
        ep['hud_display_name']=dict(value=first['raw'],message_reference=message_reference(ep),
            possible_title_segment=first['name_relation']['possible_title_segment'],
            relation=first['name_relation']['kind'],observation_time=first['timestamp'],established_at=t,
            evidence=[ep['entry_evidence'],*[c['evidence'] for c in nearby]],
            ocr_confidences=[c['ocr_confidence'] for c in nearby],
            confidence_semantics='OCR scores, not identity probabilities',source='in_battle_hud')
    identity=(deepcopy(state.pokemon[pid].species.value) if known else
        dict(canonical_id=entity.canonical_id,species_id=now['species_id'],kind='species',
             name=entity.names.get('zh-hans'),knowledge_snapshot=knowledge().snapshot_id,identity_status='species_only'))
    return dict(identity=identity,raw_nickname=ep['hud_display_name']['value'],
        message_reference=message_reference(ep),display_name_relation=deepcopy(ep['hud_display_name']),
        entry_event_id=ep['entry_event_id'],prospective_only=True,
        timely_entry_identification=timely,established_at=t,historical_entry_applied=False,
        evidence=[ep['entry_evidence'],*[c['evidence'] for c in nearby]],policy='episode_first_hud_bounded_v2')


def known_support(state,event):
    """A resolved current episode needs verification, not a new entry search."""
    from .active_continuity import current_episode
    from .evidence_fusion import context_supported
    from .state_engine import evidence_link
    a=event.attributes;pid=state.sides[event.side].active_slots.get(a.get('slot'))
    ep=current_episode(state,pid);p=state.pokemon.get(pid)
    if not ep or not message_reference(ep) or not p or not p.species.known:return None
    species=a.get('species') or {};icon=a.get('icon') or {};resolution=species.get('resolution') or {}
    sid=p.species.value['species_id'];t=a['observation_time']
    prior=p.species.value.get('canonical_identity');variant=icon.get('canonical_identity')
    if prior and variant and prior!=variant:return None
    if not ep.get('hud_display_name'):
        confirmed=support(state,event)
        if confirmed:return confirmed
    if (a.get('identity_reused_from') or not context_supported(state,event.side,a['slot'],t)
            or alias_key(species.get('raw_text') or '')!=alias_key(display_name(ep))
            or species.get('confidence',0)<.95 or icon.get('status')!='resolved'
            or icon.get('species_id')!=sid or resolution.get('species_id')!=sid
            or not icon.get('candidates') or icon['candidates'][0].get('species_id')!=sid
            or a.get('source_region_type') not in (None,'battle_hud')
            or not any(s.source_type=='video_hud' and s.observation_ids and s.details.get('timestamp')==t for s in event.evidence)):
        return None
    return dict(identity=deepcopy(p.species.value),raw_nickname=display_name(ep),
        entry_event_id=ep['entry_event_id'],prospective_only=True,established_at=t,
        historical_entry_applied=False,evidence=[*deepcopy(p.species.provenance),evidence_link(event)],
        policy='current_episode_independent_hud_v1')
