"""Offline phase/turn performance from immutable production call records.

A saved-evidence prototype has no acquisition cost measurements. A completed
profiled run records actual monotonic spans; aggregation does not change them.
"""
import argparse
from bisect import bisect_right
from collections import Counter,defaultdict
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.fast_video import digest
from recognition.event_report import verify_seal
from recognition.video_sampling import atomic_json
from scripts.production_phase_timeline import PHASES,CONDITIONS,build_timeline,sample_at


def read(path):return json.loads(path.read_text())
def lines(path):
    with path.open() as stream:return [json.loads(line) for line in stream if line.strip()]


def enrich(frames,rows):
    by={r['source_id']:r for r in rows}
    by_time={r['timestamp']:r for r in rows}
    result=[]
    for f in frames:
        f=deepcopy(f);row=by.get(f.get('source_id')) or by_time.get(f['timestamp'])
        if row:
            f.update(source_id=row['source_id'],image=row['image'],sha256=row['sha256'],message=row['message'])
            if 'ui' not in f:f['ui']=row['ui']
            if 'w_detection' not in f:f['w_detection']=row.get('command_inspection')
        result.append(f)
    return result


def prototype(owner,baseline,target):
    source=owner.cache('event-driven/'+baseline);verify_seal(source)
    rows=read(source/'observations.json')['observations'];monitors=[read(p) for p in sorted((source/'monitor').glob('*.json'))]
    frames=enrich([{**r,'command_label':dict(visible=r.get('command',{}).get('visible',False))} for r in monitors],rows)
    data=read(source/'video-only.json');replay=read(source/'replay.json');duration=read(source/'manifest.json')['decoder']['container_duration_seconds']
    timeline=build_timeline(frames,data['events'],duration,receipts=replay['history'])
    timeline['authentic_per_phase_compute_measured']=False
    timeline['baseline']=baseline
    target.mkdir(parents=True,exist_ok=True);atomic_json(target/'phase-timeline.json',timeline)
    atomic_json(target/'turn-performance.json',dict(measurement='saved_evidence_prototype',authentic_per_phase_compute_measured=False,
        confirmed_game_turns=[],provisional_groups=timeline['cycles'],processing_seconds=None))
    print('Prototype only: saved evidence; no authentic per-phase compute measurements',flush=True)
    return timeline


def semantic_compare(first,second):
    """Paths differ by run; evidence IDs, pixels, predictions and state must not."""
    def normalized(value):
        if isinstance(value,list):return [normalized(v) for v in value]
        if isinstance(value,dict):return {k:normalized(v) for k,v in value.items()}
        if isinstance(value,str):
            return re.sub(r'(\.cache|reports)/battles/([^/]+)/event-driven/[^/]+/',r'\1/battles/\2/event-driven/<RUN>/',value)
        return value
    a=read(first/'observations.json');b=read(second/'observations.json')
    # Full snapshots include raw OCR/icon rankings, source IDs and pixel hashes.
    observations_equal=normalized(a)==normalized(b)
    prediction_a=read(first/'video-only.json');prediction_b=read(second/'video-only.json')
    predictions_equal=normalized(prediction_a)==normalized(prediction_b)
    replay_equal=normalized(read(first/'replay.json'))==normalized(read(second/'replay.json'))
    return dict(path_normalization='Run directory components only; no IDs, times, values or bindings removed',
        observations_equal=observations_equal,predictions_equal=predictions_equal,replay_equal=replay_equal,
        event_ids_equal=[e['event_id'] for e in prediction_a['events']]==[e['event_id'] for e in prediction_b['events']],
        final_state_equal=normalized(read(first/'replay.json')['state'])==normalized(read(second/'replay.json')['state']))


def empty_bucket():
    return dict(source_processing_seconds=0.,frame_processing_seconds=0.,decode_wait_seconds=0.,delayed_event_seconds=0.,
        frames_sampled=0,frames_inspected=0,frames_decoded=0,counters=Counter(),modules=defaultdict(lambda:dict(calls=0,inclusive_seconds=0.,exclusive_seconds=0.)),
        receipt_statuses=Counter(),event_types=Counter(),message_occurrences=set(),inspected_message_frames=0)


