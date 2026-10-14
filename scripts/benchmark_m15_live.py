"""Threaded live-adapter stress test using cached frames as a fake camera.

No phone or video decoding. Source timestamps remain cached video time while
capture monotonic clocks are actual acquisition, not simulated deadlines.
"""
import json
import argparse
from pathlib import Path
import resource
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recognition import box
from recognition.paddle_ocr import create_ocr
from streaming import StreamingPipeline
from streaming.recognition import RegionBackend
from streaming.monitoring import ROIMonitor, MonitoringRates
from streaming.replay import recorded_frames
from streaming.live import run_live
from stream_replay import distribution

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace',type=Path,default=ROOT/'reports/m15live-cached-camera-v2.jsonl')
    parser.add_argument('--output',type=Path,default=ROOT/'reports/M1.5-live-adapter-v2.json')
    args=parser.parse_args()
    frames=list(recorded_frames(ROOT/'.cache/m15-resolution-178-200/frames.json'))
    source=iter(frames)
    ocr=create_ocr('paddle-v6')
    ocr.read(frames[0].image,box(frames[0].image,(.22,.685,.64,.797)),multiline=True)
    rates=MonitoringRates(message_ocr_fps=2.5)
    p=StreamingPipeline(RegionBackend(ocr),monitoring=ROIMonitor(rates),icons=False)
    measures={k:[] for k in ['decision_completion','ordered_availability','message_availability','dispatch_lateness']}
    acquired=[];accepted=[];messages=[];final={};capture_metrics={}
    path=args.trace
    path.parent.mkdir(parents=True,exist_ok=True)
    start=time.monotonic()
    with path.open('w') as output:
        def sink(row):
            nonlocal final,capture_metrics
            output.write(json.dumps(row,ensure_ascii=False)+'\n')
            d=row['data']
            if row['type']=='capture_monitor':acquired.append(d['capture_monotonic'])
            elif row['type']=='capture_update' and d.get('accepted'):
                accepted.append(d['phase_update']['timestamp'])
                measures['dispatch_lateness'].append(d['phase_update']['capture_metadata']['dispatch_lateness_seconds'])
            elif row['type']=='observations':measures['ordered_availability'].append(d['ordered_availability_seconds'])
            elif row['type']=='message_available':
                messages.append(d);measures['message_availability'].append(d['message_availability_seconds'])
            elif row['type']=='decision_settled':measures['decision_completion'].append(d['readiness_latency_seconds'])
            elif row['type']=='stream_end':final=d
            elif row['type']=='live_capture_end':capture_metrics=d
        run_live(lambda:next(source,None),p,sink,rates=rates,capacity=4)
    wall=time.monotonic()-start
    report={'schema_version':1,'scope':'Real-clock threaded adapter stress test with preloaded cached fake-camera frames, not live phone capture; no video decoding.',
            'configured_acquisition_fps':rates.acquisition_fps,'actual_acquisition_fps':(len(acquired)-1)/(acquired[-1]-acquired[0]) if len(acquired)>1 else None,
            'processing_seconds':wall,'accepted_frame_throughput_fps':len(accepted)/wall,
            'capture_metrics':capture_metrics,'recognition_metrics':final['metrics'],
            'latencies':{k:distribution(v) for k,v in measures.items()},
            'final_readiness':final['readiness'],'peak_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'trace':str(path)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
