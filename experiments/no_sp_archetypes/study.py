"""Checkpointed M3.5.3 audit, internal evaluation and unlabeled application."""
import argparse
from collections import Counter
from dataclasses import asdict
import fcntl
from pathlib import Path
import json
import platform
import traceback
import numpy as np
from metagame.common import atomic_json, encode, sha, now
from experiments.build_similarity.core import SPConfig
from .data import publications, adapt_publications, split_application, TARGET
from .frozen import load, file_hash, ROOT
from .evaluate import evaluate
from .model import Predictor, ALPHA, LEVEL_WEIGHTS

VERSION='M3.5.3-v1'
NAMES=('Higher-Speed investment','Higher-Attack investment','Lower-Speed defensive investment')


def cluster_reference(frozen):
    summaries=[]
    for z,c in enumerate(frozen['cluster_summaries']):
        rows=[r for r,label in zip(frozen['training'],frozen['labels']) if label==z]
        summary=dict(c,name=NAMES[z],share=len(rows)/len(frozen['training']),medoid=frozen['medoids'][z])
        summary['quantiles']={s:dict(zip(('q1','median','q3'),np.quantile([r['training_points'][s] for r in rows],[.25,.5,.75]).tolist())) for s in rows[0]['training_points']}
        byid={r['empirical_record_id']:r for r in rows}
        summary['representative_builds']=[byid[rid] for rid in c['representatives']]
        summaries.append(summary)
    return summaries


def select_queue(records, limit=20):
    pool=[r for r in records if r['primary_independent_pool']]
    queue=[];reasons={};seen_patterns=set();availability={}
    def take(label,candidates,n):
        availability[label]=len(candidates)
        selected=0
        for r in candidates:
            rid=r['empirical_record_id']
            pattern=(tuple(sorted(r['configuration']['moves'])),r.get('item'))
            if rid in queue:
                reasons[rid].append(label);continue
            if pattern in seen_patterns:continue
            if len(queue)>=limit or selected>=n:break
            queue.append(rid);reasons[rid]=[label];seen_patterns.add(pattern);selected+=1
    for z in range(3):
        take(f'high-margin cluster {z}',sorted((r for r in pool if r['prediction']['moves_only']['top']==z and r['prediction']['moves_only']['margin']>=.15),key=lambda r:(-r['prediction']['moves_only']['margin'],r['empirical_record_id'])),3)
    take('ambiguous boundary',sorted(pool,key=lambda r:(r['prediction']['moves_only']['margin'],r['empirical_record_id'])),3)
    take('novel or rare moveset',sorted((r for r in pool if r['prediction']['novelty']['rare_complete_set'] or r['prediction']['novelty']['out_of_distribution']),key=lambda r:(-len(r['prediction']['novelty']['unseen_moves']),r['prediction']['exact_support'],r['empirical_record_id'])),3)
    def shift(r):
        p=r['prediction'];return sum(abs(a-b) for a,b in zip(p['moves_only']['weights'],(p['moves_item'] or p['moves_only'])['weights']))
    take('item changes weights (L1 ≥ 0.1)',sorted((r for r in pool if shift(r)>=.1),key=lambda r:(-shift(r),r['empirical_record_id'])),3)
    take('additional distinct moveset/item',sorted(pool,key=lambda r:(r['prediction']['moves_only']['margin'],r['empirical_record_id'])),limit)
    # Never fabricate cases to meet a quota. Retain fewer if distinct patterns
    # cannot supply 20 useful cases; the complete population stays available.
    return dict(ids=queue,reasons=reasons,availability=availability,limit=limit,
                selected_by_cluster=dict(Counter(str(next(r for r in pool if r['empirical_record_id']==rid)['prediction']['moves_only']['top']) for rid in queue)),
                policy='Independent pool only; fixed category order, ≤3 initially per category, distinct moveset/item patterns, then ambiguity-ordered fill; no true labels available')


