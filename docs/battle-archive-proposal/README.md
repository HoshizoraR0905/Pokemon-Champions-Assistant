# Proposed long-term battle archive — 0.1.0

2026-10-31. **Design only:** no exporter, migration, runtime integration, dataset update or inference change is implemented. The [JSON Schema](battle-archive-v0.1.schema.json) and [synthetic partial-opponent example](partial-opponent.example.json) are proposals. Their version is independent of StateEngine schema 2 and decision-state schema 1.

Proposed destination: `reports/battles/<battle_id>/archive/<revision>/`, through BattleArtifacts. This is an immutable evidence export, not another authoritative BattleState, identity database or live hidden-state model. Keep existing canonical KnowledgeBase species/form/move/item/ability IDs and all original event/instance/episode IDs.

## Existing representations inspected

| Source | Information / limitation |
|---|---|
| `tracking/battle_state.py` | Fact knowledge/provenance/alternatives; HP history, stages, item/ability transitions, revealed moves/known slots, transformations/mechanics; side/field effects. Reserved unknown `hidden_configuration` is not an observed build. |
| `tracking/state_engine.py:EventRecord`, `to_dict()` | Original event, delivery/order, application status/reason/policy, bindings, revisions, retraction and state hash. Final state alone loses deferred evidence and chronology. `StateEngine.from_dict()` **calls replay**; passive export must not use it. |
| `tracking/identity_ledger.py` | `state.knowledge.identity_ledger` roster/aliases/entries and repeat-preview provenance. Preview membership does not establish selection or nickname identity. |
| `tracking/active_continuity.py` | `active_entry_episodes`, encounter/instance IDs, entry/departure evidence, possible prior individuals and continuity status. Species equality does not establish biological continuity. |
| `tracking/decision_state.py` | Compact current-state view and optional deterministic hidden constraints; explicitly incomplete. It omits history and cannot be the sole export input. |
| `tracking/hp_causes.py`, `resolution_context.py` | Saved sequential resolution projection: parent versus immediate cause, episodes/components, endpoints, per-hit capability, attribution and segment membership. |
| `battle_evidence/speed_replay_offline.py`, `speed_order/` | Bound instances, forms/priorities, causal context, admissibility and compact joint constraints. Action chronology is not automatically a raw-Speed inequality. |
| `metagame/published/`, `vgc_population.py`, `empirical_measure.py`, `experiments/build_similarity/data.py` | Public occurrence IDs, partial-field eligibility, source groups, form/item compatibility, joint cores and exploratory similarity. Preserve existing population/weighting contracts. |

## Compact package and example

`archive.json` contains the envelope, interned sources, subjects, assertions, original events, full receipt payloads, chronology, damage/Speed evidence, one final state checkpoint and loss ledger. Large sections may later use hash-addressed JSONL companions within the same revision; the envelope must identify encoding, counts, byte lengths and SHA-256. This is a future packaging option, not another schema or an implemented pipeline.

Store an original event once. A receipt retains every original field except its interned `event`, referenced by ID. Actions/facts reference those objects. Avoid full state snapshots at every frame or enumerated candidate universes. Preserve correlations using existing compact joint-domain representations or declared hash-pinned companions, never independent stat ranges.

The example demonstrates six preview members; two leads; one revealed backline member; one **unknown fourth selection**; one revealed move with unknown exact slots/item; absolute HP 100→84 with unknown cause/per-hit amounts; and an unresolved end-of-turn-order witness. It is synthetic, intentionally not accepted as a complete package, and asserts no real battle result. Its missing values do not invalidate the partial Pokémon record.

## Field/provenance contract

