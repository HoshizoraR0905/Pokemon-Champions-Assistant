# M2.3.7 — Battle 6 full-match recognition review

**Automated/provisional; no independent human ground truth. Semantic acceptance is incomplete.**

[Open the offline review](M2.3.7-battle-6-review/review.html). [Machine-readable turns](M2.3.7-battle-6-turns.json).

## Recording and frozen baseline

Video: `tests/fixtures/sample_battle_6.mp4`; SHA-256 `5a91a2425ac20ff02def159d18ee4c8ae571d328ace0a5265ba77284746478e3`; 753.75s; display 2622×1206; average 47.163745 FPS (variable timestamps).

FFmpeg reports coded 1206×2622 with a 90° display-matrix rotation; extraction uses its 2622×1206 display orientation. Container duration is 753.75s; the count/average-rate estimate is separately retained. Actual source PTS, requested grid times and uncertainty are distinct.

Baseline source freeze: `.cache/battles/sample_battle_6/m237/baseline-freeze.json`; prediction seal: `baseline-prediction-seal.json`. No Battle 6 manual answers, nickname mappings or species choices enter recognition. Existing recognizers/parser/StateEngine are unchanged. No diagnostic tuning is folded into this baseline.

Sampling: 2.0 FPS throughout, width 328 survey and 1311×603 recognition; targeted 3.0 FPS near UI transitions. HUD/interface anchors are at most 2.0s apart when stable, plus detected UI transitions. All supported live-message rows are read. Prediction budgets: 18096 OCR, 9048 icon calls. Exact-pixel caches and per-frame checkpoints are reused.

Extra 3-FPS acquisition covers 149.000s in 36 planned windows, selected chronologically within the frozen 20% duration cap. The later unselected transitions retain the full 2-FPS baseline and are not claimed as enhanced temporal coverage. All planned and decoded target times are retained in acquisition.json.

Recognition configuration: existing PP-OCRv6 medium ONNX on CPU, batch 1, literal read threshold .75 and supported-occurrence threshold .90. Icons use unchanged default and silhouette profiles; independent-profile disagreement abstains. Existing StateEngine reliability_v1, reliability_v2 and identity_v1 are enabled. Exact source, model revision/checksums and icon source are pinned in the freeze and runtime manifests. Confidence is not measured correctness.

## Entire-recording coverage and interpretation

1807 distinct source-PTS frames; 1508/1508 base grid cells represented; 0 empty cells. First sample 0.000000s; last sample 753.510000s. This is sampling coverage, not event recall. Sub-frame events and unrecognized regions can still be missed.

11 proposed command cycles; **0 independently confirmed turn boundaries**. Command menus after live text propose boundaries; animation, switches, two Pokémon selections and unsupported overlays can make that heuristic wrong. Ordinals below are provisional and editable.

A complete chronological inventory of sampled intervals is included below. No interval is automatically certified as containing no relevant event. Baseline outcome/winner remains **unknown**: the existing pipeline has no independently validated result extraction for this video.

## Opening team preview and identities

The following are frozen automatic icon proposals, not manually verified roster members. Rows retain form/game identity and duplicate occurrences. Preview membership does not establish an active slot or nickname.

| Observed at | Opponent row | Automatic species ID | Status |
|---|---|---|---|
| 26.672s | 1 | 445 | resolved |
| 26.672s | 2 | 812 | resolved |
| 26.672s | 3 | 637 | resolved |
| 26.672s | 4 | 727 | resolved |
| 26.672s | 5 | 26 | resolved |
| 26.672s | 6 | 1000 | resolved |
| 339.673s | 1 | None | unresolved |
| 339.673s | 2 | None | unresolved |
| 339.673s | 3 | None | unresolved |
| 339.673s | 4 | None | unresolved |
| 339.673s | 5 | None | unresolved |
| 339.673s | 6 | None | unresolved |

Later preview-labelled rows are retained even when unresolved; they may be misrouted in-battle menus rather than a new team preview. They do not establish a changed opponent roster.

Player roster baseline proposals (first observed record for each displayed row):

| Row | Observed at | Automatic OCR | Canonical proposal |
|---|---|---|---|
| own_team_1 | 6.335s | 妙蛙花 | 妙蛙花 / Venusaur |
| own_team_2 | 6.335s | 喷火龙 | 喷火龙 / Charizard |
| own_team_3 | 6.335s | 大嘴鸥 | 大嘴鸥 / Pelipper |
| own_team_4 | 6.335s | 烈咬陆鲨 | 烈咬陆鲨 / Garchomp |
| own_team_5 | 6.335s | 长毛巨魔 | 长毛巨魔 / Grimmsnarl |
| own_team_6 | 6.335s | 铝钢桥龙 | 铝钢桥龙 / Archaludon |

## Post-baseline visual diagnostic account — provisional, not independent ground truth

Hoshi is shown as **WIN** and REIKOU as **LOSE** at 750.010s. The baseline recognized neither result semantics nor a winner; this same-frame agent visual reading is a separate diagnostic proposal. The preceding surrender sentence does not itself identify which side surrendered. Device controls cover the final frame.

The original baseline has 11 command-cycle proposals, including suspected mid-action splits. The eight groups below are a **post-baseline agent regrouping**, supported by chronological message/selection evidence and the visible historical “回合4” heading at 473s. All boundaries remain provisional, especially transitions around replacement and log/selection interfaces. No human-confirmed turn count is claimed.

### Diagnostic provisional turn 1 — 134.67–203.67s

**Starting participants (provisional).** Grimmsnarl + Archaludon versus Gholdengo + Incineroar.

**Chronological account.** REIKOU withdraws Incineroar and sends Rillaboom. Grass appears. Grimmsnarl announces Light Screen; Gholdengo Nasty Plot; Archaludon Snarl. Stat/effectiveness and healing notices follow.

**Ending participants / field limits.** Grimmsnarl + Archaludon versus Gholdengo + Rillaboom; displayed HP needs separate verification. Exact boundary HP, status and unrevealed abilities/items remain unknown unless a linked frame/receipt supplies them.

**Recognition audit.** Automatic boundaries at 174.53 and 181.51 interrupt this action sequence and are suspected false command-cycle splits.

### Diagnostic provisional turn 2 — 203.67–292.01s

**Starting participants (provisional).** Same four displayed participants as the prior interval.

**Chronological account.** Gholdengo announces Shadow Ball; Archaludon Defense rises. Archaludon announces Snarl. Rillaboom announces U-turn, returns, and REIKOU sends Garchomp. Grimmsnarl announces Spirit Break; a not-very-effective notice names Gholdengo, then Special Attack decreases and healing messages appear.

**Ending participants / field limits.** Grimmsnarl + Archaludon versus Gholdengo + Garchomp. Exact boundary HP, status and unrevealed abilities/items remain unknown unless a linked frame/receipt supplies them.

**Recognition audit.** The 224.50 automatic cycle boundary interrupts this action sequence. Do not infer exact damage or targets from ordering alone.

### Diagnostic provisional turn 3 — 292.01–400.50s

**Starting participants (provisional).** Grimmsnarl + Archaludon versus Gholdengo + Garchomp.

**Chronological account.** Opponent Garchomp Mega-Evolution announcement. Grimmsnarl announces Parting Shot; opponent Garchomp Attack/Special Attack fall. Grimmsnarl returns; Pelipper enters; rain starts. Opponent Garchomp announces Earth Power; Archaludon Defense rises. Gholdengo announces Shadow Ball; Archaludon faints. Hoshi sends Garchomp as replacement.

**Ending participants / field limits.** Pelipper + Garchomp versus Gholdengo + transformed Garchomp. Exact boundary HP, status and unrevealed abilities/items remain unknown unless a linked frame/receipt supplies them.

**Recognition audit.** Replacement selection after the faint is not independently proven to start a new turn; baseline 375.35 split is suspect. Item/form suffix and mechanical effects are not inferred.

### Diagnostic provisional turn 4 — 400.50–476.01s

**Starting participants (provisional).** Pelipper + Garchomp versus Gholdengo + transformed Garchomp.

**Chronological account.** REIKOU withdraws Gholdengo and sends Rillaboom. A player Garchomp transformation announcement appears. Opponent Garchomp announces Protect, then its defensive stance; player Garchomp announces Protect and its stance. Pelipper announces Tailwind; a side-condition start sentence follows. Rillaboom receives a healing notice.

**Ending participants / field limits.** Pelipper + transformed Garchomp versus Rillaboom + transformed Garchomp. Exact boundary HP, status and unrevealed abilities/items remain unknown unless a linked frame/receipt supplies them.

**Recognition audit.** Player transformation and opponent Protect execution are missed in baseline; a later stance effect is not equivalent to recovered executed-move membership.

### Diagnostic provisional turn 5 — 476.01–546.51s

**Starting participants (provisional).** Pelipper + Garchomp versus Rillaboom + Garchomp.

**Chronological account.** Hoshi withdraws Garchomp and sends Grimmsnarl. REIKOU withdraws Garchomp and sends Incineroar. Player pair Attack falls. Rillaboom announces Fake Out. Pelipper announces Hurricane; effectiveness and Rillaboom fainting notices follow. Grimmsnarl heals; grass disappears. REIKOU sends Garchomp as replacement.

**Ending participants / field limits.** Pelipper + Grimmsnarl versus Incineroar + Garchomp. Exact boundary HP, status and unrevealed abilities/items remain unknown unless a linked frame/receipt supplies them.

**Recognition audit.** Hurricane, withdrawals, Attack drop, healing and terrain-end messages have baseline coverage/semantic losses. No exact target or damage is backfilled into earlier state.

### Diagnostic provisional turn 6 — 546.51–592.50s

**Starting participants (provisional).** Pelipper + Grimmsnarl versus Incineroar + Garchomp.

**Chronological account.** Opponent Incineroar announces Fake Out; opponent Garchomp announces Power Gem. A super-effective notice names Pelipper. Pelipper announces Weather Ball; a later super-effective notice names Incineroar. Grimmsnarl flinches and cannot act.

**Ending participants / field limits.** Same displayed participants; HP is a per-frame observation, not inferred from animations. Exact boundary HP, status and unrevealed abilities/items remain unknown unless a linked frame/receipt supplies them.

**Recognition audit.** These readable messages were not scheduled by the frozen UI path. Sampled waiting/menu intervals surround the actions; no hidden selected move is invented for Grimmsnarl.

### Diagnostic provisional turn 7 — 592.50–684.51s

**Starting participants (provisional).** Pelipper + Grimmsnarl versus Incineroar + Garchomp.

**Chronological account.** REIKOU withdraws Incineroar and sends Gholdengo. Opponent Garchomp announces Power Gem; a super-effective notice names Pelipper. Pelipper announces Weather Ball. Gholdengo faints. Grimmsnarl announces Spirit Break; opponent Garchomp is named in effectiveness and Special Attack-drop notices. Rain stops and player Tailwind stops. REIKOU sends Incineroar; player pair Attack falls.

**Ending participants / field limits.** Pelipper + Grimmsnarl versus Garchomp + Incineroar. Exact boundary HP, status and unrevealed abilities/items remain unknown unless a linked frame/receipt supplies them.

**Recognition audit.** 592.50 is a provisional boundary around a new selection phase, not an exact action time. Baseline merges this with the previous cycle and misses the Gholdengo faint and multiple moves/effects.

### Diagnostic provisional turn 8 — 684.51–753.75s

**Starting participants (provisional).** Pelipper + Grimmsnarl versus Garchomp + Incineroar.

**Chronological account.** Incineroar announces Fake Out, then Garchomp Power Gem. A super-effective notice names Pelipper. Pelipper announces Tailwind; Grimmsnarl flinches. Player Light Screen disappears. A side-unspecified surrender sentence and a victory-over-REIKOU sentence appear. The 750s screen reads Hoshi WIN / REIKOU LOSE; device controls cover the final frame.

**Ending participants / field limits.** Result-screen proposal: Hoshi won; the generic surrender sentence itself does not name the surrendering side. Remaining HP, individual persistence and exact duration counters need review. Exact boundary HP, status and unrevealed abilities/items remain unknown unless a linked frame/receipt supplies them.

**Recognition audit.** Two late Tailwind candidates appear to split one continuous visible announcement. End-result and expiry semantics were not extracted. Independent human verification remains absent.

### Concrete diagnostic failures and state conflicts

Visible live messages at 451, 520, 567, 578, 637, 646 and 652 seconds are classified as occluded by status_overlay in the frozen UI path. The 300s move description is also routed as status_overlay. This is a region-classification/admission-coverage failure; no new OCR was needed to see it.

Seven additional move-announcement examples are identified visually (451, 520, 567, 571, 578, 637 and 646 seconds). These are **agent diagnostic examples, not an independent recall denominator**. The same scan exposes missed player transformation, withdrawals, Gholdengo fainting and several condition transitions. It is not an exhaustive independent census of all omissions.

