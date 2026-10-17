"""Scoped M2.3.8-V saved-evidence audit, acquisition and replay.

No video decoding, command HUD reconciliation, reference imports or model changes.
Use --battle sample_battle_5 / sample_battle_6 --stage audit|trainers|replay.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json
from tracking.battle_state import from_dict
from tracking.state_engine import StateEngine, EventRecord, event_from_dict, ordering

RUN='m238-trainer-nickname-v3'

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def forbidden(*args,**kwargs):raise AssertionError('Saved replay cannot acquire recognition')

def inputs(owner):
    runs=('m238-rc-b5-v1','m238-rc-b5-v1') if owner.battle_id=='sample_battle_5' else ('m238-scrolling-semantics-v4','m238-active-persistence-v1')
    return owner.cache('event-driven/'+runs[0]+'/observations.json'),owner.cache('event-driven/'+runs[1]+'/replay.json')

def audit(owner,folder):
    obs,base=inputs(owner);data=read(obs);baseline=read(base)
    protected={str(p.relative_to(ROOT)):sha(p) for p in [obs,base]}
    for p in owner.report('').parent.glob('M2.3.8*'):
        if p.is_file():protected[str(p.relative_to(ROOT))]=sha(p)
    rows=data['observations']
    icons=[]
    for r in rows:
        for m in r.get('snapshot',{}).get('pokemon',[]):
            s=m.get('species') or {};i=m.get('icon') or {}
            if not m['slot'].startswith('opponent') or not s.get('raw_text'):continue
            icons.append(dict(timestamp=r['timestamp'],source_id=r['source_id'],sha256=r['sha256'],
                slot=m['slot'],raw=s['raw_text'],ocr_confidence=s.get('confidence'),status=i.get('status'),
                species_id=i.get('species_id'),method=i.get('method'),identity_reused_from=m.get('identity_reused_from'),
                candidates=[{k:c.get(k) for k in ['species_id','similarity']} for c in i.get('candidates',[])[:2]]))
    atomic_json(folder/'audit.json',dict(battle_id=owner.battle_id,protected=protected,
        preview=[{k:r.get(k) for k in ['side','preview_row','species_id','status','evidence']} for r in data['roster']],
        trainers=[dict(timestamp=r['timestamp'],observations=r['trainer_observations']) for r in rows if r.get('trainer_observations')],icons=icons,
        baseline_receipts=len(baseline['history']),recognition_calls=0))

def trainers(owner,folder,*,reuse=None,matchmaking_times=()):
    import cv2
    from recognition.fast_video import CachedOCR
    from recognition.trainers import recognize_preview_trainers,recognize_matchmaking_trainer,trainer_observation,aggregate_trainer
    target=folder/'trainers.json'
    if target.exists():print('Trainer acquisition reused');return
    data=read(inputs(owner)[0]);rows=[r for r in data['observations'] if r.get('trainer_observations')]
    if reuse:
        prior=owner.cache('event-driven/'+reuse+'/trainers.json');saved=read(prior)
        counts=Counter();backend=CachedOCR(folder,counts);out=deepcopy(saved['observations']);dialogs=[];began=time.monotonic()
        for t in matchmaking_times:
            r=min(data['observations'],key=lambda r:abs(r['timestamp']-t))
            assert abs(r['timestamp']-t)<.3 and sha(ROOT/r['image'])==r['sha256']
            backend.source=r['source_id'];backend.timestamp=r['timestamp']
            for raw in recognize_matchmaking_trainer(cv2.imread(str(ROOT/r['image'])),backend,
                    source=r['source_id'],sha256=r['sha256'],timestamp=r['timestamp']):
                raw['evidence'][0]['image']=r['image'];dialogs.append(raw)
                if raw['parse_status']=='supported':out.append(trainer_observation(raw,owner.battle_id,'opponent'))
        out.sort(key=lambda c:c['evidence'][0]['timestamp'])
        atomic_json(target,dict(observations=out,counts=dict(counts),wall_seconds=time.monotonic()-began,
            reused_from=str(prior.relative_to(ROOT)),reused_sha256=sha(prior),reused_counts=saved['counts'],
            matchmaking_times=list(matchmaking_times),matchmaking_observations=dialogs))
        return
    if not rows:
        old=read(owner.cache('event-driven/m238-trainer-opening-v3/trainers.json'))
        atomic_json(target,dict(observations=old['trainer_observations'],counts=dict(ocr_invocations_performed=0),reused_from='m238-trainer-opening-v3'));return
    counts=Counter();backend=CachedOCR(folder,counts);out=[];claims={};began=time.monotonic()
    for r in rows[:3]:
        sides=tuple(s for s in ('self','opponent') if claims.get(s,{}).get('status')!='accepted')
        if not sides:break
        backend.source=r['source_id'];backend.timestamp=r['timestamp']
        image=cv2.imread(str(ROOT/r['image']))
        assert sha(ROOT/r['image'])==r['sha256']
        result=recognize_preview_trainers(image,backend,source=r['source_id'],sha256=r['sha256'],timestamp=r['timestamp'],sides=sides)
        for side,raw in result.items():
            raw['evidence'][0]['image']=r['image'];obs=trainer_observation(raw,owner.battle_id,side)
            out.append(obs);claims[side]=aggregate_trainer(claims.get(side),obs)
        atomic_json(folder/'trainer-progress.json',dict(observations=out,claims=claims,counts=dict(counts)))
        print('Trainer frame',r['timestamp'],[(s,v.get('display_name'),v['status']) for s,v in claims.items()],flush=True)
    atomic_json(target,dict(observations=out,claims=claims,counts=dict(counts),wall_seconds=time.monotonic()-began,model_identity=backend.identity))

def metrics(result):
    hist=result['history'];moves=[h for h in hist if h['event']['event_type']=='move_execution']
    return dict(receipts=dict(Counter(h['application_status'] for h in hist)),
        moves=dict(total=len(moves),actor_bound=sum(bool(h['bindings'].get('actor')) for h in moves)),
        transitions={kind:dict(Counter(h['application_status'] for h in hist if h['event']['event_type']==kind)) for kind in ['send_out','switch_out','faint']},
        trainers={s:t['trainer'] for s,t in result['state']['sides'].items()},
        contradictions=[dict(event_id=h['event']['event_id'],reason=h['reason']) for h in hist if h['application_status']=='rejected'])

def replay(owner,folder):
    from recognition.event_report import video_events
    target=folder/'replay.json'
    source_names=['recognition/trainers.py','recognition/event_schedule.py','recognition/event_report.py',
        'battle_events/parser.py','tracking/identity_ledger.py','tracking/evidence_fusion.py',
        'tracking/state_engine.py','tracking/reliability.py','tracking/active_continuity.py',
        'tracking/active_persistence.py','scripts/validate_m238v.py']
    identity={n:sha(ROOT/n) for n in source_names}
    obs,base=inputs(owner);identity.update({str(p.relative_to(ROOT)):sha(p) for p in [obs,base,folder/'trainers.json']})
    manifest=folder/'manifest.json'
    if manifest.exists():
        assert read(manifest)['identity']==identity,'Source changed: preserve namespace and select a new version'
        if target.exists():print('Completed replay reused');return
    atomic_json(manifest,dict(status='running',identity=identity,recognition_calls=0))
    for name in source_names:
        dest=folder/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/name).read_bytes())
    data=read(obs);rows=deepcopy(data['observations']);baseline=read(base)
    captures=read(folder/'trainers.json')['observations']
    by_source={r['source_id']:r for r in rows}
    for r in rows:r['trainer_observations']=[]
    for c in captures:
        source=c['evidence'][0]['source'];r=by_source[source];r['trainer_observations'].append(c)
    # Preserve the frozen B6 message adapter. Only replace trainer observations;
    # rebuilding messages here would discard its scrolling-semantics evidence.
    if owner.battle_id=='sample_battle_6':
        events=[deepcopy(h['event']) for h in baseline['history'] if h['event']['event_type']!='trainer_observation']
        trainer_events=[e for e in video_events(rows,[],owner.battle_id) if e['event_type']=='trainer_observation']
        events+=trainer_events
        events.sort(key=lambda e:(e['attributes']['observation_time'],e['attributes'].get('sequence',0)))
    else:events=video_events(rows,data['roster'],owner.battle_id)
    for i,e in enumerate(events,1):e['attributes']['sequence']=i
    atomic_json(folder/'events.json',dict(events=events))
    engine=StateEngine(from_dict(baseline['initial_state']));first={};violations=[];occupancy={}
    engine.history=[EventRecord(deepcopy(e),i,ordering(event_from_dict(e),sequence=i)) for i,e in enumerate(events,1)]
    def progress(record,state):
        occupancy[record.event['attributes']['observation_time']]={s+':'+slot:pid for s,team in state.sides.items() for slot,pid in team.active_slots.items()}
        for side,team in state.sides.items():
            if len(set(team.active_slots.values()))!=len(team.active_slots):violations.append(record.event['event_id'])
            for slot,pid in team.active_slots.items():
                first.setdefault(side+':'+slot,dict(timestamp=record.event['attributes']['observation_time'],instance_id=pid,species_id=state.pokemon[pid].species.value.get('species_id')))
        if record.delivery_index%200==0:
            atomic_json(folder/'progress.json',dict(completed=record.delivery_index,total=len(events),timestamp=record.event['attributes']['observation_time']))
            print('Replay',record.delivery_index,'/',len(events),flush=True)
    began=time.monotonic()
    try:
        with ExitStack() as stack:
            for name in ['recognition.fast_video.CachedOCR.read','recognition.fast_video.CachedIcons.identify','recognition.fast_video.decoded_frames','cv2.imread','cv2.VideoCapture']:stack.enter_context(patch(name,forbidden))
            engine.replay(snapshot_callback=progress)
        result=engine.to_dict();result['first_slot_establishment']=first
        atomic_json(target,result)
        old={h['event']['event_id']:h for h in baseline['history']};regressions=[]
        for h in result['history']:
            prior=old.get(h['event']['event_id'])
            if prior and prior['bindings'].get('actor') and prior['application_status'].startswith('applied'):
                if not h['application_status'].startswith('applied') or h['bindings'].get('actor',{}).get('pokemon_instance_id')!=prior['bindings']['actor'].get('pokemon_instance_id'):
                    regressions.append(dict(event_id=h['event']['event_id'],before=prior['application_status'],after=h['application_status'],reason=h['reason']))
        slot_differences=[]
        if baseline.get('slot_states'):
            for t,slots in occupancy.items():
                old_slots=next((r['slots'] for r in reversed(baseline['slot_states']) if r['timestamp']<=t),{})
                old_slots={k:v['instance_id'] for k,v in old_slots.items() if v.get('instance_id')}
                if slots!=old_slots:slot_differences.append(dict(timestamp=t,before=old_slots,after=slots))
        missing_moves=[]
        for pid,p in baseline['state']['pokemon'].items():
            current=result['state']['pokemon'].get(pid,{})
            for move in p['moves']['executed']:
                if move not in current.get('moves',{}).get('executed',[]):missing_moves.append(dict(instance_id=pid,move=move))
        atomic_json(folder/'comparison.json',dict(before=metrics(baseline),after=metrics(result),first_slot_establishment=first,
            regressions=regressions,slot_differences=slot_differences,missing_moves=missing_moves,
            duplicate_slot_violations=violations,wall_seconds=time.monotonic()-began,recognition_calls=0))
        atomic_json(manifest,dict(status='complete',identity=identity,recognition_calls=0,replay_sha256=sha(target)))
    except BaseException as exc:
        atomic_json(manifest,dict(status='failed',identity=identity,error=repr(exc)));raise

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',required=True,choices=['sample_battle_5','sample_battle_6']);p.add_argument('--stage',required=True,choices=['audit','trainers','replay']);p.add_argument('--run-id',default=RUN)
    p.add_argument('--reuse-trainers');p.add_argument('--matchmaking-times',type=float,nargs='*',default=[])
    a=p.parse_args();owner=BattleArtifacts(a.battle,ROOT);folder=owner.cache('event-driven/'+a.run_id);folder.mkdir(parents=True,exist_ok=True)
    if a.stage=='audit':audit(owner,folder)
    elif a.stage=='trainers':trainers(owner,folder,reuse=a.reuse_trainers,matchmaking_times=a.matchmaking_times)
    else:replay(owner,folder)

if __name__=='__main__':main()
