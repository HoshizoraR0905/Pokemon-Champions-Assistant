# B16 semantic parsing and state reconstruction — development/regression

2026-10-27. Phases 1–5 completed. No commit/push. B16 already guided development; this is not a held-out accuracy result.

## Architecture and changes

The existing BattleState remains authoritative. Raw OCR and evidence remain separate from normalized semantics. MessageOccurrences → EventParser → prefix identity/evidence fusion → StateEngine policy and atomic transitions → receipts/state snapshots. Fact distinguishes observed, derived, unknown and conflicting values. Missing side/instance/slot evidence still defers application.

Literal parsing now supports continued sleep/wake, sun/sand announcements, opponent Tailwind, Wide Guard side activation and bound per-action protection/absorption outcomes. Side conditions record onset event and known turn; durations remain unknown without evidence. Generic Mega completion records the transformation with X/Y form unknown. The canonical stone reaction permits contextual 丫→Y normalization while preserving raw text. Low-confidence semantic candidates remain auditable. HP announcements do not create an amount or attacker/move cause; no move cause is inferred from adjacency.

Modified production modules: `battle_events/parser.py`, new `battle_events/message_patterns.py`, `recognition/message_occurrences.py`, `tracking/state_engine.py`. New end-to-end tests: `tests/test_semantic_state.py`; evaluation tests: `tests/test_b16_state_benchmark.py`. The synthetic banner in `tests/test_scrolling_semantics.py` now supplies banner provenance rather than contradictory live-message provenance.

Example: “从对手身后吹起了顺风！” → side_condition_change(opponent, tailwind, start) → opponent.conditions.tailwind.active=true, initiated_by points to that event, duration unknown. A separate move_execution records the user using Tailwind; neither record invents a target or a four-turn timer.

## Cleanup and normal production performance

Exact inventory, deletion result and historical baseline are retained in `docs/b16-semantic-state/`. Deleted 11,733 verified B16-generated files (3,138,331,700 logical bytes); original 1,413,192,982-byte video SHA256 unchanged. No shared assets, repository sources/tests, unrelated battles or user inputs were deleted.

| Metric | Measured value |
|---|---:|
| Original video | 753.74 s |
| Normal CLI wall, excluding reference/evaluation | 666.124 s |
| Normal pipeline PTR | **0.8838** |
| Internal pipeline wall | 665.341 s |
| Final replay/export stage | 178.869 s |
| Source-decoded frames | 30216 |
| Sampling | 2 FPS; 1508 materialized/monitored frames |
| Detailed inspections | 1276 (1026 at 2 FPS; 250 at 1 FPS) |
| OCR model invocations | 4204 |
| Icon model invocations | 126 |
| Candidate events / deferred | 1290 / 30 |

Cold run `b16-semantic-state-20261027-v1`: full video, lightweight identity, PP-OCRv6_medium_rec ONNX CPU revision `50c7eacafc52fa7bcf4194e8cd08e46f8558504b`; no imported recognition/frame/state cache, manual team/state/identity injection or retrospective log input. Same-run exact crop reuse (1 hit) is not an imported cache. Default sampling is 2 FPS, with separate adaptive inspection and OCR schedules.

Old internal PTR≈2.3651 (1782.653s); old external CLI PTR≈2.3672 (1784.249s). New double-faint scheduling avoided all 20 ordinary prefix replays. Semantic code also changed, and the old run enabled call profiling while this run did not. macOS arm64, 8 logical CPUs; no controlled thermal/background-load or repeated-trial comparison. No controlled speedup multiplier is claimed. Final replay remains expensive.

## Independent reference coverage

After live sealing, a separate original-video 2-FPS scan found 51 log views / 303 row observations. Automatic assembly produced 90 rows and 11 overlap issues. Agent source-pixel review recovered another 28 readable rows at scroll boundaries, for **118 distinct chronological log records**. This includes records omitted from the previous 89-row audit, so denominators differ.

The reference uses actual turn headings, row order, boundary anchors and scroll positions; viewing timestamps are never action timestamps. All original source/event/observation IDs survive. 280 raw observations map exactly to curated rows, including 162 duplicate observations beyond the first; 104 rows have multiple exact views. The remaining 23 raw fragments/OCR variants remain unresolved and unscored as extra events. No unique readable reference row was discarded by a confidence threshold. This does not establish whole-match log completeness.

Reference semantics were independently annotated from pixels without calling EventParser or reading live predictions. Canonical identity resolution reuses KnowledgeBase only. Shared ONNX OCR/geometry still allow correlated errors; agent pixel review is not independent human ground truth. The reference was sealed before comparison.

The 118 log records yield 121 event facts; 3 separately decoded HUD-zero observations yield **124 evaluable event facts** and **191 supported state checkpoint fields**. Sources: Battle Log=121 event facts; HUD=3; facts requiring both=0. HUD navigation used prior audit times, with fresh original-pixel verification; no new live prediction was used to supply reference values.

Move targets, attribution of numeric damage to a move/attacker, absolute opponent HP, exact stage values/baselines, Mega X/Y identity, weather termination, Trick Room and terrain are not independently evaluable here. They receive no success credit. Tailwind activation and termination are both represented. Numeric HP includes own absolute values and opponent displayed percentages; percentage differences are percentage points, not absolute HP.

## Event facts and actual state fields

**A. Event-fact reconstruction: 107/124 = 86.29%.** This includes complete recognized announcements that were not applied to authoritative state; those remain explicitly labeled.
**B. Key-state reproduction: 154/191 = 80.63%.** Micro-averaged field counts, not an average of category percentages.

