"""Causal presentation projection over sealed evidence; never runs recognition.

Source events stay immutable. Transactions link observations, not inferred queue
positions. Reviewed identity links become usable only at their evidence time.
"""
from bisect import bisect_right
from collections import Counter
from copy import deepcopy
import json

from knowledge.stat_feasibility import summary
from speed_order import configuration_domain
from speed_order.core import knowledge, name
from speed_order.forms import training_stats, mega_base_form
from .speed_replay import canonical_fact, universe
from .speed_reviewed import projection, empirical_configs
from .speed_replay_offline import file_hash

VERSION = 'causal-replay-projection-v2'


def species_id(identity):
    entity = knowledge().entities.get(identity)
    return f'pokeapi:species:{entity.species_id}' if entity and entity.species_id else None


def segment_at(replay, timestamp):
    rows = [t for t in replay['turns'] if t['command_interval'][1] <= timestamp < t['next_command_interval'][1]]
    return rows[-1] if rows else None


def descriptor(event, raw):
    actor = (raw.get(event['id'], {}).get('actor') or {}).get('canonical_id')
    return dict(individual=event.get('instance_id'), species=species_id(actor), current_form=None,
                identity_confidence='recognized_source' if actor else 'unresolved',
                unresolved=[] if actor else ['source_actor_species_unresolved'])


