"""B22 team linkage, bounded 3/4 FPS Dual Wingbeat probe and read-only deferred audit.

Run: .venv/bin/python scripts/validate_b22_followup.py --run-id b22-followup-validation-v1
No original production CLI or historical OCR. Completed OCR stages stay cached.
"""
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts,canonical_id
from recognition.video_sampling import atomic_json
from tracking.battle_state import from_dict
from tracking.state_engine import StateEngine,EventRecord
from tracking.knowledge_grounding import attach_verified_profile
from recognition.resolution_sampling import dense_plans,sample_window,episode_dense_samples


def read(p):return json.loads(p.read_text())
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-id',required=True)
    parser.add_argument('--reuse-probes-from')
    a=parser.parse_args();canonical_id(a.run_id)
    owner=BattleArtifacts('sample_battle_22',ROOT)
    out=owner.cache('diagnosis/'+a.run_id);out.mkdir(parents=True,exist_ok=True)
    if a.reuse_probes_from:
        import ast
        canonical_id(a.reuse_probes_from)
        previous=owner.cache('diagnosis/'+a.reuse_probes_from)
        for fps in [3,4]:
            p=previous/f'{fps}fps.json'
            if not p.exists():continue
            value=read(p);probe_path=Path(value['sampling_manifest']);probe=read(probe_path)
            saved_source=probe_path.parent/'source/recognition/resolution_sampling.py'
            assert sha(saved_source)==probe['identity']['sources']['recognition/resolution_sampling.py']
            def body(path):
                return ast.dump(next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='sample_window'),include_attributes=False)
            assert body(saved_source)==body(ROOT/'recognition/resolution_sampling.py')
            for name,h in probe['identity']['sources'].items():
                if name!='recognition/resolution_sampling.py':assert sha(ROOT/name)==h,name
            if not (out/p.name).exists():atomic_json(out/p.name,value)
    bench=owner.cache('fresh-benchmark/fresh-b22-ditto-20261030-v1')
    original_path=owner.cache('event-driven/fresh-b22-ditto-20261030-v1/replay.json')
    saved=owner.cache('diagnosis/b22-focused-v6/replay.json')
    team_path=ROOT/'tests/fixtures/battle_evidence/sample-team7-reviewed.json'
    team_evidence=owner.cache('diagnosis/b22-followup-v1/team-evidence.json')
    dependencies=['scripts/validate_b22_followup.py','tracking/knowledge_grounding.py','tracking/state_engine.py','tracking/reliability.py',
        'tracking/transformation.py','tracking/resolution_context.py','tracking/hp_causes.py','recognition/resolution_sampling.py']
    identity=dict(inputs={str(p.relative_to(ROOT)):sha(p) for p in [saved,original_path,team_path,team_evidence,ROOT/'knowledge/data/52poke-resolution-v1.json']},
        implementations={p:sha(ROOT/p) for p in dependencies})
    mp=out/'manifest.json'
    old=read(mp) if mp.exists() else None
    if old and old['identity']!=identity:raise ValueError('Changed stage identity: preserve this namespace and use another run ID')
    if old and old['status']=='complete':
        for p,h in old['outputs'].items():assert sha(out/p)==h,p
        print('Reused complete follow-up:',out);return
    m=old or dict(identity=identity,status='running',stages={},resume_command=f'.venv/bin/python scripts/validate_b22_followup.py --run-id {a.run_id}')
    if a.reuse_probes_from and not old:
        previous=owner.cache('diagnosis/'+a.reuse_probes_from);pm=read(previous/'manifest.json')
        # Team-state reconstruction has independent dependencies from hit timing.
        # Reuse its successful output when its inputs and three state consumers
        # match; changing the hit adapter does not invalidate team attachment.
        keys=['tracking/knowledge_grounding.py','tracking/state_engine.py','tracking/transformation.py','tracking/reliability.py']
        team_valid=(pm['stages'].get('team_replay')=='complete'
            and all(pm['identity']['implementations'].get(k)==identity['implementations'][k] for k in keys)
            and all(identity['inputs'].get(k)==v for k,v in pm['identity']['inputs'].items()))
        if team_valid:
            for name in ['team-linked-replay.json','team-link-summary.json']:
                assert sha(previous/name)==pm['outputs'][name]
                (out/name).write_bytes((previous/name).read_bytes())
            m['stages']['team_replay']='complete'
            m['team_stage_reused_from']=dict(manifest=str(previous/'manifest.json'),sha256=sha(previous/'manifest.json'))
    def stage(name,value):
        m['stages'][name]=value;atomic_json(mp,m);print(name,value,flush=True)
    guards=[read(bench/'initial-freeze.json'),read(bench/'b16-b21-protected.json')]
    protected=[*bench.glob('*.json'),*(bench/'diagnosis').glob('*.json')]
    protected += list((ROOT/'docs/b22-ditto').glob('*'))+list((ROOT/'docs/b22-implementation').glob('*'))
    m.setdefault('protected',{str(p.relative_to(ROOT)):sha(p) for p in protected if p.is_file()})
    try:
        if not m['stages'].get('integrity_before'):
            for g in guards:
                for p,h in g['files'].items():assert sha(ROOT/p)==h,p
            stage('integrity_before',sum(len(g['files']) for g in guards))
        frozen=read(saved);original=read(original_path);team=read(team_path);evidence=read(team_evidence)
        if m['stages'].get('team_replay')!='complete':
            initial=attach_verified_profile(from_dict(frozen['initial_state']),team,evidence['b22_roster_review'],root=ROOT)
            engine=StateEngine(initial);engine.history=[EventRecord(**deepcopy(r)) for r in frozen['history']]
            stage('team_replay','running')
            def progress(r,state):
                if r.delivery_index%50==0:
                    m['team_processed']=r.delivery_index;atomic_json(mp,m);print('team',r.delivery_index,flush=True)
            engine.replay(snapshot_callback=progress)
            atomic_json(out/'team-linked-replay.json',engine.to_dict())
            d=next(p for p in engine.state.pokemon.values() if (p.original_identity.value or {}).get('species_id')==132)
            assert len(d.transformations)==2
            first,second=[x['snapshot'] for x in d.transformations]
            assert all(f['knowledge']=='unknown' for f in first['non_hp_stats'].values())
            assert first['form']['knowledge']=='unknown'
            assert {k:f['value'] for k,f in second['non_hp_stats'].items()}==dict(attack=63,defense=121,special_attack=115,special_defense=132,speed=91)
            assert len(second['moves']['known_slots'])==4
            atomic_json(out/'team-link-summary.json',dict(team_id=team['team_id'],review=evidence['b22_roster_review'],
                attached_instances={k:v['configuration_instance_id'] for k,v in engine.state.knowledge['team']['instances'].items()},
                copied=[dict(target_instance_id=x['target_instance_id'],form=x['form'],stats=x['non_hp_stats'],moves=x['moves']['known_slots']) for x in [first,second]],
                conflicts=engine.state.conflicts,limitations=['Configured base stats do not certify Mega/Z battle stats.','Attachment follows prior user exact-six policy and new agent visual roster review.']))
            stage('team_replay','complete')
        # Source observation comparison uses the unmodified saved event receipts.
        engine=StateEngine(from_dict(frozen['initial_state']));engine.state=from_dict(frozen['state'])
        engine.history=[EventRecord(**deepcopy(r)) for r in frozen['history']]
        base=engine.hp_resolutions()
        plan=next(p for p in dense_plans(engine) if p['mechanics'].get('reference_capable') and
                  any(r.event['event_id']==p['action_event_id'] and r.event['canonical_references'].get('move',{}).get('canonical_id')=='pokeapi:move:814' for r in engine.history))
        ep=next(ep for ep in base['episodes'] if ep['source_event_id']==plan['action_event_id'])
        atomic_json(out/'sampling-plan.json',plan)
        measurements=[];selected=None;dense_projection=None
        for fps in [3,4]:
            measurement_path=out/f'{fps}fps.json'
            if measurement_path.exists():
                measurement=read(measurement_path);sampled=read(Path(measurement['sampling_manifest']))
            else:
                stage('local_sampling',f'{fps} FPS')
                started=time.perf_counter()
                sampled=sample_window(owner,a.run_id+f'-{fps}fps',start=plan['start'],end=plan['end'],sample_fps=fps,side='own',slot='left',trigger=plan['trigger_time'])
                elapsed=time.perf_counter()-started
                measurement=dict(fps=fps,wall_seconds=elapsed,measured=sampled['measured'],counts=sampled['counts'],
                    sampling_manifest=str(owner.cache('hp-resolution-sampling/'+a.run_id+f'-{fps}fps/manifest.json')),
                    actual_first_pts=sampled['frames'][0],actual_last_pts=sampled['frames'][-1])
                atomic_json(measurement_path,measurement)
            dense=episode_dense_samples(owner,engine,ep,sampled)
            assert dense is not None
            dense_projection=engine.hp_resolutions(dense_samples={ep['episode_id']:dense})
            after=next(x for x in dense_projection['episodes'] if x['episode_id']==ep['episode_id'])
            measurement.update(hit_resolution=after['hit_resolution'],numeric_samples=len(dense['samples']),
                hp_sequence=[dict(time=s['time'],value=s['value'],event_id=s['event_id']) for s in dense['samples']])
            atomic_json(measurement_path,measurement);measurements.append(measurement)
            if after['hit_resolution']['per_hit_status']=='supported' and selected is None:selected=fps
            if selected is not None and (fps==4 or not (out/'4fps.json').exists()):break
        assert selected is not None,'Both tested rates unresolved: preserve outputs and report limits'
        assert after['before']==ep['before']==72 and after['after']==ep['after']==27 and after['delta']==ep['delta']==-45
        assert after['hit_resolution']['per_hit_damage']==[21,24]
        assert [(h['before'],h['after']) for h in after['hit_resolution']['hits']]==[(72,51),(51,27)]
        assert len(base['actions'])==len(dense_projection['actions']) and len(base['episodes'])==len(dense_projection['episodes'])
        assert all((a['before'],a['after'],a['delta'])==(b['before'],b['after'],b['delta']) for a,b in zip(base['episodes'],dense_projection['episodes']))
        atomic_json(out/'projection-with-hits.json',dense_projection)
        messages=[dict(event_id=r.event['event_id'],time=r.event['attributes'].get('observation_time'),type=r.event['event_type'],text=r.event['original_text']) for r in engine.history
                  if plan['start']<=r.event['attributes'].get('observation_time',-1)<=plan['end'] and r.event['event_type'] in {'move_execution','critical_hit','multi_hit'}]
        two=[dict(time=h['event']['attributes']['observation_time'],value=h['event']['attributes']['hp']['value']) for h in original['history']
             if h['event']['event_type']=='hud_observation' and plan['start']<=h['event']['attributes'].get('observation_time',-1)<plan['end'] and h['event']['side']=='self' and h['event']['attributes'].get('slot')=='left']
        atomic_json(out/'multi-hit-summary.json',dict(plan=plan,original_2fps_hit_resolution=ep['hit_resolution'],original_2fps_hp=two,
            selected_fps=selected,measurements=measurements,messages=messages,
            aggregate=dict(before=72,after=27,delta=-45,unit=ep['unit'],parent_action_id=ep['parent_action_id']),
            fourth_fps='measured_during_initial_baseline_gap_abstention_but_not_necessary' if selected==3 and len(measurements)>1 else 'not_tested_3fps_sufficient' if selected==3 else 'tested_after_3fps_insufficient',
            limitation='One source occurrence; no universal multi-hit reliability claim. Original 2 FPS policy abstains; this is not proof its visible plateau lacked information.'))
        stage('multi_hit','complete')
        deferred=[]
        for h in original['history']:
            if h['application_status']!='deferred':continue
            e=h['event'];t=e['attributes']['observation_time']
            deferred.append(dict(event_id=e['event_id'],time=t,side=e['side'],slot=e['attributes'].get('slot'),
                hp=e['attributes'].get('hp'),reason=h['reason'],evidence=e['evidence'],
                interpretation='pre_battle_preview_false_hud_no_active_identity' if t<134 else 'fainted_slot_vacant_during_replacement_party_panel',
                previous_faint=648.0083333333333 if t>600 else None,next_entry=656.01 if t>600 else 134.52333333333334,
                persistent_identity_failure=False))
        assert len(deferred)==12
        atomic_json(out/'deferred-audit.json',dict(method='Read-only original receipts and agent visual checks of saved frames 000058,000216,001290; no occupancy edits',rows=deferred))
        for p,h in m['protected'].items():assert sha(ROOT/p)==h,p
        for g in guards:
            for p,h in g['files'].items():assert sha(ROOT/p)==h,p
        stage('integrity_after','complete')
        m.update(status='complete',outputs={p.name:sha(p) for p in out.glob('*.json') if p.name!='manifest.json'})
        atomic_json(mp,m);print('Complete:',out,flush=True)
    except BaseException as exc:
        m.update(status='interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed',error=repr(exc));atomic_json(mp,m);raise


if __name__=='__main__':main()
