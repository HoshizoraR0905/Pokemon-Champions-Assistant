# B16 — activation banners and event-linked HP

2026-10-28. Development/regression on B16; not held out and not independent human annotation accuracy. Baseline `b16-semantic-state-20261027-v1` remains intact. Acquisition `b16-banner-hp-20261028-v5`; final replay/evaluation `b16-banner-hp-20261028-v6`. No commit/push or next milestone.

The existing Recognition Tools → Visual Extraction → EventParser / StateEngine chain remains authoritative. The same sealed reference is reused without new facts, denominator changes, or Battle Log injection into acquisition. Changes below are measured against original source-pixel evidence, followed by actual applied-state receipts and read-only replay verification.

## Measured reconstruction changes

| Measure | Baseline | Updated |
|---|---:|---:|
| Ability activations, correctly attributed and applied | 4/6 | **6/6** |
| Item activations, correctly attributed and applied | 1/3 | **3/3** |
| Weather transitions | 4/5 | **4/5** |
| Numeric HP endpoint pairs, damage + healing | 14/21 | **18/21** |
| Exact own absolute HP pairs | 7/10 | **10/10** |
| Opponent displayed percentage-point pairs | 7/11 | **8/11** |
| Independent actual HUD-zero endpoints | 0/3 | **3/3** |
| Explicit burn-cause notices retained in affected HP history; amount unknown | 0/2 | **2/2** |
| Numeric HP changes linked to a cause in this live run | 0 | **0** |
| Tailwind announcements / correct side state | 2/2 | **2/2** |

The four newly reproduced numeric pairs are `log:51:0`, `log:94:0`, `log:109:0`, `log:112:0`. For each, the baseline still lacks a compatible same-instance endpoint pair even when tested against the updated alignment window. **All four gains require new accepted endpoint evidence; zero gains are credited to alignment-window changes alone.** Their exact endpoint event IDs, times, units, hashes and the baseline-presence check are in [before-after.json](before-after.json).

Total reconstructed event facts (including recognized-only notices): **107/124 → 120/124**. Applied event facts: **97/124 → 110/124**; 10 recognized-only notices remain. Actual supported state fields: **154/191 → 175/191 (91.62%)**. Final event statuses are 110 correct/applied, 10 recognized-only, 4 missing; state statuses are 175 correct/applied, 8 recognized-only, 8 missing. No incorrect aligned reference fact is reported; whole-match false-positive precision is unmeasured. HP endpoints, differences and zero checks share evidence and are not independent statistical samples.

The two burn messages have `recorded_observation` receipts and explicitly supported causes in the correct individual's authoritative HP ledger; they receive no numerical HP-damage credit. The numeric reference facts have no independently verified numeric cause/amount labels. Numeric causal accuracy is therefore **unmeasured**, and this run produces no optional numeric cause link. Successful synthetic cause-link contracts do not establish real-video causal coverage.

## Failure by stage

| Evidence / stage | Baseline failure | Changed behavior |
|---|---|---|
| Right Pelipper / Drizzle, 131.005 s: visibility | Holder sprite joins two text baselines; no banner candidate reaches OCR | Right text crop ends before sprite; two rows are independently read |
| Left Charizard / Drought, 187.015 s: visibility/OCR/normalization | Already succeeds | Retained; exact species and ability IDs, original evidence and separate sun announcement |
| Right Pelipper / Drizzle, 668.53 s: visibility | Global blue-color heuristic falsely identifies rainy battlefield as a detail panel and vetoes banner extraction | Local dark banner/two-line evidence owns acquisition; literal possessive species suffix and canonical two-variant consensus gate emission |
| Side/instance binding | Species-only context is ambiguous when both sides have Pelipper active | Source-calibrated fixed-layout side evidence plus a unique active species on that side; uncalibrated layouts and duplicate same-side instances remain unresolved |
| Item activation | Two Leftovers activations absent upstream | Same left/right extraction and exact item normalization as abilities; activation records no consumption or numeric healing |
| Zero HP visibility | Gray name panels fail colored-name gate at all three reference zeros | Gray panel + white label + empty bar admits OCR; color itself never supplies a zero |
| HP acquisition | Full-card gate and lack of periodic HP refresh can omit useful reads | Independent digits/bar signatures, new visibility, changed HUD, three-second message/banner opportunities and two-second periodic refresh; COMMAND throttling cannot suppress changed HUD/banner evidence |
| Zero HP parsing | `value or ""` discards numeric zero | None-only fallback; observed zero, unreadable reading, hidden HUD and unknown state remain distinct |
| Burn/cause semantics | Explicit burn residual notices have no supported causal HP observation | Literal affected-subject notices enter that individual's existing HP ledger; absent amounts remain absent |
| Remaining opponent HP baselines | `100→67` (Garchomp), `25→0` (Archaludon), `62→33` (Pelipper) have no accepted before endpoint on the corresponding bound live instance | After endpoints 67%, 0%, 33% are read; intermediate 81%, 19%, 53% do not establish the missing baselines |
| Remaining sunlight announcement around 529.5–530.5 s | OCR `日照变強了！` / `日照变强了！`, confidence 0.861–0.905, does not reach occurrence admission | Still missing; no threshold reduction or weather inferred from Drought |

