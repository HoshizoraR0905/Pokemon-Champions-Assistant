# Visual turn v2.1 frozen evaluation handoff

This validation iteration adds no detector behavior. Stop for human review; do not tune against Battle10, start M3.4.2, change priors, commit or push.

## Completed stages and authoritative selections

- `.cache/m34-visual-v21/freeze.json`: pre-holdout source/configuration/package and historical prediction/reference hashes;172 files.
- Battle10 acquisition: `.cache/battles/sample_battle_10/event-driven/m34-v21-holdout-frozen-v1/`. Production and observable replay complete; profiler and source snapshot are under the corresponding `evaluation/` directory. Do not rerun acquisition.
- `.cache/m34-visual-v21/holdout-prediction-seal.json`: initial V2 prediction sealed before reference-grid generation/inspection. The canonical result lives under `.cache/battles/sample_battle_10/m34-visual-v2/55263114604cd22f/visual-evidence.json`; the sealed path traverses an isolated index-routing root and resolves to that same file.
- Each battle has `m34-visual-v21/reference-grid/manifest.json`: complete independent two-second source grid, actual global source timestamps plus chunk PTS/timebase/origin and image hashes. All1,805 grid frames were reviewed. Reference grid preparation added zero decoding/OCR. Source sheets use cached production PNGs.
- `reports/battles/sample_battle_N/inputs/M3.4-visual-reference-v21.json`: curated agent phase/boundary proposals and every chronological no-transition frame record. Development and holdout reference freeze files are separate.
- Battle5 `M3.4-visual-human-correction-v21.json`: two user-reviewed fields only,≈195–196s; no whole-turn/battle human approval. Separate targeted check in `human-correction-check.json` bounds the next-entry error by0.5–2.0s; completion has no independent detector estimate.
- `evaluation-index.json`, per-battle `evaluation.json`, `disputed-boundaries.json`, `resources.json`, `preservation-result.json` and `historical-preservation-result.json`: comparison, costs and preservation audits.
- [Validation report](../reports/M3.4-visual-turn-v21-validation.md) and `.cache/m34-visual-v21/review.html`: final review handoff. Historical v2 report remains unchanged.

B6's first draft incorrectly treated a pivot party selector near340s as normal command. Full-resolution inspection of the same chronological grid showed the336s actor-return message. The draft, initial comparison and earlier freeze were retained. The revised proposal explicitly states that this source correction occurred after development comparison. Stable retained IDs were not renumbered. This is not blinded validation.

The failed first B5 grid attempt rejected chunk-relative PTS as global. Its incomplete manifest/sheets remain in `reference-grid-attempt1-chunk-pts-check-failed`; the successful sampler includes recorded seek origins or explicitly recovered offsets where the old cache dropped them. No historical frames were edited or removed.

## Local review

```sh
cd /Users/yyi/Pokemon-Champions-Assistant
.venv/bin/python scripts/serve_visual_review.py --port 8766
```

Open <http://127.0.0.1:8766/.cache/m34-visual-v21/review.html>. The server binds only127.0.0.1, serves existing repository assets, rejects symlinks outside the root and supports single byte-range requests for original MP4 seeking. Stop it with Ctrl-C. Do not change Safari/browser security settings. The session's server may already be listening; reuse it rather than starting a second one.

Each source-only page is a complete chronological grid without reference or prediction overlays. The separate annotation page exposes current phase proposals, per-field uncertainty, nearby frames/video and collapsed frozen prediction/counter comparisons. Select `human-reviewed` for an inspected but uncertain/corrected field or `human-approved` only for a specifically accepted field. Enter both interval endpoints if correcting timing, add evidence, and export the selected individual decisions. Save the downloaded JSON as human-authored evidence for later explicit import/reconciliation. Export does not rewrite references or imply approval of other fields; no import or detector tuning occurs in this milestone.

## Results and limits

Development5–9:24/25 subsequent entries interval-compatible;19 bounded to≤2s;5 compatible but insufficiently localized;1 late. Holdout10:8/9 compatible and bounded to≤2s;1 missing. Opening anchors are separate and included in each evaluation. No pooled headline accuracy is reported.

Priority disputes: B10 final784.032–786.032s ordinary command is missing, with a genuine three-card/two-versus-one layout; B6 prediction474.513–475.013s is2.5–5.001667s from the470.012–472.013s reference; B7 first return has a wide/incomplete prediction. Tiny2.001667s upper bounds remain unresolved rather than being rounded down. Neither semantic phase coverage nor reduced-layout robustness is certified by these counts.

The source sampler and evaluator are in `battle_evidence/visual_v21.py`; all old detector modules are frozen. Chronological matching uses minimum interval distance≤2s. A guaranteed timing pass additionally requires maximum possible absolute error≤2s. The≤10s unmatched-counterpart association is diagnostic, never a timing pass. Unknown intervals are unscored. Resolution-start timing is a separate comparison, completion is not independently estimated, and terminal banners are agent source annotations rather than successful automatic terminal recognition. Counter semantics/scope/reset limitations remain visible. Existing hidden-extension behavior is preserved.

## Reuse and resume commands

Regenerate only derived evaluation/pages/report (no OCR, decoding or reference edits):

```sh
.venv/bin/python scripts/report_visual_turns_v21.py
```

Reopen a completed source-grid manifest/page directly. The sampler's implementation hash is an input identity; if code or source inputs change, preserve the old grid and explicitly version a new namespace instead of overwriting it. No missing grid cells required targeted extraction in this run; a future missing cell fails explicitly rather than selecting a distant sample or expanding its bracket.

The holdout adapter can reuse completed evidence/visual outputs without touching the old shared indices:

```sh
.venv/bin/python scripts/run_visual_v21_holdout.py
```

This checks the frozen baseline and completed production acquisition first, then uses original `evidence_run`/`visual_run` functions with only an in-process Battle10 run mapping and isolated `m34e` index routing. It preserves the existing seal on reuse. Do not run a fresh production namespace merely because a chat disconnects. If acquisition were genuinely incomplete, inspect its execution manifest/process first, then resume the exact identity:

```sh
.venv/bin/python scripts/profile_production.py --battle sample_battle_10 --run-id m34-v21-holdout-frozen-v1 --resume
```

This command is documented for interruption recovery, not needed after the completed/sealed run.

## Validation

Focused visual v1/v2/v2.1, evaluation, evidence, Speed inference and artifact-policy checks:166 passed (including localhost range/escape and sampler PTS/grid/cache regressions). Portable damage, inverse damage, speed ordering, hidden state, metagame and published-team regressions:1,025 passed,2 historical-artifact cases deselected. The first combined broad invocation also included the new server test, which initially failed because the host's HTTP proxy intercepted localhost; the test now explicitly bypasses proxies for its local fixture, and passes. Broad domain tests themselves all passed on that invocation.

Browser check via ordinary Chrome security over localhost: all six source/review pages, frame links (HTTP200), MP4 ranges (HTTP206), collapsed predictions, unselected review statuses, single-field approval export and absence of JS exceptions passed. Browser artifacts are in `.cache/m34-visual-v21/browser-check-v1/`; Safari itself was not automated. Recheck in a fresh artifact directory with:

```sh
node scripts/verify_visual_v21.cjs .cache/m34-visual-v21/browser-check-v2
```

172 pre-holdout baseline files remain unchanged. Existing prior preservation audit still matches631/634 files including both metagame databases; its only three differences are the V2 implementation changes made before this task. Current hashes of those detector modules remain frozen. No old evidence was deleted, no prior/database mutated and no commit/push performed.
