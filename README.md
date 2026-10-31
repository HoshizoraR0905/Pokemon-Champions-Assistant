# Pokémon Champions Assistant

Recognize visible information from Pokémon Champions screenshots and recorded battles, preserve evidence and uncertainty, and reconstruct supported battle state for separate damage and Speed inference tools. Input control and game-memory access are outside this project.

The current production video pipeline is **event-driven + lightweight identity**, using PP-OCRv6 ONNX on CPU. Start with the [architecture and parameter guide](docs/recognition-cleanup/architecture.md), [dependency/deletion audit](docs/recognition-cleanup/deletion-audit.md), and [regression/performance results](docs/recognition-cleanup/validation.md).

## October 2026 major update: B16–B23 recognition and M3 inference

Recent recorded-battle validation reaches **100/104 = 96.15% message-record reproduction on B22's visible Battle Log reference**. B23 independently reaches **65/69 = 94.20%** on its partial reference. These are scoped message comparisons, not whole-match recognition accuracy or complete state/mechanics correctness. See the [B22 evidence](docs/b22-ditto/report.md) and [B23 benchmark](docs/mega-b23/report.md).

- Ditto/Transform now preserves persistent identity across supported returns, entry episodes and copied battle state, while keeping native build information separate from transformed moves. [Implementation and limits](docs/b22-implementation/report.md).
- Action-level HP evidence supports aggregate damage and evidence-backed individual hits, with targeted 3/4 FPS inspection when needed. B22's Dual Wingbeat example resolves **21 + 24 = 45 HP**; unknown hits remain unknown. [Validation](docs/b22-followup/report.md).
- Damage/Speed joint constraints, held-item policies, public-build evidence and offline build-similarity research are expanded. Archive design and storage-retention reports are included; the proposed archive exporter is not implemented.

See the [major update notes](docs/releases/2026-10-31-major-update.md) for the full scope, validation and remaining limitations.

## Run

Use the existing local environment and previously verified model/icon caches:

```sh
.venv/bin/python main.py --video tests/fixtures/sample_battle_16.mp4 --profile event-driven --identity-mode lightweight --run-id my-run --sample-fps 2
.venv/bin/python main.py --help
```

`--sample-fps` controls acquisition and cheap visual monitoring, default 2 FPS; 3 FPS is supported in a separate run. Verified COMMAND reduces detailed inspection to 1 FPS; unchanged crops can reuse OCR. `--interval` and `--ocr` apply to the standard adapter and are rejected on production profiles. Production does not fall back to Tesseract.

Each recording owns `.cache/battles/<battle_id>/` and `reports/battles/<battle_id>/`. Use a new `--run-id` after changing code/settings; `--resume` requires identical inputs and fingerprints. Never overwrite old benchmark runs or seals. `--end-seconds` and `--max-frames` support scoped experiments. Compatible frame/prediction caches can be reused; see the parameter guide for validation rules.

Screenshot and team configuration adapters remain available:

```sh
.venv/bin/python main.py --image tests/fixtures/battle_screen.png
.venv/bin/python main.py --images image1.png image2.png --collect-team
```

These adapters use their explicitly selected OCR backend (`--ocr auto/paddle-v6/paddle-v5/tesseract`). Their optional Tesseract fallback does not describe the production video pipeline. Model setup, streaming experiments and historical milestone instructions are preserved in the [archived pre-cleanup README](docs/archive/README-before-recognition-cleanup-20261027.md); historical performance statements there are not current production guarantees. See `requirements.txt` and `pyproject.toml` for dependencies and optional backends; model downloads are explicit setup operations.

Battle Log processing runs separately **after** a sealed video-only prediction:

```sh
.venv/bin/python scripts/compare_battle_log.py --help
```

Raw OCR, normalized labels, structured events and state application receipts are distinct. Missing evidence stays unknown. Battle Log viewing time is not the original action time. B16's saved full audit reports 55/89 extracted log facts applied, 14 recognized but not fully applied, 12 with incomplete semantic parsing, and 8 not reconstructed. These are audit categories, not an independent whole-match recognition accuracy measurement. Cleanup preserves these limitations.

## Validation

```sh
.venv/bin/python -m pytest -m 'not local_artifacts'
.venv/bin/python scripts/verify_recognition_cleanup.py --battle sample_battle_16 --source-run b16-auto-eval-20261026-v1 --run-id cleanup-v1 --replay --compare-prefix
```

Optional historical evidence tests use `local_artifacts` markers. Portable tests do not require the original battle recordings. Existing source, curated fixtures and reports remain intact; generated videos/frames/OCR/state outputs normally remain local. No automatic commit or push.
