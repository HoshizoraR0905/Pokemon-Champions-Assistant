"""Streaming-first replay CLI. Emits evidence and readiness, never gameplay events."""
import argparse
import json
from pathlib import Path
import platform
import resource
import statistics
import time

from capture import video_frames
from recognition.paddle_ocr import create_ocr
from recognition.icons import default_icons
from streaming import Limits, StreamingPipeline
from streaming.recognition import RegionBackend
from streaming.replay import cached_frames, recorded_frames, replay, acquire_at_rate
from streaming.monitoring import MonitoringRates, ROIMonitor


def distribution(values):
    if not values:
        return {'count':0,'median_seconds':None,'p95_seconds':None,'worst_seconds':None}
    values = sorted(values)
    import math
    return {'count':len(values),'median_seconds':statistics.median(values),
            'p95_seconds':values[max(0,math.ceil(.95*len(values))-1)],'worst_seconds':values[-1]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    inputs=parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--cache-manifest',type=Path)
    inputs.add_argument('--frames',type=Path)
    inputs.add_argument('--video',type=Path)
    parser.add_argument('--start',type=float)
    parser.add_argument('--end',type=float)
    parser.add_argument('--interval',type=float,help='Video decode sampling interval; defaults to 1/acquisition-fps')
    parser.add_argument('--speed',type=float,help='1=real-time-paced; omit for burst replay')
    parser.add_argument('--serial',action='store_true')
    parser.add_argument('--ocr',default='auto',choices=['auto','paddle-v6','paddle-v5','tesseract'])
    parser.add_argument('--icons',action='store_true',help='Opt in to expensive visual identity refinement')
    parser.add_argument('--no-icons',action='store_true')
    parser.add_argument('--max-inflight',type=int,default=4)
    parser.add_argument('--queue-jobs',type=int,default=64)
    parser.add_argument('--gap-threshold',type=float,default=.5)
    parser.add_argument('--readiness-target',type=float,default=1.)
    parser.add_argument('--adaptive',action='store_true')
    parser.add_argument('--acquisition-fps',type=float,default=5.)
    parser.add_argument('--phase-fps',type=float,default=2.)
    parser.add_argument('--message-fps',type=float,default=5.)
    parser.add_argument('--routine-fps',type=float,default=2.)
    parser.add_argument('--icon-fps',type=float,default=1.)
    parser.add_argument('--stable-refresh',type=float,default=2.)
    parser.add_argument('--message-ocr-fps',type=float,default=5.,help='Lower experimental budgets preserve unresolved candidate crops')
    parser.add_argument('--candidate-capacity',type=int,default=16)
    parser.add_argument('--onnx-directory',type=Path)
    parser.add_argument('--onnx-provider',choices=['cpu','coreml'],default='cpu')
    parser.add_argument('--onnx-batch-size',type=int,default=1)
    parser.add_argument('--trace',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.video and (args.start is not None or args.end is not None):
        parser.error('Use a recorded frame sequence or cache manifest for selected intervals; no sequential timestamp-offset decoding')
    rates=MonitoringRates(args.acquisition_fps,args.phase_fps,args.message_fps,
                          args.routine_fps,args.icon_fps,args.stable_refresh,
                          candidate_capacity=args.candidate_capacity,message_ocr_fps=args.message_ocr_fps)
    init=time.monotonic()
    if args.onnx_directory:
        from recognition.onnx_ocr import ONNXOCRBackend
        ocr=ONNXOCRBackend(args.onnx_directory,provider=args.onnx_provider,
                           batch_size=args.onnx_batch_size)
    else:
        ocr=create_ocr(args.ocr)
    icons=default_icons() if args.icons and not args.no_icons else None
    backend=RegionBackend(ocr,icons)
    initialized=time.monotonic()-init
    if args.cache_manifest:
        frames=cached_frames(args.cache_manifest,start=args.start,end=args.end)
    elif args.frames:
        frames=recorded_frames(args.frames,start=args.start,end=args.end)
    else:
        frames=video_frames(args.video,args.interval if args.interval is not None else 1/args.acquisition_fps)
    frames=acquire_at_rate(frames,args.acquisition_fps,
        on_gap=lambda evidence:pipeline.mark_interruption('acquisition_subsampling_at_source_end',evidence=evidence))
    monitoring = ROIMonitor(rates) if args.adaptive else None
    limits=Limits(max_inflight_frames=args.max_inflight,queue_jobs=args.queue_jobs,
                  max_capture_gap=args.gap_threshold,readiness_target_seconds=args.readiness_target)
    pipeline=StreamingPipeline(backend,asynchronous=not args.serial,icons=args.icons and not args.no_icons,limits=limits,
                               monitoring=monitoring)
    measures={k:[] for k in ['capture_to_classification','ocr','icon','recognition_availability',
                             'ordered_availability','decision_readiness','message_availability','replay_dispatch_lateness']}
    decisions=[];phases=[];messages=[];final={}
    args.trace.parent.mkdir(parents=True,exist_ok=True)
    start=time.monotonic()
    with args.trace.open('w') as output:
        def sink(row):
            nonlocal final
            output.write(json.dumps(row,ensure_ascii=False)+'\n');output.flush()
            data=row['data']
            if row['type']=='capture_update' and data.get('accepted'):
                p=data['phase_update'];phases.append({'timestamp':p['timestamp'],'phase':p['phase']})
                measures['capture_to_classification'].append(p['capture_to_classification_seconds'])
                measures['replay_dispatch_lateness'].append(p['capture_metadata']['dispatch_lateness_seconds'])
            if row['type']=='observations':
                measures['ordered_availability'].append(data['ordered_availability_seconds'])
                for obs in data['observations']:
                    if obs['category'] in {'ocr','icon'}:
                        measures[obs['category']].append(obs['recognition_seconds'])
                    measures['recognition_availability'].append(obs['availability_seconds'])
                    if obs['label']=='battle_message':messages.append(obs)
            if row['type']=='message_available':
                measures['message_availability'].append(data['message_availability_seconds'])
            if row['type']=='decision_settled':
                decisions.append(data);measures['decision_readiness'].append(data['readiness_latency_seconds'])
            if row['type']=='stream_end':final=data
        replay(frames,pipeline,sink,speed=args.speed)
    elapsed=time.monotonic()-start
    report={'schema_version':1,'environment':{'platform':platform.platform(),'machine':platform.machine(),
           'python':platform.python_version()},'mode':'serial' if args.serial else 'one_ocr_worker_plus_icon_worker',
           'replay_speed':args.speed,'initialization_seconds':initialized,'processing_seconds':elapsed,
           'peak_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
           'ocr_engine':getattr(ocr,'model_name',type(ocr).__name__),'ocr_warnings':ocr.warnings,
           'icons_available':icons is not None,'limits':vars(limits),'metrics':final.get('metrics'),
           'frames_per_second':len(phases)/elapsed,'latencies':{k:distribution(v) for k,v in measures.items()},
           'monitoring_metrics':final.get('monitoring_metrics'),
           'monitoring_rates':vars(monitoring.rates) if monitoring else None,
           'decisions':decisions,'phases':phases,'message_observations':messages,
           'final_readiness':final.get('readiness'),'diagnostics':final.get('diagnostics'),
           'coverage':'Captured replay evidence only. Sampling gaps and unresolved reads are not complete gameplay coverage.',
           'latency_semantics':'Monotonic simulated-capture time; paced dispatch lateness is separate from source-video timestamps. No phone transport measured.'}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['mode','frames_per_second','latencies','final_readiness']},indent=2))


if __name__=='__main__':
    main()
