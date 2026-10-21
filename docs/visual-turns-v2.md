# Visual turn reconstruction v2 — review required

V2 extends the existing `battle_evidence` estimator and offline runner. Four visible HUD cards are strong evidence, not a universal command prerequisite. M2.4 recognition, StateEngine, the calculators, databases and Bayesian model are unchanged. The original v1 results and report are preserved.

## Context-dependent command support

`normal_command_support` combines native controls with the current phase context:

| Layout/evidence | Acceptance rule |
| --- | --- |
| Four independently observed cards | Native Fight/Pokémon controls and ordinary battle geometry; two temporal observations. |
| Two or three independently observed cards | Both sides represented, native controls, a recognized integer COMMAND timer in 0–90, established opening/command/resolution history, and three consecutive supporting observations. |
| One visible card | The same timer/history/geometry requirements plus explicitly verified nonempty occupancy for both sides; three supporting observations. |
| Zero visible cards | Cannot establish a new ordinary command anchor. A previously established command can persist through supported menu/panel context. |
| Verified occupancy contradicts visible HUDs | Reject the anchor, including a nominal four-card layout. |
| Pending faint/pivot replacement | Reject a new command anchor until the replacement is resolved. |

This is not a two-card threshold. Side evidence, native control geometry, history, timer, occupancy consistency and persistence are separate gates. Unverified/stale cached occupancy is not promoted to current truth. The existing cached StateEngine projections have known drift; this task does not recertify them or silently use them to verify occupancy. The explicit verified-occupancy path is covered by controlled tests, not claimed as a new real-data fact.

`flexible_controls` stays in the new visual sidecar. It recognizes native round controls in their normal, pressed/yellow and entrance-animation positions, with constrained shape, color, emblem and paired spatial geometry. It returns evidence without applying a HUD quorum. Existing `recognition.command_checkpoint` is unchanged. Geometry alone cannot create a turn.

## Transitions and exclusions

The positive pattern remains established command → live resolution → next established command. A replacement/pivot must not increment the turn. Submenu returns without executed resolution remain in the same command. Missing HUDs during animation do not create phase transitions.

A short native anchor can persist into a move/target menu, a recognized status panel, or consistent COMMAND/HUD context even when a broad cached classifier says unknown/animation. This continuity starts from a native anchor and cannot bootstrap from COMMAND, a message or an overlay. Battle Log overlays are excluded; their content is not used.

Ordinary move menus that appear before any observed next native anchor remain `supported_but_incomplete`, with widened time bounds. Unknown/unsupported selections remain uncertain. The current strongest segment status still requires two distinct execution announcements, with the inherited extra-execution/possible-merge guard. This conservative action requirement can miss valid single-action late-game turns; it has not been replaced with invented action evidence.

`VisualPhaseEstimator(..., profile='v1')` preserves legacy behavior for existing callers/tests; `profile='v2'` enables the contextual rules. The offline runner defaults to v2 and stores output under each battle's `m34-visual-v2/<fingerprint>/`. It reuses raw OCR/geometry checkpoints and writes new interpretation artifacts without changing v1 results. Comparison uses the frozen original v1 result files, not a recomputation with changed source code.

## Separate references and review status

Each battle has a curated proposal file at:

`reports/battles/sample_battle_N/inputs/M3.4-visual-reference-v2.json`

These files were authored from chronological original-recording frame review before v2 inference/comparison. `visual_review.py` selects frames on a fixed five-second grid, without reading predictions, classifications, event boundaries or counters for selection. Additional one-second windows were chosen from visual review of the opening/resolution or recording tails. Source PTS/frame references and observation hashes are retained. The reference hashes were frozen before v2 implementation.

The reviewer is an AI coding agent with prior project context. The status is **agent-reviewed**, human approval is false, and review uses sampled source frames rather than continuous video playback. These are not independently human-verified ground truth. Most regular transitions have approximately five-second brackets; finer selected tail windows have approximately one-second brackets. Unknown detail between reviewed frames is explicit.

