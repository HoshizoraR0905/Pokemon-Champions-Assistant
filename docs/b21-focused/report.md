# B21 focused recovery/miss fixes and occupancy diagnosis

Completed 2026-10-29. The occupancy diagnosis is read only; no occupancy repair was attempted. No video decoding, OCR, benchmark/reference overwrite, commit or push occurred.

## Focused result

The eight specified recovery events now bind their explicitly named recipient and are admitted as `recorded_observation`. The saved miss now produces a target-bound `move_miss`, associated with Milotic's Hypnosis. This recovers **nine specific semantic records**, not a newly measured whole-match accuracy.

All eight recovery messages individually satisfy the requested conditional `grassy_terrain` attribution. Four observed command cycles establish the resolution context; the four original occupants have each executed an action, switched out or fainted before these messages. Terrain is observed active, and no separate explicit recovery source is associated with these eight occurrences. The later Leftovers recovery and earlier Sitrus recovery remain separate.

Numerical HP reconstruction is a separate result: **six** of these recoveries have supported final endpoints and deltas. Two retain an unknown numeric delta because the existing final-plateau requirement is not satisfied within their supported resolution windows. Qualitative cause does not manufacture an HP amount.

| Video seconds | Original message (line breaks omitted) | Before → after semantic status | Conditional cause | Saved endpoint values | After: supported numeric delta |
|---:|---|---|---|---|---|
| 192.515 | 对手的轰擂金刚猩的体力回复了！ | deferred / actor unknown → recorded / Rillaboom | grassy_terrain | 69% → 74% | +5 percentage points |
| 196.017 | 长毛巨魔的体力回复了！ | deferred / actor unknown → recorded / Grimmsnarl | grassy_terrain | 6 → 18 HP | +12 HP |
| 251.525 | 铝钢桥龙的体力回复了！ | deferred / actor unknown → recorded / Archaludon | grassy_terrain | 168 → 180 HP | unknown: final plateau unresolved |
| 255.027 | 对手的轰擂金刚猩的体力回复了！ | deferred / actor unknown → recorded / Rillaboom | grassy_terrain | 74% → 80% | unknown: final plateau unresolved |
| 322.005 | 铝钢桥龙的体力回复了！ | deferred / actor unknown → recorded / Archaludon | grassy_terrain | 192 → 194 HP | +2 HP |
| 325.505 | 对手的轰擂金刚猩的体力回复了！ | deferred / actor unknown → recorded / Rillaboom | grassy_terrain | 15% → 21% | +6 percentage points |
| 426.522 | 对手的苍炎刃鬼的体力回复了！ | deferred / actor unknown → recorded / Ceruledge | grassy_terrain | 30% → 36% | +6 percentage points |
| 430.022 | 对手的美纳斯的体力回复了！ | deferred / actor unknown → recorded / Milotic | grassy_terrain | 54% → 60% | +6 percentage points |
| 318.503 | 没有击中铝钢桥龙！ | provisional_or_repeat / no event → recorded move_miss | Hypnosis missed Archaludon | no damage event | none generated |

The endpoint-values column reports saved observations/reference values, including the two whose finality the program still cannot certify. It is not a claim that all eight numeric resolutions are accepted. Before the fix, the six now-supported positive changes had ambiguous ordinary-move contexts, with `move_effect_or_self_cost_not_established`; their causes were unknown. Afterwards their parent is no longer that ordinary move and their supported cause is Grassy Terrain. The two remaining unknown deltas were not filled using a fraction of maximum HP. The additional observed command boundary at 271.512 precedes the Battle Log UI interval; the 279.030 boundary is the relevant subsequent action-cycle start.

The saved chronological recovery order is retained: Rillaboom → Grimmsnarl; Archaludon → Rillaboom; Archaludon → Rillaboom; Ceruledge → Milotic. These are observed sequences, not definitive Speed stats or a complete Speed ranking.

## Implementation and resolution evidence

The possessive recovery pattern previously passed `长毛巨魔的` (and analogous names) into identity resolution. The localized grammar fix removes the possessive marker and reuses canonical names, side-owned aliases and active-instance resolution. It does not change the resolver or persistent identity policy.

`没有击中X！` uses the existing parser and occurrence pipeline, with X as target and no invented attacker. The original 318.503333 observation has confidence about 0.994. New event `event:dd98e1802abab333f8793c35` retains the source observation/image/hash and occurrence evidence, and links to the existing 317.003333 Hypnosis execution `event:a4ef99378be752cd59034d61`. Its target is Archaludon instance `8da0c8381a7b4b3f` (full IDs have prefix `sample_battle_21:self:encounter:`). That target is blocked from damage attribution for this missed action. Retraction removes the derived miss outcome.

