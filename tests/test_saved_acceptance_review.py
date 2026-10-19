"""Cache-only acceptance tooling and optional completed Battle 7 review checks."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from recognition.fast_video import fingerprint
import scripts.review_m238_acceptance as review


def test_cache_only_reader_reports_missing_evidence_and_never_initializes_model(tmp_path,monkeypatch):
    monkeypatch.setattr(review,'ROOT',tmp_path)
    monkeypatch.setattr('recognition.onnx_ocr.ONNXOCRBackend.__init__',review.forbidden)
    source=tmp_path/'source';(source/'reads').mkdir(parents=True)
    backend=review.CacheOnlyOCR(source,Counter());backend.source='frame';backend.timestamp=1
    image=np.zeros((20,40,3),dtype=np.uint8)
    missing=backend.read(image,(0,0,40,20),italic=True,independent=True)
    assert missing.value is None and backend.missing[0]['timestamp']==1
    assert backend.real is None and not backend.hits
    key=fingerprint(dict(shape=list(image.shape),pixels=hashlib.sha256(image.tobytes()).hexdigest(),**backend.identity))
    (source/'reads'/(key+'.json')).write_text(json.dumps(dict(text='钢铠鸦',confidence=.999)))
    observed=backend.read(image,(0,0,40,20),italic=True,independent=True)
    assert observed.value=='钢铠鸦' and observed.confidence==.999
    assert backend.real is None and len(backend.hits)==1


@pytest.mark.local_artifacts
def test_completed_battle7_acceptance_uses_prefix_evidence_and_preserves_supported_facts():
    from tracking.evidence_projection import source_times
    root=Path('.cache/battles/sample_battle_7/evaluation/m238-final-acceptance-v1')
    if not (root/'replay-manifest.json').exists():pytest.skip('Optional completed Battle 7 acceptance review absent')
    manifest=json.loads((root/'replay-manifest.json').read_text())
    assert manifest['status']=='complete'
    summary=json.loads((root/'replay-summary.json').read_text())
    assert summary['checkpoints']==6 and summary['corrections']==0
    assert not summary['application_status_regressions']
    assert not summary['duplicate_active_instances']
    assert summary['pokemon_state_equal_to_blocker_diagnostic']
    assert summary['outcomes']==dict(match=20,inconclusive=4)
    assert not summary['changed_statuses'] and not summary['noncheckpoint_binding_changes']
    replay=json.loads((root/'replay.json').read_text())
    original=json.loads(Path('.cache/battles/sample_battle_7/evaluation/m238w-blocker-diagnostic-v1/replay.json').read_text())
    assert {h['event']['event_id'] for h in replay['history'] if h['event']['event_type']!='command_checkpoint'}=={
        h['event']['event_id'] for h in original['history'] if h['event']['event_type']!='command_checkpoint'}
    for receipt in summary['receipts']:
        for outcome in receipt['outcomes']:
            assert not outcome['corrected']
            for proof in outcome['alias_proofs']:
                assert max(source_times(proof['evidence']))<=receipt['timestamp']
    expected={182.03:'side_condition_change',194.0:'status_change',324.02166666666665:'side_condition_change',
              420.50333333333333:'status_change'}
    matched=[]
    for h in replay['history']:
        e=h['bindings'].get('resolved_event',h['event']);t=e['attributes']['observation_time']
        if t in expected and e['event_type']==expected[t]:
            assert h['application_status']=='applied_candidate';matched.append(t)
        support=h.get('bindings',{}).get('hud',{}).get('entry_identity_support')
        if support:
            assert max(source_times(support['evidence']))<=t
    assert set(matched)==set(expected)
    prefix=json.loads((root/'prefix.json').read_text())
    assert all(x['slots']['opponent:right']['instance_id'] is None for x in prefix if 499.51666666666665<=x['timestamp']<521.0216666666666)
    established=next(x for x in prefix if x['timestamp']==521.0216666666666 and x['slots']['opponent:right']['instance_id'])
    assert established['slots']['opponent:right']['species_id']==279
    audit=json.loads((root/'deferred-audit.json').read_text())
    assert len(audit)==35 and all(x['review_status']=='deferred' for x in audit)
