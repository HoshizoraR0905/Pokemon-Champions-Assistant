# B24 fresh evaluation — durable progress

User request: full three-layer evaluation; no archetype, desired answer, public usage priors or historical acquisition. Latest assumption: all hidden non-HP stats use user-default-down-zero-sp-v1, lowered SP0 only; neutral/raised SP0..32, global alignment and66-SP budget. Known exact own profiles remain observed inputs.

Production run: fresh-b24-20261101-v1. Exact container duration1052.82s,43422 source frames. Input MP4 SHA c9f0c3504215a1da8b23a9592e12d2737588d3e0a975a33d15a2710295394299. Standard main.py event-driven lightweight sample-fps2; no recognition tuning or imported cache. Existing adaptive multi-hit is enabled by normal production behavior. External timing driver is scripts/run_fresh_video_benchmark.py. Driver output and stage logs are under fresh-benchmark/fresh-b24-20261101-v1. Inspect running processes and execution.json before any resume; never launch another acquisition while alive.

Preflight: evaluation/fresh-b24-20261101-v1/preflight.json protects85 prior B16–B23 seals/declared files/manifests/reports and snapshots129 runtime source files. New inference modules are outside production source paths; production source changes are prohibited until completion/freeze. No first-run predictions viewed yet; independent transcription begins only after initial-freeze.json exists.

Current stages: production active; reference/HP review/inference/report pending. Generic script scripts/evaluate_b24.py supports verify, reference, contexts, inference. No own profile, roster, battle result or mechanic has been preselected. Curated review input will be reports/battles/sample_battle_24/inputs/b24-evaluation-review-20261101.json after direct visual review.

After production completes:

```sh
.venv/bin/python scripts/evaluate_b24.py --stage verify
.venv/bin/python scripts/evaluate_b24.py --stage reference
```

Reference command scans saved inspected frames using independent geometric Battle Log detection and line extraction. Verify every readable distinct row against original saved PNGs, record clipped rows, frame IDs/hash/time/visible turn labels and ordered overlap deduplication, then freeze reference before reading predictions. Inspect independent HP endpoint images and exact six-member own roster; match through TeamProfiles, without assuming Team7. Do not treat automatic reference OCR as manually verified truth.

After review is saved:

```sh
.venv/bin/python scripts/evaluate_b24.py --stage contexts
.venv/bin/python scripts/evaluate_b24.py --stage inference
```

This reuses saved recognition and existing StateEngine/M3; does not rerun acquisition. Context promotions of source-unaccepted evidence are excluded via the existing frozen-admission guard. Completed contexts are reusable for inference-only dependency changes. If a handler fix is needed, first complete reference comparison and freeze initial coverage; preserve first inference trace and create a new fingerprinted output. No Defense/HP joint damage inference.

Validation so far:91 tests passed (configuration domain, inference integration, constraint trace, previous focused repairs). Default-domain tests cover exact integer sets, global alignment,66-SP budget, same SP mapping across forms, and no silent fallback. No commits/pushes.

Additional preparation: scripts/evaluate_b24.py reuses the existing saved-context adapter and requests diagnostic_save_replay, persisting a full diagnostic replay alongside context JSONL so later HP projections need no duplicate state replay. Default-rule support is an optional configuration_rule parameter on ChronologicalTrace/invert_saved_order/invert_saved_hit/stat_pairs; older callers retain their previous mechanical domain. No recognition/tracking/knowledge/damage runtime sources changed during the first production run. Initial91 tests passed before adding the optional replay artifact.

Exact header evidence is in evaluation/fresh-b24-20261101-v1/container-exact.json: movie-header46427579/44100 seconds, video media header315833/300 seconds; audio media header includes padding. FFmpeg reports rounded1052.82s. Report named timing denominators rather than silently equating these durations.


## Completed first run and independent comparison

Production COMPLETE AND SEALED: external1460.9837227498647s; FFmpeg denominator1052.82s; PTR1.3876861407931695;2106 materialized/monitored frames,2073 inspected,43422 source-decoded frames. OCR8504 calls428.594327542698s; icons84 calls28.63984662713483s. Timed reconstruction scope858.5836793330964s includes event construction, engine replay, optional adaptive processing and serialization through video-only outputs, excludes later viewer asset packaging. Original2780 receipts:2657 applied_candidate,77 recorded_observation,34 applied_partial,12 deferred; zero conflicts.14 provisional command cycles. No adaptive source file found yet (check manifest, do not assume cost).

Initial freeze: fresh-benchmark/fresh-b24-20261101-v1/initial-freeze.json;129 runtime sources confirmed unchanged through completion in production-source-integrity.json.85 historical guards verified. No historical acquisition.

