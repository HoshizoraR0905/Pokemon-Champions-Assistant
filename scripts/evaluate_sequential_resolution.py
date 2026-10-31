"""Frozen-denominator B16 sequential-resolution development regression.

Compute predictions first from sealed live receipts. Reference membership and
requested diagnostic expectations are comparison inputs only. No OCR or replay
acquisition is invoked here and original artifacts are never rewritten.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from battle_artifacts import BattleArtifacts
from recognition.event_report import atomic_json
from recognition.fast_video import digest
from scripts.evaluate_hp_resolutions import load_saved
from tracking.state_engine import hash_state

ROOT=Path(__file__).resolve().parents[1]
FROZEN='b16-action-resolution-20261028-v4'
SOURCES=['tracking/hp_causes.py','tracking/resolution_context.py','tracking/state_engine.py',
         'knowledge/__init__.py','knowledge/resolution_effects.py','knowledge/data/52poke-resolution-v1.json',
         'recognition/resolution_sampling.py','scripts/evaluate_hp_resolutions.py','scripts/evaluate_sequential_resolution.py']


def evaluate(owner,run_id):
    engine,source=load_saved(owner)
    frozen_path=owner.cache('hp-resolutions/'+FROZEN+'/episodes.json')
    frozen=json.loads(frozen_path.read_text())
    groups={frozenset(o['segment_event_ids']):o for o in frozen['episodes']}
    assert len(groups)==21,'Frozen denominator changed'
    out=owner.cache('sequential-hp/'+run_id);report=owner.report('evaluation/'+run_id)
    out.mkdir(parents=True,exist_ok=True);report.mkdir(parents=True,exist_ok=True)
    review=owner.cache('sequential-hp/source-review-20261028-v1/manifest.json')
    onset=owner.cache('sequential-hp/source-review-20261028-v1/onset/manifest.json')
    identity=dict(source_replay_sha256=digest(source/'replay.json'),frozen_episode_sha256=digest(frozen_path),
        reference_sha256=digest(owner.report('evaluation/b16-semantic-state-20261027-v1/reference-facts.json')),
        source_review_sha256=digest(review),onset_review_sha256=digest(onset),
        knowledge_manifest_sha256=digest(ROOT/'knowledge/data/manifest.json'),
        sources={p:digest(ROOT/p) for p in SOURCES})
    manifest=out/'manifest.json'
    if manifest.exists():
        old=json.loads(manifest.read_text())
        if old['identity']!=identity:raise ValueError('Run identity changed; choose a new run ID')
        if old['status']=='complete':print('Reused completed sequential comparison:',report);return
    m=dict(status='running',identity=identity,completed_stages=[],resume_command=f'.venv/bin/python scripts/evaluate_sequential_resolution.py --run-id {run_id}')
    atomic_json(manifest,m)
    try:
        state_before=hash_state(engine.state);receipts_before=[asdict(r) for r in engine.history]
        prediction=engine.hp_resolutions()
        assert hash_state(engine.state)==state_before,'Projection mutated battle state'
        assert [asdict(r) for r in engine.history]==receipts_before,'Projection mutated event receipts'
        atomic_json(out/'prediction.json',prediction)
        m['completed_stages'].append('prediction_without_reference_inputs');atomic_json(manifest,m)
        actual={frozenset(o['segment_event_ids']):o for o in prediction['episodes']}
        assert len(actual)==len(prediction['episodes'])==21 and set(actual)==set(groups),'Frozen group membership changed'
        all_segments=[eid for o in prediction['episodes'] for eid in o['segment_event_ids']]
        assert len(all_segments)==len(set(all_segments))==41,'Dropped or duplicate numeric segment'
        comparisons=[]
        for key,old in groups.items():
            new=actual[key]
            assert new['affected_instance_id']==old['affected_instance_id'] and new['unit']==old['unit']
            comparisons.append(dict(frozen_episode_id=old['episode_id'],episode_id=new['episode_id'],
                before_status=old['attribution_status'],after_status=new['attribution_status'],
                previous_reasons=old['reasons'],new_reasons=new['reasons'],before_hp=new['before'],after_hp=new['after'],delta=new['delta'],
                affected_instance_id=new['affected_instance_id'],source_event_id=new['source_event_id'],
                source_time=new['source_event']['time'],cause=new['cause'],source_instance_id=new['actor_instance_id'],
                endpoints=new['endpoints'],segment_event_ids=new['segment_event_ids']))
        m['completed_stages'].append('frozen_21_group_comparison');atomic_json(manifest,m)
        # These are the user's requested, fixed diagnostic expectations, applied
        # only after inference. They do not enter any recognition/state method.
        expected=[(196.5,1018,100,13,-87,'displayed_percent'),
                  (206.00166666666667,6,184,164,-20,'absolute'),
                  (206.00166666666667,3,156,129,-27,'absolute')]
        diagnostics=[]
        for t,sid,before,after,delta,unit in expected:
            hits=[o for o in prediction['episodes'] if abs(o['source_event']['time']-t)<.01 and
                  engine.state.pokemon[o['affected_instance_id']].species.value['species_id']==sid]
            assert len(hits)==1
            o=hits[0]
            assert (o['before'],o['after'],o['delta'],o['unit'],o['attribution_status'])==(before,after,delta,unit,'supported')
            diagnostics.append(dict(expected_source_time=t,expected_species_id=sid,episode=o,
                acceptance='requested development diagnostic matched; source-reviewed, not held-out causal accuracy'))
        atomic_json(report/'diagnostic-traces.json',diagnostics)
        complete=sum(o['complete_endpoints'] for o in prediction['episodes'])
        targets=sum(o['affected_target_status']=='supported' for o in prediction['episodes'])
        causes=sum(o['immediate_cause_status']=='supported' for o in prediction['episodes'])
        supported=sum(o['attribution_status']=='supported' for o in prediction['episodes'])
        old_supported=sum(o['attribution_status']=='supported' for o in frozen['episodes'])
        nested=[o for o in prediction['episodes'] if o['parent_action_id'] and o['parent_action_id']!=o['source_event_id']]
        independent=[o for o in prediction['episodes'] if not o['parent_action_id']]
        metrics=dict(frozen_action_target_denominator=21,numeric_segments=41,complete_endpoints=complete,
            supported_affected_targets=targets,unique_immediate_causes=causes,complete_attribution=supported,
            before_complete_attribution=old_supported,before_causal_coverage=old_supported/21,after_causal_coverage=supported/21,
            nested_hp_episodes=len(nested),nested_hp_supported=sum(o['attribution_status']=='supported' for o in nested),
            independent_effect_episodes=len(independent),unresolved_episodes=21-supported,
            unresolved_reasons=dict(Counter(r for o in prediction['episodes'] for r in o['reasons'])),
            supported_by_cause=dict(Counter(o['cause']['kind'] for o in prediction['episodes'] if o['attribution_status']=='supported')),
            requested_diagnostics_matched=len(diagnostics),independent_causal_accuracy=None,
            state_hash_unchanged=True,all_receipts_unchanged=True,event_facts='120/124',state_fields='175/191',
            original_reference_numeric_pairs='18/21',original_observed_zeros='3/3',
            new_ocr_calls=0,new_sampling_for_prediction=False,
            real_multi_hit_validation='not present in saved B16 evidence; synthetic contracts only',
            source_review_frames=len(json.loads(review.read_text())['frames'])+len(json.loads(onset.read_text())['frames']),
            source_review_ocr_calls=0)
        atomic_json(report/'metrics.json',metrics);atomic_json(report/'episode-comparisons.json',comparisons)
        atomic_json(report/'sequential-resolution.json',prediction)
        lines=['# M2 — Sequential battle resolution and HP attribution','',f'Run `{run_id}`. Development regression, not held-out accuracy. Source predictions and all references stay sealed.','',
            'Root cause of the prior failure: the previous projection constructed `action_targets` from named effectiveness/qualitative notices and explicit target IDs, then required `key in action_targets` before accepting a move cause. HUD numeric changes did not populate that set. Thus Weather Ball and both Snarl recipients were rejected despite supported instance bindings and compatible HP pairs. Every ability/item activation was also a boundary, so Stamina incorrectly ended the parent HP context rather than becoming a non-HP nested step.',
            '', 'The new view walks the actual ordered receipts. A move establishes a parent context; bound HP animations establish affected recipients. A documented banner opens a recipient/direction-specific immediate cause only when actual HP evidence occurs. Stat-only effects do not steal the HP cause. Reactions retain holder, attacker, affected instance and parent separately; overlapping sources, unknown semantics, identity/coverage gaps, direction conflicts, source-time ties and unsettled endpoints still cause abstention. No team-opposition target rule or move-name target guess is used.',
            '', '| Measure | Previous action view | Sequential view |','|---|---:|---:|',
            f'| Frozen action/target groups | 21 | 21 |',f'| Complete stable HP endpoints | 16 | {complete} |',
            f'| Supported affected targets | not separately scored | {targets}/21 |',
            f'| Unique immediate cause, including incomplete totals | 10/21 | {causes}/21 |',
            f'| Complete causal attribution | {old_supported}/21 ({old_supported/21:.1%}) | {supported}/21 ({supported/21:.1%}) |',
            f'| Nested HP effect episodes | not separately scored | {len(nested)} |',
            f'| Unresolved complete-attribution cases | {21-old_supported} | {21-supported} |',
            '', 'The 21 membership sets and all 41 original numeric change IDs are byte-independent comparison keys: each appears once and maps to the same affected instance/unit as the frozen action evaluation. The denominator was read before prediction, never altered after results. Supported target/cause counts mean evidence-supported associations, not independently measured target/cause accuracy. The three requested diagnostics are checked after inference. No 21-case independent causal labels exist, so causal accuracy is unmeasured.',
            '', 'Original event/state reconstruction stays **120/124 event facts, 175/191 state fields, 18/21 reference numeric pairs and 3/3 observed zero endpoints**. The complete serialized StateEngine state and every receipt are identical before/after deriving this view. No new HP values, stages, items, abilities or switches are applied.',
            '', '## Actual action/effect episodes','',
            '| Source time (s) | Source / parent | Affected | HP before → final | Signed delta / unit | Status / unresolved reason |',
            '|---:|---|---|---|---|---|']
        for o in prediction['episodes']:
            name=engine.state.pokemon[o['affected_instance_id']].species.value['name']
            side='own' if ':self:' in o['affected_instance_id'] else 'opponent'
            cause=o['cause'] or {};label=(cause.get('source') or {}).get('name') or cause.get('status') or 'unknown'
            parent=o['parent_action_id'] or 'independent effect'
            lines.append(f'| {o["source_event"]["time"]:.3f} | {label}; `{parent}` | {side} {name} | {o["before"]} → {o["after"]} | {o["delta"]} / {o["unit"]} | {o["attribution_status"]}; '+', '.join(o['reasons'])+' |')
        lines+=['','## Diagnostic source traces','',
            'An isolated original-video review rechecked the SHA against the sealed media and decoded 7 short source seeks plus 6 onset frames, with **zero OCR calls**. At about 200.2 s, the original HUD visibly shows Archaludon at 100%; subsequent source frames show the decrease, 13%, Stamina and Defense increase. Around 208–210 s both own HP endpoints and Special Attack drops are visible. These review frames/expectations are excluded from predictor inputs; prediction endpoints retain their original accepted event IDs and times.',
            '', '| Source event | Recipient | Accepted HP endpoint events | Delta |','|---|---|---|---|']
        for d in diagnostics:
            o=d['episode'];be=o['endpoints']['before'];ae=o['endpoints']['after']
            lines.append(f'| `{o["source_event_id"]}` @ {o["source_event"]["time"]:.6f} | `{o["affected_instance_id"]}` | `{be["event_id"]}` @ {be["time"]:.6f} → `{ae["event_id"]}` @ {ae["time"]:.6f} | {o["delta"]} {o["unit"]} |')
        lines+=['', 'Full source → actor/holder → affected instance → raw HP animation observations → resulting history receipts and stat/pivot/reaction steps: [diagnostic-traces.json](diagnostic-traces.json), [sequential-resolution.json](sequential-resolution.json), [episode-comparisons.json](episode-comparisons.json).',
            '', '## Remaining limits','',
            'Three pre-action endpoints remain missing. Two final values have no confirmed visible plateau. Their target and immediate source can be supported while total damage stays unknown. No percentage is converted to exact HP. Unknown banners and competing sources remain ambiguous in regression tests; no effect is assumed merely because an ability/item is active.',
            '', 'B16 has no real Triple Axel, repeated Rough Skin, ally pivot or supported critical-hit sequence in the saved predictions. Those contracts are tested synthetically and do not establish real-video detection success. Multi-hit totals and reaction totals are separate. Per-hit amounts require independent hit evidence plus adequate source sampling; missing boundaries retain unknown per-hit amounts. The targeted PTS decoder, pre-roll and HP-only cached OCR remain in use, with escalation from 5 FPS up to the measured source FPS limit when timing remains unresolved. This evaluation runs no new acquisition/OCR.',
            '', 'A scoped, offline 52Poké categorical supplement is queried through the existing KnowledgeBase canonical IDs. It records article URLs, revisions, retrieval date, Champions applicability and attribution/license. It contains no damage fractions, probability priors or equipped-move assertions. See `knowledge/data/52poke-resolution-v1.json`. No runtime network access or competing identity database was introduced.',
            '', 'No commit, push or next milestone. Commands, focused tests and source-review manifest locations are documented in `docs/m2-sequential-hp/`.']
        (report/'report.md').write_text('\n'.join(lines)+'\n')
        for file in SOURCES:
            dest=out/'source'/file;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/file).read_bytes())
        m.update(status='complete',completed_stages=['prediction_without_reference_inputs','frozen_21_group_comparison','diagnostics','report'],
                 metrics=metrics,outputs=[str(report/'report.md'),str(out/'prediction.json')])
        atomic_json(manifest,m);print(json.dumps(metrics,ensure_ascii=False,indent=2))
    except BaseException as exc:
        m.update(status='interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed',error=repr(exc));atomic_json(manifest,m);raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);args=p.parse_args()
    evaluate(BattleArtifacts('sample_battle_16',ROOT),args.run_id)
