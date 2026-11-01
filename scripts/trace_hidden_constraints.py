"""Cache-first B20-B23 inference experiment; no decoding, OCR or priors."""
import argparse
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
RUNNER_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json
from battle_evidence.constraint_trace import ChronologicalTrace,event_time,resolved_event,VERSION,digest,public_candidate_comparison
RUNS={20:'fresh-b20-postfix-v1',21:'fresh-b21-context-v1',22:'fresh-b22-ditto-20261030-v1',23:'mega-b23-20261030-v1'}
EXPERIMENT='hidden-constraints-20261031-v1'
INTEGRATE=False
FOCUSED=False
REVIEW=ROOT/'docs/hidden-constraints-b20-b23/integration-review-20261101.json'
def read(path):return json.loads(path.read_text())
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()
def setup(number):
    owner=BattleArtifacts(f'sample_battle_{number}',ROOT)
    source=owner.cache('event-driven/'+RUNS[number]);replay=source/'replay.json'
    projection=owner.cache('fresh-benchmark/'+RUNS[number]+'/hp-resolutions.json');companions=[]
    if number==22:
        replay=ROOT/'.cache/mega-stats-validation/mega-team7-b22-v1/replay.json'
        projection=owner.cache('diagnosis/b22-followup-validation-v4/projection-with-hits.json')
        companions=[replay.parent/'manifest.json',owner.cache('diagnosis/b22-followup-validation-v4/manifest.json')]
    if number==21:
        companions=[owner.cache('diagnosis/double-faint-hud-20261029-v2/replay.json'),
            owner.cache('diagnosis/double-faint-hud-20261029-v2/manifest.json')]
    out=owner.cache('diagnosis/'+EXPERIMENT);out.mkdir(parents=True,exist_ok=True)
    paths=[source/n for n in ('video-only-seal.json','manifest.json','replay.json','video-only.json','observations.json')]
    paths += [replay,projection,*companions]
    if INTEGRATE:paths += [REVIEW,ROOT/'tests/fixtures/battle_evidence/sample-team7-reviewed.json']
    if FOCUSED:paths += [ROOT/'docs/focused-repair-20261101/scope.json']
    identity=dict(version=VERSION,battle_id=owner.battle_id,inputs={str(p.relative_to(ROOT)):sha(p) for p in set(paths)},
        rules={'item_clause':'user confirms ranked doubles across all six members','life_orb':'user-reviewed no-display counterfactual with Magic Guard and Sheer Force exceptions'},no_statistical_priors=True)
    manifest=out/'manifest.json'
    if manifest.exists():
        m=read(manifest)
        if m['identity']!=identity:raise ValueError('Input identity changed; preserve outputs and use another namespace')
    else:
        m=dict(identity=identity,status='inspected',stages={},errors=[],resume_command=f'.venv/bin/python scripts/trace_hidden_constraints.py --battle {number} --resume')
        atomic_json(manifest,m)
    if INTEGRATE:
        flag='--focused-repair' if FOCUSED else '--integration-audit'
        m['resume_command']=f'.venv/bin/python scripts/trace_hidden_constraints.py --battle {number} {flag} --stage trace --resume'
        m['invalidation_policy']='Prior context fingerprints retained. Screen activation and quantified stage repairs invalidate earlier diagnostic contexts; compatible completed contexts are reused for inference-only changes.'
        atomic_json(manifest,m)
    return owner,source,replay,projection,out,m

def source_payload(number,replay,owner):
    payload=read(replay)
    if number==21:
        corrected=read(owner.cache('diagnosis/double-faint-hud-20261029-v2/replay.json'))
        overlay={r['event']['event_id']:r for r in corrected['history']}
        for r in payload['history']:
            replacement=overlay.get(r['event']['event_id'])
            if replacement:
                # Preserve original full-stream delivery/order IDs. Adopt only
                # the existing saved correction, never a new guessed identity.
                for field in ('event','application_status','reason','bindings','state_hash'):
                    r[field]=deepcopy(replacement[field])
        payload['state']=corrected['state'];payload['state_hash']=corrected['state_hash']
    if INTEGRATE:
        from tracking.battle_state import from_dict
        from tracking.knowledge_grounding import attach_verified_profile
        review=read(REVIEW)['battles'][str(number)]
        initial=attach_verified_profile(from_dict(payload['initial_state']),
            read(ROOT/'tests/fixtures/battle_evidence/sample-team7-reviewed.json'),review['roster'],root=ROOT)
        initial.knowledge['battle_start_review']=review['opening']
        if FOCUSED:
            initial.knowledge['initial_full_hp_rule']=dict(verified=True,confirmed_by='user 2026-11-01 focused repair',species_ids=[1018],maximum=194,
                scope='verified Team7 first entry only; preserve HP on all reentries')
        payload['initial_state']=initial.to_dict()
    return payload
