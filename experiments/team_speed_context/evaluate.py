"""Same-fold paired regression, training-group permutations and learning curves."""
from collections import defaultdict
from copy import deepcopy
import hashlib
import numpy as np
from .features import DESIGN, FEATURES, FAMILIES
from .model import Ridge, TARGETS, interaction_support


def rank(value):return hashlib.sha256(value.encode()).hexdigest()


def group_folds(rows,seed):
    groups=sorted({r['group'] for r in rows},key=lambda g:rank(f'm354:{seed}:{g}'))
    if len(groups)<DESIGN['outer_folds']:raise ValueError('Insufficient independent source groups')
    return {g:i%DESIGN['outer_folds'] for i,g in enumerate(groups)}


def metrics(truth,predictions,groups=None):
    y=np.asarray(truth,float);p=np.asarray(predictions,float);error=np.abs(y-p)
    if not len(y):return dict(n=0,mae=[None]*3,median_absolute_error=[None]*3,group_macro_mae=[None]*3)
    if groups is None:groups=list(range(len(y)))
    grouped=[[i for i,g in enumerate(groups) if g==key] for key in sorted(set(groups))]
    return dict(n=len(y),groups=len(grouped),mae=error.mean(0).tolist(),median_absolute_error=np.median(error,axis=0).tolist(),
                group_macro_mae=np.mean([error[ids].mean(0) for ids in grouped],axis=0).tolist())


def permute_groups(rows,seed):
    """Bijective whole-group block permutation in equal-multiplicity strata.

    Donor vectors are copied intact; own observations, targets and group IDs
    never change. Only the supplied training rows can supply donor context.
    """
    output=deepcopy(rows);groups=defaultdict(list)
    for i,row in enumerate(rows):groups[row['group']].append(i)
    strata=defaultdict(list)
    for g,indices in groups.items():strata[len(indices)].append(g)
    rng=np.random.default_rng(seed);mapping={};unexchangeable=[]
    for size,keys in sorted(strata.items()):
        keys=sorted(keys);donors=rng.permutation(keys).tolist()
        if len(keys)==1:unexchangeable+=keys
        for receiver,donor in zip(keys,donors):
            mapping[receiver]=donor
            dst=sorted(groups[receiver],key=lambda i:rows[i]['id']);src=sorted(groups[donor],key=lambda i:rows[i]['id'])
            for i,j in zip(dst,src):output[i]['context']=deepcopy(rows[j]['context'])
    return output,dict(seed=seed,donor_groups=mapping,unexchangeable_groups=unexchangeable,
                       fixed_point_groups=sum(a==b for a,b in mapping.items()),stratum_group_counts={str(size):len(keys) for size,keys in strata.items()})


def training_subset(rows,seed,fold,fraction):
    groups=sorted({r['group'] for r in rows},key=lambda g:rank(f'm354-learning:{seed}:{fold}:{g}'))
    count=max(1,int(np.ceil(len(groups)*fraction)))
    selected=set(groups[:count]);return [i for i,r in enumerate(rows) if r['group'] in selected]


