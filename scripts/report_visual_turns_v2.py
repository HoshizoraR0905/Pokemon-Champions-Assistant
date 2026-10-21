"""Summarize existing v2 artifacts; never runs recognition or changes references."""
from pathlib import Path
from collections import Counter
import hashlib
import html
import json
import os
from speed_inference.offline import atomic_json

ROOT=Path(__file__).resolve().parents[1]


def main():
    os.chdir(ROOT);cache=ROOT/'.cache/m34-visual-v2'
    outputs=[json.loads(Path(p).read_text()) for p in json.loads((cache/'evaluation-index.json').read_text())]
    predictions=[json.loads(Path(p).read_text()) for p in json.loads((cache/'battle-index.json').read_text())]
    baseline=json.loads((cache/'preservation.json').read_text())
    changes=[n for n,h in baseline.items() if not Path(n).exists() or hashlib.sha256(Path(n).read_bytes()).hexdigest()!=h]
    allowed={'battle_evidence/visual.py','battle_evidence/visual_controls.py','battle_evidence/visual_offline.py'}
    if set(changes)-allowed:raise ValueError('Unexpected preservation changes: '+str(set(changes)-allowed))
    freeze=json.loads((cache/'reference-freeze.json').read_text())['references']
    if any(hashlib.sha256(Path(n).read_bytes()).hexdigest()!=h for n,h in freeze.items()):raise ValueError('Frozen reference changed')
    atomic_json(cache/'preservation-result.json',dict(baseline_files=len(baseline),changed=changes,unchanged=len(baseline)-len(changes),reference_freeze_unchanged=True))
    costs=[];sheets=[]
    for n in range(5,10):
        costs.extend(json.loads(p.read_text()) for p in Path(f'.cache/battles/sample_battle_{n}/m34-visual-v2').glob('*/manifest.json') if json.loads(p.read_text()).get('status')=='complete')
        sheets.extend(json.loads(p.read_text()) for p in Path(f'.cache/battles/sample_battle_{n}/m34-visual-review').glob('*/manifest.json'))
    pipeline_seconds=sum(c.get('metrics',{}).get('seconds',0) for c in costs)
    counter=Counter(c['status'] for o in outputs for c in o['counter_checks'])
    def phase_counts(version):return Counter(p['status'] for o in outputs for p in o['comparisons'][version]['phase_transition_comparisons'] if p['phase_type']=='resolution_start')
    totals={v:Counter() for v in ('v1','v2')}
    for o in outputs:
        for v in totals:totals[v].update(o['comparisons'][v]['counts'])
    statuses=Counter(s['status'] for p in predictions for s in p['visual']['segments'])
    report=ROOT/'reports/M3.4-visual-turn-v2-validation.md'
    def rel(path,base=report.parent):return os.path.relpath(Path(path).absolute(),base)
    page=['<!doctype html><meta charset="utf-8"><title>M3.4 v2 review</title>',
        '<style>body{background:#15191c;color:#eee;font:18px system-ui;max-width:1100px;margin:2em auto}a{color:#9cf}section{padding:1em;border:1px solid #678;margin:1em}table{border-collapse:collapse}td,th{padding:.5em;border:1px solid #678}</style>',
        '<h1>M3.4 v2 — human review pending</h1><p>References are agent-reviewed proposals, not independently human-verified ground truth. Command-entry interval matches do not validate resolution start/completion timing.</p>',
        '<p>Review the original MP4 and source frames, then use each page’s correction-note exporter or edit the separate proposal JSON. Exporting notes does not approve annotations.</p>']
    for o in outputs:
        b=o['battle_id'];reference=Path(o['reference']);chron=next(s for s in sheets if s['battle_id']==b and s['identity']['step']==5)
        page.append(f'<section><h2>{b}</h2><a href="{html.escape(rel(o["review_html"],cache))}">Review transitions, video and frames</a> · <a href="{html.escape(rel(reference,cache))}">Proposal JSON</a> · <a href="{html.escape(rel(chron["index"],cache))}">Chronological source sheets</a><p>v1: {o["comparisons"]["v1"]["counts"]}<br>v2: {o["comparisons"]["v2"]["counts"]}</p></section>')
    (cache/'review.html').write_text('\n'.join(page))
    lines=['# M3.4 visual reconstruction v2 — implementation and agent-reference comparison','',
        '**Human review required; turn-boundary reconstruction is not declared validated.** The detector no longer requires four visible HUD cards. Separately authored agent references cover 30 command phases and 25 subsequent command-entry boundaries across Battles 5–9. V2 matches all 25 command-entry intervals under the documented tolerance, but fine resolution timing remains incomplete.','',
        '[Open the review index]('+rel(cache/'review.html')+') · [v2 design and resume commands](../docs/visual-turns-v2.md)','',
        '## Evidence status and review process','',
        'The references are labeled `agent-reviewed`, with `human_approved: false`. They were authored before v2 implementation/comparison from chronological original-recording cached PNGs selected on a fixed five-second grid. Visually identified opening/resolution/tail windows received one-second source-frame refinements. The sampler did not read predicted boundaries, classifications, event ledgers or counters for selection. The agent had prior project context: this is separately authored source review, not blinded independent human annotation or continuous video playback.','',
        f'The review process generated 29 contact sheets: {sum(len(s["frames"]) for s in sheets)} source-frame reads, {len({f["image"] for s in sheets for f in s["frames"]})} unique frames. Observation hashes, source PTS/image references and reviewed image hashes are retained in the sheet manifests. References were frozen in `.cache/m34-visual-v2/reference-freeze.json` before prediction work; their hashes still match.','',
        'Each reference records opening/send-out completion; command entry; resolution start; resolution completion; next command entry; menus, possible replacements, terminal result, confidence and uncertain intervals. Resolution completion and next-command entry are separate fields. Many nonterminal transitions share the same broad sampling bracket and are not individually resolved within it. Terminal resolution completion and the WIN/result presentation have separate source intervals.','',
        'The local review pages link source before/after PNGs and the original MP4 and provide a correction-note exporter. No annotation is automatically approved or rewritten. The JSON files are curated review proposals in `reports/battles/<battle_id>/inputs/`; generated sheets, HTML, evaluations and full predictions stay in `.cache/`.','',
        '## v1 versus v2: subsequent command entries','',
        'Matching uses a chronological, one-to-one maximum match and a **1.6-second maximum gap between reference and predicted intervals**. Wide intervals cannot earn multiple matches. Opening anchors are evaluated separately. Uncertain reference boundaries do not become definite false positives/misses. Confirmed and incomplete predictions are counted separately. **Precision and recall are withheld** because no human has approved the references. These counts describe agreement with agent proposals.','',
        '| Battle | Agent reference returns | v1 matched / missed / unmatched | v2 matched / missed / unmatched | v2 confirmed / incomplete |','| --- | ---: | --- | --- | --- |']
    for o,p in zip(outputs,predictions):
        a=o['comparisons']['v1']['counts'];b=o['comparisons']['v2']['counts'];s=p['metrics']['segments']
        lines.append(f'| {o["battle_id"]} | {b["reference_boundaries"]} | {a["matched"]} / {a["missed"]} / {a["unmatched_predictions"]} | {b["matched"]} / {b["missed"]} / {b["unmatched_predictions"]} | {s.get("confirmed",0)} / {s.get("supported_but_incomplete",0)} |')
    lines+=['',f'Totals: v1 {totals["v1"]["matched"]} matches, {totals["v1"]["missed"]} misses and {totals["v1"]["unmatched_predictions"]} unmatched endpoint; v2 {totals["v2"]["matched"]} matches, zero misses and zero unmatched endpoints. V2 has {statuses["confirmed"]} confirmed local cycles and {statuses["supported_but_incomplete"]} supported incomplete cycle. Absolute game turn numbers remain uncertified.','',
        'B6’s v1 endpoint near716.020 s is a delayed native return after a command that already began around680.015 s. It is counted as an unmatched/wrong-time endpoint and creates a submenu-return review alert; this does not prove an extra actual game turn. V2 uses the native680.015 anchor plus subsequent recognized status-panel continuity.','',
        'B8’s return around322.005 s was missing from v1 and is recovered by v2. Its opening anchor also moves from155.010 to122.003 s; v1’s point was30.005 s outside the reviewed120.003–125.005 opening interval. This initial-anchor comparison is separate from the25 subsequent returns.','',
        'All25 v2 prediction intervals overlap their corresponding agent intervals. Point timestamps are not all equally precise: B7’s incomplete first cycle has a native return at208.002 s,3.000 s after the reference bracket’s upper end, but the widened prediction interval overlaps it. This remains incomplete; overlap is not exact-time certification. V1’s B9 point is1.985 s beyond its corresponding reference bracket; v2 places the anchor inside the bracket.','',
        'Neither version has a merge/split flag under this reference set. The evaluator includes controlled regressions for merges, splits, overly broad intervals and submenu false-turn alerts. Zero detected real flags is not evidence that unreviewed details cannot contain such errors.','',
        '## Phase-type and HUD-layout limits','',
        '| Measurement | v1 | v2 | Meaning |','| --- | --- | --- | --- |',
        f'| Observable resolution-start intervals matched | {phase_counts("v1")["interval_match"]} /29 | {phase_counts("v2")["interval_match"]} /29 | First recorded executed-move evidence is often later than withdrawal, transformation or other visible resolution onset. |',
        f'| Resolution starts late/outside interval | {phase_counts("v1")["resolution_start_late_or_missed"]} | {phase_counts("v2")["resolution_start_late_or_missed"]} | Retained mismatches, not promoted to accurate phase timing. |',
        f'| No resolution-start prediction | {phase_counts("v1")["no_resolution_start_prediction"]} | {phase_counts("v2")["no_resolution_start_prediction"]} | One additional final command in B7 has an uncertain/unobservable executed resolution and is excluded. |',
        '| Separately estimated resolution completions | 0 /29 | 0 /29 | The estimator does not independently timestamp these; next-command entries are not substituted as completion measurements. |',
        '| Automatic terminal result recognized | 0 /5 | 0 /5 | Agent source review observes WIN/results in all five; automatic terminal recognition remains incomplete. |',
        '| Unmatched returns near reviewed command submenus | 1 | 0 | B6’s v1 delayed return; no v2 alert under these proposals. |','',
        '**The25/25 command-entry match must not be interpreted as full turn/phase validation.** The first-execution-based resolution clock is late for many switching/Mega sequences, and a separate completion estimator is absent. The structured evaluation reports every such mismatch/unavailable comparison. These are remaining limitations for review, not reasons to invent finer boundaries.','',
        'All25 scored subsequent command-entry references have four visible cards in unobscured representative source frames. Real reduced-combatant command coverage is therefore **0** in this reference set. V2 supports reduced/occluded layouts through context-dependent rules and controlled tests, including deliberate HUD masking on a copy of an actual B8 frame. That transformation is synthetic and is not claimed as an observed two-combatant battle. Transient reduced visibility in real animations remains a separate phenomenon.','',
        'Four uncertain replacement/pivot intervals are retained separately and excluded from definite phase error rates. Ordinary move/target menus, status inspection and native returns remain in the same command phase unless executed resolution intervenes. No Battle Log content is used as a primary or required boundary source.','',
        '## Previously unresolved tails','',
        '| Battle | Source review | v2 outcome / limit |','| --- | --- | --- |',
        '| 5 | Last command around440–445; terminal field-to-result transition482–483; WIN484–485. | No further ordinary command exists in the reviewed tail; the final executed resolution is not automatically closed as a numbered turn. |',
        '| 6 | Native command at680.015, followed by status/move/target navigation until715; later716 return is same command. Field-to-result746–747; WIN749–750. | Corrected late boundary; final terminal resolution remains separate from next-command detection. |',
        '| 7 | Native command at659.012; menu/target returns through678; WIN686–687. | No executed final resolution is established from the independent source review. No fabricated final action turn. Earlier first-cycle boundary remains incomplete. |',
        '| 8 | Native command at322.005/324.005; subsequent resolution and field-to-result392–393; WIN394–395. | Missing322 boundary recovered. Four cards are visible in the original reviewed source, so this is not evidence of a true reduced-combatant command. |',
        '| 9 | New command around335–340, native return378, final field-to-result437–438; WIN439–440. | Earlier335–340 anchor now supported without treating later submenu return as a new turn. Final terminal result is an agent annotation, not an automatically recognized result. |','',
        '## Effect-counter cross-check','',
        f'Consecutive reference phases have {counter["supports_one_annotated_turn"]} usable rain/Trick Room one-turn corroborations and zero retained counter conflicts in this selection. {counter["activation_or_epoch_changed; relation withheld"]} reset/reactivation relation is withheld. {counter["side_or_effect_instance_unresolved; raw observations only"]} pairs have unresolved side/effect-instance binding and {counter["semantics_unverified; raw observations only"]} pairs have unverified semantics; these stay raw observations. A counter agreement does not replace source-frame review.','',
        'Sandstorm, sun, terrain, screens and Tailwind fractions remain source observations. Unscoped Tailwind/screens are not assigned to a side to improve a score. Hidden extension handling is preserved: displayed0/5 is not expiration;2/5→1/5→0/5→3/8 is still explicitly a user-described controlled scenario, not a newly observed recording sequence.','',
        '## Runtime, reuse and preservation','',
        '| Battle | Observation rows reused | Additional v2 geometry/panel inspections across development | Final interpretation seconds | New OCR in final invocation |','| --- | ---: | ---: | ---: | ---: |']
    for p in predictions:
        m=p['metrics'];lines.append(f'| {p["battle_id"]} | {m["observation_rows"]} | {m["v2_extra_frame_inspections"]} | {m["seconds"]:.3f} | {m["incremental_ocr_crops"]} |')
    lines+=['',f'No new OCR crops, original-video decodes, frame extraction or StateEngine replays were performed for v2. All4,710 observation rows and prior raw OCR were reused. Legacy `new_ocr_crops` fields retain earlier v1 costs; the explicit incremental fields are zero on the final interpretation pass. Across development, the compatible base geometry was reused and603 additional cached-PNG geometry/panel inspections were recorded. Review-sheet generation took{sum(s["seconds"] for s in sheets):.2f} s; retained completed v2 interpretation passes total{pipeline_seconds:.2f} s; the final interpretation pass took{sum(p["metrics"]["seconds"] for p in predictions):.2f} s. These processing measurements exclude agent review time, tests and ad hoc inspection; they are not an end-to-end application benchmark.','',
        f'Preservation baseline: {len(baseline)} files. Only the three intended existing files changed: `battle_evidence/visual.py`, `visual_controls.py`, `visual_offline.py`; {len(baseline)-len(changes)} baseline files match, including original v1 results/index/report, prior snapshots, M2.4, StateEngine, calculators, M3.3 databases and M3.4.1 inference code. References remain identical to their pre-prediction freeze. No historical artifacts were deleted.','',
        'Speed eligibility remains0 for all five recordings; no likelihood, prior, posterior, rule profile or M3.4.2 feature was changed. Local membership still requires the existing verified build/order/modifier evidence for a Speed update.','',
        '## Checks and review handoff','',
        '- Focused visual v1/v2, reference evaluation, battle evidence, M3.4.1 and artifact-policy checks: **159 passed**,2.32 s. Includes optional real-frame/controlled-occlusion cases available locally.','- Portable damage, inverse damage, Speed ordering, hidden-state, metagame and published-team regressions: **1,025 passed,2 optional historical-artifact cases deselected**,8.72 s. No full recognition/OCR suite was rerun for this visual-only change.','- Evaluation covers interval tolerance, one-to-one matching, merge/split guards, uncertain-reference exclusion, withheld human metrics, counters/reset/conflicts and separation of command entry from unavailable resolution-completion measurements.','- Cached output reuse, output/dependency hashes, frozen references and unchanged baseline files are checked separately from semantic acceptance.','',
        'Review the linked pages and confirm/correct command brackets, the B7 incomplete first boundary, replacement causes and fine resolution timing. Genuine reduced-combatant examples are still needed for real-layout acceptance. Human review is pending; this milestone is not declared validated. Nothing was committed or pushed.','',
        'Reproduce a selected battle’s stages with the commands in [visual-turns-v2.md](../docs/visual-turns-v2.md). The selected indices are `.cache/m34-visual-v2/battle-index.json` and `evaluation-index.json`; the frozen v1 selection is `v1-index.json`. Each battle’s manifests and checkpoints are isolated under its canonical cache directory.','',
        '## Review files','']
    for o in outputs:
        lines.append(f'- {o["battle_id"]}: [proposal JSON]({rel(o["reference"])}) · [video/frame review]({rel(o["review_html"])})')
    report.write_text('\n'.join(lines)+'\n')
    print(report)
    print(cache/'review.html')


if __name__=='__main__':main()
