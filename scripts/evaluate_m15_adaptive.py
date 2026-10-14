"""Audit adaptive experiment evidence and detector workload without OCR."""
import base64
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from streaming.monitoring import ROIMonitor
from streaming.replay import recorded_frames
from stream_replay import distribution

ROOT=Path(__file__).resolve().parents[1]


def main():
    truth=json.loads((ROOT/'tests/fixtures/m15_adaptive_ground_truth.json').read_text())['messages']
    for gold in truth:
        assert hashlib.sha256((ROOT/gold['fixture']).read_bytes()).hexdigest()==gold['sha256']
    runs=[]
    for path in sorted((ROOT/'reports').glob('m15opt-*.jsonl')):
        rows=[json.loads(l) for l in path.read_text().splitlines()]
        bundles=[r['data'] for r in rows if r['type']=='observations']
        captures=[r['data']['phase_update'] for r in rows if r['type']=='capture_update' and r['data'].get('accepted')]
        assert [b['capture_sequence'] for b in bundles]==list(range(len(captures)))
        messages=[o for b in bundles for o in b['observations'] if o['label']=='battle_message']
        assert [o['timestamp'] for o in messages]==sorted(o['timestamp'] for o in messages)
        assert len({m['observation_id'] for m in messages})==len(messages)
        lane=[r['data'] for r in rows if r['type']=='message_available']
        assert [m['observation_id'] for m in lane]==[m['observation_id'] for m in messages]
        checks=[]
        for gold in truth:
            normalized=''.join(gold['expected_text'].split())
            found=[m for m in messages if ''.join(str(m['observation'].get('value') or '').split())==normalized]
            checks.append({'reviewed_timestamp':gold['timestamp'],'reviewed_text':normalized,
                           'exact_reviewed_point_recognized':any(abs(m['timestamp']-gold['timestamp'])<1e-6 for m in found),
                           'text_inventory_found':bool(found),'matching_ocr_timestamps':[m['timestamp'] for m in found]})
        candidates=[c for b in bundles for c in b.get('candidate_evidence',[])]
        for c in candidates:
            crop=cv2.imdecode(np.frombuffer(base64.b64decode(c['png_base64']),np.uint8),cv2.IMREAD_COLOR)
            assert hashlib.sha256(crop.tobytes()).hexdigest()==c['sha256']
        final=rows[-1]['data'];assert rows[-1]['type']=='stream_end'
        assert final['metrics']['submitted_jobs']==final['metrics']['completed_jobs']
        assert final['readiness']['status']=='uncertain' and final['readiness']['pending_jobs']==0
        decisions=[r['data'] for r in rows if r['type']=='decision_settled']
        runs.append({'trace':str(path.relative_to(ROOT)),'trace_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                     'captured_frames':len(captures),'message_lane_entries':len(lane),
                     'candidate_crops_verified':len(candidates),'reviewed_text_checks':checks,
                     'recognized_reviewed_points':sum(c['exact_reviewed_point_recognized'] for c in checks),
                     'reviewed_text_inventory_found':sum(c['text_inventory_found'] for c in checks),
                     'decision_timestamps':[d['timestamp'] for d in decisions],
                     'phase_counts':dict(Counter(c['phase'] for c in captures)),
                     'final_readiness':final['readiness']})
    monitor=ROIMonitor();timings=[]
    for frame in recorded_frames(ROOT/'.cache/m15-resolution-178-200/frames.json'):
        started=time.monotonic();monitor.inspect(frame);timings.append(time.monotonic()-started)
    report={'schema_version':1,'annotation_scope':'Five visible message text points, development clip only. Inventory coverage is not exhaustive message recall or a new timestamp annotation.',
            'method':'Saved-trace ordering, candidate PNG roundtrip/checksum audit, and standalone ROI monitor timing; no OCR and no video decoding.',
            'runs':runs,'standalone_roi_monitor_latency':distribution(timings),
            'standalone_roi_monitor_metrics':monitor.metrics,'opencv_threads':cv2.getNumThreads()}
    live_path=ROOT/'reports/m15live-cached-camera-v2.jsonl'
    if live_path.exists():
        live=[json.loads(line) for line in live_path.read_text().splitlines()]
        captures={r['data']['frame_index']:r['data'] for r in live if r['type']=='capture_monitor'}
        bundles=[r['data'] for r in live if r['type']=='observations']
        source_candidates=[r['data'] for r in live if r['type']=='capture_candidate']
        for c in source_candidates:
            crop=cv2.imdecode(np.frombuffer(base64.b64decode(c['png_base64']),np.uint8),cv2.IMREAD_COLOR)
            assert hashlib.sha256(crop.tobytes()).hexdigest()==c['sha256']
        for bundle in bundles:
            assert bundle['capture_monotonic']==captures[bundle['frame_index']]['capture_monotonic']
        assert [b['capture_sequence'] for b in bundles]==list(range(len(bundles)))
        recognized=[o for b in bundles for o in b['observations'] if o['label']=='battle_message' and o['category']=='ocr']
        inventory=[any(''.join(str(m['observation'].get('value') or '').split())==''.join(gold['expected_text'].split()) for m in recognized) for gold in truth]
        source_message_ids={c['frame_index'] for c in source_candidates if c['label']=='message'}
        assert source_message_ids==set(captures)
        assert {c['frame_index'] for c in source_candidates if c['label']=='controls'}==set(captures)
        report['live_adapter_audit']={'acquired_frames':len(captures),'ordered_bundles':len(bundles),
            'source_roi_crops_verified':len(source_candidates),'source_message_candidates':len(source_message_ids),
            'reviewed_text_inventory_found':sum(inventory),'real_capture_clocks_preserved':True,
            'scope':'Fake-camera stress test; candidate crops prove retained pixels, not successful recognition of every message.'}
    (ROOT/'reports/M1.5-adaptive-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print([(r['trace'],r['captured_frames'],r['recognized_reviewed_points'],r['reviewed_text_inventory_found'],r['candidate_crops_verified']) for r in runs])


if __name__=='__main__':main()
