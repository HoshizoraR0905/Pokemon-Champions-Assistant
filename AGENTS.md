# Pokémon Champions Assistant: repository instructions

Apply these instructions to all milestones, including M3.1 and beyond. Follow the
user's current scope; do not start the next milestone or commit/push unless asked.

## Explore progressively

- Start with the working-tree status and the relevant entry points, interfaces,
  definitions, callers, and tests. Do not read the whole repository.
- Use `rg --files`, targeted `rg -n`, and narrow `sed -n` ranges. Locate a class or
  function before reading its implementation in a large Python file.
- Search source directories explicitly. Exclude `.cache/`, generated reports,
  datasets, videos, extracted frames/screenshots, OCR dumps, full-state snapshots,
  large HTML timelines, benchmark JSONL, and temporary outputs from broad searches.
- Read such artifacts only by explicit path and with targeted queries or compact
  summaries. Do not dump large generated reports to find source-code symbols.
- Reuse established task context. Re-read files only when changes or new evidence
  justify it; expand the search scope when correctness requires it.
- Distinguish curated fixtures and annotations from generated output. Inspect
  manually curated ground truth when needed for testing or validation.

## Repository map and existing abstractions

- `main.py`, `api/`, `capture/`, `recognition/`, `streaming/`, and
  `stream_replay.py` provide capture, recognition, and streaming entry points.
- `battle_events/` holds evidence-backed event schemas and parsing; `tracking/`
  holds observable state, mechanics, hidden constraints, and the decision-facing
  projection. `damage/` is the existing damage-calculation package.
- `knowledge/` contains shared knowledge and rule evidence. Inspect existing
  adapters, representations, and databases before adding new ones.
- `scripts/` contains milestone processing and validation commands; `tests/`
  contains focused tests and curated fixtures. Check command arguments before
  invoking a processing script; defaults may process every recording.
- Use `BattleArtifacts` in `battle_artifacts.py` for recording-owned paths and
  ownership checks. Canonical paths are `.cache/battles/<battle_id>/` and
  `reports/battles/<battle_id>/`; curated report inputs live in `inputs/`.
  Preserve legacy aliases and immutable source/event IDs. Shared models and
  knowledge remain outside individual battle namespaces.
- Extend established modules where appropriate. Avoid broad refactoring for a
  localized task or duplicate event/state structures, databases, and adapters.
  Document intentional architecture changes and compatibility implications.

## Cache-first, scoped execution

- Before expensive work, inspect existing stage manifests, output availability,
  input fingerprints, pipeline/adapter versions, rule profiles, and relevant
  implementation dependencies. Reuse compatible completed results.
- Run only missing or invalidated stages. A disconnect is not cache invalidation.
  Avoid repeated decoding, OCR, or full replay; do not regenerate five battle
  reports to test a localized change.
- Process one battle at a time unless parallel execution is clearly justified.
  Isolate all evidence, outputs, and checkpoints by `battle_id`.
- Do not delete or overwrite caches without explicit justification. Record the
  invalidation reason and preserve reusable successful stages.
- Break large tasks into independently testable stages: inspect, give a concise
  plan, implement one component, test it, save progress, then continue. Run
  broader relevant regression checks after the components are integrated.

## Recoverability and long-running work

- Expensive scripts must show progress, checkpoint meaningful partial results,
  and record stage status, input/version identity, outputs, and errors in a
  manifest or equivalent durable record. Prefer atomic checkpoint writes.
- Preserve successful stages when a later stage fails. Document exact resume
  commands, scoped battle/stage arguments, completed work, and remaining work.
  Essential intermediate state must not exist only in chat history.
- On resuming: inspect the working tree, check running processes, inspect the
  relevant manifests and outputs, find the first incomplete/invalid stage, and
  resume there. Do not launch a duplicate job while one is still active.
- Keep changes scoped and preserve unrelated working-tree edits.

## Evidence and mechanics

- Distinguish direct observations, deterministic deductions, provisional
  assumptions, and unresolved evidence; preserve provenance for each.
- Separate verified Champions mechanics from Showdown or community references.
  Do not silently substitute generic Pokémon rules for unverified Champions
  behavior. State unsupported mechanics and their practical limits explicitly.
- Unknown information stays unknown. Do not invent opponent moves, held items,
  abilities, stats, EVs, IVs, natures, or arbitrary Bayesian priors. Any priors must
  have a justified, documented source. Revealed move membership does not establish
  exact move slots.

## Project-wide knowledge sources: 52Poké

