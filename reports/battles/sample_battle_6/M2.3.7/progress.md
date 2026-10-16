# M2.3.7 completion and recoverability

All artifact stages completed on 2026-10-16. **Semantic acceptance remains pending independent human review.** Full report, turns JSON and offline viewer are under this directory; the requested top-level names are compatibility links.

Battle 6: 753.75s; 1,807 distinct source-PTS frames; all 1,508 base 2-FPS cells present. Baseline: 6,724 OCR and 2,154 icon attempts, 78 message candidates, 18 move candidates, 10 instance-bound admissions and zero target bindings. The current baseline creates 11 command-cycle proposals. A separate post-baseline visual diagnostic proposes eight action groups and 32 source-backed notes, including Hoshi WIN / REIKOU LOSE. None is independent ground truth or a runtime lookup/state correction.

Validation: 68 focused regression tests passed. Offline Chrome outside the repository decoded all 1,801 distinct image assets and exercised 70 representative groups, actual annotation download/import, reload persistence and the human override for incorrect overlay classifications. Final preservation verified 3,453 historical paths and 73 frozen source dependencies. Battle 5 annotations/results/seals and the pending M236 feedback-summary work remain unchanged. No commit/push or damage/Speed/prior changes.

Source, sampling, prediction ledgers, archived recognition runner, archived reconstruction adapter, baseline prediction seal, raw replay and validation receipts are durable under `.cache/battles/sample_battle_6/m237/`. `completion.json` records exact hashes, costs, limits and commands. The fractional 3-FPS seek failure and integer-boundary caller adjustment are retained in `acquisition-adjustment.json`; successful 2-FPS chunks were reused. No diagnostic reran OCR or video decoding.

No job is required to resume the human review. Open `review/review.html`, import an exported `m237-event-review-annotations.json`, and export notes regularly. Corrections remain separate from predictions/state. False overlay classifications can be overridden for frame-review controls without changing detector output.

```sh
.venv/bin/python scripts/process_m237.py --stage verify
.venv/bin/python scripts/process_m237.py --stage deliver
node scripts/verify_m237_review.cjs
```

`deliver` is cache-only and preserves human annotation files; it regenerates presentation from saved predictions/diagnostics. Successful completed stages verify their hashes before reuse. Before any expensive resume, check processes and stage manifests; do not launch a duplicate job.

Remaining: independent event/turn review; status-overlay false positives that hide readable live messages; move-description routing; missed moves, withdrawals and fainting; stale weather/terrain from unsupported end messages; possible repeated-announcement splitting; and outcome extraction. Baseline facts and the eight visual groupings are explicitly provisional. Do not count a successful replay/browser check as semantic accuracy, relax admission rules or start a new milestone without scope.
