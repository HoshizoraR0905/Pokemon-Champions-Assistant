# M2 — Sequential battle resolution and HP attribution

Run `b16-sequential-resolution-20261028-v2`. Development regression, not held-out accuracy. Source predictions and all references stay sealed.

Root cause of the prior failure: the previous projection constructed `action_targets` from named effectiveness/qualitative notices and explicit target IDs, then required `key in action_targets` before accepting a move cause. HUD numeric changes did not populate that set. Thus Weather Ball and both Snarl recipients were rejected despite supported instance bindings and compatible HP pairs. Every ability/item activation was also a boundary, so Stamina incorrectly ended the parent HP context rather than becoming a non-HP nested step.

The new view walks the actual ordered receipts. A move establishes a parent context; bound HP animations establish affected recipients. A documented banner opens a recipient/direction-specific immediate cause only when actual HP evidence occurs. Stat-only effects do not steal the HP cause. Reactions retain holder, attacker, affected instance and parent separately; overlapping sources, unknown semantics, identity/coverage gaps, direction conflicts, source-time ties and unsettled endpoints still cause abstention. No team-opposition target rule or move-name target guess is used.

| Measure | Previous action view | Sequential view |
|---|---:|---:|
| Frozen action/target groups | 21 | 21 |
| Complete stable HP endpoints | 16 | 16 |
| Supported affected targets | not separately scored | 21/21 |
| Unique immediate cause, including incomplete totals | 10/21 | 21/21 |
| Complete causal attribution | 6/21 (28.6%) | 16/21 (76.2%) |
| Nested HP effect episodes | not separately scored | 1 |
| Unresolved complete-attribution cases | 15 | 5 |

The 21 membership sets and all 41 original numeric change IDs are byte-independent comparison keys: each appears once and maps to the same affected instance/unit as the frozen action evaluation. The denominator was read before prediction, never altered after results. Supported target/cause counts mean evidence-supported associations, not independently measured target/cause accuracy. The three requested diagnostics are checked after inference. No 21-case independent causal labels exist, so causal accuracy is unmeasured.

Original event/state reconstruction stays **120/124 event facts, 175/191 state fields, 18/21 reference numeric pairs and 3/3 observed zero endpoints**. The complete serialized StateEngine state and every receipt are identical before/after deriving this view. No new HP values, stages, items, abilities or switches are applied.

## Actual action/effect episodes

| Source time (s) | Source / parent | Affected | HP before → final | Signed delta / unit | Status / unresolved reason |
|---:|---|---|---|---|---|
| 196.500 | 气象球; `event:2baefb695d2b9062abb9d76b` | opponent 铝钢桥龙 | 100 → 13 | -87 / displayed_percent | supported;  |
| 206.002 | 大声咆哮; `event:e9c59f0662ebf67a14333839` | own 喷火龙 | 184 → 164 | -20 / absolute | supported;  |
| 206.002 | 大声咆哮; `event:e9c59f0662ebf67a14333839` | own 妙蛙花 | 156 → 129 | -27 / absolute | supported;  |
| 214.520 | 吃剩的东西; `independent effect` | opponent 铝钢桥龙 | 13 → 19 | 6 / displayed_percent | supported;  |
| 245.008 | 污泥炸弹; `event:4ad08727df1df16fb9302b9f` | opponent 大嘴鸥 | 100 → 68 | -32 / displayed_percent | supported;  |
| 255.510 | 吃剩的东西; `independent effect` | opponent 铝钢桥龙 | 19 → 25 | 6 / displayed_percent | supported;  |
| 283.015 | 污泥炸弹; `event:7a4b3941ae0ede982ad1585e` | opponent 大嘴鸥 | 68 → 37 | -31 / displayed_percent | supported;  |
| 286.515 | 文柚果; `event:7a4b3941ae0ede982ad1585e` | opponent 大嘴鸥 | 37 → 62 | None / displayed_percent | ambiguous; final_visible_plateau_unresolved |
| 290.032 | 气象球; `event:e5e43c97cfab3045243a326e` | opponent 烈咬陆鲨 | None → 67 | None / displayed_percent | ambiguous; pre_action_hp_missing |
| 345.008 | 岩崩; `event:b7eff3ec648ada89ef961a0d` | own 妙蛙花 | 129 → 84 | -45 / absolute | supported;  |
| 361.512 | 气象球; `event:f69fc719b2fce86f2cded3e4` | own 妙蛙花 | 84 → 0 | -84 / absolute | supported;  |
| 443.508 | 电光束; `event:be7962741c1963b03ffc9f93` | opponent 铝钢桥龙 | None → 0 | None / displayed_percent | ambiguous; pre_action_hp_missing |
| 538.507 | 热风; `event:bde2c64e7a077fa13ac14efa` | own 大嘴鸥 | 164 → 110 | -54 / absolute | supported;  |
| 552.510 | 气象球; `event:733fef2838067330fe6f31f7` | opponent 烈咬陆鲨 | 67 → 48 | -19 / displayed_percent | supported;  |
| 561.012 | burn; `independent effect` | own 大嘴鸥 | 110 → 100 | -10 / absolute | supported;  |
| 613.520 | 气象球; `event:09cb712d05dd826c3d910058` | own 铝钢桥龙 | 194 → 0 | -194 / absolute | supported;  |
| 623.522 | burn; `independent effect` | own 大嘴鸥 | 100 → 90 | None / absolute | ambiguous; final_visible_plateau_unresolved |
| 676.530 | 气象球; `event:654fec86a6dc78e8f7c8b794` | opponent 大嘴鸥 | None → 33 | None / displayed_percent | ambiguous; pre_action_hp_missing |
| 685.532 | 暴风; `event:a7534eb21a34a5c13f5e8ebc` | own 大嘴鸥 | 90 → 0 | -90 / absolute | supported;  |
| 715.503 | 气象球; `event:57b0a83d01f6869b640f764c` | opponent 喷火龙 | 100 → 0 | -100 / displayed_percent | supported;  |
| 727.005 | 气象球; `event:a631a4841a20683a3dc28209` | own 喷火龙 | 164 → 12 | -152 / absolute | supported;  |

