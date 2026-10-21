# sample_battle_8 — frozen production evaluation

[Offline HTML review](review.html). Run: `m239-production-first-pass-v1`. Evaluation: `m239-acceptance-v1`.

Review status: **BLOCKED_BY_MATERIAL_STATE_ERRORS**. An exact saved-event replay reproduced every original application status, state hash and final state. This establishes reproducibility, not independent correctness. Duplicate active-instance violations: 0. Runtime predictions are unchanged; review annotations are separate.

697 saved observations, 417 event records. Application statuses: `{"recorded_observation": 242, "deferred": 19, "applied_candidate": 150, "applied_partial": 6}`. Contradictions: 0.

Command checks: 5 eligible frames, 1 attempts; slot outcomes `{"match": 2, "inconclusive": 2}`; 0 actual corrections. One attempt per scheduled command phase; ambiguous single-frame identities cannot repair occupancy.

Deferred reasons: `{"unresolved_candidate_fields": 15, "retained_hud_identity_unresolved": 3, "actor_or_target_identity_unresolved": 1}`. Deferred and partially applied records remain unresolved unless individually reviewed.

## Findings

- P0: Korean trainer/display references disappear from Chinese/English OCR. Both opening opponent send-outs defer; later withdrawals, replacements, sleep, faint and move actors cannot bind. The entire sealed state contains no opponent Pokemon instances, so neither opponent slot ever becomes occupied even provisionally.
- P1: Visible Chinese 喷火龙，回来！ starts left of the fixed message ROI at 279.013s. The ROI [288,413,839,481] is classified partial and never read. No self switch_out event is emitted. The 281.513s Archaludon send-out is unplaced/recorded; Charizard remains the predicted right occupant until HUD placement at 308.002s. Its old episode has no observed departure.
- P1: 日照变强了！ is visibly present and successfully OCR-read, but every occurrence is unknown/unemitted. Rain established at 119.503s remains the state weather through the observed sun interval until the later rain message at 264.012s. Ability 日照 is separately observed; this does not repair the missed explicit weather transition.
- P1: Visible 对对手的대쓰여너 / 效果绝佳！ loses its Korean name in OCR. The surviving 对对手的 / 效果绝佳！ is recorded with side=self, target_side=self and receiver_display_reference=对手的. Adjacent noisy readings produce additional opponent-side observations. No target instance or damage effect is applied, but the explicit opponent side is misreported.
- coverage_gap: The source inventory also contains an unemitted wake-up, later send-out, explicit 气势披带 survival and surrender/outcome text. Foreign identity loss, incomplete literal recognition and unsupported parser forms remain distinct from ordinary unreadable HUD deferrals. Their complete occurrence inventory is retained; no item, status or termination fact was invented.

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
        "sample_battle_8",
        "--run-id",
        "m239-production-first-pass-v1",
        "--child"
      ],
      "resumed": false,
      "wall_seconds": 442.2041139170178,
      "peak_process_tree_rss_mb": 879.703125,
      "pid": 40205,
      "returncode": 0
    }
  ],
  "status": "complete",
  "wall_seconds": 442.2041139170178,
  "peak_process_tree_rss_mb": 879.703125,
  "frozen_runtime_unchanged": true,
  "video_unchanged": true,
  "production_counts": {
    "ocr_invocations_performed": 2280,
    "icon_invocations_performed": 608,
    "frames_materialized_at_2fps": 801,
    "cheap_monitor_frames": 801,
    "frames_sampled": 697,
    "frames_classified": 697,
    "phase:unknown": 160,
    "unknown_inspection_frames": 160,
    "unknown_fallback_checkpoints": 43,
    "inspected_frames_at_2fps": 589,
    "frames_without_model_ocr": 180,
    "frames_rejected_before_ocr": 174,
    "frame_rejected:empty_or_animation_or_menu": 145,
    "region_selected:newly_visible": 170,
    "field_condition_reading_invocations": 379,
    "ocr_read_requests": 1988,
    "ocr_prediction_requests": 2280,
    "ocr_invocations_attempted": 2280,
    "ocr_seconds": 116.39720209274674,
    "phase:team_configuration": 4,
    "battle_message_ocr_invocations": 250,
    "icon_invocations_attempted": 608,
    "icon_seconds": 239.654126159905,
    "player_team_acquisitions": 1,
    "region_selected:retry_unreliable": 24,
    "region_rejected:unchanged_region": 51,
    "frame_rejected:unchanged_regions": 28,
    "region_selected:changed_region": 705,
    "phase:team_preview": 138,
    "trainer_label_read_requests": 4,
    "opponent_preview_acquisitions": 1,
    "ocr_region_reads_reused": 158,
    "ocr_invocations_avoided_unchanged": 178,
    "full_identity_recognition_invocations": 293,
    "hud_hp_reading_invocations": 354,
    "phase:battle_animation": 218,
    "ability_banner_reading_invocations": 32,
    "phase:battle_message": 94,
    "phase:battle_screen": 17,
    "inspected_frames_at_1fps": 108,
    "frames_not_inspected_adaptive_1fps": 104,
    "phase:move_selection": 28,
    "identity_reads_reused": 61,
    "phase:move_target_selection": 31,
    "icon_region_reuses": 1,
    "message_ocr_invocations_avoided_unchanged": 20,
    "command_checkpoint_attempts": 1,
    "frame_rejected:full_screen_flash": 1,
    "phase:switch_selection": 7,
    "source_decoded_frames": 21503
  },
  "decoder": {
    "source_decoded_frames": 21503,
    "command": [
      "/Users/yyi/Pokemon-Champions-Assistant/.venv/lib/python3.10/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1",
      "-hide_banner",
      "-loglevel",
      "info",
      "-threads",
      "2",
      "-i",
      "/Users/yyi/Pokemon-Champions-Assistant/tests/fixtures/sample_battle_8.mp4",
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
    "container_duration_seconds": 400.1
  },
  "cold_end_to_end_wall_seconds": 438.557515625027,
  "timeline_replay_seconds": 26.529767041967716,
  "video_seconds_per_wall_second": 0.9047857932752772
}
```

Original screenshots, chronological events, four-slot prefix timeline, trainer/roster/alias evidence, transitions, checkpoint receipts and exact deferred reasons are available in the HTML. Images are relative links to the retained original cache. No live network is needed. Chinese text is original battle evidence. Snapshot matching is not a measured recognition accuracy score.

Production command: `.venv/bin/python main.py --video tests/fixtures/sample_battle_8.mp4 --profile event-driven --run-id m239-production-first-pass-v1`. Reuse the existing completed run; do not reacquire it. Frozen source, first-pass fingerprints, execution logs and process-tree memory measurements are retained under the battle's evaluation namespace. Reporting uses saved events only, with decoding/OCR/icons blocked.
