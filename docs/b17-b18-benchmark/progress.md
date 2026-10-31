# B17/B18 fresh production benchmark — 2026-10-28

Scope: full original videos, fresh independent run namespaces, no Battle Log,
no retrospective log reconstruction, no injected identities/HP/targets and no
recognition tuning before sealing the initial results. No commit or push.

Run ID: `fresh-b17-b18-20261028-v1`, isolated under each `BattleArtifacts` owner.
Both runs and post-seal verification/reporting are complete. B17 ran first;
B18 started only after B17 completed and was sealed. Original
source videos and B16 historical artifacts remain untouched.

Inputs (headers, not a full decoding pass):

| Input | SHA-256 | Header source frames | Average source FPS | Original resolution |
|---|---|---:|---:|---|
| `tests/fixtures/sample_battle_17.mp4` | `30bca7722d20ca4d9c3f163d8dde804d47118006e10cb8c572153d4951cb8239` | 23799 | 44.9330224391 | 2622×1206 |
| `tests/fixtures/sample_battle_18.mp4` | `d40048026a628602d7ce2b97cd8adc361ada64e0acb99447471620d787121bf9` | 12663 | 30.0399726399 | 2622×1206 |

Exact source paths, container duration, stream-derived duration and metadata
commands are saved in each `fresh-benchmark/<run>/input.json`. Source rates are
averages, not constant-frame-rate assertions. The production source decode count
will be checked against the container header frame count.

Production command: `.venv/bin/python main.py --video PATH --profile event-driven
--identity-mode lightweight --sample-fps 2 --run-id fresh-b17-b18-20261028-v1`.
PP-OCRv6 ONNX CPU and pinned icon/knowledge assets are reused; recognition caches
are fresh per battle. Acquisition normalizes frames to the established 1311×603
geometry. Cheap monitoring samples at 2 FPS, with adaptive detailed inspection
at 1 FPS during stable COMMAND and overrides for messages/banner/HP changes.

Current production `main.py` calls recognition, event parsing, StateEngine replay
and normal viewer/export. Targeted high-FPS HP acquisition is still a separate
tool and is not integrated into that CLI. No optional targeted pass is included
in this initial normal-pipeline benchmark. The current action-level HP view is
derived immediately afterward from saved live receipts and separately timed.
It is sealed with the initial results; no manual evidence supplements are used.

External timing driver:

```sh
.venv/bin/python -u scripts/run_fresh_video_benchmark.py \
  --battles sample_battle_17 sample_battle_18 \
  --run-id fresh-b17-b18-20261028-v1
```

Driver output: `/tmp/b17-b18-production-driver-20261028.log`.
Per-battle durable logs: `.cache/battles/<battle>/fresh-benchmark/<run>/`.
The driver writes input metadata, execution attempts, process IDs and 30-second
elapsed checkpoints, then derived HP output and an initial freeze inventory.
Production preserves raw frames/reads/icons/observations, every receipt, initial
and final state and source snapshots in `event-driven/<run>/`.

On interruption, inspect processes and these manifests first. Do not launch a
duplicate. Completed executions/seals are reused. A failed completed timing
attempt can resume with the same driver command plus `--resume`; resumed timing
is explicitly distinguished from an uninterrupted cold run. An unclosed external
timing interval requires recovering the actual process outcome, not inventing
elapsed time. Never erase completed acquisition or sealed outputs to restart.

The driver stores a read-only hash inventory of existing B16 manifests,
predictions, sealed replays and benchmark reports. Verify that inventory after
processing. No B16 replay is planned.

Preflight regression: **355 passed, 3 deselected in 109.26 s**. This includes HP
completion/sequential attribution, state/event/banner/identity contracts,
recognition cleanup and Git artifact policy. Log:
`/tmp/b17-b18-preflight-tests-20261028.log`. All tests finished before the normal
timed commands began. Compilation and `git diff --check` passed for the driver.

B17 completed and sealed: 529.71 s container duration, 474.530107 s external
normal wall, 1060 monitored frames, 1052 detailed inspections, 4307 OCR model
calls, PTR 0.895830. Internal cold wall is 473.905887 s.

B18 completed and sealed: 421.58 s container duration, 751.729657 s external
normal wall, 844 monitored frames, 831 detailed inspections, 3033 OCR model
calls, PTR 1.783125. Internal cold wall is 750.661159 s. Both were uninterrupted
first attempts with empty prediction namespaces. Source decode counts match the
header counts exactly: 23799 and 12663. No source processing stage failed or
required resuming. There are no active benchmark/verification jobs remaining.

