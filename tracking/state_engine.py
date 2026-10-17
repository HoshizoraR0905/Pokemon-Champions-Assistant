"""Replayable M2.2 transitions; no OCR, video decoding, or damage calculations."""
from copy import deepcopy
from dataclasses import dataclass, field, asdict
import hashlib
import json
import math
from battle_events.schema import BattleEvent, Evidence
from .battle_state import (BattleState, PokemonState, Fact, Effect, Duration, fact,
                           STATS, WEATHER, TERRAIN, MAJOR_STATUS, from_dict)

from .mechanics import MechanicRegistry
from .mechanic_rules import MechanicRules

class Deferred(Exception): pass
class Contradiction(Exception): pass

@dataclass
class ApplicationPolicy:
    name: str = 'conservative-candidate-v1'
    minimum_ocr_confidence: float = .75
    allowed_uncertainties: tuple = ('actor_variant_unresolved','target_variant_unresolved',
                                   'target_associated_from_sequence')
    allow_candidates: bool = True

    def check(self,event):
        if (event.event_type=='move_execution' and event.attributes.get('source_region_type') is not None
                and event.attributes['source_region_type']!='battle_message'):
            raise Deferred('move_execution_requires_live_message_region')
        if event.status not in {'candidate','confirmed'}:raise Deferred('event_not_candidate_or_confirmed')
        if not event.evidence:raise Deferred('missing_provenance')
        if event.status=='candidate':
            if not self.allow_candidates:raise Deferred('candidate_policy_disabled')
            if event.parsing_confidence not in {'supported','uncertain'}:raise Deferred('unsupported_parsing_confidence')
            if event.ocr_confidence is not None and event.ocr_confidence<self.minimum_ocr_confidence:
                raise Deferred('low_ocr_confidence')
            if set(event.uncertainty)-set(self.allowed_uncertainties):raise Deferred('unresolved_candidate_fields')
        # High OCR confidence alone never promotes the candidate to confirmed.

@dataclass
class EventRecord:
    event: dict
    delivery_index: int
    ordering: dict | None
    application_status: str = 'deferred'
    reason: str | None = None
    policy: str | None = None
    bindings: dict = field(default_factory=dict)
    state_hash: str | None = None
    revisions: list[dict] = field(default_factory=list)
    retracted: bool = False


def event_from_dict(value):
    value=deepcopy(value)
    value['evidence']=[Evidence(**e) if isinstance(e,dict) else e for e in value['evidence']]
    return BattleEvent(**value)