The final baseline projection still marks grassy terrain and rain active despite readable ending messages at approximately 535.023s and 665.512s. Tailwind stop/restart and Light Screen expiration also lack supported transition handling. The engine states printed below are preserved program outputs with these diagnostic conflicts; they must not be treated as verified current battle states.

A continuously visible late Pelipper Tailwind announcement spans a frame the selector rejects between two automatic occurrence groups (733.007/734.023s). This is a suspected duplicate split; zero duplicate stable IDs does not establish zero duplicated real actions.

| Observed at | Agent visual reading | Baseline / interpretation |
|---|---|---|
| 300.000s | Large selected-move description: 大声咆哮; power 55, accuracy 95, lowers opponents’ special attack by 1 stage. Available choice, not execution. | move_description_overlay; selected=False, overlay=status_overlay. Move-description panel is visibly present; inspect the frozen region classification. |
| 449.008s | 烈咬陆鲨超级进化成了／超级烈咬陆鲨！ | missed_transformation; selected=False, overlay=status_overlay. Unprefixed Garchomp transformation; player association is provisional using preceding entry and Hoshi reaction evidence, not merely absence of 对手 or 3D position. |
| 451.010s | 对手的烈咬陆鲨使出了／守住！ | missed_move; selected=False, overlay=status_overlay. Opponent Protect announcement missed; a later defensive-stance effect was recognized. |
| 459.010s | 烈咬陆鲨／摆出了防守的架势！ | missed_effect; selected=False, overlay=status_overlay. Defensive stance observation; do not infer immunity to all later attacks. |
| 469.012s | 对手的轰擂金刚猩的／体力回复了！ | missed_healing; selected=False, overlay=status_overlay. Healing notice only; amount and cause not supplied. |
| 500.002s | 烈咬陆鲨，／回来！ | missed_withdrawal; selected=False, overlay=status_overlay. Player withdrawal; later Grimmsnarl arrival is separate evidence. |
| 507.018s | REIKOU换下了／烈咬陆鲨！ | missed_withdrawal; selected=False, overlay=status_overlay. Opponent withdrawal; do not infer a faint. |
| 514.003s | 大嘴鸥和长毛巨魔的／攻击降低了！ | missed_stat_change; selected=False, overlay=status_overlay. Names and direction are visible; no ability attribution from this sentence alone. |
| 520.022s | 大嘴鸥使出了／暴风！ | missed_move; selected=False, overlay=status_overlay. Pelipper Hurricane announcement; target not stated in this sentence. |
| 533.007s | 长毛巨魔的／体力回复了！ | missed_healing; selected=False, overlay=status_overlay. Amount/cause unknown. |
| 535.023s | 脚下的青草消失不见了！ | missed_condition_end; selected=False, overlay=status_overlay. Terrain-ending evidence; no unobserved earlier expiration time inferred. |
| 567.028s | 对手的炽焰咆哮虎使出了／击掌奇袭！ | missed_move; selected=False, overlay=status_overlay. Opponent Incineroar Fake Out; target not stated. |
| 571.030s | 对手的烈咬陆鲨使出了／力量宝石！ | missed_move; selected=False, overlay=status_overlay. Opponent Garchomp Power Gem; no earlier target backfill. |
| 575.030s | 对大嘴鸥／效果绝佳！ | missed_effectiveness; selected=False, overlay=status_overlay. Effectiveness receiver Pelipper is visible here; association with preceding move remains provisional. |
| 578.030s | 大嘴鸥使出了／气象球！ | missed_move; selected=False, overlay=status_overlay. Pelipper Weather Ball; no type/power/target assumption. |
| 584.032s | 对对手的炽焰咆哮虎／效果绝佳！ | missed_effectiveness; selected=False, overlay=status_overlay. Effectiveness receiver observed after the move; no exact damage supplied. |
| 589.015s | 长毛巨魔／畏缩了，无法使出招式！ | missed_flinch; selected=False, overlay=status_overlay. No execution or unobserved selected move is invented. |
| 631.007s | REIKOU换下了／炽焰咆哮虎！ | missed_withdrawal; selected=False, overlay=status_overlay. Opponent withdrawal, not a faint. |
| 637.007s | 对手的烈咬陆鲨使出了／力量宝石！ | missed_move; selected=False, overlay=status_overlay. A later separate Power Gem announcement; not merged with 571s. |
| 641.008s | 对大嘴鸥／效果绝佳！ | missed_effectiveness; selected=False, overlay=status_overlay. Receiver observed at this timestamp, no earlier target backfill. |
| 646.008s | 大嘴鸥使出了／气象球！ | missed_move; selected=False, overlay=status_overlay. A later separate Weather Ball announcement. |
| 652.010s | 对手的赛富豪倒下了！ | missed_faint; selected=False, overlay=status_overlay. Gholdengo fainting notice is readable; damage cause is not asserted from this sentence. |
| 661.012s | 对对手的烈咬陆鲨／效果绝佳！ | missed_effectiveness; selected=False, overlay=status_overlay. Receiver observed after the 656s Spirit Break candidate. |
| 663.012s | 对手的烈咬陆鲨的／特攻降低了！ | missed_stat_change; selected=False, overlay=status_overlay. Direction observed; magnitude not stated. |
| 665.512s | 雨停了！ | unsupported_condition_end; selected=True, overlay=None. Frozen OCR selected the message but parser did not support its semantics. |
| 667.012s | 我方的顺风停止了！ | unsupported_condition_end; selected=True, overlay=None. Frozen OCR selected the message but parser did not support its semantics. |
| 733.523s | 大嘴鸥使出了／顺风！ | suspected_duplicate; selected=False, overlay=None. Text remains visible between the 733.007 and 734.023 automatic groups, but selection is false on this intervening frame. Suspected one visible occurrence split into two; real execution denominator remains unreviewed. |
| 740.525s | 我方的光墙消失了！ | unsupported_condition_end; selected=True, overlay=None. Frozen OCR selected the text, but condition-end semantics are unsupported. |
| 743.508s | 有一方选择了投降。 | unsupported_result; selected=True, overlay=None. The sentence does not identify which side surrendered. |
| 745.508s | 战胜了／REIKOU！ | unsupported_result; selected=True, overlay=None. Readable result text remained an unknown candidate. |
| 750.010s | Hoshi — WIN; REIKOU — LOSE | result_screen; selected=False, overlay=None. Direct same-frame visual reading; baseline StateEngine did not extract a winner. Independent review pending. |
| 473.030s | 回合4; historical rows include Gholdengo withdrawal, Rillaboom entry, player Garchomp transformation and opponent Garchomp Protect. | historical_battle_log; selected=False, overlay=battle_log_overlay. Explicit selected historical turn heading supports the fourth provisional action group; log-opening timestamp is not the original event time or necessarily the current command turn. |

All diagnostic records retain source PTS timestamps, frame hashes and image references in the JSON and offline viewer. They are not inserted into recognizer dictionaries, raw baseline outputs, StateEngine history, frozen labels or human annotations.


Player roster/name/item OCR and all independent icon scores remain in the technical appendix and per-frame viewer. Nicknames are not translated into species by lookup guesses. Stable individual identity and re-entry are only those admitted by existing receipts. Canonical naming does not establish Champions learnability, an equipped move slot or a usage probability; no new legality assumptions or external knowledge imports are introduced.

## Full chronological account

Quoted text is raw automatic OCR, including errors. A canonical event below is a program proposal with its admission receipt, not a verified action. Unknown targets, outcomes, damage causes and end-of-turn order stay unknown. Starting and ending states are chronological prefixes; later evidence is never backdated.

### Opening / turn unresolved — 0.000–134.673s

Boundary: unresolved; opening / no proven turn boundary.

**Starting state.** Player: active identities/slots unknown. Opponent: active identities/slots unknown. Field: unknown in admitted state. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: none admitted at this prefix.

**Chronological observations.**

- 0.000–0.000s: “你知 / 各种排” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:4c8f504b01bce00ea58fb331).
- 0.500–0.500s: “你知道对战数 / 可以确认各种排” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:ccf10fd7764706f51de03777).
- 13.335–13.335s: “对战队伍后来匹配 / 7” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:984cfe78c4bddae0e14ec663).
- 123.020–124.505s: “REIKOU派出了赛富豪 / 和炽焰咆哮虎！” — `send_out`. entry_observation: recorded_observation; move unknown; actor unknown; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.); send_out: deferred; move unknown; actor 赛富豪; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:5e5dfd771233173012cc8fdc).
- 126.672–128.005s: “上吧！长毛巨魔！ / 铝钢桥龙！” — `send_out`. entry_observation: recorded_observation; move unknown; actor unknown; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.); send_out: recorded_observation; move unknown; actor 铝钢桥龙; target unknown (Only named identity is supported; placement and biological continuity are not established.); send_out: recorded_observation; move unknown; actor 长毛巨魔; target unknown (Only named identity is supported; placement and biological continuity are not established.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:996dd9393e72196ed4aad7d2).
- 130.505–132.005s: “长毛巨魔和铝钢桥龙的 / 攻击降低了！” — `stat_change`. stat_change: deferred; move unknown; actor 长毛巨魔; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:361078f311f4b062bd83def5).
- 134.007s HUD `opponent_active_1`: automatic name reading “炽焰咆哮虎”; automatic HP 100; resolved species pokeapi:species:727. This is display evidence, not proof of damage cause or persistent instance.
- 134.007s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 100; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 134.007s HUD `own_active_1`: automatic name reading “长毛巨魔”; automatic HP {'current': 201, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 134.007s HUD `own_active_2`: automatic name reading “铝钢桥龙”; automatic HP {'current': 194, 'maximum': 194}; resolved species pokeapi:species:1018. This is display evidence, not proof of damage cause or persistent instance.

Literal field-header OCR (not a trigger/duration deduction): 1.500s: 0 1; 13.002s: 80088 1; 78.513s: 1 X; 104.018s: 1 7; 109.518s: X X; 117.020s: X 1; 127.505s: BO .

**Ending engine projection (unverified).** Player: right: 铝钢桥龙 (sample_battle_6:self:entry:abf2a156ef338a18), last observed 194/194; status unknown; ability unknown; item unknown; left: 长毛巨魔 (sample_battle_6:self:entry:e80692fa2a8bba41), last observed 201/201; status unknown; ability unknown; item unknown. Opponent: active identities/slots unknown. Field: unknown in admitted state. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: none admitted at this prefix.

**Recognition audit.** 6 message candidates; 5 without an admitted semantic conclusion. Correct, incorrect and missed-event counts are unmeasured (0 independently reviewed). UI, HP observations, unresolved reads and coverage cards are inspectable in the viewer.

### Baseline provisional cycle 1 — 134.673–174.530s

Boundary: provisional; first observed command menu.

**Starting state.** Player: right: 铝钢桥龙 (sample_battle_6:self:entry:abf2a156ef338a18), last observed 194/194; status unknown; ability unknown; item unknown; left: 长毛巨魔 (sample_battle_6:self:entry:e80692fa2a8bba41), last observed 201/201; status unknown; ability unknown; item unknown. Opponent: active identities/slots unknown. Field: unknown in admitted state. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: none admitted at this prefix.

**Chronological observations.**

- 138.023s HUD `own_active_2`: automatic name reading “”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 139.023s HUD `own_active_2`: automatic name reading “铝钢桥龙”; automatic HP {'current': 194, 'maximum': 194}; resolved species pokeapi:species:1018. This is display evidence, not proof of damage cause or persistent instance.
- 140.357s HUD `own_active_2`: automatic name reading “”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 140.690s HUD `own_active_2`: automatic name reading “铝钢桥龙”; automatic HP {'current': 194, 'maximum': 194}; resolved species pokeapi:species:1018. This is display evidence, not proof of damage cause or persistent instance.
- 158.010s HUD `opponent_active_1`: automatic name reading “炽焰咆哮虎”; automatic HP 100; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 160.677s HUD `opponent_active_1`: automatic name reading “炽焰咆哮虎”; automatic HP 100; resolved species pokeapi:species:727. This is display evidence, not proof of damage cause or persistent instance.
- 162.510–164.012s: “REIKOU换下了 / 炽焰咆哮虎！” — `switch_out`. switch_out: deferred; move unknown; actor 炽焰咆哮虎; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:58817e49b49a317026e6b6b8).
- 166.012–167.012s: “REIKOU / 派出了轰擂金刚猩！” — `send_out`. entry_observation: recorded_observation; move unknown; actor unknown; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.); send_out: deferred; move unknown; actor 轰擂金刚猩; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:72ae0483db0970cad972126f).
- 170.512–171.512s: “脚下青草如茵！” — `terrain_change`. terrain_change: applied_candidate; move unknown; actor unknown; target unknown (The supported observation passed the existing state policy.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:40f3ca44de0333b5efe2dc1b).
- 172.512–173.513s: “长毛巨魔使出了 / 光墙!” — `move_execution`. move_execution: applied_partial; move 光墙; actor 长毛巨魔; target unknown (Actor and executed move were supported. Targets and move effects were not established.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:7c4e8c9b29e3182e0d89080c).

