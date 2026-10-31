# sample_battle_18 — fresh video-only reconstruction

Initial run `fresh-b17-b18-20261028-v1`. Raw predictions and the HP view were sealed before failure review. No Battle Log or independent labels exist; all counts describe pipeline behavior, not accuracy.

Normal production wall: **751.730 s**; PTR **1.7831**. Monitoring: 844 frames; detailed inspections: 831; OCR model calls: 3033.

Parsed move executions: **13** (13 admitted, including revelation-only records). Switch-out/send-out/faint predictions: **4/8/1**.

HP coverage: **3/4** groups have complete stable numeric endpoints; **3/4** have complete supported causal totals. All 7 admitted nonzero numeric segments occur exactly once. The denominator is observed action/target HP groups, as in B16, and excludes completely unseen HP events; it is not recall. 4 groups have a supported immediate cause including incomplete totals.

Receipts: `{'deferred': 3, 'recorded_observation': 371, 'applied_candidate': 721, 'applied_partial': 13}`. Deferred: 3; rejected: 0; state conflicts: 0. Exact event adaptation and complete state/receipt/hash replay were reproduced offline, which establishes determinism rather than recognition correctness.

## Predicted observable events

Event-type inventory: `{'hud_observation': 691, 'preview_observation': 358, 'trainer_observation': 2, 'entry_observation': 6, 'send_out': 8, 'ability_activation': 3, 'stat_change': 7, 'move_execution': 13, 'move_effect': 6, 'side_condition_change': 2, 'switch_out': 4, 'weather_change': 1, 'effectiveness': 4, 'transformation': 1, 'faint': 1, 'item_activation': 1}`.

Deferred reasons: `{'message_episode_occupancy_unresolved': 3}`.
Unresolved HP reasons: `{'final_visible_plateau_unresolved': 1, 'resolution_window_still_open': 1}`.

## Move and condition receipts

These are source-text/parser predictions with their actual admission status, not independently verified executions/effects. Item/ability announcements alone do not supply HP amounts.

| Source s | Kind | Side | Literal text | Receipt |
|---:|---|---|---|---|
| 126.505 | ability_activation | opponent | 炽焰咆哮虎的威吓 | applied_candidate |
| 127.005 | stat_change | self | 长毛巨魔和铝钢桥龙的 攻击降低了！ | applied_candidate |
| 127.005 | stat_change | self | 长毛巨魔和铝钢桥龙的 攻击降低了！ | applied_candidate |
| 158.51 | move_execution | self | 铝钢桥龙使出了 守住！ | applied_partial |
| 164.01166666666666 | move_execution | self | 长毛巨魔使出了 光墙！ | applied_partial |
| 168.01166666666666 | side_condition_change | self | 光墙使我方的 特殊抗性提高了！ | applied_candidate |
| 170.01166666666666 | move_execution | opponent | 对手的烈咬陆鲨使出了 跺脚！ | applied_partial |
| 174.01333333333332 | move_execution | opponent | 对手的炽焰咆哮虎使出了 抛下狠话！ | applied_partial |
| 229.52166666666668 | ability_activation | self | 大嘴鸥的降雨 | applied_candidate |
| 229.52166666666668 | weather_change | field | 开始下雨了！ | applied_candidate |
| 232.005 | move_execution | self | 长毛巨魔使出了 反射壁! | applied_partial |
| 236.02333333333334 | side_condition_change | self | 反射壁使我方的 物理抗性提高了！ | applied_candidate |
| 237.52333333333334 | move_execution | opponent | 对手的烈咬陆鲨使出了 跺脚！ | applied_partial |
| 241.52333333333334 | move_execution | opponent | 对手的炽焰咆哮虎使出了 抛下狠话！ | applied_partial |
| 245.025 | stat_change | self | 大嘴鸥的 攻击、特攻降低了！ | applied_candidate |
| 308.00166666666667 | move_execution | opponent | 对手的烈咬陆鲨使出了 守住！ | applied_partial |
| 313.00333333333333 | move_execution | self | 长毛巨魔使出了 抛下狠话！ | applied_partial |
| 316.52 | stat_change | opponent | 对手的铝钢桥龙的 攻击、特攻降低了！ | applied_candidate |
| 328.005 | move_execution | opponent | 对手的铝钢桥龙使出了 电光束！ | applied_partial |
| 336.50666666666666 | stat_change | opponent | 对手的铝钢桥龙的 特攻提高了！ | applied_candidate |
| 370.51166666666666 | move_execution | self | 烈咬陆鲨使出了 龙之波动！ | applied_partial |
| 381.515 | move_execution | self | 铝钢桥龙使出了 大声咆哮！ | applied_partial |
| 385.515 | stat_change | opponent | 对手的铝钢桥龙的 特攻降低了！ | applied_candidate |
| 387.515 | ability_activation | opponent | 铝钢桥龙的持久力 | applied_candidate |
| 388.015 | stat_change | opponent | 对手的铝钢桥龙的 防御提高了！ | applied_candidate |
| 390.515 | move_execution | opponent | 对手的铝钢桥龙使出了 龙之波动！ | applied_partial |
| 398.01666666666665 | item_activation | opponent | 铝钢桥龙的吃剩的东西 | applied_candidate |

