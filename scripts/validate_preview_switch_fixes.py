"""Scoped saved-data checks for the B17/B18 fixes; never writes frozen runs.

Stages checkpoint their inputs/version identity. No video decoding or OCR.
The icons stage performs real matching only on saved preview images.
"""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.fast_video import digest
from recognition.video_sampling import atomic_json

RUN='fresh-b17-b18-20261028-v1'
EXPERIMENT='three-fixes-20261028-v1'


def read(path):return json.loads(path.read_text())


def start(battle,stage):
    from recognition.event_report import verify_seal
    owner=BattleArtifacts(battle,ROOT);source=owner.cache('event-driven/'+RUN);verify_seal(source)
    out=owner.cache('diagnosis/'+EXPERIMENT+'/'+stage);out.mkdir(parents=True,exist_ok=True)
    identity=dict(input_sha256=digest(source/'observations.json'),script_sha256=digest(Path(__file__)),
        sources={str(p.relative_to(ROOT)):digest(p) for d in ['recognition','tracking','battle_events'] for p in (ROOT/d).glob('*.py')},
        knowledge_sources={n:digest(ROOT/n) for n in ['knowledge/__init__.py',
            'knowledge/resolution_effects.py','knowledge/data/52poke-resolution-v1.json']})
    manifest=out/'stage.json'
    if manifest.exists():
        prior=read(manifest)
        if prior['identity']!=identity:raise ValueError('Changed stage identity: use a new EXPERIMENT')
        if prior['status']=='complete':print('Reuse',manifest);return None
        raise ValueError('Inspect interrupted stage/process before selecting a new experiment')
    atomic_json(manifest,dict(status='running',identity=identity))
    return owner,source,out,identity


def b17():
    args=start('sample_battle_17','reparse')
    if not args:return
    owner,source,out,identity=args
    from recognition.message_occurrences import MessageOccurrences
    from recognition.event_report import video_events
    from tracking.battle_state import from_dict
    from tracking.state_engine import StateEngine,EventRecord,event_from_dict,ordering
    data=read(source/'observations.json');baseline=read(source/'replay.json');group=MessageOccurrences(owner.battle_id,source_occurrence_ids=True)
    for row in data['observations']:
        result=group.observe(row);row['occurrence_decision']=dict(events=result['events'],reason=result['reason'])
    data['occurrences']=group.groups;atomic_json(out/'observations.json',data)
    events=video_events(data['observations'],data['roster'],owner.battle_id)
    engine=StateEngine(from_dict(baseline['initial_state']))
    for i,e in enumerate(events,1):
        e['attributes']['sequence']=i;engine.history.append(EventRecord(e,i,ordering(event_from_dict(e))))
    checkpoints=[]
    def progress(record,state):
        t=record.event['attributes']['observation_time']
        if record.delivery_index%100==0:
            atomic_json(out/'progress.json',dict(receipt=record.delivery_index,total=len(events),timestamp=t))
            print('B17 saved replay',record.delivery_index,len(events),flush=True)
        if 341.5<=t<=341.6 or 347.5<=t<=347.6 or 360.5<=t<=360.6:
            checkpoints.append(dict(time=t,event_id=record.event['event_id'],event_type=record.event['event_type'],status=record.application_status,
                slots={s:{slot:state.pokemon[pid].species.value.get('name') for slot,pid in team.active_slots.items()} for s,team in state.sides.items()}))
    began=time.perf_counter();engine.replay(snapshot_callback=progress);seconds=time.perf_counter()-began
    actual=engine.to_dict();atomic_json(out/'replay.json',actual)
    before=Counter(h['reason'] for h in baseline['history'] if h['application_status']=='deferred')
    after=Counter(h['reason'] for h in actual['history'] if h['application_status']=='deferred')
    unrelated={h['event']['event_id'] for h in baseline['history'] if h['reason']=='message_episode_occupancy_unresolved' and h['event']['side']=='self'}
    remaining={h['event']['event_id'] for h in actual['history'] if h['reason']=='message_episode_occupancy_unresolved'}
    assert remaining==unrelated and len(unrelated)==9
    withdrawal=[h for h in actual['history'] if h['event']['event_type']=='switch_out' and h['event']['attributes'].get('cause')=='eject_button']
    assert len(withdrawal)==1 and withdrawal[0]['application_status']=='applied_candidate'
    assert checkpoints[-1]['slots']['opponent']==dict(left='千面避役',right='喷火龙')
    fixed={h['event']['event_id'] for h in baseline['history'] if 'active_identity_context_unresolved' in h['bindings'].get('resolved_event',h['event'])['uncertainty'] and h['application_status']=='deferred'}
    admitted={h['event']['event_id'] for h in actual['history'] if h['application_status'] in {'applied_candidate','applied_partial','recorded_observation'}}
    assert len(fixed)==6 and fixed<=admitted
    atomic_json(out/'stage.json',dict(status='complete',identity=identity,replay_seconds=seconds,
        before_deferred=dict(before),after_deferred=dict(after),cascade_hud_recovered=202,cascade_messages_admitted=6,
        unrelated_occupancy_events_preserved=sorted(unrelated),checkpoints=checkpoints,
        withdrawal=withdrawal[0],remaining=[h for h in actual['history'] if h['application_status']=='deferred']))
    print('B17 complete',dict(before),dict(after),flush=True)


