# M2 — Action-level HP resolution

Run `b16-action-resolution-20261028-v1`. Read-only projection of sealed `b16-hp-attribution-20261028-v5` receipts and HP history; no Battle Log labels enter predictions.

**41 adjacent changes → 21 action/target episodes**, across 25 move executions (including moves without observed damage). **16 complete endpoint pairs**, **10 known causes**, **6 complete supported causal episodes**. 15 episodes remain unresolved.

Comparable action-level attribution coverage: **2/21 (9.5%) → 6/21 (28.6%)**. The denominator is the same 21 observed action/target groups, determined from saved live event boundaries before consulting any reference. The old count of 13/41 describes adjacent animation fragments and is not action coverage. The before numerator additionally requires all fragments in a complete stable episode to have the same supported legacy source. After coverage among complete endpoint episodes is 6/16 (37.5%).

Totals use the last reliable pre-action HP and the final observed plateau before the next independent action/effect. Critical, effectiveness and hit-count messages stay in their action. HP observation gaps limit hit resolution; an event/identity coverage gap still vetoes a causal total. A source announcement alone does not establish a target. Item activation alone does not prove healing. Missing pre-action HP yields a partial observation only, never an invented total. A single last HP read without a visible plateau or an observed zero followed by its faint is not a settled endpoint.

Derived projection leaves every serialized state field, history receipt and original endpoint unchanged. Original metrics: **120/124 event facts; 175/191 state fields; 18/21 reference numeric pairs; 3/3 observed HUD zeros**. The stricter stable action boundary count is a separate measure. No causal accuracy is reported without independently verified cause labels.

| Source time (s) | Affected instance | Before → final | Unit | Total signed delta | Cause / status | Boundary issues |
|---:|---|---|---|---:|---|---|
| 196.500 | opponent 铝钢桥龙 | 100 → 13 | displayed_percent | -87 | unknown; ambiguous | affected_target_or_cause_unresolved |
| 206.002 | own 喷火龙 | 184 → 164 | absolute | -20 | unknown; ambiguous | affected_target_or_cause_unresolved |
| 206.002 | own 妙蛙花 | 156 → 129 | absolute | -27 | unknown; ambiguous | affected_target_or_cause_unresolved |
| 214.520 | opponent 铝钢桥龙 | 13 → 19 | displayed_percent | 6 | unknown; ambiguous | affected_target_or_cause_unresolved |
| 245.008 | opponent 大嘴鸥 | 100 → 68 | displayed_percent | -32 | unknown; ambiguous | affected_target_or_cause_unresolved |
| 255.510 | opponent 铝钢桥龙 | 19 → 25 | displayed_percent | 6 | unknown; ambiguous | affected_target_or_cause_unresolved |
| 283.015 | opponent 大嘴鸥 | 68 → 37 | displayed_percent | -31 | unknown; ambiguous | affected_target_or_cause_unresolved |
| 286.515 | opponent 大嘴鸥 | 37 → 62 | displayed_percent | None | unknown; ambiguous | affected_target_or_cause_unresolved, final_visible_plateau_unresolved |
| 290.032 | opponent 烈咬陆鲨 | None → 67 | displayed_percent | None | 气象球; ambiguous | pre_action_hp_missing |
| 345.008 | own 妙蛙花 | 129 → 84 | absolute | -45 | unknown; ambiguous | affected_target_or_cause_unresolved |
| 361.512 | own 妙蛙花 | 84 → 0 | absolute | -84 | 气象球; supported |  |
| 443.508 | opponent 铝钢桥龙 | None → 0 | displayed_percent | None | 电光束; ambiguous | pre_action_hp_missing |
| 538.507 | own 大嘴鸥 | 164 → 110 | absolute | -54 | 热风; supported |  |
| 552.510 | opponent 烈咬陆鲨 | 67 → 48 | displayed_percent | -19 | 气象球; supported |  |
| 561.012 | own 大嘴鸥 | 110 → 100 | absolute | -10 | burn; supported |  |
| 613.520 | own 铝钢桥龙 | 194 → 0 | absolute | -194 | unknown; ambiguous | affected_target_or_cause_unresolved |
| 623.522 | own 大嘴鸥 | 100 → 90 | absolute | None | burn; ambiguous | final_visible_plateau_unresolved |
| 676.530 | opponent 大嘴鸥 | None → 33 | displayed_percent | None | 气象球; ambiguous | pre_action_hp_missing |
| 685.532 | own 大嘴鸥 | 90 → 0 | absolute | -90 | unknown; ambiguous | affected_target_or_cause_unresolved |
| 715.503 | opponent 喷火龙 | 100 → 0 | displayed_percent | -100 | 气象球; supported |  |
| 727.005 | own 喷火龙 | 164 → 12 | absolute | -152 | 气象球; supported |  |

Full actor/target IDs, source and endpoint evidence, original segment membership, final plateau receipts, critical/count notices, and boundary receipts: [action-episodes.json](action-episodes.json).

B16 has **0** reference-capable or independently announced multi-hit inspection candidates and **0** supported critical episodes in the saved predictions. No real-video multi-hit success is claimed. Pinned simulator `multihit` facts may trigger inspection but retain their provisional Champions status. Per-hit deltas require >=5 FPS observations and an independent matching hit count; unresolved hits retain the supported action total with per-hit amounts unknown.

High-rate source access uses a targeted original-video PTS second decoding pass, with configurable pre-roll from before the recognized action and the known pre-action endpoint. Ordinary acquisition remains 2 FPS. HP-only visibility/refresh/OCR reuse gates are unchanged; changing frame FPS does not invoke full-screen OCR. Per-frame PTS, hashes, frames sampled, raw frames decoded, ROI requests, model predictions, cache hits and partial checkpoints are recorded by the probe command.

Limitations: B16 does not validate multi-hit or critical-hit detection. Unknown move recipients, missing pre-action readings and two unresolved final plateaus remain; item healing sources need explicit effect evidence. Tests of spread/recoil/items/abilities/multi-hit validate contracts only. Next priorities are independently reviewed action/critical/hit labels and a real multi-hit recording; no further milestone is started.
