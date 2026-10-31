# sample_battle_17 — fresh video-only reconstruction

Initial run `fresh-b17-b18-20261028-v1`. Raw predictions and the HP view were sealed before failure review. No Battle Log or independent labels exist; all counts describe pipeline behavior, not accuracy.

Normal production wall: **474.530 s**; PTR **0.8958**. Monitoring: 1060 frames; detailed inspections: 1052; OCR model calls: 4307.

Parsed move executions: **19** (15 admitted, including revelation-only records). Switch-out/send-out/faint predictions: **2/9/4**.

HP coverage: **9/11** groups have complete stable numeric endpoints; **6/11** have complete supported causal totals. All 22 admitted nonzero numeric segments occur exactly once. The denominator is observed action/target HP groups, as in B16, and excludes completely unseen HP events; it is not recall. 7 groups have a supported immediate cause including incomplete totals.

Receipts: `{'recorded_observation': 23, 'deferred': 218, 'applied_candidate': 1115, 'applied_partial': 15, 'rejected': 1}`. Deferred: 218; rejected: 1; state conflicts: 3. Exact event adaptation and complete state/receipt/hash replay were reproduced offline, which establishes determinism rather than recognition correctness.

## Predicted observable events

Event-type inventory: `{'preview_observation': 6, 'trainer_observation': 2, 'hud_observation': 1294, 'entry_observation': 7, 'send_out': 9, 'switch_out': 2, 'move_effect': 8, 'transformation': 2, 'move_execution': 19, 'side_condition_change': 5, 'effectiveness': 5, 'faint': 4, 'ability_activation': 2, 'stat_change': 3, 'item_activation': 2, 'visual_observation': 1, 'weather_change': 1}`.

Deferred reasons: `{'message_episode_occupancy_unresolved': 211, 'unresolved_candidate_fields': 7}`.
Unresolved HP reasons: `{'pre_action_hp_missing': 2, 'no_active_resolution_source': 1, 'final_visible_plateau_unresolved': 1, 'move_effect_or_self_cost_not_established': 3, 'source_event_not_admitted_or_bound': 2}`.

## Move and condition receipts

These are source-text/parser predictions with their actual admission status, not independently verified executions/effects. Item/ability announcements alone do not supply HP amounts.

| Source s | Kind | Side | Literal text | Receipt |
|---:|---|---|---|---|
| 148.00833333333333 | move_execution | self | 长毛巨魔使出了 光墙! | applied_partial |
| 152.00833333333333 | side_condition_change | self | 光墙使我方的 特殊抗性提高了！ | applied_candidate |
| 154.01 | move_execution | opponent | 对手的劈斧螳螂使出了 岩斧！ | applied_partial |
| 158.51 | move_execution | self | 烈咬陆鲨使出了 力量宝石！ | applied_partial |
| 208.50166666666667 | move_execution | opponent | 对手的千面避役使出了 守住! | applied_partial |
| 214.50333333333333 | move_execution | self | 长毛巨魔使出了 反射壁！ | applied_partial |
| 218.50333333333333 | side_condition_change | self | 反射壁使我方的 物理抗性提高了！ | applied_candidate |
| 221.02 | move_execution | opponent | 对手的劈斧螳螂使出了 岩斧! | applied_partial |
| 227.52166666666668 | move_execution | self | 烈咬陆鲨使出了 力量宝石！ | applied_partial |
| 244.00833333333333 | ability_activation | opponent | 踏冰人偶的除障 | applied_candidate |
| 244.50833333333333 | side_condition_change | self | 我方的光墙消失了！ | applied_candidate |
| 246.50833333333333 | side_condition_change | self | 我方的反射壁消失了！ | applied_candidate |
| 268.5283333333333 | move_execution | opponent | 对手的踏冰人偶使出了 击掌奇袭! | applied_partial |
| 272.01166666666666 | move_execution | self | 长毛巨魔使出了 光墙! | applied_partial |
| 276.5133333333333 | side_condition_change | self | 光墙使我方的 特殊抗性提高了！ | rejected |
| 280.53 | move_execution | opponent | 对手的千面避役使出了 冰冻光束！ | applied_partial |
| 322.005 | move_execution | opponent | 对手的千面避役使出了 守住！ | applied_partial |
| 327.505 | move_execution | self | 铝钢桥龙使出了 大声咆哮！ | applied_partial |
| 337.50666666666666 | stat_change | opponent | 对手的踏冰人偶的 特攻降低了！ | applied_candidate |
| 339.00666666666666 | item_activation | opponent | 踏冰人偶的逃脱按键 | applied_candidate |
| 351.51 | move_execution | self | 长毛巨魔使出了 灵魂冲击！ | applied_partial |
| 356.01 | item_activation | self | 铝钢桥龙的吃剩的东西 | applied_candidate |
| 407.5183333333333 | move_execution | self | 长毛巨魔使出了 抛下狠话！ | applied_partial |
| 411.02 | stat_change | opponent | 对手的千面避役的 攻击、特攻降低了！ | deferred |
| 425.505 | ability_activation | self | 大嘴鸥的降雨 | applied_candidate |
| 425.505 | weather_change | field | 开始下雨了！ | applied_candidate |
| 428.005 | move_execution | opponent | 对手的千面避役使出了 聚气！ | deferred |
| 435.0233333333333 | move_execution | opponent | 对手的喷火龙使出了 腹鼓！ | deferred |
| 442.0083333333333 | move_execution | self | 铝钢桥龙使出了 电光束！ | applied_partial |
| 450.525 | stat_change | self | 铝钢桥龙的 特攻提高了！ | applied_candidate |
| 506.50166666666667 | move_execution | opponent | 对手的千面避役使出了 狙击！ | deferred |
| 519.5033333333333 | move_execution | opponent | 对手的喷火龙使出了 龙爪！ | deferred |

