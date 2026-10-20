"""Deterministic offline fixtures for the current Ranked application cache.

All test payloads below are synthetic schema fixtures, not captured game data.
"""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import time
import pytest
import requests
from metagame.common import immutable_raw, now, sha
from metagame.fetch import Fetcher, HTTPFailure
from metagame.identity import Names
from metagame.ingest import ingest, load_receipt
from metagame.parser import parse_battle, parse_index, POINT_COLUMNS, stat_vector
from metagame.query import query, completeness
from metagame.sources import source_url
from metagame.statistics import hierarchical_smooth, joint_from_counts, wilson
from metagame.store import Store, prepare_root, locked


@pytest.fixture(scope='module')
def names():
    return Names()


def row(category, name, percent, rank=1, **kwargs):
    return dict(pokemon='Pelipper', column_position=12, category=category, name=name, rank=rank,
        percentage='' if percent is None else str(percent)+'%', percentage_value=percent,
        stat_up='',stat_down='', **kwargs)


def battle(fmt='Doubles', species='pelipper', title='Pelipper'):
    rows = [row('move','Hurricane',97.6),row('held_item','Focus Sash',46.8),
        row('ability','Drizzle',99.9),row('teammate','Archaludon',None),
        row('stat_alignment','Modest',54.5),
        row('stat_points','',22.0, **dict(zip(POINT_COLUMNS,[2,0,0,32,0,32])))]
    for r in rows:
        r['pokemon'] = title
    return dict(pokemon=title,showdownId=species,format=fmt,season='Current',date=None,
        source=f'pokemon_champions_assets/battle_data/{fmt}/{title}.csv',
        columns=['pokemon','column_position','category','rank','name','percentage',*POINT_COLUMNS], rows=rows)


def index(fmt='Doubles'):
    b = battle(fmt)
    return dict(generatedAt='2026-10-19T00:00:00Z',dataVersion='synthetic-v1',pokemon=[
        dict(name='Pelipper',showdownName='Pelipper',showdownId='pelipper',
             battleDataCsvs=[dict(season='Current',format=fmt,path=b['source'])])])


class FixtureFetcher:
    requests = 0
    cache_hits = 0
    def __init__(self, root, payload=None, idx=None):
        self.root, self.payload, self.idx = root, payload or battle(), idx or index()
    def get(self, url, **kwargs):
        self.requests += 1
        raw = json.dumps(self.idx if url.endswith('/api') else self.payload).encode()
        path,digest = immutable_raw(self.root,raw)
        return dict(url=url,raw_path=str(path),raw_sha256=digest,checked_at=now(),checked_epoch=time.time(),
            retrieved_at=now(),headers={},status=200)


def test_shared_exact_english_chinese_and_form_names(names):
    assert names.resolve('大嘴鸥')['canonical_id']==names.resolve('pelipper')['canonical_id']
    assert names.resolve('Indeedee-F')['named_form_id'] is not None
    assert names.resolve('Indeedee-F')['canonical_id']!=names.resolve('Indeedee')['canonical_id']
    assert names.resolve('imaginary-form')['canonical_id'] is None
    assert names.resolve('hurricane','move')['canonical_id']=='pokeapi:move:542'


def test_real_schema_shape_preserves_missing_denominators_and_sp_semantics():
    rows,warnings = parse_battle(battle(),'pelipper','Doubles')
    assert warnings==[]
    assert rows[0]['proportion']==.976 and rows[0]['sample_count'] is None
    assert rows[3]['rank']==1 and rows[3]['proportion'] is None
    assert rows[5]['stat_vector']['kind']=='champions_sp'
    assert rows[5]['stat_vector']['values']==[2,0,0,32,0,32]
    assert rows[5]['stat_vector']['validation']=='valid_under_pinned_profile'
    assert rows[5]['nature'] is None


@pytest.mark.parametrize('mutation',[lambda b:b.update(season='M7'),lambda b:b.update(format='Singles'),
    lambda b:b.update(showdownId='archaludon'),lambda b:b.update(columns=['name']),
    lambda b:b['rows'][0].update(category='future_schema'),
    lambda b:b['rows'][0].update(percentage_value=101),
    lambda b:b['rows'][0].update(percentage_value=float('nan')),
    lambda b:b['rows'][0].update(percentage='96%'),
    lambda b:b['rows'][0].update(pokemon='wrong')])
def test_schema_drift_and_mismatches_do_not_silently_normalize(mutation):
    b = battle();mutation(b)
    with pytest.raises(ValueError):parse_battle(b,'pelipper','Doubles')


def test_explicit_stat_kinds_partial_and_invalid_values_preserved():
    assert stat_vector('legacy_ev',[252,0,0,252,4,0])['kind']=='legacy_ev'
    assert stat_vector('unknown',[None]*6)['values']==[None]*6
    assert stat_vector('observed_final_stats',[100]*6)['kind']=='observed_final_stats'
    assert stat_vector('champions_sp',[None,0,0,32,0,32])['validation']=='incomplete'
    assert stat_vector('champions_sp',[32]*6)['validation']=='invalid_under_pinned_profile'
    with pytest.raises(ValueError):stat_vector('sp',[0]*6)