Normal four-HUD command sessions now contribute an existing `phase_observation`, with the active participant IDs recorded in its receipt. This is an observed command-cycle boundary, not an invented game-turn number. The existing resolution/HP code checks completion of all four original participant actions before deriving end-of-turn recovery:

| Command-cycle start | Evidence that original participants have finished | Recovery messages checked |
|---:|---|---|
| 128.005 | Garchomp Protect; Grimmsnarl Light Screen; Rillaboom Wood Hammer; Milotic Ice Beam | 192.515, 196.017 |
| 198.517 | Garchomp withdraws 226.022; Rillaboom Grassy Glide 234.523; Grimmsnarl faints 237.523; Milotic Ice Beam 241.523 | 251.525, 255.027 |
| 279.030 | Archaludon Dragon Pulse 300.000; Rillaboom Wood Hammer 306.018; Pelipper faints 311.002; Milotic Hypnosis 317.003 and miss 318.503 | 322.005, 325.505 |
| 335.007 | Rillaboom withdraws 360.510; Garchomp Earth Power 387.515; Archaludon Electro Shot 395.517; Milotic Ice Beam 417.520 | 426.522, 430.022 |

Repeated action readings do not add participants or create additional terrain recoveries. A replacement sent after an original occupant's action does not receive a second turn action in this proof. No timestamp timeout determines these boundaries.

The attribution requires active Grassy Terrain, a supported end-of-turn resolution and no associated explicit recovery source. It records one terrain recovery per instance per resolution. Inactive/ended terrain, incomplete action cycles, duplicate notifications, an explicit item source, and unresolved current healing/status actions do not get forced into terrain attribution. A previously consumed item notification is not reused as a new recovery source.

All eight B21 HP animations precede their named recovery message. The existing projection can rebind the one preceding recipient-specific increase within the Battle Message window, without generating a second change or summing animation frames. Later unchanged saved HP reads may confirm that same endpoint before another possible action/source. If finality is unsupported, delta remains unknown. The independent Archaludon Leftovers banner at 257.027 supplies its separate 180 → 192 recovery; Milotic's Sitrus supplies 29% → 54% before its 54% → 60% terrain recovery.

