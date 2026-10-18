"""Prefix-local command HUD verification of authoritative active occupancy.

Only explicit checkpoints can correct current slots. No transition explanation,
party continuity, HP, status, stages or hidden configuration is manufactured.
"""
from copy import deepcopy
import math
from battle_events.aliases import alias_key
from battle_events.schema import stable_id
from .battle_state import PokemonState, Fact
from .evidence_projection import source_times

SLOTS=('self:left','self:right','opponent:left','opponent:right')


def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def observed_identity(state,observation,timestamp):
    from .evidence_fusion import knowledge
    from battle_events.parser import EventParser
    species=observation.get('species') or {};icon=observation.get('icon') or {}
    raw=species.get('raw_text') or ''
    if (not observation.get('visible') or observation.get('timestamp')!=timestamp
            or observation.get('identity_reused_from') or not finite(species.get('confidence'))
            or species['confidence']<.95 or not raw):
        return None,'missing_or_unreadable_independent_hud',[]
    # Identity is obtained without consulting predicted occupants or roster order.
    exact=knowledge().exact['species'].get(__import__('knowledge').normalize(raw),[])
    sids={e.species_id for e in exact};proofs=[]
    if len(sids)==1:sid=next(iter(sids));basis='unique_literal_species'
    else:
        aliases=[a for a in state.knowledge.get('identity_ledger',{}).get('aliases',[])
            if a.get('status')=='accepted' and a['side']==observation['side']
            and a['lookup_key']==alias_key(raw) and a.get('evidence')
            and source_times(a['evidence']) and max(source_times(a['evidence']))<=timestamp]
        ids={a['identity']['species_id'] for a in aliases}
        if len(ids)!=1:return None,'nickname_membership_unresolved',[]
        sid=next(iter(ids));basis='prefix_local_v_nickname_species_association'
        proofs=[dict(instance_id=a.get('instance_id'),active_episode_id=a.get('active_episode_id'),
                     evidence=deepcopy(a['evidence'])) for a in aliases]
    if (species.get('resolution') or {}).get('status')=='conflict':return None,'text_visual_conflict',proofs
    if icon.get('status')=='resolved' and icon.get('species_id')!=sid:return None,'text_visual_conflict',proofs
    entity=knowledge().entities.get(f'pokeapi:species:{sid}')
    if not entity:return None,'unknown_canonical_species',proofs
    return dict(canonical_id=entity.canonical_id,species_id=sid,kind='species',name=entity.names.get('zh-hans'),
                identity_status='species_only',knowledge_snapshot=knowledge().snapshot_id),basis,proofs