Applied event facts: 97/124; event comparison statuses: {"correct_applied": 97, "missing": 17, "recognized_not_applied": 10}. State comparison statuses: {"correct_applied": 154, "missing": 29, "recognized_not_applied": 8}. No incorrect actor/target/value was established among aligned facts; that is not a whole-match false-positive claim. Unverifiable requested fields stay outside these supported denominators.

| Category | Event facts correct / evaluable | Applied event facts | State fields correct / evaluable |
|---|---:|---:|---:|
| Switching/fainting | 21/21 | 21/21 | 42/42 |
| Ability activation | 4/6 | 4/6 | 4/6 |
| Weather | 4/5 | 4/5 | 8/10 |
| Other notices/effectiveness/absorption | 11/11 | 1/11 | 1/9 |
| Mega completion (X/Y unknown) | 2/2 | 2/2 | 2/2 |
| Move execution | 25/25 | 25/25 | 25/25 |
| Status/recovery | 9/9 | 9/9 | 9/9 |
| Numeric damage/HP loss | 11/18 | 11/18 | 36/54 |
| Stat change direction (exact stage unknown) | 4/4 | 4/4 | 4/4 |
| Item activation | 1/3 | 1/3 | 1/3 |
| Numeric healing | 3/3 | 3/3 | 9/9 |
| Protective effects | 10/10 | 10/10 | 10/10 |
| Tailwind | 2/2 | 2/2 | 3/3 |
| Explicit burn-damage notices (amount unknown) | 0/2 | 0/2 | 0/2 |
| Independent HUD zero endpoints | 0/3 | 0/3 | 0/3 |
| Move target / Trick Room / terrain | Not evaluable | — | Not evaluable |

Comparison uses chronological semantic/identity matching and reference entry episodes. Same-frame capture ties do not inherit an action order from lexicographic event IDs. No text-equality-only matching or log viewing timestamps are used. Numeric HP pairs require two applied endpoints in the same live instance within the supported chronological action window; no attacker or move is attributed. A supported endpoint can score its state field even when the full pair is missing.

State checkpoints come from a read-only replay using the existing StateEngine. Every per-event state hash, application status/reason and final state matched the sealed live output. Evaluation creates no replacement authoritative state. HP before/after/difference fields share evidence and are not independent statistical samples. Zero mismatches in deterministic replay are not recognition accuracy.

## Remaining failures

- **Ability activation / missing: 2**. Examples: `log:3:0` (opponent, species 279, 降雨); `log:101:0` (opponent, species 279, 降雨). No chronological semantic match.
- **Other notices/effectiveness/absorption / recognized_not_applied: 10**. Examples: `log:5:0` (self, species 6, mega_stone_reaction_notice); `log:39:0` (opponent, species 445, effectiveness:not_very_effective). recorded_observation.
- **Item activation / missing: 2**. Examples: `log:20:0` (opponent, species 1018, 吃剩的东西); `log:29:0` (opponent, species 1018, 吃剩的东西). No chronological semantic match.
- **Numeric damage/HP loss / missing: 7**. Examples: `log:38:0` (opponent, species 445, 100→67); `log:51:0` (self, species 3, 84→0). Missing same-instance numeric endpoint pair; faint is not an HP-zero observation.
- **Weather / missing: 1**. Examples: `log:72:0` (field, species field, sun). No chronological semantic match.
- **Explicit burn-damage notices (amount unknown) / missing: 2**. Examples: `log:84:0` (self, species 279, burn residual; amount unknown); `log:96:0` (self, species 279, burn residual; amount unknown). No chronological semantic match.
- **Independent HUD zero endpoints / missing: 3**. Examples: `hud:0` (self, species 3, HUD=0); `hud:1` (self, species 279, HUD=0). No chronological semantic match.

The failures include activation-banner acquisition, at least one sunlight announcement not emitted, missing zero/baseline HP reads, unsupported burn-residual notices, and effectiveness/reaction records that remain observations without corresponding scoped state. No rules were tuned using this final comparison and relabeled as held-out results.

## Validation and artifacts

Pre-run relevant tests: 147 passed, 1 deselected. First portable sweep: 2591 passed, 1 synthetic-provenance fixture failure, 73 deselected; corrected the fixture and 56 related tests passed. Final portable sweep: 2592 passed, 73 deselected (302.27s); additional evaluator tie-order tests: 5 passed. Counts overlap. One environment ccache warning. No optional present artifact failures were suppressed; local_artifacts were explicitly excluded.

Machine-readable artifacts: [reference facts](reference-facts.json), [event-fact scores](event-fact-scores.json), [state comparisons](state-comparisons.json), [published metrics](published-metrics.json), [raw observation resolution](observation-resolution.json). Detailed snapshots, source/config fingerprints, stage manifests, timestamps, seals and logs remain in the matching `.cache/battles/sample_battle_16/` namespace. Prior evaluator output is retained under `state-benchmark/evaluation-revisions/v1/` with its correction reason.

Reproduce/resume only incomplete stages using `docs/b16-semantic-state/progress.md`; do not rerun the cold decoder or delete successful stages. Remaining semantic gaps above are reported, not silently patched after evaluation.

## 两条中文简历指标

- 使用 PP-OCRv6 ONNX 与事件驱动轻量管线，对 753.74 秒完整录像执行冷启动解析，正常处理耗时 666.124 秒，实测 PTR=0.8838（不含独立日志提取与评估）。
- 在 B16 开发回归评估中，以 118 条源像素审阅日志及 3 个独立 HUD 点建立参考，复现 107/124 个事件事实和 154/191 个关键状态字段（80.63%），分别报告已应用、仅识别与缺失；非独立人工标注准确率。
