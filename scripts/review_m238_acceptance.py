"""Bounded saved-frame W scheduling and saved-event acceptance review.

Every model cache miss is reported, never inferred. Outputs use a new evaluation
namespace; source recognition and blocker diagnostics are read-only.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from models import Observation
from recognition.command_checkpoint import CommandCheckpointSchedule,schedule_checkpoint,checkpoint_event
from recognition.event_report import verify_seal
from recognition.fast_video import CachedOCR,digest,fingerprint
from recognition.video_sampling import atomic_json
from scripts.run_production_evaluation import runtime_sources
from tracking.battle_state import from_dict
from tracking.state_engine import StateEngine,EventRecord,event_from_dict,ordering


def read(path):return json.loads(path.read_text())
def forbidden(*args,**kwargs):raise AssertionError('Acceptance review cannot acquire recognition')
class CacheUnavailable(Exception):pass


class CacheOnlyOCR(CachedOCR):
    def __init__(self,source,counts):
        super().__init__(source,counts)
        self.hits=[];self.missing=[]

    def predict(self,crops):
        result=[]
        for crop in crops:
            key=fingerprint(dict(shape=list(crop.shape),pixels=hashlib.sha256(crop.tobytes()).hexdigest(),**self.identity))
            path=self.folder/'reads'/(key+'.json')
            if not path.exists():raise CacheUnavailable(key)
            self.counts['ocr_prediction_requests']+=1;self.counts['ocr_exact_cache_hits']+=1
            self.hits.append(dict(source_id=self.source,timestamp=self.timestamp,path=str(path.relative_to(ROOT)),sha256=digest(path)))
            result.append(read(path))
        return result

    def read(self,image,bounds,**kwargs):
        try:return super().read(image,bounds,**kwargs)
        except CacheUnavailable as exc:
            self.missing.append(dict(source_id=self.source,timestamp=self.timestamp,bounds=list(bounds),cache_key=str(exc),
                                     reason='compatible_exact_crop_read_unavailable'))
            return Observation(region=list(bounds))


def begin(target,stage,identity):
    path=target/(stage+'-manifest.json')
    if path.exists():
        old=read(path)
        if old['identity']!=identity:raise ValueError('Review identity changed; preserve outputs and use a new review ID')
        if old['status']=='complete':
            for name,h in old['outputs'].items():
                if digest(target/name)!=h:raise ValueError('Review output changed: '+name)
            return False
    atomic_json(path,dict(status='running',identity=identity))
    return True


def finish(target,stage,identity,names):
    atomic_json(target/(stage+'-manifest.json'),dict(status='complete',identity=identity,
                outputs={name:digest(target/name) for name in names}))


def schedule(source,target,identity,rows):
    if not begin(target,'schedule',identity):return read(target/'schedule.json')
    import cv2
    counts=Counter();backend=CacheOnlyOCR(source,counts);scheduler=CommandCheckpointSchedule();frames=[]
    progress=target/'schedule-progress.json';start=0
    if progress.exists():
        old=read(progress);frames=old['frames'];scheduler.__dict__.update(old['scheduler']);start=len(frames)
        backend.hits=old['cache_hits'];backend.missing=old['missing_reads'];counts.update(old['counts'])
    with ExitStack() as stack:
        for name in ['recognition.fast_video.decoded_frames','cv2.VideoCapture',
                     'recognition.onnx_ocr.ONNXOCRBackend.__init__','recognition.onnx_ocr.ONNXOCRBackend.predict',
                     'recognition.fast_video.CachedIcons.identify']:
            stack.enter_context(patch(name,forbidden))
        for original in rows[start:]:
            row=deepcopy(original);row.pop('command_checkpoint',None);row.pop('command_inspection',None)
            image_path=ROOT/row['image']
            if not image_path.resolve().is_relative_to(source.resolve()):raise ValueError('Saved frame is outside the source run')
            if digest(image_path)!=row['sha256']:raise ValueError('Saved frame hash mismatch')
            image=cv2.imread(str(image_path))
            if image is None:raise ValueError('Saved frame cannot be read')
            backend.source=row['source_id'];backend.timestamp=row['timestamp']
            before=len(backend.missing)
            schedule_checkpoint(row,image,scheduler,backend,counts)
            frames.append(dict(timestamp=row['timestamp'],source_id=row['source_id'],image=row['image'],sha256=row['sha256'],
                phase_id='command:'+str(scheduler.phase),phase_active=scheduler.active,
                inspection=row['command_inspection'],checkpoint=row.get('command_checkpoint'),
                event=checkpoint_event(row,identity['battle_id']),missing_reads=backend.missing[before:],
                original_checkpoint=original.get('command_checkpoint'),original_inspection=original.get('command_inspection')))
            if len(frames)%100==0:
                atomic_json(progress,dict(frames=frames,scheduler=scheduler.__dict__,cache_hits=backend.hits,
                                         missing_reads=backend.missing,counts=dict(counts)))
                print('Saved-frame schedule',len(frames),'/',len(rows),flush=True)
    result=dict(frames=frames,counts=dict(counts),cache_hits=backend.hits,missing_reads=backend.missing,
                model_identity=backend.identity,recognition_calls=0,video_decoding=0,
                eligible_frames=sum(f['inspection']['eligible'] for f in frames),
                attempts=sum(bool(f['event']) for f in frames))
    atomic_json(target/'schedule.json',result);finish(target,'schedule',identity,['schedule.json'])
    return result


def slot_summary(state):
    result={}
    for side,team in state.sides.items():
        for slot in ['left','right']:
            pid=team.active_slots.get(slot);p=state.pokemon.get(pid)
            result[side+':'+slot]=dict(instance_id=pid,species_id=p.species.value.get('species_id') if p and p.species.known else None,
                occupancy='active' if p else 'vacant' if slot in team.vacant_slots else 'unknown',
                major_status=p.major_status.value if p else None)
    return result


def without_sequence(value):
    if isinstance(value,dict):return {k:without_sequence(v) for k,v in value.items() if k!='sequence'}
    if isinstance(value,list):return [without_sequence(v) for v in value]
    return value


def replay(target,identity,baseline,scheduling):
    identity=dict(identity,schedule_sha256=digest(target/'schedule.json'))
    if not begin(target,'replay',identity):return read(target/'replay-summary.json')
    original=read(baseline/'replay.json');old={h['event']['event_id']:h for h in original['history']}
    events=[deepcopy(h['event']) for h in original['history'] if h['event']['event_type']!='command_checkpoint']
    events += [deepcopy(f['event']) for f in scheduling['frames'] if f['event']]
    events.sort(key=lambda e:(e['attributes']['observation_time'],-1 if e['event_type']=='command_checkpoint' else e['attributes']['sequence']))
    engine=StateEngine(from_dict(original['initial_state']))
    for i,e in enumerate(events,1):
        e['attributes']['sequence']=i;engine.history.append(EventRecord(e,i,ordering(event_from_dict(e),sequence=i)))
    prefix=[];violations=[];regressions=[];binding_changes=[];deferred=[];changed=[]
    start=time.monotonic()
    def capture(record,state):
        e=record.bindings.get('resolved_event',record.event);t=e['attributes']['observation_time']
        if e['event_type']!='hud_observation' or 495<=t<=522 or record.application_status=='deferred':
            prefix.append(dict(event_id=e['event_id'],timestamp=t,event_type=e['event_type'],side=e['side'],
                               raw=e['original_text'],status=record.application_status,slots=slot_summary(state)))
        for side,team in state.sides.items():
            if len(team.active_slots)!=len(set(team.active_slots.values())):violations.append(dict(event_id=e['event_id'],side=side))
        previous=old.get(e['event_id'])
        if previous and e['event_type']!='command_checkpoint':
            before=(previous['application_status'],previous['reason']);after=(record.application_status,record.reason)
            if before!=after:changed.append(dict(event_id=e['event_id'],timestamp=t,before=before,after=after))
            if before[0].startswith('applied') and not after[0].startswith('applied'):regressions.append(e['event_id'])
            if without_sequence(previous['bindings'])!=without_sequence(record.bindings):binding_changes.append(e['event_id'])
        if previous and previous['application_status']=='deferred':
            deferred.append(dict(event_id=e['event_id'],timestamp=t,original_event=deepcopy(previous['event']),
                                 resolved_event=deepcopy(e),original_reason=previous['reason'],
                                 review_status=record.application_status,review_reason=record.reason,slots=slot_summary(state)))
        if record.delivery_index%100==0:
            atomic_json(target/'replay-progress.json',dict(completed=record.delivery_index,total=len(events),
                        regressions=regressions,duplicate_active_instances=violations,prefix=prefix,deferred=deferred))
            print('Acceptance replay',record.delivery_index,'/',len(events),flush=True)
    with ExitStack() as stack:
        for name in ['recognition.fast_video.CachedOCR.read','recognition.fast_video.CachedOCR.predict',
                     'recognition.fast_video.CachedIcons.identify','recognition.fast_video.decoded_frames','cv2.imread','cv2.VideoCapture']:
            stack.enter_context(patch(name,forbidden))
        engine.replay(snapshot_callback=capture)
    receipts=engine.state.knowledge.get('command_reconciliation',{}).get('receipts',[])
    outcome_counts=Counter(o['status'] for receipt in receipts for o in receipt['outcomes'])
    summary=dict(records=len(events),checkpoints=len(receipts),outcomes=dict(outcome_counts),
                 corrections=sum(r['corrections'] for r in receipts),receipts=receipts,
                 application_status_regressions=regressions,changed_statuses=changed,
                 noncheckpoint_binding_changes=binding_changes,duplicate_active_instances=violations,
                 pokemon_state_equal_to_blocker_diagnostic=without_sequence(original['state']['pokemon'])==without_sequence(engine.to_dict()['state']['pokemon']),
                 deferred=len([r for r in engine.history if r.application_status=='deferred']),
                 recognition_calls=0,wall_seconds=time.monotonic()-start)
    atomic_json(target/'replay.json',engine.to_dict());atomic_json(target/'replay-summary.json',summary)
    atomic_json(target/'prefix.json',prefix);atomic_json(target/'deferred-audit.json',deferred)
    finish(target,'replay',identity,['replay.json','replay-summary.json','prefix.json','deferred-audit.json'])
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--battle',required=True);parser.add_argument('--source-run',required=True)
    parser.add_argument('--baseline-diagnostic',required=True);parser.add_argument('--review-id',required=True)
    parser.add_argument('--stage',required=True,choices=['schedule','replay'])
    args=parser.parse_args();owner=BattleArtifacts(args.battle)
    source=owner.cache('event-driven/'+args.source_run);baseline=owner.cache('evaluation/'+args.baseline_diagnostic)
    target=owner.cache('evaluation/'+args.review_id)
    if target.resolve() in {source.resolve(),baseline.resolve()}:raise ValueError('A new review namespace is required')
    if target.exists() and not any(target.glob('*-manifest.json')):raise ValueError('Review namespace is occupied')
    target.mkdir(parents=True,exist_ok=True);verify_seal(source)
    identity=dict(battle_id=owner.battle_id,source_run=args.source_run,baseline_diagnostic=args.baseline_diagnostic,
        sources=runtime_sources(),runner_sha256=digest(Path(__file__)),
        original_seal_sha256=digest(source/'video-only-seal.json'),observations_sha256=digest(source/'observations.json'),
        baseline_replay_sha256=digest(baseline/'replay.json'),baseline_manifest_sha256=digest(baseline/'diagnostic-manifest.json'))
    if args.stage=='schedule':
        result=schedule(source,target,identity,read(source/'observations.json')['observations'])
        print(json.dumps({k:result[k] for k in ['eligible_frames','attempts','counts','missing_reads']},indent=2))
    else:
        if not (target/'schedule-manifest.json').exists():raise ValueError('Schedule stage must complete first')
        if begin(target,'schedule',identity):raise ValueError('Schedule stage is incomplete')
        result=replay(target,identity,baseline,read(target/'schedule.json'))
        print(json.dumps({k:v for k,v in result.items() if k!='receipts'},indent=2))
    verify_seal(source)


if __name__=='__main__':main()
