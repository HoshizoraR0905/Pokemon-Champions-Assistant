"""Portable M3.5.1 math, source multiplicity and leakage regressions."""
from copy import deepcopy
from dataclasses import replace
import math
import numpy as np
import pytest
from experiments.build_similarity.core import (SPConfig, sp_array, sp_distances,
    MoveModel, BuildDistance, kmedoids, hierarchical, cut_tree, silhouette,
    adjusted_rand, soft_membership, moves)
from experiments.build_similarity.data import source_groups, fold
from experiments.build_similarity.study import distance, heldout, run_configuration


def row(i, sp=(32,0,2,32,0,0), ms=('a','b','c','d'), team=None, item='item-a'):
    return dict(empirical_record_id=str(i), training_points=dict(zip(('hp','attack','defense','special_attack','special_defense','speed'),sp)),
        configuration=dict(species='hatterene',sp=dict(kind='champions_sp',values=list(sp)),moves=list(ms),ability='ability-a',nature='quiet',item=item),
        item=item,nature='quiet',ability='ability-a',species='hatterene',
        observed_team_signature=team or 'team-'+str(i), evaluation_group=team or 'group-'+str(i),
        publications=[dict(id='p'+str(i),url='url'+str(i),source_key='s'+str(i))],
        original_record_ids=['original-'+str(i)])


def sp_pair(x,y,config=SPConfig()):
    return sp_distances(np.array([x]),np.array([y]),config)[0,0]


@pytest.mark.parametrize('formulation',['raw','proportion'])
def test_sp_symmetry_zero_convexity_zero_bulk_and_determinism(formulation):
    config=SPConfig(formulation=formulation)
    examples=np.array([[32,0,2,32,0,0],[24,0,5,32,5,0],[20,32,8,0,6,0],[32,0,10,0,24,0],[0,0,0,0,0,0],[0,32,0,32,0,2]])
    matrix=sp_distances(examples,examples,config)
    assert np.array_equal(matrix,sp_distances(examples,examples,config))
    assert np.allclose(matrix,matrix.T) and (matrix>=0).all() and np.allclose(np.diag(matrix),0)
    zero=[0]*6
    small=sp_pair(zero,[0,4,0,0,0,0],config)
    medium=sp_pair(zero,[0,8,0,0,0,0],config)
    large=sp_pair(zero,[0,32,0,0,0,0],config)
    assert 0<small<medium<large
    assert medium>2*small
    assert sp_pair(zero,[16,0,0,0,0,0],config)>0
    assert sp_pair(zero,zero,config)==0
    # Explicit analytic convex second difference at many normalized positions.
    phi=lambda t: math.expm1(config.gamma*t)
    assert all(phi(t-.01)+phi(t+.01)>2*phi(t) for t in np.linspace(.01,.99,50))


def test_hatterene_defensive_reallocation_is_modest_and_incineroar_attack_speed_distinguished():
    hat=[32,0,2,32,0,0]; other=[24,0,5,32,5,0]
    redistribute=sp_pair(hat,other)
    offensive=sp_pair([20,0,8,0,6,0],[20,32,8,0,6,0])
    assert 0<redistribute<offensive/5
    levels=[[20,0,8,0,6,v] for v in (0,8,16,32)]
    assert sp_pair(levels[0],levels[1])<sp_pair(levels[0],levels[2])<sp_pair(levels[0],levels[3])
    for formulation in ('raw','proportion'):
        d=SPConfig(formulation=formulation)
        assert sp_pair([0,0,0,0,0,0],[0,32,0,0,0,0],d)>2*sp_pair([0,0,0,0,0,0],[0,16,0,0,0,0],d)
    # Proportion allocation contributes exactly zero if either bulk is zero.
    base=SPConfig(formulation='proportion')
    assert sp_pair([0]*6,[32,0,0,0,0,0],base)==sp_pair([0]*6,[32,0,0,0,0,0],replace(base,allocation=0))


@pytest.mark.parametrize('sp',[(33,0,0,0,0,0),(32,32,3,0,0,0),(-1,0,0,0,0,0),(1.5,0,0,0,0,0)])
def test_illegal_sp_rejected(sp):
    with pytest.raises(ValueError):sp_array([row(0,sp)])
    with pytest.raises(ValueError):sp_distances(np.array([sp]),np.zeros((1,6)))


@pytest.mark.parametrize('kwargs',[dict(gamma=0),dict(defense=-1),dict(gamma=float('nan')),dict(offense_scale=0),dict(formulation='bad')])
def test_invalid_sp_parameters(kwargs):
    with pytest.raises(ValueError):SPConfig(**kwargs)


