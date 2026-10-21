# M3.4 battle evidence reconstruction

`battle_evidence` adds read-only evidence infrastructure alongside the maintained
StateEngine. It consumes preserved events, saved replay receipts and optional
verified annotations/build bindings. Recognition, calculators, M3.4.1 likelihoods
and empirical databases retain their existing responsibilities. No inverse damage
or live overlay is invoked.

## Offline entry points

```sh
.venv/bin/python -m battle_evidence --battle 9
.venv/bin/python -m battle_evidence --battle 9 --annotations verified-annotations.json --builds verified-build-bindings.json
.venv/bin/python -m pytest -q tests/test_battle_evidence.py
```

`--battle` selects exactly one preserved production run from Battles 5–9, using the
same inputs audited in M3.4.1. The installed entry point is
`champions-battle-evidence`. There is no default all-video operation.

A run writes `.cache/battles/<id>/m34-evidence/<fingerprint>/manifest.json` and
`reconstruction.json`, through `BattleArtifacts`. Raw recognition inputs are never
rewritten. Outputs include normalized source-linked ledger, turn/window assignments,
immutable before/after snapshots, effect histories, integer HP transitions and
M3.4.1 admissions/rejections. These detailed generated files stay local.

The missing StateEngine projection stage runs once per compatible input/engine/
projector identity. It has a separate fingerprint under `m34-evidence/stages/`.
Replay progress and compact partial projections are checkpointed every 100 events;
a complete stage is reused by changed downstream annotation/duration/attribution
experiments. A failed replay retains partial projections and its error; rerunning
restarts that incomplete replay stage, not OCR or any successful stage. The existing
StateEngine does not provide a safe arbitrary-event resume contract, so partial
projections are diagnostics, not a silently resumed authoritative state. Run the
same scoped command to resume work. Historical fingerprint directories are retained.

## Evidence ledger and turns

`TurnReconstruction.consume(event)` receives an evidence projection, not a replacement
BattleEvent. Every source event retains its immutable ID, occurrence/action ID,
source position, original-event SHA, source type/IDs, timestamps, OCR uncertainty,
status and saved individual binding. Verified annotations are separate assertions
with provenance; they cannot rewrite source identity, time or raw OCR text.
Corrections require explicit reconstruction. Identical IDs are idempotent; revised
payloads cannot silently replace prior evidence.

A `turn_evidence` assertion requires a positive integer number, `verified: true`
and source evidence. It can contain an explicit start/end boundary, bounded time
interval, decision ID and verified execution order. Numbered actions with only a
heading remain in a partial turn. A confirmed start plus separate verified
`turn_continuity` evidence can establish subsequent membership. Both endpoints are
required for a complete turn. Regressions are reported rather than repaired.

Command cycles produce **ambiguous unnumbered windows**, not game turns. A command
checkpoint is a signal within a phase, not another boundary. Forced replacement,
phase transitions, elapsed seconds and timestamp adjacency do not increment a game
turn. Unknown membership is retained in `unassigned_actions`; candidate-window
membership is stored separately. Observed ledger order is separate from verified
execution order. Historical Battle Log headings require explicit chronological
integration before they can establish action-time state; capture time alone cannot.

## Effect durations

`EffectDurations` is a read-only inference projection over authoritative effect
observations. Keys include side/field and named effect. Each record retains activation,
start turn/intra-turn timing, initial duration support, remaining support, observed
changes, applied boundary ticks, source policy and uncertainty. Self/opponent
Tailwind are independent. Weather and terrain replacement are distinct from
coexisting named side conditions. Cancellation/expiration do not require inventing
a missing activation.

The pinned `duration-rules-v1.json` records 52Poké Champions-specific descriptions,
revision IDs, retrieval dates, rendered snapshot hashes, attribution and limitations.
Documented defaults are Tailwind 4 and Trick Room 5, including the activation turn.
Countdown bookkeeping occurs **after** a confirmed end-of-turn boundary; no relative
ordering of individual residual effects is inferred. An action snapshot can retain
an active effect that is expired in the later after-end snapshot.

A confirmed consecutive next-turn start can account for a missing preceding end
boundary once. Repeated boundaries do not tick twice. Missing turn continuity widens
the support and makes active state uncertain; seconds never decrement a duration.
An activation without a known turn yields a bounded/unknown countdown, not a guessed
start turn. An observation of an already active effect does not reset its clock.
Successful reapplication starts a new activation record; expiration history survives.

Weather, terrain, screens and item extensions accept explicit `initial_support`,
`duration_verified`, `duration_sources` and `decrement_at` evidence. Unknown extension
status may be represented by a documented support such as {5,8}; a known extension
can select {8}. The caller must establish the applicable activation mode and rule
coverage. The tracker does not assume every rain/terrain/screen message implies
that domain, or that Damp Rock/Light Clay is equipped. Unsupported duration rules
remain unknown. The checked Damp Rock Champions description supports an 8-turn
extended rain case; it does not identify a setter's held item in a recording.

