# sample_battle_14 — frozen production evaluation

[Offline HTML review](review.html). Run: `fresh-heldout-20261026-v1`. Evaluation: `fresh-heldout-20261026-v1-review`.

Review status: **pending**. An exact saved-event replay reproduced every original application status, state hash and final state. This establishes reproducibility, not independent correctness. Duplicate active-instance violations: 0. Runtime predictions are unchanged; review annotations are separate.

599 saved observations, 560 event records. Application statuses: `{"recorded_observation": 25, "applied_candidate": 531, "applied_partial": 3, "deferred": 1}`. Contradictions: 0.

Command checks: 7 eligible frames, 0 attempts; slot outcomes `{}`; 0 actual corrections. One attempt per scheduled command phase; ambiguous single-frame identities cannot repair occupancy.

Deferred reasons: `{"unresolved_candidate_fields": 1}`. Deferred and partially applied records remain unresolved unless individually reviewed.

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
    "/Users/yyi/Pokemon-Champions-Assistant/tests/fixtures/sample_battle_14.mp4",
    "--profile",
    "event-driven",
    "--run-id",
    "fresh-heldout-20261026-v1"
  ],
  "first_pass": true,
  "resumed": false,
  "peak_process_tree_rss_mb": 752.3125,
  "wall_seconds": 166.01469395903405,
  "notes": "No cached observations, frame cache or prediction cache supplied.",
  "pid": 28587,
  "returncode": 0,
  "frozen_runtime_unchanged": true,
  "video_unchanged": true,
  "production_counts": {
    "ocr_invocations_performed": 1752,
    "icon_invocations_performed": 36,
    "frames_materialized_at_2fps": 651,
    "cheap_monitor_frames": 651,
    "frames_sampled": 599,
    "frames_classified": 599,
    "phase:team_preview": 127,
    "ocr_read_requests": 1614,
    "ocr_prediction_requests": 1752,
    "ocr_invocations_attempted": 1752,
    "ocr_seconds": 90.9157321464736,
    "trainer_label_read_requests": 2,
    "region_selected:newly_visible": 106,
    "field_condition_reading_invocations": 257,
    "icon_invocations_attempted": 36,
    "icon_seconds": 9.490047543193214,
    "opponent_preview_acquisitions": 1,
    "inspected_frames_at_2fps": 543,
    "region_selected:changed_region": 768,
    "ocr_region_reads_reused": 388,
    "ocr_invocations_avoided_unchanged": 482,
    "region_selected:retry_unreliable": 29,
    "region_rejected:unchanged_region": 169,
    "frames_without_model_ocr": 182,
    "frames_rejected_before_ocr": 158,
    "frame_rejected:unchanged_regions": 42,
    "phase:unknown": 109,
    "battle_message_ocr_invocations": 163,
    "ability_banner_reading_invocations": 37,
    "unknown_inspection_frames": 109,
    "unknown_fallback_checkpoints": 25,
    "message_ocr_invocations_avoided_unchanged": 94,
    "phase:battle_animation": 160,
    "phase:battle_screen": 138,
    "frame_rejected:empty_or_animation_or_menu": 115,
    "phase:battle_message": 35,
    "hud_hp_reading_invocations": 524,
    "inspected_frames_at_1fps": 56,
    "frames_not_inspected_adaptive_1fps": 52,
    "phase:move_selection": 4,
    "phase:move_target_selection": 11,
    "frame_rejected:full_screen_flash": 1,
    "phase:pokemon_selection": 2,
    "phase:switch_selection": 11,
    "phase:team_configuration": 2,
    "player_team_acquisitions": 2,
    "source_decoded_frames": 10861
  },
  "decoder": {
    "source_decoded_frames": 10861,
    "command": [
      "/Users/yyi/Pokemon-Champions-Assistant/.venv/lib/python3.10/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1",
      "-hide_banner",
      "-loglevel",
      "info",
      "-threads",
      "2",
      "-i",
      "/Users/yyi/Pokemon-Champions-Assistant/tests/fixtures/sample_battle_14.mp4",
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
    "container_duration_seconds": 325.46
  },
  "cold_end_to_end_wall_seconds": 164.73495291697327,
  "timeline_replay_seconds": 20.771182833006606,
  "video_seconds_per_wall_second": 1.9604288767373255
}
```

Original screenshots, chronological events, four-slot prefix timeline, trainer/roster/alias evidence, transitions, checkpoint receipts and exact deferred reasons are available in the HTML. Images are relative links to the retained original cache. No live network is needed. Chinese text is original battle evidence. Snapshot matching is not a measured recognition accuracy score.

Production command: `.venv/bin/python main.py --video tests/fixtures/sample_battle_14.mp4 --profile event-driven --run-id fresh-heldout-20261026-v1`. Reuse the existing completed run; do not reacquire it. Frozen source, first-pass fingerprints, execution logs and process-tree memory measurements are retained under the battle's evaluation namespace. Reporting uses saved events only, with decoding/OCR/icons blocked.