Literal field-header OCR (not a trigger/duration deduction): 154.343s: Crand ; 173.012s: 222000 1.

**Ending engine projection (unverified).** Player: right: 铝钢桥龙 (sample_battle_6:self:entry:abf2a156ef338a18), last observed 194/194; status unknown; ability unknown; item unknown; left: 长毛巨魔 (sample_battle_6:self:entry:e80692fa2a8bba41), last observed 201/201; status unknown; ability unknown; item unknown. Opponent: left: 炽焰咆哮虎 (sample_battle_6:opponent:hud:823b27e8970dcf18fcda90d8), last observed 100%; status unknown; ability unknown; item unknown; right: 赛富豪 (sample_battle_6:opponent:hud:a1cec7374153d652ccaa6f24), last observed 100%; status unknown; ability unknown; item unknown. Field: terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: sample_battle_6:self:entry:e80692fa2a8bba41: 光墙.

**Recognition audit.** 4 message candidates; 2 without an admitted semantic conclusion. Correct, incorrect and missed-event counts are unmeasured (0 independently reviewed). UI, HP observations, unresolved reads and coverage cards are inspectable in the viewer.

### Baseline provisional cycle 2 — 174.530–181.513s

Boundary: provisional; command menu observed after live-message interval.

**Starting state.** Player: right: 铝钢桥龙 (sample_battle_6:self:entry:abf2a156ef338a18), last observed 194/194; status unknown; ability unknown; item unknown; left: 长毛巨魔 (sample_battle_6:self:entry:e80692fa2a8bba41), last observed 201/201; status unknown; ability unknown; item unknown. Opponent: left: 炽焰咆哮虎 (sample_battle_6:opponent:hud:823b27e8970dcf18fcda90d8), last observed 100%; status unknown; ability unknown; item unknown; right: 赛富豪 (sample_battle_6:opponent:hud:a1cec7374153d652ccaa6f24), last observed 100%; status unknown; ability unknown; item unknown. Field: terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: sample_battle_6:self:entry:e80692fa2a8bba41: 光墙.

**Chronological observations.**

- 176.513–178.013s: “光墙使我方的 / 特殊抗性提高了！” — `stat_change`. stat_change: deferred; move unknown; actor unknown; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:5b9c82e7b2123ae4d5a1cdea).
- 179.013–180.030s: “对手的赛富豪使出了 / 诡计！” — `move_execution`. move_execution: deferred; move 诡计; actor 赛富豪; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:ec6faae24e88e490d75fa2e9).

Literal field-header OCR (not a trigger/duration deduction): 179.013s: R 2.

**Ending engine projection (unverified).** Player: right: 铝钢桥龙 (sample_battle_6:self:entry:abf2a156ef338a18), last observed 194/194; status unknown; ability unknown; item unknown; left: 长毛巨魔 (sample_battle_6:self:entry:e80692fa2a8bba41), last observed 201/201; status unknown; ability unknown; item unknown. Opponent: left: 炽焰咆哮虎 (sample_battle_6:opponent:hud:823b27e8970dcf18fcda90d8), last observed 100%; status unknown; ability unknown; item unknown; right: 赛富豪 (sample_battle_6:opponent:hud:a1cec7374153d652ccaa6f24), last observed 100%; status unknown; ability unknown; item unknown. Field: terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: sample_battle_6:self:entry:e80692fa2a8bba41: 光墙.

**Recognition audit.** 2 message candidates; 2 without an admitted semantic conclusion. Correct, incorrect and missed-event counts are unmeasured (0 independently reviewed). UI, HP observations, unresolved reads and coverage cards are inspectable in the viewer.

### Baseline provisional cycle 3 — 181.513–203.668s

Boundary: provisional; command menu observed after live-message interval.

**Starting state.** Player: right: 铝钢桥龙 (sample_battle_6:self:entry:abf2a156ef338a18), last observed 194/194; status unknown; ability unknown; item unknown; left: 长毛巨魔 (sample_battle_6:self:entry:e80692fa2a8bba41), last observed 201/201; status unknown; ability unknown; item unknown. Opponent: left: 炽焰咆哮虎 (sample_battle_6:opponent:hud:823b27e8970dcf18fcda90d8), last observed 100%; status unknown; ability unknown; item unknown; right: 赛富豪 (sample_battle_6:opponent:hud:a1cec7374153d652ccaa6f24), last observed 100%; status unknown; ability unknown; item unknown. Field: terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: sample_battle_6:self:entry:e80692fa2a8bba41: 光墙.

**Chronological observations.**

- 183.532–184.532s: “对手的赛富豪的 / 特攻大幅提高了！” — `stat_change`. stat_change: deferred; move unknown; actor 赛富豪; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:ab29462f3ef5a9144a307c75).
- 186.032–187.032s: “铝钢桥龙使出了 / 大声咆哮！” — `move_execution`. move_execution: applied_partial; move 大声咆哮; actor 铝钢桥龙; target unknown (Actor and executed move were supported. Targets and move effects were not established.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:c70cad01dc163a8b1e7a7974).
- 187.032s HUD `opponent_active_1`: automatic name reading “”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 187.532s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP 97; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 187.532s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 95; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 188.032s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP 86; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 188.032s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 75; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 188.532s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 188.532s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 74; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 189.032s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP 85; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 189.532s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 190.032–191.015s: “对对手的赛富豪 / 效果绝佳！” — `effectiveness`. effectiveness: deferred; move unknown; actor unknown; target 赛富豪 (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:fb63b2e8be50c1a96528bab2).
- 190.032s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 191.532s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 192.032–194.500s: “对手的赛富豪和 / 对手的轰擂金刚猩的” — `stat_change`. stat_change: deferred; move unknown; actor 轰擂金刚猩; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:9e8120a23908be8616eb1ad3).
- 192.032s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 194.500s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 195.000s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 195.517s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 197.000s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 197.500–198.517s: “对手的赛富豪的 / 体力回复了！” — `move_effect`. move_effect: recorded_observation; move unknown; actor 赛富豪; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:0d819b2acd04230dc3c16207).
- 199.500s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP 88; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 201.000–202.333s: “对手的轰擂金刚猩的 / 体力回复了！” — `move_effect`. move_effect: recorded_observation; move unknown; actor 轰擂金刚猩; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:a88b3eb8f0beb5f7fe478c51).
- 203.002s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 203.002s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 80; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 203.352s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.

Literal field-header OCR (not a trigger/duration deduction): 186.532s: 7 7; 203.352s: 青草场地状态 4/5.

**Ending engine projection (unverified).** Player: right: 铝钢桥龙 (sample_battle_6:self:entry:abf2a156ef338a18), last observed 194/194; status unknown; ability unknown; item unknown; left: 长毛巨魔 (sample_battle_6:self:entry:e80692fa2a8bba41), last observed 201/201; status unknown; ability unknown; item unknown. Opponent: left: 炽焰咆哮虎 (sample_battle_6:opponent:hud:823b27e8970dcf18fcda90d8), last observed 100%; status unknown; ability unknown; item unknown; right: 赛富豪 (sample_battle_6:opponent:hud:a1cec7374153d652ccaa6f24), last observed 100%; status unknown; ability unknown; item unknown. Field: terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: sample_battle_6:self:entry:abf2a156ef338a18: 大声咆哮; sample_battle_6:self:entry:e80692fa2a8bba41: 光墙.

**Recognition audit.** 6 message candidates; 5 without an admitted semantic conclusion. Correct, incorrect and missed-event counts are unmeasured (0 independently reviewed). UI, HP observations, unresolved reads and coverage cards are inspectable in the viewer.

### Baseline provisional cycle 4 — 203.668–224.505s

Boundary: provisional; command menu observed after live-message interval.

**Starting state.** Player: right: 铝钢桥龙 (sample_battle_6:self:entry:abf2a156ef338a18), last observed 194/194; status unknown; ability unknown; item unknown; left: 长毛巨魔 (sample_battle_6:self:entry:e80692fa2a8bba41), last observed 201/201; status unknown; ability unknown; item unknown. Opponent: left: 炽焰咆哮虎 (sample_battle_6:opponent:hud:823b27e8970dcf18fcda90d8), last observed 100%; status unknown; ability unknown; item unknown; right: 赛富豪 (sample_battle_6:opponent:hud:a1cec7374153d652ccaa6f24), last observed 100%; status unknown; ability unknown; item unknown. Field: terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: sample_battle_6:self:entry:abf2a156ef338a18: 大声咆哮; sample_battle_6:self:entry:e80692fa2a8bba41: 光墙.

**Chronological observations.**

- 203.668s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 205.335s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 206.335s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 207.002s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 207.335s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 208.335s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 209.002s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 209.502s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 209.668s HUD `opponent_active_1`: automatic name reading “轰擂金刚”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 209.668s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 209.668s HUD `own_active_1`: automatic name reading “”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 209.668s HUD `own_active_2`: automatic name reading “”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 211.002s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 211.002s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 80; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 211.002s HUD `own_active_1`: automatic name reading “长毛巨魔”; automatic HP {'current': 201, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 211.002s HUD `own_active_2`: automatic name reading “铝钢桥龙”; automatic HP {'current': 194, 'maximum': 194}; resolved species pokeapi:species:1018. This is display evidence, not proof of damage cause or persistent instance.
- 211.335s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 213.020s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 213.520s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 215.003s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 215.503s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 217.003s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 217.503s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 219.003s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 219.503s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 220.670s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 221.337–222.503s: “对手的赛富豪使出了 / 暗影球！” — `move_execution`. move_execution: deferred; move 暗影球; actor 赛富豪; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:c1aae1609cd4b50a2e6a27b7).

Literal field-header OCR (not a trigger/duration deduction): 222.503s: 1 6.

**Ending engine projection (unverified).** Player: right: 铝钢桥龙 (sample_battle_6:self:entry:abf2a156ef338a18), last observed 194/194; status unknown; ability unknown; item unknown; left: 长毛巨魔 (sample_battle_6:self:entry:e80692fa2a8bba41), last observed 201/201; status unknown; ability unknown; item unknown. Opponent: left: 炽焰咆哮虎 (sample_battle_6:opponent:hud:823b27e8970dcf18fcda90d8), last observed 100%; status unknown; ability unknown; item unknown; right: 赛富豪 (sample_battle_6:opponent:hud:a1cec7374153d652ccaa6f24), last observed 80%; status unknown; ability unknown; item unknown. Field: terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: sample_battle_6:self:entry:abf2a156ef338a18: 大声咆哮; sample_battle_6:self:entry:e80692fa2a8bba41: 光墙.

**Recognition audit.** 1 message candidates; 1 without an admitted semantic conclusion. Correct, incorrect and missed-event counts are unmeasured (0 independently reviewed). UI, HP observations, unresolved reads and coverage cards are inspectable in the viewer.

### Baseline provisional cycle 5 — 224.505–292.015s

Boundary: provisional; command menu observed after live-message interval.

**Starting state.** Player: right: 铝钢桥龙 (sample_battle_6:self:entry:abf2a156ef338a18), last observed 194/194; status unknown; ability unknown; item unknown; left: 长毛巨魔 (sample_battle_6:self:entry:e80692fa2a8bba41), last observed 201/201; status unknown; ability unknown; item unknown. Opponent: left: 炽焰咆哮虎 (sample_battle_6:opponent:hud:823b27e8970dcf18fcda90d8), last observed 100%; status unknown; ability unknown; item unknown; right: 赛富豪 (sample_battle_6:opponent:hud:a1cec7374153d652ccaa6f24), last observed 80%; status unknown; ability unknown; item unknown. Field: terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: sample_battle_6:self:entry:abf2a156ef338a18: 大声咆哮; sample_battle_6:self:entry:e80692fa2a8bba41: 光墙.

**Chronological observations.**

