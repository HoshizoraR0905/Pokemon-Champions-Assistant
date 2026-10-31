"""M3.4.4 mathematical diagnostics, not calibrated opponent probabilities."""
from copy import deepcopy
import math
import pytest
from battle_evidence.empirical_measure import tilt,inclusion,full_record_signature,template,ALPHAS


def row(i,moves,*,signature=None):
    return dict(build_id=str(i),observed_team_signature=signature or str(i),species='s',configuration=dict(moves=moves),issues=[],publications=[dict(id='pub'+str(i))])


def records(rows):
    return {str(i):dict(core_id=r.get('core','a' if i==0 else 'b'),template=template(r)) for i,r in enumerate(rows)}


def test_single_move_normalization_and_exact_odds_multiplier():
    rows=[row(0,['m','a','b','c']),row(1,['x','a','b','c'])]
    r=tilt(records(rows),rows,['m']);w=r['frequencies']['m']['effective_weight']
    assert sum(c['share'] for c in r['cores'])==pytest.approx(1)
    assert r['records'][0]['share']/r['records'][1]['share']==pytest.approx(w)


@pytest.mark.parametrize('alpha',ALPHAS)
def test_deterministic_alpha_and_no_change_for_universal_move(alpha):
    rows=[row(0,['m','a','b','c']),row(1,['m','x','b','c'])]
    a=tilt(records(rows),rows,['m'],alpha=alpha);b=tilt(records(rows),rows,['m'],alpha=alpha)
    assert [r['share'] for r in a['records']]==[r['share'] for r in b['records']]==[.5,.5]
    assert all(r['effective_weight']>=1 for r in a['frequencies'].values())


def test_alpha_zero_restores_unweighted_record_measure():
    rows=[row(i,['m','x','y','z'] if i==0 else ['a','b','c','d']) for i in range(4)]
    assert [r['share'] for r in tilt(records(rows),rows,['m'],alpha=0)['records']]==[.25]*4


def test_rare_weights_exceed_common_and_zero_occurrences_are_finite():
    rows=[row(i,['common','a','b','rare' if i==0 else 'c']) for i in range(8)]
    assert inclusion(rows,'rare')['effective_weight']>inclusion(rows,'common')['effective_weight']
    unseen=inclusion(rows,'unseen');assert unseen['positive']==0 and math.isfinite(unseen['effective_weight'])
    result=tilt(records(rows),rows,['unseen']);assert result['surviving_records']==8
    assert all(r['share']==.125 for r in result['records'])


def test_partial_templates_are_censored_not_automatic_negative():
    rows=[row(0,['m',None,None,None]),row(1,['a',None,None,None]),row(2,['a','b','c','d'])]
    f=inclusion(rows,'m');assert f['positive']==1 and f['negative']==1 and f['unknown']==1 and f['denominator']==2
    assert len(tilt(records(rows),rows,['m'])['records'])==3


def test_multi_move_product_and_repeated_moves_not_double_counted():
    rows=[row(0,['m','n','b','c']),row(1,['a','b','c','d'])]
    r=tilt(records(rows),rows,['m','n','m']);f=r['frequencies']
    assert r['records'][0]['share']/r['records'][1]['share']==pytest.approx(f['m']['effective_weight']*f['n']['effective_weight'])
    assert r['moves']==['m','n']
    assert [x['share'] for x in tilt(records(rows),rows,[])['records']]==[.5,.5]


def test_core_pushforward_keeps_record_and_publication_ids():
    rows=[row(i,['a','b','c','d']) for i in range(3)];rs=records(rows);rs['1']['core_id']='a';rs['2']['core_id']='b'
    r=tilt(rs,rows,[]);assert [(c['core_id'],c['share']) for c in r['cores']]==[('a',2/3),('b',1/3)]
    assert set(r['cores'][0]['records'])=={'0','1'}
    assert rs['0']['template']['publications']==[dict(id='pub0')]


def test_identical_build_occurrences_count_twice_and_condition_normally():
    a=row(0,['m','b','c','d']);b=deepcopy(a);b['publications']=[dict(id='second-team')]
    rows=[a,b,row(2,['x','b','c','d'])];rs=records(rows)
    for r in rs.values():r['core_id']='same-core'
    measure=tilt(rs,rows,['m'])
    assert measure['population_observations']==3
    assert measure['frequencies']['m']['positive']==2
    assert measure['frequencies']['m']['raw_frequency']==pytest.approx(2/3)
    assert measure['cores'][0]['source_records']==3 and measure['cores'][0]['share']==pytest.approx(1)
    conditioned=tilt(rs,rows,['m'],surviving_ids=['0','1'])
    assert [r['share'] for r in conditioned['records']]==[.5,.5,0]
    assert sum(r['share'] for r in conditioned['records'])==pytest.approx(1)


