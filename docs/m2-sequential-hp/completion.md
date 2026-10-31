# Five B16 HP episodes — source-backed completion, 2026-10-28

Final derived run: `b16-hp-completion-20261028-v6`.
[Per-case report](../../reports/battles/sample_battle_16/evaluation/b16-hp-completion-20261028-v6/report.md).
Manual review supplied diagnostic expectations, not numeric recognition input.
All new numeric endpoints came from the original video through the existing
PTS decoder, HUD visibility/refresh gates and HP-only OCR. No sealed prediction,
reference, state reconstruction or earlier evaluation was overwritten.

| Source / affected instance | Pre-event HP and provenance | Post-event HP and provenance | Delta | Complete |
|---|---|---|---:|---|
| 286.515 s, Sitrus Berry / opponent Pelipper | 37%, admitted HUD at 286.015 s | 62%, additional repeated source reads through 289.432 s | +25 percentage points | yes |
| 290.032 s, Weather Ball / opponent Garchomp | 100%, visible source HUD at 293.600 s before its decrease; not an initial-HP assumption | 67%, repeated source/native readings | −33 percentage points | yes |
| 443.508 s, Electro Shot / opponent Archaludon | 25%, three distinct onset frames at 457.260, 457.310, 457.360 s | 0%, visible source/native reads followed by faint | −25 percentage points | yes |
| 623.522 s, burn / own Pelipper | 100 absolute HP, admitted prior reading; source at 624.022 s also shows 100/164 before decreasing | 90/164, repeated source readings through 625.222 s | −10 HP | yes |
| 676.530 s, Weather Ball / opponent Pelipper | 62%, distinct onset reads at 680.232, 680.265, 680.332 s | 33%, repeated source/native readings | −29 percentage points | yes |

Source-event time is the message receipt, which can precede visible HP animation.
The report and `cases.json` retain exact event/instance IDs, entry/placement
bindings, original and supplementary frame paths, PTS, hashes, numeric units,
cause receipts and all original segment IDs. Full frames were also inspected:
the switch-in messages for Garchomp, Archaludon and Pelipper, the Berry banner,
the burn message and all five numeric outcomes agree with these source traces.

## Why the earlier episodes were incomplete

Berry and burn each had only one accepted final value at ordinary 2 FPS.
The HP card subsequently disappeared, leaving no second visible plateau frame.
The old projection required a repeated plateau or observed zero followed by
faint. The original correct readings were retained; additional source frames
confirm their stability rather than estimating an amount from a banner.

The three attack windows lacked admitted pre-action HP. Garchomp's first source
read at onset is visibly 100%. For the two returning Pokémon, a 20 FPS onset
pass finds repeated 25% / 62% before their values start to decrease. In particular,
Archaludon's first **5 FPS** source read is already 23%; the later ordinary 19%
read was also an animation fragment. Neither establishes the full action total.
The actual onset is 25%, making the defensible total −25 percentage points.

## General implementation

- `tracking/resolution_context.py` records switch-in baseline provenance in the
  existing read-only action projection. Stable earlier HP follows the same
  authoritative instance ID; explicit numeric off-field changes update it.
  Observed effects with no numeric amount invalidate carry. New entry HUD
  readings confirm/correct carry only before another potentially HP-affecting
  resolution; a first read after an attack is not called an entry confirmation.
- First entry exposes a conditional 100% hypothesis with
  `usable_as_numeric_baseline=False`. A first sighting does not prove an untouched
  history. This task needs no unobserved full-HP derivation: Garchomp has an actual
  full-scale source reading. No Regenerator, HP fraction, hidden item or possible
  ability changes a numeric baseline.
- `tracking/resolution_endpoints.py` accepts independent source evidence for
  endpoint completion. A non-full animation-onset baseline requires captured
  visibility onset, at least three distinct times spanning 0.1 s, gaps no larger
  than 0.25 s, and a subsequent decrease. Known/announced multi-hit actions cannot
  use this non-full onset shortcut. A partial or duplicated frame alone cannot
  establish it. Final stability retains the configured 0.4 s duration; a reliable
  final read may also finish at an admitted independent boundary within 0.5 s,
  absent an HP gap. A later credible numerical change invalidates the old plateau
  until stability or termination is established again. Conflicting known maxima/units still veto totals; an unknown
  maximum stays unknown and does not contradict a compatible absolute HP value.
- `recognition/resolution_sampling.py::endpoint_source_samples` verifies the
  source-video/frame hashes and binds physical HUD observations to existing
  entry and placement intervals. It rejects foreign battles and departed
  occupants, and follows admitted position-exchange receipts prospectively.
  A later exchange cannot change an earlier frame's occupant.
  `tracking/hp_causes.py` passes the optional endpoint observations
  to the same projection. They never become injected live event receipts.
- `scripts/evaluate_hp_completion.py` checkpoints binding, prediction, frozen
  membership comparison and reporting separately. It fingerprints raw sampled
  observation files, manifests, knowledge and implementation, and snapshots
  source files. Completed matching runs are reused; changed inputs need a new
  run ID. It performs no acquisition or OCR itself.

Existing identity rules remain authoritative: explicit instance references or
verified complete parties support persistence; matching species alone does not.
Some sealed B16 encounters still have unproven biological continuity. This task
does not silently merge them. Observed local 25% / 62% baselines resolve their
totals without that merge. Entry hazards, entry effects and the subsequent attack
keep independent source steps and use the post-entry-effect HP for the attack.

