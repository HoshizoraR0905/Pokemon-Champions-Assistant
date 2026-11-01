# B20–B23 integration audit handoff

Scope: saved-evidence inference only. No recognition, decoding, production CLI,
commit, push, benchmark rewrite, identity merge, or next milestone.

The repository already had uncommitted constraint tracing, item rules and old
reports when this task began. Those changes remain in place. In particular,
`battle_evidence/life_orb.py` and `team_items.py` were not edited in this task.

## Evidence and implementation

- `integration-review-20261101.json` records the four manually inspected saved
  preview images, hashes, exact six-member roster and opening source event.
  All four show Team 7. Existing user same-build policy is retained.
- Reuse `tracking.knowledge_grounding`, `form_stats`, `StateEngine`, saved HP
  resolutions, `battle_evidence.turns`, original command cycles and opportunity
  snapshots, `damage.inverse.infer_attack_stat`, and `speed_order` v2.
- Opt-in opening review establishes known neutral field, side conditions,
  stages and initial major status. The default partial-recording state remains
  unknown. Reference language interpretation quantifies complete ordinary and
  大幅 stat announcements. Ordinary switches reset stages; special inherited
  stages remain unresolved. Explicit coverage gaps invalidate known modifiers.
- Legacy screen activation announcements are normalized to start transitions
  without changing raw source receipts or IDs. Event endings and existing
  duration semantics remain in the original engine.
- Native/current form stats map through the existing SP/alignment calculator.
  Mega Garchomp Z defensive stats are not replaced with normal/Mega stats.
- Unknown items, native abilities and critical hits retain alternatives. Items
  and abilities that affect grounding stay correlated under terrain. Defeated
  HP endpoints provide lower damage bounds, rather than falsely exact damage.
- Narrow forward additions cover explicit Metronome counts 0–5, Normal Gem,
  Unnerve/resist berries, relevant connected-hit-neutral abilities and Hammer
  Arm damage. No new damage formula or general solver was introduced.
- Four-opportunity certification is a narrow admission adapter in the existing
  turn module, not a replacement turn engine. Switch/forced-replacement cycles,
  repeated or missing actions, internal boundaries and gaps remain unresolved.
  Effective priorities, modifiers, order items and ties remain M3's job.
- Full v1 traces and source run outputs are untouched. The previously reviewed
  B22 Life Orb window is reused by hash; it is not backdated into earlier hits.
  B23's sealed `team_profile_linkage=unbound` remains its original first-run
  result. Reviewed diagnostic attachment is explicitly a separate result.

## Cache and recovery

New namespace: `.cache/battles/sample_battle_N/diagnosis/hidden-integration-20261101-v1/`.
`manifest.json` records source identity, context fingerprints, stage status,
progress, errors and output checksums. Context JSONL prefixes are fsynced;
inference prefixes use atomic `partial.json`. Completed stages are reused.

During development, the known-inactive baseline exposed old screen `observe`
activations, and ordinary stage announcements exposed missing magnitudes. These
were genuine context invalidations. Earlier diagnostic context/trace versions
were retained, never deleted. Changes confined to damage/order adapters require
only inference reruns against completed compatible contexts. No disconnect was
used as a reason to invalidate recognition or replay.

Run one battle at a time:

```sh
.venv/bin/python scripts/trace_hidden_constraints.py --battle 20 --integration-audit --stage trace --resume
.venv/bin/python scripts/trace_hidden_constraints.py --battle 21 --integration-audit --stage trace --resume
.venv/bin/python scripts/trace_hidden_constraints.py --battle 22 --integration-audit --stage trace --resume
.venv/bin/python scripts/trace_hidden_constraints.py --battle 23 --integration-audit --stage trace --resume
.venv/bin/python scripts/report_inference_integration.py
```

Do not start a duplicate while the corresponding manifest PID is running.
After source changes, use its new fingerprint; never replace an old immutable
trace. Inference prefixes are audit checkpoints; cheap inference restarts from
cached complete contexts rather than importing an unsafe partial engine state.

## Validation and limits

Portable focused regression command:

