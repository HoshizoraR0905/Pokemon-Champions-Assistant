"""Read-only post-seal verification/reporting for fresh videos without Battle Logs.

No acquisition, OCR, manual labels, state corrections or production rewrites.
"""
import argparse
import csv
from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts,canonical_id
from recognition.event_report import atomic_json,verify_seal,video_events
from recognition.fast_video import digest
from tracking.hp_causes import ADMITTED,event_time


def read(p):return json.loads(p.read_text())


def completion_intervals(samples,duration,start_epoch_ns,normal_wall_seconds):
    """Acquisition completion intervals, not per-second global replay costs."""
    if duration<=0 or normal_wall_seconds<0:raise ValueError('Invalid timing bounds')
    ordered=sorted(samples,key=lambda s:s['target_timestamp'])
    previous=start_epoch_ns;last_target=-1.;groups={}
    for sample in ordered:
        target=sample['target_timestamp'];completed=sample['completion_epoch_ns']
        if not 0<=target<duration or target<=last_target or completed<previous:
            raise ValueError('Nonchronological or out-of-range completion evidence')
        groups.setdefault(math.floor(target),[]).append(sample)
        previous=completed;last_target=target
    rows=[];previous=start_epoch_ns
    for second in range(math.ceil(duration)):
        group=groups.get(second,[]);end=min(second+1.,duration)
        completed=group[-1]['completion_epoch_ns'] if group else None
        elapsed=(completed-previous)/1e9 if completed is not None else None
        rows.append(dict(video_second_start=second,video_second_end=end,sampled_frames=len(group),
            detailed_frames=sum(s['inspected'] for s in group),
            acquisition_completion_interval_seconds=elapsed,
            acquisition_seconds_per_video_second=elapsed/(end-second) if elapsed is not None else None,
            cumulative_completion_seconds=(completed-start_epoch_ns)/1e9 if completed is not None else None,
            first_target_timestamp=group[0]['target_timestamp'] if group else None,
            last_target_timestamp=group[-1]['target_timestamp'] if group else None))
        if completed is not None:previous=completed
    tail=normal_wall_seconds-(previous-start_epoch_ns)/1e9
    if tail<0:raise ValueError('File completion clock exceeds measured CLI wall')
    return rows,tail


