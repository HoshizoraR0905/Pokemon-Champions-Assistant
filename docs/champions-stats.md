# Champions stat construction

`knowledge.champions_stats` constructs actual **unmodified** Champions stats.
It is independent of `damage`, uses the existing `KnowledgeBase` base stats and
canonical form identities, and performs no network or recognition work.

```python
from knowledge.champions_stats import ChampionsStats, STATS, alignment_patterns, legal_allocations

charizard = ChampionsStats('喷火龙', form='base')
points = dict.fromkeys(STATS, 0)
points.update(hp=2, attack=32, speed=32)
result = charizard.calculate(points, {'increase': 'attack', 'decrease': 'special_attack'})
# stats: hp=155, attack=149, defense=98, special_attack=116,
#        special_defense=105, speed=152

possible = charizard.attainable('attack', adjustments=['0.9', '1.0', '1.1'])
# Exact values: 93..141, then 143..149. 142 is unattainable.
configs = charizard.reverse_lookup('attack', 149, adjustments=['0.9', '1.0', '1.1'])
# Only training_points=32, adjustment='1.1'.
```

The rules are HP = base + points + 75 and other stats =
`(base + points + 20) * numerator // 10`, with numerator 9, 10 or 11.
No floating point, IV, EV, nature inference, level conversion or damage rounding
is involved. Adjustment arguments are exact strings. HP accepts only `'1.0'`.
Unknown inputs produce errors; no implicit neutral alignment is selected.

All six training values must be explicit integers 0..32, with sum **at most** 66.
Unspent points are valid. A complete alignment is one increased and one distinct
decreased non-HP stat, or `{'increase': None, 'decrease': None}` for neutral.
`alignment_patterns()` exposes the 21 distinct numerical patterns; it does not
choose a pattern or assign probabilities. Four neutral nature labels cannot be
selected in Champions according to the pinned nature article; the utility models
numerical adjustment patterns, not selection of those labels or personality.

`attainable` returns the exact sorted integer values, min/max, count, gaps, and
all compatible `(training_points, adjustment)` configurations. Callers explicitly
supply the allowed adjustment alternatives; the default point domain covers the
documented 0..32. Restrict `point_domain` or use `allocated_other` to account for
points spent on other stats. Omitted other allocations are unconstrained, not
observed zero. Each marginal result can be extended with zero elsewhere, but
maxima for different stats need not be jointly attainable. A non-neutral marginal
adjustment needs its compensating opposite adjustment elsewhere.

For joint configurations use explicit finite point domains and alignment choices:

```python
domains = {s: [p] for s, p in points.items()}
allocations = list(legal_allocations(domains))
reverse = charizard.reverse_configurations(
    {'attack': 149, 'speed': 152},
    alignments=[{'increase': 'attack', 'decrease': 'special_attack'}],
    point_domains=domains,
)
```

`legal_allocations` enforces the shared budget. `reverse_configurations` also
requires the **same** alignment for all requested actual stats. Both reject work
exceeding `max_combinations` before enumeration (default 1,000,000, maximum
10,000,000); they never silently truncate. Supply bounded domains rather than
requesting the enormous full six-stat Cartesian product. The allocation iterator
is lazy; joint reverse lookup materializes results within that bound.

A bare species requires `form='base'` or an explicit canonical form. Exact form
names/IDs establish their own variant; omit `form` or use `as_named`. Canonical
`pokeapi:pokemon:*` IDs resolve through the shared `IdentityIndex`; ambiguous
variants are rejected. No alternative identity database is created. Missing base
stats and fixed-HP species requiring exception verification fail explicitly.
Presence in the base-stat catalog does not certify current regulation legality.

## Sources and reproducibility

The bundled `knowledge/data/champions_stat_rules.json` records URLs, revision IDs,
retrieval date (2026-10-15), rendered HTML hashes, attribution and game scope:

- [能力, revision 2607357](https://wiki.52poke.com/index.php?title=能力&oldid=2607357): Champions formulas, point limits and factors.
- [性格, revision 2568467](https://wiki.52poke.com/index.php?title=性格&oldid=2568467): adjustment pairs, neutral patterns and Champions label restrictions.
- [Pokémon Champions, revision 2628728](https://wiki.52poke.com/index.php?title=Pokémon_Champions&oldid=2628728): training and nature/mint mapping; levels/IVs do not determine stats.

These are community-documented rules, not independently certified official
mechanics. There are no speculative numerical constants in this profile. Fixed-HP
exceptions, battle modifiers and regulation availability are outside its verified
scope. Existing base stats retain their separately pinned local catalog provenance;
they are not relabeled as encyclopedia imports.

Independent expected ranges/base stats are transcribed from the actual **StatPoint**
columns, with form containers checked on [Charizard, revision 2627146](https://wiki.52poke.com/index.php?title=喷火龙&oldid=2627146)
and [Sneasler, revision 2575062](https://wiki.52poke.com/index.php?title=大狃拉&oldid=2575062).
The curated fixture contains 24 ranges across the base Charizard, both Mega forms,
and Sneasler. Expected values are not generated by the stat formula.

52Poké contributors' material is licensed under
[CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/).
Attribution and source links accompany the rule/fixture records; this licensing
applies to those source-derived records, separately from code and local base-stat
source licenses. Full rendered snapshots remain local in `.cache/champions-stats/`.
An article oldid does not pin transcluded templates; the recorded HTML SHA-256
identifies the exact rendered snapshot used for verification.

```sh
.venv/bin/python -m pytest -q tests/test_champions_stats.py tests/test_damage.py
.venv/bin/python scripts/validate_champions_stats.py
# Optional: require and check the already-downloaded snapshots, never refetch:
.venv/bin/python scripts/validate_champions_stats.py --snapshots
```

M3.1 continues accepting caller-supplied actual stats without consulting this
utility. M3.1.1 may explicitly use `attainable(..., adjustments=[...])['values']`
as its candidate domain, preserving provenance and alternatives. This does not
implement the inverse damage solver or automatically assume an opponent build.
