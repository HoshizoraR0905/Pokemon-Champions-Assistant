# Constraint-based inverse damage, v1

`damage.infer_attack_stat` enumerates a bounded set of actual, **unmodified**
Attack or Special Attack values through the existing M3.1 forward calculator.
There is no inverse formula, guessed build, nature assumption, probability prior,
or automatic video/HP-delta interpretation.

```python
import json
from damage import infer_attack_stat

request = json.load(open('examples/inverse_damage/single.json'))
request['candidate_stats'] = range(80, 151)  # Python API takes an integer iterable.
result = infer_attack_stat(**request)
# result['feasible']['values'] == list(range(89, 110))
```

The Python API accepts a finite iterable for `candidate_stats`, e.g. `range(80,151)`
or `[89, 92, 100]`. Explicit duplicates are deduplicated; boolean, non-integer,
empty, zero and out-of-forward-range values are rejected. No default domain is
assumed. Candidate values must be 1..65535, the forward engine's numerical input
bound; **this is not a claim that every such value is species-legally attainable**.
The supplied domain is authoritative. It may come from an explicitly configured
Champions stat utility query, with its provenance attached as `domain_provenance`.

The JSON CLI accepts an integer list or inclusive `{"minimum":80,"maximum":150}`:

```sh
.venv/bin/python -m damage.inverse_cli examples/inverse_damage/single.json
cat examples/inverse_damage/rounding-gap.json | .venv/bin/python -m damage.inverse_cli
# Installed entry point: champions-inverse-damage [request.json]
```

CLI exit 0 means a completed exact, conditional or empty feasibility calculation;
exit 2 means unsupported or insufficient/invalid information. JSON parse failures
also produce a structured response. Schemas are `damage/schemas/inverse-request-v1.json`
and `inverse-response-v1.json`; runtime semantic validation uses only stdlib and
existing damage/knowledge modules. A JSON Schema validator is optional development
tooling, with pinned versions reused from M3.1.

## Observations and identities

Each observation supplies these exact fields:

| Field | Meaning |
| --- | --- |
| `id` | Unique observation ID |
| `battle_id` | Battle/scenario namespace |
| `attacker_instance_id`, `target_instance_id` | Stable individual identities, not species names |
| `stat_epoch` | Explicit interval during which the underlying numerical stat is unchanged |
| `damage_kind` | Must be `direct_move_damage` |
| `damage` | Nonnegative exact integer, inclusive `{minimum, maximum}`, or `{allowed_values:[...]}` |
| `evidence` | Nonempty evidence/provenance and direct-damage justification |
| `input` | Complete M3.1 forward request, including its explicit profile |

The designated `attacker.stats[stat]` entry is a template placeholder and is
replaced by every candidate. It is not an additional known-stat constraint.
Observation-specific stages and all other inputs remain intact. Irrelevant
other stats may be unknown exactly when the forward handler supports that.

All observations must share `(battle_id, attacker_instance_id, stat_epoch)` and
resolve to the same canonical current form and level. Exact Chinese/English
aliases resolve through the existing knowledge identities. Different instances,
forms, levels or epochs require a `continuity` object covering exactly all
observation IDs: `{subject_id, observation_ids, evidence, unchanged_stat:true}`.
This is an explicit evidence assertion that the numerical stat is unchanged, not
an automatic conversion across a transformation. A changed underlying stat needs
a separate solve or justified continuity; ordinary stage changes need no such
conversion. The solver cannot independently verify a caller's continuity claim.

An HP decrease alone is rejected as damage evidence. The caller must establish
which direct move caused it and whether residual effects, healing, multiple hits,
or KO censoring are involved. If damage exceeds remaining HP, the HP loss gives
only a lower bound, not the raw damage. Supply a justified interval/set consistent
with that bound, or leave the observation unresolved. The solver compares raw
potential damage rolls, never capped `hp_loss_rolls`, and never widens evidence.

## Joint finite scenarios

Uncertain inputs stay null/conflicting until resolved by explicit alternatives;
they are not treated as neutral. A finite variable has:

```json
{
  "id": "held_item",
  "scope": "shared",
  "observation_ids": ["hit1", "hit2"],
  "path": "attacker.item",
  "values": ["none", "Life Orb"]
}
```

`shared` applies one value to all listed observations. `observation` expands into
an independent choice for each listed observation (`held_item:hit1`, etc.). Paths
must name existing leaf context fields; overlapping bindings and attempts to
change the inferred stat or its attacker identity/form/level/stat basis are
rejected. Defender context and stat stages can vary explicitly. Correlated
uncertainties beyond this shared/local variable model should be submitted as
separate fully explicit solves, preserving each complete correlated assignment;
do not encode correlation as independent variables.

