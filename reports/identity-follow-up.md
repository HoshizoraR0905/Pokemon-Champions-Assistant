# Canonical Pokémon identity audit (2026-10-13)

The local identity snapshot is derived from pinned [PokéAPI `pokemon.csv`](https://github.com/PokeAPI/pokeapi/blob/81d20919845b6a445969b9265aab5cec6b04cece/data/v2/csv/pokemon.csv), [`pokemon_forms.csv`](https://github.com/PokeAPI/pokeapi/blob/81d20919845b6a445969b9265aab5cec6b04cece/data/v2/csv/pokemon_forms.csv), and the species-name table already cited in `knowledge/data/manifest.json`. The PokéAPI [API documentation](https://pokeapi.co/docs/v2) distinguishes a species (shared National Pokédex identity), a Pokémon (a variant with game data), and a Pokémon-form (a visual form attached to a Pokémon). A Pokémon-form ID is not a National Pokédex number or necessarily a Pokémon ID. PokéAPI's `is_default` applies to forms within Pokémon variants; it cannot be used as a unique default for an entire species with several variants. This limitation is also discussed in [PokéAPI issue #1568](https://github.com/PokeAPI/pokeapi/issues/1568).

The pinned [Champions sprite repository](https://github.com/KevinToodlepoot/pokemon-champions-sprites) says filenames follow Pokémon Showdown names, not PokéAPI numeric IDs. `charizard-mega-x.png`, `raichu-alola.png`, and `indeedee-female.png` are joined through the reviewed PokeAPI form identifier/name mapping in `scripts/build_identity.py`. Its pinned commit is recorded in `knowledge/data/visual_assets.json`. Fourteen filenames remain unmapped; those assets cannot establish a canonical identity. Visual asset presence does not prove current game availability or M-C eligibility.

| Observed identity | National species ID | Pokémon variant ID | Source form row ID | Canonical identity | Canonical `form_id` |
| --- | ---: | ---: | ---: | --- | ---: |
| Charizard | 6 | 6 | 6 | `pokeapi:pokemon:6` | null |
| Mega Charizard X | 6 | 10034 | 10134 | `pokeapi:pokemon:10034` | null |
| Mega Charizard Y | 6 | 10035 | 10135 | `pokeapi:pokemon:10035` | null |
| Raichu | 26 | 26 | 26 | `pokeapi:pokemon:26` | null |
| Alolan Raichu | 26 | 10100 | 10202 | `pokeapi:pokemon:10100` | null |
| Indeedee Male | 876 | 876 | 876 | `pokeapi:pokemon:876` | null |
| Indeedee Female | 876 | 10186 | 10355 | `pokeapi:pokemon:10186` | null |
| Alcremie Ruby Cream / Strawberry Sweet | 869 | 869 | 10346 | `pokeapi:form:10346` | 10346 |

These IDs are verified against the installed pinned form rows, not inferred from sprite filenames. All 1,579 form rows now have unique canonical identities, valid species references, and a preserved `source_form_id`. Of those rows, 1,323 need only a Pokémon ID and have `form_id: null`; 256 share a Pokémon ID with another visual form and use a form-specific key. The schema is `identity.json` v2 and `visual_assets.json` v2, with new checksums in `manifest.json`. The source commits and update dates are unchanged: this is a derived representation migration, not a new upstream data refresh. `scripts/build_identity.py` reproduces the v2 fields from the pinned inputs.

`identity_status` makes null form IDs unambiguous:

- `resolved_unique`: the species has only one mapped form row.
- `resolved_default`: the ordinary/default Pokémon variant was actually identified where other species variants exist.
- `resolved_variant`: a distinct Pokémon variant, such as a regional, gender-specific, or Mega variant, was identified.
- `resolved_form`: a Pokémon-form row is needed to distinguish forms sharing one Pokémon variant ID.
- `species_only`: the species is known, but the current variant is not established; `pokemon_id` and `canonical_identity` stay null.
- `conflicting_variant`: observations disagree about the current identity.

The M1.2 `EntityResolution` and `IconEvidence` objects now include `pokemon_id`, `canonical_identity`, and `identity_status`, while retaining the legacy `canonical_id` entity reference for existing callers. The icon matcher evaluates distinct canonical identities within its visual margin; when competing forms cannot be separated, it returns an ambiguous variant. Text and icon evidence are fused only after independent recognition. A bare species name such as `爱管侍` or `雷丘` does not select male Indeedee or ordinary Raichu. Existing M1.2 fixture recognition remains compatible.

The M1.3 team snapshot is schema v2. It keeps `instance_id` separate from current Pokémon identity. The `form` field is optional; the required field is now `identity`. A valid null `form_id` does not block completion. Loading a v1 team file migrates identified form rows to their unique identity where possible; species-only records remain unresolved. In the supplied screenshots, Corviknight remains species-only because the current icon result does not reliably identify its variant. Five other team members have resolved Pokémon IDs. All still await explicit field verification, so `complete` is false.

A future battle-state layer can retain `own_team_1` as the instance while recording a sequence of observed identities such as `pokeapi:pokemon:6`, then `pokeapi:pokemon:10034`, with timestamps. Potential outcomes are separate from observed identities. This follow-up does not infer future Mega outcomes or implement transformation tracking.

Validation: `python -m pytest -q tests/test_canonical_identity.py tests/test_identity_m12.py tests/test_team_configuration.py` checks the verified IDs, nullable forms, unique keys, source joins, actual Champions thumbnails, ambiguous variants, stable team instance IDs, and the supplied configuration screenshots. The full `python -m pytest -q` run passed **108 tests** on 2026-10-13. Manifest checksums, all 1,579 unique identity keys, every mapped visual asset, and the six saved team records also passed a referential-consistency audit.