No parsed status/terrain notice is treated as evidence of absence. Full literal references and per-fact evidence remain in [semantic-inventory.json](semantic-inventory.json).

## HP episodes

| Source s | Affected instance | Cause | Before → after | Delta/unit | Status / reasons |
|---:|---|---|---|---|---|
| 158.51 | opponent 千面避役 / `sample_battle_17:opponent:encounter:1dbc3907e30e25e2` | 力量宝石 | None → 46 | None / displayed_percent | ambiguous; pre_action_hp_missing |
| 221.02 | self 超级烈咬陆鲨 / `sample_battle_17:self:encounter:e02f3546ef88d7bd` | 岩斧 | 184 → 112 | -72 / absolute | supported;  |
| 227.52166666666668 | opponent 劈斧螳螂 / `sample_battle_17:opponent:encounter:13cf7192f139bc25` | 力量宝石 | 100 → 0 | -100 / displayed_percent | supported;  |
| 268.5283333333333 | self 超级烈咬陆鲨 / `sample_battle_17:self:encounter:e02f3546ef88d7bd` | 击掌奇袭 | 112 → 96 | -16 / absolute | supported;  |
| 280.53 | self 超级烈咬陆鲨 / `sample_battle_17:self:encounter:e02f3546ef88d7bd` | 冰冻光束 | 96 → 0 | -96 / absolute | supported;  |
| 299.5 | self 铝钢桥龙 / `sample_battle_17:self:encounter:d548c26c2bec968d` | unknown | 188 → 182 | -6 / absolute | ambiguous; no_active_resolution_source |
| 327.505 | opponent 踏冰人偶 / `sample_battle_17:opponent:encounter:510e5b786a1c1254` | 大声咆哮 | 100 → 85 | -15 / displayed_percent | supported;  |
| 356.01 | self 铝钢桥龙 / `sample_battle_17:self:encounter:d548c26c2bec968d` | 吃剩的东西 | 182 → 194 | 12 / absolute | supported;  |
| 407.5183333333333 | self 大嘴鸥 / `sample_battle_17:self:encounter:e9e334a296fbe4a4` | unknown | None → 123 | None / absolute | ambiguous; final_visible_plateau_unresolved, move_effect_or_self_cost_not_established, pre_action_hp_missing |
| 506.50166666666667 | self 大嘴鸥 / `sample_battle_17:self:encounter:e9e334a296fbe4a4` | unknown | 123 → 0 | -123 / absolute | ambiguous; move_effect_or_self_cost_not_established, source_event_not_admitted_or_bound |
| 519.5033333333333 | self 铝钢桥龙 / `sample_battle_17:self:encounter:d548c26c2bec968d` | unknown | 194 → 0 | -194 / absolute | ambiguous; move_effect_or_self_cost_not_established, source_event_not_admitted_or_bound |

## Final state and identity limits

Final phase: `{'value': None, 'knowledge': 'unknown'}`; turn: `{'value': None, 'knowledge': 'unknown'}`. Game turns are not reconstructed from hypothetical logs.

| Side | Slot | Instance | Species | Current HP | Fainted / status |
|---|---|---|---|---|---|
| opponent | left | `sample_battle_17:opponent:encounter:1dbc3907e30e25e2` | 千面避役 | absolute `{'value': None, 'knowledge': 'unknown'}`; percent `{'value': 46, 'knowledge': 'observed'}` | `{'value': False, 'knowledge': 'observed'}` / `{'value': None, 'knowledge': 'unknown'}` |
| opponent | right | `sample_battle_17:opponent:encounter:510e5b786a1c1254` | 踏冰人偶 | absolute `{'value': None, 'knowledge': 'unknown'}`; percent `{'value': 85, 'knowledge': 'observed'}` | `{'value': False, 'knowledge': 'observed'}` / `{'value': None, 'knowledge': 'unknown'}` |

Full observable inventory, conditions, revealed moves, stages, items and abilities: [final-state-summary.json](final-state-summary.json). Facts retain observed/derived/unknown/conflicting categories. Encounter counts are not biological team size; unproven same-species returns are not merged.

Potential multi-hit/contact/ally examples: `{}`. [examples.json](examples.json) contains prediction evidence, not independent verification. Zero notices do not prove no such move occurred. No high-FPS acquisition is integrated into this production command; optional source review is not represented as measured recognition success.

Raw events, receipt bindings and source images: [events.json](events.json). [Original production viewer](../../event-driven/fresh-b17-b18-20261028-v1/review.html). HP projection with endpoint IDs and provenance remains in `fresh-benchmark/<run>/hp-resolutions.json`.

Limitations: no independent event/state labels or accuracy measurement; incomplete numeric endpoints, ambiguous causes/identities, deferred/rejected receipts and unknown facts remain unresolved. No recognition rules were tuned from this recording. The stock production viewer includes inherited caveat text about prior recognition context; this benchmark’s fresh namespace/cache provenance is recorded separately in the execution/freeze manifests.