Aggregate normal wall is 1226.259764 s over 951.29 video seconds. Pooled
ms/sample is 644.043994; pooled ms/inspection is 651.226641; aggregate PTR is
1.2890. These use summed wall/frame/duration denominators.

Read-only event and full-receipt reproduction completed after both initial seals
existed. B17 reproduced all 1372 receipts in 144.712123 s and saved 14 prefix
state snapshots; B18 reproduced all 1108 in 259.387860 s and saved 12 snapshots.
Complete serialized history, final state and state hash match the original runs.
All HP segment memberships and actual endpoint observations were checked:
B17 22 nonzero segments / 11 groups, B18 7 / 4 groups. The independent HP
projection times were 0.131495 s and 0.007202 s, outside normal command timing.

The original successful verification used `--verification-id v1`. Its exact,
fingerprint-matched source is preserved in each `verification/v1/source/`.
Report export initially failed with `KeyError: field`; BattleState stores weather,
terrain, Trick Room and global effects separately. Only reporting code was
corrected, then report export was resumed without rerunning acquisition or replay.
AST comparisons in `report-code-compatibility.json` confirm the verified
`read`, `engine_from_saved`, `check_freeze` and `verify` functions are unchanged.
The original verification manifests and fingerprints remain intact.

Do not repeat completed video or verification stages. Regenerate reports from
the saved v1 verification with the summary command below. If a new verification
is actually required with the current reporting module's whole-file fingerprint,
use a new verification ID (`v2` in this example), preserving completed v1:

```sh
.venv/bin/python -u scripts/summarize_fresh_no_log.py \
  --battles sample_battle_17 sample_battle_18 \
  --run-id fresh-b17-b18-20261028-v1 --stage verify --verification-id v2
.venv/bin/python scripts/summarize_fresh_no_log.py \
  --battles sample_battle_17 sample_battle_18 \
  --run-id fresh-b17-b18-20261028-v1 --stage summary --verification-id v1
```

Verification writes independently resumable stage status and prefix state
snapshots under each `fresh-benchmark/<run>/verification/v1/`. Repeat the same
command to reuse successful identical stages. A verification implementation/input
change requires a new verification ID and preserves earlier verification outputs.
It never reruns source decoding or OCR. Unknown observations and missing labels
remain explicit. No event/state accuracy claim is possible without independent
annotations. Final comparison target:
`reports/Fresh-Video-Benchmark-B17-B18-20261028.md`.

Postflight regression: **355 passed, 3 deselected in 121.13 s**, no selected
failures/skips. This began after both timed production commands exited, so it
does not affect their performance metrics. Durable test results and console logs
are retained under B17's `fresh-benchmark/<run>/test-results.json` and
`preflight-test-log.json` / `postflight-test-log.json`. Temporary originals are
`/tmp/b17-b18-preflight-tests-20261028.log` and
`/tmp/b17-b18-postflight-tests-20261028.log`. Both test commands used:

```sh
.venv/bin/python -m pytest -q tests/test_hp_completion.py tests/test_sequential_resolution.py tests/test_hp_resolutions.py tests/test_hp_attribution.py tests/test_banner_hp_tracking.py tests/test_semantic_state.py tests/test_evidence_fusion.py tests/test_battle_state.py tests/test_stateful_mechanics.py tests/test_knowledge_grounding.py tests/test_event_driven.py tests/test_b16_state_benchmark.py tests/test_scrolling_semantics.py tests/test_git_artifact_policy.py tests/test_recognition_cleanup.py -m 'not local_artifacts'
```

Reporting scripts compile and `git diff --check` passes. The final reports were
generated and inspected for both recordings, including final state/condition
schemas and all requested formulas. B16 guarded files remain byte-identical;
no B16 replay or processing was launched. See [source-review.md](source-review.md)
for localized conflicts, tail overlays, performance interpretation and the absence
of independently verified special-move examples. No production recognition rules
were modified; no later milestone, commit or push was started.

Final hash checks passed for all initial source/recognition/replay seals and
**88 protected B16 files**, plus the original B16 video hash. Each battle's
`benchmark-summary.json` records final report/output hashes, successful
verification/source identities, one uninterrupted production attempt and no log
or accuracy scoring. Generated frames/HTML/JSON remain ignored; source scripts,
concise Markdown reports and handoff notes are reviewable without staging dumps.
