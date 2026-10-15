"""Read-only M236-U seals, dependency, budget and preservation verification."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
P=ROOT/'.cache/battles/sample_battle_5/m236u'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify():
    read=lambda name:json.loads((P/name).read_text())
    seal=read('implementation-seal.json');deps=read('dependency-seal.json')
    assert all(sha(ROOT/f)==h for f,h in {**seal['code'],**deps['code']}.items()),'U implementation/dependency changed; do not reuse sealed results'
    assert sha(ROOT/'tests/fixtures/battles/m236u_ui_review.json')==seal['fixture_sha256']
    original=read('baseline.json')['protected'];authorized={'reports/M2.3.6-review/review.html','reports/M2.3.6-review/README.md'}
    assert all(sha(ROOT/f)==h for f,h in original.items() if f not in authorized),'Historical output/fixture/ledger changed'
    old=json.loads((ROOT/'.cache/battles/sample_battle_5/m236/implementation-seal.json').read_text())
    assert all(sha(P/'baseline-code'/f)==old['code'][f] for f in ['battle_events/parser.py','tracking/state_engine.py'])
    ledger=read('ocr-ledger.json');assert ledger['total']<=ledger['limit']==96
    assert ledger['total']==len(ledger['reservations'])
    replay=read('regression-replay.json');receipts=replay['executed_event_receipts']
    assert len(receipts)==2 and sum(r['status']=='applied_partial' for r in receipts)==1
    assert sum(r['reason']=='move_actor_not_bound_to_observed_prefix' for r in receipts)==1
    assert all(not moves for t,moves in replay['prefix_revealed_moves'].items() if float(t)<415.5)
    baseline=json.loads((ROOT/'.cache/m234/baseline.json').read_text())
    allowed={'tracking/state_engine.py','tracking/evidence_fusion.py','tracking/hidden_state.py','battle_events/schema.py'}
    legacy=[f for f,h in baseline.items() if sha(ROOT/f)!=h and f not in allowed]
    return dict(status='verified',historical_paths_checked=len(original)-len(authorized),authorized_review_outputs=sorted(authorized),
                original_source_archive_verified=True,ocr_predictions=ledger['total'],ocr_limit=ledger['limit'],
                u_dependencies_verified=len(deps['code']),legacy_source_audit_incompatibilities=legacy,
                replays_decoding_or_inference_performed=False)


if __name__=='__main__':print(json.dumps(verify(),indent=2))