- 224.505s HUD `own_active_2`: automatic name reading “铝钢桥龙”; automatic HP {'current': 171, 'maximum': 194}; resolved species pokeapi:species:1018. This is display evidence, not proof of damage cause or persistent instance.
- 225.005s HUD `own_active_2`: automatic name reading “铝钢桥龙”; automatic HP {'current': 88, 'maximum': 194}; resolved species pokeapi:species:1018. This is display evidence, not proof of damage cause or persistent instance.
- 225.505s HUD `own_active_2`: automatic name reading “铝钢桥龙”; automatic HP {'current': 86, 'maximum': 194}; resolved species pokeapi:species:1018. This is display evidence, not proof of damage cause or persistent instance.
- 226.505–228.005s: “铝钢桥龙的 / 防御提高了!” — `stat_change`. stat_change: applied_candidate; move unknown; actor 铝钢桥龙; target unknown (The supported observation passed the existing state policy.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:030fb9eef6496fd3c32035f1).
- 229.005s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 74; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 229.505s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 70; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 230.005s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 230.505–231.505s: “对手的赛富豪的生命 / 被少量削减了！” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:b6a901d39d3758b0f9b1331f).
- 233.007–234.007s: “铝钢桥龙使出了 / 大声咆哮！” — `move_execution`. move_execution: applied_partial; move 大声咆哮; actor 铝钢桥龙; target unknown (Actor and executed move were supported. Targets and move effects were not established.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:9d95738bc956e79dcf63a0ce).
- 234.507s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP 91; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 234.507s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 70; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 235.507s HUD `opponent_active_1`: automatic name reading “轰擂金刚猩”; automatic HP 78; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 235.507s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 43; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 237.007–238.007s: “对对手的赛富豪 / 效果绝佳！” — `effectiveness`. effectiveness: deferred; move unknown; actor unknown; target 赛富豪 (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:c5af2245538983c5e33c800c).
- 239.007–241.507s: “对手的轰擂金刚猩的” — `stat_change`. stat_change: deferred; move unknown; actor 轰擂金刚猩; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:ce91649da50b90b16fb3fd03).
- 243.508–244.508s: “对手的轰擂金刚猩使出了 / 急速折返！” — `move_execution`. move_execution: deferred; move 急速折返; actor 轰擂金刚猩; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:b2a3ac8b09731500f5df6a6f).
- 245.508s HUD `own_active_1`: automatic name reading “长毛巨魔”; automatic HP {'current': 173, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 246.008s HUD `own_active_1`: automatic name reading “长毛巨魔”; automatic HP {'current': 153, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 247.008s HUD `own_active_1`: automatic name reading “长毛巨魔”; automatic HP {'current': 153, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 247.508–248.508s: “对手的轰擂金刚猩 / 要回到REIKOU的身边了!” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:33fea82318067a10321d27f8).
- 247.508s HUD `own_active_1`: automatic name reading “长毛巨魔”; automatic HP {'current': 153, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 261.010–262.010s: “REIKOU / 派出了烈咬陆鲨！” — `send_out`. entry_observation: recorded_observation; move unknown; actor unknown; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.); send_out: deferred; move unknown; actor 烈咬陆鲨; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:00460cc2ec1864b70efa9eb4).
- 264.678s HUD `own_active_2`: automatic name reading “0”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 265.345–266.512s: “长毛巨魔使出了 / 灵魂冲击！” — `move_execution`. move_execution: applied_partial; move 灵魂冲击; actor 长毛巨魔; target unknown (Actor and executed move were supported. Targets and move effects were not established.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:3d23e9698c813fe686e5c65a).
- 267.512s HUD `opponent_active_1`: automatic name reading “人”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 268.012s HUD `opponent_active_2`: automatic name reading “S”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 268.362s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 40; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 268.678s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 34; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 269.345s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 32; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 270.678–272.012s: “对对手的赛富豪 / 效果不好” — `effectiveness`. effectiveness: deferred; move unknown; actor unknown; target 赛富豪 (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:20d0ad3449ce593b0f9f0841).
- 273.013–274.013s: “对手的赛富豪的 / 特攻降低了！” — `stat_change`. stat_change: deferred; move unknown; actor 赛富豪; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:daa8f830098af54d105cc388).
- 275.513s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 34; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 276.013s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 38; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 277.013–278.013s: “对手的赛富豪的 / 体力回复了！” — `move_effect`. move_effect: recorded_observation; move unknown; actor 赛富豪; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:7cc1745be78a25b34ffe160c).
- 279.013s HUD `own_active_2`: automatic name reading “铝钢桥龙”; automatic HP {'current': 90, 'maximum': 194}; resolved species pokeapi:species:1018. This is display evidence, not proof of damage cause or persistent instance.
- 279.513s HUD `own_active_2`: automatic name reading “铝钢桥龙”; automatic HP {'current': 98, 'maximum': 194}; resolved species pokeapi:species:1018. This is display evidence, not proof of damage cause or persistent instance.
- 280.513–281.513s: “铝钢桥龙的 / 体力回复了！” — `move_effect`. move_effect: recorded_observation; move unknown; actor 铝钢桥龙; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:23486360cf90fff1fd173a98).
- 282.515s HUD `own_active_1`: automatic name reading “长毛巨魔”; automatic HP {'current': 157, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 284.015–285.015s: “长毛巨魔的 / 体力回复了！” — `move_effect`. move_effect: recorded_observation; move unknown; actor 长毛巨魔; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:c909395e84fb68f2449844d6).
- 288.515s HUD `own_active_2`: automatic name reading “铝钢桥龙”; automatic HP {'current': 99, 'maximum': 194}; resolved species pokeapi:species:1018. This is display evidence, not proof of damage cause or persistent instance.
- 289.015s HUD `own_active_2`: automatic name reading “铝钢桥龙”; automatic HP {'current': 109, 'maximum': 194}; resolved species pokeapi:species:1018. This is display evidence, not proof of damage cause or persistent instance.
- 289.682s HUD `own_active_2`: automatic name reading “铝钢桥龙”; automatic HP {'current': 110, 'maximum': 194}; resolved species pokeapi:species:1018. This is display evidence, not proof of damage cause or persistent instance.
- 290.515s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 290.515s HUD `own_active_1`: automatic name reading “长毛巨魔”; automatic HP {'current': 165, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 291.348s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.

Literal field-header OCR (not a trigger/duration deduction): 244.508s: 00 2; 266.512s: ORL °; 290.682s: 青草场地状态 3/5.

**Ending engine projection (unverified).** Player: right: 铝钢桥龙 (sample_battle_6:self:entry:abf2a156ef338a18), last observed 110/194; status unknown; ability unknown; item unknown; left: 长毛巨魔 (sample_battle_6:self:entry:e80692fa2a8bba41), last observed 165/201; status unknown; ability unknown; item unknown. Opponent: left: 炽焰咆哮虎 (sample_battle_6:opponent:hud:823b27e8970dcf18fcda90d8), last observed 100%; status unknown; ability unknown; item unknown; right: 赛富豪 (sample_battle_6:opponent:hud:a1cec7374153d652ccaa6f24), last observed 38%; status unknown; ability unknown; item unknown. Field: terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: sample_battle_6:self:entry:abf2a156ef338a18: 大声咆哮, 大声咆哮; sample_battle_6:self:entry:e80692fa2a8bba41: 光墙, 灵魂冲击.

**Recognition audit.** 14 message candidates; 11 without an admitted semantic conclusion. Correct, incorrect and missed-event counts are unmeasured (0 independently reviewed). UI, HP observations, unresolved reads and coverage cards are inspectable in the viewer.

### Baseline provisional cycle 6 — 292.015–375.347s

Boundary: provisional; command menu observed after live-message interval.

**Starting state.** Player: right: 铝钢桥龙 (sample_battle_6:self:entry:abf2a156ef338a18), last observed 110/194; status unknown; ability unknown; item unknown; left: 长毛巨魔 (sample_battle_6:self:entry:e80692fa2a8bba41), last observed 165/201; status unknown; ability unknown; item unknown. Opponent: left: 炽焰咆哮虎 (sample_battle_6:opponent:hud:823b27e8970dcf18fcda90d8), last observed 100%; status unknown; ability unknown; item unknown; right: 赛富豪 (sample_battle_6:opponent:hud:a1cec7374153d652ccaa6f24), last observed 38%; status unknown; ability unknown; item unknown. Field: terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: sample_battle_6:self:entry:abf2a156ef338a18: 大声咆哮, 大声咆哮; sample_battle_6:self:entry:e80692fa2a8bba41: 光墙, 灵魂冲击.

**Chronological observations.**

- 295.000s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 297.667s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 300.500s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 312.670s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 312.670s HUD `own_active_2`: automatic name reading “铝钢桥龙”; automatic HP None; resolved species pokeapi:species:1018. This is display evidence, not proof of damage cause or persistent instance.
- 313.337s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 313.337s HUD `own_active_2`: automatic name reading “铝钢桥龙”; automatic HP {'current': 110, 'maximum': 194}; resolved species pokeapi:species:1018. This is display evidence, not proof of damage cause or persistent instance.
- 314.003s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 316.670s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 317.670s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 319.003–320.003s: “对手的烈咬陆鲨的烈咬陆鲨进化石Z和 / REIKOU的全一环起了反应！” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:088365764ec7da3b8f45389e).
- 328.505–329.505s: “对手的烈咬陆鲨超级进化成了 / 超级烈咬陆鲨！” — `alias_observation`. alias_observation: recorded_observation; move unknown; actor unknown; target unknown (Only named identity is supported; placement and biological continuity are not established.); transformation: applied_candidate; move unknown; actor 超级烈咬陆鲨; target unknown (The supported observation passed the existing state policy.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:fc6bf0d26c2d00fe0a174251).
- 330.505–331.505s: “长毛巨魔使出了 / 抛下狠话！” — `move_execution`. move_execution: applied_partial; move 抛下狠话; actor 长毛巨魔; target unknown (Actor and executed move were supported. Targets and move effects were not established.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:13a53d025b6c17d897cf73ba).
- 333.507–335.007s: “对手的烈咬陆鲨的 / 攻击、特攻降低了！” — `stat_change`. stat_change: applied_candidate; move unknown; actor 超级烈咬陆鲨; target unknown (The supported observation passed the existing state policy.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:e10c6da864647e5ab56f8258).
- 335.507–336.507s: “长毛巨魔 / 要回到Hoshi的身边了!” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:cc460969a7f9a79a0998b25f).
- 337.007s HUD `own_active_2`: automatic name reading “H”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 355.510–356.510s: “上吧！大嘴鸥！” — `send_out`. entry_observation: recorded_observation; move unknown; actor unknown; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.); send_out: recorded_observation; move unknown; actor 大嘴鸥; target unknown (Only named identity is supported; placement and biological continuity are not established.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:c952f6d7b2de0d4610c6464c).
- 360.010–360.010s: “开始下雨了！” — `weather_change`. weather_change: applied_candidate; move unknown; actor unknown; target unknown (The supported observation passed the existing state policy.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:c00e5b7323996fcc54dad089).
- 363.345–363.345s: “对手的烈咬陆鲨使出了 / 大地之力!” — `move_execution`. move_execution: applied_partial; move 大地之力; actor 超级烈咬陆鲨; target unknown (Actor and executed move were supported. Targets and move effects were not established.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:785b8dc4332c42ad69839e73).
- 364.345s HUD `own_active_2`: automatic name reading “铝钢桥龙”; automatic HP {'current': 93, 'maximum': 194}; resolved species pokeapi:species:1018. This is display evidence, not proof of damage cause or persistent instance.
- 366.012s HUD `own_active_2`: automatic name reading “铝钢桥龙”; automatic HP {'current': 46, 'maximum': 194}; resolved species pokeapi:species:1018. This is display evidence, not proof of damage cause or persistent instance.
- 369.678–370.012s: “铝钢桥龙的 / 防御提高了！” — `stat_change`. stat_change: deferred; move unknown; actor 铝钢桥龙; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:e130d5fa32bb96f84c35c0ac).
- 372.680–373.013s: “对手的赛富豪使出了 / 暗影球！” — `move_execution`. move_execution: deferred; move 暗影球; actor 赛富豪; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:d1c0f54474c86a3dfd45c1fe).

Literal field-header OCR (not a trigger/duration deduction): 297.333s: 青草场地状态 3/5; 309.502s: 光墙状态 6/8; 331.505s: 心 正; 356.010s: 8 X.

**Ending engine projection (unverified).** Player: right: 铝钢桥龙 (sample_battle_6:self:entry:abf2a156ef338a18), last observed 46/194; status unknown; ability unknown; item unknown; left: 长毛巨魔 (sample_battle_6:self:entry:e80692fa2a8bba41), last observed 165/201; status unknown; ability 恶作剧之心; item 光之黏土. Opponent: left: 烈咬陆鲨 (sample_battle_6:opponent:hud:4c42039a31c041de3ce2f5e3), last observed 100%; status unknown; ability unknown; item unknown; right: 赛富豪 (sample_battle_6:opponent:hud:a1cec7374153d652ccaa6f24), last observed 38%; status unknown; ability unknown; item unknown. Field: weather: rain active=True; terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: sample_battle_6:self:entry:abf2a156ef338a18: 大声咆哮, 大声咆哮; sample_battle_6:self:entry:e80692fa2a8bba41: 光墙, 灵魂冲击, 抛下狠话; sample_battle_6:opponent:alias:936803684f7d70f904f25c15: 大地之力.

**Recognition audit.** 10 message candidates; 4 without an admitted semantic conclusion. Correct, incorrect and missed-event counts are unmeasured (0 independently reviewed). UI, HP observations, unresolved reads and coverage cards are inspectable in the viewer.

### Baseline provisional cycle 7 — 375.347–400.500s

Boundary: provisional; command menu observed after live-message interval.

