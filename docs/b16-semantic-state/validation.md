# B16 semantic/state validation — 2026-10-27

Phases 1–5 completed. No commit/push. Source video unchanged. Existing unrelated
working-tree edits preserved. This is development/regression evaluation, not a
held-out or independent human accuracy result.

| Result | Measured value |
|---|---:|
| Video duration | 753.74 s |
| Cold normal CLI wall (reference/evaluation excluded) | 666.124 s |
| PTR | 0.8838 |
| Internal pipeline / final reconstruction-export stage | 665.341 / 178.869 s |
| Source-decoded / sampled / detailed-inspection frames | 30,216 / 1,508 / 1,276 |
| OCR / icon invocations | 4,204 / 126 |
| Candidate events / machine-deferred | 1,290 / 30 |
| Reference log views / raw row observations | 51 / 303 |
| Automatically assembled / manually recovered distinct rows | 90 / 28 |
| Distinct log rows / independent HUD zero checks | 118 / 3 |
| Event facts reproduced | 107/124 = 86.29% |
| Event facts actually applied | 97/124 = 78.23% |
| Key-state checkpoint fields reproduced | 154/191 = 80.63% |

The 10 recognized-but-not-applied event facts remain explicitly separate from
state application. Event comparisons: 97 applied, 10 recognized-only, 17 missing;
state comparisons: 154 applied, 8 recognized-only, 29 missing. No aligned incorrect
value/actor/side was established; unmatched live predictions are not a verified
whole-match false-positive denominator. Global machine-deferred=30 is a separate
population from these reference comparisons.

Production sampling remains 2 FPS; adaptive detailed inspection uses 1 FPS during
qualified COMMAND states. PP-OCRv6_medium_rec ONNX CPU and the latest double-faint
scheduler were used; all 20 ordinary prefix checks avoided replay. No imported
recognition, frames or state cache; automatic team acquisition only; no reference
facts supplied to the live pipeline. One exact crop hit arose within this run.
Old internal PTR≈2.365 used different semantic/scheduling code and enabled the
call profiler; this is not a controlled speedup experiment.

Reference construction was sealed before comparison and used fresh original-video
log pixels, separate HUD decoding and agent annotations; it never used live
predictions or EventParser to supply reference semantics. Shared OCR/geometry
remain a correlation risk. Of 303 raw rows, 280 have exact curated-row matches,
including 162 repeat observations; 23 fragments/OCR variants remain unresolved.
All 118 distinct readable records are retained. Eleven automatic scroll-overlap
issues led to pixel-reviewed recovery of 28 rows, rather than exclusion. The old
89-row baseline consequently has a different denominator.

Supported fields are scored after actual StateEngine transitions. Every per-event
hash, application status/reason and final state matched the sealed output.
Same-capture groups are matched without inventing within-frame action order from
lexicographic event IDs. A first evaluator version that imposed that order is
retained with its invalidation reason; the live prediction/reference never changed.
Verified full semantic snapshots are reused when only comparison/report code changes.

HP losses require same-instance observed endpoints; opponent percentages remain
percentages. Numeric damage/healing recovered 14/21 endpoint pairs; 3/3 independent
HUD-zero checks were missed. No numeric HP loss was attributed to a move/attacker.
Two explicit burn-residual notices remain missing rather than borrowing causality
from nearby numeric changes. Exact targets, absolute opponent HP, exact stat-stage
baselines, screen-left/right reference occupancy and Mega X/Y identity are not
credited. No Trick Room/terrain/weather-termination reference was available.
Tailwind activation and termination were both evaluated; durations stay unknown.

Validation: pre-run relevant suite 147 passed, 1 deselected. First portable sweep
2591 passed plus one synthetic-banner provenance fixture failure; the fixture now
uses banner source provenance and 56 related tests passed. Final portable sweep:
**2592 passed, 73 deselected**, 302.27s. Additional evaluator regressions: **5 passed**
(overlapping counts). One ccache environment warning. No full video/OCR rerun was
used to fix the fixture or evaluator. Independent HUD seeking initially failed
with OpenCV; targeted FFmpeg decoding completed without repeating live acquisition.

The remaining semantic/acquisition failures are accepted as measured limitations,
not hidden or tuned away after final comparison. Full per-category counts,
examples, resume commands, machine-readable facts, comparisons and provenance:

[Final report](../../reports/battles/sample_battle_16/evaluation/b16-semantic-state-20261027-v1/report.md)

[Historical baseline](baseline.md) · [Recovery/commands](progress.md) ·
[Exact cleanup inventory](cleanup-inventory.json) · [Deletion receipt](cleanup-result.json)
