"""Factorized, deterministic configuration constraints; independent of OCR/state mutation."""
from copy import deepcopy
from dataclasses import dataclass, field, asdict
import hashlib
import json
from pathlib import Path

PROFILES={'champions-evidence-only-v1','showdown-champions-reference-v1'}
FIELDS=('species','original_form','mega_eligibility','held_item','item_at_start','native_ability',
        'observed_ability','moves','nature','training_allocation','ivs','max_hp','attack','defense',
        'special_attack','special_defense','speed','mechanic_configuration')
OPS={'equal','exclude','candidates','interval','member','slot','conditional','any_of'}

@dataclass
class Constraint:
    constraint_id: str
    instance_id: str
    variable: str
    operation: str
    value: object
    event_ids: list = field(default_factory=list)
    strength: str = 'hard'
    evidence_status: str = 'confirmed'
    rule_id: str | None = None
    rule_profile: str | None = None
    provenance: list = field(default_factory=list)
    prerequisites: list = field(default_factory=list)
    reason: str = 'direct observation'

    def __post_init__(self):
        if not self.event_ids and not self.provenance:self.provenance=[{'source_type':'caller_asserted_constraint','observation_id':self.constraint_id}]
        if self.operation not in OPS or self.strength not in {'hard','provisional','unresolved'}:
            raise ValueError('Invalid constraint')
        if self.operation=='interval' and (not isinstance(self.value,list) or len(self.value)!=2 or
             any(not isinstance(n,(int,float)) or isinstance(n,bool) for n in self.value) or self.value[0]>self.value[1]):
            raise ValueError('Invalid numeric interval')
        if self.operation in {'candidates','exclude','any_of'} and not isinstance(self.value,list):
            raise ValueError('Expected a candidate/alternative list')
        if self.operation=='slot' and (not isinstance(self.value,dict) or type(self.value.get('slot')) is not int or self.value['slot']<1):
            raise ValueError('Invalid move slot')


def empty_domain():
    return {'status':'unknown','value':None,'candidates':None,'interval':None,'members':[],
            'slots':{},'exclusions':[],'eliminations':[],'constraints':[],'conflicts':[],'unresolved':[],
            'provisional':None}


def domain(constraints):
    """Intersect one factor without enumerating joint configurations."""
    result=empty_domain();candidates=None;bounds=None;members=[];slots={};exclusions=[]
    equal_seen=False;last_consistent=None
    for c in constraints:
        result['constraints'].append(c['constraint_id'])
        op,value=c['operation'],c['value']
        if op in {'conditional','any_of'} or c['strength']=='unresolved':
            result['unresolved'].append(deepcopy(c));continue
        old=deepcopy({'candidates':candidates,'interval':bounds,'members':members,'slots':slots})
        reason=None
        if op=='equal':
            equal_seen=True
            candidates=[value] if candidates is None else [v for v in candidates if v==value]
            if isinstance(value,(int,float)) and not isinstance(value,bool):
                bounds=[value,value] if bounds is None else [max(bounds[0],value),min(bounds[1],value)]
        elif op=='candidates':
            candidates=list(dict.fromkeys(value)) if candidates is None else [v for v in candidates if v in value]
        elif op=='exclude':
            for v in value:
                if v not in exclusions:exclusions.append(v)
            if candidates is not None:candidates=[v for v in candidates if v not in value]
        elif op=='interval':bounds=list(value) if bounds is None else [max(bounds[0],value[0]),min(bounds[1],value[1])]
        elif op=='member':
            if value not in members:members.append(value)
        elif op=='slot':
            key=str(value['slot']);move=value['move_id']
            if key in slots and slots[key]!=move:reason='incompatible_move_slot'
            slots[key]=move
            if move not in members:members.append(move)
        if candidates is not None:
            candidates=[v for v in candidates if v not in exclusions and (bounds is None or not isinstance(v,(int,float)) or bounds[0]<=v<=bounds[1])]
            if not candidates:reason='empty_candidate_intersection'
            if any(v not in candidates for v in members):reason='revealed_member_outside_candidates'
        if any(v in exclusions for v in members):reason='revealed_member_excluded'
        if bounds is not None and bounds[0]>bounds[1]:reason='empty_numeric_intersection'
        removed=[] if old['candidates'] is None or candidates is None else [v for v in old['candidates'] if v not in candidates]
        if op=='exclude':removed=list(dict.fromkeys(removed+value))
        for candidate in removed:result['eliminations'].append({'candidate':candidate,'constraint_id':c['constraint_id'],'reason':c['reason'],'event_ids':deepcopy(c['event_ids']),'rule_id':c['rule_id']})
        if old['interval'] and bounds and old['interval']!=bounds:
            result['eliminations'].append({'prior_interval':old['interval'],'remaining_interval':deepcopy(bounds),'constraint_id':c['constraint_id'],'reason':c['reason']})
        if reason:result['conflicts'].append({'constraint_id':c['constraint_id'],'reason':reason,'prior_domain':old,'proposed_constraint':deepcopy(c)})
        elif not result['conflicts']:last_consistent=deepcopy({'candidates':candidates,'interval':bounds,'members':members,'slots':slots})
    result.update(candidates=candidates,interval=bounds,members=members,slots=slots,exclusions=exclusions)
    if result['conflicts']:
        result.update(status='conflicting',value=None,last_consistent=last_consistent)
    elif equal_seen and candidates and len(candidates)==1:result.update(status='confirmed',value=candidates[0])
    elif members:result.update(status='confirmed',value=deepcopy(members))
    elif bounds and bounds[0]==bounds[1]:result.update(status='confirmed',value=bounds[0])
    elif candidates is not None or bounds is not None or exclusions:result['status']='possible' if constraints and all(c['reason']=='complete verified legality domain' for c in constraints) else 'constrained'
    return result


