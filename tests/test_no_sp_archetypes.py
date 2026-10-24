"""Portable selection, provenance, leakage, model and durable review regressions."""
from copy import deepcopy
from collections import Counter
from dataclasses import asdict
from http.client import HTTPConnection
from pathlib import Path
import json
import sqlite3
import threading

import numpy as np
import pytest

from experiments.no_sp_archetypes.data import (sp_status, application_eligible, reasons,
    adapt_publications, observable_team_signature, connected_groups, split_application)
from experiments.no_sp_archetypes.model import Predictor, moveset
from experiments.no_sp_archetypes.evaluate import evaluate, fold_id, metrics
from experiments.no_sp_archetypes.review import ReviewStore, handler_for
from experiments.no_sp_archetypes.study import select_queue
from experiments.build_similarity.core import SPConfig
from metagame.published.canonical import Canonicalizer
from http.server import ThreadingHTTPServer


@pytest.fixture(scope='module')
def canonicalizer():return Canonicalizer()


def raw(sp=None,**kwargs):
    value=dict(species='Incineroar',item='Sitrus Berry',ability='Intimidate',nature='Adamant',
               moves=['Fake Out','Flare Blitz','Parting Shot','Throat Chop'])
    if sp is not None:value['sp']=dict(kind='champions_sp',values=list(sp))
    value.update(kwargs);return value


def publication(c,pid='p',url=None):
    return dict(id=pid,extraction_id='e'+pid,source_url=url or 'https://example.com/'+pid,
                source_key='source-'+pid,source_id='vgcmulticalc',title='Example '+pid,
                record_sha256='hash-'+pid,canonical=json.dumps(c))


@pytest.mark.parametrize('vector,status',[(None,'missing_sp'),([32,None,0,0,0,0],'partial_sp'),
    ([32,32,0,0,0,2],'valid_sp'),([33,0,0,0,0,0],'invalid_sp'),([32,32,4,0,0,0],'invalid_sp')])
def test_sp_selection_keeps_unknown_and_rejects_invalid_training(canonicalizer,vector,status):
    m=canonicalizer.mon(raw(vector));assert sp_status(m)==status
    assert application_eligible(m)==(status!='valid_sp')
    if status=='missing_sp':assert m['normalized']['sp']['values']==[None]*6


def test_audit_distinguishes_missing_fields_and_unresolved_identity(canonicalizer):
    m=canonicalizer.mon(raw(item=None,nature=None,moves=['Fake Out']))
    assert set(reasons(m))>={'missing_sp','missing_or_conflicting_item','missing_or_conflicting_nature','missing_or_conflicting_moves'}
    assert not application_eligible(m)
    m=canonicalizer.mon(raw(species='Definitely unresolved species'))
    assert sp_status(m)=='missing_sp'  # "species" must not match the field "sp".
    assert 'unresolved_species_form' in reasons(m)
    assert not application_eligible(m)


def test_non_sp_compatibility_and_optional_missing_item_nature(canonicalizer):
    for opts in [dict(ability='Drizzle'),dict(item='Charizardite Y')]:
        m=canonicalizer.mon(raw(**opts));assert not application_eligible(m)
        assert any('incompatibility' in r for r in reasons(m))
    m=canonicalizer.mon(raw(item=None,nature=None,ability=None))
    assert application_eligible(m)
    m=canonicalizer.mon(raw(conflicts=['build_export_disagreement']))
    assert not application_eligible(m)


def team(canonicalizer,sp=None):
    target=raw(sp)
    mates=[raw(sp,species=s) for s in ('Pelipper','Oranguru','Hatterene','Dragonite','Pikachu')]
    return canonicalizer.team(dict(pokemon=[target,*mates]))


def test_team_join_provenance_and_original_occurrence_identity(canonicalizer):
    c=team(canonicalizer)
    original=deepcopy(c)
    rows,audit=adapt_publications([publication(c)])
    assert c==original
    r=rows[0]
    assert r['empirical_record_id']=='vgc-occurrence:p:ep:member:0'
    assert r['original_record_ids']==['p:ep:member:0']
    assert len(r['teammates'])==5
    assert [m['normalized']['species'] for m in r['teammates']]==[m['normalized']['species'] for m in c['members'][1:]]
    assert all(m['source_url']==r['source_url'] for m in r['teammates'])
    assert all(len(m['normalized']['moves'])==4 and m['normalized']['item'] for m in r['teammates'])
    assert r['configuration']['sp']['values']==[None]*6 and r['training_points'] is None
    assert audit['counts']['missing_sp']==6 and audit['publications']==1


