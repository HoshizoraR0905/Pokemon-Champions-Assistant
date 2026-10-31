# M3.2.2 offline deterministic Speed replay

**M3.4.2 received-damage extension:** [joint offensive-stat inference and validation](../reports/M3.4.2-offensive-stat-inference.md). Use `?battle=11&damage=1` or the checkbox for the optional, precomputed two-layer damage overlay; Speed-only artifacts and historical figures are preserved.

**Latest Mega ability correction:** [mapping, corrected counts and current packages](../reports/M3.3-M3.2.2-mega-ability-mapping.md). The previous direct current-form ability filter is superseded; all 68 complete Mega Raichu Y member records are eligible.

**Battle 11 showcase:** [standalone report, captured figures and nature audit](m3.2.2-battle11-speed-report.md).

## Current completion and reviewed replay (2026-10-22)

The Stage A design below is retained for its adapter/recovery contract. Its old
zero-admission UI gate describes the automatic audit alone. The separate
source-reviewed layer and interactive replay are now implemented and validated.
See the [final report](../reports/M3.2.2-real-speed-replay-validation.md) for actual
Battle 11 results, inherited assumptions, the verified Rage Powder/Follow Me priority correction, test
receipts and measured performance. Automatic Stage A admission remains zero;
Battle 11 adds one source-reviewed-order comparison and three conditional ones.
These counters do not establish unconditional Champions mechanics certification.

Open the tested local page:
`http://127.0.0.1:8767/scripts/templates/speed_replay.html?battle=11`.
If needed, start the existing server:

```sh
.venv/bin/python scripts/serve_visual_review.py --port 8767 --page 'scripts/templates/speed_replay.html?battle=11'
```

All three repaired replay packages now use the corrected M-C catalog and
source-reviewed transformations/switches. Current priorities are Fake Out +3,
Follow Me +2 and Rage Powder +2. Old fingerprints remain historical snapshots.
See the [targeted repair report](../reports/M3.2.2-replay-correctness-repair.md). Reuse them through each battle's
`.cache/battles/sample_battle_N/m322-reviewed-speed/latest.json`. For a changed review, reuse Stage A and run
`scripts/build_reviewed_speed_replay.py --battle N`. Only an invalidated action or
catalog dependency needs the scoped Stage A command first. For Battle 11, the
reviewed builder also takes `--reviews tests/fixtures/battle_evidence/battle11-speed-review.json`.
Reviewed results, empirical support and replay JSON each have manifest hashes and
checkpoints. Historical fingerprints remain available. The UI filters updates by
availability time and shows full-model versus empirical results separately.

`metagame/published/speed_support.py` uses the existing scoped published-team
store read-only. Published joint support is descriptive, with explicit missing
fields; it is never a legal-domain bound or an unmeasured probability prior.

## Original Stage A contract and gate

The remaining sections document the original automatic Stage A path. References
to a gated/unbuilt UI in those sections are historical, superseded by the current
reviewed layer above; the zero-admission behavior of that CLI is preserved.

Stage A reuses sealed M2.4 recognition/StateEngine evidence, frozen visual v2.2,
compatible M3.4.1 action artifacts, the original reviewed TeamConfiguration and
M3.2.1 v2 inference. It does not invoke the old Bayesian analysis, recognize video,
replay StateEngine, alter visual defaults, or build another mechanics engine.

The requested Stage B is gated: when no real comparison can enter the solver,
stop with an evidence/model blocker report. A generated JSON or a working web
page is not semantic acceptance. See the [Stage A results](../reports/M3.2.2-real-speed-replay-validation.md).

## Run one recording at a time

```sh
.venv/bin/python scripts/report_speed_replay.py --battle 10 --visual-version v2.2
.venv/bin/python scripts/report_speed_replay.py --battle 11 --visual-version v2.2
.venv/bin/python scripts/report_speed_replay.py --battle 12 --visual-version v2.2
```

Each command uses `BattleArtifacts` and writes a fingerprinted directory at
`.cache/battles/sample_battle_N/m322-speed-replay/<fingerprint>/`. It contains
`manifest.json`, `replay.json`, `summary.md`. A `latest.json` pointer records the
current result. Small per-recording reports are
`reports/battles/sample_battle_N/M3.2.2-speed-inference-validation.md`.

Compatible completed outputs are hash-checked and reused. Input identity includes
the recognition/event caches, original snapshot source, source video SHA and file
identity, selected action artifact, frozen visual version, original team profile
and roster frames, mechanics/solver/data dependencies, bounds and review content.
Original videos are checked against acquisition SHA-256 once; an atomic receipt
reuses that hash when file identity is unchanged. Hashing does not decode video.
Successful source stages and old fingerprint directories survive later failures.
Manifests record the failing stage and exact repeat command.

## Chronology and source selection

