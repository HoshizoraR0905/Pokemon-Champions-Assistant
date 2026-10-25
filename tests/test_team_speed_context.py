"""Portable capability semantics, leakage, permutation and export regressions."""
from copy import deepcopy
import csv
import json
from pathlib import Path
from collections import Counter

import numpy as np
import pytest
from experiments.team_speed_context.features import (Mechanisms,FEATURES,FAMILIES,DESIGN,observed,presence,count_known,conjunction,dictionary)
from experiments.team_speed_context.model import Encoder,Ridge,interaction_support
from experiments.team_speed_context.evaluate import group_folds,permute_groups,training_subset,evaluate_fold,metrics
from experiments.team_speed_context.run import protected_files

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'milestone_reports/assets/m354'


@pytest.fixture(scope='module')
def mechanics():return Mechanisms()


def teammate(mechanics,species='Metagross',ability='Clear Body',item='Sitrus Berry',moves=None,ordinal=0):
    moves=moves or ['Protect','Iron Head','Psychic','Earthquake']
    return dict(species=mechanics.ids[species] if species else None,ability=mechanics.ids[ability] if ability else None,
                item=mechanics.ids[item] if item else None,moves=[mechanics.ids[m] if m else None for m in moves],
                nature='nature:adamant',issues=[],ordinal=ordinal,source_url='https://example.com/team')


def mates(mechanics):return [teammate(mechanics,ordinal=i) for i in range(5)]


def test_modes_are_nonexclusive_and_count_only_other_five(mechanics):
    team=mates(mechanics)
    team[0]['moves']=[mechanics.ids[m] for m in ['Tailwind','Trick Room','Protect','Taunt']]
    context,evidence=mechanics.extract(team)
    assert context['tailwind_count']==context['trick_room_count']==context['taunt_count']==1
    assert context['natural_fast_count']==0 and context['sun_setter_option']==0
    assert evidence['no_activation_or_bring_assumption']
    with pytest.raises(ValueError):mechanics.extract(team+[team[0]])


def test_unknown_is_not_absent_and_known_presence_survives_unknown(mechanics):
    team=mates(mechanics);team[0]['moves']=[None]
    c,_=mechanics.extract(team)
    assert c['tailwind_count'] is None and c['priority_support_option'] is None
    team[1]['moves'][0]=mechanics.ids['Helping Hand']
    c,_=mechanics.extract(team);assert c['priority_support_option']==1
    assert presence([0,None]) is None and presence([1,None])==1
    assert count_known([1,None]) is None and conjunction(0,None)==0


def test_weather_setter_receiver_and_supported_pair_separate(mechanics):
    team=mates(mechanics)
    team[0]=teammate(mechanics,'Pelipper','Drizzle',ordinal=0)
    c,_=mechanics.extract(team)
    assert c['rain_setter_option']==1 and c['swift_swim_option']==0 and c['rain_pair_option']==0
    team[1]=teammate(mechanics,'Basculegion','Swift Swim',ordinal=1)
    c,_=mechanics.extract(team)
    assert c['rain_setter_option']==c['swift_swim_option']==c['rain_pair_option']==1
    team[0]=teammate(mechanics,ordinal=0)
    c,_=mechanics.extract(team)
    assert c['swift_swim_option']==1 and c['rain_setter_option']==c['rain_pair_option']==0


def test_missing_ability_not_imputed_from_legal_species_options(mechanics):
    team=mates(mechanics);team[0]=teammate(mechanics,'Venusaur',None,ordinal=0)
    c,_=mechanics.extract(team)
    assert c['chlorophyll_option'] is None  # Legal option is not an observation.
    assert c['swift_swim_option']==0  # Pinned native domain can rule it out.
    team[0]=teammate(mechanics,'Venusaur','Overgrow',ordinal=0)
    c,_=mechanics.extract(team);assert c['chlorophyll_option']==0


def test_conditional_mega_sun_does_not_select_mega_or_mega_speed(mechanics):
    team=mates(mechanics)
    team[0]=teammate(mechanics,'Charizard','Blaze','Charizardite Y',ordinal=0)
    team[1]=teammate(mechanics,'Venusaur','Chlorophyll',ordinal=1)
    c,e=mechanics.extract(team)
    assert c['sun_setter_option']==c['chlorophyll_option']==c['sun_pair_option']==1
    assert any(p['ability']=='Drought' and p['mega'] for p in e['teammates'][0]['profiles'])
    # Metagross native Speed is 70; the stone does not turn it into 110 for this feature.
    meta=teammate(mechanics,'Metagross','Clear Body','Metagrossite')
    assert mechanics.natural_fast(meta)==0