def aggregate(timeline,frames,operations,history,decode_log,child_seconds):
    buckets={p:empty_bucket() for p in PHASES};cycles=defaultdict(lambda:{p:empty_bucket() for p in PHASES});shared=empty_bucket()
    samplemap={s['timestamp']:s for s in timeline['samples']}
    def assigned(timestamp):
        sample=samplemap.get(timestamp)
        if sample is None:return [(shared,None)]
        result=[(buckets[sample['phase']],sample)]
        if sample['cycle_id']:result.append((cycles[sample['cycle_id']][sample['phase']],sample))
        return result
    for f in frames:
        for b,sample in assigned(f['timestamp']):
            seconds=f.get('processing_wall_seconds',0.)
            b['frame_processing_seconds']+=seconds;b['source_processing_seconds']+=seconds
            b['frames_sampled']+=1;b['frames_inspected']+=int(bool(f.get('inspected')))
            if f.get('message',{}).get('selected'):b['inspected_message_frames']+=1
    # Only disjoint causal root spans add to phase processing wall. All other
    # timers remain a module breakdown; inclusive parents are never added again.
    roots={'decode_sampling_wait','adapt_frame','state_event'}
    root_total=0.
    for op in operations:
        timestamp=(op.get('source') or {}).get('timestamp')
        for b,_ in assigned(timestamp):
            m=b['modules'][op['module']];m['calls']+=1;m['inclusive_seconds']+=op['inclusive_seconds'];m['exclusive_seconds']+=op['exclusive_seconds']
            # Counter deltas exist on one adapter layer only.
            b['counters'].update(op.get('counters',{}))
            if op['module'] in roots:
                seconds=op['inclusive_seconds'];b['source_processing_seconds']+=seconds
                b['decode_wait_seconds' if op['module']=='decode_sampling_wait' else 'delayed_event_seconds']+=seconds
        if op['module'] in roots:root_total+=op['inclusive_seconds']
    for h in history:
        e=h['event'];timestamp=e['attributes']['observation_time']
        for b,_ in assigned(timestamp):
            b['receipt_statuses'][h['application_status']]+=1;b['event_types'][e['event_type']]+=1
            occurrence=e['attributes'].get('occurrence_id')
            if occurrence and e['attributes'].get('source_region_type')=='battle_message':b['message_occurrences'].add(occurrence)
    # Actual source-decoded frame counts from FFmpeg showinfo PTS. No decoder
    # CPU duration is invented; source-video intervals may remain UNKNOWN.
    intervals=timeline['intervals'];starts=[r['start'] for r in intervals]
    decoded=0
    with decode_log.open() as stream:
        for line in stream:
            if 'showinfo@source' not in line:continue
            match=re.search(r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:([\d.]+)',line)
            if not match:continue
            t=float(match[3]);i=bisect_right(starts,t)-1;interval=intervals[i] if i>=0 else None
            phase=interval['phase'] if interval and t<interval['end'] else 'UNKNOWN'
            buckets[phase]['frames_decoded']+=1
            if interval and interval.get('cycle_id'):cycles[interval['cycle_id']][phase]['frames_decoded']+=1
            decoded+=1
    frame_total=sum(f.get('processing_wall_seconds',0.) for f in frames)
    remainder=child_seconds-frame_total-root_total
    # Shared root work includes preparation, batch ordering, post/export and
    # wrapper/logging gaps. It is measured by conservation, not shoved into a turn.
    if remainder < -.01:raise AssertionError('Overlapping processing wall partitions')
    shared['source_processing_seconds']+=max(0.,remainder)
    def serial(b,video_seconds=None):
        return {**b,'counters':dict(b['counters']),'modules':dict(b['modules']),
            'receipt_statuses':dict(b['receipt_statuses']),'event_types':dict(b['event_types']),
            'distinct_battle_messages':len(b['message_occurrences']),'message_occurrences':sorted(b['message_occurrences']),
            'video_seconds':video_seconds,
            'video_seconds_per_processing_second':video_seconds/b['source_processing_seconds'] if video_seconds is not None and b['source_processing_seconds'] else None}
    result=dict(phases={p:serial(b,timeline['phase_video_seconds'][p]) for p,b in buckets.items()},
        shared_unallocated=serial(shared),
        cycles=[dict(cycle_id=cid,turn_number=None,status='provisional_not_game_turn',phases={p:serial(b) for p,b in phase.items()}) for cid,phase in cycles.items()],
        accounting=dict(child_seconds=child_seconds,frame_consumer_wall_seconds=frame_total,disjoint_causal_root_seconds=root_total,
            shared_residual_seconds=remainder,decoded_source_frames=decoded,
            partition_sum=sum(b['source_processing_seconds'] for b in buckets.values())+shared['source_processing_seconds'],
            interpretation='Actual monotonic frame consumer wall + decoder-next waits + delayed per-row adaptation/per-event state spans. Parent inclusive timers are excluded. Shared evidence intervals and unattributable preparation/export remain shared.'))
    return result


def build(owner,run_id,baseline,evaluation_id):
    source=owner.cache('event-driven/'+run_id);verify_seal(source)
    profile=owner.cache('evaluation/'+run_id);execution=read(profile/'execution.json');assert execution['status']=='complete'
    for name,sha in execution['sealed_outputs'].items():assert digest(source/name)==sha
    for name,sha in execution['profile_outputs'].items():assert digest(profile/name)==sha
    target=owner.cache('evaluation/'+evaluation_id);target.mkdir(parents=True,exist_ok=True)
    rows=read(source/'observations.json')['observations'];prediction=read(source/'video-only.json');replay=read(source/'replay.json');manifest=read(source/'manifest.json')
    frames=[];operations=[];segments=[]
    for folder in sorted((profile/'profiler').glob('segment-*')):
        meta=read(folder/'profiler.json');segments.append(meta)
        frames+=lines(folder/'frames.jsonl')
        operations+=[dict(o,segment=folder.name) for o in lines(folder/'operations.jsonl')]
    if len(segments)!=1:raise ValueError('Resumed profiling preserved; multi-segment PTS decode accounting requires explicit review before reporting')
    frames=enrich(frames,rows);duration=manifest['decoder']['container_duration_seconds']
    timeline=build_timeline(frames,prediction['events'],duration,receipts=replay['history'],measurement='actual_profiled_acquisition')
    timeline['authentic_per_phase_compute_measured']=True
    performance=aggregate(timeline,frames,operations,replay['history'],source/'decode.log',segments[0]['child_elapsed_seconds'])
    comparison=semantic_compare(owner.cache('event-driven/'+baseline),source)
    performance.update(run_id=run_id,baseline=baseline,measurement='actual_profiled_acquisition',verified_game_turns=timeline['verified_absolute_turns'],
        complete_process_wall_seconds=execution['wall_seconds'],video_seconds=duration,video_seconds_per_process_second=duration/execution['wall_seconds'],
        peak_sampled_process_tree_rss_mib=execution['peak_process_tree_rss_mib'],profiler=segments,semantic_comparison=comparison,
        note='Cycle ordinals are not verified game-turn numbers. No cache-based estimate replaces a measured run.')
    atomic_json(target/'phase-timeline.json',timeline);atomic_json(target/'turn-performance.json',performance)
    # Candidate repeated work retains the exact causal call records for review.
    repeats=defaultdict(list)
    for op in operations:
        if op['module']=='ocr_read' and op.get('purpose')=='hud_identity_name' and op.get('raw_text'):
            repeats[(op.get('slot'),op['raw_text'])].append(op)
    candidates=[]
    for (slot,raw),calls in repeats.items():
        if len(calls)>1:candidates.append(dict(slot=slot,raw_text=raw,calls=calls,status='repeated_same_raw_label; redundancy_unproven_without_occupancy/visibility evidence'))
    command_calls=[o for o in operations if (samplemap_sample:=sample_at(timeline,(o.get('source') or {}).get('timestamp'))) and samplemap_sample['phase']=='COMMAND' and o['module'] in {'ocr_read','ocr_predict','icon_identify'}]
    atomic_json(target/'recognition-work-review.json',dict(repeated_identity_candidates=candidates,command_calls=command_calls,
        policy='No observation is disabled. Repeated labels can be needed after switches, occlusion, ambiguity or W; inspect source records before claiming avoidable work.'))
    render(owner,target,timeline,performance,command_calls)
    return timeline,performance


def render(owner,target,timeline,performance,command_calls):
    report=owner.report('evaluation/'+target.name);report.mkdir(parents=True,exist_ok=True)
    payload=dict(timeline=timeline,performance=performance,command_calls=command_calls)
    encoded=json.dumps(payload,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=ROOT/'scripts/templates/production_performance.html'
    (report/'review.html').write_text(template.read_text().replace('__DATA__',encoded))
    atomic_json(target/'report-manifest.json',dict(status='complete',inputs={p.name:digest(p) for p in [target/'phase-timeline.json',target/'turn-performance.json']},
        outputs={str(report/'review.html'):digest(report/'review.html')},sources={str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),ROOT/'scripts/production_phase_timeline.py',template]}))
    print(json.dumps(dict(report=str(report/'review.html'),phases={p:dict(video_seconds=b['video_seconds'],processing_seconds=b['source_processing_seconds'],ocr=b['counters'].get('ocr_invocations_performed',0),icons=b['counters'].get('icon_invocations_performed',0)) for p,b in performance['phases'].items()},
        cycles=len(performance['cycles']),accounting=performance['accounting'],semantic_comparison=performance['semantic_comparison']),indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',required=True);p.add_argument('--run-id',required=True);p.add_argument('--baseline',required=True);p.add_argument('--evaluation-id',required=True);p.add_argument('--prototype-only',action='store_true')
    a=p.parse_args();owner=BattleArtifacts(a.battle)
    if a.prototype_only:prototype(owner,a.baseline,owner.cache('evaluation/'+a.evaluation_id))
    else:build(owner,a.run_id,a.baseline,a.evaluation_id)


if __name__=='__main__':main()
