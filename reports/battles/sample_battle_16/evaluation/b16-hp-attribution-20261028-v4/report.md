# M2 — B16 evidence-based HP attribution

Run `b16-hp-attribution-20261028-v4`; sealed v6 events and endpoints, v5 acquisition; no OCR or reference edits.

Observed numeric changes: **41**, complete adjacent endpoint pairs: **41**. Supported: **13**; ambiguous: **28**; unknown: **0**. Causal coverage: **31.7%**.

Cause categories: `{'move_damage': 9, 'recoil': 0, 'self_hp_cost': 0, 'item': 0, 'ability': 0, 'status': 4, 'weather': 0, 'hazard': 0, 'instant_faint': 0, 'healing': 0}`.

Counts include animation segments. Observations without a baseline are separately listed; they cannot establish a change. The sealed reference stays at 124 event facts, 191 state fields and 21 endpoint episodes; these are distinct denominators.

Every receipt status/reason and all final non-attribution state fields equal v6. Existing reconstruction metrics remain **120/124**, **175/191**, numeric reference endpoint pairs **18/21**, observed HUD zeros **3/3**. State hashes change because HP histories now include causal metadata.

Causal correctness is unmeasured: no independently verified numeric causal labels exist. No detected conflict is established by this replay comparison; an incorrect-link rate cannot be inferred. Synthetic tests verify contracts only.

