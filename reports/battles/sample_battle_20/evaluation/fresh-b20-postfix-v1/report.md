# sample_battle_20 — fresh video-only reconstruction

Initial run `fresh-b20-postfix-v1`. Raw predictions and the HP view were sealed before failure review. Partial Battle Log review is reported separately; these counts describe pipeline behavior, not accuracy.

Interrupted/resumed run: exact total wall and PTR unavailable. External wall lower bound **4242.383 s**, PTR lower bound **8.8194**; not a full cold timing measurement. Monitoring: 962 frames; detailed inspections: 947; OCR model calls: 3669.

Parsed move executions: **17** (17 admitted, including revelation-only records). Switch-out/send-out/faint predictions: **1/7/3**.

HP coverage: **11/14** groups have complete stable numeric endpoints; **9/14** have complete supported causal totals. All 29 admitted nonzero numeric segments occur exactly once. The denominator is observed action/target HP groups, as in B16, and excludes completely unseen HP events; it is not recall. 12 groups have a supported immediate cause including incomplete totals.

Receipts: `{'deferred': 2, 'recorded_observation': 23, 'applied_candidate': 885, 'applied_partial': 17}`. Deferred: 2; rejected: 0; state conflicts: 13. Exact event adaptation and complete state/receipt/hash replay were reproduced offline, which establishes determinism rather than recognition correctness.

## Predicted observable events

Event-type inventory: `{'hud_observation': 854, 'preview_observation': 6, 'trainer_observation': 3, 'entry_observation': 5, 'send_out': 7, 'ability_activation': 3, 'stat_change': 5, 'weather_change': 2, 'move_effect': 6, 'transformation': 2, 'move_execution': 17, 'side_condition_change': 2, 'effectiveness': 7, 'visual_observation': 2, 'faint': 3, 'item_activation': 2, 'switch_out': 1}`.

Deferred reasons: `{'message_episode_occupancy_unresolved': 2}`.
Unresolved HP reasons: `{'final_visible_plateau_unresolved': 2, 'move_effect_or_self_cost_not_established': 2, 'pre_action_hp_missing': 1, 'resolution_window_still_open': 1}`.

## Move and condition receipts

These are source-text/parser predictions with their actual admission status, not independently verified executions/effects. Item/ability announcements alone do not supply HP amounts.

