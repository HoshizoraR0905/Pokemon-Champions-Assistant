"""Verify and publish recovered B21–B24 measurements; no pipeline execution."""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())

def run():
    original=ROOT/'docs/performance/b24-runtime-measurements.json'
    data=read(original)
    for p,h in data['sources'].items():
        if sha(ROOT/p)!=h:raise ValueError('Recovered source changed: '+p)
    verification={}
    for k,b in data['battles'].items():
        source=ROOT/b['source_directory'];p=read(source/'replay.json');m=read(source/'manifest.json')
        execution=read(ROOT/b['benchmark_directory']/'execution.json')
        assert len(p['history'])==b['receipts']
        assert dict(Counter(r['event']['event_type'] for r in p['history']))==b['event_types']
        assert len(json.dumps(p['state'],ensure_ascii=False,separators=(',',':')).encode())==b['state_structure']['compact_json_bytes']
        assert execution['normal_cli_wall_seconds']==b['full_external_cli_wall_seconds']
        assert m['cold_end_to_end_wall_seconds']==b['internal_pipeline_seconds']
        assert m['results']['replay_seconds']==b['broad_reconstruction_seconds']
        assert len(execution['attempts'])==1 and execution['returncode']==0
        verification[k]=dict(replay_sha256=sha(source/'replay.json'),timing_and_workload_rechecked=True)
    profiles={}
    for battle in (23,24):
        path=ROOT/f'.cache/battles/sample_battle_{battle}/diagnosis/runtime-components-v2/manifest.json'
        profile=read(path);assert profile['status']=='complete' and profile['source_replay_unchanged']
        assert profile['identity']['replay']==verification[str(battle)]['replay_sha256']
        assert sha(path.parent/'diagnose_b24_runtime.py')==profile['identity']['script']
        profiles[str(battle)]=dict(path=str(path.relative_to(ROOT)),sha256=sha(path),data=profile)
    b23=data['battles']['23'];b24=data['battles']['24'];n=b24['receipts']/b23['receipts']
    constant_cost=b23['broad_reconstruction_seconds']/b23['receipts']*(b24['receipts']-b23['receipts'])
    data.update(schema_version=2,scope='Verified recovered production measurements plus separate frozen-state microbenchmarks; no recognition or replay',
        original_measurements=dict(path=str(original.relative_to(ROOT)),sha256=sha(original)),
        verification=dict(recovered_source_hashes_checked=len(data['sources']),mismatches=0,battles=verification),
        component_profiles=profiles,
        scaling_diagnostics=dict(constant_B23_seconds_per_receipt_workload_delta_seconds=constant_cost,
            remaining_broad_delta_seconds=data['B24_minus_B23']['delta_components']['broad_reconstruction']['seconds']-constant_cost,
            caveat='Accounting counterfactual, not causal attribution; receipt mix and state size differ',
            quadratic_event_count_ratio=n*n,
            broad_ratio_divided_by_squared_event_count_ratio=data['B24_minus_B23']['broad_reconstruction_ratio']/(n*n)),
        limitations_additional=['Microbenchmarks use initial/final snapshots, not historical receipt prefixes; do not multiply terminal cost by receipt count.',
            'to_dict and JSON serialization overlap hash_state; cumulative profile rows overlap each other.',
            'v1 profiles retained with noisy wall samples; v2 adds process CPU timing; no historical production function-share estimate.'])
    output=ROOT/'docs/performance/b24-runtime-diagnosis-measurements.json'
    encoded=json.dumps(data,ensure_ascii=False,indent=2)+'\n'
    if output.exists() and output.read_text()!=encoded:raise ValueError('Preserve previous diagnosis JSON; use a new version')
    if not output.exists():output.write_text(encoded)
    print('Verified production sources and component profiles;',output)

if __name__=='__main__':run()
