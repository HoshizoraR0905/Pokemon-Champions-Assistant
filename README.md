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
python main.py --video tests/fixtures/sample_battle.mp4 --interval 1 --max-frames 30 --annotated outputs/video > outputs/battle.jsonl
python -m pytest -q
```

Image input emits one JSON object. Video input streams one JSON object per sampled frame (JSON Lines), including newly observed events and the accumulated own-team configuration. `--annotated` is an output filename for images and an output directory for videos. Recognition uses actual video position timestamps where available, with an explicitly marked FPS fallback. Sampling decodes sequentially without retaining video frames; smaller intervals improve coverage at the cost of more OCR work. Sampling can miss brief messages and does not establish turn numbers.

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