def transition(engine,state,event,record):
    from .state_engine import Contradiction,Deferred,evidence_link
    from .active_continuity import current_episode,enter,placed
    from .identity_ledger import remember_alias
    a=event.attributes;t=a.get('observation_time');checkpoint=a.get('checkpoint') or {}
    if a.get('battle_id')!=state.battle_id:raise Contradiction('checkpoint_battle_ownership_mismatch')
    if not state.knowledge.get('command_reconciliation_v1'):raise Deferred('command_reconciliation_profile_required')
    if not finite(t) or not checkpoint.get('phase_id'):raise Contradiction('invalid_checkpoint')
    previous=checkpoint.get('previous_timestamp')
    if not checkpoint.get('stable') or not finite(previous) or not 0<t-previous<=1.1:
        raise Deferred('command_window_not_stable')
    ledger=state.knowledge.setdefault('command_reconciliation',dict(attempts=[],verified={},receipts=[]))
    phase=checkpoint['phase_id']
    if phase in ledger['attempts']:
        record.bindings['command_reconciliation']=dict(phase_id=phase,status='duplicate_phase_attempt_ignored')
        return True
    ledger['attempts'].append(phase)
    observations=a.get('observations',[])
    if len(observations)!=4 or {str(o.get('side'))+':'+str(o.get('slot')) for o in observations}!=set(SLOTS):
        raise Contradiction('checkpoint_requires_four_explicit_regions')
    from recognition.command_checkpoint import SLOT_REGIONS
    for o in observations:
        mapping=SLOT_REGIONS.get(o.get('region_id'))
        if not mapping or (o['side'],o['slot'],o.get('name_roi'))!=(mapping[0],mapping[1],list(mapping[2])):
            raise Contradiction('checkpoint_region_ownership_mismatch')
    proof=evidence_link(event);outcomes=[]
    valid_window=checkpoint.get('inspection',{}).get('eligible') is True
    for o in observations:
        key=o['side']+':'+o['slot'];team=state.sides[o['side']];pid=team.active_slots.get(o['slot'])
        old=state.pokemon.get(pid);old_sid=old.species.value.get('species_id') if old and old.species.known else None
        if not any(p.source_type=='command_hud_checkpoint' and p.source_id==o.get('source_id')
                   and o.get('sha256') in p.observation_ids and p.details.get('timestamp')==t
                   and p.details.get('image')==o.get('image') for p in event.evidence):
            raise Contradiction('checkpoint_observation_source_mismatch')
        ref,basis,aliases=observed_identity(state,o,t) if valid_window else (None,'incomplete_normal_command_view',[])
        status='inconclusive' if ref is None else 'unexpected_occupancy' if old_sid is None else 'match' if old_sid==ref['species_id'] else 'conflict'
        outcomes.append(dict(key=key,status=status,basis=basis,observed=deepcopy(ref),
            previous_instance_id=pid,previous_species_id=old_sid,corrected=False,
            observation=deepcopy(o),alias_proofs=aliases,comparison_scope='species_and_hud_slot; individual_continuity_unverified'))
    # Same-species occupancy within one side does not identify party instances.
    for side in state.sides:
        same=[o for o in outcomes if o['key'].startswith(side+':') and o['observed']]
        if len(same)==2 and same[0]['observed']['species_id']==same[1]['observed']['species_id']:
            for o in same:
                if o['status']!='match':o.update(status='inconclusive',basis='same_species_individual_ambiguity')
    for outcome in outcomes:
        key=outcome['key'];side,slot=key.split(':');status=outcome['status']
        if status in {'conflict','unexpected_occupancy'}:
            start=ledger['verified'].get(key)
            evidence_events=[]
            for earlier in engine.history:
                e=earlier.event;time=e.get('attributes',{}).get('observation_time')
                if earlier.ordering is None or record.ordering is None or earlier.ordering['domain']!=record.ordering['domain'] or earlier.ordering['key']>=record.ordering['key']:continue
                if earlier.retracted or not finite(time) or time>t or start is not None and time<=start:continue
                if e['event_type']=='coverage_observation' or any(p['source_type']=='video_message' for p in e['evidence']):
                    evidence_events.append(dict(event_id=e['event_id'],timestamp=time,raw_text=e['original_text'],
                                                event_type=e['event_type'],evidence=deepcopy(e['evidence'])))
            outcome['historical_gap']=dict(start=start,end=t,start_status='last_independent_checkpoint' if start is not None else 'unknown_no_prior_checkpoint',
                exact_transition_recovered=False,message_and_coverage_evidence=evidence_events)
            team=state.sides[side];old=state.pokemon.get(outcome['previous_instance_id'])
            if old:
                ep=current_episode(state,old.pokemon_instance_id)
                if ep:ep['departure']=dict(reason='reconciliation_occupancy_superseded',timestamp=t,slot=slot,
                    event_id=event.event_id,evidence=proof,unresolved_historical_gap=True)
                old.location=Fact(provenance=[proof]) # Prior history remains; current location is unknown.
            pid=state.battle_id+':'+side+':reconciled:'+stable_id(state.battle_id,event.event_id+':'+slot).split(':')[1]
            p=PokemonState(pid,side);state.pokemon[pid]=p;team.party_instance_ids.append(pid)
            engine._assign(p,'species',outcome['observed'],event);engine._assign(p,'original_identity',outcome['observed'],event)
            engine._assign(p,'location',dict(kind='active',slot=slot),event)
            team.active_slots[slot]=pid
            if slot in team.vacant_slots:team.vacant_slots.remove(slot)
            ep=enter(state,p,event,record,slot=slot,observed=True);placed(state,p,event,record,slot)
            ep['start_kind']='command_reconciliation';ep['historical_gap_unresolved']=True
            # A complete party does not establish which individual this new
            # observed episode belongs to. Keep compatible candidates explicit.
            ep['persistent_identity_status']='unproven'
            ep['possible_prior_instance_ids']=[candidate for candidate in team.party_instance_ids
                if candidate!=pid and state.pokemon[candidate].species.known
                and state.pokemon[candidate].species.value.get('species_id')==outcome['observed']['species_id']]
            record.bindings['entry_episode']=deepcopy(ep)
            state.knowledge.get('occupancy_uncertainty',{}).pop(key,None)
            state.knowledge.setdefault('hud_fusion',{}).setdefault('slots',{})[key]=dict(
                event_id=event.event_id,timestamp=t,raw=outcome['observation']['species']['raw_text'],
                confidence=outcome['observation']['species']['confidence'],species_id=outcome['observed']['species_id'],
                status='accepted',reason='independent_command_checkpoint',evidence=proof)
            raw=outcome['observation']['species']['raw_text']
            remember_alias(state,raw,outcome['observed'],[proof],side=side,instance_id=pid,source='command_checkpoint_existing_species_association')
            outcome.update(corrected=True,corrected_instance_id=pid,active_episode_id=ep['episode_id'])
        if status in {'match','conflict','unexpected_occupancy'}:ledger['verified'][key]=t
    receipt=dict(event_id=event.event_id,timestamp=t,phase_id=phase,source=proof,
                 outcomes=outcomes,corrections=sum(o['corrected'] for o in outcomes))
    ledger['receipts'].append(receipt);record.bindings['command_reconciliation']=deepcopy(receipt)
    return True
