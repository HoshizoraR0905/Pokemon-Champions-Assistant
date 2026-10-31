"""Prospective, atomic HUD placement for two replacements after two faints only."""
from copy import deepcopy

POLICY = 'double_faint_hud_v1'


def vacant_pair(state, side):
    team=state.sides[side]
    if team.active_slots or set(team.vacant_slots)!={'left','right'}:return None
    episodes=[e for e in state.knowledge.get('active_entry_episodes',[]) if e['side']==side]
    old=[e for e in episodes if e.get('departure') or e.get('slot') is not None][-2:]
    if len(old)!=2:return None
    departures=[e.get('departure') or {} for e in old]
    if ({d.get('slot') for d in departures}!={'left','right'} or
            any(d.get('reason')!='faint' for d in departures)):return None
    first=min(d['timestamp'] for d in departures)
    if any(e['start']>=first for e in old):return None
    if any(o.get('kind')=='coverage_gap' and o.get('side') in {side,'field','unknown'}
            and o['end']>first for o in state.observations):return None
    return old


def retain_candidate(state,event):
    """A recognized arrival is evidence, never an admitted encounter/placement."""
    a=event.attributes;identity=(a.get('message_identity') or {}).get('identity')
    if (event.event_type!='send_out' or event.actor or event.side not in state.sides
            or a.get('identity_admission')!='recognized_candidate' or not identity
            or not identity.get('species_id') or not identity.get('canonical_id')
            or a.get('source_region_type')!='battle_message'):return False
    old=vacant_pair(state,event.side)
    if not old or a['observation_time']<=max(e['departure']['timestamp'] for e in old):return False
    candidates=state.knowledge.setdefault('double_faint_candidates',[])
    if not any(c['entry_event_id']==event.event_id for c in candidates):
        candidates.append(dict(candidate_only=True,status='pending',identity=deepcopy(identity),
            side=event.side,species_id=identity['species_id'],start=a['observation_time'],
            start_kind='send_out',entry_event_id=event.event_id,episode_id='candidate:'+event.event_id,
            faint_event_ids=[e['departure']['event_id'] for e in old],event=event.to_dict()))
    return True


def pending_pair(state, side):
    old=vacant_pair(state,side)
    if not old:return None
    last=max(e['departure']['timestamp'] for e in old)
    entries=[e for e in state.knowledge.get('active_entry_episodes',[]) if e['side']==side
        and not e.get('departure') and e['start_kind']=='send_out' and e['start']>last
        and state.pokemon[e['instance_id']].species.known
        and state.pokemon[e['instance_id']].location.value==dict(kind='unplaced_entry',slot=None)]
    admitted_ids={e['entry_event_id'] for e in entries}
    entries+= [c for c in state.knowledge.get('double_faint_candidates',[]) if c['side']==side
        and c['status']=='pending' and c['start']>last and c['entry_event_id'] not in admitted_ids
        and c['faint_event_ids']==[e['departure']['event_id'] for e in old]]
    if len(entries)!=2:return None
    pending={p.pokemon_instance_id for p in state.pokemon.values() if p.side_id==side
        and p.location.value==dict(kind='unplaced_entry',slot=None)}
    if pending!={e['instance_id'] for e in entries if not e.get('candidate_only')}:return None
    return entries


def independent_candidate_support(reading, ref):
    """A deferred arrival needs actual agreeing text and icon observations."""
    icon=reading.get('icon') or {};species=reading.get('species') or {}
    independent=(species.get('resolution') or {}).get('independent_text') or species.get('resolution') or {}
    return bool(ref and icon.get('status')=='resolved' and icon.get('species_id')==ref['species_id']
        and independent.get('status')=='resolved' and independent.get('species_id')==ref['species_id'])


