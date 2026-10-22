# Deterministic action order v2 (M3.2.1)

The additive v2 API accepts manually prepared or synthetic structured evidence.
It does not import video recognition, OCR, StateEngine, the Bayesian engine or
metagame data. The original `effective_speed`, `compare_speed`, v1 `infer_speed`,
schemas and fixtures keep their numerical behavior. Existing M3.4.1 extraction
and probabilistic execution interfaces remain unchanged.

```python
from speed_order import configuration_domain, infer_speed, simulate_action_order

universe = configuration_domain(
    identity='Charizard', form='base', abilities=['Blaze', 'Solar Power'],
    items=['Charizardite X', 'Charizardite Y'])

result = infer_speed(
    schema_version=2, observations=prepared_observations,
    configurations=universe['configurations'],
    profile='showdown-champions-reference-v1')
```

`configuration_domain` reuses `champions_attainable_stats`, including known SP,
point domains, alignments, other-stat constraints and the shared 66-point budget.
It enumerates Speed SP/alignment projections, retaining compact other-stat domains
under one shared budget. Unspecified SP on other stats is not asserted to be zero.
Item alternatives must be supplied; ability alternatives must be native to the
canonical current form. Sourced replacement belongs in explicit state changes.
This is not roster/regulation certification. A direct finite configuration list
may instead declare hypothetical legal integer Speed inputs, as in scenarios A/B;
these ranges are not assertions about canonical species stats.

## Evidence contract

Typed contracts are in `speed_order/contracts.py`. The complete JSON shape is
in `speed_order/schemas/request-v2.json`; semantic cross-field checks are performed
at runtime. Prefer canonical KnowledgeBase IDs. Exact bilingual names resolve
through that same KnowledgeBase; result priority records use canonical move IDs.

Every observation explicitly supplies:

- `id`, `battle_id`, `decision_id` and stable `subject` individual ID.
- `state`: a participant map keyed by stable individual ID, plus a full field
  snapshot. Participants retain all v1 actor fields; `training`, `hp_full` and
  `grounded` are optional additional contexts. Unknown subject Speed/item/ability
  are null until bound by a shared configuration. Unknown other state requires
  explicit finite `alternatives`, or the answer remains unresolved.
- `actions`: the complete pending ordinary-action set at this decision. Each has
  a unique action ID, individual, canonical move, `kind="move"`,
  `outcome="completed"`, activation evidence, post-action `changes`, and provenance.
  Optional `effective_priorities` restricts the mechanically calculated bracket;
  an incompatible known bracket excludes a configuration, rather than generating
  a Speed inequality.
- `sequence`: a verified action-ID prefix. It can include the entire sequence.
  Missing unknown pending actions must not be represented as a complete set.
- `initial_changes`: documented changes before the first decision, including
  Mega transformations. Changes after an action belong to that action's `changes`.
- `alternatives`: finite per-observation temporal snapshots, each with `id`,
  `participants` patches and a `field` patch. An empty list means the supplied
  snapshot is fully specified. Persistent item/ability choices belong in shared
  configurations, not independent alternatives on each turn.
- `strict_speed`: separately certified pairs `[faster_action_id, slower_action_id]`
  requiring strictly greater effective Speed at their first simultaneous pending
  decision. This is never inferred from acting earlier. An empty list is ordinary
  tie-inclusive order evidence.
- `evidence`: nonempty source references, `basis` (direct/deduced/user requirement/
  synthetic/reference) and explicit confidence text. Confidence is provenance,
  not a likelihood or automatic evidence-admission score. The caller is responsible
  for supplying reliable order, snapshot timing and complete pending coverage.

No turn boundaries are detected. Observation list order is supplied chronology.
All observations in a solve must concern the same battle and individual. Each
configuration persists across that chronology. Evidenced item/ability changes and
Mega transformations update the carried subject state. Documented status/stage/
weather/terrain snapshots are per observation, not retroactively applied. Unburden
activation history is carried; it cannot be silently reselected between turns.
Optional configuration `persistent` binds initial `unburden_active` and
`activation_evidence`. Other persistent mechanics remain unsupported.

## Pending actions and changes

`simulate_action_order(state=..., actions=..., observed_order=..., ...)` returns
all compatible traces. At each decision it calculates three independent keys:
effective move priority, special within-bracket order rank, and effective Speed
(reversed under Trick Room). Tied best actions branch exhaustively. After each
completed action, supplied changes apply, then all remaining actions are evaluated
again. It never invents a tie winner. Per-step `before`, `after`, `pending_before`,
priority/override/Speed `metrics`, changes and `decision_index` preserve the exact
point at which each modifier applies. Speed diagnostics reuse the original stage,
fixed-point modifier chain and paralysis floor semantics.

Supported `set` changes target `field` or a stable individual. They cover stage,
paralysis/status, Tailwind, weather, terrain, Trick Room, supported abilities and
suppression/replacement, item changes, Unburden activation history and conditional
HP/grounding context. Changes are evidence, not inferred effects of the selected
move: submit each effect once. This prevents move/Battle Log double application.

`cancel` removes an explicitly identified pending action, with no order relation
asserted for the removed action. Interrupted, skipped, forced, switch, repeated,
multi-action and unresolved action kinds are gated. Provide a sourced cancellation
when appropriate; absence of an announcement does not establish cancellation.

## Priority and overrides