def test_index_schema_and_source_url_constraints():
    assert len(parse_index(index()))==1
    d=index();d['pokemon']*=2
    with pytest.raises(ValueError):parse_index(d)
    with pytest.raises(ValueError):source_url('pelipper?season=M7')
    assert '?' not in source_url('pelipper')


def test_ingestion_duplicate_resume_and_offline_query(tmp_path,names,monkeypatch):
    fetcher=FixtureFetcher(tmp_path)
    result,path=ingest(tmp_path,species=['大嘴鸥'],fetcher=fetcher,names=names)
    assert result['status']=='complete' and path.exists()
    db=Store(tmp_path,readonly=True);before=len(db.snapshots());db.close()
    ingest(tmp_path,species=['Pelipper'],fetcher=fetcher,names=names)
    db=Store(tmp_path,readonly=True);assert len(db.snapshots())==before;db.close()
    monkeypatch.setattr(requests.Session,'get',lambda *a,**k:pytest.fail('Offline query attempted network'))
    q=query(tmp_path,'大嘴鸥',teammate='Archaludon',names=names)
    assert q['source_population']=='third_party_claimed_ingame_ranked'
    assert q['species_usage']['estimate'] is None and q['species_usage']['rank']==12
    assert q['distributions']['move'][0]['identity']['canonical_id']=='pokeapi:move:542'
    assert q['teammate_context']['conditioned_estimates']['move']['status']=='unavailable_joint_data'
    assert not q['teammate_context']['marginals_are_conditioned']
    assert q['additional_metrics']['lift']['estimate'] is None
    assert q['stat_marginals']['covered_reported_mass']==.22
    assert q['stat_marginals']['quantiles'] is None
    assert query(tmp_path,'Archaludon',names=names)['status']=='not_cached'
    assert completeness(tmp_path)['cached_species']==1


def test_failed_new_payload_keeps_successful_projection(tmp_path,names):
    ingest(tmp_path,species=['Pelipper'],fetcher=FixtureFetcher(tmp_path),names=names)
    b=battle();b['rows'][0]['category']='new_schema'
    result,_=ingest(tmp_path,species=['Pelipper'],fetcher=FixtureFetcher(tmp_path,b),names=names)
    assert result['status']=='partial' and len(result['errors'])==1
    assert query(tmp_path,'Pelipper',names=names)['distributions']['move'][0]['proportion']==.976


def test_format_isolation(tmp_path,names):
    ingest(tmp_path,species=['Pelipper'],fetcher=FixtureFetcher(tmp_path),names=names)
    b=battle('Singles');b['rows'][0].update(percentage='60%',percentage_value=60)
    ingest(tmp_path,species=['Pelipper'],battle_format='Singles',
        fetcher=FixtureFetcher(tmp_path,b,index('Singles')),names=names)
    assert query(tmp_path,'Pelipper',names=names)['distributions']['move'][0]['proportion']==.976
    assert query(tmp_path,'Pelipper',battle_format='Singles',names=names)['distributions']['move'][0]['proportion']==.6


def test_hash_mismatch_cannot_be_queried_as_new_raw(tmp_path):
    path,digest=immutable_raw(tmp_path,b'first')
    path.write_bytes(b'corrupted')
    with pytest.raises(ValueError):load_receipt(dict(raw_path=str(path),raw_sha256=digest))
    with pytest.raises(ValueError):immutable_raw(tmp_path,b'first')


def test_cache_ownership_and_single_writer(tmp_path):
    other=tmp_path/'unowned';other.mkdir();(other/'important').write_text('preserve')
    with pytest.raises(ValueError):prepare_root(other)
    root=prepare_root(tmp_path/'owned')
    with locked(root):
        with pytest.raises(RuntimeError):
            with locked(root):pass
    assert (other/'important').read_text()=='preserve'


def test_bounded_retention_only_removes_managed_cache(tmp_path,names):
    for value in (97.6,90,80):
        b=battle();b['rows'][0].update(percentage=str(value)+'%',percentage_value=value)
        ingest(tmp_path,species=['Pelipper'],fetcher=FixtureFetcher(tmp_path,b),names=names,max_versions=2)
    db=Store(tmp_path);assert len(db.snapshots())==2
    unrelated=tmp_path/'raw'/'unowned-note.bin';unrelated.write_text('preserve')
    result=db.prune(clock=lambda:time.time()+8*86400)
    assert result['removed_snapshots']>0 and db.snapshots()==[]
    assert unrelated.read_text()=='preserve';db.close()


def test_schema_version_guard(tmp_path):
    prepare_root(tmp_path);db=Store(tmp_path);db.db.execute('PRAGMA user_version=999');db.close()
    with pytest.raises(ValueError):Store(tmp_path)


