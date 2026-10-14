"""Small fixed B1 experiments; no full-battle recognition or state replay."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import resource
import sys
import time
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.validate_m233b1 import CachedMessageOCR,source_identity,battle_lock,choose
from recognition.video_sampling import SamplingConfig,acquire,atomic_json,fingerprint
from recognition.message_selection import MessageSelector,SelectionConfig
from recognition.phases import classify_phase
from battle_artifacts import BattleArtifacts

POLICIES=['baseline','reduced','temporal','hybrid']
INTERVALS={'sample_battle_0':(408,416),'sample_battle_1':(214,230)}


def contacts(rows,path):
    for offset in range(0,len(rows),36):
        group=rows[offset:offset+36];sheet=np.full((12*125,3*600,3),245,np.uint8)
        for j,r in enumerate(group):
            im=cv2.imread(str(ROOT/r['image']));h,w=im.shape[:2]
            crop=cv2.resize(im[int(.64*h):int(.85*h),int(.18*w):int(.86*w)],(600,100))
            y=j//3*125;x=j%3*600;sheet[y:y+100,x:x+600]=crop
            cv2.putText(sheet,f"{offset+j}: {r['timestamp']:.6f}s",(x+4,y+119),cv2.FONT_HERSHEY_SIMPLEX,.46,(0,0,0),1)
        target=path.parent/(path.stem+f'-{offset//36:02d}.jpg');cv2.imwrite(str(target),sheet)


def evaluation_key(paths):
    inputs=[ROOT/'.cache/m15-onnx-medium/local-manifest.json',ROOT/'recognition/message_selection.py',ROOT/'recognition/phases.py',
        ROOT/'recognition/onnx_ocr.py',ROOT/'tests/fixtures/battles/m233b1_selection_diagnostics.json']
    acquisition=paths.cache('m233b1/experiment/acquisition.json')
    if acquisition.exists():inputs.append(acquisition)
    return fingerprint(dict(ocr_contract='cpu/batch1/multiline; unchanged backend.read ROI',configs=[SelectionConfig(policy=p).__dict__ for p in POLICIES],
        files={str(p.relative_to(ROOT)):__import__('hashlib').sha256(p.read_bytes()).hexdigest() for p in inputs}))


def seal_results():
    """Verify saved decisions before preserving the first measured cost record."""
    import hashlib
    diagnostics=json.loads((ROOT/'tests/fixtures/battles/m233b1_selection_diagnostics.json').read_text())['frames']
    for bid in ['sample_battle_0','sample_battle_1','sample_battle_2','sample_battle_4']:
        paths=BattleArtifacts(bid);target=paths.cache('m233b1/experiment/results.json')
        result=json.loads(target.read_text())
        for policy in POLICIES:
            counts=Counter()
            for row in [r for r in diagnostics if r['battle_id']==bid]:
                decision=MessageSelector(SelectionConfig(policy=policy)).select(cv2.imread(str(ROOT/row['image'])),row['phase'],timestamp=row['timestamp'])
                if decision['selected']:counts[row['label']]+=1
            assert dict(counts)==result['diagnostic'][policy]['selected_by_label']
        if bid in INTERVALS:
            acquired=json.loads(paths.cache('m233b1/experiment/acquisition.json').read_text())
            phases={r['sha256']:r['phase'] for r in acquired['unique_frames']}
            for rate,frames in acquired['schedules'].items():
                for policy in POLICIES:
                    rows,_=choose([dict(r,phase=phases[r['sha256']]) for r in frames],SelectionConfig(policy=policy))
                    assert [r['selection']['selected'] for r in rows]==[r['selected'] for r in result['schedules'][rate][policy]['selection']]
        atomic_json(target.parent/'results-manifest.json',dict(status='complete',input_hash=evaluation_key(paths),
            output_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),measurement='first completed scoped evaluation; preserved across warm resumes'))
        print(bid,'saved decisions verified; original cost measurements preserved',flush=True)


def prepare():
    for bid,(start,end) in INTERVALS.items():
        paths=BattleArtifacts(bid);identity=source_identity(paths);target=paths.cache('m233b1/experiment/acquisition.json')
        if target.exists():
            prior=json.loads(target.read_text())
            if prior.get('video_fingerprint')==identity and prior.get('interval')==[start,end] and all(
                (ROOT/r['image']).is_file() and __import__('hashlib').sha256((ROOT/r['image']).read_bytes()).hexdigest()==r['sha256'] for r in prior['unique_frames']):
                print(bid,'reused complete acquisition experiment',flush=True);continue
        schedules={};timings={};unique={}
        with battle_lock(paths):
            for rate in [.5,1,2,3]:
                began=time.perf_counter();rows=acquire(paths,identity,SamplingConfig(rate),start,end)
                timings[str(rate)]=time.perf_counter()-began;schedules[str(rate)]=rows
                for r in rows:unique.setdefault(r['sha256'],r)
            rows=sorted(unique.values(),key=lambda r:r['timestamp'])
            for row in rows:row['phase']=classify_phase(cv2.imread(str(ROOT/row['image'])))[0]
            atomic_json(target,dict(battle_id=bid,interval=[start,end],video_fingerprint=identity,
                schedules=schedules,unique_frames=rows,acquisition_seconds=timings,
                process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)))
            contacts(rows,target.parent/'inspection.jpg')
            print(bid,'unique',len(rows),'schedules',{k:len(v) for k,v in schedules.items()},'seconds',timings,flush=True)


def evaluate():
    diagnostics=json.loads((ROOT/'tests/fixtures/battles/m233b1_selection_diagnostics.json').read_text())['frames']
    labels_path=ROOT/'tests/fixtures/battles/m233b1_interval_labels.json'
    labels=json.loads(labels_path.read_text()) if labels_path.exists() else {}
    for bid in ['sample_battle_0','sample_battle_1','sample_battle_2','sample_battle_4']:
        paths=BattleArtifacts(bid);identity=source_identity(paths)
        target=paths.cache('m233b1/experiment/results.json');manifest=target.parent/'results-manifest.json'
        if target.exists() and manifest.exists():
            saved=json.loads(manifest.read_text())
            if saved.get('input_hash')==evaluation_key(paths) and saved.get('output_sha256')==__import__('hashlib').sha256(target.read_bytes()).hexdigest():
                print(bid,'reused completed OCR experiment; zero new calls',flush=True);continue
        ocr=CachedMessageOCR(paths,identity)
        result=dict(battle_id=bid,diagnostic={},schedules={},ocr_outcomes=[],process_peak_rss_bytes=None)
        with battle_lock(paths):
            # Isolated diagnostic images deliberately reset temporal state; repeated controls are tested below.
            for policy in POLICIES:
                counts=Counter();selected=[];actual_before=deepcopy(ocr.counts);started=time.perf_counter()
                for row in [r for r in diagnostics if r['battle_id']==bid]:
                    im=cv2.imread(str(ROOT/row['image']));selector=MessageSelector(SelectionConfig(policy=policy))
                    decision=selector.select(im,row['phase'],timestamp=row['timestamp'])
                    if decision['selected']:
                        counts[row['label']]+=1;value,reuse=ocr.read(row,im)
                        selected.append(dict(timestamp=row['timestamp'],label=row['label'],expected_token=row['expected_token'],message=value,ocr_reuse=reuse))
                result['diagnostic'][policy]=dict(selected_by_label=dict(counts),selected=selected,
                    actual_new_read_calls=ocr.counts['new_read_calls']-actual_before['new_read_calls'],seconds=time.perf_counter()-started)
            if bid in INTERVALS:
                acquisition=json.loads(paths.cache('m233b1/experiment/acquisition.json').read_text())
                phases={r['sha256']:r['phase'] for r in acquisition['unique_frames']}
                for rate,frames in acquisition['schedules'].items():
                    result['schedules'][rate]={}
                    for policy in POLICIES:
                        ordered=[dict(r,phase=phases[r['sha256']]) for r in frames]
                        rows,selection_time=choose(ordered,SelectionConfig(policy=policy))
                        selected=[r for r in rows if r['selection']['selected']];before=deepcopy(ocr.counts);started=time.perf_counter();keys=[];messages=[]
                        for r in selected:
                            im=cv2.imread(str(ROOT/r['image']));key=ocr.key(im);keys.append(key)
                            value,reuse=ocr.read(r,im)
                            messages.append(dict(timestamp=r['timestamp'],sha256=r['sha256'],message=value,ocr_reuse=reuse))
                        result['schedules'][rate][policy]=dict(frames_acquired=len(rows),ocr_candidates=len(selected),
                            unique_crop_requests=len(set(keys)),duplicated_crop_requests=len(keys)-len(set(keys)),
                            actual_new_read_calls=ocr.counts['new_read_calls']-before['new_read_calls'],
                            selection_seconds=selection_time,ocr_wall_seconds=time.perf_counter()-started,messages=messages,
                            selection=[dict(timestamp=r['timestamp'],sha256=r['sha256'],**r['selection']) for r in rows])
                result['acquisition']=dict(seconds=acquisition['acquisition_seconds'],interval=acquisition['interval'],unique_source_frames=len(acquisition['unique_frames']))
            result['ocr_counts']=ocr.counts;result['ocr_configuration']=ocr.config
            result['process_peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
            atomic_json(paths.cache('m233b1/experiment/results.json'),result)
            print(bid,json.dumps(ocr.counts),flush=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=['prepare','evaluate','checkpoint'],required=True)
    args=parser.parse_args()
    if args.stage=='prepare':prepare()
    elif args.stage=='checkpoint':seal_results()
    else:
        evaluate();seal_results()
