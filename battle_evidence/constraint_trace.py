"""Saved-evidence hidden constraints; no frequencies, ranking or posterior model.

This is a diagnostic projection. BattleState and its existing receipts remain
authoritative; this module never constructs an alternative observable engine.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from knowledge.champions_stats import ChampionsStats, STATS
from knowledge.stat_feasibility import champions_attainable_stats, summary
from speed_order.core import knowledge, name
from speed_order import infer_speed
from damage.inverse import infer_attack_stat
from damage.selectors import select_stats
from damage.data import database, Diagnostic
from damage.joint import legal_damage_items
from damage.engine import DIRECT, FIXED
from .life_orb import absence_constraint
from .team_items import six_member_exclusions

VERSION='hidden-constraints-v1'
PROFILE='showdown-champions-reference-v1'
TRACKED=('speed','attack','special_attack')
ACCEPTED={'applied_candidate','applied_confirmed','applied_partial','recorded_observation'}
RULE_PATH=Path(__file__).with_name('data')/'hidden-constraints-rules-v1.json'
RULE_DATA=json.loads(RULE_PATH.read_text())
USER_RULE=dict(id=RULE_DATA['life_orb_absence']['id'],
    accepted_ui_guarantee=RULE_DATA['life_orb_absence']['accepted_ui_guarantee'],
    verification=RULE_DATA['life_orb_absence']['verification'],
    statement=RULE_DATA['life_orb_absence']['rule'],independently_game_ui_verified=False,
    source_record='battle_evidence/data/hidden-constraints-rules-v1.json',
    source_sha256=hashlib.sha256(RULE_PATH.read_bytes()).hexdigest())

def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def value(f):
    return f.get('value') if isinstance(f,dict) and f.get('knowledge') in {'observed','derived'} else None

def event_time(e):
    return e.get('attributes',{}).get('observation_time',0.)

def actor_id(record):
    return record.get('bindings',{}).get('actor',{}).get('pokemon_instance_id')

def resolved_event(record):
    return record.get('bindings',{}).get('resolved_event') or record['event']

def canonical(v,kind):
    if isinstance(v,dict):return v.get('canonical_identity') or v.get('canonical_id')
    return v

def source_refs(e):
    return [dict(source_id=s.get('source_id'),observation_ids=s.get('observation_ids',[]),
        timestamp=s.get('details',{}).get('timestamp'),image=s.get('details',{}).get('image'))
        for s in e.get('evidence',[])]

@lru_cache(maxsize=256)
def native_domains(identity,configuration_rule=None):
    if configuration_rule:
        from .configuration_domain import initial_domain
        result=initial_domain(identity,configuration_rule)
        if result['status']!='exact':raise ValueError('Default configuration domain unresolved: '+str(result['diagnostics']))
        return {s:deepcopy(result['stats'][s]) for s in TRACKED}
    out={}
    for stat in TRACKED:
        r=champions_attainable_stats(identity=identity,stat=stat,form='as_named' if ':pokemon:' in identity or ':form:' in identity else 'base',retain_witnesses=False)
        out[stat]=r['joint_feasible'] if r['status']=='exact' else None
    return out

def model_identity(identity):
    m=ChampionsStats(identity,form='as_named' if ':pokemon:' in identity or ':form:' in identity else 'base')
    return m.identity

def refine_numeric(before,after,*,evidence_id):
    """Monotonic set intersection; an empty intersection is a conflict, never a reset."""
    old=set(before['values']);new=old & set(after['values'])
    if not new:
        return deepcopy(before),dict(status='contradiction',evidence_id=evidence_id,
            attempted=deepcopy(after),reason='no_joint_completion; previous support retained for audit, not accepted as consistent')
    return summary(new),dict(status='exact',excluded=sorted(old-new),evidence_id=evidence_id)

def infer_complete_speed(observation,configurations):
    """Reuse the v2 engine, retaining priority/tie/Trick Room semantics."""
    return infer_speed(schema_version=2,observations=[observation],configurations=configurations,
        profile=PROFILE,max_evaluations=1000000)

def infer_complete_offense(observation,values,stat):
    """No unknown defender/modifier is filled by this adapter."""
    return infer_attack_stat(observations=[observation],candidate_stats=values,stat=stat,ruleset=PROFILE)

def known_context(p,field,sides,side):
    """Return explicit unknowns; no neutral defaults for modifier fields."""
    status=value(p.get('status',{}))
    return dict(form=canonical(value(p.get('variant',{})),'species'),
        stages={s:value(p.get('stages',{}).get(s,{}).get('value',{})) for s in ('attack','defense','special_attack','special_defense','speed')},
        status=status,ability=canonical(value(p.get('ability',{}).get('identity',{})),'ability'),
        item=canonical(value(p.get('item',{}).get('identity',{})),'item'),
        hp={k:value(p.get('hp',{}).get(k,{})) for k in ('current','maximum','unit')},
        tailwind=value(sides.get(side,{}).get('conditions',{}).get('tailwind',{}).get('active',{})),
        field={k:value(field.get(k,{}).get('kind' if k!='trick_room' else 'active',{}))
            for k in ('weather','terrain','trick_room')},
        configured=p.get('known_configuration'),copied=p.get('copied_appearance'),
        current_form_stats={s:value(f) for s,f in p.get('mechanics',{}).get('battle_stats',{}).get('current',{}).items()})

def message_absence_window(rows,start,end):
    selected=[r for r in rows if start<=r['timestamp']<=end]
    positive=[];unread=[];readable=0;source=[]
    for r in selected:
        m=r.get('message',{});text=m.get('raw_text','') or ''
        source.append(r.get('source_id'))
        if '生命宝珠' in text or '生命被少量削减' in text:positive.append(r.get('source_id'))
        if m.get('selected') and m.get('confidence',0)>=.90:
            readable+=1
        elif m.get('visibility') not in {'hidden','absent','not_visible','invisible'}:
            unread.append(r.get('source_id'))
    return dict(complete=bool(selected) and not unread,loss_displayed=bool(positive),
        selected_frames=len(selected),readable_frames=readable,unread_frames=len(unread),
        positive_sources=positive,unread_source_examples=unread[:5],source_examples=source[:3],
        basis='Saved message-selection/visibility/read-confidence evidence; no unread frame is silently certified absent')


def public_candidate_comparison(result,database_root,midpoint):
    """Read-only candidate compatibility. Counts are not prior weights/rankings."""
    from metagame.published.store import Teams
    from metagame.published import VERSION as CANONICAL
    from metagame.published.observed import eligibility
    from metagame.published.speed_support import alignment
    kb=knowledge();db=Teams(database_root,readonly=True)
    try:publications=[r for r in db.scoped('tournament_published','M-C','Doubles',CANONICAL) if r['source_id']=='vgcmulticalc']
    finally:db.close()
    pools=defaultdict(list)
    for publication in publications:
        canonical_team=json.loads(publication['canonical'])
        for ordinal,member in enumerate(canonical_team['members']):
            n=member['normalized'];entity=kb.entities.get(n.get('species'))
            if entity:
                pools[entity.species_id].append(dict(occurrence_id=publication['id']+':'+publication['extraction_id']+':member:'+str(ordinal),
                    normalized=n,eligible=eligibility(member),publication_id=publication['id'],source_key=publication['source_key']))
    outputs=[]
    for mon in result['roster']:
        pool=pools[mon['species_id']]
        for lineage in mon['lineages'] or [dict(instance_id=None,stats=mon['initial'],original_item=None)]:
            updates=[u for u in result['updates'] if u.get('persistent_team_member_id',u['pokemon_instance_id'])==lineage['instance_id'] and u['kind']=='revealed_move' and u['observation'].get('native_membership')]
            stages={}
            for label,cutoff in [('initial',float('-inf')),('first_half',midpoint),('final',float('inf'))]:
                moves={u['observation']['move'] for u in updates if u['timestamp']<=cutoff}
                eligible_item_events=[r for r in mon['confirmed_items'] if r['time']<=cutoff and r['instance_id'] in lineage.get('source_instance_ids',[lineage['instance_id']])]
                original_item=lineage['original_item'] if eligible_item_events else None
                allowed_stats=mon['initial'] if label!='final' else lineage['stats']
                survivors=[];unresolved=set();excluded=Counter()
                for row in pool:
                    n=row['normalized'];valid=row['eligible'];reasons=[]
                    if valid['moves'] and not moves<=set(n['moves']):reasons.append('complete published template lacks revealed native move')
                    elif not valid['moves'] and not moves<=set(x for x in n['moves'] if x):unresolved.add(row['occurrence_id'])
                    if original_item and valid['item'] and n['item']!=original_item:reasons.append('confirmed original item differs')
                    if valid['sp'] and valid['nature'] and mon['initial_form']:
                        try:
                            model=ChampionsStats(mon['initial_form'],form='as_named' if ':form:' in mon['initial_form'] else 'base')
                            stats=model.calculate(dict(zip(STATS,n['sp']['values'])),alignment(n['nature']))['stats']
                            if any(allowed_stats[s] and stats[s] not in allowed_stats[s]['values'] for s in TRACKED):reasons.append('supported native-stat domain differs')
                        except (ValueError,KeyError,NotImplementedError):unresolved.add(row['occurrence_id'])
                    else:unresolved.add(row['occurrence_id'])
                    if reasons:excluded.update(set(reasons))
                    else:survivors.append(row['occurrence_id'])
                stages[label]=dict(compatible_or_unresolved=len(survivors),unresolved_partial_records=len(set(survivors)&unresolved),
                    excluded_by_reason=dict(excluded),surviving_occurrence_ids=survivors,observed_native_moves=sorted(moves),original_item=original_item)
            outputs.append(dict(roster_id=mon['roster_id'],instance_id=lineage['instance_id'],initial_pool_occurrences=len(pool),stages=stages,
                reduction=len(pool)-stages['final']['compatible_or_unresolved']))
    return dict(source='vgcmulticalc',population='tournament_published',regulation='M-C',format='Doubles',canonical_version=CANONICAL,
        active_publications=len(publications),records=outputs,ranking=None,frequencies_used=False,
        limits=['Compatibility with this scoped candidate library only; missing samples never prove legal impossibility.',
            'Unproven same-species returns are evaluated separately, never intersected or counted as independent opponent samples.',
            'Incomplete candidate fields remain unresolved; public Mega/base source representations are not silently rewritten.'])

class ChronologicalTrace:
    def __init__(self,battle_id,roster,records,final_state,*,rule_verified=True,hp_action_ids=None,integrate=False,persistent_aliases=None,configuration_rule=None):
        self.battle_id=battle_id;self.records=records;self.final_state=final_state
        self.configuration_rule=configuration_rule
        self.members={};self.pid_member={};self.lineages={};self.updates=[];self.rejected=[];self.counter=Counter()
        self.rule_verified=rule_verified;self.conflicts=[];self.negative_actions=set()
        self.catalog_items=sorted(set(legal_damage_items())|{'none'})
        self.contexts={};self.sequence=0
        self.hp_action_ids=hp_action_ids
        self.integrate=integrate
        self.persistent_aliases=persistent_aliases or {}
        self.speed_ledgers={}
        for row in sorted(roster,key=lambda r:r['preview_row']):
            sid=row.get('species_id');rid=row.get('member_occurrence') or f'{battle_id}:opponent:preview:{row["preview_row"]}'
            icon=row.get('icon',{})
            ident=icon.get('canonical_identity') or icon.get('canonical_id') or f'pokeapi:species:{sid}'
            try:domains=native_domains(ident,self.configuration_rule) if self.configuration_rule else native_domains(ident);form=model_identity(ident)
            except (ValueError,KeyError,NotImplementedError):domains={s:None for s in TRACKED};form=None
            kb=knowledge();label=kb.entities.get(f'pokeapi:species:{sid}')
            first=[event_time(r['event']) for r in records if r['event']['event_type']=='preview_observation'
                and r['event'].get('attributes',{}).get('row',{}).get('preview_row')==row['preview_row']]
            self.members[rid]=dict(roster_id=rid,species_id=sid,name=label.label(True) if label else str(sid),
                preview_row=row['preview_row'],preview_identity=ident,initial_form=form,
                initial=deepcopy(domains),initial_available_at=min(first) if first else None,
                initial_basis='Source preview form/default-form interpretation and pinned Champions SP/alignment rules; not exact hidden SP',
                joint_training_constraint=dict(representation='existing Champions SP/alignment domain',
                    point_domains={s:[0,32] for s in STATS},point_domain_encoding='inclusive integer ranges',
                    total_SP_max=66,alignment='one raised and one distinct lowered non-HP stat, or numerical neutral',
                    marginals_are_not_independent=True,engine='knowledge.stat_feasibility.champions_attainable_stats'),
                preview_evidence=row.get('evidence'),lineage_ids=[],revealed_moves=[],confirmed_items=[],confirmed_abilities=[],
                original_item_exclusions=[],conditional_original_item_exclusions=[],events=[])
        if len(self.members)!=6:raise ValueError('A six-row source preview is required; do not fabricate missing members')
        for pid,p in final_state.get('pokemon',{}).items():
            if p['side_id']!='opponent':continue
            sid=(value(p.get('original_identity',{})) or value(p.get('species',{})) or {}).get('species_id')
            matches=[m for m in self.members.values() if m['species_id']==sid]
            if len(matches)==1:self.pid_member[pid]=matches[0]['roster_id']

    def lineage(self,pid,member):
        source_pid=pid;pid=self.persistent_aliases.get(pid,pid)
        if pid not in self.lineages:
            episodes=[deepcopy(ep) for ep in self.final_state.get('knowledge',{}).get('active_entry_episodes',[]) if self.persistent_aliases.get(ep.get('instance_id'),ep.get('instance_id'))==pid]
            self.lineages[pid]=dict(instance_id=pid,roster_id=member['roster_id'],
                source_instance_ids=[],
                identity_continuity='unique_species_verified_team_member' if self.persistent_aliases else 'source_persistent_instance_only',episodes=[{k:ep.get(k) for k in
                 ('episode_id','encounter_id','start','entry_event_id','departure','persistent_identity_status','possible_prior_instance_ids')} for ep in episodes],
                initial=deepcopy(member['initial']),stats=deepcopy(member['initial']),current_form=member['initial_form'],
                form_epochs=[],current_item=None,original_item=None,ability=None,moves=[],excluded_current_items=[],
                native_moves=[],copied_stats=None,current_item_options=None,conditional_current_item_exclusions=[],
                symbolic_constraints=[],conditional_constraints=[])
            self.lineages[pid]['item_stat_support']={}
            member['lineage_ids'].append(pid)
        if source_pid not in self.lineages[pid]['source_instance_ids']:self.lineages[pid]['source_instance_ids'].append(source_pid)
        return self.lineages[pid]

    def joined_item_stats(self,line,stat,support):
        """Retain one named current-item witness across an unchanged item epoch.

        M3 supplies each row's feasible values. This is a finite relational join,
        not another damage/stat solver. Item changes start a new epoch.
        """
        previous=line['item_stat_support'].get(stat)
        rows={item:set(domain['values']) for item,domain in support.items()}
        if previous is not None:rows={item:values & set(previous.get(item,[])) for item,values in rows.items() if item in previous}
        line['item_stat_support'][stat]={item:sorted(values) for item,values in rows.items() if values}
        return summary({v for values in rows.values() for v in values})

    def append(self,member,pid,e,record,kind,observation,constraint,*,status='inferred',before=None,after=None,excluded=None,affects=(),rule=None):
        self.sequence+=1
        r=dict(update_id=f'{self.battle_id}:constraint:{self.sequence}',battle_id=self.battle_id,
            persistent_team_member_id=self.persistent_aliases.get(pid,pid),
            opponent_roster_id=member['roster_id'],pokemon_instance_id=pid,timestamp=event_time(e),
            source_event_id=e['event_id'],source_receipt_id=e['event_id']+':delivery:'+str(record.get('delivery_index')),
            application_status=record.get('application_status'),kind=kind,observation=observation,
            new_constraint=constraint,classification=status,before=before,after=after,
            excluded=excluded or [],other_affected_roster_ids=list(affects),
            provenance=dict(rule=rule or {},sources=source_refs(e),ocr_confidence=e.get('ocr_confidence'),
                parsing_confidence=e.get('parsing_confidence'),uncertainty=e.get('uncertainty',[]),
                derived_actor_binding=record.get('_trace_actor_binding')))
        self.updates.append(r);member['events'].append(r['update_id']);self.counter[kind]+=1
        return r

    def process_event(self,record,ctx):
        e=resolved_event(record);pid=actor_id(record);rid=self.pid_member.get(pid)
        if record.get('application_status') not in ACCEPTED:
            if e['event_type']!='hud_observation':
                self.rejected.append(dict(event_id=e['event_id'],timestamp=event_time(e),kind=e['event_type'],
                    instance_id=pid,reason=record.get('reason'),status=record.get('application_status')))
            return
        if (not rid and e['event_type']=='move_effect' and e.get('side')=='opponent'
                and e.get('attributes',{}).get('effect')=='mega_stone_reaction_notice'):
            sid=(e.get('actor') or {}).get('species_id')
            matches=[m['roster_id'] for m in self.members.values() if m['species_id']==sid]
            candidates=[p for p,r in self.pid_member.items() if r in matches and
                (value(ctx.get('pokemon',{}).get(p,{}).get('location',{})) or {}).get('kind')=='active']
            if len(matches)==1 and len(candidates)==1:
                pid=candidates[0];rid=matches[0];record=deepcopy(record)
                record['_trace_actor_binding']=dict(basis='explicit opponent/species in accepted notice and one agreeing active source instance',instance_id=pid)
        if e['event_type'] in {'side_condition_change','weather_change','terrain_change','trick_room_change'}:
            for member in self.members.values():
                self.append(member,None,e,record,'battle_context',
                    dict(kind=e['event_type'],side=e.get('side'),text=e.get('original_text'),
                        attributes={k:v for k,v in e.get('attributes',{}).items() if k in ('condition','change','weather','terrain','active','duration')}),
                    'Contemporaneous field/side modifier evidence changes damage/Speed context; no intrinsic stat is neutral-filled',
                    status='observed',affects=[x for x in self.members if x!=member['roster_id']],
                    rule={'source':'accepted global/side-effect event','scope':'explicit event side, not presumed permanent'})
            return
        if not rid:return
        member=self.members[rid];line=self.lineage(pid,member);kind=e['event_type'];a=e.get('attributes',{})
        self.contexts[e['event_id']]=ctx
        view=ctx.get('pokemon',{}).get(pid,{})
        copied=view.get('copied_non_hp_stats')
        if copied:
            copied={s:dict(value=value(f),knowledge=f.get('knowledge'),
                source_event_ids=sorted({p.get('event_id') for p in f.get('provenance',[]) if p.get('event_id')}))
                for s,f in copied.items()}
        if copied and copied!=line['copied_stats']:
            old=deepcopy(line['copied_stats']);line['copied_stats']=deepcopy(copied)
            self.append(member,pid,e,record,'copied_current_stats',
                dict(copied_appearance=view.get('copied_appearance'),copied_stats=copied),
                'Current copied non-HP stats follow the evidenced target snapshot; native Ditto SP/Attack/Speed remain unconstrained',
                status='inferred',before=old,after=deepcopy(copied),
                rule={'source':'existing Transform snapshot in the saved/current diagnostic StateEngine projection','scope':'temporary copied stats; not native hidden configuration'})
        if kind=='move_execution':
            move=(e.get('canonical_references',{}).get('move') or {}).get('canonical_id')
            if not move:return
            transformed=a.get('move_origin')=='transformed' or bool(view.get('copied_appearance'))
            obs=dict(move=move,text=e.get('original_text'),move_origin=a.get('move_origin','not_established'),native_membership=not transformed)
            if move not in line['moves'] or (not transformed and move not in line['native_moves']):
                if move not in line['moves']:line['moves'].append(move)
                if not transformed:
                    line['native_moves'].append(move)
                    if move not in member['revealed_moves']:member['revealed_moves'].append(move)
                self.append(member,pid,e,record,'revealed_move',obs,
                    'Revealed execution membership; exact equipped move slots remain unknown' if not transformed else 'Copied move execution; no native equipped membership',
                    status='observed',before=None,after=line['moves'].copy(),rule={'native_membership_requires_origin':'not copied/temporarily supplied'})
            if self.hp_action_ids is not None and e['event_id'] not in self.hp_action_ids:
                from damage.data import resolve
                try:
                    reference=resolve(move,'move','move');definition=database()[1]['moves'].get(reference['canonical_id'],{})
                except Diagnostic:definition={}
                if definition.get('category') in {'Physical','Special'}:
                    self.append(member,pid,e,record,'damage_unavailable',
                        dict(move=move,category=definition['category'],text=e.get('original_text')),
                        'No bound saved action-target HP resolution; attacker/defender stats and successful-hit counterfactual are unresolved',
                        status='unresolved',before=None,after=None,rule={'source':'accepted attack has no usable matching saved HP episode'})
                    self.counter['missing_hp_'+definition['category'].lower()+'_actions']+=1
        elif kind=='item_change':
            line['item_stat_support']={}
            change=a.get('change');old=line['current_item']
            item=(e.get('canonical_references',{}).get('item') or {}).get('canonical_id')
            line['current_item']='none' if change in {'consume','remove','transfer'} else item
            line['excluded_current_items']=[]
            line['conditional_current_item_exclusions']=[]
            self.append(member,pid,e,record,'item_lifecycle',dict(change=change,item=item,target=record.get('bindings',{}).get('target')),
                'Current possession changes; native/original assignment is retained separately and is not inferred for a recipient',
                status='observed',before=old,after=line['current_item'],rule={'source':'existing StateEngine item_change receipt'})
        elif kind in {'item_activation','ability_activation','ability_change'}:
            typ='item' if kind=='item_activation' else 'ability'
            raw=e.get('canonical_references',{}).get(typ) or {}
            ident=raw.get('canonical_id');label=raw.get('name')
            if not ident:return
            old=line['current_item' if typ=='item' else 'ability']
            line['current_item' if typ=='item' else 'ability']=ident
            member['confirmed_items' if typ=='item' else 'confirmed_abilities'].append(dict(id=ident,name=label,time=event_time(e),event_id=e['event_id'],instance_id=pid))
            self.append(member,pid,e,record,'confirmed_'+typ,dict(identity=ident,name=label,consumption=a.get('consumption_observed')),
                'Current item at activation; original ownership is a separate claim' if typ=='item' else 'Ability observed at this activation, not automatically the native ability after Transform',
                status='observed',before=old,after=ident,rule={'scope':'current possession/effective ability'})
            if typ=='item':
                # A later activation resolves the current possession witness
                # at this time, without backdating it to an earlier action.
                from damage.data import resolve
                try:item_name=resolve(ident,'item','item')['name']
                except Diagnostic:item_name=label
                for stat,rows in line['item_stat_support'].items():
                    domain=summary(rows.get(item_name,[]))
                    before=deepcopy(line['stats'][stat])
                    after,verdict=refine_numeric(before,domain,evidence_id=e['event_id'])
                    line['item_stat_support'][stat]={item_name:rows.get(item_name,[])}
                    if not domain['values']:
                        self.conflicts.append(dict(event_id=e['event_id'],reason='revealed_item_damage_empty',stat=stat))
                    if verdict.get('excluded'):
                        line['stats'][stat]=after
                        self.append(member,pid,e,record,'numeric_refinement',dict(stat=stat,item=ident),
                            dict(feasible=domain,source='same current-item epoch and observed activation'),
                            before=before,after=after,excluded=verdict['excluded'],
                            rule={'source':'M3 per-item witnesses joined with current-item activation; no original ownership inference'})
                # First recognized action need not be the first actual action.
                # Require explicit original-loadout continuity rather than a
                # missing recognized transfer or an arbitrary time threshold.
                original=bool(a.get('original_equipped_verified') and
                    a.get('initial_ownership_review',{}).get('unchanged_since_start'))
                if original:line['original_item']=ident
                claim=dict(owner=rid,item=label or ident,sources=source_refs(e),
                    original_equipped_verified=original,kind='original_candidate')
                for update in six_member_exclusions(list(self.members),[claim],battle_id=self.battle_id,rule_verified=self.rule_verified)['updates']:
                    target=self.members[update['target']]
                    field='original_item_exclusions' if update['status']=='exact' else 'conditional_original_item_exclusions'
                    if update['item'] in target[field]:continue
                    previous_exclusions=target[field].copy()
                    target[field].append(update['item'])
                    self.append(target,None,e,record,'item_clause',dict(confirmed_current_holder=pid,item=ident),
                        f'Original item != {label or ident}' if update['status']=='exact' else f'IF observed holder originally equipped {label or ident}, original item != {label or ident}',
                        status='inferred' if update['status']=='exact' else 'conditional',excluded=[ident],affects=[rid],
                        before={field:previous_exclusions},after={field:target[field].copy()},
                        rule={'id':'champions-reviewed-item-clause-v1','applicability':'user confirms ranked doubles, all six members',
                            'original_ownership':'explicit reviewed unchanged-since-start proof' if original else 'not established; no silent conversion from current possession'})
                if a.get('consumption_observed'):
                    line['item_stat_support']={}
                    self.append(member,pid,e,record,'consumed_item',dict(item=ident),'Current item consumed; original item evidence retained',
                        status='observed',before=ident,after='none');line['current_item']='none'
        elif kind=='transformation':
            ident=canonical(value(view.get('variant',{})),'species')
            before=line['current_form']
            self.append(member,pid,e,record,'form_or_transform',dict(mechanic=a.get('mechanic'),identity=ident,text=e.get('original_text')),
                'New current-form epoch; native SP and copied-state identity are not replaced by an independent build sample',
                status='observed',before=before,after=ident,rule={'source':'source StateEngine transformation receipt'})
            if a.get('mechanic')=='mega_evolution':
                line['current_form']=ident
                if ident:
                    try:domains=native_domains(ident,self.configuration_rule) if self.configuration_rule else native_domains(ident);line['form_epochs'].append(dict(time=event_time(e),form=ident,stats=domains))
                    except (ValueError,KeyError,NotImplementedError):pass
                else:line['form_epochs'].append(dict(time=event_time(e),form=None,stats=None,reason='Exact Mega variant unresolved; no base-form fallback'))
                from .speed_items import species_stones,item_ids
                stones=sorted(species_stones(f"pokeapi:species:{member['species_id']}"))
                options=[item_ids().get(s) for s in stones if item_ids().get(s)]
                line['current_item_options']=options
                if 'Life Orb' not in line['conditional_current_item_exclusions']:line['conditional_current_item_exclusions'].append('Life Orb')
                self.append(member,pid,e,record,'mega_item_class',
                    dict(mega_result_text=e.get('original_text'),current_form=ident,known_stone_options=options),
                    'At the witnessed Mega transition, the required-stone item class excludes current Life Orb; exact stone/original ownership may remain unresolved',
                    status='conditional',before=None,after=options,excluded=['Life Orb'],
                    rule={'source':'existing canonical form required_item facts and accepted Mega result','profile':PROFILE,
                        'scope':'transition only; original ownership/transfer history not silently inferred'})
                self.counter['positive_mega_item_class_exclusions']+=1
        elif kind in {'stat_change','status_change','volatile_change','move_effect','switch_out','send_out','faint','move_miss','protection_outcome'}:
            if kind=='switch_out' and line['copied_stats'] is not None and not view.get('copied_appearance'):
                self.append(member,pid,e,record,'copied_state_ended',dict(text=e.get('original_text')),
                    'Source Transform state restored on departure; native stat uncertainty was never replaced by copied values',
                    status='inferred',before=deepcopy(line['copied_stats']),after=None,
                    rule={'source':'existing successful switch-out and restored temporary-transform projection'})
                line['copied_stats']=None
                line['current_form']=member['initial_form']
            if kind=='move_effect' and a.get('effect')=='mega_stone_reaction_notice':
                text=''.join((e.get('original_text') or '').split())
                matches=[]
                for item in knowledge().entities.values():
                    label=item.names.get('zh-hans','')
                    if item.kind=='item' and '进化石' in label and '的'+label+'和' in text:
                        matches.append(item)
                if len(matches)==1:
                    stone=matches[0];old=line['current_item'];line['current_item']=stone.canonical_id
                    member['confirmed_items'].append(dict(id=stone.canonical_id,name=stone.names.get('zh-hans'),
                        time=event_time(e),event_id=e['event_id'],instance_id=pid,basis='exact named Mega stone reaction'))
                    self.append(member,pid,e,record,'confirmed_item',dict(identity=stone.canonical_id,name=stone.names.get('zh-hans'),text=e.get('original_text')),
                        'Exact named stone reaction establishes possession at that reaction; original ownership remains separately scoped',
                        status='observed',before=old,after=stone.canonical_id,
                        rule={'source':'exact canonical Chinese item spelling in accepted reaction; no OCR suffix correction'})
                    claim=dict(owner=rid,item=stone.names.get('en'),sources=source_refs(e),original_equipped_verified=False,kind='original_candidate')
                    for update in six_member_exclusions(list(self.members),[claim],battle_id=self.battle_id,rule_verified=self.rule_verified)['updates']:
                        target=self.members[update['target']]
                        if update['item'] in target['conditional_original_item_exclusions']:continue
                        previous_exclusions=target['conditional_original_item_exclusions'].copy()
                        target['conditional_original_item_exclusions'].append(update['item'])
                        self.append(target,None,e,record,'item_clause',dict(current_stone_owner=pid,item=stone.canonical_id),
                            'If this stone was originally equipped, another original roster item cannot equal it',status='conditional',excluded=[stone.canonical_id],affects=[rid],
                            before={'conditional_original_item_exclusions':previous_exclusions},after={'conditional_original_item_exclusions':target['conditional_original_item_exclusions'].copy()},
                            rule={'id':'champions-reviewed-item-clause-v1','applicability':'user confirms all six; initial ownership not proven from current possession'})
            attrs={k:v for k,v in a.items() if k in ('stats','stages','direction','status','condition','change','effect','outcome','cause','mechanic')}
            if kind=='stat_change':
                attrs['quantitative_relation']='after_stage = before_stage + signed observed stages, saturated at verified limits; unresolved magnitude remains unknown'
            self.append(member,pid,e,record,'context_'+kind,dict(text=e.get('original_text'),attributes=attrs),
                'Entry/exit/effect evidence changes action context; intrinsic native stat values are not equated to temporary modifiers',
                status='observed',rule={'source':'accepted receipt','persistent_identity':'source ID only; no species-based merge'})

    def damage(self,ep,records,contexts,rows,*,reviewed_absence=None):
        pid=ep.get('actor_instance_id');rid=self.pid_member.get(pid)
        if not rid:return
        rec=records.get(ep['source_event_id'])
        if not rec:return
        e=resolved_event(rec);member=self.members[rid];line=self.lineage(pid,member)
        if (ep.get('cause') or {}).get('kind')!='move':return
        move=ep.get('source_move') or {};mid=move.get('canonical_id');info=None
        try:
            from damage.data import resolve
            ref=resolve(mid,'move','move');info=dict(database()[1]['moves'].get(ref['canonical_id'],{}),**ref)
        except Diagnostic:pass
        category=info.get('category') if info else None
        selector=select_stats(info['name'],category) if category in {'Physical','Special'} else None
        ctx=contexts.get(e['event_id'],{});target=ep.get('target_instance_id')
        ps=ctx.get('pokemon',{});side_ctx=ctx.get('sides',{});field=ctx.get('field',{})
        at=known_context(ps.get(pid,{}),field,side_ctx,'opponent')
        de=known_context(ps.get(target,{}),field,side_ctx,'self' if ':self:' in (target or '') else 'opponent')
        supported=ep.get('attribution_status')=='supported' and ep.get('complete_endpoints') is True and ep.get('delta',0)<0
        limitations=[]
        if not supported:limitations.append('HP attribution/endpoints not causally complete')
        if selector is None:limitations.append('move category/stat selector unavailable or nonstandard')
        elif not selector['constrains_opponent_offensive_stat'] or selector['offensive_stat'] not in {'attack','special_attack'}:
            limitations.append('move does not constrain the attacker Attack/Special Attack; no new Defense solver')
        if info and info['name'] not in DIRECT|FIXED:
            limitations.append('move lacks an audited existing connected-hit damage handler')
        if ep.get('unit')!='absolute':limitations.append('percentage HP uncertainty retained; exact absolute damage unavailable')
        configured=de.get('configured')
        if not configured:limitations.append('defender stats unknown; joint attacker/defender relation retained')
        for k in ('stages','status','ability','item'):
            if k=='stages':
                if any(v is None for v in at[k].values()) or any(v is None for v in de[k].values()):limitations.append('stat stages incomplete')
            elif at[k] is None or de[k] is None:limitations.append(k+' context incomplete')
        if any(v is None for v in at['field'].values()):limitations.append('field context incomplete')
        hit=ep.get('hit_resolution') or {}
        obs=dict(move=mid,move_name=info.get('name') if info else move.get('name'),category=category,
            actor=pid,target=target,before=ep.get('before'),after=ep.get('after'),delta=ep.get('delta'),unit=ep.get('unit'),
            complete_endpoints=ep.get('complete_endpoints'),attribution=ep.get('attribution_status'),
            per_hit_damage=hit.get('per_hit_damage'),critical_hit=ep.get('critical_hit'),segment_event_ids=ep.get('segment_event_ids',[]))
        relation=dict(selector=selector,damage=abs(ep['delta']) if ep.get('delta') is not None else None,
            damage_unit=ep.get('unit'),attacker_context=at,defender_context=de,
            quantifier='One shared attacker configuration, uncertain defender/context and a legal random roll must satisfy each supported observation',
            critical_alternatives=[ep['critical_hit']] if ep.get('critical_hit') is not None else [False,True],
            critical_alternatives_are_not_priors=True,
            unresolved=sorted(set(limitations)),engine='damage.inverse.infer_attack_stat / damage.calculate',profile=PROFILE)
        stat=selector.get('offensive_stat') if selector and selector['constrains_opponent_offensive_stat'] else None
        before=deepcopy(line.get('speed_hard_stats',line['stats']).get(stat)) if stat in TRACKED else None
        self.append(member,pid,e,rec,'damage_joint_constraint' if supported else 'damage_unusable',obs,relation,
            status='conditional' if supported else 'unresolved',before=before,after=deepcopy(before),
            rule={'source':'saved HP resolution','profile':PROFILE,'verification':'pinned executable reference, not independent Champions certification'})
        if self.integrate and stat in {'attack','special_attack'} and before and member['initial_form']:
            from .inference_integration import invert_saved_hit
            numeric=invert_saved_hit(ep,ctx,native=member['initial_form'],retained=before['values'],stat=stat,battle_id=self.battle_id,configuration_rule=self.configuration_rule)
            relation['numerical_inference']=numeric
            self.updates[-1]['new_constraint']['numerical_inference']=numeric
            self.counter['inverse:'+numeric['status']]+=1
            if numeric['status']=='exact':
                numeric['single_observation_feasible']=deepcopy(numeric['feasible'])
                if numeric.get('item_support'):
                    numeric['feasible']=self.joined_item_stats(line,stat,numeric['item_support'])
                    numeric['shared_current_item_epoch']=True
                after,verdict=refine_numeric(before,numeric['feasible'],evidence_id=e['event_id'])
                if 'speed_hard_stats' in line:line['speed_hard_stats'][stat]=deepcopy(after)
                if not numeric['feasible']['values']:
                    self.conflicts.append(dict(event_id=e['event_id'],reason='shared_item_damage_empty',details=numeric))
                if verdict.get('excluded'):
                    line['stats'][stat]=after
                    self.append(member,pid,e,rec,'numeric_refinement',dict(stat=stat,episode=ep['episode_id']),
                        dict(feasible=numeric['feasible'],reference_profile=PROFILE),before=before,after=after,
                        excluded=verdict['excluded'],rule={'source':'existing inverse damage engine; all admitted alternatives unioned','profile':PROFILE})
            elif numeric['status']=='contradiction':self.conflicts.append(dict(event_id=e['event_id'],reason='inverse_damage_empty',details=numeric))
        self.counter['physical_damage_candidates' if category=='Physical' else 'special_damage_candidates' if category=='Special' else 'other_damage_candidates']+=1
        if supported:self.counter['causally_supported_damage']+=1
        for reason in sorted(set(limitations)):self.counter['limit:'+reason]+=1
        if e['event_id'] in self.negative_actions:return
        self.negative_actions.add(e['event_id'])
        # Completion boundaries come from action chronology, never an arbitrary seconds window.
        end=(ep.get('resolution_end') or {}).get('time')
        window=message_absence_window(rows,event_time(e),end) if end is not None else dict(complete=False,loss_displayed=False,unread_frames=None)
        ability=at.get('ability')
        try:ability_label=name(ability,'ability') if ability else None
        except (ValueError,KeyError):ability_label=None
        neg=dict(sources=source_refs(e),rule=USER_RULE,ability=ability_label,ability_active=True if ability else None,
            magic_guard_excluded=bool(ability_label and ability_label!='Magic Guard'),
            sheer_force_suppression_excluded=bool(ability_label and ability_label!='Sheer Force'),
            successful_hit=supported,not_protected=supported,not_immune=supported,
            resolution_complete=end is not None and ep.get('complete_endpoints') is True,
            multi_hit=bool(hit.get('hit_count') and hit['hit_count']>1),
            multi_hit_complete=hit.get('per_hit_status')=='supported',
            item_active=None,item_history_clear=None,after_move_hook_reached=None,
            display_window_complete=window['complete'],loss_displayed=window['loss_displayed'])
        if at.get('item') is not None:
            # A directly observed different item already resolves current Life Orb.
            neg['known_current_item']=at['item']
        if reviewed_absence:
            review=reviewed_absence.get(e['event_id'])
            if review:
                if review['actor_instance_id']!=pid or review['battle_id']!=self.battle_id:
                    raise ValueError('Reviewed negative evidence crosses actor/battle scope')
                if review['conditions']['ability']!=ability_label:
                    raise ValueError('Reviewed ability disagrees with the action-time source context')
                neg.update(review['conditions'])
                neg['sources']+=review['frames']
                neg['visual_review']=dict(reviewer=review['reviewer'],frame_count=review['frame_count'],
                    basis=review['basis'],limitations=review['limitations'])
                window=dict(window,complete=True,visual_review_overrides_unread_OCR=True,
                    reviewed_saved_frames=review['frame_count'],loss_displayed=False)
        verdict=absence_constraint(neg)
        before_items=dict(known_current_item=line['current_item'],excluded_current_items=line['excluded_current_items'].copy())
        if verdict['exclude_current_life_orb']:
            line['excluded_current_items'].append('Life Orb')
            self.counter['supported_current_item_exclusions']+=1
        self.append(member,pid,e,rec,'life_orb_counterfactual',
            dict(message_window=window,conditions=neg),verdict,status=verdict['status'],
            before=before_items,after=dict(known_current_item=line['current_item'],excluded_current_items=line['excluded_current_items'].copy()),
            excluded=['Life Orb'] if verdict['exclude_current_life_orb'] else [],rule=USER_RULE)
        self.counter['life_orb:'+verdict['status']]+=1

    def speed_pairs(self,records,contexts,cycles):
        moves=[]
        for rec in records:
            e=resolved_event(rec)
            if rec.get('application_status') not in ACCEPTED or e['event_type']!='move_execution':continue
            pid=actor_id(rec)
            if pid:moves.append((event_time(e),rec,pid))
        for i,cycle in enumerate(cycles):
            start=cycle['start'];end=cycle.get('end',cycles[i+1]['start'] if i+1<len(cycles) else float('inf'))
            certification=None
            if self.integrate:
                from .turns import certify_saved_cycle
                certification=certify_saved_cycle(records,cycle,end,contexts)
            rows=[row for row in moves if start<=row[0]<end]
            counts=Counter(row[2] for row in rows)
            # A repeated actor proves the cycle may span more than one decision.
            for j,(_,rec,pid) in enumerate(rows):
                if pid not in self.pid_member:continue
                member=self.members[self.pid_member[pid]];line=self.lineage(pid,member);e=resolved_event(rec)
                for _,other,qid in rows:
                    if qid==pid or (qid not in self.pid_member and ':self:' not in qid):continue
                    other_time=event_time(resolved_event(other))
                    if other_time<event_time(e):
                        left=resolved_event(other);right=e;first_pid=qid;second_pid=pid;receipt=rec
                    elif other_time>event_time(e):
                        left=e;right=resolved_event(other);first_pid=pid;second_pid=qid;receipt=other
                    else:
                        continue
                    pa=(left.get('canonical_references',{}).get('move') or {}).get('canonical_id')
                    pb=(right.get('canonical_references',{}).get('move') or {}).get('canonical_id')
                    pri=[];reasons=[]
                    for m in (pa,pb):
                        try:
                            f=knowledge().facts['moves'][m];pri.append(f.get('priority'))
                        except (KeyError,TypeError):pri.append(None)
                    if counts[pid]>1 or counts[qid]>1:reasons.append('actor acts repeatedly inside provisional command cycle')
                    if pri[0] is None or pri[1] is None:reasons.append('priority unavailable')
                    elif pri[0]!=pri[1]:reasons.append('different base priorities; no established equal effective-priority bracket')
                    if not certification or certification['status']!='certified_local_membership':
                        reasons.append('provisional command cycle is not a certified single order decision')
                    c1=contexts.get(left['event_id'],{});c2=contexts.get(right['event_id'],{})
                    actors={q:known_context(c2.get('pokemon',{}).get(q,{}),c2.get('field',{}),c2.get('sides',{}),'opponent' if ':opponent:' in q else 'self') for q in (qid,pid)}
                    relation=dict(first=first_pid,second=second_pid,base_priorities=pri,contexts=actors,
                        inequality='effective_speed(first) >= effective_speed(second), or <= under Trick Room; ties retained',
                        conditions=['same established ordering decision','equal effective priority','no order-changing activation','complete contemporaneous modifier state'],
                        admissibility_reasons=reasons,other_event_id=left['event_id'])
                    if certification:relation['certification']=certification
                    update=self.append(member,pid,right,receipt,'speed_order_candidate',
                        dict(first_event_id=left['event_id'],second_event_id=right['event_id'],command_cycle={k:v for k,v in cycle.items() if k!='end'},
                            joint_relation_id=digest([left['event_id'],right['event_id']])),
                        relation,status='unresolved' if reasons else 'conditional',
                        before=line['stats']['speed'],after=line['stats']['speed'],
                        affects=[self.pid_member[qid]] if qid in self.pid_member else (),
                        rule={'source':'saved command cycle and chronological accepted moves; no timestamp-distance threshold','engine':'speed_order.infer_speed v2','profile':PROFILE})
                    update['action_timestamp']=update['timestamp']
                    update['timestamp']=end if end!=float('inf') else max((event_time(r['event']) for r in records),default=update['timestamp'])
                    if self.integrate and not reasons and qid not in self.pid_member and line['stats']['speed']:
                        changes=[r['event']['event_id'] for r in records if event_time(left)<event_time(r['event'])<event_time(right)
                            and (r['event']['event_type'] in {'weather_change','terrain_change','trick_room_change','transformation','ability_activation','item_activation','item_change','status_change'}
                            or r['event']['event_type']=='stat_change' and 'speed' in r['event'].get('attributes',{}).get('stats',[])
                            or r['event']['event_type']=='side_condition_change' and r['event'].get('attributes',{}).get('condition')=='tailwind')]
                        if changes:relation['numeric_blockers']=['intervening modifier event requires full pending-queue context: '+','.join(changes)]
                        else:
                            from .speed_preference import SavedSpeedInference
                            lrec=next(r for r in records if r['event']['event_id']==left['event_id'])
                            rrec=next(r for r in records if r['event']['event_id']==right['event_id'])
                            before=deepcopy(line['stats']['speed'])
                            key=line['instance_id']
                            if key not in self.speed_ledgers:
                                line['speed_hard_stats']=deepcopy(line['stats'])
                                line['speed_hard_stats']['speed']=deepcopy(member['initial']['speed'])
                                self.speed_ledgers[key]=SavedSpeedInference(native=member['initial_form'],
                                    stat_constraints=line['speed_hard_stats'],battle_id=self.battle_id,configuration_rule=self.configuration_rule,
                                    excluded_items=line['excluded_current_items'])
                            # Match hypothetical loadout alternatives jointly.
                            # Observed current possession is not silently promoted
                            # to an original ownership reservation.
                            from speed_order.mechanics import mega_stones
                            team_domains={rid:({'none','Choice Scarf','Quick Claw'}|mega_stones())-
                                set(m['original_item_exclusions']) for rid,m in self.members.items()}
                            if 'Iron Ball' not in member['original_item_exclusions']:
                                team_domains[member['roster_id']].add('Iron Ball')
                            for other_key,ledger in self.speed_ledgers.items():
                                if other_key==key or not ledger.results or ledger.results[-1]['status']!='exact':continue
                                if ledger.results[-1]['policy'].get('observed_current_item') is not None:continue
                                rid=self.lineages[other_key]['roster_id']
                                team_domains[rid]={w['item'] for w in ledger.results[-1]['configuration_branches']}
                            from .speed_preference import held_item
                            if self.rule_verified and held_item(c1,pid) is None:
                                self.speed_ledgers[key].args.update(team_item_domains=team_domains,
                                    team_member=member['roster_id'],item_clause_enabled=True)
                            else:
                                for arg in ('team_item_domains','team_member','item_clause_enabled'):
                                    self.speed_ledgers[key].args.pop(arg,None)
                            numeric=self.speed_ledgers[key].add(lrec,rrec,c1,subject=pid,proof=certification,
                                stat_constraints=line['speed_hard_stats'])
                            line['speed_policy']=deepcopy(numeric)
                            relation['numerical_inference']=numeric
                            self.counter['speed_inverse:'+numeric['status']]+=1
                            if numeric['status']=='exact':
                                after=deepcopy(numeric['feasible'])
                                verdict=dict(excluded=sorted(set(before['values'])-set(after['values'])),
                                    restored=sorted(set(after['values'])-set(before['values'])))
                                if verdict['excluded'] or verdict['restored']:
                                    line['stats']['speed']=after
                                    refinement=self.append(member,pid,right,receipt,'numeric_refinement',dict(stat='speed',pair=update['observation']['joint_relation_id']),
                                        dict(feasible=numeric['feasible'],profile=PROFILE,preference=numeric['policy'],restored=verdict['restored']),before=before,after=after,excluded=verdict['excluded'],
                                        rule={'source':'accumulated M3 ordering witnesses; user Iron Ball last-resort preference; ties retained','profile':PROFILE})
                                    refinement['action_timestamp']=event_time(right);refinement['timestamp']=update['timestamp']
                            elif numeric['status']=='contradiction':self.conflicts.append(dict(event_id=right['event_id'],reason='inverse_speed_empty'))
                    self.counter['speed_pair_candidates']+=1
                    self.counter['speed_pair:'+update['classification']]+=1

    def result(self):
        for member in self.members.values():
            member['lineages']=[deepcopy(self.lineages[p]) for p in member['lineage_ids']]
            member['revealed']=bool(member['lineage_ids'])
            member['remaining_identity_ambiguity']=len(member['lineage_ids'])>1
            member['final_stats']={s:deepcopy(member['initial'][s]) for s in TRACKED}
            if self.integrate and member['lineages']:
                # Union unresolved lineages; never intersect different IDs.
                for s in TRACKED:
                    domains=[line['stats'][s] for line in member['lineages']]
                    if all(domains):member['final_stats'][s]=summary({v for domain in domains for v in domain['values']})
            member['final_stats_note']='Native-form projections; current-form epochs are separate. Different unproven encounter IDs are never intersected.'
            member['final_stat_representation']='Conservative retained marginal outer bounds; unresolved joint constraints have not been projected. Not every value is certified jointly feasible.'
            member['no_numeric_refinement_reason']='No complete admitted M3 numeric context yet; joint/conditional relations are retained without filling unknowns.'
            if self.integrate:
                member['no_numeric_refinement_reason']='All complete reference contexts were evaluated; unresolved branches retain support. Source-lineage reductions and the union across unresolved identities are reported separately.'
        refined={stat:set() for stat in TRACKED}
        for u in self.updates:
            if u['kind']=='numeric_refinement' and u['classification']=='inferred' and u.get('excluded'):
                refined[u['observation']['stat']].add(u['opponent_roster_id'])
        lineage_refined={s:{u.get('persistent_team_member_id',u['pokemon_instance_id']) for u in self.updates if u['kind']=='numeric_refinement'
            and u['observation'].get('stat')==s and u.get('excluded')} for s in TRACKED}
        if self.integrate:
            refined={s:{m['roster_id'] for m in self.members.values() if m['initial'][s] and
                m['final_stats'][s]['values']!=m['initial'][s]['values']} for s in TRACKED}
        source_conflicts=[dict(event_id=c.get('event_id'),reason=c.get('reason'),source='saved BattleState conflict')
            for c in self.final_state.get('conflicts',[])]
        self.counter['unique_speed_pair_candidates']=len({u['observation']['joint_relation_id'] for u in self.updates if u['kind']=='speed_order_candidate'})
        self.counter['usable_unconditional_speed_observations']=sum(u['kind']=='numeric_refinement' and u['observation'].get('stat')=='speed' for u in self.updates)
        self.counter['usable_unconditional_offense_observations']=sum(u['kind']=='numeric_refinement' and u['observation'].get('stat') in {'attack','special_attack'} for u in self.updates)
        return dict(version=VERSION,battle_id=self.battle_id,no_statistical_priors=True,
            population_weights=None,rankings=None,roster=list(self.members.values()),updates=self.updates,
            excluded_unaccepted_events=self.rejected,counts=dict(self.counter),contradictions=self.conflicts,
            source_state_conflicts=source_conflicts,
            selection=dict(required_selected_count=4,rule='user-confirmed ranked doubles / task bring-four scope',
                revealed_roster_members=[m['roster_id'] for m in self.members.values() if m['revealed']],
                unrevealed_roster_members=[m['roster_id'] for m in self.members.values() if not m['revealed']],
                unresolved_selected_slots=max(0,4-sum(m['revealed'] for m in self.members.values())),
                persistent_continuity_ambiguous=[m['roster_id'] for m in self.members.values() if m['remaining_identity_ambiguity']],
                caution='Roster association does not merge separate source encounter identities.'),
            numerical_refinement=dict(speed_pokemon=len(refined['speed']),attack_pokemon=len(refined['attack']),special_attack_pokemon=len(refined['special_attack']),
                source_lineages={s:len(v) for s,v in lineage_refined.items()},
                copied_current_stat_observations=self.counter['copied_current_stats'],
                meaning='Unconditional native-stat numerical refinements only; symbolic/joint constraints and form changes are counted separately'),
            item_clause_applicability=dict(verified=self.rule_verified,basis='User confirms all four are ranked doubles, clause applies to all six'),
            limitations=['Initial native form follows the saved preview identity; no opponent SP/nature/item prior',
                'Original-item ownership is separate from current activation; unproven return identities remain separate lineages',
                'Unknown stages, statuses, defense and effect context prevent unjustified numerical marginal projections'])

