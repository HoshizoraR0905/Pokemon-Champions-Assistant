"""Offline synthetic design fixtures; no claim that these are legal game teams."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from metagame.common import immutable_raw,now
from metagame.published.canonical import Canonicalizer
from metagame.published.store import Teams,prepare
from metagame.published.query import query,coverage
from metagame.published.adapters import parse_export,points,extract,SOURCES
from metagame.published.collect import collect
from metagame.published import VERSION


@pytest.fixture(scope='module')
def canon():return Canonicalizer()


def team(key='a',population='community_published'):
    species=['Pelipper','Archaludon','Rillaboom','Incineroar','Indeedee-F','Gardevoir']
    return dict(source_key=key,title='Synthetic '+key,source_url='https://fixture.invalid/'+key,
        population=population,regulation='M-C',format='Doubles',metadata=dict(synthetic=True),
        pokemon=[dict(species=s,ability='Drizzle',item='Sitrus Berry',nature='Modest',
            moves=['Hurricane','Weather Ball','Tailwind','Protect'],
            sp=dict(kind='champions_sp',values=[2,0,0,32,0,32])) for s in species])


def database(tmp_path):
    root=prepare(tmp_path);db=Teams(root)
    raw_path,digest=immutable_raw(root,b'synthetic source evidence')
    cid=db.capture('fixture',dict(synthetic=True),dict(url='https://fixture.invalid',
        raw_path=str(raw_path),raw_sha256=digest,retrieved_at=now()))
    return db,cid


def add(db,cid,canon,record,source='fixture'):
    if source!='fixture':
        db.db.execute('INSERT OR IGNORE INTO sources VALUES(?,?)',(source,'{}'));db.db.commit()
        raw_path,digest=immutable_raw(db.root,b'synthetic '+source.encode())
        cid=db.capture(source,{},dict(url='https://'+source+'.invalid',raw_path=str(raw_path),
            raw_sha256=digest,retrieved_at=now()))
    return db.add(source,record,canon.team(record),cid,'synthetic-fixture-v1')


def test_six_order_move_order_nicknames_cosmetics_and_metadata_do_not_change_identity(canon):
    a=team();b=deepcopy(a);b['pokemon'].reverse()
    for m in b['pokemon']:
        m['moves'].reverse();m.update(nickname='other',shiny=True)
    b.update(source_url='https://elsewhere.invalid/',title='other',metadata=dict(author='different',rental='other'))
    x,y=canon.team(a),canon.team(b)
    assert x['status']==y['status']=='exact_complete'
    assert x['composition_id']==y['composition_id'] and x['exact_build_id']==y['exact_build_id']


def test_multilingual_canonical_names(canon):
    a=team();b=deepcopy(a)
    b['pokemon'][0].update(species='大嘴鸥',ability='降雨',item='文柚果',nature='内敛',
        moves=['暴风','气象球','顺风','守住'])
    assert canon.team(a)['exact_build_id']==canon.team(b)['exact_build_id']


@pytest.mark.parametrize('field,value',[('item','Focus Sash'),('moves',['Hurricane','Weather Ball','Wide Guard','Protect']),
    ('sp',dict(kind='champions_sp',values=[2,0,0,32,0,31])),('ability','Keen Eye'),('nature','Bold')])
def test_same_composition_different_verified_core_build(canon,field,value):
    a=team();b=deepcopy(a);b['pokemon'][0][field]=value
    x,y=canon.team(a),canon.team(b)
    assert x['composition_id']==y['composition_id']
    assert x['exact_build_id']!=y['exact_build_id'] and y['exact_build_id'] is not None


def test_form_multiset_and_multiplicity(canon):
    a=team();b=deepcopy(a);b['pokemon'][4]['species']='Indeedee'
    assert canon.team(a)['composition_id']!=canon.team(b)['composition_id']
    b=deepcopy(a);b['pokemon'][1]['species']='Pelipper'
    c=canon.team(b)
    assert c['composition'].count('pokeapi:species:279')==2
    assert c['composition_id']!=canon.team(a)['composition_id']


def test_unknown_is_not_known_or_an_exact_identity(canon):
    a=team();b=deepcopy(a);b['pokemon'][0]['sp']['values'][-1]=None
    x=canon.team(b)
    assert x['status']=='composition_complete' and x['exact_build_id'] is None
    assert x['composition_id']==canon.team(a)['composition_id']
    assert x['members'][0]['normalized']['sp']['values'][-1] is None


def test_partial_conflicting_and_invalid_sp_preserve_evidence(canon):
    a=team();a['pokemon'][0]['species']='unresolved-form'
    assert canon.team(a)['status']=='partial'
    a=team();a['pokemon'][0]['sp']['values']=[32]*6
    x=canon.team(a)
    assert x['status']=='conflicting' and x['composition_complete'] and x['exact_build_id'] is None
    assert x['members'][0]['original']['sp']['values']==[32]*6
    a=team();a['pokemon'][0]['form']=None
    assert canon.team(a)['composition_id'] is None


def test_untyped_or_legacy_sp_never_becomes_exact(canon):
    for kind in ['unknown','legacy_ev','observed_final_stats']:
        a=team();a['pokemon'][0]['sp']['kind']=kind
        assert canon.team(a)['exact_build_id'] is None


def test_publication_multiplicity_and_children_are_preserved(tmp_path,canon):
    db,cid=database(tmp_path)
    a=team()
    for i in range(5):
        r=deepcopy(a);r['source_key']=str(i);r['source_url']='https://fixture.invalid/'+str(i)
        add(db,cid,canon,r)
    b=team('different-sp');b['pokemon'][0]['sp']['values'][-1]=31
    add(db,cid,canon,b);add(db,cid,canon,b)
    r=coverage(tmp_path,population='community_published',regulation='M-C')
    assert r['source_publications']==6 and r['unique_builds']==2 and r['unique_compositions']==1
    assert len(next(iter(r['composition_children'].values())))==2
    assert max(len(v) for v in r['exact_build_publications'].values())==5
    assert db.db.execute('SELECT count(*) FROM pokemon_builds').fetchone()[0]>=7
    db.close()


def test_publications_on_five_sites_share_one_build(tmp_path,canon):
    db,cid=database(tmp_path)
    for i in range(5):
        a=team();a['source_url']='https://site'+str(i)+'.invalid/team'
        add(db,cid,canon,a,source='site'+str(i))
    r=coverage(tmp_path,population='community_published',regulation='M-C')
    assert r['source_publications']==5 and r['unique_builds']==r['unique_compositions']==1
    db.close()


def test_partial_duplicate_candidates_do_not_merge_known_configuration(tmp_path,canon):
    db,cid=database(tmp_path);add(db,cid,canon,team())
    b=team('partial');b['pokemon'][0]['sp']['values'][-1]=None
    add(db,cid,canon,b)
    r=coverage(tmp_path,population='community_published',regulation='M-C')
    assert r['unique_builds']==1 and r['publication_revisions']==2
    assert r['potential_duplicate_candidates'] and r['unique_build_excluded_publication_revisions']==1
    q=query(tmp_path,'Pelipper',population='community_published',regulation='M-C')
    assert q['eligible_target_builds']==1
    stored=db.db.execute("SELECT canonical FROM extractions WHERE status='composition_complete'").fetchone()[0]
    assert json.loads(stored)['members'][0]['normalized']['sp']['values'][-1] is None
    db.close()


def test_conflicting_build_can_retain_unambiguous_composition(tmp_path,canon):
    db,cid=database(tmp_path);a=team();a['pokemon'][0]['sp']['values']=[32]*6;add(db,cid,canon,a)
    r=coverage(tmp_path,population='community_published',regulation='M-C')
    assert r['unique_builds']==0 and r['unique_compositions']==1
    db.close()


def three_builds(db,cid,canon):
    a=team('a');add(db,cid,canon,a)
    for i in range(4):
        dup=deepcopy(a);dup['source_key']='dup'+str(i);add(db,cid,canon,dup)
    b=team('b');b['pokemon'][0]['moves'][2]='Wide Guard';b['pokemon'][0]['item']='Focus Sash';add(db,cid,canon,b)
    c=team('c');c['pokemon'][1]['species']='Torkoal';c['pokemon'][0]['item']='Focus Sash';add(db,cid,canon,c)


def test_conditional_denominators_and_composition_estimator(tmp_path,canon):
    db,cid=database(tmp_path);three_builds(db,cid,canon)
    q=query(tmp_path,'Pelipper',population='community_published',regulation='M-C')
    tailwind=next(x for x in q['field_distributions']['moves'] if x['value']=='pokeapi:move:366')
    assert (tailwind['numerator'],tailwind['denominator'])==(2,3)
    conditioned=query(tmp_path,'Pelipper',population='community_published',regulation='M-C',teammates=['Archaludon'])
    tailwind=next(x for x in conditioned['field_distributions']['moves'] if x['value']=='pokeapi:move:366')
    assert (tailwind['numerator'],tailwind['denominator'])==(1,2)
    assert sorted(x['estimate'] for x in conditioned['field_distributions']['item'])==[.5,.5]
    comp=query(tmp_path,'Pelipper',population='community_published',regulation='M-C',unit='unique_composition')
    assert comp['total_eligible_designs']==2 and 'field_distributions' not in comp
    mate=next(r for r in comp['teammates'] if r['canonical_id']=='pokeapi:species:1018')
    assert mate['frequency']['numerator']==1 and mate['frequency']['denominator']==2
    assert comp['interpretation'].endswith('not Ranked encounters')
    db.close()


def test_item_given_move_and_move_move_joint_counts(tmp_path,canon):
    db,cid=database(tmp_path);three_builds(db,cid,canon)
    q=query(tmp_path,'Pelipper',population='community_published',regulation='M-C',given_move='Tailwind',move_pair=['Tailwind','Protect'])
    assert q['eligible_target_builds']==2
    assert q['requested_move_pair']['numerator']==q['requested_move_pair']['denominator']==2
    assert [r['estimate'] for r in q['field_distributions']['item']]==[.5,.5]
    db.close()


def test_lift_uses_correct_same_population_baseline(tmp_path,canon):
    db,cid=database(tmp_path);three_builds(db,cid,canon)
    d=team('no-pelipper');d['pokemon'][0]['species']='Farigiraf';add(db,cid,canon,d)
    q=query(tmp_path,'Pelipper',population='community_published',regulation='M-C',unit='unique_composition')
    mate=next(r for r in q['teammates'] if r['canonical_id']=='pokeapi:species:1018')
    assert mate['frequency']['estimate']==.5
    assert mate['population_baseline']['estimate']==pytest.approx(2/3)
    assert mate['cooccurrence']['estimate']==pytest.approx(1/3)
    assert mate['lift']==pytest.approx(.75)
    assert mate['frequency']['sampling_interval'] is None
    db.close()


def test_population_format_regulation_isolation_and_no_ranked_estimator(tmp_path,canon):
    db,cid=database(tmp_path);add(db,cid,canon,team())
    add(db,cid,canon,team('tournament','tournament_published'))
    other=team('other-reg');other['regulation']='M-B';add(db,cid,canon,other)
    other=team('singles');other['format']='Singles';add(db,cid,canon,other)
    for pop in ['community_published','tournament_published']:
        r=coverage(tmp_path,population=pop,regulation='M-C')
        assert r['source_publications']==1
    with pytest.raises(ValueError):query(tmp_path,'Pelipper',population='ranked',regulation='M-C')
    with pytest.raises(ValueError):query(tmp_path,'Pelipper',population='all',regulation='M-C')
    with pytest.raises(ValueError):query(tmp_path,'Pelipper',population='community_published',regulation='M-C',unit='unique_composition',given_move='Tailwind')
    db.close()


def test_versioned_identities_never_overwrite_old_versions(tmp_path,canon):
    db,cid=database(tmp_path);a=team();add(db,cid,canon,a)
    v2=Canonicalizer(version='test-v2');other=add(db,cid,v2,a)
    assert other['exact_build_id']!=canon.team(a)['exact_build_id']
    assert len(db.scoped('community_published','M-C','Doubles',VERSION))==1
    assert len(db.scoped('community_published','M-C','Doubles','test-v2'))==1
    db.db.execute("UPDATE algorithms SET definition_sha256='different' WHERE version=?",(VERSION,));db.db.commit()
    with pytest.raises(ValueError):add(db,cid,canon,a)
    db.close()


def test_multiple_teammate_sparse_sample_guard(tmp_path,canon):
    db,cid=database(tmp_path);add(db,cid,canon,team())
    q=query(tmp_path,'Pelipper',population='community_published',regulation='M-C',teammates=['Archaludon','Incineroar'])
    assert q['status']=='insufficient_multiple_teammate_sample'
    assert q['teammate_context_frequency']['numerator']==1 and q['teammate_context_frequency']['estimate'] is None
    db.close()


def test_sp_deduction_requires_corroboration_and_full_budget():
    text='Pelipper @ Sitrus Berry\nAbility: Drizzle\nEVs: 2 HP / 32 SpA / 32 Spe\nModest Nature\n- Hurricane\n- Weather Ball\n- Tailwind\n- Protect'
    m=parse_export(text)[0]
    assert m['sp']['kind']=='unknown' and m['sp']['values']==[None]*6
    m=parse_export(text,source_sp_lines=['2 HP / 32 SpA / 32 Spe'])[0]
    assert m['sp']['values']==[2,0,0,32,0,32]
    assert m['evidence']['zero_components_deduced_from_66_budget']==[1,2,4]
    vals,_=points('1 HP / 32 SpA / 32 Spe')
    assert vals==[1,None,None,32,None,32]
    m=parse_export(text,source_sp_lines=['1 HP / 32 SpA / 32 Spe'])[0]
    assert 'visible_sp_export_disagreement' in m['conflicts']


def test_invalid_schema_version_and_no_retention_on_team_database(tmp_path):
    db,cid=database(tmp_path)
    assert not hasattr(db,'prune')
    db.db.execute('PRAGMA user_version=99');db.close()
    with pytest.raises(ValueError):Teams(tmp_path,readonly=True)


def test_without_teammate_and_empty_context(tmp_path,canon):
    db,cid=database(tmp_path);three_builds(db,cid,canon)
    q=query(tmp_path,'Pelipper',population='community_published',regulation='M-C',exclude_teammates=['Archaludon'])
    assert q['eligible_target_builds']==1
    assert q['field_distributions']['item'][0]['value']=='pokeapi:item:252'
    empty=query(tmp_path,'Pelipper',population='community_published',regulation='M-C',teammates=['Farigiraf'])
    assert empty['eligible_target_builds']==0 and empty['field_distributions']['item']==[]
    db.close()


def test_partial_unknown_species_has_candidates_without_canonical_composition(tmp_path,canon):
    db,cid=database(tmp_path);add(db,cid,canon,team())
    b=team('unknown');b['pokemon'][0]['species']=None;add(db,cid,canon,b)
    r=coverage(tmp_path,population='community_published',regulation='M-C')
    assert r['potential_duplicate_candidates'] and r['unique_composition_excluded_publication_revisions']==1
    db.close()


def page_fixture():
    from html import escape
    export='Pelipper @ Sitrus Berry\nAbility: Drizzle\nEVs: 2 HP / 32 SpA / 32 Spe\nModest Nature\n- Hurricane\n- Weather Ball\n- Tailwind\n- Protect'
    sheet='<li class="sh-mon"><dl><dt>Item</dt><dd>Sitrus Berry</dd><dt>Ability</dt><dd>Drizzle</dd><dt>Nature</dt><dd>Modest</dd><dt>SP</dt><dd>2 HP / 32 SpA / 32 Spe</dd></dl></li>'
    return '<h1>Regulation M-C</h1><section class="rt-team" id="synthetic"><div class="rt-top"><h2>Synthetic fixture</h2></div>'+sheet*6+'<textarea>'+escape('\n\n'.join([export]*6))+'</textarea></section>'


def test_source_adapter_and_immutable_collector_resume(tmp_path):
    from metagame.common import sha,atomic_json
    page=page_fixture();records=extract('pokedaily',page)
    assert len(records)==1 and len(records[0]['pokemon'])==6
    source=tmp_path/'source.html';source.write_text(page)
    receipt=tmp_path/'receipt.json';atomic_json(receipt,dict(url=SOURCES['pokedaily']['url'],status=200,
        sha256=sha(source.read_bytes()),retrieved_at=now()))
    root=tmp_path/'teams'
    result,path=collect(root,'pokedaily',from_file=source,receipt_file=receipt)
    assert result['status']=='complete' and result['network_requests']==0 and path.exists()
    collect(root,'pokedaily',from_file=source,receipt_file=receipt)
    db=Teams(root,readonly=True)
    assert db.db.execute('SELECT count(*) FROM publications').fetchone()[0]==1
    assert db.db.execute('SELECT count(*) FROM captures').fetchone()[0]==1
    db.close()
    source.write_text(page+'modified')
    result,path=collect(root,'pokedaily',from_file=source,receipt_file=receipt)
    assert result['status']=='failed' and 'hash mismatch' in result['error']
    assert coverage(root,population='community_published',regulation='M-C',battle_format='Unknown')['unique_compositions']==1


def test_source_adapters_reject_schema_drift_and_blocked_source():
    with pytest.raises(ValueError):extract('pokedaily','<h1>Other page</h1>')
    with pytest.raises(ValueError):extract('pokedaily',page_fixture(),limit=7)
    assert 'pokefeed' not in SOURCES and 'missingno' not in SOURCES
    export='Pelipper @ Sitrus Berry\nAbility: Drizzle\nAbility: Keen Eye'
    assert 'duplicate_ability' in parse_export(export)[0]['conflicts']


def test_format_correction_preserves_records_and_excludes_unsupported_doubles(tmp_path,canon):
    db,cid=database(tmp_path)
    path,digest=immutable_raw(tmp_path,b'fictional page fixture')
    capture=db.capture('pokedaily',{},dict(url=SOURCES['pokedaily']['url'],raw_path=str(path),raw_sha256=digest,retrieved_at=now()))
    a=team();a['metadata']['original_export']='synthetic same export'
    db.add('pokedaily',a,canon.team(a),capture,'before')
    b=deepcopy(a);b['format']='Unknown'
    db.add('pokedaily',b,canon.team(b),capture,'corrected')
    assert len(db.scoped('community_published','M-C','Doubles'))==0
    assert len(db.scoped('community_published','M-C','Unknown'))==1
    assert db.db.execute('SELECT count(*) FROM publications').fetchone()[0]==2
    assert db.db.execute('SELECT count(*) FROM publication_supersessions').fetchone()[0]==1
    db.close()


def test_current_extraction_selection_does_not_duplicate_publications(tmp_path,canon):
    db,cid=database(tmp_path);a=team();canonical=canon.team(a)
    db.add('fixture',a,canonical,cid,'adapter-1')
    db.add('fixture',a,canonical,cid,'adapter-2')
    assert len(db.scoped('community_published','M-C','Doubles'))==1
    assert db.db.execute('SELECT count(*) FROM extractions').fetchone()[0]==2
    db.close()


def test_immutable_extraction_and_capture_source_guards(tmp_path,canon):
    db,cid=database(tmp_path);a=team();add(db,cid,canon,a)
    canonical=canon.team(a);canonical['knowledge_snapshot']='altered'
    with pytest.raises(ValueError):db.add('fixture',a,canonical,cid,'synthetic-fixture-v1')
    with pytest.raises(ValueError):db.add('different-source',a,canon.team(a),cid,'fixture')
    db.close()


def test_ranked_retention_manager_cannot_adopt_published_database(tmp_path):
    from metagame.store import prepare_root
    root=prepare(tmp_path)
    with pytest.raises(ValueError):prepare_root(root)
    assert (root/'published-owner.json').exists()


def test_unsupported_gameplay_fields_prevent_exact_equivalence(canon):
    a=team();a['pokemon'][0]['unsupported_fields']=['Unknown gameplay choice: X']
    result=canon.team(a)
    assert result['exact_build_id'] is None and result['composition_id'] is not None


def test_observed_signature_missingness_and_strict_identity(canon):
    from metagame.published.observed import observation
    a=team();b=deepcopy(a)
    for m in b['pokemon']:m['sp']=dict(kind='unknown',values=[None]*6)
    x,y=canon.team(a),canon.team(b)
    assert x['exact_build_id'] and y['exact_build_id'] is None
    assert observation(x)['signature']!=observation(y)['signature']
    shuffled=deepcopy(b);shuffled['pokemon'].reverse()
    assert observation(y)['signature']==observation(canon.team(shuffled))['signature']
    b['pokemon'][0]['nature']=None
    assert observation(y)['signature']!=observation(canon.team(b))['signature']
    assert 'nature' in observation(canon.team(b))['payload']['members'][0]['missing'] or any(
        'nature' in m['missing'] for m in observation(canon.team(b))['payload']['members'])


def test_partial_field_denominators_and_source_separation(tmp_path,canon):
    db,cid=database(tmp_path)
    a=team('a');b=team('b');c=team('c')
    for record in (b,c):
        for m in record['pokemon']:m['sp']=dict(kind='unknown',values=[None]*6)
    b['pokemon'][0]['moves']=['Hurricane','Weather Ball','Wide Guard','Protect']
    b['pokemon'][0]['nature']=None
    c['pokemon'][0]['item']=None;c['pokemon'][0]['moves']=[]
    for record in (a,b,c):add(db,cid,canon,record)
    for i in range(3):
        duplicate=deepcopy(b);duplicate['source_key']='repost'+str(i);add(db,cid,canon,duplicate)
    add(db,cid,canon,team('other'),source='other')
    db.close()
    r=query(tmp_path,'Pelipper',source='fixture',population='community_published',regulation='M-C',
        unit='distinct_observed_configuration',teammates=['Archaludon'],move_pair=['Tailwind','Protect'])
    assert r['context_designs']==3 and r['source_publications']==6
    assert r['field_eligibility']['moves']['eligible_distinct_records']==2
    tailwind=next(v for v in r['field_distributions']['moves'] if v['value']=='pokeapi:move:366')
    assert (tailwind['numerator'],tailwind['denominator'])==(1,2)
    assert r['field_eligibility']['item']['eligible_distinct_records']==2
    assert r['field_eligibility']['nature']['eligible_distinct_records']==2
    assert r['field_eligibility']['sp']['eligible_distinct_records']==1
    assert r['requested_move_pair']['denominator']==2
    assert max(s['represented_publications'] for s in r['signatures'])==4
    with pytest.raises(ValueError,match='explicit source'):
        query(tmp_path,'Pelipper',population='community_published',regulation='M-C',unit='distinct_observed_configuration')


def test_partial_sp_components_and_conflicting_sp_leave_moves_eligible(canon):
    from metagame.published.observed import eligibility
    a=team();a['pokemon'][0]['sp']['values']=[2,None,None,32,None,32]
    m=canon.team(a)['members'][0];e=eligibility(m)
    assert e['moves'] and e['item'] and not e['sp'] and e['sp_hp'] and not e['sp_atk']
    a['pokemon'][0]['sp']['values']=[32]*6
    e=eligibility(canon.team(a)['members'][0])
    assert e['moves'] and e['nature'] and not e['sp'] and not e['sp_hp']


def source_summary(i=0,reg='M-C'):
    r=team()
    return dict(id=f'MC{i}',description=f'Synthetic team {i}',player='Fixture',regulation=reg,
        event='Synthetic Regional',placement='Top 16',date='2026-10-01',pasteId=f'paste{i}',
        hasSps=True,setsBlock=i//20,replicaCode='fixture-code' if i%2 else None,
        members=[dict(name=m['species'],item=m['item']) for m in r['pokemon']])


def source_block(summaries,missing_sp=False):
    return 'export const COMMUNITY_TEAM_SETS: CommunityTeamSets = '+json.dumps({r['id']:[dict(
        ability=m['ability'],nature=m['nature'],moves=m['moves'],**({} if missing_sp else
        dict(sps=dict(zip(('hp','atk','def','spa','spd','spe'),m['sp']['values'])))))
        for m in team()['pokemon']] for r in summaries})


def test_licensed_index_paging_detail_metadata_and_drift(canon):
    from metagame.published.vgcmulticalc import discovery,pages,detail,literal,DEFAULT_REVISION
    summaries=[source_summary(i) for i in range(43)]
    raw='export const COMMUNITY_TEAMS: VgcPastesTeam[] = '+json.dumps(summaries)
    rows=discovery(raw,'M-C');assert [len(p) for p in pages(rows)]==[20,20,3]
    full=detail(rows[1],source_block(rows[:20]),DEFAULT_REVISION)
    partial=detail(rows[1],source_block(rows[:20],True),DEFAULT_REVISION)
    assert canon.team(full)['exact_build_id'] and canon.team(partial)['exact_build_id'] is None
    assert partial['pokemon'][0]['moves']==full['pokemon'][0]['moves']
    assert full['metadata']['replica_code']=='fixture-code'
    assert full['metadata']['placement']=='Top 16' and 'paste=paste1' in full['source_url']
    assert canon.team(full)['members'][4]['normalized']['species']==canon.names.resolve('Indeedee-F')['canonical_id']
    with pytest.raises(ValueError):discovery(raw,'M-B')
    with pytest.raises(ValueError):literal('export const X: T = process.env.SECRET','X')
    with pytest.raises(ValueError):literal('export const X: T = {a: 1, a: 2}','X')
    with pytest.raises(ValueError):detail(rows[1],source_block(rows[2:20]),DEFAULT_REVISION)
    drift=source_block(rows[:20]).replace('"ability":','"newGameplayField":')
    with pytest.raises(ValueError,match='fields changed'):detail(rows[1],drift,DEFAULT_REVISION)


def test_detail_collection_checkpoint_retry_and_idempotence(tmp_path):
    from metagame.published.vgcmulticalc import collect as collect_details
    class Fake:
        def __init__(self):self.requests=0;self.cache_hits=0;self.fail=True
        def get(self,url,**kwargs):
            self.requests+=1
            rows=[source_summary(i) for i in range(23)]
            if url.endswith('LICENSE'):data='MIT License\nCopyright Robson Bittencourt'
            elif 'community-teams-m-c.ts' in url:data='export const COMMUNITY_TEAMS: T = '+json.dumps(rows)
            elif url.endswith('002.ts') and self.fail:raise RuntimeError('HTTP 429; resume later')
            else:data=source_block(rows)
            path,digest=immutable_raw(tmp_path,data.encode())
            return dict(url=url,status=200,raw_path=str(path),raw_sha256=digest,retrieved_at=now())
    f=Fake()
    r,path=collect_details(tmp_path,fetcher=f)
    assert r['status']=='partial' and len(r['completed'])==20 and len(r['errors'])==3
    f.fail=False
    r,path=collect_details(tmp_path,fetcher=f)
    assert r['status']=='complete' and len(r['completed'])==23
    db=Teams(tmp_path);n=db.db.execute('SELECT count(*) FROM publications').fetchone()[0];db.close()
    assert n==23
    r,path=collect_details(tmp_path,fetcher=f)
    db=Teams(tmp_path)
    assert db.db.execute('SELECT count(*) FROM publications').fetchone()[0]==n
    assert db.db.execute('SELECT count(*) FROM observed_configurations').fetchone()[0]==n
    db.close()


def public_payload(with_sp=True,mode=True):
    blocks=[]
    for m in team()['pokemon']:
        lines=[m['species']+' @ '+m['item'],'Ability: '+m['ability'],'Level: 50']
        if with_sp:lines.append('EVs: 2 HP / 32 SpA / 32 Spe')
        lines.append(m['nature']+' Nature');lines.extend('- '+v for v in m['moves'])
        blocks.append('\n'.join(lines))
    return dict(kind='team',version=1,useSpsMode=mode,showdown='\n\n'.join(blocks),name='Fixture',createdAt='2026-10-01')


def test_public_detail_sp_flag_missing_sp_and_unknown_schema(canon):
    from metagame.published.submissions import detail,discovery
    summary=source_summary();summary['source']='community'
    assert len(discovery(json.dumps([summary]),'M-C'))==1
    a=detail(summary,json.dumps(public_payload()))
    b=detail(summary,json.dumps(public_payload(False)))
    legacy=detail(summary,json.dumps(public_payload(mode=False)))
    assert canon.team(a)['exact_build_id'] and canon.team(b)['exact_build_id'] is None
    assert b['pokemon'][0]['moves']==a['pokemon'][0]['moves']
    assert a['pokemon'][0]['sp']['values']==[2,0,0,32,0,32]
    assert legacy['pokemon'][0]['sp']['kind']=='legacy_ev'
    assert legacy['pokemon'][0]['sp']['values'][1] is None
    for payload in [dict(kind='protected',version=1),dict(public_payload(),version=2),dict(public_payload(),newField=1)]:
        with pytest.raises(ValueError):detail(summary,json.dumps(payload))
    changed=deepcopy(summary);changed['members'][0]['name']='Charizard'
    assert canon.team(detail(changed,json.dumps(public_payload())))['composition_conflicting']


def test_showdown_source_designs_are_excluded_without_deleting_evidence(tmp_path,canon):
    db,cid=database(tmp_path)
    a=team();a['title']='Fixture Showdown Ladder Peak';add(db,cid,canon,a)
    assert db.db.execute('SELECT count(*) FROM publications').fetchone()[0]==1
    assert db.scoped('community_published','M-C','Doubles')==[]
    db.close()
    r=coverage(tmp_path,population='community_published',regulation='M-C')
    assert r['source_publications']==0


def test_public_collection_requires_authorization_before_any_io(tmp_path):
    from metagame.published.submissions import collect as collect_public
    with pytest.raises(ValueError,match='authorization'):
        collect_public(tmp_path/'no-write',authorization_note='')
    assert not (tmp_path/'no-write').exists()


def test_public_collection_resumes_and_never_unlocks(tmp_path):
    from metagame.published.submissions import collect as collect_public
    class Fake:
        def __init__(self):self.requests=0;self.cache_hits=0;self.protected=True;self.urls=[]
        def get(self,url,**kwargs):
            self.requests+=1;self.urls.append(url)
            if '/index/' in url:
                row=source_summary();row['source']='community';data=json.dumps([row])
            else:data=json.dumps(dict(kind='protected',version=1) if self.protected else public_payload(False))
            path,digest=immutable_raw(tmp_path,data.encode())
            return dict(url=url,status=200,raw_path=str(path),raw_sha256=digest,retrieved_at=now())
    f=Fake();r,path=collect_public(tmp_path,authorization_note='Synthetic test only',fetcher=f)
    assert r['status']=='partial' and len(r['errors'])==1
    f.protected=False
    r,path=collect_public(tmp_path,authorization_note='Synthetic test only',fetcher=f)
    assert r['status']=='complete' and len(r['completed'])==1
    r,path=collect_public(tmp_path,authorization_note='Synthetic test only',fetcher=f)
    db=Teams(tmp_path);assert db.db.execute('SELECT count(*) FROM publications').fetchone()[0]==1;db.close()
    assert not any('unlock' in u for u in f.urls)


def test_observed_definition_guard_and_append_only_schema(tmp_path,canon,monkeypatch):
    from metagame.published import observed
    db,cid=database(tmp_path);add(db,cid,canon,team());db.close()
    db=Teams(tmp_path)
    assert db.db.execute('PRAGMA user_version').fetchone()[0]==4
    assert [r[0] for r in db.db.execute('SELECT version FROM migrations ORDER BY version')]==[1,2,3,4]
    db.close()
    monkeypatch.setattr(observed,'definition_digest',lambda:'changed-under-same-version')
    with pytest.raises(ValueError,match='increment observed version'):Teams(tmp_path,readonly=True)


def test_known_publication_family_partial_copy_does_not_add_weight_or_fill_source(tmp_path,canon):
    from metagame.published.publication_families import families
    db,cid=database(tmp_path)
    a=team('original');a['metadata']['replica_code']='FIXTURE'
    b=team('copy');b['metadata']['replica_code']='FIXTURE'
    for m in b['pokemon']:m['sp']=dict(kind='unknown',values=[None]*6)
    add(db,cid,canon,a);add(db,cid,canon,b)
    rows=db.scoped('community_published','M-C','Doubles');groups,audit=families(rows)
    assert len(groups)==1 and len(groups[0][1])==2 and audit['dominated_publication_records']==1
    assert json.loads(groups[0][0]['canonical'])['exact_build_id']
    stored=json.loads(next(r['original'] for r in rows if r['source_key']=='copy'))
    assert stored['pokemon'][0]['sp']['values']==[None]*6
    db.close()


def test_conflicting_rental_assertions_are_preserved_without_arbitrary_selection(tmp_path,canon):
    from metagame.published.publication_families import families
    db,cid=database(tmp_path)
    a=team('a');b=team('b')
    for r in (a,b):r['metadata']['replica_code']='FIXTURE'
    b['pokemon'][0]['sp']['values']=[2,0,0,32,0,31]
    add(db,cid,canon,a);add(db,cid,canon,b)
    rows=db.scoped('community_published','M-C','Doubles');groups,audit=families(rows)
    assert not groups and len(audit['conflicting_families'])==1
    # The mandatory strict Exact Build identities remain distinct and intact.
    assert len({r['build_id'] for r in rows})==2
    db.close()


def test_build_estimator_cannot_automatically_pool_sources(tmp_path,canon):
    db,cid=database(tmp_path)
    add(db,cid,canon,team('a'));add(db,cid,canon,team('b'),source='other')
    db.close()
    with pytest.raises(ValueError,match='select one source'):
        query(tmp_path,'Pelipper',population='community_published',regulation='M-C')
    r=query(tmp_path,'Pelipper',source='fixture',population='community_published',regulation='M-C')
    assert r['total_eligible_designs']==1


def test_observed_estimator_counts_known_rental_partial_copy_once(tmp_path,canon):
    db,cid=database(tmp_path)
    a=team('original');a['metadata']['replica_code']='FIXTURE'
    b=team('copy');b['metadata']['replica_code']='FIXTURE'
    for m in b['pokemon']:m['sp']=dict(kind='unknown',values=[None]*6)
    c=team('independent');c['pokemon'][0]['moves']=['Hurricane','Weather Ball','Wide Guard','Protect']
    for r in (a,b,c):add(db,cid,canon,r)
    db.close()
    q=query(tmp_path,'Pelipper',source='fixture',population='community_published',regulation='M-C',unit='distinct_observed_configuration')
    assert q['context_designs']==2 and q['source_publications']==3
    tailwind=next(r for r in q['field_distributions']['moves'] if r['value']=='pokeapi:move:366')
    assert (tailwind['numerator'],tailwind['denominator'])==(1,2)
    assert q['publication_family_audit']['dominated_publication_records']==1
    assert max(s['represented_publications'] for s in q['signatures'])==2


def test_observed_estimator_reports_conflicting_publication_family(tmp_path,canon):
    db,cid=database(tmp_path)
    a=team('a');b=team('b')
    for r in (a,b):r['metadata']['replica_code']='FIXTURE'
    b['pokemon'][0]['sp']['values']=[2,0,0,32,0,31]
    for r in (a,b):add(db,cid,canon,r)
    db.close()
    q=query(tmp_path,'Pelipper',source='fixture',population='community_published',regulation='M-C',unit='distinct_observed_configuration')
    assert q['context_designs']==0 and q['status']=='insufficient_data'
    assert len(q['publication_family_audit']['conflicting_families'])==1
    assert q['field_eligibility']['moves']['eligible_distinct_records']==0
    strict=query(tmp_path,'Pelipper',source='fixture',population='community_published',regulation='M-C')
    assert strict['total_eligible_designs']==2


def test_known_target_fields_survive_other_species_unknown_but_context_needs_roster(tmp_path,canon):
    db,cid=database(tmp_path)
    a=team();a['pokemon'][-1]['species']='Unresolved source-specific form'
    add(db,cid,canon,a);db.close()
    opts=dict(source='fixture',population='community_published',regulation='M-C',unit='distinct_observed_configuration')
    q=query(tmp_path,'Pelipper',**opts)
    assert q['context_designs']==1 and q['field_eligibility']['moves']['eligible_distinct_records']==1
    q=query(tmp_path,'Pelipper',teammates=['Archaludon'],**opts)
    assert q['context_designs']==0 and q['incomplete_roster_context_exclusions']==1
    q=query(tmp_path,'Pelipper',exclude_teammates=['Charizard'],**opts)
    assert q['context_designs']==0  # Unknown roster cannot establish absence.
