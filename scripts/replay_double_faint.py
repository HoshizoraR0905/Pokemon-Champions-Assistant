"""Post-benchmark double-faint repair using saved frames; never changes a seal.

python scripts/replay_double_faint.py --battle sample_battle_15 \
  --source-run fresh-heldout-20261026-v1 --run-id post-benchmark-double-faint-v1
"""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from battle_artifacts import BattleArtifacts, canonical_id
from recognition.event_report import verify_seal, video_events
from recognition.fast_video import CachedOCR, CachedIcons, digest
from recognition.video_sampling import atomic_json, fingerprint
from recognition.double_faint import DoubleFaintVerifier
from tracking.double_faint import pending_pair, POLICY
from tracking.state_engine import StateEngine, EventRecord, event_from_dict, ordering
from capture import Frame


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--battle',required=True)
    parser.add_argument('--source-run',required=True)
    parser.add_argument('--run-id',required=True)
    args=parser.parse_args()
    canonical_id(args.source_run);canonical_id(args.run_id)
    if not args.run_id.startswith('post-benchmark-') or args.run_id==args.source_run:
        parser.error('Use a separate post-benchmark-* run ID')
    paths=BattleArtifacts(args.battle)
    source=paths.cache('event-driven/'+args.source_run)
    out=paths.cache('event-driven/'+args.run_id);out.mkdir(parents=True,exist_ok=True)
    report=paths.report('event-driven/'+args.run_id);report.mkdir(parents=True,exist_ok=True)
    verify_seal(source)
    protected=['video-only-seal.json','video-only.json','replay.json','observations.json','manifest.json']
    hashes={p:digest(source/p) for p in protected}
    dependencies=['tracking/double_faint.py','tracking/evidence_fusion.py','recognition/double_faint.py',
                  'recognition/event_report.py','scripts/replay_double_faint.py']
    identity=dict(source=hashes,implementations={p:digest(ROOT/p) for p in dependencies})
    manifest_path=out/'repair-manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else dict(
        label='post-benchmark; diagnostic replay, not held-out performance',identity=identity,stages={})
    if manifest['identity']!=identity:raise ValueError('Changed inputs/implementation; use a new run ID')
    if manifest.get('status')=='complete':
        print((report/'summary.json').read_text());return
    def stage(name,status):
        manifest['stages'][name]=status;atomic_json(manifest_path,manifest)
    original=json.loads((source/'replay.json').read_text())
    from tracking.battle_state import from_dict
    def fresh():
        engine=StateEngine(from_dict(original['initial_state']))
        engine.history=[EventRecord(**deepcopy(r)) for r in original['history']]
        return engine
    engine=fresh()
    eligible={}
    def progress(record,state):
        if record.event['event_type']=='hud_observation':
            pairs={side:deepcopy(pair) for side in state.sides if (pair:=pending_pair(state,side))}
            if pairs:eligible[record.event['attributes']['observation_time']]=pairs
        if record.delivery_index%100==0:print('Prefix replay',record.delivery_index,flush=True)
    stage('baseline','running');engine.replay(snapshot_callback=progress)
    baseline=engine.to_dict()
    if any((a['application_status'],a['reason'],a['bindings'],a['state_hash']) !=
           (b['application_status'],b['reason'],b['bindings'],b['state_hash'])
           for a,b in zip(baseline['history'],original['history'])):
        raise ValueError('Unmodified sealed replay no longer reproduces; inspect before repair')
    stage('baseline','complete; sealed statuses/bindings/hashes reproduced')
    data=json.loads((source/'observations.json').read_text())
    rows=deepcopy(data['observations'])
    repaired_rows=out/'observations.json'
    counts=Counter();attempts=[]
    if repaired_rows.exists():
        saved=json.loads(repaired_rows.read_text());rows=saved['observations'];attempts=saved['attempts']
    else:
        import cv2
        from recognition import Recognizer
        ocr=CachedOCR(out,counts);icons=CachedIcons(out,counts);recognizer=Recognizer(ocr,icons=icons)
        verifier=DoubleFaintVerifier(args.battle);done=set()
        stage('hud_verification','running; saved-frame reads only')
        for row in rows:
            pairs=eligible.get(row['timestamp'],{})
            verifier.pending={s:p for s,p in pairs.items() if tuple(e['episode_id'] for e in p) not in done}
            if not verifier.pending:continue
            # Use the recorded, independently detected visible card geometry.
            cards=[]
            for region in row['ui']['regions']:
                if region['region_type']=='active_hud' and region['visibility']=='visible':
                    f=region['fields'];cards.append((f['side'],f['card_index'],f['offset'],f['name_roi']))
            if not cards:continue
            image=cv2.imread(str(ROOT/row['image']))
            if image is None:raise FileNotFoundError(row['image'])
            if digest(ROOT/row['image'])!=row['sha256']:raise ValueError('Saved-frame hash mismatch')
            ocr.source=icons.frame_source=row['source_id'];ocr.timestamp=icons.timestamp=row['timestamp']
            verifier.verify(recognizer,Frame(image,row['source_id'],0,row['timestamp'],row),cards,counts,row)
            proofs=[m['double_faint_hud'] for m in row.get('snapshot',{}).get('pokemon',[]) if m.get('double_faint_hud')]
            if proofs:
                attempts.append(proofs[0]);print('Independent HUD attempt',row['timestamp'],flush=True)
                atomic_json(out/'hud-attempts.json',dict(attempts=attempts,counts=dict(counts)))
            for side,pair in pairs.items():
                if side not in verifier.pending:done.add(tuple(e['episode_id'] for e in pair))
        atomic_json(repaired_rows,dict(observations=rows,attempts=attempts,counts=dict(counts)))
    stage('hud_verification','complete')
    # Preserve every sealed event ID/order/parse. Only add new frame-local HUD proof.
    proofs={e['event_id']:e['attributes']['double_faint_hud'] for e in video_events(rows,data['roster'],args.battle)
            if e['attributes'].get('double_faint_hud')}
    engine=fresh()
    for record in engine.history:
        if record.event['event_id'] in proofs:
            record.event['attributes']['double_faint_hud']=proofs[record.event['event_id']]
    stage('repaired_replay','running');engine.replay();after=engine.to_dict()
    atomic_json(out/'replay.json',after)
    def totals(history):
        return dict(total_deferred=sum(r['application_status']=='deferred' for r in history),
                    occupancy_unresolved=sum(r['reason']=='message_episode_occupancy_unresolved' for r in history),
                    rejected=sum(r['application_status']=='rejected' for r in history))
    changes=[dict(event_id=b['event']['event_id'],timestamp=b['event']['attributes'].get('observation_time'),
                  event_type=b['event']['event_type'],before=a['application_status'],after=b['application_status'],
                  before_reason=a['reason'],after_reason=b['reason'])
             for a,b in zip(original['history'],after['history'])
             if (a['application_status'],a['reason'])!=(b['application_status'],b['reason'])]
    regressions=[c for c in changes if c['before']!='deferred' or c['after'] in {'rejected','deferred'}]
    verifications=[o for o in after['state']['observations'] if o.get('kind')==POLICY]
    summary=dict(label=manifest['label'],battle_id=args.battle,run_id=args.run_id,source_run=args.source_run,
        before=totals(original['history']),after=totals(after['history']),verifications=verifications,
        recovered_by_type=dict(Counter(c['event_type'] for c in changes if c['before']=='deferred' and c['after']!='deferred')),
        changed_records=changes,regressions=regressions,new_conflicts=[c for c in after['state']['conflicts'] if c not in original['state']['conflicts']],
        recognition_counts=dict(counts),sealed_files_unchanged=all(digest(source/p)==h for p,h in hashes.items()))
    atomic_json(out/'comparison.json',summary);atomic_json(report/'summary.json',summary)
    stage('repaired_replay','complete');manifest['status']='complete';atomic_json(manifest_path,manifest)
    print(json.dumps({k:v for k,v in summary.items() if k not in {'changed_records','verifications'}},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