Move base priority comes from the existing versioned Champions KnowledgeBase.
The closed audited set extends v1 with Fake Out, Grassy Glide, Giga Drain and
Draining Kiss. Protect +4, Fake Out +3 and Trick Room -7 are covered. Prankster
adds 1 for status moves, Gale Wings adds 1 for Flying moves at explicitly full HP,
Triage adds 3 for audited heal-flag moves, and grounded Grassy Glide gains 1 on
grassy terrain. Unknown relevant conditions require finite state alternatives.
Suppression removes an ability's applicable effect. Unlisted moves/abilities
remain unresolved; their effects are not assumed neutral.

Each action has `activation={state, coverage_complete, evidence}`. For Quick Claw:

| State | Treatment |
| --- | --- |
| `activated` | Within-bracket early rank, even with low Speed; incompatible items excluded |
| `not_activated` | Ordinary rank only if `coverage_complete=true` |
| `unknown` | Both eligible ranks, no probabilities |

An incomplete observation with no recognized message stays `unknown`. Activation
is fixed for that action and persists through subsequent reordering/item loss.
It never changes move priority or Speed and cannot overtake a higher bracket.
Stall has a separate late rank, with ordinary Speed/ties within the same rank.
Combined Stall/Quick Claw interactions are deliberately unresolved. Custap Berry,
Lagging Tail and Full Incense are gated as unavailable in the pinned Champions
reference. Quick Draw, Mycelium Might and forced-order moves require additional
handlers; no generic neutral fallback is used.

## Forms and continuity

A `transform` change supplies `values={"forms": [canonical_mega_form, ...]}`. All
compatible stone/form branches remain possible. Canonical species membership,
catalog-required stone and form-dependent native ability are checked. Stable
individual ID, training domains, numerical alignment, held stone and activation
history persist. No second opponent instance is created. Repeated Mega changes,
incompatible species and missing training are rejected/gated.

`configuration_speed` is the original configured-form unmodified Speed;
`actual_speed` is current-form unmodified Speed; each decision's metrics contain
effective battle Speed. `form_stat_domains` records transformed unmodified stat
projections under the preserved training budget, rather than an invented complete
build. The closed weather-start subset (Drought/Drizzle/Sand Stream/Snow Warning)
updates weather on an active transformation. Other automatic ability side effects
require documented supported state changes or remain unresolved.

Charizard, Mega X and Mega Y all have base Speed 100 in the pinned catalog, so
their Speed under the same training is unchanged; their other stats and abilities
differ. Mega Swampert provides a regression where the form's Speed actually changes.

## Results and bounds

`feasible` is the exact set of original configured-form unmodified Speed integers,
with min/max, intervals and gaps. `per_form` separately summarizes form-specific
unmodified Speed values. `compatible_configurations` retains complete correlated
histories; `remaining_abilities/items` refer to initial hypotheses, while
`current_abilities/items` summarize final carried states. `tie_compatible` names
configurations where the subject can participate in a tied ordering decision.
Per-observation records distinguish accepted prefix configurations from those
that also survive all observations. `exclusions` and a nonminimal conflict list
explain an empty result; no constraints are widened to repair it.

`exact` means complete within the explicitly supplied finite universe and
provisional reference profile. It is not independent Champions certification.
An unsupported or unresolved viable branch produces `unresolved` with the full
feasible set null. Partial work/exclusions are diagnostic only. Schema/profile
mixing is rejected. Default bounds are 100,000 total simulation nodes/evaluations,
4,096 trace/history branches, 128 observations and 16 pending actions. Exceeding
a bound withholds the answer; no feasible configuration is silently truncated.
Larger explicit supported bounds can be selected. These are bounded exhaustive
evaluations, not guarantees of interactive latency.

The strict `champions-evidence-only-v1` profile still declines numerical evaluation.
The original >999 cap disagreement and reference rounding gates remain intact.
Sources, hashes, licensing and verification scope are in
`speed_order/data/sources-v2.json` and the [milestone report](../reports/M3.2.1-dynamic-action-order.md).

## Commands

```sh
.venv/bin/python -m speed_order examples/speed_order/v2/ordinary.json
.venv/bin/python -m speed_order examples/speed_order/v2/dynamic-paralysis.json
.venv/bin/python -m speed_order examples/speed_order/v2/mega-branches.json
.venv/bin/python -m pytest -q tests/test_dynamic_action_order.py tests/test_speed_order.py
.venv/bin/python scripts/validate_dynamic_action_order.py --schema-library .cache/m31/schema-lib
```

The validator checks v1 fixture hashes, saved reference sources, valid/invalid v2
schemas and small/moderate branching workloads. Atomic fingerprinted checkpoints
are in `.cache/m321/`; repeat the same command to resume/reuse completed stages.
No runtime network or recorded-video work is required. This milestone does not
provide the future M3.4.1 adapter or Bayesian/damage inference.


## M-C priority correction (2026-10-22)

Current Champions priorities: Fake Out +3, Follow Me +2, Rage Powder +2.
The Quark catalog's stale +3 fields for the two redirection moves are corrected
in the current M-C facts with retained upstream provenance, using
`knowledge/data/champions_priority_corrections.json`. The offline snapshot importer
preserves the correction; archived snapshots and other-generation data are
unchanged. Ordering coverage now accepts these two moves; their target-redirection
effects are not simulated by this change. Prankster still modifies status-move
priority normally. Source evidence, the 261-test result, and the historical replay
cache boundary are recorded in the final section of the
[M3.2.2 report](../reports/M3.2.2-real-speed-replay-validation.md).
