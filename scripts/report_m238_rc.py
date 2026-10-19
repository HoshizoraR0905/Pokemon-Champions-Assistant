"""Read-only evaluation and offline review of the sealed M2.3.8 Battle 5 RC.

No acquisition, runtime tuning, annotation imports into state, or baseline replay
under new rules. A separate saved-event replay captures prefix slots and must
exactly reproduce every original receipt and state hash.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.validate_m238_rc import OWNER,RUN,PIPE,META,REPORT,SLOTS,read,metrics,brief,links
from recognition.event_report import verify_seal
from recognition.video_sampling import atomic_json
from recognition.fast_video import digest
from tracking.battle_state import from_dict
from tracking.state_engine import StateEngine,EventRecord
from scripts.replay_m238t import slot_snapshot,intervals,frozen_slot_timeline
from tracking.evidence_projection import source_times


def forbidden(*args,**kwargs):raise AssertionError('RC reporting cannot acquire recognition/video evidence')


def timeline():
    seal=verify_seal(PIPE)
    target=META/'timeline-v1'
    if (target/'complete.json').exists():
        done=read(target/'complete.json')
        assert done['seal']==seal['files'] and done['runner_sha256']==digest(Path(__file__))
        assert digest(target/'slots.json')==done['slots_sha256']
        print('Completed saved-event timeline reused');return
    if target.exists():raise FileExistsError('Partial timeline exists: inspect it and preserve before choosing another version')
    target.mkdir();atomic_json(target/'manifest.json',dict(status='running',seal=seal['files'],runner_sha256=digest(Path(__file__)),recognition_calls=0))
    original=read(PIPE/'replay.json');engine=StateEngine(from_dict(original['initial_state']))
    engine.history=[EventRecord(deepcopy(h['event']),h['delivery_index'],deepcopy(h['ordering'])) for h in original['history']]
    changes=[dict(timestamp=0,event_id=None,slots=slot_snapshot(engine.state,0))];last=None;violations=[];slot_changes=[];began=time.monotonic()
    def capture(record,state):
        nonlocal last
        t=record.event['attributes']['observation_time'];slots=slot_snapshot(state,t)
        previous=changes[-1]['slots']
        # These are actual prefix mutations, not retrospective party guesses.
        changed=[k for k in SLOTS if previous[k].get('instance_id')!=slots[k].get('instance_id')]
        if changed:slot_changes.append(dict(timestamp=t,event_id=record.event['event_id'],kind=record.event['event_type'],
            slots={k:dict(before=previous[k],after=slots[k]) for k in changed},bindings=deepcopy(record.bindings)))
        for side,team in state.sides.items():
            if len(set(team.active_slots.values()))!=len(team.active_slots):violations.append(dict(event_id=record.event['event_id'],issue='duplicate_active_instance',side=side))
        event=record.bindings.get('resolved_event',record.event)
        if any(v>t for v in source_times(event['attributes'].get('binding_sources',[]))):violations.append(dict(event_id=event['event_id'],issue='future_binding_source'))
        dep=record.bindings.get('departure')
        if dep:
            key=event['side']+':'+str(dep['slot']);pid=record.bindings.get('actor',{}).get('pokemon_instance_id')
            if previous.get(key,{}).get('instance_id')!=pid or slots.get(key,{}).get('instance_id'):
                violations.append(dict(event_id=event['event_id'],issue='departure_slot_mismatch'))
        sig=json.dumps({k:{a:v for a,v in x.items() if a!='evidence'} for k,x in slots.items()},sort_keys=True)
        if sig!=last:changes.append(dict(timestamp=t,event_id=record.event['event_id'],slots=slots));last=sig
        if record.delivery_index%100==0:
            atomic_json(target/'progress.json',dict(completed=record.delivery_index,total=len(engine.history),video_timestamp=t))
            atomic_json(target/'partial-slots.json',changes)
            print('Saved-event timeline',record.delivery_index,'/',len(engine.history),flush=True)
    with ExitStack() as stack:
        for name in ['recognition.fast_video.CachedOCR.read','recognition.fast_video.CachedOCR.predict','recognition.fast_video.CachedIcons.identify','recognition.fast_video.decoded_frames','cv2.imread','cv2.VideoCapture']:stack.enter_context(patch(name,forbidden))
        engine.replay(snapshot_callback=capture)
    result=engine.to_dict()
    receipt_differences=[h['event']['event_id'] for h,old in zip(result['history'],original['history'])
        if (h['application_status'],h['reason'],h['state_hash'])!=(old['application_status'],old['reason'],old['state_hash'])]
    assert not receipt_differences and result['state_hash']==original['state_hash'],receipt_differences
    atomic_json(target/'slots.json',changes);atomic_json(target/'slot-mutations.json',slot_changes)
    atomic_json(target/'complete.json',dict(status='complete',seal=seal['files'],runner_sha256=digest(Path(__file__)),slots_sha256=digest(target/'slots.json'),
        slot_mutations_sha256=digest(target/'slot-mutations.json'),state_hash_matches=True,all_receipts_and_prefix_state_hashes_match=True,
        consistency_violations=violations,wall_seconds=time.monotonic()-began,recognition_calls=0))
    print(json.dumps(read(target/'complete.json'),indent=2))


def normalized(s):return re.sub(r'\s+','',s or '').translate(str.maketrans({'!':'！',',':'，','。':''})).casefold()


def align(history,baseline):
    """Display-only correspondence, never used as event/identity truth."""
    out=[]
    for h in history:
        e=h['event'];t=e['attributes']['observation_time']
        candidates=[old for old in baseline if old['event']['event_type']==e['event_type']
            and abs(old['event']['attributes'].get('observation_time',-100)-t)<=1.1
            and (normalized(old['event']['original_text'])==normalized(e['original_text'])
                 or any(p['source_id']==q['source_id'] for p in old['event']['evidence'] for q in e['evidence']))]
        out.append(dict(after=brief(h),before=[brief(x) for x in candidates],
            correspondence='same type plus same source or normalized literal text within 1.1s; display only' if candidates else 'no comparable sparse-baseline receipt'))
    return out


def recognition_comparison(rows):
    """Compare only exactly matched original source timestamps; no fuzzy accuracy."""
    source=OWNER.cache('m236/development-observations.json');old=read(source)['observations']+read(OWNER.cache('m236/held_out-observations.json'))['observations']
    by_source={r['source_id']:r for r in rows};pairs=[]
    for r in old:
        new=by_source.get(r['source_id'])
        if not new:continue
        pairs.append(dict(timestamp=r['timestamp'],source_id=r['source_id'],png_sha256_equal=r['sha256']==new['sha256'],
            old_message=(r.get('message') or {}).get('raw_text'),new_message=(new.get('message') or {}).get('raw_text'),
            old_hud=[dict(slot=p['slot'],raw=(p.get('species') or {}).get('raw_text'),icon=(p.get('icon') or {}).get('species_id')) for p in r.get('snapshot',{}).get('pokemon',[])],
            new_hud=[dict(slot=p['slot'],raw=(p.get('species') or {}).get('raw_text'),icon=(p.get('icon') or {}).get('species_id')) for p in new.get('snapshot',{}).get('pokemon',[])]))
    return dict(source=str(source.relative_to(ROOT)),exact_source_pairs=len(pairs),pairs=pairs,
        limitations='Only exact source_id pairs are compared. Changed text may reflect routing/selection/region differences; this does not isolate OCR-model accuracy. Icon differences are observations, not adjudicated accuracy.')


def reference_review(rows,history):
    """Evaluation only, called strictly after verifying the video-only seal."""
    cases=[]
    for path,key in [('tests/fixtures/battles/m235_review.json','examples'),('tests/fixtures/battles/m236u_ui_review.json','cases')]:
        fixture=read(ROOT/path)
        for label in fixture[key]:
            t=label['timestamp'];near=min(rows,key=lambda r:abs(r['timestamp']-t));offset=near['timestamp']-t
            expected=(label.get('expected') or {}).get('message');actual=(near.get('message') or {}).get('raw_text','')
            cases.append(dict(reference=path,timestamp=t,reviewer=label.get('reviewer',fixture.get('review_method',fixture.get('method'))),
                expected=deepcopy(label.get('expected', {k:v for k,v in label.items() if k in {'hud','move_message','popup','panel','current_occupancy','ambiguity'}})),
                expected_message=expected,nearest_frame_timestamp=near['timestamp'],offset_seconds=offset,
                comparable_time=abs(offset)<=.27,raw_message=actual,
                exact_normalized_transcription=(normalized(expected)==normalized(actual)) if expected is not None and abs(offset)<=.27 else None,
                nearby_receipts=[brief(h) for h in history if abs(h['event']['attributes']['observation_time']-t)<=1.1 and h['event']['event_type']!='hud_observation'],
                evidence=[dict(timestamp=near['timestamp'],image=os.path.relpath(ROOT/near['image'],REPORT.parent)),dict(timestamp=t,image=os.path.relpath(ROOT/label['image'],REPORT.parent))]))
    return dict(cases=cases,reference_frames=len(cases),independent_human_accuracy=None,
        limitations=['Small purposive, historically exposed agent-reviewed fixtures, not exhaustive human ground truth.',
          'Nearest-frame comparisons within 0.27s are time-near, not proof of identical video pixels or message phase.',
          'Browser-test annotation exports contain synthetic feedback; inventoried but not scored as human truth.',
          'No labels, historical Battle Log rows or corrections are runtime inputs; predictions remain sealed.'])


def consistency(replay):
    violations=[];bound=0
    for h in replay['history']:
        e=h['bindings'].get('resolved_event',h['event']);t=e['attributes']['observation_time'];pid=h['bindings'].get('actor',{}).get('pokemon_instance_id')
        if any(p.get('details',{}).get('timestamp',t)>t for p in e['evidence']):violations.append(dict(event_id=e['event_id'],issue='future_event_evidence'))
        if pid and h['application_status'] in {'applied_candidate','applied_partial','applied_confirmed','recorded_observation'}:
            bound+=1;p=replay['state']['pokemon'].get(pid)
            if not p or p['side_id']!=e['side']:violations.append(dict(event_id=e['event_id'],issue='bound_side_mismatch'))
            if p and e.get('actor',{}):
                sid=e['actor'].get('species_id')
                if sid and p['species']['value'].get('species_id')!=sid:violations.append(dict(event_id=e['event_id'],issue='bound_species_mismatch'))
    return dict(bound_admissions_checked=bound,violations=violations,identity_conflicts=deepcopy(replay['state']['conflicts']),
        unresolved_occupancy_contradictions=replay['state']['knowledge'].get('occupancy_uncertainty',{}),independent_false_admission_rate=None)


def time_log(path):
    text=path.read_text();real=re.search(r'([\d.]+) real\s+([\d.]+) user\s+([\d.]+) sys',text);rss=re.search(r'(\d+)\s+maximum resident set size',text)
    return dict(log=str(path.relative_to(ROOT)),real_seconds=float(real[1]) if real else None,
        user_seconds=float(real[2]) if real else None,sys_seconds=float(real[3]) if real else None,
        peak_resident_bytes=int(rss[1]) if rss else None,
        memory_scope='Darwin /usr/bin/time -l maximum resident set size; not a measured simultaneous aggregate process-tree peak')


def build():
    seal=verify_seal(PIPE);manifest=read(PIPE/'manifest.json')
    assert manifest['status']=='complete'
    complete=read(META/'timeline-v1/complete.json');assert complete['seal']==seal['files']
    outputs=[Path(str(REPORT)+ext) for ext in ('.json','.html','.md')]
    if any(p.exists() for p in outputs):raise FileExistsError('Preserve existing reports; use a new report version')
    new=read(PIPE/'replay.json');old=read(OWNER.cache('m236u/regression-replay.json'))['engine'];prefix=read(OWNER.cache('event-driven/m238-trainer-opening-v3/prefix.json'))
    rows=read(PIPE/'observations.json')['observations'];end=manifest['decoder']['container_duration_seconds']
    events=align(new['history'],old['history']);baseline_events=[brief(h) for h in old['history']]
    env=read(META/'preservation.json')['environment'];measures=[time_log(META/'process-time.log'),time_log(META/'process-time-resume-01.log')]
    data=dict(schema='m238-release-candidate-v1',battle_id=OWNER.battle_id,
        status='diagnostic validation; independent semantic acceptance not established',
        baseline_kind='Frozen sparse M2.3.6-U regression replay; unequal coverage, not a previous full M2.3.8 Battle 5 run',
        counts=dict(baseline=metrics(old['history']),opening_baseline=metrics(prefix['history']),current=metrics(new['history'])),
        performance=dict(kind='resumed full-recording production pipeline; not cold benchmark or cached-only replay',
            cold_end_to_end_seconds=None,active_pipeline_seconds=manifest['active_seconds'],segments=measures,
            recognition_invocations=manifest['counts'],environment=env,video_duration_seconds=end,
            note='Initial attempt was interrupted on request. Resume restores observations and exact caches; scheduler/region reuse is normal within-run caching. Resumed stage timing is not cold-pipeline performance. Timeline replay timing is separate.'),
        timeline=intervals(read(META/'timeline-v1/slots.json'),end),before_timeline=frozen_slot_timeline(old['history'],end),
        events=events,baseline_events=baseline_events,
        transitions=[x for x in events if x['after']['kind'] in {'send_out','switch_out','faint','position_change'}],
        deferred=[x for x in events if x['after']['status'] in {'deferred','rejected'}],
        slot_mutations=read(META/'timeline-v1/slot-mutations.json'),
        entry_episodes=new['state']['knowledge'].get('active_entry_episodes',[]),
        event_evidence={h['event']['event_id']:links(h['event'],REPORT.parent) for h in new['history']+old['history']},
        frames=[dict(timestamp=r['timestamp'],image=os.path.relpath(ROOT/r['image'],REPORT.parent),source_id=r['source_id'],raw_message=(r.get('message') or {}).get('raw_text'),ui=r['ui']['phase']) for r in rows],
        consistency=consistency(new),prefix_validation=complete,recognition_comparison=recognition_comparison(rows),
        reference_review=reference_review(rows,new['history']),
        trainer_observations=[dict(timestamp=r['timestamp'],observations=r['trainer_observations'],image=os.path.relpath(ROOT/r['image'],REPORT.parent)) for r in rows if r.get('trainer_observations')],
        preview_rows=read(PIPE/'observations.json')['roster'],tests=read(META/'tests.json') if (META/'tests.json').exists() else None,
        git_review=read(META/'git-review.json') if (META/'git-review.json').exists() else None,
        preservation=read(META/'preservation-check.json') if (META/'preservation-check.json').exists() else None,
        limits=['Complete pipeline execution is distinct from independently verified semantic coverage.',
          'Battle 5 has historical development/slot-order exposure; it is not pristine held-out generalization.',
          'Sparse baseline counts cannot be directly interpreted as a recognition improvement or regression rate.',
          'HUD absence does not vacate a slot; supported departures and replacements remain separate events. Contradictions and gaps stay uncertain.',
          'Entry episodes are not automatically distinct party members; repeated species do not establish biological identity.',
          'All candidate/partial receipts retain their limits; revealed move membership is not an equipped slot or verified move effect.',
          'Independent exhaustive Battle 5 log/transition accuracy and false-admission rates remain unmeasured.'])
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    with outputs[0].open('x') as f:json.dump(data,f,ensure_ascii=False,indent=2)
    template=(ROOT/'scripts/templates/m238rc_review.html').read_text()
    with outputs[1].open('x') as f:f.write(template.replace('__DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')))
    lines=['# M2.3.8 release-candidate validation — Battle 5','',
        '[Offline review](M2.3.8-release-candidate-v1.html) · [Structured report](M2.3.8-release-candidate-v1.json)','',
        'The full production pipeline ran on Battle 5 with the unchanged M2.3.8-U implementation. It resumed a user-interrupted cold attempt; **this is not a completed cold benchmark**. Recognition was performed, not merely replayed. Frozen predictions and references were not runtime inputs.','',
        '## Coverage and denominators','',data['baseline_kind']+'. The newer trainer-opening v3 prefix is a second, opening-only comparator. Battle 5 has historical development exposure; automated consistency does not establish independent accuracy.','',
        '```json',json.dumps(data['counts'],indent=2),'```','',
        '## Performance and environment','', '```json',json.dumps(data['performance'],indent=2),'```','',
        '## State and identity checks','', '```json',json.dumps(data['consistency'],ensure_ascii=False,indent=2),'```','',
        'The extra timeline uses saved events only. Every receipt, reason and prefix state hash must match the sealed production replay; it is not recognition or cold-pipeline timing.','',
        '```json',json.dumps(complete,indent=2),'```','',
        '## Recognition and reference limits','',
        f"Exactly paired old/new source observations: {data['recognition_comparison']['exact_source_pairs']}. Differences are routing/reading observations, not isolated model accuracy gains. Full paired details are in JSON and HTML.",'',
        f"Available curated reference frames: {data['reference_review']['reference_frames']}. These are small, historically exposed agent reviews. Browser-test annotations contain synthetic edits and are not independent human truth. No exhaustive independent transition denominator is available.",'',
        '## Transitions','', '| Time | Original game text | Type | Side | Receipt | Cause |','|---|---|---|---|---|---|']
    for x in data['transitions']:
        r=x['after'];raw=r['raw'].replace('\n',' ').replace('|','\\|');lines.append(f"| {r['timestamp']:.3f} | {raw} | {r['kind']} | {r['side']} | {r['status']} | {r['reason'] or '—'} |")
    lines+=['','## Deferred causes','', '```json',json.dumps(data['counts']['current']['deferred_causes'],indent=2),'```','',
        '## Tests, Git and preservation','', '```json',json.dumps(dict(tests=data['tests'],git_review=data['git_review'],preservation=data['preservation']),ensure_ascii=False,indent=2),'```','',
        'Browser verification, scoped manual evidence review, final blockers, exact commands and proposed explicit commit paths are recorded in the completion report. No commit or push is authorized by this validation.','',
        '## Limits','']+['- '+x for x in data['limits']]
    with outputs[2].open('x') as f:f.write('\n'.join(lines)+'\n')
    print(json.dumps(data['counts'],indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',required=True,choices=['timeline','report']);args=p.parse_args()
    timeline() if args.stage=='timeline' else build()
