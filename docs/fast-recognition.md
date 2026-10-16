# Fast video recognition

Run the reusable profile through the ordinary video-analysis CLI:

```sh
.venv/bin/python main.py --video tests/fixtures/sample_battle_6.mp4 \
  --profile fast --run-id my-fast-run
```

`fast-regions-v2` uses the existing OCR, icon, identity, event and StateEngine
implementations. It adds observation scheduling, not another Battle State.
The original `standard` profile and Battle 6 M2.3.7 baseline remain available.
`--profile diagnostic` additionally reads changed command/selection interfaces.
The fast profile uses the pinned local ONNX CPU OCR model. Existing standard
profile OCR/backend, team collection and image options retain their own scope.

Inspection policy:

| Visible phase | Inspection frequency |
| --- | --- |
| Stable command/selection/switch interface | 1 FPS |
| Live battle message | 2 FPS |
| Ordinary animation | 1 FPS |
| Full-screen transition without qualified regions | 1 FPS |
| Changed region or ambiguous UI transition | 2 FPS temporarily |
| Unknown phase | 2 FPS |

The temporary boost lasts 1.5 seconds **after detecting a change** and never
blacks out monitoring. A continuing live message or unknown phase retains 2 FPS.
These are inspection frequencies. They are not OCR budgets. The decoder emits
up to two candidate frames per second; the adaptive scheduler decides which to
inspect. FFmpeg still decodes intervening source frames. The manifest counts
source decoding, materialized candidates and actual inspections separately.
Source integer PTS/timebase and requested sampling cells are retained separately.

Each message, HUD, ability banner and field region is checked independently.
A menu does not veto other regions. Normalized crop/glyph comparisons exclude
whole-frame animation from semantic change decisions. Glyph differences are
normalized by visible signal, so a small changed word is not diluted by empty
background. Newly visible/changed regions and a bounded unreliable retry may
request recognition. Unchanged region readings retain original source/time
references; exact crop caches provide a separate, recorded reuse layer.
A confirmed disappearance clears reuse, allowing an identical later message to
form another occurrence. Partial geometry is marked unresolved, rather than
asserting disappearance. Long uncertain gaps can still split occurrences and
require review. HUD disappearance never means a Pokémon left battle.

Stable menus suppress detailed OCR and sprite matching. A newly changed team
preview may supply roster evidence; it does not establish active slots. HUD
identity, numeric HP and status-like changes remain independently eligible.
Selected detail overlays require the existing selection-border corroboration.
Ability screen edges do not establish battle sides, and field indicators do not
establish effect triggers or duration semantics. Unsupported overlays/unknown
phases preserve timestamps and source images, with insufficient-coverage
checkpoints at most every three seconds. No invented evidence is admitted as a
fallback. Historical battle logs are excluded from live message occurrences.
The fast profile does not yet extract full historical-log or party-panel content;
those baseline evidence losses must remain in comparisons.

A 1 FPS stable phase can miss a subsecond UI state before the next inspection;
2 FPS can miss a state shorter than 0.5 seconds. A transition boost begins only
once the change is observed. It cannot recover an unseen transition. Additional
transition-triggered source sampling requires a separate measured experiment;
this profile does not claim multi-hit impact or brief banner completeness.

Every run owns `.cache/battles/<battle_id>/fast/<run_id>/` and
`reports/battles/<battle_id>/fast/<run_id>/`. The identity seals sampling settings,
source hashes, video checksum, model manifest and icon index. Source copies,
per-frame observations, crop predictions, images and checkpoints are retained.
The review package contains original PNG evidence and causal state prefixes,
uses relative asset links, and opens offline. Human notes use a separate export
and never modify model predictions.

To resume an interrupted unchanged run:

```sh
.venv/bin/python main.py --video tests/fixtures/sample_battle_6.mp4 \
  --profile fast --run-id my-fast-run --resume
```

Resuming verifies identity, restores the saved context/scheduler/region gates,
and seeks to the first incomplete half-second cell. Exact successful crop caches
remain reusable. In-memory fuzzy OCR/icon caches start fresh; resumed overhead
is counted. A changed implementation requires a new run ID. A disconnected
terminal is not grounds to discard a successful prefix. A checkpoint/tail
mismatch is an explicit error requiring inspection rather than silent deletion.

To measure a genuinely fresh end-to-end run, including Python startup, hashing,
decoding, recognition, replay, comparison and viewer packaging:

```sh
.venv/bin/python scripts/benchmark_fast.py \
  --video tests/fixtures/sample_battle_6.mp4 --run-id new-cold-run
```

This command requires an unused namespace and records hardware and the complete
CLI wall time. Static local weights/templates/knowledge are shared; previous
video frames, predictions and states are not used. Resumed/warm runs cannot be
reported as cold measurements. The full-video target is container duration +
five seconds. A performance pass does not imply semantic acceptance.

Counters distinguish sampled/classified frames, adaptive skips, pre-OCR rejects
by reason, unchanged-region OCR calls avoided, exact-cache hits, attempted and
completed OCR/icon invocations, message candidates and admitted state receipts.
`ocr_invocations_avoided_unchanged` counts the crop predictions that an unchanged
read would have requested (one per native message row; observed crop count for
other reads). It is distinct from frames rejected before any OCR adapter request.
Actual recovered-event correctness remains unknown without independent labels.

`comparison.json` retains every unpaired baseline message occurrence and state
assertion, plus every differing/missing baseline HUD/banner/field reading, with
source IDs and timestamps. Receipt matching is one-to-one within 1.1 seconds,
with kind/canonical/literal/actor agreement. Region readings may be retained
from up to ten seconds earlier, which is reported separately from repeated
observations. This alignment is diagnostic, not ground truth or an accuracy
score. Fewer assertions, repeated-state suppression and more move candidates
cannot establish equivalent coverage or better accuracy.