class Response:
    def __init__(self,status=200,body=b'{}',headers=None):
        self.status_code,self.body,self.headers=status,body,headers or {}
    def iter_content(self,size):yield self.body
    def close(self):pass


class Session:
    def __init__(self,outputs):self.outputs=list(outputs);self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs))
        item=self.outputs.pop(0)
        if isinstance(item,Exception):raise item
        return item


class Clock:
    value=1000.
    def __call__(self):return self.value
    def sleep(self,seconds):self.value+=seconds


def test_http_freshness_304_conditional_headers_and_rate_limit(tmp_path):
    clock=Clock();session=Session([Response(headers={'ETag':'v1','Last-Modified':'date'}),Response(304)])
    fetcher=Fetcher(tmp_path,session=session,clock=clock,sleep=clock.sleep,interval=2)
    first=fetcher.get(source_url())
    assert fetcher.get(source_url())==first and len(session.calls)==1
    second=fetcher.get(source_url(),force=True)
    assert second['raw_sha256']==first['raw_sha256'] and second['status']==304
    assert session.calls[1][1]['headers']['If-None-Match']=='v1'
    assert session.calls[1][1]['headers']['If-Modified-Since']=='date'
    assert clock.value>=1002


def test_http_retry_after_backoff_and_failed_request_checkpoint(tmp_path):
    clock=Clock();session=Session([Response(429,headers={'Retry-After':'5'}),requests.Timeout('timeout'),Response()])
    fetcher=Fetcher(tmp_path,session=session,clock=clock,sleep=clock.sleep)
    assert fetcher.get(source_url())['status']==200
    assert fetcher.requests==3 and clock.value>=1007
    failing=Fetcher(tmp_path,session=Session([Response(503)]*3),clock=clock,sleep=clock.sleep)
    with pytest.raises(HTTPFailure):failing.get(source_url('pelipper'))
    assert list((tmp_path/'http-errors').glob('*.json'))
    assert list((tmp_path/'raw').glob('*.bin'))


@pytest.mark.parametrize('status',[401,403,404,302])
def test_http_does_not_bypass_access_controls_or_follow_redirects(tmp_path,status):
    session=Session([Response(status)])
    with pytest.raises(ValueError):Fetcher(tmp_path,session=session).get(source_url())
    assert len(session.calls)==1


def test_wait_and_download_bounds(tmp_path,monkeypatch):
    with pytest.raises(ValueError):
        Fetcher(tmp_path,session=Session([Response(429,headers={'Retry-After':'120'})])).get(source_url())
    monkeypatch.setattr('metagame.fetch.MAX_BODY',2)
    with pytest.raises(ValueError):Fetcher(tmp_path,session=Session([Response(body=b'123')])).get(source_url())


def test_count_based_statistics_and_unknown_count_guards():
    pair=joint_from_counts(2,2,3,10,count_basis='independent_unweighted_team_counts')
    assert pair['cooccurrence']==.2 and pair['lift']==pytest.approx(1/.3)
    assert wilson(2,2)[0]<.5 and wilson(2,2)[1]==1
    smooth=hierarchical_smooth({'a':2,'b':0},{'a':10,'b':10},4,count_basis='independent_unweighted_counts')
    assert smooth['estimates']['a']==pytest.approx(2/3)
    assert smooth['estimates']['b']>0
    with pytest.raises(ValueError):hierarchical_smooth({'a':2},{'a':10},4,count_basis='weighted_mass')
    with pytest.raises(ValueError):joint_from_counts(2,2,3,10,count_basis='rounded_percentages')
    with pytest.raises(ValueError):joint_from_counts(5,2,3,10,count_basis='independent_unweighted_team_counts')


def test_invalid_retention_rejected_before_fetch(tmp_path,names):
    fetcher=FixtureFetcher(tmp_path)
    with pytest.raises(ValueError):
        ingest(tmp_path,species=['Pelipper'],fetcher=fetcher,names=names,retention_days=float('nan'))
    assert fetcher.requests==0


def test_unknown_source_entity_is_retained_not_fuzzily_replaced(tmp_path,names):
    b=battle();b['rows'][0]['name']='Unverified Future Move'
    result,_=ingest(tmp_path,species=['Pelipper'],fetcher=FixtureFetcher(tmp_path,b),names=names)
    assert result['status']=='complete'
    q=query(tmp_path,'Pelipper',names=names)
    move=q['distributions']['move'][0]
    assert move['original_name']=='Unverified Future Move' and move['identity']['canonical_id'] is None
    assert completeness(tmp_path)['species'][0]['unresolved_entities']


def test_missing_sp_component_is_not_zero_filled():
    b=battle();b['rows'][-1]['hp_points']=''
    records,_=parse_battle(b,'pelipper','Doubles')
    assert records[-1]['stat_vector']['values'][0] is None
    assert records[-1]['stat_vector']['validation']=='incomplete'
