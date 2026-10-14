# Per-battle artifact migration

Recordings are registered independently as `sample_battle_0` through `sample_battle_4`. The user-authorized rename `sample_battle_5.mp4 → sample_battle_4.mp4` is complete. `sample_battle.mp4` is a compatibility symlink to recording 0, not another recording. Five distinct video files are present; no video decoding/OCR was performed during migration or validation.

## Canonical locations

| Battle | Cache namespace | Report namespace | Migrated material |
| --- | --- | --- | --- |
| `sample_battle_0` | `.cache/battles/sample_battle_0/` | `reports/battles/sample_battle_0/` | Original M1.4 frame cache, original-sample timelines/review, attributed target overlay, per-video annotation projection |
| `sample_battle_1` | `.cache/battles/sample_battle_1/` | `reports/battles/sample_battle_1/` | M1.4 frames/workflow evidence, M1.5 clip cache, single-recording run traces/metrics and attributed ROI overlays |
| `sample_battle_2` | `.cache/battles/sample_battle_2/` | `reports/battles/sample_battle_2/` | M2 alignment/log/trainer caches, M2.1 OCR/events/truth, M2.2 initial state, snapshots, replays, mechanics/timelines/reports |
| `sample_battle_3` | `.cache/battles/sample_battle_3/` | `reports/battles/sample_battle_3/` | Survey/extractions/OCR/HUD caches, M2.2.3–M2.3.1 events, snapshots, hidden constraints, timelines, metrics, reports, opening configuration and annotations |
| `sample_battle_4` | `.cache/battles/sample_battle_4/` | `reports/battles/sample_battle_4/` | Recording manifest and isolated directories; no analysis invented for this new recording |

Each report namespace contains `battle.json`, recording its canonical ID, video path and owned directories. Inputs live under `inputs/`. Shared species/form/move/ability/item/rules data and model weights/environments remain outside these namespaces. The opening configuration for recording 3 is now `reports/battles/sample_battle_3/inputs/opening_team.json`; `data/teams/my_team.json` remains unchanged and shared.

The machine-readable inventory in `battle-artifact-migration.json` lists **147 moved paths**, original addresses, canonical addresses and pre-move checksums for files. Existing directories were renamed locally, not decoded or copied frame by frame. Attributable entries from mixed M1.4 annotations are projected into each battle's inputs while the original aggregate fixture remains available.

## Compatibility and identities

Old report/cache/fixture addresses are relative symlinks to the owned files/directories. Historical source IDs, event IDs, annotation IDs, Pokémon instance IDs, source fingerprints and serialized state hashes are retained. No blind serialized-string replacement occurred. Recordings 2 and 3 already had canonical battle IDs, so their identities require no renaming. The original M1.4 cache's video fingerprint still matches the renamed recording 0.

`battle_artifacts.py` implements the reusable resolver, canonical old-name alias, explicit video/ID consistency checks, cached-manifest ownership checks, output guards and historical evidence-address mapping. A different physical video cannot reuse an already registered stem. Cross-battle namespace writes and escaping symlinks are rejected. Explicit external destinations also retain file ownership in a locked `.battle-artifact-owners.json` sidecar, preventing later writes from another recording.

The full-battle builder preserves historical evidence and annotation addresses through `historical_reference`; moving a file therefore does not change the state hash. All moved non-HTML file payloads were checked against their pre-move SHA-256 values after reconstruction and remain byte-identical. Recording 3 retains final hash `4696ae0b62d98dbcfda1ad3595046b7997d638ef493ea33adda6ecb50b88bdbc`.

HTML is deliberately re-exported from saved data using the existing lossless compact codec. No battle evidence is removed. Links calculate the project root from the actual page location, working from both canonical paths and historical report aliases. Recording 3's reconstructed HTML is about 1.32 MiB; M2.2.4 and hidden-state pages remain roughly 1.4–1.6 MiB. All 197 states navigate successfully. Browser-script checks do not constitute browser-layout timing.