def second_timing(owner,run):
    """Use original atomic monitor/observation mtimes; never instrument recognition."""
    folder=owner.cache('fresh-benchmark/'+run);source=owner.cache('event-driven/'+run)
    execution=read(folder/'execution.json')
    if execution['status']!='complete' or len(execution['attempts'])!=1:
        raise ValueError('Per-second first-run timing needs one completed timing interval')
    attempt=execution['attempts'][0];start=attempt['subprocess_start_epoch_ns']
    samples=[];observations={}
    for p in sorted((source/'observations').glob('*.json')):
        row=read(p);key=row['target_timestamp']
        if key in observations:raise ValueError('Duplicate observation cell')
        observations[key]=p
    for p in sorted((source/'monitor').glob('*.json')):
        row=read(p);target=row['target_timestamp'];observed=observations.get(target)
        if row['inspected']!=(observed is not None):raise ValueError('Monitor/observation mismatch')
        completion=observed if observed is not None else p
        samples.append(dict(target_timestamp=target,timestamp=row['timestamp'],inspected=row['inspected'],
            completion_epoch_ns=completion.stat().st_mtime_ns,path=str(completion.relative_to(ROOT)),sha256=digest(completion),
            completion_basis='completed_atomic_observation' if observed else 'atomic_monitor_before_cheap_skip'))
    assert len(samples)==execution['sampled_frames'] and len(observations)==execution['detailed_inspection_frames']
    rows,tail=completion_intervals(samples,execution['input']['duration_seconds'],start,execution['normal_cli_wall_seconds'])
    destination=folder/'per-second';destination.mkdir(exist_ok=True)
    identity=dict(execution_sha256=digest(folder/'execution.json'),script_sha256=digest(Path(__file__)))
    checkpoint=destination/'manifest.json'
    if checkpoint.exists():
        prior=read(checkpoint)
        if prior['identity']!=identity:raise ValueError('Timing identity changed; preserve previous result')
        assert prior['status']=='complete'
        for name,h in prior['outputs'].items():assert digest(destination/name)==h,name
        return prior
    atomic_json(destination/'source-completions.json',samples)
    with (destination/'seconds.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    atomic_json(destination/'seconds.json',rows)
    value=dict(status='complete',identity=identity,video_seconds=execution['input']['duration_seconds'],
        normal_cli_wall_seconds=execution['normal_cli_wall_seconds'],seconds_per_video_second=execution['PTR'],
        timeline_rows=len(rows),sampled_frames=len(samples),detailed_frames=len(observations),
        post_last_sample_cli_seconds=tail,
        epoch_minus_monotonic_elapsed_seconds=(attempt['subprocess_end_epoch_ns']-start)/1e9-execution['normal_cli_wall_seconds'],
        interpretation='Per-second acquisition completion intervals include startup in the first sampled second and decoding/checkpoint work between completions. Global state replay/packaging and decoder tail are reported separately as post_last_sample_cli_seconds. Non-inspected samples use monitor publication immediately before the cheap skip. Filesystem wall-clock timestamps are not independent monotonic per-frame timers; empty sample bins remain unknown.',
        outputs={name:digest(destination/name) for name in ['source-completions.json','seconds.csv','seconds.json']})
    atomic_json(checkpoint,value);return value


def engine_from_saved(saved):
    from tracking.battle_state import from_dict
    from tracking.state_engine import StateEngine,EventRecord
    engine=StateEngine(from_dict(saved['initial_state']))
    engine.state=from_dict(saved['state']);engine.history=[EventRecord(**deepcopy(r)) for r in saved['history']]
    return engine


def check_freeze(owner,run):
    folder=owner.cache('fresh-benchmark/'+run);freeze=read(folder/'initial-freeze.json')
    assert freeze['status']=='sealed'
    for name,expected in freeze['files'].items():
        assert digest(ROOT/name)==expected,'Initial output changed: '+name
    source=owner.cache('event-driven/'+run);verify_seal(source)
    manifest=read(source/'manifest.json')
    for name,sha in manifest['identity']['sources'].items():assert digest(ROOT/name)==sha,'Production source changed: '+name
    for name,sha in manifest['outputs'].items():assert digest(ROOT/name)==sha,'Production report changed: '+name
    assert digest(owner.video())==manifest['identity']['video_sha256']
    for name,sha in read(folder/'b16-protected.json')['files'].items():assert digest(ROOT/name)==sha,'Historical B16 changed: '+name
    return folder,source,manifest


def verify(owner,run,verification_id='v1'):
    folder,source,manifest=check_freeze(owner,run);out=folder/'verification'/verification_id;out.mkdir(parents=True,exist_ok=True)
    identity=dict(initial_freeze_sha256=digest(folder/'initial-freeze.json'),script_sha256=digest(Path(__file__)))
    path=out/'manifest.json';m=read(path) if path.exists() else dict(status='running',identity=identity,stages={})
    if m['identity']!=identity:raise ValueError('Verification identity changed; preserve prior stage and use a separate verification run')
    if m['status']=='complete':return m
    atomic_json(path,m)
    try:
        if 'performance' not in m['stages']:
            execution=read(folder/'execution.json');counts=manifest['counts']
            assert execution['sampled_frames']==execution['monitored_frames']==counts['frames_materialized_at_2fps']
            assert execution['detailed_inspection_frames']==counts['frames_sampled']
            assert execution['input']['duration_seconds']==manifest['decoder']['container_duration_seconds']
            if execution['full_cold_timing_comparable']:
                assert manifest['cold_run']
                assert execution['source_decoded_frames']==execution['input']['source_frames']
                wall=execution['normal_cli_wall_seconds'];sampled=execution['sampled_frames'];inspected=execution['detailed_inspection_frames']
                assert execution['ms_per_sampled_frame']==1000*wall/sampled
                assert execution['ms_per_inspected_frame']==1000*wall/inspected
                assert execution['PTR']==wall/execution['input']['duration_seconds']
                assert execution['effective_sampled_fps']==sampled/wall
                assert wall>=execution['internal_pipeline_seconds']
                performance=dict(header_frame_count_matches_decoder=True,all_rate_formulas_checked=True,
                    external_minus_internal_seconds=wall-execution['internal_pipeline_seconds'])
            else:
                recovery=read(folder/'recovery-v1/recovery.json')
                assert recovery['status']=='complete' and not manifest['cold_run']
                assert execution['normal_cli_wall_seconds'] is None and execution['PTR'] is None
                assert execution['normal_cli_wall_lower_bound_seconds']==recovery['original_external_wall_lower_bound_seconds']+recovery['resume_wall_seconds']
                assert execution['PTR_lower_bound']==execution['normal_cli_wall_lower_bound_seconds']/execution['input']['duration_seconds']
                performance=dict(full_cold_timing_comparable=False,exact_external_wall_available=False,
                    lower_bound_formulas_checked=True,header_frame_count_matches_decoder=None,
                    decoder_note='Resumed decoder metadata describes only the suffix; full source decoding count unmeasured.')
            m['stages']['performance']=dict(**performance,monitoring_and_inspection_counts_checked=True)
            atomic_json(path,m)
        if 'events' not in m['stages']:
            began=time.perf_counter();data=read(source/'observations.json')
            events=video_events(data['observations'],data['roster'],owner.battle_id)
            for n,e in enumerate(events,1):e['attributes']['sequence']=n
            assert events==read(source/'video-only.json')['events'],'Adapted event predictions changed'
            m['stages']['events']=dict(exact_events_ids_order_evidence=True,count=len(events),wall_seconds=time.perf_counter()-began)
            atomic_json(path,m);print(owner.battle_id,'exact event reproduction',len(events),flush=True)
        expected=read(source/'replay.json')
        if 'replay' not in m['stages']:
            engine=engine_from_saved(expected);began=time.perf_counter()
            def progress(record,state):
                if record.delivery_index%100==0 or record.delivery_index==len(engine.history):
                    atomic_json(out/'progress.json',dict(stage='replay',record=record.delivery_index,total=len(engine.history)))
                    atomic_json(out/'snapshots'/f'{record.delivery_index:06d}.json',state.to_dict())
                    print(owner.battle_id,'verification replay',record.delivery_index,'/',len(engine.history),flush=True)
            engine.replay(snapshot_callback=progress);actual=json.loads(json.dumps(engine.to_dict()))
            assert actual==expected,'Replay history/state/hash changed'
            m['stages']['replay']=dict(exact_complete_serialization=True,exact_receipts=True,exact_final_state=True,
                exact_final_hash=True,events=len(engine.history),wall_seconds=time.perf_counter()-began)
            atomic_json(path,m)
        if 'hp' not in m['stages']:
            began=time.perf_counter();engine=engine_from_saved(expected);before=engine.to_dict()
            projection=engine.hp_resolutions();assert projection==read(folder/'hp-resolutions.json')
            assert engine.to_dict()==before
            numeric={o['evidence']['event_id']:(pid,o) for pid,p in engine.state.pokemon.items()
                     for o in p.hp.observations if 'unit' in o}
            covered=[eid for o in projection['episodes'] for eid in o['segment_event_ids']]
            changed={eid for eid,(_,o) in numeric.items() if o.get('delta')}
            assert len(covered)==len(set(covered)) and set(covered)==changed
            for episode in projection['episodes']:
                for c in episode['components']:
                    for key in ['before','after']:
                        trace=c['endpoints'][key]
                        if trace:
                            pid,obs=numeric[trace['event_id']]
                            assert pid==episode['affected_instance_id'] and obs['after']==c[key] and obs['unit']==c['unit']
                    if c['delta'] is not None:assert c['delta']==c['after']-c['before']
                if episode['delta'] is not None:assert episode['delta']==sum(c['delta'] for c in episode['components'])
            m['stages']['hp']=dict(exact_projection=True,state_and_receipts_unchanged=True,
                nonzero_segments=len(changed),groups=len(projection['episodes']),all_numeric_membership_and_endpoints_preserved=True,
                wall_seconds=time.perf_counter()-began);atomic_json(path,m)
        # Recheck original seals/guards after verification; no reference scoring.
        check_freeze(owner,run);m.update(status='complete',b16_historical_hashes_unchanged=True,initial_predictions_unchanged=True)
        atomic_json(path,m);return m
    except BaseException as exc:
        m.update(status='interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed',error=repr(exc));atomic_json(path,m);raise


def fact(value):
    return dict(value=value.get('value'),knowledge=value.get('knowledge','unknown')) if isinstance(value,dict) else value


def event_row(h):
    e=h['bindings'].get('resolved_event') or h['event']
    return dict(event_id=e['event_id'],time=event_time(e),kind=e['event_type'],side=e['side'],
        text=e.get('original_text'),references=e.get('canonical_references'),attributes=e.get('attributes'),
        status=h['application_status'],reason=h.get('reason'),bindings=h['bindings'],evidence=e['evidence'])


def describe(owner,run,verification_id='v1',*,partial_reference=False):
    folder,source,manifest=check_freeze(owner,run)
    verification=read(folder/'verification'/verification_id/'manifest.json');assert verification['status']=='complete'
    target=owner.report('evaluation/'+run);target.mkdir(parents=True,exist_ok=True)
    saved=read(source/'replay.json');state=saved['state'];history=saved['history'];events=[event_row(h) for h in history]
    projection=read(folder/'hp-resolutions.json');episodes=projection['episodes'];execution=read(folder/'execution.json')
    numeric=[o for p in state['pokemon'].values() for o in p['hp']['observations'] if 'unit' in o]
    types=Counter(e['kind'] for e in events);admitted=Counter(e['kind'] for e in events if e['status'] in ADMITTED)
    reasons=Counter(e['reason'] for e in events if e['status']=='deferred')
    complete=sum(o['complete_endpoints'] for o in episodes);supported=sum(o['attribution_status']=='supported' for o in episodes)
    examples=[]
    for e in events:
        if e['kind']=='multi_hit':examples.append(dict(category='multi_hit_notice',basis='parser_prediction_only',event=e))
    for o in episodes:
        rule=o.get('effect_semantics') or {};cause=o.get('cause') or {};actor=o.get('actor_instance_id');target_id=o['affected_instance_id']
        if rule.get('effect')=='contact_attacker_damage':examples.append(dict(category='contact_reaction',basis='causal_projection_prediction_only',episode=o))
        if cause.get('kind')=='move' and actor and actor!=target_id and state['pokemon'][actor]['side_id']==state['pokemon'][target_id]['side_id']:
            examples.append(dict(category='ally_targeted_move',basis='causal_projection_prediction_only',episode=o))
    inventory=[]
    for pid,p in state['pokemon'].items():
        species=p['species'];moves=p['moves']
        inventory.append(dict(instance_id=pid,side=p['side_id'],species=fact(species),location=fact(p['location']),
            fainted=fact(p['fainted']),hp={k:fact(p['hp'][k]) for k in ['current','maximum','displayed_percent','unit']},
            status=fact(p['major_status']),ability=fact(p['ability']['current']),
            item_identity=fact(p['item']['identity']),item_status=fact(p['item']['status']),
            stages={k:dict(value=fact(v['value']),interval=fact(v['interval'])) for k,v in p['stages'].items()},
            revealed_executed_moves=moves['executed'],known_move_slots=moves['known_slots']))
    final=dict(phase=fact(state['phase']),turn=fact(state['turn']),
        field={k:state[k] for k in ['weather','terrain','trick_room','global_effects']},
        sides={s:dict(active_slots=v['active_slots'],trainer=v.get('trainer'),conditions=v.get('conditions'),hazards=v.get('hazards')) for s,v in state['sides'].items()},
        inventory=inventory,source_replay=str(source/'replay.json'))
    metrics=dict(performance=execution,production_counts=manifest['counts'],production_summary=manifest.get('results',{}),
        event_types=dict(types),admitted_event_types=dict(admitted),
        move_executions_recognized=types['move_execution'],move_executions_admitted=admitted['move_execution'],
        switches=types['switch_out'],send_outs=types['send_out'],faints=types['faint'],
        receipt_statuses=dict(Counter(e['status'] for e in events)),deferred_events=sum(e['status']=='deferred' for e in events),
        deferred_reasons=dict(reasons),rejected_events=sum(e['status']=='rejected' for e in events),conflicts=len(state['conflicts']),
        side_resolved_events=sum(e['side'] in ['self','opponent','field'] for e in events),
        actor_bound_receipts=sum(bool(e['bindings'].get('actor',{}).get('pokemon_instance_id')) for e in events),
        entry_episodes=len(state['knowledge'].get('active_entry_episodes',[])),encounter_instances=len(state['pokemon']),
        hp_numeric_observations=len(numeric),hp_numeric_changes=sum(bool(o.get('delta')) for o in numeric),
        hp_units=dict(Counter(o['unit'] for o in numeric)),hp_initial_or_missing_baselines=sum(o.get('observed_before') is None for o in numeric),
        action_executions=len(projection['actions']),observed_hp_episode_denominator=len(episodes),
        complete_hp_episodes=complete,supported_hp_causal_episodes=supported,
        immediate_cause_supported=sum(o['immediate_cause_status']=='supported' for o in episodes),
        causal_coverage=supported/len(episodes) if episodes else None,
        complete_endpoint_causal_coverage=supported/complete if complete else None,
        incomplete_reasons=dict(Counter(r for o in episodes for r in o['reasons'])),
        unknown_events=types['unknown'],accuracy_measured=False,independent_reference_used=False,battle_log_used=False,
        examples_by_category=dict(Counter(e['category'] for e in examples)),verification=verification['stages'])
    atomic_json(target/'metrics.json',metrics);atomic_json(target/'final-state-summary.json',final)
    atomic_json(target/'events.json',events);atomic_json(target/'examples.json',examples)
    reference_note=('Partial Battle Log review is reported separately; these counts describe pipeline behavior, not accuracy.' if partial_reference else 'No Battle Log or independent labels exist; all counts describe pipeline behavior, not accuracy.')
    timing=(f'Normal production wall: **{execution["normal_cli_wall_seconds"]:.3f} s**; PTR **{execution["PTR"]:.4f}**.' if execution['normal_cli_wall_seconds'] is not None else
        f'Interrupted/resumed run: exact total wall and PTR unavailable. External wall lower bound **{execution["normal_cli_wall_lower_bound_seconds"]:.3f} s**, PTR lower bound **{execution["PTR_lower_bound"]:.4f}**; not a full cold timing measurement.')
    lines=[f'# {owner.battle_id} — fresh video-only reconstruction','',f'Initial run `{run}`. Raw predictions and the HP view were sealed before failure review. '+reference_note,
        '',timing+f' Monitoring: {execution["sampled_frames"]} frames; detailed inspections: {execution["detailed_inspection_frames"]}; OCR model calls: {execution["ocr_model_invocations"]}.',
        '',f'Parsed move executions: **{types["move_execution"]}** ({admitted["move_execution"]} admitted, including revelation-only records). Switch-out/send-out/faint predictions: **{types["switch_out"]}/{types["send_out"]}/{types["faint"]}**.',
        '',f'HP coverage: **{complete}/{len(episodes)}** groups have complete stable numeric endpoints; **{supported}/{len(episodes)}** have complete supported causal totals. All {metrics["hp_numeric_changes"]} admitted nonzero numeric segments occur exactly once. The denominator is observed action/target HP groups, as in B16, and excludes completely unseen HP events; it is not recall. {metrics["immediate_cause_supported"]} groups have a supported immediate cause including incomplete totals.',
        '',f'Receipts: `{metrics["receipt_statuses"]}`. Deferred: {metrics["deferred_events"]}; rejected: {metrics["rejected_events"]}; state conflicts: {metrics["conflicts"]}. Exact event adaptation and complete state/receipt/hash replay were reproduced offline, which establishes determinism rather than recognition correctness.',
        '', '## Predicted observable events','',f'Event-type inventory: `{dict(types)}`.',
        '',f'Deferred reasons: `{dict(reasons)}`.',f'Unresolved HP reasons: `{metrics["incomplete_reasons"]}`.',
        '', '## Move and condition receipts','',
        'These are source-text/parser predictions with their actual admission status, not independently verified executions/effects. Item/ability announcements alone do not supply HP amounts.',
        '', '| Source s | Kind | Side | Literal text | Receipt |','|---:|---|---|---|---|']
    semantic=[e for e in events if e['kind'] in {'move_execution','ability_activation','item_activation','weather_change',
        'terrain_change','status_change','side_condition_change','stat_change'}]
    atomic_json(target/'semantic-inventory.json',semantic)
    for e in semantic:
        text=(e.get('text') or '').replace('\n',' ').replace('|','\\|')
        lines.append(f'| {e["time"]} | {e["kind"]} | {e["side"]} | {text} | {e["status"]} |')
    lines+=['','No parsed status/terrain notice is treated as evidence of absence. Full literal references and per-fact evidence remain in [semantic-inventory.json](semantic-inventory.json).',
        '', '## HP episodes','', '| Source s | Affected instance | Cause | Before → after | Delta/unit | Status / reasons |','|---:|---|---|---|---|---|']
    for o in episodes:
        p=state['pokemon'][o['affected_instance_id']];name=(p['species'].get('value') or {}).get('name') or 'unknown'
        cause=o['cause'] or {};label=(cause.get('source') or {}).get('name') or cause.get('status') or cause.get('kind') or 'unknown'
        lines.append(f'| {o["source_event"]["time"]} | {p["side_id"]} {name} / `{o["affected_instance_id"]}` | {label} | {o["before"]} → {o["after"]} | {o["delta"]} / {o["unit"]} | {o["attribution_status"]}; '+', '.join(o['reasons'])+' |')
    lines +=['','## Final state and identity limits','',f'Final phase: `{final["phase"]}`; turn: `{final["turn"]}`. Game turns are not reconstructed from hypothetical logs.',
        '', '| Side | Slot | Instance | Species | Current HP | Fainted / status |','|---|---|---|---|---|---|']
    for side,v in state['sides'].items():
        for slot,pid in v['active_slots'].items():
            p=state['pokemon'][pid];sp=(p['species'].get('value') or {}).get('name') or 'unknown'
            lines.append(f'| {side} | {slot} | `{pid}` | {sp} | absolute `{fact(p["hp"]["current"])}`; percent `{fact(p["hp"]["displayed_percent"])}` | `{fact(p["fainted"])}` / `{fact(p["major_status"])}` |')
    lines +=['', 'Full observable inventory, conditions, revealed moves, stages, items and abilities: [final-state-summary.json](final-state-summary.json). Facts retain observed/derived/unknown/conflicting categories. Encounter counts are not biological team size; unproven same-species returns are not merged.',
        '',f'Potential multi-hit/contact/ally examples: `{metrics["examples_by_category"]}`. [examples.json](examples.json) contains prediction evidence, not independent verification. Zero notices do not prove no such move occurred. No high-FPS acquisition is integrated into this production command; optional source review is not represented as measured recognition success.',
        '', f'Raw events, receipt bindings and source images: [events.json](events.json). [Original production viewer](../../event-driven/{run}/review.html). HP projection with endpoint IDs and provenance remains in `fresh-benchmark/<run>/hp-resolutions.json`.',
        '', 'Limitations: these descriptive counts do not measure event/state accuracy; incomplete numeric endpoints, ambiguous causes/identities, deferred/rejected receipts and unknown facts remain unresolved. No recognition rules were tuned from this recording. The stock production viewer includes inherited caveat text about prior recognition context; this benchmark’s fresh namespace/cache provenance is recorded separately in the execution/freeze manifests.']
    (target/'report.md').write_text('\n'.join(lines)+'\n');return metrics


def comparison(battles,run):
    metrics=[read(BattleArtifacts(b,ROOT).report('evaluation/'+run+'/metrics.json')) for b in battles]
    performance=[m['performance'] for m in metrics]
    wall=sum(p['normal_cli_wall_seconds'] for p in performance);sampled=sum(p['sampled_frames'] for p in performance)
    inspected=sum(p['detailed_inspection_frames'] for p in performance);duration=sum(p['input']['duration_seconds'] for p in performance)
    pooled=dict(normal_wall_seconds=wall,sampled_frames=sampled,detailed_inspection_frames=inspected,
        video_duration_seconds=duration,ms_per_sampled_frame=1000*wall/sampled,ms_per_inspected_frame=1000*wall/inspected,
        PTR=wall/duration,effective_sampled_fps=sampled/wall)
    rows=[('Video duration (s)',lambda m:f'{m["performance"]["input"]["duration_seconds"]:.2f}'),
        ('Source frames',lambda m:m['performance']['input']['source_frames']),
        ('Average source FPS',lambda m:f'{m["performance"]["input"]["source_average_fps"]:.6f}'),
        ('Sampled / monitored frames',lambda m:m['performance']['sampled_frames']),
        ('Detailed inspection frames',lambda m:m['performance']['detailed_inspection_frames']),
        ('OCR model invocations',lambda m:m['performance']['ocr_model_invocations']),
        ('Normal processing wall (s)',lambda m:f'{m["performance"]["normal_cli_wall_seconds"]:.3f}'),
        ('ms per sampled frame',lambda m:f'{m["performance"]["ms_per_sampled_frame"]:.3f}'),
        ('ms per detailed frame',lambda m:f'{m["performance"]["ms_per_inspected_frame"]:.3f}'),
        ('PTR',lambda m:f'{m["performance"]["PTR"]:.4f}'),
        ('Effective sampled FPS',lambda m:f'{m["performance"]["effective_sampled_fps"]:.3f}'),
        ('Move executions parsed / admitted',lambda m:f'{m["move_executions_recognized"]} / {m["move_executions_admitted"]}'),
        ('Complete HP endpoints / observed groups',lambda m:f'{m["complete_hp_episodes"]} / {m["observed_hp_episode_denominator"]}'),
        ('Supported complete HP causal groups / groups',lambda m:f'{m["supported_hp_causal_episodes"]} / {m["observed_hp_episode_denominator"]}'),
        ('Deferred events / state conflicts',lambda m:f'{m["deferred_events"]} / {m["conflicts"]}'),
        ('Rejected events',lambda m:m['rejected_events'])]
    lines=['# Fresh B17/B18 video processing and performance benchmark','',f'Initial pre-tuning run `{run}`. Both recordings have no Battle Log. No independent accuracy labels were supplied or generated. Processing/replay consistency and observed HP coverage are separate from correctness.',
        '', '| Metric | B17 | B18 |','|---|---:|---:|']
    for label,fn in rows:lines.append('| '+label+' | '+' | '.join(str(fn(m)) for m in metrics)+' |')
    lines +=['',f'Aggregate normal wall: **{wall:.3f} s** over {duration:.2f} video seconds. Pooled ms/sample: **{pooled["ms_per_sampled_frame"]:.3f}** ({sampled} samples); pooled ms/inspection: **{pooled["ms_per_inspected_frame"]:.3f}** ({inspected} inspections). Aggregate PTR **{pooled["PTR"]:.4f}** and throughput **{pooled["effective_sampled_fps"]:.3f} sampled frames/s** use summed numerators and denominators, not means of per-video rates.',
        '', '## Measurement and frozen inputs','', 'Actual production command: `main.py --video VIDEO --profile event-driven --identity-mode lightweight --sample-fps 2 --run-id '+run+'`. PP-OCRv6 ONNX CPU; current HUD/message/banner/identity semantics and StateEngine. Source images normalize from 2622×1206 to 1311×603. Shared pinned models/icons/knowledge are permitted; per-battle frame/recognition/state caches began empty. These are new prediction-cache runs, not claims of cold OS filesystem caches.',
        '', 'External monotonic timing includes subprocess/import startup, source hashing/sampling/decoding, visual extraction, OCR/icons, parsing, identity/state reconstruction and normal viewer export. Input header inspection, derived HP projection, sealing, regression replay and report generation are outside this clock. Counts labelled sampled/monitored refer to all 2 FPS materialized frames; the legacy production field `frames_sampled` and stock summary `sampled_frames` actually count detailed inspections.',
        '', 'Container durations come from FFmpeg header text (0.01 s precision), matching the prior B16 PTR denominator convention; average stream FPS and header frame counts are separately preserved. No full-video preflight decoding was performed.',
        '', '| Frozen input | B17 | B18 |','|---|---|---|',
        '| Exact video path | '+' | '.join('`'+p['input']['path']+'`' for p in performance)+' |',
        '| Source SHA-256 | '+' | '.join('`'+p['input']['sha256']+'`' for p in performance)+' |',
        '| Original resolution | '+' | '.join(str(p['input']['width'])+'×'+str(p['input']['height']) for p in performance)+' |',
        '', 'Host/execution metadata: `'+str(performance[0]['hardware'])+'`.',
        '', '| Cross-check | B17 | B18 |','|---|---:|---:|',
        '| Internal pipeline wall (s) | '+' | '.join(f'{p["internal_pipeline_seconds"]:.3f}' for p in performance)+' |',
        '| External minus internal (s) | '+' | '.join(f'{p["normal_cli_wall_seconds"]-p["internal_pipeline_seconds"]:.3f}' for p in performance)+' |',
        '| Actual decoder source frames | '+' | '.join(str(p['source_decoded_frames']) for p in performance)+' |',
        '| Recorded OCR work (s) | '+' | '.join(f'{m["production_counts"].get("ocr_seconds",0):.3f}' for m in metrics)+' |',
        '| Recorded icon work (s) | '+' | '.join(f'{m["production_counts"].get("icon_seconds",0):.3f}' for m in metrics)+' |',
        '| Icon recognition calls | '+' | '.join(str(m['production_counts'].get('icon_invocations_performed',0)) for m in metrics)+' |',
        '| Packaging/reconstruction through summary (s) | '+' | '.join(f'{m["production_summary"].get("replay_seconds",0):.3f}' for m in metrics)+' |',
        '| Separate HP projection (s; excluded) | '+' | '.join(f'{read(BattleArtifacts(b,ROOT).cache("fresh-benchmark/"+run+"/projection-stage.json"))["wall_seconds"]:.3f}' for b in battles)+' |',
        '| Adaptive high-FPS passes / frames / seconds | 0 / 0 / 0 | 0 / 0 / 0 |',
        '', 'Targeted high-FPS inspection is an available separate tool, not integrated into the current normal command. It was not added to the untouched initial run or represented as integrated processing. The latest action-level HP projection is saved and timed separately from the sealed live receipts; no manual endpoint supplements are supplied.',
        '', 'The OCR/icon work counters are existing wall spans around recognition work, which may include initialization and I/O; they are not isolated CPU-time profiles. The packaging/reconstruction span begins before event adaptation and ends at summary creation, before the remainder of viewer export. It is a diagnostic subspan, not a replacement for external command wall time. Decoder work can overlap other work, so no additive CPU attribution is claimed.',
        '', '## Comparison with prior B16','', 'B16 previously measured normal PTR **0.8838** (666.124 s / 753.74 s). These measurements use the current implementation and different source durations, frame rates and battle content; 2 FPS/lightweight profile names alone do not establish equivalent work. Changes include the current sequential HP/causal enrichment and reconstruction implementation. Rate differences are descriptive observations, not isolated evidence that any one change caused a speedup or slowdown.',
        '', 'The archived B16 configuration is `event-driven-v1`; these fresh runs use `event-driven-banner-hp-v2`. Nominal 2 FPS/lightweight settings and the pinned OCR/icon manifest hashes are unchanged, while recognition/state/parser implementations differ. The latest B16 source-completed HP result additionally used separate targeted source evidence; these initial B17/B18 coverage counts have no such supplementary pass.',
        '', '## Observable reconstruction and limits','']
    for b,m in zip(battles,metrics):
        lines +=[f'- {b}: event types `{m["event_types"]}`; deferred reasons `{m["deferred_reasons"]}`; unresolved HP reasons `{m["incomplete_reasons"]}`.',
            f'  Identity: {m["actor_bound_receipts"]} actor-bound receipts, {m["entry_episodes"]} entry episodes, {m["encounter_instances"]} encounter instances. HP: {m["hp_numeric_observations"]} numeric observations, {m["hp_numeric_changes"]} nonzero segments. Example candidates `{m["examples_by_category"]}` are parser/projection predictions unless separately source-reviewed.',
            f'  [Per-battle report](battles/{b}/evaluation/{run}/report.md) · [final state](battles/{b}/evaluation/{run}/final-state-summary.json).']
    lines +=['', 'The action-level denominator uses observed HP action/target groups as in B16, including incomplete groups. It does not enumerate every actual damage event in the video. Unknown targets/causes, first readings with no baseline, unsettled final values and missing coverage remain unresolved. Ability/item activations do not automatically imply numeric HP changes. Opponent HP units remain displayed percentage points.',
        '', 'Both full-video CLI runs completed and their output inventories/source/model/configuration fingerprints were sealed before failure inspection. Event adaptation, full receipts/state/hash replay and HP projection/endpoint membership were reproduced afterward with no OCR or decoding. All protected historical B16 files remained byte-identical. These checks measure reproducibility rather than event/state accuracy. No Battle Log extraction/reconstruction/scoring or B16 replay was run.',
        '', 'A post-seal saved-frame review found phone Control Center overlays in both final frames despite stored `battle_animation` phase labels, and confirmed the visible Light Screen message associated with B17’s rejected condition receipt. The localized evidence, other conflicts and limits are documented in [source review](../docs/b17-b18-benchmark/source-review.md). These observations were not used to modify initial predictions or generate accuracy labels.',
        '', 'Provenance, checkpoints and resume commands: [benchmark notes](../docs/b17-b18-benchmark/progress.md). No production recognition rules were modified from these samples; no commit or push.']
    validation_path=BattleArtifacts(battles[0],ROOT).cache('fresh-benchmark/'+run+'/test-results.json')
    if validation_path.exists():
        validation=read(validation_path)
        lines+=['','## Regression validation','']
        for label in ['preflight','postflight']:
            v=validation[label];lines.append(f'{label}: **{v["passed"]} passed, {v["deselected"]} deselected** in {v["seconds"]:.2f} s. No selected failures/skips. Optional historical-artifact tests were deselected.')
        lines+=['','Both commands returned zero. The reporting-only schema correction preserved the fingerprint-matched successful verification implementation and reran only report export; no video acquisition/OCR or state replay was repeated for it.']
    output=ROOT/'reports/Fresh-Video-Benchmark-B17-B18-20261028.md';output.write_text('\n'.join(lines)+'\n')
    atomic_json(BattleArtifacts(battles[0],ROOT).cache('fresh-benchmark/'+run+'/pooled-metrics.json'),pooled)
    print(output);return pooled


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--battles',nargs='+',required=True);p.add_argument('--run-id',required=True)
    p.add_argument('--stage',choices=['verify','summary'],required=True)
    p.add_argument('--verification-id',default='v1');a=p.parse_args()
    battles=[canonical_id(b) for b in a.battles];run=canonical_id(a.run_id)
    # Require both initial seals before any error/limitation inspection.
    for b in battles:assert BattleArtifacts(b,ROOT).cache('fresh-benchmark/'+run+'/initial-freeze.json').exists()
    if a.stage=='verify':
        for b in battles:verify(BattleArtifacts(b,ROOT),run,canonical_id(a.verification_id))
    else:
        for b in battles:describe(BattleArtifacts(b,ROOT),run,canonical_id(a.verification_id))
        comparison(battles,run)
