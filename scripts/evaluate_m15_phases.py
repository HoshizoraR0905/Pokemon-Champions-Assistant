"""Phase-only online compatibility evaluation on existing M1.4 sampled caches.

No heavy recognition is measured here; timing benchmarks are separate.
"""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from streaming import StreamingPipeline
from streaming.replay import cached_frames

ROOT=Path(__file__).resolve().parents[1]


class NoRegions:
    def plan(self,frame,phase,include_icons=True):return []


class NoBackend:
    def recognize(self,frame,region):raise AssertionError('phase-only evaluation')


def main():
    truth=json.loads((ROOT/'tests/fixtures/m14_phase_ground_truth.json').read_text())
    result={'schema_version':1,'scope':'Online phase classification only; cached two-second samples, sparse M1.4 labels. No OCR accuracy or capture completeness claim.','videos':{}}
    for name,annotations in truth['videos'].items():
        p=StreamingPipeline(NoBackend(),planner=NoRegions(),asynchronous=False,icons=False)
        predictions=[];transitions=[]
        for frame in cached_frames(ROOT/'.cache/m14-phases'/name.removesuffix('.mp4')/'manifest.json'):
            update=p.process_frame(frame)['phase_update']
            predictions.append({'timestamp':frame.timestamp,'frame_index':frame.index,'phase':update['phase']})
            if 'transition' in update:transitions.append(update['transition'])
        p.close()
        points=[]
        for point in annotations['reviewed_points']:
            nearest=min(predictions,key=lambda o:abs(o['timestamp']-point['second']))
            points.append({**point,'prediction':nearest,'correct':point['phase']==nearest['phase']})
        boundaries=[]
        for ref in annotations.get('reviewed_transitions',[]):
            match=any(t['from']==ref['from'] and t['to']==ref['to']
                      and ref['earliest_timestamp']-.05<=t['earliest_timestamp']
                      and t['latest_timestamp']<=ref['latest_timestamp']+.05 for t in transitions)
            boundaries.append({**ref,'matched':match})
        result['videos'][name]={'sample_count':len(predictions),'correct':sum(p['correct'] for p in points),
                               'reviewed_count':len(points),'points':points,'reviewed_transitions':boundaries}
    (ROOT/'reports/M1.5-phase-compatibility.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print({n:(r['correct'],r['reviewed_count']) for n,r in result['videos'].items()})


if __name__=='__main__':main()