Independent reference: geometric scan of2073 saved inspected frames found26 Battle Log views at884–896.5s, visible turns1–9. Auto assembly54 rows dropped readable scroll segments. Agent viewed ALL26 pages (reference-pages/page-001.png through026), source-only before production event inspection, and transcribed119 readable occurrences with explicit occurrence grouping. Curated reports/battles/sample_battle_24/inputs/b24-battle-log-reference-20261101.json +seal. Includes104 message/semantic rows and15 HP endpoint pairs. Two clipped fragments on page13 not invented. Mega reaction source says 全一环起了反应, NOT generic 钥石产生了反应; source zoom corrected and resealed before prediction inspection (old transcript archived locally).

Source-reviewed comparison frozen BEFORE repairs: evaluation/.../reference-comparison/reviewed-comparison.json and baseline-quality-seal.json.97/104 literal/banner records recognized and corresponding accepted;25/25 named move announcements recognized as applied_partial/move_revelation_only, not full effects. Instruct notice t2:4 is NOT a named execution and was manually corrected from reference parser's classification. Seven missing rows: Instruct-result notice, three sandstorm-start notices, two sand residual notices, critical-hit notice t9. Reference parser doesn't understand several sand log phrasings; manual truth overrides recorded. Raw Battle Message denominator should EXCLUDE11 ability/item banner labels:86/93 body messages;97/104 includes semantic/banner facts. Add that distinction to final metrics. HP endpoints13/15 correct; correct action-source groups11/15; causally supported complete10/15. Missing initialArch194→167; missing returnTyrantrum44%→8%; sand Pelipper164→154 and Garchomp184→173 misgrouped under Tailwind; Tyrantrum54%→44% Life Orb final plateau unresolved. Extra unsupported8%→6% Ice Fang self-cost fragment overlaps the distinct correctly supported8%→0% Life Orb episode. Preserve baseline metrics.

Own team source-reviewed full roster+items matches existing TeamProfiles sample_team_team7_20261021. Source production already auto-bound this profile. Review image000041.png at20.003333s; selection proof000161.png at80.013333s shows Grimmsnarl,Garchomp,Pelipper,Archaludon in that order. Opponent preview, independently inspected: Tyranitar248,Tyrantrum697,Camerupt323,Rillaboom812,Steelix208,Oranguru765. Only first six resolved roster sightings are authoritative;35 subsequent unresolved sightings must not erase established roster facts. Source engine split returning opponents into9 instances.

Post-reference scoped repairs begun:
- identity_ledger.unique_roster_return now considers resolved roster assertions; later unresolved sightings don't retract those, while conflicting resolved species still block merge. Added unresolved-sighting reentry regressions.
- initial_conditions.activated_field opt-in Sand Stream activation -> derived sandstorm using existing _field_event; no fabricated weather message, no arbitrary duration. StateEngine calls it on explicit ability activation only. Review supplies verified ability_field_reference rule to this diagnostic run only (52Poké Champions oldid2561804). Existing direct rain messages still supersede weather. Inverse adapter normalizes sandstorm -> sand.
- Source reviewed context inputs immutable at inputs/b24-evaluation-review-20261101.json: full roster/profile, neutral opening firstsend event:1ff50f41588206ea17877edf, verified first-entry Arch HP194 derived baseline, opt-in Sand Stream rule, diagnostic_hp_projection flag. Do NOT edit review or tracking/helper code during context run unless necessary; changes invalidate costly context stage.
- CONTEXT RUN ACTIVE via `.venv/bin/python -u scripts/evaluate_b24.py --stage contexts --version reviewed-context-20261101-v1` (PTY session22719). Cache namespace diagnosis/b24-reviewed-context-20261101-v1. Existing create_contexts has opt-in diagnostic_save_replay, saving final replay for cheap derived HP projection. No duplicate replay needed for HP. Frozen admission guard excludes source-deferred rows that become admissible only after identity repair. Inspect processes/manifests before resume.