def test_two_conditional_mega_roles_leave_pair_unknown(mechanics,monkeypatch):
    team=mates(mechanics)
    def profile(m):
        if m['ordinal']==0:return [dict(ability='Drought',mega=True)],False
        if m['ordinal']==1:return [dict(ability='Chlorophyll',mega=True)],False
        return [dict(ability='Clear Body',mega=False)],False
    monkeypatch.setattr(mechanics,'profiles',profile)
    c,_=mechanics.extract(team)
    assert c['sun_setter_option']==c['chlorophyll_option']==1 and c['sun_pair_option'] is None
    monkeypatch.undo()


def test_manual_weather_unknown_in_narrow_verified_definition(mechanics):
    team=mates(mechanics);team[0]['moves'][0]=mechanics.ids['Sunny Day']
    c,_=mechanics.extract(team);assert c['sun_setter_option'] is None


def test_target_and_teammate_sp_never_enter_features(mechanics):
    team=mates(mechanics);baseline=mechanics.extract(team)
    changed=deepcopy(team)
    for member in changed:member.update(sp={'values':[32]*6},training_points={'speed':32},actual_speed=999,cluster=1)
    assert mechanics.extract(changed)==baseline
    raw=dict(normalized=dict(changed[0],sp='secret'),ordinal=1,original={'sp':'secret'})
    projection=observed(raw)
    assert 'sp' not in projection and 'original' not in projection and 'training_points' not in projection
    assert set(projection)=={'species','moves','ability','item','nature','issues','ordinal','source_url'}


def sample_rows(n_groups=20):
    rows=[];targets=[]
    for g in range(n_groups):
        for j in range(2 if g%7==0 else 1):
            context={f:0. for f in FEATURES};context['tailwind_count']=float(g%2)
            context['natural_fast_count']=float(g%4)
            rows.append(dict(id=f'record-{g}-{j}',group=f'group-{g}',own=dict(moves=['a','b','c','d' if g%2 else 'e'],item='berry' if g%3 else 'orb'),
                             context=context,interactions={s['name']:0. for s in DESIGN['interactions']}))
            targets.append([float(2+g%8),float(g%5),float(50+g%9)])
    return rows,np.array(targets)


def test_training_only_vocabulary_imputation_scaling_and_unknowns():
    rows,y=sample_rows(8);rows[0]['context']['sun_setter_option']=None
    encoder=Encoder(['sun_setter_option']).fit(rows[:4]);before=deepcopy(encoder.receipt())
    test=deepcopy(rows[4:]);test[0]['own']['moves']=['never','seen','in','training'];test[0]['own']['item']='unseen'
    test[0]['context']['sun_setter_option']=1000.
    encoded=encoder.transform(test)
    assert encoder.receipt()==before
    assert 'never' not in encoder.moves and 'unseen' not in encoder.items
    assert np.isfinite(encoded).all()
    assert set(encoder.training_ids)=={r['id'] for r in rows[:4]}
    all_missing=deepcopy(rows[:4])
    for r in all_missing:r['context']['sun_setter_option']=None
    e=Encoder(['sun_setter_option']).fit(all_missing)
    assert e.fill[-1]==0 and np.isfinite(e.transform(test)).all()
    assert e.receipt()['all_feature_names'][-1]=='missing:sun_setter_option'


def test_ridge_deterministic_independent_targets_and_marginal_clipping():
    rows,y=sample_rows(12)
    a=Ridge(FEATURES).fit(rows,y);b=Ridge(FEATURES).fit(rows,y)
    assert a.receipt()==b.receipt() and np.array_equal(a.predict(rows),b.predict(rows))
    changed=y.copy();changed[:,1]+=20
    c=Ridge(FEATURES).fit(rows,changed)
    assert np.allclose(a.predict(rows)[:,[0,2]],c.predict(rows)[:,[0,2]])
    assert a.alpha==10
    for r in rows:r['context']['tailwind_count']=1e6
    p=a.predict(rows);assert (p>=0).all() and (p<=np.array([32,32,66])).all()


