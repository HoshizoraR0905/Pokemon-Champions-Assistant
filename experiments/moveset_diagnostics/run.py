"""Cache-first diagnostics over saved M3.5.1 artifacts; sources remain immutable."""
import argparse
from dataclasses import asdict
import fcntl
from itertools import combinations
import json
from pathlib import Path
import platform
import traceback
import numpy as np
from metagame.common import atomic_json, encode, sha, now
from experiments.build_similarity.core import (SPConfig, MoveModel, moves, sp_array,
    sp_distances, kmedoids, adjusted_rand)
from .analysis import (MODELS, restore_embedding, distances, fit_partitions,
                       select_k, describe, comparison)

ROOT=Path(__file__).resolve().parents[2]
DEFAULT_STUDY=ROOT/'.cache/research/m351/7933afbb341cdbeddbe3'
SOURCE_FILES=('population.json','moves.json','incineroar-sp.json','incineroar-learned.json',
              'incineroar-jaccard.json','incineroar-stability.json','selection.json')
VERSION='m353-moveset-diagnostics-v1'


def file_hash(path):return sha(Path(path).read_bytes())


def protected_snapshot(study, root=ROOT):
    """Hash only; never connect to or write the live annotation database."""
    files=[Path(study)/f for f in SOURCE_FILES]+[Path(study)/'manifest.json']
    files+=sorted((root/'experiments/no_sp_archetypes').rglob('*.py'))
    files+=sorted((root/'experiments/no_sp_archetypes/assets').glob('*'))
    files += [p for p in (root/'.cache/research/m353').glob('reviews.sqlite3*') if p.is_file()]
    return {str(p):file_hash(p) for p in files if p.is_file()}


def read_sources(study):
    study=Path(study);manifest=json.loads((study/'manifest.json').read_text())
    evidence=json.loads((ROOT/'milestone_reports/M3.5.2_Midterm_Research_Report/evidence-summary.json').read_text())
    data={};hashes={}
    if manifest['status']!='complete':raise ValueError('Incomplete M3.5.1 source study')
    for f in SOURCE_FILES:
        h=file_hash(study/f);stage=manifest['stages'][Path(f).stem]
        if stage['status']!='complete' or h!=stage['sha256']:raise ValueError('Source stage integrity: '+f)
        if f in evidence['source_sha256'] and h!=evidence['source_sha256'][f]:raise ValueError('Published evidence hash mismatch: '+f)
        data[f]=json.loads((study/f).read_text());hashes[f]=h
    rows=data['population.json']['targets']['Incineroar'];ids=[r['empirical_record_id'] for r in rows]
    if len(ids)!=197 or len(set(ids))!=197:raise ValueError('Expected 197 original Incineroar occurrences')
    if any(r['species']!='pokeapi:species:727' or not r['item'] for r in rows):raise ValueError('Species/item context mismatch')
    sp_array(rows)
    for r in rows:moves(r)
    for key,expected in [('sp',[31,24,142]),('learned',[34,7,156]),('jaccard',[112,66,19])]:
        result=data[f'incineroar-{key}.json']
        if result['occurrence_ids']!=ids:raise ValueError('Saved partition occurrence order mismatch')
        if result['config']['sp']!=asdict(SPConfig()):raise ValueError('Changed SP parameters')
        if result['kmedoids'][2]['sizes']!=expected:raise ValueError('Wrong reference K=3 partition')
        for candidate in result['kmedoids']:
            if candidate['sizes']!=[candidate['labels'].count(z) for z in range(candidate['k'])]:raise ValueError('Source label-count mismatch')
            if any(candidate['summaries'][z]['medoid']!=ids[i] for z,i in enumerate(candidate['medoids'])):raise ValueError('Source medoid identity mismatch')
    if data['selection.json']['Incineroar']['sp']!=3 or data['selection.json']['Incineroar']['learned']!=1 or data['selection.json']['Incineroar']['jaccard']!=1:
        raise ValueError('Unexpected reference selections')
    return data,hashes


def build_distances(source):
    rows=source['population.json']['targets']['Incineroar']
    model=restore_embedding(source['moves.json'])
    scale=source['incineroar-learned.json']['normalization'][1]['scale']
    matrices,normalization=distances(rows,model,learned_scale=scale)
    sp=source['incineroar-sp.json']
    sp_component=sp_distances(sp_array(rows),sp_array(rows),SPConfig())/sp['normalization'][0]['scale']
    if not np.allclose(sp_component,sp['distance_matrix'],atol=1e-12,rtol=1e-12):raise ValueError('SP baseline reconstruction mismatch')
    if not np.allclose(sp_component+matrices['moves-learned'],source['incineroar-learned.json']['distance_matrix'],atol=1e-12,rtol=1e-12):
        raise ValueError('Restored fitted embedding does not reconstruct original combined distances')
    if not np.allclose(sp_component+matrices['moves-jaccard'],source['incineroar-jaccard.json']['distance_matrix'],atol=1e-12,rtol=1e-12):
        raise ValueError('Canonical Jaccard reconstruction mismatch')
    return dict(matrices={key:d.tolist() for key,d in matrices.items()},normalization=normalization,
                restored_embedding='Saved full-population vectors; no full-population fit/SVD executed')


