# Focused repair handoff — 2026-11-01

Scope: user attachment SHA is in `scope.json`; the subsequent Ditto steering is recorded there. No production replay, decoding, OCR, icon extraction, statistical priors, commits or pushes. Previous uncommitted work is retained.

Implementation:

- `tracking/identity_ledger.py`, `state_engine.py`, `active_continuity.py`: verified six-member species identity across regional/gender forms, separate encounter episodes, persistent HP/moves/build and original identity; immutable source IDs are represented through aliases. Ditto remains native at entry until explicit Imposter or Transform evidence; copied state ends on departure.
- `tracking/initial_conditions.py`, `resolution_endpoints.py`: scoped verified first-entry Archaludon HP194; derived provenance rather than HUD fabrication; conservative stable-plateau separation of B23 Flare Blitz from burn. Derived projections are saved separately.
- `damage/engine.py`, request schema: six conventional direct moves, explicitly indexed Dual Wingbeat hits, action-time ability contracts and threshold evidence. Recoil/status/priority effects remain separate.
- `battle_evidence/inference_integration.py`, `constraint_trace.py`: M3 inverse calls, per-hit shared build, named item witnesses across unchanged possession epochs, persistent native stat joins. Marginal results remain conservative outer bounds for other unresolved joint constraints.
- `scripts/trace_hidden_constraints.py`: opt-in `--focused-repair` namespace, dependency fingerprints, JSONL context checkpoints and per-damage inference checkpoints. Previously completed context files are reused for inference-only changes. Source receipts never overwritten.

Validation completed: broad regression 1384 passed, 10 deselected (`not local_artifacts`) across damage/inverse, identity, persistence, Ditto, HP resolution/attribution, knowledge grounding, inference, items and speed suites. Focused tests include all six new moves with normal/critical integer roll comparisons, ten ability comparisons against pinned Champions calc0.12.0, real Dual Wingbeat21+24 shared-build inversion, four saved endpoint repairs, no automatic reentry healing, and regional/gender identities. Oracle was available; those comparisons were executed. After adding the frozen-admission guard and explicit first-entry Ditto regression, focused + Ditto suites passed61 tests (39 focused +22 Ditto); focused/integration/constraint suites also passed86 before the final first-entry test. `git diff --check` passed. Determinism and arithmetic reference agreement do not establish recognition accuracy or independent Champions certification.

All battle outputs live in `.cache/battles/sample_battle_N/diagnosis/focused-repair-20261101-v1/`; per-battle `latest.json` selects the current trace. Manifests retain previous attempts and completed fingerprints. To resume, inspect each manifest and running process first. Run **one missing context stage at a time**:

```sh
.venv/bin/python scripts/trace_hidden_constraints.py --battle 22 --focused-repair --stage contexts --resume
.venv/bin/python scripts/trace_hidden_constraints.py --battle 22 --focused-repair --stage trace --resume
```

Use the same commands with20/21/23 only when that stage is missing or dependencies changed. Inference-only changes reuse contexts. Incomplete context attempts are retained; existing engine has no safe suffix resume, so only an incomplete invalidated attempt may repeat. Never edit runner while trace publication is active.

After all four stages complete:

```sh
.venv/bin/python scripts/verify_focused_repair.py
.venv/bin/python scripts/report_focused_repair.py
```

The integrity JSON checks frozen seals, original declared inputs, prior completed inference outputs and new completed outputs. It intentionally does not repeat the earlier full historical 57k-artifact scan. B21’s initial diagnostic replay promoted eight frozen deferred HUD receipts after identity repair. That invalid context stage remains archived. The runner excludes exactly these newly promoted inputs, records source_admission_guard and repeats only B21; source receipts remain present and unmodified in the trace. Other completed contexts with unchanged admission are reused. Context final hashes differ from source hashes because diagnostic state is repaired; admitted receipt status differences must remain zero. Original source conflicts/unaccepted receipts remain visible in report and trace. B23 frozen original team linkage remains `unbound`; diagnostic Team7 attachment is separately documented.

Source corroboration/revision IDs/license: `sources.json`. New curated test fixtures preserve selected accepted evidence plus original path/hash provenance, not generated dumps. Remaining unresolved observations and exact blockers are listed individually in the focused report; do not treat successful replay as complete semantic acceptance or start another milestone.

Final status: all four saved-evidence context/inference stages complete. Each latest trace has zero receipt-status mismatches and zero inference contradictions.27/28 audited damage relationships evaluated (previous11); the remaining copied-Ditto Hurricane cannot project to native offense. All four HP repairs accepted on saved causal evidence. Integrity check:175 unique files,62 prior declared trace JSON outputs, zero mismatches. Original source conflicts remain13/2/2/1 for B20/B21/B22/B23; these are not erased or semantic acceptance claims.
