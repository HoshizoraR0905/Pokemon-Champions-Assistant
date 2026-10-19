"""Bounded evidence capture abstains; later HUD/human answers cannot label it."""
from dataclasses import asdict
import hashlib
from copy import deepcopy
import pytest
from recognition.entry_model import probe_entry,preview_candidates
from tests.test_provisional_occupancy import arrival
from tests.test_trainer_nickname_binding import visual_fixture


def test_probe_is_bounded_and_cannot_read_species_from_future_huds(tmp_path):
    _,receipt=arrival();_,state,_=visual_fixture();preview=state.knowledge['identity_ledger']['roster']
    path=tmp_path/'frame.png';path.write_bytes(b'saved immutable frame')
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    rows=[dict(timestamp=t,source_pts=t,source_time_base='1/1',source_id=str(t),image='frame.png',sha256=sha,
               snapshot=dict(species='human or future label must be ignored')) for t in range(2,9)]
    result=probe_entry(asdict(receipt),rows,preview,tmp_path)
    assert [r['timestamp'] for r in result['frames']]==[3,4,5]
    assert result['status']=='abstained' and result['species_id'] is None and result['recognition_calls']==0
    assert all(c['score'] is None for c in result['candidate_scores'])
    changed=deepcopy(rows)
    for row in changed:row['snapshot']={'species':279}
    assert probe_entry(asdict(receipt),changed,preview,tmp_path)==result
    with pytest.raises(ValueError,match='bounded'):
        probe_entry(asdict(receipt),rows,preview,tmp_path,max_frames=5)


def test_probe_requires_complete_preview_before_the_entry_and_applied_arrival(tmp_path):
    _,receipt=arrival();_,state,_=visual_fixture();preview=state.knowledge['identity_ledger']['roster']
    assert not preview_candidates(preview[:-1],'opponent',1)
    for r in preview:r['evidence']['timestamp']=2
    assert not preview_candidates(preview,'opponent',1)
    payload=asdict(receipt);payload['application_status']='deferred'
    with pytest.raises(ValueError,match='applied entry'):
        probe_entry(payload,[],preview,tmp_path)
