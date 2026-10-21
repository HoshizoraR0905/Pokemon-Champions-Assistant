# M3.4.1 offline Bayesian Speed inference

`speed_inference` keeps a finite configuration posterior separate from recognition
and StateEngine mutation. It reuses `knowledge.champions_stats.ChampionsStats` for
unmodified Speed and `speed_order.core.evaluate_order` for ordering. It does not
read either M3.3 database, use empirical priors, infer damage stats, or recommend
moves. The implementation is offline; no runtime network requests are needed.

## Run

From the repository's existing environment:

```sh
.venv/bin/python -m speed_inference controlled --output .cache/m341/controlled.json
.venv/bin/python -m speed_inference infer examples/speed_inference/controlled.json --output .cache/m341/reproduced.json
.venv/bin/python -m speed_inference audit --battle 6
.venv/bin/python -m pytest -q tests/test_speed_inference.py
```

The installed entry point is `champions-speed-inference`. The `audit` subcommand
requires the repository's saved battle workspace and `battle_artifacts.py`.
It selects exactly one existing run for one battle. It performs no OCR, extraction,
StateEngine replay, or mutation of source artifacts. Output ownership is enforced
through `BattleArtifacts`. Audit manifests fingerprint source events/replay/manifest,
new implementation and maintained Speed/stat dependencies. Complete compatible
results with a matching output SHA are reused. Failed stages record an error and
can be resumed with the same command; previous fingerprint directories remain intact.

## Configuration prior

A candidate comprises current species/form, Speed SP, numerical Stat Alignment,
and optional evidenced finite persistent item/ability alternatives. Explicit current
form is required; a species does not implicitly mean its base form. The maintained
rules allow SP 0–32 per stat, total at most 66, and 21 numerical alignments: one
neutral, plus 20 distinct ordered increase/decrease pairs among five non-HP stats.
No IV/EV or generic Generation 9 stat formula is introduced.

The default prior is uniform over these **Speed-relevant configuration projections**,
not over Speed values or full six-stat builds. Unknown other SP are existential:
there must be a legal completion, but completions do not contribute multiplicity
and missing allocations are not recorded as zero. Known partial allocations reduce
the remaining budget. This leaves room for a future joint-stat model without
pretending the current prior is uniform over its larger sample space.

For base Charizard there are 33 × 21 = 693 default candidates, with unmodified
Speed 108–167. Thirteen alignments leave Speed neutral and four each increase or
decrease it. Integer rounding adds further multiplicity differences; the induced
Speed marginal is nonuniform. Configuration weights and the resulting Speed
marginal are both exported. Equal numerical neutral nature names are not counted
as separate selectable Stat Alignments.

An unknown item/ability is `null`, never `none`. An observation must establish its
current value or provide a finite domain with `coverage: complete_given_evidence`
and provenance. Such domains must be legal under the pinned current-form catalog;
they are explicitly conditional hypotheses, not guesses at a complete pool of
possible opponent builds. Native abilities must match that catalog, and required
Mega items must match the current form. Ability transfer/suppression beyond the
existing model and item transitions across persistent hypotheses require explicit
model/epoch review. No unsupported hypothesis is discarded to force a result.

## Evidence and mechanics contract

The request example shows all required fields. Each observation carries immutable
underlying action IDs, battle and individual IDs, stat epoch, observed sequence,
source provenance, origin (`recorded` or `synthetic`), and explicit verification of
actor, move, same-turn membership, chronology, priority, decision snapshot, ordering
exceptions, continuity, and own unmodified Speed. These are caller assertions
requiring supporting evidence; the library cannot certify video annotations.
It checks the own Speed against the maintained legal stat projection and checks
identities/form consistency. It never infers own unmodified Speed from a HUD.
The M3.2 allowlist checks move priority; species-specific equipped move membership
must be established by the caller's move evidence, not inferred from a learnset.

The default `champions-evidence-only-v1` profile declines numerical updates:
independent Champions-specific effective-Speed rounding and tie/order semantics
are not established. Only an explicit `showdown-champions-reference-v1` request
permits **conditional provisional reference** updates. The maintained M3.2
provenance and the newly pinned tie-source policy are included in every snapshot.
No provisional outcome is labeled independently verified in-game mechanics.

Within that reference profile, supported equal-priority ordinary actions use
likelihood 1 for the matching strict order, 0 for the reverse, and 1/2 for ties.
Trick Room reverses the strict comparison while ties retain 1/2. Existing M3.2
code supplies stages, Tailwind, supported weather/terrain abilities, evidenced
Unburden, Scarf, Iron Ball and paralysis, including its exact rounding and gates.
Speed Boost requires an already evidenced stage. Above effective Speed 999 the
existing reference disagreement is excluded. Unknown modifier state, unsupported
abilities/items, priority differences, ordering overrides, switches, repeated/failed
actions, and unverified changes during a turn do not update the posterior.

At most **one pair per individual per turn** is accepted, even under different
ordering decision labels. Tie ranks from one shuffle are correlated; multiplying
two pairwise halves could give 1/4 where a three-way first-place event has
probability 1/3. Shared underlying action IDs are also rejected. This deliberately
conservative sampling policy excludes some potentially informative evidence until
a joint ordering likelihood is audited.

## State, arithmetic and persistence

`configuration_space(...)` creates a reproducible fingerprinted model;
`SpeedBelief(model, battle_id=..., instance_id=..., stat_epoch=...)` retains its
log weights and evidence ledger. `update(observation)` returns admission reasons,
per-configuration likelihoods, predictive likelihood, and before/after summaries.
`infer(...)` processes a chronological bounded list. The default candidate bound is
20,000 (explicit hard ceiling 200,000), list bound 10,000 and batch work bound
1,000,000 candidate-observation pairs. Long work can use explicit incremental
updates/checkpoints rather than an unbounded batch.

`BeliefBank` keys beliefs by battle, individual and stat epoch. The same established
individual continues across switches without resetting. Same-species uncertain
individuals are never merged; changed form/epoch requires explicit registration.
Duplicate IDs do not update, changed payloads require explicit replay, and reused
action IDs, dependent same-turn pairs and backward turn submissions are excluded.
Revision/retraction handling is deliberate reconstruction and chronological replay,
not an unverified online StateEngine hook.

Updates use log-sum-exp and deterministic ordering. A displayed probability may
underflow to zero while its finite log weight remains in positive support. An
all-zero likelihood records a contradiction and freezes updates. `posterior_defined`
is then false; retained distributions are labeled last-consistent diagnostic weights,
not a posterior for contradictory evidence. There is no reset or smoothing.

`summary()` reports the marginal, mean, all MAP ties, a deterministic lowest MAP
representative, and a discrete equal-tailed 95% interval (configurable mass).
Intervals are conditional model summaries, not accuracy or empirical sample
confidence intervals. Speed-marginal KL and configuration KL are reported separately;
a successful constant-likelihood update may have zero information gain.
`export()` includes model, full configuration weights, prior, history, source policy,
mechanics provenance and posterior. JSON is atomically written by the CLI.
`SpeedBelief.restore(snapshot)` reconstructs/replays and rejects inconsistent
posteriors, model fingerprints or changed ordering provenance/policy.
