# Mega stats and B23 handoff

2026-10-30, resumed after connection interruption.

- Mega implementation and cached B22 validation already existed when resuming.
  `scripts/validate_mega_stats.py --run-id mega-team7-b22-v1` verified all
  input/output fingerprints and reused the completed stage. No B22 video/OCR run.
- Regression command passed: **293 passed, 3 deselected in 63.34s**:

  ```sh
  .venv/bin/python -m pytest -q tests/test_mega_form_stats.py tests/test_champions_stats.py tests/test_ditto_unnerve.py tests/test_battle_state.py tests/test_event_driven.py tests/test_stateful_mechanics.py tests/test_hidden_state.py tests/test_evidence_fusion.py tests/test_hp_resolutions.py tests/test_sequential_resolution.py tests/test_git_artifact_policy.py -m 'not local_artifacts'
  ```

- B23 had only pre-existing protection/source snapshots, no production namespace,
  execution manifest, or active job. Started its first production attempt:

  ```sh
  .venv/bin/python scripts/run_fresh_video_benchmark.py --battles sample_battle_23 --run-id mega-b23-20261030-v1
  ```

- Execution and periodic elapsed checkpoints:
  `.cache/battles/sample_battle_23/fresh-benchmark/mega-b23-20261030-v1/execution.json`.
  Production checkpoints and observations:
  `.cache/battles/sample_battle_23/event-driven/mega-b23-20261030-v1/`.
  The driver automatically seals its initial outputs before review.
- On interruption, inspect processes and both manifests first. Never start a
  duplicate process or replace the first run. A running timing manifest cannot
  be resumed by inventing its end time. A complete execution can be checked with
  the same driver command without new acquisition.
- **Completed**: first production attempt and initial freeze. Full CLI wall
  803.716960 s, video 787.28 s, PTR 1.020878; 1,575 materialized/1,566 inspected
  frames, 5,764 OCR and 12 icon calls. No adaptive multi-hit windows requested.
- Independently transcribed all 23 saved log frames before prediction contents;
  fixed 84 readable rows (69 semantic, 15 numeric HP). Message-record result
  65/69; ordered HP endpoints and exact aggregates 15/15, program complete and
  supported 12/15. Not whole-match/full-state accuracy or human-reviewed truth.
- **Important limitation**: Team 7 was not attached in production (`self_rows=0`).
  Saved preview at 15.003 s visibly matches the six-member roster, but normal
  preview acquisition emitted only opponent rows. Consequently B23 did not use
  calculated Team 7 stats. Exact self Mega-Z identity did resolve. Do not rewrite
  the frozen run to imply runtime linkage succeeded.
- 30 deferred receipts (26 HUD occupancy, 4 unknown-side Garchomp messages), one
  `54/194` → `54/94` OCR maximum conflict, two unsupported message wordings and
  unproven general Incineroar return continuity are documented in `report.md`
  and `issues.json`. No repairs or second production run applied.
- Integrity passed: 57,342 files, including 46,627 protected B16–B22 and 10,602
  B23 first-run sealed files. No processing job remains active. No commit/push.

Read-only review/resume commands (do not reacquire completed video):

```sh
.venv/bin/python docs/mega-b23/score.py
.venv/bin/python docs/mega-b23/audit.py metrics
.venv/bin/python docs/mega-b23/audit.py verify
```

Heavy predictions, images, checkpoints, exact external execution times, initial
freeze, independent reference freeze and adaptive freeze remain under the B23
cache paths above. Compact report/evidence is in this directory. Mega-stage
fingerprints remain reusable under `.cache/mega-stats-validation/mega-team7-b22-v1/`.
Further behavior changes and their acceptance should be separate focused work.
