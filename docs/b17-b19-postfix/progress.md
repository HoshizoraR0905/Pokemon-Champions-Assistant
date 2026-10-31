# Three focused fixes and first B19 run — 2026-10-28

Current status: B19 complete. User confirmed no Battle Log; log scoring is not applicable. B20 continuation: docs/b20-fresh/progress.md. Earlier chronological notes below are retained.

Scope: original project; parser Eject Button withdrawal, existing preview retry gate,
existing identity ledger preview compaction only. Preserve other dirty edits.
No commit/push or newly discovered B19 fixes.

Plan/status:
1. Inspect existing interfaces and frozen manifests: complete. No related running job.
2. Implement and test each correction: complete.
3. Saved B17 reparse/reconstruction, saved B18 frame/counter regression and isolated
   packaging measurements; never modify frozen `fresh-b17-b18-20261028-v1`.
4. Focused integrated regression before first B19 run.
5. Fresh B19 (`tests/fixtures/sample_battle_19.mp4`, unique original candidate),
   `fresh-b19-postfix-v1`, normal CLI through existing external timing/freezing driver.
6. Only after seal: review actual partial log reference, compare supported facts,
   report coverage boundaries, full performance and descriptive state/HP results.

Diagnostic namespaces will be recording-owned `diagnosis/three-fixes-20261028-v1`;
new benchmark outputs use `fresh-benchmark/fresh-b19-postfix-v1` and matching
`event-driven` namespace. First inspect manifests/processes before resuming.

Source changes to reset/cause handling must reuse existing switching behavior;
no generic mechanics assumptions, new state framework or live-network dependency.

## Completed checks

- Focused suite: 185 passed, 1 local-artifact test deselected, 72.87 s.
- B17 saved recognition reparse/replay: completed. Deferred 218 -> 10
  (occupancy211 ->9; other7 ->1). All original202 cascading HUD events and6
  related messages recovered; nine unrelated occupancy IDs preserved exactly.
- New8 portable tests passed before integrated suite.
- B18 saved-frame icon validation running; no new decoding/OCR.

Commands (stage manifests prevent duplicate completed work):
```sh
.venv/bin/python scripts/validate_preview_switch_fixes.py --stage b17
.venv/bin/python scripts/validate_preview_switch_fixes.py --stage b18-icons
.venv/bin/python scripts/profile_saved_package.py --battle sample_battle_18 --source-run fresh-b17-b18-20261028-v1 --experiment three-fixes-20261028-v1/package
.venv/bin/python scripts/validate_preview_switch_fixes.py --stage b18-consistency
```

- B18 actual saved-frame matching complete: requests358 ->28, matchers692 ->56;
  measured icon span20.608 s (baseline249.852 s), real-preview requests22,
  false-preview requests6. Four resolved rows retained; rows2/5 remain unknown.
- Same358 B18 observations through updated ledger: roster358 ->145, state
  3,566,546 ->2,305,338 UTF-8 bytes; packaging134.844 s including export.
  Non-preview receipts/final facts compared exactly; second deterministic replay running.
- Final acquisition amendment ensures new preview contexts bypass outer unchanged
  gate. AST audit saved as acquisition-compatibility.json: only observe_phase
  return/analyze call-site changed; completed reparse/package implementation and
  saved-frame evaluation effects unchanged, so successful stages preserved.
- Final focused HP/preview checks after amendment:79 passed,33.16 s.

Do not blindly rerun completed stages: their whole-source identities precede the
final acquisition-only amendment. Inspect the compatibility audit and completed
outputs; no saved parser/state processing implementation changed.

## Final Task 1 completion

52Poké Champions-specific item row checked: Eject Button disappears after one use
in that battle (article revision2635531, retrieved2026-10-28). Added one assertion
to the existing versioned canonical KnowledgeBase resolution supplement; no new
importer/database. Explicit withdrawal reuses `_item` consumption, with derived
fact provenance; activation banner alone remains insufficient. Related122 tests
passed in38.20s. B17 v1 successful occupancy result preserved; v2 reparse/replay
now checks final consumption-enabled code, without OCR.

