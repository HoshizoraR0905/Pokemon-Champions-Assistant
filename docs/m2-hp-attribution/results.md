# M2 HP attribution — final development result

Completed run: `b16-hp-attribution-20261028-v5`. Sealed v5 acquisition / v6 predictions and the original B16 reference are preserved. No decoding, OCR, sampling/threshold changes, commits or pushes.

41 observed nonzero numeric changes have complete adjacent same-instance endpoint pairs. **13 supported**, **28 ambiguous**, **0 unknown without candidates**; causal coverage **31.7%**. Counts include animation segments and do not replace the 21 reference endpoint episodes. Twelve initial numeric observations lack baselines and cannot establish changes.

B16 supported categories: 9 move-damage segments and 4 explicit burn segments. Recoil, self cost, item, ability, weather, hazard, Perish Song and healing have zero supported B16 segments; their successful/abstaining synthetic tests establish contracts only.

Every event receipt status/reason and all non-attribution state, including archived HP snapshots, match v6 exactly. Original metrics remain **120/124 event facts**, **175/191 state fields**, **18/21 numeric reference endpoint pairs**, **3/3 observed HUD-zero endpoints**. No new state conflict is introduced. Incorrect causal-label associations are unmeasured because no independently verified numeric cause labels exist; no causal accuracy is claimed.

Rows below group adjacent attributed segments sharing one source occurrence. They report observed portions of the animation, not total move damage. Own values are absolute HP; opponent values are displayed percentage points.

| Affected Pokémon | Supported observed segments | Cause / source time (s) | Source event |
|---|---|---|---|
| own 妙蛙花 | 66 → 2 → 0 (absolute) | 气象球 / 361.512 | `event:f69fc719b2fce86f2cded3e4` |
| opponent 烈咬陆鲨 | 81 → 67 (displayed_percent) | 气象球 / 290.032 | `event:e5e43c97cfab3045243a326e` |
| opponent 烈咬陆鲨 | 67 → 55 → 48 (displayed_percent) | 气象球 / 552.510 | `event:733fef2838067330fe6f31f7` |
| opponent 铝钢桥龙 | 19 → 0 (displayed_percent) | 电光束 / 443.508 | `event:be7962741c1963b03ffc9f93` |
| own 大嘴鸥 | 122 → 110 (absolute) | 热风 / 538.507 | `event:bde2c64e7a077fa13ac14efa` |
| own 大嘴鸥 | 110 → 103 → 100 (absolute) | burn / 561.012 | `event:3077ddb3cb20d11e73b499db` |
| own 大嘴鸥 | 100 → 92 → 90 (absolute) | burn / 623.522 | `event:bacd62f676cec2194ca1f5bc` |
| own 喷火龙 | 101 → 12 (absolute) | 气象球 / 727.005 | `event:a631a4841a20683a3dc28209` |
| opponent 大嘴鸥 | 53 → 33 (displayed_percent) | 气象球 / 676.530 | `event:654fec86a6dc78e8f7c8b794` |

| Unresolved example | Evidence limitation |
|---|---|
| Opponent Pelipper 37 → 52 → 62 percentage points | Item activation does not establish a numeric healing occurrence or its exclusive source. |
| Opponent Charizard 100 → 48 → 0 percentage points | Named move recipient exists, but unreadable/unresolved HUD evidence interrupts the window; abstention retained. |
| Own Charizard 184 → 170 absolute HP | Multiple actions and activations span the endpoint interval. |

Full per-segment IDs, endpoint times, binding, evidence and abstention reasons: [final report](../../reports/battles/sample_battle_16/evaluation/b16-hp-attribution-20261028-v5/report.md) and its linked `causal-links.json`. Source snapshots, partial states, replay and stage manifest remain under `.cache/battles/sample_battle_16/hp-attribution/b16-hp-attribution-20261028-v5/`.

Validation: **229 passed, 3 deselected** (`not local_artifacts`), 41.34 s; compilation and `git diff --check` passed. The suite covers required categories, spread recipients, units/zero, missing observations, gaps/ties, competing causes, source-holder ambiguity, replay, retraction and correction.

Implementation: `tracking/hp_causes.py`, scoped replay hooks in `tracking/state_engine.py`, `tests/test_hp_attribution.py`, and `scripts/evaluate_hp_attribution.py`. Existing parsers, HP numeric admission and identities remain responsible for their original facts. Optional causal metadata changes state hashes; replay rebuilds it from the admitted prefix rather than trusting cached links.

Next priorities: independently review causal labels; resolve specific missing endpoint/coverage evidence and obtain explicit item/ability HP-effect announcements. These remain outside the completed change. Resume/cache commands and intermediate run explanations are in [progress.md](progress.md).
