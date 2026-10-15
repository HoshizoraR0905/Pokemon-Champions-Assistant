# Speed order constraints, v1

The standalone `speed_order` package evaluates exact effective Speed, inverts
verified order comparisons, and provides a read-only ordering query. It imports no
OCR/video code and requires no network. Existing damage APIs are unchanged.

```python
from speed_order import effective_speed, infer_speed, compare_speed
import json
request = json.load(open('examples/speed_order/infer.json'))['input']
request['candidate_speeds'] = range(50, 250)
result = infer_speed(**request)
# Opponent first against Speed 100 => feasible actual Speeds 100..249.
```

```sh
.venv/bin/python -m speed_order examples/speed_order/infer.json
.venv/bin/python -m speed_order examples/speed_order/compare.json
# Installed entry point: champions-speed-order [request.json]
```

The JSON envelope is `{operation: effective|infer|compare, input: {...}}`. Inference
and comparison accept exact integer lists; JSON also accepts inclusive
`{minimum, maximum}` domains. No domain is assumed unless an explicit `champions`
constraint object requests M3.1.2's legal-Speed generator. CLI exit 0 means a
completed computation or explicitly non-informative/non-Speed assessment; exit 2
means unsupported/insufficient information. Request/response JSON schemas ship in
`speed_order/schemas/`; semantic validation additionally enforces identities,
priority agreement, evidence, legal ranges and work bounds.

## Source scope and supported arithmetic

Profiles are explicit. `showdown-champions-reference-v1` uses the pinned Champions
reference, never a silent Gen 9 fallback. `champions-evidence-only-v1` deliberately
declines numerical Speed comparisons: general encyclopedia descriptions do not
independently verify Champions modifier rounding. Base priority metadata comes
from the existing pinned Champions knowledge catalog; different audited priority
brackets can be identified without computing Speed under either profile.

Actual unmodified Speed must be an integer 1..4095; stages must be -6..6. Within
that numerical bound, existing pure integer helpers apply stage floor/16-bit
behavior, chain fixed-point factors, and round half down. Factors are chained
before one rounding; paralysis halves with floor afterward (except Quick Feet).
The stage uses the supplied snapshot; Speed Boost adds no extra multiplier.

Supported modifiers are Tailwind; Swift Swim/rain, Chlorophyll/sun, Sand Rush/sand,
Slush Rush/snow; evidenced active/inactive Unburden; Surge Surfer/electric terrain;
Quick Feet/status; Choice Scarf; and Iron Ball. Explicit neutral abilities/items
are a closed allowlist in `core.py`; other mechanics are unsupported. Suppressed
abilities require `ability_active=false`. Unburden requires explicit activation
history and, when active, no held item. Item absence alone never activates it.
Other effects must be explicitly `[]`. Unknown/conflicting inputs remain unresolved.

**Reference cap discrepancy:** the existing pinned `@smogon/calc` 0.12.0
`getFinalSpeed` treats Champions generation 0 as <=2 for its cap and returns at
most 999. The pinned Showdown simulator allows 10000 and Champions reverses
Speed directly for Trick Room without the standard underflow behavior. Results
whose uncapped effective Speed exceeds 999 are therefore explicitly unsupported
in this implementation. A recorded modern-generation cap probe detects this
reference discrepancy only; it is not used as a Champions result or fallback.
All original oracle expectations are retained. Broader high-Speed support needs
an independently validated choice of Champions reference behavior.

