"""B21 double-faint validation from saved pixels and a compatible saved checkpoint.

No video decoder/full OCR/production CLI; outputs stay in a separate diagnostic run.
"""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import argparse,ast,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts,canonical_id
from recognition.fast_video import CachedOCR,CachedIcons,digest
from recognition.event_report import verify_seal,video_events
from recognition.video_sampling import atomic_json
from tracking.battle_state import from_dict
from tracking.state_engine import StateEngine,EventRecord,ordering,event_from_dict
from tracking.double_faint import pending_pair,POLICY
from recognition.double_faint import DoubleFaintVerifier

def read(p):return json.loads(p.read_text())
def stamp(e):return e['attributes'].get('observation_time',0)
def replay(initial,events,path,label):
    e=StateEngine(from_dict(initial));e.history=[EventRecord(deepcopy(v),i+1,ordering(event_from_dict(v),i+1)) for i,v in enumerate(events)]
    def progress(r,state):
        if r.delivery_index%100==0:
            atomic_json(path,dict(stage=label,processed=r.delivery_index,total=len(events)));print(label,r.delivery_index,'/',len(events),flush=True)
    e.replay(snapshot_callback=progress);return e

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-id',required=True);parser.add_argument('--reuse-run-id');args=parser.parse_args();canonical_id(args.run_id)
    owner=BattleArtifacts('sample_battle_21');src=owner.cache('event-driven/fresh-b21-context-v1');verify_seal(src)
    target=owner.cache('diagnosis/'+args.run_id);target.mkdir(parents=True,exist_ok=True)
    seedpath=owner.cache('diagnosis/recovery-miss-occupancy-20261029-v3/focused-replay.json')
    deps=['recognition/identity_modes.py','recognition/double_faint.py','tracking/double_faint.py','tracking/state_engine.py',
        'tracking/active_continuity.py','tracking/evidence_fusion.py','recognition/command_checkpoint.py','scripts/validate_b21_double_faint.py']
    identity=dict(inputs={n:digest(src/n) for n in ['replay.json','observations.json','video-only-seal.json']},seed_sha256=digest(seedpath),
        sources={n:digest(ROOT/n) for n in deps})
    reuse=None
    if args.reuse_run_id:
        canonical_id(args.reuse_run_id);reuse=owner.cache('diagnosis/'+args.reuse_run_id)
        prior=read(reuse/'manifest.json');assert prior['status']=='complete'
        assert prior['identity']['inputs']==identity['inputs'] and prior['identity']['seed_sha256']==identity['seed_sha256']
        for n,h in prior['outputs'].items():assert digest(reuse/n)==h,n
        for n,h in prior['identity']['sources'].items():
            if n not in {'tracking/double_faint.py','recognition/double_faint.py','scripts/validate_b21_double_faint.py'}:assert digest(ROOT/n)==h,n
        # Only verification/retry changed; no-proof prefixes cannot enter it.
        functions=lambda t:{n.name:ast.dump(n) for n in ast.parse(t).body if isinstance(n,ast.FunctionDef)}
        old_functions=functions((reuse/'validated-source/tracking/double_faint.py').read_text());current=functions((ROOT/'tracking/double_faint.py').read_text())
        assert all(old_functions[n]==current[n] for n in ['vacant_pair','retain_candidate','pending_pair'])
        identity['reused_run']=dict(run_id=args.reuse_run_id,manifest_sha256=digest(reuse/'manifest.json'))
    manifest=target/'manifest.json'
    if manifest.exists():
        m=read(manifest)
        if m['identity']!=identity:raise ValueError('Implementation/input changed; preserve this run and choose a new run ID')
        if m['status']=='complete':
            for n,h in m['outputs'].items():assert digest(target/n)==h,n
            print('Reusing complete saved-data validation');return
        raise ValueError('Incomplete run: inspect process/errors before choosing a new run ID')
    m=dict(identity=identity,status='running',decoded_frames=0,full_video_ocr=False,stages={});atomic_json(manifest,m)
    def stage(name,status):m['stages'][name]=status;atomic_json(manifest,m)
    try:
        original=read(src/'replay.json');data=read(src/'observations.json');events=[h['event'] for h in original['history']]
        seed=read(seedpath)['state'];suffix=[e for e in events if stamp(e)>435]
        # Checkpoint compatibility: no double-faint candidate existed before435s;
        # all modified preexisting methods other than replay remain identical.
        assert not seed['knowledge'].get('double_faint_candidates')
        stage('candidate_prefix','running')
        prefix=[e for e in suffix if stamp(e)<536]
        assert all(not e['attributes'].get('double_faint_hud') for e in suffix)
        def restore(value):
            saved=StateEngine(from_dict(value['initial_state']));saved.state=from_dict(value['state'])
            saved.history=[EventRecord(**deepcopy(r)) for r in value['history']];return saved
        e=restore(read(reuse/'before-hud.json')) if reuse else replay(seed,prefix,target/'progress.json','candidate-prefix')
        pair=pending_pair(e.state,'opponent');assert pair and len(pair)==2
        candidates=e.state.knowledge['double_faint_candidates'];assert len(candidates)==1
        assert candidates[0]['status']=='pending' and 'instance_id' not in candidates[0]
        assert candidates[0]['species_id']==398 and e.state.sides['opponent'].active_slots=={}
        assert not any(p.species.known and p.species.value.get('species_id')==398 for p in e.state.pokemon.values())
        atomic_json(target/'before-hud.json',e.to_dict());stage('candidate_prefix','complete')
        row=deepcopy(next(r for r in data['observations'] if 536<r['timestamp']<536.1))
        framepath=ROOT/row['image'];assert digest(framepath)==row['sha256']
        recognition_cache=target/'targeted-recognition';counts=Counter()
        if reuse and not recognition_cache.exists():shutil.copytree(reuse/'targeted-recognition',recognition_cache)
        stage('command_hud_recognition','running: saved536.006667 frame only')
        import cv2
        from recognition import Recognizer
        from recognition.command_checkpoint import inspect_command,strict_single_ui
        from recognition.fast_profile import independent_cards
        from capture import Frame
        image=cv2.imread(str(framepath));assert image is not None
        row['command_inspection']=inspect_command(image);assert strict_single_ui(row['command_inspection'])
        ocr=CachedOCR(recognition_cache,counts);icons=CachedIcons(recognition_cache,counts)
        ocr.source=icons.frame_source=row['source_id'];ocr.timestamp=icons.timestamp=row['timestamp']
        recognizer=Recognizer(ocr,icons=icons);v=DoubleFaintVerifier(owner.battle_id);v.pending={'opponent':pair}
        v.verify(recognizer,Frame(image,row['source_id'],0,row['timestamp'],row),independent_cards(image),counts,row)
        proofs=[mon['double_faint_hud'] for mon in row['snapshot']['pokemon'] if mon.get('double_faint_hud')]
        assert proofs,'No independent recognition proof acquired'
        atomic_json(target/'command-hud-recognition.json',dict(row=row,counts=dict(counts),pair=pair,verification_pending=list(v.pending)))
        stage('command_hud_recognition','complete')
        additions={e['event_id']:e['attributes']['double_faint_hud'] for e in video_events([row],[],owner.battle_id) if e['attributes'].get('double_faint_hud')}
        repaired=deepcopy(suffix)
        for ev in repaired:
            if ev['event_id'] in additions:ev['attributes']['double_faint_hud']=additions[ev['event_id']]
        assert len(additions)==2
        stage('saved_suffix_replay','running')
        after=replay(seed,repaired,target/'progress.json','recovered-suffix');atomic_json(target/'replay.json',after.to_dict())
        # No-proof control shares the same current mechanics, checkpoint and IDs.
        before=restore(read(reuse/'control-replay.json')) if reuse else replay(seed,suffix,target/'progress.json','no-proof-control');atomic_json(target/'control-replay.json',before.to_dict())
        stage('saved_suffix_replay','complete')
        old={h['event']['event_id']:h for h in original['history']};control={r.event['event_id']:r for r in before.history}
        original194={eid for eid,h in old.items() if h['reason']=='message_episode_occupancy_unresolved' and stamp(h['event'])>441}
        assert len(original194)==194
        rows=[];regressions=[];hp_changes=[]
        admitted={'applied_candidate','applied_confirmed','applied_partial','recorded_observation'}
        for r in after.history:
            eid=r.event['event_id'];c=control[eid];raw=old[eid]
            result=dict(event_id=eid,timestamp=stamp(r.event),kind=r.event['event_type'],text=r.event['original_text'],
                original_status=raw['application_status'],original_reason=raw['reason'],
                control_status=c.application_status,control_reason=c.reason,after_status=r.application_status,after_reason=r.reason,
                actor=r.bindings.get('actor'))
            if eid in original194 or (c.application_status,c.reason)!=(r.application_status,r.reason):rows.append(result)
            if c.application_status in admitted and (c.application_status!=r.application_status or
                    c.bindings.get('actor')!=r.bindings.get('actor')):regressions.append(result)
        # Compare the original admitted numerical HUD readings by event ID, actor
        # and endpoint. Causal attributions may legitimately gain new evidence.
        def numerics(engine):
            return {o['evidence']['event_id']:(pid,o['after'],o['unit'],o.get('maximum')) for pid,p in engine.state.pokemon.items()
                for o in p.hp.observations if 'unit' in o}
        beforehp=numerics(before);afterhp=numerics(after)
        hp_changes=[dict(event_id=eid,before=value,after=afterhp.get(eid)) for eid,value in beforehp.items() if afterhp.get(eid)!=value]
        remaining=[r for r in rows if r['event_id'] in original194 and r['after_status']=='deferred']
        verifications=[o for o in after.state.observations if o.get('kind')==POLICY]
        assert verifications,'StateEngine did not accept the independent HUD placement'
        summary=dict(original_occupancy_deferrals=194,resolved=sum(r['event_id'] in original194 and r['after_status'] in admitted for r in rows),
            remaining=remaining,changed_or_original_occupancy_records=rows,regressions=regressions,previously_accepted_numeric_changes=hp_changes,
            verified_placements=verifications,recognition_counts=dict(counts),reused_compatible_prefix_and_control=args.reuse_run_id,
            full_video_ocr=False,decoded_frames=0,checkpoint_through_seconds=435,suffix_events=len(suffix),
            frozen_unchanged=all(digest(src/n)==h for n,h in identity['inputs'].items()),
            limitation='Prospective confirmation only; pre-HUD receipts remain unresolved. Local recovery is not whole-match accuracy.')
        atomic_json(target/'comparison.json',summary)
        assert not regressions and not hp_changes,(len(regressions),len(hp_changes))
        m.update(status='complete',outputs={n:digest(target/n) for n in ['before-hud.json','command-hud-recognition.json','replay.json','control-replay.json','comparison.json']});atomic_json(manifest,m)
        print('Recovered',summary['resolved'],'remaining',len(remaining),'regressions',len(regressions),'HP changes',len(hp_changes),dict(counts),flush=True)
    except BaseException as exc:
        m.update(status='failed',error=repr(exc));atomic_json(manifest,m);raise
if __name__=='__main__':main()
