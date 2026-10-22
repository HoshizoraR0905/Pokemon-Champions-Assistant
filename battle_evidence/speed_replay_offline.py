"""M3.2.2 Stage A over sealed caches, with no recognition or posterior updates."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
from time import perf_counter
import hashlib
import json

from battle_artifacts import BattleArtifacts
from team_configuration import TeamConfiguration
from .action_offline import inputs_for, bind_team
from .speed_adapter import audit_pair, own_form_speed
from .speed_replay import (VERSION, TimeIndex, DeterministicHistory, available_time, causal_state,
                           canonical_fact, current_identity, possible_forms, legal_projection, universe)
from knowledge.stat_feasibility import summary as speed_summary

ROOT=Path(__file__).resolve().parents[1]


def file_hash(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()


def atomic(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True)+'\n');temp.replace(path)


def select_actions(battle):
    """Select only compatible completed artifacts; never rerun their Bayesian stage."""
    compatible=[];rejected=[];hashes={}
    def hashed(path):
        path=Path(path)
        if str(path) not in hashes:
            hashes[str(path)]=file_hash(path) if path.is_file() else None
        return hashes[str(path)]
    candidates=list(battle.cache('m341-actions').glob('*/manifest.json'))+list(battle.cache('m322-actions').glob('*/manifest.json'))
    for path in sorted(candidates):
        m=json.loads(path.read_text())
        if m.get('status')!='complete':
            rejected.append(dict(path=str(path),reason='not_complete'));continue
        expected={**m['identity']['inputs'],**m['identity']['dependencies']}
        changed=[p for p,sha in expected.items() if hashed(p)!=sha]
        changed += [str(path.parent/name) for name,sha in m['outputs'].items() if hashed(path.parent/name)!=sha]
        if changed:
            rejected.append(dict(path=str(path),reason='changed_identity_or_output',paths=changed));continue
        compatible.append(path)
    if not compatible:
        # A catalog correction can invalidate the action projection without
        # invalidating sealed recognition. Reconstruct only deterministic action
        # records; do not invoke action_inference.analyse or its Bayesian stage.
        from .actions import reconstruct
        visual,states,raw,paths=inputs_for(battle)
        dependencies=[Path(__file__),Path(__file__).with_name('actions.py'),
            Path(__file__).with_name('action_offline.py'),ROOT/'speed_order/core.py',
            ROOT/'speed_order/execution.py',ROOT/'knowledge/__init__.py',
            ROOT/'knowledge/data/champions_facts.json',ROOT/'knowledge/data/manifest.json']
        identity=dict(version='m322-deterministic-actions-v1',inputs={str(p):file_hash(p) for p in paths},
            dependencies={str(p):file_hash(p) for p in dependencies},
            reason='No compatible cached action projection; reuse sealed events without inference or recognition')
        dest=battle.cache('m322-actions/'+digest(identity)[:16]);dest.mkdir(parents=True,exist_ok=True)
        manifest=dest/'manifest.json';m=dict(status='running',stage='deterministic_action_projection',identity=identity)
        atomic(manifest,m)
        try:
            data=reconstruct(visual,states['snapshots'],source_events=raw)
            atomic(dest/'actions.json',data)
            m.update(status='complete',stage='complete',outputs={'actions.json':file_hash(dest/'actions.json')},
                metrics=dict(video_decodes=0,ocr_calls=0,state_engine_replays=0,bayesian_updates=0))
            atomic(manifest,m)
        except Exception as exc:
            m.update(status='failed',error=repr(exc));atomic(manifest,m);raise
        return data,manifest,dict(selected=str(manifest),compatible=[str(manifest)],rejected=rejected,
                                  refreshed='deterministic_projection_only')
    path=compatible[-1];data=json.loads((path.parent/'actions.json').read_text());battle.check_identity(data['battle_id'])
    return data,path,dict(selected=str(path),compatible=[str(p) for p in compatible],rejected=rejected)


def verify_video(battle, manifest):
    identity=manifest['identity'];path=Path(identity['video_path']);stat=path.stat()
    stamp=dict(path=str(path),size=stat.st_size,mtime_ns=stat.st_mtime_ns,inode=stat.st_ino,
               acquisition_sha256=identity['video_sha256'])
    receipt=battle.cache('m322-speed-replay/video-identity.json')
    if receipt.exists():
        saved=json.loads(receipt.read_text())
        if saved.get('identity')==stamp and saved.get('sha256')==identity['video_sha256']:
            return dict(identity=stamp,sha256=saved['sha256'],hash_reused=True)
    sha=file_hash(path)
    if sha!=identity['video_sha256']:
        raise ValueError('Source video differs from sealed recognition input')
    atomic(receipt,dict(identity=stamp,sha256=sha))
    return dict(identity=stamp,sha256=sha,hash_reused=False)


def frame_rows(rows):
    keys=('timestamp','source_id','image','sha256','source_pts','source_time_base',
          'seek_origin_seconds','target_timestamp','chunk_id','chunk_timestamp','global_timestamp')
    return sorted([{k:r[k] for k in keys if k in r} for r in rows],key=lambda r:r['timestamp'])


def load_team(battle, actions, *, root):
    path=Path(root)/'tests/fixtures/battle_evidence/sample-team7-reviewed.json'
    roster_path=Path(root)/'tests/fixtures/battle_evidence/team7-roster-bindings.json'
    team=TeamConfiguration.load(path);rosters=json.loads(roster_path.read_text())['roster_reviews']
    if team.data['knowledge_snapshot_sha256']!=team.knowledge.snapshot_id:
        raise ValueError('Reviewed team identity snapshot differs from current canonical knowledge')
    paths=[path,roster_path]
    for source in team.data['sources']:
        image=Path(root)/source['path']
        if file_hash(image)!=source['sha256']:
            raise ValueError('Original TeamConfiguration source frame changed')
        paths.append(image)
    builds,binding=bind_team(actions,team,rosters,root=root)
    review=next(r for r in rosters if r['battle_id']==battle.battle_id)
    paths.append(Path(root)/review['image'])
    members={m['instance_id']:m for m in team.data['members']}
    records={}
    for (bid,iid),build in builds.records.items():
        member=members[binding['bindings'][iid]];fields=member['fields'];p=deepcopy(build)
        allocations={s:fields['allocation_'+s+'_display'] for s in build['stats']}
        if all(f['status']=='manual_verified' and not f.get('conflicts') for f in allocations.values()):
            p['training_points']={s:f['value'] for s,f in allocations.items()}
            p['alignment']=deepcopy(member['reviewed_stat_alignment'])
        records[iid]=p
    return team,records,binding,paths,review


def timed_review(review, event_times, frames):
    """Recorded attachments must resolve every source to the existing chronology."""
    result=deepcopy(review)
    if result.get('origin')!='recorded':
        return result
    if result.get('reviewer',{}).get('kind') not in {'agent','human'} or not result['reviewer'].get('id'):
        raise ValueError('Recorded attachments require explicit agent/human reviewer identity')
    known=dict(event_times)
    for frame in frames:
        known[frame['source_id']]=frame['timestamp'];known[frame['image']]=frame['timestamp']
    required_times=[]
    def visit(value):
        if isinstance(value,dict):
            if set(value)=={'sources','basis','confidence'}:
                for source in value['sources']:
                    if source not in known or known[source] is None:
                        raise ValueError('Unresolvable chronological review source: '+str(source))
                    required_times.append(known[source])
            for child in value.values():
                visit(child)
        elif isinstance(value,list):
            for child in value:
                visit(child)
    visit(result)
    result['available_at']=max([result['available_at']]+required_times)
    return result


def chronological_audit(battle_id, visual, states, raw, actions, builds, frames, *, reviews=None,
                        max_configurations=100000, max_evaluations=100000):
    """Build only meaningful event snapshots; source frame density remains untouched."""
    if visual.get('schema')!='normal-screen-three-hud-v2.2':
        raise ValueError('Frozen visual v2.2 must be selected explicitly')
    reviews=reviews or {}; ledger=visual['reconstruction']['ledger']
    events={e['id']:e for e in ledger};event_times={eid:available_time(e) for eid,e in events.items()}
    if len(events)!=len(ledger):
        raise ValueError('Revised/duplicate source IDs need explicit evidence reconstruction')
    for eid,e in events.items():
        if e.get('source_retracted') or e.get('source_revision_requires_review') or e.get('kind')=='inactive_source_observation':
            event_times[eid]=None # Never use invalidated evidence as a positive fact.
    actions_by_id={a['id']:a for a in actions['actions']}
    saved=states['snapshots'];comparisons=[]
    if set(reviews)-{r['id'] for r in actions['relations']}:
        raise ValueError('Review references an unknown comparison')
    for relation in actions['relations']:
        first=actions_by_id[relation['action_ids'][0]]
        when=available_time(first)
        observable=causal_state(saved.get(first['event_id'],{}).get('before',{}),when,event_times)
        review=reviews.get(relation['id']);review_error=None
        if review is not None:
            try:
                review=timed_review(review,event_times,frames)
            except (ValueError,TypeError,KeyError) as exc:
                review=None;review_error=str(exc)
        comparison=audit_pair(relation,actions_by_id,observable,builds,review=review)
        if review_error:
            comparison['blockers'].append(review_error)
        comparison['intervening_event_ids']=deepcopy(relation['intervening_event_ids'])
        comparisons.append(comparison)
    timeline=[]
    for eid,e in events.items():
        if e.get('source_event_type') in {'hud_observation','visual_observation','command_cycle','effectiveness','hp_change'}:
            continue
        when=event_times[eid]
        if when is None:
            continue
        original=raw.get(eid,{})
        timeline.append(dict(id=eid,timestamp=when,kind=e.get('source_event_type'),instance_id=e.get('instance_id'),
            side=e.get('side'),text=e.get('text'),sources=deepcopy(e.get('sources',[])),
            confidence=dict(source_status=e.get('source_status'),recognition=original.get('ocr_confidence'),
                            parsing=original.get('parsing_confidence'),uncertainty=deepcopy(e.get('uncertainty',[]))),
            canonical_references=deepcopy(original.get('canonical_references',{})),
            interpretation='recognized source evidence; complete context and correctness not automatically certified'))
    for segment in visual['visual']['segments']:
        # These are retrospective phase labels, explicitly not hidden state facts.
        timeline.append(dict(id='m322:command:'+segment['id'],timestamp=segment['start'][1],kind='normal_command_entry',
            local_index=segment['local_index'],segment_id=segment['id'],interval=segment['start'],status=segment['status'],
            provenance='frozen v2.2 retrospective boundary, applied no earlier than upper interval bound'))
    phase_rows=visual['visual'].get('phase_history',[])
    previous_phase=None
    for phase in phase_rows:
        if phase['phase']!=previous_phase:
            timeline.append(dict(id='m322:phase:'+phase['frame_id'],timestamp=phase['timestamp'],kind='visual_phase',
                phase=phase['phase'],possible_phases=phase['possible_phases'],source_id=phase['source_id'],
                provenance='frozen v2.2 derived visual phase; not independent human ground truth'))
        previous_phase=phase['phase']
    for comparison in comparisons:
        if comparison['timestamp'] is not None:
            timeline.append(dict(id='m322:comparison:'+comparison['id'],timestamp=comparison['timestamp'],
                                 kind='speed_comparison',comparison_id=comparison['id']))
    timeline.sort(key=lambda e:(e['timestamp'],e['kind']=='speed_comparison',e['id']))
    index=TimeIndex(frames);phase_index=TimeIndex(phase_rows)
    universe_catalog={};training_domains={};snapshots=[];histories={};solver_seconds=0.
    by_comparison={c['id']:c for c in comparisons};latest_observable={};observed_actions=[];last_saved_time=-1
    snapshot_sources=sorted([(event_times[eid],eid,pair['after']) for eid,pair in saved.items()
        if eid in event_times and event_times[eid] is not None and pair.get('after')],key=lambda v:(v[0],events[v[1]]['position']))
    cursor=0;last_subjects={}
    for event in timeline:
        timestamp=event['timestamp']
        while cursor<len(snapshot_sources) and snapshot_sources[cursor][0]<=timestamp:
            when,eid,snapshot=snapshot_sources[cursor]
            latest_observable=causal_state(snapshot,when,event_times)
            last_saved_time=when;cursor+=1
        if event['kind']=='move_execution':
            observed_actions += [a['id'] for a in actions['actions'] if a['event_id']==event['id']]
        if event['kind']=='speed_comparison':
            comparison=by_comparison[event['comparison_id']]
            if comparison['status']=='prepared':
                subject=comparison['observation']['subject'];configs=comparison.pop('configurations')
                if subject not in histories:
                    histories[subject]=DeterministicHistory(configs,profile='showdown-champions-reference-v1',max_evaluations=max_evaluations)
                elif digest(histories[subject].configurations)!=digest(configs):
                    # A later revelation must constrain the existing universe through
                    # the observation, not replace or shrink its initial domain.
                    comparison.update(status='deferred',blockers=['persistent_configuration_universe_replacement_rejected'])
                    configs=None
                if configs is not None:
                    start=perf_counter();update=histories[subject].submit(comparison['observation'],timestamp)
                    solver_seconds+=perf_counter()-start
                    status='duplicate_ignored' if update['status']=='duplicate_ignored' else 'admitted' if update.get('admitted') else 'deferred'
                    comparison.update(status=status,update=update)
        subjects={}
        for iid,mon in latest_observable.get('pokemon',{}).items():
            if mon.get('side')!='opponent':
                continue
            try:
                identity=current_identity(mon)
                alternatives=possible_forms(mon)
                for candidate in alternatives:
                    if candidate not in universe_catalog:
                        universe_catalog[candidate]=universe(candidate,max_configurations=max_configurations)
                        legal=legal_projection(candidate)
                        training_domains[candidate]=dict(configurations=legal['configurations'],provenance=legal['provenance'])
                if identity:
                    key=identity # All item/ability revelations below are displayed,
                    # not silently promoted from recognized candidates to certified eliminations.
                    if key not in universe_catalog:
                        universe_catalog[key]=universe(identity,max_configurations=max_configurations)
                        legal=legal_projection(identity)
                        training_domains[key]=dict(configurations=legal['configurations'],provenance=legal['provenance'])
                    domain=universe_catalog[key]
                    subject=dict(individual=iid,current_form=identity,universe_ref=key,
                        legal_unmodified_speed=domain['legal_unmodified_speed'],status='unresolved',
                        certified_order_feasible=None,configuration_count=domain['configuration_count'],
                        unresolved_reasons=domain['unresolved_reasons']+['no_certified_action_time_configuration_universe'],
                        observed_ability=canonical_fact(mon.get('ability')),observed_item=canonical_fact(mon.get('item')),
                        observed_status=canonical_fact(mon.get('status')),
                        observed_speed_stage=canonical_fact(mon.get('stages',{}).get('speed')),
                        effective_speed_alternatives=None,tie_compatible=None)
                else:
                    subject=dict(individual=iid,current_form=None,status='unresolved',legal_unmodified_speed=None,
                                 certified_order_feasible=None,unresolved_reasons=['current_form_unresolved'])
                    if alternatives:
                        subject.update(possible_forms=alternatives,universe_refs=alternatives,
                            legal_unmodified_speed=speed_summary(v for candidate in alternatives
                                for v in universe_catalog[candidate]['legal_unmodified_speed']['values']),
                            configuration_count=sum(universe_catalog[c]['configuration_count'] for c in alternatives),
                            form_scope='Union of current Champions catalog alternatives; no base/Mega branch selected')
            except (ValueError,KeyError,TypeError,NotImplementedError) as exc:
                subject=dict(individual=iid,current_form=None,status='unresolved',legal_unmodified_speed=None,
                             certified_order_feasible=None,unresolved_reasons=[str(exc)])
            if iid in histories:
                certified=histories[iid].at(timestamp)
                if certified:
                    subject['certified_order_feasible']=certified['certified']
                    subject['last_inference']=certified
            if subject.get('legal_unmodified_speed') is None and iid in last_subjects:
                previous=last_subjects[iid]
                subject['last_known_projection']=dict(form=previous.get('current_form'),
                    legal_unmodified_speed=previous.get('legal_unmodified_speed'),
                    scope='Earlier observed form only; not asserted as current-form Speed')
            subjects[iid]=subject
        # Retain independently identified individuals across switches; never merge
        # same-species source IDs to make later evidence appear continuous.
        last_subjects.update(subjects)
        frame=index.at(timestamp)
        phase=phase_index.at(timestamp)
        snapshots.append(dict(timestamp=timestamp,event_id=event['id'],frame=frame,
            last_observed_phase=None if phase is None else dict(phase=phase['phase'],possible=phase['possible_phases'],
                                                               timestamp=phase['timestamp'],source_id=phase['source_id']),
            state_source_available_at=last_saved_time if last_saved_time>=0 else None,
            observed_action_ids=list(dict.fromkeys(observed_actions)),opponents=deepcopy(last_subjects),
            field={k:deepcopy(latest_observable.get(k)) for k in ['weather','terrain','trick_room','side_conditions']}))
    # Per-action snapshots deliberately exclude posterior/own_stats fields saved by
    # older analyses. Only source-bound observable facts are reused.
    traces=[]
    for group in actions['groups']:
        trace=dict(turn_id=group['turn_id'],local_index=group['local_index'],status=group['membership_status'],
                   pending_coverage='not_certified_by_announcements',actions=[],comparisons=[])
        segment=next(s for s in visual['visual']['segments'] if s['id']==group['turn_id'])
        trace['command_interval']=segment['start'];trace['next_command_interval']=segment['end']
        for aid in group['action_ids']:
            a=actions_by_id[aid];when=available_time(a)
            before=causal_state(saved.get(a['event_id'],{}).get('before',{}),when,event_times)
            after=causal_state(saved.get(a['event_id'],{}).get('after',{}),when,event_times)
            later=[available_time(actions_by_id[x]) for x in group['action_ids'] if available_time(actions_by_id[x])>when]
            upper=min(later) if later else segment['end'][1]
            changes=[dict(event_id=eid,timestamp=event_times[eid],kind=e.get('source_event_type'),text=e.get('text'),
                          sources=e.get('sources',[]),uncertainty=e.get('uncertainty',[]))
                for eid,e in events.items() if event_times[eid] is not None and when<event_times[eid]<upper
                and e.get('source_event_type') in {'status_change','stat_change','weather_change','terrain_change',
                    'side_condition_change','trick_room_change','item_activation','item_change','ability_activation',
                    'transformation','switch_out','send_out','faint'}]
            trace['actions'].append(dict(id=aid,event_id=a['event_id'],timestamp=when,individual=a['instance_id'],
                side=a['side'],move=a['move'],text=a['text'],current_form=current_identity(before.get('pokemon',{}).get(a['instance_id'],{})),
                actor_identity_reliable=a['actor_identity_reliable'],move_identity_reliable=a['move_identity_reliable'],
                priority=a['priority'],before_announcement=before,after_announcement=after,
                following_observed_changes=changes,change_attribution='Chronological following evidence; not automatically caused by this action',
                sources=a['sources'],confidence=a['confidence']))
        trace['comparisons']=[c['id'] for c in comparisons if actions_by_id[c['action_ids'][0]]['turn_id']==group['turn_id']]
        traces.append(trace)
    counts=dict(recognized_actions=len(actions['actions']),local_segments=len(traces),
        confirmed_segments=sum(t['status']=='confirmed' for t in traces),candidate_relations=len(comparisons),
        own_opponent_relations=sum({actions_by_id[c['action_ids'][0]]['side'],actions_by_id[c['action_ids'][1]]['side']}=={'self','opponent'} for c in comparisons),
        admitted=sum(c['status']=='admitted' for c in comparisons),rejected=sum(c['status']=='rejected' for c in comparisons),
        deferred=sum(c['status']=='deferred' for c in comparisons),
        duplicate_observations=sum(c['status']=='duplicate_ignored' for c in comparisons),
        narrowed=sum(c.get('update',{}).get('narrowed',False) for c in comparisons),
        comparable=sum(c.get('observation') is not None for c in comparisons),
        blocker_counts=dict(Counter(b for c in comparisons if c['status']=='deferred' for b in c['blockers'])),
        model_blockers=dict(Counter(b['kind'] for c in comparisons for b in c['model_blockers'])),
        actions_without_local_membership=sum(a['turn_id'] is None for a in actions['actions']))
    return dict(version=VERSION,battle_id=battle_id,stage_a_status='ready_for_stage_b' if counts['admitted'] else 'blocked_no_admitted_constraints',
        profile='showdown-champions-reference-v1',visual_version=visual['schema'],counts=counts,
        timeline=timeline,snapshots=snapshots,turns=traces,comparisons=comparisons,frames=frames,
        universe_catalog=universe_catalog,training_domains=training_domains,
        unassigned_actions=[dict(id=a['id'],timestamp=available_time(a),event_id=a['event_id'],sources=a['sources'],
                                 reason='local_turn_unverified') for a in actions['actions'] if a['turn_id'] is None],
        metrics=dict(solver_seconds=solver_seconds,video_decodes=0,ocr_calls=0,state_engine_replays=0),
        scope='Recognized evidence and legal stat projections are not certified full configuration or Speed-order constraints.')


def markdown(result):
    c=result['counts'];lines=[f"# {result['battle_id']} — M3.2.2 Stage A",'',
        f"Stage A: **{result['stage_a_status']}**. Source profile: frozen visual v2.2; conditional deterministic v2 mechanics.",
        '', 'Recognition, order recovery, comparison admission and actual elimination are separate.', '',
        '| Metric | Count |','| --- | ---: |']
    for key in ['local_segments','confirmed_segments','recognized_actions','actions_without_local_membership',
                'candidate_relations','own_opponent_relations','comparable','admitted','rejected','deferred','narrowed']:
        lines.append(f'| {key} | {c[key]} |')
    lines += ['', 'Known builds: '+result['build_binding']['status']+'. Individual IDs remain separate across unresolved reentries.',
        '', 'Speed/order-equivalent items share a branch with concrete hypotheses retained; unknown relevant modifiers are not assumed neutral.', '',
        '## Deferred evidence blockers','', '| Reason | Comparisons |','| --- | ---: |']
    for key,count in sorted(c['blocker_counts'].items()):
        lines.append(f'| `{key}` | {count} |')
    lines += ['', '## Legal projection / full-configuration boundary','',
        '| Catalog form (observed or retained alternative) | Speed projection | Values | Speed/order configuration classes | Unresolved causes |',
        '| --- | --- | ---: | ---: | --- |']
    for key,domain in sorted(result['universe_catalog'].items()):
        s=domain['legal_unmodified_speed']
        label=__import__('speed_order.core',fromlist=['knowledge']).knowledge().entities[key].names.get('zh-hans',key)
        lines.append(f"| {label} (`{key}`) | {s['intervals']} | {s['count']} | {domain['configuration_count']} | {', '.join(domain['unresolved_reasons'])} |")
    lines += ['', 'These are complete stat projections within the pinned form/native catalog, not exhaustive certified battle configurations.',
              'Neutral items share one conditional Speed/order class while concrete item hypotheses remain in JSON. Compatible Mega stones stay separate. Class counts do not multiply every neutral held item.',
              'Observed item/ability banners retain recognition confidence and source IDs; they are not silently applied as reviewed eliminations.',
              '', '## Actual chronological turn/action traces','']
    by_comparison={c['id']:c for c in result['comparisons']}
    for turn in result['turns']:
        lines += [f"### Local segment {turn['local_index']} — {turn['status']}", '',
            f"Normal-command entry interval: {turn['command_interval']}; next entry: {turn['next_command_interval']}. "
            'These are retrospective frozen boundary labels, not independently reviewed complete resolution windows.', '',
            '| Time (s) | Actor / stable instance | Move / catalog priority alternatives | Source frame |',
            '| ---: | --- | --- | --- |']
        for a in turn['actions']:
            image=next((s.get('image') for s in a['sources'] if s.get('image')),None)
            link=f'[frame](../../../{image})' if image else 'missing'
            label=(a['text'] or '').replace('\n',' ').replace('|',' ')
            lines.append(f"| {a['timestamp']:.3f} | {a['side']} `{a['individual']}` / `{a['current_form']}` | {label}; {a['priority']['effective_priorities']} | {link} |")
        for cid in turn['comparisons']:
            comparison=by_comparison[cid]
            lines.append(f"\n- `{cid}`: **{comparison['status']}**; "+', '.join(comparison['blockers'])+'.')
        lines += ['', 'The JSON retains source confidence, every action-time before/after observable state, '
                  'intervening event IDs and model-specific handler diagnostics. Missing announcements are not cancellations.', '']
    lines += ['## Limitations and resume','',
        'No certified comparison was narrowed unless explicitly counted above. The native ability and Speed/order-equivalence '
        'universe remains unresolved when relevant handlers, evidence or bounds prevent complete evaluation. '
        'HP (except applicable Gale Wings), damage stats and absolute turn numbers are not admission requirements.', '',
        f"Preprocessing: {result['metrics'].get('preprocessing_seconds',0):.4f}s; solver: {result['metrics']['solver_seconds']:.4f}s. "
        'Zero video decodes/OCR/StateEngine replays. Browser performance is not measured because Stage B is gated.', '',
        'Manifest and replay JSON: `'+result['artifact_directory']+'`.', '',
        f"Resume: `.venv/bin/python scripts/report_speed_replay.py --battle {result['battle_id'].rsplit('_',1)[1]} --visual-version v2.2`.",
        '', 'If admission is zero, stop before UI construction as requested. A future source-backed review attachment '
        'must certify a complete pending set and action-time modifiers; known contradictions must not be reset.', '']
    return '\n'.join(lines)


def run(number, *, root=ROOT, reviews=None, max_configurations=100000, max_evaluations=100000):
    battle=BattleArtifacts(f'sample_battle_{number}',root).prepare();started=perf_counter()
    print(battle.battle_id,'validating frozen inputs and compatible action cache',flush=True)
    visual,states,raw,paths=inputs_for(battle)
    actions,action_manifest,selection=select_actions(battle)
    paths += [action_manifest,action_manifest.parent/'actions.json']
    team,builds,binding,team_paths,roster=load_team(battle,actions,root=root);paths+=team_paths
    source=next(p for p in paths if str(p).endswith(('/video-only.json','/events.json')))
    observation_path=source.with_name('observations.json');recognition_manifest=source.with_name('manifest.json')
    paths += [observation_path,recognition_manifest]
    observations=json.loads(observation_path.read_text());battle.check_identity(observations['battle_id'])
    frames=frame_rows(observations['observations']);frame_index=TimeIndex(frames)
    roster_frames=[f for f in frames if Path(f['image']).resolve()==(Path(root)/roster['image']).resolve()]
    if len(roster_frames)!=1:
        raise ValueError('Roster build binding source has no unique actual frame timestamp')
    binding['available_at']=roster_frames[0]['timestamp']
    for build in builds.values():
        build['available_at']=binding['available_at']
    # Build binding must be available by the observed action, never inferred from
    # a complete roster that is only visible later in this recording.
    builds={iid:b for iid,b in builds.items() if any(a['instance_id']==iid and
            available_time(a)>=binding['available_at'] for a in actions['actions'])}
    inputs={str(p):file_hash(p) for p in dict.fromkeys(paths)}
    # Validate exactly the source frame files cited by action evidence. Display
    # frame metadata otherwise retains the saved file hashes without decoding.
    frame_lookup={r['image']:r for r in frames};verified_frames=[]
    for a in actions['actions']:
        for s in a['sources']:
            image=s.get('image')
            if not image or image in verified_frames:
                continue
            row=frame_lookup.get(image)
            if row is None or row['timestamp']>available_time(a) or file_hash(Path(root)/image)!=row['sha256']:
                raise ValueError('Action source frame missing, altered, or later than announcement')
            inputs[image]=row['sha256'];verified_frames.append(image)
    dependencies=[Path(__file__),Path(__file__).with_name('speed_adapter.py'),Path(__file__).with_name('speed_replay.py'),
        Path(__file__).with_name('speed_items.py'),Path(__file__).with_name('speed-item-projection-v1.json'),
        ROOT/'scripts/report_speed_replay.py',ROOT/'team_configuration/__init__.py',ROOT/'battle_artifacts.py',
        ROOT/'battle_evidence/builds.py',ROOT/'battle_evidence/action_offline.py',ROOT/'battle_evidence/actions.py',
        ROOT/'knowledge/__init__.py',ROOT/'knowledge/identity.py',ROOT/'knowledge/champions_stats.py',
        ROOT/'knowledge/stat_feasibility.py',ROOT/'knowledge/data/champions_facts.json',ROOT/'knowledge/data/manifest.json',
        ROOT/'knowledge/data/champions_stat_rules.json',ROOT/'damage/core.py']
    dependencies += sorted((ROOT/'speed_order').glob('*.py'))+sorted((ROOT/'speed_order/data').glob('*.json'))
    dependencies += sorted((ROOT/'speed_order/schemas').glob('*.json'))
    video_manifest=json.loads(recognition_manifest.read_text())
    video=Path(video_manifest['identity']['video_path']);stat=video.stat()
    identity=dict(version=VERSION,battle_id=battle.battle_id,inputs=inputs,
        dependencies={str(p):file_hash(p) for p in dependencies},
        video=dict(path=str(video),sha256=video_manifest['identity']['video_sha256'],size=stat.st_size,mtime_ns=stat.st_mtime_ns),
        reviews=reviews,visual_version='v2.2',mechanics_profile='showdown-champions-reference-v1',
        solver_configuration=dict(max_configurations=max_configurations,max_evaluations=max_evaluations))
    fingerprint=digest(identity);dest=battle.cache('m322-speed-replay/'+fingerprint[:16]);dest.mkdir(parents=True,exist_ok=True)
    manifest=dest/'manifest.json';output=dest/'replay.json';summary=dest/'summary.md'
    if manifest.exists():
        saved_manifest=json.loads(manifest.read_text())
        if saved_manifest.get('status')=='complete' and all((dest/name).is_file() and file_hash(dest/name)==sha for name,sha in saved_manifest['outputs'].items()):
            print(battle.battle_id,'reused completed Stage A',fingerprint[:16],flush=True)
            return dict(battle_id=battle.battle_id,reused=True,result=str(output),counts=saved_manifest['counts'])
    m=json.loads(manifest.read_text()) if manifest.exists() else dict(identity=identity,completed={})
    m.update(status='running',stage='source_identity');m.pop('error',None);atomic(manifest,m)
    try:
        print(battle.battle_id,'checking source video hash (no decoding)',flush=True)
        video_receipt=verify_video(battle,video_manifest)
        m['completed']['sources']=dict(video=video_receipt,verified_action_frames=len(verified_frames),action_cache=selection)
        m['stage']='chronological_evidence_and_inference';atomic(manifest,m)
        print(battle.battle_id,'building causal evidence audit; original caches preserved',flush=True)
        result=chronological_audit(battle.battle_id,visual,states,raw,actions,builds,frames,reviews=reviews,
                                  max_configurations=max_configurations,max_evaluations=max_evaluations)
        result.update(input_identity=identity,build_binding=binding,team_profile=dict(path=str(team_paths[0]),
            sha256=inputs[str(team_paths[0])],team_id=team.data['team_id'],video_sha256=team.data['video_sha256'],sources=team.data['sources']),
            action_cache_selection=selection,artifact_directory=str(dest.relative_to(Path(root))),
            duration_coverage=dict(last_cached_frame=frames[-1]['timestamp'],source_video=str(video),
                container_duration_seconds=video_manifest.get('decoder',{}).get('container_duration_seconds'),
                note='Duration reused from sealed decoder metadata; frame navigation uses actual cached timestamps'))
        timing=perf_counter();snapshot_index=TimeIndex(result['snapshots'])
        for j in range(2000):
            t=frames[-1]['timestamp']*j/1999;frame_index.at(t);snapshot_index.at(t)
        selector_seconds=perf_counter()-timing
        result['metrics'].update(preprocessing_seconds=perf_counter()-started,
            selection_benchmark=dict(queries=2000,seconds=selector_seconds,seconds_per_query=selector_seconds/2000,
                                     scope='Python frame/snapshot lookup only; not browser responsiveness'),
            cached_frames=len(frames),verified_action_frame_files=len(verified_frames),video_hash_reused=video_receipt['hash_reused'])
        atomic(output,result);summary.write_text(markdown(result))
        m['completed']['audit']=dict(status=result['stage_a_status'],counts=result['counts'])
        m.update(status='complete',stage='complete',counts=result['counts'],metrics=result['metrics'],
                 outputs={'replay.json':file_hash(output),'summary.md':file_hash(summary)},
                 storage_bytes=sum(p.stat().st_size for p in [output,summary]))
        atomic(manifest,m)
        battle.guard_output(battle.report('M3.2.2-speed-inference-validation.md')).write_text(markdown(result))
        atomic(battle.cache('m322-speed-replay/latest.json'),dict(path=str(manifest),fingerprint=fingerprint,status='complete'))
        print(battle.battle_id,result['stage_a_status'],result['counts'],flush=True)
        return dict(battle_id=battle.battle_id,reused=False,result=str(output),counts=result['counts'])
    except Exception as exc:
        m.update(status='failed',error=repr(exc),resume=f'Repeat --battle {number} --visual-version v2.2; sealed inputs and completed stages retained.')
        atomic(manifest,m);raise