def test_observable_team_sp_omission_source_overlap_and_independent_pool(canonicalizer):
    complete=team(canonicalizer,[32,32,0,0,0,2]);missing=team(canonicalizer)
    assert observable_team_signature(complete)==observable_team_signature(missing)
    different=deepcopy(missing);different['members'][1]['normalized']['item']=canonicalizer.mon(raw(item='Life Orb'))['normalized']['item']
    assert observable_team_signature(different)!=observable_team_signature(missing)
    rows,audit=adapt_publications([publication(complete,'train'),publication(missing,'overlap'),publication(different,'independent')])
    train=[r for r in rows if r['publication_id']=='train' and r['species']=='pokeapi:species:727']
    application=split_application(rows,train)
    assert len(application)==2
    assert {r['publication_id']:r['primary_independent_pool'] for r in application}=={'overlap':False,'independent':True}
    overlapping=next(r for r in application if r['publication_id']=='overlap')
    assert 'observable_team_signature' in overlapping['source_overlap']['direct']


def test_grouping_transitive_url_key_and_hash_links():
    groups=connected_groups({'a':[('url','one')],'b':[('url','one'),('hash','two')],
                             'c':[('hash','two')],'d':[('url','other')]})
    assert groups['a']==groups['b']==groups['c']!=groups['d']
    assert groups==connected_groups(dict(reversed(list({'a':[('url','one')],'b':[('url','one'),('hash','two')],'c':[('hash','two')],'d':[('url','other')]}.items()))))


def build(i,z=0,item='berry',ms=None,group=None):
    points=[32,0,1,0,10,23] if z==0 else [32,25,2,0,2,5] if z==1 else [31,0,14,0,19,2]
    return dict(empirical_record_id=str(i),training_points=dict(zip(('hp','attack','defense','special_attack','special_defense','speed'),points)),
                configuration=dict(moves=list(ms or (('a','b','c','d') if z==0 else ('a','e','f','g') if z==1 else ('a','b','h','i')))),
                item=item,evaluation_group=group or 'group-'+str(i),primary_independent_pool=True)


def test_occurrence_weighted_prior_and_exact_counts():
    rows=[build(i,z) for i,z in enumerate([0,1,2,2,2])]
    model=Predictor(rows,[0,1,2,2,2])
    p=model.predict(['a','b','h','i'])
    assert model.prior==[.2,.2,.6] and p['exact_counts']==[0,0,3]
    assert p['moves_only']['weights'][2]>model.prior[2]
    # No deduplication of identical moves/item/SP configurations.
    assert model.n==5


@pytest.mark.parametrize('ms',[['w','x','y','z'],['a','b','x','y'],['a','b','c','d']])
def test_normalized_deterministic_rare_unseen_predictions(ms):
    model=Predictor([build(0,0),build(1,1),build(2,2)],[0,1,2])
    first=model.predict(ms,'unknown-item');second=model.predict(list(reversed(ms)),'unknown-item')
    assert first==second
    for key in ('moves_only','moves_item'):
        weights=first[key]['weights'];assert all(np.isfinite(weights)) and min(weights)>0
        assert sum(weights)==pytest.approx(1)
    if ms==['w','x','y','z']:
        assert first['moves_only']['weights']==pytest.approx(model.prior)
        assert first['novelty']['out_of_distribution'] and first['novelty']['insufficient_support']
    assert first['novelty']['rare_complete_set']


def test_missing_item_unknown_item_and_joint_inclusion():
    rows=[build(0,0,item='scarf'),build(1,1,item='orb'),build(2,2,item='berry')]
    model=Predictor(rows,[0,1,2])
    missing=model.predict(['a','b','c','d'])
    assert missing['moves_item'] is None
    unseen=model.predict(['a','b','c','d'],'unseen')
    assert unseen['moves_only']==unseen['moves_item']
    known=model.predict(['a','b','c','d'],'orb')
    assert known['moves_item']['weights'][1]>known['moves_only']['weights'][1]
    assert known['item_counts']==[0,1,0]


def test_no_sp_nature_ability_or_teammates_are_features():
    rows=[build(i,z) for i,z in enumerate([0,1,2])];other=deepcopy(rows)
    for r in other:r.update(training_points=None,nature='unseen',ability='unseen',teammates=['fake'])
    a=Predictor(rows,[0,1,2]).predict(['a','b','c','d'],'berry')
    b=Predictor(other,[0,1,2]).predict(['a','b','c','d'],'berry')
    assert a==b


def test_mixture_is_average_of_normalized_conditionals_not_likelihood_product():
    model=Predictor([build(0,0),build(1,1),build(2,2)],[0,1,2])
    p=model.predict(['a','b','c','d'])
    expected=sum(level['weight']*np.array(level['moves_only']) for level in p['levels'])
    assert p['moves_only']['weights']==pytest.approx(expected)
    assert len(p['supporting_subsets'])==15


@pytest.mark.parametrize('values',[['a']*4,['a','b','c'],['a','b','c',None]])
def test_invalid_moves_not_silently_repaired(values):
    with pytest.raises(ValueError):moveset(values)


