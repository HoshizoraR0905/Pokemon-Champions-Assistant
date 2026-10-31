# B21 double-faint replacement and command-HUD recovery

Completed 2026-10-29 using the original saved B21 frame, observations, events and a compatible saved state checkpoint. The original frozen predictions, partial Battle Log reference and previous diagnostic outputs remain unchanged.

**192 of the original 194 persistent occupancy deferrals are resolved.** The two remaining receipts occur at 535.506667s, before independent confirmation at 536.006667s. They retain uncertainty; placement is not backdated. This local replay does not establish a new whole-match accuracy or reconstruction rate.

## Behavior and implementation

The global message identity admission threshold remains **0.95**. A complete send-out with a valid canonical candidate below that threshold retains `actor=None`, `actor_unresolved` and a deferred receipt. The existing message-identity metadata now explicitly distinguishes `recognized_candidate`, `admitted` and `unresolved`.

When both slots are vacant following two accepted faints, the existing double-faint state code retains the unconfirmed arrival evidence, anchored to those two faint event IDs. It stores no Pokémon instance or slot for that candidate. `pending_pair` can then supply the verifier with one admitted-but-unplaced arrival and one unconfirmed candidate, or two of either kind. It still requires precisely two arrivals after the same two faints, no occupied slot and no intervening coverage gap. Unrelated or stale candidates do not supply placement.

The existing recognizer waits for the independently detected normal command UI and reads both HUD positions. It resolves each name without roster/active-state hints, reads the existing icon recognizer and applies the existing text/icon combination. It never uses HP to identify the occupant or assumes send-out order determines the side.

The StateEngine checks the whole two-slot bijection before changing state. A candidate-only arrival requires both resolved independent name evidence and an agreeing resolved icon. After verification, it uses the existing `_resolve` instance allocation and `active_continuity.enter/placed` paths. The deferred arrival's original event ID determines the instance ID; the arrival timestamp and evidence are preserved, while species resolution/admission and placement are explicitly recorded at the HUD timestamp. The formerly admitted Rillaboom encounter is reused. Existing persistent-identity/possible-prior-instance policy remains intact.

The recognizer also keeps verification pending when a candidate icon is unresolved, even if strong name text alone would identify the species. A later eligible command frame can retry; the acquisition stop condition shares the StateEngine’s candidate corroboration check. No earlier receipt is silently promoted using future evidence. Retraction of the confirming HUD removes its prospective identity admission and both placements on replay. Incomplete, ambiguous, conflicting, reused or wrongly sourced proof preserves the vacant/unresolved state atomically.

Changed runtime files are limited to:

- `recognition/identity_modes.py`: explicit candidate/admission metadata; unchanged threshold.
- `recognition/double_faint.py`: require the existing normal-command UI check before targeted reads.
- `tracking/double_faint.py`: include retained candidates in the existing pair; validate both identities and admit/place them together through existing allocation/continuity functions.
- `tracking/state_engine.py`: a five-line candidate-evidence audit hook during replay. `_resolve`, `_transition` and other StateEngine methods are unchanged.

No new runtime module/framework was added. Ordinary single-replacement behavior remains unchanged. Recovery, move-miss, Confusion, Struggle, damage, sampling and performance implementations were not modified.

## Original saved command frame: recognition actually executed

Source: `.cache/battles/sample_battle_21/event-driven/fresh-b21-context-v1/frames/001062.png`, timestamp **536.0066666666667**, source ID `tests/fixtures/sample_battle_21.mp4#536.0066666666667`.

The source PNG hash was checked before recognition: `95ff67db8d8348816abc7b571d3c585ba9d5fdfadd7f870169533b785ddf327f`. The existing `inspect_command` and `independent_cards` functions detected the normal command screen/card geometry from these pixels. The report or user-supplied placement was not used as recognition input.

| Opponent HUD slot | Independent raw name OCR | OCR confidence | Independently resolved icon | Top icon similarity | Combined result |
|---|---|---:|---|---:|---|
| left | 姆克鹰 | 0.999 | species 398, `pokeapi:pokemon:398` | 0.93645 | `text_icon_agreement`: Staraptor |
| right | 轰擂金刚猩 | 0.998 | species 812, `pokeapi:pokemon:812` | 0.86593 | `text_icon_agreement`: Rillaboom |