```sh
.venv/bin/python -m pytest -q tests/test_inference_integration.py tests/test_constraint_trace.py tests/test_action_order.py tests/test_mega_form_stats.py tests/test_battle_state.py tests/test_stateful_mechanics.py tests/test_preview_switch_fixes.py tests/test_event_driven.py tests/test_inverse_damage.py tests/test_damage.py tests/test_speed_order.py tests/test_dynamic_action_order.py tests/test_command_reconciliation.py tests/test_trainer_opening.py tests/test_git_artifact_policy.py -m 'not local_artifacts'
```

Final integrated run: **1203 passed, 5 deselected** (45.78 seconds). The initial regression run caught
the historical oracle adapter hash changing; it was restored exactly, and the
new explicit Metronome option uses a separate test-only oracle adapter. Original
oracle fixtures/manifests were not regenerated. Six Metronome counts and the
scoped new hit handlers match the pinned Champions reference. Portable tests
include a compact curated projection of the real B22 Rock Slide input, explicit
neutral/unknown distinctions, stage/switch behavior, exact-six attachment timing,
sealed-source preservation, same-turn admission, ties and unknown order items.

All four final inference passes are complete. The report records 30 certified
local relations, 5 numerically usable same-priority Speed comparisons (1 actual
source-lineage reduction), and 11 solved damage relationships (5 Attack and 1
Special Attack reduction events). With unresolved source IDs unioned, 2 roster
Attack panels and 1 Special Attack panel narrow; no full roster Speed panel
narrows. There are no new empty candidate sets. Single-hit marginal intersections
remain conservative, not a joint shared-item/SP/history feasibility proof.

Original B16–B22 protected inventory: **46,627 files, zero hash mismatches**;
B23 initial freeze: **10,602 files, zero hash mismatches**; B23 adaptive freeze:
**2 files, zero hash mismatches**. The four video-only seals and **40 complete
old v1 output/report checksums** passed. New traces passed strict JSON,
chronological availability, monotonic-domain and source-preservation checks.
B23's original initial-state linkage remains `unbound`.

The runner fingerprint is captured before long operations and checked before
publication, so editing the runner while a job runs cannot label old in-memory
code with a new on-disk fingerprint. Compatible completed state contexts were
reused for the final inference refreshes.

Final before/after counts are in the dated audit report. A completed artifact
stage is not recognition accuracy, complete semantic coverage, or milestone
acceptance. Original HP/visual conflicts, unaccepted receipts, unsupported
multi-hit inversion and unresolved encounter continuity remain visible.

## Sources and attribution

`integration-sources-20261101.json` records local reference hashes, retrieval
date, applicability and revision IDs read from permanent links. Revision-specific
snapshot requests returned HTTP 403; runtime stays offline.

- [52Poké: stat changes](https://wiki.52poke.com/wiki/能力变化): general stat
  announcement magnitudes and ordinary switching corroboration. Champions UI
  interpretation remains a labeled reference assumption, not independent game
  verification. Special inherited stages such as Baton Pass remain unresolved
  rather than being filled with ordinary neutral values.
- [52Poké: Aerodactyl Champions learnset](https://wiki.52poke.com/wiki/化石翼龙/Champions招式表):
  applicable Champions Rock Slide entry (physical, power 75), not a Generation 9
  availability substitution or equipped-slot claim.
- [52Poké: Metagross Champions learnset](https://wiki.52poke.com/wiki/巨金怪/Champions招式表):
  applicable Hammer Arm entry (physical, power 100).
- The existing `mega-stat-evidence-v1.json` preserves versioned form assertions,
  revision IDs and applicability. The existing reviewed Team 7 fixture preserves
  displayed SP, stat alignment, moves, held items, abilities and same-build policy.
- Executable arithmetic/rounding, Metronome, Normal Gem and Unnerve comparisons
  use local pinned `@smogon/calc` **0.12.0**, Champions generation 0, with its
  existing MIT attribution. Item legal/effect alternatives come from the existing
  versioned item registry, without usage frequencies or invented priors.

52Poké contributors retain article attribution/licensing; no article was copied
in full. Rendered permanent links exposed revision IDs 2609641 (stat changes), 2608736
(Aerodactyl Champions learnset) and 2608677 (Metagross Champions learnset).
Revision-specific fetches returned HTTP 403, so unavailable revision bodies were
not fabricated. No new crawler/importer was added.
