# B24 action-order evidence audit — 2026-11-01

## Result and scope

Completed Task 1 before performance work. Resumed from the completed reviewed-context trace `7c3ffb267920ed10` and context file `contexts-119376ea8122799a-attempt-1.jsonl`; no recognition, video access, StateEngine replay or production CLI. The historical result had 36 member-panel updates representing 30 distinct event pairs. Only two pairs reached the numerical adapter, both unresolved. This was partly an interface failure, but zero numerical reductions is still the correct **marginal** result after repair under the existing provisional reference profile: two pairs now solve exactly; neither removes a native Speed value. No target Speed, unknown equipped move, probability or unrestricted stat domain was inserted.

Detailed reproducible output: `.cache/battles/sample_battle_24/diagnosis/speed-order-audit-v1/audit-v4.json`. Earlier `initial-audit.json`, `audit.json` and `audit-v2.json` and `audit-v3.json` remain preserved. The final output contains full receipts/evidence, certifications, old blockers, solver observations/configurations, form-branch results and exact joint SP/alignment domains for all six members. Production and completed-context hashes were checked before/after the audit. The frozen production and previous damage inference have not been republished.

## The approximately 15-minute sequence

The saved messages place the sequence at **930.506667 s (15:30.507)** and **943.525 s (15:43.525)**, rather than exactly 900 s. The command observation is `event:5a1d8cf6dcb7b83e21c04536` at 897.001667 s; provisional cycle 12 starts there, ending at the next command boundary 954.526667 s. Its four distinct original occupants each act once:

| Time (s) | Accepted action event ID | Actor and move |
| --- | --- | --- |
| 920.005 | `event:19a6c23b0dca455b28ab998e` | 铝钢桥龙 / Protect |
| 925.005 | `event:df786c1b0e0ecc8541068975` | 大钢蛇 / Protect (exact ID in candidate table below) |
| 930.506667 | `event:b04c832694bde680a01262e4` | 长毛巨魔 / Spirit Break (`pokeapi:move:789`) |
| 943.525 | `event:5785e44cdf6b514c0d4a86d5` | 班基拉斯 / Curse (`pokeapi:move:174`; displayed 咒术) |

The two important messages are `长毛巨魔使出了 / 灵魂冲击！` and `对手的班基拉斯使出了 / 咒术!`. Their source IDs are `tests/fixtures/sample_battle_24.mp4#930.5066666666667` and `...#943.525`; saved frames are `001831.png` and `001857.png` in the frozen run's `frames/`. Observation IDs are respectively `58c8cfe4d23a1fc6e8b8189972fd87ea0eb7b13eb790c07da3a71352cdfa818a` and `dd247026f3ab68d7c26a911d8a7f23ef36eabacce54b968051511393bc97ce20`. These are live Battle Message observations, not stale rows from an open Battle Log.

### Complete chain and first failed link

