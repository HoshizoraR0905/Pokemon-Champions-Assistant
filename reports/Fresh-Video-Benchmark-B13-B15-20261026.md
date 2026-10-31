# Fresh held-out video benchmark: Battles 13–15

2026-10-26 (Asia/Shanghai). **3/3 original-video runs completed; recognition accuracy remains pending independent human annotation.** This is a current-pipeline engineering benchmark, not semantic acceptance or a development milestone.

Base commit: `78b5b001a09b4aed47af2c2c0d0b3b4ca9eca5d8`, with pre-existing uncommitted changes. The exact version is the commit **plus frozen runtime files and SHA-256 manifest**; commit alone does not reproduce the working tree. No runtime source, threshold, parsing rule or prediction was changed for these videos.

Hardware: Apple M1 Pro, 16 GiB RAM, macOS 26.3.1 arm64; Python 3.10.4. Maintained README production entry: `main.py --profile event-driven`, default `EventConfig`, `--identity-mode lightweight`, icons enabled, PP-OCRv6 medium ONNX CPU (batch 1). Shared immutable model/icon/knowledge assets were reused; all three video-owned prediction namespaces started absent, with no prior frame/recognition/state/annotation inputs. Internal unchanged-region reuse remains enabled. The shared team recorded in B13 was not manually transcribed or injected into predictions.

All videos display at **2622×1206**, encoded **1206×2622** with rotation metadata; the production recognition layout is **1311×603**. Source frame counts below are counted during complete FFmpeg decoding and match OpenCV metadata.

| Video | Duration (s) | Source frames | Sampled frames | Inspected frames | Runtime (s) | Processing FPS | Event records | Completed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| sample_battle_13 | 347.23 | 12,007 | 695 | 622 | 251.786 | 2.760 | 403 | Yes |
| sample_battle_14 | 325.46 | 10,861 | 651 | 599 | 166.259 | 3.916 | 560 | Yes |
| sample_battle_15 | 828.90 | 27,786 | 1,658 | 1,419 | 367.721 | 4.509 | 1,074 | Yes |
| Pooled | 1501.59 | 50,654 | 3,004 | 2,640 | 785.766 | 3.823 | 2,037 | 3/3 |

Runtime = measured fresh canonical CLI wall + separately measured automatic Pass B log extraction/parsing/export wall. Sampling is 2 FPS independently of OCR frequency; confirmed COMMAND reduces detailed inspection to 1 FPS. Processing FPS = materialized sampled frames / runtime; pooled FPS uses summed frames/summed times. This is offline throughput, not source FPS or streaming latency.

| Video | Fresh CLI external wall (s) | CLI internal wall (s) | Separate log stage (s) |
| --- | ---: | ---: | ---: |
| sample_battle_13 | 251.486 | 248.751 | 0.299 |
| sample_battle_14 | 166.015 | 164.735 | 0.244 |
| sample_battle_15 | 367.280 | 362.880 | 0.441 |

The external CLI wall includes startup/exit and up to 5 seconds of monitor polling tail. The log timer surrounds the existing `compare` operation; report-directory preparation and Python imports precede it. Source freezing/environment capture, subsequent review rendering, saved-state replay, browser tests and manual review are excluded. Thus the sum is measured processing-stage time, not total elapsed time of this audit session. Each video was acquired once in sequence, without resume. OS file-cache warmth and machine load were not controlled; no repeated-run confidence interval or speedup against an old version is claimed.

## Record categories and runtime limitations

| Video | Gameplay semantic candidates | HUD observations | Other observations | Deferred | Partial application | Log entries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| sample_battle_13 | 31 | 240 | 132 | 6 | 6 | 0 |
| sample_battle_14 | 14 | 524 | 22 | 1 | 3 | 0 |
| sample_battle_15 | 114 | 935 | 25 | 312 | 18 | 0 |

Gameplay candidates total **159**; HUD/preview/entry/trainer observations total **1,878**. These are machine categories, not verified actual gameplay events. Application statuses overlap those categories. There are **319 deferred and 27 partial** records overall, including B15’s 312 deferred records. Predicted move executions: **6 / 3 / 29** for B13/B14/B15; these are detection counts, not recall denominators.

No repeated event IDs were found; semantic extra/duplicate detections remain **unmeasured**. The selector’s `provisional_or_repeat` count combines unresolved fragments and repeated observations and is not a duplicate count. All raw message observations and per-source occurrence decisions remain available.

