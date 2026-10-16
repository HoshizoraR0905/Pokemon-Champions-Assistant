"""Trainer-ID addendum: scoped saved opening replay and a fresh Battle 6 log.

No video acquisition, Pokémon OCR or icon recognition. Header OCR is a separate,
bounded capture stage; completed captures and replay stages are reused.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import json
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.fast_video import digest
from recognition.video_sampling import atomic_json
from recognition.event_report import video_events, verify_seal
from recognition.message_occurrences import MessageOccurrences
from tracking.battle_state import BattleState
from tracking.state_engine import StateEngine, EventRecord, event_from_dict, ordering

RUN = 'm238-trainer-opening-v3'
SOURCES = ['recognition/trainers.py','recognition/event_schedule.py','recognition/event_report.py',
           'recognition/fast_video.py','tracking/identity_ledger.py','tracking/evidence_fusion.py',
           'tracking/state_engine.py','battle_events/schema.py','battle_events/parser.py',
           'scripts/replay_trainer_opening.py']


def forbidden(*args, **kwargs):
    raise AssertionError('Saved replay cannot run video/image/OCR/icon acquisition')


def capture(battle):
    """At most three preview frames, stop each side after its first clear read."""
    paths = BattleArtifacts(battle, ROOT)
    folder = paths.cache('event-driven/' + RUN); folder.mkdir(parents=True,exist_ok=True)
    if (folder/'trainers.json').exists():
        return json.loads((folder/'trainers.json').read_text())
    prior=paths.cache('event-driven/m238-trainer-opening-v1/trainers.json')
    if prior.exists():
        result=json.loads(prior.read_text())
        result.update(reused_from=str(prior.relative_to(ROOT)),reused_capture_sha256=digest(prior),
                      original_counts=result['counts'],counts=dict(ocr_invocations_performed=0,trainer_captures_reused=1))
        atomic_json(folder/'trainers.json',result)
        return result
    import cv2
    from capture import Frame
    from types import SimpleNamespace
    from recognition.event_schedule import IdentitySchedule
    from recognition.fast_video import CachedOCR
    if battle == 'sample_battle_6':
        rows = json.loads(paths.cache('event-driven/m238-live-3-diagnostic/observations.json').read_text())['observations']
        row = next(r for r in rows if r['ui']['phase']=='team_preview')
    else:
        rows = json.loads(paths.cache('m235/survey.json').read_text())['frames']
        row = next(r for r in rows if r['phase']=='team_preview')
    counts=Counter(); ocr=CachedOCR(folder,counts)
    ocr.source=row['source_id'];ocr.timestamp=row['timestamp']
    frame=Frame(cv2.imread(str(ROOT/row['image'])),row['source_id'],0,row['timestamp'],dict(row,sha256=digest(ROOT/row['image'])))
    schedule=IdentitySchedule()
    observed=schedule.acquire_trainers(SimpleNamespace(ocr=ocr),frame,'team_preview',.9,battle,counts)
    result=dict(status='complete',battle_id=battle,frame=frame.metadata,trainer_observations=observed,
                counts=dict(counts),model_identity=ocr.identity)
    atomic_json(folder/'trainers.json',result)
    return result


def inputs_for(battle):
    paths=BattleArtifacts(battle,ROOT); header=capture(battle)
    if battle=='sample_battle_6':
        source=paths.cache('event-driven/m238-live-3-diagnostic')
        verify_seal(source)
        data=json.loads((source/'observations.json').read_text());rows=deepcopy(data['observations'])
        row=next(r for r in rows if r['source_id']==header['frame']['source_id'])
        row['trainer_observations']=header['trainer_observations']
        return rows,data['roster'],data
    source=paths.cache('m236/development-observations.json')
    saved=json.loads(source.read_text())
    r=header['frame']
    rows=[dict(r,ui=dict(phase='team_preview',confidence=.9),trainer_observations=header['trainer_observations'],
               message=dict(selected=False,raw_text='',confidence=0),snapshot={},visual=dict(parsed=[],readings={}),
               occurrence_decision=dict(events=[]))]
    occurrences=MessageOccurrences(battle,source_occurrence_ids=True)
    for raw in saved['observations']:
        if raw['timestamp']>141:break
        row=deepcopy(raw);msg=row['message']
        row.update(ui=dict(phase=row['snapshot'].get('screen','unknown'),confidence=row['snapshot'].get('confidence',0)),
                   visual=dict(parsed=[],readings={}),message=dict(selected=bool(msg.get('raw_text')),
                       raw_text=msg.get('raw_text',''),confidence=msg.get('confidence',0),source_region_type='battle_message'))
        row['occurrence_decision']=occurrences.observe(row)
        rows.append(row)
    return rows,[],dict(observations=rows,occurrences=occurrences.groups,roster=[])


def replay(events, battle, progress_path):
    engine=StateEngine(BattleState(battle,knowledge=dict(identity_v1=True,reliability_v1=True,reliability_v2=True)))
    first_slots={}
    for i,event in enumerate(events,1):
        engine.history.append(EventRecord(deepcopy(event),i,ordering(event_from_dict(event),sequence=i)))
    def progress(record,state):
        for side,team in state.sides.items():
            for slot,pid in team.active_slots.items():
                key=side+':'+slot
                if key not in first_slots:
                    first_slots[key]=dict(timestamp=record.event['attributes']['observation_time'],
                        instance_id=pid,identity=state.pokemon[pid].species.value,evidence_event=record.event['event_id'])
        if record.delivery_index%100==0:
            row=dict(stage='saved_replay',completed=record.delivery_index,total=len(events),
                     timestamp=record.event['attributes']['observation_time'])
            atomic_json(progress_path,row);print(json.dumps(row),flush=True)
    with ExitStack() as stack:
        for name in ['recognition.fast_video.CachedOCR.read','recognition.fast_video.CachedOCR.predict',
                     'recognition.fast_video.CachedIcons.identify','recognition.fast_video.decoded_frames',
                     'cv2.imread','cv2.VideoCapture']:
            stack.enter_context(patch(name,forbidden))
        engine.replay(snapshot_callback=progress)
    result=engine.to_dict();result['first_slot_establishment']=first_slots
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',required=True,choices=['capture','prepare','prefix','full','report'])
    args=parser.parse_args()
    if args.stage=='capture':
        for battle in ('sample_battle_5','sample_battle_6'):
            data=capture(battle);print(battle,[(t['side'],t['raw_text'],t['ocr_confidence'],t['status']) for t in data['trainer_observations']])
        return
    paths=BattleArtifacts('sample_battle_6',ROOT);folder=paths.cache('event-driven/'+RUN)
    folder.mkdir(parents=True,exist_ok=True)
    identity={name:digest(ROOT/name) for name in SOURCES}
    manifest_path=folder/'manifest.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text())
        if manifest['sources']!=identity:raise ValueError('Source changed; preserve namespace and choose a new version')
    else:
        manifest=dict(sources=identity,completed=[],status='ready',video_decoding=0,icon_calls=0)
        atomic_json(manifest_path,manifest)
        for name in SOURCES:
            target=folder/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    if args.stage in manifest['completed']:print(args.stage+' complete; reused');return
    if args.stage=='prepare':
        for battle in ('sample_battle_5','sample_battle_6'):
            rows,roster,_=inputs_for(battle)
            events=video_events(rows,roster,battle)
            for i,event in enumerate(events,1):event['attributes']['sequence']=i
            owner=BattleArtifacts(battle,ROOT).cache('event-driven/'+RUN)
            atomic_json(owner/'events.json',dict(battle_id=battle,events=events,header_capture_sha256=digest(owner/'trainers.json')))
        manifest['completed'].append('prepare');atomic_json(manifest_path,manifest);return
    if 'prepare' not in manifest['completed']:raise ValueError('Prepare first')
    if args.stage=='prefix':
        for battle in ('sample_battle_5','sample_battle_6'):
            owner=BattleArtifacts(battle,ROOT).cache('event-driven/'+RUN)
            if (owner/'prefix.json').exists():continue
            events=json.loads((owner/'events.json').read_text())['events']
            selected=[e for e in events if e['attributes']['observation_time']<=141]
            atomic_json(owner/'prefix.json',replay(selected,battle,owner/'prefix-progress.json'))
        manifest['completed'].append('prefix');atomic_json(manifest_path,manifest);return
    if args.stage=='full':
        if 'prefix' not in manifest['completed']:raise ValueError('Validate prefix first')
        events=json.loads((folder/'events.json').read_text())['events']
        manifest.update(status='running',stage='full');atomic_json(manifest_path,manifest)
        try:
            result=replay(events,paths.battle_id,folder/'full-progress.json')
            atomic_json(folder/'replay.json',result)
            from scripts.build_m236_review import receipt
            baseline=json.loads(paths.cache('event-driven/m238-live-3-diagnostic/video-only.json').read_text())
            receipts=[]
            for record in result['history']:
                row=receipt(record);row['bindings']=record['bindings'];row['turn']=None
                row['turn_status']='unknown; no historical reference used';receipts.append(row)
            prediction=dict(baseline,events=events,receipts=receipts,adapter_version=RUN,
                reference_previously_available=True,independent_reference_used=False)
            atomic_json(folder/'prediction.json',prediction)
            atomic_json(folder/'prediction-seal.json',dict(stage='post_reference_diagnostic_frozen',
                files={n:digest(folder/n) for n in ['events.json','replay.json','prediction.json']},
                source_observations_sha256=digest(paths.cache('event-driven/m238-live-3-diagnostic/observations.json'))))
            manifest.update(status='ready');manifest['completed'].append('full');atomic_json(manifest_path,manifest)
        except BaseException as exc:
            manifest.update(status='failed',error=repr(exc));atomic_json(manifest_path,manifest);raise
        return
    if 'full' not in manifest['completed']:raise ValueError('Complete saved replay first')
    from scripts.audit_m238q import build,render
    rows,_,observations=inputs_for(paths.battle_id)
    observations=dict(observations,observations=rows)
    prediction=json.loads((folder/'prediction.json').read_text());result=json.loads((folder/'replay.json').read_text())
    ref=json.loads(paths.cache('event-driven/m238-live-2/reference/battle-log.json').read_text())
    data=build(prediction,result,observations,ref)
    data.update(source_prediction=RUN,status='post_reference_saved_message_reconstruction_unverified',
        validation=dict(prediction_seal=json.loads((folder/'prediction-seal.json').read_text()),
                        tests=str(folder/'tests.json')),first_slot_establishment=result['first_slot_establishment'])
    # Current receipt causes replace the Q report's historical causal diagnosis.
    by_id={h['event']['event_id']:h for h in result['history']}
    for move in data['moves']:
        record=by_id[move['id']]
        move.update(first_failure_time=None,causal_chain=[],category='partial_actor_move_admission'
            if record['application_status']=='applied_partial' else 'remaining_prefix_or_reliability_gap',
            reason=record['reason'])
    data['counts']['move_first_failure_categories']=dict(Counter(m['category'] for m in data['moves']))
    for event in data['inventory']:
        if event['origin']=='frozen_v3':event['origin']='sealed_latest_reconstruction'
    data['proposed_fixes']=['Unresolved re-entry and alias continuity remain explicit.',
        'Two recognized semantic changes are still suppressed by occurrence grouping.',
        'Unsupported message vocabulary and outcome text remain observations only.',
        'Battle Log reference covers disconnected portions of displayed turn 4; no whole-match recall claim.']
    target=ROOT/'reports/M2.3.8-trainer-opening-battle-log-v3'
    document=render(data).replace('M2.3.8-Q-event-audit','M2.3.8-trainer-opening-battle-log-v3')
    document=document.replace('M2.3.8-Q','Latest battle-message reconstruction')
    document=document.replace('First failure / causal chain','Saved replay / remaining uncertainty')
    with Path(str(target)+'.json').open('x') as stream:json.dump(data,stream,ensure_ascii=False,indent=2)
    with Path(str(target)+'.html').open('x') as stream:stream.write(document)
    manifest['completed'].append('report');manifest['status']='complete';atomic_json(manifest_path,manifest)
    print(json.dumps(data['counts'],indent=2))


if __name__=='__main__':main()