def test_moves_are_exactly_four_and_order_invariant():
    a=row(0); b=row(1,ms=('d','b','a','c'))
    assert moves(a)==moves(b)
    with pytest.raises(ValueError):moves(row(2,ms=('a','b','c')))
    with pytest.raises(ValueError):moves(row(2,ms=('a','b','c','d','item')))


def test_cooccurrence_preserves_multiplicity_support_and_is_not_raw_count_similarity():
    rows=[row(i,ms=('common','a','b','c') if i<8 else ('common','d','e','f')) for i in range(10)]
    model=MoveModel(dimension=4).fit(rows)
    i,j=model.index['a'],model.index['b']
    assert model.n==10 and model.frequency[model.index['common']]==10
    assert model.counts[i,j]==8
    assert model.counts[model.index['d'],model.index['e']]==2
    assert model.association[model.index['common'],i] < model.association[i,j]/5
    assert np.all(np.diag(model.association)==0)
    assert np.all(model.association>=0) and np.max(model.association)<=3
    assert model.diagnostics()['equal_weight_kish_ess']==10
    assert len(model.training_ids)==10
    assert np.allclose(model.distances(rows,rows),MoveModel(dimension=4).fit(rows).distances(rows,rows))


def test_transform_unknown_moves_never_refits_or_adds_vocabulary():
    rows=[row(0),row(1,ms=('a','b','e','f'))]
    model=MoveModel().fit(rows); before=model.embedding.copy()
    unseen=[row(9,ms=('w','x','y','z'))]
    assert (model.transform(unseen)==0).all()
    assert model.distances(unseen,unseen)[0,0]==0
    assert (model.distances(unseen,rows)==1).all()
    assert 'w' not in model.index and np.array_equal(before,model.embedding)
    assert model.training_ids==['0','1']


def test_normalization_is_train_only_and_constant_features_are_finite():
    rows=[row(0),row(1)]
    model=MoveModel().fit(rows)
    bd=BuildDistance(model,weights=(1,1,1,1)).fit(rows)
    assert bd.scales==[1.,1.,1.,1.]
    assert np.allclose(bd.distances(rows,rows),0)
    test=[row(4,sp=(0,32,0,0,0,32),ms=('a','b','e','f'),item='item-b')]
    before=list(bd.scales)
    assert np.isfinite(bd.distances(test,rows)).all() and bd.scales==before
    jac=BuildDistance(model,move='jaccard').fit(rows)
    assert jac.components(test,rows)[1][0,0]==pytest.approx(1-2/6)


def test_pam_occurrence_weighting_changes_observed_medoid():
    d=np.array([[0,1,9],[1,0,8],[9,8,0]],float)
    assert kmedoids(d,1)['medoids']==[1]
    repeated=[0,1,2,2,2]
    weighted=d[np.ix_(repeated,repeated)]
    result=kmedoids(weighted,1)
    assert repeated[result['medoids'][0]]==2
    assert result==kmedoids(weighted,1)
    two=kmedoids(weighted,2)
    assert sorted(Counter(two['labels']).values())==[2,3]


from collections import Counter

def test_hierarchy_precomputed_average_and_multiple_cuts():
    d=np.array([[0,1,8,10],[1,0,9,11],[8,9,0,2],[10,11,2,0]],float)
    tree=hierarchical(d)
    assert [x[2] for x in tree]==[1,2,9.5]
    assert cut_tree(4,tree,k=1)==[0,0,0,0]
    assert cut_tree(4,tree,k=2)==[0,0,1,1]
    assert cut_tree(4,tree,threshold=1.5)==[0,0,1,2]
    assert silhouette(d,[0,0,1,1])>.8
    assert silhouette(d,[0]*4) is None
    assert adjusted_rand([0,0,1,1],[1,1,0,0])==1
    assert adjusted_rand([0,0,1,1],[0,1,0,1])<0
    with pytest.raises(ValueError):kmedoids(d,0)
    with pytest.raises(ValueError):hierarchical(d+1)


def test_soft_scores_are_finite_temperature_sensitive_similarity_scores():
    d=np.array([[0,3],[1e8,1e8+3]])
    p=soft_membership(d,[9,1],1)
    assert np.allclose(p.sum(1),1) and (p>=0).all()
    assert p[0,0]>.9
    assert soft_membership(d,[9,1],.1)[0,0]>p[0,0]
    with pytest.raises(ValueError):soft_membership(d,[9,1],0)


def test_groups_join_related_records_transitively_without_changing_counts():
    rows=[row(i) for i in range(4)]
    rows[1]['publications'][0]['id']=rows[0]['publications'][0]['id']
    rows[2]['observed_team_signature']=rows[1]['observed_team_signature']
    before=deepcopy(rows); groups=source_groups(rows)
    assert groups['0']==groups['1']==groups['2'] and groups['3']!=groups['0']
    assert len(rows)==4 and rows==before
    assert fold(groups['0'])==fold(groups['2'])


