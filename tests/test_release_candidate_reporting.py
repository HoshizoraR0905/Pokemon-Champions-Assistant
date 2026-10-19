"""Portable checks for diagnostic comparisons; no recognition or fixture media."""
from copy import deepcopy
import json
import pytest

from scripts import report_m238_rc as report
from scripts.validate_m238_rc import metrics


def receipt(text='使用了测试招式！', timestamp=10, source='frame-a', kind='move_execution'):
    return dict(event=dict(event_id=source, event_type=kind, side='unknown', original_text=text,
        actor=None, target=None, uncertainty=[], attributes=dict(observation_time=timestamp),
        evidence=[dict(source_id=source, details=dict(timestamp=timestamp))]),
        bindings={}, application_status='deferred', reason='actor_unresolved')


def test_comparison_requires_time_type_and_literal_or_same_evidence():
    current=receipt(); same=receipt(' 使用了测试招式! ',10.5,'old')
    assert len(report.align([current],[same])[0]['before'])==1
    for bad in [receipt(timestamp=20),receipt(kind='unknown'),receipt('别的消息',source='other')]:
        assert report.align([current],[bad])[0]['before']==[]
    # Shared original evidence may align corrected transcription, never state.
    corrected=receipt('不同读法'); before=deepcopy(current)
    assert len(report.align([current],[corrected])[0]['before'])==1
    assert current==before


def test_metrics_does_not_count_partial_receipt_as_fully_applied_or_invent_binding():
    unbound=receipt(); bound=receipt(source='bound')
    bound['bindings']={'resolved_event':deepcopy(bound['event'])}
    bound['bindings']['resolved_event']['attributes']['actor_instance_id']='self:episode-1'
    bound['application_status']='applied_partial';bound['reason']='only_move_membership'
    m=metrics([unbound,bound,receipt(kind='send_out')])
    assert m['moves']==dict(candidates=2,bound=1,bound_fraction=.5,
        receipts={'deferred':1,'applied_partial':1})
    assert m['deferred_causes']=={'actor_unresolved':2}
    assert metrics([])['moves']['bound_fraction'] is None


def test_process_measurement_keeps_missing_values_unknown(tmp_path,monkeypatch):
    monkeypatch.setattr(report,'ROOT',tmp_path)
    p=tmp_path/'time.log';p.write_text(' 21.15 real  8.25 user  1.50 sys\n 4194304 maximum resident set size\n')
    r=report.time_log(p)
    assert (r['real_seconds'],r['peak_resident_bytes'])==(21.15,4194304)
    p.write_text('interrupted before measurement')
    assert report.time_log(p)['real_seconds'] is None
    assert report.time_log(p)['peak_resident_bytes'] is None


def test_consistency_preserves_contradictions_and_flags_future_evidence():
    h=receipt();h['event']['evidence'][0]['details']['timestamp']=11
    state=dict(pokemon={},conflicts=[{'reason':'preserve me'}],knowledge={'occupancy_uncertainty':{'slot':'conflict'}})
    r=report.consistency(dict(history=[h],state=state))
    assert r['violations']==[dict(event_id='frame-a',issue='future_event_evidence')]
    assert r['identity_conflicts']==state['conflicts']
    assert r['independent_false_admission_rate'] is None


def test_reference_comparison_does_not_score_different_message_phase_as_truth(tmp_path,monkeypatch):
    monkeypatch.setattr(report,'ROOT',tmp_path);monkeypatch.setattr(report,'REPORT',tmp_path/'reports'/'audit')
    fixtures=tmp_path/'tests/fixtures/battles';fixtures.mkdir(parents=True)
    for name,key in [('m235_review.json','examples'),('m236u_ui_review.json','cases')]:
        (fixtures/name).write_text(json.dumps({key:[dict(timestamp=10,image='original.png',expected={'message':'测试！'})]}))
    rows=[dict(timestamp=11,image='new.png',message=dict(raw_text='测试！'))]
    result=report.reference_review(rows,[])
    assert all(not x['comparable_time'] and x['exact_normalized_transcription'] is None for x in result['cases'])
    assert result['independent_human_accuracy'] is None


def test_acquisition_guard_explicitly_rejects_new_recognition():
    with pytest.raises(AssertionError,match='cannot acquire'):
        report.forbidden('frame.png')