def context_fingerprint(payload):
    tree=ast.parse(Path(__file__).read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='create_contexts')
    ps=[ROOT/'tracking'/n for n in ('state_engine.py','battle_state.py','decision_state.py','identity_ledger.py','active_continuity.py','evidence_fusion.py','transformation.py','form_stats.py','hp_causes.py','resolution_context.py','initial_conditions.py','knowledge_grounding.py')]
    return digest(dict(function=ast.dump(fn,include_attributes=False),inputs=digest(payload),dependencies={str(p.relative_to(ROOT)):sha(p) for p in ps}))[:16]

def freeze_promoted_inputs(payload,manifest):
    """A repaired identity must not promote source-deferred evidence.

    A completed diagnostic receipt audit identifies the exact newly admissible
    rows. Only that invalid stage repeats. Full source receipts stay in trace().
    """
    if not FOCUSED:return payload
    stage=manifest['stages'].get('contexts:'+context_fingerprint(payload),{})
    accepted={'applied_candidate','applied_confirmed','applied_partial','recorded_observation'}
    excluded=[r for r in stage.get('receipt_status_mismatches',[]) if r['source_status'] not in accepted and r['replay_status'] in accepted]
    if not excluded:return payload
    payload=deepcopy(payload);ids={r['event_id'] for r in excluded}
    payload['history']=[r for r in payload['history'] if r['event']['event_id'] not in ids]
    payload['diagnostic_source_admission_guard']=dict(version='retain-frozen-admission-v1',excluded=excluded,
        reason='Identity repair cannot promote source-unaccepted receipts into numerical inputs')
    return payload