1. **Saved evidence → accepted action:** `recognition.event_report.video_events`, then `tracking.state_engine.StateEngine.replay` and `tracking.evidence_fusion.move_revelation` preserve both named live uses as `applied_partial`, reason `move_revelation_only`. This reason limits StateEngine's effect application; it does not erase the observed use or actor binding. Both actions reach `ChronologicalTrace.speed_pairs`. Globally promoting all move revelations to completed effects would be incorrect and was not done.
2. **Actor → persistent identity:** Grimmsnarl source and persistent ID is `sample_battle_24:self:encounter:1be8e24381544df9`. Tyranitar source ID is `sample_battle_24:opponent:encounter:759673a9a39eb3f5`, aliased in the contemporaneous context to persistent `sample_battle_24:opponent:encounter:f221ed853589d065`. It is roster preview row 1/species 248. The return at 862.511667 s is `event:41811f05626e626ed65daccf`; Sand Stream at 866.011667 s is `event:8050b987829a0c9e439e2437`. The context writer copies the persistent view under the immutable source alias. No identity substitution is required at the numerical adapter.
3. **Identity → cycle:** `battle_evidence.turns.certify_saved_cycle` uses the saved command/resolution occupant marker and bounded four-action stream. Cycle 12 is `certified_local_membership`, reasons empty, with four unique original opportunities and no interior switch, replacement, coverage gap or premature residual boundary. Absolute game-turn numbers remain unknown; no Battle Log turn association is necessary for this local proof. No timestamp-distance heuristic was added.
4. **Cycle → priority:** both catalog base priorities are 0. Grimmsnarl's observed/configured Prankster raises Status moves, not physical Spirit Break. Tyranitar's observed Sand Stream does not raise Curse priority. Effective priorities are therefore 0 and 0 under the pinned reference. The two Protect actions have priority +4 and cannot compare Speed against these priority-0 actions.
5. **Modifiers:** Grimmsnarl actual unmodified Speed is 80 from the verified own-team profile. Both Speed stages are 0, status is `none`, and both Tailwind flags are false in the first action's saved context. Field: sandstorm, terrain none, Trick Room false. Trick Room began at 184.531667 s (`event:692a304ad9a0bcb8b7bfde37`) and explicitly ended at 533.023333 s (`event:afc0d81237309f298a2911f1`); it was not active here. Tyranitar's subsequent Speed drop at 948.026667 s (`event:9247fbbf7c43641722ce895c`) occurs **after Curse**, and is not applied retroactively. The intervening 937.525 s drop (`event:07de7bcbd6959f697c89f624`) is Special Attack, not Speed.
6. **Certified relation → M3: first failed link.** `battle_evidence.inference_integration.invert_saved_order` previously demanded exactly one current form. Tyranitar with species-only identity and Sand Stream permits base `pokeapi:species:248` and Mega `pokeapi:form:10149` in the local catalog. It returned `current form unresolved for ...759673a9a39eb3f5` before calling `speed_order.infer_speed`. This is an adapter limitation, not missing action-cycle membership or `move_revelation_only` filtering.
7. **Next latent failure:** after enumerating forms the M3 move gate rejected Curse as `Unaudited or special move: Curse`. The pinned move definition and Champions override retain priority 0. The priority contract now admits Curse; no Curse boosts/HP effects are automatically synthesized. The two-action adapter blocks an earlier Speed-changing move without explicit pending-queue transitions; Curse is terminal in this comparison.
8. **M3 → feasible set:** the repaired adapter unions supported form branches with identical native/current SP and alignment mapping. Any unresolved branch blocks an unconditional result; incompatible known required-item branches are excluded explicitly. Here Mega Tyranitar's required-stone branch is incompatible with acting after Speed 80 (its default minimum current Speed is 81); base Tyranitar remains possible. This is a local reference-branch result, not a new independently observed form fact.

### What the inequality actually establishes

With equal priority, no evidenced queue override, and Trick Room off, the sequence supports `effective Speed(Tyranitar) <= 80`, **including ties**. It does not prove strictly slower native Speed. Grimmsnarl has Light Clay; Tyranitar's item remains unknown. Existing legal order-item alternatives are retained without probability weights. In the base branch, Speed-neutral items allow native Speed 72; a Choice Scarf branch has no survivor; Quick Claw can remain unactivated and allows 72; **Iron Ball allows every native Speed in the default set**, since even 124 becomes 62 after its Speed reduction. Thus the joint Speed/item relation is informative, while its marginal Speed union is unchanged. This audit does not establish Tyranitar actually held Iron Ball.

The other repaired comparison is Archaludon Protect before Mega Steelix Protect, 920.005→925.005 s. Its previous blocker was `known comparison item/ability unresolved`: Archaludon's item identity is unset, but its slot status is explicitly `none` following Knock Off. The Speed adapter now resolves explicit `none/consumed/lost/transferred` statuses as empty, as the damage adapter already does. Archaludon's Speed is 116, so every native Steelix value 45–90 already satisfies the relation. This repairs missing propagation without producing a reduction.

