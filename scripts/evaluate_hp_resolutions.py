"""Action-level B16 development evaluation and optional scoped source HP probe."""
import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from battle_artifacts import BattleArtifacts
from recognition.fast_video import digest
from recognition.event_report import atomic_json,verify_seal
from tracking.state_engine import StateEngine,EventRecord,hash_state
from tracking.battle_state import from_dict

ROOT=Path(__file__).resolve().parents[1]
BASE='b16-hp-attribution-20261028-v5'


def load_saved(owner):
    source=owner.cache('hp-attribution/'+BASE)
    manifest=json.loads((source/'manifest.json').read_text())
    if manifest['status']!='complete':raise ValueError('Required saved reconstruction is incomplete')
    verify_seal(owner.cache('event-driven/b16-banner-hp-20261028-v6'))
    data=json.loads((source/'replay.json').read_text())
    # Read-only projection of existing admitted receipts. Do not run OCR or
    # regenerate reconstruction stages simply to attach a derived view.
    engine=StateEngine(from_dict(data['initial_state']))
    engine.state=from_dict(data['state']);engine.history=[EventRecord(**r) for r in data['history']]
    return engine,source


def evaluate(owner,run_id,*,fps=5.,probe_run_id=None):
    from recognition.resolution_sampling import dense_plans
    engine,source=load_saved(owner)
    out=owner.cache('hp-resolutions/'+run_id);report=owner.report('evaluation/'+run_id)
    identity=dict(battle_id=owner.battle_id,source_replay_sha256=digest(source/'replay.json'),
        sources={p:digest(ROOT/p) for p in ['tracking/hp_causes.py','tracking/state_engine.py',
            'recognition/resolution_sampling.py','scripts/evaluate_hp_resolutions.py','battle_events/parser.py']},sample_fps=fps,
        knowledge_manifest=digest(ROOT/'knowledge/data/manifest.json'),
        damage_reference_manifest=digest(ROOT/'damage/data/manifest.json'),
        reference_sha256=digest(owner.report('evaluation/b16-semantic-state-20261027-v1/reference-facts.json')))
    probe=None
    if probe_run_id:
        probe_path=owner.cache('hp-resolution-sampling/'+probe_run_id+'/manifest.json')
        probe=json.loads(probe_path.read_text())
        if probe['status']!='complete':raise ValueError('Probe is incomplete')
        identity['probe_manifest_sha256']=digest(probe_path)
        # A planning-only edit does not invalidate a successfully measured
        # decoding/OCR stage. Verify the exact sampling function is unchanged.
        import ast
        saved=probe_path.parent/'source/recognition/resolution_sampling.py'
        if saved.exists():
            assert digest(saved)==probe['identity']['sources']['recognition/resolution_sampling.py']
            def sample_body(path):
                return ast.dump(next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='sample_window'),include_attributes=False)
            assert sample_body(saved)==sample_body(ROOT/'recognition/resolution_sampling.py')
        else:assert digest(ROOT/'recognition/resolution_sampling.py')==probe['identity']['sources']['recognition/resolution_sampling.py']
    out.mkdir(parents=True,exist_ok=True);report.mkdir(parents=True,exist_ok=True)
    manifest=out/'manifest.json'
    if manifest.exists():
        old=json.loads(manifest.read_text())
        if old['identity']!=identity:raise ValueError('Identity mismatch: select a new run ID')
        if old['status']=='complete':print('Reused complete action projection:',report);return
    m=dict(status='running',identity=identity,completed_stages=[],resume_command=f'.venv/bin/python scripts/evaluate_hp_resolutions.py evaluate --run-id {run_id}')
    atomic_json(manifest,m)
    try:
        before_hash=hash_state(engine.state);before_receipts=[asdict(r) for r in engine.history]
        result=engine.hp_resolutions()
        assert hash_state(engine.state)==before_hash
        assert [asdict(r) for r in engine.history]==before_receipts
        prior={o['evidence']['event_id']:o for p in engine.state.pokemon.values() for o in p.hp.observations if o.get('delta')}
        covered=[eid for o in result['episodes'] for eid in o['segment_event_ids']]
        assert len(covered)==len(set(covered)) and set(covered)==set(prior), 'Numeric change membership changed'
        atomic_json(out/'episodes.json',result)
        m['completed_stages'].append('action_projection');atomic_json(manifest,m)
        plans=dense_plans(engine,sample_fps=fps);atomic_json(out/'dense-inspection-plan.json',plans)
        episodes=result['episodes'];old_full=[]
        for o in episodes:
            # Same action/target denominator, same stability and completeness.
            # A legacy partial segment label does not establish a whole episode.
            segments=[prior[eid] for eid in o['segment_event_ids']]
            if (o['complete_endpoints'] and all(s.get('attribution_status')=='supported' and
                o['source_event_id'] in s.get('cause_event_ids',[]) for s in segments)):
                old_full.append(o['episode_id'])
        supported=[o for o in episodes if o['attribution_status']=='supported']
        complete=[o for o in episodes if o['complete_endpoints']]
        reasons=Counter(r for o in episodes for r in o['reasons'])
        old_source=(source/'source/tracking/hp_causes.py').read_text()
        legacy_unchanged=(ROOT/'tracking/hp_causes.py').read_text().startswith(old_source)
        assert legacy_unchanged, 'Legacy transition/enrichment changed: scoped full replay validation required'
        metrics=dict(sampling_probe=probe['measured'] if probe else None,numeric_segments=len(prior),action_target_episodes=len(episodes),move_executions=len(result['actions']),
            complete_endpoints=len(complete),known_causes=sum(o['cause'] is not None for o in episodes),
            supported_complete_episodes=len(supported),unresolved_episodes=len(episodes)-len(supported),
            unresolved_boundary_episodes=sum(any(r!='affected_target_or_cause_unresolved' for r in o['reasons']) for o in episodes),
            before_episodes_touched_by_supported_segments=sum(any(prior[eid].get('attribution_status')=='supported' for eid in o['segment_event_ids']) for o in episodes),
            before_complete_attributed_episodes=len(old_full),before_action_coverage=len(old_full)/len(episodes),
            after_action_coverage=len(supported)/len(episodes),complete_endpoint_causal_coverage=len(supported)/len(complete),
            legacy_supported_segments=sum(o.get('attribution_status')=='supported' for o in prior.values()),
            supported_by_category=dict(Counter((o['cause']['kind'] if o['cause'] else 'unknown') for o in supported)),
            unresolved_reasons=dict(reasons),multi_hit_inspection_candidates=len(plans),
            critical_hit_episodes=sum(o['critical_hit'] is True for o in episodes),
            multi_hit_detection_success_on_real_video=None,causal_correctness=None,
            state_hash_unchanged=True,all_receipts_identical=True,legacy_enrichment_code_unchanged=legacy_unchanged,
            event_facts='120/124',state_fields='175/191',reference_endpoint_pairs='18/21',reference_observed_zeros='3/3')
        atomic_json(report/'metrics.json',metrics);atomic_json(report/'action-episodes.json',result)
        atomic_json(report/'dense-inspection-plan.json',plans)
        lines=['# M2 — Action-level HP resolution','',f'Run `{run_id}`. Read-only projection of sealed `{BASE}` receipts and HP history; no Battle Log labels enter predictions.','',
            f'**{len(prior)} adjacent changes → {len(episodes)} action/target episodes**, across {len(result["actions"])} move executions (including moves without observed damage). **{len(complete)} complete endpoint pairs**, **{metrics["known_causes"]} known causes**, **{len(supported)} complete supported causal episodes**. {len(episodes)-len(supported)} episodes remain unresolved.',
            '',f'Comparable action-level attribution coverage: **{len(old_full)}/{len(episodes)} ({metrics["before_action_coverage"]:.1%}) → {len(supported)}/{len(episodes)} ({metrics["after_action_coverage"]:.1%})**. The denominator is the same 21 observed action/target groups, determined from saved live event boundaries before consulting any reference. The old count of 13/41 describes adjacent animation fragments and is not action coverage. Those labels touch 9 action/target groups, including partial episodes; they do not establish 9 complete action totals. The before numerator additionally requires all fragments in a complete stable episode to have the same supported legacy source. After coverage among complete endpoint episodes is {len(supported)}/{len(complete)} ({metrics["complete_endpoint_causal_coverage"]:.1%}).',
            '', 'Totals use the last reliable pre-action HP and the final observed plateau before the next independent action/effect. Critical, effectiveness and hit-count messages stay in their action. HP observation gaps limit hit resolution; an event/identity coverage gap still vetoes a causal total. A source announcement alone does not establish a target. Item activation alone does not prove healing. Missing pre-action HP yields a partial observation only, never an invented total. A single last HP read without a visible plateau or an observed zero followed by its faint is not a settled endpoint.',
            '', 'Derived projection leaves every serialized state field, history receipt and original endpoint unchanged. Original metrics: **120/124 event facts; 175/191 state fields; 18/21 reference numeric pairs; 3/3 observed HUD zeros**. The stricter stable action boundary count is a separate measure. No causal accuracy is reported without independently verified cause labels.',
            '', '| Source time (s) | Affected instance | Before → final | Unit | Total signed delta | Cause / status | Boundary issues |',
            '|---:|---|---|---|---:|---|---|']
        for o in episodes:
            name=engine.state.pokemon[o['affected_instance_id']].species.value['name']
            side='own' if ':self:' in o['affected_instance_id'] else 'opponent'
            cause=o['cause'] or {};label=(cause.get('source') or {}).get('name') or cause.get('status') or 'unknown'
            lines.append(f'| {o["source_event"]["time"]:.3f} | {side} {name} | {o["before"]} → {o["after"]} | {o["unit"]} | {o["delta"]} | {label}; {o["attribution_status"]} | '+', '.join(o['reasons'])+' |')
        lines+=['','Full actor/target IDs, source and endpoint evidence, original segment membership, final plateau receipts, critical/count notices, and boundary receipts: [action-episodes.json](action-episodes.json).',
            '',f'B16 has **{len(plans)}** reference-capable or independently announced multi-hit inspection candidates and **{metrics["critical_hit_episodes"]}** supported critical episodes in the saved predictions. No real-video multi-hit success is claimed for B16. Pinned simulator `multihit` facts may trigger inspection but retain their provisional Champions status. Targeted inspection starts at 3 FPS and tests 4 FPS only if necessary; per-hit deltas require observed stable plateaus and an independent matching count. Unresolved hits retain the aggregate action total.',
            '', 'High-rate source access uses a targeted original-video PTS second decoding pass, with configurable pre-roll from before the recognized action and the known pre-action endpoint. Ordinary acquisition remains 2 FPS. HP-only visibility/refresh/OCR reuse gates are unchanged; changing frame FPS does not invoke full-screen OCR. Per-frame PTS, hashes, frames sampled, raw frames decoded, ROI requests, model predictions, cache hits and partial checkpoints are recorded by the probe command.',
            '', 'Limitations: B16 does not validate multi-hit or critical-hit detection. Unknown move recipients, missing pre-action readings and two unresolved final plateaus remain; item healing sources need explicit effect evidence. Tests of spread/recoil/items/abilities/multi-hit validate contracts only. Next priorities are independently reviewed action/critical/hit labels and a real multi-hit recording; no further milestone is started.']
        if probe:
            pm=probe['measured'];trigger=probe['identity']['trigger']
            pre=sum(f['timestamp']<trigger for f in probe['frames']) if trigger is not None else None
            lines+=['',f'Actual scoped source probe `{probe_run_id}`: **{pm["sampled_frames"]} frames**, **{pm["frames_per_requested_second"]:.1f} sampled FPS**, {pm["ocr_read_requests"]} HP ROI read requests, **{pm["ocr_model_predictions"]} OCR model predictions**, **0 full-screen OCR calls**. Source showinfo counted {probe["counts"]["source_decoded_frames"]} frames before the sample filter; maximum sampled PTS gap {pm["max_pts_gap"]:.6f} s. {pre} frames precede the declared move-recognition trigger. The ordinary weather-ball probe is an acquisition/cost check, not multi-hit detection. Its HP samples remain separate observations and do not enter the 21-episode measurement or overwrite state.',
                    '',f'Probe manifest and per-frame receipts: `.cache/battles/sample_battle_16/hp-resolution-sampling/{probe_run_id}/`. The successfully measured sampling function is unchanged; a later admission check affects planning only. Reusable frames/OCR are preserved.']
        (report/'report.md').write_text('\n'.join(lines)+'\n')
        for name in identity['sources']:
            path=out/'source'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((ROOT/name).read_bytes())
        m.update(status='complete',completed_stages=['action_projection','sampling_plan','comparison','report'],metrics=metrics,outputs=[str(report/'report.md'),str(out/'episodes.json')])
        atomic_json(manifest,m);print(json.dumps(metrics,ensure_ascii=False,indent=2))
    except BaseException as exc:
        m.update(status='failed',error=repr(exc));atomic_json(manifest,m);raise


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['evaluate','probe','inspect']);p.add_argument('--run-id',required=True)
    p.add_argument('--fps',type=float,default=3.);p.add_argument('--max-fps',type=float,default=4.);p.add_argument('--start',type=float);p.add_argument('--end',type=float)
    p.add_argument('--probe-run-id');p.add_argument('--side',choices=['own','opponent']);p.add_argument('--slot',choices=['left','right']);p.add_argument('--trigger-time',type=float)
    a=p.parse_args();owner=BattleArtifacts('sample_battle_16',ROOT)
    if a.stage=='evaluate':evaluate(owner,a.run_id,fps=a.fps,probe_run_id=a.probe_run_id)
    elif a.stage=='inspect':
        from recognition.resolution_sampling import inspect_resolutions
        engine,_=load_saved(owner)
        result=inspect_resolutions(owner,a.run_id,engine,initial_fps=a.fps,maximum_fps=a.max_fps)
        print(json.dumps(dict(planned_windows=result['planned_windows'],completed=result['completed'])))
    else:
        if a.start is None or a.end is None:p.error('probe requires explicit --start and --end')
        from recognition.resolution_sampling import sample_window
        result=sample_window(owner,a.run_id,start=a.start,end=a.end,sample_fps=a.fps,side=a.side,slot=a.slot,trigger=a.trigger_time)
        print(json.dumps(result['measured'],indent=2))


if __name__=='__main__':main()
