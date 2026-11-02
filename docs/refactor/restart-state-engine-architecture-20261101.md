# Archived restart prompt — before StateEngine implementation

This is the historical pre-implementation handoff. The workspace path has been normalized for portability; the original remains in the local publication-review cache. See [the completed architecture report](state-engine-architecture-20261102.md) for current results. Do not restart completed measurements from this prompt.

---

Continue in the Pokémon Champions Assistant repository root. Follow repository `AGENTS.md`. Resume the StateEngine architecture refactor; do not repeat the completed baseline publication phase.

## Published baseline: already complete

- Baseline commit: `cb8bc7c1ecb49eae316fd9535e294aebd0eee10a`.
- Published branch: `m2.3.1-clean-artifacts` on `origin` (`https://github.com/HoshizoraR0905/Pokemon-Champions-Assistant.git`).
- Annotated tag: `pre-state-engine-refactor-20261101`.
- Tag object: `b029110ed1f1fa3157a7a4b05f77c998736ad30d`; its peeled commit and the remote branch were both verified against the baseline commit.
- Current local branch: `refactor/battle-state-architecture`, created at that baseline. This refactor branch has not been pushed.
- Baseline regression: **1765 passed, 15 local-artifact tests deselected in 146.54 seconds**, using 39 portable state/mechanics/identity/HP/damage/Speed regression modules. No video decoding, real OCR or model-recognition tests were selected.
- Baseline documentation and exact test command: `docs/baselines/pre-state-engine-refactor-20261101.md` and `docs/baselines/pre-state-engine-refactor-20261101-validation.json`.
- Local log: `.cache/baselines/pre-state-engine-refactor-20261101/regressions.log`.
- No suspect credentials were found in the proposed files. Historical absolute machine paths remain as provenance strings. No ignored cache/video/full-state data was force-added. Generated `reports/battles/*/diagnosis/**/trace-*.md` expansions remain local and are now explicitly ignored.
- Two extra EOF blank lines were recorded as preexisting formatting warnings in `battle_evidence/constraint_trace.py` and `scripts/trace_hidden_constraints.py`; no baseline correctness or formatting fixes were attempted.

The user then explicitly requested: **stop after pushing the baseline, preserve progress, and generate this restart prompt**. The prior task stopped accordingly. No StateEngine architectural implementation has been made yet. Do not confuse baseline publication with refactor completion.

## Local work and measurements to resume

At handoff the uncommitted additions are:

1. `scripts/benchmark_state_architecture.py`: a new saved-event benchmark/comparison scaffold. Review it before using it; it has not been committed or pushed.
2. This restart document.

An exact `git archive` of the published baseline is available at:

`.cache/baselines/pre-state-engine-refactor-20261101/source/`

The benchmark imports baseline modules from that isolated source snapshot, so edits to working-tree modules cannot silently change baseline execution. It uses saved production initial states and recognized event histories, not video acquisition. Each implementation/battle has its own manifest, input/source/script hashes, progress stream and output directory. One battle runs at a time. Completed identical stages are reused; differing or incomplete identities are rejected to preserve prior work.

Completed **B20 baseline saved-event replay**:

`.cache/battles/sample_battle_20/diagnosis/state-architecture-20261101-v1/baseline/`

- Manifest status `complete`; 927 receipt callbacks.
- Replay wall: 72.252481 s, including diagnostic callbacks.
- Core wall excluding separately measured callbacks: 63.148236 s.
- Core CPU: 62.853259 s.
- Whole-worker peak RSS: 296206336 bytes. This includes input loading/initialization; it is not a replay-only memory delta.
- Saved input hash verified unchanged.
- `replay.json`, `hp-resolutions.json`, `prefixes.jsonl`, `manifest.json`, and exact benchmark script bytes are preserved.

Interrupted **B21 baseline saved-event replay**:

`.cache/battles/sample_battle_21/diagnosis/state-architecture-20261101-v1/baseline/`

