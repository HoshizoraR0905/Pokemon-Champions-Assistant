# StateEngine shared evidence architecture — 2026-11-02

Implemented and validated on `refactor/battle-state-architecture`, based on published baseline `cb8bc7c1ecb49eae316fd9535e294aebd0eee10a`. Final review and publication validation are recorded in [the publication review](state-engine-publication-review-20261102.md).

## Design

`tracking/evidence_history.py` separates immutable historical payloads from mutable current facts through reference sequences. Trial copies retain historical payload references; changes append or replace records. Facts themselves, current values, active slots and open entry episodes remain independently mutable. History remains available through the existing fields as a compatibility view. Closed episodes and departure snapshots are immutable; persistent return proofs refer to those shared snapshots instead of copying their HP histories.

HP causal enrichment replaces immutable observations when late evidence changes their interpretation. Nonzero deltas retain the full prior backfill algorithm; committed zero/baseline observations need no causal reevaluation. The accumulated event prefix is still inspected for nonzero causes. Corrections/retractions rebuild from initial state, preserving existing admission and identity policies.

`BattleState.to_dict` and `StateEngine.to_dict` still produce detached full legacy exports. Public apply/correct receipts are detached. The schema-2 state hash remains the SHA-256 of exactly the same sorted compact JSON; cached immutable fragments avoid repeated dataclass conversion and record serialization. Hashing still traverses mutable current facts and feeds full legacy bytes into SHA-256; it is not a new Merkle receipt hash.

`BattleState.compact_export` adds a version-1 current/evidence transport. Current fields contain explicit typed evidence references; a content-addressed table holds historical records and nested references. Repeated departures/proofs resolve to the same content identity. `expand_compact` validates referenced content and reconstructs the ordinary full state. Existing schema-2 replay imports/exports remain supported and unchanged; compact export is additive, not a silent replacement for downstream schemas.

Direct mutation of a committed historical dictionary now raises TypeError. Internal history revision uses record replacement. Integrations needing mutable JSON should use the ordinary legacy export. No global evidence registry, new biological identity owner, gameplay rules or inference preference is introduced.

## Acceptance and scope

All five saved-event baseline/refactor comparisons passed with **zero mismatches across 9,339 receipts**. The additional summary check confirmed equality of complete schema-2 replay exports, **including every receipt hash**, every decision prefix, scheduled full-state checkpoint hashes, final HP-resolution projections, and all five compact/full state round trips. Original input hashes and recorded output hashes remain unchanged, and source/script fingerprints and recorded platform/Python match across the selected runs.

These are original saved production recognized histories replayed through the **published cb8bc7c baseline and this refactor**, not a claim that post-fix baseline states equal the original production final states. Later reviewed/promoted contexts are separate evidence. Recognition, gameplay mechanics and hidden inference policies were not changed. The focused inference/damage regressions passed, including the curated B24 Spirit Break → Curse result `{72}` and Iron Ball preference. No new full-battle M3 inference traces were generated; exact reconstruction/decision inputs and existing adapter/mechanics fixtures establish compatibility within this validation scope.

The portable baseline selection plus history/Ditto/B21/B22 repair checks passed: **1,826 passed, 15 local-artifact tests deselected in 159.77 seconds**. Exact command: [validation JSON](state-engine-architecture-20261102-validation.json). Local log: `.cache/baselines/state-architecture-20261102/regressions.log`. B24's frozen/historical declared files passed `.venv/bin/python scripts/evaluate_b24.py --stage verify`. `git diff --check` passed. This is architecture acceptance against the existing reconstruction behavior, not new recognition accuracy, complete mechanic coverage, or battle-evaluation milestone acceptance.

## Saved-event performance

Core wall/CPU exclude separately timed diagnostic callbacks. Replay wall includes them; final artifact export and input loading/initialization are outside both replay timers. Progress bookkeeping and instrumentation overhead remain included. All measurements used the recorded ARM64 macOS / Python 3.10.4 environment. B21/B22 early baseline intervals overlapped short focused tests; these are shared-workstation measurements, not isolated controlled wall-time trials. CPU results are also included.

| Battle | Receipts | Baseline core wall s | Refactor core wall s | Speedup | Baseline core CPU s | Refactor core CPU s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B20 | 927 | 63.148 | 16.737 | 3.77× | 62.853 | 16.494 |
| B21 | 1384 | 158.843 | 37.502 | 4.24× | 157.632 | 37.294 |
| B22 | 2212 | 423.517 | 72.473 | 5.84× | 421.104 | 72.109 |
| B23 | 2036 | 313.299 | 63.183 | 4.96× | 309.545 | 62.625 |
| B24 | 2780 | 1053.860 | 150.650 | 7.00× | 1036.885 | 147.915 |

Per-receipt scaling is recorded in measured 100-receipt intervals. The final interval below is the last complete 100-receipt interval, not the trailing partial interval. All final totals include the entire replay.

| Battle | First 100 baseline core s | First 100 refactor core s | Last full 100 baseline core s | Last full 100 refactor core s |
| --- | ---: | ---: | ---: | ---: |
| B20 | 2.638 | 1.649 | 12.160 | 2.613 |
| B21 | 2.945 | 1.816 | 20.991 | 4.175 |
| B22 | 2.905 | 2.005 | 41.727 | 5.933 |
| B23 | 2.901 | 1.942 | 29.633 | 6.024 |
| B24 | 5.141 | 3.867 | 75.173 | 8.242 |

