from copy import deepcopy
import pytest
from battle_evidence.visual_v21 import error_bounds, timing, evaluate
from tests.test_visual_validation import ref, pred


def test_interval_error_retains_unknown_instants():
    assert error_bounds([10,12],[11,11.5]) == [0,1.5]
    assert timing([10,12],[0,30],15)['timing_quality'] == 'insufficient_localization'
    assert timing([10,12],[14.5,15],15)['timing_quality'] == 'outside_2s'
    assert timing([10,12],[12,12],12)['timing_quality'] == 'within_2s'
    assert timing([10,12],[12,12.001],12)['timing_quality'] == 'insufficient_localization'


def test_invalid_intervals_rejected():
    for a in ([2,1],[0,float('nan')],[1]):
        with pytest.raises(ValueError):error_bounds(a,[1,2])


def test_two_second_policy_and_outside_counterpart_are_separate():
    r=ref((0,1),(10,12));p=pred((14.5,15));p.update(counter_observations=[],reconstruction={'ledger':[]})
    c=evaluate(r,p)
    assert c['counts']['matched']==0
    assert len(c['outside_tolerance_associations'])==1
    assert not c['outside_tolerance_associations'][0]['interval_compatible']
    assert c['accuracy_metrics']['precision'] is None


def test_broad_overlap_cannot_certify_timing_or_multiple_entries():
    r=ref((0,1),(10,12),(20,22));p=pred((0,30));p.update(counter_observations=[],reconstruction={'ledger':[]})
    c=evaluate(r,p)
    assert c['counts']['matched']==1 and c['counts']['missed']==1
    assert c['matches'][0]['timing_quality']=='insufficient_localization'


def test_uncertain_reference_stays_unscored():
    r=ref((0,1),(10,12));r['turns'][1]['command_start']['confidence']='uncertain'
    p=pred((10,11));p.update(counter_observations=[],reconstruction={'ledger':[]})
    c=evaluate(r,p)
    assert c['counts']['missed']==c['counts']['unmatched_predictions']==0


def test_sampler_selection_ignores_prediction_labels_and_retains_chunk_pts(tmp_path, monkeypatch):
    import json
    import cv2
    import numpy as np
    import battle_evidence.visual_v21 as mod
    from battle_artifacts import BattleArtifacts
    monkeypatch.chdir(tmp_path)
    battle=BattleArtifacts('sample_battle_5',tmp_path)
    rows=[]
    for i,t in enumerate((0.,1.,2.02,3.,4.01)):
        image=tmp_path/f'{i}.png';cv2.imwrite(str(image),np.zeros((12,20,3),np.uint8))
        rows.append(dict(timestamp=t,source_pts=round((t-(2 if t>=2 else 0))*600),source_time_base='1/600',seek_origin_seconds=2 if t>=2 else 0,image=str(image),source_id=f'v#{t}',ui={'prediction_boundary':999-i}))
    source=tmp_path/'observations.json';source.write_text(json.dumps(rows))
    monkeypatch.setattr(mod,'source_rows',lambda n:(battle,source,rows))
    result=mod.sample(5)
    assert [f['target_timestamp'] for f in result['frames']]==[0,2,4]
    assert [f['timestamp'] for f in result['frames']]==[0,2.02,4.01]
    assert result['frames'][1]['seek_origin_seconds']==2
    assert result['ocr_calls']==result['frames_newly_decoded']==0
    assert mod.sample(5)['seconds']==result['seconds']
