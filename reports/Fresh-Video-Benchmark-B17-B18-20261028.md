# Fresh B17/B18 video processing and performance benchmark

Initial pre-tuning run `fresh-b17-b18-20261028-v1`. Both recordings have no Battle Log. No independent accuracy labels were supplied or generated. Processing/replay consistency and observed HP coverage are separate from correctness.

| Metric | B17 | B18 |
|---|---:|---:|
| Video duration (s) | 529.71 | 421.58 |
| Source frames | 23799 | 12663 |
| Average source FPS | 44.933022 | 30.039973 |
| Sampled / monitored frames | 1060 | 844 |
| Detailed inspection frames | 1052 | 831 |
| OCR model invocations | 4307 | 3033 |
| Normal processing wall (s) | 474.530 | 751.730 |
| ms per sampled frame | 447.670 | 890.675 |
| ms per detailed frame | 451.074 | 904.608 |
| PTR | 0.8958 | 1.7831 |
| Effective sampled FPS | 2.234 | 1.123 |
| Move executions parsed / admitted | 19 / 15 | 13 / 13 |
| Complete HP endpoints / observed groups | 9 / 11 | 3 / 4 |
| Supported complete HP causal groups / groups | 6 / 11 | 3 / 4 |
| Deferred events / state conflicts | 218 / 3 | 3 / 0 |
| Rejected events | 1 | 0 |

Aggregate normal wall: **1226.260 s** over 951.29 video seconds. Pooled ms/sample: **644.044** (1904 samples); pooled ms/inspection: **651.227** (1883 inspections). Aggregate PTR **1.2890** and throughput **1.553 sampled frames/s** use summed numerators and denominators, not means of per-video rates.

## Measurement and frozen inputs

Actual production command: `main.py --video VIDEO --profile event-driven --identity-mode lightweight --sample-fps 2 --run-id fresh-b17-b18-20261028-v1`. PP-OCRv6 ONNX CPU; current HUD/message/banner/identity semantics and StateEngine. Source images normalize from 2622×1206 to 1311×603. Shared pinned models/icons/knowledge are permitted; per-battle frame/recognition/state caches began empty. These are new prediction-cache runs, not claims of cold OS filesystem caches.

External monotonic timing includes subprocess/import startup, source hashing/sampling/decoding, visual extraction, OCR/icons, parsing, identity/state reconstruction and normal viewer export. Input header inspection, derived HP projection, sealing, regression replay and report generation are outside this clock. Counts labelled sampled/monitored refer to all 2 FPS materialized frames; the legacy production field `frames_sampled` and stock summary `sampled_frames` actually count detailed inspections.

Container durations come from FFmpeg header text (0.01 s precision), matching the prior B16 PTR denominator convention; average stream FPS and header frame counts are separately preserved. No full-video preflight decoding was performed.

| Frozen input | B17 | B18 |
|---|---|---|
| Exact video path | `/Users/yyi/Pokemon-Champions-Assistant/tests/fixtures/sample_battle_17.mp4` | `/Users/yyi/Pokemon-Champions-Assistant/tests/fixtures/sample_battle_18.mp4` |
| Source SHA-256 | `30bca7722d20ca4d9c3f163d8dde804d47118006e10cb8c572153d4951cb8239` | `d40048026a628602d7ce2b97cd8adc361ada64e0acb99447471620d787121bf9` |
| Original resolution | 2622×1206 | 2622×1206 |

Host/execution metadata: `{'platform': 'macOS-26.3.1-arm64-arm-64bit', 'machine': 'arm64', 'python': '3.10.4 (v3.10.4:9d38120e33, Mar 23 2022, 17:29:05) [Clang 13.0.0 (clang-1300.0.29.30)]', 'logical_cpus': 8}`.

| Cross-check | B17 | B18 |
|---|---:|---:|
| Internal pipeline wall (s) | 473.906 | 750.661 |
| External minus internal (s) | 0.624 | 1.068 |
| Actual decoder source frames | 23799 | 12663 |
| Recorded OCR work (s) | 249.805 | 182.810 |
| Recorded icon work (s) | 4.386 | 249.852 |
| Icon recognition calls | 12 | 692 |
| Packaging/reconstruction through summary (s) | 141.197 | 241.492 |
| Separate HP projection (s; excluded) | 0.131 | 0.007 |
| Adaptive high-FPS passes / frames / seconds | 0 / 0 / 0 | 0 / 0 / 0 |

Targeted high-FPS inspection is an available separate tool, not integrated into the current normal command. It was not added to the untouched initial run or represented as integrated processing. The latest action-level HP projection is saved and timed separately from the sealed live receipts; no manual endpoint supplements are supplied.

The OCR/icon work counters are existing wall spans around recognition work, which may include initialization and I/O; they are not isolated CPU-time profiles. The packaging/reconstruction span begins before event adaptation and ends at summary creation, before the remainder of viewer export. It is a diagnostic subspan, not a replacement for external command wall time. Decoder work can overlap other work, so no additive CPU attribution is claimed.