## Saved stages and resume

All seven source sampling manifests are complete under
`.cache/battles/sample_battle_16/hp-resolution-sampling/`:

| Suffix after `b16-hp-completion-` | Source interval | FPS |
|---|---|---:|
| `berry-20261028-v1` | 284–291 s | 5 |
| `garchomp-20261028-v1` | 280–299 s | 5 |
| `archaludon-20261028-v1` | 429–462 s | 5 |
| `return-pelipper-20261028-v1` | 665–685 s | 5 |
| `burn-20261028-v1` | 622–630 s | 5 |
| `archaludon-onset-20261028-v1` | 457.15–458.0 s | 20 |
| `pelipper-onset-20261028-v1` | 679.95–680.75 s | 20 |

Total: **468 frames, 121 HP read requests, 89 OCR model predictions, zero
full-screen OCR calls**. Ordinary acquisition remains 2 FPS. The last two
subsecond windows escalate only the missed onset, preserving pre-roll and PTS.
The sampling function itself was unchanged; adding the binding adapter later
changed the module's whole-file fingerprint. Do not invalidate or resample the
completed frames/OCR for that reason. Per-frame rows and manifests retain the
actual sampling implementation fingerprints.

The sampling function's AST was compared with the fingerprint-verified snapshot
of the earlier successful source probe and is identical. All other acquisition
dependencies still match the seven manifests. The final report directory retains
`sampling-implementation-check.json` with that check and
`manual-review-comparison.json` with all five manual diagnostics compared only
after prediction completed.

Cheap final projection/reuse command:

```sh
.venv/bin/python scripts/evaluate_hp_completion.py \
  --run-id b16-hp-completion-20261028-v6 \
  --sample-run b16-hp-completion-berry-20261028-v1 \
  --sample-run b16-hp-completion-garchomp-20261028-v1 \
  --sample-run b16-hp-completion-archaludon-20261028-v1 \
  --sample-run b16-hp-completion-return-pelipper-20261028-v1 \
  --sample-run b16-hp-completion-burn-20261028-v1 \
  --sample-run b16-hp-completion-archaludon-onset-20261028-v1 \
  --sample-run b16-hp-completion-pelipper-onset-20261028-v1
```

Final run files live in `.cache/battles/sample_battle_16/hp-completion/` and
`reports/battles/sample_battle_16/evaluation/`. Development v1–v5 are preserved;
later versions tighten unknown-maximum handling, concise provenance reporting
cache dependencies, position-exchange binding and contradictory-tail handling.
They are cheap projections over the same successful
sampling stages. No decoding/OCR was repeated for projection changes.

## Validation and limits

The final evaluation preserves the frozen **21 groups / 41 numeric segments**
exactly once and retains every previously complete total. Complete causal totals
are now **21/21**, versus 16/21 before this task. Full authoritative StateEngine
serialization, state and all event receipts are unchanged. Original recognition
metrics remain 120/124 event facts, 175/191 state fields, 18/21 original reference
numeric pairs and 3/3 observed HUD zeros. New source-backed completion is a
separate measurement, not a rewrite of those recognition metrics.

`tests/test_hp_completion.py` adds 22 portable cases covering source onset,
negative attribution, independent boundaries, same-instance carry/correction,
conditional first entry, supported/unknown off-field changes, separate hazards,
hash/occupancy checks and nonmutation. An intermediate integration run had nine
new fixture failures: direct state edits were rebuilt by replay, then the revised
fixture had no actual numeric change. The fixtures were corrected to preserve
identity without baseline HP and include a real changed segment. All 20 new
cases then passed (7.66 s). Final review added a source-binding regression for
position exchange; its focused adapter/event suite passed all 45 tests in 11.12 s.
The earlier integration passed 344 tests with 3 deselections in 90.78 s. Final
integration results including the exchange and contradictory-tail regressions
are recorded below. The last focused endpoint/action suite passed 49 tests in
20.15 s. Temporary console logs are retained under
`/tmp/m2-hp-completion-final-v6-20261028.log` and
`/tmp/m2-hp-completion-tail.log`; this document retains their essential results.

```sh
.venv/bin/python -m pytest -q tests/test_hp_completion.py tests/test_sequential_resolution.py tests/test_hp_resolutions.py tests/test_hp_attribution.py tests/test_banner_hp_tracking.py tests/test_semantic_state.py tests/test_evidence_fusion.py tests/test_battle_state.py tests/test_stateful_mechanics.py tests/test_knowledge_grounding.py tests/test_event_driven.py tests/test_b16_state_benchmark.py tests/test_scrolling_semantics.py tests/test_git_artifact_policy.py -m 'not local_artifacts'
```

Final result: **346 passed, 3 deselected in 97.54 s**. No selected test failed or
skipped. The three deselections are the optional historical-artifact cases.
Compilation and `git diff --check` passed. Final v6 source fingerprints and the
prior sealed replay / frozen action hashes were verified after reporting.
There is no active acquisition, evaluation or test job left to resume.

Opponent percentage deltas remain percentage points, with no exact-HP conversion.
The five supplied manual observations are diagnostic evidence; independent
21-case causal accuracy and real-video multi-hit behavior remain unmeasured.
No commit, push or later milestone was started.