- Treat [52Poké (神奇宝贝百科)](https://wiki.52poke.com/) as a major
  structured knowledge reference throughout the project, beyond its damage
  article. Relevant subjects include species and forms; base stats and stat
  mechanics; types and matchups; abilities and held items; moves and their power,
  category, accuracy, PP, targeting and effects; Pokémon-specific learnsets;
  evolution and Mega Evolution; battle mechanics and damage formulas; and
  game-specific availability, restrictions and rules.
- For Champions tasks, explicitly check for applicable Champions-specific
  information, including species/form learnset pages such as
  [大狃拉/Champions招式表](https://wiki.52poke.com/wiki/大狃拉/Champions招式表).
  Prefer applicable Champions data over unrelated Generation 9 learnsets or
  generic game assumptions. Respect form and game/version differences. A move
  appearing in Scarlet/Violet does not establish Champions availability; absence
  from an unrelated generation's learnset does not establish unavailability.
  Champions learnability establishes possible moves, not equipped slots,
  battle-revealed membership, or move-usage probabilities.
- Select sources by the scope of each fact: official Pokémon Champions
  documentation for official rules and availability; 52Poké for detailed data,
  Champions learnsets and documented move/item/ability mechanics; pinned local
  data and PokéAPI for canonical identity and general structured data; and pinned
  Pokémon Showdown Champions implementations for executable mechanics references
  and independent calculations. No source is authoritative for every field.
  Preserve conflicting values and provenance rather than silently overwriting
  facts. Do not substitute Generation 9 mechanics or learnsets for unverified
  Champions behavior.
- Integrate validated facts through source-specific, versioned supplements to
  the existing `KnowledgeBase`, using its canonical species, form, move, ability
  and item IDs and Chinese/English name resolution. Do not create a competing
  identity database. Preserve per-fact provenance and game/form applicability;
  keep source assertions distinct when they disagree. Future supplements should
  support base-stat, form, Champions learnset, move power/PP, ability/item and
  Champions mechanics queries. This policy alone does not authorize implementing
  a supplement, importer or crawler.
- Record each article's URL, revision ID when available, retrieval date and
  applicable game/version. Preserve licensing and attribution requirements.
  Prefer reproducible local snapshots for runtime use; battle analysis and
  damage calculation must not require live network access. Validate parsed
  tables against their actual headings and form columns. Distinguish missing or
  incomplete data from confirmed absence; an incomplete learnset does not prove
  a move impossible. Keep research scoped: avoid unbounded crawling and repeated
  full-site fetching.
- Apply this policy to all relevant milestones, including M3.1 forward damage,
  M3.1.1 inverse constraints, later M3 mechanics/inference, M2.3.4 recognition and
  entity validation, hidden-state feasibility, form-specific move legality, and
  future Bayesian inference and strategy work. Learnset feasibility supplies no
  probability prior by itself. These examples do not authorize advancing scope.

## State consistency

- Preserve the responsibilities of observable state, hidden configuration, and
  the unified decision-facing projection. Do not independently duplicate
  authoritative facts across layers.
- Maintain stable Pokémon instance identities across switches and persistent
  revealed moves. Apply quantitative stat-stage transitions when supported.
- Prevent double application of move effects and Battle Log effects; preserve
  correction/retraction behavior and cross-battle isolation.
- When changing state behavior, add meaningful regressions for previously
  verified behavior. New features must preserve established facts under
  equivalent inputs and rule profiles.

## Validation

- Use the smallest meaningful checks first: focused unit tests, relevant
  integration tests, cached replay checks, then milestone regressions. Run
  expensive multi-video validation only when needed to resolve a real concern.
- Use the existing environment, for example
  `.venv/bin/python -m pytest -q tests/test_hidden_state.py`.
  `pyproject.toml` configures the repository import path for pytest.
- `local_artifacts` tests use optional historical evidence; select portable tests
  with `.venv/bin/python -m pytest -m 'not local_artifacts'` when appropriate.
  Missing optional artifacts may skip tests; present but failing artifacts must
  not be treated as missing. Check tests for expensive side effects before running.
- Distinguish automatic recognition, curated ground truth, mechanical deductions,
  provisional assumptions, and unresolved observations in validation results.
  Deterministic replay success is not recognition accuracy or semantic coverage.
- Never claim unmeasured accuracy or coverage. Report mismatches, deferred events,
  missing comparisons, skipped checks, and partial acceptance honestly.

## Git and artifact hygiene

- Normally track source, tests, rules, configuration, documentation, small curated
  fixtures, and concise validation summaries.
- Respect `.gitignore`: videos, OCR caches, extracted frames, full-state JSON,
  large generated HTML, benchmarks, and temporary artifacts normally stay local.
  Do not delete local artifacts merely to reduce Git size.
- Preserve the existing curated-input exceptions and small-summary allowlist.
  Do not place generated dumps in `reports/battles/<battle_id>/inputs/`.
- Do not use `git add .` indiscriminately. Review explicit paths and staged diffs.
  `scripts/review_git_tracking.py` audits the index without staging changes;
  `tests/test_git_artifact_policy.py` covers artifact/alias conventions.
- `scripts/setup_battle_workspace.py` recreates compatibility aliases for existing
  targets. Migration is a separate operation, not a way to reconstruct missing
  evidence. Do not commit or push unless explicitly requested.

## Communication and handoff

- Give a concise execution plan for substantial tasks. During long operations,
  report meaningful completed/current stages, reused caches, blockers, and partial
  validation results; avoid narration of unchanged work.
- Leave durable handoff notes and resume commands for interrupted tasks.
- At completion, concisely identify changed files, resulting behavior, tests and
  results, limitations, and remaining work. Separate generated-artifact completion
  from semantic acceptance; do not advance milestones on replay success alone.

## Sampling policy for M2.3.3 and later

- The target default video sampling rate is 2 FPS (one frame every 0.5 seconds).
  M2.3.3-A must use existing caches without changing sampling, extracting frames,
  or rerunning OCR; sampling implementation belongs to M2.3.3-B.
- In M2.3.3-B, expose one documented sampling setting, include it in cache
  fingerprints/manifests, and support changing to 3 FPS without restructuring.
  Keep frame sampling frequency independent of OCR invocation frequency.
- Reuse compatible frames and recognition results; evaluate runtime and OCR cost
  on a scoped recording before processing all five videos. Faster sampling for
  brief UI states or individual multi-hit impacts is a future requirement.
