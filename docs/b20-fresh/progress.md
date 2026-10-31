# B20 fresh production and partial-log evaluation

Current status: complete within the recorded evaluation scope. No running jobs.
Production/HP sealed; exact replay and independent visible-log comparison complete.
See [final report](report.md). Remaining limits are documented, not production fixes.

2026-10-28. User corrected the input description: B19 has no Battle Log;
B20 has partial turns. B19 report updated, original frozen outputs preserved.

B20 original: tests/fixtures/sample_battle_20.mp4 (unique candidate);
903066474 bytes, average FPS40.769452, header frames19608. No B20 cache or
running process existed before this task. No production code changes planned.

Stages:
1. Fresh normal CLI through existing external driver, run fresh-b20-postfix-v1.
2. Seal complete predictions and fingerprints before failure/reference inspection.
3. Independent actual log extraction from saved source frames, manual review of
   available rows and coverage boundaries, then event-fact comparison.
4. Offline deterministic replay/HP checks; performance/state/partial-reference report.

Command:
```sh
.venv/bin/python -u scripts/run_fresh_video_benchmark.py --battles sample_battle_20 --run-id fresh-b20-postfix-v1
```
Driver console /tmp/b20-postfix-production-driver.log; checkpoints in
.cache/battles/sample_battle_20/fresh-benchmark/fresh-b20-postfix-v1/.
On interruption inspect execution.json/PIDs/processes first; do not launch
a duplicate or invalidate completed stages. No B20-specific tuning, commit or push.
Do not invoke old summary CLI --stage summary (hardcoded B17/B18 comparison path);
call its describe() function for the B20 per-battle descriptive report only.

B20 headers verified by driver: 481.03s, 19608 source frames, averageFPS 40.76945202014076. Input SHA256 17df9027239cd411d9c55ec5125e8fe35afcd58a069b628cfd9dd942d3d0eecd. Production sources unchanged from B19; no post-B19 failure fixes applied.

## Recovery after disconnect

Original driver76479/child76496 absent; execution.json left `running`, last
external checkpoint3592.397s. Source manifest/checkpoint at436.5067s and860 rows;
864 rows persisted. All production source hashes and video hash match.
Four rows437.0067–439.0067s lie beyond the atomic scheduling checkpoint. Preserved
with hashes in fresh-benchmark/fresh-b20-postfix-v1/recovery-v1/;
corresponding monitor tail also archived. Existing frames/exact OCR caches kept.
No prefix invalidation or production-source edits.

Recovery launched with normal CLI `--resume`, from437s. Durable runner:
`.cache/battles/sample_battle_20/fresh-benchmark/fresh-b20-postfix-v1/recovery-v1/resume.py`.
Inspect recovery.json PID/status and normal-pipeline-resume.log before any restart.
Original execution/manifest/checkpoint saved as *.before. Original interval has
no final external duration: exact total/PTR will remain null; only external
checkpoint + measured resume wall forms a lower bound. Resumed run is not a full
cold timing benchmark. Freeze is still required before reference review.

Portable Battle Log checks during recovery:29 passed,2 failed,6 optional local
artifact cases deselected (26.47s). Both failures are test_outcomes cases for
actorless critical-hit/multi-hit notices: existing frozen parser returns `field`,
legacy expectations say `unknown`. Verified these assignments already exist in
the original source identity. Kept unchanged; no B20-tuned production fixes.
Reporting helper now accepts interrupted/resumed timing and a partial-reference
note; compile and scoped whitespace checks passed. Production hashes unaffected.

Recognition suffix complete through480.515s; packaging in progress. Post-seal
runner launched, waiting for initial-freeze.json, then exact event/state/receipt/
hash/HP verification, descriptive report, separate historical log extraction.
Status/PID: recovery-v1/postseal-process.json. Script: recovery-v1/postseal.py.
It must not be duplicated while active; original production viewer is preserved,
log comparison viewer goes to reports/battles/sample_battle_20/evaluation/
fresh-b20-postfix-v1-logs/. Reference OCR is not manual ground truth.

## Completed production and independent local comparison