def hash_state(state):
    return hashlib.sha256(json.dumps(state.to_dict(),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def evidence_link(event):
    return {'event_id':event.event_id,'event_status':event.status,'ocr_confidence':event.ocr_confidence,
            'parsing_confidence':event.parsing_confidence,'uncertainty':list(event.uncertainty),
            'sources':[asdict(e) for e in event.evidence]}


def ordering(event,sequence=None):
    sequence=sequence if sequence is not None else event.attributes.get('sequence')
    if sequence is not None:
        if not isinstance(sequence,int) or isinstance(sequence,bool):raise ValueError('Sequence must be an explicit integer')
        return {'domain':'sequence','key':[sequence],'basis':'caller_asserted_order'}
    turns={e.details.get('turn') for e in event.evidence if e.details.get('turn') is not None}
    if len(turns)>1:return None
    if event.log_order is not None and len(turns)==1:
        turn=next(iter(turns))
        if not isinstance(turn,int) or isinstance(turn,bool) or turn<1:return None
        if not isinstance(event.log_order,int) or isinstance(event.log_order,bool) or event.log_order<1:return None
        return {'domain':'turn_log','key':[turn,event.log_order],'basis':'observed_heading_and_log_order'}
    time=event.attributes.get('event_time')
    if event.attributes.get('order_confirmed') is True and isinstance(time,(int,float)) and not isinstance(time,bool) and math.isfinite(time):
        return {'domain':'time','key':[time],'basis':'explicitly_confirmed_event_time'}
    return None


class StateEngine:
    def __init__(self,initial,policy=None,*,mechanic_rules=None,mechanic_registry=None):
        self.initial=deepcopy(initial);self.state=deepcopy(initial)
        self.policy=policy or ApplicationPolicy();self.history=[]
        self.mechanic_rules=mechanic_rules or MechanicRules()
        self.mechanic_registry=mechanic_registry or MechanicRegistry()
        self._validate_initial()
        self.mechanic_registry.initialize(self.initial)
        self.state=deepcopy(self.initial)

    def _validate_initial(self):
        seen=set()
        for side_id,side in self.initial.sides.items():
            if side_id not in {'self','opponent'} or side.side_id!=side_id:raise ValueError('Invalid side')
            if len(side.party_instance_ids)!=len(set(side.party_instance_ids)):raise ValueError('Duplicate party instance')
            for pid in side.party_instance_ids:
                p=self.initial.pokemon[pid]
                if p.side_id!=side_id or p.pokemon_instance_id!=pid or pid in seen:raise ValueError('Invalid instance ownership')
                seen.add(pid)
            for slot,pid in side.active_slots.items():
                if pid not in side.party_instance_ids:raise ValueError('Active instance absent from party')
                p=self.initial.pokemon[pid]
                if p.fainted.known and p.fainted.value:raise ValueError('Fainted initial active instance')
                if not p.location.known or p.location.value!={'kind':'active','slot':slot}:raise ValueError('Initial slot/location mismatch')
            if len(set(side.active_slots.values()))!=len(side.active_slots):raise ValueError('Instance active twice')
        if seen!=set(self.initial.pokemon):raise ValueError('Unowned instance')
        for p in self.initial.pokemon.values():
            for stage in p.stages.values():
                if stage.value.known and (not isinstance(stage.value.value,int) or not -6<=stage.value.value<=6):raise ValueError('Invalid initial stage')

    def apply(self,event,*,sequence=None):
        event=event_from_dict(event) if isinstance(event,dict) else deepcopy(event)
        payload=event.to_dict();key=ordering(event,sequence)
        existing=next((r for r in self.history if r.event['event_id']==event.event_id),None)
        if existing:
            if existing.event!=payload or (sequence is not None and existing.ordering!=key):
                raise ValueError('Same event ID has different payload/order; use correct()')
            return deepcopy(existing)  # Exactly idempotent, including retracted IDs.
        record=EventRecord(payload,len(self.history),key)
        self.history.append(record);self.replay()
        return deepcopy(record)

    def correct(self,event_id,replacement,*,sequence=None,reason):
        record=next(r for r in self.history if r.event['event_id']==event_id)
        replacement=event_from_dict(replacement) if isinstance(replacement,dict) else deepcopy(replacement)
        if replacement.event_id!=event_id:raise ValueError('Correction preserves the logical event ID')
        record.revisions.append({'event':deepcopy(record.event),'ordering':deepcopy(record.ordering),
                                 'retracted':record.retracted,'reason':reason})
        record.event=replacement.to_dict();record.ordering=ordering(replacement,sequence);record.retracted=False
        self.replay();return deepcopy(record)

    def retract(self,event_id,*,reason):
        record=next(r for r in self.history if r.event['event_id']==event_id)
        record.revisions.append({'event':deepcopy(record.event),'ordering':deepcopy(record.ordering),
                                 'retracted':record.retracted,'reason':reason})
        record.retracted=True;self.replay()

    def replay(self, *, snapshot_callback=None):
        self.state=deepcopy(self.initial)
        active=[r for r in self.history if not r.retracted and r.ordering]
        domains={r.ordering['domain'] for r in active}
        duplicate_keys={tuple(r.ordering['key']) for r in active
                        if sum(a.ordering==r.ordering for a in active)>1}
        for r in self.history:
            r.application_status='deferred';r.reason=None;r.bindings={};r.state_hash=None;r.policy=self.policy.name
            if r.retracted:r.application_status='retracted';r.reason='explicit_retraction'
            elif not r.ordering:r.reason='missing_or_ambiguous_event_order'
            elif len(domains)>1:r.reason='incomparable_order_domains'
            elif tuple(r.ordering['key']) in duplicate_keys:r.reason='ambiguous_order_tie'
        ordered=sorted((r for r in active if r.reason is None),key=lambda r:tuple(r.ordering['key']))
        # Stop at an ambiguous ordering collision rather than leap over it.
        barrier=min(duplicate_keys) if duplicate_keys and len(domains)==1 else None
        for record in ordered:
            if barrier is not None and tuple(record.ordering['key'])>barrier:
                record.reason='earlier_order_tie';continue
            event=event_from_dict(record.event);trial=deepcopy(self.state)
            try:
                from .evidence_fusion import prepare_message, move_revelation
                event=prepare_message(trial,event)
                if event.event_type=='move_execution' and event.attributes.get('fusion_context'):
                    move_revelation(self,trial,event,record)
                    self.state=trial
                    record.application_status='applied_partial'
                    record.reason='move_revelation_only'
                    record.state_hash=hash_state(self.state)
                    if snapshot_callback is not None:snapshot_callback(record,self.state)
                    continue
                self.policy.check(event)
                if event.attributes.get('fusion_context'):
                    record.bindings['resolved_event']=event.to_dict()
                turns={e.details.get('turn') for e in event.evidence if e.details.get('turn') is not None}
                if len(turns)==1 and event.event_type!='turn_boundary':
                    self._set_turn(trial,next(iter(turns)),event,tick=False)
                recorded=self._transition(trial,event,record)
                self.mechanic_registry.after_event(trial,self.state,event,record,self.mechanic_rules)
                self._available(trial,event)
                self.state=trial
                record.application_status='recorded_observation' if recorded else ('applied_candidate' if event.status=='candidate' else 'applied_confirmed')
            except Deferred as exc:
                record.reason=str(exc);record.bindings={'resolved_event':event.to_dict()} if event.attributes.get('fusion_context') else {}
            except (Contradiction,ValueError,TypeError,KeyError) as exc:
                record.application_status='rejected';record.reason=str(exc);record.bindings={}
                self.state.conflicts.append({'event_id':event.event_id,'reason':str(exc),'proposed_event':event.to_dict(),'state_unchanged':True})
            record.state_hash=hash_state(self.state)
            if snapshot_callback is not None:
                snapshot_callback(record,self.state)
        return self.state

    def evidence_projection(self, *, as_of):
        from .evidence_projection import evidence_projection
        return evidence_projection(self, as_of=as_of)

    def decision_state(self,hidden_engine=None):
        from .decision_state import decision_state
        return decision_state(self.state,self.mechanic_rules,hidden_engine=hidden_engine)

    def to_dict(self):
        return {'schema_version':2,'policy':asdict(self.policy),'mechanic_rules':self.mechanic_rules.to_dict(),'mechanic_handlers':[h.mechanic_id for h in self.mechanic_registry.handlers],'initial_state':self.initial.to_dict(),
                'history':[asdict(r) for r in self.history],'state':self.state.to_dict(),'state_hash':hash_state(self.state)}

    @classmethod
    def from_dict(cls,value,*,mechanic_registry=None):
        config=deepcopy(value['policy']);config['allowed_uncertainties']=tuple(config['allowed_uncertainties'])
        engine=cls(from_dict(value['initial_state']),ApplicationPolicy(**config),
                   mechanic_rules=MechanicRules(**value.get('mechanic_rules',{})),mechanic_registry=mechanic_registry)
        expected=value.get('mechanic_handlers')
        if expected is not None and expected != [h.mechanic_id for h in engine.mechanic_registry.handlers]:
            raise ValueError('Serialized mechanic handlers require a matching registry')
        engine.history=[EventRecord(**deepcopy(r)) for r in value['history']]
        engine.replay();return engine

    def _assign(self,obj,name,value,event,*,derived=False):
        setattr(obj,name,fact(deepcopy(value),evidence_link(event),'derived' if derived else 'observed'))

    def _consistent_fact(self,obj,name,value,event):
        previous=getattr(obj,name)
        equal=previous.value==value
        if isinstance(previous.value,dict) and isinstance(value,dict) and 'canonical_id' in previous.value and 'canonical_id' in value:
            equal=previous.value['canonical_id']==value['canonical_id']
        if previous.known and not equal:raise Contradiction('conflicting_'+name)
        self._assign(obj,name,value,event)

    def _side(self,state,side):
        if side not in state.sides:raise Deferred('unknown_battle_side')
        return state.sides[side]

    def _resolve(self,state,event,record,*,role='actor',sending=False,allow_identity_change=False):
        ref=getattr(event,role)
        side=event.side if role=='actor' else event.attributes.get('target_side')
        team=self._side(state,side)
        pid=event.attributes.get(role+'_instance_id') or (ref or {}).get('pokemon_instance_id')
        if pid:
            if pid not in state.pokemon:raise Deferred('unobserved_explicit_instance')
            p=state.pokemon[pid]
            if p.side_id!=side:raise Contradiction('instance_side_conflict')
            if ref and ref.get('species_id') and p.species.known and p.species.value.get('species_id')!=ref['species_id'] and not allow_identity_change:
                raise Contradiction('instance_species_conflict')
            record.bindings[role]={'pokemon_instance_id':pid,'basis':'explicit_instance_id'};return p
        if ref is None or ref.get('species_id') is None:raise Deferred('actor_or_target_identity_unresolved')
        matches=[state.pokemon[i] for i in team.party_instance_ids if state.pokemon[i].species.known
                 and state.pokemon[i].species.value.get('species_id')==ref['species_id']]
        if sending:
            if len(matches)==1 and team.party_complete.known and team.party_complete.value:
                p=matches[0];basis='unique_species_in_verified_complete_party'
            elif matches and not state.knowledge.get('active_continuity_v1'):raise Deferred('ambiguous_existing_instance_in_partial_or_duplicate_party')
            elif matches and team.party_complete.known and team.party_complete.value:raise Deferred('ambiguous_existing_instance_in_partial_or_duplicate_party')
            elif team.party_complete.known and team.party_complete.value:raise Contradiction('send_out_outside_complete_party')
            else:
                pid=f'{state.battle_id}:{side}:encounter:'+hashlib.sha256(event.event_id.encode()).hexdigest()[:16]
                p=PokemonState(pid,side)
                self._assign(p,'species',ref,event);self._assign(p,'original_identity',ref,event)
                if ref.get('canonical_identity'):self._assign(p,'current_variant',ref['canonical_identity'],event)
                state.pokemon[pid]=p;team.party_instance_ids.append(pid);basis='new_entry_without_species_only_party_merge' if matches else 'first_observed_instance'
        else:
            # A species name refers to an active instance only if that reference
            # is unique within this side. No cross-side or hidden-roster merge.
            matches=[p for p in matches if p.pokemon_instance_id in team.active_slots.values()]
            if len(matches)!=1:raise Deferred('ambiguous_or_missing_active_instance')
            p=matches[0];basis='unique_current_active_species_on_observed_side'
        if ref.get('canonical_identity') and p.current_variant.known and p.current_variant.value!=ref['canonical_identity']:
            raise Contradiction('variant_conflict_without_transformation')
        record.bindings[role]={'pokemon_instance_id':p.pokemon_instance_id,'basis':basis};return p

    def _transition(self,state,e,record):
        if e.event_type in {'preview_observation','entry_observation','alias_observation','trainer_observation'}:
            from .identity_ledger import transition
            return transition(self,state,e,record)
        kind=e.event_type;a=e.attributes
        if kind=='position_change':
            if a.get('mechanic')!='ally_switch' or a.get('execution_observed') is not True:
                raise Deferred('position_exchange_execution_unresolved')
            team=self._side(state,e.side)
            if set(team.active_slots)!={'left','right'} or len(set(team.active_slots.values()))!=2:
                raise Deferred('position_exchange_occupants_unresolved')
            left,right=team.active_slots['left'],team.active_slots['right']
            team.active_slots.update(left=right,right=left)
            for slot,pid in team.active_slots.items():
                self._assign(state.pokemon[pid],'location',dict(kind='active',slot=slot),e)
            fusion=state.knowledge.get('hud_fusion',{}).get('slots',{})
            lk,rk=e.side+':left',e.side+':right'
            lv,rv=fusion.pop(lk,None),fusion.pop(rk,None)
            if rv:fusion[lk]=rv
            if lv:fusion[rk]=lv
            record.bindings['exchange']=dict(before=dict(left=left,right=right),after=dict(team.active_slots))
            return False
        if kind in {'visual_observation','coverage_observation'}:
            if not state.knowledge.get('reliability_v1'):raise Deferred('reliability_profile_required')
            if kind=='coverage_observation':
                if a.get('battle_id')!=state.battle_id:raise Contradiction('coverage_battle_ownership_mismatch')
                start=a.get('start');end=a.get('observation_time')
                if not all(type(t) in (int,float) and math.isfinite(t) for t in (start,end)) or not 0<=start<=end:raise Contradiction('invalid_coverage_interval')
                if a.get('status')!='gap':raise Deferred('unsupported_coverage_assertion')
                state.observations.append(dict(kind='coverage_gap',start=start,end=end,side=e.side,fields=deepcopy(a.get('fields',[])),evidence=evidence_link(e)))
                return True
            from .reliability import visual_transition
            return visual_transition(self,state,e,record)
        if kind=='send_out' and state.knowledge.get('reliability_v1'):
            from .reliability import unplaced_entry
            result=unplaced_entry(self,state,e,record)
            if result is not None:return result
        if kind=='hud_observation':
            from .evidence_fusion import hud_transition
            return hud_transition(self,state,e,record)
        if state.knowledge.get('move_grounding') and kind=='turn_boundary':
            state.knowledge['association_boundary']=len(state.knowledge.get('causal_actions',[]))
        if state.knowledge.get('move_grounding') and kind=='move_effect' and a.get('effect_of'):
            actions=[x for x in state.knowledge.get('causal_actions',[]) if x['event_id']==a['effect_of']]
            if len(actions)==1 and a.get('outcome') in {'failed','blocked','uncertain'}:
                actions[0]['outcome']=a['outcome']
        if kind in {'effectiveness','move_effect','critical_hit','multi_hit'}:
            observation={'event_id':e.event_id,'event_type':kind,'attributes':deepcopy(a),'evidence':evidence_link(e)}
            state.observations.append(observation)
            if kind in {'critical_hit','multi_hit'} and e.actor:
                p=self._resolve(state,e,record);p.moves.hit_observations.append(observation)
            return True
        if kind=='unknown':raise Deferred('unsupported_event_type')
        if kind=='phase_observation':
            if 'phase' not in a:raise Deferred('phase_unknown')
            self._assign(state,'phase',a['phase'],e);return False
        if kind=='turn_boundary':
            turn=a.get('turn');boundary=a.get('boundary')
            if boundary not in {'start','end'}:raise Deferred('unknown_turn_boundary')
            self._set_turn(state,turn,e,tick=boundary=='start')
            if boundary=='end':self._tick_effects(state,e,turn,'turn_end')
            return False
        if kind in {'weather_change','terrain_change','trick_room_change','side_condition_change'}:
            self._field_event(state,e);return False
        if kind in {'mechanic_observation','mechanic_reset'} and a.get('scope') in {'global','per_side'}:
            return False
        if kind=='party_observation':
            team=self._side(state,e.side)
            identifiers=a.get('selected_instance_ids')
            if not isinstance(identifiers,list) or len(set(identifiers))!=len(identifiers) or set(identifiers)!=set(team.party_instance_ids):
                raise Contradiction('selected_party_observation_mismatch')
            if a.get('complete') is not True:raise Deferred('selected_party_completeness_unresolved')
            self._assign(team,'party_complete',True,e)
            return False
        if kind=='hp_change' and (a.get('intermediate') is True or a.get('observation_kind')=='animation'):
            state.observations.append({'event_id':e.event_id,'kind':'intermediate_hp_sample','attributes':deepcopy(a),'evidence':evidence_link(e)});return True
        if kind=='hp_change' and a.get('qualitative_only'):
            p=self._resolve(state,e,record)
            observation=dict(event_id=e.event_id,kind='qualitative_hp_loss',direction=a.get('direction'),
                magnitude=a.get('magnitude'),before=None,after=None,cause=None,evidence=evidence_link(e))
            p.hp.observations.append(observation);state.observations.append(deepcopy(observation));return True
        p=self._resolve(state,e,record,sending=kind=='send_out',allow_identity_change=kind=='transformation')
        team=state.sides[p.side_id]
        from .knowledge_grounding import ground_event
        if ground_event(self,state,p,e,record): return False
        if kind in {'protection_attempt','protection_outcome','mechanic_observation','mechanic_reset','type_change','ability_attempt'}:
            return False
        if kind=='send_out':
            if p.fainted.known and p.fainted.value:raise Contradiction('send_out_of_fainted_instance')
            if p.pokemon_instance_id in team.active_slots.values():raise Contradiction('already_active_instance')
            slot=a.get('slot')
            if slot is None:
                if len(team.vacant_slots)!=1:raise Deferred('active_slot_ambiguous')
                slot=team.vacant_slots[0]
            if not isinstance(slot,str):raise Contradiction('invalid_slot')
            if slot in team.active_slots:raise Contradiction('occupied_active_slot')
            if state.knowledge.get('active_continuity_v1'):
                from .active_continuity import enter,placed
                enter(state,p,e,record,slot=slot);placed(state,p,e,record,slot)
            team.active_slots[slot]=p.pokemon_instance_id
            if slot in team.vacant_slots:team.vacant_slots.remove(slot)
            self._assign(p,'location',{'kind':'active','slot':slot},e);self._assign(p,'fainted',False,e)
        elif kind in {'switch_out','faint'}:
            slots=[s for s,i in team.active_slots.items() if i==p.pokemon_instance_id]
            if state.knowledge.get('active_continuity_v1'):
                if not slots:raise Deferred('departure_active_slot_unresolved')
                from .active_continuity import depart
                depart(state,p,e,record,slots)
            if kind=='switch_out' and not slots:raise Contradiction('withdrawal_of_inactive_instance')
            for slot in slots:
                del team.active_slots[slot]
                if slot not in team.vacant_slots:team.vacant_slots.append(slot)
            self._assign(p,'location',{'kind':'fainted' if kind=='faint' else 'bench','slot':None},e)
            if kind=='faint':
                self._assign(p,'fainted',True,e)
                # A prior positive HP display is no longer current. Preserve
                # the observation ledger; don't invent an unseen endpoint.
                for name in ('current','displayed_percent'):
                    observed=getattr(p.hp,name)
                    if observed.known and observed.value>0:
                        setattr(p.hp,name,Fact(provenance=[evidence_link(e)]))
                        p.hp.percent_interval=Fact(provenance=[evidence_link(e)])
                if p.pokemon_instance_id not in team.fainted_instance_ids:team.fainted_instance_ids.append(p.pokemon_instance_id)
            # Reset rules are unverified in the default profile. Do not carry
            # modified stages as current facts through an uncertain withdrawal.
            if kind=='switch_out' and a.get('invalidate_unverified_persistence') is True:
                for stage in p.stages.values():
                    if stage.changes:
                        stage.value=Fact(provenance=[evidence_link(e)])
                        stage.interval=Fact(provenance=[evidence_link(e)])
                for effect in p.volatile.values():
                    if effect.active.known and effect.active.value:
                        effect.active=Fact(provenance=[evidence_link(e)])
                        effect.duration=Duration()
        elif kind=='hp_change':self._hp(p,e)
        elif kind=='move_execution':
            ref=e.canonical_references.get('move')
            if not ref:raise Deferred('move_identity_unknown')
            execution={'event_id':e.event_id,'move':deepcopy(ref),'evidence':evidence_link(e)}
            # Contextual M2.1 target associations are retained as candidates,
            # never used to apply HP or secondary effects.
            if e.target:execution['target_candidate']={'identity':deepcopy(e.target),'side':a.get('target_side'),'basis':deepcopy(a.get('target_basis'))}
            p.moves.executed.append(execution)
            if a.get('move_slot') is not None:p.moves.known_slots[str(a['move_slot'])]=fact(ref,evidence_link(e))
            if a.get('pp') is not None:p.moves.pp[ref['canonical_id']]=fact(a['pp'],evidence_link(e))
        elif kind=='move_observation':
            ref=e.canonical_references.get('move')
            if not ref:raise Deferred('move_identity_unknown')
            slot=a.get('move_slot')
            if not isinstance(slot,int) or isinstance(slot,bool) or not 1<=slot<=4:raise Contradiction('invalid_move_slot')
            p.moves.known_slots[str(slot)]=fact(ref,evidence_link(e))
            if 'pp' in a:
                value=a['pp']
                if not isinstance(value,dict) or set(value)!={'current','maximum'} or any(not isinstance(v,int) or isinstance(v,bool) for v in value.values()) or not 0<=value['current']<=value['maximum']:
                    raise Contradiction('invalid_observed_pp')
                p.moves.pp[ref['canonical_id']]=fact(value,evidence_link(e))
        elif kind=='stat_change':self._stats(p,e)
        elif kind=='status_change':self._status(p,e)
        elif kind=='ability_activation':
            ref=e.canonical_references.get('ability')
            if not ref:raise Deferred('ability_identity_unknown')
            self._consistent_fact(p.ability,'current',ref,e)
            p.ability.revealed.append({'ability':deepcopy(ref),'activation':True,'evidence':evidence_link(e)})
        elif kind=='ability_change':
            if 'suppressed' in a:
                if not isinstance(a['suppressed'],bool):raise Contradiction('invalid_ability_suppression')
                self._assign(p.ability,'suppressed',a['suppressed'],e)
            elif e.canonical_references.get('ability'):
                self._assign(p.ability,'current',e.canonical_references['ability'],e)
            elif a.get('change')=='remove':self._assign(p.ability,'current',None,e)
            else:raise Deferred('ability_change_unknown')
            p.ability.modifications.append({'attributes':deepcopy(a),'evidence':evidence_link(e)})
        elif kind in {'item_activation','item_change'}:self._item(state,p,e,record)
        elif kind=='transformation':self._transform(state,p,e)
        elif kind=='volatile_change':
            name=a.get('condition')
            if not isinstance(name,str) or not name:raise Deferred('volatile_condition_unknown')
            self._effect(p.volatile.setdefault(name,Effect()),name,e,state)
        else:raise Deferred('unsupported_event_type')
        return False

    def _hp(self,p,e):
        a=e.attributes;unit=a.get('unit');before=a.get('before');after=a.get('after')
        if unit not in {'absolute','displayed_percent'}:raise Deferred('hp_unit_unknown')
        if not isinstance(after,(int,float)) or isinstance(after,bool) or not math.isfinite(after) or after<0:raise Contradiction('invalid_hp_endpoint')
        if before is not None and (not isinstance(before,(int,float)) or isinstance(before,bool) or not math.isfinite(before) or before<0):raise Contradiction('invalid_hp_baseline')
        if unit=='absolute' and (int(after)!=after or before is not None and int(before)!=before):raise Contradiction('non_integer_absolute_hp')
        if unit=='displayed_percent' and (after>100 or before is not None and before>100):raise Contradiction('invalid_displayed_percent')
        current=p.hp.current if unit=='absolute' else p.hp.displayed_percent
        if current.knowledge=='conflicting':raise Deferred('unresolved_hp_conflict')
        if current.known and before is not None and current.value!=before:raise Contradiction('hp_before_mismatch')
        if p.fainted.known and p.fainted.value and after>0:raise Contradiction('hp_after_confirmed_faint_without_revival')
        maximum=a.get('maximum')
        if maximum is not None:
            if not isinstance(maximum,int) or isinstance(maximum,bool) or maximum<=0:raise Contradiction('invalid_maximum_hp')
            self._consistent_fact(p.hp,'maximum',maximum,e)
        if unit=='absolute' and p.hp.maximum.known and after>p.hp.maximum.value:raise Contradiction('hp_exceeds_observed_maximum')
        if unit=='absolute':
            self._assign(p.hp,'current',int(after),e)
            # Do not keep an earlier percentage as a simultaneous current fact.
            p.hp.displayed_percent=Fact(provenance=[evidence_link(e)])
            p.hp.percent_interval=Fact(provenance=[evidence_link(e)])
        else:
            self._assign(p.hp,'displayed_percent',after,e)
            p.hp.current=Fact(provenance=[evidence_link(e)])
            interval=a.get('percent_interval')
            if interval is not None:
                if len(interval)!=2 or not 0<=interval[0]<=interval[1]<=100:raise Contradiction('invalid_percent_interval')
                self._assign(p.hp,'percent_interval',interval,e)
            else:p.hp.percent_interval=Fact(provenance=[evidence_link(e)])
        self._assign(p.hp,'unit',unit,e)
        p.hp.observations.append({'before':before,'after':after,'unit':unit,'maximum':maximum,'evidence':evidence_link(e)})
        # Zero HP is retained as HP evidence; explicit faint establishes the
        # faint record. Never manufacture opponent absolute HP from percentage.

    def _stats(self,p,e):
        a=e.attributes;stats=a.get('stats');change=a.get('change')
        if change is None:change='increment' if a.get('direction')=='up' else ('decrement' if a.get('direction')=='down' else None)
        if change=='reset' and stats is None:stats=list(STATS)
        if not stats or any(s not in STATS for s in stats):raise Deferred('stat_names_unknown')
        amount=a.get('stages')
        if change in {'increment','decrement'} and amount is not None:
            if not isinstance(amount,int) or isinstance(amount,bool) or amount<1:raise Contradiction('invalid_stat_delta')
        for name in dict.fromkeys(stats):
            stage=p.stages[name];previous=stage.value.value if stage.value.known else None
            if stage.value.knowledge=='conflicting':raise Deferred('unresolved_stat_conflict')
            if change in {'reset','replace'}:
                value=0 if change=='reset' else a.get('value')
                if not isinstance(value,int) or isinstance(value,bool) or not -6<=value<=6:raise Contradiction('invalid_replacement_stage')
                self._assign(stage,'value',value,e);self._assign(stage,'interval',[value,value],e)
            elif change in {'increment','decrement'}:
                direction=1 if change=='increment' else -1
                if previous is not None and amount is not None:
                    value=max(-6,min(6,previous+direction*amount))
                    self._assign(stage,'value',value,e,derived=True);self._assign(stage,'interval',[value,value],e,derived=True)
                else:
                    bounds=[previous,previous] if previous is not None else (deepcopy(stage.interval.value) if stage.interval.known else [-6,6])
                    if amount is not None:bounds=[max(-6,min(6,n+direction*amount)) for n in bounds]
                    elif direction>0:bounds=[min(6,bounds[0]+1),6]
                    else:bounds=[-6,max(-6,bounds[1]-1)]
                    stage.value=Fact(provenance=[evidence_link(e)])
                    if bounds[0]==bounds[1]:self._assign(stage,'value',bounds[0],e,derived=True)
                    self._assign(stage,'interval',bounds,e,derived=True)
            else:raise Deferred('stat_change_unknown')
            stage.changes.append({'change':change,'amount':amount,'prior_known_value':previous,
                                  'evidence':evidence_link(e)})

    def _status(self,p,e):
        a=e.attributes;change=a.get('change');status=a.get('status')
        if change=='remove':
            if status and p.major_status.known and p.major_status.value not in {status,'none'}:raise Contradiction('status_removal_mismatch')
            self._assign(p,'major_status','none',e);p.status_counters={}
        elif change in {'apply','replace'}:
            if status not in MAJOR_STATUS or status in {'none','unknown'}:raise Deferred('major_status_unknown')
            if change!='replace' and p.major_status.known and p.major_status.value not in {'none',status}:raise Contradiction('conflicting_major_status')
            self._assign(p,'major_status',status,e)
            for k,v in a.get('counters',{}).items():p.status_counters[k]=fact(v,evidence_link(e))
        else:raise Deferred('status_change_unknown')

    def _item(self,state,p,e,record):
        ref=e.canonical_references.get('item');a=e.attributes
        if e.event_type=='item_activation':
            if not ref:raise Deferred('item_identity_unknown')
            if p.item.status.known and p.item.status.value in {'none','consumed','transferred'}:raise Contradiction('activation_without_current_item')
            self._consistent_fact(p.item,'identity',ref,e)
            p.item.status=Fact(provenance=[evidence_link(e)])  # Post-activation presence is unknown.
            observation={'item':deepcopy(ref),'evidence':evidence_link(e)}
            p.item.revealed.append(observation);p.item.activations.append(observation)
            # No implicit stat increase or item consumption.
            return
        change=a.get('change')
        if change in {'consume','remove','transfer'}:
            if p.item.status.known and p.item.status.value in {'none','consumed','transferred'}:raise Contradiction('item_already_absent')
            observed=ref or (p.item.identity.value if p.item.identity.known else None)
            if ref and p.item.identity.known and p.item.identity.value and p.item.identity.value['canonical_id']!=ref['canonical_id']:raise Contradiction('item_change_identity_mismatch')
            if change=='transfer':
                if not observed:raise Deferred('transferred_item_unknown')
                target=self._resolve(state,e,record,role='target')
                if target.pokemon_instance_id==p.pokemon_instance_id:raise Contradiction('item_transfer_to_self')
                if target.item.status.known and target.item.status.value=='known' and not a.get('replace_target_item'):raise Contradiction('target_item_already_held')
                self._assign(target.item,'identity',observed,e);self._assign(target.item,'status','known',e)
                target.item.revealed.append({'item':deepcopy(observed),'evidence':evidence_link(e)})
                target.item.changes.append({'change':'received','from_instance_id':p.pokemon_instance_id,'evidence':evidence_link(e)})
            self._assign(p.item,'identity',None,e)
            self._assign(p.item,'status',{'consume':'consumed','remove':'none','transfer':'transferred'}[change],e)
        elif change in {'replace','reveal'}:
            if not ref:raise Deferred('item_identity_unknown')
            if change=='reveal':self._consistent_fact(p.item,'identity',ref,e)
            else:self._assign(p.item,'identity',ref,e)
            self._assign(p.item,'status','known',e)
            p.item.revealed.append({'item':deepcopy(ref),'evidence':evidence_link(e)})
        else:raise Deferred('item_change_unknown')
        p.item.changes.append({'change':change,'item':deepcopy(ref),'evidence':evidence_link(e)})

    def _transform(self,state,p,e):
        a=e.attributes;identity=a.get('identity');mechanic=a.get('mechanic')
        if not isinstance(identity,dict) or not identity.get('canonical_identity'):raise Deferred('observed_transformation_variant_unknown')
        if mechanic is None:raise Deferred('transformation_mechanic_unknown')
        before=deepcopy(p.species.value) if p.species.known else None
        self._assign(p,'species',identity,e);self._assign(p,'current_variant',identity['canonical_identity'],e)
        p.transformations.append({'mechanic':mechanic,'before':before,'after':deepcopy(identity),'evidence':evidence_link(e)})
        p.current_types=Fact(provenance=[evidence_link(e)])
        # Original identity, instance ID, item history, HP and location survive.
        team=state.sides[p.side_id]
        if mechanic=='mega_evolution':
            if team.resources['mega_evolution'].known and team.resources['mega_evolution'].value is True:
                raise Contradiction('mega_resource_already_observed_used')
            team.resources['mega_evolution']=fact(True,evidence_link(e))
            # A newly observed form cannot establish that the prior ability
            # persists. Keep its revelation history, await the new observation.
            p.ability.current=Fact(provenance=[evidence_link(e)])
            p.ability.suppressed=Fact(provenance=[evidence_link(e)])
        # Transformation is not evidence for a hidden stone or alternate choice.

    def _field_event(self,state,e):
        a=e.attributes;kind=e.event_type
        if kind=='weather_change':
            name=a.get('weather')
            if name not in WEATHER:raise Deferred('weather_identity_unknown')
            effect=state.weather
            if a.get('change')=='resume' and 'weather_suppression' in state.global_effects:
                self._assign(state.global_effects['weather_suppression'],'active',False,e)
            if name=='disabled' and effect.kind.known:
                state.global_effects.setdefault('weather_suppression',Effect()).kind=deepcopy(effect.kind)
                self._assign(state.global_effects['weather_suppression'],'active',True,e)
        elif kind=='terrain_change':
            name=a.get('terrain')
            if name not in TERRAIN:raise Deferred('terrain_identity_unknown')
            effect=state.terrain
        elif kind=='trick_room_change':name='trick_room';effect=state.trick_room
        else:
            side=self._side(state,e.side);name=a.get('condition')
            if not isinstance(name,str) or not name:raise Deferred('side_condition_unknown')
            if a.get('category')=='hazard':
                layers=a.get('layers')
                if a.get('change') in {'end','expire','remove'}:layers=0
                if not isinstance(layers,int) or isinstance(layers,bool) or layers<0:raise Deferred('hazard_layers_unknown')
                side.hazards[name]=fact(layers,evidence_link(e));return
            effect=side.conditions.setdefault(name,Effect())
        self._effect(effect,name,e,state)

    def _effect(self,effect,name,event,state):
        a=event.attributes;change=a.get('change')
        if change in {'end','expire','remove'}:
            self._assign(effect,'active',False,event)
            self._assign(effect,'kind','none' if effect is state.weather or effect is state.terrain else name,event)
            effect.duration=Duration()
            self._assign(effect.duration,'remaining',0,event)
        elif change in {'start','change','replace','suppress','resume','observe'}:
            if change=='observe' and (effect.kind.known and effect.kind.value!=name or effect.active.known and not effect.active.value):
                raise Contradiction('observed_effect_conflicts_with_current_state')
            if name=='unknown':
                effect.active=Fact(provenance=[evidence_link(event)]);effect.kind=Fact(provenance=[evidence_link(event)])
            else:
                self._assign(effect,'active',name not in {'none','disabled'},event)
                self._assign(effect,'kind',name,event)
            if change!='observe':
                self._assign(effect,'initiated_by',{'event_id':event.event_id,'turn':state.turn.value if state.turn.known else None},event)
                effect.duration=Duration()
            duration=a.get('duration',{})
            if not isinstance(duration,dict):raise Contradiction('invalid_duration')
            for key,value in duration.items():
                if key in {'remaining','expires_at_turn'}:
                    if not isinstance(value,int) or isinstance(value,bool) or value<0:raise Contradiction('invalid_duration_count')
                    self._assign(effect.duration,key,value,event)
                elif key=='timing':
                    if value not in {'turn_start','turn_end'}:raise Contradiction('unsupported_effect_timing')
                    self._assign(effect.duration,'timing',value,event)
                elif key=='modifiers':self._assign(effect.duration,'modifiers',value,event)
            if effect.duration.remaining.known and effect.duration.remaining.value==0 and effect.active.known and effect.active.value:
                raise Contradiction('active_effect_with_zero_remaining')
        else:raise Deferred('effect_change_unknown')

    def _set_turn(self,state,turn,event,*,tick):
        if not isinstance(turn,int) or isinstance(turn,bool) or turn<1:raise Contradiction('invalid_turn')
        previous=state.turn.value if state.turn.known else None
        if previous is not None and turn<previous:raise Contradiction('turn_regression')
        self._assign(state,'turn',turn,event)
        if tick and previous is not None and turn>previous:
            if turn==previous+1:
                self._tick_effects(state,event,previous,'turn_end')
                self._tick_effects(state,event,turn,'turn_start')
            else:
                for effect in self._effects(state):
                    if effect.active.known and effect.active.value and (effect.duration.remaining.known or effect.duration.expires_at_turn.known):
                        effect.duration.remaining=Fact(provenance=[evidence_link(event)])
                        effect.duration.expires_at_turn=Fact(provenance=[evidence_link(event)])
        # A repeated heading, frame, phase or same-turn boundary never ticks.

    def _effects(self,state):
        yield state.weather;yield state.terrain;yield state.trick_room
        yield from state.global_effects.values()
        for side in state.sides.values():
            yield from side.conditions.values();yield from side.temporary_effects.values()
        for p in state.pokemon.values():yield from p.volatile.values()

    def _tick_effects(self,state,event,turn,boundary):
        for effect in self._effects(state):
            duration=effect.duration
            if not effect.active.known or effect.active.value is not True or not duration.timing.known or duration.timing.value!=boundary:continue
            if duration.last_tick.known and duration.last_tick.value[1]>=turn:continue
            initiated=effect.initiated_by.value if effect.initiated_by.known else None
            if initiated and initiated['turn'] is not None and (initiated['turn']>turn or boundary=='turn_start' and initiated['turn']==turn):continue
            expired=False
            if duration.remaining.known:
                value=max(0,duration.remaining.value-1)
                self._assign(duration,'remaining',value,event,derived=True);expired=value==0
            if duration.expires_at_turn.known and turn>=duration.expires_at_turn.value:expired=True
            if expired:
                self._assign(effect,'active',False,event,derived=True)
                if effect is state.weather or effect is state.terrain:self._assign(effect,'kind','none',event,derived=True)
            self._assign(duration,'last_tick',[boundary,turn],event,derived=True)

    def _available(self,state,event):
        for side in state.sides.values():
            pokemon=[state.pokemon[i] for i in side.party_instance_ids]
            if side.party_complete.known and side.party_complete.value and all(p.fainted.known for p in pokemon):
                provenance={'event_id':event.event_id,'rule':'complete_party_and_individual_faint_facts',
                            'party_completeness':asdict(side.party_complete),
                            'fainted_facts':{p.pokemon_instance_id:asdict(p.fainted) for p in pokemon}}
                side.remaining_available=fact(sum(not p.fainted.value for p in pokemon),provenance,'derived')
            else:side.remaining_available=Fact()