Next work:
1. Complete source-verified narrow handlers for actual seven missing moves: High Horsepower,Spirit Break,Weather Ball,Electro Shot,Psychic Fangs,Knock Off,Heavy Slam; Sand Force ability also required. Current baseline handler available5/17 accepted damaging announcements;12 unsupported.17 actions total. Five opponent action-target HP relations (Psychic Fangs,Knock Off,Heavy Slam,Ice Fang,High Horsepower); first Psychic missing baseline. A third High Horsepower lacks usable HP and one Ice Fang/HighHorsepower hits Protect. Own attacks need no Defense/HP inversion.
2. Existing KnowledgeBase facts ALREADY have current-form weights: Steelix400, MegaSteelix form10174 weight740; Garchomp95, MegaGarchomp form10158 weight95, MegaGarchompZ form10534 weight99. No new identity/weight DB/importer. Damage pinned catalog species has no weight field but shared KB does. Engine change must preserve exact fixed-point rounding, screens broken by Psychic Fangs, KnockOff removable-item contract, weather-dependent Weather Ball, Electro Shot already-observed stage increase (no double boost), Heavy Slam weight ratio.
3. Inspect pinned Champions oracle `.cache/m31/oracle/node_modules/@smogon/calc/dist/mechanics/champions.js`: lines22 ElectroShot preboost constructor default MUST be neutralized in test oracle for supplied action-time stats;67 WeatherBall type;114 PsychicFangs screens;345 HeavySlam;368 WeatherBall power;440 KnockOff;499 SandForce5325. Test adapter scripts/damage_focused_oracle.cjs remains previous-task immutable; copy to a B24 adapter. Independent source web pages opened: 52Poké Champions learnsets for Grimmsnarl,Archaludon,Pelipper,Tyranitar,Steelix,Tyrantrum; PsychicFangs,KnockOff,SandStream,SandForce articles. Record revisions/retrieval/license in new B24 sources JSON. Verified SandStream Champions oldid2561804; SandForce oldid2620229. Need retrieve rest revisions and scoped formulas.
4. Finish evaluate_b24.py: filter opponent roster to resolved rows (currently conflict with35 None entries!), derive HP projection cheaply from saved diagnostic_replay (engine.state/history hydration, hp_resolutions no replay); repair firstArch194 baseline via existing repair_saved_endpoints if needed. Use derived projection separately; original baseline untouched. Record inference wall time. Run inference same reviewed-context version to reuse context cache.
5. Final all6 Speed/Attack/SpA tables + exact JSON + SP/alignment branches and detailed chronological traces. Use DEFAULT_RULE only; fallback only after diagnosing reliable contradiction. No public dataset calls. ChronologicalTrace optional configuration_rule and stat_pairs same default rule across forms. joint_projection in evaluate_b24 joins native retained stat constraints under one alignment/66SP budget after each update, recording additional reductions. Need validate before claiming exact full joint item/stat feasibility (conservative marginal limitations remain).
6. Finish actor/target/effect correctness metrics and deferred audit; all15 log HP pairs per-case comparisons; optionally inspect last turns' live HP source frames for additional independently reviewable cases. Do not equate raw accepted totals with recognition accuracy.
7. Report main concise plus detailed per-mon traces; preserve initial coverage, frozen production, reference and all old sources. Final integrity incl original MP4 hash; no commits/pushes.

Latest tests95 passed (configuration domain, focused repair, inference integration, constraint trace);91 passed in focused+switch+Ditto+configuration selection after identity fix. First broad1384 tests belonged previous task, do not claim that as new B24 validation.


## Resume audit — 2026-11-01

First frozen/historical verification passed. B24 damage/configuration/inference/focused suites:128 passed in18.06s. Current run log: `.cache/battles/sample_battle_24/evaluation/fresh-b24-20261101-v1/resume-inference.log`.

Process-check correction: the initial lowercase-python filter missed existing macOS `Python` PID24323. The resumed task PID25307 uses current context fingerprint0853143dab85ff88, while the old process was writing8a25d0dd9e02c2d9. Stopped the stale-fingerprint process with SIGTERM; all existing JSONL attempts retained. No production acquisition was repeated. Inspect processes case-insensitively on future resume. Current context is necessary because current fingerprint has no complete stage. Do not modify context dependencies while running.

Bounded13-article 52Poké snapshots and revision/hash index saved locally under evaluation/.../source-reference/. Runtime remains offline. Broader relevant portable regressions running; final reporting pending current context/inference.

Resume broader portable regressions COMPLETE:1163 passed,4 deselected in1031.26s. Separate focused128 passed. Log resume-regressions.log. Adaptive source manifest now checked:complete, planned_windows0, no dense episodes.

Cache root cause corrected:TeamProfiles.load refreshed updated_at_utc. Exact previous fingerprint reconstructed with timestamp alone; completed da213a54b8e86b2e reused as stable864cf3718277d9d9. Both incomplete repeats preserved and marked interrupted. No more context replay. New regression3 passed. Current log resume-inference-stable.log.

After stable-input reuse, first inference3/5 exact; empty-slot adapter repair4/5 exact. Both retained. Compound-stat magnitude grammar repaired with dedup/retraction test; current context is legitimately invalidated by state helper dependency, rebuilding one scoped diagnostic stage. Current log resume-inference-compound-stage.log. New validation135 passed then38 passed. Report pending rerender from latest final trace.

Final integrated portable suite after all resume fixes:241 passed,1 deselected in63.77s. final-regressions.log. Current context replay remains active; await inference and final rerender/integrity.

FINAL COMPLETE:trace7c3ffb267920ed10;5/5 opponent HP relations numerically evaluated;2 Attack member marginals narrowed;0 inference contradictions;0 receipt differences. Endpoint matches15/15, diagnostic-supported complete12/15 (not recognition accuracy). Final241 passed/1 deselected; integrity15062 unique files zero mismatches and original MP4 SHA matches. Report reports/B24-evaluation-20261101.md and docs/b24-evaluation-20261101/handoff.md current. No jobs, commits, pushes or next milestone.
