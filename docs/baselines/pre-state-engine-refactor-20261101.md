# Reproducible baseline before StateEngine refactor — 2026-11-01

Baseline tag: `pre-state-engine-refactor-20261101` (annotated). Source branch: `m2.3.1-clean-artifacts`; parent commit `73bb0fe`. The tag identifies the exact reviewed source, tests, curated inputs and documentation before any architectural refactor. Follow-up work belongs on `refactor/battle-state-architecture`; incomplete refactor changes are not part of this baseline.

## Current architecture and supported behavior

`main.py`, `capture/`, `recognition/` and `streaming/` provide capture/acquisition and streaming/replay entry points. Event-driven video recognition defaults to 2 FPS, with frame sampling distinct from OCR scheduling. Battle Messages, HUDs, banners, preview icons and explicit UI observations are represented as evidence-backed events by `battle_events/`. Recording ownership is isolated with `BattleArtifacts`; canonical local locations are `.cache/battles/<battle_id>/` and `reports/battles/<battle_id>/`.

`tracking.state_engine.StateEngine` stores an initial `BattleState`, an ordered `EventRecord` history, and a replayed state. It distinguishes accepted, partial, deferred, rejected and retracted events. Trial-state copies isolate failed transitions. Replay supports corrections/retractions and produces receipt hashes over exported state. `tracking.battle_state` uses nested dataclasses for facts, Pokémon, sides and field effects. Unknown information differs from zero, false and known absence.

Observable tracking includes persistent identity/entry continuity, active slots, HP readings/causes, revealed moves/items/abilities, status and quantitative stat stages, transformations, weather/terrain/Trick Room, side conditions and evidence provenance. Identity records and HP histories currently remain embedded in growing state payloads, including departure snapshots and return proofs. Existing decision-facing projections and HP-resolution adapters supply the downstream mechanics/inference interfaces.

`damage/` supplies forward/inverse damage calculation and connected-hit handlers using pinned rule/data profiles. `speed_order/` supplies explicit-state action ordering; `battle_evidence/` joins saved evidence, identity, command cycles, configuration domains and chronological inference. `knowledge/` remains the canonical identity/name/stat database. Source-specific Champions applicability and 52Poké revisions remain separate from provisional Showdown executable mechanics references.

Recent B20–B24 work adds preview/switch continuity repair, named HP endpoint repair, initial/entry conditions and quantified stage messages, additional damage contracts, shared SP/alignment constraints, saved-event inference adapters and B24 evaluation tooling. The latest Speed preference solves accumulated evidence without speculative Iron Ball first, uses unobserved Iron Ball only as a necessary SP=0 fallback, and respects positively established item facts. Under that explicit preference B24 Tyranitar retains intrinsic Speed {72}; this is not an observation proving item absence.

## Known limitations preserved without fixes

- Live named uses can be admitted as `move_revelation_only`; this does not certify complete effect execution. Recognition metrics, curated truth, deterministic replay and semantic coverage remain different measurements.
- Command windows are provisional. Only supported local action membership can supply numerical Speed evidence; absolute game-turn numbering remains incomplete. Unknown modifiers, unsupported execution callbacks and ambiguous identities block inference.
- Hidden stat/item/move possibilities have no invented probabilities. Default non-HP SP domains remain downward SP=0 and neutral/upward SP=0…32, one global alignment and total SP≤66. Joint marginal projections are not a complete certified hidden-configuration solution.
- Some mechanics are exact only under the pinned provisional reference profile, not independently Champions-certified. Original versus current item ownership and transfers remain distinct.
- Speed preference currently requires a supported same-form/item epoch; reliable changes needing richer temporal transitions remain unresolved. Prior preferred marginals must not become hard evidence.
- State replay currently performs whole-state copying and full state-to-dict/JSON hashing per processed receipt. HP enrichment repeatedly traverses prefixes/histories; departure and return proofs duplicate historical payloads. The diagnosis establishes strong leads and terminal component costs, not an isolated historical production function-time attribution.