| Source s | Kind | Side | Literal text | Receipt |
|---:|---|---|---|---|
| 120.52 | ability_activation | opponent | 姆克鹰的威吓 | applied_candidate |
| 121.02 | stat_change | self | 大嘴鸥和烈咬陆鲨的 攻击降低了！ | applied_candidate |
| 121.02 | stat_change | self | 大嘴鸥和烈咬陆鲨的 攻击降低了！ | applied_candidate |
| 122.50333333333333 | ability_activation | self | 大嘴鸥的降雨 | applied_candidate |
| 123.02 | weather_change | field | 开始下雨了！ | applied_candidate |
| 186.03166666666667 | move_execution | opponent | 对手的风妖精使出了 顺风！ | applied_partial |
| 189.53166666666667 | side_condition_change | opponent | 从对手身后 吹起了顺风！ | applied_candidate |
| 192.03166666666667 | move_execution | opponent | 对手的姆克鹰使出了 近身战！ | applied_partial |
| 197.0 | stat_change | opponent | 对手的姆克鹰的 防御、特防提高了！ | applied_candidate |
| 199.5 | move_execution | self | 烈咬陆鲨使出了 力量宝石！ | applied_partial |
| 204.00166666666667 | move_execution | self | 大嘴鸥使出了 暴风！ | applied_partial |
| 226.005 | move_execution | self | 烈咬陆鲨使出了 守住！ | applied_partial |
| 233.50666666666666 | move_execution | opponent | 对手的风妖精使出了 撒娇！ | applied_partial |
| 237.50666666666666 | stat_change | opponent | 对手的姆克鹰的 攻击大幅提高了！ | applied_candidate |
| 239.00666666666666 | move_execution | opponent | 对手的姆克鹰使出了 近身战！ | applied_partial |
| 243.50833333333333 | move_execution | self | 大嘴鸥使出了 暴风！ | applied_partial |
| 280.5133333333333 | move_execution | opponent | 对手的姆克鹰使出了 羽栖！ | applied_partial |
| 291.515 | move_execution | self | 烈咬陆鲨使出了 龙之波动！ | applied_partial |
| 297.0 | move_execution | self | 大嘴鸥使出了 暴风！ | applied_partial |
| 365.0283333333333 | move_execution | self | 烈咬陆鲨使出了 守住！ | applied_partial |
| 370.0283333333333 | move_execution | opponent | 对手的晶光花使出了 力量宝石！ | applied_partial |
| 375.5133333333333 | item_activation | self | 大嘴鸥的文柚果 | applied_candidate |
| 381.015 | move_execution | opponent | 对手的风妖精使出了 月亮之力! | applied_partial |
| 385.5316666666667 | move_execution | self | 大嘴鸥使出了 暴风！ | applied_partial |
| 396.5 | side_condition_change | opponent | 对手的顺风停止了！ | applied_candidate |
| 447.0083333333333 | move_execution | opponent | 对手的晶光花使出了 力量宝石！ | applied_partial |
| 452.51 | ability_activation | self | 铝钢桥龙的持久力 | applied_candidate |
| 453.01 | stat_change | self | 铝钢桥龙的 防御提高了！ | applied_candidate |
| 455.51 | move_execution | self | 烈咬陆鲨使出了 龙之波动！ | applied_partial |
| 466.51166666666666 | weather_change | field | 雨停了！ | applied_candidate |
| 468.01166666666666 | item_activation | self | 铝钢桥龙的吃剩的东西 | applied_candidate |

No parsed status/terrain notice is treated as evidence of absence. Full literal references and per-fact evidence remain in [semantic-inventory.json](semantic-inventory.json).

## HP episodes

| Source s | Affected instance | Cause | Before → after | Delta/unit | Status / reasons |
|---:|---|---|---|---|---|
| 192.03166666666667 | self 超级烈咬陆鲨 / `sample_battle_20:self:encounter:a5d4b6b6a37ceb8e` | 近身战 | 184 → 66 | -118 / absolute | supported;  |
| 199.5 | opponent 超级姆克鹰 / `sample_battle_20:opponent:encounter:33c958b45c7ec610` | 力量宝石 | 100 → 76 | None / displayed_percent | ambiguous; final_visible_plateau_unresolved |
| 204.00166666666667 | opponent 风妖精 / `sample_battle_20:opponent:encounter:530084609b7cca64` | 暴风 | 100 → 17 | -83 / displayed_percent | supported;  |
| 243.50833333333333 | opponent 超级姆克鹰 / `sample_battle_20:opponent:encounter:33c958b45c7ec610` | 暴风 | 76 → 24 | -52 / displayed_percent | supported;  |
| 280.5133333333333 | opponent 超级姆克鹰 / `sample_battle_20:opponent:encounter:33c958b45c7ec610` | unknown | 24 → 74 | 50 / displayed_percent | ambiguous; move_effect_or_self_cost_not_established |
| 280.5133333333333 | opponent 风妖精 / `sample_battle_20:opponent:encounter:530084609b7cca64` | unknown | 17 → 10 | -7 / displayed_percent | ambiguous; move_effect_or_self_cost_not_established |
| 291.515 | opponent 超级姆克鹰 / `sample_battle_20:opponent:encounter:33c958b45c7ec610` | 龙之波动 | 74 → 37 | -37 / displayed_percent | supported;  |
| 297.0 | opponent 超级姆克鹰 / `sample_battle_20:opponent:encounter:33c958b45c7ec610` | 暴风 | 37 → 0 | -37 / displayed_percent | supported;  |
| 370.0283333333333 | self 大嘴鸥 / `sample_battle_20:self:encounter:fb3ab27934775871` | 力量宝石 | 164 → 18 | -146 / absolute | supported;  |
| 375.5133333333333 | self 大嘴鸥 / `sample_battle_20:self:encounter:fb3ab27934775871` | 文柚果 | 18 → 59 | 41 / absolute | supported;  |
| 385.5316666666667 | opponent 风妖精 / `sample_battle_20:opponent:encounter:530084609b7cca64` | 暴风 | 10 → 0 | -10 / displayed_percent | supported;  |
| 447.0083333333333 | self 铝钢桥龙 / `sample_battle_20:self:encounter:5357dbf77ecbff3a` | 力量宝石 | None → 152 | None / absolute | ambiguous; pre_action_hp_missing |
| 455.51 | opponent 烈咬陆鲨 / `sample_battle_20:opponent:encounter:13baf8c7ac9a08d4` | 龙之波动 | 100 → 0 | -100 / displayed_percent | supported;  |
| 468.01166666666666 | self 铝钢桥龙 / `sample_battle_20:self:encounter:5357dbf77ecbff3a` | 吃剩的东西 | 152 → 164 | None / absolute | ambiguous; final_visible_plateau_unresolved, resolution_window_still_open |

