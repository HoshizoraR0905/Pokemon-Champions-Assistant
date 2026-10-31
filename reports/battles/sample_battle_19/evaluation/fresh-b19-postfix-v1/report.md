# sample_battle_19 — fresh video-only reconstruction

Initial run `fresh-b19-postfix-v1`. Raw predictions and the HP view were sealed before failure review. No Battle Log or independent labels exist; all counts describe pipeline behavior, not accuracy.

Normal production wall: **317.365 s**; PTR **0.8100**. Monitoring: 784 frames; detailed inspections: 776; OCR model calls: 3508.

Parsed move executions: **12** (12 admitted, including revelation-only records). Switch-out/send-out/faint predictions: **0/5/1**.

HP coverage: **10/11** groups have complete stable numeric endpoints; **10/11** have complete supported causal totals. All 24 admitted nonzero numeric segments occur exactly once. The denominator is observed action/target HP groups, as in B16, and excludes completely unseen HP events; it is not recall. 11 groups have a supported immediate cause including incomplete totals.

Receipts: `{'recorded_observation': 16, 'applied_candidate': 1068, 'rejected': 1, 'applied_partial': 12, 'deferred': 13}`. Deferred: 13; rejected: 1; state conflicts: 2. Exact event adaptation and complete state/receipt/hash replay were reproduced offline, which establishes determinism rather than recognition correctness.

## Predicted observable events

Event-type inventory: `{'preview_observation': 6, 'trainer_observation': 2, 'entry_observation': 3, 'send_out': 5, 'ability_activation': 6, 'hud_observation': 1051, 'move_execution': 12, 'move_effect': 8, 'effectiveness': 4, 'faint': 1, 'transformation': 1, 'stat_change': 8, 'item_activation': 2, 'visual_observation': 1}`.

Deferred reasons: `{'message_episode_occupancy_unresolved': 13}`.
Unresolved HP reasons: `{'resolution_window_still_open': 1}`.

## Move and condition receipts

These are source-text/parser predictions with their actual admission status, not independently verified executions/effects. Item/ability announcements alone do not supply HP amounts.

| Source s | Kind | Side | Literal text | Receipt |
|---:|---|---|---|---|
| 91.015 | ability_activation | opponent | 沙奈朵的复制 | applied_candidate |
| 92.015 | ability_activation | unknown | 沙奈朵的叶绿素 | rejected |
| 138.02333333333334 | move_execution | self | 喷火龙使出了 守住！ | applied_partial |
| 143.02333333333334 | move_execution | self | 妙蛙花使出了 守住！ | applied_partial |
| 158.52666666666667 | move_execution | opponent | 对手的皮卡丘使出了 佯攻！ | applied_partial |
| 165.52833333333334 | move_execution | opponent | 对手的沙奈朵使出了 广域战力！ | applied_partial |
| 229.005 | ability_activation | self | 喷火龙的日照 | applied_candidate |
| 231.005 | move_execution | opponent | 对手的沙奈朵使出了 守住！ | applied_partial |
| 239.50666666666666 | move_execution | opponent | 对手的皮卡丘使出了 电网！ | applied_partial |
| 248.00833333333333 | stat_change | self | 喷火龙和铝钢桥龙的 速度降低了！ | applied_candidate |
| 248.00833333333333 | stat_change | self | 喷火龙和铝钢桥龙的 速度降低了！ | applied_candidate |
| 249.50833333333333 | ability_activation | self | 铝钢桥龙的持久力 | applied_candidate |
| 250.00833333333333 | stat_change | self | 铝钢桥龙的 防御提高了！ | applied_candidate |
| 252.51 | move_execution | self | 喷火龙使出了 气象球！ | applied_partial |
| 257.51 | move_execution | self | 铝钢桥龙使出了 大声咆哮！ | applied_partial |
| 265.01166666666666 | stat_change | opponent | 对手的皮卡丘的 特攻降低了！ | applied_candidate |
| 268.01166666666666 | item_activation | self | 铝钢桥龙的吃剩的东西 | applied_candidate |
| 322.505 | move_execution | self | 喷火龙使出了 守住！ | applied_partial |
| 328.02166666666665 | move_execution | opponent | 对手的沙奈朵使出了 巨声! | applied_partial |
| 337.0233333333333 | ability_activation | self | 铝钢桥龙的持久力 | applied_candidate |
| 337.5233333333333 | stat_change | self | 铝钢桥龙的 防御提高了！ | applied_candidate |
| 342.0083333333333 | move_execution | opponent | 对手的皮卡丘使出了 蛮干！ | applied_partial |
| 345.525 | ability_activation | self | 铝钢桥龙的持久力 | applied_candidate |
| 345.525 | stat_change | self | 铝钢桥龙的 防御提高了! | applied_candidate |
| 348.525 | move_execution | self | 铝钢桥龙使出了 大声咆哮！ | applied_partial |
| 353.52666666666664 | stat_change | opponent | 对手的皮卡丘和 对手的沙奈朵的 特攻降低了！ | applied_candidate |
| 353.52666666666664 | stat_change | opponent | 对手的皮卡丘和 对手的沙奈朵的 特攻降低了！ | applied_candidate |
| 356.51 | item_activation | self | 铝钢桥龙的吃剩的东西 | applied_candidate |

