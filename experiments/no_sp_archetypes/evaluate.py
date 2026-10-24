"""Grouped internal checks. Hidden SP is used only to define evaluation labels."""
from collections import Counter
from itertools import permutations
import hashlib
import math
import numpy as np
from experiments.build_similarity.core import SPConfig, sp_array, sp_distances, kmedoids
from .model import Predictor


def fold_id(group, seed, folds=3):
    return int(hashlib.sha256(f'm353:{seed}:{group}'.encode()).hexdigest(), 16) % folds


def metrics(truth, probabilities):
    p = np.asarray(probabilities, float); y = np.asarray(truth, int)
    if not len(y): raise ValueError('Empty evaluation partition')
    predicted = p.argmax(1)
    confusion = np.zeros((3,3), int)
    for a,b in zip(y,predicted): confusion[a,b] += 1
    return dict(n=len(y), accuracy=float((predicted==y).mean()),
                recall=[float(confusion[z,z]/confusion[z].sum()) if confusion[z].sum() else None for z in range(3)],
                confusion=confusion.tolist(), brier=float(((p-np.eye(3)[y])**2).sum(1).mean()),
                nll=float(-np.log(np.maximum(p[np.arange(len(y)),y],1e-15)).mean()))


def evaluate(rows, reference_medoids, config, seeds=(353,354,355), progress=lambda _: None):
    """K=3/settings fixed; refit all training labels inside each source fold.

    Match fold medoids to frozen reference medoids by minimum SP dissimilarity
    permutation ONLY to name columns consistently. It changes neither partitions
    nor scores and never uses held-out records to fit the classifier.
    """
    reports, predictions = [], []
    for seed in seeds:
        seed_predictions=[]
        for fold in range(3):
            train = [r for r in rows if fold_id(r['evaluation_group'],seed)!=fold]
            test = [r for r in rows if fold_id(r['evaluation_group'],seed)==fold]
            if len(train)<3 or not test: raise ValueError('Insufficient grouped split')
            groups_train={r['evaluation_group'] for r in train};groups_test={r['evaluation_group'] for r in test}
            assert not groups_train & groups_test
            x=sp_array(train);d=sp_distances(x,x,config)
            # Positive scale is trained on this fold only; uniform scaling
            # leaves PAM assignments and nearest-medoid labels unchanged.
            positive=d[np.triu_indices(len(d),1)];positive=positive[positive>0]
            scale=float(np.median(positive)) if len(positive) else 1.
            fit=kmedoids(d/scale,3)
            medoids=[train[i] for i in fit['medoids']]
            cross=sp_distances(sp_array(medoids),sp_array(reference_medoids),config)
            perm=min(permutations(range(3)),key=lambda perm:(sum(cross[z,perm[z]] for z in range(3)),perm))
            labels=[perm[z] for z in fit['labels']]
            model=Predictor(train,labels)
            truth=[perm[int(z)] for z in sp_distances(sp_array(test),sp_array(medoids),config).argmin(1)]
            probs={name:[] for name in ('prior','majority','moves','moves_item')}
            for row,y in zip(test,truth):
                prediction=model.predict(row['configuration']['moves'],row.get('item'))
                majority=[0.,0.,0.];majority[max(range(3),key=lambda z:model.prior[z])]=1.
                candidates=dict(prior=model.prior,majority=majority,moves=prediction['moves_only']['weights'],
                                moves_item=(prediction['moves_item'] or prediction['moves_only'])['weights'])
                for name,p in candidates.items():probs[name].append(p)
                entry=dict(id=row['empirical_record_id'],seed=seed,fold=fold,group=row['evaluation_group'],truth=y,probabilities=candidates)
                predictions.append(entry);seed_predictions.append(entry)
            reports.append(dict(seed=seed,fold=fold,training_ids=[r['empirical_record_id'] for r in train],
                                test_ids=[r['empirical_record_id'] for r in test],training_groups=sorted(groups_train),test_groups=sorted(groups_test),
                                medoid_ids=[r['empirical_record_id'] for r in medoids],label_permutation=list(perm),scale=scale,
                                train_sizes=model.sizes,test_sizes=[truth.count(z) for z in range(3)],
                                metrics={name:metrics(truth,p) for name,p in probs.items()}))
            progress(dict(seed=seed,fold=fold,completed_folds=len(reports),total_folds=len(seeds)*3))
    per_seed=[]
    for seed in seeds:
        ps=[p for p in predictions if p['seed']==seed]
        per_seed.append(dict(seed=seed,metrics={name:metrics([p['truth'] for p in ps],[p['probabilities'][name] for p in ps]) for name in ('prior','majority','moves','moves_item')}))
    return dict(folds=reports,predictions=predictions,per_seed=per_seed,
                pooled={name:metrics([p['truth'] for p in predictions],[p['probabilities'][name] for p in predictions]) for name in ('prior','majority','moves','moves_item')},
                interpretation='Repeated grouped internal evaluation; pooled entries repeat occurrences across seeds; no independent external labels')