Sources, revisions, package/source hashes and scope limits are pinned in
`speed_order/data/sources-v1.json`. The source set includes 52Poké's
[速度, revision 2616893](https://wiki.52poke.com/index.php?title=速度&oldid=2616893),
the existing @smogon/calc 0.12.0 Champions utility hashes and the Showdown
[Champions getActionSpeed](https://github.com/smogon/pokemon-showdown/blob/3a766f2cfb5e51c1e428cfe87d0dba91a8f01640/data/mods/champions/scripts.ts)
and [getStat](https://github.com/smogon/pokemon-showdown/blob/3a766f2cfb5e51c1e428cfe87d0dba91a8f01640/sim/pokemon.ts)
implementations. Generic wiki mechanics are supporting descriptions, not claims
of official Champions verification. Cached source snapshots remain local;
52Poké contributors retain CC BY-NC-SA 3.0 attribution. Executable references
retain their MIT attribution through existing source records.

## Context and evidence

A participant supplies exactly:
`identity`, `form`, `instance_id`, `actual_speed`, `stage`, `tailwind`, `ability`,
`ability_active`, `item`, `status`, `unburden_active`, `activation_evidence`,
`other_effects`. Species/forms resolve through the existing canonical knowledge
and stat utility; there is no second identity database. The opponent's template
actual Speed is replaced by each candidate. The comparison Pokémon's actual Speed
must be supplied when Speed matters.

A context supplies both `own` and `opponent` participants, `field`
(`weather`, `terrain`, `trick_room`, `other_effects`), `actions` for each participant,
`ordering_effects`, `timing`, `comparable`, and nonempty source `evidence`.
Each action records `kind`, `move`, `effective_priority` and `evidence`.
The audited ordinary move allowlist verifies supplied priority against the local
Champions catalog. Priority-changing abilities (Prankster, Gale Wings, Triage),
conditional/special moves such as Grassy Glide, and unsupported overrides are gated.

Timing records `turn`, `decision_id`, `state_at` and `modifier_changes`. A useful
pair needs `state_at='order_decision'`, no unverified within-decision modifier
changes, and `comparable=true`. End-of-turn snapshots and animation timestamps
cannot stand in for order-decision evidence. Different turns may supply different
stage/weather/item snapshots; no later state is applied retroactively. Mid-turn
recalculation is deliberately unverified and yields a non-informative pair.

An inference observation records `id`, `battle_id`, `stat_epoch`, a two-action
`sequence` (`['opponent','own']` or its reverse), `evidence_kind` and `context`.
Only `evidence_kind='verified_action_order'` provides a Speed comparison. All
observations must share battle, opponent instance, canonical form and stat epoch.
There is no cross-instance/species-only inference or automatic epoch conversion.
Evidence and comparability are explicit caller assertions, not recognition outputs.

Switches, unable/fainted actions, entering mid-turn, repeated/multi-action or forced
action kinds produce non-informative observations. They never invent inequalities.
Known unequal priorities are also non-informative for inverse Speed. Triggered
Quick Claw/Custap, late-order items, Stall, After You and Quash require dedicated
interaction handling. An explicitly evidenced active ordering effect yields
`non_speed_ordering`, with no Speed guarantee. Mere item presence does not establish
activation; such item contexts remain unsupported. Unknown effects stay unsupported.

## Feasibility and scenarios

For supported equal-priority actions, ties permit either sequence. Opponent-first
means opponent effective Speed >= own outside Trick Room, <= own inside it;
opponent-second reverses those non-strict inequalities. Multiple observations
share one underlying Speed, with stages applied separately.

Finite variables follow M3.1.1's shared/local semantics:

```json
{
  "id": "scarf",
  "scope": "shared",
  "observation_ids": ["order1", "later"],
  "path": "opponent.item",
  "values": ["none", "Choice Scarf"]
}
```

`shared` means one assignment across the listed observations; `observation` means
independent choices. Independent item/ability choices across multiple observations
also require nonempty `change_evidence`. The API cannot verify that evidence, but
never infers an item change from necessity. Read-only query variable bindings use
`observation_ids=['query']`. No variable may redefine inferred actual Speed or
participant identities. Bindings use existing scalar leaf fields only.

The solver computes the union of assignment-consistent intersections, not the
intersection of per-observation unions. All scenario assignments, informative flags,
compatible effective values and tie flags are retained. Per-observation marginal
sets are diagnostic, not the joint answer. An unsupported/unresolved branch makes
the complete feasible set unknown (`null`), with diagnostics; it is not dropped.
All-non-informative observations retain the candidate domain with that explicit
status. Empty sets include a deletion-minimal conflict where practical; checks are
capped at 128 observations and otherwise labeled nonminimal. No widening occurs.

Optional `champions={identity, form, ...}` reuses M3.1.2's exact Speed domain and
cross-stat point/alignment restrictions. With no numerical domain supplied, that
joint legal domain is enumerated. With an explicit numerical domain, the result
retains `numerical_feasible` separately and filters by the legal set. Compatible
compact training configurations preserve the shared 66-point budget and alignment.
This models training feasibility, not roster legality or a preferred build.

Defaults are 4096 candidate entries, 128 assignments and 100000 conservative
candidate × observation × assignment evaluations. Assignment/evaluation limits
are configurable up to 1024/1000000. Enumeration is deterministic. Equivalent
within-solve order requests are memoized; effective-Speed results and identities
use bounded process-local caches with copied outputs to prevent caller mutation.

## Decision-facing query

`compare_speed(context=..., opponent_speeds=..., profile=..., variables=...)`
quantifies over every candidate and supplied assignment before a guaranteed claim.
Statuses are `own_guaranteed_first`, `opponent_guaranteed_first`,
`speed_tie_possible`, `mixed_order_possible`, `non_speed_ordering`,
`insufficient_information` and `unsupported`, with a short explanation.

Guarantee booleans remain false on unresolved branches. Priority-based winners
are labeled non-Speed ordering. Tie resolution gives both orders without assigning
probabilities. `non_tie_possible_first`, `tie_only_uncertainty` and
`non_tie_order_varies` distinguish tie uncertainty from genuinely different
non-tie outcomes across candidate builds/scenarios. Detailed rows preserve their
source contexts. No move recommendation or strategy policy is added.

## Validation and recovery

```sh
.venv/bin/python -m pytest -q tests/test_speed_order.py
.venv/bin/python scripts/validate_speed_order.py --schema-library .cache/m31/schema-lib
```

The pinned Node adapter independently executes @smogon/calc's Speed utility and
the actual pinned Champions `getActionSpeed` method. It supplies raw stats and
activation flags directly, and verifies package source hashes. Ordinary tests use
saved fixtures without Node/network. `scripts/build_speed_fixtures.py` is an
explicit optional offline rebuild command, not part of inference or tests.

The validator prints progress and atomically checkpoints each completed reference
and benchmark stage under `.cache/m32/`, fingerprinted by code, schemas, data,
fixtures and relevant shared dependencies. Changed versions preserve older files.
Repeated commands reuse compatible stages; a later schema-enabled run still checks
previously unchecked stages. Failures record errors and preserve completed work.
`latest-validation.json` identifies the last completed run. Timings are measured,
not real-time guarantees. No video processing or automatic order extraction occurs.
