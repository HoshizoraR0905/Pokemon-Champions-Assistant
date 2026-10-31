# Current recognition architecture (2026-10-27)

Production video entry: `main.py --video PATH --profile event-driven --identity-mode lightweight --run-id NAME` → `recognition.fast_video.analyze`. The default `standard` CLI profile is retained for screenshot, configuration and old video clients. It is a separate supported adapter, not the production battle reconstruction path. No new recognition/mechanics/inference features are introduced by this cleanup.

| Layer | Owners and executable flow | Contract |
|---|---|---|
| Recognition tools | `fast_video.decoded_frames` (FFmpeg, source PTS, frame grid); `CachedOCR` → `onnx_ocr.ONNXOCRBackend`; `CachedIcons` → `icons`/`sprite_shape`; `fast_profile.normalized/difference/RegionGate`; `video_sampling.atomic_json/fingerprint` | BGR pixels, raw OCR observations/tokens, independent icon scores, original source/time, durable crop caches. No biological occupancy. |
| Visual extraction | `regions.REGISTRY` and shared `hud_roi`, message/field/detail constants; `fast_profile.inspect/independent_cards`; `phases`, `ui_regions.message_rows/read_message`; `identity_modes.read_hp`; `trainers`; `Recognizer` configuration/preview branches; `visual_evidence`, `party_panel`, `command_checkpoint` | Where to look, visibility, OCR refresh, raw field readings. Region registry records phases, geometry owners, expected content, methods, acceptance conditions, refresh and output. Dynamic popup/log/configuration geometry stays in its named owner rather than being copied into a second table. |
| Semantic parsing and state | `MessageOccurrences.observe` → `event_report.video_events`; `EventParser`, `MessageNames`, `EntityResolver`/`KnowledgeBase`, `move_resolution`, `visual_adapter`; `StateEngine` → existing `identity_ledger`, `active_continuity`, `entry_hud`, `evidence_fusion`, `command_reconciliation`, `tracking.double_faint` | Immutable event IDs and evidence; normalized identities separate from raw text; conservative admission and stable encounters/slots. Unknown names/targets/slots stay unknown. Only StateEngine applies authoritative state. |

`fast_video.analyze` orchestrates these layers, saves each observation/checkpoint, then calls `event_report.reconstruct_and_package` for the final ordered replay, receipts, viewer and seal. Context checkpoint serialization now belongs to `recognition.context`, eliminating production imports of the historical M2.3.7 processing driver. Normal reconstruction still uses established report/receipt helpers; this cleanup does not rewrite report schemas.

Double-faint acquisition scans only new message/trainer observations, looking for two distinct faint references on the same side followed by two replacement references. Existing trainer consensus and EventParser route announcements. Unknown routing remains permissive, never an assignment. Ordinary replacement resets a one-faint window. Each candidate is admitted through the unchanged StateEngine/pending_pair policy at most once, then independent per-slot name/icon proof is read at the existing >=2-second retry cadence. A topology change on the same side invalidates pending acquisition. Empty pending work returns before creating an EntityResolver. Scheduling hints are rebuilt from saved rows on resume and are not a second authoritative state ledger. A genuine candidate still incurs **one full prefix replay**, so worst-case candidate-heavy recordings remain a performance limitation. This change does not optimize StateEngine hashing or development EntryVerifier replays.

## Parameters and frame rate

| Parameter | Scope / effect |
|---|---|
| `--sample-fps 2` (default) or `3` | Production/fast/diagnostic FFmpeg acquisition grid and cheap monitoring. For example `main.py --video PATH --profile event-driven --identity-mode lightweight --sample-fps 3 --run-id fps3`. Included in manifest identity/config; resume requires the same setting. `EventInspection` still inspects at 1 FPS during verified COMMAND; visible messages override it. Frame frequency and actual OCR invocation frequency remain separate. |
| `--identity-mode lightweight` | Message identity + HP reads + qualified double-faint verification. `development` additionally runs observational entry verification, with separate historical replay cost. |
| `--end-seconds`, `--max-frames` | Scope a fresh run; use these before processing a whole recording. |
| `--frame-cache PATH` | Same-battle acquisition manifest; verifies video, frame hashes/scale and matching sampling FPS. Does not manufacture missing grid cells. |
| `--recognition-cache PATH...` | Same-battle exact pixel prediction reuse with matching model/icon/adapter dependencies. |
| `--reconstruct-from PATH` | Sealed recognition-stage reuse; deliberately strict source/dependency checks. Cleanup source changes do not authorize bypassing those checks; use the read-only regression script below to compare historical evidence. |
| `--run-id`, `--resume` | Battle-owned namespace and exact input/source/config identity; changed source needs a new run ID. Existing cache/seals are preserved. |
| `--no-icons` | Disable matching; leaves unavailable icon evidence unknown. |
| `--interval`, `--ocr`, `--language`, team configuration, annotation/JSONL flags | Supported standard screenshot/video adapter. Production now rejects explicitly passed `--interval`/`--ocr` rather than silently ignoring them. Production always uses PP-OCRv6 ONNX CPU. Other standard-only flags are documented here; they do not tune production acquisition. |

The configuration definitions are `EventConfig` (`event_schedule.py`) and `FastConfig` (`recognition/experimental.py`). Region thresholds are in the named extractor and summarized in `regions.REGISTRY`; OCR acceptance .75 is in `CachedOCR`/ONNX; message identity .95 is in `identity_modes.message_identity`. These are heuristic scores, not probability priors. A 3-FPS acquisition test validates the setting; no new full-recording OCR cost/accuracy benchmark at 3 FPS is claimed.

## Separate supported paths

* Battle Log: `scripts/compare_battle_log.py --battle-id ID --run-id NAME` (see `--help` for current arguments) verifies Pass A seal before `battle_log.detect_log/extract_view/assemble_views`, `EventParser`, `log_comparison.align`. B16's separate evaluator also uses these same extractors, with its saved auto-reference path. Historical viewing timestamps never become action times. No reference data enters live predictions.
* Screenshot/configuration: `main.py --image/--images`, `Recognizer`, `TeamConfiguration`, `Tracker`. `paddle_ocr.create_ocr` and `ocr.OCR` are still required here and by `stream_replay.py` and historical benchmarks; Tesseract fallback exists **only on those adapters**, not production ONNX.
* Streaming/experiments: `stream_replay.py`, `streaming.*`, fast/diagnostic profiles and `entry_model.probe_entry` retain explicit opt-in entry points. They are not selected by the production command. See audit for why they were retained.
* Evaluation/review: `event_report`, `fast_report`, `scripts/build_battle_evaluation.py`, `report_entry_hud.py`, `production_profiler.py`, saved replay scripts. Profiler now wraps the executed `identity_modes.read_hp`, replacing its dead HUD hook.
* Damage/Speed/statistical work consumes saved events/state/evidence. `battle_evidence.visual_offline` shares ONNX/command primitives; `visual_controls` shares card detection; replay/projection and modeling modules retain their own feasible-set/statistical responsibility. Recognition never imports their inference engines or invents a prior from learnsets.

Read-only deterministic verification (one battle per invocation):

```sh
.venv/bin/python scripts/verify_recognition_cleanup.py --battle sample_battle_16 --source-run b16-auto-eval-20261026-v1 --run-id cleanup-v1 --replay --compare-prefix
```

The verifier fingerprints inputs and source, writes atomic stage results in `.cache/battles/ID/cleanup/NAME/manifest.json`, reuses completed stages, and preserves all sealed data. A failed in-progress replay resumes from that stage, not from OCR. It emits concise comparisons, not generated full-state dumps. No commit/push is performed.
