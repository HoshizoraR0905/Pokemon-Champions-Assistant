# Offline viewer validation — 2026-10-16

## Diagnosis and limits

All 136 frame paths and four additional preview-image paths resolve to existing
cached PNGs. In the original viewer, default headless Chrome with `file://` and
**without** `--allow-file-access-from-files` loaded the main Coaching frame and
three representative thumbnails: natural dimensions 1311×603. The full-frame
DOM box was 1067×490.766 CSS pixels, display:block and visibility:visible. The
551×68 crop canvas rendered. No console/resource errors were captured after a
reload. The main frame starts below the initial viewport (y≈1659); it is not
CSS-hidden. This is an observed layout fact, not an established cause of the
reported intermittent failure.

**The reported embedded-image failure was not reproduced.** Right-click/new-tab
opening was not used as validation. There is no evidence here for missing files
or a general Chrome block on embedded local images. The original viewer relies
on repository-relative cache paths, lacks load-error feedback, and assigns some
image sources before installing load callbacks. These are confirmed portability/
robustness weaknesses; their causal connection to the user's failure remains
unconfirmed. Headless automated Chrome does not reproduce every interactive
Chrome profile, extension or local-file setting.

Default local-file canvases become origin-tainted: a diagnostic `getImageData`
attempt raised SecurityError. This restricts reading pixels back into JavaScript;
it did not prevent `drawImage` display. Pixel readback is not needed by the viewer.
Crop rendering was checked in Chrome screenshots instead of enabling file-access
bypass flags.

## Delivered behavior

The review directory contains `review.html`, `assets/`, README and
`assets-manifest.json`. There are 140 distinct original-byte assets (198.70 MiB),
addressed by SHA-256. Repeated references share the same file. Cached sources are
unchanged, and `source_image` plus manifest source lists retain original paths.
No image conversion or compression changed hashes. No frame/event IDs or
recognition predictions were replaced. Local assets are ignored by Git under
the existing artifact policy; keep them with the HTML when copying the package.

Image handlers are registered before assigning sources, including cached-image
handling. Failures show an explicit error. Yellow boxes retain selected-region
geometry; cyan boxes show cached visible U HUD bounds. Import retains all v2
fields/records, including unknown fields, blank values and legacy reviewed=false;
editing retains additional fields on that record. The partial human progress
indicator is separate from frozen evaluation denominators.

## Executed checks

Browser: `Chrome/155.0.8059.40`. A fresh temporary profile, `file://`, network disabled through Chrome DevTools, no backend and no file-access override. The package was copied outside the repository to a temporary review directory and tested there.

- All 36 groups: embedded full frame and before/during/after thumbnails load and switch; crops readable offline without file-access flag
- All 24 preview rows render inside page
- All 136 raw frames decode; zero resource or JavaScript errors before deliberate error test
- Actual saved JSON imported via file picker with deep equality, including blank/unknown fields and legacy reviewed=false
- HUD overlay DOM bounds match cached native coordinates within one CSS pixel; selected message box visually checked in screenshot
- Additional case exported and persisted on reload; every prior record unchanged; source JSON unchanged
- Explicit missing-image error verified

The original JSON was imported through the actual file input and compared by deep
equality. A previously unannotated Coaching event then received a temporary
validation comment; exported JSON retained every original event/frame/legacy
record exactly. Browser reload preserved it. All temporary edits/downloads used
a separate Chrome profile and cache output directory; the user's file was never
replaced. Progress after original import: **0/11 event verdicts; 7/11 occurrences
with feedback on their frames; 20/136 individually reviewed frames**.

All 36 groups' before/during/after thumbnails were clicked; all 136 raw frames and
24 preview rows loaded at positive native and DOM dimensions. Message/panel crops
were drawn; the screenshots show inline images and canvas output. Cached visible
HUD box coordinates match the corresponding full-frame positions within one CSS
pixel. This tests overlay placement, not the recognition geometry's semantic
accuracy. Existing party/status/log controls and crops also passed the previous
viewer regression script.

There were zero unexpected resource or JavaScript errors before the deliberate
missing-asset test. That test produced the expected `ERR_FILE_NOT_FOUND` and
visible error message. These expected diagnostic errors are recorded separately
in the raw result; they do not refer to any packaged image.

- Focused tests: `.venv/bin/python -m pytest -q tests/test_m236_review.py` — **5 passed**, including byte preservation, deduplication and repeatable packaging.
- Existing viewer checks: `node scripts/verify_m236_review.cjs` — **passed**, no browser exceptions. This older script uses its existing file-access flag; the new portable check above does not.
- Portable check: `node scripts/verify_m236_portable_review.cjs` — **passed**, also executed with `REVIEW_HTML` pointing to the relocated package.

## Evidence and repeat commands

Raw diagnostics: `.cache/m236-viewer-repair/original-diagnostic.json`,
`repaired-diagnostic.json`, `validation.json`, `relocated-path.txt`.
Screenshots: `.cache/battles/sample_battle_5/m236u/browser-check/original-default-file.png`,
`repaired-coaching-inline.png`, `repaired-hud-inline.png`.
Previous regression: `.cache/battles/sample_battle_5/m236u/browser-check/browser-result.json`.
These are local generated artifacts. Validation exports in that cache directory
are synthetic test output and must not replace the user's annotation export.

```sh
.venv/bin/python scripts/package_m236_review.py
.venv/bin/python scripts/summarize_m236_feedback.py
.venv/bin/python -m pytest -q tests/test_m236_review.py
node scripts/verify_m236_portable_review.cjs
```

No OCR, extraction, recognition model, StateEngine, frozen labels or evaluation
report changed. No new milestone, commit or push. Intermittent failure root cause
remains unconfirmed; offline packaging and import/export are validated outcomes.

Original annotation SHA-256 (unchanged): `3c0570bcd3eee4bc74dae241e6471d587d71b58c077c7bb91b2346a684bfe3fc`.
Current HTML SHA-256: `cfd2f96318d0ff15a307c7e5955db20e4a71869adfbac5a3e155e342df9f1703`.
