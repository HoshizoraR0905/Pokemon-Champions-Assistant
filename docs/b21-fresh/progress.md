# B21 first production benchmark — 2026-10-29

Current status: complete; no running jobs. See [final report](report.md).
Do not rerun the completed production CLI. Earlier notes are chronological.

Task: process newly added B21 using current production settings; record total
CLI wall/video-second ratio and per-video-second acquisition/recognition completion
intervals; evaluate reconstruction against independently checked partial Battle Log.
No B21-tuned production fixes, other videos, commit or push.

Input unique:tests/fixtures/sample_battle_21.mp4. No B21 namespace or active job
found before launch. Use fresh-b21-context-v1, event-driven/lightweight,2FPS.
Driver adds subprocess epoch start/end anchors for per-second file-completion
measurements; production CLI/recognition/state behavior unchanged. Overall wall
uses perf_counter. Separate state reconstruction/packaging is not spread across
individual video seconds. Per-second acquisition completion uses original atomic
monitor/observation file timestamps; retain its measurement limits explicitly.

Plan:
1. Run fresh production through existing external timing/freezing driver.
2. Seal original predictions/HP before log/failure inspection.
3. Per-second CSV and overall ratio; independent visible-log source transcription
   and structured/HP comparisons with explicit coverage and unresolved cases.
4. Relevant deterministic/HP/integrity checks and concise report.

Command:
```sh
.venv/bin/python -u scripts/run_fresh_video_benchmark.py --battles sample_battle_21 --run-id fresh-b21-context-v1
```
External log:.cache/battles/sample_battle_21/fresh-benchmark/fresh-b21-context-v1/
normal-pipeline-attempt-1.log. Execution.json and production manifest/checkpoint
hold durable progress. Inspect PIDs/processes first on interruption; never launch
a duplicate. A missing final elapsed interval must stay unknown, as in B20.
Do not inspect references before initial-freeze.json exists. Do not use old
hardcoded B17/B18 summary CLI; use per-battle describe only if needed.

Input headers:703.21s,23380 source frames,average33.2495064FPS,1319351968bytes,
SHA256ef9c6ac463dc496948271475387da5a48d5df9926d2078269c92f2e54c8ac809.
Timing helper in scripts/summarize_fresh_no_log.py;6 portable accounting tests
passed. It records one-second bins from original atomic file completions, marks
empty bins unknown, rejects reversed/out-of-range clocks, and keeps replay/
packaging tail separate. Exact total uses external monotonic CLI measurement.

Post-seal runner launched, waiting for seal. PID/status in fresh-benchmark/.../
postprocess.json; script postseal.py alongside it. It generates timing CSV/JSON,
checks exact event adaptation and HP membership, then runs independent historical
OCR into a separate report viewer. No redundant full second state replay; no
new full-replay determinism claim. After its completion, source transcription/
review and scoped rate scoring remain. Inspect running processes before resume.


## Final closure

Production complete and sealed, one uninterrupted cold attempt.703.21s video,
559.751187208s external CLI wall,0.7959943505s/video-second.1407 sampled,
1385 inspected,23380 source decoded/header frames match.4120 OCR,12 icon matchers.
Per-second CSV/JSON704 rows, no empty bins; source file completions plus separate
162.637844719s post-sample tail exactly account for total wall. Replay160.815s
is included, not added again. Clock epoch-minus-monotonic difference-0.001017s.
Peak526–527video seconds has81.524308s completion interval; no root profiling/tuning.

All25 log source frames visually reviewed before production event/automatic OCR
content inspection.73 visible reference rows,turns1–4, completeness not asserted.
Curated docs/b21-fresh/log-reference.json SHA256
5408c618f1d1b4696e86cea7082bbae404fd3f31f37af2ad1d0a8580e84c1bac.
Codex visual transcription, not human labels.8 adjacent source frames checked
for window boundaries; no extra log rows scored from ordinary HUDs.

Structured admitted semantic reconstruction44/53=83.0188679%,46 distinct receipt
records for44 rows.12/12 logged move executions matched.8 actor-unresolved
recovery notices deferred;1 miss notice has saved OCR but no event. Source audit
saved in manual-review/mismatch-audit.json. No B21-specific behavior correction.

20 numerical HP rows:18 ordered raw endpoint pairs,18 exact projection pairs,
15 complete endpoint pairs,9 program-supported causal groups. Do not combine
these into global accuracy. Missing pre-action endpoints:Archaludon194→168 and
Ceruledge100%→30%. No hindsight backfill of frozen predictions.

Automatic historical stage18.216s separately:25 views,40 assembled candidates,
11 assembly issues;18 provisional,12 ambiguous,8 missing,2 incomplete,0 verified.
Raw predictions/reference viewer remain separate.6 portable timing tests passed.
Exact event readaptation and HP nonmutation/membership checks passed; no redundant
full second state replay and no new determinism acceptance claim.

Integrity complete:8423 B21 freeze files, original production report/source hashes,
video and88 B16 guarded files unchanged; B17/B18/B19/B20 video-only seals3 files
each verified without replay. Final receipt:fresh-benchmark/.../final-integrity.json.
Postprocess.json status/stage both complete. No active jobs, commit/push or other
video processing. Unrelated existing working-tree edits preserved.

Changed source scope:existing external timing driver now records child epoch
start/end; existing reporting helper exports file-completion timelines; added
6 timing tests. No production recognition/state/mechanics edits. Generated chart,
CSV, comparisons and manifests stay in B21 cache; concise report/reference in docs.

Read-only reference comparison:
```sh
.venv/bin/python .cache/battles/sample_battle_21/fresh-benchmark/fresh-b21-context-v1/manual-review/evaluate.py
```
Timing reuse:
```sh
.venv/bin/python - <<'TIMING'
from pathlib import Path
from battle_artifacts import BattleArtifacts
from scripts.summarize_fresh_no_log import second_timing
second_timing(BattleArtifacts('sample_battle_21',Path.cwd()),'fresh-b21-context-v1')
TIMING
```
Source/identity mismatch must preserve old outputs, not force overwrite. Do not
reuse old summary CLI with its B17/B18 hardcoded destination. Remaining limitations
include partial log/agent review, unmeasured turn/slot/full-state accuracy,219
deferred receipts and2 conflicts; no implied new milestone acceptance.
