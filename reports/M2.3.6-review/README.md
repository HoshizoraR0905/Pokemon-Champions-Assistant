# Review M2.3.6 battle events

Open [review.html](review.html) directly in Chrome and refresh if you had the old
viewer open. Keep `review.html` and `assets/` together; you can copy this review
directory elsewhere. All display images use local hash-addressed assets. No
server, network, OCR, video decoding or special Chrome file-access flag is needed.
The package is about 202 MiB because the original PNG bytes are preserved.
`assets-manifest.json` records hashes and original evidence paths; do not rename assets.

## Start here

1. Use **Priority review queue**, the default view. Coaching appears first because
   a real readable move announcement was not recovered. Queue labels distinguish
   actual failures, conservative unknowns, supported results and background noise.
2. Select an event in the left column. Read **What the program detected**, **What
   entered Battle State**, and **Why / what to review**. Open the decision receipts
   for the accepted/rejected messages and their reasons.
3. Inspect **Before / during / after**. The selected full frame and yellow message
   crop show the actual pixels. Raw OCR is displayed separately from state
   admission. Click the context thumbnails or expand the individual-frame selector.
4. Classify the selected frame's message region, then fill in **Your event
   correction** below. Use ordinary text and Pokémon names; no JSON editing is
   required. Leave actor, target, species or HP blank when you cannot determine it.
5. Changes save in the browser as you edit. Click **Export annotations** to save a
   portable file. Reopen the viewer and use **Import annotations** to continue.

**Chronological events** sorts the same groups by time. **Advanced: all frames**
retains access to all 120 sampled frames. **Team preview** exposes all 24 saved
roster-row observations. Neither a navigation group nor a sampled frame is an
additional independent recognition test.

## Practical examples

**White Mega Evolution animation (408.002s).** Choose **Mega Evolution animation —
no-text example**. The During frame is almost white; the message crop has no
readable battle message. Its raw OCR `ype`, confidence .443, was rejected for low
confidence. The separately recorded manual visibility check preselects **No battle
message visible**. Add frame feedback such as “White flash; no battle message”;
choose **Correctly rejected background OCR noise** and event type **No battle
message / animation**. Leave the visible-message field blank. This is useful
feedback confirming harmless noise, not a missed valid message. This label applies
to the selected frame, not to every frame of Mega Evolution.

**Readable Mega Evolution message (413.503s).** Choose **Big Mom’s Mega Evolution
revelation** and its During frame. Select **Readable battle message, correctly
recognized**, enter the visible message if useful, and mark the event **Correct**.
The program admitted a named Kangaskhan episode; its active doubles slot and HP
remain unknown. The animation frame and this readable message are separate review
questions, not contradictory OCR outcomes.

**Fake Out (416.503s).** Choose **Fake Out — identified and attributed**. Confirm the
readable message and mark the event Correct if appropriate. You can enter
“Big Mom used Fake Out” and actor “Big Mom / Kangaskhan”. Leave target blank unless
it is explicitly supported: the program recorded executed move membership only,
not a target or damage effect.

**Coaching (425.5–427.5s).** Choose the first queue item. Inspect neighboring frames
until you can read the move. For a readable frame whose OCR contains only the
nickname and “used” prefix, select **Readable battle message, incorrectly
recognized**. Enter “对手的Invincible使出了指导！” in Actual visible message. In
Your event correction choose **A real event or information was missed**, event
type **Executed move announcement**, actual event “Invincible used Coaching”, and
actor “Invincible”. Explain the incomplete move transcription in feedback. The
reviewed move is Coaching; the automatic result did not identify it. Do not infer
a current Lucario slot from an earlier identity across a coverage gap.

**Unresolved Big Nugget icon.** Choose **Unresolved nickname: Big Nugget**. Inspect
HUD candidates and the icon crop. If you cannot independently identify the icon,
choose Cannot determine or Conservative unresolved result is appropriate, leave
species blank and explain what evidence is missing. A perfectly transcribed
nickname and a possible roster member do not prove species or individual identity.

## Visibility categories and corrections

Every message region offers these choices:

- No battle message visible.
- Readable battle message, correctly recognized.
- Readable battle message, incorrectly recognized.
- Readable battle message, missed completely.
- Text partially visible / animation transition.
- Cannot determine / not reviewed.

Choose “missed completely” when a real readable message was present but no usable
transcription exists. Use “incorrectly recognized” for wrong or incomplete OCR of
readable text. Use “partially visible” when the pixels themselves do not yet show
a full message. A low-confidence OCR result alone cannot establish visibility.
A blank frame with rejected OCR noise is not a valid-message miss.

Frame annotations store visibility, visible text and frame feedback separately
from the event verdict, actual event type/text, actor, target, species, HP,
unsupported-camera-association flag and event feedback. A frame can have no text
while its surrounding event was correctly recognized on another frame. Flagging
an event as Incorrect assertion moves it to queue priority 1 without changing
frozen scores.

## Denominators and limitations

The header preserves the frozen evaluation: **11 reviewed actual occurrences**
(3 development entries and 8 held-out events), including **two held-out executed
moves**. Fake Out was identified/attributed; Coaching was not. Six of eight
held-out event kinds were recognized; that does not mean six state effects were
admitted. Current held-out HUD/HP facts are **12/13**. Frame sampling, grouped HP
observations, nickname cards and unclassified background intervals do not enlarge
these denominators. No ability-revelation occurrence was reviewed in this segment.

