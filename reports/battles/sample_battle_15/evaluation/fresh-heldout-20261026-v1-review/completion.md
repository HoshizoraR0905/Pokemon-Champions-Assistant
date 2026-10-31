# sample_battle_15 — frozen production evaluation

[Offline HTML review](review.html). Run: `fresh-heldout-20261026-v1`. Evaluation: `fresh-heldout-20261026-v1-review`.

Review status: **pending**. An exact saved-event replay reproduced every original application status, state hash and final state. This establishes reproducibility, not independent correctness. Duplicate active-instance violations: 0. Runtime predictions are unchanged; review annotations are separate.

1419 saved observations, 1074 event records. Application statuses: `{"recorded_observation": 62, "applied_candidate": 682, "deferred": 312, "applied_partial": 18}`. Contradictions: 0.

Command checks: 75 eligible frames, 0 attempts; slot outcomes `{}`; 0 actual corrections. One attempt per scheduled command phase; ambiguous single-frame identities cannot repair occupancy.

Deferred reasons: `{"unresolved_candidate_fields": 25, "message_episode_occupancy_unresolved": 287}`. Deferred and partially applied records remain unresolved unless individually reviewed.

## Findings

- Independent correctness review pending.

## Resources and reproducibility

```json
{
  "status": "complete",
  "command": [
    "/Users/yyi/Pokemon-Champions-Assistant/.venv/bin/python",
    "-u",
    "/Users/yyi/Pokemon-Champions-Assistant/main.py",
    "--video",
    "/Users/yyi/Pokemon-Champions-Assistant/tests/fixtures/sample_battle_15.mp4",
    "--profile",
    "event-driven",
    "--run-id",
    "fresh-heldout-20261026-v1"
  ],
  "first_pass": true,
  "resumed": false,
  "peak_process_tree_rss_mb": 717.546875,
  "wall_seconds": 367.28019637498073,
  "notes": "No cached observations, frame cache or prediction cache supplied.",
  "pid": 28700,
  "returncode": 0,
  "frozen_runtime_unchanged": true,
  "video_unchanged": true,
  "production_counts": {
    "ocr_invocations_performed": 3446,
    "icon_invocations_performed": 24,
    "frames_materialized_at_2fps": 1658,
    "cheap_monitor_frames": 1658,
    "frames_sampled": 1419,
    "frames_classified": 1419,
    "phase:team_preview": 164,
    "ocr_read_requests": 3442,
    "ocr_prediction_requests": 3446,
    "ocr_invocations_attempted": 3446,
    "ocr_seconds": 174.78482552198693,
    "trainer_label_read_requests": 4,
    "region_selected:newly_visible": 387,
    "ability_banner_reading_invocations": 45,
    "icon_invocations_attempted": 24,
    "icon_seconds": 8.292638372862712,
    "opponent_preview_acquisitions": 2,
    "inspected_frames_at_2fps": 1167,
    "field_condition_reading_invocations": 619,
    "region_selected:changed_region": 1476,
    "ocr_region_reads_reused": 582,
    "ocr_invocations_avoided_unchanged": 861,
    "frames_without_model_ocr": 419,
    "region_selected:retry_unreliable": 39,
    "region_rejected:unchanged_region": 347,
    "frames_rejected_before_ocr": 388,
    "frame_rejected:unchanged_regions": 126,
    "phase:unknown": 107,
    "battle_message_ocr_invocations": 546,
    "unknown_inspection_frames": 107,
    "unknown_fallback_checkpoints": 35,
    "message_ocr_invocations_avoided_unchanged": 279,
    "frame_rejected:empty_or_animation_or_menu": 260,
    "phase:battle_animation": 720,
    "phase:battle_message": 160,
    "hud_hp_reading_invocations": 935,
    "phase:battle_screen": 145,
    "inspected_frames_at_1fps": 252,
    "frames_not_inspected_adaptive_1fps": 239,
    "phase:move_selection": 68,
    "phase:move_target_selection": 34,
    "frame_rejected:full_screen_flash": 2,
    "phase:pokemon_selection": 5,
    "phase:switch_selection": 16,
    "source_decoded_frames": 27786
  },
  "decoder": {
    "source_decoded_frames": 27786,
    "command": [
      "/Users/yyi/Pokemon-Champions-Assistant/.venv/lib/python3.10/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1",
      "-hide_banner",
      "-loglevel",
      "info",
      "-threads",
      "2",
      "-i",
      "/Users/yyi/Pokemon-Champions-Assistant/tests/fixtures/sample_battle_15.mp4",
      "-an",
      "-vf",
      "showinfo@source=checksum=0,select='isnan(prev_selected_t)+gt(floor((t+0.0)*2+0.000000001),floor((prev_selected_t+0.0)*2+0.000000001))',scale=1311:603,showinfo@sample=checksum=0",
      "-fps_mode",
      "vfr",
      "-pix_fmt",
      "bgr24",
      "-f",
      "rawvideo",
      "pipe:1"
    ],
    "container_duration_seconds": 828.9
  },
  "cold_end_to_end_wall_seconds": 362.87992524995934,
  "timeline_replay_seconds": 80.12870358303189,
  "video_seconds_per_wall_second": 2.2568600435884134
}
```

Original screenshots, chronological events, four-slot prefix timeline, trainer/roster/alias evidence, transitions, checkpoint receipts and exact deferred reasons are available in the HTML. Images are relative links to the retained original cache. No live network is needed. Chinese text is original battle evidence. Snapshot matching is not a measured recognition accuracy score.

Production command: `.venv/bin/python main.py --video tests/fixtures/sample_battle_15.mp4 --profile event-driven --run-id fresh-heldout-20261026-v1`. Reuse the existing completed run; do not reacquire it. Frozen source, first-pass fingerprints, execution logs and process-tree memory measurements are retained under the battle's evaluation namespace. Reporting uses saved events only, with decoding/OCR/icons blocked.