def test_grouped_evaluation_training_only_and_deterministic():
    # Each source group has all three investments, so every fold can fit K=3.
    rows=[build(f'{i}-{z}',z,group=f'source-{i}') for i in range(15) for z in range(3)]
    medoids=[build('ref-'+str(z),z) for z in range(3)]
    a=evaluate(rows,medoids,SPConfig(),seeds=(353,))
    assert a==evaluate(rows,medoids,SPConfig(),seeds=(353,))
    assert len(a['predictions'])==len(rows)
    byid={r['empirical_record_id']:r for r in rows}
    for f in a['folds']:
        assert not set(f['training_ids']) & set(f['test_ids'])
        assert not set(f['training_groups']) & set(f['test_groups'])
        assert set(f['medoid_ids'])<=set(f['training_ids'])
        assert all(fold_id(byid[rid]['evaluation_group'],353)==f['fold'] for rid in f['test_ids'])
    assert a['pooled']['moves']['accuracy']>a['pooled']['majority']['accuracy']
    assert a['pooled']['moves']['recall'][1]>0


def test_metrics_brier_log_loss_and_confusion():
    m=metrics([0,1,2],[[.5,.25,.25],[.1,.8,.1],[.1,.2,.7]])
    assert m['accuracy']==1 and m['recall']==[1,1,1]
    assert m['confusion']==[[1,0,0],[0,1,0],[0,0,1]]
    assert m['brier']==pytest.approx((.375+.06+.14)/3)
    assert m['nll']==pytest.approx(-np.log([.5,.8,.7]).mean())


def payload():
    model=Predictor([build(0,0),build(1,1),build(2,2)],[0,1,2])
    r=build('application');r['prediction']=model.predict(['a','b','c','d'],'berry')
    return dict(model_fingerprint='model-a',records=[r])


def annotation(**kwargs):
    return dict(observation_id='application',model_fingerprint='model-a',assessment='ambiguous',preferred_cluster=None,notes='Interpretation only',**kwargs)


def test_durable_annotations_revisions_export_and_resume(tmp_path):
    path=tmp_path/'review.sqlite3';p=payload();store=ReviewStore(path,p)
    value=annotation();saved=store.save(value)
    assert saved['suggested_weights']['moves_only']==p['records'][0]['prediction']['moves_only']
    assert saved['reviewed_at'] and 'not verified' in saved['interpretation']
    store.session(dict(last_record='application',population='curated',sort='uncertain'))
    reopened=ReviewStore(path,p)
    assert reopened.latest()==[saved] and reopened.session()['last_record']=='application'
    value.update(assessment='reasonable',preferred_cluster=2,notes='=formula-like user note')
    second=reopened.save(value)
    assert second['revision']>saved['revision'] and len(reopened.latest())==1
    assert "'=formula-like" in reopened.csv()
    with sqlite3.connect(path) as db:assert db.execute('SELECT count(*) FROM reviews').fetchone()[0]==2
    new=ReviewStore(path,dict(p,model_fingerprint='model-b'))
    assert new.latest()==[] and new.session()=={}


@pytest.mark.parametrize('change',[dict(model_fingerprint='wrong'),dict(observation_id='unknown'),dict(assessment='true_sp_label'),dict(preferred_cluster=True),dict(preferred_cluster=4),dict(notes='x'*20001)])
def test_annotation_validation(tmp_path,change):
    store=ReviewStore(tmp_path/'a.sqlite3',payload());value=annotation();value.update(change)
    with pytest.raises(ValueError):store.save(value)
    assert store.latest()==[]


def test_review_http_save_export_and_restart(tmp_path):
    store=ReviewStore(tmp_path/'a.sqlite3',payload())
    server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(payload(),store))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def request(method,path,body=None,headers=None):
        c=HTTPConnection('127.0.0.1',server.server_port,timeout=3)
        c.request(method,path,body=json.dumps(body) if body is not None else None,headers={'Content-Type':'application/json',**(headers or {})})
        r=c.getresponse();data=r.read();status=r.status;c.close();return status,data
    try:
        assert request('GET','/')[0]==200
        assert request('GET','/api/reviews')==(200,b'[]')
        assert request('PUT','/api/reviews',annotation())[0]==200
        code,data=request('GET','/api/export.json');assert code==200 and len(json.loads(data)['reviews'])==1
        assert b'Interpretation only' in request('GET','/api/export.csv')[1]
        assert request('PUT','/api/session',{'last_record':'application'})[0]==200
        assert json.loads(request('GET','/api/session')[1])['last_record']=='application'
        assert request('GET','/../review.py')[0]==404
        assert request('PUT','/api/reviews',annotation(),{'Origin':'https://example.com'})[0]==403
    finally:server.shutdown();server.server_close();thread.join()
    assert len(ReviewStore(tmp_path/'a.sqlite3',payload()).latest())==1


def test_queue_diverse_patterns_actual_availability_and_overlap_exclusion():
    rows=[]
    model=Predictor([build(0,0),build(1,1),build(2,2)],[0,1,2])
    for i in range(30):
        r=build(str(i),2,item='item-'+str(i));r['prediction']=model.predict(r['configuration']['moves'],r['item']);rows.append(r)
    rows[0]['primary_independent_pool']=False
    q=select_queue(rows)
    assert len(q['ids'])==20 and len(set(q['ids']))==20 and '0' not in q['ids']
    assert q==select_queue(rows)
    assert q['availability']['high-margin cluster 0']==0
    assert select_queue(rows[:2])['ids']==['1']
