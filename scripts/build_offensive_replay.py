"""Inventory cached own HP evidence and build one versioned offensive overlay."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import resource
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from battle_evidence.action_offline import inputs_for
from battle_evidence.speed_replay_offline import atomic,digest,file_hash,load_team,select_actions
from battle_evidence.offensive import candidate_inventory,admit_review,offensive_overlay,compact_offensive_storage


def atomic_large(path,data):
    """Stream large artifacts so atomic publication does not duplicate JSON text."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    with temp.open('w') as stream:
        json.dump(data,stream,ensure_ascii=False,sort_keys=True)
        stream.write('\n')
    temp.replace(path)


def inverse_diagnostics(replay, observations):
    """Run existing solvers without expanding every item/Speed row for the UI."""
    from copy import deepcopy
    from battle_evidence.offensive import observed_configuration_domain
    from damage.inverse import infer_attack_stat
    from damage.joint import filter_joint
    from knowledge.champions_stats import ChampionsStats
    from speed_order.core import knowledge

    results={}
    for actor in sorted({o['attacker'] for o in observations}):
        events=[o for o in observations if o['attacker']==actor]
        participant=next(s for s in reversed(replay['snapshots']) if s['timestamp']<=events[0]['timestamp'])['opponents'][actor]
        observed=filter_joint(observed_configuration_domain(replay,participant),events)
        form=events[0]['attacker_form']
        if any(o['attacker_form']!=form for o in events):
            raise ValueError('Diagnostics require an unchanged attacker form')
        model=ChampionsStats(form,form='as_named' if knowledge().entities[form].form_id else 'base')
        candidates=model.attainable('special_attack',adjustments=['0.9','1.0','1.1'])['values']
        probes={}
        for ability in knowledge().facts['pokemon'][form]['ability_names']:
            rows=[]
            for o in events:
                request=deepcopy(o['input']);request['attacker'].update(ability=ability,item='none')
                rows.append(dict(id=o['id'],battle_id=o['battle_id'],attacker_instance_id=actor,
                    target_instance_id=o['target'],stat_epoch=form,damage=o['damage'],
                    damage_kind='direct_move_damage',evidence='Source-bound uncensored reviewed hit: '+o['id'],input=request))
            probes[ability]=infer_attack_stat(observations=rows,candidate_stats=candidates,stat='special_attack',
                ruleset='showdown-champions-reference-v1',variables=[dict(id='critical',scope='observation',
                    observation_ids=[o['id'] for o in events],path='field.critical',values=[False,True])],
                domain_provenance='Pinned single-stat Champions legality domain; explicit no-item probe, not exhaustive held-item or joint Speed support')
        results[actor]=dict(observed=observed,native_ability_probes=probes,
            scope='Special Attack diagnostics only; no exhaustive full-reference or required-item conclusion')
    return results


