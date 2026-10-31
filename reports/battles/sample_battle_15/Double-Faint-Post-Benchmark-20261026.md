# B15 double-faint verification — post-benchmark

Run: `post-benchmark-double-faint-v3`; original: `fresh-heldout-20261026-v1`. Diagnostic repair of saved evidence, not held-out performance or a new cold throughput measurement.

At **460.001666667s**, independent name OCR and icon recognition of saved frame `000810.png` establish **opponent.left = Archaludon (1018)** and **opponent.right = Sneasler (903)**. Frame SHA256: `cae2ff95d5f9d8043ebc9dc64f32049d0cef506575ccee228df7671090934dc5`. Names read 铝钢桥龙 / 大狃拉; the existing text/icon fusion admits the lower-confidence Sneasler text with independently agreeing icon evidence. Two name OCR predictions and four icon profile inferences were performed on this one frame.

Stable instances: left `sample_battle_15:opponent:encounter:08ff67c8935ede73`; right `sample_battle_15:opponent:encounter:84f56977223aed6f`. Original species/form facts remain unchanged. Placements begin at visual confirmation; arrival receipts remain unplaced. Subsequent HP readings and messages bind to these instances. Their later faints at 802.526667s and 810.026667s now apply; neither remains active in the final state.

| Metric | Sealed before | Repaired after |
|---|---:|---:|
| Total event records | 1,074 | 1,074 |
| Deferred | 312 | 40 |
| message_episode_occupancy_unresolved | 287 | 29 |
| Rejected | 0 | 0 |
| Newly verified replacement instances | — | 2 |

Recovered **272 records**: 258 HUD observations, 10 move executions, 2 stat changes, 2 faints. Deferred reduction **87.18%**; occupancy-deferral reduction **89.90%**. These are record-application metrics, not recognition accuracy, gameplay-event recall or 272 unique gameplay actions. No new conflicts or previously admitted status regressions were found. Remaining 40 deferred records are outside this fix.

Implementation: `tracking/double_faint.py` derives the narrowly eligible pair from supported entry/departure episodes; `recognition/double_faint.py` uses the existing independent resolver, OCR/icon acquisition and fusion. `recognition/fast_video.py` schedules this scoped acquisition; `recognition/event_report.py` carries same-frame paired evidence; `tracking/evidence_fusion.py` applies atomic prospective placement. No announcement, faint, Speed or roster order supplies slot proof. Incomplete, conflicting and non-unique pairs abstain. Single replacements and withdrawals do not qualify.

Validation: **9 focused tests passed**; **77 portable related tests passed**, 1 historical-artifact test deselected in the portable run. When run separately with historical artifacts included, that test failed its old immutable-file hash audit for damage/data.py, damage/engine.py, knowledge data and speed_order files outside this change; it was not treated as missing. `git diff --check` and Python compilation passed. The unmodified B15 replay reproduced all original statuses, bindings and state hashes before repair. Original seal, predictions, replay, observations and manifest hashes remain unchanged; human annotations were not edited. Visual inspection confirms the reported pair in the saved source frame. This is scoped regression validation, not independent whole-video semantic acceptance.

Artifacts: [comparison and all changed record IDs](../../../.cache/battles/sample_battle_15/event-driven/post-benchmark-double-faint-v3/comparison.json), [repaired replay](../../../.cache/battles/sample_battle_15/event-driven/post-benchmark-double-faint-v3/replay.json), [manifest](../../../.cache/battles/sample_battle_15/event-driven/post-benchmark-double-faint-v3/repair-manifest.json). Earlier v1/v2 attempts remain local: v1 omitted the existing text/icon fusion and was interrupted; v2 was interrupted to correct a resolver attribute before acquisition. v3 is the completed result.

Reuse completed result:

```sh
.venv/bin/python scripts/replay_double_faint.py --battle sample_battle_15 --source-run fresh-heldout-20261026-v1 --run-id post-benchmark-double-faint-v3
```

No video re-decoding, general sampling/model changes, annotations, commit or push.