## Comparison with prior B16

B16 previously measured normal PTR **0.8838** (666.124 s / 753.74 s). These measurements use the current implementation and different source durations, frame rates and battle content; 2 FPS/lightweight profile names alone do not establish equivalent work. Changes include the current sequential HP/causal enrichment and reconstruction implementation. Rate differences are descriptive observations, not isolated evidence that any one change caused a speedup or slowdown.

The archived B16 configuration is `event-driven-v1`; these fresh runs use `event-driven-banner-hp-v2`. Nominal 2 FPS/lightweight settings and the pinned OCR/icon manifest hashes are unchanged, while recognition/state/parser implementations differ. The latest B16 source-completed HP result additionally used separate targeted source evidence; these initial B17/B18 coverage counts have no such supplementary pass.

## Observable reconstruction and limits

- sample_battle_17: event types `{'preview_observation': 6, 'trainer_observation': 2, 'hud_observation': 1294, 'entry_observation': 7, 'send_out': 9, 'switch_out': 2, 'move_effect': 8, 'transformation': 2, 'move_execution': 19, 'side_condition_change': 5, 'effectiveness': 5, 'faint': 4, 'ability_activation': 2, 'stat_change': 3, 'item_activation': 2, 'visual_observation': 1, 'weather_change': 1}`; deferred reasons `{'message_episode_occupancy_unresolved': 211, 'unresolved_candidate_fields': 7}`; unresolved HP reasons `{'pre_action_hp_missing': 2, 'no_active_resolution_source': 1, 'final_visible_plateau_unresolved': 1, 'move_effect_or_self_cost_not_established': 3, 'source_event_not_admitted_or_bound': 2}`.
  Identity: 1126 actor-bound receipts, 9 entry episodes, 9 encounter instances. HP: 921 numeric observations, 22 nonzero segments. Example candidates `{}` are parser/projection predictions unless separately source-reviewed.
  [Per-battle report](battles/sample_battle_17/evaluation/fresh-b17-b18-20261028-v1/report.md) · [final state](battles/sample_battle_17/evaluation/fresh-b17-b18-20261028-v1/final-state-summary.json).
- sample_battle_18: event types `{'hud_observation': 691, 'preview_observation': 358, 'trainer_observation': 2, 'entry_observation': 6, 'send_out': 8, 'ability_activation': 3, 'stat_change': 7, 'move_execution': 13, 'move_effect': 6, 'side_condition_change': 2, 'switch_out': 4, 'weather_change': 1, 'effectiveness': 4, 'transformation': 1, 'faint': 1, 'item_activation': 1}`; deferred reasons `{'message_episode_occupancy_unresolved': 3}`; unresolved HP reasons `{'final_visible_plateau_unresolved': 1, 'resolution_window_still_open': 1}`.
  Identity: 731 actor-bound receipts, 8 entry episodes, 8 encounter instances. HP: 540 numeric observations, 7 nonzero segments. Example candidates `{}` are parser/projection predictions unless separately source-reviewed.
  [Per-battle report](battles/sample_battle_18/evaluation/fresh-b17-b18-20261028-v1/report.md) · [final state](battles/sample_battle_18/evaluation/fresh-b17-b18-20261028-v1/final-state-summary.json).

The action-level denominator uses observed HP action/target groups as in B16, including incomplete groups. It does not enumerate every actual damage event in the video. Unknown targets/causes, first readings with no baseline, unsettled final values and missing coverage remain unresolved. Ability/item activations do not automatically imply numeric HP changes. Opponent HP units remain displayed percentage points.

Both full-video CLI runs completed and their output inventories/source/model/configuration fingerprints were sealed before failure inspection. Event adaptation, full receipts/state/hash replay and HP projection/endpoint membership were reproduced afterward with no OCR or decoding. All protected historical B16 files remained byte-identical. These checks measure reproducibility rather than event/state accuracy. No Battle Log extraction/reconstruction/scoring or B16 replay was run.

A post-seal saved-frame review found phone Control Center overlays in both final frames despite stored `battle_animation` phase labels, and confirmed the visible Light Screen message associated with B17’s rejected condition receipt. The localized evidence, other conflicts and limits are documented in [source review](../docs/b17-b18-benchmark/source-review.md). These observations were not used to modify initial predictions or generate accuracy labels.

Provenance, checkpoints and resume commands: [benchmark notes](../docs/b17-b18-benchmark/progress.md). No production recognition rules were modified from these samples; no commit or push.

## Regression validation

preflight: **355 passed, 3 deselected** in 109.26 s. No selected failures/skips. Optional historical-artifact tests were deselected.
postflight: **355 passed, 3 deselected** in 121.13 s. No selected failures/skips. Optional historical-artifact tests were deselected.

Both commands returned zero. The reporting-only schema correction preserved the fingerprint-matched successful verification implementation and reran only report export; no video acquisition/OCR or state replay was repeated for it.
