# B16 semantic/state development benchmark

Scope: Phases 1–5 authorized after Phase 0 acceptance. No commit/push.
Evaluation is development/regression: B16 was used to identify parsing gaps.

## Completed before cold run

- Existing BattleState/EventParser/StateEngine extended; no second authoritative
  state model. Literal sleep/continued sleep/wake, sun/sand, both-side Tailwind,
  Wide Guard side activation and individual outcome observations, qualitative
  healing/damage/zero notices, canonical stone OCR variant, generic Mega completion.
- Completed protection/absorption outcomes use existing per_action MechanicState,
  not an invented protection duration. Side effects retain unknown durations.
- Generic Mega completion records a transformation but leaves precise X/Y variant
  unknown. No held stone or ability is inferred from generic completion.
- Semantic candidates below the unchanged occurrence gate remain auditable;
  original OCR/evidence survives normalization. No HP cause inferred from an
  adjacent move; no qualitative notice supplies a numeric HP endpoint.
- Focused pre-run checks: 147 passed, 1 local-artifact test deselected in 61.55s.
- User-authorized cleanup deleted exactly 11,733 generated files, 3,138,331,700
  logical bytes. Inventory and baseline remain here; original video SHA256 verified.

## Cold run and recovery

Fresh run ID: `b16-semantic-state-20261027-v1`.

```sh
.venv/bin/python scripts/run_b16_benchmark.py
```

The driver refuses duplicate measurements. Inspect the existing child PID and
`normal-process.json` before any resume. Do not start a second decoder:

```sh
ps -axo pid,etime,command | rg 'main.py|run_b16_benchmark.py'
tail -8 .cache/battles/sample_battle_16/evaluation/b16-semantic-state-20261027-v1/normal-pipeline.log
```

Production CLI writes atomic checkpoints. If genuinely interrupted, preserve
successful stages and use the exact same source/config/run identity:

```sh
.venv/bin/python main.py --video tests/fixtures/sample_battle_16.mp4 --profile event-driven --identity-mode lightweight --sample-fps 2 --run-id b16-semantic-state-20261027-v1 --resume
```

A resumed run cannot be reported as the original uninterrupted cold CLI wall time.
The normal-process driver records full process time without call instrumentation;
log extraction, read-only evaluator replay and tests are excluded.

## Reference and evaluation order

Only after the production seal exists:

```sh
.venv/bin/python scripts/benchmark_b16_state.py extract
.venv/bin/python scripts/benchmark_b16_state.py contacts
# Inspect original log crops; author fresh reference annotations without predictions.
.venv/bin/python scripts/benchmark_b16_state.py reference
.venv/bin/python scripts/benchmark_b16_state.py compare
```

Log extraction resumes saved views via its manifest; reference annotations bind
exact extraction SHA256, row text, evidence and ordering. Comparison consumes a
sealed reference and verifies unchanged live files. Its snapshots are read-only
projections of StateEngine replay, not reference-driven state updates.

## Final completion

All requested stages completed under the run above. Normal CLI wall 666.124s /
753.74s = PTR 0.8838; 107/124 event facts reproduced (97 applied, 10 recognized-only)
and 154/191 state fields reproduced. The separate original-video reference scan
recovered 118 log records, including 28 readable rows rejected by automatic overlap
assembly, and three independent HUD-zero points. Remaining measured failures and
all caveats are in validation.md and the final report; no recognition tuning followed
the final comparison. No active job needs resuming.

Final publication and reusable reference-only observation inventory:

```sh
.venv/bin/python scripts/summarize_b16_state.py
```

`extract` and `reference` reuse verified completed/sealed stages. `compare` can
reuse verified semantic checkpoint projections if only evaluator/report code changes;
production source changes are rejected against the cold-run fingerprints. Final
portable tests: 2592 passed, 73 deselected; additional evaluator tests: 5 passed.
