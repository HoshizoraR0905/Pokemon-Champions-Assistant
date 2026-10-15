# Champions stat feasibility composition

M3.1.2 composes the existing stat utility and numerical inverse calculator. It
changes neither their formulas nor the M3.1.1 API/output. Runtime remains offline.

```python
from knowledge.stat_feasibility import champions_attainable_stats

legal = champions_attainable_stats(identity='Kingambit', form='base', stat='attack')
values = legal['joint_feasible']['values']
```

The function supports existing canonical IDs and exact Chinese/English names.
Explicit form names or IDs identify their own variant; a bare species requires
`form='base'` or a form ID/name. Mega forms use their own KnowledgeBase base stats.
Missing/ambiguous identities return `insufficient_information` diagnostics.

Optional arguments:

- `known_training_points`: partial mapping of stat names to exact 0..32 integers.
- `point_domains`: partial mapping to explicit finite point domains (default 0..32).
- `adjustments`: partial mapping to a factor string or list of alternatives,
  e.g. `{'attack': '1.1'}` or `{'speed': ['0.9', '1.0']}`.
- `alignments`: explicit complete `{increase, decrease}` alternatives. Omission
  enumerates all 21 distinct legal numerical patterns, including neutral.
- `stat_constraints`: partial mapping to actual integers, inclusive
  `{minimum, maximum}` ranges or `{allowed_values: [...]}` sets.
- `retain_witnesses`: default true, one deterministic existence witness per value;
  false omits witnesses while keeping the complete compact configuration set.

The default enumerates all documented possibilities, with no preferred build.
Null entries inside supplied constraints are rejected. Explicit empty allowed-value
sets represent contradictions, rather than missing information.

`attainable` is the exact selected-stat projection under point/adjustment
restrictions and budget, before additional actual-stat constraints.
`joint_feasible` additionally enforces all actual-stat constraints in one build.
Both contain sorted `values`, `minimum`, `maximum`, `hull`, `intervals`, `count`
and `has_gaps`. Charizard's unconstrained Attack set is 93..141 and 143..149;
142 is unattainable. A hull alone loses that fact.

## Compact joint configurations

`configurations.representation == 'alignment-point-domains-budget-v1'` denotes the
union of at most 21 branches. Each branch has one shared legal alignment and,
for each of six stats, rows with exact `training_points`, `actual_stat` and
`adjustment`. Choose one row per stat **subject to the shared sum <= 66**.
The point domains are not permission to combine arbitrary rows without the sum
check. This representation contains every compatible full configuration without
listing the enormous Cartesian product. It is complete, not a truncated sample.

All numerical rows come from `ChampionsStats.attainable`; the integration contains
no stat formula. For one fixed alignment, constraints on each stat leave independent
point domains coupled only by the sum cap. A completion exists exactly when all
six domains are nonempty and the sum of their minimum points is at most 66.
A particular row has a completion exactly when its points plus the other five
minima fit the cap. These tests give exact projections and safe domain pruning.
Witnesses use those minima and are verified by `ChampionsStats.calculate`.
They demonstrate existence, not a preference or a probability.

The structural bound is 21 alignments × 6 stats × 33 point rows. Search never
expands a six-stat Cartesian product. Tests compare the compact representation
against complete small-domain enumeration, including allocations near the cap.
Further explicit enumeration may reuse `legal_allocations` with its existing
work bound. Correlations other than a single alignment and the documented total
budget are not represented by this stat API.

## Inverse composition

```python
import json
from damage.champions_feasibility import infer_champions_attack_stat

request = json.load(open('examples/champions_feasibility/intersection.json'))
result = infer_champions_attack_stat(**request)
# damage_feasible: 89..109
# final_feasible: 93..109
# excluded_by_stat_legality: [89, 90, 91, 92]
```

Supply the ordinary inverse request plus `champions: {identity, form, ...}` using
the optional arguments above. This composition helper accepts the same numerical
domain formats as the existing JSON inverse command (Python integer iterable or
JSON inclusive min/max). It calls M3.1.1 once and preserves its entire original
output in `damage_result`. No original damage candidate is widened or replaced.
`champions` must resolve to the same form as every damage observation, with one
established level context. The Champions stat formula itself has no level/IV term;
level remains the supplied forward damage context.

Outputs distinguish:

- `damage_feasible`: unchanged numerical answer under the supplied damage profile.
- `champions_attainable`: the selected stat's exact attainable domain under declared
  training/adjustment constraints.