## Commands

```sh
.venv/bin/python scripts/migrate_battle_artifacts.py
.venv/bin/python scripts/replay_m22.py --battle-id sample_battle_2
.venv/bin/python scripts/replay_m222.py --battle-id sample_battle_2
.venv/bin/python scripts/export_m221.py --battle-id sample_battle_2
.venv/bin/python scripts/build_m223.py --battle-id sample_battle_3
.venv/bin/python scripts/validate_m223.py --battle-id sample_battle_3
.venv/bin/python scripts/replay_m224.py --battle-id sample_battle_3
.venv/bin/python scripts/replay_m231.py --battle-id sample_battle_3
```

Generic extraction, clip preparation, M2.1 evaluation, M2.2 replay, timeline export and M1.5 clip benchmarks now select owned paths using `--battle-id` / `--video` where appropriate. Clip benchmarks derive and check ownership from cache metadata before loading recognition models. Historical fixed-input evaluation scripts continue through the compatibility aliases.

The M2.2.3 reconciliation, M2.2.4 opening enrichment and M2.3.1 checkpoint replay are recording-3 fixture workflows. They explicitly reject another battle rather than applying its hand-checked selection, timestamps or checkpoints to a different video. Their underlying extraction, state, knowledge initialization and hidden-constraint APIs remain reusable. New recordings need their own evidence/initialization inputs; this organizational task does not produce new recognition results.

## Validation and remaining shared artifacts

- Five videos can be located independently, with distinct physical files.
- Recording 2's cached 20-event replay succeeds. Synthetic independent outputs for recordings 0 and 4 succeed; attempts to overwrite another recording's result fail without changing it.
- Recording 3 rebuilds all 196 events from cached observations/annotations and retains all 28 HP and 28 identity checkpoints, zero conflicts, and its original final hash.
- Focused organization/viewer/full-battle run: **44 passed**. Combined organization/knowledge/hidden/viewer/full-battle run: **109 passed**. After adding same-stem video protection and both browser-location link checks: **31 organization/viewer tests passed**. Final phase/organization checks: **32 passed, 1 video-adapter test deselected**. Machine-readable results are recorded in `battle-artifact-validation.json`.
- Cached HTML data was losslessly restored before/after repacking. Canonical M2.2.4 initialization/navigation checked at approximately 31/51 ms in Node's minimal DOM; the legacy hidden-timeline alias also passed. These are script smoke timings, not browser-layout measurements.
- `.cache/` and video exclusions remain in force. Per-battle extracted/evidence output directories are now also ignored by Git. Local frame payloads remain available through their compatibility links; global model/knowledge assets are not duplicated.

Mixed-battle aggregate summaries (such as M1.4 follow-up accuracy and M1.5 phase/ROI compatibility), unbound standalone fixture overlays, and shared OCR/model-runtime benchmarks remain at their original shared addresses. Their ownership cannot be conservatively assigned to one recording. Attributable underlying frame caches, workflow/target evidence and annotations have been isolated; immutable historical references resolve through aliases. The migration manifest records shared retained artifacts and these explicit exceptions. No mechanics, recognition models, observable transition algorithms or hidden-state inference algorithms were changed. No commits or pushes were made.

Single-recording archived M1.4 timelines were also isolated under each battle's `archive/` directory; mixed archived summaries remain shared. Small, versioned screenshot regression fixtures remain in `tests/fixtures`; bulk frame/evidence outputs remain ignored and local.

Final standalone organization checks: **18 passed** in 3.53s, including cached original-video reuse with video decoding explicitly forbidden, and refusal to apply recording-3 reconciliation to recording 4. The rebuilt canonical M2.2.3 viewer navigates all 197 states (Node minimal-DOM initialization/navigation about 28/34 ms). `git diff --check` passed; both canonical viewers were opened locally.