| Affected instance | Before → after | Unit | Status / cause | Endpoint times | Evidence IDs / unresolved reason |
|---|---:|---|---|---|---|
| sample_battle_16:opponent:encounter:6a435277a5b2e70f | 100 → 98 (-2) | displayed_percent | ambiguous | 238.54 → 246.50833333333333 | multiple_actions_between_endpoints, no_unique_named_recipient_in_action_window |
| sample_battle_16:opponent:encounter:6a435277a5b2e70f | 98 → 73 (-25) | displayed_percent | ambiguous | 246.50833333333333 → 247.00833333333333 | no_unique_named_recipient_in_action_window |
| sample_battle_16:opponent:encounter:6a435277a5b2e70f | 73 → 68 (-5) | displayed_percent | ambiguous | 247.00833333333333 → 247.50833333333333 | no_unique_named_recipient_in_action_window |
| sample_battle_16:opponent:encounter:6a435277a5b2e70f | 68 → 45 (-23) | displayed_percent | ambiguous | 284.515 → 285.015 | no_unique_named_recipient_in_action_window |
| sample_battle_16:opponent:encounter:6a435277a5b2e70f | 45 → 37 (-8) | displayed_percent | ambiguous | 285.015 → 285.515 | no_unique_named_recipient_in_action_window |
| sample_battle_16:opponent:encounter:6a435277a5b2e70f | 37 → 52 (+15) | displayed_percent | ambiguous | 288.015 → 288.515 | activation_without_scoped_hp_effect, no_unique_named_recipient_in_action_window |
| sample_battle_16:opponent:encounter:6a435277a5b2e70f | 52 → 62 (+10) | displayed_percent | ambiguous | 288.515 → 289.015 | activation_without_scoped_hp_effect, no_unique_named_recipient_in_action_window |
| sample_battle_16:opponent:encounter:56c49d3a1c44c11e | 100 → 64 (-36) | displayed_percent | ambiguous | 174.01333333333332 → 200.5 | activation_without_scoped_hp_effect, multiple_actions_between_endpoints, no_unique_named_recipient_in_action_window |
| sample_battle_16:opponent:encounter:56c49d3a1c44c11e | 64 → 13 (-51) | displayed_percent | ambiguous | 200.5 → 201.01666666666668 | no_unique_named_recipient_in_action_window |
| sample_battle_16:opponent:encounter:56c49d3a1c44c11e | 13 → 17 (+4) | displayed_percent | ambiguous | 217.02 → 217.52 | activation_without_scoped_hp_effect, no_unique_named_recipient_in_action_window |
| sample_battle_16:opponent:encounter:56c49d3a1c44c11e | 17 → 19 (+2) | displayed_percent | ambiguous | 217.52 → 218.02 | activation_without_scoped_hp_effect, no_unique_named_recipient_in_action_window |
| sample_battle_16:opponent:encounter:56c49d3a1c44c11e | 19 → 23 (+4) | displayed_percent | ambiguous | 257.51 → 258.01 | activation_without_scoped_hp_effect, blocked_or_unresolved_action_outcome, no_unique_named_recipient_in_action_window |
| sample_battle_16:opponent:encounter:56c49d3a1c44c11e | 23 → 25 (+2) | displayed_percent | ambiguous | 258.01 → 258.51 | activation_without_scoped_hp_effect, blocked_or_unresolved_action_outcome, no_unique_named_recipient_in_action_window |
| sample_battle_16:self:encounter:74f6f62a20ccc52f | 184 → 170 (-14) | absolute | ambiguous | 174.01333333333332 → 208.01833333333335 | activation_without_scoped_hp_effect, missing_hp_observation, multiple_actions_between_endpoints, no_unique_named_recipient_in_action_window |
| sample_battle_16:self:encounter:74f6f62a20ccc52f | 170 → 164 (-6) | absolute | ambiguous | 208.01833333333335 → 208.51833333333335 | missing_hp_observation, no_unique_named_recipient_in_action_window |
| sample_battle_16:self:encounter:ff3714f826d32c20 | 156 → 138 (-18) | absolute | ambiguous | 174.01333333333332 → 208.01833333333335 | activation_without_scoped_hp_effect, missing_hp_observation, multiple_actions_between_endpoints, no_unique_named_recipient_in_action_window |
| sample_battle_16:self:encounter:ff3714f826d32c20 | 138 → 129 (-9) | absolute | ambiguous | 208.01833333333335 → 208.51833333333335 | missing_hp_observation, no_unique_named_recipient_in_action_window |
| sample_battle_16:self:encounter:ff3714f826d32c20 | 129 → 110 (-19) | absolute | ambiguous | 338.00666666666666 → 350.5083333333333 | multiple_actions_between_endpoints, no_unique_named_recipient_in_action_window |
| sample_battle_16:self:encounter:ff3714f826d32c20 | 110 → 84 (-26) | absolute | ambiguous | 350.5083333333333 → 351.0083333333333 | no_unique_named_recipient_in_action_window |
| sample_battle_16:self:encounter:ff3714f826d32c20 | 84 → 66 (-18) | absolute | ambiguous | 353.01 → 365.51166666666666 | multiple_actions_between_endpoints |
| sample_battle_16:self:encounter:ff3714f826d32c20 | 66 → 2 (-64) | absolute | supported / move 气象球 | 365.51166666666666 → 366.01166666666666 | event:f69fc719b2fce86f2cded3e4, event:183b360d17b08d811268ec32 |
| sample_battle_16:self:encounter:ff3714f826d32c20 | 2 → 0 (-2) | absolute | supported / move 气象球 | 366.01166666666666 → 366.51166666666666 | event:f69fc719b2fce86f2cded3e4, event:183b360d17b08d811268ec32 |
| sample_battle_16:opponent:encounter:042a1409419f9f91 | 81 → 67 (-14) | displayed_percent | supported / move 气象球 | 294.0 → 294.5 | event:e5e43c97cfab3045243a326e, event:761271eabc6313bca0fe0cba |
| sample_battle_16:opponent:encounter:042a1409419f9f91 | 67 → 55 (-12) | displayed_percent | supported / move 气象球 | 556.01 → 556.51 | event:733fef2838067330fe6f31f7, event:cad6a861d76519a1a248e97c |
| sample_battle_16:opponent:encounter:042a1409419f9f91 | 55 → 48 (-7) | displayed_percent | supported / move 气象球 | 556.51 → 557.01 | event:733fef2838067330fe6f31f7, event:cad6a861d76519a1a248e97c |
| sample_battle_16:self:encounter:4a5ffbaf5d03f406 | 194 → 144 (-50) | absolute | ambiguous | 598.0166666666667 → 617.5033333333333 | blocked_or_unresolved_action_outcome, multiple_actions_between_endpoints, no_unique_named_recipient_in_action_window |
| sample_battle_16:self:encounter:4a5ffbaf5d03f406 | 144 → 0 (-144) | absolute | ambiguous | 617.5033333333333 → 618.02 | no_unique_named_recipient_in_action_window |
| sample_battle_16:opponent:encounter:5ff05718998eb73d | 19 → 0 (-19) | displayed_percent | supported / move 电光束 | 457.51 → 458.01 | event:be7962741c1963b03ffc9f93, event:b87ce712379088befdac46a5 |
| sample_battle_16:self:encounter:2ac46eab0b3dff21 | 164 → 122 (-42) | absolute | ambiguous | 518.0033333333333 → 545.0083333333333 | activation_without_scoped_hp_effect, missing_hp_observation, multiple_actions_between_endpoints |
| sample_battle_16:self:encounter:2ac46eab0b3dff21 | 122 → 110 (-12) | absolute | supported / move 热风 | 545.0083333333333 → 545.5083333333333 | event:bde2c64e7a077fa13ac14efa, event:a17235bed7daa658ed4a05be |
| sample_battle_16:self:encounter:2ac46eab0b3dff21 | 110 → 103 (-7) | absolute | supported / status  | 561.5116666666667 → 562.0116666666667 | event:3077ddb3cb20d11e73b499db |
| sample_battle_16:self:encounter:2ac46eab0b3dff21 | 103 → 100 (-3) | absolute | supported / status  | 562.0116666666667 → 562.5116666666667 | event:3077ddb3cb20d11e73b499db |
| sample_battle_16:self:encounter:2ac46eab0b3dff21 | 100 → 92 (-8) | absolute | supported / status  | 624.0216666666666 → 624.505 | event:bacd62f676cec2194ca1f5bc |
| sample_battle_16:self:encounter:2ac46eab0b3dff21 | 92 → 90 (-2) | absolute | supported / status  | 624.505 → 625.0216666666666 | event:bacd62f676cec2194ca1f5bc |
| sample_battle_16:self:encounter:2ac46eab0b3dff21 | 90 → 39 (-51) | absolute | ambiguous | 660.5283333333333 → 690.0 | activation_without_scoped_hp_effect, identity_or_coverage_gap, missing_hp_observation, multiple_actions_between_endpoints, no_unique_named_recipient_in_action_window |
| sample_battle_16:self:encounter:2ac46eab0b3dff21 | 39 → 0 (-39) | absolute | ambiguous | 690.0 → 690.5 | missing_hp_observation, no_unique_named_recipient_in_action_window |
| sample_battle_16:opponent:encounter:b9b5877eef43d9e3 | 100 → 48 (-52) | displayed_percent | ambiguous | 715.0033333333333 → 719.505 | missing_hp_observation, unresolved_event_in_window |
| sample_battle_16:opponent:encounter:b9b5877eef43d9e3 | 48 → 0 (-48) | displayed_percent | ambiguous | 719.505 → 720.005 | missing_hp_observation, unresolved_event_in_window |
| sample_battle_16:self:encounter:9c35e64612992e37 | 164 → 101 (-63) | absolute | ambiguous | 715.0033333333333 → 731.0066666666667 | missing_hp_observation, multiple_actions_between_endpoints, unresolved_event_in_window |
| sample_battle_16:self:encounter:9c35e64612992e37 | 101 → 12 (-89) | absolute | supported / move 气象球 | 731.0066666666667 → 731.5066666666667 | event:a631a4841a20683a3dc28209, event:77b8d4deafe3d6af4f3e19b3 |
| sample_battle_16:opponent:encounter:4d8ce5638af5c17e | 53 → 33 (-20) | displayed_percent | supported / move 气象球 | 680.5316666666666 → 681.0316666666666 | event:654fec86a6dc78e8f7c8b794, event:18d270fc6d576a8b2e88fa8c |

Full source-event → prefix-bound instance → endpoint → causal evidence → applied HP-history traces: [causal-links.json](causal-links.json).

Remaining gaps: no named recipient in many actions; aggregate windows containing several effects; unreadable/hidden HUDs; missing baselines. Item/ability activation alone does not establish a numeric HP occurrence. Later target evidence can revise earlier animation segments only within an uninterrupted action. No damage formulas or move-name target assumptions are used.

Next priorities: review the proposed links independently and collect scoped evidence for unresolved effects. No further milestone is started.
