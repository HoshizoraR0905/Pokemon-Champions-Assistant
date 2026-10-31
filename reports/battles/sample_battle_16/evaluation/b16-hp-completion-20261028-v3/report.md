# B16 HP endpoint completion

Run `b16-hp-completion-20261028-v3`. Development evaluation using saved original-video HP-only observations.

Complete attribution: **21/21**, previously 16/21. Frozen membership retains all 41 original numeric segments exactly once. All 16 previously supported totals are unchanged.

No manual HP values enter prediction. Extra source reads bind to existing send-out/slot intervals; they do not merge same-species encounters, rewrite sealed state or become live recognition results. The original StateEngine state and every receipt are unchanged.

| Source time | Cause | Affected | Pre HP / provenance | Post HP / provenance | Signed delta | Complete |
|---:|---|---|---|---|---:|---|
| 286.515 | 文柚果 | opponent 大嘴鸥 | 37 / pre_source_observation | 62 / repeated_visible_hp | 25 displayed_percent | supported |
| 290.032 | 气象球 | opponent 烈咬陆鲨 | 100 / observed_full_scale_before_decrease | 67 / repeated_visible_hp | -33 displayed_percent | supported |
| 443.508 | 电光束 | opponent 铝钢桥龙 | 25 / observed_source_animation_onset | 0 / observed_zero_then_faint | -25 displayed_percent | supported |
| 623.522 | burn | self 大嘴鸥 | 100 / pre_source_observation | 90 / repeated_visible_hp | -10 absolute | supported |
| 676.530 | 气象球 | opponent 大嘴鸥 | 62 / observed_source_animation_onset | 33 / repeated_visible_hp | -29 displayed_percent | supported |

## Per-case evidence and uncertainty

### 286.515 s — 大嘴鸥

- Instance: `sample_battle_16:opponent:encounter:6a435277a5b2e70f`; cause receipt: `event:c503c8b239bb5f406d603fb1`.
- Before: `event:ac004549dd5182f82dcb1a03` at PTS 286.015000; frame `.cache/battles/sample_battle_16/event-driven/b16-banner-hp-20261028-v5/frames/000501.png`.
- After: `source-hp:e327b10daf414bbeca9472fd694e17aa56ce2c8c828f37576a1637274339d03e:opponent_active_2` at PTS 289.431667; frame `.cache/battles/sample_battle_16/hp-resolution-sampling/b16-hp-completion-berry-20261028-v1/frames/000027.png`.
- Previous rejection: final_visible_plateau_unresolved.
- Current unresolved reasons: none under the stated evidence policy.

### 290.032 s — 烈咬陆鲨

- Instance: `sample_battle_16:opponent:encounter:042a1409419f9f91`; cause receipt: `event:e5e43c97cfab3045243a326e`.
- Before: `source-hp:6ac543ffe0de70a6976f559de15ed7a2904d8ee6aa4b93710486d1482c075699:opponent_active_1` at PTS 293.600000; frame `.cache/battles/sample_battle_16/hp-resolution-sampling/b16-hp-completion-garchomp-20261028-v1/frames/000068.png`.
- After: `source-hp:a62c3bfcb1b4cd59dea71750bed4a37c00c54743c4ccc0fb3fb8bc2498f352df:opponent_active_1` at PTS 298.200000; frame `.cache/battles/sample_battle_16/hp-resolution-sampling/b16-hp-completion-garchomp-20261028-v1/frames/000091.png`.
- Previous rejection: pre_action_hp_missing.
- Current unresolved reasons: none under the stated evidence policy.

### 443.508 s — 铝钢桥龙

- Instance: `sample_battle_16:opponent:encounter:5ff05718998eb73d`; cause receipt: `event:be7962741c1963b03ffc9f93`.
- Before: `source-hp:ed27a544cda156f40f26757e1519d580e9cf8b2b7aa0c4bd32b7f5ea8f844a54:opponent_active_2` at PTS 457.260000; frame `.cache/battles/sample_battle_16/hp-resolution-sampling/b16-hp-completion-archaludon-onset-20261028-v1/frames/000002.png`.
- After: `source-hp:412dc274c716fe2fc6213791c86c23ca4c68a2d4062779af3d4bc99962a25130:opponent_active_2` at PTS 461.411667; frame `.cache/battles/sample_battle_16/hp-resolution-sampling/b16-hp-completion-archaludon-20261028-v1/frames/000162.png`.
- Previous rejection: pre_action_hp_missing.
- Current unresolved reasons: none under the stated evidence policy.

