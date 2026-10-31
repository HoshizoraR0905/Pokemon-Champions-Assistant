# B16 banner / HP development regression

Scope: user request dated 2026-10-28. No next milestone, commit, push, new
recognition pipeline or second state model. Preserve existing dirty-tree work.

Baseline: `b16-semantic-state-20261027-v1`, immutable reference and reports.
Intermediate acquisition: `b16-banner-hp-20261028-v1` (before gray HUD fix).
Intermediate v2: complete recognition, reconstruction intentionally interrupted after the blue-rain global-veto defect was identified. Successful OCR stages preserved.
Intermediate v3: completed acquisition and replay; source of reusable OCR predictions for the final run.
Intermediate v4: interrupted after a focused recoil grammar test exposed an overly broad affected-name match. Successful prior caches preserved.
Final acquisition: `b16-banner-hp-20261028-v5`, complete and sealed; all 1276 source frames reused and zero new OCR model invocations.
Final replay/evaluation: `b16-banner-hp-20261028-v6`, reuses that sealed recognition stage. A final HP-history fix records the delta of an explicit numeric pair even when no prior HUD baseline exists. It changes optional replay metadata only.

Source review confirmed right Pelipper/Drizzle at 131.005 s and left
Charizard/Drought at 187.015 s. User confirmed reversed timestamps in request.
Use production FFmpeg PTS-based extraction; OpenCV random-seek probes were
inconsistent and are excluded from all scoring. Source seeks and hashes:
`.cache/battles/sample_battle_16/banner-hp-20261028-v1/source-seek-manifest.json`.

Reuse 1276 saved original frames and compatible model/crop predictions. The old
run did not save pixels for 232 COMMAND monitoring-only sample cells. No claim
of a fresh full-grid acquisition, cold performance or held-out accuracy.
Frame cache records ownership, media fingerprint, individual frame hashes,
sampling and the missing-cell limitation; no annotations enter acquisition.

Diagnoses: right sprite merges text baselines; gray faint HUD fails colored-name
visibility gate; zero-valued numeric observations must survive reading; full-card
change signatures are poor HP triggers; explicit burn notices lacked semantics.
Ability activation does not establish weather. Cause notices do not establish
numbers. Numeric links require one explicit affected-instance notice between
compatible observed endpoints, no intervening unscoped action/effect, and a
matching sign. Otherwise cause stays unknown. Source holder remains separate.

Resume only a genuinely incomplete final run, after checking processes:

```sh
ps -axo pid,etime,command | rg 'main.py|benchmark_b16_state.py'
tail -5 .cache/battles/sample_battle_16/banner-hp-20261028-v1/reconstruction-v6.log
.venv/bin/python main.py --video tests/fixtures/sample_battle_16.mp4 --profile event-driven --identity-mode lightweight --sample-fps 2 --run-id b16-banner-hp-20261028-v6 --reconstruct-from .cache/battles/sample_battle_16/event-driven/b16-banner-hp-20261028-v5 --resume
.venv/bin/python scripts/benchmark_b16_state.py compare --run-id b16-banner-hp-20261028-v6 --reference-run-id b16-semantic-state-20261027-v1
```

Do not use `extract` or `reference` to regenerate the sealed baseline. Do not
rerun completed decoding/OCR just because this chat or a client disconnects.

Cache compatibility: the current event-driven version is accepted by the existing
reconstruction command. Only `tracking/hp_causes.py` was added to its replay-only
metadata allowlist; OCR, geometry, parser and scheduling fingerprints still must
match. Geometry invalidation and byte-identical observation reuse are tested.

## Completed

Final v6 acquisition reuse, replay, packaging and read-only reference comparison
are complete. No pipeline process needs resuming. Reference seal is unchanged.
Ability 4/6→6/6; item 1/3→3/3; weather 4/5 unchanged; numeric pairs 14/21→18/21
(own 7/10→10/10, opponent 7/11→8/11); independent zeros 0/3→3/3; explicit
burn notices 0/2→2/2 with numeric amount unknown. Numeric cause links remain 0;
reference numeric causal accuracy is unmeasured. State fields 154/191→175/191.
All four pair gains require new accepted endpoints under the updated anchors.
Final relevant tests: 436 passed, 9 deselected; diff whitespace check passed.

```sh
.venv/bin/python scripts/summarize_banner_hp_regression.py --run-id b16-banner-hp-20261028-v6
```

Final report: `reports/battles/sample_battle_16/evaluation/b16-banner-hp-20261028-v6/report.md`.
