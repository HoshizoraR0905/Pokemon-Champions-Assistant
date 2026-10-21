"""M2.4 measured contiguous phase segments and offline comparison; no inference."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import html
import json
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json
from recognition.event_report import verify_seal
from recognition.fast_video import digest
from scripts.production_phase_timeline import build_timeline
from scripts.report_production_profile import read,lines,enrich,semantic_compare


def timeline_for(frames, events, duration, history):
    timeline=build_timeline(frames,events,duration,receipts=history,measurement='actual_monotonic_acquisition')
    for s in timeline['samples']:
        old=s['phase'];s['subtype']=None
        if old=='FORCED_REPLACEMENT':
            if s['ui_phase'] in {'pokemon_selection','switch_selection'} and s['ui_confidence']>=.9:
                s['phase']='COMMAND_TIME'
                s['subtype']='forced_replacement' if any(r['side']=='self' and r['start']<=s['timestamp']<r['end'] for r in timeline['forced_replacement_candidates']) else None
                s['basis'].append('observed_selection_input_ui')
            else:s['phase']='UNKNOWN';s['basis'].append('replacement_input_not_observed')
        else:s['phase']={'COMMAND':'COMMAND_TIME','TURN_EXECUTION':'BATTLE_TIME','TEAM_PREVIEW':'PRE_BATTLE'}.get(old,old)
        if old=='TEAM_PREVIEW':s['subtype']='team_preview'
        if s['phase']=='COMMAND_TIME' and s['ui_phase'] in {'pokemon_selection','switch_selection'} and s['ui_confidence']>=.9 and any(r['side']=='self' and r['start']<=s['timestamp']<r['end'] for r in timeline['forced_replacement_candidates']):
            s['subtype']='forced_replacement'
            s['basis'].append('observed_selection_input_with_faint_to_arrival_context')
    samples=timeline['samples'];intervals=[]
    if samples and samples[0]['timestamp']>0:
        intervals.append(dict(start=0.,end=samples[0]['timestamp'],phase='UNKNOWN',subtype=None,basis=['unobserved_leading_interval'],certainty='unknown'))
    for a,b in zip(samples,samples[1:]):
        same=(a['phase'],a['subtype'])==(b['phase'],b['subtype']) and a['phase']!='UNKNOWN'
        intervals.append(dict(start=a['timestamp'],end=b['timestamp'],phase=a['phase'] if same else 'UNKNOWN',
            subtype=a['subtype'] if same else None,certainty='observed_sample_agreement' if same else 'uncertain_boundary',
            basis=[a['basis'],b['basis']],boundary_evidence=[deepcopy(a),deepcopy(b)],
            boundary_uncertainty_seconds=b['timestamp']-a['timestamp'] if not same else None,
            candidates=None if same else [a['phase'],b['phase']],turn_number=a['turn_number'] if a['turn_number']==b['turn_number'] else None))
    tail=samples[-1]['timestamp'] if samples else 0.
    if tail<duration:intervals.append(dict(start=tail,end=duration,phase='UNKNOWN',subtype=None,basis=['unobserved_tail'],certainty='unknown'))
    segments=[]
    for interval in intervals:
        if segments and (segments[-1]['phase'],segments[-1]['subtype'])==(interval['phase'],interval['subtype']):
            segments[-1]['end']=interval['end'];segments[-1]['boundary_evidence'].append(interval)
            if segments[-1]['turn_number']!=interval.get('turn_number'):segments[-1]['turn_number']=None
        else:segments.append(dict(index=len(segments)+1,start=interval['start'],end=interval['end'],phase=interval['phase'],
            subtype=interval['subtype'],turn_number=interval.get('turn_number'),boundary_evidence=[interval]))
    for s in segments:s['video_duration_seconds']=s['end']-s['start']
    timeline.update(schema_version=2,segments=segments,intervals=intervals,
        certainty_video_seconds={c:sum(i['end']-i['start'] for i in intervals if i['certainty']==c) for c in {i['certainty'] for i in intervals}},
        phase_video_seconds=dict(Counter({p:sum(s['video_duration_seconds'] for s in segments if s['phase']==p) for p in {s['phase'] for s in segments}})))
    return timeline


def measure_segments(timeline, frames, operations, events, child_seconds, decode_log=None):
    segments=deepcopy(timeline['segments'])
    shared=dict(processing_wall_seconds=0.,modules={})
    for s in segments:s.update(processing_wall_seconds=0.,decoded_frames=0,sampled_frames=0,inspected_frames=0,event_count=0,modules={},counters={})
    def bucket(timestamp):
        if timestamp is None:return shared
        return next((s for s in segments if s['start']<=timestamp<s['end']),shared)
    for f in frames:
        b=bucket(f['timestamp']);b['processing_wall_seconds']+=f['processing_wall_seconds']
        if b is not shared:
            b['sampled_frames']+=1;b['inspected_frames']+=int(bool(f.get('inspected')))
    # These are disjoint from frame consumer spans. Inclusive nested module
    # breakdown is diagnostic only, never added to processing wall partitions.
    roots={'decode_sampling_wait','adapt_frame','state_event'}
    for op in operations:
        b=bucket((op.get('source') or {}).get('timestamp'))
        module=b['modules'].setdefault(op['module'],dict(calls=0,inclusive_seconds=0.,exclusive_seconds=0.))
        module['calls']+=1;module['inclusive_seconds']+=op['inclusive_seconds'];module['exclusive_seconds']+=op['exclusive_seconds']
        if b is not shared:
            for k,v in op.get('counters',{}).items():b['counters'][k]=b['counters'].get(k,0)+v
        if op['module'] in roots and op.get('purpose') != 'development_identity_verification':
            b['processing_wall_seconds']+=op['inclusive_seconds']
    shared['initialization_triggers']=[]
    frame_times={f['timestamp'] for f in frames}
    for op in operations:
        timestamp=(op.get('source') or {}).get('timestamp')
        if op['module'] in {'ocr_model_load','icon_model_load'} and timestamp in frame_times:
            b=bucket(timestamp)
            if b is not shared:
                b['processing_wall_seconds']-=op['inclusive_seconds']
                shared['processing_wall_seconds']+=op['inclusive_seconds']
                shared['initialization_triggers'].append(dict(module=op['module'],source=op['source'],seconds=op['inclusive_seconds']))
    allocated=sum(s['processing_wall_seconds'] for s in segments)+shared['processing_wall_seconds']
    residual=child_seconds-allocated
    if residual < -.01:raise ValueError('Overlapping wall-time partitions')
    shared['processing_wall_seconds']+=max(0.,residual)
    for e in events:
        b=bucket(e['attributes']['observation_time'])
        if b is not shared:b['event_count']+=1
    if decode_log:
        with decode_log.open() as stream:
            for line in stream:
                if 'showinfo@source' not in line:continue
                match=re.search(r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:([\d.]+)',line)
                if match:
                    b=bucket(float(match[3]))
                    if b is not shared:b['decoded_frames']+=1
    for s in segments:
        s['real_time_processing_ratio']=s['processing_wall_seconds']/s['video_duration_seconds'] if s['video_duration_seconds'] else None
        s['ocr_inference_count']=s['modules'].get('ocr_inference',{}).get('calls',0)
        s['ocr_inference_seconds']=s['modules'].get('ocr_inference',{}).get('inclusive_seconds',0.)
        s['icon_matching_count']=sum(s['modules'].get(k,{}).get('calls',0) for k in ('icon_default_inference','icon_silhouette_inference'))
        s['icon_matching_seconds']=sum(s['modules'].get(k,{}).get('inclusive_seconds',0.) for k in ('icon_default_inference','icon_silhouette_inference'))
        s['cache_hits']=sum(v for k,v in s['counters'].items() if 'hit' in k or 'reused' in k or 'reuses' in k)
        s['cache_misses']=s['counters'].get('ocr_invocations_performed',0)+s['counters'].get('icon_invocations_performed',0)
    return dict(schema_version=1,segments=segments,shared_unallocated=shared,child_wall_seconds=child_seconds,
        partition_sum=sum(s['processing_wall_seconds'] for s in segments)+shared['processing_wall_seconds'],
        timing_policy='Frame consumer wall + disjoint decode waits/adaptation/state-event spans; nested inclusive modules are never added. Main thread only; FFmpeg CPU not measured. Ratio = wall/video.',
        non_battle_summary={p:dict(video_seconds=sum(s['video_duration_seconds'] for s in segments if s['phase']==p),
            processing_wall_seconds=sum(s['processing_wall_seconds'] for s in segments if s['phase']==p)) for p in ('PRE_BATTLE','POST_BATTLE','UNKNOWN')})


def report(owner,run_id):
    source=owner.cache('event-driven/'+run_id);measurement=owner.cache('evaluation/'+run_id)
    verify_seal(source)
    execution=read(measurement/'execution.json');manifest=read(source/'manifest.json')
    for name,sha in execution['sealed_outputs'].items():
        if digest(source/name)!=sha:raise ValueError('Measured production seal changed: '+name)
    for name,sha in execution['profile_outputs'].items():
        if digest(measurement/name)!=sha:raise ValueError('Measured profile changed: '+name)
    if execution['status']!='complete':raise ValueError('Run incomplete')
    profiles=sorted((measurement/'profiler').glob('segment-*'))
    if len(profiles)!=1:raise ValueError('Resumed timing requires explicit separate acquisition-segment reporting')
    folder=profiles[0];frames=enrich(lines(folder/'frames.jsonl'),read(source/'observations.json')['observations'])
    events=read(source/'video-only.json')['events'];history=read(source/'replay.json')['history'];ops=lines(folder/'operations.jsonl')
    timeline=timeline_for(frames,events,manifest['decoder']['container_duration_seconds'],history)
    performance=measure_segments(timeline,frames,ops,events,read(folder/'profiler.json')['child_elapsed_seconds'],source/'decode.log')
    performance['process_startup_monitoring_unallocated_seconds']=execution['wall_seconds']-performance['child_wall_seconds']
    target=owner.report('evaluation/'+run_id+'-m24');target.mkdir(parents=True,exist_ok=True)
    atomic_json(target/'phase-timeline.json',timeline);atomic_json(target/'segment-performance.json',performance)
    verification=source/'identity-verification.json'
    if verification.exists():atomic_json(target/'identity-verification.json',read(verification))
    headings='<tr><th>Segment</th><th>Phase / subtype</th><th>Video</th><th>Wall s</th><th>Wall/video</th><th>OCR</th><th>Icon matches</th><th>Events</th><th>Breakdown</th></tr>'
    rows=[]
    for s in performance['segments']:
        modules=s['modules'];ocr=modules.get('ocr_inference',{});icon=dict(calls=s['icon_matching_count'],inclusive_seconds=s['icon_matching_seconds'])
        breakdown=html.escape(json.dumps(dict(modules=modules,counters=s['counters'],decoded_frames=s['decoded_frames'],sampled_frames=s['sampled_frames'],inspected_frames=s['inspected_frames'],boundary_evidence=s['boundary_evidence']),ensure_ascii=False,indent=2))
        rows.append(f"<tr><td>{s['index']}</td><td>{s['phase']} {s['subtype'] or ''}</td><td>{s['start']:.2f}–{s['end']:.2f}</td><td>{s['processing_wall_seconds']:.3f}</td><td>{s['real_time_processing_ratio']:.3f}</td><td>{ocr.get('calls',0)} / {ocr.get('inclusive_seconds',0):.3f}s</td><td>{icon.get('calls',0)} / {icon.get('inclusive_seconds',0):.3f}s</td><td>{s['event_count']}</td><td><details><summary>Module timings / provenance</summary><pre>{breakdown}</pre></details></td></tr>")
    bars=''.join(f'<span title="{s["phase"]} {s["start"]:.2f}–{s["end"]:.2f}; {s["processing_wall_seconds"]:.3f}s wall" style="display:inline-block;width:{100*s["video_duration_seconds"]/timeline["video_duration_seconds"]}%;height:{8+min(92,50*s["real_time_processing_ratio"])}px;vertical-align:bottom;background:{ {"COMMAND_TIME":"#57c9a4","BATTLE_TIME":"#7a9fee","PRE_BATTLE":"#cca265","POST_BATTLE":"#bf87cb"}.get(s["phase"],"#777")}"></span>' for s in performance['segments'])
    page=f'<!doctype html><meta charset="utf-8"><title>M2.4 phase costs</title><style>body{{font:15px system-ui;margin:32px;background:#101827;color:#eee}}table{{border-collapse:collapse}}td,th{{padding:8px;border-bottom:1px solid #445}}pre{{white-space:pre-wrap}}</style><h1>{html.escape(run_id)}</h1><p>Green COMMAND_TIME; blue BATTLE_TIME; tan PRE_BATTLE; purple POST_BATTLE; grey UNKNOWN. Bar height scales with measured wall/video cost (capped at 100px); hover for source bounds and exact wall cost. Sample boundaries are uncertain.</p><div style="white-space:nowrap">{bars}</div><table>{headings}{"".join(rows)}</table><h2>Non-battle and shared costs</h2><pre>{html.escape(json.dumps(dict(non_battle=performance["non_battle_summary"],shared_wall_seconds=performance["shared_unallocated"]["processing_wall_seconds"]),indent=2))}</pre><p>Nested module timers are diagnostic; processing wall partitions count each interval once. See adjacent JSON for provenance and full module costs.</p>'
    if verification.exists():
        page+='<h2>Independent entry verification</h2><table><tr><th>Arrival</th><th>Side / slot</th><th>Message prediction</th><th>First HUD</th><th>Outcome</th></tr>'
        for entry in read(verification)['entries']:
            attempt=next(iter(entry['attempts']),{})
            page+=f"<tr><td>{entry['timestamp']:.3f}</td><td>{entry['side']} / {entry['slot']}</td><td>{html.escape(entry['text'])}</td><td>{html.escape(attempt.get('species',{}).get('raw_text','not observed'))}</td><td>{entry['outcome']}</td></tr>"
        page+='</table>'
    (target/'timeline.html').write_text(page)
    totals=Counter();identity_calls=Counter()
    for op in ops:
        if op['module'] in {'ocr_inference','icon_identify'}:totals[op['module']+'_seconds']+=op['inclusive_seconds']
        if op['purpose']=='development_identity_verification' and op['module'] in {'ocr_inference','icon_identify'}:
            identity_calls[op['module']+'_calls']+=1
            identity_calls[op['module']+'_seconds']+=op['inclusive_seconds']
    prediction=[r for r in history if r['event']['event_type']=='send_out']
    episodes=read(source/'replay.json')['state']['knowledge'].get('active_entry_episodes',[])
    summary=dict(run_id=run_id,identity_mode=manifest['identity']['identity_mode'],wall_seconds=execution['wall_seconds'],
        peak_rss_mib=execution['peak_process_tree_rss_mib'],profiled_child_wall_seconds=performance['child_wall_seconds'],parent_envelope_extra_seconds=execution['wall_seconds']-performance['child_wall_seconds'],counts=manifest['counts'],model_seconds=dict(ocr_inference_seconds=manifest['counts'].get('ocr_seconds',0.),icon_inference_seconds=manifest['counts'].get('icon_seconds',0.)),adapter_and_inference_spans=dict(totals),hud_identity_work=dict(name_ocr_read_calls=manifest['counts'].get('verification_hud_name_reads',0),icon_adapter_calls=manifest['counts'].get('verification_hud_icon_reads',0),ocr_inference_calls=identity_calls.get('ocr_inference_calls',0),ocr_inference_seconds=identity_calls.get('ocr_inference_seconds',0.),icon_adapter_seconds=identity_calls.get('icon_identify_seconds',0.)),
        message_species_coverage=dict(denominator='automatically emitted send-out members; not independent recall',total=len(prediction),identified=sum(bool(ep.get('species_id')) for ep in episodes if ep.get('start_kind')=='send_out')),
        application_statuses=dict(Counter(r['application_status'] for r in history)),deferred_reasons=dict(Counter(r['reason'] for r in history if r['application_status']=='deferred')),
        verification_outcomes=dict(Counter(e['outcome'] for e in read(verification)['entries'])) if verification.exists() else {},
        phase_wall_seconds={p:sum(s['processing_wall_seconds'] for s in performance['segments'] if s['phase']==p) for p in ('COMMAND_TIME','BATTLE_TIME','PRE_BATTLE','POST_BATTLE','UNKNOWN')},
        cache_conditions=execution['caches'])
    atomic_json(target/'summary.json',summary)
    return summary,target


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',required=True);p.add_argument('--lightweight',required=True);p.add_argument('--development',required=True)
    a=p.parse_args();owner=BattleArtifacts(a.battle)
    light,target=report(owner,a.lightweight);dev,_=report(owner,a.development)
    comparison=semantic_compare(owner.cache('event-driven/'+a.lightweight),owner.cache('event-driven/'+a.development))
    def replay_payload(value):
        if isinstance(value,dict):return {k:replay_payload(v) for k,v in value.items() if k!='state_hash'}
        if isinstance(value,list):return [replay_payload(v) for v in value]
        if isinstance(value,str):return re.sub(r'(\.cache|reports)/battles/([^/]+)/event-driven/[^/]+/',r'\1/battles/\2/event-driven/<RUN>/',value)
        return value
    comparison['structured_replay_equal_excluding_path_dependent_hashes']=replay_payload(read(owner.cache('event-driven/'+a.lightweight+'/replay.json')))==replay_payload(read(owner.cache('event-driven/'+a.development+'/replay.json')))
    comparison['hash_note']='Per-step state hashes retain original run-specific evidence paths. Structured replay comparison excludes only these opaque hashes and normalizes run directories; raw comparisons are retained above.'

    light_sources=read(owner.cache('evaluation/'+a.lightweight+'/execution.json'))['identity']['sources']
    dev_sources=read(owner.cache('evaluation/'+a.development+'/execution.json'))['identity']['sources']
    changed_sources=[k for k in light_sources.keys()|dev_sources.keys() if light_sources.get(k)!=dev_sources.get(k)]
    result=dict(lightweight=light,development=dev,semantic_comparison=comparison,source_differences=changed_sources,
        measured_wall_difference_seconds=dev['wall_seconds']-light['wall_seconds'],measured_child_wall_difference_seconds=dev['profiled_child_wall_seconds']-light['profiled_child_wall_seconds'],
        limits='Sequential fresh process/crop caches; immutable model assets shared. OS filesystem cache uncontrolled. One pair, not repeated statistically controlled trials. Profiling adds overhead. Parent envelope includes an exit-poll tail of up to five seconds per run; child monotonic wall is reported separately.')
    atomic_json(target/'mode-comparison.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