**Starting state.** Player: right: 铝钢桥龙 (sample_battle_6:self:entry:abf2a156ef338a18), last observed 46/194; status unknown; ability unknown; item unknown; left: 长毛巨魔 (sample_battle_6:self:entry:e80692fa2a8bba41), last observed 165/201; status unknown; ability 恶作剧之心; item 光之黏土. Opponent: left: 烈咬陆鲨 (sample_battle_6:opponent:hud:4c42039a31c041de3ce2f5e3), last observed 100%; status unknown; ability unknown; item unknown; right: 赛富豪 (sample_battle_6:opponent:hud:a1cec7374153d652ccaa6f24), last observed 38%; status unknown; ability unknown; item unknown. Field: weather: rain active=True; terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: sample_battle_6:self:entry:abf2a156ef338a18: 大声咆哮, 大声咆哮; sample_battle_6:self:entry:e80692fa2a8bba41: 光墙, 灵魂冲击, 抛下狠话; sample_battle_6:opponent:alias:936803684f7d70f904f25c15: 大地之力.

**Chronological observations.**

- 375.513s HUD `own_active_2`: automatic name reading “铝钢桥龙”; automatic HP {'current': 34, 'maximum': 194}; resolved species pokeapi:species:1018. This is display evidence, not proof of damage cause or persistent instance.
- 377.680–378.347s: “铝钢桥龙倒下了！” — `faint`. faint: deferred; move unknown; actor 铝钢桥龙; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:fbc3c0b843e4df8391ff2789).
- 379.013–379.013s: “ / 4” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:116de005861639e87bb9ca88).
- 380.013–380.013s: “H / ” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:a8cef1dce8951cf3a688a17e).
- 380.513–380.513s: “之 / RA” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:29f1712a5766f2bcc41b3552).
- 380.680–380.680s: “我 / EA” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:c2ad5cc06d12425a74b716b4).
- 384.698s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 29; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 392.667–394.000s: “上吧！烈咬陆鲨！” — `send_out`. entry_observation: recorded_observation; move unknown; actor unknown; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.); send_out: recorded_observation; move unknown; actor 超级烈咬陆鲨; target unknown (Only named identity is supported; placement and biological continuity are not established.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:2f2e7a305beebb230af98ce7).
- 396.333s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:form:10534. This is display evidence, not proof of damage cause or persistent instance.
- 396.333s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 35; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 396.333s HUD `own_active_1`: automatic name reading “大嘴鸥”; automatic HP {'current': 164, 'maximum': 164}; resolved species pokeapi:species:279. This is display evidence, not proof of damage cause or persistent instance.
- 396.333s HUD `own_active_2`: automatic name reading “烈咬陆鲨”; automatic HP {'current': 184, 'maximum': 184}; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 400.000s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 400.000s HUD `opponent_active_2`: automatic name reading “”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 400.000s HUD `own_active_1`: automatic name reading “鸡”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 400.000s HUD `own_active_2`: automatic name reading “击鲨”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.

Literal field-header OCR (not a trigger/duration deduction): 392.667s: 8 X; 400.000s: 青草场地状态 2/5.

**Ending engine projection (unverified).** Player: right: 烈咬陆鲨 (sample_battle_6:self:entry:85531db5ddf5cbd5), last observed 184/184; status unknown; ability unknown; item unknown; left: 大嘴鸥 (sample_battle_6:self:entry:74c9c18234ef7d5a), last observed 164/164; status unknown; ability 降雨; item 文柚果. Opponent: left: 烈咬陆鲨 (sample_battle_6:opponent:hud:4c42039a31c041de3ce2f5e3), last observed 100%; status unknown; ability unknown; item unknown; right: 赛富豪 (sample_battle_6:opponent:hud:a1cec7374153d652ccaa6f24), last observed 38%; status unknown; ability unknown; item unknown. Field: weather: rain active=True; terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: sample_battle_6:self:entry:abf2a156ef338a18: 大声咆哮, 大声咆哮; sample_battle_6:self:entry:e80692fa2a8bba41: 光墙, 灵魂冲击, 抛下狠话; sample_battle_6:opponent:alias:936803684f7d70f904f25c15: 大地之力.

**Recognition audit.** 6 message candidates; 5 without an admitted semantic conclusion. Correct, incorrect and missed-event counts are unmeasured (0 independently reviewed). UI, HP observations, unresolved reads and coverage cards are inspectable in the viewer.

### Baseline provisional cycle 8 — 400.500–476.013s

Boundary: provisional; command menu observed after live-message interval.

**Starting state.** Player: right: 烈咬陆鲨 (sample_battle_6:self:entry:85531db5ddf5cbd5), last observed 184/184; status unknown; ability unknown; item unknown; left: 大嘴鸥 (sample_battle_6:self:entry:74c9c18234ef7d5a), last observed 164/164; status unknown; ability 降雨; item 文柚果. Opponent: left: 烈咬陆鲨 (sample_battle_6:opponent:hud:4c42039a31c041de3ce2f5e3), last observed 100%; status unknown; ability unknown; item unknown; right: 赛富豪 (sample_battle_6:opponent:hud:a1cec7374153d652ccaa6f24), last observed 38%; status unknown; ability unknown; item unknown. Field: weather: rain active=True; terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: sample_battle_6:self:entry:abf2a156ef338a18: 大声咆哮, 大声咆哮; sample_battle_6:self:entry:e80692fa2a8bba41: 光墙, 灵魂冲击, 抛下狠话; sample_battle_6:opponent:alias:936803684f7d70f904f25c15: 大地之力.

**Chronological observations.**

- 400.500s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 400.500s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 35; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 400.500s HUD `own_active_1`: automatic name reading “大嘴鸥”; automatic HP {'current': 164, 'maximum': 164}; resolved species pokeapi:species:279. This is display evidence, not proof of damage cause or persistent instance.
- 400.500s HUD `own_active_2`: automatic name reading “烈咬陆鲨”; automatic HP {'current': 184, 'maximum': 184}; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 401.502s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:form:10534. This is display evidence, not proof of damage cause or persistent instance.
- 402.002s HUD `own_active_2`: automatic name reading “”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 402.502s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 35; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 402.502s HUD `own_active_1`: automatic name reading “大嘴鸥”; automatic HP None; resolved species pokeapi:species:279. This is display evidence, not proof of damage cause or persistent instance.
- 402.502s HUD `own_active_2`: automatic name reading “烈咬陆鲨”; automatic HP None; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 402.668s HUD `opponent_active_2`: automatic name reading “赛富豪”; automatic HP 35; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 402.668s HUD `own_active_1`: automatic name reading “大嘴鸥”; automatic HP {'current': 164, 'maximum': 164}; resolved species pokeapi:species:279. This is display evidence, not proof of damage cause or persistent instance.
- 402.668s HUD `own_active_2`: automatic name reading “烈咬陆鲨”; automatic HP {'current': 184, 'maximum': 184}; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 403.335s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 404.668s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:form:10534. This is display evidence, not proof of damage cause or persistent instance.
- 405.002s HUD `own_active_2`: automatic name reading “”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 406.002s HUD `own_active_2`: automatic name reading “”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 406.502s HUD `own_active_2`: automatic name reading “”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 413.503s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 413.503s HUD `own_active_2`: automatic name reading “烈咬陆鲨”; automatic HP {'current': 184, 'maximum': 184}; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 423.005s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:form:10534. This is display evidence, not proof of damage cause or persistent instance.
- 423.505s HUD `own_active_2`: automatic name reading “__”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 424.005s HUD `own_active_2`: automatic name reading “”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 424.505s HUD `own_active_2`: automatic name reading “_”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 426.505s HUD `own_active_2`: automatic name reading “1”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 427.005s HUD `own_active_2`: automatic name reading “”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 430.005s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 430.005s HUD `own_active_2`: automatic name reading “烈咬陆鲨”; automatic HP {'current': 184, 'maximum': 184}; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 433.007–434.007s: “REIKOU换下了 / 赛富豪！” — `switch_out`. switch_out: deferred; move unknown; actor 赛富豪; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:a1d249852fbed789f6eb0b86).
- 436.007–437.007s: “REIKOU / 派出了轰擂金刚猩！” — `send_out`. entry_observation: recorded_observation; move unknown; actor unknown; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.); send_out: deferred; move unknown; actor 轰擂金刚猩; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:d3905277d992074910f99c2c).
- 440.007–440.007s: “烈咬陆鲨的烈咬陆鲨进化石Z和 / Hoshi的全一环起了反应!” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:cfb890f4bd4b71741c3bd2ba).
- 454.510–454.510s: “对手的烈咬陆鲨 / 摆出了防守的架势！” — `move_effect`. move_effect: recorded_observation; move unknown; actor 超级烈咬陆鲨; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:59de8934a49af250861dfe17).
- 456.010–456.010s: “烈咬陆鲨使出了 / 守住！” — `move_execution`. move_execution: deferred; move 守住; actor 超级烈咬陆鲨; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:3cafb94abe48fab2f1f85380).
- 462.512–462.512s: “大嘴鸥使出了 / 顺风！” — `move_execution`. move_execution: applied_partial; move 顺风; actor 大嘴鸥; target unknown (Actor and executed move were supported. Targets and move effects were not established.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:bb3296dbe982fe8df655ffc2).
- 466.512–466.512s: “从我方身后 / 吹起了顺风！” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:e1a832a56cebbf833d09862d).
- 467.012s HUD `opponent_active_2`: automatic name reading “轰擂金刚猩”; automatic HP 79; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 471.013s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:form:10534. This is display evidence, not proof of damage cause or persistent instance.
- 471.013s HUD `opponent_active_2`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 471.013s HUD `own_active_2`: automatic name reading “烈咬陆鲨”; automatic HP {'current': 184, 'maximum': 184}; resolved species pokeapi:form:10534. This is display evidence, not proof of damage cause or persistent instance.
- 475.013s HUD `opponent_active_2`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.

Literal field-header OCR (not a trigger/duration deduction): 405.002s: 下雨状态 4/5; 410.002s: 光墙状态 5/8; 415.003s: 下雨状态 4/5; 420.503s: 1 ; 437.507s: 1 A; 444.008s: 1 ，; 471.013s: 下雨状态n 3/5.

**Ending engine projection (unverified).** Player: right: 烈咬陆鲨 (sample_battle_6:self:entry:85531db5ddf5cbd5), last observed 184/184; status unknown; ability unknown; item unknown; left: 大嘴鸥 (sample_battle_6:self:entry:74c9c18234ef7d5a), last observed 164/164; status unknown; ability 降雨; item 文柚果. Opponent: left: 烈咬陆鲨 (sample_battle_6:opponent:hud:4c42039a31c041de3ce2f5e3), last observed 100%; status unknown; ability unknown; item unknown; right: 赛富豪 (sample_battle_6:opponent:hud:a1cec7374153d652ccaa6f24), last observed 35%; status unknown; ability unknown; item unknown. Field: weather: rain active=True; terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: sample_battle_6:self:entry:abf2a156ef338a18: 大声咆哮, 大声咆哮; sample_battle_6:self:entry:e80692fa2a8bba41: 光墙, 灵魂冲击, 抛下狠话; sample_battle_6:opponent:alias:936803684f7d70f904f25c15: 大地之力; sample_battle_6:self:entry:74c9c18234ef7d5a: 顺风.

**Recognition audit.** 7 message candidates; 6 without an admitted semantic conclusion. Correct, incorrect and missed-event counts are unmeasured (0 independently reviewed). UI, HP observations, unresolved reads and coverage cards are inspectable in the viewer.

### Baseline provisional cycle 9 — 476.013–546.508s

Boundary: provisional; command menu observed after live-message interval.

**Starting state.** Player: right: 烈咬陆鲨 (sample_battle_6:self:entry:85531db5ddf5cbd5), last observed 184/184; status unknown; ability unknown; item unknown; left: 大嘴鸥 (sample_battle_6:self:entry:74c9c18234ef7d5a), last observed 164/164; status unknown; ability 降雨; item 文柚果. Opponent: left: 烈咬陆鲨 (sample_battle_6:opponent:hud:4c42039a31c041de3ce2f5e3), last observed 100%; status unknown; ability unknown; item unknown; right: 赛富豪 (sample_battle_6:opponent:hud:a1cec7374153d652ccaa6f24), last observed 35%; status unknown; ability unknown; item unknown. Field: weather: rain active=True; terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: sample_battle_6:self:entry:abf2a156ef338a18: 大声咆哮, 大声咆哮; sample_battle_6:self:entry:e80692fa2a8bba41: 光墙, 灵魂冲击, 抛下狠话; sample_battle_6:opponent:alias:936803684f7d70f904f25c15: 大地之力; sample_battle_6:self:entry:74c9c18234ef7d5a: 顺风.

**Chronological observations.**