Both text resolutions were independently `exact` before combination. Icons used the existing `masked_multiscale_template` recognizer, source commit `4953be0b8f2eee5415255c4e0bb2bdec6065c75b`. Similarity and OCR scores are recognizer scores, not identity probabilities.

The first validation run (v1) executed **two name OCR invocations**, **two HUD icon reads**, and **four icon computations** across the existing default/silhouette profiles. Both sources were genuinely executed and available for both assignments. Final v2 validation reused those exact source-pixel/model-keyed recognition outputs (two OCR cache hits and four icon-profile cache hits), rather than repeating inference. No full-video decoding/OCR or production CLI was run. HP values 100% and 21% were taken from the existing saved HP observations only after placement; they did not establish identity.

## Saved-data transitions and remaining events

| Video seconds | Saved event / evidence | Result |
|---:|---|---|
| 488.031667 | Ceruledge faint, `event:73f2b180653f1dcc82b4d7ba` | remains `applied_candidate`; opponent right becomes vacant |
| 510.020000 | Milotic faint, `event:c919147072664a1e53b1c439` | remains `applied_candidate`; both opponent slots vacant |
| 522.005000 | Rillaboom send-out, `event:9e867544de4c07e667694ba1` | admitted identity retained as unplaced encounter `8c8e06a289acb7f8`; no slot inferred |
| 526.505000 | Staraptor send-out, `event:f155150e38450eb678b7058b`; message confidence 0.9471874999999998 | canonical species-398 candidate retained; actor/identity admission deferred; no Staraptor instance created yet |
| 535.506667 | opponent right `event:5343d383539a9712b9aca06b`, left `event:61b9e04002119fc4b89ed50d` | both remain deferred: `message_episode_occupancy_unresolved` |
| 536.006667 | independent command-HUD name/icon pair | atomic confirmation: left Staraptor `0204227741816acc`, right Rillaboom `8c8e06a289acb7f8` |
| after confirmation | 192 original occupancy-deferred HUD receipts | admitted with the recovered active instances |

Instance suffixes above have prefix `sample_battle_21:opponent:encounter:`. The candidate becomes `hud_confirmed` at 536.006667, with its original send-out evidence retained. No second Staraptor encounter is created on replay. The original Staraptor message receipt remains deferred at its original prefix; the HUD receipt separately records its supported later admission.

The placement also allows eight originally deferred semantic receipts to bind:

| Video seconds | Event | Result |
|---:|---|---|
| 571.013 | Staraptor Mega Evolution | `applied_candidate`, same Staraptor instance |
| 583.515 | Rillaboom Fake Out | `applied_partial`, existing move-revelation path; correct instance |
| 587.515 | Staraptor Close Combat | `applied_partial`, existing move-revelation path; correct instance |
| 593.517 | Rillaboom named HP recovery | `recorded_observation`; existing recipient/recovery implementation reused |
| 651.527 | Rillaboom faint | `applied_candidate`, recovered right-slot instance |
| 655.527 | Staraptor Close Combat | `applied_partial`, same Staraptor instance |
| 660.512 | Staraptor stat-change message | `applied_candidate`, same Staraptor instance |
| 684.532 | Staraptor faint | `applied_candidate`, recovered left-slot instance |

Partial move admission establishes revealed move membership through the existing path; it is not a claim of complete target/damage reconstruction. No damage mechanic was changed. The saved wording of the stat event was not mechanically reinterpreted in this task.

The affected suffix has **205 → 5 deferred receipts** in the no-proof control versus the recovered replay: the two pre-confirmation HUD receipts, the original low-confidence Staraptor send-out, and the pre-confirmation abilities at **530.506667** (Staraptor Intimidate) and **533.006667** (Rillaboom Grassy Surge). Those ability receipts remain unresolved at their historical prefixes; this task does not backfill their effects using later placement. Later HP observations, transformation, moves and faints do use the confirmed instances. The earlier six temporary replacement-gap deferrals are outside this recovery window and unchanged.

## Validation and stability

The scoped validator reused the prior completed focused checkpoint through **435 seconds**: before that time neither side had the qualifying double-faint candidate state. The new candidate audit therefore has no applicable earlier state transition. Checkpoint files and their completed-manifest hashes were verified unchanged.