def normalize(replay, states, raw, review, *, root):
    """Normalize every recall/arrival and account for every saved occupant edge."""
    if replay['battle_id'] not in review['battles'] or review['origin'] != 'recorded':
        raise ValueError('Recorded battle review required')
    audit = review['battles'][replay['battle_id']]
    originals = {e['id']: e for e in replay['timeline']}
    for eid, source in audit['sources'].items():
        e = originals[eid]
        if source['source_id'] not in {s['source_id'] for s in e['sources']} or file_hash(root/source['image']) != source['sha256']:
            raise ValueError('Changed or mismatched reviewed source')
    for form in audit['transformations']:
        original=originals[form['event_id']]
        actor=(raw.get(form['event_id'],{}).get('actor') or {}).get('canonical_id')
        sources=[form['source']]+form.get('supporting_sources',[])
        if (species_id(form['original_form'])!=species_id(form['resulting_form']) or
            species_id(actor)!=species_id(form['original_form']) or
            form['timestamp']<max(s['timestamp'] for s in sources) or
            not form['interval'][0]<=form['timestamp']<=form['interval'][1] or
            not form['individual'].startswith(replay['battle_id']+':') or
            original['kind']!='transformation'):
            raise ValueError('Invalid causal species/form transformation review')
    for eid, phase in audit.get('phase_reviews',{}).items():
        source=phase['command_source']
        frame=next((f for f in replay['frames'] if f['source_id']==source['source_id']),None)
        if not frame or frame['timestamp']>originals[eid]['timestamp'] or file_hash(root/source['image'])!=source['sha256']:
            raise ValueError('Invalid normal-command phase source')
    result = []; consumed = {}; pending = {}; fainted = {}; seen_sides = set(); gaps = []
    moves = {a['event_id']: a for t in replay['turns'] for a in t['actions']}
    for e in sorted(replay['timeline'], key=lambda e: (e['timestamp'], e['id'])):
        kind = e['kind']; side = e.get('side'); time = e['timestamp']; turn = segment_at(replay, time)
        revelation=next((r for r in audit.get('revelations',[]) if r['event_id']==e['id']),None)
        if revelation:
            result.append(dict(deepcopy(revelation),id='revelation:'+e['id'],kind='item_revelation',phase='mega_activation',
                side=side,segment_id=turn['turn_id'] if turn else None,sources=deepcopy(e['sources']),source_event_ids=[e['id']]))
        if kind == 'faint' and side in {'self', 'opponent'}:
            fainted.setdefault(side, []).append(e)
        if kind == 'switch_out':
            if side in pending:
                gaps.append(dict(event_id=pending[side]['id'], reason='another_recall_before_arrival'))
                pending[side]['unresolved'].append('incoming_pokemon_unresolved')
            prior_moves = [m for m in replay['timeline'] if m['kind'] == 'move_execution' and
                           m.get('instance_id') == e.get('instance_id') and m['timestamp'] < time and
                           (not turn or m['timestamp'] >= turn['command_interval'][1])]
            previous = prior_moves[-1] if prior_moves else None
            move = (raw.get(previous['id'], {}).get('canonical_references', {}).get('move') or {}).get('canonical_id') if previous else None
            fact = knowledge().entities.get(move)
            # A pivot requires explicit return wording and its own earlier move;
            # mere HUD change or proximity to a move is insufficient.
            pivot = previous and fact and fact.names.get('en') in {'Parting Shot', 'U-turn', 'Volt Switch', 'Flip Turn'} and '要回到' in (e.get('text') or '')
            earlier_actions = [a for a in moves.values() if turn and a['timestamp'] >= turn['command_interval'][1] and a['timestamp'] < time]
            voluntary = turn and not earlier_actions and any(w in (e.get('text') or '') for w in ['换下', '回来'])
            phase_review=audit.get('phase_reviews',{}).get(e['id'])
            if phase_review:
                command_time=phase_review['command_source']['timestamp']
                if any(m['kind']=='move_execution' and command_time<m['timestamp']<time for m in replay['timeline']):
                    raise ValueError('Reviewed voluntary switch phase has intervening move evidence')
                voluntary=phase_review['phase']=='voluntary_switch'
            category = 'pivot_replacement' if pivot else 'voluntary_switch' if voluntary else 'unresolved_transition'
            tx = dict(id='transition:'+e['id'], kind=category, timestamp=time, interval=[time, time],
                segment_id=turn['turn_id'] if turn else None, local_index=turn['local_index'] if turn else None,
                phase='move_resolution' if pivot else 'voluntary_switch' if voluntary else 'unresolved', side=side,
                outgoing=descriptor(e, raw), incoming=None, arrival_time=None,
                reason='move_induced_pivot' if pivot else 'normal_command_recall_before_moves' if voluntary else 'phase_timing_not_certified',
                pivot_move_id=previous['id'] if pivot else None,
                source_event_ids=[e['id']], sources=deepcopy(e.get('sources', [])),
                confidence='agent_source_reviewed' if e['id'] in audit['sources'] else 'recognized_unreviewed',
                identity_confidence='source_individuals_separate_until_reviewed_link',
                speed_comparable=False, unresolved=[] if pivot or voluntary else ['normal_command_segment_or_phase_coverage_missing'])
            if phase_review:
                tx['sources'].append(deepcopy(phase_review['command_source']))
                tx['partial_window_ref']=phase_review['partial_window_ref']
                tx['membership_gap']='Frozen local segment unavailable; command-frame phase review does not create a turn boundary'
            result.append(tx); pending[side] = tx; consumed[e['id']] = tx['id']
        elif kind == 'send_out':
            tx = pending.pop(side, None)
            if tx:
                if turn and tx.get('segment_id') and turn['turn_id']!=tx['segment_id']:
                    tx.update(kind='unresolved_transition',phase='unresolved',reason='arrival_in_different_local_segment')
                    tx['unresolved'].append('recall_arrival_pairing_crosses_command_boundary')
                tx.update(incoming=descriptor(e, raw), arrival_time=time, interval=[tx['timestamp'], time])
                tx['arrival_source_event_id']=e['id']
                tx['source_event_ids'].append(e['id']); tx['sources'] += deepcopy(e.get('sources', [])); consumed[e['id']] = tx['id']
            else:
                f = fainted.get(side, [])
                departure = f.pop(0) if f else None
                initial = side not in seen_sides or (not turn and time < replay['turns'][0]['command_interval'][0])
                category = 'forced_replacement' if departure else 'initial_send_out' if initial else 'unresolved_transition'
                tx = dict(id='transition:'+e['id'],kind=category,timestamp=time,interval=[time,time],
                    segment_id=turn['turn_id'] if turn else None,local_index=turn['local_index'] if turn else None,
                    phase='replacement' if departure else 'deployment' if initial else 'unresolved',side=side,
                    outgoing=descriptor(departure,raw) if departure else None,incoming=descriptor(e,raw),arrival_time=time,
                    reason='replacement_after_recognized_faint' if departure else 'initial_deployment' if initial else 'no_correlated_departure',
                    pivot_move_id=None,source_event_ids=[e['id']]+([departure['id']] if departure else []),
                    sources=deepcopy(e['sources'])+(deepcopy(departure['sources']) if departure else []),
                    confidence='recognized_source',identity_confidence='recognized_source',speed_comparable=False,
                    unresolved=[] if initial or departure else ['outgoing_individual_or_switch_reason_unknown'])
                result.append(tx); consumed[e['id']] = tx['id']
            seen_sides.add(side)
        elif kind == 'move_execution':
            a = moves.get(e['id'], {})
            result.append(dict(id=e['id'],kind='executed_move',timestamp=time,phase='move',side=side,
                individual=e.get('instance_id'),move=a.get('move') or (raw.get(e['id'],{}).get('canonical_references',{}).get('move') or {}).get('canonical_id'),
                text=e.get('text'),segment_id=turn['turn_id'] if turn else None,
                sources=deepcopy(e.get('sources',[])),priority=deepcopy(a.get('priority')),source_event_ids=[e['id']]))
        elif kind == 'transformation':
            form = next((f for f in audit['transformations'] if f['event_id']==e['id']), None)
            result.append(dict(id='mega:'+e['id'],kind='mega_evolution' if form else 'unresolved_transformation',
                phase='mega_evolution',timestamp=max(time,form['timestamp']) if form else time,
                interval=deepcopy(form['interval']) if form else [time,time],side=side,
                individual=form['individual'] if form else e.get('instance_id'),original_form=form['original_form'] if form else None,
                resulting_form=form['resulting_form'] if form else None,
                segment_id=turn['turn_id'] if turn else None,sources=deepcopy(e['sources'])+(deepcopy(form.get('supporting_sources',[])) if form else []),source_event_ids=[e['id']],
                timing_basis=form.get('timing_basis') if form else None,
                confidence=form['confidence'] if form else 'unresolved',basis=form['basis'] if form else 'unresolved_source_form'))
    for tx in pending.values():tx['unresolved'].append('incoming_pokemon_unresolved')
    # Prevented/selected actions remain distinct from moves and replacement phases.
    for e in replay.get('reviewed_inference',{}).get('review',{}).get('events',[]) if replay.get('reviewed_inference',{}).get('review') else []:
        if e['kind'] in {'prevented_action','selected_action'}:
            result.append(dict(deepcopy(e),phase='move' if e['kind']=='prevented_action' else 'selection',segment_id=(segment_at(replay,e['timestamp']) or {}).get('turn_id')))
    edges = []
    for eid,pair in states['snapshots'].items():
        a = pair.get('before',{}).get('observable',{}).get('occupancy',{})
        b = pair.get('after',{}).get('observable',{}).get('occupancy',{})
        if a != b:
            edges.append(dict(source_event_id=eid,before=a,after=b,transaction_id=consumed.get(eid),
                status='accounted_for' if eid in consumed else 'unresolved_transition',
                gaps=[] if eid in consumed else ['occupant_edge_without_recall_arrival_transaction']))
    # Expose every unexplained edge as a visible event rather than hiding it.
    for edge in edges:
        if edge['status'] != 'accounted_for':
            e = originals.get(edge['source_event_id'])
            if e:result.append(dict(id='edge:'+e['id'],kind='unresolved_transition',timestamp=e['timestamp'],phase='unresolved',
                side=e.get('side'),outgoing=None,incoming=None,arrival_time=None,source_event_ids=[e['id']],sources=e['sources'],
                unresolved=edge['gaps'],segment_id=(segment_at(replay,e['timestamp']) or {}).get('turn_id')))
    result.sort(key=lambda e:(e['timestamp'],e['id']))
    # Enrich presentation identities only with form/link evidence already available
    # at that descriptor's timestamp. Original encounter IDs remain in sources.
    for event in result:
        for field, when in [('outgoing',event['timestamp']),('incoming',event.get('arrival_time'))]:
            actor = event.get(field)
            if not actor or when is None:continue
            aliases={l['alias']:l['individual'] for l in audit.get('identity_links',[]) if l['available_at']<=when}
            def canonical(iid):
                while iid in aliases:iid=aliases[iid]
                return iid
            iid=canonical(actor['individual'])
            prior=[f for f in audit['transformations'] if canonical(f['individual'])==iid and f['timestamp']<=when]
            if prior:actor['current_form']=prior[-1]['resulting_form']
    positions = Counter()
    for e in result:
        key = (e.get('segment_id') or e.get('partial_window_ref'), e['phase'])
        positions[key] += 1
        e['observed_phase_position'] = positions[key] if key[0] else None
        e['phase_rank'] = {'voluntary_switch':0,'mega_evolution':1,'move':2}.get(e['phase'])
    for e in result:
        if e.get('pivot_move_id'):
            move = next((m for m in result if m['id']==e['pivot_move_id']),None)
            if move:move['pivot_transaction_id']=e['id']
    return result,dict(occupant_edges=edges,source_review_gaps=gaps,counts=dict(Counter(e['kind'] for e in result)),
                       missed_occupant_edges=sum(e['status']!='accounted_for' for e in edges))


