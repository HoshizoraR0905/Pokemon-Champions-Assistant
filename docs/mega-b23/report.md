# Champions Mega stats and fresh B23 benchmark

2026-10-30. Mega calculation validated; B23 first production run completed and
frozen. **B23 runtime team linkage did not succeed**, so its first run did not use
Team 7's calculated stats. The independently visible roster matches Team 7;
the normal preview acquisition did not emit structured self-roster rows. This is
a concrete integration limitation, not an accepted end-to-end Mega-stat result.

## Mega calculation

Reused `knowledge.champions_stats.ChampionsStats`: HP = base + SP + 75;
other stats = `(base + SP + 20) * factor // 10`, with integer factors 9/10/11.
The implementation uses the saved explicit SP allocations and reviewed alignment
arrows; it does not reverse-fit either from displayed stats. All **36 displayed
original-form values** of the six Team 7 members reproduce exactly.

Values below are HP / Attack / Defense / Special Attack / Special Defense / Speed.
They are unmodified displayed stats, separate from stat stages and temporary
effects. Listing a possible Mega form does not assert that the team holds its stone.

| Team 7 member / form | Calculated stats |
|---|---|
| Venusaur | 156 / 91 / 103 / 167 / 121 / 132 |
| Mega Venusaur | 156 / 108 / 143 / 191 / 141 / 132 |
| Charizard | 184 / 93 / 99 / 143 / 121 / 137 |
| Mega Charizard X | 184 / 135 / 132 / 166 / 121 / 137 |
| Mega Charizard Y | 184 / 111 / 99 / 198 / 151 / 137 |
| Pelipper | 164 / 63 / 121 / 115 / 132 / 91 |
| Garchomp | 184 / 135 / 116 / 145 / 105 / 154 |
| Mega Garchomp | 184 / 171 / 136 / 189 / 115 / 144 |
| Mega Garchomp Z | 184 / 135 / 106 / 212 / 105 / 203 |
| Grimmsnarl | 201 / 140 / 111 / 103 / 114 / 80 |
| Archaludon | 194 / 112 / 166 / 146 / 109 / 116 |

Verified form base stats (same column order):

