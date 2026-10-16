# M2.3.8 implementation and acceptance record

Scope: scheduling, UI routing, identity continuity, literal effect endings, and an
independent historical-log comparison. Existing PP-OCRv6 preprocessing, weights,
Chinese/English reading, icon matching and canonical identity policy are reused.
No damage/Speed, priors or strategy work is included.

## Audit (2026-10-16)

The initial working tree contained uncommitted M2.3.7 and fast-profile work,
M2.3.6 human-feedback edits and three COMMAND illustrations. Preserve these.
The frozen Battle 6 namespace is `.cache/battles/sample_battle_6/m237/`; Battle 5
review inputs and outputs remain owned by their previous stages.
`fast-v1-cold-1` was interrupted, two v1 probes include a failed adapter call and
a completed bounded run. PID 8468 / child 8474 were already running
`fast-v2-cold-1` at audit; this task neither restarted nor stopped them. Their
existing artifacts and performance classifications must remain distinct.

The actual reusable entry point is `main.py -> recognition.fast_video.analyze`.
Reuse `fast_profile.inspect` for independent region visibility, `CachedOCR` and
`CachedIcons` for unchanged recognizers, `MessageOccurrences` for live-message
occurrences, `identity_events` / `evidence_fusion` / `StateEngine` for evidence and
state, and `battle_log.extract_view` / `assemble_views` for independent reference
extraction. Do not call the M2.3.7 baseline writer with changed source files.
The new opt-in profile owns a new run directory. Legacy fast scheduling stays
available for historical experiments.

## Implementation order and acceptance gates

1. Audit and preserve historical manifests/source seals.
2. Acquire six player rows from opening team configuration; opponent rows only
   at team preview. Rows, forms, unknowns and repeated species remain separate.
3. Monitor useful regions at 2 FPS. Confirmed COMMAND reduces ordinary inspection
   to 1 FPS; retain command state for two seconds of temporary label loss. A
   locally qualified live message overrides the reduced rate. The two label
   search bands come from supplied illustrations, not 3D scene positions.
4. Full HUD identity on entry/change/unresolved follow-up; HP-only readings retain
   original identity provenance. HUD disappearance does not vacate a slot.
5. Read changed message, banner and field regions independently.
6. Parse explicit termination statements; no UI disappearance expiry inference.
7. Reconstruct and seal video-only events before any reference extraction.
8. Extract historical log pages independently, retaining inspection timestamps,
   turn headers, scroll provenance, partial rows and overlap uncertainties.
9. Align events conservatively; unmatched predictions outside observed coverage
   are unscored. Human annotations stay separate from machine predictions.
10. Report measured runtime/cache reuse and focused regression results. A cached
    experiment is not a cold benchmark and cannot establish human correctness.

No full-video run is permitted until local tests cover COMMAND relocation/loss,
independent message eligibility, entry ordering/slot mapping, Ally Switch,
termination messages and Pass A/Pass B isolation. Reviewed slot mappings must
have explicit evidence; unverified mappings remain unresolved.

## Current invocation and recovery

The opening 32-second cache-assisted probe (`m238-team-probe-2`) completed in
41.957 seconds, with 106 new OCR crop predictions and 66 icon-profile predictions.
It acquired each six-row roster once. Its 21 spurious active-HUD scheduling
requests on prebattle team layouts exposed an ownership-routing bug, corrected
before the complete experiment. This probe is retained as a diagnostic, not a
performance baseline. `m238-team-probe-1` failed before recognition because the
COMMAND observation and scheduler both supplied `reason`; it is preserved too.

`m238-live-1` uses the already acquired Battle 6 2-FPS PNG grid. Pixel-level OCR
and icon predictions are reused from the compatible v2 run and opening probe.
Source version, model manifest, icon index, cache ownership and frame hashes are
checked. High-level interpretations, baseline state, human labels and historical
text are not imported. The run is cache-assisted; no cold-speed claim is valid.

```sh
.venv/bin/python main.py --video tests/fixtures/sample_battle_6.mp4 \
  --profile event-driven --run-id m238-live-1 \
  --frame-cache .cache/battles/sample_battle_6/m237/acquisition.json \
  --recognition-cache .cache/battles/sample_battle_6/fast/fast-v2-cold-1 \
    .cache/battles/sample_battle_6/event-driven/m238-team-probe-2
```

For an interrupted unchanged run, inspect its process and manifest, then append
`--resume` to exactly that command. Do not run it while its existing PID is active.
If the implementation changes, preserve the prefix and choose a new run ID;
compatible pixel predictions remain reusable. Source copies and per-frame
checkpoints live under `.cache/battles/sample_battle_6/event-driven/<run-id>/`.
A successful `video-only-seal.json` must exist before the independent command:

```sh
.venv/bin/python scripts/compare_battle_log.py \
  --battle-id sample_battle_6 --run-id m238-live-1
```

The reference stage checkpoints individual changed log views. An interrupted
unchanged extraction resumes with `--resume`. Its separate manifest pins Pass A's
prediction hash and the reference implementation. The viewer opens offline at
`reports/battles/sample_battle_6/event-driven/m238-live-1/review.html`.
Human annotation JSON is separate, importable/exportable and never consumed by
recognition. Log timestamps mean inspection time, never action time.

The CLI's ordinary reusable form uses the video directly (omit both cache
options). COMMAND pixels are searched in two normalized, fixture-verified bands
at the supported 1311×603 working scale. Hidden countdowns remain null. Cheap
monitor decisions are saved for every 2-FPS candidate, including command skips;
OCR decisions and actual next inspection rate are saved on inspected frames.

## Reviewed entry order

`tests/fixtures/battles/m238_entry_order.json` records agent inspection of Battle
5's literal opponent entry at 121.02s, own entry at 125.022s, and named HUDs at
140.023s. The opponent's first name is on the right HUD and the player's first
name on the left HUD. Existing StateEngine slots use screen-HUD left/right.
No rendered model coordinates or nickname-to-species answers enter the mapping.
This is one reviewed opening, not independent human acceptance or a general
identity-accuracy measurement. Single replacements use the engine's established
vacant-slot evidence; ambiguous side/order/nicknames stay unresolved.

## Report-stage correction before reference inspection

The first full cache-assisted run froze successfully before any historical text
extraction: 235.594 seconds including 90.006 seconds of replay, 1,306 inspections
covering the 753.75-second recording. It saved 17 supported ability-banner and
three supported selected-detail observations that the first report adapter did
not emit. That prediction remains immutable. Correct only the report adapter,
reuse its sealed compatible recognition stage, and freeze a second prediction:

```sh
.venv/bin/python main.py --video tests/fixtures/sample_battle_6.mp4 \
  --profile event-driven --run-id m238-live-2 \
  --reconstruct-from .cache/battles/sample_battle_6/event-driven/m238-live-1
```

This command runs no decoding, OCR or icon recognition. It verifies the source
seal, video and recognition dependencies and copies no historical reference
files. New source and prediction seals remain separate. Use `m238-live-2` for the
subsequent `compare_battle_log.py` command and final review package. Do not report
its replay-only runtime as full video-analysis runtime.
