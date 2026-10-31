"""Build an offline, English evaluation of a frozen battle replay.

This generic read-only report command never decodes video or invokes models.
A separate saved-event replay validates every original receipt/hash and records
four-slot prefix state. Review notes are evidence annotations, never state input.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json
from recognition.fast_video import digest
from tracking.state_engine import StateEngine,EventRecord
from tracking.battle_state import from_dict
from tracking.active_continuity import current_episode
SLOTS=('self:left','self:right','opponent:left','opponent:right')


def read(p):return json.loads(p.read_text())


def review_image(owner, report, value):
    """Keep review screenshots inside its static root; never rewrite source PNGs."""
    if not value:return None
    source=(owner.root/value).resolve()
    assert (source.is_relative_to(owner.cache_dir.resolve())
            or source.is_relative_to(owner.report_dir.resolve())
            or source.is_relative_to(owner.root/'tests/fixtures'))
    assets=report/'assets';assets.mkdir(exist_ok=True)
    destination=assets/(digest(source)+'.png')
    if not destination.exists():
        try:os.link(source,destination)
        except OSError:shutil.copyfile(source,destination)
    return 'assets/'+destination.name


def refresh_review_images(owner, evaluation_id):
    """Refresh only presentation from existing saved DATA, preserving annotations."""
    report=owner.report('evaluation/'+evaluation_id);html=report/'review.html'
    source=html.read_text()
    data=json.loads(source.split('<script>const DATA=',1)[1].split(';\nconst $',1)[0])
    cache={}
    def local(value):
        if value not in cache:
            path=(report/value).resolve()
            cache[value]=review_image(owner,report,path)
        return cache[value]
    for frame in data['frames']:
        if frame.get('image'):frame['image']=local(frame['image'])
    for event in data['events']:
        for evidence in event['images']:
            if evidence.get('image'):evidence['image']=local(evidence['image'])
    for finding in data['review'].get('findings',[]):
        for evidence in finding.get('evidence',[]):
            if evidence.get('image'):evidence['image']=local(evidence['image'])
    template=ROOT/'scripts/templates/battle_evaluation.html'
    payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    html.write_text(template.read_text().replace('__DATA__',payload))
    # This is the review manifest, never the sealed production manifest.
    manifest_path=owner.cache('evaluation/'+evaluation_id+'/report-manifest.json')
    if manifest_path.exists():
        manifest=read(manifest_path)
        manifest.setdefault('presentation_revisions',[]).append(dict(previous_html_sha256=hashlib.sha256(source.encode()).hexdigest(),kind='local_inline_images'))
        manifest['outputs'][str(html.relative_to(owner.root))]=digest(html)
        manifest['sources'][str(template.relative_to(ROOT))]=digest(template)
        manifest['sources'][str(Path(__file__).relative_to(ROOT))]=digest(Path(__file__))
        atomic_json(manifest_path,manifest)
    return html
def forbidden(*args,**kwargs):raise AssertionError('Offline evaluation cannot acquire recognition or video')


def slots(state):
    result={}
    for key in SLOTS:
        side,slot=key.split(':');team=state.sides[side];pid=team.active_slots.get(slot);p=state.pokemon.get(pid)
        if not p:result[key]=dict(instance_id=None,status='vacant' if slot in team.vacant_slots else 'unknown');continue
        ep=current_episode(state,pid)
        result[key]=dict(instance_id=pid,species_id=p.species.value.get('species_id') if p.species.known else None,
            name=p.species.value.get('name') if p.species.known else None,status='last_supported_occupancy',
            hp_current=p.hp.current.value,hp_maximum=p.hp.maximum.value,
            major_status=p.major_status.value,fainted=p.fainted.value,
            stages={k:v.value.value for k,v in p.stages.items() if v.value.known},
            episode_id=ep['episode_id'] if ep else None,persistent_identity_status=ep.get('persistent_identity_status') if ep else 'unknown')
    return result


def timeline(folder,target):
    original=read(folder/'replay.json');identity=dict(replay_sha256=digest(folder/'replay.json'),runner_sha256=digest(Path(__file__)))
    manifest_path=target/'timeline-manifest.json';output=target/'timeline.json'
    if manifest_path.exists():
        old=read(manifest_path);assert old['identity']==identity,'Timeline identity changed: preserve it and choose a new evaluation ID'
        if old['status']=='complete':
            assert digest(output)==old['output_sha256'];return read(output)
    atomic_json(manifest_path,dict(status='running',identity=identity))
    engine=StateEngine(from_dict(original['initial_state']))
    engine.history=[EventRecord(deepcopy(h['event']),h['delivery_index'],deepcopy(h['ordering']),retracted=h.get('retracted',False)) for h in original['history']]
    expected={h['event']['event_id']:h for h in original['history']};changes=[dict(timestamp=0,event_id=None,slots=slots(engine.state))];deltas={};violations=[];start=time.monotonic()
    def capture(record,state):
        old=expected[record.event['event_id']]
        assert record.application_status==old['application_status'] and record.state_hash==old['state_hash'],record.event['event_id']
        assert record.reason==old['reason'] and record.bindings==old['bindings'],record.event['event_id']
        now=slots(state);before=changes[-1]['slots']
        delta={k:dict(before=before[k],after=now[k]) for k in SLOTS if before[k]!=now[k]}
        if delta:
            deltas[record.event['event_id']]=delta;changes.append(dict(timestamp=record.event['attributes']['observation_time'],event_id=record.event['event_id'],slots=now))
        for side in state.sides.values():
            if len(set(side.active_slots.values()))!=len(side.active_slots):violations.append(record.event['event_id'])
        if (record.delivery_index+1)%100==0:
            atomic_json(target/'timeline-progress.json',dict(completed=record.delivery_index+1,total=len(expected),changes=changes,deltas=deltas))
            print('Frozen timeline',record.delivery_index+1,'/',len(expected),flush=True)
    with ExitStack() as stack:
        for name in ['recognition.fast_video.CachedOCR.read','recognition.fast_video.CachedOCR.predict','recognition.fast_video.CachedIcons.identify','recognition.fast_video.decoded_frames','cv2.VideoCapture','cv2.imread']:stack.enter_context(patch(name,forbidden))
        engine.replay(snapshot_callback=capture)
    assert engine.to_dict()['state']==original['state'],'Final state drift'
    result=dict(changes=changes,deltas=deltas,violations=violations,wall_seconds=time.monotonic()-start,all_original_receipts_and_hashes_equal=True,recognition_calls=0)
    atomic_json(output,result);atomic_json(manifest_path,dict(status='complete',identity=identity,output_sha256=digest(output)))
    return result


def build(owner,run_id,evaluation_id,observations=None):
    folder=owner.cache('event-driven/'+run_id);target=owner.cache('evaluation/'+evaluation_id);target.mkdir(parents=True,exist_ok=True)
    report=owner.report('evaluation/'+evaluation_id);report.mkdir(parents=True,exist_ok=True)
    if (folder/'video-only-seal.json').exists():
        from recognition.event_report import verify_seal
        verify_seal(folder)
    replay=read(folder/'replay.json');obs_path=observations or folder/'observations.json';rows=read(obs_path)['observations']
    line=timeline(folder,target)
    def image_link(value):
        if not value:return None
        if value not in image_cache:image_cache[value]=review_image(owner,report,value)
        return image_cache[value]
    image_cache={}
    by_source={r['source_id']:r for r in rows}
    def images(e):
        refs=[]
        for p in e['evidence']:
            r=by_source.get(p['source_id']);path=p.get('details',{}).get('image') or (r or {}).get('image')
            if path:refs.append(dict(image=image_link(path),source_id=p['source_id'],timestamp=p.get('details',{}).get('timestamp'),sha256=(r or {}).get('sha256')))
        return refs
    events=[]
    for h in replay['history']:
        e=h['event'];resolved=h.get('bindings',{}).get('resolved_event') or e
        events.append(dict(event_id=e['event_id'],timestamp=e['attributes']['observation_time'],kind=e['event_type'],side=resolved['side'],
            text=e['original_text'],status=h['application_status'],reason=h['reason'],actor=resolved.get('actor'),target=resolved.get('target'),
            bindings=h['bindings'],attributes=e['attributes'],evidence=e['evidence'],images=images(e),changes=line['deltas'].get(e['event_id'],{})))
    frames=[dict(timestamp=r['timestamp'],source_id=r['source_id'],sha256=r['sha256'],image=image_link(r['image']),
        ui=r['ui'],message=r.get('message'),snapshot=r.get('snapshot'),command=r.get('command'),inspection=r.get('command_inspection'),checkpoint=r.get('command_checkpoint')) for r in rows]
    if (folder/'audit.json').exists():
        audited={r['source_id']:r for r in read(folder/'audit.json')['frames']}
        for f in frames:
            a=audited.get(f['source_id'],{});f['inspection']=a.get('inspection',f['inspection']);f['checkpoint']=a.get('checkpoint',f['checkpoint'])
    state=replay['state'];knowledge=state['knowledge'];ledger=knowledge.get('command_reconciliation',{});receipts=ledger.get('receipts',[])
    # Receipt screenshots and original proof chains remain intact in event details.
    counts=dict(events=len(events),statuses=dict(Counter(e['status'] for e in events)),event_types=dict(Counter(e['kind'] for e in events)),
        deferred_reasons=dict(Counter(e['reason'] for e in events if e['status']=='deferred')),
        contradictions=len(state.get('conflicts',[])),checkpoints=len(receipts),corrections=sum(r['corrections'] for r in receipts),
        checkpoint_slots=dict(Counter(o['status'] for r in receipts for o in r['outcomes'])),
        eligible_frames=sum(bool(f['inspection'] and f['inspection'].get('eligible')) for f in frames))
    identities=dict(trainers={s:v.get('trainer') for s,v in state['sides'].items()},
        preview_rows=read(folder/'observations.json').get('roster',[]) if (folder/'observations.json').exists() else [],
        ledger=knowledge.get('identity_ledger',{}),episodes=knowledge.get('active_entry_episodes',[]))
    if (folder/'video-only.json').exists():identities['preview_rows']=read(folder/'video-only.json').get('teams',[])
    execution=owner.cache('evaluation/'+run_id+'/execution.json');performance=read(execution) if execution.exists() else {}
    manifest=read(folder/'manifest.json') if (folder/'manifest.json').exists() else {}
    performance={k:v for k,v in performance.items() if k not in {'identity','sealed_outputs'}}
    performance['production_counts']=manifest.get('counts',{});performance['decoder']=manifest.get('decoder',{})
    performance['cold_end_to_end_wall_seconds']=manifest.get('cold_end_to_end_wall_seconds')
    performance['timeline_replay_seconds']=line['wall_seconds']
    duration=manifest.get('decoder',{}).get('container_duration_seconds')
    wall=performance.get('wall_seconds')
    performance['video_seconds_per_wall_second']=duration/wall if duration and wall else None
    notes_path=target/'agent-review.json';notes=read(notes_path) if notes_path.exists() else dict(status='pending',independent_human_review=False,findings=[])
    data=dict(battle_id=owner.battle_id,run_id=run_id,counts=counts,events=events,frames=frames,timeline=line['changes'],identities=identities,
        checkpoint_receipts=receipts,performance=performance,review=notes,consistency={k:line[k] for k in ['all_original_receipts_and_hashes_equal','violations','recognition_calls']},
        provenance=dict(replay_sha256=digest(folder/'replay.json'),observations_sha256=digest(obs_path),frozen_first_pass=bool(manifest.get('cold_run')),
            description='Automatic candidates and replay consistency are not independently verified correctness. Review annotations do not enter the runtime.'))
    template=ROOT/'scripts/templates/battle_evaluation.html';html=report/'review.html';md=report/'completion.md'
    payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    html.write_text(template.read_text().replace('__DATA__',payload))
    findings='\n'.join(f"- {f.get('severity','unresolved')}: {f.get('description',f)}" for f in notes.get('findings',[])) or '- Independent correctness review pending.'
    md.write_text(f'''# {owner.battle_id} — frozen production evaluation

[Offline HTML review](review.html). Run: `{run_id}`. Evaluation: `{evaluation_id}`.

Review status: **{notes.get('status','pending')}**. An exact saved-event replay reproduced every original application status, state hash and final state. This establishes reproducibility, not independent correctness. Duplicate active-instance violations: {len(line['violations'])}. Runtime predictions are unchanged; review annotations are separate.

{len(rows)} saved observations, {len(events)} event records. Application statuses: `{json.dumps(counts['statuses'])}`. Contradictions: {counts['contradictions']}.

Command checks: {counts['eligible_frames']} eligible frames, {counts['checkpoints']} attempts; slot outcomes `{json.dumps(counts['checkpoint_slots'])}`; {counts['corrections']} actual corrections. One attempt per scheduled command phase; ambiguous single-frame identities cannot repair occupancy.

Deferred reasons: `{json.dumps(counts['deferred_reasons'])}`. Deferred and partially applied records remain unresolved unless individually reviewed.

## Findings

{findings}

## Resources and reproducibility

```json
{json.dumps(performance,indent=2)}
```

Original screenshots, chronological events, four-slot prefix timeline, trainer/roster/alias evidence, transitions, checkpoint receipts and exact deferred reasons are available in the HTML. Images are relative links to the retained original cache. No live network is needed. Chinese text is original battle evidence. Snapshot matching is not a measured recognition accuracy score.

Production command: `.venv/bin/python main.py --video tests/fixtures/{owner.battle_id}.mp4 --profile event-driven --run-id {run_id}`. Reuse the existing completed run; do not reacquire it. Frozen source, first-pass fingerprints, execution logs and process-tree memory measurements are retained under the battle's evaluation namespace. Reporting uses saved events only, with decoding/OCR/icons blocked.
''')
    atomic_json(target/'evaluation-summary.json',dict(counts=counts,review=notes,performance=performance,consistency=data['consistency']))
    atomic_json(target/'report-manifest.json',dict(status='complete',inputs=dict(replay=digest(folder/'replay.json'),observations=digest(obs_path),review=digest(notes_path) if notes_path.exists() else None),
        sources={str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),template]},outputs={str(p.relative_to(ROOT)):digest(p) for p in [html,md]}))
    print(str(html.relative_to(ROOT)),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',required=True);p.add_argument('--run-id',required=True);p.add_argument('--evaluation-id',required=True);p.add_argument('--observations',type=Path)
    p.add_argument('--refresh-images-only',action='store_true',help='Refresh saved review HTML/assets only; no replay or annotation writes')
    a=p.parse_args();owner=BattleArtifacts(a.battle,ROOT)
    if a.refresh_images_only:
        print(refresh_review_images(owner,a.evaluation_id));return
    if a.observations:assert a.observations.resolve().is_relative_to(owner.cache_dir.resolve())
    build(owner,a.run_id,a.evaluation_id,a.observations)
if __name__=='__main__':main()