## Historical performance and semantic evidence

The B21–B24 comparison below retains original external CLI timing definitions; subsequent projections, sealing and diagnostic inference are excluded. No video/OCR/production benchmark was rerun to create this baseline. Existing function microbenchmarks are separate from historical production timings. No production PTR improvement is claimed.

Detailed references:

- [B24 evaluation](../../reports/B24-evaluation-20261101.md) and [handoff](../b24-evaluation-20261101/handoff.md).
- [Speed action-order failure audit](../b24-evaluation-20261101/speed-order-failure-analysis.md).
- [Iron Ball last-resort preference and six-member results](../b24-evaluation-20261101/speed-order-iron-ball-last-resort-v1.md).
- [Runtime diagnosis](../performance/b24-runtime-diagnosis.md) and [measurements](../performance/b24-runtime-diagnosis-measurements.json).
- [B20–B23 focused repair](../../reports/B20-B23-focused-repair-20261101.md) and [inference integration](../../reports/B20-B23-inference-integration-audit-20261101.md).

## Publication and artifact boundary

The baseline includes reviewed source, focused tests, small curated fixtures/annotations, source revision records and concise diagnostic reports. Generated `reports/battles/*/diagnosis/**/trace-*.md` expansions are intentionally ignored, in addition to existing video/cache/frame/OCR/full-state/HTML exclusions. Existing successful outputs and ignored local evidence are preserved on disk. No ignored artifact is force-added.

Source/document publication was scanned for private-key blocks, GitHub-token formats, API-key formats and literal secret assignments; no matches were found in the proposed change set. Machine-specific absolute paths occur in historical benchmark commands/profiles and curated evidence locations. They are provenance strings rather than credentials. Those records are retained unchanged, since rewriting them would invalidate source identities and diagnostic checksums. They do not make absent local evidence portable.

GitHub alone cannot reproduce full saved B20–B24 replays: original MP4s, frame/OCR/icon/model caches, full production `replay.json`/observations, large context JSONL files, stage manifests and expanded traces remain local. Source seals/hash lists identify the local evidence, but cannot reconstruct missing bytes. Portable tests use tracked synthetic/curated inputs. Optional `local_artifacts` checks require separately available evidence; missing optional evidence may skip, while present failures must remain failures.

For local recovery, see the existing handoffs and versioned stage manifests. Baseline validation uses cached/synthetic inputs only and explicitly excludes tests which decode videos or invoke real OCR/icon models. Publication follows reviewed explicit paths and an index audit; no broad `git add .`, force-push or history rewrite.

## Original benchmark table

| Battle | Video (s) | External CLI (s) | PTR | Broad reconstruction/package (s) | OCR cumulative (s) | Receipts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B21 | 703.21 | 559.751 | 0.795994 | 160.815 | 212.847 | 1384 |
| B22 | 860.18 | 850.076 | 0.988254 | 387.361 | 330.679 | 2212 |
| B23 | 787.28 | 803.717 | 1.020878 | 357.967 | 319.898 | 2036 |
| B24 | 1052.82 | 1460.984 | 1.387686 | 858.584 | 428.594 | 2780 |

## Baseline validation and review

Selected 39 portable regression modules covering state, identity, HP, mechanics, event adapters, damage/Speed inference, configuration domains, replay projections and artifact policy: **1765 passed, 15 local-artifact tests deselected in 146.54 s**. Exact command and results: `pre-state-engine-refactor-20261101-validation.json`; local full log: `.cache/baselines/pre-state-engine-refactor-20261101/regressions.log`. No acquisition/model tests were selected. Frozen/historical B24 validation passed. Index audit found no ignored tracked paths or broken/untracked symlink targets. Staging exposed two existing extra EOF blank lines in `battle_evidence/constraint_trace.py` and `scripts/trace_hidden_constraints.py`; source bytes and existing fingerprints are preserved rather than changed for formatting. No correctness issue was fixed in this phase.