def create_contexts(payload,out,m):
    """One existing-engine replay, not quadratic per-event apply or recognition."""
    from tracking.battle_state import from_dict
    from tracking.state_engine import StateEngine,EventRecord,ApplicationPolicy
    from tracking.mechanic_rules import MechanicRules
    fingerprint=context_fingerprint(payload);key='contexts:'+fingerprint;old=m['stages'].get(key)
    if old and old['status']=='complete':
        p=out/old['output']
        if sha(p)!=old['sha256']:raise ValueError('Completed context checksum mismatch')
        print('Reused context stage',p,flush=True);return p
    if old and old.get('pid'):
        try:os.kill(old['pid'],0)
        except ProcessLookupError:pass
        else:
            if old['pid']!=os.getpid():raise ValueError('Context replay process remains active')
    attempt=(old or {}).get('attempt',0)+1;p=out/f'contexts-{fingerprint}-attempt-{attempt}.jsonl'
    assert not p.exists()
    policy=deepcopy(payload['policy'])
    if 'allowed_uncertainties' in policy:policy['allowed_uncertainties']=tuple(policy['allowed_uncertainties'])
    engine=StateEngine(from_dict(payload['initial_state']),ApplicationPolicy(**policy),mechanic_rules=MechanicRules(**payload.get('mechanic_rules',{})))
    engine.history=[EventRecord(**deepcopy(r)) for r in payload['history']]
    originals={r['event']['event_id']:r for r in payload['history']}
    stage=dict(status='running',pid=os.getpid(),attempt=attempt,output=p.name,started=time.time(),
        completed_receipts=0,source_receipts=len(engine.history),
        checkpoint_policy='Partial JSONL retained. No safe engine suffix-resume API: only an incomplete replay stage may repeat; completed battles/stages never repeat.')
    m['stages'][key]=stage;m['status']='context_replay';atomic_json(out/'manifest.json',m)
    mismatches=[];count=0
    relevant={'move_execution','item_activation','ability_activation','transformation','stat_change','status_change',
        'volatile_change','move_effect','switch_out','send_out','faint','side_condition_change','weather_change','terrain_change'}
    with p.open('x') as stream:
        def callback(record,state):
            nonlocal count
            count+=1;original=originals[record.event['event_id']]
            if original['application_status']!=record.application_status:
                mismatches.append(dict(event_id=record.event['event_id'],source_status=original['application_status'],replay_status=record.application_status,reason=record.reason))
            if record.event['event_type'] in relevant:
                view=engine.decision_state()
                if FOCUSED:
                    aliases=deepcopy(state.knowledge.get('instance_aliases',{}))
                    for alias,pid in aliases.items():
                        if pid in view['pokemon']:view['pokemon'][alias]=deepcopy(view['pokemon'][pid])
                    active_sources={ep['instance_id']:ep.get('encounter_id',ep['instance_id']) for ep in state.knowledge.get('active_entry_episodes',[]) if ep.get('departure') is None}
                    for side in view['sides'].values():side['active_slots']={slot:active_sources.get(pid,pid) for slot,pid in side['active_slots'].items()}
                    view['source_instance_aliases']=aliases
                stream.write(json.dumps(dict(event_id=record.event['event_id'],record=original,replay_application_status=record.application_status,
                    context=dict(pokemon=view['pokemon'],sides=view['sides'],field=view['field'],global_effects=view['global_effects'],source_instance_aliases=view.get('source_instance_aliases',{}))),ensure_ascii=False,separators=(',',':'))+'\n')
            if count%50==0:
                stream.flush();os.fsync(stream.fileno());stage['completed_receipts']=count
                stage['elapsed_seconds']=time.time()-stage['started'];atomic_json(out/'manifest.json',m)
                print('saved context progress',count,'/',len(engine.history),flush=True)
        engine.replay(snapshot_callback=callback);stream.flush();os.fsync(stream.fileno())
    stage.update(status='complete',completed_receipts=count,sha256=sha(p),wall_seconds=time.time()-stage['started'],
        receipt_status_mismatches=mismatches,source_final_state_hash=payload.get('state_hash'),replayed_final_state_hash=engine.to_dict()['state_hash'])
    if FOCUSED:
        stage['instance_aliases']=deepcopy(engine.state.knowledge.get('instance_aliases',{}))
        stage['persistent_histories']={pid:dict(hp_observation_event_ids=[o.get('evidence',{}).get('event_id') for o in mon.hp.observations],
            revealed_move_event_ids=[o['event_id'] for o in mon.moves.executed],current_hp=mon.hp.current.value,
            unit=mon.hp.unit.value,original_identity=mon.original_identity.value)
            for pid,mon in engine.state.pokemon.items() if pid in stage['instance_aliases'].values()}
    if payload.get('diagnostic_save_replay'):
        final=out/f'context-replay-{fingerprint}-attempt-{attempt}.json'
        atomic_json(final,engine.to_dict())
        stage['diagnostic_replay']=dict(path=final.name,sha256=sha(final))
    atomic_json(out/'manifest.json',m);return p
def readable_update(u):
    obs=u['observation'];constraint=u['new_constraint'];kind=u['kind']
    description=obs.get('text') if isinstance(obs,dict) else None
    if kind in {'damage_joint_constraint','damage_unusable'}:
        description=f"{obs.get('move_name') or obs.get('move')}: {obs.get('before')} → {obs.get('after')} {obs.get('unit')}; target {obs.get('target')}; per-hit amounts {obs.get('per_hit_damage')}."
        selector=constraint.get('selector') or {}
        constraint=f"Joint damage relation using {selector.get('offensive_owner','unknown')}.{selector.get('offensive_stat','unknown')}, damage {constraint.get('damage')} {constraint.get('damage_unit')}. Unresolved: "+'; '.join(constraint.get('unresolved',[]))
    elif kind=='speed_order_candidate':
        description=f"Observed announcements: {obs['first_event_id']} before {obs['second_event_id']} in a saved provisional command cycle."
        constraint=f"{constraint['first']} before {constraint['second']}; base priorities {constraint['base_priorities']}. "+constraint['inequality']+". Conditions: "+'; '.join(constraint['conditions'])+". Admission limits: "+'; '.join(constraint['admissibility_reasons'])
    elif kind=='life_orb_counterfactual':
        window=obs['message_window'];conditions=obs['conditions']
        description=f"Post-action display check: {window.get('selected_frames')} saved frames; {window.get('unread_frames')} raw OCR-unread frames; visual review {window.get('reviewed_saved_frames',0)} frames. Effective ability {conditions.get('ability')}."
        constraint=f"{constraint['status']}: {constraint.get('constraint') or 'no current Life Orb exclusion'}. Reasons: "+', '.join(constraint.get('reasons',[]))
    elif kind=='copied_current_stats':
        description='Copied current stats: '+', '.join(f"{s}={v.get('value')}" for s,v in u['after'].items())+'.'
    elif kind=='battle_context':
        description=(obs.get('text') or obs.get('kind',''))+'; explicit side '+str(obs.get('side'))+'.'
    if not description:description=json.dumps(obs,ensure_ascii=False,separators=(',',':'))
    if not isinstance(constraint,str):constraint=json.dumps(constraint,ensure_ascii=False,separators=(',',':'))
    def short(x):
        if x is None:return 'unknown / not projected'
        if isinstance(x,dict) and 'values' in x:return f"{x.get('minimum')}–{x.get('maximum')}; {x.get('count')} values (marginal outer bound)"
        if isinstance(x,dict) and all(isinstance(v,dict) and 'value' in v for v in x.values()):
            return ', '.join(f"{s}={v['value']}" for s,v in x.items())
        return json.dumps(x,ensure_ascii=False,separators=(',',':'))
    provenance=u['provenance'];rule=provenance.get('rule',{})
    proof=rule.get('id') or rule.get('source') or rule.get('profile') or 'saved accepted evidence'
    refs=[s.get('source_id') for s in provenance.get('sources',[]) if s.get('source_id')]
    return description,constraint,short(u['before'])+' → '+short(u['after']),str(proof)+'; source IDs: '+', '.join(refs)