def test_fold_source_group_isolation_and_target_independent_assignment():
    rows,y=sample_rows(20)
    for seed in DESIGN['outer_seeds']:
        mapping=group_folds(rows,seed)
        assert mapping==group_folds(list(reversed(rows)),seed)
        for g in mapping:assert len({mapping[r['group']] for r in rows if r['group']==g})==1
        assert set(mapping.values())==set(range(5))
    assert len({tuple(sorted(group_folds(rows,s).items())) for s in DESIGN['outer_seeds']})>1


def test_permutation_preserves_complete_group_blocks_and_own_fields():
    rows,y=sample_rows(28);original=deepcopy(rows)
    permuted,receipt=permute_groups(rows,1234)
    assert rows==original and permuted==permute_groups(rows,1234)[0]
    assert set(receipt['donor_groups'])==set(receipt['donor_groups'].values())=={r['group'] for r in rows}
    for dst in rows:
        i=rows.index(dst);new=permuted[i]
        assert new['own']==dst['own'] and new['id']==dst['id'] and new['group']==dst['group']
        donor=receipt['donor_groups'][dst['group']]
        donors=[r for r in rows if r['group']==donor]
        assert any(new['context']==r['context'] for r in donors)
    for g in receipt['donor_groups']:
        before=sorted(json.dumps(r['context'],sort_keys=True) for r in rows if r['group']==receipt['donor_groups'][g])
        after=sorted(json.dumps(r['context'],sort_keys=True) for r in permuted if r['group']==g)
        assert before==after


def test_learning_subsets_nested_and_group_complete_without_targets():
    rows,y=sample_rows(25)
    subsets=[training_subset(rows,354,0,f) for f in DESIGN['learning_fractions']]
    assert set(subsets[0])<=set(subsets[1])<=set(subsets[2])==set(range(len(rows)))
    for indices in subsets:
        for g in {rows[i]['group'] for i in indices}:assert {i for i,r in enumerate(rows) if r['group']==g}<=set(indices)


def test_interactions_are_separate_and_gate_uses_training_groups():
    rows,y=sample_rows(20)
    for r in rows:r['interactions']['taunt_tailwind']=float(int(r['group'].split('-')[-1])<9)
    support=interaction_support(rows,'taunt_tailwind');assert support['positive_groups']==9 and not support['fit']
    for r in rows:
        if r['group']=='group-9':r['interactions']['taunt_tailwind']=1.
    assert interaction_support(rows,'taunt_tailwind')['fit']
    assert len(DESIGN['interactions'])==3


def test_one_fold_receipts_prove_preprocessing_and_permutation_isolation():
    rows,y=sample_rows(20);result=evaluate_fold(rows,y,354,0)
    assert not set(result['training_ids'])&set(result['test_ids'])
    assert not set(result['training_groups'])&set(result['test_groups'])
    for receipt in result['model_receipts'].values():
        assert receipt['preprocessing']['training_ids']==result['training_ids']
        assert not set(receipt['preprocessing']['training_ids'])&set(result['test_ids'])
    for control in result['controls']:
        assert set(control['receipt']['donor_groups'].values())<=set(result['training_groups'])
        assert not set(control['receipt']['donor_groups'].values())&set(result['test_groups'])
        assert control['preprocessing']['training_ids']==result['training_ids']
    assert len(result['controls'])==6 and len(result['learning_curves'])==6
    assert result==evaluate_fold(rows,y,354,0)


def test_simple_error_metrics_and_group_weighting():
    m=metrics([[0,0,0],[0,0,0],[0,0,0]],[[1,1,1],[1,1,1],[4,4,4]],['a','a','b'])
    assert m['mae']==[2,2,2] and m['median_absolute_error']==[1,1,1] and m['group_macro_mae']==[2.5]*3