The user confirmed the example times: **02:11 is right Pelipper; 03:07 is left Charizard**. Production FFmpeg PTS-based extraction rechecked these source moments. OpenCV random-seek probes were inconsistent and excluded. Curated source crops and their frame SHA256/placement metadata are in `tests/fixtures/battles/sample_battle_16/banner_hp_v1/`; fixed-layout calibration and its limits are in `docs/b16-banner-hp/banner-side-calibration.json`.

## HP evidence and limits

The zero readings are actual source OCR: self Venusaur **0/156** at 366.5117 s, self Pelipper **0/164** at 690.5 s, opponent Charizard **0%** at 720.005 s. A faint announcement invalidates stale positive current HP but does not manufacture a zero endpoint.

HP history retains original endpoint evidence, affected instance, compatible unit, observed baseline, signed delta and optional cause-event IDs. Opponent deltas are displayed percentage points, never absolute HP. An explicit numeric before/after message supplies a delta even without an earlier HUD baseline. Acquisition `hidden` means no eligible HUD card was detected, not proof of the physical reason for its absence. Unreadable visible-card reads and their state receipts remain auditable; neither category overwrites a known number with zero.

Literal cause grammars cover move damage/healing, recoil and named self costs (including Flare Blitz / Belly Drum), explicit item or ability sources, burn/poison, Stealth Rock, Sandstorm and a Perish Song countdown-zero notice. These are text interpretations, not new Champions mechanics, availability checks, damage formula rules, or learned priors. Effects without a recognized literal grammar remain unknown. An item/ability banner alone does not establish HP damage, healing, consumption or weather.

The affected individual and source holder are separate; a uniquely observed holder can have its own instance link. Cause events survive without numbers. Optional numeric links require exactly one explicit affected-instance cause notice between compatible observed endpoints and the appropriate change direction. Intervening unscoped attacks, switches, fainting, coverage gaps, unreadable HUDs, other activations or competing HP effects veto attribution. Same-frame ordering does not establish subframe physical timing. Multiple spread/recoil/item effects are never forced into one-to-one temporal matches.

## Reuse and implementation

Only saved original source pixels and compatible same-model crop predictions entered acquisition. There are **1,276 saved inspected frames**; **232 COMMAND monitoring-only sampling cells lack saved pixels**. This is a cached-pixel regression, not a fresh full-grid 2-FPS acquisition or speed benchmark. Sampling remains 2 FPS; HP OCR refresh is a separate schedule. Updated geometry required 555 additional OCR model calls across development stages (95 + 18 + 442); successful outputs were preserved. Final acquisition added zero model calls, and final replay decoded no frames and invoked no OCR/icons.

Intermediate v2 replay and v4 acquisition were intentionally interrupted after specific newly discovered defects; successful earlier stages remain. Final progress, invalidation reasons and exact scoped resume/evaluation commands are in `docs/b16-banner-hp/progress.md`. No baseline cache/report was deleted or overwritten.

Changed modules: `recognition/visual_evidence.py`, `identity_modes.py`, `event_schedule.py`, `fast_video.py`, `fast_profile.py`, `identity_flow.py`, `parsers.py`, `event_report.py`; `battle_events/message_patterns.py`, `parser.py`; `tracking/evidence_fusion.py`, `state_engine.py`, new `hp_causes.py`. Evaluation extends `scripts/benchmark_b16_state.py` with separate run/reference selection and verifies explicit cause notices in the affected instance ledger; new `scripts/summarize_banner_hp_regression.py` publishes unit-separated before/after pairs. Tests and source crops are in `tests/test_banner_hp_tracking.py` and the fixture directory above. Existing unrelated working-tree edits were preserved.

The existing reconstruction command accepts the new event-driven version. Its replay-only allowlist additionally includes optional `tracking/hp_causes.py` metadata; geometry, OCR, parser and schedule fingerprints still must match. Tests verify byte-identical observation reuse and geometry-change rejection. No alternate recognition pipeline or authoritative state was introduced.

## Validation and remaining work

Final relevant portable regression suite: **436 passed, 9 deselected** in 125.79 s (`-m 'not local_artifacts'`). No present artifact failure was reclassified as missing. These are focused repository regressions, not a complete rerun of the 2,592-test historical suite. `git diff --check` passed. Read-only evaluation reproduced every per-event state hash, application status/reason and final state from the sealed updated run.

The remaining four missing reference facts are the three opponent baseline pairs above and one low-confidence sunlight announcement (`log:72:0`). Ten previously recognized-only effectiveness/reaction notices retain their original limited state applicability. Runtime still has **30 deferred HUD observations**, all `message_episode_occupancy_unresolved`, and the same baseline ability `visual_fact_disagreement` at 488.0317 s (`event:51065f0dbabb3ef974ce090b`); no new conflict was introduced. Lower deferred counts are not used as a success measure.

Further work would require evidence for the absent opponent baselines, a justified solution to the low-confidence sunlight reading, and independent numeric causal annotations / additional real source examples. No new sampling rate, broader video campaign, mechanics inference milestone or legacy adapter was introduced to fill those gaps.

Artifacts: [before/after and gain audit](before-after.json), [reference facts](reference-facts.json), [event comparisons](event-comparisons.json), [state comparisons](state-comparisons.json), [metrics](metrics.json). Sealed predictions, source snapshots, monitor rows, checkpoints, stage manifests and test logs remain under the matching `.cache/battles/sample_battle_16/` runs. Reproduce only incomplete stages with the commands in `docs/b16-banner-hp/progress.md`.
