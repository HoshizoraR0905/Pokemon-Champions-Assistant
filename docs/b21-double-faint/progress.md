# B21 double-faint / command-HUD recovery — 2026-10-29

Authorized scope: retain low-confidence canonical send-out candidates without
identity/slot admission; confirm two replacements through existing independent
command-HUD names/icons; replay affected saved events. No global threshold,
single-replacement, recovery/miss/confusion/struggle/damage, sampling or performance
changes; no full video decoding/OCR, original benchmark writes, commit or push.

Before-source and protected-mechanics hashes are saved under
.cache/battles/sample_battle_21/diagnosis/double-faint-hud-20261029-v1/.

Implemented initial localized candidate retention and atomic HUD confirmation
in identity_modes.py, tracking/double_faint.py, recognition/double_faint.py and
a small StateEngine replay audit hook. Original identity allocation/continuity
functions are reused. Deferred raw message receipt is not retroactively promoted.

Initial checks:10 candidate regressions passed;32 existing double-faint/identity/
recognition workflow tests passed (2 ffmpeg sampling cases deliberately excluded).

Actual targeted recognition executed on saved frames/001062.png at536.006667:
2 independent name OCR calls,2 icon reads (4 default/silhouette computations).
Left rawOCR姆克鹰 confidence.999 +resolved icon398/pokemon398;
right rawOCR轰擂金刚猩 confidence.998 +resolved icon812/pokemon812.
Both use text_icon_agreement. No manually supplied mapping enters StateEngine.

Initial saved validation v1 is running or checkpointed via
scripts/validate_b21_double_faint.py --run-id double-faint-hud-20261029-v1.
Inspect manifest/process before restarting. Prefix checkpoint280 events through
535.506667 retains only one pending canonical candidate and no Staraptor encounter.
The final suffix/control replay and stability comparisons are still in progress.


Completed final validation:
- Final runtime retry guard shares candidate text/icon support with StateEngine.
  Unresolved candidate icons keep scheduling pending for later command frames.
- v1 preserved;final v2 reuses compatible280-event prefix, no-proof control and
  exact OCR/icon outputs. Candidate/pair function ASTs, input/seed/source/output
  identities checked. Final673-event recovered replay rerun;byte-identical to v1.
- Original194 persistent occupancy deferrals:192 resolved;2 at535.506667 remain
  before536.006667 confirmation. Eight later semantic records now bind, including
  partial move-revelation receipts. Suffix205->5 deferred;remaining send-out and
  two abilities are historically before proof and not retroactively promoted.
-468 originally accepted suffix receipts and390 numeric endpoints unchanged.
  All497 prior numeric control observations unchanged;192 additional HUD records.
-257 integrated checks and24 active-persistence checks passed. After retry guard,
  final29 focused checks passed, including13 candidate-workflow cases. Two
  unrelated FFmpeg sampling cases deliberately deselected. diff --check passed.
- Frozen benchmark/reference, prior focused diagnostic outputs and10 protected
  mechanics/sampling/continuity source files unchanged. No commit/push.
- No video decoding/full OCR/production CLI. Actual v1 reads:2 name OCR and2 icon
  reads (4 profile computations). Final v2 reused exact source/model cache hits.

Final report:docs/b21-double-faint/report.md. No pending required work or live job.
To verify completed output without rerunning recognition/replay:
.venv/bin/python scripts/validate_b21_double_faint.py --run-id double-faint-hud-20261029-v2 --reuse-run-id double-faint-hud-20261029-v1
