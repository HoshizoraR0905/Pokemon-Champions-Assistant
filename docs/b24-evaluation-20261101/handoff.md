# B24 evaluation handoff — 2026-11-01

Completed within the recovered B24 three-layer evaluation scope. No next milestone, production reacquisition, commit or push. Main report: `reports/B24-evaluation-20261101.md`.

Final trace: `.cache/battles/sample_battle_24/diagnosis/b24-reviewed-context-20261101-v1/traces/7c3ffb267920ed10/trace.json`. `latest.json` selects it; stage manifest status is complete. All5 saved opponent damage relationships evaluated, zero new contradictions, zero receipt-acceptance differences. Two opponent Attack marginals narrowed; no Speed or Special Attack member marginal narrowed. Domains remain conservative marginal projections, not a certified full joint configuration solution.

## Preserved baseline and limits

First production `fresh-b24-20261101-v1` remains sealed. Original MP4 SHA matches. Independent source-only reference119 rows was reviewed before predictions; frozen comparison covers104 message/banner rows and15 HP pairs. Body messages86/93; with banners97/104. Named moves25/25 were only move_revelation_only. Baseline HP endpoints13/15, correct action groups11/15, causally supported complete10/15. No whole-match accuracy claim.

Final diagnostic endpoint matches15/15;12/15 are marked supported and complete by the diagnostic projection. This is not a new recognition score or independent causal certification. Sand damage attributed under Tailwind, unresolved Life Orb54%→44% plateau and unsupported extra8%→6% self-cost remain disclosed. Three accepted opponent executions lack usable HP relationships; no Defense/HP inversion or probability priors were added.

Full stat integer sets, global alignment/SP branches, entity/effect/deferred/HP audits and per-member chronological traces stay local in `.cache/battles/sample_battle_24/evaluation/fresh-b24-20261101-v1/final/`. Initial3/5 and subsequent4/5 inference versions remain alongside final5/5. Source receipts and all partial attempts are preserved.

## Resume fixes and cache identity

`scripts/evaluate_b24.py`: `TeamProfiles.load()` refreshes `updated_at_utc` through its existing report calculation. The diagnostic runner now restores that bookkeeping timestamp from the persisted validated profile. Identical facts therefore retain a stable fingerprint. Narrow compatibility reuse reconstructs the exact former input using only the previous load timestamp and requires its full dependency/input fingerprint and saved replay/context hashes to match. Actual proof reconstructed completed fingerprintda213a54b8e86b2e exactly; this113MB context was reused without changing output bytes.

Initial process detection mistakenly filtered lowercase python and missed macOS Python PID24323, causing a duplicate attempt. Both incomplete repeats were stopped and marked interrupted; all partial JSONL remains. Later analysis proved timestamp drift, rather than battle-fact differences, caused those fingerprints. Always check processes case-insensitively before resuming.

`battle_evidence/inference_integration.py`: observed consumed/none/lost/transferred status resolves an empty defender item slot before checking missing identity or required-item fallback. Truly unknown status stays unresolved. This enabled High Horsepower inversion.

`tracking/initial_conditions.py`: existing opt-in stage-language interpretation now accepts an explicit list separated by 、 with one shared magnitude/direction. Existing StateEngine applies the numeric changes, dedup and retraction. This enabled the Parting Shot stage context for Psychic Fangs. That actual dependency change required one new diagnostic replay; completed prior stages were retained.

Seven B24 connected-hit handlers and Sand Force were already written at interruption and validated during resume. New report generator `scripts/report_b24_evaluation.py` reads saved evidence only, verifies seals/checksums, and publishes the concise report and local detailed audits. It does not acquire, replay or infer.

## Validation and integrity

Final integrated portable regression:241 passed,1 deselected in63.77s, after all resume fixes. Log: `.cache/battles/sample_battle_24/evaluation/fresh-b24-20261101-v1/final-regressions.log`. Includes B24 cache/damage/configuration/inference/constraint/focused repair plus Ditto, HP resolution/attribution and state. Cache-specific3 tests cover deterministic payloads and rejection of reuse when an actual Attack fact changes. Empty-slot tests cover four explicit statuses, unknown preservation and input immutability. Compound-stage regression covers both stat transitions, repeated application, source immutability and retraction.

Earlier broader portable group1163 passed,4 deselected before the last two fixes. Groups overlap; do not sum as unique tests. Pinned Champions calc0.12.0 arithmetic comparisons passed; these are executable-reference comparisons, not independent Champions certification. `git diff --check` passed.

`integrity.json`:15062 unique declared frozen/historical/completed files checked, zero mismatches; original MP4 matches; independent reference and baseline seals verified. `sources.json` records13 bounded 52Poké article snapshots, revision IDs, retrieval date, applicability and licensing. Actual Champions learnset headings/columns were checked. Runtime remains offline; learnability supplies no equipped slots or probability prior.

## Exact rerun/resume commands

No job remains active. If interrupted in a future modification, inspect the working tree, process liveness and manifest before launching anything:

```sh
ps -axo pid,etime,command | rg -i 'python.*evaluate_b24'
.venv/bin/python scripts/evaluate_b24.py --stage verify
.venv/bin/python -u scripts/evaluate_b24.py --stage inference --version reviewed-context-20261101-v1
.venv/bin/python scripts/report_b24_evaluation.py
git diff --check
```

Unchanged current dependencies reuse complete contexts and inference. An actual state dependency change requires a new context fingerprint; inference-only changes reuse contexts. The StateEngine has no safe suffix-resume API, so incomplete context attempts may repeat while their partial output is retained. Do not edit the runner during active publication.

Latest successful run log: `.cache/battles/sample_battle_24/evaluation/fresh-b24-20261101-v1/resume-inference-compound-stage.log`. Original progress and earlier logs remain local for audit. Main report distinguishes generated completion from unresolved semantic coverage; no further work or milestone was advanced.

Final unchanged-input resume smoke check executed successfully: reused complete context119376ea8122799a and inference7c3ffb267920ed10, with no replay or new inference publication.
