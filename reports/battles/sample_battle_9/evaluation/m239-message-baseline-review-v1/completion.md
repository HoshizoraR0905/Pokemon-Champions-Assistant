# sample_battle_9 — frozen production evaluation

[Offline HTML review](review.html). Run: `m239-message-baseline-v1`. Evaluation: `m239-message-baseline-review-v1`.

Review status: **pending**. An exact saved-event replay reproduced every original application status, state hash and final state. This establishes reproducibility, not independent correctness. Duplicate active-instance violations: 0. Runtime predictions are unchanged; review annotations are separate.

754 saved observations, 598 event records. Application statuses: `{"recorded_observation": 75, "applied_candidate": 506, "deferred": 3, "applied_partial": 14}`. Contradictions: 1.

Command checks: 31 eligible frames, 5 attempts; slot outcomes `{"match": 18, "identity_resolved": 2}`; 0 actual corrections. One attempt per scheduled command phase; ambiguous single-frame identities cannot repair occupancy.

Deferred reasons: `{"retained_hud_identity_unresolved": 1, "unresolved_candidate_fields": 2}`. Deferred and partially applied records remain unresolved unless individually reviewed.

## Findings

- Independent correctness review pending.

## Resources and reproducibility

```json
{
  "first_pass": true,
  "segments": [
    {
      "command": [
        "/Users/yyi/Pokemon-Champions-Assistant/.venv/bin/python",
        "-u",
        "/Users/yyi/Pokemon-Champions-Assistant/scripts/benchmark_production.py",
        "--battle",
        "sample_battle_9",
        "--run-id",
        "m239-message-baseline-v1",
        "--child"
      ],
      "resumed": false,
      "wall_seconds": 517.5955074169906,
      "peak_process_tree_rss_mb": 791.5,
      "pid": 43448,
      "returncode": 0
    }
  ],
  "status": "complete",
  "wall_seconds": 517.5955074169906,
  "peak_process_tree_rss_mb": 791.5,
  "frozen_runtime_unchanged": true,
  "video_unchanged": true,
  "production_counts": {
    "ocr_invocations_performed": 2651,
    "icon_invocations_performed": 600,
    "frames_materialized_at_2fps": 889,
    "cheap_monitor_frames": 889,
    "frames_sampled": 754,
    "frames_classified": 754,
    "phase:unknown": 125,
    "region_selected:newly_visible": 174,
    "field_condition_reading_invocations": 472,
    "ocr_read_requests": 2430,
    "ocr_prediction_requests": 2651,
    "ocr_invocations_attempted": 2651,
    "ocr_seconds": 132.78204039140837,
    "unknown_inspection_frames": 125,
    "unknown_fallback_checkpoints": 36,
    "inspected_frames_at_2fps": 614,
    "frames_without_model_ocr": 157,
    "frames_rejected_before_ocr": 149,
    "frame_rejected:empty_or_animation_or_menu": 128,
    "region_selected:changed_region": 980,
    "phase:battle_animation": 328,
    "ocr_region_reads_reused": 327,
    "ocr_invocations_avoided_unchanged": 356,
    "icon_invocations_attempted": 600,
    "icon_seconds": 239.81410725734895,
    "full_identity_recognition_invocations": 294,
    "hud_hp_reading_invocations": 527,
    "region_rejected:unchanged_region": 62,
    "region_selected:retry_unreliable": 19,
    "phase:team_preview": 145,
    "trainer_label_read_requests": 2,
    "opponent_preview_acquisitions": 1,
    "frame_rejected:unchanged_regions": 20,
    "ability_banner_reading_invocations": 39,
    "phase:battle_message": 39,
    "battle_message_ocr_invocations": 238,
    "phase:battle_screen": 49,
    "identity_reads_reused": 233,
    "inspected_frames_at_1fps": 140,
    "command_checkpoint_attempts": 5,
    "frames_not_inspected_adaptive_1fps": 135,
    "phase:move_selection": 50,
    "phase:move_target_selection": 8,
    "frame_rejected:full_screen_flash": 1,
    "message_ocr_invocations_avoided_unchanged": 29,
    "phase:pokemon_selection": 1,
    "phase:switch_selection": 9,
    "source_decoded_frames": 15814
  },
  "decoder": {
    "source_decoded_frames": 15814,
    "command": [
      "/Users/yyi/Pokemon-Champions-Assistant/.venv/lib/python3.10/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1",
      "-hide_banner",
      "-loglevel",
      "info",
      "-threads",
      "2",
      "-i",
      "/Users/yyi/Pokemon-Champions-Assistant/tests/fixtures/sample_battle_9.mp4",
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
    "container_duration_seconds": 444.25
  },
  "cold_end_to_end_wall_seconds": 512.8035428749863,
  "timeline_replay_seconds": 79.12168787501287,
  "video_seconds_per_wall_second": 0.858295703177537
}
```

Original screenshots, chronological events, four-slot prefix timeline, trainer/roster/alias evidence, transitions, checkpoint receipts and exact deferred reasons are available in the HTML. Images are relative links to the retained original cache. No live network is needed. Chinese text is original battle evidence. Snapshot matching is not a measured recognition accuracy score.

Production command: `.venv/bin/python main.py --video tests/fixtures/sample_battle_9.mp4 --profile event-driven --run-id m239-message-baseline-v1`. Reuse the existing completed run; do not reacquire it. Frozen source, first-pass fingerprints, execution logs and process-tree memory measurements are retained under the battle's evaluation namespace. Reporting uses saved events only, with decoding/OCR/icons blocked.
