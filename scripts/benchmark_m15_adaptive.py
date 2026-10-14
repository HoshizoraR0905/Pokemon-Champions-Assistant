"""Controlled cached-frame CPU experiments, without video decoding."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import resource
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recognition.paddle_ocr import create_ocr
from streaming import StreamingPipeline
from streaming.recognition import RegionBackend, RegionPlanner
from streaming.monitoring import ROIMonitor, MonitoringRates
from streaming.replay import recorded_frames, acquire_at_rate, replay
from battle_artifacts import BattleArtifacts, add_arguments, manifest_battle
from stream_replay import distribution

ROOT = Path(__file__).resolve().parents[1]


def trial(ocr, name, frames, *, adaptive=False, fps=5., decision_regions=False, speed=1., message_ocr_fps=5., trace_directory=None):
    monitor = ROIMonitor(MonitoringRates(acquisition_fps=fps,message_ocr_fps=message_ocr_fps)) if adaptive else None
    pipeline = StreamingPipeline(RegionBackend(ocr),icons=False,monitoring=monitor,
                                  planner=RegionPlanner(decision_regions=decision_regions))
    measures = {k:[] for k in ['classification_service','capture_to_classification','ocr',
                              'ordered_availability','message_availability','decision_completion',
                              'dispatch_lateness','worker_wait']}
    messages = []; captures=[]; decisions=[]; final={}; calls={}
    path = (trace_directory or ROOT/'reports')/f'm15opt-{name}.jsonl'
    path.parent.mkdir(parents=True,exist_ok=True)
    start = time.monotonic()
    with path.open('w') as out:
        def sink(row):
            nonlocal final
            out.write(json.dumps(row,ensure_ascii=False)+'\n')
            data = row['data']
            if row['type']=='capture_update' and data.get('accepted'):
                p=data['phase_update'];captures.append({'timestamp':p['timestamp'],'phase':p['phase']})
                measures['classification_service'].append(p['classification_seconds'])
                measures['capture_to_classification'].append(p['capture_to_classification_seconds'])
                measures['dispatch_lateness'].append(p['capture_metadata']['dispatch_lateness_seconds'])
            elif row['type']=='observations':
                measures['ordered_availability'].append(data['ordered_availability_seconds'])
                for obs in data['observations']:
                    if obs['category']=='ocr':
                        measures['ocr'].append(obs['recognition_seconds'])
                        measures['worker_wait'].append(obs['started_monotonic']-obs['capture_monotonic'])
                        calls[obs['label']]=calls.get(obs['label'],0)+1
                    if obs['label']=='battle_message':messages.append(obs)
            elif row['type']=='message_available':measures['message_availability'].append(data['message_availability_seconds'])
            elif row['type']=='decision_settled':
                decisions.append(data);measures['decision_completion'].append(data['readiness_latency_seconds'])
            elif row['type']=='stream_end':final=data
        replay(acquire_at_rate(iter(frames),fps,
            on_gap=lambda evidence:pipeline.mark_interruption('acquisition_subsampling_at_source_end',evidence=evidence)),
            pipeline,sink,speed=speed)
    wall=time.monotonic()-start
    truth=json.loads((ROOT/'tests/fixtures/m15_adaptive_ground_truth.json').read_text())['messages']
    checks=[]
    for expected in truth:
        matches=[m for m in messages if ''.join(str(m['observation'].get('value') or '').split())==''.join(expected['expected_text'].split())]
        # Reviewed points establish only their own timestamp; text elsewhere is
        # reported separately and is not a new human-labelled correctness claim.
        exact=next((m for m in matches if abs(m['timestamp']-expected['timestamp'])<1e-6),None)
        checks.append({'reviewed_timestamp':expected['timestamp'],'reviewed_frame_recognized':exact is not None,
                       'same_text_timestamps':[m['timestamp'] for m in matches]})
    return {'name':name,'backend':getattr(ocr,'model_name',type(ocr).__name__),
            'adaptive':adaptive,'decision_regions':decision_regions,'acquisition_fps':fps,
            'replay_speed':speed,'processing_seconds':wall,'throughput_fps':len(captures)/wall,
            'candidate_versions':sum(m['category']=='candidate' for m in messages),
            'service_throughput_fps':len(captures)/sum(measures['ocr']) if measures['ocr'] else None,
            'ocr_service_seconds':sum(measures['ocr']),'recognition_calls':calls,
            'latencies':{k:distribution(v) for k,v in measures.items()},
            'metrics':final['metrics'],'monitoring_metrics':final.get('monitoring_metrics'),
            'readiness':final['readiness'],'decisions':decisions,'reviewed_messages':checks,
            'phases':captures,'trace':str(path),
            'peak_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames',type=Path,default=None)
    parser.add_argument('--output',type=Path,default=None)
    parser.add_argument('--onnx-directory',type=Path)
    parser.add_argument('--provider',choices=['cpu','coreml'],default='cpu')
    parser.add_argument('--budget-only',action='store_true')
    parser.add_argument('--single-budget',action='store_true')
    parser.add_argument('--acceleration-only',action='store_true')
    parser.add_argument('--trace-directory',type=Path)
    add_arguments(parser)
    args=parser.parse_args();owner=manifest_battle(args.frames) if args.frames else 'sample_battle_1'
    paths=BattleArtifacts.select(args.battle_id,args.video,default=owner).prepare()
    args.frames=args.frames or paths.cache('m15-resolution-178-200/frames.json')
    paths.check_identity(manifest_battle(args.frames))
    args.output=paths.guard_output(args.output or paths.report('M1.5-adaptive-performance.json'))
    args.trace_directory=paths.guard_output(args.trace_directory or paths.report_dir)
    args.trace_directory.mkdir(parents=True,exist_ok=True)
    frames=list(recorded_frames(args.frames))
    start=time.monotonic()
    if args.onnx_directory:
        from recognition.onnx_ocr import ONNXOCRBackend
        ocr=ONNXOCRBackend(args.onnx_directory,provider=args.provider)
    else:ocr=create_ocr('paddle-v6')
    init=time.monotonic()-start
    from recognition import box
    ocr.read(frames[0].image,box(frames[0].image,(.22,.685,.64,.797)),multiline=True)
    report={'schema_version':1,'initialization_seconds':init,'runs':[],
            'scope':'110 existing 5fps cached frames, 22 seconds; no video decoding, no 10fps claim; one warm model, sequential trials, no icons.',
            'model_directory':str(args.onnx_directory) if args.onnx_directory else None}
    configs=[('A-baseline',False,5.,False,5.),('B-fixed2',False,2.,False,5.),
             ('C-scheduling',True,5.,False,5.),('C-integrated',True,5.,True,5.)]
    if args.budget_only:
        configs=[('C-budget',True,5.,False,2.5),('C-budget-integrated',True,5.,True,2.5)]
    if args.single_budget:
        configs=[('C-final-budget-v2',True,5.,True,2.5)]
    if args.acceleration_only:
        configs=[('D-coreml-existing',False,5.,False,5.),('E-coreml-budget',True,5.,False,2.5)]
    for name,adaptive,fps,extra,message_rate in configs:
        row=trial(ocr,name,frames,adaptive=adaptive,fps=fps,decision_regions=extra,message_ocr_fps=message_rate,
                  trace_directory=args.trace_directory)
        report['runs'].append(row)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(name,row['processing_seconds'],row['metrics']['submitted_jobs'],row['latencies']['decision_completion'],flush=True)


if __name__=='__main__':main()
