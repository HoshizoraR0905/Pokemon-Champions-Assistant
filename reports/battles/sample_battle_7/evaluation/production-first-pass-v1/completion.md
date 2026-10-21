# sample_battle_7 — frozen production evaluation

[Offline HTML review](review.html). Run: `production-first-pass-v1`. Evaluation: `production-first-pass-v1`.

Review status: **failed_material_state_reconstruction; repository cleanup stopped**. An exact saved-event replay reproduced every original application status, state hash and final state. This establishes reproducibility, not independent correctness. Duplicate active-instance violations: 0. Runtime predictions are unchanged; review annotations are separate.

1146 saved observations, 874 event records. Application statuses: `{"recorded_observation": 268, "applied_candidate": 541, "deferred": 42, "applied_partial": 23}`. Contradictions: 0.

Command checks: 6 eligible frames, 3 attempts; slot outcomes `{"inconclusive": 5, "match": 7}`; 0 actual corrections. One attempt per scheduled command phase; ambiguous single-frame identities cannot repair occupancy.

Deferred reasons: `{"unresolved_candidate_fields": 9, "retained_hud_identity_unresolved": 31, "actor_or_target_identity_unresolved": 2}`. Deferred and partially applied records remain unresolved unless individually reviewed.

## Findings

- P1 blocker: Papudo single replacement never acquires an accepted nickname/species binding or opponent.right occupancy. The 499.517s send-out and later Tailwind/Hurricane events remain deferred; the slot is still absent in final state despite clear Pelipper HUDs at 596s and 668.013s.
- P1 blocker: Two explicit burn messages are lost from major-status state: Garchomp at 194.000s and Archaludon at 420.503s. Message text and burn HUD icons are clear, but both events defer with actor_or_target_identity_unresolved; all final major_status fields remain unknown.
- P1 blocker: Self Reflect activation at 182.030s and opponent Light Screen activation at 324.022s are misclassified as stat_change with an empty stats list and deferred. The resulting state omits supported protection intervals. Opponent Light Screen expiry is later admitted without a recorded activation.
- P2 limitation: Cold production wall time is 849.658s for a 690.87s video (0.813 video-seconds per wall-second), exceeding its 695.87s target. External monitored wall time is 854.448s. Icon inference alone accounts for 409.929s; OCR inference is 192.806s; production replay is 146.780s.
- P2 limitation: Only six inspected frames pass the normal-command detector; three checkpoints produce 7 matches and 5 inconclusive outcomes, with no correction. Post-freeze visual review additionally finds five clear ordinary four-HUD command screens wrongly vetoed as status_overlay, plus a sixth normal-control screen with a countdown prompt. The sparse coverage is not solely a consecutive-frame issue.

## Resources and reproducibility

```json
{
  "status": "complete",
  "command": [
    "/Users/yyi/Pokemon-Champions-Assistant/.venv/bin/python",
    "-u",
    "/Users/yyi/Pokemon-Champions-Assistant/main.py",
    "--video",
    "/Users/yyi/Pokemon-Champions-Assistant/tests/fixtures/sample_battle_7.mp4",
    "--profile",
    "event-driven",
    "--run-id",
    "production-first-pass-v1"
  ],
  "first_pass": true,
  "resumed": false,
  "peak_process_tree_rss_mb": 785.296875,
  "wall_seconds": 854.4479336660006,
  "notes": "No cached observations, frame cache or prediction cache supplied.",
  "pid": 30761,
  "returncode": 0,
  "frozen_runtime_unchanged": true,
  "video_unchanged": true,
  "production_counts": {
    "ocr_invocations_performed": 3886,
    "icon_invocations_performed": 1052,
    "frames_materialized_at_2fps": 1382,
    "cheap_monitor_frames": 1382,
    "frames_sampled": 1146,
    "frames_classified": 1146,
    "phase:unknown": 174,
    "unknown_inspection_frames": 174,
    "unknown_fallback_checkpoints": 61,
    "inspected_frames_at_2fps": 897,
    "frames_without_model_ocr": 296,
    "frames_rejected_before_ocr": 269,
    "frame_rejected:empty_or_animation_or_menu": 238,
    "phase:team_configuration": 4,
    "region_selected:newly_visible": 325,
    "ocr_read_requests": 3590,
    "ocr_prediction_requests": 3887,
    "ocr_invocations_attempted": 3886,
    "ocr_seconds": 192.80579394189408,
    "battle_message_ocr_invocations": 439,
    "field_condition_reading_invocations": 569,
    "icon_invocations_attempted": 1052,
    "icon_seconds": 409.92900785285747,
    "player_team_acquisitions": 1,
    "region_rejected:unchanged_region": 138,
    "message_ocr_invocations_avoided_unchanged": 53,
    "ocr_invocations_avoided_unchanged": 610,
    "region_selected:retry_unreliable": 21,
    "ocr_exact_cache_hits": 1,
    "frame_rejected:unchanged_regions": 28,
    "full_identity_recognition_invocations": 520,
    "hud_hp_reading_invocations": 782,
    "phase:team_preview": 162,
    "trainer_label_read_requests": 2,
    "opponent_preview_acquisitions": 1,
    "region_selected:changed_region": 1266,
    "ocr_region_reads_reused": 557,
    "ability_banner_reading_invocations": 28,
    "phase:battle_animation": 464,
    "phase:battle_message": 137,
    "phase:battle_screen": 54,
    "command_checkpoint_attempts": 3,
    "identity_reads_reused": 262,
    "inspected_frames_at_1fps": 249,
    "phase:move_selection": 67,
    "frames_not_inspected_adaptive_1fps": 236,
    "phase:move_target_selection": 56,
    "frame_rejected:full_screen_flash": 3,
    "phase:pokemon_selection": 13,
    "phase:switch_selection": 15,
    "icon_region_reuses": 6,
    "source_decoded_frames": 29956
  },
  "decoder": {
    "source_decoded_frames": 29956,
    "command": [
      "/Users/yyi/Pokemon-Champions-Assistant/.venv/lib/python3.10/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1",
      "-hide_banner",
      "-loglevel",
      "info",
      "-threads",
      "2",
      "-i",
      "/Users/yyi/Pokemon-Champions-Assistant/tests/fixtures/sample_battle_7.mp4",
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
    "container_duration_seconds": 690.87
  },
  "cold_end_to_end_wall_seconds": 849.6576430830173,
  "timeline_replay_seconds": 141.44884804199683,
  "video_seconds_per_wall_second": 0.8085571663048314
}
```

Original screenshots, chronological events, four-slot prefix timeline, trainer/roster/alias evidence, transitions, checkpoint receipts and exact deferred reasons are available in the HTML. Images are relative links to the retained original cache. No live network is needed. Chinese text is original battle evidence. Snapshot matching is not a measured recognition accuracy score.

Production command: `.venv/bin/python main.py --video tests/fixtures/sample_battle_7.mp4 --profile event-driven --run-id production-first-pass-v1`. Reuse the existing completed run; do not reacquire it. Frozen source, first-pass fingerprints, execution logs and process-tree memory measurements are retained under the battle's evaluation namespace. Reporting uses saved events only, with decoding/OCR/icons blocked.