## Known builds and immutable snapshots

`KnownBuilds.register(battle_id=..., instance_id=..., record=...)` requires verified
build and individual-binding provenance. A record contains explicit identity/form
and either a full Champions `training_points` vector plus numerical `alignment`, or
separately verified `observed_stats`. Conflicting calculated/displayed stats are
rejected. Partial metadata produces partial known stats, never default SP/IV/EV.
`ChampionsStats.calculate` supplies all six unmodified stats. Existing
`TeamConfiguration` records can be imported through `KnownBuilds.import_team` with
explicit battle-instance bindings; only manually verified fields are accepted.
`TeamProfiles.load` can supply that existing configuration object. Preview rosters
and similarly named Pokémon do not establish build bindings. Allocation display
columns are not automatically interpreted as Champions SP.

Snapshots project the StateEngine at actual replay prefixes, with provenance-bearing
identity, occupancy, current/max HP, status, stages, item/ability knowledge and field
facts. They retain last-observed facts as such: delivery order alone certifies no
dynamic continuity. A prefix containing future source time is withheld. No final
state is back-projected. The returned dictionaries are independent copies with
content-derived snapshot IDs; consuming later events cannot mutate earlier views.

Own stat views distinguish configured stats, stage-adjusted stats and full combat
modifiers. Existing stage arithmetic and M3.2 effective-Speed APIs are reused.
Unknown/suppressed ability state, item activation, Tailwind or other modifiers remain
unknown. Full offensive/defensive effective stats require an audited damage action
context; the infrastructure leaves them explicitly unknown rather than equating
stage-adjusted stats with final damage stats. Changed forms require new applicable
build/stat evidence. The strict default numerical Speed profile still declines
uncertified Champions ordering calculations.

## Exact HP changes and M3.4.1 adapter

`attribute_hp(before, after, causes, coverage=...)` separates raw displayed delta
from exact damage. Readings require individual, battle, continuity epoch, integer
HP/max, ordered source positions and provenance. The cache adapter retains accepted
own HUD readings and repeated-source support. Two agreeing distinct accepted sources
at OCR confidence ≥.98 provide explicitly labeled recognition support; this is not
independent manual recognition validation. Intermediate/unsupported readings and
max-HP/form/identity changes cannot manufacture a clean damage measurement.

An eligible attack needs a unique verified causal event, a cataloged damaging move, attacker/move/receiver,
target membership, a damage-resolution snapshot, event position between readings,
complete cause coverage, single hit, and verified absence of redirection/substitute.
Spread attacks additionally need per-target resolution. Multiple attacks or causes,
residual loss, healing/draining, recoil, self-damage, item/ability effects, and unknown
causes remain separate. A fainting HP loss is censored unless exact uncensored
damage is independently established. No inverse calculator is called.

Actual offline causes are **candidates**, including intervening announcements and
the last preceding announcement that might still be resolving; proximity is never
confirmation. Missing complete causal coverage excludes damage inference.

The Speed adapter requires verified same turn, same order decision, execution order,
actor/move identities and priorities, an evidence-backed contemporaneous decision
snapshot, continuity and own verified Speed. It rejects intervening state changes
that need an unaudited ordering model. Source occurrence IDs become underlying action
IDs, so relabeling cannot duplicate evidence. It calls the existing M3.4.1 admission,
likelihood and per-individual belief ledger; strict/provisional mechanics profiles
and correlated-pair exclusion remain intact. No separate Bayesian formula is added.

## Historical views and replay drift

The default repository experiment also consumes the small agent-reviewed
`tests/fixtures/battle_evidence/real-log-excerpts.json`; use
`--historical-reviews <path>` to select another reviewed file. It preserves displayed
headings 1/4/3 in Battles 5/6/8, raw visible excerpts, exact frame hashes and the
review's limitations. These reviews are not independent human ground truth.
Battle 6 additionally reuses its existing assembled historical log. Duplicate log
entries retain stable IDs, and historical capture times remain distinct from unknown
execution times. These partial historical turns are exported separately from live
membership and never receive an invented dynamic state or biological instance link.

Every experiment compares the current-code replay's final hash and compact projected
state against the saved versions. Disagreement is exported in `replay_validation`,
including affected projected paths, and attached to snapshots. This distinction is
necessary when preserved caches predate current working-tree logic. It does not
rewrite the historical state or certify earlier prefixes from final agreement.

The structured-snapshot adapter can construct M3.2 contexts from known projected
form, stage, status, ability/item and field facts. Activation/suppression, other
effects and absent Tailwind still require explicit contemporary evidence; no empty
or false modifier defaults are inferred from missing observations. A fully reviewed
`decision_context` can alternatively be supplied as a snapshot annotation. Both paths
use verified own configured Speed and the same M3.4.1 gates. The
`uncensored_damage_verified` HP exception specifically attests that uncapped damage
equals the displayed loss; evidence that an attack merely occurred is insufficient.
