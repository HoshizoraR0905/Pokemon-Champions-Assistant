"""Actual serial/worker timing on the same streaming path and selected real video frames."""
from pathlib import Path
import json
import platform
import resource
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from capture import load_image
from recognition.paddle_ocr import create_ocr
from recognition.icons import default_icons
from streaming import StreamingPipeline, Limits
from streaming.recognition import RegionBackend
from streaming.replay import recorded_frames, replay
from battle_artifacts import BattleArtifacts, add_arguments, manifest_battle
from stream_replay import distribution

ROOT=Path(__file__).resolve().parents[1]


def normalized(text):
    return ''.join((text or '').split())


def run(backend,name,serial,speed,manifest):
    pipeline=StreamingPipeline(backend,asynchronous=not serial,icons=backend.icons is not None,
                              limits=Limits(max_inflight_frames=4,queue_jobs=64))
    samples={k:[] for k in ['capture_to_classification','ocr','icon','recognition_availability',
                           'ordered_availability','decision_readiness','replay_dispatch_lateness']}
    phases=[];messages=[];decisions=[];final={}
    path=BattleArtifacts(manifest_battle(manifest)).prepare().report(f'm15-{name}.jsonl')
    began=time.monotonic()
    with path.open('w') as output:
        def sink(row):
            nonlocal final
            output.write(json.dumps(row,ensure_ascii=False)+'\n');output.flush()
            d=row['data']
            if row['type']=='capture_update' and d.get('accepted'):
                p=d['phase_update'];phases.append({'timestamp':p['timestamp'],'phase':p['phase']})
                samples['capture_to_classification'].append(p['capture_to_classification_seconds'])
                samples['replay_dispatch_lateness'].append(p['capture_metadata']['dispatch_lateness_seconds'])
            elif row['type']=='observations':
                samples['ordered_availability'].append(d['ordered_availability_seconds'])
                for o in d['observations']:
                    samples[o['category']].append(o['recognition_seconds'])
                    samples['recognition_availability'].append(o['availability_seconds'])
                    if o['label']=='battle_message':messages.append(o)
            elif row['type']=='decision_settled':
                decisions.append(d);samples['decision_readiness'].append(d['readiness_latency_seconds'])
            elif row['type']=='stream_end':final=d
        replay(recorded_frames(manifest),pipeline,sink,speed=speed)
    elapsed=time.monotonic()-began
    truth=json.loads((ROOT/'tests/fixtures/m15_message_ground_truth.json').read_text())
    message_checks=[]
    for expected in truth['messages']:
        nearest=min(messages,key=lambda o:abs(o['timestamp']-expected['timestamp']))
        obs=nearest['observation']
        message_checks.append({**expected,'observed_timestamp':nearest['timestamp'],
                               'predicted':obs.get('value'),'raw_text':obs.get('raw_text'),
                               'confidence':obs.get('confidence'),
                               'exact_accepted_match':normalized(obs.get('value'))==normalized(expected['expected_text'])})
    row={'name':name,'serial':serial,'replay_speed':speed,'processing_seconds':elapsed,
         'trace':str(path.relative_to(ROOT)),'frames_per_second':len(phases)/elapsed,
         'latencies':{k:distribution(v) for k,v in samples.items()},'decisions':decisions,
         'metrics':final['metrics'],'final_readiness':final['readiness'],
         'diagnostics':final['diagnostics'],'message_checks':message_checks,'phase_samples':phases,
         'peak_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    print(name,round(elapsed,3),'seconds',row['metrics'],'decision',row['latencies']['decision_readiness'],flush=True)
    return row


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames',type=Path,default=None)
    parser.add_argument('--output',type=Path,default=None)
    add_arguments(parser)
    args=parser.parse_args();owner=manifest_battle(args.frames) if args.frames else 'sample_battle_1'
    paths=BattleArtifacts.select(args.battle_id,args.video,default=owner).prepare()
    args.frames=args.frames or paths.cache('m15-resolution-178-200/frames.json')
    paths.check_identity(manifest_battle(args.frames))
    args.output=paths.guard_output(args.output or paths.report('M1.5-performance.json'))
    began=time.monotonic()
    ocr=create_ocr('paddle-v6');icons=default_icons();backend=RegionBackend(ocr,icons)
    initialization=time.monotonic()-began
    # Equal warm-model/cache policy for every trial; no model replication.
    image=load_image(ROOT/'tests/fixtures/battle_message.png').image
    from recognition import box
    ocr.read(image,box(image,(.22,.685,.64,.797)),multiline=True)
    if icons:
        battle=load_image(ROOT/'tests/fixtures/battle_screen.png').image
        icons.identify(battle,box(battle,(.084,.854,.135,.959)))
    runs=[]
    for name,serial,speed in [('serial-burst',True,None),('workers-burst',False,None),('workers-paced',False,1.)]:
        runs.append(run(backend,name,serial,speed,args.frames))
        args.output.write_text(json.dumps({'schema_version':1,'runs':runs},ensure_ascii=False,indent=2)+'\n')
    report={'schema_version':1,'environment':{'platform':platform.platform(),'python':platform.python_version(),
        'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),
        'memory_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))},
        'initialization_seconds':initialization,'ocr_model':ocr.model_name,'ocr_cpu_threads':4,
        'icons_available':icons is not None,'model_instances':1,'input_manifest':str(args.frames),
        'source_interval_seconds':[178.,200.],'capture_sampling_fps':5.,
        'method':'Sequential trials with one shared warm OCR model and icon cache; no video decoding during replay. Timing order/cache warming is a limitation.',
        'latency_semantics':'Monotonic simulated capture to collector availability; paced dispatch lateness is separately measured. No phone transport measurement.',
        'runs':runs,'limitations':['Only one 22-second development clip, not production live capture.',
          'Two manually transcribed message points do not establish full message recall.',
          'Nearest-rank P95 is descriptive; decision sample size is small.',
          'Source timestamps use a resampled 5fps grid with 0.2s uncertainty, not original frame PTS.',
          'Peak RSS is process-wide high-water mark including the reused OCR model and icon banks.']}
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