### 623.522 s — 大嘴鸥

- Instance: `sample_battle_16:self:encounter:2ac46eab0b3dff21`; cause receipt: `event:bacd62f676cec2194ca1f5bc`.
- Before: `event:7d3d382585fabb42f28e96b1` at PTS 598.016667; frame `.cache/battles/sample_battle_16/event-driven/b16-banner-hp-20261028-v5/frames/000993.png`.
- After: `source-hp:642a8c13fca230b0833cc2a662a462cd59e2dfd73e92ffa46028a736f457dc00:own_active_1` at PTS 625.221667; frame `.cache/battles/sample_battle_16/hp-resolution-sampling/b16-hp-completion-burn-20261028-v1/frames/000016.png`.
- Previous rejection: final_visible_plateau_unresolved.
- Current unresolved reasons: none under the stated evidence policy.

### 676.530 s — 大嘴鸥

- Instance: `sample_battle_16:opponent:encounter:4d8ce5638af5c17e`; cause receipt: `event:654fec86a6dc78e8f7c8b794`.
- Before: `source-hp:861a7aeaebf90b44de4549a6700d1fd359013324e67725590a76ec9e4c7b2a21:opponent_active_1` at PTS 680.231667; frame `.cache/battles/sample_battle_16/hp-resolution-sampling/b16-hp-completion-pelipper-onset-20261028-v1/frames/000005.png`.
- After: `source-hp:b37be27b2c1261ac6bb71c8bc7205dc133f8be6d9e9d4ad4a192f684cf0a0c5e:opponent_active_1` at PTS 684.615000; frame `.cache/battles/sample_battle_16/hp-resolution-sampling/b16-hp-completion-return-pelipper-20261028-v1/frames/000098.png`.
- Previous rejection: pre_action_hp_missing.
- Current unresolved reasons: none under the stated evidence policy.

Native 2 FPS evidence had only one final reading for Berry/burn; HP cards then disappeared before the next receipt. Additional source frames establish repeated visible values. For the three attacks, source onset readings recover baselines that were absent from admitted 2 FPS history. Archaludon requires 20 FPS onset inspection: the first 5 FPS value is already in the animation. These are observed endpoints, not inferred healing fractions or assumed starting HP.

A non-full onset requires at least three distinct source times spanning 0.1 s before the first decrease, contiguous at <=0.25 s gaps. Full-scale evidence supplies its own upper bound. Ordinary final stability still uses the configured 0.4 s duration. A trustworthy final read can also finish at an admitted independent resolution within 0.5 s, absent an HP gap. Gaps, competing sources and unresolved identities still veto acceptance.

Same-instance switch carries remain derived facts with original evidence. New entry HUDs confirm or correct them. First-entry 100% is only an unestablished conditional hypothesis without supporting numeric evidence. No possible Regenerator, item or ability supplies a numeric change. Existing unresolved biological continuity across some same-species encounters remains unresolved; these five totals use local source observations rather than an identity merge.

Displayed opponent percentages are percentage points, not exact HP. No independent 21-case causal labels or real multi-hit validation are claimed. Original event/state metrics stay 120/124 and 175/191; original reference numeric pairs 18/21 and zeros 3/3 remain separate metrics.

Sampling totals across separate completed source runs: `{'sampled_frames': 468, 'ocr_read_requests': 121, 'ocr_model_predictions': 89, 'full_screen_ocr_calls': 0}`. Sampling source PTS, frame hashes, visibility/reuse receipts, OCR and resume checkpoints remain under each sample manifest. No full-screen OCR or broad replay was run.

Full per-case numeric/source provenance: [cases.json](cases.json). Projection: [episodes.json](episodes.json).
