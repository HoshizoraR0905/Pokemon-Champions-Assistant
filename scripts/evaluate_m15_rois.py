"""Focused 5fps/3fps ROI detection experiment. No OCR or video decoding."""
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
from capture import load_image,Frame
from recognition import box
from recognition.phases import classify_phase
from streaming.replay import recorded_frames,cached_frames,acquire_at_rate
from streaming.roi_experiment import FocusedROIMonitor,PROVENANCE,fields_for,anchored_text
from stream_replay import distribution

ROOT=Path(__file__).resolve().parents[1]


def evaluate(name,frames,interval_kind):
    monitor=FocusedROIMonitor();counts=defaultdict(Counter);components=defaultdict(Counter)
    records=[];times=[]
    trace=ROOT/'reports'/f'm15roi-{name}.jsonl'
    with trace.open('w') as output:
        for frame in frames:
            phase=classify_phase(frame.image)[0]
            started=time.monotonic();row=monitor.inspect(frame,phase);times.append(time.monotonic()-started)
            row['capture_metadata']=frame.metadata
            row['image_sha256']=hashlib.sha256(frame.image.tobytes()).hexdigest()
            output.write(json.dumps(row,ensure_ascii=False)+'\n');records.append(row)
            for roi in row['roi_observations']:
                c=counts[roi['label']];c['observations']+=1;c['visible_samples']+=roi['visibility']!='exit'
                c[roi['visibility']]+=1
                for key in ['raw_trigger','proposal_trigger','conservative_trigger','raw_only_ambiguity']:
                    c[key]+=bool(roi.get(key))
                c['bar_only_intermediate_candidates']+=roi.get('observation_kind')=='bar_intermediate_or_display_change' and roi['visibility']!='entry'
                for field in roi['components']:
                    components[roi['label']][field['label']]+=field['changed']
    return {'name':name,'frame_count':len(records),'sampling':interval_kind,
            'timestamps':[r['timestamp'] for r in records],
            'phase_counts':dict(Counter(r['phase'] for r in records)),
            'rois':{k:{**dict(v),'component_triggers':dict(components[k])} for k,v in counts.items()},
            'detector_service':distribution(times),'trace':str(trace.relative_to(ROOT))},records


