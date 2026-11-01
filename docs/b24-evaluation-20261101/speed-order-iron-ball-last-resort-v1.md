# B24 Speed inference — Iron Ball last-resort preference v1

Date: 2026-11-01. Rule: `user-iron-ball-last-resort-v1`.

The new user preference changes Tyranitar's retained intrinsic Speed from **{72, 81–119, 121–124} to {72}**. Its non-Iron-Ball domain satisfies the accepted evidence, so speculative Iron Ball configurations are not retained. All other opponents' Speed marginals are unchanged. This is a result under a user-selected inference preference, **not proof that Tyranitar lacks Iron Ball or that Speed 72 was directly observed**.

The previous [action-order audit](speed-order-failure-analysis.md), its original `audit-v4.json`, the completed diagnostic contexts and the frozen production run remain unchanged. That earlier audit correctly described the union of all supported item alternatives; this report supersedes its *preferred inference result* under the additional rule. No video, OCR, icon recognition, StateEngine replay or production CLI was rerun. Performance investigation results were not modified.

## Implemented decision policy

`battle_evidence.speed_preference.infer_saved_speed` uses the existing M3 ordering engine and Champions SP calculator. It first intersects **all accepted comparisons for one persistent Pokémon** using shared native SP, global alignment, current form, ability and item witnesses. Speed stages, status, field and Tailwind come from each observation's saved context; a hidden item is not chosen afresh per comparison.

The first pass excludes unobserved Iron Ball. If any complete non-Iron-Ball witness survives the accumulated constraints and applicable Item Clause matching, only those witnesses are retained. Neutral items, Choice Scarf and Quick Claw alternatives remain available where permitted by existing mechanics; the new policy does not remove other uncertainty or assign probabilities.

Only when that pass is exactly empty, with no unresolved modifier, and Iron Ball is not excluded by reliable held-item/ownership information, is the speculative Iron Ball pass considered. It fixes **Speed SP=0**, retaining permitted Speed alignment branches and the existing shared 66-SP budget. Effective Speed and rounding are evaluated by the existing engine, not a new arithmetic formula. If that pass is also empty, the result is a contradiction; unresolved engine/modifier evidence remains unresolved and does not trigger a fallback.

An explicitly established Iron Ball is used directly. The speculative preference and its fallback-only SP=0 restriction do not replace observed item facts or narrow an observed Iron Ball's ordinary permitted SP domain. Tests include later positive Iron Ball evidence reopening a previously preferred singleton. A known empty slot or another known item cannot be replaced with a hypothetical Iron Ball.

The default non-HP domain is unchanged: downward alignment SP={0}; neutral and upward alignment SP={0,…,32}. There is no unrestricted-domain retry. One global alignment and total SP≤66 remain joint constraints. The final Speed rows are rechecked against that shared budget, including implications for other stat marginals.

## Chronology and interface changes

`SavedSpeedInference` retains the hard stat domain and immutable source comparisons, then recomputes the whole conjunction whenever a new comparison arrives. It never feeds its prior preferred Speed marginal back as a hard mechanical constraint. Consequently a later observation can make the non-Iron-Ball conjunction empty and reopen previously disfavored intrinsic speeds through SP=0 Iron Ball witnesses. The ledger preserves earlier results and source IDs for chronological reporting.

`invert_saved_order` now uses this policy for its single-observation interface. `_order_form_union` remains the internal unpreferred support enumerator. `ChronologicalTrace.speed_pairs` uses one ledger per persistent member instead of intersecting independent marginal solutions. `scripts.evaluate_b24.joint_projection` recomputes conditional joint marginals from the saved hard domain; damage constraints are recorded separately from a preferred Speed projection so that preference-dependent branches can be restored. The production recognition/StateEngine paths are unchanged.

The team layer reuses `battle_evidence.team_items.matching`. Hypothetical loadout alternatives must have an all-different completion; an Iron Ball reserved by another supported original-loadout hypothesis cannot be reused. Hard original-item exclusions retain their existing evidence scope. Current observed possession is **not** silently converted into proven original ownership, particularly across transfers or consumption. The direct API accepts reviewed team item domains and tests a competing Iron Ball owner. B24's final speculative domains contain no Iron Ball and admit a joint Item Clause completion; the saved matching is a compatibility witness, not an inferred equipped team.

The saved adapter currently certifies one shared current-form/item epoch. Reliable item or form changes needing explicit temporal transitions are reported as unresolved rather than solved by switching hidden items between observations. Missing Trick Room, Speed stages, status or Tailwind likewise prevents an exact projection. This retains the prior evidence limitations; it does not introduce a new turn engine or silently substitute generic game mechanics.

## B24 supporting evidence

The relation becomes available at the end of certified command cycle 12, **954.526667 s**. The principal pair is:

| Action | Time (s) | Source event ID |
| --- | ---: | --- |
| Grimmsnarl Spirit Break | 930.506667 | `event:b04c832694bde680a01262e4` |
| Tyranitar Curse (displayed 咒术) | 943.525000 | `event:5785e44cdf6b514c0d4a86d5` |

