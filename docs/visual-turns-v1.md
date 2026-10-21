# Normal-screen visual turns and effect counters, v1

The `battle_evidence` package accepts temporal normal-screen evidence without Battle Log. The offline entry point is:

```sh
.venv/bin/python -m battle_evidence.visual_offline --battle 9
```

Run one battle at a time. The command requires the preserved M3.4 index at `.cache/m34e/battle-index.json` and the selected recognition observations/PNGs. It does not run StateEngine, decode recordings, open a database, or change source events. `BattleArtifacts` validates recording ownership. Outputs live under `.cache/battles/<battle_id>/m34-visual/<fingerprint>/`. The validation report identifies the selected results.

## Phase model

| Logical phase | Evidence and interpretation |
| --- | --- |
| PRE_BATTLE | Existing team-preview/configuration UI classification; no turn assignment. |
| INITIAL_SENDOUT | Recorded send-out before the first established command anchor; no increment. |
| NORMAL_COMMAND | Native Fight and Pokémon controls plus four independent HUD cards, sustained across observations. |
| COMMAND_SUBMENU | Menu navigation within an existing command; an isolated message or COMMAND label does not close it. |
| TURN_RESOLUTION | Live move-execution announcements while ordinary controls/overlays are absent; persistence through animations does not create boundaries. |
| FORCED_SELECTION | Selection with pending faint/pivot evidence, or a menu without established ordinary-command continuity. Conservative classification can remain unresolved. |
| POST_TURN_TRANSITION | A candidate command return after resolution, or an observed terminal result. |
| UNKNOWN | Missing, unsupported or conflicting visual evidence; no invented action or boundary. |

`VisualPhaseEstimator` requires an established command → live resolution → established next command sequence. A normal anchor may persist into immediate ordinary command/menu context with a timer and independent HUD/menu evidence. That persistence always starts from the two native controls; it cannot bootstrap from COMMAND alone. Opening/closing submenus produces no increment. The pressed yellow Fight variant is recognized in `visual_controls.py` using a confined native annulus/emblem, the independently detected Pokémon control and four HUDs. Recognition's existing detector is unchanged.

Two distinct execution announcements are required for the strongest segment status. More than four distinct executions without another command anchor are marked ambiguous because a missed command phase or an extra-execution mechanic needs review. Four is a conservative ambiguity guard, not an asserted Champions maximum. Actor/move identity may remain candidate evidence even when the phase segment is confirmed.

Faints/pivots require resolution of the pending selection. Ordinary move menus after resolution without an observed new native command anchor remain transition candidates with widened boundary intervals. They are not called forced replacements. These candidates, unresolved selection returns, insufficient execution evidence and observation gaps produce `supported_but_incomplete`; counter conflicts or possible merged cycles produce `ambiguous`. Unknown intervals remain in phase history. Each segment retains frame/event IDs, start/end video-time bounds, competing-interpretation reasons, interruptions, gaps and counter constraints. Absolute game-turn numbers remain null. Local indices are labels for observed segments, not a count of the whole battle. An observed battle result freezes inference and leaves any terminal resolution incomplete.

The current native-layout policy requires four HUDs. Late battles with fewer visible combatants, rapid menu entry and unsupported layouts may have no complete next-command anchor. The maximum tolerated consecutive-observation interval is 1.6 s; missing cached PNGs are also gaps. These settings are recorded in the manifest. Frame density alone does not establish semantic coverage.

## Counter observations and semantics

`parse_counter` accepts exact named labels and a valid fraction only inside the native field region `(265, 26, 562, 154)`. The implemented reader uses the shared first row: existing separate label/fraction OCR is preferred; a missing region can use one bounded `(265,26,562,61)` crop, at most 40 per battle. It does not scan arbitrary screen fractions, HP, PP or timers. Different effects rotate through that first row; no absence assertion is made when another label is shown.

Every parsed reading retains its raw text/display, numerator, denominator, effect, scope, semantic evidence, inferred elapsed turns, displayed remaining, revealed total, possible actual totals/remaining, source frame/timestamp, confidence and confirmation sources. A second distinct frame within 4 s with the same fraction and confidence at least 0.9 confirms the current reading. Earlier records are immutable. Identical reads reinforce confidence and have elapsed delta zero.