def test_same_training_core_different_moves_remain_observations_then_aggregate():
    # Ten distinct movesets on one core, plus three on another core. Neither
    # family links nor core identity compress P or the move denominator.
    rows=[row(i,['m' if i<3 else 'x',f'variant{i}','b','c']) for i in range(13)]
    distinct=rows
    rs=records(distinct)
    for i,r in enumerate(rs.values()):r['core_id']='A' if i<10 else 'B'
    f=inclusion(distinct,'m');assert (f['positive'],f['denominator'])==(3,13)
    baseline=tilt(rs,distinct,['m'],alpha=0)
    assert baseline['population_observations']==13
    assert baseline['cores'][0]['source_records']==10
    assert baseline['cores'][0]['share']==pytest.approx(10/13)
    weighted=tilt(rs,distinct,['m'],alpha=.5)
    assert weighted['cores'][0]['share']==pytest.approx(sum(r['share'] for r in weighted['records'] if r['core_id']=='A'))
    assert sum(c['share'] for c in weighted['cores'])==pytest.approx(1)


def test_hard_constraints_dominate_weights_and_exhaustion_does_not_reset():
    rows=[row(0,['rare','a','b','c']),row(1,['a','b','c','d'])];rs=records(rows)
    r=tilt(rs,rows,['rare'],alpha=1,surviving_ids=['1']);assert r['cores'][0]['core_id']=='b' and r['records'][0]['hard_excluded']
    empty=tilt(rs,rows,['rare'],surviving_ids=[]);assert empty['status']=='empirical_exhausted' and empty['cores']==[]
    provisional=tilt(rs,rows,[],unresolved_ids=['0']);assert provisional['status']=='retained_with_unresolved_mechanics'


@pytest.mark.parametrize('n_a,expected',[(10,'B'),(100,'A')])
def test_controlled_ten_or_hundred_vs_three_at_same_multiplier(n_a,expected):
    # Fixed diagnostic reference produces p_hat=3.5/56=1/16, w=4 at alpha=.5.
    frequency=[row(i,['m','a','b','c'] if i<3 else ['x','a','b','c']) for i in range(55)]
    rows=[row(i,['x','a','b','c'] if i<n_a else ['m','a','b','c']) for i in range(n_a+3)]
    rs=records(rows)
    for i,r in enumerate(rs.values()):r['core_id']='A' if i<n_a else 'B'
    result=tilt(rs,frequency,['m']);assert result['frequencies']['m']['effective_weight']==pytest.approx(4)
    assert result['cores'][0]['core_id']==expected


def test_bad_parameters_rejected():
    for args in (dict(alpha=-1),dict(alpha=float('nan')),dict(a=0),dict(b=-1)):
        with pytest.raises(ValueError):inclusion([],'m',**args)


def test_time_causal_measure_rewind_and_repeated_actions_use_distinct_moves():
    from battle_evidence.empirical_measure import attach_measures
    rows=[row(0,['pokeapi:move:473','pokeapi:move:94','pokeapi:move:182','pokeapi:move:433']),
          row(1,['pokeapi:move:605','pokeapi:move:182','pokeapi:move:433','pokeapi:move:797'])]
    cats={'pokeapi:species:858':dict(records=records(rows),frequency_rows=rows)}
    replay=dict(snapshots=[dict(timestamp=t,opponents={'actor':dict(current_form='pokeapi:species:858',support_ref='same')}) for t in range(4)],
        support_catalog={'same':dict(full={},observed=dict(builds=['0','1']))},
        action_timeline=[dict(timestamp=t,kind='executed_move',side='opponent',individual='actor',move=m) for t,m in [(1,'pokeapi:move:473'),(2,'pokeapi:move:473'),(3,'pokeapi:move:94')]])
    attach_measures(replay,cats)
    def at(i):return replay['empirical_measures'][replay['support_catalog'][replay['snapshots'][i]['opponents']['actor']['support_ref']]['observed']['measure_ref']]['0.5']
    assert at(0)['moves']==[] and [r['share'] for r in at(0)['records']]==[.5,.5]
    assert at(1)['moves']==at(2)['moves']==['pokeapi:move:473']
    assert at(1)['records']==at(2)['records']
    assert at(3)['moves']==['pokeapi:move:473','pokeapi:move:94']
    assert at(3)['records'][0]['share']>at(2)['records'][0]['share']
    assert at(0)['moves']==[] # later attachment did not mutate historical measures


def test_unresolved_records_have_separate_evaluated_normalization():
    rows=[row(0,['a','b','c','d']),row(1,['a','b','c','d'])]
    r=tilt(records(rows),rows,[],unresolved_ids=['0'])
    assert [x['share'] for x in r['records']]==[.5,.5]
    assert [x['evaluated_share'] for x in r['records']]==[0,1]
    assert r['evaluated_records']==r['provisional_records']==1