For assignment z and observation i, the solver forms
`S_i(z) = {A in domain: support(forward(A, context_i(z))) intersects damage_i}`.
The result is `union_z intersection_i S_i(z)`. It never intersects independently
unioned observation sets when shared unknowns are present. Rolls may vary between
hits; shared conditions may not. `scenarios` preserves every assignment, including
empty branches, each observation's set, matching raw rolls, full supported rolls
for compatible candidates, and actual forward-handler stat dependencies.

Dependencies come from `damage.engine.stat_dependencies(successful_result)`,
which reads the executed forward trace. Body Press uses the attacker's Defense;
Psyshock uses Special Attack against Defense. Fixed damage and immunity are
stat-independent. These may validate/reject an observation but cannot numerically
narrow the requested stat if its dependency is absent. A physical observation is
not treated as a Special Attack constraint. Foul Play and any other mechanics
unsupported by the forward engine remain unsupported.

## Results, bounds and reproducibility

`feasible.values` is authoritative. Min/max, `hull`, disjoint inclusive `intervals`,
`count` and `has_gaps` summarize that exact integer set. `unconstrained` means the
entire supplied domain remains feasible; `informative_dependency` separately says
whether the requested stat occurs in the executed handler. A relevant move can
also be uninformative within a particular domain due to rounding/broad evidence.
Top-level per-observation sets are marginal unions for diagnostics, not substitutes
for the joint result. Matching rolls live under each scenario's observation row.

Statuses:

- `exact`: completed enumeration with fixed explicit context.
- `conditional`: completed enumeration over explicit finite unknown alternatives.
- `empty`: no consistent candidate and assignment; evidence/domain stay unchanged.
- `unsupported`: the selected forward profile or any needed branch is unsupported.
- `insufficient_information`: unresolved/conflicting or invalid input, identity,
  evidence, candidate-domain or work-limit problem.

For unsupported/unresolved branches, the complete union is unknown: top-level
`feasible` is null. Already completed scenario rows are partial diagnostics only;
the solver does not silently discard the problematic branch. Forward diagnostics,
observations, domain provenance and scenario bindings are preserved.

Empty results include individually feasible observations and a deletion-minimal
conflicting subset when the configured minimization budget completes. This is
minimal by deletion, not necessarily minimum cardinality. If the budget stops
minimization, the smaller explanatory subset is labeled accordingly. Diagnosis
suggests checking identity, changed underlying stats, mechanics and HP attribution;
it does not assert a specific cause or drop a constraint.

Default `limits` are `max_candidates=4096`, `max_assignments=128`,
`max_evaluations=100000`, `max_conflict_checks=128`. Each is configurable up to
1,000,000. The evaluation check conservatively bounds candidates × assignments ×
observations before work, even if memoization could save calls. Equivalent complete
forward requests are memoized within a solve; static knowledge remains cached in
the forward layer. Candidate enumeration and output order are deterministic.
Conflict minimization reuses exact sets, with no additional forward calculations.

`exact` qualifies the finite feasibility computation, **not official Champions
mechanics verification**. M3.1 still supports only the bounded provisional
`showdown-champions-reference-v1` profile. `champions-evidence-only-v1` remains
unsupported for numerical damage, and is the deliberately conservative API
default. No Gen 9 fallback is selected. Forward source/version/hash provenance
is retained, and the inverse module adds no new mechanics assumptions.

The optional [Champions stat utility](champions-stats.md) can supply a discrete
domain only with explicit adjustment alternatives. `examples/inverse_damage/stat-domain.json`
records such a domain and provenance. It does not infer or weight a training build.

## Validation and resuming

Independent fixtures pin `@smogon/calc` 0.12.0, its dedicated Champions generation,
existing adapter/package-lock hashes and source manifest. Nineteen exhaustive
41-value domains contain 779 raw forward evaluations. Expected inverse sets are
derived from those Node outputs without importing Python damage/inverse code.
Historical M3.1 oracle fixtures are immutable prerequisites. The optional explicit
rebuild command is `scripts/build_inverse_fixtures.py`; normal validation needs
neither Node nor network.

```sh
.venv/bin/python -m pytest -q tests/test_inverse_damage.py tests/test_damage.py tests/test_champions_stats.py tests/test_git_artifact_policy.py
.venv/bin/python scripts/validate_inverse_damage.py --schema-library .cache/m31/schema-lib
# Repeat the same command to reuse fingerprint-compatible completed stages.
```

Validation prints stages and atomically saves each completed group/benchmark under
`.cache/m311/`. Fingerprints cover inverse/forward code, schemas, source data and
fixtures. Changed fingerprints receive separate checkpoint files; old successful
results remain available. `latest-validation.json` points to the last completed
run. Runtime benchmarks are machine-specific measurements, not guarantees.
The solver itself is bounded and in-memory; process-level resumability belongs to
the validation harness rather than an implicit persistent inference cache.

Future battle-state integration must translate established instance continuity,
stat epochs, quantitative stages and justified direct damage into this contract.
No OCR, recognition pipeline, M2.3.4, Bayesian inference or strategy integration is
implemented here.
