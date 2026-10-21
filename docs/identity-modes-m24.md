# Message identity modes (M2.4)

New event-driven runs default to `lightweight`. Standard/fast/diagnostic historical entry points retain their established behavior. Enable the game's `不显示对战名` setting for the expected canonical-name operating condition; unsupported names still remain unknown.

```sh
.venv/bin/python main.py --video tests/fixtures/sample_battle_9.mp4 --profile event-driven --identity-mode lightweight --run-id my-lightweight-v1
.venv/bin/python main.py --video tests/fixtures/sample_battle_9.mp4 --profile event-driven --identity-mode development --run-id my-development-v1
```

Use the recording's actual registered video path (`BattleArtifacts('sample_battle_9').video()`), or use the battle-scoped measured commands below, which resolve it automatically. Run IDs own isolated caches and reports. Existing IDs are never overwritten; `--resume` requires identical configuration, inputs and runtime source fingerprints. Successful recognition stages survive later failures.

Both modes use complete high-confidence send-out messages, exact canonical names and the pinned verified Chinese title vocabulary in `knowledge/data/52poke_titles_v1.json`. The original text, title assertion, timestamp and evidence remain available. Forms not distinguished by the message stay unknown. Missing species never comes from preview icons, HUDs or stale nickname aliases. Placement uses the maintained four-slot/entry-episode engine; an unresolved placement stays unresolved. Species equality never proves persistent party identity across entries.

Both modes continue ordinary HP reads, percentage observations, supported detail-panel status observations, field indicators, messages, command detection and separately scoped team acquisition. Preview icon calls are roster work, not active-species evidence. W control detection remains available; its identity reads and corrective reconciliation are disabled for both message modes. Old HUD/W code and models are retained for historical profiles.

Development mode freezes each message episode's prediction before independently classifying its first eligible post-entry HUD name and icon. It makes one attempt; no corroboration retry is currently configured. Unreadable/conflicting evidence yields `inconclusive`, absent or unplaced episodes yield `not_observed`, and confirmed disagreement yields `mismatch`. Subsequent frames never reopen a completed attempt. Re-entry gets a new episode. Verification evidence is saved separately in `identity-verification.json` and never changes event/state inputs. The verifier may inspect an otherwise unscheduled half-second candidate without changing the shared state acquisition schedule.

Measured acquisition and reporting:

```sh
.venv/bin/python scripts/profile_production.py --battle sample_battle_9 --run-id my-lightweight-v1 --identity-mode lightweight
.venv/bin/python scripts/profile_production.py --battle sample_battle_9 --run-id my-development-v1 --identity-mode development
.venv/bin/python scripts/report_m24.py --battle sample_battle_9 --lightweight my-lightweight-v1 --development my-development-v1
```

Do not run a CLI acquisition and then a profiler with the same occupied run ID. Profiling writes atomic `evaluation/<run-id>/execution.json`, immutable source snapshots, `profiler/segment-*/operations.jsonl`, `frames.jsonl` and `profiler.json`. Production observations and replay stay in `event-driven/<run-id>/`. The report writes `phase-timeline.json`, `segment-performance.json`, `identity-verification.json`, `summary.json`, `mode-comparison.json` and standalone `timeline.html` under `reports/battles/<battle-id>/evaluation/<run-id>-m24/`.

`COMMAND_TIME` includes supported move/target selection and normal controls. Forced replacement requires an observed player selection UI; its subtype is retained. Pre-battle team UI, post-battle evidence and unknown frames remain separate. Boundaries between differing sampled observations are UNKNOWN intervals, with source bounds and uncertainty rather than invented precise turn starts. A provisional faint-to-arrival span alone cannot establish player input.

Wall measurements use a monotonic clock during actual acquisition. Processing partitions consist of frame consumer wall, decoder waits and delayed per-frame/event reconstruction spans. Nested model/module spans are reported separately as inclusive and exclusive costs and never summed into wall twice. Initialization, exports, batch/shared evidence work and unattributed overhead remain shared. FFmpeg's source frame count is measured from showinfo; its asynchronous CPU time is not claimed. Wall/video is the reported real-time ratio. Peak memory is sampled process-tree RSS, not a guaranteed instantaneous maximum.

A saved old HUD-driven recognition stage cannot reproduce the new production policy by final-event replay: `--reconstruct-from` rejects cross-policy reuse. Use a distinct diagnostic namespace. Compatible crop/recognition cache reuse remains explicit and fingerprinted; never interpret an offline replay or removed-call estimate as measured acquisition speed.

The final Battle 9 equivalent-cache comparison uses these exact scoped commands (fresh namespaces required):

```sh
.venv/bin/python scripts/profile_production.py --battle sample_battle_9 --run-id m24-lightweight-final-v1 --identity-mode lightweight --recognition-cache .cache/battles/sample_battle_9/event-driven/m24-development-v2
.venv/bin/python scripts/profile_production.py --battle sample_battle_9 --run-id m24-development-final-v1 --identity-mode development --recognition-cache .cache/battles/sample_battle_9/event-driven/m24-development-v2
.venv/bin/python scripts/report_m24.py --battle sample_battle_9 --lightweight m24-lightweight-final-v1 --development m24-development-final-v1
.venv/bin/python scripts/validate_m24_history.py
.venv/bin/python -m pytest -q -m 'not local_artifacts'
```

Both final runs copy the same immutable same-battle pixel predictions, decode afresh, and use new processes. These are measured warm-prediction-cache runs, not fresh model-inference benchmarks. The earlier separately named v2 fresh-cache acquisitions remain available for sensitivity and model-cost measurements; a subsequent verification-only title-freeze fix and explicit event-title persistence are recorded in the source snapshots, so they are not presented as final-version identical-source measurements.

Per-segment `sampled_frames` counts physical 2 FPS candidates; `inspected_frames` counts accepted adaptive inspections (the acquisition manifest historically calls these `frames_sampled`). Lazy model initialization remains shared with its triggering source recorded. Parent wall envelopes include up to five seconds of exit polling; exact profiled child monotonic wall is reported separately.