| Group | Contract |
|---|---|
| Envelope | Battle ID, archive revision/supersession, source run IDs, video identity, game/format/regulation/rules. Unknown format remains unknown. Population is `censored_battle_evidence`. |
| Sources | Original source/evidence/observation IDs, path/URI, byte hash or missing-hash reason, video time, original PTS/time base, availability, raw text/ROI references, separate OCR/parsing/visual confidence. Pinned knowledge/rule/public sources retain URL, revision when available, retrieval date, game/form applicability, version, license and attribution in provenance. No live network dependency. |
| Atomic facts | Subject, field, value, knowledge/basis, original source pointer, evidence/premise refs, availability/validity, alternatives and scope. Map observed→observed; derived→inferred with deterministic/constraint basis; hypothesis→assumed/provisional. Preserve source enums/raw payloads in loss accounting so mappings are reversible. Manual reviewed observations remain distinct from automatic recognition. |
| Unknown/conflict | Unknown requires null. Zero, false, known absence and unknown differ. Missing item activation does not prove no item. Conflicts retain separate assertions/provenance; no silent winner. Confidence is not an opponent-build probability. |
| Subjects/episodes | Reuse supported persistent IDs and keep encounter/entry IDs and continuity evidence. Unresolved encounters keep `possible_same_as`; never merge by species/nickname alone. Entries are appearances, **not independent build samples**. Preview-only subjects are valid. |
| Six-member roster | Six UI-position slots, each with identity claim/subject/preview evidence. Unknown rows remain null, never invented species. Exact form may remain unknown. Preview slot is neither selected-party order nor move slot. |
| Selected four | Four only under a verified format/profile; retain confirmed selected instances, leads, revealed backline, unresolved slots and admissible pools. Returning/fainting adds no individual. Six roster members are not six selected members. Unseen is not unselected; complement deductions need complete roster, selected count and resolved identities. |
| Moves | Revealed native membership is separate from exact known slots, PP and complete moveset. A single move is valid; unknown slots are not filled. Copied/Transform/temporarily available moves have separate scope and validity. Non-observation supplies no negative membership evidence. |
| Item/ability/form | Native/configured versus current/effective identities; suppression, consumption/removal/swap, Mega transitions and copied snapshots; causal event links. Consumed item remains original-build evidence. A copied ability is not native-build proof. Preserve ambiguous form alternatives. |
| Stats/SP | Displayed stats, calculated unmodified stats, stages/effective stats, Champions SP/alignment and inferred domains remain distinct. Preserve formula/profile/premises and disjoint/joint witnesses. Never fill unknown SP/EV/IV/nature with conventional defaults or substitute generic Gen-9 rules. Unsupported mechanics stay conditional. |
| Events/receipts/actions | Preserve all original payloads/deliveries, ordering, deferred/rejected observations, reasons, bindings, revisions/retractions and quantitative stage transitions. Chronology covers moves/switches/faints/field/status effects. Video occurrence, displayed-log time and knowledge availability differ. Command cycles are not verified game turns. |
| Damage | Actor/target/move may be unknown. Preserve action/parent/immediate-cause refs; before/after values/timestamps/maximum; absolute/percent/interval units; aggregate/sign convention; attribution; source segment membership; critical/effectiveness/context alternatives. Separate attack damage, recovery, recoil, self-cost and residual effects. |
| Multi-hit | Null individual hits means unknown, not zero/equal-split damage. Supported hit amounts require individual endpoint evidence/order and sampling capability. Announced hit count plus aggregate does not reveal each amount. Each numeric segment belongs once or has an explicit unresolved disposition. |
| Speed | Preserve action order, priority alternatives, speed stages, status/item/ability effects, dynamic activation, Trick Room/Tailwind and tie/reordering possibilities. A strict/equality/domain constraint requires saved admissibility and pinned applicable rules. End-of-turn order is a distinct witness with effect-specific rules; it does not automatically reveal raw Speed. |
| Causality | Inferences/comparisons carry premises and `available_at`. Rewind excludes later move/item/identity revelations and annotations unavailable then. Identity reconciliation never backdates knowledge. |
| Loss/retention | Every relevant source JSON pointer is mapped, raw-preserved, external-required, unsupported or missing with reason. Required external companions are hash-pinned. Structured acceptance, self-containment, pixel-review capability and complete frozen-artifact retention are separate flags. |
| Images | Preserve video/PTS/frame IDs/hashes even if screenshots are removed. `removed_authorized` and provenance identify the retention policy/cleanup ledger. Regenerated pixels cannot recreate original runtime measurements or restore the original frozen bundle's historical integrity. |

