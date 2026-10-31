# M2 — action-level damage resolution

Completed development run: `b16-action-resolution-20261028-v4`. Reuses sealed B16 v5 acquisition and the saved v6/v5 attribution receipts. No source predictions or Battle Log reference facts were changed.

**41 adjacent numeric changes → 21 action/target episodes** across 25 move executions. The grouping comes from live event windows, not reference labels. Every old numeric change belongs to exactly one episode. Moves without observed HP changes remain in the action inventory; they are not asserted to cause zero damage.

| Measure | Result |
|---|---:|
| Complete pre-action / stable final endpoints | 16/21 |
| Known cause, including incomplete episodes | 10/21 |
| Complete supported causal totals | 6/21 (28.6%) |
| Comparable legacy complete totals, derived from old labels | 2/21 (9.5%) |
| Known causal totals among complete endpoints | 6/16 (37.5%) |
| Unresolved source / target | 11 episodes |
| Missing pre-action HP | 3 episodes |
| Final plateau not confirmed | 2 episodes |

The unresolved categories overlap. Fifteen episodes fail full causal acceptance; five have unresolved endpoint boundaries. The old 13/41 labels touch nine action groups, but include incomplete totals and animation tails. The derived before value of 2/21 uses the same complete-boundary and full-fragment criteria as the new view; it is not a previously published action metric. The original reference denominator remains unchanged.

| Complete supported episode | Before → settled HP | Signed delta | Source time (s) | Source event |
|---|---|---:|---:|---|
| own 妙蛙花: 气象球 | 84 → 0 (absolute) | -84 | 361.512 | `event:f69fc719b2fce86f2cded3e4` |
| own 大嘴鸥: 热风 | 164 → 110 (absolute) | -54 | 538.507 | `event:bde2c64e7a077fa13ac14efa` |
| opponent 烈咬陆鲨: 气象球 | 67 → 48 (displayed_percent) | -19 | 552.510 | `event:733fef2838067330fe6f31f7` |
| own 大嘴鸥: burn | 110 → 100 (absolute) | -10 | 561.012 | `event:3077ddb3cb20d11e73b499db` |
| opponent 喷火龙: 气象球 | 100 → 0 (displayed_percent) | -100 | 715.503 | `event:57b0a83d01f6869b640f764c` |
| own 喷火龙: 气象球 | 164 → 12 (absolute) | -152 | 727.005 | `event:a631a4841a20683a3dc28209` |

Opponent values are displayed percentage points, not absolute HP or formula-derived damage. Raw observed values in incomplete episodes remain visible, but their authoritative total delta is unknown. Three examples are Garchomp 81→67, Archaludon 19→0 and Pelipper 53→33: they do not establish the HP before the corresponding action began. The second burn has observed 100→90 but only one final 90 reading; it is not accepted as a settled total.

Original metrics stay **120/124 event facts**, **175/191 state fields**, **18/21 reference numeric pairs**, **3/3 observed HUD zeros**. These endpoint-pair metrics differ from the stricter stable action endpoint count of 16/21. The read-only action projection leaves the complete serialized state and every receipt byte-equivalent, verified before/after querying. The legacy HP admission/enrichment implementation is unchanged. Replay, retraction, correction and serialization are separately tested. No independently verified action-cause labels exist, so causal correctness is unmeasured.

## Sampling and hit resolution

Ordinary acquisition remains at its current 2 FPS default. `recognition/resolution_sampling.py` reuses the production FFmpeg PTS decoder, HUD visibility, `hp_refresh`, cached numeric OCR and fixed HP ROIs. A scoped original-video second pass seeks back before the recognized action and known baseline, so delayed recognition does not discard pre-trigger source frames. `--fps` defaults to 5 for these windows and accepts higher rates. A provisional pinned multi-hit reference can request inspection; it is not promoted to verified Champions mechanics or an equipped-move claim.

Actual B16 engineering probe: **45 sampled frames over 9 seconds at 5 FPS**, **271 source frames counted before selection**, **8 pre-trigger frames**, maximum PTS gap **0.218333 s**, **30 HP ROI read requests**, **15 HP reading invocations**, **13 OCR model predictions**, **0 full-screen OCR calls**. First/last sampled PTS are 360.010000 / 368.811667 s. The existing model and thresholds were reused. This is a weather-ball acquisition/cost probe, not evidence of multi-hit detection.

The real probe adapter independently binds 18 visible/reused HP samples to the existing Venusaur instance and its endpoint receipts. Its first visible dense HP is 79, not the accepted pre-action 84; the adapter preserves the supported total 84→0 and leaves per-hit damage unknown. It never inserts a fabricated dense 84 sample. The binding check and unchanged-state proof are saved beside the probe manifest.

B16 saved predictions contain zero supported critical notices or multi-hit inspection candidates. The real multi-hit inspection run completed with zero planned windows and zero new frame/OCR work. No real multi-hit detection success is claimed. Synthetic tests demonstrate hit contracts only.

Per-hit amounts require at least 5 FPS coverage, stable plateaus and an independent matching hit count. Verified capability alone permits candidates but does not invent a count. Distinct hits without observable separation retain a supported action total with unknown per-hit damage. A short pause inside an animation does not end the action. Bare critical notices require a uniquely supported recipient; spread recipients and multi-hit critical indices are not guessed. Explicit hit indices can attach `critical_hit=true` to the relevant hit. Another-instance item damage can coexist with a continuing multi-hit target window; inseparable same-target effects cause abstention.

## Files and evidence

Implementation: `tracking/hp_causes.py`, the `StateEngine.hp_resolutions()` projection in `tracking/state_engine.py`, narrow literal unscoped critical/count parsing in `battle_events/parser.py`, `recognition/resolution_sampling.py`, `scripts/evaluate_hp_resolutions.py`, and `tests/test_hp_resolutions.py`. Existing segment observations and legacy labels remain for audit and compatibility; action episodes are the new damage-resolution output. No second state model or annotation UI was added.

All 21 episodes, actor/target identities, endpoint times, source provenance, final-plateau receipts, raw segment membership, reasons and unresolved hit data are in the [final report](../../reports/battles/sample_battle_16/evaluation/b16-action-resolution-20261028-v4/report.md) and its linked `action-episodes.json`.

Validation: **256 passed, 3 deselected**, 55.59 s (`not local_artifacts`); compilation and `git diff --check` passed. Covers ordinary/critical/spread, multi-hit plateaus and missing plateaus, recoil, Life Orb/helmet-style item evidence, Rough Skin, residual/healing, observation gaps, source/holder separation, unit and zero preservation, in-flight windows, revision/retraction, between-hit effects and replay round-trip. No failure was relabeled as missing artifacts.

Next priorities: independent action/critical/hit annotations and a real confirmed multi-hit recording; explicit recipient/effect evidence for remaining source ambiguities; missing pre-action readings and the two unsettled final plateaus. No next milestone, commit or push was performed.

## Scoped mechanics check

Retrieved 2026-10-28: [52Poké, Bullet Seed, revision 2627565](https://wiki.52poke.com/index.php?title=种子机关枪（招式）&oldid=2627565). Its move-description table has an explicit Champions row describing 2–5 attacks; the separate Z-A row has different wording. This check does not establish equipped moves, hit counts in B16, or hit probabilities. No new runtime supplement/importer was introduced; runtime inspection uses the existing offline pinned reference and independent hit notices. Attribution: 神奇宝贝百科 contributors; article license CC BY-NC-SA 3.0.

See [progress.md](progress.md) for scoped commands, cache ownership and interruption recovery.
