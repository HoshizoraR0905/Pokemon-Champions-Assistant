# M2 — evidence-based HP attribution

Scope: existing EventParser → StateEngine → numeric HP history only. No OCR,
sampling, visual thresholds, mechanics formulas, new reference facts, commit,
push, or later milestone. Existing dirty-tree work preserved.

Source: sealed `b16-banner-hp-20261028-v6/replay.json`, acquired in v5. Existing
reference: `b16-semantic-state-20261027-v1`; no denominator changes.

Implementation: `tracking/hp_causes.py` builds candidate causes and explicit
abstention reasons; `StateEngine.replay` enriches histories from processed
prefixes. A named recipient outcome can supplement earlier HUD animation
segments inside the same uninterrupted move action. Recipient instance binding
is captured at the outcome's prefix, not inferred from final party occupancy.
Unknown targets remain ambiguous. Activation alone never supplies HP causality.
Explicit effect announcements remain distinct from numeric endpoints. All HP
numbers and units still come from existing accepted observations.

Tests: `tests/test_hp_attribution.py` plus existing HP/state/fusion/mechanics/
event-driven regressions. The full focused command is:

```sh
.venv/bin/python -m pytest -q tests/test_hp_attribution.py tests/test_banner_hp_tracking.py tests/test_semantic_state.py tests/test_evidence_fusion.py tests/test_battle_state.py tests/test_stateful_mechanics.py tests/test_knowledge_grounding.py tests/test_event_driven.py tests/test_b16_state_benchmark.py -m 'not local_artifacts'
```

Evaluation stage: independent run `b16-hp-attribution-20261028-v5`.

```sh
ps -axo pid,etime,command | rg 'evaluate_hp_attribution.py'
.venv/bin/python scripts/evaluate_hp_attribution.py --run-id b16-hp-attribution-20261028-v5
```

Do not start a duplicate running job. Completed compatible results are reused.
Identity mismatches require a new run ID. The run manifest records sealed source
and implementation hashes, progress, partial state, and exact resume command.
Only the small deterministic replay stage restarts if interrupted; sealed OCR,
frame and endpoint stages are never regenerated. Atomic partial state snapshots
are diagnostic evidence, not a second authoritative battle state. Final replay
and source snapshots stay under `.cache/battles/sample_battle_16/hp-attribution/`.

v1 completed replay, then hit an audit-only assertion: metadata was removed from
live HP but not archived historical HP copies. Recursive stripping of the same
numeric-observation metadata establishes exact non-attribution state equality;
all receipt statuses/reasons match. Its successful replay is preserved. v2 was
interrupted at prefix 100 to keep one replay active at a time. v3 includes
the corrected recursive audit, durable partial states, source snapshots, and
stricter checks between numeric endpoints and later recipient notices.


v3 completed the corrected audit: 9 supported move-animation segments out of
41 numeric changes, with unchanged receipt behavior and non-attribution state.
Its report is preserved as an intermediate development result. v4 adds
explicit effect windows when both HUD endpoints follow the occurrence notice
(e.g. the two saved burn sequences), unknown-holder abstention, protected-outcome
abstention, and retention of competing move candidates. This is an algorithm
change, not acquisition invalidation; v5 recognition and v6 predictions stay sealed.


v4 completed: 41 nonzero adjacent numeric HP deltas, 13 supported (9 move damage,
4 burn residual), 28 ambiguous; zero unknown with no candidate; 12 observations
lack an initial baseline and are not established changes. The 13/41 coverage is
31.71%, not accuracy. All non-attribution state (including historical snapshots)
and every receipt status/reason match v6. Other real-video cause categories have
zero supported links; synthetic category tests are not real-video measurements.
Final v5 repeats the same scoped saved-event regression after tightening generic
healing-source admission and explicitly matching a named move recovery notice to
its corresponding action. No OCR, frame decoding or reference rewriting occurs.


Final code validation: **229 passed, 3 deselected**, 41.34 s. The deselections
are the explicitly excluded `local_artifacts` tests; no failure was relabeled
as missing evidence. `git diff --check` and Python compilation passed. The suite
includes all requested causal categories, required abstention, late recipient and
explicit residual windows, replay round-trip, event retraction and correction,
competing recoil/item effects, stable identities, coverage gaps and ambiguous
ordering. No claim of real-video accuracy is based on these synthetic contracts.


Final v5 is **complete**: 13/41 supported (9 move, 4 burn), 28 ambiguous; all original non-attribution state and receipt status/reason comparisons passed. See [results.md](results.md) and `reports/battles/sample_battle_16/evaluation/b16-hp-attribution-20261028-v5/report.md`. No active replay remains. Reinvoking the scoped command reuses the completed result.