- 476.013s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 476.013s HUD `opponent_active_2`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 476.013s HUD `own_active_2`: automatic name reading “烈咬陆鲨”; automatic HP {'current': 184, 'maximum': 184}; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 478.013s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:form:10534. This is display evidence, not proof of damage cause or persistent instance.
- 478.013s HUD `opponent_active_2`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 478.013s HUD `own_active_2`: automatic name reading “烈咬陆鲨”; automatic HP {'current': 184, 'maximum': 184}; resolved species pokeapi:form:10534. This is display evidence, not proof of damage cause or persistent instance.
- 478.513s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 478.513s HUD `opponent_active_2`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 478.513s HUD `own_active_2`: automatic name reading “烈咬陆鲨”; automatic HP {'current': 184, 'maximum': 184}; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 484.015s HUD `opponent_active_2`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 484.515s HUD `opponent_active_1`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:form:10534. This is display evidence, not proof of damage cause or persistent instance.
- 484.515s HUD `opponent_active_2`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 484.515s HUD `own_active_1`: automatic name reading “大嘴鸥”; automatic HP {'current': 164, 'maximum': 164}; resolved species pokeapi:species:279. This is display evidence, not proof of damage cause or persistent instance.
- 484.515s HUD `own_active_2`: automatic name reading “烈咬陆鲨”; automatic HP {'current': 184, 'maximum': 184}; resolved species pokeapi:form:10534. This is display evidence, not proof of damage cause or persistent instance.
- 485.015s HUD `opponent_active_2`: automatic name reading “轰擂金刚猩”; automatic HP None; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 485.015s HUD `own_active_1`: automatic name reading “大嘴鸥”; automatic HP {'current': 164, 'maximum': 164}; resolved species pokeapi:species:279. This is display evidence, not proof of damage cause or persistent instance.
- 503.018–503.518s: “上吧！长毛巨魔！” — `send_out`. entry_observation: recorded_observation; move unknown; actor unknown; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.); send_out: recorded_observation; move unknown; actor 长毛巨魔; target unknown (Only named identity is supported; placement and biological continuity are not established.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:097d6031a8c7bd2fc09fa230).
- 509.518–510.020s: “REIKOU / 派出了炽焰咆哮虎！” — `send_out`. entry_observation: recorded_observation; move unknown; actor unknown; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.); send_out: deferred; move unknown; actor 炽焰咆哮虎; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:c3de03769e7fcb3bf44d131a).
- 515.520–517.020s: “对手的轰擂金刚猩使出了 / 击掌奇袭!” — `move_execution`. move_execution: deferred; move 击掌奇袭; actor 轰擂金刚猩; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:08b41e49110b3339fae7d5fe).
- 517.520s HUD `own_active_2`: automatic name reading “长毛巨魔”; automatic HP {'current': 149, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 518.020s HUD `own_active_2`: automatic name reading “长毛巨魔”; automatic HP {'current': 137, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 523.522s HUD `opponent_active_2`: automatic name reading “轰擂金刚狸”; automatic HP 61; resolved species pokeapi:species:812. This is display evidence, not proof of damage cause or persistent instance.
- 525.022–525.022s: “对对手的轰擂金刚猩 / 效果绝佳！” — `effectiveness`. effectiveness: deferred; move unknown; actor unknown; target 轰擂金刚猩 (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:11ec6464647935b507a7eaf1).
- 527.522–528.022s: “对手的轰擂金刚猩倒下了！” — `faint`. faint: deferred; move unknown; actor 轰擂金刚猩; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:c991310300ccad9d9a3e6411).
- 531.023s HUD `own_active_2`: automatic name reading “长毛巨魔”; automatic HP {'current': 143, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 541.525–542.025s: “REIKOU / 派出了烈咬陆鲨！” — `send_out`. entry_observation: recorded_observation; move unknown; actor unknown; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.); send_out: deferred; move unknown; actor unknown; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:159c31fe7929e1a7d39b3060).

Literal field-header OCR (not a trigger/duration deduction): 476.013s: 青草场地状态 1/5; 485.015s: 光墙状态 4/8; 517.020s: 1 1.

**Ending engine projection (unverified).** Player: right: 长毛巨魔 (sample_battle_6:self:entry:4a40e984167a27ef), last observed 143/201; status unknown; ability unknown; item unknown; left: 大嘴鸥 (sample_battle_6:self:entry:74c9c18234ef7d5a), last observed 164/164; status unknown; ability 降雨; item 文柚果. Opponent: left: 烈咬陆鲨 (sample_battle_6:opponent:hud:4c42039a31c041de3ce2f5e3), last observed 100%; status unknown; ability unknown; item unknown; right: 轰擂金刚猩 (sample_battle_6:opponent:hud:4dedbf15c1687b37c625a37e), last observed unknown HP; status unknown; ability unknown; item unknown. Field: weather: rain active=True; terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: sample_battle_6:self:entry:abf2a156ef338a18: 大声咆哮, 大声咆哮; sample_battle_6:self:entry:e80692fa2a8bba41: 光墙, 灵魂冲击, 抛下狠话; sample_battle_6:opponent:alias:936803684f7d70f904f25c15: 大地之力; sample_battle_6:self:entry:74c9c18234ef7d5a: 顺风.

**Recognition audit.** 6 message candidates; 5 without an admitted semantic conclusion. Correct, incorrect and missed-event counts are unmeasured (0 independently reviewed). UI, HP observations, unresolved reads and coverage cards are inspectable in the viewer.

### Baseline provisional cycle 10 — 546.508–684.515s

Boundary: provisional; command menu observed after live-message interval.

**Starting state.** Player: right: 长毛巨魔 (sample_battle_6:self:entry:4a40e984167a27ef), last observed 143/201; status unknown; ability unknown; item unknown; left: 大嘴鸥 (sample_battle_6:self:entry:74c9c18234ef7d5a), last observed 164/164; status unknown; ability 降雨; item 文柚果. Opponent: left: 烈咬陆鲨 (sample_battle_6:opponent:hud:4c42039a31c041de3ce2f5e3), last observed 100%; status unknown; ability unknown; item unknown; right: 轰擂金刚猩 (sample_battle_6:opponent:hud:4dedbf15c1687b37c625a37e), last observed unknown HP; status unknown; ability unknown; item unknown. Field: weather: rain active=True; terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: unknown. Executed-move revelations: sample_battle_6:self:entry:abf2a156ef338a18: 大声咆哮, 大声咆哮; sample_battle_6:self:entry:e80692fa2a8bba41: 光墙, 灵魂冲击, 抛下狠话; sample_battle_6:opponent:alias:936803684f7d70f904f25c15: 大地之力; sample_battle_6:self:entry:74c9c18234ef7d5a: 顺风.

**Chronological observations.**