def resample(source, repeat, fits):
    """Same groups/seeds/80% procedure; refit only for stability, never tuning."""
    training=source['population.json']['training'];rows=source['population.json']['targets']['Incineroar']
    groups=sorted({r['evaluation_group'] for r in training})
    rng=np.random.default_rng(351+repeat)
    selected=set(rng.choice(groups,max(1,int(.8*len(groups))),replace=False))
    train=[r for r in training if r['evaluation_group'] in selected]
    indices=[i for i,r in enumerate(rows) if r['evaluation_group'] in selected]
    subset=[rows[i] for i in indices]
    model=MoveModel(**source['moves.json']['parameters']).fit(train)
    matrices,norm=distances(subset,model)
    out={}
    for key,d in matrices.items():
        out[key]={}
        for candidate in fits[key]['pam']:
            k=candidate['k'];refit=kmedoids(d,k)
            out[key][str(k)]=dict(repeat=repeat,anchors=len(indices),ari=adjusted_rand([candidate['labels'][i] for i in indices],refit['labels']),
                                 groups=len(selected),training_occurrences=len(train),
                                 medoid_ids=[subset[i]['empirical_record_id'] for i in refit['medoids']],sizes=[refit['labels'].count(z) for z in range(k)])
    return dict(models=out,normalization=norm,retained_ids=[rows[i]['empirical_record_id'] for i in indices],
                selected_groups=sorted(selected),training_ids=[r['empirical_record_id'] for r in train],
                description='Global representation refitted on source-group subsample only for pipeline stability; all original weights preserved')