For example, two **supported** hit claims can separately retain absolute endpoints 100→88 and 88→79, yielding damages 12 and 9. Their total 21 is derived only when both belong to the same admitted action/target and exclude intervening effects. These are illustrative numbers, not measurements. If continuity is unproven, retain both encounters/possible linkage and exclude them from independent build-occurrence counting until resolved.

## Relationship to existing M3 datasets

Read-only query on 2026-10-31: existing `Teams(..., readonly=True).scoped(...)` plus `observed.eligibility`, source vgcmulticalc, tournament_published, M-C, Doubles, canonical version `published-team-identity-v1`:

| Counting unit | Count |
|---|---:|
| Selected active public team records | 1,083 |
| Teams with six eligible complete SP vectors | 557 |
| Teams with no eligible complete SP vector | 515 |
| Mixed-SP-completeness teams | 11 |
| Member occurrences / complete eligible SP / missing-or-ineligible SP | 6,498 / 3,397 / 3,101 |
| Eligible complete four-move member templates | 6,498 |

“About 500 with SP and about 1,000 without SP” is therefore not two verified disjoint current sets: there are about 1,000 teams **in total**, partitioned above. SP completeness alone is not full joint-build eligibility. The stricter existing `load_vgc` calculation/core checks retain 3,392 records; the saved M3.5.1 complete-move association pool has 3,388 occurrences and 551 connected evaluation groups. These are different units/filters, not 551 independent opposing builds.

A future optional comparison returns `(archive revision, as-of evidence time, dataset/source/population/regulation/format/version, candidate occurrence ID)` and field-level **compatible / contradicted / unresolved / not evaluated**:

1. Use existing canonical/form compatibility adapters. Base/Mega compatibility requires applicable stone/ability/form evidence; do not rewrite source sheets.
2. Unknown item/SP/ability contributes no mismatch. A complete candidate missing an established native equipped move can contradict membership; an incomplete candidate not listing it remains unresolved. Copied or uncertain OCR moves cannot become native hard exclusions.
3. Intersect damage/Speed/stat constraints only with their identity, rule/context and assumptions. Preserve complete joint survivors: never combine one witness's item with another's nature/SP. Missing candidate SP remains incomplete.
4. Optional similarity uses available eligible components and reports its mask/coverage. One matching field out of one known is not a full-build match. Never zero-fill SP or apply symmetric Jaccard as if unrevealed moves were absent. M3.5.1 embeddings/scales are exploratory versioned inputs, not an automatically deployed posterior.
5. Keep public publication/extraction/member occurrence IDs and missingness. One opposing persistent subject contributes one censored battle observation regardless of switches; multiple processing runs of one recording share a lineage and add no samples. Unknown continuity must not inflate independent counts.
6. Backline comparison conditions **public team** candidates on supported roster/lead/revealed-member facts and retains ambiguous matching assignments/feasible selected subsets. Six-member published teams do not supply bring-four/lead frequencies. Probability prediction needs future selection labels, documented censoring/selection assumptions and calibration; no invented equal priors across unseen choices.

Maintain three datasets with separate contracts: public complete/partial **build occurrences**; public **aggregate usage** with its season/rank/format/denominator; and our own **censored battle evidence** with capture/exposure quality and player/team/match grouping. Do not pool them into an unqualified empirical distribution. Preserve independent public occurrences under the current adapter; equality diagnostics/evaluation grouping do not change its weights. Learnset legality alone supplies no frequency prior.

## Export workflow (proposed; not executed)

1. Choose explicit saved source revisions through BattleArtifacts. Inventory manifests/seals, hashes, rule/knowledge profiles, input video, annotation independence and image-retention overlays. Keep alternative runs separate; do not guess across incompatible latest pointers.
2. Load saved `initial_state`, `state`, `history`, source events and existing saved HP/Speed projections directly as JSON. Do not call `StateEngine.from_dict()`, replay, OCR, decoding or a solver. Missing saved projections remain declared unavailable until a separately authorized enrichment.
3. Intern original payloads/receipts; retain every delivery/correction. Link roster, subjects and episodes using existing bindings/ledger while preserving alternatives. Extract histories and causal availability, not only final known values.
4. Export HP segments/resolutions and saved Speed/joint constraints; keep unsupported evidence raw. Every relevant source pointer gets an explicit disposition; unknown source fields require raw preservation or an acceptance blocker.
5. Validate and atomically publish a new revision with durable `inspect → normalize → reconcile → validate → publish` checkpoints and input/code/profile fingerprints. Reuse completed valid export stages; preserve successful partial work.
6. Leave source runs, M3 datasets and existing pointers unchanged. Consumers choose an explicit archive revision. Corrections supersede revisions, never mutate immutable event IDs.

