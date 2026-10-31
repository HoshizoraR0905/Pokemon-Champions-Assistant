# Cleanup compatibility, performance and limitations

Validation date: 2026-10-27. Existing working-tree edits and all benchmark/cache/source artifacts were preserved. No commit or push. Source-level changes and exact call paths are described in [architecture.md](architecture.md) and [deletion-audit.md](deletion-audit.md).

## Automated checks

* Final current-source portable suite: **2569 passed, 73 deselected**, one environment warning about absent ccache (244.00s). This includes damage, inverse damage, Speed inference, statistical modeling, state correction/retraction, Battle Log and review dependencies. `local_artifacts` tests were explicitly excluded, not counted as successes. No failing present artifacts were suppressed.
* Before cleanup: 59 focused production identity/event/region/double-faint tests passed (39.02s). After the first integration, the portable suite passed 2568 tests; after scheduler isolation, 111 relevant tests passed. The final full suite above includes the subsequent other-side pending-pair regression.
* New regressions cover a genuine same-side pair, opposite-side faints, intervening replacement, other-side activity preserving a valid pair, no-candidate early return, evidence immutability and resume. Sampling tests decode a generated one-second video at both 2 and 3 FPS and preserve separate COMMAND inspection. Existing double-faint tests retain atomic placement, rejected conflicting/conditioned proof and retraction coverage.
* `git diff --check` passes. No index changes, commit or push.

Counts describe overlapping test runs, not additive independent coverage. Test logs are `.cache/recognition-cleanup-final-tests.log` and `.cache/recognition-cleanup-focused.log`.

## Frozen saved-evidence comparisons

Results are produced by `scripts/verify_recognition_cleanup.py`; its atomic stage manifests record source/input SHA256, progress, exact comparisons and separate namespace ownership. Original seals are verified before and after, and original manifests/observations/events/replay bytes are protected. It never decodes the battle video or invokes OCR/icon inference. Pixel checks use one saved frame per observed phase, not all frames or accuracy ground truth.

| Saved battle | Evidence/events | State / bindings / snapshots | Battle Log |
|---|---|---|---|
| B13 `fresh-heldout-20261026-v1` | 403 events reproduce exactly, including IDs, semantics, order and evidence | 403 full history records (bindings, status/reason and per-record state hash), final state and hash reproduce exactly | Saved reference contains zero views/entries: empty assembly/parse reproduced; provides no Battle Log coverage evidence |
| B16 `b16-auto-eval-20261026-v1` | 1276 events reproduce exactly; 9 observed phases have identical frozen/current visual extraction geometry | All 1276 history records, bindings, statuses/reasons and per-event hashes; final state/hash and complete JSON replay match | 45 views → 89 entries and all event candidates exactly reproduced; same 10 assembly issues |

B13's first comparison harness completed its successful replay checks, then found Python tuple versus JSON list inequality in policy metadata. The verifier now normalizes its output through JSON before whole-payload comparison. This was a verifier serialization issue; recorded event/state/hash comparisons were already true. The original failed diagnostic manifest is retained.

B13 additionally reproduces visual geometry on one saved frame for each of its observed phases. B16's state replay took 138.828s; B13's final verification replay took 35.159s. These replay times are recorded for reproducibility, not a controlled speed comparison (tests ran concurrently during portions of these final semantic checks). The controlled prefix measurement below completed before those tests began.

Both completed manifests report `protected_files_unchanged=true` and `status=complete`:

* `.cache/battles/sample_battle_13/cleanup/cleanup-v2/manifest.json`
* `.cache/battles/sample_battle_16/cleanup/cleanup-v1/manifest.json`

Reproduce/resume with the same commands and source fingerprints:

```sh
.venv/bin/python scripts/verify_recognition_cleanup.py --battle sample_battle_13 --source-run fresh-heldout-20261026-v1 --run-id cleanup-v2 --replay
.venv/bin/python scripts/verify_recognition_cleanup.py --battle sample_battle_16 --source-run b16-auto-eval-20261026-v1 --run-id cleanup-v1 --replay --compare-prefix
```

Raw OCR evidence is reused unchanged. This does not establish new recognition accuracy, semantic completeness or held-out performance. The live pipeline's strict reconstruction-cache dependency check remains in force; the verifier does not bypass or modify acquisition manifests.

## Performance

B16's 20 ordinary prefix checks now scan only newly appended observations and perform **zero historical prefix replays**. The first gate pass took 0.058840s in total on the saved observations, with no pending pair. No OCR/icon reads are needed when there is no candidate. The original B16 full audit measured 20 prefix replays, 13,903 replayed events and 1,174.290s; those historical totals are evidence of the regression, not a controlled new end-to-end timing comparison.

Controlled comparison: the frozen verifier took **132.139735s**, versus **0.106374s** for the new verifier on the same prefix; **1 replay → 0**, with identical empty pending results. This is a component comparison, not an end-to-end speedup. It loads the frozen original `DoubleFaintVerifier` implementation and the new implementation on the **same last B16 prefix** (1255 saved rows), under the same current StateEngine and machine, without tests/OCR/video acquisition running concurrently. Baseline runs first; one sample is reported with no confidence interval. This isolates scheduling work; final authoritative replay/export remains necessary.

A genuine same-side double-faint replacement candidate still incurs one full prefix replay per candidate key; independent HUD verification keeps its original 2-second retry cadence. The optimization eliminates ordinary repeated historical replay, not every possible full replay. Development identity mode still has separate prefix replay costs. No full cold-B16 OCR run was performed, and no new overall PTR, whole-pipeline speedup or 3-FPS full-recording cost is claimed.

## Remaining semantic limitations

The preserved B16 full source-pixel audit classifies the 89 extracted Battle Log records as 55 applied, 14 recognized but not fully applied, 12 with incomplete semantic parsing, and 8 not reconstructed. These are not an exhaustive whole-match denominator or independent human labels. Log scroll assembly still has 10 reported issues; viewing times do not establish original action times.

Known gaps include some activation banners, some zero/end HP endpoints, sleep/wake and side-effect grammars, and deferred Mega/ability effects. Cleanup adds no new features to fill these gaps, makes no speculative slot/target/identity assignments, and does not advance recognition or inference milestones. Shared OCR/parser errors can remain correlated across live/log channels. A deterministic equivalent replay proves compatibility under the saved evidence and rule profile; it does not prove semantic acceptance or 100% reconstruction.
