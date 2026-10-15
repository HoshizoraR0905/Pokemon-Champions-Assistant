# Forward damage contract v1

M3.1 is an offline Python component, independent of OCR, tracker state, video,
recommendations and probabilistic opponent inference. The implementation is
exact **within its supported provisional reference model**. It does not label
community-derived mechanics as verified Champions mechanics.

## Sources and profiles

| Source | Pin and role | Limits / license |
| --- | --- | --- |
| Existing `knowledge/data` | Entities SHA `27b5fac46d4b8d5805476f4fd1d491efab1c8ae49e2b15e63cae8dfd6a0f16c5`; full knowledge manifest hash pinned in `damage/data/manifest.json` | Existing PokéAPI localization/identity, Quark Champions facts and official regulation evidence remain authoritative for their stated scopes; existing licenses retained |
| [PokéAPI v2 documentation](https://pokeapi.co/docs/v2) and existing localization snapshot | Repository commit `81d20919845b6a445969b9265aab5cec6b04cece` in shared knowledge manifest; canonical species/form/move/ability/item namespace | Localization/identity/static resource semantics, not a Champions mechanics specification; BSD-3-Clause repository attribution already present |
| [`@smogon/calc`](https://github.com/smogon/damage-calc) | npm **0.12.0**, **Champions generation 0**; package integrity/transitive versions in oracle lockfile; executable JS/data hashes in damage manifest | Community provisional reference, MIT; included `damage/data/LICENSE.smogon.txt` |
| [Inspected Champions source](https://github.com/smogon/damage-calc/blob/9c57e9b8c1d8a7403b71c10042136ea5e001593b/calc/src/mechanics/champions.ts) | Inspected Git revision `9c57e9b8c1d8a7403b71c10042136ea5e001593b`; executable npm-file hashes, not moving master, define oracle behavior | Source inspection is not proof of official Champions conformance |
| [Showdown battle actions](https://github.com/smogon/pokemon-showdown/blob/master/sim/battle-actions.ts) | Evaluated as a mechanics source; not used as the pinned runtime implementation | A battle simulator's latest standard generation is not automatically Champions |
| [52poke damage page](https://wiki.52poke.com/w/index.php?title=%E4%BC%A4%E5%AE%B3&oldid=2617717) | Revision **2617717**, retrieved 2026-10-15; snapshot hash in fixture manifest | Community explanation and two independently documented full-roll examples. Its modifier section identifies Gen 9-era scope; not official Champions verification. Page text/images are not vendored |
| Official [battle](https://www.pokemonchampions.jp/ja/battle/) and [training](https://www.pokemonchampions.jp/ja/training/) pages | Reviewed 2026-10-15; existing official availability/regulation snapshot remains in shared knowledge | Establish battle formats/training context, not complete integer formula or SP conversions |

`champions-evidence-only-v1` returns `unsupported` for numerical damage: no
independently verified Champions formula/rounding rule set is pinned.
`showdown-champions-reference-v1` uses the dedicated Champions path in the pinned
oracle, not Gen 9. Successful results have status `exact_reference` and explicit
provisional provenance. Neither profile silently changes into the other.

## Data separation

`damage/data/reference-v1.json` is a canonical-ID supplement, not a second name
or identity database. Exact resolution reuses `KnowledgeBase`, normalized English,
Chinese and existing aliases. Bare numeric move IDs are rejected; use e.g.
`pokeapi:move:89`. No approximate move/species guesses are accepted. Canonical `pokeapi:pokemon:<id>` identities use the existing identity index to establish their unique variant; IDs with multiple form rows require explicit disambiguation.

The supplement contains metadata for 344 shared species/forms, 525 shared moves
and the reference type chart. Three local entries lack a unique reference join:
Aegislash's unqualified species and canonical forms 711/745; they return unsupported
rather than borrowing another form. Base stats are metadata only: **all numerical
combat stats come from the caller**. Local/reference type or move-definition
conflicts block calculation. Fixed-damage power 0 versus local sentinel 1 is an
explicit exceptional-move representation difference handled separately.

The existing Champions catalog, availability/regulation evidence, reference move
metadata, and mechanics provenance are distinct. A computable scenario does not
prove competitive legality, native ability, natural move membership or a valid
training distribution. No runtime network requests or JavaScript dependency.

## Input convention

See `damage/schemas/request-v1.json`. Supply one `profile`, `attacker`, `defender`,
`move`, and `field`. Unknown or misspelled extra fields are rejected.

For each Pokémon:

- `identity`: exact canonical ID or Chinese/English name. A species identity
  requires `form: "base"` or a specific form identity. An explicit form identity
  may omit `form` or use `"as_named"`. No automatic Mega transformation is applied.
- `level`: explicit integer 1–100. The attacking level enters the formula;
  defender level is metadata because actual defensive stats are supplied.
  Non-50 Champions-reference scenarios are hypothetical explicit-level tests,
  not a claim about competitive level legality.
- `stats`: actual **unmodified** `attack`, `defense`, `special_attack`,
  `special_defense`, `speed` (1–65535). Supply `stat_basis: "unmodified"`.
  These stats already incorporate whatever training/nature the caller knows,
  but not stages, abilities, items, weather or screens. `"effective"` is rejected
  to prevent applying those modifiers twice. No stat-construction helper or
  EV/IV/nature/SP defaults are implemented.
- `stages`: −6..+6, including zero. Relevant unknown stages block calculation; Sacred Sword explicitly proves the defensive stage irrelevant, so that stage may remain unknown;
  unused stats/stages may be absent/null and do not enter an audited handler.
- `maximum_hp` and `current_hp`: actual values or null. Missing maximum HP omits
  percentages; missing current HP omits KO probability. HP-dependent abilities
  require their relevant actual HP values. Current HP cannot exceed maximum HP;
  zero current HP is rejected for an active-hit scenario.
- `ability`, `item`, `status`: exact resolved names/IDs, with `"none"` meaning
  explicitly absent/inactive. `null` means unknown, not neutral.
- `other_effects: []`: explicit declaration that additional transforms, type/stat
  overrides, suppression interactions, charging states, protection, substitutes,
  aura/ally effects etc. not otherwise supplied are absent. Nonempty/unknown
  values return unsupported/incomplete, never neutral.

Field: `format` (`singles`/`doubles`), `weather` (`none`/`sun`/`rain`/`sand`/`snow`),
`terrain` (`none`/`electric`/`grassy`/`psychic`/`misty`), `critical`, `reflect`,
`light_screen`, `aurora_veil`, `helping_hand`, `friend_guard`, `targets_hit`,
`attacker_grounded`, `defender_grounded`, `other_effects`.

Booleans are explicit true/false; null means unknown. `targets_hit` describes
spread applicability (including applicable ally targets), not hit accuracy.
The supported doubles spread path requires at least two targets; single-target
moves require one. A doubles spread move with only one remaining target is
unsupported pending a dedicated reference test. Terrain needs explicit compatible
grounding. Grounding overrides (Gravity, Iron Ball, Air Balloon, Roost, etc.) and
suppressed-Levitate/terrain interactions are unsupported. With no terrain,
grounding can be unknown: type/ability immunity is evaluated from resolved static
types/abilities and explicitly absent other effects.

A conflicting observation is `{"state":"conflicting","values":[...,...]}`.
It remains distinct from null, absence and unsupported known mechanics. Diagnostics
are fail-fast and report the first blocking path, not an exhaustive list of every
missing field. No unknown modifier is silently assigned a neutral value.

## Calculation and output

Core integer arithmetic follows the pinned Champions reference: staged stats,
chained 4096-based power modifiers, effective offense/defense, floored base formula,
spread/weather/critical, random factors 85..100, half-down STAB, type effectiveness,
burn and chained final modifiers. Reference 16/32-bit overflow points are retained;
neutral STAB is not unnecessarily multiplied (important for overflow). There is no
single combined floating-point multiplier. The calculation trace exposes effective
stats, base steps and every roll's integer intermediate values.

`damage/schemas/response-v1.json` describes results. They contain canonical
identities, profile/database provenance, `rolls`, integer frequencies and rational
probabilities, min/max, rational percent-of-max-HP values, conditional KO probability,
modifiers, trace, assumptions and diagnostics. Rolls are **uncapped potential damage**;
`hp_loss_rolls` separately caps at known current HP. The probability is conditional
on the supplied snapshot, chosen critical outcome and a connecting hit. Accuracy,
critical chance, recoil, healing and later secondary effects are not part of that
one-hit target-damage distribution.

Ordinary supported hits enumerate all 16 equiprobable factors, retaining duplicate
integer values. Immunity and level-fixed damage are deterministic single-outcome
distributions; the ordinary random factor is inapplicable. Unsupported extra
randomness never receives a fabricated 16-roll distribution.

Conditional scenarios use `{"scenarios":[{"id":"...","input":{...}},...]}`
(maximum 64, unique IDs). Every scenario is a full explicit input; there are no
implicit builds, substitutions or scenario probabilities. Each result retains its
own success/uncertainty status. The group status is `conditional_scenarios`, not
unqualified Champions-exact.

## Supported boundary

The source allowlists in `damage/engine.py` are the exact machine-readable coverage:
**69** audited standard/special direct moves plus **2** fixed-damage handlers.
Status moves and any move outside the allowlist are rejected. Facade, Body Press,
Psyshock and Sacred Sword have explicit handlers. Seismic Toss and Night Shade use
level-fixed damage with immunity checks.

Reference modifiers: stages; STAB/Adaptability; all static type matchups;
burn/Guts/Facade; sun/rain; sand Rock special defense and snow Ice defense; four
terrains; critical stage bypass, Sniper and critical prevention; three screens
without stacking; doubles spread; Helping Hand and Friend Guard; supported
contact/punch/bite/pulse/slicing and Normal-type conversion abilities; supported
stat/HP/defensive/absorption abilities; audited damage items, resistance berries,
and matching current-form Mega stones (neutral for this single hit).

There are 23 attacker-role and 18 defender-role known ability names (plus explicit
none), and 43 audited item names (plus matching Mega stones and none). Role-specific
allowlists prevent silently ignoring an unfamiliar ability. They do not infer
whether the Pokémon naturally has the ability or move. Neutral accepted items
may have later effects, which are outside direct target damage.

Unsupported includes arbitrary abilities/items, type changes, Tera/Dynamax/Z moves,
Gravity/grounding overrides, protection/substitute/broken-field interactions,
variable-power moves outside explicit handlers, multi-hit distributions and
between-hit changes, Foul Play, Knock Off, Electro Shot pre-hit boosts and other
unaudited exceptions. Return must not be treated as a fixed-power ordinary move.
Galvanize and Storm Drain are deliberately unsupported: their pinned Champions
reference paths do not match familiar Gen 9 expectations. No Gen 9 fallback or
unverified Champions ruling is introduced.

This bounded implementation does not complete unrestricted M3.1 mechanics
acceptance. It supplies a validated standalone interface and supported reference
subset; broader coverage and verified Champions rules remain open.

## Python API and CLI

```python
import json
from damage import calculate, calculate_scenarios
request = json.load(open("examples/damage/neutral.json"))
result = calculate(request)
assert result["status"] == "exact_reference"
```

```sh
.venv/bin/python -m damage examples/damage/neutral.json
.venv/bin/python -m damage examples/damage/terrain.json
.venv/bin/python -m damage examples/damage/conditional.json
# After installing the package: champions-damage input.json
```

stdin is supported. CLI exit 0 means a reference calculation or a conditional
container was returned; inspect each scenario status. Exit 2 means invalid,
incomplete, ambiguous, conflicting or unsupported input. Non-finite JSON numbers
are rejected. Runtime uses Python standard library and shared knowledge only;
neither Node, jsonschema, OCR nor video assets are required.

## Reference reproduction

The curated 95-case suite, 160 mixed-modifier cases and 118 terrain/overflow cases
are pinned with hashes. Of 373 oracle cases, 371 have full-roll parity and two
explicitly remain unsupported. Inputs and oracle results are separate immutable
files; tests never update expected rolls from Python implementation output.

The test-only Node adapter sets all actual raw stats, HP, level, status, ability,
item and boosts explicitly, then calls the pinned Champions mechanics function.
It bypasses the public wrapper's clone/stat reconstruction. In particular,
Champions constructor level 50 and default native ability are overwritten; oracle
EV/nature description strings are cosmetic constructor scaffolding, not inferred
build inputs. The oracle itself computes every expected damage roll independently.

```sh
mkdir -p .cache/m31/oracle
cp tests/fixtures/damage/oracle-package.json .cache/m31/oracle/package.json
cp tests/fixtures/damage/oracle-package-lock.json .cache/m31/oracle/package-lock.json
npm ci --prefix .cache/m31/oracle --ignore-scripts --no-audit --no-fund
.venv/bin/python scripts/build_damage_data.py
node scripts/damage_oracle.cjs tests/fixtures/damage/reference-inputs.json > /tmp/reference-check.json
cmp /tmp/reference-check.json tests/fixtures/damage/reference-rolls.json
node scripts/damage_oracle.cjs tests/fixtures/damage/combo-inputs.json > /tmp/combo-check.json
cmp /tmp/combo-check.json tests/fixtures/damage/combo-rolls.json
node scripts/damage_oracle.cjs tests/fixtures/damage/extra-inputs.json > /tmp/extra-check.json
cmp /tmp/extra-check.json tests/fixtures/damage/extra-rolls.json
.venv/bin/python scripts/validate_damage.py
.venv/bin/python -m pytest -q tests/test_damage.py
# Optional schema tooling, isolated from runtime:
.venv/bin/python -m pip install --target .cache/m31/schema-lib -r tests/fixtures/damage/schema-requirements.txt
.venv/bin/python scripts/validate_damage.py --schema-library .cache/m31/schema-lib
```

Generated validation/checkpoints stay under `.cache/m31/`. No runtime fetching,
video processing or automatic tracker ingestion occurs. A future M2.3.4 adapter
must validate identity/form, actual stat convention, chronology/freshness, each
modifier and its uncertainty before producing this explicit contract; stale OCR
Battle State is not automatically accepted here.