The event group names and reference messages may come from earlier manual review;
these are explicitly separate from program detections. The single white-frame
visibility seed is a presentation-only manual annotation in
`tests/fixtures/battles/m236_viewer_visibility.json`, not a change to the frozen
M2.3.6 evaluation fixture. Other unreviewed background frames remain unclassified;
they are not automatically labelled no-text using OCR confidence.

Version 2 exports use `m236-human-review-v2` and can be imported without editing
JSON. Original version 1 exports and browser notes are preserved as legacy notes.
Browser file-page storage can be unavailable or browser-specific; export before
closing if the page reports that local storage is unavailable. Imports affect
review notes only, never frozen labels, recognition, Battle State or metrics.

## Regeneration and validation

Regenerate only the presentation from saved evaluation/replay outputs:

```sh
.venv/bin/python scripts/build_m236_review.py
```

Use this renderer for the event-centered viewer. The older
`evaluate_m236.py --split all` command belongs to the original frozen evaluator
and regenerates its older frame viewer; it is unnecessary for this UI update.
The prior viewer is preserved locally as `m236/review-v1-preserved.html`.

Focused tests and the local Chrome workflow check:

```sh
.venv/bin/python -m pytest -q tests/test_m236_review.py tests/test_git_artifact_policy.py
node scripts/verify_m236_review.cjs
```

The Chrome check uses a temporary browser profile and automated review notes. It
exercises the five examples above, structured export/import, reload persistence,
legacy import, priority changes, chronological navigation, frame browsing and
preview browsing. It does not enter automated annotations into your browser.
Local receipts and screenshots live in `m236/review-v2-check/`; the renderer's
input/output hashes are in `m236/review-v2-manifest.json`.

## M2.3.6-U: typed UI and large overlay review

Refresh the viewer after the U update. The header's original M2.3.6 denominators
remain frozen. The separate U summary reports 10 newly labelled test frames,
3 readable message occurrences and 1 executed move. The advanced browser now
also includes cached U layout examples; these extra images are not new independent
M2.3.6 tests.

Use **Review category** to select Pokémon / Party Overlay, Check Status Overlay,
Battle Log Overlay, or Move Description Overlay. The last category explicitly
shows no verified positives and remains untested. Overlay cards show overlay
pixels rather than interpreting a central-message crop. Message controls are
disabled on those panels; use the event correctness and extracted-field controls.
Party/reserve HP is not active-slot HP. Status-panel conditions are current display
observations, not newly triggered effects. Log rows are historical and their
original event times remain unknown when unsupported. Move descriptions, when
verified examples become available, can describe a selected move but never imply
execution or an opponent's moveset.

For **Coaching**, select its baseline/U comparison card. Change **Which reading
are you reviewing?** to M2.3.6-U. The new visual-row OCR reads 指导; occurrence
metadata explains that repeated frames support one candidate. Its actor remains
unbound in the integration replay. Record transcription as correct while choosing
an actor-attribution error or appropriate unresolved result; do not claim the
move was safely revealed to an active individual.

For a **field indicator**, enter the literal condition and counter in Field
condition / counter or ability information, e.g. “沙暴状态, 4/5; duration meaning
unknown”. Do not convert that fraction into remaining turns. Error category and
comments can distinguish visibility, row grouping, transcription, region semantics,
actor/target, admission, duplicate events and missing semantics. New Correctness
choices also include No relevant UI visible and Partially visible. All remain
optional structured review notes, separate from evaluation and recognition.

The current renderer is:

```sh
.venv/bin/python scripts/render_m236u_review.py
```

Use it to rebuild the U-extended viewer from completed cached results. The older
M2.3.6 renderers belong to the preserved baseline and should not be used to update
this U comparison. The previous event viewer is preserved locally as
`m236u/previous-review.html`. U review and resource manifests are separate from
closed M2.3.6 budgets and outputs. No new OCR runs when rendering this page.

## Resume the saved partial review (2026-10-16 repair)

1. Open `review.html` and select **Import annotations**.
2. Select this directory's existing `m236-event-review-annotations.json`.
3. The partial-review indicator should show **0/11 event verdicts**, **7/11
   occurrences with event/frame feedback**, and **20/136 individually reviewed
   frames**. Frame feedback is not an event-level verdict. Indeterminate blank
   records remain unreviewed; legacy reviewed flags retain their original meaning.
4. Inspect **Team preview**, nickname cards, and individual frames to resume the
   corrections already entered. Blank correction fields are preserved as blank.
5. Export to a new filename/location to retain the original export. The viewer
   does not write to the original JSON file. Temporary validation exports are
   confined to `.cache/battles/sample_battle_5/m236u/browser-check/`.

[Human feedback and priorities](human-feedback-summary.md) and
[Chrome validation and limits](viewer-validation.md) distinguish confirmed
observations from hypotheses. The intermittent original image failure was not
reproduced in this Chrome environment. The repair removes cache-path dependency,
registers image callbacks before assigning sources, and displays explicit errors.
Cyan boxes show cached visible U HUD regions; yellow shows the selected message
or panel region. Existing frozen scores are separate from your partial review.

To rebuild only the package or summary, using existing HTML/caches:

```sh
.venv/bin/python scripts/package_m236_review.py
.venv/bin/python scripts/summarize_m236_feedback.py
node scripts/verify_m236_portable_review.cjs
```

The packaging command requires either existing `assets/` or the original cached
images. It never extracts frames or invokes OCR. The U renderer also calls this
packager on future explicit renders; no recognition rerun is needed for this fix.
Assets and generated review outputs follow the existing Git ignore policy and
remain available locally. No commit or push was performed.
