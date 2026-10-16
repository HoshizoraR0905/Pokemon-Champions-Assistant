"""Review presentation keeps background intervals and feedback out of evaluation."""
import json
from copy import deepcopy
from pathlib import Path
import pytest
from scripts.build_m236_review import build,event_priority,receipt
from scripts.summarize_m236_feedback import review_counts

CACHE=Path('.cache/battles/sample_battle_5/m236')


def test_feedback_counts_separate_occurrences_cards_and_frame_reviews():
    data = dict(frames=[dict(id=f) for f in ['a', 'b', 'c', 'd']], events=[
        dict(id='occurrence:approved', reviewed_occurrence=True, frame_ids=['a']),
        dict(id='occurrence:frame_only', reviewed_occurrence=True, frame_ids=['b']),
        dict(id='occurrence:blank', reviewed_occurrence=True, frame_ids=['c']),
        dict(id='ui', reviewed_occurrence=False, frame_ids=['d']),
    ])
    annotations = dict(events={
        'occurrence:approved': dict(verdict='correct'),
        'occurrence:blank': dict(verdict='cannot_determine'),
        'ui': dict(verdict='no_ui'),
        'preview:row': dict(verdict='correct'),
    }, frames={
        'a': dict(message_class='readable_correct', reading_source='baseline'),
        'b': dict(message_class='cannot_determine', visible_message='literal text'),
        'c': dict(message_class='cannot_determine', reading_source='ui_u'),
        'unknown-frame': dict(message_class='readable_correct'),
    }, legacy_annotations={
        'a': dict(reviewed=True), 'd': dict(reviewed=True), 'unknown-legacy': dict(reviewed=True),
    })
    result = review_counts(annotations, data)
    assert result['reviewed'] == {'a', 'b', 'd'}
    assert result['structured'] == {'a', 'b'}
    assert result['legacy_only'] == {'d'}
    assert result['occurrence_verdicts'] == {'correct': 1}
    assert result['group_verdicts'] == {'correct': 1, 'no_ui': 1}
    assert result['frame_feedback'] == result['touched'] == 2
    assert result['frame_classes'] == {'readable_correct': 1, 'cannot_determine': 2}
    # An explicit verdict counts even when no constituent frame was reviewed.
    annotations['events']['occurrence:blank']['verdict'] = 'unresolved'
    result = review_counts(annotations, data)
    assert result['occurrence_verdicts'] == {'correct': 1, 'unresolved': 1}
    assert result['touched'] == 3 and result['frame_feedback'] == 2


def test_feedback_report_uses_saved_verdicts_and_preserves_annotation_bytes(tmp_path, monkeypatch):
    from scripts import summarize_m236_feedback as feedback

    monkeypatch.setattr(feedback, 'TARGET', tmp_path)
    annotation = tmp_path / 'm236-event-review-annotations.json'
    original = b'{"schema":"m236-human-review-v2", "events":{"e":{"verdict":"correct"}}, "frames":{}, "legacy_annotations":{}}\n'
    annotation.write_bytes(original)
    data = dict(frames=[], preview=[], events=[dict(
        id='e', reviewed_occurrence=True, frame_ids=[], start=1, end=2,
        title='Saved occurrence', kind='move_execution', receipts=[],
    )])
    (tmp_path / 'review.html').write_text('const DATA=' + json.dumps(data) + ';\nconst $')
    feedback.main()
    report = (tmp_path / 'human-feedback-summary.md').read_text()
    assert '1 reviewed, 0 still without a verdict' in report
    assert 'Actual-event verdicts: correct 1.' in report
    assert 'Individually reviewed frames: 0/0' in report
    assert annotation.read_bytes() == original