No parsed status/terrain notice is treated as evidence of absence. Full literal references and per-fact evidence remain in [semantic-inventory.json](semantic-inventory.json).

## HP episodes

| Source s | Affected instance | Cause | Before → after | Delta/unit | Status / reasons |
|---:|---|---|---|---|---|
| 370.51166666666666 | opponent 烈咬陆鲨 / `sample_battle_18:opponent:encounter:1748e08ed1c1c14c` | 龙之波动 | 100 → 0 | -100 / displayed_percent | supported;  |
| 381.515 | opponent 铝钢桥龙 / `sample_battle_18:opponent:encounter:0d76a971f507aa4f` | 大声咆哮 | 100 → 84 | -16 / displayed_percent | supported;  |
| 390.515 | self 超级烈咬陆鲨 / `sample_battle_18:self:encounter:e9d6138aacaca861` | 龙之波动 | 184 → 119 | -65 / absolute | supported;  |
| 398.01666666666665 | opponent 铝钢桥龙 / `sample_battle_18:opponent:encounter:0d76a971f507aa4f` | 吃剩的东西 | 84 → 90 | None / displayed_percent | ambiguous; final_visible_plateau_unresolved, resolution_window_still_open |

## Final state and identity limits

Final phase: `{'value': None, 'knowledge': 'unknown'}`; turn: `{'value': None, 'knowledge': 'unknown'}`. Game turns are not reconstructed from hypothetical logs.

| Side | Slot | Instance | Species | Current HP | Fainted / status |
|---|---|---|---|---|---|
| self | right | `sample_battle_18:self:encounter:e9d6138aacaca861` | 超级烈咬陆鲨 | absolute `{'value': 119, 'knowledge': 'observed'}`; percent `{'value': None, 'knowledge': 'unknown'}` | `{'value': False, 'knowledge': 'observed'}` / `{'value': None, 'knowledge': 'unknown'}` |
| self | left | `sample_battle_18:self:encounter:4b23133d0609cb24` | 铝钢桥龙 | absolute `{'value': 194, 'knowledge': 'observed'}`; percent `{'value': None, 'knowledge': 'unknown'}` | `{'value': False, 'knowledge': 'observed'}` / `{'value': None, 'knowledge': 'unknown'}` |
| opponent | right | `sample_battle_18:opponent:encounter:0d76a971f507aa4f` | 铝钢桥龙 | absolute `{'value': None, 'knowledge': 'unknown'}`; percent `{'value': 90, 'knowledge': 'observed'}` | `{'value': False, 'knowledge': 'observed'}` / `{'value': None, 'knowledge': 'unknown'}` |

Full observable inventory, conditions, revealed moves, stages, items and abilities: [final-state-summary.json](final-state-summary.json). Facts retain observed/derived/unknown/conflicting categories. Encounter counts are not biological team size; unproven same-species returns are not merged.

Potential multi-hit/contact/ally examples: `{}`. [examples.json](examples.json) contains prediction evidence, not independent verification. Zero notices do not prove no such move occurred. No high-FPS acquisition is integrated into this production command; optional source review is not represented as measured recognition success.

Raw events, receipt bindings and source images: [events.json](events.json). [Original production viewer](../../event-driven/fresh-b17-b18-20261028-v1/review.html). HP projection with endpoint IDs and provenance remains in `fresh-benchmark/<run>/hp-resolutions.json`.

Limitations: no independent event/state labels or accuracy measurement; incomplete numeric endpoints, ambiguous causes/identities, deferred/rejected receipts and unknown facts remain unresolved. No recognition rules were tuned from this recording. The stock production viewer includes inherited caveat text about prior recognition context; this benchmark’s fresh namespace/cache provenance is recorded separately in the execution/freeze manifests.
