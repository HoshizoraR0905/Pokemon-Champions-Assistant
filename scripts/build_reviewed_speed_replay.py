"""Build one recoverable local replay from sealed Stage A and optional reviews."""
from pathlib import Path
import argparse
import json
import sys
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from battle_artifacts import BattleArtifacts
from battle_evidence.speed_replay_offline import atomic, digest, file_hash, load_team, select_actions
from battle_evidence.speed_reviewed import apply_review
from metagame.published.speed_support import SpeedSupportIndex
from speed_order.core import knowledge
from battle_evidence.action_offline import inputs_for
from battle_evidence.speed_replay_projection import normalize, project

ROOT=Path(__file__).resolve().parents[1]


def run(number, *, stage_a=None, reviews=None, empirical_mode='expand_on_contradiction', expand=False):
    battle=BattleArtifacts(f'sample_battle_{number}',ROOT).prepare()
    if stage_a is None:
        pointer=json.loads(battle.cache('m322-speed-replay/latest.json').read_text())
        stage_a=Path(pointer['path']).parent/'replay.json'
    source=json.loads(Path(stage_a).read_text())
    if source['battle_id']!=battle.battle_id:
        raise ValueError('Cross-battle source rejected')
    stage_manifest=Path(stage_a).with_name('manifest.json')
    sealed=json.loads(stage_manifest.read_text())
    if sealed['status']!='complete' or file_hash(stage_a)!=sealed['outputs']['replay.json']:
        raise ValueError('Unsealed or changed Stage A output')
    database=ROOT/'.cache/metagame/published-teams/teams.sqlite3'
    paths=[Path(stage_a),stage_manifest,database,Path(__file__),
           ROOT/'battle_evidence/speed_reviewed.py',ROOT/'metagame/published/speed_support.py',
           ROOT/'battle_evidence/speed_replay_projection.py',
           ROOT/'knowledge/data/entities.json',ROOT/'knowledge/data/manifest.json',
           ROOT/'tests/fixtures/battle_evidence/sample-team7-reviewed.json',
           ROOT/'tests/fixtures/battle_evidence/team7-roster-bindings.json']
    paths+=sorted((ROOT/'speed_order').glob('*.py'))+sorted((ROOT/'speed_order/data').glob('*.json'))
    paths+=[ROOT/p for p in ['battle_evidence/speed_replay.py','battle_evidence/speed_items.py',
        'battle_evidence/speed_adapter.py','knowledge/data/champions_stat_rules.json','knowledge/data/champions_facts.json',
        'knowledge/champions_stats.py','knowledge/stat_feasibility.py','metagame/published/observed.py',
        'metagame/published/publication_families.py','metagame/published/store.py']]
    review=json.loads(Path(reviews).read_text()) if reviews else None
    if reviews: paths.append(Path(reviews))
    if review:
        paths += [ROOT/s['image'] for e in review['events'] for s in e['sources']]
    transition_review=json.loads((ROOT/'tests/fixtures/battle_evidence/replay-transitions-reviewed.json').read_text())
    paths += [ROOT/s['image'] for s in transition_review['battles'][battle.battle_id]['sources'].values()]
    paths += [ROOT/r['command_source']['image'] for r in transition_review['battles'][battle.battle_id].get('phase_reviews',{}).values()]
    identity=dict(version='reviewed-speed-replay-v2',battle_id=battle.battle_id,empirical_mode=empirical_mode,manual_expansion=expand,
        transition_review=transition_review['battles'][battle.battle_id],transition_review_version=transition_review['version'],
        inputs={str(p):file_hash(p) for p in paths}, scope=dict(source='vgcmulticalc',population='tournament_published',regulation='M-C',format='Doubles'))
    fingerprint=digest(identity)[:16];dest=battle.cache('m322-reviewed-speed/'+fingerprint)
    dest.mkdir(parents=True,exist_ok=True);manifest=dest/'manifest.json'
    if manifest.exists():
        m=json.loads(manifest.read_text())
        if m['status']=='complete' and all(file_hash(dest/k)==v for k,v in m['outputs'].items()):
            print(battle.battle_id,'reused',fingerprint,flush=True)
            atomic(battle.cache('m322-reviewed-speed/latest.json'),dict(path=str(dest/'replay.json'),fingerprint=fingerprint))
            return
    m=json.loads(manifest.read_text()) if manifest.exists() else dict(identity=identity,completed={})
    m.update(status='running',stage='empirical_index',
           resume_command=f'.venv/bin/python scripts/build_reviewed_speed_replay.py --battle {number}'+(f' --reviews {reviews}' if reviews else ''))
    atomic(manifest,m);start=perf_counter()
    try:
        print(battle.battle_id,'building read-only M-C joint support index',flush=True)
        checkpoint=m['completed'].get('empirical_index')
        if checkpoint and (dest/'empirical.json').is_file() and file_hash(dest/'empirical.json')==checkpoint['sha256']:
            saved=json.loads((dest/'empirical.json').read_text());corpus=saved['by_form']
            index=SpeedSupportIndex([r for support in corpus.values() for r in support['builds']],saved['scope'])
            print('reused empirical checkpoint',flush=True)
        else:
            index=SpeedSupportIndex.load(database.parent,source='vgcmulticalc',population='tournament_published',regulation='M-C')
            species=set(source['universe_catalog'])
            if review:
                from speed_order.core import identity_key
                species.update(identity_key(t['identity'],t['form']) for c in review['comparisons'] for t in c['actors'].values())
            species.update(t['resulting_form'] for t in transition_review['battles'][battle.battle_id]['transformations'])
            corpus={s:index.support(s) for s in sorted(species)}
            atomic(dest/'empirical.json',dict(scope=index.scope,by_form=corpus))
        m['completed']['empirical_index']=dict(path='empirical.json',sha256=file_hash(dest/'empirical.json'))
        m['stage']='reviewed_inference';atomic(manifest,m)
        checkpoint=m['completed'].get('reviewed_inference')
        if checkpoint and (dest/'reviewed-inference.json').is_file() and file_hash(dest/'reviewed-inference.json')==checkpoint['sha256']:
            result=json.loads((dest/'reviewed-inference.json').read_text())
            print('reused reviewed-inference checkpoint',flush=True)
        elif review:
            print(battle.battle_id,'evaluating source-reviewed chronological constraints',flush=True)
            actions,_,_=select_actions(battle);_,builds,_,_,_=load_team(battle,actions,root=ROOT)
            result=apply_review(source,review,builds,index,root=ROOT,empirical_mode=empirical_mode,expand=expand)
        else:
            result=dict(updates=[],review=None,scope='No additional source-certified comparisons; original deferrals retained',solver_seconds=0)
        atomic(dest/'reviewed-inference.json',result)
        m['completed']['reviewed_inference']=dict(path='reviewed-inference.json',sha256=file_hash(dest/'reviewed-inference.json'))
        m['stage']='replay_packaging';atomic(manifest,m)
        source['reviewed_inference']=result
        m['stage']='causal_replay_projection';atomic(manifest,m)
        print(battle.battle_id,'normalizing source transitions and causal support layers',flush=True)
        _,states,raw,_=inputs_for(battle)
        semantic,audit=normalize(source,states,raw,transition_review,root=ROOT)
        source['action_timeline']=semantic
        source['transition_audit']=audit
        source.update(project(source,semantic,states,raw,index,transition_review))
        m['completed']['causal_replay_projection']=dict(events=len(semantic),audit=audit['counts'])
        atomic(manifest,m)
        source['empirical_catalog']={s:{k:v for k,v in support.items() if k not in {'builds','scope'}} for s,support in corpus.items()}
        source['empirical_scope']=index.scope
        from battle_evidence.speed_items import item_ids
        species=set(corpus)
        source['empirical_statistics']={s:{'choice_scarf':index.statistic(s,{'item':item_ids()['Choice Scarf']}),
            'iron_ball':index.statistic(s,{'item':item_ids()['Iron Ball']}),
            'boosting_alignment':index.statistic(s,{'speed_alignment':1.1}),
            'maximum_speed_sp_given_boosting':index.statistic(s,{'speed_sp':32},given={'speed_alignment':1.1})}
            for s in species}
        source['empirical_artifact']=str((dest/'empirical.json').relative_to(ROOT))
        kb=knowledge()
        source['names']={k:e.names for k,e in kb.entities.items() if e.kind in {'species','move','item','ability'}}
        source['source_stage_a']=str(stage_a)
        source['artifact_directory']=str(dest.relative_to(ROOT))
        source['reviewed_metrics']=dict(preprocessing_seconds=perf_counter()-start,solver_seconds=result['solver_seconds'],
            reviewed_constraints=len(result['updates']),deterministic=sum(u['scope']=='source_reviewed_order' for u in result['updates']),
            conditional=sum(u['scope']!='source_reviewed_order' for u in result['updates']),video_decodes=0,ocr_calls=0)
        atomic(dest/'replay.json',source)
        m.update(status='complete',stage='complete',outputs={name:file_hash(dest/name) for name in ['empirical.json','reviewed-inference.json','replay.json']},
                 metrics=source['reviewed_metrics'],bytes=sum((dest/name).stat().st_size for name in ['empirical.json','reviewed-inference.json','replay.json']))
        atomic(manifest,m)
        atomic(battle.cache('m322-reviewed-speed/latest.json'),dict(path=str(dest/'replay.json'),fingerprint=fingerprint))
        print(json.dumps(dict(battle=battle.battle_id,path=str(dest/'replay.json'),metrics=m['metrics'],bytes=m['bytes'])),flush=True)
    except Exception as exc:
        m.update(status='failed',error=repr(exc));atomic(manifest,m);raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',type=int,required=True,choices=[10,11,12])
    p.add_argument('--stage-a',type=Path);p.add_argument('--reviews',type=Path)
    p.add_argument('--empirical-mode',choices=['empirical_only','expand_on_contradiction','full_legal'],default='expand_on_contradiction')
    p.add_argument('--expand-empirical',action='store_true');a=p.parse_args()
    run(a.battle,stage_a=a.stage_a,reviews=a.reviews,empirical_mode=a.empirical_mode,expand=a.expand_empirical)