`available_time` uses explicit evidence timestamps, uncertainty bounds and required
source times. It never applies an uncertain observation before its safe upper
bound. Retrospective frozen phase boundaries remain labeled as such. They do not
supply hidden item/ability/stat knowledge.

`causal_state` uses the existing before/after snapshots, stripping facts whose
source event IDs are missing, invalidated or later than the selected cutoff.
Future instance records are also removed. The recognition cache's `context_after`
is deliberately unused: it can contain later preview context on early frames.
The system does not reconstruct early states from final-state identities or items.
Existing Bayesian/own-stat fields in old reports are not copied into the replay.

`TimeIndex` selects the last row **at or before** the chosen timestamp, for both
source frames and inference snapshots. No future frame is substituted. Actual
PTS/time base, seek origin, source image/hash and available chunk/global-time
metadata are retained. Frame density remains that of the existing cache.
The original container duration is reused from sealed decoder metadata; the last
cached frame timestamp is separately reported. Cached image files are referenced,
not duplicated or regenerated. Action-cited image hashes are checked.

The timeline includes recognized moves, transformations, activations/revelations,
statuses/stages, weather/terrain/Trick Room, switching/fainting, source confidence,
and v2.2 phase changes/normal-command intervals. Per-action `before_announcement`
and `after_announcement` are snapshots around the announcement, **not** a claim
that the entire move had completed. `following_observed_changes` are chronological
events up to the next announcement; causal attribution is not invented.

## Configuration domains and certified constraints

`legal_projection` and `universe` reuse `champions_attainable_stats` and the current
canonical KnowledgeBase. They retain all Speed SP/numerical alignments and compact
joint training budgets. Forms, native abilities and required Mega stones come
from the same catalog. Concrete held-item hypotheses include the 166 catalog
items plus explicit none for an unrestricted base form. Speed/order-equivalent
items share a solver branch; this does not eliminate concrete item hypotheses.
Required current-form stones restrict the applicable item domain.

Domains are represented as a complete factorized projection with an explicit
Speed/order configuration-class count and training-domain reference. No feasible
Speed explanation is sampled or silently dropped. This is a pinned native-ability/catalog/stat projection,
not independent certification of every game regulation or ability-transfer history.
Unsupported relevant item/ability branches and class products above the v2 limit
are exposed. The number of ordinary neutral items is not a resource blocker.
Recognized banners display their time/provenance but do not automatically become
reviewed restrictions of the initial configuration universe.

`legal_unmodified_speed` is the complete form-specific **stat projection**. For an
unresolved current form, it is explicitly the union of retained catalog forms;
`current_form` remains null and no base/Mega branch is chosen.
`certified_order_feasible` remains null until supported order evidence is admitted;
null does not mean an empty set. A later unresolved comparison retains previously
certified information. A supported contradiction remains empty and is not reset.
Earlier-form projections are not silently asserted as current after an unresolved
transformation. Original configured Speed, current-form unmodified Speed and
effective Speed are separate.

`DeterministicHistory` resubmits original persistent configurations and admitted
observations to existing `infer_speed(schema_version=2, ...)`. It does not implement
new inference. The engine retains correlations, ties, Quick Claw alternatives,
mid-turn changes and forms. Duplicate IDs with identical content, and equivalent
physical observations submitted under another relation ID, are ignored;
revisions require a new fingerprinted replay. Distinct source individuals are
never merged just because the species matches, and same-ID reentries retain history.
No likelihoods, posterior weights or empirical priors are created.

`speed_items.py` supplies an adapter projection, not a second item/Speed engine.
`speed-item-projection-v1.json` records the canonical catalog hash and pinned
Showdown source identity. In the 166-item catalog, direct Speed/order callbacks
occur for Choice Scarf, Iron Ball and Quick Claw. Ordinary comparisons therefore
need these three classes plus one equivalent neutral class. Compatible Mega stones
stay distinct even though they have no direct Speed multiplier, preserving their
correlation with form transformations. Concrete names/IDs survive in
`item_equivalence_classes`; `underlying_item_configuration_count` is separately
reported from the projected `configuration_count` used by the solver.

The equivalence is conditional on supplied HP, status, grounding, switching and
activation history. Indirect effects through these states are not silently erased
or automatically simulated. Missing Gale Wings HP or Grassy Glide grounding stays
unknown; Unburden still requires explicit item-loss history, and a known held item
cannot be neutralized to hide an active-Unburden contradiction. All numerical Speed,
priority, activation and form behavior still comes from the existing v2 engine.

## Admission and optional targeted review attachments

`audit_pair` distinguishes definite non-Speed comparisons, unverified evidence,
and missing v2 handlers. Announcement counts never prove the complete pending set.
Different native effective-priority brackets are excluded from Speed comparison;
unknown priority alternatives do not become unconditional inequalities.
Missing Quick Claw text is never converted to nonactivation.

