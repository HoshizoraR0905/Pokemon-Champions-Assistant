"""Opt-in observation reliability. No mechanics or calculation dependencies."""
from copy import deepcopy
import hashlib
import math
from .battle_state import PokemonState, Fact, fact


def unplaced_entry(engine, state, event, record):
    """Preserve a named arrival without choosing a doubles slot or old instance."""
    from .state_engine import evidence_link, Deferred, Contradiction
    team = engine._side(state, event.side)
    if event.attributes.get('slot') is not None or len(team.vacant_slots) == 1:
        return None
    ref = event.actor or {}
    if not ref.get('species_id'):
        raise Deferred('entry_identity_unresolved')
    # Consecutive identical source announcements are one display occurrence.
    # No duration-based merge, no species-only merge across intervening actions.
    earlier=[r for r in engine.history if not r.retracted and r.ordering and record.ordering
        and r.ordering['domain']==record.ordering['domain'] and tuple(r.ordering['key'])<tuple(record.ordering['key'])
        and r.event['event_type']!='hud_observation']
    prior=max(earlier,key=lambda r:tuple(r.ordering['key'])) if earlier else None
    if prior and prior.event['event_type']=='send_out' and prior.event['side']==event.side and prior.event['original_text']==event.original_text:
        pid=prior.bindings.get('actor',{}).get('pokemon_instance_id')
        if pid in state.pokemon and state.pokemon[pid].location.value=={'kind':'unplaced_entry','slot':None}:
            record.bindings['actor']=dict(pokemon_instance_id=pid,basis='consecutive_same_announcement')
            record.bindings['admissibility']=dict(identity=True,slot=False,continuity=False)
            state.observations.append(dict(kind='repeated_entry_display',instance_id=pid,evidence=evidence_link(event)))
            return True
    pid = state.battle_id + ':' + event.side + ':entry:' + hashlib.sha256(event.event_id.encode()).hexdigest()[:16]
    if team.party_complete.known and team.party_complete.value:
        p=engine._resolve(state,event,record,sending=True)
        pid=p.pokemon_instance_id
        if pid in team.active_slots.values():raise Contradiction('already_active_instance')
        if p.fainted.known and p.fainted.value:raise Contradiction('send_out_of_fainted_instance')
    else:
        p = PokemonState(pid, event.side)
        engine._assign(p, 'species', ref, event)
        engine._assign(p, 'original_identity', ref, event)
        state.pokemon[pid] = p
        team.party_instance_ids.append(pid)
    engine._assign(p, 'location', {'kind': 'unplaced_entry', 'slot': None}, event)
    state.knowledge.setdefault('unplaced_entries', []).append(dict(instance_id=pid, side=event.side,
        species_id=ref['species_id'], event_id=event.event_id, timestamp=event.attributes.get('observation_time')))
    record.bindings['actor'] = dict(pokemon_instance_id=pid, basis='named_entry_slot_unresolved')
    record.bindings['admissibility'] = dict(identity=True, slot=False, continuity=False)
    state.observations.append(dict(kind='unplaced_entry', evidence=evidence_link(event), instance_id=pid))
    # This is an encounter episode, not proof it differs from an earlier party member.
    return True