No parsed status/terrain notice is treated as evidence of absence. Full literal references and per-fact evidence remain in [semantic-inventory.json](semantic-inventory.json).

## HP episodes

| Source s | Affected instance | Cause | Before → after | Delta/unit | Status / reasons |
|---:|---|---|---|---|---|
| 158.52666666666667 | self 妙蛙花 / `sample_battle_19:self:encounter:d2cce58fc755498d` | 佯攻 | 156 → 146 | -10 / absolute | supported;  |
| 165.52833333333334 | self 妙蛙花 / `sample_battle_19:self:encounter:d2cce58fc755498d` | 广域战力 | 146 → 0 | -146 / absolute | supported;  |
| 239.50666666666666 | self 铝钢桥龙 / `sample_battle_19:self:encounter:c36b277856ee360a` | 电网 | 194 → 182 | -12 / absolute | supported;  |
| 239.50666666666666 | self 喷火龙 / `sample_battle_19:self:encounter:ef5128a442ced02f` | 电网 | 184 → 146 | -38 / absolute | supported;  |
| 257.51 | opponent 皮卡丘 / `sample_battle_19:opponent:encounter:eb3f5c416403711d` | 大声咆哮 | 100 → 64 | -36 / displayed_percent | supported;  |
| 268.01166666666666 | self 铝钢桥龙 / `sample_battle_19:self:encounter:c36b277856ee360a` | 吃剩的东西 | 182 → 194 | 12 / absolute | supported;  |
| 328.02166666666665 | self 铝钢桥龙 / `sample_battle_19:self:encounter:c36b277856ee360a` | 巨声 | 194 → 170 | -24 / absolute | supported;  |
| 342.0083333333333 | self 铝钢桥龙 / `sample_battle_19:self:encounter:c36b277856ee360a` | 蛮干 | 170 → 71 | -99 / absolute | supported;  |
| 348.525 | opponent 沙奈朵 / `sample_battle_19:opponent:encounter:d2486c2a02dc82a0` | 大声咆哮 | 100 → 87 | -13 / displayed_percent | supported;  |
| 348.525 | opponent 皮卡丘 / `sample_battle_19:opponent:encounter:eb3f5c416403711d` | 大声咆哮 | 64 → 26 | -38 / displayed_percent | supported;  |
| 356.51 | self 铝钢桥龙 / `sample_battle_19:self:encounter:c36b277856ee360a` | 吃剩的东西 | 71 → 83 | None / absolute | ambiguous; resolution_window_still_open |

## Final state and identity limits

Final phase: `{'value': None, 'knowledge': 'unknown'}`; turn: `{'value': None, 'knowledge': 'unknown'}`. Game turns are not reconstructed from hypothetical logs.

| Side | Slot | Instance | Species | Current HP | Fainted / status |
|---|---|---|---|---|---|
| self | left | `sample_battle_19:self:encounter:ef5128a442ced02f` | 喷火龙 | absolute `{'value': 146, 'knowledge': 'observed'}`; percent `{'value': None, 'knowledge': 'unknown'}` | `{'value': False, 'knowledge': 'observed'}` / `{'value': None, 'knowledge': 'unknown'}` |
| self | right | `sample_battle_19:self:encounter:c36b277856ee360a` | 铝钢桥龙 | absolute `{'value': 83, 'knowledge': 'observed'}`; percent `{'value': None, 'knowledge': 'unknown'}` | `{'value': False, 'knowledge': 'observed'}` / `{'value': None, 'knowledge': 'unknown'}` |
| opponent | right | `sample_battle_19:opponent:encounter:eb3f5c416403711d` | 皮卡丘 | absolute `{'value': None, 'knowledge': 'unknown'}`; percent `{'value': 26, 'knowledge': 'observed'}` | `{'value': False, 'knowledge': 'observed'}` / `{'value': None, 'knowledge': 'unknown'}` |
| opponent | left | `sample_battle_19:opponent:encounter:d2486c2a02dc82a0` | 沙奈朵 | absolute `{'value': None, 'knowledge': 'unknown'}`; percent `{'value': 87, 'knowledge': 'observed'}` | `{'value': False, 'knowledge': 'observed'}` / `{'value': None, 'knowledge': 'unknown'}` |

Full observable inventory, conditions, revealed moves, stages, items and abilities: [final-state-summary.json](final-state-summary.json). Facts retain observed/derived/unknown/conflicting categories. Encounter counts are not biological team size; unproven same-species returns are not merged.

Potential multi-hit/contact/ally examples: `{}`. [examples.json](examples.json) contains prediction evidence, not independent verification. Zero notices do not prove no such move occurred. No high-FPS acquisition is integrated into this production command; optional source review is not represented as measured recognition success.

Raw events, receipt bindings and source images: [events.json](events.json). [Original production viewer](../../event-driven/fresh-b19-postfix-v1/review.html). HP projection with endpoint IDs and provenance remains in `fresh-benchmark/<run>/hp-resolutions.json`.

Limitations: no independent event/state labels or accuracy measurement; incomplete numeric endpoints, ambiguous causes/identities, deferred/rejected receipts and unknown facts remain unresolved. No recognition rules were tuned from this recording. The stock production viewer includes inherited caveat text about prior recognition context; this benchmark’s fresh namespace/cache provenance is recorded separately in the execution/freeze manifests.