Only fields capable of affecting that comparison are required. There is no gate
on defensive stats, damage, unrelated stat stages, absolute game-turn numbers,
or HP outside an applicable Gale Wings condition. Explicit finite state alternatives
are allowed; exact weather/stage/status knowledge is not mandatory. Finite unknown
stage/status/Trick Room possibilities are retained in deferred diagnostics rather
than treated as neutral. Their full product is not submitted before queue coverage
is certified. V2's closed handler set and resource limits remain visible boundaries.

Verified full Team 7 records are loaded from
`tests/fixtures/battle_evidence/sample-team7-reviewed.json`, with original frame and
video hashes and the user's unique-six-species binding policy. Each recording's
roster source hash and timestamp are verified. Configured values are attached only
to separately identified own source individuals at/after binding availability.
They do not overwrite an unknown current form, current ability, or held-item state.
Changed forms use the original verified training/alignment and shared Champions
calculator, and require compatible species/stone continuity.

A small JSON review can be supplied using `--reviews PATH`, keyed by an existing
retained relation ID. It supplies:

- `verified`, `origin`, `reviewer` (`kind`: agent/human, plus `id` for recorded
  evidence), `available_at`, and v2 source/basis/confidence `evidence`.
- `pending_coverage_complete=true` and `pending_action_ids`, referring only to
  recognized source action IDs in one known local decision.
- A complete v2 `state`, `subject`, `initial_changes`, finite `alternatives`,
  per-action `changes`, `outcomes`, and Quick Claw `activation` records.
- `configuration_domain`: arguments to existing `configuration_domain`, plus
  `complete_given_evidence=true`, `available_at`, and source `evidence`.

The adapter constructs v2 actions from immutable recognized moves/individuals;
reviews cannot replace them, fabricate own Speed, cross battles/unknown turns,
or mix synthetic and recorded origins. For recorded attachments every evidence
source must resolve to an existing event ID, frame source ID or frame path.
All required source times raise the effective admission time if necessary. A
review requiring a later item revelation cannot narrow an earlier snapshot.
Synthetic tests are explicitly labeled and cannot certify actual recording coverage.

Later item knowledge constrains the existing persistent universe through a new
observation. Substituting a smaller configuration list for the initial universe is
rejected. This avoids applying later revelations retrospectively to earlier actions.
Conflicts and unsupported cases retain evidence/explanations for review.

## Validation and UI boundary

```sh
.venv/bin/python -m pytest -q tests/test_speed_replay.py tests/test_dynamic_action_order.py \
  tests/test_speed_order.py tests/test_action_order.py tests/test_visual_v22.py \
  tests/test_visual_review_server.py -m 'not local_artifacts'
```

The new tests distinguish synthetic mechanical truth from real recognition. They
exercise causal source filtering, exact floor selection, time uncertainty, item
revelations, switches/reentries, Mega changes, dynamic paralysis, Tailwind/Trick
Room, priority/Quick Claw alternatives, legal gaps, duplicates, contradictions,
resource exhaustion, and actual adapter→v2→snapshot narrowing in synthetic inputs.

Python frame/snapshot lookup latency is measured separately from preprocessing
and solver time. It is **not browser responsiveness**. When Stage A admits zero
real constraints, no new UI or working replay URL is claimed. The existing
`scripts/serve_visual_review.py` is inspected and preserved; Stage B can later reuse
its localhost-only byte-range server once trustworthy replay evidence exists.


## Repaired semantic projection

`scripts/build_reviewed_speed_replay.py` retains the original `timeline` and adds
`action_timeline` transactions, canonical `species`, evidence-timed aliases,
`occupancy`, `support_catalog` references, `observed_builds` joint records and
`form_configuration_support`. All current form/count/domain-reference fields are
updated together; a confirmed Mega does not retain stale unresolved-form flags.
`battle_evidence/speed_replay_projection.py` derives these from sealed sources and
`tests/fixtures/battle_evidence/replay-transitions-reviewed.json`.

An incoming transaction identity becomes visible only at `arrival_time`. Reviewed
aliases do not merge pre-return snapshots. Mega snapshots apply at confirmation
upper bounds; original training, stone and source encounter IDs remain available.
The separate `m322-actions` cache can refresh deterministic action projections when
a catalog invalidates old action fingerprints, without invoking the Bayesian
analysis stage. It verifies sealed inputs and preserves the old M3.4.1 outputs.

Default cards show observed joint builds followed by full reference support.
Details expose exact gaps, incomplete records, source/build IDs, joint training
domains and unsupported native branches. Reference support retains supported
non-neutral item alternatives. Unsupported branches or uncertified modifiers
remain explicitly unresolved; observed support supplies no probability prior.
