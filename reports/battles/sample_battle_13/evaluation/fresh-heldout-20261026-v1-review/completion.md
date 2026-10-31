# sample_battle_13 — frozen production evaluation

[Offline HTML review](review.html). Run: `fresh-heldout-20261026-v1`. Evaluation: `fresh-heldout-20261026-v1-review`.

Review status: **pending**. An exact saved-event replay reproduced every original application status, state hash and final state. This establishes reproducibility, not independent correctness. Duplicate active-instance violations: 0. Runtime predictions are unchanged; review annotations are separate.

622 saved observations, 403 event records. Application statuses: `{"recorded_observation": 137, "deferred": 6, "applied_candidate": 254, "applied_partial": 6}`. Contradictions: 0.

Command checks: 6 eligible frames, 0 attempts; slot outcomes `{}`; 0 actual corrections. One attempt per scheduled command phase; ambiguous single-frame identities cannot repair occupancy.

Deferred reasons: `{"message_episode_occupancy_unresolved": 4, "unresolved_candidate_fields": 2}`. Deferred and partially applied records remain unresolved unless individually reviewed.

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
    "/Users/yyi/Pokemon-Champions-Assistant/tests/fixtures/sample_battle_13.mp4",
    "--profile",
    "event-driven",
    "--run-id",
    "fresh-heldout-20261026-v1"
  ],
  "first_pass": true,
  "resumed": false,
  "peak_process_tree_rss_mb": 765.65625,
  "wall_seconds": 251.48639012489002,
  "notes": "No cached observations, frame cache or prediction cache supplied.",
  "pid": 28395,
  "returncode": 0,
  "frozen_runtime_unchanged": true,
  "video_unchanged": true,
  "production_counts": {
    "ocr_invocations_performed": 1626,
    "icon_invocations_performed": 248,
    "frames_materialized_at_2fps": 695,
    "cheap_monitor_frames": 695,
    "frames_sampled": 622,
    "frames_classified": 622,
    "phase:unknown": 183,
    "unknown_inspection_frames": 183,
    "unknown_fallback_checkpoints": 37,
    "inspected_frames_at_2fps": 543,
    "frames_without_model_ocr": 166,
    "frames_rejected_before_ocr": 155,
    "frame_rejected:empty_or_animation_or_menu": 131,
    "region_selected:newly_visible": 122,
    "field_condition_reading_invocations": 375,
    "ocr_read_requests": 1400,
    "ocr_prediction_requests": 1626,
    "ocr_invocations_attempted": 1626,
    "ocr_seconds": 85.71378438908141,
    "phase:team_configuration": 7,
    "battle_message_ocr_invocations": 178,
    "icon_invocations_attempted": 248,
    "icon_seconds": 81.79283046117052,
    "player_team_acquisitions": 1,
    "region_rejected:unchanged_region": 78,
    "message_ocr_invocations_avoided_unchanged": 30,
    "ocr_invocations_avoided_unchanged": 308,
    "region_selected:retry_unreliable": 32,
    "frame_rejected:unchanged_regions": 22,
    "phase:team_preview": 178,
    "trainer_label_read_requests": 2,
    "opponent_preview_acquisitions": 113,
    "region_selected:changed_region": 604,
    "ocr_region_reads_reused": 278,
    "ability_banner_reading_invocations": 42,
    "hud_hp_reading_invocations": 240,
    "phase:battle_animation": 141,
    "phase:battle_message": 46,
    "phase:battle_screen": 21,
    "inspected_frames_at_1fps": 79,
    "frames_not_inspected_adaptive_1fps": 73,
    "phase:move_selection": 30,
    "phase:move_target_selection": 11,
    "frame_rejected:full_screen_flash": 2,
    "phase:pokemon_selection": 2,
    "phase:switch_selection": 3,
    "source_decoded_frames": 12007
  },
  "decoder": {
    "source_decoded_frames": 12007,
    "command": [
      "/Users/yyi/Pokemon-Champions-Assistant/.venv/lib/python3.10/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1",
      "-hide_banner",
      "-loglevel",
      "info",
      "-threads",
      "2",
      "-i",
      "/Users/yyi/Pokemon-Champions-Assistant/tests/fixtures/sample_battle_13.mp4",
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
    "container_duration_seconds": 347.23
  },
  "cold_end_to_end_wall_seconds": 248.7509412909858,
  "timeline_replay_seconds": 34.130137583008036,
  "video_seconds_per_wall_second": 1.3807108998127613
}
```

Original screenshots, chronological events, four-slot prefix timeline, trainer/roster/alias evidence, transitions, checkpoint receipts and exact deferred reasons are available in the HTML. Images are relative links to the retained original cache. No live network is needed. Chinese text is original battle evidence. Snapshot matching is not a measured recognition accuracy score.

Production command: `.venv/bin/python main.py --video tests/fixtures/sample_battle_13.mp4 --profile event-driven --run-id fresh-heldout-20261026-v1`. Reuse the existing completed run; do not reacquire it. Frozen source, first-pass fingerprints, execution logs and process-tree memory measurements are retained under the battle's evaluation namespace. Reporting uses saved events only, with decoding/OCR/icons blocked.
