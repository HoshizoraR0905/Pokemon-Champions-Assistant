# M2 sequential resolution recovery — 2026-10-28

The connection interruption left implementation and evaluation artifacts ahead
of the working handoff. Recovery began with Git status/diffs, process inspection,
targeted source/test reads and stage-manifest fingerprints, before any edit.
No relevant Python, pytest, OCR, replay or ffmpeg job was still running.
All existing unrelated working-tree changes and historical outputs were retained.

## Recovered implementation and completed evidence

- `tracking/resolution_context.py` implements the chronological projection;
  `tracking/hp_causes.py` delegates action resolution to it. StateEngine owns
  numeric admission and persistent state. Parent moves survive stat-only banners,
  nested reactions and pivots; recipient bindings come from actual evidence.
- `knowledge/resolution_effects.py` exposes the existing scoped, versioned
  52Poké categorical supplement through KnowledgeBase canonical identities.
- `recognition/resolution_sampling.py` already supports cached targeted HP-only
  inspection and adaptive sampling. No sampling or OCR change was needed here.
- `tests/test_sequential_resolution.py` already had 30 parameter-expanded cases;
  action resolution and adjacent attribution had another 62. These **92 passed
  in 39.47 s** on recovery. The old pytest last-failure cache contained a renamed
  action-target test; it was historical evidence, not proof of a current failure.
- Sequential evaluation v1 and v2 both have complete manifests. All source hashes
  in **v2** match the recovered implementation. v1 differs only in evaluator code.
  Frozen action v4 remains the prior comparison baseline, not the current result.

The matching v2 command reused completed output. A separate fresh projection
from sealed saved receipts exactly matched the entire saved v2 prediction;
`engine.to_dict()` was identical before/after, including state and receipts.
No acquisition, replay reconstruction, video decoding or OCR was invoked.

[Completed B16 report](../../reports/battles/sample_battle_16/evaluation/b16-sequential-resolution-20261028-v2/report.md):
21 frozen action/target groups, 41 numeric segments, 16 complete endpoint pairs,
16 complete causal attributions (previous action view: 6), and all three requested
Weather Ball / Snarl diagnostics matched. All 21 immediate-cause associations are
supported by this evidence policy; independent causal accuracy is unmeasured.
Original reconstruction metrics remain 120/124 event facts, 175/191 state fields,
18/21 reference numeric pairs, and 3/3 observed HUD-zero endpoints.

## Interrupted and superseded stages

- Banner/HP event-driven v2 and v4 record `KeyboardInterrupt()`; subsequent v6
  reconstruction and its sealed inputs are complete. Do not resume older runs.
- Numeric attribution v1 preserved all 1300 replay receipts but failed packaging
  because the comparison initially omitted historical HP metadata. Its manifest
  records the corrected recursive comparison and superseding final run.
- Numeric attribution v2 intentionally stopped at prefix 100, preserving partial
  snapshots and one-battle-at-a-time execution. v3 superseded it; final v5 is
  complete and is the sequential evaluator's source.
- Action projections v1–v4, sequential v1–v2, source review/onset review and the
  scoped 5 FPS probe all have complete manifests. Historical whole-file source
  mismatches do not invalidate successful frame/OCR stages.

There is no incomplete current expensive stage to restart. The interrupted
session's exact final shell command cannot be established from manifests or
pytest caches; final regression completion had no durable sequential-task record.

## Recovery changes and remaining acceptance limits

Added five negative cases: noncontact move with Rough Skin banner, Life Orb holder
different from the move user, healing banner followed by loss, a new move clearing
old pending reactions, and banner retraction removing stale causal/self-damage
totals. The first targeted run passed four cases; the fifth exposed an incorrect
new assertion expecting a dictionary where the established unknown total is
`None`. The assertion was corrected; production behavior required no change.

Five B16 totals remain unresolved: three lack pre-action endpoints and two lack
confirmed final plateaus. No extra amounts were inferred. B16 contains no saved
real multi-hit / ally-pivot / repeated-contact-reaction validation sequence;
synthetic contracts do not establish real-video recognition or causal accuracy.
Independent cause labels and additional source evidence remain outside this
recovery. No next milestone, commit or push was started.

## Reproducible validation

Completed matching evaluation (reuse only):

```sh
.venv/bin/python scripts/evaluate_sequential_resolution.py --run-id b16-sequential-resolution-20261028-v2
```

Final portable integration command:

```sh
.venv/bin/python -m pytest -q tests/test_sequential_resolution.py tests/test_hp_resolutions.py tests/test_hp_attribution.py tests/test_banner_hp_tracking.py tests/test_semantic_state.py tests/test_evidence_fusion.py tests/test_battle_state.py tests/test_stateful_mechanics.py tests/test_knowledge_grounding.py tests/test_event_driven.py tests/test_b16_state_benchmark.py -m 'not local_artifacts'
```

Final result: **289 passed, 3 deselected in 79.08 s**, including all 35 sequential
resolution cases. The three deselections are optional historical-artifact cases.
There were no skips or failures in the selected tests.

Additional parser and artifact-policy regression:

```sh
.venv/bin/python -m pytest -q tests/test_scrolling_semantics.py tests/test_git_artifact_policy.py -m 'not local_artifacts'
```

Result: **35 passed in 9.20 s**. Together the final two commands cover **324
passing tests**, with 3 deselections. Recovery console logs remain at
`/tmp/m2-sequential-recovery-pytest-20261028.log` and
`/tmp/m2-sequential-recovery-parser-20261028.log`; this document preserves the
commands/results independently of those temporary logs.

Compilation of the resolution, supplement, sampling, evaluator and changed test
modules passed; `git diff --check` passed. Optional historical-artifact tests and
unrelated damage/inference suites are not acceptance claims for this scoped
recovery. No implementation change invalidated the complete matching B16 v2
evaluation, so it was preserved instead of generating another report version.