def visible_transaction(event, timestamp):
    """Project arrival fields at their own evidence time, not departure time."""
    result=deepcopy(event)
    result['sources']=[s for s in result.get('sources',[]) if s.get('timestamp',timestamp)<=timestamp]
    if event.get('arrival_time') is not None and event['arrival_time']>timestamp:
        result['incoming']=None;result['arrival_time']=None
        result['interval']=[event['timestamp'],None]
        result['source_event_ids']=[i for i in result.get('source_event_ids',[]) if i!=event.get('arrival_source_event_id')]
        result['arrival_source_event_id']=None
        result['unresolved']=result.get('unresolved',[])+['incoming_pokemon_unresolved']
    return result


def support_layers(full, empirical, *, complete_before, incomplete, empirical_rows, conditions, unresolved):
    """Keep observed joint builds and complete reference alternatives distinct."""
    return dict(observed=dict(speed=empirical['speed'],complete_before=complete_before,
                    complete_after=empirical['configuration_count'],incomplete_excluded=incomplete,
                    builds=empirical_rows,scope='Observed joint published builds only; absence does not establish illegality'),
        full=dict(**full,status='unresolved' if unresolved else 'exact_reference_projection',unresolved_reasons=unresolved,
                  definition='Pinned native/catalog/SP reference support under supplied conditions, not independent Champions certification'),
        conditions=conditions)