Both effective priorities are 0. Trick Room is inactive; both Speed stages are 0; neither side has Tailwind; statuses are `none`. Grimmsnarl's verified unmodified Speed is 80. Thus the supported relation is Tyranitar effective Speed **≤80**, with ties permitted. Curse's subsequent Speed reduction is not applied retroactively.

Under the default stat domain, the non-Iron-Ball explanation retains intrinsic Speed **72**, Speed factor **0.9**, SP **0**. The four surviving global alignment patterns raise one of Attack, Defense, Special Attack or Special Defense and lower Speed. Choice Scarf cannot satisfy the bound; the Quick Claw possibility must be unactivated and also retains 72. Unknown neutral-item equivalence is not a claim that its item slot is empty. Iron Ball would allow faster intrinsic values, but those alternatives are excluded by the preference because the non-Iron-Ball conjunction is feasible.

The other valid relation is Archaludon Protect → Mega Steelix Protect at **920.005→925.005 s**. Archaludon's Speed is 116, its item slot is explicitly empty, and Steelix's full 45–90 intrinsic domain already satisfies that order. Its exact source IDs and saved state are included in the versioned inference JSON and the preceding audit.

The 30 deduplicated candidates now classify as **18 different/uncertain priority, 10 uncertified cycle, 1 valid without marginal reduction, 1 valid and numerically informative**. No blocked candidate was promoted to valid by the item preference. There are no new contradictions or unresolved modifiers in the two accepted numerical comparisons. Other source recognition, cycle and callback limitations remain documented in the previous audit.

## Six-opponent results

All ranges are inclusive integer sets of intrinsic, unmodified native Speed. “Before” is the previous audit result. Each opponent's non-Iron-Ball domain remains feasible and **none needs an Iron Ball fallback**. For preview-only or otherwise uncertified members, this means the default domain has no admitted Speed comparison to contradict it, not that every candidate action was explained.

| Opponent | Before | After | Speed factor / SP | Global alignment patterns |
| --- | --- | --- | --- | ---: |
| 班基拉斯 | 72, 81–119, 121–124 | **72** | 0.9 / {0} | 4 |
| 怪颚龙 | 81, 91–130, 132–135 | unchanged | 0.9 / {0}; 1.0 or 1.1 / {0,…,32} | 21 |
| 喷火驼 | 54, 60–97, 99–101 | unchanged | 0.9 / {0}; 1.0 or 1.1 / {0,…,32} | 21 |
| 轰擂金刚猩 | 94, 105–141, 143–150 | unchanged | 0.9 / {0}; 1.0 or 1.1 / {0,…,32} | 21 |
| 大钢蛇 | 45, 50–86, 88–90 | unchanged | 0.9 / {0}; 1.0 or 1.1 / {0,…,32} | 17 |
| 智挥猩 | 72, 80–119, 121–123 | unchanged | 0.9 / {0}; 1.0 or 1.1 / {0,…,32} | 21 |

These SP/alignment rows are marginals of joint branches, not independently selectable builds. Steelix's 17 patterns retain the earlier offense constraints. Full per-pattern SP→stat rows and total-budget semantics are in `roster[].joint_domain.configurations.branches`. Conditional changes to other stat marginals induced by the preferred Speed alignment remain preference-dependent, not new direct observations. This is not a full joint solution of all hidden damage/item configurations or a recognition-accuracy claim.

## Saved outputs and validation

Final complete inference: `.cache/battles/sample_battle_24/diagnosis/speed-order-audit-v1/audit-iron-ball-last-resort-v4.json`. Intermediate new-policy v1–v3 files and the original pre-policy `audit-v4.json` remain preserved. The final file includes input/code hashes, all 30 pair classifications, source receipts, numerical decisions, per-member policy status, exact configuration witnesses and joint SP/alignment branches. A compact summary and validation record accompany this report in `speed-order-iron-ball-last-resort-v1.json`.

Targeted tests cover three species, satisfiable non-Iron-Ball explanations, necessary Iron Ball fallback, fallback SP=0, explicitly observed items, later observed Iron Ball, contradictory cumulative comparisons, reopening a preferred marginal, shared alignment/budget, team uniqueness, unresolved modifiers, the saved B24 pair, and the actual trace-to-joint-projection interface. Validation: **142 passed in 16.55 s** in the focused suite; **121 passed, 8 deselected in 1.61 s** in the additional Speed/replay suite (overlap is not summed). Frozen/historical verification, identical-result republication and `git diff --check` passed. Exact commands and checks are recorded in the companion JSON.

Resume without recognition or replay:

```sh
.venv/bin/python scripts/audit_b24_speed.py
.venv/bin/python -m pytest -q tests/test_speed_preference.py tests/test_inference_integration.py tests/test_constraint_trace.py tests/test_configuration_domain.py tests/test_speed_order.py tests/test_b24_evaluation.py -m 'not local_artifacts'
.venv/bin/python scripts/evaluate_b24.py --stage verify
git diff --check
```

An identical audit publication checks for identical output bytes; a differing result requires a new `--output` path. Do not invoke the contexts or production stages to reproduce these results. Runtime mechanics remain on the prior pinned provisional Champions reference; existing 52Poké revision/Champions applicability and Iron Ball half-Speed corroboration are in `speed-order-sources.json`. No new knowledge importer or live runtime dependency was added. No commit or push occurred.
