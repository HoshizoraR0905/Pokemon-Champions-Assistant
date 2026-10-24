"""Validate saved SP-only assignments; never refit the frozen application model."""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import numpy as np
from experiments.build_similarity.core import SPConfig, sp_array, sp_distances

ROOT=Path(__file__).resolve().parents[2]


def file_hash(path):return sha256(Path(path).read_bytes()).hexdigest()


def load(study, raw_rows):
    study=Path(study)
    manifest=json.loads((study/'manifest.json').read_text())
    evidence=json.loads((ROOT/'milestone_reports/M3.5.2_Midterm_Research_Report/evidence-summary.json').read_text())
    sources={}
    for filename in ('population.json','incineroar-sp.json'):
        stage=manifest['stages'][Path(filename).stem]
        actual=file_hash(study/filename)
        if stage['status']!='complete' or actual!=stage['sha256'] or actual!=evidence['source_sha256'][filename]:
            raise ValueError('Frozen artifact provenance mismatch: '+filename)
        sources[filename]=actual
    population=json.loads((study/'population.json').read_text())
    result=json.loads((study/'incineroar-sp.json').read_text())
    config=result['config']
    if config['sp']!=asdict(SPConfig()) or config['weights']!=[1.,0.,0.,0.]:
        raise ValueError('Expected unchanged M3.5.1 SP-only parameters')
    saved=population['targets']['Incineroar']
    ids=[r['empirical_record_id'] for r in saved]
    if ids!=result['occurrence_ids'] or len(set(ids))!=197:
        raise ValueError('Frozen occurrence identities/order changed')
    fit=next(c for c in result['kmedoids'] if c['k']==3)
    labels=fit['labels']
    if [labels.count(z) for z in range(3)]!=[31,24,142]:raise ValueError('Not the frozen SP-only K=3 partition')
    byid={r['empirical_record_id']:r for r in raw_rows}
    train=[]
    for old in saved:
        row=byid[old['empirical_record_id']]
        if not row['complete'] or row['configuration']!=old['configuration'] or row['training_points']!=old['training_points'] or row['reasons']:
            raise ValueError('Source training observation differs from saved M3.5.1 population')
        train.append(row)
    if {r['empirical_record_id'] for r in raw_rows if r['species']=='pokeapi:species:727' and r['complete'] and not r['reasons']}!=set(ids):
        raise ValueError('Current complete Incineroar source population differs from frozen training population')
    x=sp_array(train)
    d=sp_distances(x,x,SPConfig(**config['sp']))/result['normalization'][0]['scale']
    if not np.allclose(d,result['distance_matrix'],rtol=1e-12,atol=1e-12):raise ValueError('Saved SP distance matrix mismatch')
    if any(fit['summaries'][z]['medoid']!=ids[fit['medoids'][z]] for z in range(3)):
        raise ValueError('Frozen medoid identity mismatch')
    medoids=[train[i] for i in fit['medoids']]
    return dict(training=train,labels=labels,medoids=medoids,cluster_summaries=fit['summaries'],
                config=config,source_hashes=sources,study_fingerprint=evidence['study_fingerprint'])