def visual_transition(engine, state, event, record):
    from .state_engine import Deferred, Contradiction, evidence_link
    a = event.attributes
    if a.get('battle_id') != state.battle_id:
        raise Contradiction('visual_battle_ownership_mismatch')
    if a.get('source_kind') not in {'ability_popup', 'selected_detail_panel','party_configuration_panel'}:
        raise Deferred('visual_layout_unresolved')
    timestamp=a.get('observation_time')
    if type(timestamp) not in (int,float) or not math.isfinite(timestamp) or timestamp<0:raise Contradiction('invalid_visual_timestamp')
    ref = event.actor or {}; team = engine._side(state, event.side)
    candidates = [state.pokemon[i] for i in team.party_instance_ids
        if state.pokemon[i].species.known and state.pokemon[i].species.value.get('species_id') == ref.get('species_id')
        and (i in team.active_slots.values() or state.pokemon[i].location.value == {'kind':'unplaced_entry','slot':None})]
    if state.knowledge.get('reliability_v2'):
        from .evidence_projection import source_times
        # An information panel does not re-establish stale active continuity.
        candidates=[p for p in candidates if not any(o.get('kind')=='coverage_gap'
            and o.get('side') in {event.side,'field','unknown'}
            and o['end']>max(source_times(p.location.provenance),default=float('-inf')) for o in state.observations)]
        if not candidates and ref.get('species_id'):
            pid=state.battle_id+':'+event.side+':visual:'+hashlib.sha256(event.event_id.encode()).hexdigest()[:16]
            p=PokemonState(pid,event.side);state.pokemon[pid]=p;team.party_instance_ids.append(pid)
            engine._assign(p,'species',ref,event)
            engine._assign(p,'location',{'kind':'observed_unplaced','slot':None},event)
            candidates=[p]
    # A selected panel supplies a side and species, never a doubles slot.
    if len(candidates) != 1:
        raise Deferred('visual_instance_unresolved')
    p = candidates[0]; link = evidence_link(event)
    record.bindings['actor'] = dict(pokemon_instance_id=p.pokemon_instance_id, basis='unique_chronological_species_on_observed_side')
    fields = a.get('fields', {})
    accepted = {}
    def observe(obj, name, value, path):
        old = getattr(obj, name)
        # Stable identity fields disagreeing across sources remain conflicts.
        if old.known and old.value != value:
            setattr(obj, name, Fact(None, 'conflicting', old.provenance+[link],
                [{'value':deepcopy(old.value),'provenance':deepcopy(old.provenance)}, {'value':deepcopy(value),'provenance':[link]}]))
            state.conflicts.append(dict(event_id=event.event_id, reason='visual_fact_disagreement', field=path))
        elif old.knowledge != 'conflicting':
            engine._assign(obj, name, value, event)
            accepted[path] = deepcopy(value)
    if fields.get('ability'):
        observe(p.ability, 'current', fields['ability'], 'ability')
        p.ability.revealed.append(dict(ability=fields['ability'], evidence=link))
    if fields.get('item'):
        observe(p.item, 'identity', fields['item'], 'item')
        p.item.revealed.append(dict(item=fields['item'], evidence=link))
    hp = fields.get('hp')
    if hp:
        if type(hp.get('current')) is not int or type(hp.get('maximum')) is not int or not 0<=hp['current']<=hp['maximum'] or hp['maximum']<=0:
            raise Contradiction('invalid_visual_hp')
        observe(p.hp, 'maximum', hp['maximum'], 'maximum_hp')
        if p.hp.maximum.known:
            hp_event = deepcopy(event); hp_event.attributes = dict(unit='absolute', after=hp['current'], maximum=hp['maximum'])
            engine._hp(p, hp_event); accepted['maximum_hp'] = hp['maximum']
    for name, value in fields.get('stages', {}).items():
        e = deepcopy(event); e.attributes = dict(stats=[name], change='replace', value=value)
        engine._stats(p, e)
    # Field labels assert current presence only, not initiation or UI-counter semantics.
    for label,effect in [('rain',state.weather),('grassy',state.terrain)]:
        if fields.get('field',{}).get(label,{}).get('active') is True:
            engine._assign(effect,'active',True,event)
            engine._assign(effect,'kind',label,event)
    # Aurora Veil's affected side is not established by this panel layout.
    # Direct observations replace absolute stages, never activate ability/item effects.
    record.bindings['visual_receipt'] = dict(instance_id=p.pokemon_instance_id, fields=accepted)
    state.observations.append(dict(kind='visual_observation', evidence=link, instance_id=p.pokemon_instance_id,
                                   fields=deepcopy(fields), receipt=deepcopy(accepted)))
    return False
