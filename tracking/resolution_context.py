"""Sequential, evidence-backed resolution projection over StateEngine receipts.

The mutable dictionaries here are short-lived resolution contexts, never battle
state. All HP, identity, stages and event admission remain owned by StateEngine.
A parent action survives banners/stat messages; an immediate source is scoped to
its documented recipient and effect, and can yield back to the parent.
"""
from collections import defaultdict
from copy import deepcopy
from .hp_causes import ADMITTED,event_time,resolve_hits,battle_message


def sequential_resolutions(engine, *, stable_seconds=.4, dense_samples=None, mechanics=None, endpoint_samples=None):
    return _Projection(engine,stable_seconds,dense_samples or {},mechanics or {},endpoint_samples or []).run()


class _Projection:
    def __init__(self,engine,stable,dense,mechanics,endpoint_samples):
        if stable<=0:raise ValueError('stable_seconds must be positive')
        from speed_order.core import knowledge
        self.kb=knowledge();self.engine=engine;self.stable=stable;self.dense=dense;self.mechanics=mechanics
        self.endpoint_samples=endpoint_samples
        self.carry={};self.entries=[]
        self.records=sorted((r for r in engine.history if r.ordering and not r.retracted),key=lambda r:tuple(r.ordering['key']))
        self.events=[r.bindings.get('resolved_event') or r.event for r in self.records]
        self.index={e['event_id']:i for i,e in enumerate(self.events)}
        self.numeric={};self.notice_holders={}
        for pid,p in engine.state.pokemon.items():
            for o in p.hp.observations:
                if 'unit' in o and o['evidence']['event_id'] in self.index:self.numeric[o['evidence']['event_id']]=(pid,o)
                if o.get('event_id'):self.notice_holders[o['event_id']]=o.get('source_instance_id')
        self.history=defaultdict(list);self.epoch=defaultdict(int);self.slot_identity={}
        self.actions=[];self.sources=[];self.components=[];self.open={};self.targets=[];self.loose_steps=[]
        self.parent=None;self.pending=[];self.root=None;self.stat_source=None;self.pivot_side=None
        self.global_gaps=[r.event['event_id'] for r in engine.history if not r.retracted and not r.ordering
                          and r.event['event_type'] in {'move_execution','hp_change','ability_activation','item_activation','coverage_observation'}]

    def actor(self,i):return self.records[i].bindings.get('actor',{}).get('pokemon_instance_id')
    def admitted(self,i):return self.records[i].application_status in ADMITTED
    def trace(self,i):
        if i is None or i>=len(self.events):return None
        e=self.events[i]
        return dict(event_id=e['event_id'],time=event_time(e),event_type=e['event_type'],evidence=deepcopy(e['evidence']))
    def previous(self,pid,i):
        t=event_time(self.events[i])
        observed=next((s for s in reversed(self.history[pid]) if s['epoch']==self.epoch[pid] and
                     (t is None or s['time'] is not None and s['time']<t)),None)
        return observed or self.carry.get(pid)

    def entry(self,i,pid):
        """Same-instance carry is a derivation, never a fabricated HUD read."""
        prior=self.history[pid][-1] if self.history[pid] else None
        supported=self.actor(i)==pid and self.admitted(i)
        value=None
        if prior and supported:
            tail=[]
            for sample in reversed(self.history[pid]):
                if sample['value']!=prior['value'] or sample['epoch']!=prior['epoch']:break
                if tail and tail[-1]['time']-sample['time']>2.1:break
                tail.append(sample)
            settled=bool(len(tail)>=2 and tail[0]['time']-tail[-1]['time']>=self.stable-1e-7)
            full=prior['value']==(prior['maximum'] if prior['unit']=='absolute' else 100)
            intervening=self.events[prior['i']+1:i]
            uncertain=any(e['event_type'] in {'unknown','coverage_observation'} or
                e['event_type'] in {'hp_change','ability_activation','item_activation'} and
                self.actor(self.index[e['event_id']])==pid for e in intervening)
            # A merely possible Regenerator never changes the carried value.
            # An observed unresolved effect invalidates it until numeric evidence.
            explicit_pair=self.events[prior['i']]['event_type']=='hp_change' and prior['observation'].get('baseline_kind')=='explicit_endpoint_pair'
            if not uncertain and (settled or full or explicit_pair):value=dict(prior,epoch=self.epoch[pid],basis='derived_same_instance_carry',
                entry_event_id=self.events[i]['event_id'])
        self.carry[pid]=value
        self.entries.append(dict(entry_event_id=self.events[i]['event_id'],pokemon_instance_id=pid,
            initial_full_hp_hypothesis=dict(value=100,unit='displayed_percent',status='conditional_unestablished',
                usable_as_numeric_baseline=False) if not prior else None,
            carried_hp=value['value'] if value else None,carry_provenance=self.trace(prior['i']) if value else None,
            status='derived_same_instance_carry' if value else 'numeric_baseline_unresolved',
            confirmation=None))
    def step(self,i,kind=None,source=None,affected=None,**extra):
        parent=self.parent
        values=parent['resolution_steps'] if parent else self.loose_steps
        value=dict(step_id=self.events[i]['event_id']+':step:'+str(len(values)),event_id=self.events[i]['event_id'],
            parent_action_id=parent['event_id'] if parent else None,kind=kind or self.events[i]['event_type'],
            source_instance_id=source['holder'] if source else None,observed_actor_instance_id=self.actor(i),
            immediate_cause_event_id=source['id'] if source else None,
            affected_instance_id=affected,evidence=self.trace(i),**extra)
        values.append(value);return value
    def association(self,source,pid,i,basis):
        if not pid:return
        value=dict(parent_action_id=source['parent']['event_id'] if source.get('parent') else None,
                   source_event_id=source['id'],affected_instance_id=pid,evidence_event_id=self.events[i]['event_id'],
                   basis=basis,damage=None)
        if value not in self.targets:self.targets.append(value)
        if source.get('parent'):source['parent']['target_instance_ids'].add(pid)
    def new_source(self,i,cause,holder,expected=None,direction=None,rule=None,reasons=(),parent=None):
        s=dict(id=self.events[i]['event_id'],i=i,cause=deepcopy(cause),holder=holder,
               expected=set(expected) if expected is not None else None,direction=direction,rule=rule,
               reasons=list(reasons),parent=parent,observed=False,resolved=False,events=[self.events[i]['event_id']],
               baselines={pid:self.previous(pid,i) for pid in self.history},explicit={},components=[])
        self.sources.append(s);return s
    def multi(self,parent):
        if not parent:return False
        cap=self.mechanics.get(parent['source_move']['canonical_id']) or self.kb.resolution_effect(parent['source_move']['canonical_id']) or {}
        if cap.get('hit_range') and cap['hit_range'][-1]>1:return True
        start=parent['_i']
        end=next((j for j in range(start+1,len(self.events)) if self.events[j]['event_type']=='move_execution'),len(self.events))
        return any(self.admitted(j) and self.events[j]['event_type']=='multi_hit' and
                   self.events[j]['attributes'].get('hits',0)>1 for j in range(start+1,end))
    def close_component(self,c,i):
        if c['end'] is None:c['end']=i
        if self.open.get(c['pid']) is c:self.open.pop(c['pid'])
    def close_parent(self,i):
        if self.parent:
            self.parent['completion_boundary']=self.trace(i)
            self.parent['_end']=i
        for c in list(self.open.values()):self.close_component(c,i)
        self.parent=None;self.pending=[];self.root=None;self.stat_source=None;self.pivot_side=None
    def plateau(self,c):
        tail=[];previous=None
        for sample in reversed(c['samples']):
            if sample['value']!=c['samples'][-1]['value'] or sample['time'] is None:break
            if previous:
                if previous['time']-sample['time']>2.1:break
                if any(g>sample['i'] and g<previous['i'] for g in c['hp_gaps']):break
            tail.append(sample);previous=sample
        times=[s['time'] for s in tail]
        return bool(len(set(times))>=2 and max(times)-min(times)>=self.stable-1e-7),list(reversed(tail))
    def add_parent(self,i):
        self.close_parent(i);e=self.events[i];ref=e['canonical_references'].get('move') or {}
        p=dict(event_id=e['event_id'],parent_action_id=e['event_id'],source_move=deepcopy(ref),
               actor_instance_id=self.actor(i),target_instance_ids=set(),episode_ids=[],resolution_steps=[],
               evidence=self.trace(i),admitted=self.admitted(i),completion_boundary=None,_i=i,_end=None)
        fact=self.kb.facts.get('moves',{}).get(ref.get('canonical_id'),{})
        p['move_classification_evidence']=dict(category=fact.get('category'),evidence_type=fact.get('evidence_type'),
            source=deepcopy(self.kb.facts.get('source')),knowledge_snapshot=self.kb.snapshot_id)
        p['_rule']=self.kb.resolution_effect(ref.get('canonical_id')) or {}
        p['_category']=fact.get('category') or p['_rule'].get('category')
        if not fact.get('category') and p['_rule'].get('category'):
            p['move_classification_evidence'].update(category=p['_category'],resolution_rule=deepcopy(p['_rule']))
        reasons=[]
        if not self.admitted(i) or not self.actor(i):reasons.append('source_event_not_admitted_or_bound')
        if p['_rule'].get('effect')=='struggle' and e['attributes'].get('effect_outcome') in {'failed','blocked','selected'}:
            reasons.append('blocked_or_failed_effect')
        source=self.new_source(i,dict(kind='move',source=ref),self.actor(i),parent=p,reasons=reasons)
        source['category']=p['_category'];p['_source']=source
        self.parent=p;self.actions.append(p);self.step(i,source=source)
        explicit=e['attributes'].get('target_instance_id')
        if explicit and not e['attributes'].get('target_basis'):
            source['explicit'][explicit]='down';self.association(source,explicit,i,'explicit_target_evidence')

    def banner(self,i):
        e=self.events[i];kind=e['event_type'].split('_')[0];ref=e['canonical_references'].get(kind) or {}
        holder=self.actor(i);rule=self.kb.resolution_effect(ref.get('canonical_id'))
        if rule and rule.get('timing')=='turn_end':self.close_parent(i)
        reasons=[];expected=None;direction=None
        if not self.admitted(i) or not holder:reasons.append('activation_holder_unresolved')
        if rule and rule.get('hp_effect') is False:
            s=self.new_source(i,dict(kind=kind,source=ref),holder,expected=[holder] if holder else [],rule=rule,parent=self.parent,reasons=reasons)
            self.stat_source=s;self.step(i,source=s,effect_semantics=rule);return
        if rule:
            direction=rule.get('direction')
            if rule.get('recipient')=='holder':expected=[holder] if holder else None
            elif rule.get('recipient')=='parent_actor':
                expected=[self.parent['actor_instance_id']] if self.parent and self.parent['actor_instance_id'] else None
                if not self.parent or holder not in self.parent['target_instance_ids']:reasons.append('contact_trigger_target_not_observed')
                if not self.parent or not self.parent['_rule'].get('contact'):reasons.append('contact_mechanics_not_confirmed')
            if rule.get('requires_parent_actor') and (not self.parent or holder!=self.parent['actor_instance_id']):
                reasons.append('post_attack_holder_not_parent_actor')
        else:reasons.append('activation_hp_semantics_unknown')
        s=self.new_source(i,dict(kind=kind,source=ref),holder,expected=expected,direction=direction,rule=rule,parent=self.parent,reasons=reasons)
        self.activate(s,i);self.step(i,source=s,effect_semantics=rule)

    def activate(self,s,i):
        # Only a settled reaction can be popped before another potentially
        # competing source. Two banners before one HP animation remain rivals.
        for older in self.pending:
            affected=older['expected']
            overlap=affected is None or s['expected'] is None or bool(affected&s['expected'])
            if not overlap:continue
            comps=[c for c in older['components'] if c['samples']]
            if comps and all(self.plateau(c)[0] for c in comps):older['resolved']=True
        for pid,c in list(self.open.items()):
            if s['expected'] is None or pid in s['expected']:self.close_component(c,i)
        self.pending=[x for x in self.pending if not x['resolved']]+[s]
        self.root=s if self.parent is None else self.root

    def notice(self,i):
        e=self.events[i];a=e['attributes'];cause=a.get('cause');affected=self.actor(i)
        if not cause:
            if a.get('recovery_source_status')=='duplicate_grassy_recovery_in_resolution':self.close_parent(i)
            if self.parent and affected:
                source=self.parent['_source']
                if ((a.get('direction') in {'down','zero'} and source.get('category') in {'Physical','Special'} and affected!=source['holder'])
                    or a.get('effect_of')==self.parent['event_id']):
                    source['explicit'][affected]=a.get('direction')
                    self.association(source,affected,i,'literal_recipient_outcome')
            self.step(i,affected=affected);return
        holder=self.notice_holders.get(e['event_id'])
        if cause['kind'] in {'move_recoil','self_hp_cost','confusion_self_damage','struggle_recoil'}:holder=affected
        ref=(cause.get('source') or {}).get('canonical_id')
        if (cause['kind']=='move' and self.parent and ref==self.parent['source_move'].get('canonical_id')
            and holder==self.parent['actor_instance_id']):
            src=self.parent['_source'];src['explicit'][affected]=a.get('direction');src['events'].append(e['event_id'])
            self.association(src,affected,i,'explicit_move_effect_notice');self.step(i,source=src,affected=affected);return
        matches=[s for s in self.pending if ref and (s['cause'].get('source') or {}).get('canonical_id')==ref and
                 s['holder']==holder and not s['resolved']]
        if len(matches)==1:
            src=matches[0];src['expected']={affected};src['direction']=a.get('direction');src['events'].append(e['event_id'])
            # Literal source/recipient evidence establishes the occurrence even
            # if generic contact/profile prerequisites were not available.
            src['reasons']=[r for r in src['reasons'] if r not in {'contact_trigger_target_not_observed','contact_mechanics_not_confirmed','activation_hp_semantics_unknown'}]
            self.step(i,source=src,affected=affected);return
        if cause['kind'] in {'status','weather','entry_hazard','instant_faint','confusion_self_damage','grassy_terrain'}:self.close_parent(i)
        reasons=[]
        if not self.admitted(i) or not affected:reasons.append('effect_recipient_unresolved')
        if cause.get('holder') and holder is None:reasons.append('source_holder_instance_unresolved')
        src=self.new_source(i,cause,holder,expected=[affected] if affected else [],direction=a.get('direction'),
                            rule=self.kb.resolution_effect(ref) if ref else None,parent=self.parent,reasons=reasons)
        if cause['kind']=='grassy_terrain' and self.admitted(i) and affected:
            # The game can finish the HP animation before displaying its named
            # recovery message. Rebind that one observed increase, bounded by
            # the preceding Battle Message, rather than creating another heal.
            boundary=max((j for j in range(i) if battle_message(self.events[j]) or
                self.events[j]['event_type'] in {'phase_observation','turn_boundary','item_activation','ability_activation'}),default=-1)
            candidates=[c for c in self.components if c['pid']==affected and c['direction']=='up'
                and c['changes'] and all(self.index[o['evidence']['event_id']]>boundary for o in c['changes'])]
            if len(candidates)==1:
                c=candidates[0];old=c['source'];parent=c['parent']
                if old:old['components'].remove(c)
                steps=parent['resolution_steps'] if parent else self.loose_steps
                if c['step'] in steps:steps.remove(c['step'])
                c.update(source=src,choices=[src],source_key=src['id'],parent=None,valid=True,named_recovery_animation=True,
                    reasons=[r for r in c['reasons'] if r not in {'no_active_resolution_source',
                        'competing_immediate_causes','effect_recipient_scope_conflict',
                        'move_effect_or_self_cost_not_established','immediate_effect_direction_conflict',
                        'literal_effect_direction_conflict','blocked_or_failed_effect'}])
                src['components'].append(c);src['observed']=True;src['baselines'][affected]=c['before']
                c['step']=self.step(i,'hp_resolution',src,affected,
                    binding_basis='named_recovery_after_observed_hp_animation',
                    hp_event_ids=[o['evidence']['event_id'] for o in c['changes']])
        self.activate(src,i);self.step(i,source=src,affected=affected)

    def primary_candidate(self,pid,direction):
        if not self.parent or self.parent.get('_hp_done'):return None
        s=self.parent['_source']
        if s['explicit'].get(pid) in {direction,'zero'}:return s
        if direction!='down' or s.get('category') not in {'Physical','Special'}:return None
        # Same team is permitted. Self-loss without a supported self-target/
        # self-cost occurrence still has multiple interpretations.
        if pid==s['holder']:return None
        return s
    def choose(self,pid,direction,i):
        primary=self.primary_candidate(pid,direction)
        pending=[s for s in self.pending if not s['resolved'] and (s['expected'] is None or pid in s['expected'])]
        # Observed Struggle target loss establishes successful use. A later
        # observed loss on its own user is a separate cause, never target-damage
        # recoil or confusion. The 1/4-max rule supplies no fabricated endpoint.
        if (not pending and self.parent and self.parent['_rule'].get('effect')=='struggle'
                and self.parent['admitted'] and pid==self.parent['actor_instance_id'] and direction=='down'
                and not self.parent.get('_blocked_targets') and
                self.events[self.parent['_i']]['attributes'].get('effect_outcome') not in {'failed','blocked','selected'}):
            damage=[c for c in self.parent['_source']['components'] if c['pid']!=pid and c['valid'] and c['direction']=='down']
            if damage:
                source=next((s for s in self.sources if s['parent'] is self.parent and s['cause']['kind']=='struggle_recoil'),None)
                if source is None:
                    source=self.new_source(self.parent['_i'],dict(kind='struggle_recoil',source=self.parent['source_move']),
                        pid,expected=[pid],direction='down',rule=self.parent['_rule'],parent=self.parent)
                    source['events']+= [o['evidence']['event_id'] for c in damage for o in c['changes']]
                return [source]
        compatible=[s for s in pending if s['direction'] is None or s['direction']==direction or s['direction']=='zero']
        if compatible:
            # A documented same-target reaction during a multi-hit action can
            # overlap resumed direct hits; absence of a hit boundary is not an
            # excuse to assign the whole interval to the latest banner.
            if primary and self.multi(self.parent) and pid in self.parent['target_instance_ids']:
                compatible=compatible+[primary]
                self.parent.setdefault('_uncertain_totals',set()).add(pid)
            if primary and any(s['expected'] is None for s in compatible) and primary not in compatible:
                compatible.append(primary)
            return compatible
        if pending:
            if primary and self.multi(self.parent) and all(s['observed'] and all(self.plateau(c)[0] for c in s['components']) for s in pending):
                for s in pending:s['resolved']=True
                return [primary]
            return pending+([primary] if primary else [])
        if primary:
            yielding=[s for s in self.pending if s['observed'] and not s.get('yielded') and s['expected'] is not None and pid not in s['expected']]
            if yielding:
                self.step(i,'resume_parent',source=primary,affected=pid,after_source_event_ids=[s['id'] for s in yielding])
                for s in yielding:s['yielded']=True
            return [primary]
        # Preserve a candidate for diagnostics, but never declare unsupported
        # status-move damage, unexplained self-cost or healing to be direct hits.
        return [self.parent['_source']] if self.parent else ([self.root] if self.root else [])

    def sample(self,i,pid,o):
        e=self.events[i];t=event_time(e)
        sample=dict(i=i,time=t,value=o['after'],unit=o['unit'],maximum=o.get('maximum'),
                    event_id=e['event_id'],epoch=self.epoch[pid],observation=o,
                    confidence=(e['attributes'].get('hp') or {}).get('confidence',e.get('ocr_confidence') or 0))
        for entry in reversed(self.entries):
            if entry['pokemon_instance_id']==pid and entry['confirmation'] is None:
                start=self.index[entry['entry_event_id']]
                intervening=any(x['event_type'] in {'move_execution','hp_change','ability_activation','item_activation'}
                    for x in self.events[start+1:i])
                entry['confirmation']=dict(evidence=self.trace(i),value=o['after'],outcome=
                    'first_read_after_resolution_not_entry_confirmation' if intervening else
                    'confirmed' if entry['carried_hp']==o['after'] else 'corrected' if entry['carried_hp'] is not None else 'observed')
                break
        slot=e['attributes'].get('slot')
        if slot:self.slot_identity[(e['side'],slot)]=pid
        if not o.get('delta'):
            full=sample['value']==(sample['maximum'] if sample['unit']=='absolute' else 100)
            active=self.pending+([self.parent['_source']] if self.parent else [])
            if full:
                for source in active:
                    if source['baselines'].get(pid) is None and (source['expected'] is None or pid in source['expected']):
                        source['baselines'][pid]=dict(sample,basis='observed_full_scale_before_decrease')
            c=self.open.get(pid)
            if c and c['end'] is None:c['samples'].append(sample)
            self.history[pid].append(sample);return
        direction='up' if o['delta']>0 else 'down'
        choices=self.choose(pid,direction,i)
        valid=(len(choices)==1 and not choices[0]['reasons'])
        if choices and choices[0]['cause']['kind']=='move':
            valid=valid and choices[0] is self.primary_candidate(pid,direction)
        elif choices:
            valid=valid and (choices[0]['direction'] in {None,direction,'zero'}) and (choices[0]['expected'] is None or pid in choices[0]['expected'])
        source=choices[0] if len(choices)==1 else None
        # Ambiguous intervals retain every candidate and get one ownership
        # record. Membership is never duplicated to inflate attribution counts.
        key=(source['id'] if source else 'ambiguous:'+','.join(sorted(s['id'] for s in choices)) if choices else 'unscoped:'+e['event_id'])
        c=self.open.get(pid)
        if c and (c['source_key']!=key or c['valid']!=valid or c['direction']!=direction):self.close_component(c,i);c=None
        if c is None:
            if source:
                existing=[x for x in source['components'] if x['pid']==pid]
                base=(self.history[pid][-1] if existing and self.history[pid] else source['baselines'].get(pid))
            else:base=self.history[pid][-1] if self.history[pid] else None
            c=dict(pid=pid,source=source,choices=choices,source_key=key,parent=self.parent,
                   before=base,start=i,end=None,samples=[],changes=[],valid=valid,reasons=[],hp_gaps=[],direction=direction)
            if not choices:c['reasons'].append('no_active_resolution_source')
            if len(choices)>1:c['reasons'].append('competing_immediate_causes')
            if source and not valid:
                c['reasons'].extend(source['reasons'])
                if source['cause']['kind']=='move':c['reasons'].append('move_effect_or_self_cost_not_established')
                else:
                    if source['expected'] is not None and pid not in source['expected']:c['reasons'].append('effect_recipient_scope_conflict')
                    if source['direction'] not in {None,direction,'zero'}:
                        c['reasons'].append('immediate_effect_direction_conflict')
                        if self.events[source['i']]['event_type']=='hp_change':c['reasons'].append('literal_effect_direction_conflict')
            if source:source['components'].append(c)
            self.components.append(c);self.open[pid]=c
            c['step']=self.step(i,'hp_resolution',source,pid,candidate_source_event_ids=[x['id'] for x in choices])
        c['samples'].append(sample);c['changes'].append(o);self.history[pid].append(sample)
        if source:source['observed']=True
        if valid and source and source['parent'] and source['cause']['kind']=='move':
            self.association(source,pid,i,'bound_hud_change_in_unique_resolution')

    def gap(self,i):
        e=self.events[i];a=e['attributes'];kind=e['event_type']
        if kind=='hud_observation':
            pid=self.actor(i) or self.slot_identity.get((e['side'],a.get('slot')))
            if pid and pid in self.open:self.open[pid]['hp_gaps'].append(i)
            if not self.admitted(i) and (a.get('hp') or {}).get('value') is not None:
                if pid:
                    self.epoch[pid]+=1
                    if pid in self.open:self.open[pid]['reasons'].append('affected_identity_gap')
        else:
            for c in self.open.values():c['reasons'].append('event_coverage_gap' if kind=='coverage_observation' else 'unknown_event_in_resolution')
            active=self.pending+([self.root] if self.root else [])+([self.parent['_source']] if self.parent else [])
            for s in {s['id']:s for s in active}.values():
                s['reasons'].append('event_coverage_gap' if kind=='coverage_observation' else 'unknown_event_in_resolution')

    def run(self):
        for i,e in enumerate(self.events):
            kind=e['event_type'];a=e['attributes'];actor=self.actor(i)
            if (self.root and self.root['cause']['kind']=='confusion_self_damage'
                    and e['event_id']!=self.root['id'] and battle_message(e)):
                self.close_parent(i)
            if kind=='move_execution':self.add_parent(i)
            elif kind in {'ability_activation','item_activation'}:self.banner(i)
            elif kind=='hp_change' and a.get('qualitative_only'):self.notice(i)
            elif kind=='volatile_change' and a.get('condition')=='confusion':
                self.close_parent(i)
                self.step(i,affected=actor,attributes=deepcopy(a))
            elif kind in {'switch_out','send_out'}:
                pivot=bool(self.parent and (self.parent['_rule'].get('pivot') or a.get('effect_of')==self.parent['event_id']))
                follows=pivot and (kind=='switch_out' and actor==self.parent['actor_instance_id'] or
                                  kind=='send_out' and self.pivot_side==e['side'])
                if follows:
                    if kind=='switch_out':
                        self.pivot_side=e['side'];self.parent['_hp_done']=i
                        for c in list(self.open.values()):self.close_component(c,i)
                    self.step(i,'pivot_'+kind,source=self.parent['_source'],affected=actor,
                              switching_instance_id=actor)
                else:self.close_parent(i)
                if actor:
                    self.epoch[actor]+=1
                    if kind=='send_out':self.entry(i,actor)
                    else:self.carry.pop(actor,None)
                    for key in [key for key,value in self.slot_identity.items() if value==actor]:self.slot_identity.pop(key)
            elif kind=='phase_observation' and (a.get('resolution_cycle_start') or a.get('phase')=='end_of_turn'):
                self.close_parent(i)
            elif kind in {'turn_boundary','command_checkpoint'}:
                if not (self.root and self.root['cause']['kind']=='confusion_self_damage'):self.close_parent(i)
            elif kind in {'coverage_observation','unknown'}:
                if kind=='coverage_observation' and a.get('fields')==['hp']:
                    for c in self.open.values():c['hp_gaps'].append(i)
                else:self.gap(i)
            elif kind=='hud_observation' and e['event_id'] not in self.numeric:self.gap(i)
            elif kind in {'stat_change','critical_hit','effectiveness','multi_hit','move_effect','move_miss','faint','weather_change','terrain_change','status_change'}:
                src=self.parent['_source'] if self.parent else None
                if (kind=='stat_change' and self.stat_source and actor in (self.stat_source['expected'] or set())
                    and set(a.get('stats',[])) and set(a.get('stats',[]))<=set((self.stat_source['rule'] or {}).get('stats',[]))
                    and a.get('direction')=='up'):src=self.stat_source
                target=self.records[i].bindings.get('hp_recipient_instance_id')
                if self.admitted(i):
                    if target and src:self.association(src,target,i,'named_effect_recipient')
                    if kind=='stat_change' and actor and self.parent:
                        if src is self.parent['_source']:self.association(src,actor,i,'bound_stat_effect_recipient')
                    self.step(i,source=src,affected=target or actor,attributes=deepcopy(a))
                if kind=='faint' and self.admitted(i) and actor:
                    c=self.open.get(actor)
                    if c and c['samples'][-1]['value']==0:
                        c['terminal_faint_index']=i;self.close_component(c,i)
                    for key in [key for key,value in self.slot_identity.items() if value==actor]:self.slot_identity.pop(key)
                if kind=='move_effect' and self.parent and (a.get('outcome') in {'blocked','failed'} or a.get('effect') in {'protected_from_attack','wide_guard_received'}):
                    self.parent.setdefault('_blocked_targets',set()).add(actor)
                    if a.get('outcome') in {'blocked','failed'}:self.parent['_source']['reasons'].append('blocked_or_failed_effect')
                if kind=='effectiveness' and a.get('effect')=='immune' and self.parent:
                    self.parent.setdefault('_blocked_targets',set()).add(target)
                if kind=='move_miss' and self.parent and self.admitted(i) and a.get('effect_of')==self.parent['event_id']:
                    self.parent.setdefault('_blocked_targets',set()).add(target)
            if e['event_id'] in self.numeric:
                pid,o=self.numeric[e['event_id']];self.sample(i,pid,o)
        return self.finish()

    def component_result(self,c):
        pid=c['pid'];src=c['source'];samples=c['samples'];before=c['before'];last=samples[-1]
        end=c['end'] if c['end'] is not None else len(self.events)
        if c.get('named_recovery_animation'):
            # Other recipients' recovery notices may hide this HUD. Confirm its
            # final value from later unchanged reads before another possible
            # action/source, without treating that return as a second recovery.
            stop=next((j for j in range(end+1,len(self.events)) if
                self.events[j]['event_type'] in {'move_execution','switch_out','send_out','faint','unknown','coverage_observation','terrain_change'} or
                self.events[j]['event_type'] in {'hp_change','item_activation','ability_activation'} and
                self.actor(j)==pid),len(self.events))
            later=[s for s in self.history[pid] if end<s['i']<stop]
            if later and all(s['value']==last['value'] and s['epoch']==last['epoch'] and
                    s['unit']==last['unit'] and s['maximum']==last['maximum'] for s in later):
                samples=samples+later;last=samples[-1]
        from .resolution_endpoints import supplement_endpoints
        before,last,samples,supplement_basis=supplement_endpoints(self,c,before,last,samples)
        # Plateau checks below use the augmented local copy, never mutate receipts.
        c=dict(c,samples=samples)
        reasons=list(c['reasons'])
        if src:reasons.extend(src['reasons'])
        if not before:reasons.append('pre_action_hp_missing')
        elif any(self.events[j]['event_type'] in {'coverage_observation','unknown'} for j in range(before['i']+1,src['i'] if src else c['start'])):
            reasons.append('baseline_coverage_gap')
        if before and before['epoch']!=last['epoch']:reasons.append('encounter_boundary')
        maxima={x['maximum'] for x in ([before] if before else [])+samples if x['maximum'] is not None}
        if before and (len(maxima)>1 or any(x['unit']!=before['unit'] for x in samples)):
            reasons.append('incompatible_endpoint_units_or_maximum')
        stable,tail=self.plateau(c)
        boundary=self.trace(c['end'])
        confusion_final=bool(src and src['cause']['kind']=='confusion_self_damage'
            and boundary and battle_message(self.events[c['end']]))
        transition=bool(not stable and boundary and boundary['event_type'] in
            {'move_execution','switch_out','send_out','turn_boundary','command_checkpoint'} and
            self.admitted(c['end']) and last['time'] is not None and boundary['time'] is not None and
            0<boundary['time']-last['time']<=.5 and not c['hp_gaps'] and
            last.get('confidence',self.events[last['i']].get('ocr_confidence') or 0)>=.95)
        zero=last['value']==0 and (c.get('terminal_faint_index') is not None or any(self.admitted(j) and self.events[j]['event_type']=='faint' and self.actor(j)==pid
            and last['i']<j<end for j in range(c['start']+1,end)))
        if not stable and not zero and not transition and not confusion_final:reasons.append('final_visible_plateau_unresolved')
        if c['end'] is None and not zero:reasons.append('resolution_window_still_open')
        if self.global_gaps:reasons.append('unordered_possible_cause')
        if src and event_time(self.events[src['i']]) is not None and samples[0]['time']==event_time(self.events[src['i']]):
            reasons.append('source_change_time_tie')
        if c['parent'] and pid in c['parent'].get('_blocked_targets',set()):reasons.append('blocked_or_failed_effect')
        if c['parent'] and pid in c['parent'].get('_uncertain_totals',set()):
            reasons.extend(['same_target_competing_resolution','multi_hit_interrupted_by_same_target_effect'])
        numeric_reasons={'pre_action_hp_missing','encounter_boundary','incompatible_endpoint_units_or_maximum',
            'final_visible_plateau_unresolved','resolution_window_still_open','affected_identity_gap',
            'event_coverage_gap','unknown_event_in_resolution','unordered_possible_cause','same_target_competing_resolution',
            'baseline_coverage_gap','source_change_time_tie','multi_hit_interrupted_by_same_target_effect'}
        complete=not bool(set(reasons)&numeric_reasons)
        return dict(before=before['value'] if before else None,after=last['value'],baseline_basis=before.get('basis','pre_source_observation') if before else 'unknown',
            delta=last['value']-before['value'] if complete else None,unit=last['unit'],
            complete_endpoints=complete,reasons=sorted(set(reasons)),valid=c['valid'] and not (src and src['reasons']),
            endpoints=dict(before=before.get('trace') or self.trace(before['i']) if before else None,
                           after=last.get('trace') or self.trace(last['i'])),
            endpoint_supplement=supplement_basis,
            final_plateau_event_ids=[s['event_id'] for s in tail],
            final_endpoint_basis='observed_zero_then_faint' if zero else 'repeated_visible_hp' if stable else
                'final_observation_before_next_battle_message' if confusion_final else
                'trusted_hp_then_independent_resolution' if transition else 'unresolved',
            resolution_end=self.trace(c['end']),hp_observation_gaps=[self.events[j]['event_id'] for j in c['hp_gaps']],
            segment_event_ids=[o['evidence']['event_id'] for o in c['changes']])

    def finish(self):
        grouped=defaultdict(list)
        for c in self.components:
            src=c['source'];grouped[(src['id'] if src else c['source_key'],c['pid'],c['direction'])].append(c)
        episodes=[]
        for (source_id,pid,direction),cs in grouped.items():
            src=cs[0]['source'];parent=cs[0]['parent'];parts=[self.component_result(c) for c in cs]
            reasons=sorted({r for x in parts for r in x['reasons']})
            complete=all(x['complete_endpoints'] for x in parts)
            valid=all(x['valid'] for x in parts)
            causal_veto={'blocked_or_failed_effect','effect_recipient_scope_conflict','event_coverage_gap',
                'unknown_event_in_resolution','unordered_possible_cause','baseline_coverage_gap','source_change_time_tie',
                'encounter_boundary','affected_identity_gap'}
            valid=valid and not bool(set(reasons)&causal_veto)
            cause=deepcopy(src['cause']) if src and valid else None
            start=src['i'] if src else cs[0]['start']
            eid=source_id+':hp:'+pid
            if sum(sid==source_id and key==pid for sid,key,_ in grouped)>1:eid+=':'+direction
            samples=[]
            for c in cs:
                if c['before']:samples.append(dict(event_id=c['before']['event_id'],time=c['before']['time'],value=c['before']['value']))
                samples.extend(dict(event_id=s['event_id'],time=s['time'],value=s['value']) for s in c['samples'])
            # Duplicate baseline samples belong to components, not extra hits.
            samples=list({s['event_id']:s for s in samples if s['time'] is not None}.values())
            samples.sort(key=lambda s:s['time'])
            critical=[];counts=[];completion_ids=[]
            if parent and src is parent['_source']:
                stop=parent['_end'] if parent['_end'] is not None else len(self.events)
                recipients=parent['target_instance_ids']
                for j in range(parent['_i']+1,stop):
                    re=self.events[j];ra=re['attributes']
                    if not self.admitted(j) or re['event_type'] not in {'critical_hit','multi_hit'}:continue
                    target=ra.get('target_instance_id') or ra.get('affected_instance_id')
                    if target!=pid and not (target is None and len(recipients)==1 and pid in recipients):continue
                    if re['event_type']=='critical_hit':critical.append(dict(event_id=re['event_id'],hit_index=ra.get('hit_index'),time=event_time(re)))
                    elif type(ra.get('hits')) is int:
                        counts.append(ra['hits']);completion_ids.append(re['event_id'])
            count=counts[0] if counts and len(set(counts))==1 else None
            cap=self.mechanics.get((cause or {}).get('source',{}).get('canonical_id'))
            if cap is None and cause and cause['kind']=='move':cap=self.kb.resolution_effect((cause.get('source') or {}).get('canonical_id'))
            dense=self.dense.get(eid);fps=2.;dense_issue=None
            if dense:
                ds=dense.get('samples',[]);fps=dense.get('sample_fps',2.)
                if (not ds or not complete or ds[0]['value']!=parts[0]['before'] or ds[-1]['value']!=parts[-1]['after'] or
                    any(s.get('pokemon_instance_id')!=pid or s.get('unit')!=parts[0]['unit'] or not s.get('evidence') or s.get('confidence',0)<.75 for s in ds)):
                    dense_issue='dense_endpoint_or_identity_mismatch'
                else:samples=ds
            hits=resolve_hits(samples,sampling_fps=fps,capability=cap,hit_count=count,critical_events=critical,
                              baseline_carry_supported=bool(dense and dense.get('baseline_carry_supported')))
            if parent and (self.multi(parent) or bool((cap or {}).get('reference_capable'))):
                hits.update(completion_confirmed=count is not None,completion_event_ids=completion_ids,
                            completion_basis='explicit_hit_count_message' if count is not None else 'unconfirmed')
            if hits['hits']:
                unresolved=[]
                for crit in critical:
                    if crit.get('hit_index') is not None:continue
                    matching=[]
                    for j,hit in enumerate(hits['hits']):
                        following=hits['hits'][j+1].get('damage_begin_time') if j+1<len(hits['hits']) else None
                        if (crit.get('time') is not None and hit.get('end_time') is not None and hit['end_time']<=crit['time']
                            and following is not None and crit['time']<following):matching.append(hit)
                    if len(matching)==1:
                        matching[0]['critical_hit']=True
                        matching[0].setdefault('critical_event_ids',[]).append(crit['event_id'])
                        matching[0]['critical_basis']='message_between_confirmed_hit_boundaries'
                    else:unresolved.append(crit)
                if not unresolved:hits['reasons']=[r for r in hits['reasons'] if r!='critical_hit_hit_index_unknown']
            supported=complete and valid and not reasons
            if not supported or dense_issue:
                hits.update(hits=None,per_hit_damage=None,per_hit_status='unknown')
                hits['reasons'].append(dense_issue or 'complete_causal_action_endpoints_required')
            choices={s['id']:s for c in cs for s in c['choices']}
            delta=sum(p['delta'] for p in parts) if complete else None
            episode=dict(episode_id=eid,source_event_id=source_id,source_event=self.trace(start),
                parent_action_id=parent['event_id'] if parent else None,actor_instance_id=src['holder'] if src else None,
                source_holder_instance_id=src['holder'] if src else None,affected_instance_id=pid,target_instance_id=pid,
                cause=cause,candidate_cause=deepcopy(src['cause']) if src else None,
                candidate_causes=[dict(source_event_id=s['id'],cause=deepcopy(s['cause']),source_instance_id=s['holder'],reasons=s['reasons']) for s in choices.values()],
                cause_event_ids=list(src['events']) if src else list(choices),
                source_move=deepcopy(cause['source']) if cause and cause['kind']=='move' else None,
                parent_move=deepcopy(parent['source_move']) if parent else None,
                before=parts[0]['before'],after=parts[-1]['after'],delta=delta,
                net_endpoint_delta=parts[-1]['after']-parts[0]['before'] if complete else None,
                unit=parts[0]['unit'],resolution_direction=direction,complete_endpoints=complete,affected_target_status='supported' if valid else 'ambiguous',affected_instance_status='supported',
                immediate_cause_status='supported' if valid else 'ambiguous',attribution_status='supported' if supported else 'ambiguous',
                reasons=reasons,critical_hit=True if critical and valid else None,critical_event_ids=[c['event_id'] for c in critical],
                hit_resolution=hits,triggered_by=None,components=parts,
                segment_event_ids=[eid for p in parts for eid in p['segment_event_ids']],
                observed_partial_before=cs[0]['changes'][0]['observed_before'],observed_partial_after=cs[-1]['changes'][-1]['after'],
                endpoints=dict(before=parts[0]['endpoints']['before'],after=parts[-1]['endpoints']['after']),
                final_plateau_event_ids=parts[-1]['final_plateau_event_ids'],final_endpoint_basis=parts[-1]['final_endpoint_basis'],
                hp_observation_gaps=[eid for p in parts for eid in p['hp_observation_gaps']],resolution_end=parts[-1]['resolution_end'],
                effect_semantics=src['rule'] if src else None)
            episodes.append(episode)
            if parent:
                parent['episode_ids'].append(eid)
                for c in cs:c['step'].update(episode_id=eid,attribution_status=episode['attribution_status'])
        # Link only confirmed dense hit boundaries to reaction occurrences.
        # Holder/recipient roles and parent identity are independent of timing.
        for reaction in episodes:
            if (not reaction['cause'] or not reaction['parent_action_id'] or
                (reaction.get('effect_semantics') or {}).get('effect')!='contact_attacker_damage'):continue
            holder=reaction['source_holder_instance_id'];t=reaction['source_event']['time'];matches=[]
            for direct in episodes:
                if direct['parent_action_id']!=reaction['parent_action_id'] or direct['affected_instance_id']!=holder:continue
                if direct['hit_resolution']['per_hit_status']!='supported':continue
                hits=direct['hit_resolution']['hits'] or []
                for j,hit in enumerate(hits):
                    after=hits[j+1].get('damage_begin_time') if j+1<len(hits) else None
                    if t is not None and hit.get('end_time') is not None and hit['end_time']<=t and (after is None or t<after):
                        matches.append(dict(parent_action_id=reaction['parent_action_id'],hit_index=hit['index'],
                            hit_target_instance_id=holder,hit_evidence_ids=hit['evidence_ids']))
            if len(matches)==1:reaction['triggered_by']=matches[0]
        for p in self.actions:
            confirmed=[]
            for episode in episodes:
                if episode['parent_action_id']!=p['event_id'] or not episode['cause'] or episode['cause']['kind']!='move':continue
                for hit in episode['hit_resolution']['hits'] or []:
                    confirmed.append(dict(step_id=p['event_id']+':hit:'+str(hit['index'])+':'+episode['affected_instance_id'],
                        parent_action_id=p['event_id'],kind='confirmed_move_hit',episode_id=episode['episode_id'],
                        source_instance_id=p['actor_instance_id'],affected_instance_id=episode['affected_instance_id'],
                        hit_index=hit['index'],hp_evidence_ids=hit['evidence_ids'],critical_hit=hit['critical_hit'],
                        time=hit.get('end_time'),event_id=p['event_id'],
                        evidence=dict(time=hit.get('end_time'),hp_evidence_ids=hit['evidence_ids'])))
            for step in p['resolution_steps']:
                for episode in episodes:
                    if episode['parent_action_id']==p['event_id'] and (step.get('episode_id')==episode['episode_id'] or step['event_id']==episode['source_event_id']):
                        step['triggered_by']=episode['triggered_by']
            p['confirmed_hits']=confirmed
            p['resolution_steps']=sorted(p['resolution_steps']+confirmed,key=lambda s:(
                (s.get('evidence') or {}).get('time') if (s.get('evidence') or {}).get('time') is not None else float('inf'),
                self.index.get(s.get('event_id'),0)))
            relevant=[o for o in episodes if o['parent_action_id']==p['event_id']]
            p['totals']=dict(direct_damage_by_target={},reaction_damage_by_instance={},healing_by_instance={},unresolved_hp_by_instance={},self_damage=None)
            for o in relevant:
                key='unresolved_hp_by_instance' if not o['cause'] else 'healing_by_instance' if o['resolution_direction']=='up' else 'direct_damage_by_target' if o['cause']['kind']=='move' else 'reaction_damage_by_instance'
                entry=dict(delta=o['delta'],unit=o['unit'],episode_id=o['episode_id'],supported=o['attribution_status']=='supported')
                p['totals'][key].setdefault(o['affected_instance_id'],[]).append(entry)
            own=[o for o in relevant if o['affected_instance_id']==p['actor_instance_id'] and o['delta'] is not None and o['delta']<0 and o['attribution_status']=='supported']
            if own and len({o['unit'] for o in own})==1:p['totals']['self_damage']=dict(amount=-sum(o['delta'] for o in own),unit=own[0]['unit'],episode_ids=[o['episode_id'] for o in own])
            p['target_instance_ids']=sorted(p['target_instance_ids'])
            p['status']='observed_hp_resolution' if relevant else 'no_observed_hp_change'
            p['current_resolution_step']=p['resolution_steps'][-1]['step_id'] if p['resolution_steps'] else None
            for key in list(p):
                if key.startswith('_'):p.pop(key)
        return dict(schema_version=2,policy='sequential-resolution-v1',actions=self.actions,episodes=episodes,
            switch_in_baselines=self.entries,
            target_associations=self.targets,standalone_steps=self.loose_steps,unmapped_changes=[],stable_seconds=self.stable,
            unordered_possible_causes=self.global_gaps)
