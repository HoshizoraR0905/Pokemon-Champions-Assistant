"""Reproducible, checkpointed offline experiment. All source access is read-only."""
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
from itertools import combinations
import argparse
import hashlib
import json
import platform
import time
import traceback
import numpy as np
from .core import (SPConfig, MoveModel, BuildDistance, kmedoids, hierarchical,
                   cut_tree, silhouette, adjusted_rand, soft_membership, moves,
                   sp_array, distribution)
from .data import prepare, fold, core_signature
from battle_evidence.empirical_measure import full_record_signature

VERSION = 'M3.5.1-v1'
ROOT = Path(__file__).resolve().parents[2]


def atomic(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n')
    tmp.replace(path)


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def slug(label):
    return label.lower().replace(' ', '-')


def variants():
    base = SPConfig()
    return {
        'sp': dict(sp=base, weights=(1., 0., 0., 0.)),
        'jaccard': dict(sp=base, move='jaccard', weights=(1., 1., 0., 0.)),
        'learned': dict(sp=base, weights=(1., 1., 0., 0.)),
        'item-nature': dict(sp=base, weights=(1., 1., .5, .5)),
        'proportion': dict(sp=replace(base, formulation='proportion'), weights=(1., 1., 0., 0.)),
        'gamma1': dict(sp=replace(base, gamma=1.), weights=(1., 1., 0., 0.)),
        'gamma3': dict(sp=replace(base, gamma=3.), weights=(1., 1., 0., 0.)),
        'defense-low': dict(sp=replace(base, defense=.1), weights=(1., 1., 0., 0.)),
        'defense-high': dict(sp=replace(base, defense=.6), weights=(1., 1., 0., 0.)),
        'moves-half': dict(sp=base, weights=(1., .5, 0., 0.)),
        'moves-double': dict(sp=base, weights=(1., 2., 0., 0.)),
        'dimension8': dict(sp=base, weights=(1., 1., 0., 0.), dimension=8),
        'dimension32': dict(sp=base, weights=(1., 1., 0., 0.), dimension=32),
    }


def distance(model, config, rows, target=None):
    args = {k: v for k, v in config.items() if k != 'dimension'}
    sp = args['sp']
    weights = args['weights']
    # Exclude target from every distance component in which it occurs.
    if target in ('speed', 'attack', 'special_attack'):
        sp = replace(sp, **{target: 0.})
    elif target == 'bulk':
        sp = replace(sp, bulk=0., defense=0., allocation=0.)
    elif target == 'item':
        weights = (*weights[:2], 0., weights[3])
    return BuildDistance(model, sp=sp, move=args.get('move', 'learned'), weights=weights).fit(rows)


def frequencies(rows, key):
    return dict(sorted(Counter(r[key] for r in rows).items()))


def summarize(rows, labels, medoids, d):
    summaries = []
    for z in sorted(set(labels)):
        indices = [i for i, label in enumerate(labels) if label == z]
        members = [rows[i] for i in indices]
        m = medoids[z]
        x = sp_array(members); bulk = x[:, [0, 2, 4]].sum(1)
        proportions = np.divide(x[:, [0, 2, 4]], bulk[:, None], out=np.zeros((len(x), 3)), where=bulk[:, None] > 0)
        summaries.append(dict(cluster=z, occurrences=len(members),
            distinct_training_cores=len({core_signature(r) for r in members}),
            distinct_full_builds=len({full_record_signature(r) for r in members}),
            medoid=rows[m]['empirical_record_id'],
            sp={s:dict(summary=distribution(x[:, j]), frequencies=dict(sorted(Counter(map(int, x[:, j])).items()))) for j, s in enumerate(('hp','attack','defense','special_attack','special_defense','speed'))},
            bulk=distribution(bulk), allocation_patterns=dict(Counter(','.join(map(str, map(int, a))) for a in x[:, [0,2,4]])),
            allocation_proportion_mean=proportions.mean(0).tolist(),
            nature=frequencies(members, 'nature'), item=frequencies(members, 'item'), ability=frequencies(members, 'ability'),
            move_frequencies=dict(Counter(m for r in members for m in moves(r))),
            move_pairs=[dict(moves=list(pair), occurrences=count) for pair, count in Counter(pair for r in members for pair in combinations(moves(r),2)).most_common()],
            complete_movesets=[dict(moves=list(ms), occurrences=count) for ms,count in Counter(moves(r) for r in members).most_common()],
            representatives=[rows[i]['empirical_record_id'] for i in sorted(indices, key=lambda i:(d[i,m],i))[:3]],
            occurrence_ids=[r['empirical_record_id'] for r in members]))
    return summaries


def neighbors(rows, d):
    result = []
    for i, row in enumerate(rows):
        ordered = sorted((j for j in range(len(rows)) if j != i), key=lambda j:(d[i,j],j))
        cross_group = [j for j in ordered if rows[j]['evaluation_group'] != row['evaluation_group']]
        def entries(js):
            return [dict(id=rows[j]['empirical_record_id'], distance=float(d[i,j])) for j in js[:3]]
        result.append(dict(id=row['empirical_record_id'], nearest=entries(ordered), nearest_other_source_group=entries(cross_group)))
    return result


def run_configuration(rows, model, config):
    bd = distance(model, config, rows)
    d = bd.distances(rows, rows)
    candidates = []
    max_k = min(3 if len(rows) < 20 else 4, len(rows))
    for k in range(1, max_k+1):
        fit = kmedoids(d, k)
        labels, medoids = fit['labels'], fit['medoids']
        sizes = [labels.count(z) for z in range(k)]
        candidates.append(dict(k=k, **fit, sizes=sizes, silhouette=silhouette(d, labels),
            minimum_size=min(sizes), summaries=summarize(rows, labels, medoids, d),
            medoid_distances=d[:, medoids].tolist(),
            alternative_clusters=np.argsort(d[:, medoids], axis=1, kind='stable').tolist(),
            similarity_membership_scores=soft_membership(d[:, medoids], sizes).tolist()))
    tree = hierarchical(d)
    cuts = []
    for k in range(1, max_k+1):
        labels = cut_tree(len(rows), tree, k=k)
        medoids = []
        for z in sorted(set(labels)):
            ids = np.flatnonzero(np.array(labels) == z)
            medoids.append(int(ids[np.argmin(d[np.ix_(ids,ids)].sum(0))]))
        cuts.append(dict(k=k, labels=labels, sizes=[labels.count(z) for z in range(k)],
                         silhouette=silhouette(d, labels), medoids=medoids,
                         summaries=summarize(rows, labels, medoids, d)))
    thresholds = []
    for q, t in zip((.25,.5,.75), np.quantile([x[2] for x in tree], [.25,.5,.75])):
        labels = cut_tree(len(rows), tree, threshold=float(t))
        thresholds.append(dict(height_quantile=q, threshold=float(t), labels=labels,
                               sizes=list(Counter(labels).values()), silhouette=silhouette(d, labels)))
    return dict(config=dict(sp=asdict(config['sp']), weights=list(config['weights']),
                            move=config.get('move','learned'), dimension=model.dimension),
                occurrence_ids=[r['empirical_record_id'] for r in rows],
                normalization=bd.diagnostics, distance_matrix=d.tolist(),
                kmedoids=candidates, hierarchical=dict(linkage='average', merges=tree, k_cuts=cuts, threshold_cuts=thresholds),
                nearest_neighbors=neighbors(rows,d))


def resampling(training, rows, configs, baseline, repeats=3):
    """Source-group 80% subsampling; refit embeddings/scales/clusters each time.

    Compare partitions only on retained occurrence anchors. No duplicate removal.
    """
    output = {key: {str(c['k']): [] for c in result['kmedoids']} for key,result in baseline.items()}
    group_list = sorted({r['evaluation_group'] for r in training})
    for repeat in range(repeats):
        rng = np.random.default_rng(351+repeat)
        selected = set(rng.choice(group_list, max(1,int(.8*len(group_list))), replace=False))
        train = [r for r in training if r['evaluation_group'] in selected]
        indices = [i for i,r in enumerate(rows) if r['evaluation_group'] in selected]
        subset = [rows[i] for i in indices]
        models = {dim: MoveModel(dimension=dim).fit(train) for dim in (8,16,32)}
        for key, config in configs.items():
            bd = distance(models[config.get('dimension',16)], config, subset)
            d = bd.distances(subset,subset)
            for candidate in baseline[key]['kmedoids']:
                k = candidate['k']
                if len(subset) < k:
                    continue
                refit = kmedoids(d,k)
                ari = adjusted_rand([candidate['labels'][i] for i in indices],refit['labels'])
                output[key][str(k)].append(dict(repeat=repeat, anchors=len(indices), ari=ari,
                                                groups=len(selected), training_occurrences=len(train)))
    return output


def heldout(training, targets, configs, folds=3):
    """Target-masked 5-neighbor prediction versus training species baseline.

    Three deterministic source-group folds; no hyperparameter selection on these
    scores. Embedding and normalization are fitted only inside each training fold.
    """
    targets_to_predict = ('speed','attack','special_attack','bulk','item')
    scores = {label:{key:{t:[] for t in targets_to_predict} for key in configs} for label in targets}
    audits = []
    oov = []
    for f in range(folds):
        train = [r for r in training if fold(r['evaluation_group'],folds) != f]
        test = [r for r in training if fold(r['evaluation_group'],folds) == f]
        model = MoveModel().fit(train)
        assert not ({r['evaluation_group'] for r in train} & {r['evaluation_group'] for r in test})
        audits.append(dict(fold=f, train_occurrences=len(train), test_occurrences=len(test),
                           train_groups=sorted({r['evaluation_group'] for r in train}),
                           test_groups=sorted({r['evaluation_group'] for r in test}),
                           training_ids=model.training_ids))
        oov.append(dict(fold=f, unknown_move_tokens=sum(m not in model.index for r in test for m in moves(r)),
                        test_move_tokens=4*len(test)))
        for label, rows in targets.items():
            tr = [r for r in rows if fold(r['evaluation_group'],folds) != f]
            te = [r for r in rows if fold(r['evaluation_group'],folds) == f]
            if len(tr) < 5 or not te:
                continue
            for key, config in configs.items():
                for target in targets_to_predict:
                    bd = distance(model,config,tr,target)
                    d = bd.distances(te,tr)
                    # Train-only K=2 demonstration; prediction uses all 5 neighbors.
                    dt = bd.distances(tr,tr); km = kmedoids(dt,min(2,len(tr)))
                    dm = bd.distances(te,[tr[i] for i in km['medoids']])
                    def value(r):
                        return r['item'] if target == 'item' else sum(r['training_points'][s] for s in ('hp','defense','special_defense')) if target == 'bulk' else r['training_points'][target]
                    values = [value(r) for r in tr]
                    mode = lambda v: min(Counter(v), key=lambda x:(-Counter(v)[x],x))
                    baseline = mode(values) if target == 'item' else float(np.median(values))
                    for i,r in enumerate(te):
                        near = np.argsort(d[i],kind='stable')[:min(5,len(tr))]
                        v = [values[j] for j in near]
                        predicted = mode(v) if target == 'item' else float(np.median(v))
                        actual = value(r)
                        loss = int(predicted != actual) if target == 'item' else abs(predicted-actual)
                        base_loss = int(baseline != actual) if target == 'item' else abs(baseline-actual)
                        scores[label][key][target].append(dict(id=r['empirical_record_id'],group=r['evaluation_group'],fold=f,
                            actual=actual,predicted=predicted,baseline=baseline,loss=loss,baseline_loss=base_loss,
                            nearest_ids=[tr[j]['empirical_record_id'] for j in near],
                            train_medoid_ids=[tr[j]['empirical_record_id'] for j in km['medoids']],
                            train_medoid_distances=dm[i].tolist(),train_scales=bd.scales))
    summaries = {}
    for label, methods in scores.items():
        summaries[label] = {}
        for key, ts in methods.items():
            summaries[label][key] = {}
            for target, records in ts.items():
                summaries[label][key][target] = dict(n=len(records),groups=len({r['group'] for r in records}),
                    metric='error_rate' if target=='item' else 'MAE_SP',
                    loss=float(np.mean([r['loss'] for r in records])) if records else None,
                    baseline_loss=float(np.mean([r['baseline_loss'] for r in records])) if records else None,
                    per_fold=[dict(fold=f,n=sum(r['fold']==f for r in records),
                                   loss=float(np.mean([r['loss'] for r in records if r['fold']==f])),
                                   baseline_loss=float(np.mean([r['baseline_loss'] for r in records if r['fold']==f])))
                              for f in range(folds) if any(r['fold']==f for r in records)])
    return dict(summaries=summaries,predictions=scores,split_audit=audits,oov=oov,
                interpretation='Exploratory grouped prediction; no independent external test or calibrated uncertainty. SP targets are masked in both normalization and prediction. Natures remain as known covariates; item is excluded when predicting item.')


def choose(result, stability):
    # Conservative descriptive screen, NOT optimized to held-out prediction.
    # K=1 remains the result unless separation, size and repeatability all pass.
    eligible = []
    n = len(result['occurrence_ids'])
    for c in result['kmedoids'][1:]:
        aris = [x['ari'] for x in stability[str(c['k'])] if x['ari'] is not None]
        if c['minimum_size'] >= max(3,math_ceil(.1*n)) and c['silhouette'] >= .25 and len(aris) >= 3 and np.mean(aris) >= .65:
            eligible.append(c)
    return min(eligible,key=lambda c:c['k'])['k'] if eligible else 1


def math_ceil(x):
    return int(np.ceil(x))


def identity_fingerprint(database):
    # Capture adapter, rule, form, knowledge and classification dependencies.
    paths = [database/'teams.sqlite3', ROOT/'pyproject.toml', ROOT/'experiments/build_similarity/requirements.txt']
    if (database/'teams.sqlite3-wal').exists():
        paths.append(database/'teams.sqlite3-wal')
    for directory in ('experiments/build_similarity','knowledge','battle_evidence','metagame/published','speed_order','damage'):
        paths += sorted(p for p in (ROOT/directory).glob('*.py') if p.name != 'report.py')
        paths += sorted((ROOT/directory).glob('*.json'))
        paths += sorted((ROOT/directory/'data').glob('*.json'))
    files = {str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):file_hash(p) for p in paths}
    identity = dict(version=VERSION,files=files, numpy=np.__version__,python=platform.python_version(),
                    folds=3,resamples=3,seed=351,variants=list(variants()))
    signature = hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:20]
    return signature, identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path,default=ROOT/'.cache/metagame/published-teams')
    parser.add_argument('--output',type=Path,default=ROOT/'.cache/research/m351')
    parser.add_argument('--report',type=Path,default=ROOT/'reports/M3.5.1-build-similarity.md')
    args = parser.parse_args()
    fingerprint, identity = identity_fingerprint(args.database.resolve())
    out = args.output/fingerprint
    out.mkdir(parents=True,exist_ok=True)
    # Exclusive process lock: OS releases it after a disconnect/crash.
    import fcntl
    lock = (out/'study.lock').open('a')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('A study with this fingerprint is already running')
    manifest_path = out/'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else dict(identity=identity,fingerprint=fingerprint,stages={})
    import matplotlib
    report_identity = dict(code_sha256=file_hash(Path(__file__).with_name('report.py')),
                           matplotlib=matplotlib.__version__, report=str(args.report.resolve()))
    def stage(name, fn):
        path=out/(name+'.json'); prior=manifest['stages'].get(name,{})
        valid = prior.get('status')=='complete' and path.exists() and file_hash(path)==prior.get('sha256')
        if valid and name == 'report':
            valid = prior.get('report_identity') == report_identity
            outputs = json.loads(path.read_text())['files']
            valid = valid and all(Path(p).exists() and file_hash(p) == expected for p, expected in outputs.items())
        if valid:
            print('reuse',name,flush=True); return json.loads(path.read_text())
        reason='missing stage' if not prior else 'incomplete stage or missing/changed output'
        manifest['stages'][name]=dict(status='running',started=time.time(),reason=reason)
        atomic(manifest_path,manifest); print('start',name,flush=True)
        try:
            result=fn(); atomic(path,result)
            manifest['stages'][name]=dict(status='complete',sha256=file_hash(path),output=str(path),completed=time.time())
            if name == 'report':
                manifest['stages'][name]['report_identity'] = report_identity
            atomic(manifest_path,manifest); print('done',name,flush=True); return result
        except Exception:
            manifest['stages'][name].update(status='failed',error=traceback.format_exc())
            atomic(manifest_path,manifest); raise
    data = stage('population',lambda:dict(zip(('training','targets','audit'),prepare(args.database))))
    training,targets=data['training'],data['targets']
    configs=variants()
    # Small vocabulary SVD; these inexpensive in-memory fits avoid loading dumps.
    models={dim:MoveModel(dimension=dim).fit(training) for dim in (8,16,32)}
    stage('moves',models[16].diagnostics)
    results,stabilities={},{}
    for label,rows in targets.items():
        results[label]={}
        for key,config in configs.items():
            results[label][key]=stage(slug(label)+'-'+key,lambda rows=rows,config=config:run_configuration(rows,models[config.get('dimension',16)],config))
        stabilities[label]=stage(slug(label)+'-stability',lambda rows=rows,label=label:resampling(training,rows,configs,results[label]))
    evaluation=stage('heldout',lambda:heldout(training,targets,{key:configs[key] for key in ('sp','jaccard','learned','item-nature')}))
    selected={label:{key:choose(r,stabilities[label][key]) for key,r in methods.items()} for label,methods in results.items()}
    stage('selection',lambda:selected)
    from .report import render
    stage('report',lambda:render(out,args.report,data,results,stabilities,evaluation,selected,models[16]))
    manifest.update(status='complete',report=str(args.report),resume=f'.venv/bin/python -m experiments.build_similarity.study --database {args.database} --output {args.output} --report {args.report}')
    atomic(manifest_path,manifest)
    atomic(args.output/'latest.json',dict(path=str(out.resolve()),fingerprint=fingerprint))
    print('Report:',args.report,flush=True)


if __name__=='__main__':
    main()
