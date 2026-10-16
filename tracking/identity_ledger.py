"""Replay-owned identity claims; no recognition, probabilities or scene geometry."""
from copy import deepcopy
import re
from battle_events.aliases import alias_key


def trainer_from_opening_hud(engine, state, event, record):
    """Calibrate a named opening entry only when both sides' HUD pairs agree.

    Association becomes available at this HUD timestamp, never at the earlier
    announcement. Literal labels are matched, not party membership or future
    species observations. Existing SideState.trainer owns the resulting claim.
    """
    from .state_engine import evidence_link, event_from_dict
    timestamp = event.attributes['observation_time']
    slots = state.knowledge.get('hud_fusion', {}).get('slots', {})
    pairs = {}
    proofs = []
    for side in state.sides:
        pair = []
        for slot in ('left', 'right'):
            last = slots.get(side + ':' + slot, {})
            sources = last.get('evidence', {}).get('sources', [])
            if (last.get('status') != 'accepted' or last.get('timestamp') != timestamp
                    or not last.get('raw') or not sources
                    or sources[0]['source_id'] != event.evidence[0].source_id):
                return
            pair.append(alias_key(last['raw'])); proofs.append(deepcopy(last['evidence']))
        if len(set(pair)) != 2:
            return
        pairs[side] = set(pair)
    for earlier in engine.history:
        e = earlier.event; a = e.get('attributes', {})
        if (earlier.retracted or earlier.application_status != 'recorded_observation'
                or e['event_type'] != 'entry_observation' or e['side'] != 'unknown'
                or a.get('observation_time', float('inf')) >= timestamp
                or (e.get('ocr_confidence') or 0) < .95):
            continue
        refs = a.get('ordered_display_references', [])
        if len(refs) != 2 or len({alias_key(x) for x in refs}) != 2:
            continue
        # Do not associate an old opening with a later post-action occupancy.
        if any(r.event['event_type'] in {'move_execution', 'switch_out', 'faint', 'transformation'}
               and a['observation_time'] < r.event.get('attributes', {}).get('observation_time', float('inf')) <= timestamp
               and not r.retracted for r in engine.history):
            continue
        match = re.fullmatch(r'(.+?)派出了.+', re.sub(r'\s+', '', e['original_text']))
        if not match or match[1] == '训练家':
            continue
        sides = [side for side, pair in pairs.items() if pair == {alias_key(x) for x in refs}]
        if len(sides) != 1:
            continue
        side = sides[0]; trainer = state.sides[side].trainer
        name = match[1]
        if trainer:
            continue
        other = [team.trainer for s, team in state.sides.items()
                 if s != side and team.trainer.get('display_name') == name]
        if other:
            for claim in other:
                claim['status'] = 'conflicting'
            continue
        state.sides[side].trainer = dict(display_name=name, status='accepted', observed_at=timestamp,
            basis='opening_entry_literal_pair_and_same_frame_accepted_huds',
            evidence=[evidence_link(event_from_dict(e)), *proofs],
            unique_trainer_id=None)
        record.bindings['trainer'] = deepcopy(state.sides[side].trainer)


def remember_alias(state,raw,identity,evidence,*,side,instance_id=None,source='same_hud_independent_icon'):
    ledger=state.knowledge.setdefault('identity_ledger',dict(aliases=[],roster=[],entries=[]))
    claim=dict(battle_id=state.battle_id,side=side,raw_nickname=raw,lookup_key=alias_key(raw),
        identity=deepcopy(identity),evidence=deepcopy(evidence),instance_id=instance_id,
        source=source,status='accepted',alternatives=[],persistent_individual_proven=False)
    prior=[a for a in ledger['aliases'] if a['side']==side and a['lookup_key']==claim['lookup_key']]
    for old in prior:
        if old['identity']['species_id']!=identity['species_id'] or (
                old['raw_nickname']!=raw and old.get('instance_id')!=instance_id):
            old['status']=claim['status']='conflicting'
            claim['alternatives'].append(deepcopy(old['identity']))
    ledger['aliases'].append(claim)
    return claim