B24's actual replay spans confirm the optimization target. These are measurements of this saved-event experiment, not historical production function shares:

| B24 inclusive span | Baseline wall s | Refactor wall s |
| --- | ---: | ---: |
| Trial/reset whole-state copying | 323.863 | 32.906 |
| State hashing, including conversion/encoding | 691.001 | 62.449 |
| HP causal enrichment | 25.934 | 32.563 |

HP enrichment became slower in these runs. The new path adds copying/replacement of revised observations; the measurements do not isolate that added cost from other enrichment work. It is not the source of the measured speedup. Copy/hash work fell substantially; other overhead, including sealing, remains inside core totals. State-export spans in the refactor contain diagnostic full-state exports and must not be summed as core replay shares. Hashing no longer invokes a full `to_dict` for every receipt.

## Memory and storage boundaries

RSS is the process high-water sampled immediately after replay: it includes input loading, initialization and callbacks, and excludes subsequent final artifact exports. It is not replay-only memory consumption. The current size is only the current portion of the typed compact export; the full evidence table remains available separately. Byte counts use minified UTF-8 JSON.

| Battle | Baseline RSS MiB | Refactor RSS MiB | Current portion bytes | Legacy full-state bytes | Complete compact packet bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| B20 | 282.48 | 273.98 | 256,838 | 1,635,200 | 2,295,420 |
| B21 | 331.62 | 316.61 | 297,829 | 2,489,623 | 2,983,132 |
| B22 | 335.84 | 377.19 | 443,956 | 4,730,150 | 5,081,978 |
| B23 | 353.14 | 360.88 | 291,972 | 3,392,574 | 4,431,962 |
| B24 | 458.30 | 517.23 | 627,392 | 8,738,086 | 6,718,984 |

**RSS increased on B22, B23 and B24.** There is no uniform total-process memory improvement. Immutable payloads and cached canonical fragments trade retained memory for less repeated work; this experiment does not attribute the RSS differences to individual allocation sources. Typed references also increase total compact-packet size on B20–B23; B24's repeated departures/proofs deduplicate enough to reduce its complete packet. Current/history separation is not a universal compression claim. Legacy full exports remain the default compatibility interface.

Reference-list copies still scale with history length. Nonzero HP causes still scan chronological prefixes; mutable current metadata still traverses/copies. Full schema-2 SHA-256 still consumes full legacy bytes. The change materially reduces payload duplication and repeated conversion/serialization without claiming constant-time receipt processing or a fully incremental HP index.

## Preserved unresolved evidence

Receipt statuses and reasons are identical between implementations. None of these replays has rejected receipts; **267 remain deferred**:

| Battle | Deferred | Recorded observations | Applied candidates | Applied partial |
| --- | ---: | ---: | ---: | ---: |
| B20 | 2 | 23 | 885 | 17 |
| B21 | 211 | 36 | 1116 | 21 |
| B22 | 12 | 35 | 2137 | 28 |
| B23 | 30 | 34 | 1941 | 31 |
| B24 | 12 | 77 | 2657 | 34 |

The preserved deferred reasons are 249 `message_episode_occupancy_unresolved` and 18 `unresolved_candidate_fields`. This refactor does not promote unresolved evidence or repair recognition. The 15 deliberately deselected optional-artifact tests were not reported as passed or missing.

## Artifacts and reproducibility

[Measured summary](state-engine-architecture-20261102-measurements.json) records manifests, source/input/output identities, timings, intervals, spans, sizes, statuses and limits. It is a small summary; complete replay JSON, HP projections, compact evidence tables, prefix streams and exact benchmark bytes stay local under the canonical battle caches.

Selected experiment for B21: `state-architecture-20261101-b21-v2`; B20/B22/B23/B24: `state-architecture-20261101-v1`. The completed preexisting B20 baseline was reused. Interrupted B21 v1 remains unchanged. Published baseline code runs from `.cache/baselines/pre-state-engine-refactor-20261101/source/`. The benchmark scaffold was kept byte-identical so completed fingerprints remain compatible. Sequential driver status/log: `.cache/baselines/state-architecture-20261102/stage-driver.json` and `stage-driver.log`.

Verify saved outputs without replay:

```sh
.venv/bin/python scripts/summarize_state_architecture.py
.venv/bin/python scripts/evaluate_b24.py --stage verify
```

The first command verifies complete saved comparisons and atomically rewrites only the new compact measured summary; it does not replay. Existing complete benchmark stages also reuse compatible results. Preserve these stages for future changes; do not rerun baseline measurements simply because a later experiment uses different code.

Changed implementation: `tracking/evidence_history.py`, `battle_state.py`, `state_engine.py`, `hp_causes.py`, `active_continuity.py`, and the decision/evidence export helpers. New storage regressions: `tests/test_evidence_history.py`. Benchmark/comparison tools: `scripts/benchmark_state_architecture.py` and `scripts/summarize_state_architecture.py`.

The implementation/measurement phase performed no video decoding, real OCR/icon recognition, production CLI, full-video benchmark, commit or push. Publication is a separate follow-up, documented in the publication review. No production PTR improvement is claimed. Baseline branch/tag, original B24 production artifacts and prior Speed/performance audit versions are preserved. The original restart prompt remains a historical pre-implementation handoff; this document records the completed architecture work.