B18 consistency verification initially used native tuple-vs-JSON-list equality;
its failed check manifest is preserved. Check now normalizes via JSON as existing
verification does, and saves the second replay before assertion. Final B18
replay contains no resolution-supplement rules and no Eject Button withdrawal;
completed packaging measurement remains reusable. Revalidate full serialized
state/receipts against it after B17 completes.

## B19 live run started

- B17 final v2 replay complete:142.290s; deferred218->10; item590 consumed
  derived withChampions rule evidence; Mr.Rime retained85% HP/history.
- B18 JSON-normalized second replay exact; non-preview receipts/final facts
  preserved. Original failed native-comparison check retained separately.
- Final source compiled and diff whitespace checked. No further production edits.
- Fresh B19 started through normal driver after those checks:
```sh
.venv/bin/python -u scripts/run_fresh_video_benchmark.py --battles sample_battle_19 --run-id fresh-b19-postfix-v1
```
Driver console `/tmp/b19-postfix-production-driver.log`; durable execution/checkpoints
`.cache/battles/sample_battle_19/fresh-benchmark/fresh-b19-postfix-v1/`.
Inspect PID/execution manifest before any resume; never launch duplicate or reuse
reference/recognition caches. Wait for initial-freeze.json before reviewing cases.

## Final handoff

Three fixes, scoped B17/B18 validation, B19 production/freeze/replay/HP/performance
are complete. B19 external wall317.365434s, duration391.81s, samples784,
detailed776, PTR.8099983. Same production command must not be rerun or retuned.
B19 final source/normal report hashes match production identity. Exact post-seal
1110-event replay/receipts/state/hash and HP projection verified.

Final focused knowledge/HP/Git suite:94 passed,2 optional historical tests
deselected,28.40s. No selected test failures. Native-vs-JSON comparison diagnostic
error was corrected in validator; final B18 exact second replay passed129.267s.
Validator now records knowledge dependencies explicitly for future stages; applied
B17 v2 consumption rule hash was cross-checked against current local supplement
in `knowledge-rule-identity.json`, preserving completed results.

Integrity audit at B19 `evaluation/fresh-b19-postfix-v1/integrity.json`:
B17 7604 files, B18 6352 files, B19 5970 files,88 B16 guarded files all unchanged.
Old summary CLI has a hardcoded B17/B18 report output path: DO NOT invoke its
`--stage summary` for a new battle. One B19 invocation temporarily wrote the old
comparison; immediately restored from original frozen metrics, exact original
SHA f7876e8129131ea67aa68c4bc07f787d2b274a00e7183a318e1da4af24966c80 verified.
B19 per-battle `describe` output is independent and preserved.

Remaining required acceptance: actual partial Battle Log reference is not located.
Existing independent reference scan of all776 saved frames returned0 views/entries.
Overview, tail, all60 unknown-phase frames and top12 possible log panels reviewed;
no actual log found. Lookup of Battle19 filenames in fixtures/data/outputs found
only original video. Asked user for local reference path or source time window.
Do not claim0%/100% recall, invent labels or copy predictions into ground truth.
See `reference-review/coverage.json`; coverage boundaries/fact denominator unknown.

Continue ONLY when actual reference is supplied: inspect that original source,
transcribe/review independently into a separate reference stage, establish covered
event boundaries, compare against already sealed predictions. Do not rerun normal
B19 processing, optimize on its failures or overwrite the original reference scan.
No running jobs remain. No commit/push, no B19-specific production corrections.

Final report: docs/b17-b19-postfix/report.md (sections A–E).

## User correction and closure of B19

User confirmed B19 has NO Battle Log; B20 has logs for partial turns. B19 is
complete: no missing-reference acceptance remains, log accuracy is not applicable.
Original empty reference scan preserved; report corrected, frozen outputs unchanged.
Continue with B20 unchanged production configuration and first-run sealing.
