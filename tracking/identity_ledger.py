"""Replay-owned identity claims; no recognition, probabilities or scene geometry."""
from copy import deepcopy
from battle_events.aliases import alias_key


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
    if event.event_type=='preview_observation':
        row=deepcopy(a['row'])
        if row.get('battle_id')!=state.battle_id or row.get('side')!='opponent':raise Contradiction('preview_ownership_mismatch')
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
