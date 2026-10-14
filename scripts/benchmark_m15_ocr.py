"""Same labelled game crops for CPU/ONNX/Core ML and batching evaluation."""
import argparse
from collections import defaultdict, Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import resource
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from capture import load_image
from recognition import box
from stream_replay import distribution
from scripts.benchmark_m12 import levenshtein

ROOT=Path(__file__).resolve().parents[1]


def cases():
    truth=json.loads((ROOT/'tests/fixtures/m12_ground_truth.json').read_text())
    groups=defaultdict(list)
    for row in truth['regions']:
        if row['kind']!='icon':groups[row['kind']].append(row)
    chosen=[]
    for kind, rows in groups.items():
        # Deterministic spread of existing annotations, not chosen by predictions.
        indices=sorted(set([0,len(rows)//3,2*len(rows)//3,len(rows)-1]))
        chosen.extend(rows[i] for i in indices)
    gold=next(r for r in groups['species_text'] if r['expected']=='赛富豪')
    if gold not in chosen:chosen.append(gold)
    result=[]
    for row in chosen:
        image=load_image(ROOT/'tests/fixtures'/row['image']).image
        assert hashlib.sha256((ROOT/'tests/fixtures'/row['image']).read_bytes()).hexdigest()==truth['images'][row['image']]['sha256']
        result.append(({**row,'multiline':False},image,tuple(row['box'])))
    for row in json.loads((ROOT/'tests/fixtures/m15_adaptive_ground_truth.json').read_text())['messages']:
        path=ROOT/row['fixture'];image=load_image(path).image
        assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
        result.append(({'image':row['fixture'],'kind':'message','expected':''.join(row['expected_text'].split()),
                        'multiline':True,'timestamp':row['timestamp']},image,box(image,(.22,.685,.64,.797))))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend',choices=['paddle','onnx'],default='paddle')
    parser.add_argument('--model-directory',type=Path)
    parser.add_argument('--provider',choices=['cpu','coreml'],default='cpu')
    parser.add_argument('--batch-size',type=int,default=1)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();dataset=cases()
    start=time.monotonic()
    if args.backend=='paddle':
        from recognition.paddle_ocr import PaddleOCRBackend
        ocr=PaddleOCRBackend()
    else:
        from recognition.onnx_ocr import ONNXOCRBackend
        ocr=ONNXOCRBackend(args.model_directory,provider=args.provider,batch_size=args.batch_size,
                           profile_prefix=ROOT/'.cache'/args.output.stem)
    initialization=time.monotonic()-start
    _,image,bounds=dataset[0];ocr.read(image,bounds)
    rows=[]
    for expected,image,bounds in dataset:
        start=time.monotonic();obs=ocr.read(image,bounds,numeric=expected['kind']=='numeric',multiline=expected['multiline'])
        elapsed=time.monotonic()-start
        text=''.join(obs.raw_text.split());want=''.join(str(expected['expected']).split())
        rows.append({**expected,'bounds':bounds,'raw_text':obs.raw_text,'accepted':obs.value,
                     'confidence':obs.confidence,'seconds':elapsed,'exact':text==want,
                     'edit_distance':levenshtein(want,text),'expected_length':len(want)})
        print(expected['kind'],str(expected['expected']),repr(obs.raw_text),round(elapsed,3),flush=True)
    metrics={}
    for kind in sorted(set(r['kind'] for r in rows)):
        group=[r for r in rows if r['kind']==kind]
        metrics[kind]={'count':len(group),'exact_accuracy':sum(r['exact'] for r in group)/len(group),
                       'cer':sum(r['edit_distance'] for r in group)/sum(r['expected_length'] for r in group),
                       'latency':distribution([r['seconds'] for r in group])}
    batching=None
    if args.backend=='onnx':
        # Batch across independent single-line regions; message line batching is
        # already measured by read(). Padding widths can change numerical output.
        singles=[(e,img[b[1]:b[3],b[0]:b[2]]) for e,img,b in dataset if not e['multiline']]
        start=time.monotonic();predicted=ocr.predict([crop for e,crop in singles]);wall=time.monotonic()-start
        batchrows=[{'expected':str(e['expected']),'predicted':p['text'],'confidence':p['confidence']} for (e,crop),p in zip(singles,predicted)]
        batching={'batch_size':args.batch_size,'regions':len(singles),'seconds':wall,
                  'regions_per_second':len(singles)/wall,'exact_accuracy':sum(''.join(r['expected'].split())==''.join(r['predicted'].split()) for r in batchrows)/len(batchrows),
                  'rows':batchrows}
    profile=None;provider_events={};device_plan={}
    if args.backend=='onnx':
        profile=ocr.end_profile()
        events=json.loads(Path(profile).read_text())
        counts=Counter();durations=Counter()
        for event in events:
            provider=event.get('args',{}).get('provider')
            if provider:
                counts[provider]+=1;durations[provider]+=event['dur']/1e6
        provider_events={'counts':dict(counts),'seconds':dict(durations)}
    service=sum(r['seconds'] for r in rows)
    report={'schema_version':1,'backend':ocr.model_name,'requested_provider':args.provider,
            'active_providers':getattr(ocr,'active_providers',None),'initialization_seconds':initialization,
            'batch_size':args.batch_size,'single_region_calls':len(rows),'service_seconds':service,
            'regions_per_second':len(rows)/service,'latency':distribution([r['seconds'] for r in rows]),
            'peak_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'metrics':metrics,'rows':rows,'cross_region_batch':batching,'profile_file':profile,
            'provider_events':provider_events,
            'model_manifest':json.loads((args.model_directory/'local-manifest.json').read_text()) if args.model_directory else None,
            'limitations':['Small deterministic development subset, not a holdout corpus.','One warm trial; initialization/cache policy differs by runtime.','Provider assignment alone is not proof of GPU/ANE dispatch.','RSS is process-wide high-water mark, not incremental model memory.']}
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('SUMMARY',service,metrics,provider_events,flush=True)


if __name__=='__main__':main()
