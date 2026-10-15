"""Review presentation keeps background intervals and feedback out of evaluation."""
import json
from copy import deepcopy
from pathlib import Path
import pytest
from scripts.build_m236_review import build,event_priority,receipt

CACHE=Path('.cache/battles/sample_battle_5/m236')


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