def render(result):
    def bounds(v):return '?' if not v else f"{v['minimum']}–{v['maximum']} ({v['count']} values)"
    lines=[f"# {result['battle_id']}: chronological hidden constraints","",
        "Saved evidence only. No usage priors, frequency weights, rankings or posterior probabilities.",
        "Initial sets are native-form projections. Final retained marginals are conservative outer bounds, not solved projections of every joint constraint.",
        "Conditional relations and current/copied-form epochs are separate. Current-item exclusions are action-/lineage-scoped; they are not original-loadout exclusions.","",
        "## Six-member summary","",
        "| Pokémon / preview | Revealed lineages | Initial → final Speed | Initial Atk / SpA | Final Atk / SpA | Confirmed items at observation | Excluded current / original | Updates |",
        "|---|---:|---|---|---|---|---|---:|"]
    for mon in result['roster']:
        s=mon['initial'];f=mon['final_stats'];items=', '.join(sorted({x['name'] or x['id'] for x in mon['confirmed_items']})) or 'unknown'
        excluded=sorted({x for lineage in mon['lineages'] for x in lineage['excluded_current_items']})
        lines.append(f"| {mon['name']} / {mon['preview_row']} | {len(mon['lineage_ids'])} | {bounds(s['speed'])} → {bounds(f['speed'])} | {bounds(s['attack'])} / {bounds(s['special_attack'])} | {bounds(f['attack'])} / {bounds(f['special_attack'])} | {items} | {', '.join(excluded) or 'none'} / {', '.join(mon['original_item_exclusions']) or 'none established'} | {len(mon['events'])} |")
    lines+=["","## Counts and limits","","```json",json.dumps(result['counts'],ensure_ascii=False,indent=2),"```","",
        "Numerical refinements count valid unconditional native-stat set reductions. Provisional command cycles do not certify single action-order decisions.",
        "No unknown stage, status, item, ability or defender stat is silently set to neutral/zero.",""]
    validation=result['context_validation']
    lines += [f"Diagnostic context final hash matches source: {validation['final_hash_matches']}; receipt-status mismatches: {len(validation['receipt_status_mismatches'])}.",
        validation['authority'],"Original source conflicts and unaccepted receipts are retained in trace.json; this experiment does not resolve them by replay success.",""]
    byid={u['update_id']:u for u in result['updates']}
    lines+=["## Separate public-candidate compatibility","",
        "Unweighted library occurrence counts, not probabilities. Missing library configurations remain legally possible.","",
        "| Preview | Source lineage | Initial pool | First half compatible/unresolved | Final compatible/unresolved | Library reduction |",
        "|---|---|---:|---:|---:|---:|"]
    for row in result.get('candidate_compatibility',{}).get('records',[]):
        lines.append(f"| {row['roster_id']} | {row['instance_id'] or 'unrevealed'} | {row['initial_pool_occurrences']} | {row['stages']['first_half']['compatible_or_unresolved']} | {row['stages']['final']['compatible_or_unresolved']} | {row['reduction']} |")
    lines+=[""]
    for mon in result['roster']:
        lines += [f"## Preview {mon['preview_row']}: {mon['name']}","",f"Roster ID: {mon['roster_id']}; preview available at {mon['initial_available_at']}.",
            f"Initial: Speed {bounds(mon['initial']['speed'])}; Attack {bounds(mon['initial']['attack'])}; SpA {bounds(mon['initial']['special_attack'])}.",
            "Original/current item, exact equipped move slots and SP allocation begin unknown.",""]
        if not mon['lineage_ids']:lines+=["Not revealed in the retained accepted stream. Unseen is not proof of unselected.",""]
        if len(mon['lineage_ids'])>1:lines+=["**Multiple source instance IDs remain unresolved continuity hypotheses. Do not intersect them or count them as independent builds.**",""]
        for line in mon['lineages']:
            lines += [f"### Source lineage {line['instance_id']}","",
                f"Entry episodes: {len(line['episodes'])}; original item: {line['original_item'] or 'unknown'}; last observed current item: {line['current_item'] or 'unknown'}.",""]
            for ep in line['episodes']:lines.append(f"- Entry {ep['start']}: {ep['episode_id']}; continuity {ep.get('persistent_identity_status')}; possible previous IDs: {ep.get('possible_prior_instance_ids') or []}.")
            lines+=[""]
        for uid in mon['events']:
            u=byid[uid]
            description,constraint,transition,provenance=readable_update(u)
            lines += [f"### t={u['timestamp']:.3f}s — {u['kind']} [{u['classification']}]","",
                f"Source event: {u['source_event_id']}; receipt: {u['source_receipt_id']}; instance: {u['pokemon_instance_id'] or 'cross-team preview member'}.",
                description,"","**Constraint:** "+constraint,"",
                "**Before / after:** "+transition,"",
                "Excluded: "+json.dumps(u['excluded'],ensure_ascii=False)+"; other affected: "+json.dumps(u['other_affected_roster_ids'],ensure_ascii=False)+".",
                "Provenance: "+provenance+". Full context, hashes, confidence and alternatives are preserved in trace.json.",""]
        lines += ["Final: "+mon['final_stats_note'],mon['no_numeric_refinement_reason'],""]
    return '\n'.join(lines)+'\n'
