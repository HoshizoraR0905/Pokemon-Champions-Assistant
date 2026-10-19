"""M2.3.8-W staged audit/acquisition/replay of saved Battle 5 or 6 evidence.

No video decoding, full-battle OCR, historical edits, commits or network access.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import resource
import shutil
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json
from recognition.command_checkpoint import CommandCheckpointSchedule,checkpoint_event,capture_checkpoint_huds

RUN='m238-command-reconciliation-v1'

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def forbidden(*a,**k):raise AssertionError('Saved replay cannot acquire recognition')

def source(owner):
    run='m238-rc-b5-v1' if owner.battle_id=='sample_battle_5' else 'm238-scrolling-semantics-v4'
    return owner.cache('event-driven/'+run+'/observations.json')

def begin(folder,stage,dependencies):
    identity={str(p.relative_to(ROOT)):sha(p) for p in dependencies}
    manifest=folder/(stage+'-manifest.json')
    if manifest.exists():
        old=read(manifest);assert old['identity']==identity,'Stage identity changed; preserve namespace and choose a new version'
        if old['status']=='complete':return None
    data=dict(stage=stage,status='running',identity=identity)
    atomic_json(manifest,data)
    for p in dependencies:
        if p.suffix=='.py':
            dest=folder/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists():shutil.copy2(p,dest)
    return data

def finish(folder,stage,data,**extra):
    data.update(status='complete',**extra);atomic_json(folder/(stage+'-manifest.json'),data)

def audit(owner,folder):
    from recognition.command_checkpoint import inspect_command
    import cv2
    dependencies=[source(owner),ROOT/'recognition/command_checkpoint.py',ROOT/'recognition/ui_regions.py',ROOT/'recognition/fast_profile.py',Path(__file__)]
    manifest=begin(folder,'audit',dependencies)
    if manifest is None:print('Completed UI audit reused');return
    rows=read(source(owner))['observations'];schedule=CommandCheckpointSchedule();results=[];start=0
    progress=folder/'audit-progress.json'
    if progress.exists():
        old=read(progress);results=old['frames'];start=len(results);schedule.__dict__.update(old['schedule'])
    began=time.monotonic()
    for r in rows[start:]:
        image_path=ROOT/r['image'];assert image_path.resolve().is_relative_to(owner.cache_dir.resolve())
        assert sha(image_path)==r['sha256'],image_path
        image=cv2.imread(str(image_path));assert image is not None
        ui,attempt=schedule.inspect(r,image)
        results.append(dict(timestamp=r['timestamp'],source_id=r['source_id'],image=r['image'],sha256=r['sha256'],
            cached_phase=r['ui'].get('phase'),cached_command=r.get('command'),inspection=ui,checkpoint=attempt))
        if len(results)%100==0:
            atomic_json(progress,dict(frames=results,schedule=schedule.__dict__))
            print('UI audit',len(results),'/',len(rows),'checkpoints',sum(bool(x['checkpoint']) for x in results),flush=True)
    examples=[]
    for i in range(3):
        p=ROOT/'tests/fixtures/Image_Illustration'/f'Command_Label_Location_{i}.png'
        im=cv2.imread(str(p));result=inspect_command(cv2.resize(im,(1311,603),interpolation=cv2.INTER_AREA))
        examples.append(dict(image=str(p.relative_to(ROOT)),sha256=sha(p),expected='negative',
            meaning=['target_selection','move_description','party_status'][i],inspection=result,
            normalization='Reference-only resize to native layout; runtime other resolutions remain unsupported'))
        assert not result['normal_controls']
    atomic_json(folder/'audit.json',dict(battle_id=owner.battle_id,frames=results,reference_examples=examples,
        counts=dict(frames=len(results),normal_controls=sum(x['inspection']['normal_controls'] for x in results),
          eligible_frames=sum(x['inspection']['eligible'] for x in results),checkpoints=sum(bool(x['checkpoint']) for x in results),
          exclusion_causes=dict(Counter(x['inspection']['reason'] for x in results))),
        recognition_calls=0,video_decoding=0,wall_seconds=time.monotonic()-began,
        peak_process_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024)))
    finish(folder,'audit',manifest,audit_sha256=sha(folder/'audit.json'))

def acquire(owner,folder):
    import cv2
    from recognition.fast_video import CachedOCR,fingerprint
    class ReusingOCR(CachedOCR):
        def predict(self,crops):
            for crop in crops:
                key=fingerprint(dict(shape=list(crop.shape),pixels=hashlib.sha256(crop.tobytes()).hexdigest(),**self.identity))
                dest=self.folder/'reads'/(key+'.json')
                for old in cache_sources:
                    candidate=old/'reads'/(key+'.json')
                    if not dest.exists() and candidate.exists():
                        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(candidate,dest)
                        reused.append(dict(path=str(candidate.relative_to(ROOT)),sha256=sha(candidate)))
            return super().predict(crops)
    dependencies=[folder/'audit.json',source(owner),ROOT/'recognition/command_checkpoint.py',ROOT/'recognition/onnx_ocr.py',ROOT/'recognition/fast_video.py',Path(__file__)]
    manifest=begin(folder,'acquire',dependencies)
    if manifest is None:print('Completed scoped captures reused');return
    rows={r['source_id']:r for r in read(source(owner))['observations']}
    cache_sources=[source(owner).parent,owner.cache('event-driven/m238-live-1'),owner.cache('event-driven/m238-command-reconciliation-v1')]
    counts=Counter();reused=[];backend=ReusingOCR(folder,counts);captures=[];began=time.monotonic()
    progress=folder/'capture-progress.json'
    if progress.exists():
        old=read(progress);captures=old['captures'];counts.update(old['counts']);reused=old['reused']
    attempted={c['source_id'] for c in captures}
    for item in read(folder/'audit.json')['frames']:
        if not item['checkpoint'] or item['source_id'] in attempted:continue
        r=deepcopy(rows[item['source_id']]);r['command_checkpoint']=item['checkpoint'];before=dict(counts)
        if item['inspection']['eligible']:
            assert sha(ROOT/r['image'])==r['sha256']
            backend.source=r['source_id'];backend.timestamp=r['timestamp']
            capture_checkpoint_huds(r,cv2.imread(str(ROOT/r['image'])),backend)
        ev=checkpoint_event(r,owner.battle_id)
        captures.append(dict(source_id=r['source_id'],timestamp=r['timestamp'],event=ev,
            cost={k:counts[k]-before.get(k,0) for k in counts}))
        atomic_json(progress,dict(captures=captures,counts=dict(counts),reused=reused))
        print('Scoped checkpoint',r['timestamp'],r['command_checkpoint']['phase_id'],flush=True)
    atomic_json(folder/'captures.json',dict(captures=captures,counts=dict(counts),exact_cache_sources=reused,
        model_identity=backend.identity,video_decoding=0,icon_calls=0,wall_seconds=time.monotonic()-began,
        peak_process_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024)))
    finish(folder,'acquire',manifest,captures_sha256=sha(folder/'captures.json'))

def replay(owner,folder):
    from tracking.state_engine import StateEngine,EventRecord,event_from_dict,ordering
    from tracking.battle_state import from_dict
    from tracking.evidence_projection import source_times
    baseline=owner.cache('event-driven/m238-trainer-nickname-v3/replay.json')
    dependencies=[baseline,folder/'captures.json',Path(__file__),*[ROOT/n for n in [
        'battle_events/schema.py','recognition/event_report.py','tracking/state_engine.py','tracking/command_reconciliation.py',
        'tracking/evidence_fusion.py','tracking/active_continuity.py','tracking/active_persistence.py','tracking/identity_ledger.py']]]
    manifest=begin(folder,'replay',dependencies)
    if manifest is None:print('Completed checkpoint replay reused');return
    original=read(baseline);events=[deepcopy(h['event']) for h in original['history']]
    events += [c['event'] for c in read(folder/'captures.json')['captures']]
    events.sort(key=lambda e:(e['attributes']['observation_time'],-1 if e['event_type']=='command_checkpoint' else e['attributes']['sequence']))
    for i,e in enumerate(events,1):e['attributes']['sequence']=i
    initial=from_dict(original['initial_state']);initial.knowledge['command_reconciliation_v1']=True
    engine=StateEngine(initial);engine.history=[EventRecord(e,i,ordering(event_from_dict(e),sequence=i)) for i,e in enumerate(events,1)]
    began=time.monotonic();violations=[]
    def progress(record,state):
        for s,team in state.sides.items():
            if len(set(team.active_slots.values()))!=len(team.active_slots):violations.append(dict(event_id=record.event['event_id'],cause='duplicate_active_instance'))
        if record.delivery_index%200==0:
            atomic_json(folder/'replay-progress.json',dict(completed=record.delivery_index,total=len(events),timestamp=record.event['attributes']['observation_time']))
            print('Replay',record.delivery_index,'/',len(events),flush=True)
    try:
        with ExitStack() as stack:
            for n in ['recognition.fast_video.CachedOCR.read','recognition.fast_video.CachedOCR.predict','recognition.fast_video.CachedIcons.identify','recognition.fast_video.decoded_frames','cv2.imread','cv2.VideoCapture']:stack.enter_context(patch(n,forbidden))
            engine.replay(snapshot_callback=progress)
        result=engine.to_dict();atomic_json(folder/'replay.json',result)
        receipts=engine.state.knowledge.get('command_reconciliation',{}).get('receipts',[])
        original_by_id={h['event']['event_id']:h for h in original['history']};regressions=[]
        for h in result['history']:
            old=original_by_id.get(h['event']['event_id'])
            if old and old['application_status'].startswith('applied') and not h['application_status'].startswith('applied'):
                regressions.append(dict(event_id=h['event']['event_id'],before=old['application_status'],after=h['application_status'],reason=h['reason']))
        outcomes=[o for r in receipts for o in r['outcomes']]
        summary=dict(battle_id=owner.battle_id,checkpoints=len(receipts),classification=dict(Counter(o['status'] for o in outcomes)),
            corrections=sum(r['corrections'] for r in receipts),receipts=receipts,regressions=regressions,
            invariants=violations,rejected=[dict(event_id=h['event']['event_id'],reason=h['reason']) for h in result['history'] if h['application_status']=='rejected'],
            wall_seconds=time.monotonic()-began,recognition_calls=0)
        atomic_json(folder/'summary.json',summary)
        finish(folder,'replay',manifest,summary_sha256=sha(folder/'summary.json'),replay_sha256=sha(folder/'replay.json'))
    except BaseException as exc:
        manifest.update(status='failed',error=repr(exc));atomic_json(folder/'replay-manifest.json',manifest);raise

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',required=True,choices=['sample_battle_5','sample_battle_6']);p.add_argument('--run-id',default=RUN);p.add_argument('--stage',required=True,choices=['audit','acquire','replay'])
    a=p.parse_args();owner=BattleArtifacts(a.battle,ROOT);folder=owner.cache('event-driven/'+a.run_id);folder.mkdir(parents=True,exist_ok=True)
    globals()[a.stage](owner,folder)
if __name__=='__main__':main()
