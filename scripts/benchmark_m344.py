"""M3.4.4: third-hit incremental call from sealed two-hit joint survivors."""
import argparse
import json
from pathlib import Path
import resource
import sys
from time import perf_counter,process_time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from damage.joint import filter_joint,project_joint,concrete_ids
from battle_evidence.speed_replay_offline import atomic,file_hash


def benchmark(profile,output):
    start=perf_counter();pointer=json.loads((ROOT/f'.cache/battles/sample_battle_12/m342-offensive/latest-{profile}.json').read_text());path=Path(pointer['path'])
    manifest=json.loads(path.with_name('manifest.json').read_text());assert manifest['status']=='complete'
    # Read tiny admitted inputs and the second-hit checkpoint, not replay JSON
    # or source images. Seal/checkpoint hashes are verified before the clock.
    observations=json.loads(path.with_name('observations.json').read_text())
    assert len(observations)==3 and observations[-1]['damage']==46
    assert file_hash(path.with_name('observations.json'))==manifest['outputs']['observations.json']
    checkpoint=next(v for v in manifest['checkpoints'].values() if v['layer']=='full' and v['observation']==observations[1]['id'])
    prior_path=Path(checkpoint['path']);assert file_hash(prior_path)==checkpoint['sha256']
    prior=json.loads(prior_path.read_text());loading=perf_counter()-start
    init=perf_counter()
    for stat in ('attack','special_attack'):project_joint(prior['configurations'],stat)
    initialization=perf_counter()-init;memo={}
    cpu=process_time();wall=perf_counter();rss_before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result=filter_joint([],observations,prior=prior,evaluation_cache=memo)
    wall=perf_counter()-wall;cpu=process_time()-cpu;peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    last=result['updates'][-1]
    assert concrete_ids(result['configurations'])<=concrete_ids(prior['configurations'])
    # A second explicit warm-output-cache diagnostic is measured separately. It
    # is never reported as latency of first admission of the third observation.
    warm=perf_counter();repeat=filter_joint([],observations,prior=prior,evaluation_cache=memo);warm=perf_counter()-warm
    assert concrete_ids(repeat['configurations'])==concrete_ids(result['configurations'])
    receipt=dict(milestone='M3.4.4',profile=profile,package=str(path),checkpoint=str(prior_path),checkpoint_sha256=checkpoint['sha256'],
        observations_sha256=file_hash(path.with_name('observations.json')),real_third_hit_admitted=True,source_independent_synthetic=False,
        checkpoint_input_load_seconds=loading,prior_projection_cache_initialization_seconds=initialization,
        third_hit_api_wall_seconds=wall,third_hit_api_cpu_seconds=cpu,third_hit_filter_seconds=last['incremental_seconds'],
        configuration_validation_copy_seconds=wall-last['incremental_seconds'],filter_loop_seconds=last['filter_loop_seconds'],projection_seconds=last['projection_seconds'],
        peak_rss_bytes=peak,rss_high_water_before_bytes=rss_before,forward_evaluations=last['forward_evaluations'],forward_cache_hits=last['cache_hits'],outcome_cache_hits=last['outcome_cache_hits'],
        prior_hit_local_timings=[u['incremental_seconds'] for u in prior['updates']],
        warm_output_cache_diagnostic=dict(wall_seconds=warm,forward_evaluations=repeat['updates'][-1]['forward_evaluations'],cache_hits=repeat['updates'][-1]['cache_hits']),
        before={s:project_joint(prior['configurations'],s) for s in ('attack','special_attack')},
        after={s:project_joint(result['configurations'],s) for s in ('attack','special_attack')},
        third_numerical_exclusions=len(last['numerical_excluded_ids']),third_item_evidence_exclusions=len(last['item_evidence_excluded_ids']),
        unresolved_classes=last['unresolved_after']['configuration_classes'],package_metrics=manifest['metrics'],
        note='Primary third-hit API clock excludes all input/image/video/OCR/browser loading and prior-cache initialization. New third-hit output cache is initially empty. Projection/result assembly included. Warm repeat is a separate diagnostic.')
    # IDs can be restored from the sealed checkpoints; compact summaries suffice.
    for group in ('before','after'):
        for v in receipt[group].values():v.pop('ids',None)
    atomic(output,receipt);print(json.dumps({k:receipt[k] for k in ('profile','third_hit_api_wall_seconds','third_hit_api_cpu_seconds','forward_evaluations','forward_cache_hits','peak_rss_bytes','unresolved_classes')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',choices=['practical','comprehensive'],required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();benchmark(a.profile,a.output)