def run(number,review_path=None,inventory_only=False,diagnostics_only=False,item_profile="practical",item_review=None,move_smoothing_a=.5,move_smoothing_b=.5,empirical_alpha=.5):
    import math
    if any(not math.isfinite(v) or v<=0 for v in (move_smoothing_a,move_smoothing_b)):raise ValueError('Finite positive move smoothing required')
    start=perf_counter();battle=BattleArtifacts(f'sample_battle_{number}',ROOT).prepare()
    pointer=json.loads(battle.cache('m322-reviewed-speed/latest.json').read_text());source=Path(pointer['path'])
    seal=json.loads(source.with_name('manifest.json').read_text())
    if seal['status']!='complete' or file_hash(source)!=seal['outputs']['replay.json']:
        raise ValueError('Unsealed source Speed replay')
    dependencies=[source,source.with_name('manifest.json'),Path(__file__),ROOT/'battle_evidence/offensive.py',
                  ROOT/'battle_evidence/hp.py',ROOT/'knowledge/champions_stats.py',ROOT/'knowledge/data/manifest.json',
                  ROOT/'tests/fixtures/battle_evidence/sample-team7-reviewed.json',
                  ROOT/'tests/fixtures/battle_evidence/team7-roster-bindings.json']
    dependencies+=list((ROOT/'damage').glob('*.py'))+list((ROOT/'damage/data').glob('*.json'))
    dependencies.append(ROOT/'battle_evidence/data/team-item-rule-v1.json')
    dependencies += [ROOT/'battle_evidence'/name for name in ('team_items.py','life_orb.py','empirical_measure.py','move_legality.py','damage_review_history.py','item_policy.py','speed_items.py','speed_replay_offline.py','speed_reviewed.py','speed_replay_projection.py','builds.py','action_offline.py')]
    item_events=[];item_review_paths=[]
    if item_review:
        dependencies.append(item_review)
        item_review_paths.append(item_review)
        item_document=json.loads(item_review.read_text());item_events=item_document['events']
        if item_document.get('base_review'):
            base=ROOT/item_document['base_review'];dependencies.append(base)
            item_review_paths.append(base)
            item_events=json.loads(base.read_text())['events']+item_events
        for e in item_events:
            if e['id'] in item_document.get('current_possession_interpretations',{}):
                e.update(item_document['current_possession_interpretations'][e['id']])
        item_events=sorted(item_events,key=lambda e:(e['timestamp'],e['id']))
        dependencies += [ROOT/s['image'] for e in item_events for s in e['sources']]
    empirical_source=source.parent/'empirical.json'
    if not empirical_source.exists():raise ValueError('Sealed M3.3 empirical population missing')
    if file_hash(empirical_source)!=seal['outputs']['empirical.json']:raise ValueError('M3.3 empirical snapshot altered')
    dependencies.append(empirical_source)
    vgc_database=ROOT/'.cache/metagame/published-teams/teams.sqlite3'
    dependencies += [vgc_database,ROOT/'battle_evidence/vgc_population.py']
    dependencies += [ROOT/'metagame/published'/n for n in ('store.py','canonical.py','observed.py','speed_support.py','population.py')]
    if review_path:
        dependencies.append(review_path)
        review=json.loads(review_path.read_text())
        dependencies += [ROOT/s['image'] for e in review['events'] for s in e['sources'].values()]
    team=json.loads((ROOT/'tests/fixtures/battle_evidence/sample-team7-reviewed.json').read_text())
    dependencies += [ROOT/s['path'] for s in team['sources']]
    rosters=json.loads((ROOT/'tests/fixtures/battle_evidence/team7-roster-bindings.json').read_text())
    dependencies += [ROOT/r['image'] for r in rosters['roster_reviews'] if r['battle_id']==battle.battle_id]
    identity=dict(version='M3.4.5a-item-conditioned-v1',battle_id=battle.battle_id,inventory_only=inventory_only,item_profile=item_profile,empirical_measure=dict(alpha=empirical_alpha,a=move_smoothing_a,b=move_smoothing_b),
                  inputs={str(p):file_hash(p) for p in dependencies})
    if diagnostics_only:identity['diagnostics_only']=True
    fingerprint=digest(identity)[:16];dest=battle.cache('m342-offensive/'+fingerprint);dest.mkdir(parents=True,exist_ok=True)
    manifest=dest/'manifest.json'
    saved_checkpoints={}
    if manifest.exists():
        saved=json.loads(manifest.read_text())
        saved_checkpoints=saved.get('checkpoints',{})
        if saved['status']=='complete' and all(file_hash(dest/k)==v for k,v in saved['outputs'].items()):
            print(battle.battle_id,'reused',fingerprint,flush=True)
            if not inventory_only and not diagnostics_only:atomic(battle.cache('m342-offensive/latest-'+item_profile+'.json'),dict(path=str(dest/'replay.json'),fingerprint=fingerprint,source_speed_sha256=file_hash(source)))
            if not inventory_only and not diagnostics_only and item_profile=='practical':atomic(battle.cache('m342-offensive/latest.json'),dict(path=str(dest/'replay.json'),fingerprint=fingerprint,source_speed_sha256=file_hash(source)))
            return
    status=dict(status='running',stage='cached_HP_inventory',identity=identity,
                resume_command=f'.venv/bin/python scripts/build_offensive_replay.py --battle {number}'+(f' --review {review_path}' if review_path else '')+f' --item-profile {item_profile} --move-smoothing-a {move_smoothing_a} --move-smoothing-b {move_smoothing_b} --empirical-alpha {empirical_alpha}'+(f' --item-review {item_review}' if item_review else '')+(' --inventory-only' if inventory_only else '')+(' --diagnostics-only' if diagnostics_only else ''))
    status['checkpoints']=saved_checkpoints
    inherited_full={}
    previous_pointer=battle.cache('m342-offensive/latest-'+item_profile+'.json')
    if not saved_checkpoints and previous_pointer.exists():
        previous=Path(json.loads(previous_pointer.read_text())['path'])
        previous_manifest=json.loads(previous.with_name('manifest.json').read_text())
        old_inputs=previous_manifest.get('identity',{}).get('inputs',{})
        critical={source,ROOT/'knowledge/champions_stats.py',ROOT/'knowledge/data/manifest.json'}
        critical.update(ROOT/'battle_evidence'/n for n in ('team_items.py','item_policy.py','speed_items.py','speed_replay_projection.py','speed_reviewed.py'))
        critical.update(item_review_paths)
        critical.add(ROOT/'battle_evidence/data/team-item-rule-v1.json')
        mechanics=[p for p in dependencies if p.parent==ROOT/'damage' or p.parent==ROOT/'damage/data' or p in critical]
        if previous_manifest.get('status')=='complete' and all(old_inputs.get(str(p))==file_hash(p) for p in mechanics):
            inherited_full={k:v for k,v in previous_manifest.get('checkpoints',{}).items() if v['layer']=='full'}
            status['compatible_full_prefix_source']=str(previous.with_name('manifest.json'))
    atomic(manifest,status)
    try:
        print(battle.battle_id,'reading sealed own HP evidence; no OCR/video processing',flush=True)
        phase_start=perf_counter();phase_metrics={}
        data,states,raw,paths=inputs_for(battle)
        replay=json.loads(source.read_text())
        from battle_evidence.item_policy import validate_item_review
        validate_item_review(item_events,replay,root=ROOT)
        inventory=candidate_inventory(replay,states)
        phase_metrics['source_evidence_load_seconds']=perf_counter()-phase_start
        atomic(dest/'inventory.json',dict(battle_id=battle.battle_id,candidates=inventory,
            source_hashes={str(p):file_hash(p) for p in paths},source_HP_samples=len(states['hp_samples']),
            note='Temporal candidates; only source-reviewed exact own-HP brackets can be admitted'))
        outputs=['inventory.json'];observations=[]
        if not inventory_only:
            if not review_path:raise ValueError('Explicit source review required for offensive replay')
            review=json.loads(review_path.read_text())
            # Hash actual reviewed frame inputs before writing a published pointer.
            for event in review['events']:
                for image in event['sources'].values():
                    if file_hash(ROOT/image['image'])!=image['sha256']:raise ValueError('Reviewed damage frame changed')
            phase_start=perf_counter()
            actions,*_=select_actions(battle);_,builds,_,_,_=load_team(battle,actions,root=ROOT)
            observations=admit_review(replay,review,builds,root=ROOT)
            phase_metrics['review_admission_seconds']=perf_counter()-phase_start
            atomic(dest/'observations.json',observations);outputs.append('observations.json')
            from battle_evidence.empirical_measure import upgrade_empirical_support,attach_measures
            from battle_evidence.vgc_population import load_vgc
            population=load_vgc(vgc_database.parent)
            atomic(dest/'vgc-population.json',population);outputs.append('vgc-population.json')
            replay,empirical_catalogs,phase_metrics['empirical_core_initialization_seconds']=upgrade_empirical_support(replay,population)
            replay['empirical_artifact']=str((dest/'vgc-population.json').relative_to(ROOT))
            status['stage']='joint_configuration_filter';atomic(manifest,status)
            print(battle.battle_id,'filtering persistent Speed configurations',flush=True)
            if diagnostics_only:
                result=inverse_diagnostics(replay,observations)
            else:
                last_progress=[0.0]
                def progress(value):
                    now=perf_counter()
                    if now-last_progress[0]<2:return
                    last_progress[0]=now
                    status['progress']=value;atomic(manifest,status)
                    print(json.dumps(value),flush=True)
                def checkpoint(actor,layer,value):
                    key=digest([actor,layer,value['updates'][-1]['id']])[:16]
                    path=dest/'joint-checkpoints'/f'{key}.json'
                    before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                    atomic_large(path,value)
                    status.setdefault('checkpoints',{})[key]=dict(path=str(path),sha256=file_hash(path),
                        actor=actor,layer=layer,observation=value['updates'][-1]['id'],peak_rss_before_write=before,
                        peak_rss_after_write=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
                    atomic(manifest,status)
                    print(layer,value['updates'][-1]['id'],'checkpoint saved',flush=True)
                def resume(actor,layer,events):
                    results=[]
                    for event in events:
                        key=digest([actor,layer,event['id']])[:16];saved=saved_checkpoints.get(key) or (inherited_full.get(key) if layer=='full' else None)
                        if not saved:break
                        path=Path(saved['path'])
                        if not path.exists() or file_hash(path)!=saved['sha256']:
                            raise ValueError('Present joint checkpoint missing or altered: '+str(path))
                        value=json.loads(path.read_text())
                        if any(u.get('observation_fingerprint')!=hashlib.sha256(json.dumps(o,sort_keys=True).encode()).hexdigest() for u,o in zip(value['updates'],events)):
                            if key in saved_checkpoints:raise ValueError('Checkpoint inputs changed')
                            break
                        results.append(value)
                        status.setdefault('checkpoints',{})[key]=saved
                    if results:print(layer,'reusing',len(results),'sealed joint checkpoints',flush=True)
                    return results
                phase_start=perf_counter()
                result=offensive_overlay(replay,observations,progress=progress,checkpoint=checkpoint,resume=resume,item_profile=item_profile,item_events=item_events)
                phase_metrics['numerical_overlay_seconds']=perf_counter()-phase_start
                phase_metrics['empirical_tilt_aggregate_seconds']=attach_measures(result,empirical_catalogs,a=move_smoothing_a,b=move_smoothing_b,default_alpha=empirical_alpha)
                result['offensive_inference']['milestone']='M3.4.5a'
                result['offensive_inference']['inventory_artifact']=str((dest/'inventory.json').relative_to(ROOT))
                result['offensive_inference']['source_speed_sha256']=file_hash(source)
                result['offensive_artifact_directory']=str(dest.relative_to(ROOT))
                atomic(dest/'item-explanations.json',dict(milestone='M3.4.5a',item_profile=item_profile,updates=[dict(id=u['id'],timestamp=u['timestamp'],**u['full']['item_explanations']) for u in result['offensive_inference']['updates']]))
                outputs.append('item-explanations.json')
                if 'team_item_relations' in result:
                    atomic(dest/'team-item-relations.json',result['team_item_relations']);outputs.append('team-item-relations.json')
                phase_start=perf_counter()
                compact_offensive_storage(result)
                phase_metrics['compact_storage_seconds']=perf_counter()-phase_start
            for row in inventory:
                matching=[o for o in observations if o['source_event_id']==row['source_event_id']]
                if matching:row.update(admitted=True,admitted_review_ids=[o['id'] for o in matching],reasons=['source-reviewed exact HP; mechanics conditional on stated reference/context'])
            inv=json.loads((dest/'inventory.json').read_text());inv['candidates']=inventory;atomic(dest/'inventory.json',inv)
            result_name='inverse-diagnostics.json' if diagnostics_only else 'replay.json'
            phase_start=perf_counter()
            atomic_large(dest/result_name,result)
            phase_metrics['serialization_write_seconds']=perf_counter()-phase_start
            outputs.append(result_name)
        metrics=dict(phases=phase_metrics,seconds=perf_counter()-start,candidate_actions=len(inventory),admitted=len(observations),
                     video_decodes=0,ocr_calls=0,published_database_rebuilds=0,
                     peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        status.update(status='complete',stage='complete',metrics=metrics,outputs={f:file_hash(dest/f) for f in outputs})
        atomic(manifest,status)
        if not inventory_only and not diagnostics_only:atomic(battle.cache('m342-offensive/latest-'+item_profile+'.json'),dict(path=str(dest/'replay.json'),fingerprint=fingerprint,source_speed_sha256=file_hash(source)))
        if not inventory_only and not diagnostics_only and item_profile=='practical':atomic(battle.cache('m342-offensive/latest.json'),dict(path=str(dest/'replay.json'),fingerprint=fingerprint,source_speed_sha256=file_hash(source)))
        print(json.dumps(dict(path=str(dest),metrics=metrics)),flush=True)
    except Exception as exc:
        status.update(status='failed',error=repr(exc));atomic(manifest,status);raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--battle',type=int,required=True,choices=[10,11,12])
    parser.add_argument('--review',type=Path)
    parser.add_argument('--item-profile',choices=['practical','comprehensive'],default='practical')
    parser.add_argument('--move-smoothing-a',type=float,default=.5)
    parser.add_argument('--move-smoothing-b',type=float,default=.5)
    parser.add_argument('--empirical-alpha',type=float,choices=[0,.25,.5,.6,.75,1],default=.5)
    parser.add_argument('--item-review',type=Path,help='Optional source-reviewed item ledger; no automatic detections are inferred')
    parser.add_argument('--inventory-only',action='store_true')
    parser.add_argument('--diagnostics-only',action='store_true',help='Run observed joint inference and native-ability Special Attack probes without building a replay')
    args=parser.parse_args()
    if args.inventory_only and args.diagnostics_only:parser.error('Choose inventory-only or diagnostics-only')
    run(args.battle,args.review,args.inventory_only,args.diagnostics_only,args.item_profile,args.item_review,args.move_smoothing_a,args.move_smoothing_b,args.empirical_alpha)