def test_export_aliases_do_not_change_equal_observation_mass():
    rows=[row(0,['a','b','c','d']),row(1,['a','b','c','e'])];rs=records(rows)
    rs['0']['observation_count']=3  # stale family metadata must not affect P
    r=tilt(rs,rows,[],alpha=0)
    assert [x['share'] for x in r['records']]==[.5,.5]
    assert r['population_observations']==2 and r['effective_sample_size']==2


def test_signature_includes_all_complete_build_fields_and_ignores_move_order():
    a=row(0,['a','b','c','d']);a['configuration'].update(species='s',nature='n',sp=[1,2,3,4,5,6],ability='a',item='i')
    b=deepcopy(a);b['configuration']['moves'].reverse()
    assert full_record_signature(a)==full_record_signature(b)
    for field,value in [('moves',['a','b','c','e']),('nature','n2'),('item','i2'),('ability','a2'),('sp',[2,2,3,4,5,6])]:
        b=deepcopy(a);b['configuration'][field]=value
        assert full_record_signature(a)!=full_record_signature(b)


def test_identical_vgc_team_observations_remain_separate_and_other_sources_excluded(monkeypatch):
    import json
    from battle_evidence import vgc_population as module
    normalized=dict(species='pokeapi:species:858',item='pokeapi:item:233',ability='pokeapi:ability:156',nature='nature:quiet',
        moves=['pokeapi:move:94','pokeapi:move:182','pokeapi:move:433','pokeapi:move:605'],
        sp=dict(kind='champions_sp',values=[32,0,0,32,2,0]),configuration={})
    member=dict(normalized=normalized,exact_complete=True,pokemon_build_id='original-build',missing=[],issues=[],stat_validation=dict(validation='valid_under_pinned_profile'))
    publications=[]
    for i in range(4):
        m=deepcopy(member)
        if i==2:m['normalized']['moves'][0]='pokeapi:move:473'
        publications.append(dict(id=str(i),extraction_id='e'+str(i),source_id='other-source' if i==3 else 'vgcmulticalc',
            source_url='local',source_key=str(i),canonical=json.dumps(dict(members=[m],composition=['pokeapi:species:858']))))
    class Database:
        def __init__(self,root,readonly):assert readonly
        def scoped(self,population,regulation,format,version):
            assert (population,regulation,format)==('tournament_published','M-C','Doubles')
            return publications
        def close(self):pass
    monkeypatch.setattr(module,'Teams',Database)
    p=module.load_vgc('existing');s=p['scope']
    assert publications[0]['canonical']==publications[1]['canonical']
    assert (s['selected_complete_raw_records'],s['observations_removed_by_deduplication'],s['retained_eligible_occurrences'],s['distinct_training_cores'])==(3,0,3,1)
    rows=p['by_form']['pokeapi:species:858']['builds']
    assert sum(len(r['original_record_ids']) for r in rows)==3
    assert len(rows)==3 and len({r['empirical_record_id'] for r in rows})==3
    assert p['identical_build_diagnostic']['equal_build_excess_occurrences']==1
    assert inclusion(rows,'pokeapi:move:473')['raw_frequency']==pytest.approx(1/3)


def test_cross_individual_speed_witness_maps_core_without_moveset_restriction(monkeypatch):
    from battle_evidence import empirical_measure as module, offensive
    form='pokeapi:species:858'
    old=row('old',['a','b','c','d']);new=row('new',['a','b','c','e'])
    old.update(species=form,ability='pokeapi:ability:156');new.update(species=form,ability='pokeapi:ability:156')
    for r in (old,new):r['configuration']['nature']='nature:quiet'
    core=dict(ability='Magic Bounce',item='Babiri Berry',alignment=dict(increase='special_attack',decrease='speed'),training_points=dict(speed=0),stats=dict(speed=44))
    cat=dict(records={'new':dict(core_id='c',template=template(new))},cores={'c':core},frequency_rows=[new],core_ineligible=[])
    monkeypatch.setattr(module,'catalog',lambda *args:deepcopy(cat))
    monkeypatch.setattr(module,'record_key',lambda r:'new')
    def binary(*args):raise ValueError('cross-individual Speed witnesses')
    monkeypatch.setattr(offensive,'speed_configuration_domain',binary)
    replay=dict(snapshots=[dict(opponents={'actor':dict(current_form=form,support_ref='s')})],
        support_catalog={'s':dict(observed=dict(builds=['old']))},observed_builds={'old':old},empirical_scope=dict(publication_family_audit='obsolete'))
    result,_,_=module.upgrade_empirical_support(replay,{})
    assert result['support_catalog']['s']['observed']['builds']==['new']
    assert result['empirical_scope']=={}  # Never expose the sealed family-compressed scope as the new measure.
    # A genuinely different training core cannot bypass the sealed relation.
    new['configuration']['nature']='nature:timid'
    result,_,_=module.upgrade_empirical_support(replay,{})
    assert result['support_catalog']['s']['observed']['builds']==[]