## Diagnostic source traces

An isolated original-video review rechecked the SHA against the sealed media and decoded 7 short source seeks plus 6 onset frames, with **zero OCR calls**. At about 200.2 s, the original HUD visibly shows Archaludon at 100%; subsequent source frames show the decrease, 13%, Stamina and Defense increase. Around 208–210 s both own HP endpoints and Special Attack drops are visible. These review frames/expectations are excluded from predictor inputs; prediction endpoints retain their original accepted event IDs and times.

| Source event | Recipient | Accepted HP endpoint events | Delta |
|---|---|---|---|
| `event:2baefb695d2b9062abb9d76b` @ 196.500000 | `sample_battle_16:opponent:encounter:56c49d3a1c44c11e` | `event:b386a2420309be5248dd4a94` @ 174.013333 → `event:f3270f65c67e06631a56177e` @ 205.018333 | -87 displayed_percent |
| `event:e9c59f0662ebf67a14333839` @ 206.001667 | `sample_battle_16:self:encounter:74f6f62a20ccc52f` | `event:1c128d4105dbcb1c6ef31b3e` @ 174.013333 → `event:f336e396c2edf5e18776d9d7` @ 212.018333 | -20 absolute |
| `event:e9c59f0662ebf67a14333839` @ 206.001667 | `sample_battle_16:self:encounter:ff3714f826d32c20` | `event:46332b9c06c28c3b4c8aeb2c` @ 174.013333 → `event:abfe56c9c04b77b780d6006f` @ 212.018333 | -27 absolute |

Full source → actor/holder → affected instance → raw HP animation observations → resulting history receipts and stat/pivot/reaction steps: [diagnostic-traces.json](diagnostic-traces.json), [sequential-resolution.json](sequential-resolution.json), [episode-comparisons.json](episode-comparisons.json).

## Remaining limits

Three pre-action endpoints remain missing. Two final values have no confirmed visible plateau. Their target and immediate source can be supported while total damage stays unknown. No percentage is converted to exact HP. Unknown banners and competing sources remain ambiguous in regression tests; no effect is assumed merely because an ability/item is active.

B16 has no real Triple Axel, repeated Rough Skin, ally pivot or supported critical-hit sequence in the saved predictions. Those contracts are tested synthetically and do not establish real-video detection success. Multi-hit totals and reaction totals are separate. Per-hit amounts require independent hit evidence plus adequate source sampling; missing boundaries retain unknown per-hit amounts. The targeted PTS decoder, pre-roll and HP-only cached OCR remain in use, with escalation from 5 FPS up to the measured source FPS limit when timing remains unresolved. This evaluation runs no new acquisition/OCR.

A scoped, offline 52Poké categorical supplement is queried through the existing KnowledgeBase canonical IDs. It records article URLs, revisions, retrieval date, Champions applicability and attribution/license. It contains no damage fractions, probability priors or equipped-move assertions. See `knowledge/data/52poke-resolution-v1.json`. No runtime network access or competing identity database was introduced.

No commit, push or next milestone. Commands, focused tests and source-review manifest locations are documented in `docs/m2-sequential-hp/`.