def trace(number,owner,source,replay,projection,out,m,context_path):
    payload=source_payload(number,replay,owner);original=read(source/'replay.json')
    roster=[r for r in original['state']['knowledge']['identity_ledger']['roster'] if r.get('side')=='opponent']
    records=payload['history'];rmap={r['event']['event_id']:r for r in records};contexts={}
    for line in context_path.open():
        row=json.loads(line);contexts[row['event_id']]=row['context']
    hp=read(projection);observations=read(source/'observations.json')['observations']
    persistent_aliases={alias:pid for c in contexts.values() for alias,pid in c.get('source_instance_aliases',{}).items()} if FOCUSED else {}
    if FOCUSED:
        from tracking.resolution_endpoints import repair_saved_endpoints
        hp,hp_repairs=repair_saved_endpoints(hp,records,contexts,persistent_aliases)
    reviews={};review_hashes={}
    review_paths=list(out.glob('manual-*/review.json'))
    if INTEGRATE:review_paths+=list(owner.cache('diagnosis/hidden-constraints-20261031-v1').glob('manual-*/review.json'))
    for p in review_paths:
        review=read(p)
        if not review.get('reviewer'):raise ValueError('Named visual review required')
        for frame in review['frames']:
            if sha(ROOT/frame['image'])!=frame['sha256']:raise ValueError('Reviewed source frame changed')
        if sha(ROOT/review['projection'])!=review['projection_sha256']:raise ValueError('Reviewed projection changed')
        reviews[review['action_id']]=review;review_hashes[str(p.relative_to(ROOT))]=sha(p)
    database_root=ROOT/'.cache/metagame/published-teams'
    database_hash=sha(database_root/'teams.sqlite3')
    dependencies=[ROOT/'battle_evidence'/n for n in ('constraint_trace.py','inference_integration.py','team_items.py','life_orb.py','data/hidden-constraints-rules-v1.json')]
    if FOCUSED:dependencies += [ROOT/'tracking/resolution_endpoints.py']
    dependencies += [p for directory in ('damage','speed_order','knowledge') for p in (ROOT/directory).rglob('*.py')]
    fp=digest(dict(inputs=m['identity'],candidate_database_sha256=database_hash,visual_reviews=review_hashes,
        context=sha(context_path),dependencies={str(p.relative_to(ROOT)):sha(p) for p in dependencies},runner=RUNNER_SHA))[:16]
    previous=m['stages'].get('trace:'+fp)
    if previous and previous['status']=='complete':
        if all(sha(out/p)==checksum for p,checksum in previous['outputs'].items()) and sha(ROOT/previous['report'])==previous['report_sha256']:
            summary=read(out/'traces'/fp/'summary.json');atomic_json(out/'latest.json',summary)
            print(json.dumps(dict(reused=True,**summary),ensure_ascii=False),flush=True);return
        raise ValueError('Completed trace output changed; preserve evidence and inspect before regeneration')
    if INTEGRATE:
        if previous and previous.get('pid') and previous.get('status')=='running':
            try:os.kill(previous['pid'],0)
            except ProcessLookupError:pass
            else:
                if previous['pid']!=os.getpid():raise ValueError('An inference trace process remains active')
        dest=out/'traces'/fp;dest.mkdir(parents=True,exist_ok=True)
        m['stages']['trace:'+fp]=dict(status='running',pid=os.getpid(),started=time.time(),completed_damage_episodes=0,
            checkpoint_policy='Prefix constraints retained atomically; a failed inference-only pass restarts cheaply from compatible completed state contexts.')
        m['status']='inference';atomic_json(out/'manifest.json',m)
        print('Inference stage',fp,'using saved contexts',flush=True)
    adapter=ChronologicalTrace(owner.battle_id,roster,records,payload['state'],
        integrate=INTEGRATE,
        persistent_aliases=persistent_aliases,
        hp_action_ids={ep['source_event_id'] for ep in hp.get('episodes',[]) if
            (ep.get('actor_instance_id') or '').startswith(owner.battle_id+':opponent:') and (ep.get('cause') or {}).get('kind')=='move'})
    schedule=[(event_time(resolved_event(r)),0,i,r) for i,r in enumerate(records) if r['event']['event_type']!='hud_observation']
    for i,ep in enumerate(hp.get('episodes',[])):
        end=(ep.get('resolution_end') or {}).get('time')
        if end is None:end=max((x.get('time',0) for x in (ep.get('endpoints') or {}).values() if isinstance(x,dict)),default=0)
        end=max(end or 0,event_time(rmap.get(ep.get('source_event_id'),{}).get('event',{})))
        schedule.append((end,1,i,ep))
    cycles=read(source/'video-only.json').get('command_cycles',[])
    if INTEGRATE:
        for i,cycle in enumerate(cycles):
            end=cycles[i+1]['start'] if i+1<len(cycles) else float('inf')
            schedule.append((end,2,i,dict(cycle,end=end)))
    for when,kind,idx,entry in sorted(schedule,key=lambda row:row[:3]):
        if kind==0:adapter.process_event(entry,contexts.get(entry['event']['event_id'],{}))
        elif kind==1:
            start=len(adapter.updates);adapter.damage(entry,rmap,contexts,observations,reviewed_absence=reviews)
            for u in adapter.updates[start:]:u['action_timestamp']=u['timestamp'];u['timestamp']=when
            if INTEGRATE:
                atomic_json(dest/'partial.json',dict(fingerprint=fp,through_time=when,updates=adapter.updates,
                    lineages=adapter.lineages,counts=dict(adapter.counter),status='partial_inference_not_final'))
                m['stages']['trace:'+fp]['completed_damage_episodes']+=1
                atomic_json(out/'manifest.json',m)
                print('Saved damage inference',entry['episode_id'],adapter.counter.get('numeric_refinement',0),'reductions',flush=True)
        else:adapter.speed_pairs(records,contexts,[entry])
    if not INTEGRATE:adapter.speed_pairs(records,contexts,cycles)
    result=adapter.result();result['updates'].sort(key=lambda u:(u['timestamp'],u['update_id']))
    if FOCUSED:
        result['focused_repair']=dict(version='persistent-identity-damage-endpoints-v1',aliases=persistent_aliases,hp_repairs=hp_repairs,
            rule='user-confirmed unique species identity across regional/gender forms and unique original held items; distinct encounter episodes retained')
    if INTEGRATE:
        result['integration_profile']='b20-b23-saved-state-integration-v1'
        result['team7_integration']=dict(review=read(REVIEW)['battles'][str(number)],
            diagnostic_attachment='verified_team_profile applied through existing exact-six/profile binder',
            attached_self_instances=sorted({pid for c in contexts.values() for pid,p in c.get('pokemon',{}).items()
                if p.get('side')=='self' and p.get('known_configuration',{}).get('team_id')=='sample_team_team7_20261021'}),
            sealed_source_metadata_preserved=True,source_linkage_is_separate_from_diagnostic_attachment=True)
    order={u['update_id']:i for i,u in enumerate(result['updates'])}
    for mon in result['roster']:mon['events'].sort(key=lambda uid:order[uid])
    result['sources']=dict(original_run=RUNS[number],replay=str(replay.relative_to(ROOT)),hp_projection=str(projection.relative_to(ROOT)),
        context_output=context_path.name,original_records=len(original['history']),used_records=len(records),
        limits='B22 uses a separately saved corrected/team-linked replay and supplemented hit projection. B21 overlays the saved double-faint correction onto original full-stream IDs/orders. Original files remain unchanged. Other local diagnoses are not silently pooled.')
    context_stage=next(s for s in m['stages'].values() if s.get('output')==context_path.name)
    result['context_validation']={k:context_stage[k] for k in ('receipt_status_mismatches','source_final_state_hash','replayed_final_state_hash','wall_seconds')}
    result['context_validation']['final_hash_matches']=context_stage['source_final_state_hash']==context_stage['replayed_final_state_hash']
    result['context_validation']['authority']='Saved accepted receipts remain authoritative; recomputed diagnostic contexts are reference projections, not a replacement sealed run. Hash/status differences remain unresolved diagnostic limitations.'
    meta=read(owner.cache('fresh-benchmark/'+RUNS[number]+'/input.json'));mid=meta['duration_seconds']/2
    result['first_half_vs_final']=dict(midpoint_seconds=mid,first_half_updates=sum(u['timestamp']<=mid for u in result['updates']),
        final_updates=len(result['updates']),note='Damage knowledge uses completion/endpoint availability, not future damage at action start.')
    result['first_half_vs_final']['per_roster']=[]
    for mon in result['roster']:
        snapshots={}
        for label,cutoff in [('first_half',mid),('final',float('inf'))]:
            updates=[u for u in result['updates'] if u['opponent_roster_id']==mon['roster_id'] and u['timestamp']<=cutoff]
            copied=[u for u in updates if u['kind'] in {'copied_current_stats','copied_state_ended'}]
            marginals=mon['initial'] if label=='first_half' else mon['final_stats']
            if INTEGRATE:
                from knowledge.stat_feasibility import summary as stat_summary
                seen={u.get('persistent_team_member_id',u['pokemon_instance_id']) for u in updates if u.get('persistent_team_member_id',u['pokemon_instance_id']) in mon['lineage_ids']}
                marginals={}
                for stat,initial in mon['initial'].items():
                    domains=[]
                    for pid in seen:
                        changes=[u for u in updates if u.get('persistent_team_member_id',u['pokemon_instance_id'])==pid and u['kind']=='numeric_refinement' and u['observation'].get('stat')==stat]
                        domains.append(changes[-1]['after'] if changes else initial)
                    marginals[stat]=stat_summary({v for domain in domains for v in domain['values']}) if domains and all(domains) else initial
            snapshots[label]=dict(native_stat_marginals=marginals,
                native_moves_by_source_lineage={pid:sorted({u['observation']['move'] for u in updates if u.get('persistent_team_member_id',u['pokemon_instance_id'])==pid and u['kind']=='revealed_move' and u['observation'].get('native_membership')}) for pid in mon['lineage_ids']},
                confirmed_item_events=[r for r in mon['confirmed_items'] if r['time']<=cutoff],
                supported_life_orb_exclusions=sum(u['kind']=='life_orb_counterfactual' and u['new_constraint'].get('exclude_current_life_orb',False) for u in updates),
                latest_copied_current_stats=copied[-1]['after'] if copied else None)
        result['first_half_vs_final']['per_roster'].append(dict(roster_id=mon['roster_id'],name=mon['name'],snapshots=snapshots))
    result['candidate_compatibility']=public_candidate_comparison(result,database_root,mid)
    result['candidate_compatibility']['database_sha256']=database_hash
    result['candidate_compatibility']['database_unchanged']=sha(database_root/'teams.sqlite3')==database_hash
    result['unmapped_damage_episodes']=[ep['episode_id'] for ep in hp.get('episodes',[]) if (ep.get('actor_instance_id') or '').startswith(owner.battle_id+':opponent:') and ep.get('source_event_id') not in rmap]
    result['targeted_visual_reviews']=review_hashes
    if sha(Path(__file__))!=RUNNER_SHA:raise ValueError('Runner changed during execution; preserve contexts and resume inference with the new fingerprint')
    dest=out/'traces'/fp;dest.mkdir(parents=True,exist_ok=True)
    if FOCUSED:atomic_json(dest/'repaired-hp-projection.json',hp)
    atomic_json(dest/'trace.json',result)
    report=owner.report('diagnosis/'+EXPERIMENT+'/trace-'+fp+'.md');report.parent.mkdir(parents=True,exist_ok=True);report.write_text(render(result))
    if {p:sha(ROOT/p) for p in m['identity']['inputs']}!=m['identity']['inputs']:raise ValueError('Original input changed during experiment')
    summary=dict(status='complete',battle_id=owner.battle_id,trace=str((dest/'trace.json').relative_to(ROOT)),report=str(report.relative_to(ROOT)),
        counts=result['counts'],numeric_refinement=result['numerical_refinement'],source_integrity_verified=True,no_video_decoding=True,no_ocr=True,
        public_candidate_comparison='separate unweighted library compatibility; not legal-universe filtering',
        source_state_conflicts=len(result['source_state_conflicts']),unaccepted_semantic_receipts=len(result['excluded_unaccepted_events']),
        context_status_mismatches=len(result['context_validation']['receipt_status_mismatches']),context_final_hash_matches=result['context_validation']['final_hash_matches'],
        roster_count=len(result['roster']),revealed_roster_members=sum(x['revealed'] for x in result['roster']),
        remaining_unknown_selected=result['selection']['unresolved_selected_slots'],
        first_half_vs_final={k:v for k,v in result['first_half_vs_final'].items() if k!='per_roster'})
    atomic_json(dest/'summary.json',summary);atomic_json(out/'latest.json',summary)
    m['stages']['trace:'+fp]=dict(status='complete',outputs={str(p.relative_to(out)):sha(p) for p in dest.glob('*.json')},
        report=str(report.relative_to(ROOT)),report_sha256=sha(report))
    m['status']='complete';atomic_json(out/'manifest.json',m);print(json.dumps(summary,ensure_ascii=False),flush=True)