def overlays():
    examples=[('hud','tests/fixtures/battle_screen.png'),('moves','reports/M1.4-evidence/m14_boundary_268.jpg'),
              ('party','reports/M1.4-evidence/m14_boundary_270.jpg'),('replacement','reports/M1.4-evidence/m14_boundary_280.jpg'),
              ('targets','tests/fixtures/m14_target_selection_380.png'),('messages','tests/fixtures/m15_message_move.png')]
    directory=ROOT/'reports/M1.5-roi-evidence';directory.mkdir(exist_ok=True)
    evidence=[]
    for label,relative in examples:
        path=ROOT/relative;frame=load_image(path);image=frame.image.copy();phase=classify_phase(image)[0]
        groups=fields_for(image,phase)
        for name,profile in groups.items():
            if name=='messages' and label!='messages':continue
            roi=box(image,profile['envelope']);x1,y1,x2,y2=roi
            cv2.rectangle(image,(x1,y1),(x2,y2),(0,255,255),max(1,image.shape[1]//655))
            cv2.putText(image,name,(x1,max(12,y1-3)),cv2.FONT_HERSHEY_SIMPLEX,
                        max(.3,image.shape[1]/2622), (0,255,255),1,cv2.LINE_AA)
            for field,rect,mode in profile['fields']:
                ax,ay,bx,by=box(image,rect)
                cv2.rectangle(image,(ax,ay),(bx,by),(255,200,0),1)
        dest=directory/(label+'.png');cv2.imwrite(str(dest),image)
        evidence.append({'source':relative,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                         'source_resolution':[frame.image.shape[1],frame.image.shape[0]],'phase':phase,
                         'overlay':str(dest.relative_to(ROOT)),
                         'groups':{k:{'normalized_roi':p['envelope'],'pixel_roi':box(frame.image,p['envelope']),
                             'fields':[{'label':n,'normalized_roi':r,'pixel_roi':box(frame.image,r),'mode':m} for n,r,m in p['fields']]}
                                   for k,p in groups.items()}})
    return evidence


def main():
    clip=list(recorded_frames(ROOT/'.cache/m15-resolution-178-200/frames.json'))
    datasets=[('resolution-5fps',clip,'Original cached 5fps grid, timestamp uncertainty 0.2s.'),
              ('resolution-3fps',list(acquire_at_rate(iter(clip),3.)), '3fps deadline thinning of a 5fps grid; intervals 0.2/0.4s, not native 3fps capture.'),
              ('move-window',list(cached_frames(ROOT/'.cache/m14-phases/sample_battle_1/manifest.json',start=130,end=150)), 'Existing sparse approximately 2-second samples, not 3fps.'),
              ('party-workflow',list(cached_frames(ROOT/'.cache/m14-phases/sample_battle_1/manifest.json',start=267,end=284)), 'Existing sparse approximately 2-second samples, not 3fps.'),
              ('target-window',list(cached_frames(ROOT/'.cache/m14-phases/sample_battle/manifest.json',start=376,end=384)), 'Existing sparse approximately 2-second samples, not 3fps.')]
    results=[];records={}
    for name,frames,sampling in datasets:
        result,rows=evaluate(name,frames,sampling);results.append(result);records[name]=rows
    truth=json.loads((ROOT/'tests/fixtures/m15_adaptive_ground_truth.json').read_text())['messages']
    message_checks=[]
    for gold in truth:
        frame=load_image(ROOT/gold['fixture']);assert hashlib.sha256((ROOT/gold['fixture']).read_bytes()).hexdigest()==gold['sha256']
        for name in ['resolution-5fps','resolution-3fps']:
            exact=next((r for r in records[name] if abs(r['timestamp']-gold['timestamp'])<1e-6),None)
            message=next((o for o in exact['roi_observations'] if o['label']=='messages'),None) if exact else None
            # This measures detection at annotated points, not OCR or all message recall.
            message_checks.append({'dataset':name,'reviewed_timestamp':gold['timestamp'],
                'sample_present':exact is not None,'proposal_trigger':message['proposal_trigger'] if message else None,
                'fallback_trigger':message['conservative_trigger'] if message else None,
                'expected_text':gold['expected_text']})
    workflow=[]
    monitor=FocusedROIMonitor()
    for second in [268,270,280,282]:
        frame=load_image(ROOT/f'reports/M1.4-evidence/m14_boundary_{second}.jpg')
        frame.source='reviewed-workflow';frame.index=second;frame.timestamp=float(second)
        row=monitor.inspect(frame);workflow.append(row)
    checks=[]
    for second,label,visibility in [(268,'move_controls','entry'),(270,'party_list','entry'),
                                    (280,'replacement_controls','entry'),(282,'party_list','exit'),
                                    (282,'replacement_controls','exit')]:
        row=next(r for r in workflow if r['timestamp']==second)
        found=next((r for r in row['roi_observations'] if r['label']==label and r['visibility']==visibility),None)
        checks.append({'timestamp':second,'roi':label,'visibility':visibility,
                       'preserved':bool(found and found['proposal_trigger'] and found['conservative_trigger'])})
    assert all(c['preserved'] for c in checks)
    target_checks=[]
    for name in ['m14_target_selection_380.png','m14_target_selection_660.png']:
        frame=load_image(ROOT/'tests/fixtures'/name);frame.timestamp=0.
        row=FocusedROIMonitor().inspect(frame)
        target=next(r for r in row['roi_observations'] if r['label']=='target_controls')
        assert len(target['components'])==11  # four name/HP pairs, two banner anchors, residual
        target_checks.append({'fixture':name,'phase':row['phase'],'entry_preserved':target['proposal_trigger'],
                              'field_count':len(target['components'])})
    dense_target_checks=[]
    # Visually reviewed cached frames: 188.6 is arena animation, 195.2/198.8
    # show real target cards with left/right selected-move banners respectively.
    for second,label in [(195.2,'left_banner_target_cards'),(198.8,'right_banner_target_cards')]:
        for name in ['resolution-5fps','resolution-3fps']:
            row=next((r for r in records[name] if second-1e-6<=r['timestamp']<=second+.21 and
                      any(o['label']=='target_controls' and o['visibility']!='exit' for o in r['roi_observations'])),None)
            target=next((o for o in row['roi_observations'] if o['label']=='target_controls'),None) if row else None
            dense_target_checks.append({'dataset':name,'reviewed_timestamp':second,'ui':label,
                'observed_timestamp':row['timestamp'] if row else None,
                'sampling_delay_seconds':round(row['timestamp']-second,3) if row else None,
                'proposal_trigger':target['proposal_trigger'] if target else None})
    report={'schema_version':1,'date':'2026-10-14','method':'Focused ROI visual fingerprints; no OCR/model calls, no video decoding, no changes to production scheduling.',
            'fallback':'Existing raw-pixel conservative detection remains authoritative. Foreground signatures are experimental and never used to discard evidence.',
            'roi_provenance':PROVENANCE,'evidence':overlays(),'datasets':results,
            'reviewed_message_points':message_checks,'reviewed_workflow_checks':checks,
            'reviewed_workflow_observations':workflow,'target_checks':target_checks,
            'dense_reviewed_target_checks':dense_target_checks,
            'known_classifier_false_positive':{'timestamp':188.6,'cached_image':'.cache/m15-resolution-178-200/000054.png',
                'visual_review':'Arena animation, not target UI; existing classifier produces move_target_selection. No classifier changes made.',
                'consequence':'Raw trigger counts include candidate classifications, not all confirmed UI instances.'},
            'limitations':['Sparse M1.4 samples do not measure short transient recall at 3fps.',
                           'Five message points are not exhaustive recall or a holdout corpus.',
                           'No labelled active-HUD ailment change or continuous HP-bar animation exists in the dense development clip.',
                           'Foreground equality does not prove equal text; faint/typewriter/occluded/consecutive messages retain raw fallback.',
                           'Timing excludes phase classification and OCR; it is not processing completion latency.']}
    (ROOT/'reports/M1.5-focused-rois.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print([(r['name'],r['frame_count'],{k:(v['raw_trigger'],v['proposal_trigger']) for k,v in r['rois'].items()}) for r in results])


if __name__=='__main__':main()
