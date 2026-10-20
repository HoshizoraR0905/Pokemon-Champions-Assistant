# M3.3 current Ranked statistics cache

The `metagame` package is an offline-queryable **application cache of current Pokémon Champions Ranked statistics**, supplied by [Pokémon Champions Battle Data](https://championsbattledata.com/api_guide). Its population label is `third_party_claimed_ingame_ranked`: the provider identifies it as in-game Ranked data; the project's audit has not independently verified capture, sampling or eligible rating population. No Showdown or tournament statistics are loaded into this database.

The source [allows application use and reasonable caching](https://championsbattledata.com/api-rules/). This implementation neither maintains a permanent historical mirror nor exports a public data feed. Attribution accompanies table and JSON outputs. There is no scheduled background network activity.

## Run and inspect

Use the existing environment; fresh installations can install the optional `metagame` dependency group (`requests`). The module form works without reinstalling the project:

```sh
# Default pilot: the nine requested Pokémon, current Doubles only.
.venv/bin/python -m metagame refresh

# Read SQLite only. No network, model inference or battle acquisition.
.venv/bin/python -m metagame query 大嘴鸥 --teammate 铝钢桥龙
.venv/bin/python -m metagame query Pelipper --teammate Archaludon --output json
.venv/bin/python -m metagame query Archaludon --top 10
.venv/bin/python -m metagame coverage
.venv/bin/python -m metagame snapshots

# Revalidate only the index and these two species, sending HTTP validators.
.venv/bin/python -m metagame refresh --species Pelipper Archaludon --force

# Configurable freshness/rate/retention, still a current application cache.
.venv/bin/python -m metagame refresh --refresh-hours 24 --request-interval 2 \
  --retention-days 7 --max-versions 2

# Apply retention without networking. Operates only on the owned cache.
.venv/bin/python -m metagame prune --retention-days 7 --max-versions 2
```

The default cache is `.cache/metagame/current-ranked/`. Use the global `--cache PATH` before the subcommand for an isolated cache; the directory must be empty or carry this package's ownership marker. `champions-metagame` is also registered as a package script. Explicit `--species` limits the requested entities; Chinese/English exact names and exact indexed identifiers resolve through the shared KnowledgeBase. Female Indeedee stays distinct from male/default Indeedee. Ambiguous requests fail; unknown entities in source rows remain unresolved with their original labels, rather than being fuzzily replaced.

`refresh` supports `--format Singles` for isolated future collection. `query --format Singles` explicitly selects that format; the default query remains Doubles. No Singles collection was performed for pilot acceptance.

## Cache lifecycle and recovery

Fresh successful HTTP responses are reused for 24 hours by default. After that, or with `--force`, requests send the last ETag and/or Last-Modified validator. A 304 retains the immutable current bytes and advances the validation time. A 200 writes the original response to `raw/<sha256>.bin` before normalization. HTTP timeouts are 30 seconds, with at most two retries, exponential backoff, a two-second default request spacing, bounded 16 MiB response bodies and sequential concurrency (one request). Rate spacing is persisted across runs. No login, CAPTCHA, forbidden endpoint or redirect is bypassed. A Retry-After exceeding 60 seconds stops the request for later resumption, instead of retrying early.

Retention is enforced following a refresh with successful species, or by `prune`: seven days since last HTTP validation and at most two retained raw/parser versions per URL by default (configurable maximum 1–3). Superseded/expired normalized snapshots and unreferenced owned raw responses are removed. SQLite pages are reclaimed when snapshot rows are removed. A still-current response can survive a 304 revalidation; this is a current application cache, not seven days of season history. Offline queries do not mutate or trigger cleanup; they label data older than the query freshness window `stale_cache`. A dormant application does not run a deletion daemon; run `prune` for offline cleanup.

Pruning requires this package's ownership marker and never traverses other caches, audit evidence, battle namespaces or historical datasets. Raw deletion is limited to the managed 64-hex-digest `.bin` namespace. HTTP current receipts are one per URL; last-error receipts and run manifests are capped at 20 and the retention age. Locally generated query/coverage exports made by the caller are outside the retention manager. Do not use the cache to construct a historical archive or publicly redistribute its raw dataset.

Each run checkpoints `runs/<run-id>.json` after the index and every species, recording successful snapshot IDs, errors, requests, elapsed time and the retention decision. Each species normalization is transactional; schema failure does not replace a previous valid projection. A single-writer lock prevents duplicate ingestion against the same directory. Retrying the same command resumes through reusable current HTTP responses and deduplicates identical raw/parser/knowledge identities; it does not repeat fresh API requests. A failed species can be retried alone with `--species NAME --force`, preserving earlier successful species. Interrupted normalization can be reconstructed from retained original bytes.

The SQLite schema uses ordered migrations (`PRAGMA user_version=1` and a migrations table); unknown future versions are rejected. `sources`, `snapshots`, `subjects` and typed `metrics` tables store source assertions and a projection of the shared canonical IDs. No new identity database is introduced. Typed JSON metric records hold extra spread/alignment/provenance fields without collapsing their distinct semantics. Content/parser/knowledge fingerprints isolate changed normalization. The initial version has no historical-season ingestion route.

## Statistical methodology

Every query returns source attribution, population label, format, raw hash, parser/normalizer and KnowledgeBase identities, retrieval/check timestamps, index generation/data version, source `Current` season, and the source file path. Actual game version, regulation, source publication timestamp, exact season identity, rating eligibility, sampling method and weighting remain unknown. `index_generated_at` identifies the provider's index build, not a certified game-capture time. Source metadata called `baseStats` is not imported as canonical base stats.

The `column_position` in current battle rows supplies the **ordinal species usage rank**. It is not P(A). Move, item, ability, nature and spread `percentage_value` entries are preserved as source-reported percentages and 0–1 proportions. Their exact eligible denominator is unpublished. Numerator, denominator, sample count, effective sample size, weighting and confidence intervals are all null. A source-reported 0% remains rounded 0%, not proof of impossibility. There is no multiplication of rounded percentages by an unrelated battle count, rescaling of a leading-entry table to 100%, inferred prior, automatic smoothing, or estimate pooling across cache versions.

Teammates are an **ordered list**, with absent percentages. Preserve rank and unknown proportion; do not make the first teammate a 100% event or infer probabilities from ranks. P(B,C|A), move/item/ability/nature/SP given teammate, two-move joint frequencies, complete movesets, contextual archetypes and individual builds all return `unavailable_joint_data`. Selecting Archaludon in the query does not condition Pelipper's displayed marginals. Co-occurrence probability, lift, lead/selected/revealed usage and win rate remain unavailable. Full six-member teams are not supplied; no such records are manufactured.

Spread type is explicitly one of `champions_sp`, `legacy_ev`, `observed_final_stats`, `unknown`. For this source, `stat_points` plus the six ordered named point columns supports **source-asserted Champions SP**. It is not inferred merely from numbers looking small. The provider's field definitions/display path were inspected; no client EV conversion is used. Complete six-vectors retain HP/Attack/Defense/SpA/SpD/Speed order and are validated by `knowledge.champions_stats.validate_training_points` under the existing versioned 52Poké profile, with rule hash retained. Invalid/incomplete rows stay preserved and flagged; missing components stay null. Their extraction accuracy is not independently certified.

Nature is a separate marginal and is never joined into a synthetic build. Ability, form, nature, level and other parameters must be evidenced together before a final-Speed/defense distribution is possible. No such joint input exists here. Per-stat projections report only the summed mass of the published valid SP vectors, explicitly scoped to those leading rows. They do not fill the missing tail, supply population medians/quantiles, or infer independent allocations despite the shared budget. No clustering is justified.

`metagame.statistics` provides guarded Wilson intervals for caller-supplied positive unweighted binomial counts, descriptive pair/lift calculations for explicit same-population joint team counts, and opt-in hierarchical Dirichlet means requiring documented integer child/parent counts and explicit prior strength. Those utilities are tested with synthetic counts and are **not applied** to this source. Weighted masses and rounded percentages are rejected as independent counts; source data never gains an invented interval or effective N. Six-team-slot association is descriptive, not causal.

## Review and scope

See [source audit](../reports/M3.3-source-audit.md) and [pilot validation](../reports/M3.3-pilot-validation.md). Only the agreed nine-species pilot was collected. The index may enumerate more supported species, but enumeration is neither collection coverage nor verified game-rule legality. Wider collection is a separate invocation after pilot review. M2.4/M3.2 behavior, battle fixtures, active Bayesian inference, damage prediction and strategy remain outside this package.