- Explicitly stopped at the user's request. Manifest status `interrupted`, with the previous failure/KeyboardInterrupt record and interruption reason preserved.
- 645 receipt callbacks; the last periodic 100-receipt interval ends at 600.
- Partial replay wall 40.189838 s; partial core wall 34.415995 s. These are **not** full-battle benchmarks.
- The partial prefix stream and function spans remain available. No complete final replay/HP output was published.
- There is no safe StateEngine suffix-resume snapshot here: prefix rows contain digests, not restorable full states. If B21 must run again, use a **new experiment namespace** and rerun B21 only; preserve the partial v1 files. Do not rerun completed B20 simply because B21 was interrupted.

The sequential baseline driver and B21 worker were both stopped and checked absent. B22, B23 and B24 baseline measurement stages were **not launched**. No refactor measurement or old/new semantic comparison has run. Check process liveness again on resumption rather than relying on this historical statement.

## First actions in the new session

1. Inspect `git status --short`, branch/remote/tag identity and relevant running processes. Do not reset, clean, discard or overwrite local work.
2. Read the baseline/refactor measurement manifests and the benchmark scaffold. Check input/source fingerprints before deciding what can be reused.
3. Read the existing runtime diagnosis and architecture entry points progressively. Give a concise implementation/validation plan.
4. Preserve completed B20 baseline results. If benchmark code must change, document the compatibility or invalidation reason and use a new namespace where needed. Do not blindly repeat all five replays.

Useful read-only checks:

```sh
git status --short
git branch --show-current
git rev-parse HEAD
git rev-parse 'pre-state-engine-refactor-20261101^{}'
ps -axo pid,ppid,etime,command | rg -i 'python.*(benchmark_state_architecture|pytest|replay|evaluate_b24)'
```

Existing benchmark CLI, after reviewing the scaffold:

```sh
# Complete B20 baseline should reuse, not replay:
.venv/bin/python scripts/benchmark_state_architecture.py --battle 20 --stage baseline

# B21 v1 is interrupted: use another namespace for that battle only.
.venv/bin/python scripts/benchmark_state_architecture.py --battle 21 --stage baseline --experiment state-architecture-20261101-b21-v2

# Later, one battle at a time, using consistent source/input identities:
.venv/bin/python scripts/benchmark_state_architecture.py --battle 22 --stage baseline
.venv/bin/python scripts/benchmark_state_architecture.py --battle 23 --stage baseline
.venv/bin/python scripts/benchmark_state_architecture.py --battle 24 --stage baseline

# After implementation, match each battle's selected namespace:
.venv/bin/python scripts/benchmark_state_architecture.py --battle 20 --stage refactor
.venv/bin/python scripts/benchmark_state_architecture.py --battle 20 --stage compare
```

The scaffold currently compares final full legacy state, receipts excluding migrated state hashes, final HP resolution, every receipt's decision projection, and full-state checkpoint hashes every 100 receipts and at non-HUD events. It records function spans, wall/CPU times, peak RSS and timed 100-receipt intervals. Diagnostic callback time is reported separately. Review these definitions and validate them before relying on the measurements; they do not establish exhaustive semantic acceptance by themselves.

## Refactor objective and architecture boundaries

**Keep current battle state compact, preserve complete historical evidence separately, and avoid copying or serializing the entire accumulated history for every receipt.**

Separate responsibilities while extending established modules:

- Current state: six-member rosters and persistent identities, current HP/status/stat stages/items/form, active slots, weather/terrain/Trick Room/Tailwind and other active conditions, references to relevant facts.
- Evidence history: raw recognized messages/observations, receipts, provenance, HP readings and causal attribution, switches/reentries, revealed moves/items/abilities, action cycles and ordering evidence.
- Identity/episode relationships: stable persistent member IDs, separate entry episode IDs, references to prior episodes/departures; avoid duplicating complete HP histories inside return proofs.

No target storage design has been implemented or accepted yet. Evaluate references, immutable/shared history, copy-on-write/selective copying and incremental processing against existing callers and correctness tests. Preserve backward compatibility deliberately and document migrations. Do not build a competing event/state/identity database.

Relevant entry points include:

