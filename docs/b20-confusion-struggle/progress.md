# B20 confusion and Struggle — 2026-10-29

Current status: context-binding follow-up complete, no running jobs; see [focused update](context-binding.md).
Original confusion/Struggle semantic work completed; earlier results remain preserved.
Earlier implementation notes below are chronological.

Scope: literal parser, existing volatile state and HP attribution/projection only.
No damage formula, numerical HP prediction, performance work, new video, full
OCR, commit or push. Preserve original B20 first benchmark/reference/results.

Observed B20 messages retrieved from original observations and both independent
43-row reference and automatic partial-log extraction:
- 对手的风妖精\n混乱了！ (212.502–213.503s)
- 对手的风妖精\n正在混乱中！ (232.005–233.007,287.015–288.015,379.030–380.513s)
- 不知所以地攻击了自己！ (289.015–290.015s)
No confusion-end or Struggle execution observed in frozen B20. End/Struggle tests
are synthetic; canonical move165 already resolves Struggle/挣扎.

Plan: implement parser/volatile semantics; prefix-only bare-subject binding;
separate confusion-self-damage/Struggle recoil observed-HP sources; portable
regressions; isolated saved-data window replay; seal integrity and final report.
Current: implementation done, focused integrated tests running. Do not duplicate
running pytest; inspect processes first. No video/OCR process launched.

User-requested mechanic contract: confusion40BP typeless physical with own
Attack/Defense (metadata/documentation only, no damage formula). Struggle50BP
physical typeless, recoil1/4user maximum independent of target damage. No PP-based
execution inference. No numeric recoil is synthesized from maximum HP.

52Poke references checked2026-10-29: 混乱（状态） revision2549425 and
挣扎（招式） revision2528170. Neither page has a Champions-specific row. Treat
requested Champions behavior as explicit user task contract corroborated by
general descriptions, not independent Champions verification. Struggle assertion
extends existing canonical KnowledgeBase supplement, preserving this distinction.
License CC BY-NC-SA3.0, attribution神奇宝贝百科contributors; source URLs and revision
recorded in supplement/report. Runtime remains offline. No crawler/importer added.

## Final status

Complete. Final report: report.md. Final portable suite191 passed/58.60s,
including22 focused tests. Added portable b20-confusion-messages.json fixture.
Final source-window validation v3 complete: applied1,continued1,self-hit2 new
accepted events;45 original window events and IDs/payloads preserved, with121
needed seed-prefix records from existing snapshots. Self-hit17→10 displayed
percent,-7points, own-source/own-recipient, no parent normal move.

v1 failed continued stage on old occurrence-ID collision; its completed applied
stage and failure retained. Newly split semantic events now use separate derived
IDs without rewriting original IDs. v2 completed. Final supplement-description
correction changed its fingerprint; v3 revalidated final identity, then its cache
reuse check returned3 compatible completed stages without replay. No blanket
cache deletion or overwrite.

Final integrity:6671 original B20 freeze files and88 B16 guarded files verified.
Original benchmark/reports/curated43-row reference unchanged. No full OCR/video,
performance investigation, new video, commit/push or next milestone. No jobs remain.

Resume/read-only completed validation command:
```sh
.venv/bin/python scripts/validate_confusion_struggle.py --stage all --experiment confusion-struggle-20261029-v3
```
Stage identities include original seal/observations/replay/snapshot and relevant
implementation hashes. Do not force reuse after identity mismatch. Preserve prior
stages and choose a new experiment only when implementation actually changes.


## Context-based binding follow-up — 2026-10-29

Remove the confusion timeout; use Battle Message order and existing final-HP
resolution evidence. No new modules or unrelated mechanics. Implemented primary
chronological context, explicit independent-message window boundaries, and a
unique-active-HP-decrease fallback derived during replay with evidence IDs.
Intermediate HUD samples are one resolution, not additional damage events.
Callbacks publish final receipts once; correction/retraction recalculates bindings.

First integrated check204 passed. Added final occlusion/benched-observation guards;
final suite running. Original B20 self-hit and notice-removed ablation succeeded
in v1; v2 validates final active-only candidate scope. No decoding/OCR/full replay.
Final report and exact commands: context-binding.md. Inspect process/manifest
before resuming; do not duplicate active checks or overwrite old experiments.


Final context follow-up:206 portable tests passed/63.75s. B20 final v2 normal
and notice-removed self-hit windows both passed:17→10 displayed percent,-7points,
source=recipient=Whimsicott, no Roost parent. Both completed stages reused on
verification without replay.6671 original B20 freeze files and88 B16 guards
verified unchanged. Compile/whitespace checks passed. No new modules, timers,
frame limits, OCR/decoding, performance work, commit or push.

Current commands (do not attempt old v3 experiments with changed source hashes):
```sh
.venv/bin/python scripts/validate_confusion_struggle.py --stage self-hit --experiment confusion-context-20261029-v2
.venv/bin/python scripts/validate_confusion_struggle.py --stage self-hit --omit-confusion-announcement --experiment confusion-context-without-notice-20261029-v2
```