def _domain(identity):
    u=universe(identity)
    configs=configuration_domain(identity=identity,form='as_named' if knowledge().entities[identity].form_id else 'base',
        abilities=u['abilities'],items=u['item_representatives'],max_configurations=100000)['configurations']
    return configs,u


def project(replay, semantic, states, raw, index, review):
    """Add causal state/support views without mutating original event snapshots."""
    kb=knowledge();source_snaps=deepcopy(replay['snapshots']);snap_times=[s['timestamp'] for s in source_snaps]
    review_battle=review['battles'][replay['battle_id']];links=review_battle.get('identity_links',[])
    domain_cache={};empirical_cache={};form_support={}
    def base_support(identity):
        if identity not in domain_cache:domain_cache[identity]=_domain(identity)
        return domain_cache[identity]
    # Preserve the actual original training and required stone through Mega.
    for e in semantic:
        if e['kind']!='mega_evolution':continue
        target=e['resulting_form'];base=e['original_form'];u=universe(base,item=kb.facts['pokemon'][target]['required_item'])
        configs=configuration_domain(identity=base,form='base',abilities=u['abilities'],items=u['item_representatives'],max_configurations=100000)['configurations']
        target_configs=[]
        for c in configs:
            stats=training_stats(target,c['training'])
            target_configs.append(dict(deepcopy(c),speed=stats['speed'][0],form=target,ability=kb.facts['pokemon'][target]['ability_names'][0],
                original_form=base,original_speed=c['speed'],original_ability=c['ability']))
        form_support[e['id']]=dict(configurations=target_configs,projection=projection(target_configs,u['item_equivalence_classes']),
            original_domain_ref=base,required_item=kb.facts['pokemon'][target]['required_item'],
            condition='Preserved training alignment/SP and required original Mega stone; native ability replaced; no transfer/suppression history certified',
            training_preserved=True)
    times=sorted(set(snap_times+[e['timestamp'] for e in semantic]+[e['arrival_time'] for e in semantic if e.get('arrival_time') is not None]+[l['available_at'] for l in links]))
    snapshots=[];support_catalog={};observed_builds={}
    for time in times:
        pos=bisect_right(snap_times,time)-1
        original=deepcopy(source_snaps[pos]) if pos>=0 else dict(opponents={},field={})
        original['timestamp']=time
        available=[e for e in semantic if e['timestamp']<=time]
        aliases={l['alias']:l['individual'] for l in links if l['available_at']<=time}
        def stable(iid):
            while iid in aliases:iid=aliases[iid]
            return iid
        occupancy={'self':{},'opponent':{}};forms={};identities={};identity_sources={};items={}
        for e in available:
            if e['kind']=='item_revelation':items[stable(e['individual'])]=e['item']
            if e['kind']=='mega_evolution':
                forms[stable(e['individual'])]=e
            if e['kind'] in {'initial_send_out','voluntary_switch','pivot_replacement','forced_replacement','unresolved_transition'}:
                outgoing=e.get('outgoing');incoming=e.get('incoming')
                if outgoing and outgoing.get('individual'):
                    iid=stable(outgoing['individual']);occupancy.setdefault(e['side'],{}).pop(iid,None)
                    if outgoing.get('species'):identities[iid]=outgoing['species']
                if incoming and e.get('arrival_time') is not None and e['arrival_time']<=time and incoming.get('individual'):
                    iid=stable(incoming['individual']);occupancy.setdefault(e['side'],{})[iid]=deepcopy(incoming)
                    if incoming.get('species'):identities[iid]=incoming['species'];identity_sources[iid]=e['arrival_time']
        # Remove recognized fainted occupants only at their observed timestamp.
        for e in replay['timeline']:
            if e['timestamp']<=time and e['kind']=='faint':
                iid=stable(e.get('instance_id'));last_arrival=identity_sources.get(iid,-1)
                if e['timestamp']>=last_arrival:occupancy.get(e.get('side'),{}).pop(iid,None)
        for side in occupancy.values():
            for iid,actor in side.items():
                if iid in forms:actor['current_form']=forms[iid]['resulting_form']
        opponents={}
        for iid,p in original.get('opponents',{}).items():
            key=stable(iid);p=deepcopy(p);p['individual']=key
            sid=identities.get(key) or species_id(p.get('current_form'))
            # Every unresolved possible form must share a canonical species.
            if sid is None:
                sids={species_id(k) for k in p.get('possible_forms',[])}-{None}
                if len(sids)==1:sid=next(iter(sids))
            p['species']=sid;p['active']=key in occupancy['opponent']
            if key in items:p['observed_item']=items[key]
            if key in forms:
                e=forms[key];p.update(current_form=e['resulting_form'],possible_forms=[e['resulting_form']],
                    observed_item=kb.facts['pokemon'][e['resulting_form']]['required_item'],
                    form_evidence=deepcopy(e),legal_unmodified_speed=form_support[e['id']]['projection']['speed'])
                p['universe_ref']=e['resulting_form'];p.pop('universe_refs',None)
                p['form_scope']='Source-reviewed current form; original training and required stone retained'
                p['active_ability']=kb.facts['pokemon'][e['resulting_form']]['ability_names'][0]
                p['active_ability_basis']='Canonical Mega ability after confirmed transformation; not an independent ability observation'
            current=p.get('current_form');alternatives=[current] if current else p.get('possible_forms',[])
            if key not in forms and current is None:
                # Catalog Mega possibilities are eventual build forms, not
                # active forms before an observed transformation.
                alternatives=[ident for ident in alternatives if mega_base_form(ident) is None]
                p['possible_forms']=alternatives
            updates=[u for u in replay['reviewed_inference']['updates'] if u['timestamp']<=time and any(key in [stable(x) for x in replay['reviewed_inference'].get('review',{}).get('identity_links',{}).get(a,[])] for a in u['after'])] if replay['reviewed_inference'].get('review') else []
            known_item=items.get(key)
            support_key=json.dumps([alternatives,updates[-1]['id'] if updates else None,forms[key]['id'] if key in forms else None,known_item])
            if support_key in support_catalog:
                p['support_ref']=support_key;p['legal_unmodified_speed']=support_catalog[support_key]['full']['speed']
                p['configuration_count']=support_catalog[support_key]['full']['configuration_count']
                p['unresolved_reasons']=support_catalog[support_key]['full']['unresolved_reasons']
                opponents[key]=p
                continue
            configurations=[];branches=[];reasons=[];empirical=[];before_count=0;incomplete=0
            for ident in alternatives:
                configs,u=base_support(ident)
                if known_item:configs=[c for c in configs if c['item']==known_item]
                branches+=projection(configs,u['item_equivalence_classes'])['branches'];configurations+=configs
                reasons+=u['unresolved_reasons']
                if ident not in empirical_cache:
                    rows,issues=empirical_configs(index,ident,u['item_equivalence_classes']);empirical_cache[ident]=(rows,issues)
                rows,issues=empirical_cache[ident];empirical+=deepcopy(rows);before_count+=len(rows)
                observed_builds.update({c['id']:c['observed_build'] for c in rows})
                incomplete+=index.support(ident)['incomplete_builds']
                if issues:reasons.append('published_configuration_mapping_unresolved')
            if known_item:empirical=[c for c in empirical if c['item']==known_item]
            full=dict(speed=summary(c['speed'] for c in configurations),configuration_count=len(configurations),branches=branches)
            conditions=[]
            if updates:
                update=updates[-1];actor=next(a for a in update['after'] if key in [stable(x) for x in replay['reviewed_inference']['review']['identity_links'].get(a,[])])
                # The alias membership itself must be evidenced at this time.
                full=deepcopy(update['after'][actor]);ep=update['empirical_after'][actor]
                empirical=[c for c in empirical if c['id'] in set(update.get('empirical_survivor_ids',{}).get(actor,[]))]
                conditions=update.get('inherited_conditions',update['assumptions'])
            else:ep=dict(speed=summary(c['speed'] for c in empirical),configuration_count=len(empirical))
            if key in forms:
                full=deepcopy(form_support[forms[key]['id']]['projection']);reasons+=universe(current)['unresolved_reasons']
                conditions.append(form_support[forms[key]['id']]['condition'])
            full['training_domain_refs']=alternatives
            full['surviving_configuration_ids']=update.get('model_survivor_ids',{}).get(actor) if updates else None
            full['training_scope']='Existing joint alignment/SP domain with <=66 budget; surviving IDs refer to deterministic configuration_domain iteration, not independent marginal combinations'
            if not current:reasons.append('current_form_unresolved')
            reasons+=['action_time_modifiers_not_independently_certified']
            support_catalog[support_key]=support_layers(full,ep,complete_before=before_count,incomplete=incomplete,
                empirical_rows=[c['id'] for c in empirical],conditions=conditions,unresolved=sorted(set(reasons)))
            support_catalog[support_key]['observed']['ability_mappings']={c['id']:dict(c['ability_state'],speed=c['speed']) for c in empirical}
            support_catalog[support_key]['observed']['eligibility_issues']=[issue for ident in alternatives for issue in empirical_cache[ident][1]]
            p['support_ref']=support_key
            p['configuration_count']=full['configuration_count']
            p['unresolved_reasons']=sorted(set(reasons))
            p['legal_unmodified_speed']=full['speed'];opponents[key]=p
        original.update(opponents=opponents,occupancy=occupancy,identity_aliases=aliases,
            semantic_event_ids=[e['id'] for e in available])
        snapshots.append(original)
    return dict(snapshots=snapshots,form_configuration_support=form_support,
                support_catalog=support_catalog,observed_builds=observed_builds)