- `tracking/battle_state.py`: nested dataclasses and `BattleState.to_dict`/`from_dict`.
- `tracking/state_engine.py`: replay, trial deepcopy, receipt hashing, correction/retraction and export.
- `tracking/hp_causes.py`: prefix reconstruction, HP causal enrichment and resolution projection.
- `tracking/active_continuity.py`: entry/departure records, currently including full historical HP snapshots.
- `tracking/identity_ledger.py`: persistent return proofs and duplicated departures.
- `tracking/decision_state.py`, `tracking/evidence_projection.py`, `tracking/state_timeline.py`: downstream views, exports and hash consumers.
- `battle_evidence/inference_integration.py`, `speed_preference.py`, `constraint_trace.py`: downstream M3 interfaces.

Measure actual saved-input replay cost around deepcopy, hashing/serialization, `BattleState.to_dict`, HP enrichment, identity/history duplication and repeated prefix scans. Separate required correctness work from replaceable repeated traversal. Avoid deriving a production function-share claim from terminal microbenchmarks alone.

## Correctness and validation requirements

Preserve recognized Battle Message outputs, accepted/deferred/rejected receipt semantics, persistent member/episode identities, species/item uniqueness, HP continuity across switches, multi-hit and residual damage attribution, move/item/ability revelations, weather/terrain/stat stages/Trick Room, certified ordering, M3 input projections, provenance and deterministic correction/retraction/replay.

Do **not** change gameplay mechanics, hidden-stat assumptions or the user-default inference policy during this architecture refactor. In particular:

- Default non-HP SP: downward SP=0; neutral/upward SP=0…32; one global alignment and total SP≤66.
- Unknown Iron Ball is a last resort after accumulated non-Iron-Ball evidence becomes infeasible; its speculative fallback has Speed SP=0. Explicit item facts are not overridden. Prior preferred marginals are not hard evidence.
- Under that preference, the current B24 Tyranitar Speed result is {72}; the other five sets remain documented in the existing report. This is not proof of item absence.
- Never substitute generic Generation 9 rules/learnsets for unverified Champions behavior or add arbitrary hidden priors.

Use saved B20–B24 recognized events only. Compare receipt status/reason/bindings, state chronology, identity assignments, HP endpoints/causes, revelations, Speed evidence and existing damage inference results. Existing focused repair fixtures and the curated B24 Speed fixture remain important regression inputs. Production raw-event benchmarks and later reviewed/promoted diagnostic contexts are distinct evidence sets; do not silently equate them.

If state representation/hash changes, version and document the migration. Preserve immutable event/source IDs and historical receipt hashes in their original artifacts; do not demand incompatible new serialization hashes equal old hashes.

Measure wall time, CPU time, peak memory and per-receipt scaling with consistent hardware/scope. Reuse successful stages, checkpoint meaningful partial results and keep baseline/refactor outputs separate. Full history must remain available; do not delete evidence to improve speed.

## Existing reports to retain

- `docs/performance/b24-runtime-diagnosis.md`
- `docs/performance/b24-runtime-diagnosis-measurements.json`
- `docs/b24-evaluation-20261101/speed-order-failure-analysis.md`
- `docs/b24-evaluation-20261101/speed-order-iron-ball-last-resort-v1.md` and companion JSON
- `reports/B24-evaluation-20261101.md`
- Baseline documentation/tag and focused B20–B23 repair/integration handoffs.

Historical B24 production: 1460.983723 s external CLI, 1052.82 s video, PTR 1.387686. Its 858.583679 s broad reconstruction/package timer is **not** isolated StateEngine replay. Original replay progress lacked timestamps; do not invent historical intervals. New saved-event replay measurements are separate experiments and cannot establish a production PTR improvement.

## Completion and publication boundary

Complete only when evidence remains available, current state avoids unnecessary duplicated histories, repeated whole-history copying/serialization is materially reduced, existing reconstruction/inference semantics remain equivalent, and saved-event replay demonstrates a measured improvement. Report mismatches, unresolved comparisons, skips and acceptance limits honestly.

No video recognition, OCR, icon recognition or production CLI rerun. No full-video benchmark or production PTR claim without separate user authorization. Do not force-push or rewrite the published baseline. **Do not commit or push incomplete refactor work.** The previous user requested this handoff before further implementation; this new prompt resumes the remaining work when explicitly submitted.