## Final state and identity limits

Final phase: `{'value': None, 'knowledge': 'unknown'}`; turn: `{'value': None, 'knowledge': 'unknown'}`. Game turns are not reconstructed from hypothetical logs.

| Side | Slot | Instance | Species | Current HP | Fainted / status |
|---|---|---|---|---|---|
| self | right | `sample_battle_20:self:encounter:a5d4b6b6a37ceb8e` | 超级烈咬陆鲨 | absolute `{'value': 66, 'knowledge': 'observed'}`; percent `{'value': None, 'knowledge': 'unknown'}` | `{'value': False, 'knowledge': 'observed'}` / `{'value': None, 'knowledge': 'unknown'}` |
| self | left | `sample_battle_20:self:encounter:5357dbf77ecbff3a` | 铝钢桥龙 | absolute `{'value': 164, 'knowledge': 'observed'}`; percent `{'value': None, 'knowledge': 'unknown'}` | `{'value': False, 'knowledge': 'observed'}` / `{'value': None, 'knowledge': 'unknown'}` |
| opponent | right | `sample_battle_20:opponent:encounter:bb18a1534a4d21bf` | 晶光花 | absolute `{'value': None, 'knowledge': 'unknown'}`; percent `{'value': 100, 'knowledge': 'observed'}` | `{'value': False, 'knowledge': 'observed'}` / `{'value': None, 'knowledge': 'unknown'}` |

Full observable inventory, conditions, revealed moves, stages, items and abilities: [final-state-summary.json](final-state-summary.json). Facts retain observed/derived/unknown/conflicting categories. Encounter counts are not biological team size; unproven same-species returns are not merged.

Potential multi-hit/contact/ally examples: `{}`. [examples.json](examples.json) contains prediction evidence, not independent verification. Zero notices do not prove no such move occurred. No high-FPS acquisition is integrated into this production command; optional source review is not represented as measured recognition success.

Raw events, receipt bindings and source images: [events.json](events.json). [Original production viewer](../../event-driven/fresh-b20-postfix-v1/review.html). HP projection with endpoint IDs and provenance remains in `fresh-benchmark/<run>/hp-resolutions.json`.

Limitations: these descriptive counts do not measure event/state accuracy; incomplete numeric endpoints, ambiguous causes/identities, deferred/rejected receipts and unknown facts remain unresolved. No recognition rules were tuned from this recording. The stock production viewer includes inherited caveat text about prior recognition context; this benchmark’s fresh namespace/cache provenance is recorded separately in the execution/freeze manifests.
