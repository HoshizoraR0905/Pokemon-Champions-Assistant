"""Review status and interval comparison contracts, separate from inference."""
from copy import deepcopy
import pytest
from battle_evidence.visual_validation import compare,counter_checks


def ref(*intervals):
    return dict(battle_id='b',review_status='agent-reviewed',human_approved=False,
        turns=[dict(id=f't{i}',command_start=dict(interval=list(x),confidence='medium',disposition='inferred_visible_sequence',human_approved=False),
                    resolution_start=dict(interval=[x[1]+3,x[1]+4]),hud_layout=dict(count=4),human_approved=False) for i,x in enumerate(intervals)],
        intervals=[],termination=dict(interval=[100,101]))


def pred(*intervals):
    return dict(battle_id='b',visual=dict(segments=[dict(id=f'p{i}',end=list(x),next_command_time=x[1],command_start_time=0,status='confirmed') for i,x in enumerate(intervals)]))


def test_interval_overlap_one_to_one_and_error():
    c=compare(ref((0,1),(10,11),(20,21)),pred((10.5,11.5),(20,20.5)))
    assert c['counts']['matched']==2 and c['counts']['missed']==0 and c['counts']['unmatched_predictions']==0
    assert c['matches'][0]['point_error_to_reference_interval']==.5
    assert c['accuracy_metrics']['precision'] is None


def test_tolerance_applies_to_gap_between_intervals():
    c=compare(ref((0,1),(10,11)),pred((12.5,13)))
    assert c['counts']['matched']==1 and c['matches'][0]['interval_gap']==1.5
    assert compare(ref((0,1),(10,11)),pred((13,14)))['counts']['matched']==0


def test_uncertain_reference_is_not_a_definite_FP_or_FN():
    r=ref((0,1),(10,11));r['turns'][1]['command_start']['confidence']='uncertain'
    c=compare(r,pred((10,11)))
    assert c['counts']['missed']==0 and c['counts']['unmatched_predictions']==0
    assert len(c['uncertain_predictions'])==1 and len(c['uncertain_references'])==1


def test_wide_merged_interval_cannot_earn_two_matches():
    c=compare(ref((0,1),(10,11),(20,21)),pred((9,22)))
    assert c['counts']['matched']==1 and c['counts']['missed']==1
    assert len(c['possible_merges'])==1


def test_split_predictions_not_both_counted_correct():
    c=compare(ref((0,1),(10,11)),pred((10,10.5),(10.5,11)))
    assert c['counts']['matched']==1 and c['counts']['unmatched_predictions']==1
    assert len(c['possible_splits'])==1


def test_false_submenu_return_is_explicit_review_alert():
    r=ref((0,1),(10,11));r['intervals']=[dict(kind='command_submenu',interval=[15,19],confidence='medium')]
    c=compare(r,pred((10,11),(17,18)))
    assert len(c['submenu_false_turn_review_alerts'])==1


def test_human_metrics_require_actual_transition_approval_as_well_as_root_flags():
    r=ref((0,1),(10,11));r.update(review_status='human-verified',human_approved=True)
    for t in r['turns']:t['human_approved']=True
    assert compare(r,pred((10,11)))['accuracy_metrics']['precision'] is None
    for t in r['turns']:t['command_start']['human_approved']=True
    assert compare(r,pred((10,11)))['accuracy_metrics']['precision']==1


def test_reduced_HUD_reference_coverage_not_invented():
    c=compare(ref((0,1),(10,11)),pred((10,11)))
    assert c['reduced_combatant_reference_coverage']==0
    r=ref((0,1),(10,11));r['turns'][1]['hud_layout']['count']=2
    c=compare(r,pred((10,11)))
    assert c['by_reference_HUD_count']=={'2':1}


def test_cross_battle_and_negative_tolerance_rejected():
    p=pred((10,11));p['battle_id']='other'
    with pytest.raises(ValueError):compare(ref((0,1)),p)
    with pytest.raises(ValueError):compare(ref((0,1)),pred(),tolerance=-1)


def test_no_predictions_and_no_subsequent_reference_do_not_divide_by_zero():
    c=compare(ref((0,1)),pred())
    assert c['counts']['matched']==0 and c['accuracy_metrics']['recall'] is None


def counters(a,b,*,scope='field',elapsed=(0,1),reset=False):
    rows=[]
    for i,(ts,raw,n) in enumerate(zip((1,11),(a,b),elapsed)):
        rows.append(dict(id=f'c{i}',scope=scope,effect='rain',timestamp=ts,raw_display=raw,
            inferred_elapsed_turns=n,temporal_confirmation=True,track_epoch=1))
    return dict(counter_observations=rows,reconstruction=dict(ledger=[dict(kind='effect',effect='rain',change='start',timestamp=5)] if reset else []))


def test_counter_conflict_is_retained_instead_of_forcing_reference():
    checks=counter_checks(ref((0,1),(10,11)),counters('4/5','4/5',elapsed=(1,1)))
    assert checks[0]['status']=='counter_conflict_requires_review' and checks[0]['elapsed_delta']==0


def test_counter_reset_and_unknown_scope_do_not_claim_corroboration():
    r=ref((0,1),(10,11))
    assert counter_checks(r,counters('4/5','5/5',reset=True))[0]['status'].startswith('activation_or_epoch_changed')
    assert counter_checks(r,counters('4/5','3/5',scope='unknown'))[0]['status'].startswith('side_or_effect_instance_unresolved')


def test_command_entry_cannot_masquerade_as_resolution_completion_measurement():
    r=ref((0,1),(10,11))
    for t in r['turns']:t['resolution_completion']=dict(interval=[8,9])
    c=compare(r,pred((10,11)))
    ends=[p for p in c['phase_transition_comparisons'] if p['phase_type']=='resolution_completion']
    assert all(p['status']=='not_estimated_separately' for p in ends)