The existing versioned knowledge supplement records the narrowly requested attribution contract. [52Poké's Grassy Terrain status article](https://wiki.52poke.com/wiki/青草场地（状态）), revision 2566979, describes general end-of-turn recovery; the [move article](https://wiki.52poke.com/wiki/青草场地（招式）), revision 2553663, includes a Champions description row. Retrieved 2026-10-29, CC BY-NC-SA 3.0. The general status mechanics are distinguished from Champions-specific documentation and the user's requested conditional contract. No healing fraction, groundedness, duration or Speed inference is added; runtime requires no network access.

Changed implementation: `battle_events/{message_patterns,parser,schema}.py`, `recognition/event_report.py`, `tracking/{state_engine,evidence_fusion,hp_causes,resolution_context}.py`, and the existing `knowledge/data/52poke-resolution-v1.json` supplement. New focused tests and saved-data validation commands are listed below. No new runtime module or identity framework was introduced.

## Earliest occupancy failure and persistent cascade

There are **219 original frozen deferred receipts**, of which **200** have reason `message_episode_occupancy_unresolved`. Exactly **194** occur after 441 seconds; their actual first timestamp is **535.506667**, not 441 seconds.

The literal first occupancy deferral is **261.526667**, `event:d2e2058df33d6286009c7ae4`, a self/right HUD observation. Immediately before it, self/left is Archaludon `8da0c8381a7b4b3f`, self/right is vacant following Grimmsnarl's accepted faint at 237.523333; opponent/left is Milotic `4adb8c1aecada18d`, opponent/right is Rillaboom `91d36e50fc00a60f`. There are three such deferrals through 262.528333. Pelipper's accepted send-out at 264.528333 fills the sole vacancy and resolves this gap. Another three self/right deferrals at 328.505–329.522 occur between Pelipper's accepted faint at 311.001667 and Garchomp's accepted send-out at 331.005. These six are independent, temporary replacement intervals, not the cause of the final 194.

The earlier recovery actor errors at 192–430 seconds are grammar errors in HP messages, not evidence of incorrect persistent Pokémon identities or an unresolved occupancy cascade.

The persistent issue is exposed by the opponent's double replacement:

| Video seconds | Raw Battle Message / parsed event | Frozen receipt and resulting StateEngine placement |
|---:|---|---|
| before 488.032 | active occupants | self: Archaludon left `8da0c8381a7b4b3f`, Mega Garchomp right `47284d42682f9642`; opponent: Milotic left `4adb8c1aecada18d`, Ceruledge right `883748d6f254f67e` |
| 488.031667 | `对手的苍炎刃鬼倒下了！` / faint, `event:73f2b180653f1dcc82b4d7ba` | applied_candidate; opponent right becomes vacant |
| 510.020000 | `对手的美纳斯倒下了！` / faint, `event:c919147072664a1e53b1c439` | applied_candidate; opponent left becomes vacant; `opponent.active_slots={}` |
| 522.005000 | `MingYeezy\n派出了轰擂金刚猩！` / send_out, `event:9e867544de4c07e667694ba1` | recorded_observation; canonical actor accepted; encounter `8c8e06a289acb7f8` created as unplaced, slot=None, `named_entry_slot_unresolved`; both vacancies remain |
| 526.505000 | `MingYeezy\n派出了姆克鹰！` / send_out, `event:f155150e38450eb678b7058b` | deferred / unresolved_candidate_fields / actor_unresolved; no second unplaced Pokémon/entry episode created |
| 530.506667 | `姆克鹰的威吓` / ability_activation | deferred; active_identity_context_unresolved plus actor_variant_unresolved |
| 533.006667 | `轰擂金刚猩的青草制造者` / ability_activation | deferred; active_identity_context_unresolved; separate explicit terrain-change message still applies |
| 535.506667 | opponent left and right HUD readings, `event:5343d383539a9712b9aca06b`, `event:61b9e04002119fc4b89ed50d` | first persistent occupancy deferrals; neither slot has an admitted occupant |
| through 684.531667 | later HUD, moves, transformation and faints | opponent slots remain empty; final occupancy deferral `event:a5381155aea195e0a89ca457` |

For opponent instance suffixes, the full prefix is `sample_battle_21:opponent:encounter:`. Raw messages, evidence IDs, confidence, parsed identity candidates, original receipt decisions and compact before/after transition snapshots are saved in the diagnosis artifact linked below.

At **522.005**, the StateEngine correctly refuses to infer which of two vacant slots Rillaboom occupies from a single send-out. This is the first placement ambiguity in the persistent sequence. It is not proof that send-out order equals slot order.

At **526.505**, the complete Staraptor send-out text is recognized, and `attributes.message_identity.identity` contains the canonical species-398 candidate. However, `recognition/identity_modes.py:message_identity` sets actor only when the complete reading has confidence ≥ 0.95. This observation's confidence is **0.9471874999999998**. Consequently the production event is still a parsed `send_out`, but its actor is cleared and the policy defers it. This is an identity-admission failure, **not an absent send-out parser rule**. No Staraptor encounter/active-entry episode is admitted. Its species/form ambiguity is also preserved rather than silently filled.

That admission loss prevents the existing two-replacement HUD recovery from running. `tracking/double_faint.py:pending_pair` requires two admitted unplaced named entries after the two accepted faints. Only Rillaboom exists. B21's original counters show 18 prefix observations, 17 avoided replays and one candidate prefix replay of 982 events. The scheduler therefore did notice the two literal replacement announcements; the authoritative replay nevertheless yielded no eligible pair. No double-faint HUD name/icon evidence was produced. This is not a claim that the verifier was never scheduled.

Ordinary lightweight HP HUD observations contain `species={}` and `icon=None`. Their numerical bars cannot manufacture missing occupant identities. There are no frozen `command_checkpoint` events supplying an independent placement proof. `active_slots={}`, one unplaced Rillaboom and the missing Staraptor entry therefore persist, causing the 194 later HUD deferrals. Later Rillaboom/Staraptor moves, Mega Evolution and faints encounter the same missing-active-context problem. Of the 19 non-occupancy deferrals, eight are the early recovery grammar failures fixed here, one is the root Staraptor send-out, nine later records have missing active context (including Staraptor form uncertainty), and one is the 593.517 possessive recovery with its separate grammar limitation. These are not 194 independent slot transitions. The 593.517 message is outside the nine-record fix validation window.

No incorrect persistent identity merge is established here. In particular, creating an unplaced returning Rillaboom encounter does not prove a forced merge with its earlier encounter; the policy preserves the prior-instance candidate. This task does not change that policy.

## Existing placement evidence is sufficient for a future repair

Human inspection of the already saved **536.006667-second command frame**, `frames/001062.png`, clearly shows opponent HUD **left Staraptor 100%, right Rillaboom 21%**, with distinct names/icons. Own left is Archaludon 194/194 and right Mega Garchomp 83/184. This is direct screen-HUD placement evidence, not an inference from send-out order or camera positions.

The corresponding saved observation has `command_inspection.reason=normal_four_hud_command` and all four visible HUD slots. Its lightweight structured cards contain HP only and no species/icon identities. Thus the saved image is sufficient for targeted placement verification in a future task, but the frozen structured evidence does not already contain an admitted two-entry placement proof. No OCR was rerun, no threshold lowered, no entry supplied manually to StateEngine and no slot was assigned in this task.

## Validation, frozen integrity and reproducibility

- Focused tests cover recovery grammar for both sides, terrain/end-of-turn gates, all-four action completion, inactive/ended terrain, explicit item precedence, once-per-resolution recovery, observed sequence, late messages after HP animation, later unchanged endpoint confirmation, unknown HP, missed target binding, action association, no missed-hit damage, retraction and normal command-session boundaries.
- Integrated portable regression command below passed **322 tests**. The additional command-session regression also passed in the final **16-test** focused run (323 distinct passing checks across those runs). No optional artifact test was silently accepted as missing.
- Focused saved-event replay preserves **177 original event payloads/IDs**, adds five observed command-cycle markers and one miss, and processes **183 events** through 435 seconds. It does not replay the entire match or revise the frozen predictions. The immutable initial state and necessary original identity/field/action context are retained; numeric HUD sampling retains first/last edges of each unchanged value run.
- Read-only diagnosis separately projects **37 original identity transitions**, with final slot mappings checked against the frozen BattleState. These compact snapshots are explicitly an identity-transition projection, not complete HP/mechanics snapshots. The original 1,384 frozen receipts remain authoritative for counts and receipt decisions.
- Original observations, replay, video-only predictions and benchmark HP resolutions match their initial-freeze SHA-256 values. The partial reference remains SHA-256 `5408c618f1d1b4696e86cea7082bbae404fd3f31f37af2ad1d0a8580e84c1bac`.
- Protection checks confirm the occupancy/continuity/persistence/identity-ledger/double-faint/identity-mode/fast-video files and `StateEngine._resolve` AST are unchanged relative to task start. Existing unrelated dirty work is preserved.

```sh
.venv/bin/python -m pytest -q -m 'not local_artifacts' tests/test_b21_recovery_miss.py tests/test_semantic_state.py tests/test_evidence_fusion.py tests/test_hp_attribution.py tests/test_hp_completion.py tests/test_hp_resolutions.py tests/test_sequential_resolution.py tests/test_confusion_struggle.py tests/test_preview_switch_fixes.py tests/test_double_faint.py tests/test_event_driven.py tests/test_scrolling_semantics.py tests/test_banner_hp_tracking.py
.venv/bin/python scripts/validate_b21_focused.py recovery-miss-occupancy-20261029-v3
.venv/bin/python scripts/diagnose_b21_occupancy.py
```

The validation command reuses a completed run only when inputs, relevant implementation hashes and outputs match. It refuses to overwrite an incompatible run. Earlier v1/v2 diagnostic outputs remain preserved as development checkpoints; v3 is the final focused validation. The final regression command now includes the additional focused test and would collect 323 checks.

Local outputs:

- [Nine-message before/after details and HP episodes](../../.cache/battles/sample_battle_21/diagnosis/recovery-miss-occupancy-20261029-v3/focused-summary.json)
- [Focused replay manifest](../../.cache/battles/sample_battle_21/diagnosis/recovery-miss-occupancy-20261029-v3/focused-manifest.json)
- [Frozen integrity checks](../../.cache/battles/sample_battle_21/diagnosis/recovery-miss-occupancy-20261029-v3/frozen-integrity.json)
- [Original occupancy receipts and transition snapshots](../../.cache/battles/sample_battle_21/diagnosis/recovery-miss-occupancy-20261029-v1/occupancy-diagnosis.json)
- [Saved command HUD frame](../../.cache/battles/sample_battle_21/event-driven/fresh-b21-context-v1/frames/001062.png)

Remaining limitations are the two uncertified numeric recovery deltas and the unchanged occupancy failure. Full-match semantic acceptance and a new reconstruction rate were not measured. Work stops before the occupancy fix.