def evaluate_fold(rows,targets,seed,fold):
    mapping=group_folds(rows,seed)
    train_indices=[i for i,r in enumerate(rows) if mapping[r['group']]!=fold]
    test_indices=[i for i,r in enumerate(rows) if mapping[r['group']]==fold]
    train=[rows[i] for i in train_indices];test=[rows[i] for i in test_indices]
    y=np.asarray(targets,float);ytrain=y[train_indices];ytest=y[test_indices]
    train_groups=sorted({r['group'] for r in train});test_groups=sorted({r['group'] for r in test})
    if not train or not test or set(train_groups)&set(test_groups):raise ValueError('Invalid grouped fold')
    specs={'B_own':[],'C_context':FEATURES,**{'plus_'+family:names for family,names in FAMILIES.items()}}
    predictions={'A_median':np.tile(np.median(ytrain,axis=0),(len(test),1)).tolist()}
    train_predictions={'A_median':np.tile(np.median(ytrain,axis=0),(len(train),1)).tolist()}
    receipts={};trained={}
    for name,features in specs.items():
        model=Ridge(features).fit(train,ytrain);trained[name]=model
        predictions[name]=model.predict(test).tolist();train_predictions[name]=model.predict(train).tolist();receipts[name]=model.receipt()
    interactions={}
    for spec in DESIGN['interactions']:
        name=spec['name'];support=interaction_support(train,name);interactions[name]=support
        if support['fit']:
            model=Ridge(FEATURES,interaction=name).fit(train,ytrain)
            predictions['D_'+name]=model.predict(test).tolist();train_predictions['D_'+name]=model.predict(train).tolist();receipts['D_'+name]=model.receipt()
    controls=[]
    for permutation_seed in DESIGN['permutation_seeds']:
        effective_seed=permutation_seed+1000*seed+fold
        permuted,receipt=permute_groups(train,effective_seed)
        model=Ridge(FEATURES).fit(permuted,ytrain)
        # The same real held-out contexts remain untouched.
        controls.append(dict(permutation_seed=permutation_seed,receipt=receipt,
                             predictions=model.predict(test).tolist(),train_predictions=model.predict(permuted).tolist(),
                             preprocessing=model.encoder.receipt()))
    curves=[]
    for fraction in DESIGN['learning_fractions']:
        indices=training_subset(train,seed,fold,fraction)
        subset=[train[i] for i in indices];ysub=ytrain[indices]
        for name,features in [('B_own',[]),('C_context',FEATURES)]:
            if fraction==1.:
                model=trained[name]
            else:model=Ridge(features).fit(subset,ysub)
            curves.append(dict(fraction=fraction,model=name,training_ids=[r['id'] for r in subset],training_groups=sorted({r['group'] for r in subset}),
                training=metrics(ysub,model.predict(subset),[r['group'] for r in subset]),
                heldout=metrics(ytest,model.predict(test),[r['group'] for r in test])))
    per_group=[]
    for g in test_groups:
        indices=[i for i,r in enumerate(test) if r['group']==g]
        per_group.append(dict(group=g,ids=[test[i]['id'] for i in indices],metrics={name:metrics(ytest[indices],np.asarray(p)[indices]) for name,p in predictions.items()}))
    return dict(seed=seed,fold=fold,training_ids=[r['id'] for r in train],test_ids=[r['id'] for r in test],
                training_groups=train_groups,test_groups=test_groups,truth=ytest.tolist(),training_truth=ytrain.tolist(),
                predictions=predictions,train_predictions=train_predictions,model_receipts=receipts,interaction_support=interactions,
                controls=controls,learning_curves=curves,per_group=per_group,
                train_metrics={name:metrics(ytrain,p,[r['group'] for r in train]) for name,p in train_predictions.items()},
                heldout_metrics={name:metrics(ytest,p,[r['group'] for r in test]) for name,p in predictions.items()})


