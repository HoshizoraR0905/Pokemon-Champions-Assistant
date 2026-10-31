# Previous B16 baseline retained before authorized cleanup

2026-10-27. Historical run: `b16-auto-eval-20261026-v1`; full audit:
`b16-full-audit-20261027-v1`. This is a concise historical summary, not an
independent reference or an input to the new live pipeline.

- Original video 753.74 seconds; internal normal-pipeline time 1782.653 seconds,
  PTR 2.3651. External CLI time 1784.249 seconds, PTR 2.3672. Separate Log pass
  59.434 seconds. Old run enabled the call profiler.
- All 89 extracted log rows: 55 applied (61.80%), 14 recognized but not fully
  applied, 12 seen in OCR but not correctly structured, 8 not reconstructed.
  These are row-level audit counts, not the new event/state-fact denominators.
- 45 log views, 89 assembled records, 10 assembly issues. Shared OCR/parser
  and agent pixel review were involved; no independent human accuracy claim.
- 20 unnecessary prefix replays: 13,903 event applications, 1174.290 seconds.
  Final replay: 1276 events, 136.600 seconds. Current double-faint scheduler
  gates ordinary prefixes before reconstruction; genuine candidates can still
  require replay. No controlled end-to-end speedup was established.
- New evaluation is development/regression: B16 already guided improvements.

Old generated caches/reports are intentionally invalidated by the user's explicit
request for a fresh run. Shared models, source video, source/tests/scripts and
unrelated battles are preserved. Exact cleanup inventory and results are stored
beside this file. Historical commands referring to deleted runs cannot resume.