No runtime failure or warning/fallback lines were found by the recorded log scan. The event-driven OCR backend is fixed ONNX CPU, with no Tesseract fallback invoked. Normal unknown-phase fallback checkpoints were **37 / 25 / 35**; exact crop-cache hits were **0 / 0 / 0**, while unchanged-region reading reuse was **278 / 388 / 582**. This is within-run scheduling/reuse, not imported previous predictions.

Existing automatic Battle Log Pass B completed separately and extracted **0 / 0 / 0 entries**. Whether the videos did not display readable logs or detection missed them needs original-video review. Log event-type accuracy and complete-log coverage are unmeasured; automatic log/live agreement would not be independent ground truth. Log inspection timestamps never become original action times or correct the sealed live states.

Production output contains a legacy generic disclaimer about pre-existing recognition context/not being held-out. It was preserved unchanged; actual input/cache isolation is established by the fresh directories, commands, cold-run flags and manifests for these new videos. Technical completion does not supersede any semantic limitation.

## Human review and accuracy

No verified event annotations or checkpoint truth exist yet: **0 annotated events, 0 annotated checkpoints**. These are review-progress counts, not 0% accuracy. Event precision/recall, strict text, species/form/slot, user/target, move, HP, special-mechanic and state accuracy are all **pending** per video and pooled. No overall percentage is reported.

Use each compact review guide to annotate the original video independently of predictions, then compare field-by-field. Each guide links the complete source video, existing screenshot/timeline viewers, CSV prediction and state worksheets, and an empty separate `ground-truth.json`. Missing events are entered in truth, not constrained to the prediction list. The guide defines exhaustively reviewed intervals, one-to-one occurrence matching and each numerator/denominator; it distinguishes correct recognition, wrong attribution, missing, extra/duplicate, wrong semantics and wrong state.

- [Battle 13 review guide](battles/sample_battle_13/evaluation/fresh-heldout-20261026-v1-review/review.md)
- [Battle 14 review guide](battles/sample_battle_14/evaluation/fresh-heldout-20261026-v1-review/review.md)
- [Battle 15 review guide](battles/sample_battle_15/evaluation/fresh-heldout-20261026-v1-review/review.md)

## Traceability and validation

- [Frozen plan, hardware, dependencies, dirty status and input/source hashes](../.cache/fresh-video-benchmark-20261026-v1/plan.json). Exact execution commands and per-run logs are under `.cache/battles/<battle_id>/evaluation/fresh-heldout-20261026-v1/`.
- [Machine-readable measurements and pooled totals](../.cache/fresh-video-benchmark-20261026-v1/summary.json); raw observations, per-crop OCR, source PTS/decoder logs, sealed events and states: `.cache/battles/<battle_id>/event-driven/fresh-heldout-20261026-v1/`.
- [Artifact verification](../.cache/fresh-video-benchmark-20261026-v1/validation.json): saved screenshot hashes, prediction/annotation row counts and every sealed output; each saved-event replay reproduces all receipt statuses/bindings/state hashes and final state, with zero duplicate-active-instance violations. This is internal reproducibility, not recognition accuracy.
- Offline Chrome checks passed all six existing viewer modes and all referenced unique PNGs: **617 / 599 / 1,419**. Browser checks did not create human labels. Two existing offline-evaluator regression tests passed. Runtime/source hashes remained unchanged through acquisition and postprocessing.

Commands (all acquisitions are complete; do not start them again):

```sh
# Original acquisition command, once per n=13,14,15:
.venv/bin/python -u scripts/run_production_evaluation.py --battle sample_battle_13 --run-id fresh-heldout-20261026-v1
# This launches: main.py --video tests/fixtures/sample_battle_13.mp4 --profile event-driven --run-id fresh-heldout-20261026-v1
# Safe saved-output review regeneration; reuses verified completed timelines and preserves annotation CSV/JSON:
.venv/bin/python scripts/summarize_fresh_video_benchmark.py --plan .cache/fresh-video-benchmark-20261026-v1/plan.json --stage review
```

For browser video seeking, reuse an existing local review server or run `.venv/bin/python scripts/serve_visual_review.py --port 8766` and open the linked review HTML paths via localhost. The server supports MP4 byte ranges. No new UI was built.

## Defensible resume metrics now

- “Benchmarked the production OCR parsing pipeline on **3 previously unused complete recordings totaling 25m 01.59s**, with **3/3 runs completing** without manual prediction correction.”
- “Processed **3,004 sampled frames from 50,654 source frames** at **3.82 sampled FPS pooled throughput** on Apple M1 Pro; combined measured CLI/log stages took **785.77 seconds**.”

Both describe throughput and technical completion. Do not claim high recognition accuracy or fully correct unattended battle reconstruction until the independent review is complete. No algorithm tuning, parsing fixes, commit or push was performed.
