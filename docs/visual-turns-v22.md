# Visual turn v2.2 handoff

Stop for human review. No production promotion, new milestone, commit or push.

[Validation and recommendation](../reports/M3.4-visual-turn-v22-validation.md): B10 recovered9/9 in targeted post-holdout regression, original holdout8/9 preserved. B5–9 unchanged. B6 command availability is source-bounded470.513–471.013s before Battle Log; detector remains genuinely late at474.513–475.013s. Freeze segmentation with that explicit timing exception; universal≤2s timing acceptance is unsupported.

## Implementation and durable artifacts

- `battle_evidence/visual_v22.py`: opt-in wrapper over unchanged v2; provisional stale-faint reconciliation using native geometry, timer reset, previous occupancy and resumed live resolution. Three-sample hysteresis retained. No Battle Log content, battle-specific routing, roster exhaustion assumption or global HUD-threshold change.
- `scripts/report_visual_turns_v22.py`: sequential cached temporal replay; first reproduces frozen history to verify the cached input adapter. Rebuilds local memberships and existing effect clocks; no StateEngine, OCR, video decoding, recognition or speed/Bayesian run.
- `.cache/m34-visual-v22/preservation-baseline.json`: pre-edit304 historical file hashes, including original172-file freeze. Required audit checkpoint; do not recreate it merely to bypass a mismatch.
- `.cache/battles/sample_battle_N/m34-visual-v22/manifest.json`: per-battle completed identity, dependencies, source/output hashes and replay metrics.
- Each corresponding namespace contains `visual-evidence.json`, `evaluation.json`, `historical-reference-evaluation.json`, `regression-audit.json`, `source.html`, `review.html`. B6 is compared against both references. Other battles retain v2.1 references. `attempt1/` retains superseded first replay with its invalidation reason; implementation snapshots are under `.cache/m34-visual-v22/implementation-attempt1/`.
- `.cache/m34-visual-v22/comparison.json`, `preservation-result.json`, and `review.html`: cross-battle summary,304-file preservation verification and localhost entry point.
- `reports/battles/sample_battle_6/inputs/M3.4-visual-human-observation-v22.json`: user firsthand observations separate from agent source review, actual chronology and per-frame hashes. `M3.4-visual-reference-v22.json`: scoped correction; old reference/evaluation untouched. Exact onset inside the interval unknown; no automatic human approval.
- `tests/fixtures/battle_evidence/visual_v22_b{6,10}_real.json`: intentionally scoped real cached recognition sequences with source snapshot/per-frame hashes, separate from synthetic cases in `tests/test_visual_v22.py`. Tests never substitute synthetic HUD edits for genuine B10 evidence.

## Resume without acquisition

The localhost server was already running on port8766 and is reused. If it has stopped:

```sh
.venv/bin/python scripts/serve_visual_review.py --port 8766
```

Open <http://127.0.0.1:8766/.cache/m34-visual-v22/review.html>. The older <http://127.0.0.1:8766/.cache/m34-visual-v21/review.html> is unchanged. Browser security settings need no changes. Individual decisions export JSON and do not approve a recording.

Reuse completed replay outputs and regenerate derived audits/pages:

```sh
.venv/bin/python scripts/report_visual_turns_v22.py
```

The runner verifies historical preservation before/after and reuses a completed output only when the manifest identity and output hash match. On failed/incomplete stages it resumes that battle from sealed temporal inputs. If the implementation/dependencies change, it rejects the prior identity: preserve the prior manifest/output in an explicitly named attempt namespace, document invalidation, then rerun. Source recognition/frame/OCR stages are not invalidated by a temporal-wrapper change. Do not rerun production or old report generators.

## Verification commands and results

```sh
.venv/bin/python -m pytest -q tests/test_visual_v22.py tests/test_visual_v21.py tests/test_visual_v2.py tests/test_visual_evidence.py tests/test_visual_validation.py tests/test_visual_review_server.py tests/test_battle_evidence.py tests/test_speed_inference.py tests/test_git_artifact_policy.py
.venv/bin/python -m pytest -q -m 'not local_artifacts' tests/test_damage.py tests/test_inverse_damage.py tests/test_speed_order.py tests/test_hidden_state.py tests/test_metagame.py tests/test_published_teams.py
```

188 focused tests passed, including22 v2.2 tests and local source-hash/preservation checks.1,025 domain tests passed;2 historical-artifact cases deselected. New regressions cover genuine B10, real B6 recovery/log interruption, synthetic submenu/forced/pivot/incomplete resolution/timer-only/no-history/occupancy/missing HUD/gap/new-action counterexamples, unchanged four-card behavior and duplicate/revision protection. Existing effect/counter tests retain reset/extension/unknown-scope behavior.

Browser check reuses the existing v2.1 checker with only localhost path routing changed, without modifying its frozen source:

```sh
.venv/bin/python - <<'PY'
from pathlib import Path
source = Path('scripts/verify_visual_v21.cjs').read_text().replace('m34-visual-v21', 'm34-visual-v22')
Path('.cache/m34-visual-v22/verify-browser.cjs').write_text(source)
PY
node .cache/m34-visual-v22/verify-browser.cjs .cache/m34-visual-v22/browser-check-v2
```

Use a fresh output directory. `browser-check-v1/validation.json` records Chrome155 success: all six full source/review pages,1,805 grid images, ordinary image requests/video ranges, collapsed predictions, unselected approvals, single-field export and no JS exceptions. Safari was not automated. Review contains all two-second grid frames; targeted chronology contact sheets are supplemental, not a new evaluation sampling rate.

## Acceptance limits

No new boundary false positives, semantic merges/splits or counter conflicts. The preserved B6 submenu proximity alert is the known late anchor near navigation, not an extra turn. B7 retains one incomplete segment and broad timing uncertainty; tiny2.001667s bounds remain unresolved. All recordings retain incomplete tails. The added B10 segment has no newly verified counter relation, and unsupported sun/terrain semantics remain raw. Final effects and raw counter observations are unchanged across all six.

Recommend freezing the segmentation implementation with the documented B6 timing exception and pending human acceptance. Do not claim every timestamp is within2s or that complete action/resolution timelines are certified. No tighter sampling/tolerance or general tuning was attempted.