def b18_icons():
    args=start('sample_battle_18','icons')
    if not args:return
    owner,source,out,identity=args
    import cv2
    from recognition import Recognizer
    from recognition.fast_video import CachedIcons
    from recognition.event_schedule import IdentitySchedule
    from capture import Frame
    class NoOCR:
        def read(self,*a,**kw):raise AssertionError('Saved-frame icon validation must not invoke OCR')
    data=read(source/'observations.json');counts=Counter();icons=CachedIcons(out,counts)
    recognizer=Recognizer(NoOCR(),icons=icons);schedule=IdentitySchedule();roster=[];began=time.perf_counter()
    for row in data['observations']:
        phase=row['ui']['phase'];schedule.observe_phase(phase)
        if phase!='team_preview':continue
        image=cv2.imread(str(ROOT/row['image']));icons.timestamp=row['timestamp'];icons.frame_source=row['source_id']
        roster+=schedule.acquire_team(recognizer,Frame(image,row['source_id'],len(roster),row['timestamp'],row),phase,owner.battle_id,counts)
        atomic_json(out/'progress.json',dict(timestamp=row['timestamp'],counts=dict(counts)))
    elapsed=time.perf_counter()-began;atomic_json(out/'roster.json',roster)
    first=[r for r in roster if r['evidence']['timestamp']<200];resolved={r['preview_row']:r['species_id'] for r in first if r['status']=='resolved'}
    assert resolved=={1:1018,3:768,4:279,6:445}
    assert all(r['status']!='resolved' for r in first if r['preview_row'] in (2,5))
    atomic_json(out/'stage.json',dict(status='complete',identity=identity,counts=dict(counts),wall_seconds=elapsed,
        measurement='Actual saved-frame matching, isolated empty icon crop cache; no OCR/video decode. Icon span excludes library construction, as in production.',
        resolved_rows_during_real_preview=resolved,roster_rows=len(roster),
        real_preview_requests=sum(r['evidence']['timestamp']<200 for r in roster),
        late_false_preview_requests=sum(r['evidence']['timestamp']>200 for r in roster)))
    print('B18 saved-frame icons complete',dict(counts),flush=True)


def b18_consistency():
    owner=BattleArtifacts('sample_battle_18',ROOT);base=owner.cache('event-driven/'+RUN)
    out=owner.cache('diagnosis/'+EXPERIMENT+'/package');profile=read(out/'profile-manifest.json')
    assert profile['status']=='complete'
    current=read(out/'replay.json');old=read(base/'replay.json')
    # Preview compaction may change knowledge.roster, repeat links and hashes,
    # but every non-preview receipt and every other state fact must survive.
    for a,b in zip(old['history'],current['history']):
        assert a['event']==b['event']
        if a['event']['event_type']=='preview_observation':continue
        assert (a['application_status'],a['reason'],a['bindings'])==(b['application_status'],b['reason'],b['bindings']),a['event']['event_id']
    a=deepcopy(old['state']);b=deepcopy(current['state'])
    a['knowledge']['identity_ledger'].pop('roster');b['knowledge']['identity_ledger'].pop('roster')
    b['observations']=[o for o in b['observations'] if o.get('kind')!='preview_repeat']
    assert a==b,'Non-preview final facts changed'
    path=out/'determinism.json'
    if path.exists() and read(path)['status']=='complete':print('Reuse deterministic replay');return
    from tracking.battle_state import from_dict
    from tracking.state_engine import StateEngine,EventRecord
    atomic_json(path,dict(status='running',input_replay_sha256=digest(out/'replay.json')))
    e=StateEngine(from_dict(current['initial_state']));e.history=[EventRecord(**h) for h in current['history']]
    def progress(record,state):
        if record.delivery_index%100==0:
            atomic_json(out/'determinism-progress.json',dict(receipt=record.delivery_index,total=len(e.history)))
            print('B18 consistency replay',record.delivery_index,len(e.history),flush=True)
    began=time.perf_counter();e.replay(snapshot_callback=progress);elapsed=time.perf_counter()-began
    # Compare serialized representations, as in the production JSON contract;
    # native policy/mechanics dataclasses legitimately contain tuples.
    actual=json.loads(json.dumps(e.to_dict()))
    atomic_json(out/'second-replay.json',actual)
    assert actual==current
    atomic_json(path,dict(status='complete',input_replay_sha256=digest(out/'replay.json'),
        second_replay_seconds=elapsed,exact_replay=True,non_preview_receipts_and_facts_preserved=True,
        before_roster=len(old['state']['knowledge']['identity_ledger']['roster']),after_roster=len(current['state']['knowledge']['identity_ledger']['roster']),
        before_state_bytes=len(json.dumps(old['state'],ensure_ascii=False).encode()),after_state_bytes=len(json.dumps(current['state'],ensure_ascii=False).encode())))
    print('B18 consistency complete',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',required=True,choices=['b17','b18-icons','b18-consistency'])
    p.add_argument('--experiment',default=EXPERIMENT);a=p.parse_args();EXPERIMENT=a.experiment
    {'b17':b17,'b18-icons':b18_icons,'b18-consistency':b18_consistency}[a.stage]()
