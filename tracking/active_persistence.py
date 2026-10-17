"""Prospective occupancy uncertainty, independent of HUD acquisition quality.

The authoritative slots/episodes remain in BattleState. This ledger only gates
use of those episodes after reliable contradictory evidence; missing/weak HUDs
neither erase occupancy nor erase an outstanding contradiction.
"""
from copy import deepcopy


def observe_hud(state, event, observed):
    from knowledge import normalize
    from .evidence_fusion import knowledge
    from .active_continuity import current_episode
    key = event.side + ':' + event.attributes['slot']
    pid = state.sides[event.side].active_slots.get(event.attributes['slot'])
    mon = state.pokemon.get(pid)
    episode = current_episode(state, pid)
    ledger = state.knowledge.setdefault('occupancy_uncertainty', {})
    if observed['status'] == 'accepted':
        # Admission either corroborates this episode or observes a new occupant.
        ledger.pop(key, None)
        return
    if not mon or not episode:
        return
    names = knowledge().exact['species'].get(normalize(observed.get('raw') or ''), [])
    ids = {e.species_id for e in names}
    # A failed resolver alone is not contradictory evidence. A confident exact
    # canonical label for a different species is; high-confidence source
    # disagreement also remains unresolved rather than selecting either source.
    strong_text = observed.get('confidence', 0) >= .95 and len(ids) == 1
    contradicts = ids != {mon.species.value.get('species_id')}
    if strong_text and (contradicts or observed['status'] == 'conflicting'):
        ledger[key] = dict(deepcopy(observed), status='conflicting',
                           reason='reliable_hud_identity_contradiction',
                           instance_id=pid, episode_id=episode['episode_id'])


def occupancy_gate(state, side, slot, timestamp):
    from .active_continuity import current_episode
    gate = state.knowledge.get('occupancy_uncertainty', {}).get(side + ':' + slot)
    pid = state.sides[side].active_slots.get(slot)
    episode = current_episode(state, pid)
    if (gate and episode and gate['episode_id'] == episode['episode_id']
            and gate['timestamp'] <= timestamp):
        return gate
    return None


def corroborate_entry_model(state, event, record):
    """Optional cached corroboration tied to an explicit entry, never placement.

    No model is invoked here. The adapter must preserve independent model
    provenance and an entry-event association; a species/screen-position match
    alone is insufficient. Battle 6 currently has no such cached observations.
    """
    import math
    from .state_engine import Deferred, evidence_link
    from .active_continuity import current_episode
    a = event.attributes
    t = a.get('observation_time')
    entries = [ep for ep in state.knowledge.get('active_entry_episodes', [])
               if ep['entry_event_id'] == a.get('entry_event_id')
               and ep['side'] == event.side and ep['start_kind'] == 'send_out'
               and ep['departure'] is None]
    confidence = a.get('confidence')
    if (len(entries) != 1 or type(t) not in (int, float) or not math.isfinite(t)
            or type(confidence) not in (int, float) or not math.isfinite(confidence)
            or confidence < .95 or not event.actor):
        raise Deferred('entry_model_association_unresolved')
    ep = entries[0]
    if t < ep['start']:
        raise Deferred('entry_model_before_entry')
    entry_ids = {oid for s in ep['entry_evidence']['sources'] for oid in s.get('observation_ids', [])}
    sources = [s for s in event.evidence if s.source_type == 'cached_entry_model' and s.observation_ids]
    if (not sources or any(entry_ids.intersection(s.observation_ids) for s in sources)
            or any(s.details.get('timestamp') != t for s in sources)):
        raise Deferred('entry_model_independence_unproven')
    sid = event.actor.get('species_id')
    if not sid:
        raise Deferred('entry_model_identity_unresolved')
    proof = dict(event_id=event.event_id, timestamp=t, species_id=sid,
                 confidence=a['confidence'], evidence=evidence_link(event),
                 status='agreement' if sid == ep['species_id'] else 'disagreement')
    ep.setdefault('entry_model_observations', []).append(deepcopy(proof))
    record.bindings['entry_model'] = dict(episode_id=ep['episode_id'], **proof)
    # Disagreement preserves message identity but gates its current use. Never
    # selects the model's species or infers a slot from 3D screen coordinates.
    if proof['status'] == 'disagreement' and ep.get('slot'):
        pid = ep['instance_id']
        if current_episode(state, pid) is ep and state.sides[event.side].active_slots.get(ep['slot']) == pid:
            state.knowledge.setdefault('occupancy_uncertainty', {})[event.side+':'+ep['slot']] = dict(
                proof, status='conflicting', reason='entry_message_model_disagreement',
                instance_id=pid, episode_id=ep['episode_id'])
    return True