- `stat_intersection`: damage ∩ attainable, before cross-stat constraints.
- `joint_result`: feasibility including caller stat constraints and known actual
  attacker stats/maximum HP in the observations.
- `final_feasible`: damage ∩ joint feasible; always a subset of the original answer.
- `excluded_by_stat_legality` and `excluded_by_joint_constraints`: distinct reasons
  values disappeared at the two filtering steps.
- `compatible_configurations` and `witnesses`: restricted to the final values.
- `per_scenario`: original shared/local assignments with their filtered sets.

Known non-target actual attacker stats and maximum HP in the forward requests
constrain the same build. The designated inferred stat is still a placeholder;
its template value is replaced by each candidate, as in M3.1.1. Unestablished,
unused placeholder stats should be null; null does not imply zero or neutral.
Current HP is not maximum HP and does not directly constrain training.
Conflicting known actual stats yield an empty joint set. A non-target conflicting
fact that has not been resolved to an exact stat yields diagnostics.

Ordinary stage/item/weather/screen scenarios keep M3.1.1's joint assignment logic.
Scenario variables that change actual attacker stats or maximum HP require separate
explicit composition solves and are rejected here; they cannot be silently
decoupled from training feasibility. Observation-specific stages remain supported.
Identity/form mismatch likewise prevents a filtered claim. This milestone models
one unchanged full training configuration; it does not transform stats across forms.

The helper returns completed `exact`, `conditional` or `empty` statuses from this
model, or unsupported/insufficient-information diagnostics. If numerical damage is
unresolved, no complete filtered result is claimed. Empty answers explain whether
damage alone, marginal stat legality, or joint build constraints caused the failure.

## JSON command and examples

```sh
.venv/bin/python -m damage.champions_cli examples/champions_feasibility/intersection.json
.venv/bin/python -m damage.champions_cli examples/champions_feasibility/joint-budget.json
.venv/bin/python -m damage.champions_cli examples/champions_feasibility/joint-empty.json
```

The command also accepts stdin. Exit 0 means completed exact/conditional/empty
feasibility, exit 2 means unsupported/insufficient/invalid information.
Expected exact sets are saved alongside the examples.

With neutral adjustment, Charizard HP 185 and Speed 152 each need 32 points.
Only 0..2 Attack points remain, giving Attack `{104,105,106}`. Adding Special
Attack 161 needs a third 32-point investment and makes the joint set empty.
Attack 149 and Special Attack 177 are separately attainable but require two
increased stats; their combination is impossible under one alignment.

## Source qualifications and validation

Reuse the pinned source records in `knowledge/data/champions_stat_rules.json`:
[能力 2607357](https://wiki.52poke.com/index.php?title=能力&oldid=2607357),
[性格 2568467](https://wiki.52poke.com/index.php?title=性格&oldid=2568467) and
[Pokémon Champions 2628728](https://wiki.52poke.com/index.php?title=Pokémon_Champions&oldid=2628728).
The Champions-specific alignment description maps to one positive and one distinct
negative non-HP adjustment, or numerical neutral. Four neutral nature labels are
not selectable; this utility models numerical patterns, not nature label choices.
No independent boosts across all five stats are assumed.

These are verified descriptions in pinned community documentation, not official
mechanics certification. Runtime uses the pinned profile only. Unsupported or
unverified rule extensions are not guessed; no joint-legality claim is made for
them. Fixed-HP exceptions and roster/regulation legality remain outside support.
Damage is still qualified by the provisional forward profile; stat feasibility
cannot certify that damage formula. Source-derived records retain the existing
52Poké contributor attribution and CC BY-NC-SA 3.0 notices.

The existing 24 actual Champions range columns across Charizard, Mega X, Mega Y
and Sneasler are reused as independent expectations. All five cached rendered
sources are hash/revision checked; no interactive clicks, OCR or crawling is needed.
The new API is independently checked against those ranges as well.

```sh
.venv/bin/python -m pytest -q tests/test_champions_feasibility.py tests/test_champions_stats.py tests/test_damage.py tests/test_inverse_damage.py tests/test_git_artifact_policy.py
.venv/bin/python scripts/validate_champions_stats.py --snapshots
.venv/bin/python scripts/validate_damage.py --schema-library .cache/m31/schema-lib
.venv/bin/python scripts/validate_inverse_damage.py --schema-library .cache/m31/schema-lib
```

The old numerical API/CLI, oracle fixtures and their expected rolls remain unchanged.
No speed-order inference, video processing or later milestone is implemented.