class HiddenRules:
    def __init__(self, profile='champions-evidence-only-v1', *, transformations=None, move_capacity=None):
        if profile not in PROFILES:raise ValueError('Unknown rule profile')
        self.profile=profile
        self.move_capacity=4 if profile=='showdown-champions-reference-v1' and move_capacity is None else move_capacity
        self.transformations=deepcopy(transformations if transformations is not None else json.loads(
            (Path(__file__).resolve().parents[1]/'data/hidden_rules_v1.json').read_text())['transformations'])
        self.move_capacity_rule={'rule_id':'m231:four-move-capacity:v1','verification':'simulator_reference_only',
            'provenance':['https://github.com/smogon/pokemon-showdown/blob/3a766f2cfb5e51c1e428cfe87d0dba91a8f01640/sim/pokemon.ts'],
            'prerequisites':['native_move_membership_established']}

    def to_dict(self):return {'profile':self.profile,'transformations':deepcopy(self.transformations),'move_capacity':self.move_capacity}

    def transformation(self, identity):
        return next((r for r in self.transformations if r['target_identity']==identity and self.profile in r['profiles']),None)


class HiddenEngine:
    def __init__(self, initial=None, *, rules=None):
        self.rules=rules or HiddenRules();self.initial=deepcopy(initial or {'schema_version':1,'pokemon':{},'unresolved':[]})
        self.state=deepcopy(self.initial);self.history=[];self.knowledge_observations=[];self._handling=False;self._deriving=False

    def ensure(self, pid, side, name=None):
        if pid not in self.state['pokemon']:
            self.state['pokemon'][pid]={'instance_id':pid,'side':side,'name':name,'fields':{k:empty_domain() for k in FIELDS},
                'constraints':[],'relations':[],'events_seen':[],'revelations':[],
                'item_epochs':0,'ability_modified':False,'moves_modified':False,'transformed':False,
                'dynamic_reference':{'instance_id':pid,'item_path':['pokemon',pid,'item'],'ability_path':['pokemon',pid,'ability']}}
        p=self.state['pokemon'][pid]
        if p['side']!=side:raise ValueError('Hidden instance side mismatch')
        return p

    def add(self, constraint):
        c=asdict(constraint) if isinstance(constraint,Constraint) else deepcopy(constraint)
        c=asdict(Constraint(**c))  # Validate and normalize restored/external constraints.
        p=self.state['pokemon'][c['instance_id']]
        existing=next((x for x in p['constraints'] if x['constraint_id']==c['constraint_id']),None)
        if existing:
            if existing!=c:raise ValueError('Constraint ID payload mismatch')
            return
        if not self._handling and not self._deriving:
            self.knowledge_observations.append({'constraint':deepcopy(c),'after_sequence':max((r['sequence'] for r in self.history),default=None)})
        p['constraints'].append(c);self._refresh(p,c['variable']);self._propagate(p)

    def _refresh(self,p,key):
        relevant=[c for c in p['constraints'] if c['variable']==key]
        hard=domain([c for c in relevant if c['strength']!='provisional'])
        provisional=[c for c in relevant if c['strength']=='provisional']
        if provisional:
            inferred=domain([c for c in relevant if c['strength']!='unresolved'])
            if inferred['status'] not in {'unknown','conflicting'}:inferred['status']='provisional_inference'
            hard['provisional']=inferred
        p['fields'][key]=hard

    def _propagate(self,p):
        # Factorized implications/disjunctions only; no Cartesian product or SAT.
        for c in list(p['constraints']):
            if c['operation']=='conditional' and isinstance(c['value'],dict) and 'if' in c['value'] and 'then' in c['value']:
                condition=c['value']['if'];known=p['fields'].get(condition['variable'],empty_domain())
                if known['status']=='confirmed' and known['value']==condition['equals']:
                    consequence=c['value']['then'];derived=deepcopy(c)
                    derived.update(constraint_id=c['constraint_id']+':then',variable=consequence['variable'],operation=consequence['operation'],value=consequence['value'])
                    derived['prerequisites']=derived['prerequisites']+[{'constraint_ids':known['constraints']}]
                    if not any(x['constraint_id']==derived['constraint_id'] for x in p['constraints']):
                        was_deriving=self._deriving;self._deriving=True
                        try:self.add(derived)
                        finally:self._deriving=was_deriving
                else:
                    generated=next((x for x in p['constraints'] if x['constraint_id']==c['constraint_id']+':then'),None)
                    if generated:
                        p['constraints'].remove(generated);self._refresh(p,generated['variable'])
            if c['operation']=='any_of':
                remaining=[];eliminated=[]
                for alternative in c['value']:
                    incompatible=[key for key,value in alternative.items() if p['fields'].get(key,{}).get('status')=='confirmed' and p['fields'][key]['value']!=value]
                    (eliminated if incompatible else remaining).append({'alternative':alternative,'reason':'conflicting_confirmed_field','fields':incompatible} if incompatible else alternative)
                relation={'constraint_id':c['constraint_id'],'remaining_options':remaining,'eliminated':eliminated,'status':'conflicting' if not remaining else 'unresolved'}
                prior=next((i for i,x in enumerate(p['relations']) if x.get('constraint_id')==c['constraint_id']),None)
                if prior is None:p['relations'].append(relation)
                else:p['relations'][prior]=relation
                self._refresh(p,c['variable'])
                if not remaining:
                    d=p['fields'][c['variable']]
                    if c['strength']=='provisional' and d['provisional']:d=d['provisional']
                    d['status']='conflicting';d['conflicts'].append({'constraint_id':c['constraint_id'],'reason':'disjunction_has_no_remaining_alternative','eliminated':eliminated})

    def constrain(self,p,e,key,op,value,*,strength='hard',rule=None,reason='direct observation',suffix=''):
        from .state_engine import evidence_link
        if rule and rule.get('verification')!='champions_verified' and strength!='unresolved':
            strength='provisional' if self.rules.profile in rule.get('profiles',['showdown-champions-reference-v1']) else 'unresolved'
        cid='hidden:'+hashlib.sha256(json.dumps([p['instance_id'],e.event_id,key,op,suffix,value],sort_keys=True).encode()).hexdigest()[:24]
        self.add(Constraint(cid,p['instance_id'],key,op,deepcopy(value),[e.event_id],strength,
                 'confirmed' if e.status=='confirmed' else 'candidate',rule.get('rule_id') if rule else None,
                 self.rules.profile if rule else None,[evidence_link(e)]+([deepcopy(rule)] if rule else []),
                 deepcopy(rule.get('prerequisites',[])) if rule else [],reason))

    def seed(self, observable):
        """Initial identities are evidence, not hidden legality candidate catalogs."""
        for pid,p in observable['pokemon'].items():
            if p['side_id']!='opponent':continue
            mon=self.ensure(pid,'opponent',p['species']['value'].get('name'))
            for name,key in [('species','species'),('current_variant','original_form')]:
                f=p[name]
                if f['knowledge'] in {'observed','derived'}:
                    value=f['value'].get('canonical_id') if isinstance(f['value'],dict) else f['value']
                    self.add(Constraint('initial:'+pid+':'+key,pid,key,'equal',value,provenance=deepcopy(f['provenance'])))
        self.initial=deepcopy(self.state);self.knowledge_observations=[]

    def apply(self,event,*,instance_id=None,side=None,sequence=None,application_status='applied_confirmed'):
        from .state_engine import event_from_dict
        e=event_from_dict(event) if isinstance(event,dict) else deepcopy(event)
        record={'event':e.to_dict(),'instance_id':instance_id,'side':side or e.side,
                'sequence':sequence if sequence is not None else e.attributes.get('sequence'),'application_status':application_status,'retracted':False,'revisions':[]}
        prior=next((r for r in self.history if r['event']['event_id']==e.event_id),None)
        if prior:
            if any(prior[k]!=record[k] for k in ('event','instance_id','side','sequence','application_status')):raise ValueError('Event ID payload mismatch; use correct')
            return
        if type(record['sequence']) is not int:raise ValueError('Explicit integer sequence required')
        if any(r['sequence']==record['sequence'] for r in self.history):raise ValueError('Ambiguous hidden-event order')
        self.history.append(record)
        # Increasing ordered delivery is genuinely incremental. Corrections/out-of-order replay.
        if self.history[-1]['sequence']==max(r['sequence'] for r in self.history):
            previous=deepcopy(self.state);self._handling=True
            try:self._handle(record)
            except Exception:
                self.state=previous;self.history.pop();raise
            finally:self._handling=False
        else:self.replay()

    def correct(self,event_id,replacement,*,reason,instance_id=None):
        from .state_engine import event_from_dict
        r=next(r for r in self.history if r['event']['event_id']==event_id);e=event_from_dict(replacement) if isinstance(replacement,dict) else replacement
        if e.event_id!=event_id:raise ValueError('Correction preserves event ID')
        old_record=deepcopy(r);old_state=deepcopy(self.state)
        r['revisions'].append({'event':deepcopy(r['event']),'reason':reason,'retracted':r['retracted']})
        r['event']=e.to_dict();r['side']=e.side;r['retracted']=False
        if instance_id is not None:r['instance_id']=instance_id
        try:self.replay()
        except Exception:
            r.clear();r.update(old_record);self.state=old_state;raise

    def retract(self,event_id,*,reason):
        r=next(r for r in self.history if r['event']['event_id']==event_id)
        r['revisions'].append({'event':deepcopy(r['event']),'reason':reason,'retracted':r['retracted']});r['retracted']=True;self.replay()

    def replay(self):
        self.state=deepcopy(self.initial)
        self._handling=True
        try:
            observations=deepcopy(self.knowledge_observations)
            def apply_observations(boundary):
                for observation in observations:
                    if observation['after_sequence']==boundary:
                        c=observation['constraint']
                        if c['instance_id'] in self.state['pokemon']:self.add(c)
            apply_observations(None)
            for r in sorted(self.history,key=lambda r:r['sequence']):
                if not r['retracted']:self._handle(r)
                apply_observations(r['sequence'])
        finally:self._handling=False
        return self.state

    def _handle(self,r):
        from .state_engine import event_from_dict
        e=event_from_dict(r['event']);a=e.attributes;pid=r['instance_id'] or a.get('actor_instance_id') or (e.actor or {}).get('pokemon_instance_id')
        # Opt-in, field-admitted observations retain their original candidate status.
        # Existing candidate events without this receipt remain unresolved.
        fused_hud=(e.event_type=='hud_observation' and r['application_status']=='applied_candidate')
        visual=(e.event_type=='visual_observation' and r['application_status']=='applied_candidate'
                and a.get('visual_receipt',{}).get('instance_id')==pid)
        revealed=(e.event_type=='move_execution' and e.attributes.get('fusion_context')
                  and r['application_status']=='applied_partial'
                  and a.get('actor_instance_id')==pid)
        if r['application_status'] in {'deferred','rejected','retracted'} or (e.status!='confirmed' and not fused_hud and not revealed and not visual):
            if e.event_type in {'move_execution','ability_activation','item_activation','transformation'}:self.state['unresolved'].append({'event_id':e.event_id,'reason':'observation_not_accepted_as_confirmed','status':e.status,'application_status':r['application_status']})
            return
        if not pid or r['side'] not in {'self','opponent'}:
            if e.event_type in {'move_execution','transformation','ability_activation','item_activation'}:
                self.state['unresolved'].append({'event_id':e.event_id,'reason':'instance_or_side_unresolved'})
            return
        if r['side']=='self' and e.event_type!='transformation' and not (fused_hud or revealed or visual):return
        p=self.ensure(pid,r['side'],(e.actor or {}).get('name'));p['events_seen'].append(e.event_id)
        before={k:(v['status'],v['value'],v['candidates'],v['interval'],v['members']) for k,v in p['fields'].items()}
        for i,c in enumerate([] if revealed else a.get('hidden_constraints',[])):
            self.constrain(p,e,c['variable'],c['operation'],c['value'],strength=c.get('strength','hard'),rule=c.get('rule'),reason=c.get('reason','normalized knowledge observation'),suffix=str(i))
        if e.actor and e.actor.get('canonical_id') and e.event_type!='transformation':self.constrain(p,e,'species','equal',f"pokeapi:species:{e.actor['species_id']}" if e.actor.get('species_id') else e.actor['canonical_id'])
        if visual:
            fields=a['visual_receipt']['fields']
            for key,variable in [('ability','observed_ability'),('item','observed_item')]:
                if fields.get(key):
                    self.constrain(p,e,variable,'member',fields[key]['canonical_id'])
                    self.constrain(p,e,key+'_at:'+e.event_id,'equal',fields[key]['canonical_id'])
            if fields.get('maximum_hp') is not None:self.constrain(p,e,'max_hp','equal',fields['maximum_hp'])
        if e.event_type=='send_out' and not p['transformed'] and (e.actor or {}).get('canonical_identity'):
            self.constrain(p,e,'original_form','equal',e.actor['canonical_identity'])
        if e.event_type=='move_execution' or (e.event_type=='move_observation' and a.get('configuration_confirmed') is True):
            move=e.canonical_references.get('move',{}).get('canonical_id')
            origin=a.get('move_origin','native')
            if a.get('execution_status','executed')!='executed' or a.get('effect_outcome')=='selected':return
            if not move:self.constrain(p,e,'moves','conditional',{'reason':'unresolved_move_identity'},strength='unresolved')
            elif origin in {'copied','external','temporary','transformed','called'} or p['moves_modified']:
                self.constrain(p,e,'moves','conditional',{'observed_move':move,'origin':origin,'membership_unresolved':True},strength='unresolved')
            else:
                self.constrain(p,e,'moves','member',move)
                if a.get('move_slot') is not None:self.constrain(p,e,'moves','slot',{'slot':a['move_slot'],'move_id':move})
                capacity=a.get('verified_move_capacity',self.rules.move_capacity)
                if capacity is not None and len(p['fields']['moves']['members'])>capacity:
                    self.constrain(p,e,'move_capacity','conditional',{'maximum':capacity,'observed_count':len(p['fields']['moves']['members']),'conflict':True},
                         strength='hard' if a.get('verified_move_capacity') else 'provisional',rule=None if a.get('verified_move_capacity') else self.rules.move_capacity_rule,reason='distinct moves exceed supported slot capacity')
                    p['fields']['moves']['conflicts'].append({'reason':'move_capacity_exceeded','event_id':e.event_id,'capacity':capacity,'provisional':not bool(a.get('verified_move_capacity'))})
                    p['fields']['moves']['status']='conflicting'
        elif e.event_type=='ability_change':
            if a.get('suppressed') is None:p['ability_modified']=True
        elif e.event_type=='ability_activation':
            ability=e.canonical_references.get('ability',{}).get('canonical_id')
            if ability:
                self.constrain(p,e,'ability_at:'+e.event_id,'equal',ability)
                # Effective revelation is distinct from original native configuration.
                self.constrain(p,e,'observed_ability','member',ability)
                if a.get('ability_origin')=='native' and not p['ability_modified'] and not p['transformed']:
                    self.constrain(p,e,'native_ability','equal',ability)
                else:self.constrain(p,e,'native_ability','conditional',{'observed_ability':ability,'requires':'native_origin_established'},strength='unresolved')
        elif e.event_type in {'item_activation','item_change'}:
            item=e.canonical_references.get('item',{}).get('canonical_id');change=a.get('change')
            if change in {'receive','replace','transfer'}:p['item_epochs']+=1
            if item:
                self.constrain(p,e,'item_at:'+e.event_id,'equal',item)
                key='held_item' if p['item_epochs']==0 else 'held_item_epoch:'+str(p['item_epochs'])
                self.constrain(p,e,key,'equal',item)
                if a.get('at_battle_start') is True:self.constrain(p,e,'item_at_start','equal',item)
        elif e.event_type=='hp_change' and a.get('unit')=='absolute' and a.get('maximum') is not None:
            self.constrain(p,e,'max_hp','equal',a['maximum'])
        elif e.event_type=='transformation':
            p['transformed']=True;identity=a.get('identity',{});target=identity.get('canonical_identity')
            self.constrain(p,e,'observed_transformation','member',target or identity.get('canonical_id') or 'ambiguous')
            if a.get('mechanic')=='mega_evolution':self.constrain(p,e,'mega_eligibility','equal',True)
            else:p['moves_modified']=True
            rule=self.rules.transformation(target) if target and a.get('mechanic')=='mega_evolution' else None
            if rule and (not rule.get('species_id') or rule['species_id']==(e.actor or {}).get('species_id')):
                strength='hard' if rule['verification']=='champions_verified' else 'provisional'
                options=rule['prerequisite_options']
                key='item_before_transformation:'+e.event_id
                if len(options)==1 and 'held_item' in options[0]:
                    self.constrain(p,e,key,'equal',options[0]['held_item'],strength=strength,rule=rule)
                    # Same possession epoch evidence intersects with the past-item requirement.
                    self.constrain(p,e,'held_item' if p['item_epochs']==0 else 'held_item_epoch:'+str(p['item_epochs']),
                                   'equal',options[0]['held_item'],strength=strength,rule=rule)
                else:self.constrain(p,e,key,'any_of',options,strength='unresolved',rule=rule)
            else:self.constrain(p,e,'transformation_requirements','conditional',{'target_identity':target,'reason':'no_applicable_verified_rule_or_ambiguous_form'},strength='unresolved')
        for key,v in p['fields'].items():
            sig=(v['status'],v['value'],v['candidates'],v['interval'],v['members'])
            if key not in before or sig!=before[key]:p['revelations'].append({'event_id':e.event_id,'turn':next((x.details.get('turn') for x in e.evidence if x.details.get('turn')),None),'field':key,'status':v['status'],'value':deepcopy(v['value'])})

    def candidate_domain(self,pid,key,values,*,complete,verification,provenance):
        p=self.state['pokemon'][pid]
        if complete and verification=='champions_verified':
            self.add(Constraint('legality:'+pid+':'+key,pid,key,'candidates',values,provenance=[provenance],reason='complete verified legality domain'))
        else:
            self.add(Constraint('reference:'+pid+':'+key,pid,key,'conditional',
                {'kind':'incomplete_reference','suggested_candidates':deepcopy(values),'verification':verification,'eliminates_unlisted':False},
                strength='unresolved',provenance=[deepcopy(provenance)],reason='incomplete legality reference does not exclude unlisted candidates'))

    def projection(self):
        return {'schema_version':1,'rule_profile':self.rules.profile,'move_capacity':self.rules.move_capacity,'move_capacity_rule':deepcopy(self.rules.move_capacity_rule) if self.rules.move_capacity is not None else None,'pokemon':{pid:{k:deepcopy(p[k]) for k in ('instance_id','side','name','fields','constraints','relations','dynamic_reference')} for pid,p in self.state['pokemon'].items()},
                'unresolved':deepcopy(self.state['unresolved']),'probabilities':None}

    def decision_projection(self):
        result={'rule_profile':self.rules.profile,'opponent':{},'own_transformation_requirements':{},'probability_distribution':None}
        for pid,p in self.state['pokemon'].items():
            summary={'confirmed':{k:deepcopy(d['value']) for k,d in p['fields'].items() if d['status']=='confirmed'},
                     'domains':deepcopy(p['fields']),
                     'conflicts':[deepcopy(c) for d in p['fields'].values() for c in d['conflicts']+(d['provisional']['conflicts'] if d['provisional'] else [])],
                     'supporting_constraints':deepcopy(p['constraints']),
                     'unresolved_requirements':[deepcopy(c) for d in p['fields'].values() for c in d['unresolved']],
                     'dynamic_reference':deepcopy(p['dynamic_reference'])}
            result['opponent' if p['side']=='opponent' else 'own_transformation_requirements'][pid]=summary
        return result

    def to_dict(self):return {'schema_version':1,'rules':self.rules.to_dict(),'initial':deepcopy(self.initial),'history':deepcopy(self.history),'knowledge_observations':deepcopy(self.knowledge_observations),'state':deepcopy(self.state)}

    @classmethod
    def from_dict(cls,payload):
        if not payload or 'initial' not in payload or 'rules' not in payload:return cls()  # Legacy observable envelope has no hidden layer.
        engine=cls(payload['initial'],rules=HiddenRules(**payload['rules']));engine.history=deepcopy(payload['history']);engine.knowledge_observations=deepcopy(payload.get('knowledge_observations',[]));engine.replay();return engine