| Form | Base stats | Pinned 52Poké source |
|---|---|---|
| Mega Venusaur | 80 / 100 / 123 / 122 / 120 / 80 | [Venusaur, revision 2637065](https://wiki.52poke.com/index.php?title=妙蛙花&oldid=2637065) |
| Mega Charizard X | 78 / 130 / 111 / 130 / 85 / 100 | [Charizard, revision 2637071](https://wiki.52poke.com/index.php?title=喷火龙&oldid=2637071) |
| Mega Charizard Y | 78 / 104 / 78 / 159 / 115 / 100 | Same Charizard revision |
| Mega Garchomp | 108 / 170 / 115 / 120 / 95 / 92 | [Garchomp, revision 2637261](https://wiki.52poke.com/index.php?title=烈咬陆鲨&oldid=2637261) |
| Mega Garchomp Z | 108 / 130 / 85 / 141 / 85 / 151 | Same Garchomp revision |

Source assertions were retrieved 2026-10-30 in the interrupted work and retained in
`knowledge/data/mega-stat-evidence-v1.json`, with revision, game applicability and
attribution (52Poké contributors, CC BY-NC-SA 3.0). Each exact form is cross-checked
against the existing pinned KnowledgeBase; runtime requires no network.

`tracking/form_stats.py` stores the calculation in existing
`PokemonState.mechanics['battle_stats']` and retains original configuration and
provenance in team metadata. The same actor's observed stone reaction plus
completed Mega result resolve the exact form; ambiguous generic Garchomp results
remain unknown. This does not infer equipped items, hidden abilities or moves.
HPState, item, persistent identity and stat stages are preserved.

`tracking/transformation.py` copies verified current-form non-HP stats into the
existing Ditto snapshot; stages are copied separately and Ditto's own HP is retained.
Cached B22 validation resolves its target to `pokeapi:pokemon:10309` (Mega Z),
copying **135 / 106 / 212 / 105 / 203**. All **45 nonzero numerical HP segments**,
the original **12 deferred receipts**, and two Ditto entry episodes are preserved.
This is saved-evidence validation, without decoding or OCR or rerunning B22 video.

Regression result: **293 passed, 3 deselected**, including all six native builds,
normal Mega versus Mega Z, exact rational floor checks for 0.9/1.0/1.1,
HP/item/identity/stage preservation, Ditto copy and event retraction, plus relevant
state, HP, event-driven and artifact-policy regressions. Commands and durable
stage paths are recorded in [progress.md](progress.md).

## B23 first production run

Run ID: `mega-b23-20261030-v1`. One uninterrupted production attempt in a fresh
namespace, with lightweight identity, normal 2 FPS sampling and existing automatic
multi-hit inspection enabled. No B23-driven code/threshold/performance changes
were made before or after this run. Shared pinned models, icons and knowledge
were reused; no other battle's observations were imported.

| Metric | Frozen first-run result |
|---|---:|
| Container video duration | **787.28 s** |
| External production CLI wall | **803.716960 s** |
| PTR: wall / full video duration | **1.020878 s/video-second** |
| Source frames: container / decoder | 27,260 / 27,260 |
| 2 FPS materialized / monitored frames | 1,575 / 1,575 |
| Detailed inspection frames | 1,566 |
| Detailed scheduling: 2 FPS / 1 FPS | 1,097 / 469 |
| Model OCR invocations | **5,764** |
| Icon model invocations / preview requests | **12 / 6** |
| OCR model accumulated time | 319.898119 s (included in wall) |
| Internal complete pipeline time | 802.658021 s |
| Production `replay_seconds` span | **357.967342 s**, included in wall |
| Separate HP projection | 0.312091 s, excluded from wall |
| Events / receipts | **2,036 / 2,036** |
| Accepted candidate / partial / observation | 1,941 / 31 / 34 |
| Deferred / rejected | **30 / 0** |
| State conflicts | **1 maximum_hp_disagreement** |
| HP aggregate groups | **36**, 25 complete endpoints |
| HP attribution status | 25 supported, 11 ambiguous |
| Nonzero numeric HP segments | **68**, each belongs to exactly one projected group |
| Automatic dense windows / frames / OCR calls | **0 / 0 / 0** |
| Team configuration / calculated stats actually injected | **None** |

The external timer covers subprocess startup through normal CLI exit, including
initialization, recognition, reconstruction, serialization and viewer export.
Freezing, review and the separate HP projection are excluded. `cold_run` and
`full_cold_timing_comparable` are true. The production summary's `video_duration`
is the last sampled timestamp (787.0 s); PTR uses the full 787.28 s container
duration. Source SHA256:
`9ea84465153c9ab639ac1f0467ca21892d2ea6af9af096b0b501325e6248ea83`.

**Timing limitation:** the existing `replay_seconds` timer starts before event
adaptation and stops after writing replay/prediction JSON. It includes StateEngine
replay, team-linkage preparation, automatic multi-hit inspection and some
serialization. It is not an isolated `StateEngine.replay()` measurement; pure
first-run engine time was not instrumented. No second full replay was launched
just to substitute another run's time for this first-run metric.

The 2,036 events include 1,897 HUD observations, 31 move executions and 126 events
under the existing `reconstructed_event_count` classification. These are production
counts, not independently verified event totals. There are no recognized multi-hit
announcements or reference-capable multi-hit moves in the admitted action stream;
the existing adaptive inspector completed with zero planned windows. Consequently
3 FPS was not triggered, and there is no per-hit evidence/cost to report. All 36
baseline `per_hit_status` fields are unknown; this is not measured hit-level
coverage or evidence that every unreviewed video moment lacks a multi-hit move.

## Team linkage and form results actually used

The first run records `team_profile_linkage.status=unbound`, reason
`complete_reliable_self_roster_not_available`, `self_rows=0`. No configured
instances or `battle_stats` calculations were injected. The existing
`EventSchedule.acquire_team` reads self rows only during `team_configuration`;
its ordinary `team_preview` branch reads the opponent roster. The reliable-six
attachment guard therefore correctly refuses the incomplete structured input.

Independent post-freeze inspection at 15.003 s confirms the six visible self
members are Venusaur, Charizard, Pelipper, Garchomp, Grimmsnarl and Archaludon,
matching the user-authorized unique Team 7 roster. That evidence was **not** fed
back into first-run state. The linkage problem is acquisition of this already
visible self roster, not absence of a matching saved profile. A separate focused
fix/validation is needed; this benchmark must retain its unbound result.

The observed stone reaction at 221.003 s plus completed Mega result at 230.505 s
correctly resolve self Garchomp to Mega Z (`pokeapi:pokemon:10309`). Saved HP
readings bracketing the Mega event (220.003 and 273.013 s) are both 184/184;
the Mega transition itself does not write HP. Later damage remains separate. Its
potential Team 7 Mega-Z stats are shown above, but were **not runtime inputs**.
Opponent Raichu's stone suffix was read as `丫` rather than `Y`, and the generic
Mega result retains unresolved exact form. No opponent SP, alignment, stats or
replacement form were invented. Resolving/calculating that opponent form is not
part of this focused Team 7 implementation.

## Partial Battle Log comparison

Initial outputs were sealed before error inspection. UI-only selection located
23 saved overlay frames in three windows: **201.000–202.000 s**,
**465.512–473.513 s**, **539.508–540.508 s**. All were visually inspected before
reading production event/receipt contents. Readable rows were transcribed to
[log-transcription.txt](log-transcription.txt), with source IDs, image hashes,
inspection timestamps and UI turn labels in [log-reference.json](log-reference.json).
Its independent freeze is retained in the B23 cache.

There are **84 readable reference rows: 69 semantic messages and 15 numeric HP
rows**. Overlapping screenshots of one row were deduplicated. References cover
parts of displayed turns 1–6, with gaps; they do not establish complete turns or
original event times. This is Codex visual transcription, **not human-reviewed
ground truth**. Unreadable/clipped-only text was not invented.

| Partial-reference measure | Result |
|---|---:|
| Accepted corresponding semantic message records | **65 / 69 = 94.20%** |
| Move execution records within that reference | **21 / 21** |
| Same-instance ordered raw HP endpoint pairs | **15 / 15** |
| Exact before/after/unit aggregate groups | **15 / 15** |
| Exact groups marked complete by the program | **12 / 15** |
| Exact groups marked causally supported by the program | **12 / 15** |

The 65 message rows require 69 distinct accepted receipts: two opening send-out
rows and two multi-recipient stat notices each require two receipts. Chronological
one-to-one matching prohibits reuse across repeated Fake Out, Protect, recovery
or recoil messages. Per UI turn, the message fractions are 10/10, 12/12, 8/9,
12/13, 14/16 and 9/9. These groupings do not certify precise game-turn attribution.

The four missing accepted message records are:

- Turn 3 Garchomp flinching: recognized/emitted at 307.018 s, deferred because
  side is unknown.
- Turn 4 Garchomp Attack/Special Attack drop: recognized/emitted at 351.025 s,
  deferred for the same routing uncertainty.
- Turn 5 Volcarona becoming the center of attention: OCR read the text at
  420.003 s; parser returned unknown and occurrence was not emitted.
- Turn 5 the stronger effectiveness wording `效果无比绝佳！！`: OCR read it at
  425.505 s; parser returned unknown and occurrence was not emitted. The same
  unsupported wording also appears later for Pelipper at 741.508 s, outside this
  partial reference.

The 94.20% metric measures accepted message records, **not complete semantic
field correctness or applied mechanics**. Two reviewed live/log wording
differences are explicit in the scorer: the Raichu stone Y→丫 OCR error and
`对对手`/`对于对手` immunity wording. Stone notices do not encode canonical item
identity, Raichu's exact Mega form remains unknown, and partial move-revelation or
observation receipts do not demonstrate applied effects. No strict text accuracy,
precision, complete decision-state accuracy or full-match reconstruction rate
was measured. Three HP groups (Grimmsnarl 97→85, Raichu 100%→83%, Archaludon
94→106) have correct endpoints but incomplete/ambiguous support; endpoint matches
must not be substituted for causal or hit-level validation.

[log-score.json](log-score.json) contains each matched receipt and HP evidence ID.
Recheck without OCR, decoding or state replay:

```sh
.venv/bin/python docs/mega-b23/score.py
```

## Diagnostics requiring separate fixes

The 30 deferred receipts are **26 occupancy-unresolved HUD readings** and
**4 candidate-field failures**. The HUD readings comprise two at 14.502 s and
24 between 371.530 and 383.032 s, after Grimmsnarl faints and before Archaludon's
observed send-out at 385.532 s. They do not form a persistent tail cascade.
All four candidate failures concern Garchomp: flinch at 307.018 s, joint
Attack/Special Attack drops at 351.025 and 607.002 s, and paralysis-action wording
at 591.500 s. Those literal messages miss the existing explicit side grammar;
`actor_variant_unresolved` also prevents the generic no-uncertainty fallback, and
ApplicationPolicy defers `side_unknown`. The saved OCR exists; these are not
confirmed OCR misses. Stage/status consequences of those records remain unaccepted.

The sole conflict occurs at **695.017 s**: numeric OCR proposes `54/94`, while
the saved source image visibly reads **54/194**. The established maximum 194 is
retained and the conflicting HUD reading is not silently accepted. This is a
localized maximum-HP recognition disagreement, not a Mega stat or HP-restoration
effect.

Incineroar's return at **459.010 s** creates a new encounter and retains a
possible-prior-instance link, with persistent identity `unproven`. Final state
holds the old bench episode at 76% and the active return at 46%. It does not
assert two biological individuals, but it does not establish one unified
persistent HP/item history either. This matches the existing conservative
general return policy; the previous Ditto-specific rule does not extend to it.
No global same-species merge or other unrelated repair was added.

The concrete follow-up items are self-preview profile acquisition/linkage,
literal side routing for the four Garchomp messages, the two unsupported message
wordings, Raichu suffix recognition/exact form, the localized maximum-HP read,
and evidence-backed general switch-return continuity. Evidence and narrow
diagnostic outputs are retained in [issues.json](issues.json); production outputs
were not rewritten.

## Completion and recoverability

Mega implementation paths are `tracking/form_stats.py`,
`tracking/knowledge_grounding.py`, `tracking/state_engine.py`,
`tracking/transformation.py`, `knowledge/data/mega-stat-evidence-v1.json`,
`tests/test_mega_form_stats.py` and `scripts/validate_mega_stats.py`, reusing the
existing stat calculator. On resume these changes already existed; they were
preserved and validated. This resumed work adds this report, compact evidence,
read-only audit/scoring helpers and durable progress under `docs/mega-b23/`.

First-run cache:
`.cache/battles/sample_battle_23/fresh-benchmark/mega-b23-20261030-v1/`.
The original production [viewer](../../reports/battles/sample_battle_23/event-driven/mega-b23-20261030-v1/review.html)
and all heavy outputs remain local. [benchmark-summary.json](benchmark-summary.json)
contains compact production metrics and actual runtime linkage/stat inventory.

Integrity verification passed for **57,342 files**, including **46,627 protected
B16–B22 files** and **10,602 first-run B23 sealed files**, plus adaptive outputs,
implementation/report identities and video. HP projection verified that all 68
nonzero segments occur exactly once and does not mutate authoritative state or
receipts. Reference image hashes, chronological receipt uniqueness, dual-actor
rows and action-scoped HP pairs passed the scoring assertions. No new full-video
or full-state second replay was used. These checks demonstrate preservation and
internal consistency, not semantic acceptance beyond the stated partial reference.

No commit or push; unrelated working-tree edits are preserved. B23 generation
is complete, while runtime team linkage and the documented semantic limitations
remain unaccepted and require separate focused work.