def verify(engine, state, event, record):
    """No partial placement, temporal backfill, identity mutation or roster hints."""
    from .evidence_fusion import identity_evidence
    from .state_engine import evidence_link
    from .active_continuity import placed
    pair = pending_pair(state, event.side)
    proof = event.attributes.get('double_faint_hud') or {}
    t = event.attributes['observation_time']
    if (not pair or proof.get('policy') != POLICY or proof.get('timestamp') != t
            or proof.get('source_id') not in {e.source_id for e in event.evidence}
            or t <= max(e['start'] for e in pair)):
        return False
    reads = proof.get('slots', {})
    if set(reads) != {'left', 'right'}:
        return False
    mapping = {}
    for slot, reading in reads.items():
        if reading.get('identity_reused_from') or not reading.get('independent'):
            return False
        ref, status, _ = identity_evidence(reading.get('species'), reading.get('icon'))
        if status != 'accepted':
            return False
        matches = []
        for ep in pair:
            identity = ep['identity'] if ep.get('candidate_only') else state.pokemon[ep['instance_id']].species.value
            if identity.get('species_id') != ref['species_id']:
                continue
            # Keep form-specific message identities; species-only HUD cannot verify them.
            variant = identity.get('canonical_identity')
            if variant and variant != ref.get('canonical_identity'):
                continue
            if ep.get('candidate_only'):
                # A deferred message requires both genuinely available sources.
                if not independent_candidate_support(reading,ref):continue
            matches.append((ep,ref))
        if len(matches) != 1:
            return False
        mapping[slot] = matches[0]
    if len({ep['entry_event_id'] for ep,ref in mapping.values()}) != 2:
        return False
    # Validate the entire bijection before admitting either deferred candidate.
    # Existing canonical instance allocation preserves the source event ID and
    # historical-continuity policy. Admission is prospective at this HUD frame.
    from .state_engine import event_from_dict,EventRecord
    from .active_continuity import enter
    admitted={}
    for slot,(ep,ref) in mapping.items():
        if ep.get('candidate_only'):
            arrival=event_from_dict(ep['event']);confirmed=deepcopy(arrival)
            confirmed.actor=deepcopy(ref);confirmed.attributes['observation_time']=t
            confirmed.evidence+=deepcopy(event.evidence)
            child=EventRecord(confirmed.to_dict(),record.delivery_index,record.ordering)
            p=engine._resolve(state,confirmed,child,sending=True)
            engine._assign(p,'location',dict(kind='unplaced_entry',slot=None),event)
            engine._assign(p,'fainted',False,event)
            episode=enter(state,p,arrival,child)
            episode.update(species_known_at_entry=False,species_resolution_time=t,
                identity_admitted_at=t,identity_confirmation=evidence_link(event))
            for c in state.knowledge.get('double_faint_candidates',[]):
                if c['entry_event_id']==ep['entry_event_id']:
                    c.update(status='hud_confirmed',instance_id=p.pokemon_instance_id,confirmed_at=t)
            record.bindings.setdefault('double_faint_identity_admissions',[]).append(dict(
                entry_event_id=arrival.event_id,instance_id=p.pokemon_instance_id,admitted_at=t,
                evidence=evidence_link(event),candidate_evidence=deepcopy(ep['event']['evidence'])))
        else:p=state.pokemon[ep['instance_id']]
        admitted[slot]=p
    mapping=admitted
    audit = dict(policy=POLICY, timestamp=t, evidence=evidence_link(event),
                 hud=deepcopy(proof), mapping={s:p.pokemon_instance_id for s,p in mapping.items()},
                 entry_event_ids=[e['entry_event_id'] for e in pair])
    for slot, p in mapping.items():
        state.sides[event.side].active_slots[slot] = p.pokemon_instance_id
        state.sides[event.side].vacant_slots.remove(slot)
        engine._assign(p, 'location', dict(kind='active', slot=slot), event)
        ep = placed(state, p, event, record, slot)
        ep['double_faint_verification'] = deepcopy(audit)
    state.observations.append(dict(kind=POLICY, **audit))
    record.bindings[POLICY] = audit
    return True
