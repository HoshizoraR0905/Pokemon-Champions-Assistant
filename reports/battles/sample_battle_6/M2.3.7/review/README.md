# Battle 6 offline review

Open `review.html` in Chrome with `assets/` alongside it. No server/network is needed. This extends the repaired M236 portable viewer; the frozen automatic baseline has no independent ground truth.

Use the provisional-turn sidebar to select intervals, then chronological events or Advanced: all frames. Before/during/after buttons show cached source pixels inline. Open evidence details for OCR, icon candidates, receipts and state prefixes. Unknown targets and final outcome are not filled by assumptions.

Use the event controls for verdicts, event type, text, actor, target, identity, HP, status, ability/item, field conditions, fainting/switches, order and duplicate references. Turn controls preserve corrected boundaries and ordering separately. “Save missed-event review note” records an omitted action without altering the baseline.

The sidebar preserves baseline cycle proposals; the separate diagnostic summary is not independent ground truth. Tick **Override predicted overlay for this frame review** when the frozen detector incorrectly disables transcription controls. This changes notes only.

Export annotations regularly as `m237-event-review-annotations.json`; import to resume. Browser storage may be unavailable. No annotation file is overwritten by generation. Unknown fields and blank values survive import/export. Human judgments do not change raw predictions, state or baseline metrics.

All turn numbers and narrative conclusions are automated/provisional until independently reviewed. A sampled background interval does not prove no battle event occurred. Logs are historical, menu choices are not executions, and field counters have no inferred duration meaning.

Resume presentation only:

```sh
.venv/bin/python scripts/process_m237.py --stage deliver
```

Canonical report/JSON: `reports/battles/sample_battle_6/M2.3.7/`. Requested top-level names are compatibility links to these files. Assets are hash-addressed original PNG bytes, hard-linked to compatible caches when supported. Generated HTML/JSON/assets remain local under the existing Git policy. No commit/push.