## Validation and acceptance

Structural schema checking is only the first check. All refs must resolve, roster slots be unique, subject/time/battle scopes agree, and unknown/absence/zero/conflict survive. Verify source-pointer coverage against complete source key/count/hash inventories, including unknown new mechanics. A fixed mapping list without residual checks is insufficient.

Round-trip the interned original event+receipt objects and compare canonical hashes to saved originals. Reconcile all supported field histories/effect scopes and HP segment IDs exactly once, preserving units, endpoint/attribution ambiguity and individual-hit capability. Keep linked candidate domains correlated. Do not upgrade raw action/effect order without admissibility. Preserve deferred/retracted evidence and as-of timing.

Include single-move/unknown-item/SP records, consumed/swapped items, Transform/Ditto, ambiguous Mega forms, partial preview, incomplete capture, repeated nicknames, unsupported continuity and corrections. Repeated appearances must not add build samples; incomplete selection must not become four known members.

Structured self-contained acceptance fails when required residuals/companions are missing. Pixel-independent structured acceptance can coexist with authorized image removal, while independent pixel-review and complete frozen-bundle flags must be false. Matching saved data is not measured recognition accuracy.

Future validation should start with small curated contract fixtures, then one saved battle and relevant regressions. No exporter implementation, exporter tests, recognition or full replay was performed for this design.

## Storage estimate

Measured in memory from existing saved JSON, without export or compression. The following are minified UTF-8 original receipt objects plus one final state:

| Saved source | Receipts | Receipt bytes | Final-state bytes | Combined MiB |
|---|---:|---:|---:|---:|
| B9 message baseline | 598 | 5,626,748 | 2,793,428 | 8.03 |
| B12 action acquisition | 1,148 | 2,931,933 | 1,566,412 | 4.29 |
| B16 first production | 1,290 | 3,850,465 | 2,011,937 | 5.59 |
| B23 first production | 2,036 | 4,944,106 | 3,085,150 | 7.66 |

Initial planning range: **5–15 MiB per structured evidence archive**, provisional **20 MiB/battle allowance**, excluding original video, images, shared models/datasets and large solver companions. For 15 battles, 75–225 MiB; 300 MiB at the provisional allowance. B9's raw candidate payloads show why a few kilobytes cannot preserve current semantics.

Provenance interning and removal of duplicate snapshots may reduce size, but savings are unmeasured. Full OCR/frame-observation residuals can exceed 20 MiB; the future exporter must measure and report overages, never drop evidence to fit the estimate. A lean analytical index is not an evidence-grade replacement. B9–B23 original videos occupy about 16.036 GiB; B16–B23 video costs about 107 MiB/minute independently. Optional curated crops add measured bytes; no compression benefit is claimed.

## Minimal future migration: B9–B23

1. Inventory saved revisions/lineage/retention, including the newly authorized B9/B12/B16 screenshot reduction. Choose reviewed baselines and separately attributed enrichment; multiple runs are not independent samples.
2. Prototype **one B23** export into a new namespace. Preserve its first run's unbound team-linkage result; later Team 7 calculations were not first-run runtime inputs. Missing evidence is not permission to regenerate video.
3. Validate loss accounting/round-trip/partial-build behavior. Add a separately attributed B12 reviewed damage/SP/Speed package to exercise joint constraints.
4. Export B9–B23 one battle at a time, only missing/invalid export stages. Unknown roster/selection/per-hit/Speed values remain unknown. Keep explicit source revisions and incomplete-comparison reports.
5. Compare retrieval with existing saved M3 evidence; opt consumers in only after semantic acceptance. No dataset reweighting, training, strategy milestone or structured-source deletion is authorized by this design.