## Repairs and validation

- `battle_evidence/inference_integration.py`: enumerate subject form alternatives, preserve required-item incompatibility and union completeness, recognize canonical species form IDs, propagate explicit empty item slots, and reject unsupplied earlier Speed-changing effects.
- `speed_order/mechanics.py`: admit the audited ordinary priority of Curse; keep its effects explicit. Existing uncommitted neutral-ability changes were preserved.
- `battle_evidence/turns.py`: a revelation-only receipt requires live `battle_message` use semantics to certify a cycle; historical move membership cannot certify execution.
- `battle_evidence/constraint_trace.py`: an uncertified pair is labelled unresolved, consistently with its admissibility reasons, instead of merely conditional.
- `scripts/audit_b24_speed.py`: isolated saved-input recomputation, per-pair classification and six-member joint-domain projection, source/code fingerprints, immutable versioned output guard.
- Tests cover ordinary versus reversed Trick Room inequalities, tie retention, unknown order items, observed empty slots versus unknown slots, form unions, input immutability, canonical IDs, local-cycle certification versus historical revelation, and the pending-queue guard. Focused portable suite: **124 passed in 15.08 s** (`test_inference_integration`, `test_configuration_domain`, `test_constraint_trace`, `test_speed_order`).

## Mechanics provenance and practical limits

The runtime is offline and retains profile `showdown-champions-reference-v1`; exact means exact in that supported reference/domain, not independent certification of every Champions mechanic. Local `speed_order/data/sources-v2.json` and `ordering-coverage-v1.json` record pinned source revision `3a766f2cfb5e51c1e428cfe87d0dba91a8f01640`. Relevant excerpts: `.cache/m321/sources/moves.ts` Curse definition has `priority: 0`, non-Ghost self boosts `{spe:-1, atk:1, def:1}`; `.cache/m322/sources/champions-moves.ts` inherits it and overrides callback targeting. The new contract only uses pre-execution priority and supplied state.