def assemble(source, distances_output, fits, resamples):
    rows=source['population.json']['targets']['Incineroar'];ids=[r['empirical_record_id'] for r in rows]
    models={};partitions={};matrices={}
    for key in MODELS:
        stability={str(k):[r['models'][key][str(k)] for r in resamples] for k in range(1,5)}
        selected=select_k(fits[key]['pam'],stability)
        models[key]=dict(selected_k=selected,candidates=fits[key]['pam'],hierarchical=fits[key]['hierarchical'],stability=stability,
                         normalization=distances_output['normalization'])
        matrices[key]=np.asarray(distances_output['matrices'][key])
        for k in sorted({selected,3}):
            c=next(c for c in fits[key]['pam'] if c['k']==k)
            name=f'{key}:k{k}'
            partitions[name]=dict(model=key,k=k,selected=k==selected,diagnostic=k==3,
                occurrence_ids=ids,labels=c['labels'],medoid_ids=[ids[i] for i in c['medoids']],sizes=c['sizes'],silhouette=c['silhouette'],
                stability=stability[str(k)],origin='new moves/item-only fit')
    for key,label in [('sp','sp'),('learned','combined-learned'),('jaccard','combined-jaccard')]:
        saved=source[f'incineroar-{key}.json'];matrices[label]=np.asarray(saved['distance_matrix'])
        selected=source['selection.json']['Incineroar'][key]
        c=saved['kmedoids'][2]
        partitions[f'{label}:k3']=dict(model=label,k=3,selected=selected==3,diagnostic=True,conservative_selected_k=selected,
            occurrence_ids=ids,labels=c['labels'],medoid_ids=[ids[i] for i in c['medoids']],sizes=c['sizes'],silhouette=c['silhouette'],
            stability=source['incineroar-stability.json'][key]['3'],origin='unchanged saved reference')
        models[label]=dict(selected_k=selected,candidates=[{k:c[k] for k in ('k','labels','medoids','sizes','silhouette')} for c in saved['kmedoids']],
                           hierarchical=saved['hierarchical']['k_cuts'],stability=source['incineroar-stability.json'][key])
    summaries={name:describe(rows,p,matrices[p['model']]) for name,p in partitions.items()}
    comparisons={}
    for left,right in combinations(partitions,2):comparisons[left+' | '+right]=dict(left=left,right=right,**comparison(ids,partitions[left],partitions[right]))
    return dict(models=models,partitions=partitions,comparisons=comparisons,clusters=summaries,
                normalization=distances_output['normalization'],occurrences=len(ids),
                source_groups=len({r['evaluation_group'] for r in rows}),
                distinct_full_builds=len({encode(r['configuration']) for r in rows}),
                distinct_movesets=len({moves(r) for r in rows}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,default=DEFAULT_STUDY)
    parser.add_argument('--output',type=Path,default=ROOT/'.cache/research/m353-moveset-diagnostics')
    parser.add_argument('--report',type=Path,default=ROOT/'milestone_reports/M3.5.3_Incineroar_Moveset_Clustering_Diagnostics.md')
    args=parser.parse_args()
    if args.output.resolve().is_relative_to(args.study.resolve()) or args.output.resolve().is_relative_to((ROOT/'.cache/research/m353').resolve()):
        raise ValueError('Diagnostic outputs must be separate from source study and annotation namespaces')
    protected=protected_snapshot(args.study)
    source,hashes=read_sources(args.study)
    identity=dict(version=VERSION,sources=hashes,analysis=file_hash(Path(__file__).with_name('analysis.py')),
                  runner=file_hash(Path(__file__)),core=file_hash(ROOT/'experiments/build_similarity/core.py'),
                  numpy=np.__version__,python=platform.python_version(),seeds=[351,352,353])
    fingerprint=sha(encode(identity).encode())[:20]
    run=args.output/fingerprint;run.mkdir(parents=True,exist_ok=True)
    with (run/'study.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        manifest_path=run/'manifest.json'
        manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else dict(fingerprint=fingerprint,identity=identity,stages={},created_at=now())
        manifest.update(status='running',resume_command=f'.venv/bin/python -m experiments.moveset_diagnostics.run --study {args.study} --output {args.output} --report {args.report}')
        atomic_json(manifest_path,manifest)
        def stage(name,fn,implementation=None):
            path=run/(name+'.json');old=manifest['stages'].get(name,{})
            reusable=old.get('status')=='complete' and path.exists() and file_hash(path)==old.get('sha256') and old.get('implementation')==implementation
            if reusable and name=='report':
                reusable=all(Path(p).is_file() and file_hash(p)==h for p,h in json.loads(path.read_text())['files'].items())
            if reusable:
                print('Reuse '+name,flush=True);return json.loads(path.read_text())
            reason='missing stage' if not old else 'output missing/hash mismatch or presentation implementation changed; other complete stages preserved'
            manifest['stages'][name]=dict(status='running',started_at=now(),implementation=implementation,invalidation_reason=reason)
            atomic_json(manifest_path,manifest);print('Run '+name,flush=True)
            try:
                result=fn();atomic_json(path,result)
                manifest['stages'][name].update(status='complete',completed_at=now(),sha256=file_hash(path),output=str(path));atomic_json(manifest_path,manifest)
                return result
            except Exception as exc:
                manifest['stages'][name].update(status='failed',error=str(exc),traceback=traceback.format_exc());manifest['status']='failed';atomic_json(manifest_path,manifest);raise
        stage('occurrences',lambda:dict(rows=source['population.json']['targets']['Incineroar'],source_hashes=hashes))
        d=stage('distances',lambda:build_distances(source))
        fits={key:stage('fit-'+key,lambda key=key:fit_partitions(np.asarray(d['matrices'][key]))) for key in MODELS}
        resamples=[stage('resample-'+str(repeat),lambda repeat=repeat:resample(source,repeat,fits)) for repeat in range(3)]
        summary=stage('summary',lambda:assemble(source,d,fits,resamples))
        from .report import write_report
        stage('report',lambda:write_report(args.report,source,summary,d,identity,fingerprint,run),implementation=file_hash(Path(__file__).with_name('report.py')))
        after=protected_snapshot(args.study)
        manifest['protected_files_unchanged']=(after==protected)
        if after!=protected:
            manifest.update(status='protected_files_changed',error='Source/predictor/annotation file changed while diagnostics ran; no diagnostic code writes these paths. Check for concurrent human activity.')
            atomic_json(manifest_path,manifest);raise RuntimeError(manifest['error'])
        manifest.update(status='complete',completed_at=now(),protected_file_hashes=protected);atomic_json(manifest_path,manifest)
        atomic_json(args.output/'latest.json',dict(fingerprint=fingerprint,path=str(run.resolve())))
        for key in MODELS:
            m=summary['models'][key];selected=next(c for c in m['candidates'] if c['k']==m['selected_k']);forced=next(c for c in m['candidates'] if c['k']==3)
            print(f"{key}: selected K={m['selected_k']} {selected['sizes']}; diagnostic K=3 {forced['sizes']}",flush=True)
        print(f'Complete {fingerprint}; protected files unchanged\n{args.report}',flush=True)


if __name__=='__main__':main()