| Effect | Current semantic policy | Limits |
| --- | --- | --- |
| Rain | User first-hand remaining-count assertion; `elapsed = denominator − numerator`. B8 opening rain followed by 5/5 before moves corroborates zero elapsed. Source-supported total candidates are 5 and 8. | A base display does not reveal the actual total or an item. No actual 0/5→3/8 sequence was observed here. |
| Trick Room | Remaining-count interpretation individually corroborated by B9 activation and 4/5→3/5→2/5 across independent command segments; fixed total 5 uses the existing documented duration policy. | Activation text remains a recognition candidate; this is UI semantic corroboration, not re-certification of all source events. |
| Tailwind | Individually corroborated by B7 activation message and 3/4→2/4 across the local command boundary; fixed total 4 uses the existing duration policy. | Unprefixed UI labels have unknown side. A matching candidate activation does not authorize copying the count onto both sides. |
| Sandstorm, sun, terrain, screens | Preserve exact observed fractions and temporal confirmation. | Their complete elapsed mapping, extension behavior and/or side binding remain unverified. Decreasing fractions are reported as observations, without borrowing rain's domain. |

For rain, `2/5` yields elapsed 3 and possible actual remaining `[2,5]`; `0/5` yields elapsed 5 and `[0,3]`. Both remain visible-effect observations. A later `3/8` yields elapsed 5 and revealed total 8; it supplies no extra elapsed turn. The controlled `2/5→1/5→0/5→3/8` fixture is explicitly user-described. New denominators do not overwrite prior readings. Counter regression starts an unresolved new epoch rather than asserting reactivation or inventing negative elapsed turns.

`reconcile_segments` compares independently confirmed same-effect readings during the command contexts (up to the next live execution, to allow label rotation). One elapsed turn corroborates a proposed boundary; conflicting deltas downgrade it. Activation/expiration or counter-epoch changes withhold the relation. A multi-turn counter delta across a gap is stored as one qualified relationship, never fabricated individual action histories.

## Existing evidence integration

`TurnReconstruction.attach_visual` attaches confirmed local segment membership to existing immutable event IDs, rejects cross-battle/overlapping segments and preserves inactive/revised sources. It does not certify execution order, order decisions or absolute game numbers. Existing numbered memberships remain authoritative.

`EffectDurations.observe_ui_counter` adds counter history and UI support without changing activation identity/timestamp, source-derived remaining support, or observed expiration. Unknown-side counters do not update either side. `advance_visual_boundary` supports a separate relative duration clock using verified activations and existing documented rules across contiguous confirmed local segments. It broadens uncertainty on broken continuity. Candidate activations do not become verified because a phase test passed.

`action_snapshot_overlays` references the existing before/after snapshot IDs and carries local turn membership, causal UI observations and duration state. Original snapshot bytes/IDs are preserved. An older counter is explicitly last-observed evidence; its current remaining support is withheld rather than carried forward by seconds. Future counter reads never enter an earlier action overlay. The original engine replay-validation limitations are copied into every overlay.

M3.4.1 receives local membership through its existing adapter. Absolute order-decision timing, actor/move/priority verification, configured own Speed and modifier continuity still gate updates. The adapter reports these missing inputs rather than inventing a game turn number, build or neutral modifier. No M3.3 prior is loaded. The offline cache currently accepts the original empty-build pilot; a source containing build bindings without serialized records fails explicitly instead of silently dropping them.

## Cache and resume behavior

Manifests record source hashes, implementation dependencies, model manifest/OCR implementation, detector version, reader policy, stage, progress, metrics and output hash. Successful geometry/raw-OCR checkpoints are reused across interpretation changes. Cached detector inspections from older versions are refreshed; already compatible detector results and raw OCR are retained. Checkpoints write atomically every 100 observations and after extraction; failures record their error. Cached interpreted actions/event flags are cleared before each reconstruction to prevent duplicate execution evidence.

Re-run the same scoped command to resume the first incomplete stage or reuse a completed result. A disconnect is not an invalidation reason. Older output directories remain intact; the selected index is `.cache/m34-visual/battle-index.json`. No historical caches are deleted or rewritten.

Focused validation:

```sh
.venv/bin/python -m pytest -q tests/test_visual_evidence.py tests/test_battle_evidence.py tests/test_speed_inference.py
```

The controlled tests cover menus/Encore-style messages, pivots/faints, missing frames, terminal battles, source revisions and isolation, causal counters, extension reconciliation, conflicts, duration clocks and replay-safe feature reuse. The optional local-artifact case checks the actual pressed Fight frame. Test success does not measure recognition accuracy; see the real-data report.
