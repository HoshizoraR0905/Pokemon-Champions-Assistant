# M3.5.4 — Team speed-control context and hidden numeric SP

A controlled offline experiment, separate from battle inference and the no-SP
review interface. It uses 197 original complete Incineroar occurrences, keeps
occurrence multiplicity, and predicts Speed SP, Attack SP and defensive SP total
independently. No missing-SP application record enters supervised training.

```sh
.venv/bin/python -m experiments.team_speed_context.run
.venv/bin/python -m pytest -q tests/test_team_speed_context.py \
  tests/test_no_sp_archetypes.py tests/test_moveset_diagnostics.py \
  tests/test_git_artifact_policy.py
```

Use the existing NumPy 2.2.6 / Matplotlib 3.10.9 environment documented in
`../build_similarity/requirements.txt`. No new ML framework or network retrieval
is needed. All paths below are relative to the repository root.

## Frozen design and inputs

`preregistered.json` records the local design before target/context relationships
or model performance were inspected. This is not a public statistical registration.
The feature definitions, threshold 100, alpha 10, outer/permutation seeds,
fractions, interaction gate and ablations are fixed, with no outer-fold tuning.

Required preserved local inputs:

- `.cache/research/m351/7933afbb341cdbeddbe3/population.json` and manifest;
- `.cache/research/m353/cd20fc295b0e5cb16e15/frozen.json` and manifest;
- the existing pinned ability snapshots identified in
  `speed_order/data/sources-v2.json` under `.cache/m341-actions/sources/`.

The M3.5.3 cache already joins all five original teammates by publication/member
ordinal. The adapter validates occurrence identity, configuration, supplied SP,
teammate ordinals, source-stage hashes and original/stronger source-group counts.
It preserves the 192 original M3.5.1 group IDs and evaluates with 187 stronger
M3.5.3 connected groups. Group sizes are 179 singletons, six pairs and two triples.
Those connected units are a leakage-control approximation, not proof of independence.

Original full records and response values are retained separately from feature
views. The latter expose only target moves/item and teammates' canonical
species/form, moves, ability, item, nature and provenance. Target nature, target
or teammate SP, calculated stats and SP cluster memberships are never encoded.

## Capability features and uncertainty

`features.py` implements 11 nonexclusive features: Tailwind/Trick Room counts,
weather setters, observed weather-Speed abilities and compatible pairs, native
base-Speed count, priority-support presence and teammate Taunt count.

Presence is one when supported by any known positive, even if another teammate
is unknown. Exact counts are unknown if any unresolved member could change them.
Missing values remain null in the feature dataset and blank in the CSV export.
A missing ability choice is not replaced with a legal species option. A pinned
native domain can rule out an impossible ability without asserting an unobserved
choice as present.

Weather uses supported Drought/Drizzle and Chlorophyll/Swift Swim profiles.
An observed compatible required stone and fixed native Mega ability establish
only a conditional option. A supplied original ability can remain available
before Mega; an unknown original ability is not guessed. Two roles both requiring
Mega remain unresolved. No Mega or brought subset is selected by this experiment.
Manual Sunny Day/Rain Dance without a supported automatic setter leaves weather
support unknown in this narrow definition; no new move-effect data is retrieved.

Natural Speed uses pinned pre-Mega/native base Speed >=100, never teammate SP or
assumed Mega stats. Priority support is deliberately limited to the registered
four-move set and compatible observed Prankster with a qualifying observed Status
move. Existing corrected move priorities and the conditional Champions reference
are reused. This does not certify activation, immunity, actual match usage,
comprehensive mechanics coverage or official in-game behavior.

## Evaluation and overfitting checks

- A predicts training medians. B encodes target moves/item with Ridge. C adds all
  context. Five family additions test individual context families on top of B.
- Each of three fixed seeds defines five source-grouped folds. All models share
  splits. Every vocabulary, imputation, scale and coefficient is fitted only on
  training observations. Alpha is fixed at 10; there is no tuning grid search.
- Ridge response columns are independent. Marginal clipping uses SP ranges
  0–32 and bulk 0–66, without constructing a legal joint build or full-SP prior.
- Unknown context uses training-only median imputation (zero fallback if all
  training values are missing) plus explicit missingness columns. Unseen own
  categories never expand a training vocabulary.
- Three pre-specified interactions are tested separately only when the training
  fold contains at least 10 positive and 10 negative connected groups. All three
  lack support here; no special interaction coefficient is fitted.
- Six controls per outer fold permute whole coherent training-group context
  blocks within equal multiplicity strata. Own inputs/targets do not move;
  held-out context is untouched and never supplies donors. Unexchangeable strata
  and random fixed points are recorded. No formal p-value is claimed.
- Nested learning fractions 0.35/0.65/1.0 retain all observations of selected
  source groups. Preprocessing is refitted at each size on the same outer test
  fold. Fixed alpha has different relative strength at different sample sizes.
- Errors are paired on identical held-out observations. Occurrence-weighted and
  equal-source-group errors, rare-target subgroups, training gaps, per-seed
  variation and standardized coefficient variation are saved.

The synthetic numeric fixtures used by unit tests check implementation behavior;
they are not research observations, generated Pokémon builds or training priors.

## Outputs, checkpoints and resume

The [milestone report](../../milestone_reports/M3.5.4_Team_Speed_Control_and_SP_Prediction.md)
contains actual results, feature counts, controls, curves, ablations and source-linked
case studies. Lightweight CSV/JSON and scientific figures live under
`milestone_reports/assets/m354/`. Numeric prediction rows retain the original
occurrence ID, source group, seed/fold, true value, three predictions and errors.

Complete intermediate records, fold training IDs, preprocessing receipts,
coefficients, training predictions and permutation donor maps remain local under
`.cache/research/m354/<fingerprint>/`. `latest.json` points to a completed run.
The manifest records identity, stage status/hashes/errors and exact resume commands.
A run lock prevents duplicate jobs; atomic writes preserve completed folds when a
later report stage fails. Re-run the same command to reuse compatible checkpoints.
Report-only changes regenerate presentation assets without refitting folds.

```sh
.venv/bin/python -m experiments.team_speed_context.run \
  --m351 .cache/research/m351/7933afbb341cdbeddbe3 \
  --m353 .cache/research/m353/cd20fc295b0e5cb16e15 \
  --output .cache/research/m354 \
  --report milestone_reports/M3.5.4_Team_Speed_Control_and_SP_Prediction.md
```

Protected source, predictor, review-annotation, solver, knowledge and inference
files are hashed before and after a run. They are never opened for writing.
Concurrent external changes are reported instead of overwritten. Output paths
inside source/annotation namespaces are rejected. No no-SP prediction, human
review, empirical probability, cluster, embedding, battle evidence or replay is
updated. Stop at this experiment; more complex models and live integration remain
outside scope.