Bounded 52Poké checks on 2026-11-01: [Spirit Break](https://wiki.52poke.com/wiki/灵魂冲击（招式）) classifies it physical; [Prankster](https://wiki.52poke.com/wiki/恶作剧之心（特性）) describes the Status priority change; [Tyranitar Champions learnset](https://wiki.52poke.com/wiki/班基拉斯/Champions招式表) was checked specifically for the game rather than substituting a Generation 9 learnset. The direct Curse article fetch timed out. These external page checks supply corroboration, not a new knowledge importer or runtime dependency. Existing versioned local snapshots and attribution are in `docs/b24-evaluation-20261101/sources.json`; supplementary browser revision IDs/applicability are recorded in `speed-order-sources.json` (Spirit Break 2554119, Prankster 2618394, Iron Ball 2622419, Tyranitar learnset 2608693). Complete new HTML snapshots were not captured; pinned local definitions remain the reproducible execution evidence. The Champions learnset contains 咒术 in the Ghost/Status row; Champions-specific Prankster and Iron Ball description rows corroborate the priority and half-Speed behavior. 52Poké contributors: CC BY-NC-SA 3.0; Showdown contributors: MIT. Learnability is not equipped-slot or probability evidence.

## All 30 deduplicated candidates

P = different effective priority; C = uncertified cycle; V = valid, no marginal reduction. Primary outcomes are **18 P, 10 C, 2 V, 0 numerically narrowing**. Secondary blockers are retained below and in JSON: repeated actors/Instruct recursion, switch/replacement/coverage, missing original opportunities, unaudited execution callbacks and modifiers. None was excluded for identity ambiguity alone; none has Trick Room uncertainty as its sole primary blocker. Missing callback support is not silently treated as known execution semantics. The table's effective-priority numbers use catalog/native ability facts where callback execution is unsupported; these numbers alone never admit a candidate to M3.

| # / pair ID prefix | Cycle | First → second (seconds; full action IDs) | Priorities | Outcome and concrete secondary blockers |
| --- | --- | --- | --- | --- |
| 1 / `c5f9f723` | 1 | 163.528 `event:746b71307f505588034a4a1d` → 169.512 `event:316ea246ffcd2c314eccd7e6` | 4→1 | P: unknown Iron Ball branch retains full marginal |
| 2 / `4192967d` | 1 | 163.528 `event:746b71307f505588034a4a1d` → 175.030 `event:52a6e6261c49a3ae161a36d1` | 4→0 | P: unknown Iron Ball branch retains full marginal |
| 3 / `588cec91` | 1 | 163.528 `event:746b71307f505588034a4a1d` → 180.030 `event:d2fc688e43b9b69d0775abc6` | 4→-7 | P: unknown Iron Ball branch retains full marginal |
| 4 / `06467eed` | 1 | 169.512 `event:316ea246ffcd2c314eccd7e6` → 180.030 `event:d2fc688e43b9b69d0775abc6` | 1→-7 | P: unknown Iron Ball branch retains full marginal |
| 5 / `6efdb798` | 1 | 175.030 `event:52a6e6261c49a3ae161a36d1` → 180.030 `event:d2fc688e43b9b69d0775abc6` | 0→-7 | P: unknown Iron Ball branch retains full marginal |
| 6 / `c7fb2a41` | 2 | 226.005 `event:a8b6bab41816037d2b142079` → 235.507 `event:5197553ad8d789fb181b3219` | 4→0 | P: four unique original move opportunities not resolved; Unaudited or special move: Instruct |
| 7 / `cf136956` | 2 | 235.507 `event:5197553ad8d789fb181b3219` → 243.008 `event:e0d690431137243d2c5b3a00` | 0→4 | P: four unique original move opportunities not resolved; Unaudited or special move: Instruct |
| 8 / `69fc9193` | 2 | 235.507 `event:5197553ad8d789fb181b3219` → 247.008 `event:4a14a687828b5e92eee6addd` | 0→0 | C: four unique original move opportunities not resolved; Unaudited or special move: Instruct |
| 9 / `5dbc02a6` | 2 | 235.507 `event:5197553ad8d789fb181b3219` → 257.010 `event:20dd2ce0e144267e736d93d4` | 0→0 | C: four unique original move opportunities not resolved; Unaudited or special move: Instruct |
| 10 / `c64d9e0f` | 2 | 226.005 `event:a8b6bab41816037d2b142079` → 243.008 `event:e0d690431137243d2c5b3a00` | 4→4 | C: four unique original move opportunities not resolved |
| 11 / `6b7571a8` | 2 | 243.008 `event:e0d690431137243d2c5b3a00` → 247.008 `event:4a14a687828b5e92eee6addd` | 4→0 | P: four unique original move opportunities not resolved |
| 12 / `3df46d38` | 2 | 226.005 `event:a8b6bab41816037d2b142079` → 257.010 `event:20dd2ce0e144267e736d93d4` | 4→0 | P: four unique original move opportunities not resolved |
| 13 / `8cf621cf` | 2 | 247.008 `event:4a14a687828b5e92eee6addd` → 257.010 `event:20dd2ce0e144267e736d93d4` | 0→0 | C: four unique original move opportunities not resolved |
| 14 / `c0c80dab` | 6 | 519.520 `event:221e7e2bc3ec75a30a73fba1` → 523.522 `event:d886b3b9387eb85d66d5734d` | 0→0 | C: four unique original move opportunities not resolved; original active occupants do not match resolved actions; switch, replacement or coverage gap inside cycle |
| 15 / `20069b81` | 7 | 588.515 `event:baa892591c430f32ccbd530c` → 596.500 `event:1ac146531beb105f6c751363` | 0→0 | C: four unique original move opportunities not resolved; original active occupants do not match resolved actions; switch, replacement or coverage gap inside cycle; Unaudited or special move: Knock Off |
| 16 / `748b4fc7` | 7 | 596.500 `event:1ac146531beb105f6c751363` → 607.002 `event:9e131a93271bbbd5a288bd61` | 0→0 | C: four unique original move opportunities not resolved; original active occupants do not match resolved actions; switch, replacement or coverage gap inside cycle; Unaudited or special move: Heavy Slam; Unaudited or special move: Knock Off |
| 17 / `3e5d2812` | 7 | 588.515 `event:baa892591c430f32ccbd530c` → 607.002 `event:9e131a93271bbbd5a288bd61` | 0→0 | C: four unique original move opportunities not resolved; original active occupants do not match resolved actions; switch, replacement or coverage gap inside cycle; Unaudited or special move: Heavy Slam |
| 18 / `bd2fda78` | 9 | 675.513 `event:521d2d275b9fd2c1584d6b56` → 681.515 `event:7e107808980e561ae5eacea4` | 4→0 | P: four unique original move opportunities not resolved; original active occupants do not match resolved actions; switch, replacement or coverage gap inside cycle; Unaudited or special move: Electro Shot |
| 19 / `b49835b2` | 9 | 675.513 `event:521d2d275b9fd2c1584d6b56` → 699.518 `event:283af3194fbd87b0e4ed5f78` | 4→0 | P: four unique original move opportunities not resolved; original active occupants do not match resolved actions; switch, replacement or coverage gap inside cycle |
| 20 / `1b599d55` | 10 | 759.012 `event:a6ed060e0ec2a9f220ee0f75` → 769.030 `event:45483e6877adb7e45b870769` | 4→0 | P: four unique original move opportunities not resolved; original active occupants do not match resolved actions; switch, replacement or coverage gap inside cycle |
| 21 / `55680063` | 10 | 769.030 `event:45483e6877adb7e45b870769` → 780.032 `event:ed26e76c660fabe8e7821a65` | 0→0 | C: four unique original move opportunities not resolved; original active occupants do not match resolved actions; switch, replacement or coverage gap inside cycle |
| 22 / `48e6d7af` | 10 | 759.012 `event:a6ed060e0ec2a9f220ee0f75` → 780.032 `event:ed26e76c660fabe8e7821a65` | 4→0 | P: four unique original move opportunities not resolved; original active occupants do not match resolved actions; switch, replacement or coverage gap inside cycle |
| 23 / `44de262a` | 11 | 831.507 `event:6294a184f29734b13cf9b607` → 854.027 `event:31bdc136480b7f403c204298` | 1→0 | P: four unique original move opportunities not resolved; original active occupants do not match resolved actions; switch, replacement or coverage gap inside cycle |
| 24 / `3535c6cf` | 11 | 838.008 `event:2520ba86f95c453c7cff7172` → 854.027 `event:31bdc136480b7f403c204298` | 0→0 | C: four unique original move opportunities not resolved; original active occupants do not match resolved actions; switch, replacement or coverage gap inside cycle |
| 25 / `25a89d88` | 12 | 920.005 `event:19a6c23b0dca455b28ab998e` → 925.005 `event:df786c1b0e0ecc8541068975` | 4→4 | V: all Speed values already below comparator |
| 26 / `fb549a65` | 12 | 925.005 `event:df786c1b0e0ecc8541068975` → 930.507 `event:b04c832694bde680a01262e4` | 4→0 | P: unknown Iron Ball branch retains full marginal |
| 27 / `0461cd73` | 12 | 925.005 `event:df786c1b0e0ecc8541068975` → 943.525 `event:5785e44cdf6b514c0d4a86d5` | 4→0 | P: unknown Iron Ball branch retains full marginal |
| 28 / `c348d47d` | 12 | 920.005 `event:19a6c23b0dca455b28ab998e` → 943.525 `event:5785e44cdf6b514c0d4a86d5` | 4→0 | P: unknown Iron Ball branch retains full marginal |
| 29 / `d8c4d4e8` | 12 | 930.507 `event:b04c832694bde680a01262e4` → 943.525 `event:5785e44cdf6b514c0d4a86d5` | 0→0 | V: unknown Iron Ball branch retains full marginal |
| 30 / `bd078df1` | 13 | 1000.002 `event:51d7a22be6c536f1e7696764` → 1003.502 `event:10c37df4554207292c0fff86` | 4→1 | P: four unique original move opportunities not resolved; original active occupants do not match resolved actions; switch, replacement or coverage gap inside cycle |

## Six-member before/after Speed domains

All intervals below are **inclusive integer sets**, and omitted gaps are impossible in the selected default. These are native unmodified stats, not effective battle Speed. Before = initial user-default domain; after = audited Speed relations joined with the existing final offense marginals under one global alignment and total SP ≤66. No unrestricted fallback or new damage calculation was used.

| Member | Before | After | Surviving global alignment branches |
| --- | --- | --- | --- |
| 班基拉斯 | 72, 81–119, 121–124 | 72, 81–119, 121–124 | 21 |
| 怪颚龙 | 81, 91–130, 132–135 | 81, 91–130, 132–135 | 21 |
| 喷火驼 | 54, 60–97, 99–101 | 54, 60–97, 99–101 | 21 |
| 轰擂金刚猩 | 94, 105–141, 143–150 | 94, 105–141, 143–150 | 21 |
| 大钢蛇 | 45, 50–86, 88–90 | 45, 50–86, 88–90 | 17 |
| 智挥猩 | 72, 80–119, 121–123 | 72, 80–119, 121–123 | 21 |

For **each of the six members**, the marginal Speed alignment/SP branches are: downward factor 0.9 at SP={0}; neutral factor 1.0 at SP={0,…,32}; upward factor 1.1 at SP={0,…,32}. These are feasible marginals, not independent joint choices: each branch has one global alignment, the existing final offense constraints, and total SP≤66. Steelix retains 17 global alignment patterns after existing damage constraints; the others retain 21. Exact per-pattern SP→stat rows for all stats are saved as `roster[].joint_domain.configurations.branches` in the audit JSON, together with chronological candidate IDs per member. None of the Speed evidence removes another SP or alignment branch.

Chronology: cycle 1 ends before cycle 2; cycles 2, 6, 7, 9, 10 and 11 have only conditional/blocked comparisons; cycle 12 becomes available at 954.526667 s and supplies the two valid relations above; cycle 13 adds no valid Speed bound. Camerupt and Rillaboom have no accepted execution lineage; preview identity alone cannot compare Speed. The old trace’s damage refinements and source-conflict disclosures remain intact. This is a supported local ordering audit, not whole-match semantic acceptance or recognition accuracy.

Resume/verify without expensive work:

```sh
.venv/bin/python scripts/audit_b24_speed.py --output .cache/battles/sample_battle_24/diagnosis/speed-order-audit-v1/audit-v4.json
.venv/bin/python -m pytest -q tests/test_inference_integration.py tests/test_configuration_domain.py tests/test_constraint_trace.py tests/test_speed_order.py -m "not local_artifacts"
.venv/bin/python scripts/evaluate_b24.py --stage verify
```

The audit refuses to overwrite differing results. If implementation changes, choose a new output filename. Do not run the contexts/inference stage to reproduce this audit: completed contexts are sufficient.

Additional portable Speed/replay/team-context/B24 regression group: **124 passed, 8 deselected in 5.21 s**. This overlaps the primary suite; counts are not a unique-test total. Final frozen/historical verification and `git diff --check` passed.
