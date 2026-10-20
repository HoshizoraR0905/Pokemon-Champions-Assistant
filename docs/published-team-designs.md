# Published Champions team designs

M3.3's central dataset is now **distinct published designs**. The existing [current Ranked aggregate cache](metagame-current-cache.md) stays separate as a reference population. The new implementation is `metagame.published`, with its own SQLite database at `.cache/metagame/published-teams/teams.sqlite3`. It never queries Ranked marginal percentages to construct joint records.

## Collect and reproduce

The expanded VGC Multicalc collector reads its complete MIT-licensed repository index and detail blocks at a pinned commit. The website paginates that index locally; the collector enumerates all pages and loads every referenced block, with no ten-record ceiling. Public submissions use the ordinary public UI's index/paste GET endpoints, under the user's recorded authorization for private non-commercial research. Protected pastes are rejected. Both paths preserve raw bytes, receipts and index/detail capture links before ingestion.

```sh
# Complete pinned repository-curated population; --limit 20 selects a diverse pilot.
.venv/bin/python -m metagame.published collect-details --regulation M-C
# Other Champions regulations remain separate.
.venv/bin/python -m metagame.published collect-details --regulation M-B
.venv/bin/python -m metagame.published collect-details --regulation M-A

# Resume public submissions; reuses the authorization already saved locally.
.venv/bin/python -m metagame.published collect-submissions --regulation M-C

.venv/bin/python -m metagame.published query Pelipper \
  --source vgcmulticalc --population tournament_published --regulation M-C \
  --unit distinct_observed_configuration --teammate Archaludon --output json
.venv/bin/python -m metagame.published coverage \
  --source vgcmulticalc --population tournament_published --regulation M-C
```

`tournament_published` is the existing source-family key for VGC Multicalc's curated/public sheets; it does **not** certify that every design came from an official tournament. Event, creator, placement, source date, paste creation date where returned, origin and replica code remain separate metadata. Some sheets have no event. Explicitly Showdown-labeled records are excluded from game-population queries, with existing captures preserved. Other entries remain third-party claimed Champions designs, not independently verified in-game observations.

The two-second serial request interval, finite retries, persisted rate state, immutable raw receipts, per-record atomic run checkpoints and idempotent extraction keys apply to both collectors. Pinned repository resources remain reusable indefinitely under their commit URL. Public index/paste responses refresh after 24 hours; a changed index identity invalidates a completed-record shortcut. Earlier publication revisions and captures remain local; this design corpus is separate from the bounded current-Ranked API cache.

The old `collect --source vgcmulticalc` command below reproduces the original ten-card pilot only. It is retained for compatibility, not used for expanded coverage. PokeFeed remains disabled because its terms require permission; TrickRoom is skipped at the user's direction because its 20 designs are too few. See the expanded validation/source audit for the remaining sites.

```sh
# Retained original pilot commands; not the expanded detail collector.
.venv/bin/python -m metagame.published collect --source pokedaily
.venv/bin/python -m metagame.published collect --source vgcmulticalc

# Reproduce the accepted pilot from the retained audited bytes and receipts:
.venv/bin/python -m metagame.published collect --source pokedaily \
  --from-file .cache/metagame/published-team-audit-20261020/pokedaily-page.html \
  --receipt .cache/metagame/published-team-audit-20261020/pokedaily-page.receipt.json
.venv/bin/python -m metagame.published collect --source vgcmulticalc \
  --from-file .cache/metagame/published-team-audit-20261020/vgcmulticalc-page.html \
  --receipt .cache/metagame/published-team-audit-20261020/vgcmulticalc-page.receipt.json
```

The accepted pilot reused the already audited pages: zero additional network requests. The live path reuses `metagame.fetch.Fetcher`: one concurrent request, two-second default spacing, timeouts/retries/backoff, source validators when available, bounded response size, exact raw hashes and persisted fresh-cache receipts. `--force`, `--request-interval` and a smaller `--limit` are available. A source limit cannot exceed its audited pilot maximum. No automatic crawl or expansion is performed.

Collection atomically checkpoints a manifest after every publication, while individual database transactions preserve earlier successes after a failure. Repeat collection deduplicates the same capture/publication revision; it does not multiply observations. The writer lock prevents duplicate concurrent jobs. `--database PATH` before the subcommand selects a new isolated empty/owned directory. Never point the Ranked retention pruner at this directory: the published database has no pruning method and never deletes verified historical publications.

## Choose the population, format and observation unit