def test_actual_feature_exports_multiplicity_missingness_and_no_sp_predictors():
    with (ASSETS/'feature-values.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    d=json.loads((ASSETS/'feature-definitions.json').read_text())
    assert len(rows)==len({r['occurrence_id'] for r in rows})==197
    assert len({r['source_group'] for r in rows})==187 and len({r['m351_source_group'] for r in rows})==192
    assert not any('sp' in field.lower() or 'cluster' in field.lower() or 'stat' in field.lower() for field in rows[0] if field not in FEATURES)
    for feature in d['dictionary']:
        name=feature['name'];positive=[r for r in rows if r[name]!='' and float(r[name])>0];missing=[r for r in rows if r[name]=='']
        assert len(positive)==feature['positives'] and len({r['source_group'] for r in positive})==feature['positive_groups']
        assert len(missing)==feature['missing']
        assert feature['selected_a_priori']
    assert any(float(r['tailwind_count'])>0 and float(r['trick_room_count'])>0 for r in rows)


def test_actual_paired_predictions_errors_and_metrics_recompute():
    with (ASSETS/'paired-predictions.csv').open(newline='') as f:records=list(csv.DictReader(f))
    summary=json.loads((ASSETS/'evaluation.json').read_text())
    assert len(records)==197*3*3
    for seed in DESIGN['outer_seeds']:
        for target in ('speed','attack','bulk'):
            rs=[r for r in records if int(r['seed'])==seed and r['target']==target]
            assert len(rs)==197 and len({r['occurrence_id'] for r in rs})==197
            for group in {r['source_group'] for r in rs}:assert len({r['fold'] for r in rs if r['source_group']==group})==1
    for r in records:
        assert float(r['own_absolute_error'])==pytest.approx(abs(float(r['true_sp'])-float(r['own_prediction'])),abs=2e-8)
        assert float(r['context_absolute_error'])==pytest.approx(abs(float(r['true_sp'])-float(r['context_prediction'])),abs=2e-8)
        assert float(r['own_minus_context_error'])==pytest.approx(float(r['own_absolute_error'])-float(r['context_absolute_error']),abs=2e-8)
    for j,target in enumerate(('speed','attack','bulk')):
        rs=[r for r in records if r['target']==target]
        for model,prefix in [('A_median','median'),('B_own','own'),('C_context','context')]:
            assert np.mean([float(r[prefix+'_absolute_error']) for r in rs])==pytest.approx(summary['pooled'][model]['mae'][j],abs=1e-8)
    assert len(summary['permutation'])==6 and len(summary['per_seed'])==3
    assert all(not fold[s['name']]['fit'] for fold in summary['interaction_support'] for s in DESIGN['interactions'])


def test_encoder_ignores_target_sp_cluster_nature_and_teammate_stats():
    rows,y=sample_rows(8);changed=deepcopy(rows)
    for r in changed:
        r.update(training_points={'speed':32},cluster=2,actual_speed=999,teammates=[{'sp':'secret'}])
        r['own'].update(sp={'values':[32]*6},nature='nature:timid',cluster=1)
    a=Encoder(FEATURES).fit(rows);b=Encoder(FEATURES).fit(changed)
    assert a.receipt()==b.receipt() and np.array_equal(a.transform(rows),b.transform(changed))


def test_actual_cases_join_target_and_original_teammate_observables():
    cases=json.loads((ASSETS/'case-studies.json').read_text())
    with (ASSETS/'feature-values.csv').open(newline='') as f:features={r['occurrence_id']:r for r in csv.DictReader(f)}
    assert (cases['offensive_trick_room']['n'],cases['taunt_tailwind']['n'],cases['multiple_options']['n'])==(3,2,17)
    for case in cases.values():
        assert len(case['occurrence_ids'])==len(case['individual_targets'])==case['n']
        for example in case['examples']:
            assert len(example['teammates'])==5 and len({m['ordinal'] for m in example['teammates']})==5
            assert all(m['source_url']==example['source_url'] for m in example['teammates'])
            assert all('sp' not in m and 'training_points' not in m for m in example['teammates'])
            assert all(example['context'][f]==(None if features[example['id']][f]=='' else float(features[example['id']][f])) for f in FEATURES)
            assert example['group']==features[example['id']]['source_group']


@pytest.mark.parametrize('which',['m351','m353','annotations'])
def test_runner_rejects_protected_output_namespace(tmp_path,monkeypatch,which):
    import experiments.team_speed_context.run as runner
    m351=tmp_path/'m351';m353=tmp_path/'m353'
    output={'m351':m351/'child','m353':m353/'child','annotations':tmp_path/'.cache/research/m353/child'}[which]
    monkeypatch.setattr(runner,'ROOT',tmp_path)
    monkeypatch.setattr('sys.argv',['team-context','--m351',str(m351),'--m353',str(m353),'--output',str(output)])
    with pytest.raises(ValueError,match='outside'):runner.main()
    assert not output.exists()