def summarize(rows,targets,folds):
    byid={r['id']:r for r in rows};all_predictions=[]
    for result in folds:
        for i,rid in enumerate(result['test_ids']):
            r=byid[rid]
            all_predictions.append(dict(id=rid,group=r['group'],seed=result['seed'],fold=result['fold'],truth=result['truth'][i],
                                        predictions={name:p[i] for name,p in result['predictions'].items()}))
    methods=list(folds[0]['predictions'])
    truth=[r['truth'] for r in all_predictions];groups=[r['group'] for r in all_predictions]
    pooled={name:metrics(truth,[r['predictions'][name] for r in all_predictions],groups) for name in methods if all(name in r['predictions'] for r in all_predictions)}
    per_seed=[]
    for seed in DESIGN['outer_seeds']:
        records=[r for r in all_predictions if r['seed']==seed]
        per_seed.append(dict(seed=seed,metrics={name:metrics([r['truth'] for r in records],[r['predictions'][name] for r in records],[r['group'] for r in records]) for name in pooled}))
    permutation=[]
    for seed in DESIGN['permutation_seeds']:
        predicted=[];actual=[];pgroups=[];training=[]
        for f in folds:
            c=next(c for c in f['controls'] if c['permutation_seed']==seed)
            predicted+=c['predictions'];actual+=f['truth'];pgroups += [byid[rid]['group'] for rid in f['test_ids']]
            training.append(metrics(f['training_truth'],c['train_predictions']))
        pm=metrics(actual,predicted,pgroups)
        permutation.append(dict(seed=seed,metrics=pm,improvement_vs_B=(np.array(pooled['B_own']['mae'])-pm['mae']).tolist()))
    subgroups={}
    for label,predicate in [('high_attack',lambda y:y[1]>=DESIGN['subgroup_thresholds']['high_attack']),
                            ('higher_speed',lambda y:y[0]>=DESIGN['subgroup_thresholds']['higher_speed'])]:
        rs=[r for r in all_predictions if predicate(r['truth'])]
        subgroups[label]=dict(observations=len({r['id'] for r in rs}),groups=len({r['group'] for r in rs}),
            metrics={name:metrics([r['truth'] for r in rs],[r['predictions'][name] for r in rs],[r['group'] for r in rs]) for name in pooled})
    family_groups={}
    for feature in FEATURES:
        for positive in (False,True):
            rs=[r for r in all_predictions if byid[r['id']]['context'][feature] is not None and (byid[r['id']]['context'][feature]>0)==positive]
            if not rs:continue
            family_groups[feature+('>0' if positive else '=0')]=dict(observations=len({r['id'] for r in rs}),groups=len({r['group'] for r in rs}),
                metrics={name:metrics([r['truth'] for r in rs],[r['predictions'][name] for r in rs],[r['group'] for r in rs]) for name in ('A_median','B_own','C_context')})
    paired=[]
    for r in all_predictions:
        eb=np.abs(np.array(r['truth'])-r['predictions']['B_own']);ec=np.abs(np.array(r['truth'])-r['predictions']['C_context'])
        paired.append(dict(id=r['id'],group=r['group'],seed=r['seed'],fold=r['fold'],improvement=(eb-ec).tolist()))
    unique_groups=sorted({r['group'] for r in rows})
    group_improvements=[dict(group=g,n_observations=len({r['id'] for r in paired if r['group']==g}),
                             mean_improvement=np.mean([r['improvement'] for r in paired if r['group']==g],axis=0).tolist()) for g in unique_groups]
    training={name:dict(mae=np.mean([f['train_metrics'][name]['mae'] for f in folds],axis=0).tolist(),
                        description='Mean across training folds; repeated training observations are not independent') for name in pooled}
    coefficients=[]
    for f in folds:
        receipt=f['model_receipts']['C_context']
        for name,values in zip(receipt['preprocessing']['all_feature_names'],receipt['coefficients']):
            if name in FEATURES or name.startswith('missing:'):coefficients.append(dict(seed=f['seed'],fold=f['fold'],feature=name,coefficients=values))
    return dict(pooled=pooled,per_seed=per_seed,permutation=permutation,subgroups=subgroups,feature_subgroups=family_groups,
                training=training,paired=paired,group_improvements=group_improvements,
                predictions=all_predictions,coefficients=coefficients,
                learning_curves=[dict(seed=f['seed'],fold=f['fold'],**c) for f in folds for c in f['learning_curves']],
                interaction_support=[dict(seed=f['seed'],fold=f['fold'],**f['interaction_support']) for f in folds],
                split_counts=[dict(seed=f['seed'],fold=f['fold'],train=len(f['training_ids']),test=len(f['test_ids']),train_groups=len(f['training_groups']),test_groups=len(f['test_groups'])) for f in folds],
                permutation_unexchangeable_groups=sum(len(c['receipt']['unexchangeable_groups']) for f in folds for c in f['controls']))