```sh
# Community page states M-C, but does NOT explicitly name Singles/Doubles.
# Unknown is a deliberate format cohort, not an implicit Doubles classification.
.venv/bin/python -m metagame.published coverage \
  --population community_published --regulation M-C --format Unknown
.venv/bin/python -m metagame.published query Pelipper \
  --population community_published --regulation M-C --format Unknown \
  --unit unique_composition --teammate Archaludon --output json
.venv/bin/python -m metagame.published query 大嘴鸥 \
  --population community_published --regulation M-C --format Unknown \
  --unit unique_build --teammate 铝钢桥龙
.venv/bin/python -m metagame.published query Pelipper \
  --population community_published --regulation M-C --format Unknown \
  --without-teammate Archaludon --output json

# Exact item frequencies among designs whose Pelipper has Tailwind;
# or a two-move joint event, with the denominator shown.
.venv/bin/python -m metagame.published query Pelipper \
  --population community_published --regulation M-C --format Unknown \
  --given-move Tailwind --move-pair Tailwind Protect --output json

# Tournament designs are a separate Doubles cohort.
.venv/bin/python -m metagame.published coverage \
  --population tournament_published --regulation M-C --format Doubles
```

Population and regulation are required. Format defaults to Doubles and must be explicitly `Unknown` to inspect PokeDaily's records. There is no `all` population that silently pools community, tournaments or Ranked. In this pilot a community confirmed-Doubles query is empty: the source has not supplied that metadata. Source links and stable on-page locators accompany results for individual inspection. JSON is complete; table output provides a smaller count/denominator view. `--identity-version` selects retained fingerprint versions explicitly.

`unique_build` is the default for core-build queries: every distinct complete six-member Exact Build has weight one. `unique_composition` counts each distinct six-form multiset once and does not select one child build. Its output explicitly refuses move/item/SP statistics. Duplicate publication counts, author popularity, placements and replica codes never become statistical weights.

## Two independent identities

Fingerprint version `published-team-identity-v1` uses SHA-256 of a domain-tagged, deterministic JSON encoding. Species, explicit named forms, moves, items and abilities resolve only through the existing KnowledgeBase. A small source-attributed nature-name supplement supplies the category missing from that KnowledgeBase, including English/Chinese/Japanese names from the existing pinned 52Poké nature snapshot. It adds no species/move/item/ability identity system. Its attribution and CC BY-NC-SA licensing are retained in `natures.json`; it resolves labels only, not nature mechanics.

Composition fingerprints sort the **six canonical species/form identities as a multiset**. Repeated members are retained, and female/regional/Mega forms are not collapsed to a base species. Exact fingerprints sort six normalized core Pokémon builds. Each requires known species/form, ability, item, nature, four distinct canonical move identities and all six verified source-asserted Champions SP values. Moves are sorted for membership statistics; their original source display order remains in the publication. No move-slot inference is performed. A single known point, move or item change yields another Exact Build under the same composition.

The comparison scope is the published core build plus explicitly supplied additional gameplay configuration. Gender and Happiness, when published, enter that configuration; missing explicit configuration values block exact acceptance. Unknown optional attributes are not replaced from another publication. This does not certify unreported attributes, source accuracy, competitive legality or exhaustive game configuration. Nicknames, authors, rental codes, URLs, team/member display order and shiny status do not alter identity. Published level/IV text stays in extraction evidence; the maintained Champions stat profile has neither as a stat input. Unrecognized gameplay fields prevent exact acceptance instead of being silently discarded.

A six-form-known record with missing build fields is `composition_complete`. An incomplete species/form roster is `partial`. Contradictory fields or invalid allocations are `conflicting`. `exact_complete` means complete/comparable source assertions under this declared core profile, not independent verification in the game. Conflicting build details can still support a composition when the six form identities themselves are unambiguous. Unresolved names and unsupported fields remain visible.

PokeDaily's visible sheet labels the allocations SP while its export says `EVs:`. The adapter corroborates each exported point line against that member's visible SP field before assigning `champions_sp`. It never interprets generic EV syntax as SP merely because values are small. Missing components remain null; only a valid known allocation totaling the pinned 66-point budget deterministically establishes zeros in omitted components. This deduction and its original sparse text are retained. No allocation, ability or other field is filled from a different source record.

## Storage, provenance and version changes

Schema version **4**, with ordered migrations, stores:

- Source policies and immutable source captures, with original URL, retrieval timestamp and raw hash/path.
- Immutable publication revisions and their links to one or more captures.
- Versioned canonical compositions, exact builds and Pokémon-level configurations, plus all team-member links.
- Publication-to-design extractions with parser/adapter version hashes, KnowledgeBase snapshot, nature/rule evidence and missing/conflicting fields.
- Potential-duplicate links, explicitly unproven and never used to fill fields or merge incomplete builds.
- Append-only publication corrections/supersessions, retaining the original record and replacement reason.
- Separately versioned observed configurations, explicit missingness/field eligibility and an implementation-definition guard. These are not Exact Build identities. Migrations 3–4 add this layer without rewriting the strict fingerprint profile or removing old publications.