- 546.508s HUD `opponent_active_1`: automatic name reading “炽焰咆哮虎”; automatic HP 100; resolved species pokeapi:species:727. This is display evidence, not proof of damage cause or persistent instance.
- 546.508s HUD `opponent_active_2`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 546.508s HUD `own_active_2`: automatic name reading “长毛巨魔”; automatic HP {'current': 149, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 555.027s HUD `own_active_1`: automatic name reading “0”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 555.027s HUD `own_active_2`: automatic name reading “”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 555.527s HUD `own_active_1`: automatic name reading “大嘴鸥”; automatic HP {'current': 164, 'maximum': 164}; resolved species pokeapi:species:279. This is display evidence, not proof of damage cause or persistent instance.
- 555.527s HUD `own_active_2`: automatic name reading “长毛巨魔”; automatic HP {'current': 149, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 558.527s HUD `opponent_active_2`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 559.027s HUD `opponent_active_2`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 559.528s HUD `opponent_active_2`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 568.528s HUD `own_active_2`: automatic name reading “长毛巨魔”; automatic HP {'current': 146, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 592.000s HUD `opponent_active_1`: automatic name reading “炽焰咆哮虎”; automatic HP 44; resolved species pokeapi:species:727. This is display evidence, not proof of damage cause or persistent instance.
- 592.000s HUD `opponent_active_2`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 592.000s HUD `own_active_1`: automatic name reading “大嘴鸥”; automatic HP {'current': 93, 'maximum': 164}; resolved species pokeapi:species:279. This is display evidence, not proof of damage cause or persistent instance.
- 592.000s HUD `own_active_2`: automatic name reading “长毛巨魔”; automatic HP {'current': 130, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 618.503s HUD `opponent_active_1`: automatic name reading “炽焰咆哮虎”; automatic HP 44; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 618.503s HUD `opponent_active_2`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 619.505s HUD `opponent_active_2`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 620.005s HUD `opponent_active_2`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 622.505s HUD `opponent_active_1`: automatic name reading “炽焰咆哮虎”; automatic HP 44; resolved species pokeapi:species:727. This is display evidence, not proof of damage cause or persistent instance.
- 624.505s HUD `opponent_active_2`: automatic name reading “烈咬陆鲨”; automatic HP 100; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 633.507–634.007s: “REIKOU / 派出了赛富豪！” — `send_out`. entry_observation: recorded_observation; move unknown; actor unknown; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.); send_out: deferred; move unknown; actor 赛富豪; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:8d8ae772410d4591bb6f7c2f).
- 649.510s HUD `opponent_active_1`: automatic name reading “赛富豪”; automatic HP 29; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 650.010s HUD `opponent_active_1`: automatic name reading “赛富豪”; automatic HP 2; resolved species pokeapi:species:1000. This is display evidence, not proof of damage cause or persistent instance.
- 656.010–656.510s: “长毛巨魔使出了 / 灵魂冲击！” — `move_execution`. move_execution: deferred; move 灵魂冲击; actor 长毛巨魔; target unknown (The move actor could not be bound using earlier observed evidence.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:3cd97c2b9c5d0bef05b5bb28).
- 658.010s HUD `opponent_active_2`: automatic name reading “烈咬陆鲨”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 665.512–666.012s: “雨停了！” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:2664dea3ec07d29f14c01f2e).
- 667.012–668.012s: “我方的顺风停止了！” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:57a2d04dbc7da331857a3030).
- 673.513–674.513s: “REIKOU / 派出了炽焰咆哮虎！” — `send_out`. entry_observation: recorded_observation; move unknown; actor unknown; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.); send_out: deferred; move unknown; actor unknown; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:ec69a0c853fc689de0105482).
- 673.513s HUD `own_active_1`: automatic name reading “_”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 677.513–678.515s: “大嘴鸥和长毛巨魔的 / 攻击降低了！” — `stat_change`. stat_change: deferred; move unknown; actor 大嘴鸥; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:9ad795f4439f2bd055f9e922).
- 679.515s HUD `opponent_active_1`: automatic name reading “炽焰咆哮虎”; automatic HP 44; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 679.515s HUD `opponent_active_2`: automatic name reading “烈咬陆鲨”; automatic HP 50; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 679.515s HUD `own_active_1`: automatic name reading “大嘴鸥”; automatic HP {'current': 62, 'maximum': 64}; resolved species pokeapi:species:279. This is display evidence, not proof of damage cause or persistent instance.
- 679.515s HUD `own_active_2`: automatic name reading “长毛巨魔”; automatic HP {'current': 130, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 682.515s HUD `opponent_active_1`: automatic name reading “”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 684.015s HUD `opponent_active_1`: automatic name reading “炽焰咆哮虎”; automatic HP 44; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 684.015s HUD `own_active_1`: automatic name reading “大嘴鸥”; automatic HP {'current': 62, 'maximum': 164}; resolved species pokeapi:species:279. This is display evidence, not proof of damage cause or persistent instance.
- 684.015s HUD `own_active_2`: automatic name reading “长毛巨魔”; automatic HP {'current': 130, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.

Literal field-header OCR (not a trigger/duration deduction): 546.508s: 下雨状态 2/5; 553.027s: 光墙状态 3/8; 558.027s: 下雨状态 2/5; 592.000s: 下雨状态 1/5; 618.503s: 1 J; 656.510s: 97 1; 665.512s: 大 2; 682.515s: A 1.

**Ending engine projection (unverified).** Player: right: 长毛巨魔 (sample_battle_6:self:entry:4a40e984167a27ef), last observed 130/201; status unknown; ability unknown; item unknown; left: 大嘴鸥 (sample_battle_6:self:entry:74c9c18234ef7d5a), last observed 62/164; status unknown; ability 降雨; item 文柚果. Opponent: left: 炽焰咆哮虎 (sample_battle_6:opponent:hud:1ed1702c42be880ea4a8cbee), last observed 44%; status unknown; ability unknown; item unknown; right: 烈咬陆鲨 (sample_battle_6:opponent:hud:fd677be096e00199d866b8ea), last observed 100%; status unknown; ability unknown; item unknown. Field: weather: rain active=True; terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: sample_battle_6:self:entry:74c9c18234ef7d5a: attack=-2. Executed-move revelations: sample_battle_6:self:entry:abf2a156ef338a18: 大声咆哮, 大声咆哮; sample_battle_6:self:entry:e80692fa2a8bba41: 光墙, 灵魂冲击, 抛下狠话; sample_battle_6:opponent:alias:936803684f7d70f904f25c15: 大地之力; sample_battle_6:self:entry:74c9c18234ef7d5a: 顺风.

**Recognition audit.** 6 message candidates; 6 without an admitted semantic conclusion. Correct, incorrect and missed-event counts are unmeasured (0 independently reviewed). UI, HP observations, unresolved reads and coverage cards are inspectable in the viewer.

### Baseline provisional cycle 11 — 684.515–753.750s

Boundary: provisional; command menu observed after live-message interval.

**Starting state.** Player: right: 长毛巨魔 (sample_battle_6:self:entry:4a40e984167a27ef), last observed 130/201; status unknown; ability unknown; item unknown; left: 大嘴鸥 (sample_battle_6:self:entry:74c9c18234ef7d5a), last observed 62/164; status unknown; ability 降雨; item 文柚果. Opponent: left: 炽焰咆哮虎 (sample_battle_6:opponent:hud:1ed1702c42be880ea4a8cbee), last observed 44%; status unknown; ability unknown; item unknown; right: 烈咬陆鲨 (sample_battle_6:opponent:hud:fd677be096e00199d866b8ea), last observed 100%; status unknown; ability unknown; item unknown. Field: weather: rain active=True; terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: sample_battle_6:self:entry:74c9c18234ef7d5a: attack=-2. Executed-move revelations: sample_battle_6:self:entry:abf2a156ef338a18: 大声咆哮, 大声咆哮; sample_battle_6:self:entry:e80692fa2a8bba41: 光墙, 灵魂冲击, 抛下狠话; sample_battle_6:opponent:alias:936803684f7d70f904f25c15: 大地之力; sample_battle_6:self:entry:74c9c18234ef7d5a: 顺风.

**Chronological observations.**

- 684.515s HUD `opponent_active_1`: automatic name reading “炽焰咆哮虎”; automatic HP 44; resolved species pokeapi:species:727. This is display evidence, not proof of damage cause or persistent instance.
- 684.515s HUD `opponent_active_2`: automatic name reading “烈咬陆鲨”; automatic HP 50; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 695.000s HUD `opponent_active_1`: automatic name reading “炽焰咆哮虎”; automatic HP 44; resolved species pokeapi:species:727. This is display evidence, not proof of damage cause or persistent instance.
- 697.000s HUD `opponent_active_1`: automatic name reading “炽焰咆哮虎”; automatic HP 44; resolved species pokeapi:species:727. This is display evidence, not proof of damage cause or persistent instance.
- 701.502s HUD `opponent_active_1`: automatic name reading “炽焰咆哮虎”; automatic HP 44; resolved species pokeapi:species:727. This is display evidence, not proof of damage cause or persistent instance.
- 703.502s HUD `opponent_active_1`: automatic name reading “炽焰咆哮虎”; automatic HP 44; resolved species pokeapi:species:727. This is display evidence, not proof of damage cause or persistent instance.
- 714.003s HUD `opponent_active_1`: automatic name reading “炽焰咆哮”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 714.003s HUD `opponent_active_2`: automatic name reading “烈咬陆盗”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 714.003s HUD `own_active_1`: automatic name reading “”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 714.003s HUD `own_active_2`: automatic name reading “3”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 714.503s HUD `own_active_2`: automatic name reading “”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 715.003s HUD `opponent_active_1`: automatic name reading “EV”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 716.020s HUD `opponent_active_1`: automatic name reading “炽焰咆哮虎”; automatic HP 44; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 716.020s HUD `opponent_active_2`: automatic name reading “烈咬陆鲨”; automatic HP 50; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 716.020s HUD `own_active_1`: automatic name reading “大嘴鸥”; automatic HP {'current': 62, 'maximum': 164}; resolved species pokeapi:species:279. This is display evidence, not proof of damage cause or persistent instance.
- 716.020s HUD `own_active_2`: automatic name reading “长毛巨魔”; automatic HP {'current': 130, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 716.520s HUD `opponent_active_1`: automatic name reading “炽焰咆哮虎”; automatic HP 44; resolved species pokeapi:species:727. This is display evidence, not proof of damage cause or persistent instance.
- 716.520s HUD `opponent_active_2`: automatic name reading “烈咬陆鲨”; automatic HP 50; resolved species pokeapi:species:445. This is display evidence, not proof of damage cause or persistent instance.
- 720.005s HUD `opponent_active_1`: automatic name reading “炽焰咆哮虎”; automatic HP 44; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 720.005s HUD `opponent_active_2`: automatic name reading “烈咬陆鲨”; automatic HP 50; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 723.022–724.022s: “对手的炽焰咆哮虎使出了 / 击掌奇袭！” — `move_execution`. move_execution: deferred; move 击掌奇袭; actor unknown; target unknown (Required identity, side, move or effect information was unresolved; state mutation was withheld.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:870eb20fca50459e40bfc944).
- 723.522s HUD `own_active_1`: automatic name reading “N”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 724.522s HUD `own_active_2`: automatic name reading “长毛巨魔”; automatic HP {'current': 128, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 725.522s HUD `own_active_2`: automatic name reading “长毛巨魔”; automatic HP {'current': 110, 'maximum': 201}; resolved species pokeapi:species:861. This is display evidence, not proof of damage cause or persistent instance.
- 726.522–727.522s: “对手的烈咬陆鲨使出了 / 力量宝石！” — `move_execution`. move_execution: applied_partial; move 力量宝石; actor 超级烈咬陆鲨; target unknown (Actor and executed move were supported. Targets and move effects were not established.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:20121c3ec06f88625ca5145f).
- 728.023s HUD `own_active_1`: automatic name reading “大嘴鸥”; automatic HP {'current': 45, 'maximum': 164}; resolved species pokeapi:species:279. This is display evidence, not proof of damage cause or persistent instance.
- 728.523s HUD `own_active_1`: automatic name reading “大嘴鸥”; automatic HP {'current': 15, 'maximum': 164}; resolved species pokeapi:species:279. This is display evidence, not proof of damage cause or persistent instance.
- 730.007–731.523s: “对大嘴鸥 / 效果绝佳！” — `effectiveness`. effectiveness: recorded_observation; move unknown; actor unknown; target 大嘴鸥 (Stored as an observation; this does not establish an active slot or a mechanical effect.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:4b027ec7c16b03c475347e8d).
- 733.007–733.007s: “大嘴鸥使出了 / 顺风！” — `move_execution`. move_execution: applied_partial; move 顺风; actor 大嘴鸥; target unknown (Actor and executed move were supported. Targets and move effects were not established.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:02705caa763043f677d4fbad).
- 734.023–734.023s: “大嘴鸥使出了 / 顺风！” — `move_execution`. move_execution: applied_partial; move 顺风; actor 大嘴鸥; target unknown (Actor and executed move were supported. Targets and move effects were not established.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:40fcf39f616fddab8ddcf974).
- 736.523–738.025s: “从我方身后 / 吹起了顺风！” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:f3300440a86ee019802063b3).
- 738.525–739.525s: “长毛巨魔 / 畏缩了，无法使出招式！” — `move_effect`. move_effect: recorded_observation; move unknown; actor 长毛巨魔; target unknown (Stored as an observation; this does not establish an active slot or a mechanical effect.) Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:25d9a1e886069ddcb29c6717).
- 740.525–741.525s: “我方的光墙消失了！” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:7571aca61c23704863cb5a9c).
- 743.508–744.508s: “有一方选择了投降” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:a39bfa4c31ab0968284fc3f5).
- 745.508–746.508s: “战胜了 / REIKOU!” — `unknown`. No supported semantic state receipt; unresolved. Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#event:139fe1d2882b516676a9d7c4).
- 749.510s HUD `own_active_1`: automatic name reading “Q0@.”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 750.510s HUD `own_active_1`: automatic name reading “60：”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.
- 752.010s HUD `own_active_1`: automatic name reading “00”; automatic HP None; resolved species unknown. This is display evidence, not proof of damage cause or persistent instance.

Literal field-header OCR (not a trigger/duration deduction): 693.000s: 光墙状态 1/8; 720.005s: 欢 R; 725.522s: Ca A; 730.523s: CU AE; 736.523s: t A; 747.008s: 1 H.

**Ending engine projection (unverified).** Player: right: 长毛巨魔 (sample_battle_6:self:entry:4a40e984167a27ef), last observed 110/201; status unknown; ability unknown; item unknown; left: 大嘴鸥 (sample_battle_6:self:entry:74c9c18234ef7d5a), last observed 15/164; status unknown; ability 降雨; item 文柚果. Opponent: left: 炽焰咆哮虎 (sample_battle_6:opponent:hud:1ed1702c42be880ea4a8cbee), last observed 44%; status unknown; ability unknown; item unknown; right: 烈咬陆鲨 (sample_battle_6:opponent:hud:fd677be096e00199d866b8ea), last observed 50%; status unknown; ability unknown; item unknown. Field: weather: rain active=True; terrain: grassy active=True. Counters, remaining duration and unobserved abilities/items remain unknown. Known stat stages: sample_battle_6:self:entry:74c9c18234ef7d5a: attack=-2. Executed-move revelations: sample_battle_6:self:entry:abf2a156ef338a18: 大声咆哮, 大声咆哮; sample_battle_6:self:entry:e80692fa2a8bba41: 光墙, 灵魂冲击, 抛下狠话; sample_battle_6:opponent:alias:936803684f7d70f904f25c15: 大地之力, 力量宝石; sample_battle_6:self:entry:74c9c18234ef7d5a: 顺风, 顺风, 顺风.

**Recognition audit.** 10 message candidates; 7 without an admitted semantic conclusion. Correct, incorrect and missed-event counts are unmeasured (0 independently reviewed). UI, HP observations, unresolved reads and coverage cards are inspectable in the viewer.

## Move, HP, ability, item and field accounting

The JSON preserves every event receipt, prefix state, evidence reference and proposed turn assignment. Executed moves belong only to the instance bound by StateEngine at that prefix. Menu options and PP are observations, not executions. Historical log rows stay a separate stream; opening the log emits no move. Banner screen edge alone does not bind a Pokémon/side. Literal field counters do not prove remaining turns.

## Baseline metrics and review status

| Measure | Count / result |
|---|---|
| Raw message occurrence candidates | 78 |
| Semantic/state observation candidates | 979 |
| Automatic move candidates / canonical references | 18 / 18 |
| Automatic instance-bound move actors / targets | 10 / 0 |
| Automatically admitted move receipts | 10 (not independently verified) |
| Unadmitted semantic receipts | 52 |
| OCR attempts / budget | 6724 / 18096 |
| Icon attempts / budget | 2154 / 9048 |
| Independently reviewed move/event occurrences | 0 |
| Correct transcription / canonical move / actor / target / instance HP | Unknown; correctness denominator 0 |
| Missed moves / false assertions / duplicate real events | Unknown; requires independent review |
| Duplicate stable candidate IDs | 0 |

Candidate kinds: {"preview_observation": 180, "entry_observation": 12, "send_out": 13, "stat_change": 10, "hud_observation": 705, "switch_out": 2, "terrain_change": 1, "move_execution": 18, "effectiveness": 5, "move_effect": 7, "visual_observation": 21, "alias_observation": 1, "transformation": 1, "weather_change": 1, "faint": 2}.

Admission statuses: {"recorded_observation": 456, "deferred": 32, "applied_candidate": 481, "applied_partial": 10}. Internal consistency and admission are not correctness metrics. Unknown/unresolved state facts remain in the prefix facts and receipts. Blank review notes are unreviewed, never accepted.

## Feature-by-feature evidence availability

Counts are automatic candidate observations, often shared by several capabilities. They are not independently reviewed denominators or proof that every constituent feature works. No unobserved feature is credited as tested.