def identity(pubs, study):
    paths=[]
    for directory in ('experiments/no_sp_archetypes','knowledge','speed_order','metagame/published'):
        paths += sorted(p for p in (ROOT/directory).glob('*.py') if directory != 'experiments/no_sp_archetypes' or p.name in {'data.py','evaluate.py','frozen.py','model.py','study.py'})
        paths += sorted((ROOT/directory).glob('*.json'))
        paths += sorted((ROOT/directory/'data').glob('*.json'))
    paths += [ROOT/'experiments/build_similarity/core.py',ROOT/'metagame/common.py',ROOT/'damage/core.py',ROOT/'metagame/parser.py',ROOT/'metagame/identity.py',ROOT/'knowledge/data/entities.json']
    # UI files don't change numerical results; they are served directly.
    inputs=dict(version=VERSION,publications=sha(encode(pubs).encode()),
                sources={str(p.relative_to(ROOT)):file_hash(p) for p in paths},
                frozen={name:file_hash(study/name) for name in ('population.json','incineroar-sp.json','manifest.json')},
                alpha=ALPHA,level_weights=LEVEL_WEIGHTS,python=platform.python_version(),numpy=np.__version__,seeds=[353,354,355])
    return sha(encode(inputs).encode())[:20],inputs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,default=ROOT/'.cache/metagame/published-teams')
    parser.add_argument('--study',type=Path,default=ROOT/'.cache/research/m351/7933afbb341cdbeddbe3')
    parser.add_argument('--output',type=Path,default=ROOT/'.cache/research/m353')
    parser.add_argument('--report',type=Path,default=ROOT/'milestone_reports/M3.5.3_No_SP_Archetype_Review.md')
    args=parser.parse_args()
    pubs=publications(args.database)
    fingerprint,inputs=identity(pubs,args.study)
    run=args.output/fingerprint;run.mkdir(parents=True,exist_ok=True)
    with (run/'study.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        manifest_path=run/'manifest.json'
        manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else dict(fingerprint=fingerprint,identity=inputs,stages={},created_at=now())
        manifest.update(status='running',resume_command=f'.venv/bin/python -m experiments.no_sp_archetypes.study --database {args.database} --study {args.study} --output {args.output} --report {args.report}')
        atomic_json(manifest_path,manifest)
        def stage(name,fn,implementation=None):
            path=run/(name+'.json');old=manifest['stages'].get(name,{})
            reusable=old.get('status')=='complete' and path.exists() and file_hash(path)==old.get('sha256') and old.get('implementation')==implementation
            if reusable and name=='report':
                receipt=json.loads(path.read_text())
                reusable=all(Path(p).is_file() and file_hash(p)==h for p,h in receipt['files'].items())
            if reusable:
                print(f'Reuse {name}',flush=True);return json.loads(path.read_text())
            reason='not previously complete' if not old else 'missing or hash-mismatched stage output; successful other stages preserved'
            manifest['stages'][name]=dict(status='running',started_at=now(),invalidation_reason=reason,implementation=implementation)
            atomic_json(manifest_path,manifest);print(f'Run {name}',flush=True)
            try:
                value=fn();atomic_json(path,value)
                manifest['stages'][name].update(status='complete',completed_at=now(),sha256=file_hash(path),output=str(path))
                atomic_json(manifest_path,manifest);return value
            except Exception as exc:
                manifest['stages'][name].update(status='failed',error=str(exc),traceback=traceback.format_exc());manifest['status']='failed';atomic_json(manifest_path,manifest);raise
        audit=stage('audit',lambda:dict(zip(('records','summary'),adapt_publications(pubs))))
        frozen=stage('frozen',lambda:load(args.study,audit['records']))
        def progress(info):
            manifest['stages']['evaluation']['progress']=info;atomic_json(manifest_path,manifest)
            print(f"  evaluation {info['completed_folds']}/{info['total_folds']} folds",flush=True)
        evaluation=stage('evaluation',lambda:evaluate(frozen['training'],frozen['medoids'],SPConfig(**frozen['config']['sp']),progress=progress))
        def apply():
            model=Predictor(frozen['training'],frozen['labels'])
            records=split_application(audit['records'],frozen['training'])
            for r in records:r['prediction']=model.predict(r['configuration']['moves'],r.get('item'))
            return dict(records=records,queue=select_queue(records))
        application=stage('application',apply)
        def review_data():
            from speed_order.core import knowledge
            names={cid:e.names.get('en',cid) for cid,e in knowledge().entities.items()}
            names.update({r['nature']:r['nature'].split(':')[-1].title() for r in frozen['training']+application['records'] if r.get('nature')})
            records=application['records']
            for r in records:r['queue_reasons']=application['queue']['reasons'].get(r['empirical_record_id'],[])
            return dict(model_fingerprint=fingerprint,records=records,names=names,clusters=cluster_reference(frozen),
                        independent_count=sum(r['primary_independent_pool'] for r in records),queue=application['queue']['ids'],
                        queue_note=f"Curated queue: {len(application['queue']['ids'])} distinct moveset/item patterns. Available categories: "+'; '.join(f'{k}: {v}' for k,v in application['queue']['availability'].items()),
                        annotation_location=str(ROOT/'.cache/research/m353/reviews.sqlite3'),
                        source_audit=audit['summary'],evaluation_summary=evaluation['pooled'],human_review_status='pending')
        payload=stage('review-data',review_data)
        from .report import write_report
        stage('report',lambda:write_report(args.report,audit,frozen,evaluation,application,fingerprint,run),implementation=file_hash(Path(__file__).with_name('report.py')))
        manifest.update(status='complete',completed_at=now());atomic_json(manifest_path,manifest)
        atomic_json(args.output/'latest.json',dict(fingerprint=fingerprint,path=str(run.resolve())))
        print(f'Completed {fingerprint}\nReport: {args.report}\nLaunch: .venv/bin/python -m experiments.no_sp_archetypes.review',flush=True)


if __name__=='__main__':main()