A new fingerprint definition cannot overwrite an existing version. The ingestion guard rejects changed implementation under the same fingerprint version, and also rejects changed canonical output for an existing extraction identity. Increment the version for changed semantics; old canonical identities and original records remain queryable. Current views use the latest adapter extraction for each immutable publication revision within the explicitly selected identity version; prior extractions remain stored.

The initial internal pilot provisionally labeled PokeDaily as Doubles. Inspection established that this was not stated by the page. Six append-only metadata corrections now supersede those provisional records with `Unknown` format; the original bytes and old revisions were retained. Confirmed-Doubles queries exclude the superseded assignments. This correction does not change composition or exact-build fingerprints. Original source publications are never rewritten to make their data agree.

Potential duplicates include records with the same composition and compatible known fields, or incomplete six-member records compatible with a retained record. Compatibility is not equality. Incomplete records never acquire exact fingerprints and never contribute to `unique_build`. Different exact children remain separately linked to their composition. No approximate SP-distance family layer is implemented; a future family table can link these immutable identities without merging them.

## Counts, missingness and joint statistics

`distinct_observed_configuration` is a separate estimator for partially specified designs. Its signature includes the complete observed member fields, explicit missingness, known SP components, extra configuration and unresolved assertions. An SP-unknown signature can hide multiple underlying Exact Builds; its publication count is reported but is never its statistical weight. Known target fields remain usable in an unconditional query even if an unrelated roster form is unresolved. Positive/negative teammate conditions require a complete roster; unknown roster members cannot establish absence. `unique_build` and `unique_composition` retain their original strict meanings.

The current observed profile is `observed-configuration-v3`; earlier profiles remain stored. Explicit source publication IDs, paste IDs and source-reported replica codes also identify publication families within one source/regulation/format. A richer compatible assertion may represent its known partial copies without modifying them or creating Exact Build equality. Arbitrary compatible designs are not consolidated. If no assertion supports every known field in the family, the observed estimator reports and excludes the conflicting family rather than selecting or averaging assertions. All strict identities and original source records remain intact. This publication-family policy is separate from approximate SP clustering, which remains unimplemented.

Each target field has its own denominator. Four resolved moves permit move frequencies and pairs even when SP or nature is missing. A known item, ability or nature independently permits that field's distribution. `sp` needs all six supported components of the target Pokémon's vector; `sp_hp` through `sp_spe` each need only that supported component. A condition such as Pelipper + Archaludon requires a complete resolved roster. Missing fields do not supply negative membership evidence or zeros. An ambiguous duplicate target species is excluded from target-field counts. `--given-move` additionally requires a complete target move list. JSON includes `field_eligibility` even when a field has no eligible observations.

Every estimate returns integer numerator/denominator, chosen observation unit, selected population/regulation/format, eligible designs, excluded publication revisions and source links. Source-publication and revision counts are distinct from unique-design counts. Completeness counts are labeled extraction-record counts and do not become weights. When several same-form Pokémon occur within one team, target-build statistics exclude the ambiguous target instance rather than count the team twice; composition presence statistics still count the design once.

Composition queries expose species presence, teammate presence, requested two-teammate context, co-occurrence and lift. Lift uses P(B|A)/P(B) with a baseline from the **same** selected design population; six-member team structure constrains this descriptive comparison. Teammate conditioning does not change that explicitly labeled unconditioned lift baseline. Build queries expose moves/items/abilities/natures/SP vectors, teammate-conditioned distributions, move–move joint events and item frequencies conditional on a move. `--given-move` conditions build-field estimates only; teammate/lift summaries retain their stated design scope.

A two-or-more-teammate query with fewer than five eligible context designs withholds estimates, while retaining raw counts. This is an operational small-sample guard, not a significance guarantee. Single-context estimates flag denominators below 20 as small for inspection; this display flag is not a probability prior or statistical acceptance criterion. Empty contexts return `insufficient_data` with denominator zero. Missing fields are excluded and reported, not treated as absent values.

These are **finite selected-corpus design frequencies**, not probabilities of encountering a Pokémon/team in Ranked. Creator preference, editorial selection, success/publication bias, correlated team innovation, source coverage and missing builds remain. No random-sampling or independent-observation model has been established, so sampling confidence/credible intervals remain null. This avoids claiming a narrow interval for three related curated designs. No smoothing, synthetic team generation, marginal-independence substitution, clustering, online inference, M3.2 integration or M3.4 work is performed.

See [actual-data validation and example](../reports/M3.3-published-team-validation.md).
