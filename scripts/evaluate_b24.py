"""Scoped B24 saved-evidence evaluation; production acquisition stays canonical.

Reference transcription/review is independent and versioned. This script never
reruns the production CLI, reads popularity data or mutates its frozen outputs.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json
from battle_evidence.constraint_trace import ChronologicalTrace,event_time,resolved_event,TRACKED,ACCEPTED
from battle_evidence.configuration_domain import DEFAULT_RULE,project_domain
from knowledge.stat_feasibility import summary
from recognition.event_report import verify_seal
import scripts.trace_hidden_constraints as saved

RUN='fresh-b24-20261101-v1';OWNER=BattleArtifacts('sample_battle_24',ROOT)
SOURCE=OWNER.cache('event-driven/'+RUN);EVAL=OWNER.cache('evaluation/'+RUN)
REVIEW=OWNER.input('b24-evaluation-review-20261101.json')

def read(p):return json.loads(p.read_text())
def sha(p):return saved.sha(p)
def verify():
    verify_seal(SOURCE)
    freeze=read(OWNER.cache('fresh-benchmark/'+RUN+'/initial-freeze.json'))
    for p,h in freeze['files'].items():
        if sha(ROOT/p)!=h:raise ValueError('Frozen first-run file changed: '+p)
    pre=read(EVAL/'preflight.json')
    for p,h in pre['protected_previous'].items():
        if sha(Path(p))!=h:raise ValueError('Historical artifact changed: '+p)
    return freeze

def payload():
    p=read(SOURCE/'replay.json');review=read(REVIEW)
    from tracking.battle_state import from_dict
    initial=from_dict(p['initial_state'])
    if review.get('profile_id'):
        from team_configuration.profiles import TeamProfiles
        from tracking.knowledge_grounding import attach_verified_profile
        profiles=TeamProfiles(ROOT/'.cache/team-profiles')
        profile=profiles.load(review['profile_id']).data
        # TeamConfiguration._report refreshes this derived timestamp on load.
        # Use persisted provenance so identical saved inputs retain one cache
        # identity; validation still runs through the established profile API.
        persisted=read(profiles.directory/(review['profile_id']+'.json'))['configuration']
        if 'updated_at_utc' in persisted:profile['updated_at_utc']=persisted['updated_at_utc']
        else:profile.pop('updated_at_utc',None)
        initial=attach_verified_profile(initial,profile,review['own_roster'],root=ROOT)
    if review.get('opening'):initial.knowledge['battle_start_review']=review['opening']
    for key in ('initial_full_hp_rule','ability_field_reference'):
        if review.get(key):initial.knowledge[key]=deepcopy(review[key])
    p['initial_state']=initial.to_dict();p['diagnostic_save_replay']=True
    return p

def reuse_compatible_context(p,out,m):
    """Reuse a sealed stage differing only in profile load-time bookkeeping.

    Reconstruct its exact former input and require the full fingerprint (which
    includes implementation dependencies) to match. No facts or outputs change.
    """
    key='contexts:'+saved.context_fingerprint(p)
    if key in m['stages']:return
    for old_key,old in list(m['stages'].items()):
        if not old_key.startswith('contexts:') or old.get('status')!='complete' or not old.get('diagnostic_replay'):continue
        replay_path=out/old['diagnostic_replay']['path']
        if sha(replay_path)!=old['diagnostic_replay']['sha256']:raise ValueError('Historical diagnostic replay changed')
        initial=read(replay_path)['initial_state']
        previous=initial.get('knowledge',{}).get('verified_team_profile',{}).get('configuration',{})
        if 'updated_at_utc' not in previous:continue
        candidate=deepcopy(p)
        configuration=candidate['initial_state'].get('knowledge',{}).get('verified_team_profile',{}).get('configuration')
        if configuration is None:continue
        configuration['updated_at_utc']=previous['updated_at_utc']
        if candidate['initial_state']!=initial or 'contexts:'+saved.context_fingerprint(candidate)!=old_key:continue
        if sha(out/old['output'])!=old['sha256']:raise ValueError('Compatible context checksum mismatch')
        stage=deepcopy(old)
        stage['compatibility_reuse']=dict(source_stage=old_key,
            reason='Only verified_team_profile.configuration.updated_at_utc differed; load-time report timestamp is not a battle fact',
            exact_former_fingerprint_verified=True,outputs_unchanged=True)
        m['stages'][key]=stage
        atomic_json(out/'manifest.json',m)
        print('Reused compatible completed context',old_key,'as',key,flush=True)
        return

def contexts(version):
    verify();p=payload();out=OWNER.cache('diagnosis/b24-'+version);out.mkdir(parents=True,exist_ok=True)
    identity=dict(battle_id=OWNER.battle_id,run_id=RUN,source_sha256=sha(SOURCE/'replay.json'),review_sha256=sha(REVIEW))
    path=out/'manifest.json';m=read(path) if path.exists() else dict(identity=identity,stages={},errors=[])
    if m['identity']!=identity:raise ValueError('Review identity changed; preserve namespace')
    # Existing context adapter supplies canonical aliases and separate source IDs.
    saved.FOCUSED=True
    p=saved.freeze_promoted_inputs(p,m);reuse_compatible_context(p,out,m);context=saved.create_contexts(p,out,m)
    guarded=saved.freeze_promoted_inputs(payload(),m)
    if guarded!=p:p=guarded;context=saved.create_contexts(p,out,m)
    if p.get('diagnostic_source_admission_guard'):
        m['stages']['contexts:'+saved.context_fingerprint(p)]['source_admission_guard']=p['diagnostic_source_admission_guard']
    atomic_json(path,m);return out,m,context

def joint_projection(adapter,when,record):
    """Join native marginal constraints under one SP/alignment configuration."""
    for pid,line in adapter.lineages.items():
        member=adapter.members[line['roster_id']]
        if not member['initial_form'] or any(v is None for v in line['stats'].values()):continue
        signature=json.dumps(dict(stats=line['stats'],hard=line.get('speed_hard_stats'),
            speed_observations=len(adapter.speed_ledgers[pid].orders) if pid in adapter.speed_ledgers else 0),sort_keys=True)
        if line.get('_domain_signature')==signature:continue
        if 'speed_hard_stats' in line:
            from battle_evidence.speed_preference import infer_saved_speed
            ledger=adapter.speed_ledgers[pid]
            ledger.args['stat_constraints']=deepcopy(line['speed_hard_stats'])
            speed=infer_saved_speed(ledger.orders,**ledger.args)
            line['speed_policy']=deepcopy(speed)
            if speed['status']!='exact':continue
            result=speed['joint_domain']
            # Conditional preferred marginals can widen on a later fallback;
            # always regenerate them from hard evidence and the accumulated ledger.
        else:result=project_domain(member['initial_form'],line['stats'])
        line['joint_default_configuration']=result;line['_domain_signature']=signature
        if result['status']!='exact':
            adapter.conflicts.append(dict(event_id=record['event']['event_id'],reason='default_configuration_joint_conflict',persistent_member=pid,
                domain_rule=DEFAULT_RULE,fallback_used=False,diagnostics=result['diagnostics']))
            continue
        for stat in TRACKED:
            before=deepcopy(line['stats'][stat]);after=result['stats'][stat]
            excluded=sorted(set(before['values'])-set(after['values']))
            restored=sorted(set(after['values'])-set(before['values']))
            if excluded or restored:
                line['stats'][stat]=deepcopy(after)
                u=adapter.append(member,pid,resolved_event(record),record,'numeric_refinement',dict(stat=stat),
                    dict(rule=DEFAULT_RULE,alignment_dependency='one global alignment',SP_budget=66,restored=restored,
                        speed_preference=line.get('speed_policy',{}).get('policy')),
                    before=before,after=deepcopy(after),excluded=excluded,
                    rule={'source':'existing Champions stat feasibility engine; user default configuration rule'})
                u['action_timestamp']=u['timestamp'];u['timestamp']=when
        line['_domain_signature']=json.dumps(dict(stats=line['stats'],hard=line.get('speed_hard_stats'),
            speed_observations=len(adapter.speed_ledgers[pid].orders) if pid in adapter.speed_ledgers else 0),sort_keys=True)

def inference(version):
    out,m,path=contexts(version);began=time.perf_counter();p=payload();records=p['history'];rmap={r['event']['event_id']:r for r in records}
    context={}
    for raw in path.open():
        row=json.loads(raw);context[row['event_id']]=row['context']
    aliases={a:b for c in context.values() for a,b in c.get('source_instance_aliases',{}).items()}
    hp=read(OWNER.cache('fresh-benchmark/'+RUN+'/hp-resolutions.json'))
    review=read(REVIEW)
    if review.get('diagnostic_hp_projection'):
        stage=next(s for s in m['stages'].values() if s.get('output')==path.name)
        final=out/stage['diagnostic_replay']['path']
        assert sha(final)==stage['diagnostic_replay']['sha256']
        hp_path=out/('hp-projection-'+path.stem+'.json')
        if hp_path.exists():hp=read(hp_path)
        else:
            from tracking.battle_state import from_dict
            from tracking.state_engine import StateEngine,EventRecord
            final_replay=read(final);engine=StateEngine(from_dict(final_replay['initial_state']))
            engine.state=from_dict(final_replay['state']);engine.history=[EventRecord(**r) for r in final_replay['history']]
            tick=time.perf_counter();hp=engine.hp_resolutions()
            from tracking.resolution_endpoints import repair_saved_endpoints
            hp,repairs=repair_saved_endpoints(hp,records,context,aliases)
            atomic_json(hp_path,hp)
            stage['derived_hp_projection']=dict(path=hp_path.name,sha256=sha(hp_path),seconds=time.perf_counter()-tick,
                replay_repeated=False,original_projection_unchanged=True,endpoint_repairs=repairs)
            atomic_json(out/'manifest.json',m)
    # Explicitly reviewed numeric/derived endpoint corrections remain separate.
    if review.get('hp_projection'):
        corrected=ROOT/review['hp_projection'];assert sha(corrected)==review['hp_projection_sha256'];hp=read(corrected)
    pred=read(SOURCE/'video-only.json');roster=[r for r in pred['teams'] if r['side']=='opponent' and r.get('status')=='resolved' and r.get('species_id')]
    # Collapse repeated preview sightings by resolved row, not by expected team.
    rows={}
    for r in roster:
        k=r['preview_row']
        if k in rows and rows[k]['species_id']!=r['species_id']:raise ValueError('Conflicting opponent preview row')
        rows[k]=r
    adapter=ChronologicalTrace(OWNER.battle_id,list(rows.values()),records,p['state'],integrate=True,
        persistent_aliases=aliases,configuration_rule=DEFAULT_RULE,
        hp_action_ids={e['source_event_id'] for e in hp['episodes'] if (e.get('actor_instance_id') or '').startswith(OWNER.battle_id+':opponent:') and (e.get('cause') or {}).get('kind')=='move'})
    for member in adapter.members.values():
        member['initial_basis']=DEFAULT_RULE+'; no frequency weights'
        member['joint_training_constraint'].update(configuration_rule=DEFAULT_RULE,lowered_non_hp_SP=[0])
    cycles=pred['command_cycles'];schedule=[(event_time(resolved_event(r)),0,i,r) for i,r in enumerate(records) if r['event']['event_type']!='hud_observation']
    end=max(event_time(r['event']) for r in records)
    for i,e in enumerate(hp['episodes']):
        when=(e.get('resolution_end') or {}).get('time') or end;schedule.append((when,1,i,e))
    for i,c in enumerate(cycles):
        stop=cycles[i+1]['start'] if i+1<len(cycles) else end
        schedule.append((stop,2,i,dict(c,end=stop)))
    dependencies={str(x.relative_to(ROOT)):sha(x) for base in ['battle_evidence','speed_order','damage','knowledge'] for x in (ROOT/base).rglob('*.py')}
    fp=saved.digest(dict(review=sha(REVIEW),source=sha(SOURCE/'replay.json'),hp=saved.digest(hp),context=sha(path),dependencies=dependencies,runner=sha(Path(__file__))))[:16]
    target=out/'traces'/fp;target.mkdir(parents=True,exist_ok=True)
    if (target/'trace.json').exists():
        print('Reused inference',target,flush=True);return read(target/'trace.json')
    m['stages']['inference:'+fp]=dict(status='running',pid=__import__('os').getpid(),through_time=0,rule=DEFAULT_RULE)
    observations=read(SOURCE/'observations.json')['observations']
    for when,kind,i,entry in sorted(schedule,key=lambda x:x[:3]):
        previous=len(adapter.updates)
        if kind==0:record=entry;adapter.process_event(entry,context.get(entry['event']['event_id'],{}))
        elif kind==1:
            record=rmap.get(entry.get('source_event_id'))
            adapter.damage(entry,rmap,context,observations,reviewed_absence={})
        else:
            adapter.speed_pairs(records,context,[entry]);record=rmap.get(adapter.updates[-1]['source_event_id']) if len(adapter.updates)>previous else None
        for u in adapter.updates[previous:]:u['action_timestamp']=u.get('action_timestamp',u['timestamp']);u['timestamp']=when
        if record:joint_projection(adapter,when,record)
        if kind!=0:
            atomic_json(target/'checkpoint.json',dict(through_time=when,updates=adapter.updates,lineages=adapter.lineages))
            m['stages']['inference:'+fp]['through_time']=when;atomic_json(out/'manifest.json',m)
            print('Saved',('damage' if kind==1 else 'cycle'),i,round(when,2),flush=True)
    result=adapter.result();result.update(configuration_rule=DEFAULT_RULE,fallback_used=False,inference_wall_seconds=time.perf_counter()-began,sources=dict(production=str(SOURCE.relative_to(ROOT)),context=str(path.relative_to(ROOT)),review=str(REVIEW.relative_to(ROOT))),
        context_validation=m['stages']['contexts:'+saved.context_fingerprint(saved.freeze_promoted_inputs(payload(),m))].get('receipt_status_mismatches',[]))
    for mon in result['roster']:
        if mon['initial_form']:mon['default_configuration_final']=project_domain(mon['initial_form'],mon['final_stats'])
    atomic_json(target/'trace.json',result);atomic_json(target/'hp-projection.json',hp)
    m['stages']['inference:'+fp]=dict(status='complete',outputs={str(x.relative_to(out)):sha(x) for x in target.glob('*.json')})
    atomic_json(out/'manifest.json',m);atomic_json(out/'latest.json',dict(trace=str((target/'trace.json').relative_to(ROOT)),fingerprint=fp))
    print('Inference complete',result['counts'],flush=True);return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['verify','reference','contexts','inference'],required=True)
    p.add_argument('--version',default='default-baseline-20261101-v1');a=p.parse_args()
    if a.stage=='verify':verify();print('Frozen and historical declared files verified')
    elif a.stage=='reference':
        verify()
        from scripts.evaluate_b16_auto import reference
        result=reference(OWNER,RUN);print('Independent reference rows',len(result['entries']),'views',len(result['views']))
    elif a.stage=='contexts':contexts(a.version)
    else:inference(a.version)
if __name__=='__main__':main()