It then processed the necessary **673 original suffix events**, with a 280-event prefix to establish the pending pair. It compared a no-proof control with a recovered replay, adding the new frame-local `double_faint_hud` proof to only the two original 536.006667 HUD events. All original event IDs and relative ordering are preserved; no hand-written identity or new send-out event is inserted. Successful recognition, candidate checkpoint, replay and comparison outputs are durable, with a manifest and progress records. Final v2 preserves v1 and reuses its compatible candidate-prefix/control results: input/seed hashes, relevant source hashes, unchanged candidate/pair function ASTs and completed output hashes are checked. The retry-only change cannot affect the no-proof control. The final 673-event recovered replay was rerun; its output is byte-identical to v1.

Stability checks found:

- Both original faints remain accepted with their original instances.
- All **468 originally accepted suffix receipts** retain status and actor bindings against the frozen replay.
- All **390 originally accepted numeric suffix HP observations** retain event ID, Pokémon instance, endpoint value, unit and maximum against the frozen BattleState ledger.
- Against the no-proof control, all **497 existing numeric observations** including the reused seed remain unchanged; the recovered replay adds 192 supported HUD observations.
- Previously admitted Rillaboom remains the same encounter. Staraptor is admitted only at verification; original identity is preserved through its later Mega Evolution. No existing Pokémon identity is overwritten to satisfy a mapping.
- Frozen observation/prediction/replay/HP benchmark hashes, partial Battle Log reference hash and previous focused diagnostic output hashes remain unchanged.
- Ten protected mechanics/continuity/sampling source files match their task-start hashes. Only `StateEngine.replay` changed among StateEngine methods. No commit or push occurred.

This verifies the affected suffix and reuse of the earlier checkpoint, not a new full-prefix recognition run, global accuracy measurement or official-mechanics acceptance milestone.

Validation results: the integrated regression run passed **257 tests** (two FFmpeg sampling tests deliberately deselected); the separate active-persistence suite passed **24 tests**. After the retry refinement, the final candidate/double-faint/acquisition run passed **29 tests** (including all **13** candidate-workflow cases; two sampling tests deselected). `git diff --check` passed. These runs overlap and are not added together as independent accuracy samples.

Focused candidate tests cover one/two deferred candidates, no pre-HUD encounter/placement, complete pair confirmation, deterministic instance allocation, retraction, missing name/icon, conflicting/partial/reused/wrong-source proof, incomplete announcements, ordinary single replacement, and waiting for normal command UI. Existing double-faint, identity, switch/continuity, HP, recovery/miss and Confusion/Struggle tests are included in the regression commands below. Sampling/FFmpeg tests are deliberately deselected; no sampling implementation changed.

```sh
.venv/bin/python -m pytest -q -m 'not local_artifacts' tests/test_double_faint_candidates.py tests/test_double_faint.py tests/test_identity_modes.py tests/test_recognition_cleanup.py tests/test_evidence_fusion.py tests/test_switch_continuity.py tests/test_b21_recovery_miss.py tests/test_semantic_state.py tests/test_hp_attribution.py tests/test_hp_resolutions.py tests/test_sequential_resolution.py tests/test_confusion_struggle.py -k 'not ffmpeg'
.venv/bin/python -m pytest -q -m 'not local_artifacts' tests/test_active_persistence.py
.venv/bin/python scripts/validate_b21_double_faint.py --run-id double-faint-hud-20261029-v2 --reuse-run-id double-faint-hud-20261029-v1
```

The final saved-data command reuses completed output only with matching source/input/output identities. A changed implementation requires a different diagnostic run ID; it refuses to overwrite this run.

Local artifacts:

- [Recognition outputs, original frame linkage and acquisition counts](../../.cache/battles/sample_battle_21/diagnosis/double-faint-hud-20261029-v2/command-hud-recognition.json)
- [Before-HUD state: candidate retained, slots unresolved](../../.cache/battles/sample_battle_21/diagnosis/double-faint-hud-20261029-v2/before-hud.json)
- [Per-event recovery comparison and remaining receipts](../../.cache/battles/sample_battle_21/diagnosis/double-faint-hud-20261029-v2/comparison.json)
- [Original accepted-receipt/HP stability checks](../../.cache/battles/sample_battle_21/diagnosis/double-faint-hud-20261029-v2/original-stability.json)
- [Frozen/protected-file integrity checks](../../.cache/battles/sample_battle_21/diagnosis/double-faint-hud-20261029-v2/integrity.json)
- [Completed stage manifest](../../.cache/battles/sample_battle_21/diagnosis/double-faint-hud-20261029-v2/manifest.json)
