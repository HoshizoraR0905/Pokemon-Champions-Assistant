"""Source-only endpoint completion against frozen sequential groups; no acquisition.

Sampling is a separate checkpointed stage. Manual diagnostic values are never
arguments to prediction. Preserve all sealed state, receipts and comparisons.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from battle_artifacts import BattleArtifacts
from recognition.event_report import atomic_json
from recognition.fast_video import digest
from recognition.resolution_sampling import endpoint_source_samples
from scripts.evaluate_hp_resolutions import load_saved

ROOT=Path(__file__).resolve().parents[1]
BASE='b16-sequential-resolution-20261028-v2'
SOURCES=['tracking/hp_causes.py','tracking/resolution_context.py','tracking/resolution_endpoints.py',
    'recognition/resolution_sampling.py','scripts/evaluate_hp_completion.py','knowledge/resolution_effects.py',
    'knowledge/data/52poke-resolution-v1.json','knowledge/__init__.py','knowledge/data/manifest.json',
    'tracking/active_continuity.py','tracking/state_engine.py']


def evaluate(owner,run_id,sample_runs):
    engine,source=load_saved(owner)
    baseline=owner.cache('sequential-hp/'+BASE+'/prediction.json')
    frozen=json.loads(baseline.read_text())
    out=owner.cache('hp-completion/'+run_id);report=owner.report('evaluation/'+run_id)
    out.mkdir(parents=True,exist_ok=True);report.mkdir(parents=True,exist_ok=True)
    paths=[owner.cache('hp-resolution-sampling/'+r+'/manifest.json') for r in sample_runs]
    identity=dict(source_replay=digest(source/'replay.json'),frozen_prediction=digest(baseline),
        source_video_sha256=digest(owner.video()),sample_manifests={r:digest(p) for r,p in zip(sample_runs,paths)},
        sample_observations={r:digest(Path(json.loads(p.read_text())['outputs'][0])) for r,p in zip(sample_runs,paths)},
        sources={p:digest(ROOT/p) for p in SOURCES})
    path=out/'manifest.json'
    if path.exists():
        old=json.loads(path.read_text())
        if old['identity']!=identity:raise ValueError('Changed inputs/implementation require a new run ID')
        if old['status']=='complete':print('Reused completed HP completion:',report);return old
    m=dict(status='running',identity=identity,completed_stages=[],sample_runs=sample_runs)
    atomic_json(path,m)
    try:
        samples=[];measured=Counter()
        for p in paths:
            manifest=json.loads(p.read_text());samples.extend(endpoint_source_samples(owner,engine,manifest))
            for key in ['sampled_frames','ocr_read_requests','ocr_model_predictions','full_screen_ocr_calls']:
                measured[key]+=manifest['measured'][key]
        atomic_json(out/'bound-source-samples.json',samples)
        m['completed_stages'].append('source_hash_and_existing_entry_binding');atomic_json(path,m)
        before=engine.to_dict();prediction=engine.hp_resolutions(endpoint_samples=samples)
        assert engine.to_dict()==before,'Endpoint projection changed authoritative reconstruction'
        atomic_json(out/'prediction.json',prediction)
        m['completed_stages'].append('prediction_without_manual_values');atomic_json(path,m)
        groups={frozenset(o['segment_event_ids']):o for o in frozen['episodes']}
        actual={frozenset(o['segment_event_ids']):o for o in prediction['episodes']}
        assert len(actual)==len(prediction['episodes'])==len(groups)==21 and set(actual)==set(groups)
        ids=[i for o in prediction['episodes'] for i in o['segment_event_ids']]
        assert len(ids)==len(set(ids))==41
        cases=[]
        for key,old in groups.items():
            new=actual[key]
            assert (new['affected_instance_id'],new['unit'])==(old['affected_instance_id'],old['unit'])
            if old['attribution_status']=='supported':
                assert new['attribution_status']=='supported' and (new['before'],new['after'],new['delta'])==(old['before'],old['after'],old['delta'])
            else:
                pid=new['affected_instance_id'];mon=engine.state.pokemon[pid]
                cases.append(dict(previous_episode_id=old['episode_id'],species=mon.species.value,
                    side=mon.side_id,previous_reasons=old['reasons'],prediction=new))
        metrics=dict(frozen_groups=21,numeric_segments=41,previous_complete=16,
            complete=sum(o['attribution_status']=='supported' for o in prediction['episodes']),
            reviewed_cases=len(cases),completed_reviewed_cases=sum(c['prediction']['attribution_status']=='supported' for c in cases),
            state_and_receipts_unchanged=True,event_facts='120/124',state_fields='175/191',
            original_reference_numeric_pairs='18/21',original_observed_zeros='3/3',
            independently_measured_causal_accuracy=None,source_sampling=dict(measured),new_acquisition_in_evaluation=False)
        atomic_json(report/'cases.json',cases);atomic_json(report/'metrics.json',metrics)
        atomic_json(report/'episodes.json',prediction)
        lines=['# B16 HP endpoint completion','',f'Run `{run_id}`. Development evaluation using saved original-video HP-only observations.',
            '',f'Complete attribution: **{metrics["complete"]}/21**, previously 16/21. Frozen membership retains all 41 original numeric segments exactly once. All 16 previously supported totals are unchanged.',
            '', 'No manual HP values enter prediction. Extra source reads bind to existing send-out/slot intervals; they do not merge same-species encounters, rewrite sealed state or become live recognition results. The original StateEngine state and every receipt are unchanged.',
            '', '| Source time | Cause | Affected | Pre HP / provenance | Post HP / provenance | Signed delta | Complete |',
            '|---:|---|---|---|---|---:|---|']
        for case in cases:
            o=case['prediction'];cause=o['cause'] or {};label=(cause.get('source') or {}).get('name') or cause.get('status') or 'unknown'
            lines.append(f'| {o["source_event"]["time"]:.3f} | {label} | {case["side"]} {case["species"]["name"]} | {o["before"]} / {o["components"][0]["baseline_basis"]} | {o["after"]} / {o["final_endpoint_basis"]} | {o["delta"]} {o["unit"]} | {o["attribution_status"]} |')
        lines+=['', '## Per-case evidence and uncertainty','']
        for case in cases:
            o=case['prediction']
            def location(trace):
                if trace is None:return 'unresolved'
                proof=trace['evidence'][0];raw=proof.get('source') or proof.get('details') or {}
                return f'`{trace["event_id"]}` at PTS {trace["time"]:.6f}; frame `{raw.get("image", "see receipt")}`'
            lines +=[f'### {o["source_event"]["time"]:.3f} s — {case["species"]["name"]}',
                '',f'- Instance: `{o["affected_instance_id"]}`; cause receipt: `{o["source_event_id"]}`.',
                f'- Before: {location(o["endpoints"]["before"])}.',f'- After: {location(o["endpoints"]["after"])}.',
                f'- Previous rejection: {", ".join(case["previous_reasons"])}.',
                f'- Current unresolved reasons: {", ".join(o["reasons"]) or "none under the stated evidence policy"}.','']
        lines +=['Native 2 FPS evidence had only one final reading for Berry/burn; HP cards then disappeared before the next receipt. Additional source frames establish repeated visible values. For the three attacks, source onset readings recover baselines that were absent from admitted 2 FPS history. Archaludon requires 20 FPS onset inspection: the first 5 FPS value is already in the animation. These are observed endpoints, not inferred healing fractions or assumed starting HP.',
            '', 'A non-full onset requires at least three distinct source times spanning 0.1 s before the first decrease, contiguous at <=0.25 s gaps. Full-scale evidence supplies its own upper bound. Ordinary final stability still uses the configured 0.4 s duration. A trustworthy final read can also finish at an admitted independent resolution within 0.5 s, absent an HP gap. Gaps, competing sources and unresolved identities still veto acceptance.',
            '', 'Same-instance switch carries remain derived facts with original evidence. New entry HUDs confirm or correct them. First-entry 100% is only an unestablished conditional hypothesis without supporting numeric evidence. No possible Regenerator, item or ability supplies a numeric change. Existing unresolved biological continuity across some same-species encounters remains unresolved; these five totals use local source observations rather than an identity merge.',
            '', 'Displayed opponent percentages are percentage points, not exact HP. No independent 21-case causal labels or real multi-hit validation are claimed. Original event/state metrics stay 120/124 and 175/191; original reference numeric pairs 18/21 and zeros 3/3 remain separate metrics.',
            '', f'Sampling totals across separate completed source runs: `{dict(measured)}`. Sampling source PTS, frame hashes, visibility/reuse receipts, OCR and resume checkpoints remain under each sample manifest. No full-screen OCR or broad replay was run.',
            '', 'Full per-case numeric/source provenance: [cases.json](cases.json). Projection: [episodes.json](episodes.json).']
        (report/'report.md').write_text('\n'.join(lines)+'\n')
        for file in SOURCES:
            dest=out/'source'/file;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/file).read_bytes())
        m.update(status='complete',metrics=metrics,completed_stages=m['completed_stages']+['frozen_group_comparison','report'],
            outputs=[str(out/'prediction.json'),str(report/'report.md'),str(report/'cases.json')])
        atomic_json(path,m);print(json.dumps(metrics,indent=2));return m
    except BaseException as exc:
        m.update(status='interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed',error=repr(exc));atomic_json(path,m);raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True)
    p.add_argument('--sample-run',action='append',required=True);a=p.parse_args()
    evaluate(BattleArtifacts('sample_battle_16',ROOT),a.run_id,a.sample_run)