| Feature | Automatic candidates | Evaluation status |
|---|---|---|
| Team-preview species recognition | 127 | observed_but_unresolved |
| Six-member roster identification | 6 | observed_but_unresolved |
| Initial active Pokémon | 705 | observed_but_unresolved |
| Entry recognition | 13 | observed_but_unresolved |
| Switch / replacement recognition | 15 | observed_but_unresolved |
| Nickname OCR | 348 | observed_but_unresolved |
| Nickname-to-species association | 1 | observed_but_unresolved |
| Independent icon matching | 1077 | observed_but_unresolved |
| Roster-conditioned icon matching | 207 | observed_but_unresolved |
| Mega Evolution | 1 | observed_but_unresolved |
| Form identification | 914 | observed_but_unresolved |
| Logical active-slot assignment | 705 | observed_but_unresolved |
| Persistent individual identity / re-entry | 13 | observed_but_unresolved |
| Duplicate species handling | 180 | observed_but_unresolved |
| Ambiguous identity handling | 1 | observed_but_unresolved |
| Player HUD | 354 | observed_but_unresolved |
| Opponent HUD | 351 | observed_but_unresolved |
| HUD Pokémon names | 687 | observed_but_unresolved |
| HUD Pokémon icons | 705 | observed_but_unresolved |
| Numeric HP | 322 | observed_but_unresolved |
| Percentage HP | 300 | observed_but_unresolved |
| Partial HUD | 137 | observed_but_unresolved |
| Isolated HUD | 138 | observed_but_unresolved |
| Grey HUD | 0 | not_evaluated_due_to_insufficient_semantic_review |
| Fading HUD | 0 | not_evaluated_due_to_insufficient_semantic_review |
| Status indicators | 21 | observed_but_unresolved |
| HP changes | 0 | not_evaluated_due_to_insufficient_semantic_review |
| Unavailable versus obscured UI | 2020 | observed_but_unresolved |
| Current versus historical HP | 28 | observed_but_unresolved |
| Visual-row segmentation | 224 | observed_but_unresolved |
| One-line battle messages | 32 | observed_but_unresolved |
| Genuine two-line messages | 192 | observed_but_unresolved |
| OCR transcription | 224 | observed_but_unresolved |
| Chinese text with English nicknames | 48 | observed_but_unresolved |
| Temporal fusion | 61 | observed_but_unresolved |
| Repeated-message deduplication | 61 | observed_but_unresolved |
| Canonical move-name resolution | 18 | observed_but_unresolved |
| Move execution | 18 | observed_but_unresolved |
| Actor attribution | 17 | observed_but_unresolved |
| Target attribution | 0 | not_evaluated_due_to_insufficient_semantic_review |
| Damage messages | 0 | not_evaluated_due_to_insufficient_semantic_review |
| Effectiveness messages | 5 | observed_but_unresolved |
| Multi-hit messages | 0 | not_evaluated_due_to_insufficient_semantic_review |
| Flinch / other battle effects | 7 | observed_but_unresolved |
| Stat changes | 10 | observed_but_unresolved |
| Fainting | 2 | observed_but_unresolved |
| Replacement announcements | 13 | observed_but_unresolved |
| Move-selection menu | 187 | observed_but_unresolved |
| Switching / party-selection menu | 15 | observed_but_unresolved |
| Target-selection menu | 126 | observed_but_unresolved |
| Available move PP / displayed move information | 288 | observed_but_unresolved |
| Move-description overlay | 0 | not_evaluated_due_to_insufficient_semantic_review |
| Pokémon / Party Overlay | 83 | observed_but_unresolved |
| Check Status Overlay | 418 | observed_but_unresolved |
| Battle Log Overlay | 7 | observed_but_unresolved |
| Detailed Pokémon information | 430 | observed_but_unresolved |
| Displayed choices separated from execution | 307 | observed_but_unresolved |
| Historical log opening separated from live events | 7 | observed_but_unresolved |
| Ability activation banners | 172 | observed_but_unresolved |
| Ability-to-Pokémon attribution | 0 | not_evaluated_due_to_insufficient_semantic_review |
| Held-item revelation | 0 | not_evaluated_due_to_insufficient_semantic_review |
| Weather | 1 | observed_but_unresolved |
| Terrain | 1 | observed_but_unresolved |
| Trick Room | 0 | not_evaluated_due_to_insufficient_semantic_review |
| Tailwind | 0 | not_evaluated_due_to_insufficient_semantic_review |
| Aurora Veil | 0 | not_evaluated_due_to_insufficient_semantic_review |
| Other field / side conditions | 21 | observed_but_unresolved |
| Literal displayed field counters | 0 | not_evaluated_due_to_insufficient_semantic_review |
| Remaining-duration uncertainty | 0 | not_evaluated_due_to_insufficient_semantic_review |
| Condition activation / expiration | 2 | observed_but_unresolved |
| False OCR on animation/background | 1583 | observed_but_unresolved |
| Double send-out announcements | 1 | observed_but_unresolved |
| Missing actor binding after coverage gaps | 8 | observed_but_unresolved |
| End-of-battle result | 0 | not_evaluated_due_to_insufficient_semantic_review |

Post-baseline agent visual findings (independent verification still pending): move-description overlay **observed but failed** (misrouted as status); live move/switch/faint messages **observed but failed** in the cited examples; condition expiration and result semantics **observed but failed**; repeated-message deduplication **observed but unresolved / suspected duplicate**; turn boundaries **observed but unresolved**. The historical log has a readable turn-4 heading; it is not a newly executed action. These findings supplement the baseline evidence-availability table and do not create an independent accuracy denominator.

## Known Battle 5 failure modes and remaining priorities

Retain regression coverage for background OCR, visual-row splitting, double send-outs, fading/grey cards, ability banners, move descriptions, nickname/icons, coverage-gap actor binding, repeated text and historical logs. Battle 6 candidate frames exercise only the detector-positive cases listed above; absent positives and lack of independent review prevent a new-video correctness claim.

Highest priorities: independently review turn boundaries and the complete action sequence; inspect unknown message candidates and unscheduled text; verify opening roster/instance binding; review ability-banner and field routing; establish fainting, replacement and final-result coverage. Do not weaken admission to hide these gaps.

## Processing costs, cache usage and resume

The original acquisition attempt ended in the documented fractional-seek error after 121.207s. Its successful full 2-FPS chunks were reused; the acquisition time below is the resumed invocation, not total cold decoding cost. The 30-second OCR probe cost 34.357s and its 81 per-frame checkpoints were reused. Stage times are recorded invocation wall times, not an end-to-end real-time claim.

- freeze: complete; 1.189s in its recorded invocation.
- survey: complete; 114.729s in its recorded invocation.
- acquire: complete; 27.757s in its recorded invocation.
- recognize: complete; 1339.595s in its recorded invocation.
- reconstruct: complete; 332.674s in its recorded invocation.
- Reused 81 per-frame recognition/context checkpoints from the initial cost probe or an earlier compatible invocation.
- Final recognition invocation reused 1 OCR and 0 icon predictions; probe/resume caches remain intact.

Resume/check commands (only this recording):

```sh
.venv/bin/python scripts/process_m237.py --stage verify
.venv/bin/python scripts/process_m237.py --stage reconstruct
.venv/bin/python scripts/process_m237.py --stage deliver
```

For an interrupted acquisition or recognition, use `--stage acquire` or `--stage recognize`. Completed compatible stages validate their output hashes and return. Per-frame predictions and successful OCR are preserved if a later stage fails. A budget exception is an incomplete stage, never a reduced-coverage completion.

## Validation and acceptance

Executed validation: **68 focused regression tests passed** (6.42s); offline Chrome **passed** for all 1801 unique frame assets and 70 representative groups, plus real JSON download/import, persistence and the human overlay-review override. No unexpected browser errors. Historical preservation verified 3453 paths and 73 frozen source dependencies. This validates the workflow, not semantic accuracy.

The previously documented M2.3.4 source-freeze/allowlist incompatibility remains outside this change; its historical seal was not relaxed or resealed. The new baseline pins the current source state. The focused regression suite does not replace the earlier broad milestone suite.

See `validation.json` in the Battle 6 cache for executed tests/browser checks. Reports generated before that receipt exists must not be interpreted as having passed those checks. Battle 5 frozen files, seals and annotations are checked separately by `--stage verify`. No commit/push, damage/Speed change, priors, recommendations or rule relaxation is part of this work.

**Deliverable generation is separate from semantic acceptance.** This full-video automated inventory remains provisional until a human independently reviews it. It does not establish a verified complete battle, true turn count, winner or recognition accuracy.

## Coverage appendix

| Interval (s) | Status | Sampled / expected base cells |
|---|---|---|
| 0–10.00 | sampled_unresolved_message_evidence | 20/20 |
| 10–20.00 | sampled_unresolved_message_evidence | 20/20 |
| 20–30.00 | sampled_without_supported_live_message | 20/20 |
| 30–40.00 | sampled_without_supported_live_message | 20/20 |
| 40–50.00 | sampled_without_supported_live_message | 20/20 |
| 50–60.00 | sampled_without_supported_live_message | 20/20 |
| 60–70.00 | sampled_without_supported_live_message | 20/20 |
| 70–80.00 | sampled_without_supported_live_message | 20/20 |
| 80–90.00 | sampled_without_supported_live_message | 20/20 |
| 90–100.00 | sampled_without_supported_live_message | 20/20 |
| 100–110.00 | sampled_without_supported_live_message | 20/20 |
| 110–120.00 | sampled_without_supported_live_message | 20/20 |
| 120–130.00 | sampled_with_event_candidates | 20/20 |
| 130–140.00 | sampled_with_event_candidates | 20/20 |
| 140–150.00 | sampled_without_supported_live_message | 20/20 |
| 150–160.00 | sampled_without_supported_live_message | 20/20 |
| 160–170.00 | sampled_with_event_candidates | 20/20 |
| 170–180.00 | sampled_with_event_candidates | 20/20 |
| 180–190.00 | sampled_with_event_candidates | 20/20 |
| 190–200.00 | sampled_with_event_candidates | 20/20 |
| 200–210.00 | sampled_with_event_candidates | 20/20 |
| 210–220.00 | sampled_without_supported_live_message | 20/20 |
| 220–230.00 | sampled_with_event_candidates | 20/20 |
| 230–240.00 | sampled_with_event_candidates | 20/20 |
| 240–250.00 | sampled_with_event_candidates | 20/20 |
| 250–260.00 | sampled_without_supported_live_message | 20/20 |
| 260–270.00 | sampled_with_event_candidates | 20/20 |
| 270–280.00 | sampled_with_event_candidates | 20/20 |
| 280–290.00 | sampled_with_event_candidates | 20/20 |
| 290–300.00 | sampled_without_supported_live_message | 20/20 |
| 300–310.00 | sampled_without_supported_live_message | 20/20 |
| 310–320.00 | sampled_with_event_candidates | 20/20 |
| 320–330.00 | sampled_with_event_candidates | 20/20 |
| 330–340.00 | sampled_with_event_candidates | 20/20 |
| 340–350.00 | sampled_with_event_candidates | 20/20 |
| 350–360.00 | sampled_with_event_candidates | 20/20 |
| 360–370.00 | sampled_with_event_candidates | 20/20 |
| 370–380.00 | sampled_with_event_candidates | 20/20 |
| 380–390.00 | sampled_with_event_candidates | 20/20 |
| 390–400.00 | sampled_with_event_candidates | 20/20 |
| 400–410.00 | sampled_without_supported_live_message | 20/20 |
| 410–420.00 | sampled_without_supported_live_message | 20/20 |
| 420–430.00 | sampled_without_supported_live_message | 20/20 |
| 430–440.00 | sampled_with_event_candidates | 20/20 |
| 440–450.00 | sampled_unresolved_message_evidence | 20/20 |
| 450–460.00 | sampled_with_event_candidates | 20/20 |
| 460–470.00 | sampled_with_event_candidates | 20/20 |
| 470–480.00 | sampled_without_supported_live_message | 20/20 |
| 480–490.00 | sampled_with_event_candidates | 20/20 |
| 490–500.00 | sampled_without_supported_live_message | 20/20 |
| 500–510.00 | sampled_with_event_candidates | 20/20 |
| 510–520.00 | sampled_with_event_candidates | 20/20 |
| 520–530.00 | sampled_with_event_candidates | 20/20 |
| 530–540.00 | sampled_without_supported_live_message | 20/20 |
| 540–550.00 | sampled_with_event_candidates | 20/20 |
| 550–560.00 | sampled_with_event_candidates | 20/20 |
| 560–570.00 | sampled_without_supported_live_message | 20/20 |
| 570–580.00 | sampled_without_supported_live_message | 20/20 |
| 580–590.00 | sampled_without_supported_live_message | 20/20 |
| 590–600.00 | sampled_without_supported_live_message | 20/20 |
| 600–610.00 | sampled_without_supported_live_message | 20/20 |
| 610–620.00 | sampled_without_supported_live_message | 20/20 |
| 620–630.00 | sampled_without_supported_live_message | 20/20 |
| 630–640.00 | sampled_with_event_candidates | 20/20 |
| 640–650.00 | sampled_without_supported_live_message | 20/20 |
| 650–660.00 | sampled_with_event_candidates | 20/20 |
| 660–670.00 | sampled_unresolved_message_evidence | 20/20 |
| 670–680.00 | sampled_with_event_candidates | 20/20 |
| 680–690.00 | sampled_with_event_candidates | 20/20 |
| 690–700.00 | sampled_without_supported_live_message | 20/20 |
| 700–710.00 | sampled_without_supported_live_message | 20/20 |
| 710–720.00 | sampled_without_supported_live_message | 20/20 |
| 720–730.00 | sampled_with_event_candidates | 20/20 |
| 730–740.00 | sampled_with_event_candidates | 20/20 |
| 740–750.00 | sampled_unresolved_message_evidence | 20/20 |
| 750–753.75 | sampled_without_supported_live_message | 8/8 |

<details><summary>Technical evidence and provenance</summary>

The offline viewer contains expandable OCR rows/tokens, independent and roster-conditioned icon scores, HUD observations, raw region visibility, state receipts and chronological prefix states. `reports/battles/sample_battle_6/M2.3.7/turns.json` is the canonical structured account; `.cache/battles/sample_battle_6/m237/replay.json` is the authoritative existing-engine replay. `baseline-observations.json` is sealed raw prediction output. No manual annotation is merged into these files.

</details>