def transition(engine,state,event,record):
    from .state_engine import Contradiction,Deferred,evidence_link
    a=event.attributes
    if not state.knowledge.get('identity_v1'):raise Deferred('identity_profile_required')
    if a.get('battle_id')!=state.battle_id:raise Contradiction('identity_battle_ownership_mismatch')
    ledger=state.knowledge.setdefault('identity_ledger',dict(aliases=[],roster=[],entries=[]))
    if event.event_type=='trainer_observation':
        trainer=deepcopy(a['trainer'])
        if trainer.get('battle_id')!=state.battle_id or trainer.get('side')!=event.side or event.side not in state.sides:
            raise Contradiction('trainer_ownership_mismatch')
        if (trainer.get('status')!='accepted' or trainer.get('ocr_confidence',0)<.95
                or not trainer.get('normalized_matching_form') or trainer.get('entity_kind')!='trainer'
                or trainer.get('normalized_matching_form')!=alias_key(trainer.get('raw_text',''))
                or not trainer.get('evidence')
                or any(p.get('timestamp',float('inf'))>a['observation_time'] for p in trainer.get('evidence',[]))):
            record.bindings['trainer']=dict(status='unresolved',observation=trainer)
            state.observations.append(dict(kind='trainer_identity_unresolved',evidence=evidence_link(event)))
            return True
        previous=state.sides[event.side].trainer
        trainer.update(display_name=trainer['raw_text'],observed_at=a['observation_time'])
        if previous and alias_key(previous['display_name'])!=trainer['normalized_matching_form']:
            trainer.update(status='conflicting',alternatives=[deepcopy(previous)])
        state.sides[event.side].trainer=trainer
        record.bindings['trainer']=deepcopy(trainer)
    elif event.event_type=='preview_observation':
        row=deepcopy(a['row'])
        if row.get('battle_id')!=state.battle_id or row.get('side')!=event.side or event.side not in state.sides:raise Contradiction('preview_ownership_mismatch')
        ledger['roster'].append(row);record.bindings['preview']=row
    elif event.event_type=='entry_observation':
        ledger['entries'].append(dict(event_id=event.event_id,side=event.side,
            raw_text=event.original_text,slot=None,species=None,status='unresolved',evidence=evidence_link(event)))
    elif event.event_type=='alias_observation':
        # Only an explicit, same-message species revelation can establish this
        # route. Roster membership alone is not an alias source.
        from battle_events.parser import EventParser
        from .evidence_fusion import knowledge
        parsed=EventParser(knowledge()).parse(dict(entry_id=event.event_id,source_id=event.evidence[0].source_id,
            raw_text=event.original_text,ocr_confidence=event.ocr_confidence),battle_id=state.battle_id)
        if (parsed.event_type!='transformation' or not parsed.attributes.get('identity')
                or event.ocr_confidence is None or event.ocr_confidence<.95 or parsed.side!=event.side):
            raise Deferred('explicit_alias_revelation_unresolved')
        raw=event.original_text.split('超级进化成了',1)[0].strip()
        if raw.startswith('对手的'):raw=raw[len('对手的'):]
        if not raw:raise Deferred('empty_display_alias')
        identity=parsed.attributes['identity']
        # Revelation proves a named episode, without proving its doubles slot or
        # equivalence to a past individual. Do not duplicate a known active one.
        from .battle_state import PokemonState
        from .evidence_fusion import context_supported
        matches={a.get('instance_id') for a in ledger['aliases'] if a['side']==event.side
            and a['status']=='accepted' and a['lookup_key']==alias_key(raw)
            and a['identity']['species_id']==identity['species_id']
            and any(pid==a.get('instance_id') and context_supported(state,event.side,slot,event.attributes['observation_time'])
                for slot,pid in state.sides[event.side].active_slots.items())}
        if len(matches)==1:
            pid=next(iter(matches));p=state.pokemon[pid]
        else:
            pid=state.battle_id+':'+event.side+':alias:'+event.event_id.rsplit(':',1)[-1]
            p=PokemonState(pid,event.side);state.pokemon[pid]=p;state.sides[event.side].party_instance_ids.append(pid)
            engine._assign(p,'location',dict(kind='observed_unplaced',slot=None),event)
        engine._assign(p,'species',identity,event)
        if identity.get('canonical_identity'):engine._assign(p,'current_variant',identity['canonical_identity'],event)
        claim=remember_alias(state,raw,identity,[evidence_link(event)],side=event.side,instance_id=pid,source='explicit_species_revelation')
        record.bindings['alias']=claim
    return True