def test_priority_distinguishes_failed_move_from_unbound_actor():
    occurrence=dict(label=dict(kind='move_execution'),canonical_recognized=False,actor_bound_correct=False)
    assert event_priority(occurrence)==(2,'Actual recognition failure')
    occurrence['canonical_recognized']=True
    assert event_priority(occurrence)==(3,'Conservative unresolved actor')
    occurrence.update(actor_bound_correct=True,admitted=True)
    assert event_priority(occurrence)==(8,'Supported occurrence')


def test_rejected_raw_ocr_is_not_an_admitted_event():
    record=dict(event=dict(event_id='noise',event_type='unknown',attributes=dict(observation_time=408),
                          original_text='ype',actor=None,target=None,canonical_references={}),
                bindings={},application_status='deferred',reason='low_ocr_confidence')
    out=receipt(record)
    assert out['raw_text']=='ype' and not out['admitted']
    assert 'No semantic event was admitted' in out['reason']


def test_recorded_alias_receipt_reports_the_accepted_identity_scope():
    record=dict(event=dict(event_id='alias',event_type='alias_observation',attributes=dict(observation_time=413.5),
                          original_text='Mega Evolution',actor=None,target=None,canonical_references={}),
                bindings=dict(alias=dict(status='accepted')),application_status='recorded_observation',reason=None)
    out=receipt(record)
    assert out['admitted'] and 'association accepted' in out['outcome']
    assert 'active slot remains unresolved' in out['outcome']


@pytest.mark.local_artifacts(str(CACHE/'development-evaluation.json'),str(CACHE/'held_out-evaluation.json'),str(CACHE/'held_out-replay.json'))
def test_cached_review_groups_do_not_inflate_event_or_move_denominators():
    evaluations=[json.loads((CACHE/f'{s}-evaluation.json').read_text()) for s in ['development','held_out']]
    frozen=deepcopy(evaluations)
    history=json.loads((CACHE/'held_out-replay.json').read_text())['engine']['history']
    seeds=json.loads(Path('tests/fixtures/battles/m236_viewer_visibility.json').read_text())['frames']
    data=build(evaluations,history,seeds)
    assert evaluations==frozen
    assert len(data['frames'])==120
    assert sum(e['reviewed_occurrence'] for e in data['events'])==11
    moves=[e for e in data['events'] if e['kind']=='move_execution']
    assert len(moves)==2
    assert next(e for e in moves if e['id']=='occurrence:coaching')['priority']==2
    assert next(e for e in moves if e['id']=='occurrence:fake_out')['review']['executed_move_revealed']
    white=next(f for f in data['frames'] if abs(f['timestamp']-408.001667)<.01)
    assert white['visibility_review']['classification']=='no_message'
    assert not any(r['admitted'] for r in white['receipts'])
    background=next(e for e in data['events'] if e['kind']=='background' and white['id'] in e['frame_ids'])
    assert background['representatives']['during']==white['id']
    assert background['priority']==7 and not background['reviewed_occurrence']
    assert any(e['id']=='nickname:development:Big Nugget' for e in data['events'])


def test_portable_package_preserves_evidence_and_deduplicates(tmp_path):
    from scripts.package_m236_review import package
    import hashlib

    source = tmp_path / 'cached.png'
    source.write_bytes(b'cached image evidence')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    payload = {'frames': [{'id': 'immutable-frame-id', 'image': 'cached.png'}],
               'preview': [{'evidence': {'image': 'cached.png', 'sha256': digest}}]}
    annotation = tmp_path / 'm236-event-review-annotations.json'
    annotation.write_bytes(b'{"human": "unchanged"}')
    manifest = package(payload, tmp_path)
    assert len(manifest) == 1
    image = payload['frames'][0]['image']
    assert (tmp_path / image).read_bytes() == source.read_bytes()
    assert payload['frames'][0]['id'] == 'immutable-frame-id'
    assert payload['frames'][0]['source_image'] == 'cached.png'
    assert payload['preview'][0]['evidence']['sha256'] == digest
    assert package(payload, tmp_path) == manifest
    assert annotation.read_bytes() == b'{"human": "unchanged"}'