@pytest.mark.parametrize('target',['speed','attack','special_attack','bulk','item'])
def test_prediction_target_is_excluded_before_scale_fitting(target):
    rows=[row(i,sp=(12,10,10,10,10,v)) for i,v in enumerate((0,2,4,6))]
    model=MoveModel().fit(rows); config=dict(sp=SPConfig(),weights=(1,1,.5,.5))
    a=deepcopy(rows[0]); b=deepcopy(a)
    if target=='item':b['item']='other'
    elif target=='bulk':b['training_points']['hp']=10;b['training_points']['defense']=5
    else:b['training_points'][target]=12
    bd=distance(model,config,rows,target)
    assert bd.distances([a],[b])[0,0]==pytest.approx(0)


def test_grouped_holdout_predictions_and_clustering_keep_provenance_and_are_reproducible():
    rows=[]
    for i in range(24):
        r=row(i,sp=(20,i%8,4,16,4,i%16),ms=('a','b','c','d') if i%2 else ('a','b','e','f'))
        rows.append(r)
    config={'sp':dict(sp=SPConfig(),weights=(1,0,0,0))}
    evaluation=heldout(rows,{'fixture':rows},config)
    assert evaluation==heldout(rows,{'fixture':rows},config)
    assert evaluation['summaries']['fixture']['sp']['speed']['n']==24
    for audit in evaluation['split_audit']:
        assert not set(audit['train_groups']) & set(audit['test_groups'])
    byid={r['empirical_record_id']:r for r in rows}
    for predictions in evaluation['predictions']['fixture']['sp'].values():
        for pred in predictions:
            assert all(fold(byid[n]['evaluation_group'])!=pred['fold'] for n in pred['nearest_ids'])
            assert all(fold(byid[n]['evaluation_group'])!=pred['fold'] for n in pred['train_medoid_ids'])
    result=run_configuration(rows,MoveModel().fit(rows),config['sp'])
    assert result['occurrence_ids']==[r['empirical_record_id'] for r in rows]
    for candidate in result['kmedoids']:
        assert sum(candidate['sizes'])==24
        assert all(summary['medoid'] in byid for summary in candidate['summaries'])
        assert all(len(moves(byid[summary['medoid']]))==4 for summary in candidate['summaries'])


def test_pooling_configuration_and_explicit_association_estimator():
    rows=[row(i,ms=('common','a','b','c') if i<8 else ('common','d','e','f')) for i in range(10)]
    model=MoveModel(dimension=4).fit(rows)
    a,b=model.index['a'],model.index['b']
    expected=min(3,max(0,math.log(((8+.5)/12)/((8+1)/12)**2)))*8/13
    assert model.association[a,b]==pytest.approx(expected)
    unit=MoveModel(dimension=4,pooling='unit-mean').fit(rows)
    assert np.isfinite(unit.transform(rows)).all()
    assert unit.diagnostics()['parameters']['pooling']=='unit-mean'
    assert not np.allclose(model.transform(rows),unit.transform(rows))
    with pytest.raises(ValueError):MoveModel(pooling='unknown')


def test_prepare_preserves_identical_occurrences_and_original_full_builds(monkeypatch):
    import experiments.build_similarity.data as data
    from battle_evidence.empirical_measure import full_record_signature
    forms=list(data.SPECIES.values())
    first=row(0); second=row(1); mega=row(2)
    first['species']=second['species']=forms[0]; mega['species']=forms[2]
    inputs=[first,second,mega]; before=deepcopy(inputs)
    # The adapter may return compatible contexts; own-form selection ensures a
    # single occurrence in global learning without merging equal configurations.
    def cat(population,form):
        return dict(frequency_rows=[r for r in inputs if r['species']==form],core_ineligible=[],grouping='existing-compatible-context')
    monkeypatch.setattr(data,'load_vgc',lambda _:dict(by_form={f:{} for f in forms},scope={'source':'vgcmulticalc'}))
    monkeypatch.setattr(data,'catalog',cat)
    training,targets,audit=data.prepare('never-opened')
    assert len(training)==3 and len(targets['Hatterene'])==2
    assert full_record_signature(training[0])==full_record_signature(training[1])
    assert inputs==before
    assert {r['empirical_record_id'] for r in training}=={'0','1','2'}
    for r in training:
        original=next(v for v in inputs if v['empirical_record_id']==r['empirical_record_id'])
        assert r['configuration']==original['configuration']
        assert r['publications']==original['publications']
        assert r['original_record_ids']==original['original_record_ids']