Each proposed command phase has separate command entry, resolution start, resolution completion and next-command fields. Completion and command entry sometimes share a sampling bracket; that means the proposal does not resolve their ordering within that interval. Terminal resolution completion and the result banner have distinct brackets. B7's last command has no independently established executed resolution; it is not converted into an extra completed action turn.

The local review pages link representative before/after PNGs, the original MP4, annotation notes, chronological sheets and separate v1/v2 comparison results. Correction-note export does not approve or overwrite the proposal. Human confirmation/correction is the next acceptance step.

## Comparison contract

`visual_validation.compare` matches subsequent command entries; opening anchors are reported separately. It uses chronological one-to-one maximum matching with a **1.6 s maximum gap between reference and prediction intervals**, allowing actual overlap and recording point-to-reference error separately. A broad prediction can match at most one reference, and possible merges/splits are separately flagged. Interval overlap is not exact timestamp accuracy.

Uncertain/unobservable reference boundaries do not produce definite false positives or misses. Supported/ambiguous predictions are reported separately from confirmed ones. Unmatched predictions in reviewed submenu intervals are surfaced as false-new-turn review alerts. Counts are comparisons against agent proposals; precision/recall remain null until references and relevant transitions actually receive human approval.

All reviewed unobscured command examples in these recordings have four visible cards. The recorded comparison therefore does not establish real reduced-combatant performance. Reduced/occluded layouts are covered by deterministic scenarios and a deliberately occluded copy of a real source frame; that controlled transformation is labeled synthetic.

## Effect counters and existing inference

Frozen counter observations remain separate from the annotations. Counter progression can corroborate consecutive proposed turns; activation/epoch changes withhold the relation, unknown side/effect instance or semantics remain raw evidence, and conflicts are retained. A counter does not replace visual review. The user-described `2/5 → 1/5 → 0/5 → 3/8` scenario remains a controlled test, not a newly observed sequence; displayed zero does not prove expiry.

Local memberships, duration tracking and action-snapshot overlays continue through the existing `TurnReconstruction`/`EffectDurations` infrastructure. Snapshot IDs and histories are preserved. No Bayesian model, likelihood, prior or M3.4.2 feature was changed. Speed eligibility still requires the original action/order/build/modifier evidence.

## Commands and recoverability

Prepare or reopen a prediction-free source sheet for one battle:

```sh
.venv/bin/python -m battle_evidence.visual_review --battle 8
.venv/bin/python -m battle_evidence.visual_review --battle 8 --start 319 --end 325 --step 1 --tag late-command
```

Run one battle's v2 interpretation and evaluation:

```sh
.venv/bin/python -m battle_evidence.visual_offline --battle 8 --profile v2
.venv/bin/python -m battle_evidence.visual_validation --battle 8
```

The selected result/evaluation indices are under `.cache/m34-visual-v2/`; `review.html` is the review entry point. Manifests retain implementation/input hashes, progress, output hashes and raw feature checkpoints. Legacy cost fields can include earlier v1 extraction; `incremental_ocr_crops` and `incremental_frame_inspections` describe the current invocation. A completed rerun reuses the output. Compatible OCR/geometry is retained across interpretation-only changes.

To rebuild the selected indices after a code change, process one battle at a time and checkpoint the result list:

```python
from pathlib import Path
from battle_evidence.visual_offline import run
from battle_evidence.visual_validation import evaluate
from speed_inference.offline import atomic_json
results = []
for number in range(5, 10):
    results.append(run(number, profile='v2'))
    atomic_json(Path('.cache/m34-visual-v2/battle-index.json'), results)
atomic_json(Path('.cache/m34-visual-v2/evaluation-index.json'),
            [evaluate(number) for number in range(5, 10)])
```

Reference revisions require an explicit review revision and new freeze, rather than quietly changing labels to improve prediction scores. No historical artifact should be deleted. See the v2 report for selected outputs, cost and remaining review issues.