def main():
    global INTEGRATE,EXPERIMENT,FOCUSED
    p=argparse.ArgumentParser();p.add_argument('--battle',type=int,choices=RUNS,required=True)
    p.add_argument('--stage',choices=['inspect','contexts','trace','all'],default='all');p.add_argument('--resume',action='store_true')
    p.add_argument('--integration-audit',action='store_true',help='Reviewed Team7/start integration in a separate versioned namespace')
    p.add_argument('--focused-repair',action='store_true',help='Persistent unique team identity, audited move coverage and derived initial HP')
    a=p.parse_args();FOCUSED=a.focused_repair;INTEGRATE=a.integration_audit or FOCUSED
    if INTEGRATE:EXPERIMENT='hidden-integration-20261101-v1'
    if FOCUSED:EXPERIMENT='focused-repair-20261101-v1'
    owner,source,replay,projection,out,m=setup(a.battle)
    if a.stage=='inspect':print(json.dumps(dict(battle=owner.battle_id,replay=str(replay),projection=str(projection),manifest=str(out/'manifest.json')),indent=2));return
    try:
        payload=freeze_promoted_inputs(source_payload(a.battle,replay,owner),m)
        context_path=create_contexts(payload,out,m)
        guarded=freeze_promoted_inputs(source_payload(a.battle,replay,owner),m)
        if guarded!=payload:
            payload=guarded
            context_path=create_contexts(payload,out,m)
        if payload.get('diagnostic_source_admission_guard'):
            key='contexts:'+context_fingerprint(payload)
            m['stages'][key]['source_admission_guard']=payload['diagnostic_source_admission_guard']
            atomic_json(out/'manifest.json',m)
        if a.stage!='contexts':trace(a.battle,owner,source,replay,projection,out,m,context_path)
    except Exception as exc:
        m['status']='failed';m['errors'].append(dict(type=type(exc).__name__,message=str(exc),time=time.time()));atomic_json(out/'manifest.json',m);raise
if __name__=='__main__':main()

