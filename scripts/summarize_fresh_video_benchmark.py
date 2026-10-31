"""Post-process sealed fresh runs without changing production predictions.

Run logs, review, then summary after the sequential acquisition plan completes.
Pass B uses existing log extraction in a separate report directory. Its OCR
outputs are machine predictions, never ground truth for the live pipeline.
"""
import argparse
from collections import Counter
import csv
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.fast_video import digest
from recognition.video_sampling import atomic_json


def read(path):
    return json.loads(path.read_text())


def csv_file(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def verify(owner, run):
    folder = owner.cache('event-driven/' + run)
    from recognition.event_report import verify_seal
    verify_seal(folder)
    execution = read(owner.cache('evaluation/' + run + '/execution.json'))
    for name, expected in execution['sealed_outputs'].items():
        assert digest(folder / name) == expected, name
    manifest = read(folder / 'manifest.json')
    for name, expected in manifest['outputs'].items():
        assert digest(ROOT / name) == expected, name
    assert manifest['cold_run'] and manifest['status'] == 'complete'
    assert manifest['identity']['end'] is None and manifest['identity']['max_frames'] is None
    assert not any(k in manifest['identity'] for k in ('frame_cache', 'recognition_caches'))
    return folder, manifest, execution


def logs(owner, run):
    from scripts.compare_battle_log import compare
    folder, _, _ = verify(owner, run)
    target = owner.report('evaluation/' + run + '-logs')
    checkpoint = owner.cache('evaluation/' + run + '/log-stage.json')
    if checkpoint.exists():
        result = read(checkpoint)
        assert result['status'] == 'complete', 'Inspect failed log stage before resuming'
        verify(owner, run)
        return
    target.mkdir(parents=True, exist_ok=False)
    original = owner.report('event-driven/' + run)
    for name in ('video-only.json', 'summary.json', 'monitoring.json'):
        shutil.copyfile(original / name, target / name)
    frames = read(original / 'frames.json')
    # Same-battle evidence link; no PNG copying or prediction rewrite.
    (target / 'assets').symlink_to(os.path.relpath(original / 'assets', target), target_is_directory=True)
    atomic_json(target / 'frames.json', frames)

    class SeparateReport:
        # Only reporting paths differ. OCR/extraction/parser inputs are unchanged.
        def __getattr__(self, name):
            return getattr(owner, name)

        def report(self, name):
            assert name == 'event-driven/' + run
            return target

    command = [sys.executable, str(Path(__file__).resolve()), '--plan', str(ARGS.plan), '--stage', 'logs']
    atomic_json(checkpoint, dict(status='running', command=command, output=str(target.relative_to(ROOT))))
    start = time.perf_counter()
    try:
        result = compare(SeparateReport(), run)
    except Exception as exc:
        atomic_json(checkpoint, dict(status='failed', error=repr(exc), wall_seconds=time.perf_counter()-start))
        raise
    atomic_json(checkpoint, dict(status='complete', wall_seconds=time.perf_counter()-start,
        result=result, report=str((target / 'review.html').relative_to(ROOT)),
        note='Separate automatic historical-log predictions; not verified ground truth. No live state corrections.'))
    verify(owner, run)


def review(owner, run):
    from scripts.build_battle_evaluation import build
    folder, manifest, _ = verify(owner, run)
    evaluation_id = run + '-review'
    build(owner, run, evaluation_id)
    target = owner.report('evaluation/' + evaluation_id)
    replay = read(folder / 'replay.json')
    observations = read(folder / 'observations.json')['observations']
    by_source = {r['source_id']: r for r in observations}
    rows = []
    for receipt in replay['history']:
        e = receipt['event']; resolved = receipt['bindings'].get('resolved_event') or e
        evidence = e['evidence']
        image = next((p.get('details', {}).get('image') or by_source.get(p['source_id'], {}).get('image')
                      for p in evidence if p.get('details', {}).get('image') or p['source_id'] in by_source), '')
        t = e['attributes']['observation_time']
        rows.append(dict(event_id=e['event_id'],timestamp=t,event_type=e['event_type'],
            status=receipt['application_status'],reason=receipt['reason'],side=resolved['side'],
            raw_text=e['original_text'],actor=json.dumps(resolved.get('actor'),ensure_ascii=False),
            target=json.dumps(resolved.get('target'),ensure_ascii=False),
            references=json.dumps(resolved.get('canonical_references'),ensure_ascii=False),
            attributes=json.dumps(e['attributes'],ensure_ascii=False),
            bindings=json.dumps(receipt['bindings'],ensure_ascii=False),
            evidence=json.dumps(evidence,ensure_ascii=False),
            screenshot=os.path.relpath(ROOT / image, target) if image else '',
            video=os.path.relpath(owner.video(),target)+'#t='+str(max(0,t-2)),
            ground_truth_id='',verdict='',error_categories='',reviewer='',notes=''))
    fields = list(rows[0]) if rows else ['event_id','timestamp','ground_truth_id','verdict','error_categories','reviewer','notes']
    # Do not overwrite user annotations on a reporting resume.
    prediction_csv = target / 'predictions-review.csv'
    if not prediction_csv.exists():
        csv_file(prediction_csv, rows, fields)
    timeline = read(owner.cache('evaluation/' + evaluation_id + '/timeline.json'))
    state_rows = [dict(timestamp=r['timestamp'],event_id=r['event_id'],
        predicted_slots=json.dumps(r['slots'],ensure_ascii=False),
        ground_truth_id='',verdict='',error_categories='',reviewer='',notes='') for r in timeline['changes']]
    if not (target / 'state-review.csv').exists():
        csv_file(target/'state-review.csv',state_rows,list(state_rows[0]))
    ground_truth = target / 'ground-truth.json'
    if not ground_truth.exists():
        atomic_json(ground_truth,dict(schema='fresh-video-human-ground-truth-v1',battle_id=owner.battle_id,
            video_sha256=manifest['identity']['video_sha256'],prediction_sha256=digest(folder/'video-only.json'),
            status='pending',reviewer=None,reviewed_intervals=[],events=[],checkpoints=[],
            shared_team=dict(source_video='sample_battle_13',verified=False,configuration=None),
            errors_allowed=['correct_recognition','wrong_attribution','missing_event','extra_duplicate_event',
                'wrong_semantics','wrong_state','unresolved'],
            event_fields=['ground_truth_id','time_start','time_end','channel','event_type','raw_text',
                'actor','target','move','hp_before','hp_after','evidence','verified_fields','matched_prediction_ids'],
            checkpoint_fields=['ground_truth_id','timestamp','slots','verified_fields','evidence'],
            note='Blank collections are unreviewed, not zero errors. Establish truth from video before comparing predictions.'))
    video = os.path.relpath(owner.video(),target)
    live = os.path.relpath(owner.report('event-driven/'+run+'/review.html'),target)
    log = os.path.relpath(owner.report('evaluation/'+run+'-logs/review.html'),target)
    (target/'review.md').write_text(f'''# {owner.battle_id}: first-pass human review

[Original complete video]({video}) · [Four-slot timeline and source screenshots](review.html) · [Live prediction viewer]({live}) · [Automatic Battle Log predictions]({log})

Ground truth: **pending**. Machine log output, model confidence and state acceptance are not ground truth. Do not edit sealed predictions. Video log inspection time is not original action time. COMMAND cycles are not verified turns.

1. Watch the original video with predictions hidden; record exhaustively reviewed time intervals and visible events in `ground-truth.json`. Include missing events even if no prediction exists. Assign stable truth IDs. Record channel `live_message` versus `historical_log`, visibility intervals, text, species/form, side/slot, move, user/target and HP units only where visible. Unknown stays unknown. Replay short ranges in the original player for transient states.
2. Check active identity, HP and stages at independent decision-screen timestamps and before/after switches, fainting and Mega Evolution. Fill `checkpoints` from video; use `state-review.csv` and the timeline to compare. Do not use displayed game turn numbers or predicted boundaries as proof of turn completeness. Battle 13's shared team may be manually transcribed and verified for all three videos separately; no team configuration was fed to runtime.
3. Compare to `predictions-review.csv` and the existing viewer. Use `correct_recognition`, `wrong_attribution`, `missing_event`, `extra_duplicate_event`, `wrong_semantics`, `wrong_state`, or `unresolved` (multiple error categories allowed). Keep unmatched predictions as extra only inside exhaustively reviewed intervals. Mark unreviewed rows blank. CSV/JSON hold field-level annotations; the existing viewer's export button supports log comparisons when log rows exist. Retain any exported notes beside this review.

Match true event occurrences one-to-one by source visibility interval and chronological evidence, independently of OCR text; repeated screenshots of one occurrence are not new truth events. Do not merge recurrent uses of the same move. Live and retrospective log channels are scored separately; a log row is not a second execution. An extra repeated prediction is an FP once verified, even if its text is correct. `deferred` is a state-application outcome, not automatically an FN or FP.

## Denominators after annotation

- Detection precision = matched unique predictions / all event predictions in exhaustively reviewed intervals; recall = matched truth occurrences / all visible truth occurrences in those intervals. Report FP, FN and duplicate FP counts. Exclude HUD/preview/checkpoint observations from gameplay-event detection. Score detection separately from semantic correctness.
- Strict text = exact transcription matches / matched events with verified readable text (ignore whitespace/line breaks only; retain punctuation). Report any additional normalization separately.
- Move = correct canonical move / verified executed-move occurrences, including unresolved/missed recognitions in the denominator. Menu options do not prove execution. User/target attribution = correct attribution / matched events with independently verifiable user/target, separately. Unknown targets are excluded with an explicit excluded count.
- Species/form and slot = correct fields / independently verified visible fields, separately. Species alone does not establish form or stable instance continuity. Separate raw HUD extraction from reconstructed active occupancy.
- HP = exact values or current/maximum pairs / verified readable values or pairs, separately for exact HP and percentages. HP-change endpoints, instance attribution and damage cause are distinct. Do not infer opponent exact HP from percentages.
- State = correct fields / verified checkpoint fields, separately for identity/slot, HP, stages/status/field effects and revealed moves. Also report fully correct checkpoints / reviewed checkpoints; unsupported/unknown predictions count as misses for visible verified fields.
- Event types and switching/faint/Mega/special mechanisms = correct / verified occurrences of each type, including misses. No positive examples means unmeasured, not 100%.

Keep reviewer identity, original-frame/time evidence, uncertainty and reviewed intervals. Pool numerators and denominators only across compatible definitions; never average percentages or claim an overall accuracy from this checklist.
''',encoding='utf-8')
    verify(owner, run)


def summary(plan, destination):
    results=[]
    for n in (13,14,15):
        owner=BattleArtifacts('sample_battle_'+str(n));run=plan['run_id']
        folder,m,execution=verify(owner,run)
        replay=read(folder/'replay.json');counts=m['counts'];history=replay['history']
        types=Counter(h['event']['event_type'] for h in history)
        # Observation families and auxiliary checks are never gameplay actions.
        observations={k:v for k,v in types.items() if k.endswith('_observation') or k in {'command_checkpoint','trainer_observation'}}
        gameplay={k:v for k,v in types.items() if k not in observations}
        logstage=read(owner.cache('evaluation/'+run+'/log-stage.json'))
        wall=execution['wall_seconds'];logwall=logstage['wall_seconds']
        manifest=read(folder/'reference/manifest.json')
        # Log grouping diagnostics are not measured duplicate or accuracy rates.
        row=dict(battle_id=owner.battle_id,duration_seconds=m['decoder']['container_duration_seconds'],
            source_decoded_frames=m['decoder']['source_decoded_frames'],
            materialized_frames=counts['frames_materialized_at_2fps'],inspected_frames=counts['frames_sampled'],
            pipeline_external_wall_seconds=wall,pipeline_internal_wall_seconds=m['cold_end_to_end_wall_seconds'],
            automatic_log_wall_seconds=logwall,combined_pipeline_and_log_wall_seconds=wall+logwall,
            sampled_fps=counts['frames_materialized_at_2fps']/(wall+logwall),
            event_records=len(history),observation_and_auxiliary_types=observations,
            gameplay_candidate_types=gameplay,gameplay_candidates=sum(gameplay.values()),
            application_statuses=dict(Counter(h['application_status'] for h in history)),
            duplicate_event_ids=len(history)-len({h['event']['event_id'] for h in history}),
            semantic_duplicates='unmeasured; human review pending',
            log_entries=manifest['observed_log_entries'],log_counts=manifest['counts'],
            total_with_separate_log_records=len(history)+manifest['observed_log_entries'],
            raw_message_selection_count=None,accuracy=None,accuracy_status='pending independent human ground truth',
            ocr_invocations=counts.get('ocr_invocations_performed',0),ocr_exact_cache_hits=counts.get('ocr_exact_cache_hits',0),
            ocr_unchanged_region_reuse=counts.get('ocr_region_reads_reused',0),
            unknown_phase_fallback_checkpoints=counts.get('unknown_fallback_checkpoints',0),
            inspected_at_1fps=counts.get('inspected_frames_at_1fps',0),
            icon_invocations=counts.get('icon_invocations_performed',0),
            execution_source_unchanged=execution['frozen_runtime_unchanged'],video_unchanged=execution['video_unchanged'],
            completed=True)
        obs=read(folder/'observations.json')['observations']
        row['raw_message_selection_count']=sum(bool(r.get('message',{}).get('selected')) for r in obs)
        row['occurrence_decisions']=dict(Counter(r.get('occurrence_decision',{}).get('reason','unknown') for r in obs))
        row['warning_counts']=dict(Counter(str(w) for r in obs for w in r.get('snapshot',{}).get('warnings',[])))
        warning_lines=[]
        for path in [owner.cache('evaluation/'+run+'/production.log'),folder/'decode.log']:
            with path.open(errors='replace') as stream:
                for number,line in enumerate(stream,1):
                    if re.search(r'warning|fallback|traceback|\[W:|\[E:|error',line,re.I):
                        # Ignore exported JSON keys such as error:null and normal decoder information.
                        if line.lstrip().startswith(('"','[showinfo')):
                            continue
                        warning_lines.append(dict(path=str(path.relative_to(ROOT)),line=number,text=line.rstrip()))
        atomic_json(owner.cache('evaluation/'+run+'/warning-lines.json'),warning_lines)
        row['warning_log_line_count']=len(warning_lines)
        row['zero_cross_run_cache_input']=not any(k in m['identity'] for k in ['recognition_caches','frame_cache'])
        row['pipeline_error']=m.get('error')
        results.append(row)
    totals={k:sum(r[k] for r in results) for k in ['duration_seconds','source_decoded_frames','materialized_frames',
        'inspected_frames','pipeline_external_wall_seconds','automatic_log_wall_seconds','combined_pipeline_and_log_wall_seconds',
        'event_records','gameplay_candidates','log_entries']}
    totals['sampled_fps']=totals['materialized_frames']/totals['combined_pipeline_and_log_wall_seconds']
    totals['completed']=sum(r['completed'] for r in results)
    totals['attempted']=len(results)
    destination.parent.mkdir(parents=True,exist_ok=True)
    atomic_json(destination,dict(plan=str(ARGS.plan),videos=results,pooled=totals,accuracy=None,
        evaluator_sha256=digest(Path(__file__)),
        definitions='Combined runtime is measured canonical CLI wall plus separate automatic Pass B log extraction wall. Postprocessing/review replay excluded. Observations and gameplay candidates are machine categories, not ground-truth events.'))
    print(json.dumps(dict(videos=results,pooled=totals),ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--stage',choices=['logs','review','summary'],required=True)
    ARGS=parser.parse_args();plan=read(ARGS.plan)
    assert plan['status']=='complete','Finish acquisition before postprocessing; avoid benchmark contention'
    if ARGS.stage=='summary':
        summary(plan,ARGS.plan.parent/'summary.json')
    else:
        for n in (13,14,15):
            owner=BattleArtifacts('sample_battle_'+str(n));run=plan['run_id']
            print(ARGS.stage,owner.battle_id,flush=True)
            (logs if ARGS.stage=='logs' else review)(owner,run)
