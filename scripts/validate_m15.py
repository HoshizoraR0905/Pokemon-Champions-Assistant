"""Audit saved M1.5 evidence without decoding video or running OCR."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stream_replay import distribution


def main():
    truth = json.loads((ROOT/'tests/fixtures/m15_message_ground_truth.json').read_text())['messages']
    for message in truth:
        assert hashlib.sha256((ROOT/message['fixture']).read_bytes()).hexdigest() == message['sha256']
    runs = []
    paths = sorted((ROOT/'reports').glob('m15-*.jsonl'))
    assert len(paths) == 4
    for path in paths:
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        bundles = [r['data'] for r in rows if r['type']=='observations']
        assert [b['capture_sequence'] for b in bundles] == list(range(110))
        observations = [o for b in bundles for o in b['observations']]
        messages = [o for o in observations if o['label']=='battle_message']
        assert [m['timestamp'] for m in messages] == sorted(m['timestamp'] for m in messages)
        assert len({m['observation_id'] for m in messages}) == len(messages)
        checks = []
        for expected in truth:
            found = next(m for m in messages if m['timestamp']==expected['timestamp'])
            assert ''.join(found['observation']['value'].split()) == ''.join(expected['expected_text'].split())
            checks.append({'timestamp':found['timestamp'], 'observation_id':found['observation_id'], 'exact_match':True})
        lane = [r['data'] for r in rows if r['type']=='message_available']
        if lane:
            assert [m['observation_id'] for m in lane] == [m['observation_id'] for m in messages]
        affected = [m['timestamp'] for m in messages if m['observation'].get('raw_text')
                    and m['observation']['confidence'] >= .8
                    and len(re.findall(r'[\u4e00-\u9fff]', m['observation']['raw_text'])) < 5]
        final = rows[-1]['data']
        assert rows[-1]['type']=='stream_end'
        assert final['metrics']['submitted_jobs']==final['metrics']['completed_jobs']
        assert final['readiness']['status']=='uncertain' and final['readiness']['pending_jobs']==0
        runs.append({'trace':str(path.relative_to(ROOT)), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                     'ordered_frames':len(bundles), 'message_observations':len(messages),
                     'message_lane_count':len(lane), 'reviewed_messages':checks,
                     'high_confidence_short_candidates':affected,
                     'service_seconds':{kind:sum(o['recognition_seconds'] for o in observations if o['category']==kind)
                                        for kind in ['ocr','icon']},
                     'worker_queue_wait':distribution([o['started_monotonic']-o['capture_monotonic'] for o in observations]),
                     'final_readiness':final['readiness']})
    report = {'schema_version':1, 'validation_date':'2026-10-14',
              'method':'Read-only saved trace and fixture checksum audit; no OCR or video processing.',
              'timing_scope':'Historical pre-filter-removal runs; no new performance measurement.', 'runs':runs}
    (ROOT/'reports/M1.5-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print([(r['trace'],r['ordered_frames'],len(r['reviewed_messages']),r['service_seconds']) for r in runs])


if __name__=='__main__':
    main()