Production resumed successfully; all predictions and HP projection sealed before
failure/reference review. Resume subprocess649.9867235s; external total unknown,
lower bound4242.3834298s / PTR lower bound8.8193739.962 samples,947 inspections,
3669 OCR model calls; cold timing not comparable. Prefix implementation unchanged.

Exact927-event adaptation, complete second replay/receipts/state/hash (412.618s),
HP projection nonmutation/membership/endpoints all passed.29 nonzero numeric
segments across14 groups;11 complete endpoints,9 supported causal totals.
13 conflicts(12 maximum-HP,1 ability),2 early occupancy deferrals; no rejections.

Read all19 saved log frames320.003–329.022s via scaled source-panel contact sheets.
Visible turns1,2,3 only; no full-turn/whole-match coverage claim. Codex visual
transcription, not human-supplied labels. Curated reference frozen before reading
predicted event contents: docs/b20-fresh/log-reference.json,
SHA256114fc50b2ca71e9ed4c1219d5f6de070ed850ea61b6103dea7f5ebd8700ebf8f.
43 rows:35 semantic,8 numeric HP. Structured agreement31/35 rows (34 records,
including multi-actor rows),4 missing confusion-related rows;8/8 numeric endpoint
pairs found,7/8 marked complete and5/8 supported by existing causal projection.
Do not combine these denominators into overall recognition accuracy.
Three parser-side-unknown records have correct effective bound side. No independent
state/HUD checkpoint, turn-assignment or precision accuracy measured.

Reproduction (read-only; no replay/OCR):
```sh
.venv/bin/python .cache/battles/sample_battle_20/fresh-benchmark/fresh-b20-postfix-v1/manual-review/compare_reviewed.py
```
Comparison and confusion-parser-check.json live in that manual-review directory.
All three confusion sentence forms return unknown; high-confidence raw messages
were preserved as provisional_or_repeat without emitted events. No production fix.

Separate automatic historical OCR/comparison still running after exact checks;
inspect recovery-v1/postseal-process.json and event-driven/.../reference/manifest.json
before resuming. Its predictions are supplementary, not source labels. Original
production viewer is preserved. Final report pending automatic stage/integrity.


## Final closure

Separate automatic historical extraction complete:19 views,233 OCR calls,
231.202s,37 assembled candidates,3 assembly issues. Statuses14 provisional,
12 ambiguous,6 missing,5 incomplete;0 verified. These are machine candidates,
not replacements for independent43-row visual reference.

Final integrity passed:6671 B20 initial-freeze files, all original production
reports/source hashes, video hash and88 guarded B16 files verified. B17/B18/B19
video-only seals(3 files each) verified without replay or acquisition. Durable
receipt: fresh-benchmark/.../final-integrity.json. No production code changes,
commit/push or next-milestone work. No active processing jobs remain.

Changed during this continuation:docs/b20-fresh/progress.md,
report.md,log-reference.json; existing scripts/summarize_fresh_no_log.py gained
explicit interrupted-timing verification/reporting and partial-reference wording.
All unrelated working-tree edits preserved. Reporting helper compilation and
explicit whitespace audit passed. Portable tests remain29 passed/2 failed/6
optional cases deselected; no additional broad/expensive regression was needed.

Semantic acceptance remains limited to the stated visible fields/rows. The13
state conflicts, unscored state/turn/priority/numeric-stage accuracy, whole-match
coverage and original unclosed timing are not resolved by deterministic replay.
Any B20-driven production correction requires a new user scope; do not rerun,
retune or replace this sealed first-run evidence automatically.

To recheck prior completed exact stages without recomputation:
```sh
.venv/bin/python - <<'CHECK'
from pathlib import Path
from battle_artifacts import BattleArtifacts
from scripts.summarize_fresh_no_log import verify
verify(BattleArtifacts('sample_battle_20',Path.cwd()),'fresh-b20-postfix-v1',verification_id='recovery-v1')
CHECK
```
It checks frozen identities, then reuses the complete compatible verification
manifest. If implementation identity changes, preserve this result; do not force
its reuse or overwrite it. Actual human annotation/review has not been performed.
