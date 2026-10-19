# Pokémon Champions Assistant

Milestone 1: recognize publicly visible information in local screenshots and prerecorded videos. No damage calculations, hidden-state inference, strategy engine, game-memory access, or input control is implemented.

## Setup on macOS

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest
brew install tesseract tesseract-lang
```

Python 3.10 or newer is required. OpenCV and pytesseract are the only direct runtime dependencies. Tesseract is a separate executable; `tesseract-lang` supplies Chinese language data. Without Tesseract, panel classification still works and text fields remain null with a warning. `--language eng` supports English OCR, but does not establish support for other interface layouts.

## Run

```sh
python main.py --image tests/fixtures/battle_screen.png
python main.py --image tests/fixtures/move_selection.png --annotated outputs/move_selection.png
python main.py --video tests/fixtures/sample_battle_0.mp4 --interval 1 --max-frames 30 --annotated outputs/video > outputs/battle.jsonl
python -m pytest -q
```

Image input emits one JSON object. Video input streams one JSON object per sampled frame (JSON Lines), including newly observed events and the accumulated own-team configuration. `--annotated` is an output filename for images and an output directory for videos. Recognition uses actual video position timestamps where available, with an explicitly marked FPS fallback. Sampling decodes sequentially without retaining video frames; smaller intervals improve coverage at the cost of more OCR work. Sampling can miss brief messages and does not establish turn numbers.

### Maintained event-driven battle pipeline

For a new recording, the current battle-analysis entry point is:

```sh
.venv/bin/python main.py --video /path/to/new_recording.mp4 --profile event-driven --run-id production-v1
```

This uses saved battle-message evidence, the standardized 2D HUD icons, and `tracking.state_engine.StateEngine`. Supported send-outs create occupancy immediately. `tracking/entry_hud.py` confirms the actual HUD display name and species prospectively; full message references and possible title segments remain separate. W supplies an auxiliary command-phase check. Scene-model recognition is not enabled.

For an existing saved-event baseline, run only reconstruction in a battle-owned diagnostic namespace:

```sh
.venv/bin/python scripts/replay_entry_hud.py --battle sample_battle_5 --baseline evaluation/m238-provisional-entry-v2/replay.json --diagnostic-id m238-hud-authority-v2
.venv/bin/python scripts/report_entry_hud.py --battle sample_battle_5 --diagnostic-id m238-hud-authority-v2 --baseline evaluation/m238-provisional-entry-v2/replay.json --report reports/battles/sample_battle_5/M2.3.8-HUD-authoritative-name-proof-v2.md
```

These saved-evidence commands require the named local baseline. Compatible completed manifests are reused; source drift requires a new diagnostic ID. `--reconstruct-from` on the video entry point remains subject to its stricter recognition-stage dependency checks. The shared current report implementation is `scripts/report_entry_hud.py`; the `review_entry_hud.py` and historical `reuse_entry_hud.py` paths are compatibility wrappers. Earlier milestone drivers and sealed runs remain available for historical reproduction. See the [HUD-authoritative validation and consolidation report](reports/battles/sample_battle_7/M2.3.8-HUD-authority-and-consolidation-v2.md) for the current saved-evidence acceptance.

## Design

- `capture/`: `Frame`, image loading, and video sampling. Adapters return BGR image data, source, frame index, timestamp, and metadata. QuickTime, ADB, and mobile acquisition can later implement this contract.
- `recognition/`: normalized regions, panel-color classification, Tesseract preprocessing, numeric parsers, and annotation. Regions are converted to pixel coordinates for each input image.
- `models/`: typed dataclasses for observations, Pokémon, moves, recognized frames, and events.
- `tracking/`: merges non-null configuration fields by recognized displayed name; tracks HP/name/condition-text changes and deduplicates messages. A narrow Chinese message grammar identifies explicitly written move executions without a species or move dictionary.
- `damage/`, `api/`: reserved modules only.

The recognizer supports the supplied landscape doubles layout (approximately 2.17:1). Classification uses interface geometry and panel colors, never fixture filenames, Pokémon names, or memorized OCR strings. Primary categories are `team_configuration`, `team_preview`, `battle_screen`, `move_selection`, `battle_message`, and `unknown`; secondary components distinguish the configuration tabs and mark the battle view under move selection. Battle-message classification requires readable Chinese text in the supported message region.

## Output and uncertainty

Each observation includes `value`, `confidence`, `region`, `raw_text`, and `provenance`. Regions are `(left, top, right, bottom)` pixels, with exclusive right/bottom bounds. Unreadable, invalid, or low-confidence values remain null. The default OCR acceptance threshold is 0.75; message classification requires 0.8. Confidence is a heuristic Tesseract score, not a calibrated probability. A null field can retain raw text for review. Screen confidence is also a heuristic.

Own HP and PP are `{ "current": ..., "maximum": ... }`; opponent HP is a percentage integer. Impossible ratios or percentages are rejected. Current and maximum digits are read separately because the interface uses differently sized italic fonts. Icons in opponent team preview remain unresolved and have `unresolved_icon` provenance.

Configuration summary pages attempt displayed names, abilities, held items, gender icons, four moves, and six actual stats. Form, level, nature, EVs, and IVs are explicit unknowns in the configuration schema. The supplied stats screen also shows allocation numbers and nature arrows; their units and mapping have not been validated, so numeric allocations are stored as `allocation_<stat>_display` and are not presented as EVs or nature. Gender icon color is recognized only in its known UI region, with ambiguous colors left unknown. Configuration pages merge only non-null observations. Displayed names are OCR text, not validated species identifiers; nicknames, OCR errors, or two identical species can make merging ambiguous.

Condition output preserves readable banner text rather than claiming a specific weather or terrain from visual effects. Events distinguish direct message parsing (`visible_message_parse`) from changes between observations (`observed_change`) and include recognition evidence. Name changes are not asserted to be switches; HP changes are not asserted to be damage or attributed to a move. A name change resets the slot's HP baseline. Repeated messages are suppressed until the text changes or a recognized command/preview screen establishes that the message has cleared. Initial HP readings establish baselines rather than emitting changes.

## Validation and current limits

Tests cover all three original screenshots at multiple resolutions, both configuration tabs, unsupported menus, null OCR output, JSON/annotations, numeric validation, video sampling, configuration merging, message deduplication, and explicit move-message parsing. Optional integration tests exercise real Tesseract HP, PP, and message recognition and skip when its language data is unavailable.

Four additional PNG fixtures are half-resolution frames derived from the supplied video: configuration moves at 15 seconds, configuration stats at 18 seconds, a battle message at 170 seconds, and an unsupported status menu at 300 seconds. They are test evidence, not recognition templates.

Verified at original screenshot resolution: both own HP ratios in the battle and move screens, all four move PP ratios, and all four visible move names. Some opponent percentages and Pokémon names are correctly rejected for low confidence even when their raw OCR text looks plausible. Configuration text/stats extraction is partial. Message extraction over animated scenery is experimental; not every visible message is readable. Full-video event accuracy has not been established.

Normalized regions tolerate scaling with the same composition; window chrome, letterboxing, cropping, portrait input, and materially different layouts require another profile or preprocessing. OCR may confidently misread a character. There is no species dictionary, icon matching, status-icon recognition, complete battle-message grammar, or motion-based event interpretation. Annotated outputs and raw OCR evidence are intended to support further region tuning using additional labeled screenshots.

### Current Champions data (M1.1)

Recognition defaults to the audited `2026-10-13-M-C.1` snapshot. Official M-C species eligibility is separate from community dex facts, form legality and move availability. Missing catalog entries remain unknown; omitted official species are illegal in M-C without being declared unavailable in the game. The April 16 v1.1.0 snapshot is archived in `knowledge/archive/2026-04-16-v1.1.0`.

See [the source audit and refresh instructions](reports/M1.1-data-audit.md), [version manifest](knowledge/data/manifest.json), [coverage and unresolved records](knowledge/data/coverage.json), and [real screenshot results](reports/M1.1-current-screenshots.json). Upstream MIT software licensing does not establish blanket redistribution rights for third-party data; the audit records the limits.

### M1.2: OCR and Pokémon icons

The default recognizer uses locally installed PP-OCRv6 recognition weights for Chinese and English text. If those weights are absent, it reports a Tesseract fallback. It uses a separately retrieved, checksum-verified Champions thumbnail cache for icon matching. The cache is optional and is never downloaded during recognition. Species and form names, Champion availability and M-C legality come from the local knowledge snapshot; icon matching ignores roster eligibility when ranking visual candidates.

On Apple Silicon, install optional OCR dependencies and retrieve official weights explicitly:

```sh
python -m pip install -e '.[ocr,test]'
python scripts/setup_ocr.py --backend all
python scripts/retrieve_visuals.py
python main.py --image tests/fixtures/battle_screen.png
python main.py --image tests/fixtures/team_preview.png --verbose --json-out outputs/preview.jsonl
```

`--ocr paddle-v6`, `--ocr paddle-v5` and `--ocr tesseract` select a backend. `--no-icons` disables visual matching. Terminal output is concise by default; `--verbose` shows all diagnostics, and `--json-out` writes complete JSON lines. OCR and visual scores remain separate, and a disagreement yields a conflict instead of an identity.

The identity index covers 1,025 National Pokédex species and 1,579 PokeAPI forms; the Champions thumbnail manifest lists 393 PNGs and 14 unmapped filenames. See [the M1.2 audit and benchmark](reports/M1.2-recognition.md), [form index](knowledge/data/identity.json), [visual asset manifest](knowledge/data/visual_assets.json), [ground truth](tests/fixtures/m12_ground_truth.json), and per-backend results in `reports/M1.2-*.json`. Captured thumbnails are kept in `.cache/champions-icons` and are not bundled.

### M1.3: persistent own-team configuration

Use the PaddleOCR pipeline and the existing entity database to collect the two configuration tabs into [the versioned team snapshot](data/teams/my_team.json):

```sh
python main.py --images tests/fixtures/team_configuration_moves.png tests/fixtures/team_configuration_stats.png --ocr paddle-v6
python main.py --image path/to/new_configuration.png --collect-team --ocr paddle-v6
python main.py --video path/to/recording.mp4 --interval 1 --collect-team --ocr paddle-v6
python main.py --team-summary
python -m pytest -q tests/test_team_configuration.py
```

`--team-out` selects another team file; `--team-id` names a new team. Collection saves after every configuration frame, so interrupted videos retain observations. Reprocessing the same screenshot/frame does not duplicate evidence. Other recognized screens do not enter the persistent team. The six card positions supply stable `own_team_1` through `own_team_6` instance IDs. Duplicate species remain separate by slot; a different species in an occupied slot creates a conflict and its other fields are not merged. If the team is reordered, review the conflict rather than assuming the slot still represents the same Pokémon.

The v2 JSON keeps `instance_id` separate from `species_id`, `pokemon_id`, optional `form_id`, and `canonical_identity`. A null `form_id` is valid when a Pokémon variant ID uniquely identifies the observed form. `identity_status` distinguishes `resolved_unique`, `resolved_default`, `resolved_variant`, `resolved_form`, `species_only`, and `conflicting_variant`. In Regulation M-C, a species name resolves automatically if exactly one applicable variant remains; the [versioned applicability scope](knowledge/data/identity_scopes.json) excludes unconfirmed PokéAPI G-Max rows from that M-C uniqueness check based on the published mechanics, while retaining the source rows and unknown availability. Other regulations without reviewed rules keep all variants plausible. Species with multiple applicable variants still require distinguishing evidence and never default to a base or male variant. Per-field `value`, `canonical_id`, `status`, `confidence`, source observations, and preserved conflicts remain available. The six final numerical stats are read from the stats tab. The nearby allocation numbers have separate `allocation_*_display` fields; they are not treated as final stats or EVs. Level, nature, EVs, and IVs are unknown on these pages. `complete` requires all 14 required fields, including a unique identity, for all six members to be manually verified and every active conflict resolved. Existing v1 and v2 team files are migrated or backfilled on load without discarding observations or manual verification.

For manual review, create a UTF-8 JSON array such as:

```json
[
  {"instance_id":"own_team_1","field":"hp","value":172,"reviewer":"trainer","note":"checked stats tab"},
  {"instance_id":"own_team_1","field":"ability","canonical_id":"pokeapi:ability:22","reviewer":"trainer","note":"checked moves tab"},
  {"instance_id":"own_team_1","field":"identity","canonical_id":"pokeapi:pokemon:373","reviewer":"trainer","note":"checked base form icon"}
]
```

Run `python main.py --team-corrections path/to/review.json --team-summary`. Species, ability, item, and move fields use IDs from `knowledge/data/entities.json`; identity uses a unique `pokeapi:pokemon:<id>` or `pokeapi:form:<id>` key from `knowledge/data/identity.json`. Numerical stats require positive integers. Corrections preserve the earlier observation and mark its conflict reviewed. Check [the field accuracy report](reports/M1.3-configuration.md) and [the canonical identity audit](reports/identity-follow-up.md) for fixture results and remaining unknowns.

### M1.4: phase timelines

The phase-only timeline records configuration, team preview, battle controls, move selection, Pokémon selection, replacement controls, move targeting, visible messages, probable battle animation, and unresolved frames. `pokemon_selection` names the brought-party list/detail view; `switch_selection` requires the replacement-control popover. `move_target_selection` requires the opponent/own target-grid layout and a visible selected-move banner, which can anchor on either side. Card count alone is insufficient. Ambiguous panels and unsupported device overlays remain `unknown`.

```sh
python phase_timeline.py --video path/to/recording.mp4 --interval 2 --output outputs/phases.json
python phase_timeline.py --inspect reports/M1.4-final-sample-battle-1-timeline.json
python scripts/benchmark_m14.py
python -m pytest -q tests/test_phase_timeline.py tests/test_recognition.py
```

Segments retain source, frame index, timestamps, evidence, heuristic confidence, warnings, and capture metadata. Transition bounds span the last old-phase sample and first new-phase sample; sparse sampling cannot establish an exact boundary. `last_observed_timestamp` distinguishes observed evidence from estimated segment ends. Smoothing preserves known short-lived phases and explicitly ambiguous evidence.

Selection purpose is separate from the visible phase: `voluntary`, `move_triggered`, `faint_replacement`, `revival_target_selection`, or `unknown`. `--context-annotations` accepts reviewed context with source ranges, supporting evidence, and provenance; the supplied voluntary-workflow annotation is in `tests/fixtures/m14_selection_context.json`. Optional `--context-ocr` can supply accepted Revival Blessing message evidence, with cached reads of unchanged message regions. These annotations generate no confirmed switch, revival, HP-restoration, or turn-boundary events. A battle view without controls may represent animation or waiting; its warning preserves that uncertainty.

Both complete recordings were sampled once during the follow-up, and final predictions were then refreshed from verified lossless image caches. To repeat classification locally without decoding videos:

```sh
python scripts/refresh_m14.py --video sample_battle_0.mp4 --reuse-cache
python scripts/refresh_m14.py --video sample_battle_1.mp4 --reuse-cache
```

The local caches in `.cache/m14-phases/` are optional and unbundled; reuse requires matching source metadata and frame checksums. The benchmark compares archived and final timelines against the same revised sparse annotations. See [the M1.4 final report](reports/M1.4-phases.md), [before/after evaluation](reports/M1.4-follow-up-accuracy.json), and [cached target-frame provenance](reports/M1.4-cached-target-review.json). Original reports and annotation history are preserved. M1.5 now provides incremental captured-evidence streaming; M2 reconstruction and strategy are not implemented.

### M1.5 streaming validation

The captured-evidence streaming architecture is functionally complete for the supported layout, but the 1-second processing target is not met. The saved latest 5 fps paced replay achieves 2.637 fps with 18.506-second P95 decision processing completion; all settled decisions remain uncertain. See [the M1.5 validation report](reports/M1.5-streaming.md) for ordering, readiness, message-filter corrections, measurements, and limitations.

Replay supports recorded frames or cached manifests through `stream_replay.py`; icons are opt-in. Run `.venv/bin/python scripts/validate_m15.py` to audit saved traces without OCR or video processing, and `.venv/bin/python -m pytest -q tests/test_streaming.py` for focused regressions. Historical traces are preserved; no M2 battle-state or strategy layer is provided.

### M1.5 adaptive and live follow-up

Opt-in adaptive ROI monitoring, phase-aware field reuse, unresolved candidate preservation, and a bounded live acquisition adapter are available. The default OCR backend remains Paddle CPU. The [optimization report](reports/M1.5-optimization.md) compares fixed 2 fps, adaptive CPU, ONNX CPU, and Core ML, including accuracy and live-adapter losses. The expanded CPU replay reaches 2.806 fps with 15.281-second P95 processing completion; the one-second production target remains unmet.

`stream_replay.py --adaptive` exposes separate acquisition, phase, message, routine, and icon rates. The experimental `--message-ocr-fps 2.5` budget retains deferred PNG crops as uncertain observations; its default is 5. Live sources use `streaming.live.run_live(acquire, pipeline, sink)` so acquisition/monitoring can continue during recognition backpressure. Sinks must promptly archive candidate evidence and loss records. Phone transport is not implemented or validated.

Use `scripts/evaluate_m15_adaptive.py` to audit saved traces without OCR/video processing. Optional ONNX/Core ML experiments use `scripts/setup_m15_onnx.py`, `scripts/benchmark_m15_ocr.py`, and the isolated `ocr_experimental` dependency extra; no experimental backend is automatically selected. Reproduction commands and remaining limitations are in the report.


### Per-recording artifacts

Use the recording stem as `battle_id`. Cached frames/OCR live in `.cache/battles/<battle_id>/`; events, inputs, replays, timelines and metrics live in `reports/battles/<battle_id>/`. Shared knowledge/model assets remain outside these namespaces. Historical paths are relative compatibility symlinks; saved source/event IDs are immutable.

```sh
python scripts/replay_m22.py --battle-id sample_battle_2
python scripts/build_m223.py --battle-id sample_battle_3
python scripts/replay_m224.py --battle-id sample_battle_3
python scripts/replay_m231.py --battle-id sample_battle_3
python scripts/reconstruct_m223.py --video tests/fixtures/sample_battle_4.mp4 --stage survey
```

The last command performs new processing when requested; migration and cached replay do not run it. M2.2.3 focused annotations belong to recording 3; another recording requires its own inputs. See `reports/battle-artifact-migration.md` for the migration inventory and compatibility policy.


### Git tracking and clean clones

Source, tests, shared knowledge databases, curated screenshot fixtures and manual annotations/configuration stay in Git. Generated reports are ignored by default: HTML viewers, complete state/snapshot JSON, OCR output, JSONL traces and extracted frames stay local. `reports/battles/<battle_id>/inputs/*.json` is an explicit curated-input exception; Markdown reports and explicitly listed small validation summaries are also tracked. Do not put generated dumps in `inputs/`.

After cloning, run `python scripts/setup_battle_workspace.py` to recreate historical compatibility aliases **only for targets that exist**. It does not decode videos, run OCR, overwrite data or create dangling links. Curated input and documentation aliases are already version-controlled with their targets. For an existing pre-migration checkout with local recordings/artifacts, use `python scripts/migrate_battle_artifacts.py` once, then the setup command. Do not run the migration to download or reconstruct missing evidence.

Install test dependencies with `python -m pip install -e '.[test]'` and run `python -m pytest`. Portable unit/replay tests use reviewed small event oracles and curated initialization fixtures, reconstructing timeline states in memory. Tests marked `local_artifacts` exercise optional historical recording/OCR/cache integrations; missing prerequisites produce explicit skips in a clean clone. They run automatically when the local evidence is available. `pytest -m 'not local_artifacts'` selects only portable tests. This distinction does not skip failures for artifacts that are present.

No media or generated replay data is required for the portable M2.3.1 hidden-state, projection or quantitative-mechanics regression tests. Full 197-prefix comparisons require the local cached M2.2.4 reports and preserve their rule profiles; those reports are intentionally not distributed in Git.

### Scoped sampling and message selection (M2.3.3-B1)

New acquisition uses one setting, `--sample-fps`, defaulting to **2 FPS** (0.5s).
The default comes from `recognition.video_sampling.DEFAULT_SAMPLE_FPS`; 3 FPS
uses the same timestamp-grid logic. Sampling and OCR frequency are independent:

```sh
.venv/bin/python scripts/validate_m233b1.py --battle-id sample_battle_0 --start 408 --duration 8
.cache/m15-accel-venv/bin/python scripts/validate_m233b1.py --battle-id sample_battle_0 --start 408 --duration 8 --sample-fps 2 --stage ocr
```

The first command selects candidates without OCR; the second uses the existing
optional ONNX environment. `--policy` selects `baseline`, `reduced`, `temporal`,
or default `hybrid`. `--selection-config thresholds.json` overrides fields in
`SelectionConfig`, for example `{"stroke_value":120,"repeat_similarity":0.9}`.
Install the optional `sampling` extra if `imageio_ffmpeg` is unavailable.
Explicit battle and interval arguments prevent accidental five-video jobs.
New caches stay under `.cache/battles/<battle_id>/m233b1/`; historical M2.3.2
and M2.3.3-A entry points and artifacts remain unchanged. See
[the B1 report](reports/M2.3.3-B1-sampling-and-selection.md) for measured costs,
limited coverage results, cache identities, and B2 recommendations.

M2.3.3-B2's scoped parser/move recovery and cache-only validation are documented in
[the B2 report](reports/M2.3.3-B2-parser-and-move-recognition.md). Run
`.venv/bin/python scripts/verify_m233b1.py` to verify preserved B1/prior artifacts
without recognition. B2 replay requires one explicit `--battle-id`; see the report
for saved-crop recovery and evaluation commands.

Standalone damage calculation accepts explicit JSON inputs without reading video
state: `.venv/bin/python -m damage examples/damage/neutral.json`. See the
[versioned API/data/mechanics contract](docs/damage-v1.md) and
[M3.1 validation report](reports/M3.1-validation.md). Reference-profile distributions
are provisional for Champions; unknown or unsupported mechanics produce diagnostics.

Inverse damage constraints enumerate exact feasible Attack/Special Attack sets:
`.venv/bin/python -m damage.inverse_cli examples/inverse_damage/single.json`.
See the [inverse API](docs/inverse-damage-v1.md) and
[M3.1.1 validation](reports/M3.1.1-inverse-damage-solver.md) for shared scenarios,
evidence requirements and the supported provisional mechanics scope.
