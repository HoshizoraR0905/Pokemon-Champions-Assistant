# M3.4.1 executed actions and Speed inference

Visual v2.2 is frozen and stays opt-in. This milestone adds read-only analysis in
`battle_evidence/actions.py`, `action_inference.py` and `action_offline.py`.
Recognition, StateEngine, stat arithmetic, metagame priors and the production
visual-version selection are unchanged.

## Sources and mechanics scope

The maintained KnowledgeBase Champions catalog supplies move priorities, native
form ability domains and legal item candidates. Its entries give Fake Out +3,
Protect +4 and Trick Room −7. The existing SP/alignment configuration enumerator
and Speed calculator own all stat arithmetic.

The [52Poké priority article](https://wiki.52poke.com/wiki/优先度) explains bracket
comparison and distinguishes priority changes from within-bracket ordering. Its
revision 2599726 was retrieved on 2026-10-21. The
[Prankster article](https://wiki.52poke.com/wiki/恶作剧之心), revision 2618394,
includes a Champions description row. This is community documentation, not
independent official certification of every interaction. Source URLs, revisions,
dates, hashes, attribution and licensing are recorded in
`battle_evidence/order-mechanics-v1.json`; the original two untracked audit files
were preserved unchanged. Local snapshots remain under
`.cache/m341-actions/sources/`. Runtime analysis performs no network access.
52Poké text is attributed to its contributors under CC BY-NC-SA 3.0; no article
dump is redistributed in the repository.

The executable reference is Pokémon Showdown commit
`3a766f2cfb5e51c1e428cfe87d0dba91a8f01640` (MIT, Pokémon Showdown contributors).
[Champions scripts](https://github.com/smogon/pokemon-showdown/blob/3a766f2cfb5e51c1e428cfe87d0dba91a8f01640/data/mods/champions/scripts.ts)
declare simulator generation 9. The inherited
[queue update](https://github.com/smogon/pokemon-showdown/blob/3a766f2cfb5e51c1e428cfe87d0dba91a8f01640/sim/battle.ts#L2917)
recomputes pending Speed and sorts before subsequent moves. That establishes
simulator-reference behavior; it does not independently verify Champions queue
timing. Real mid-turn changes therefore continue to defer numerical inference.
The supplemental downloaded files have retrieval/hash receipts in
`.cache/m341-actions/sources/queue-timing-receipts.json`.

[Inherited item handlers](https://github.com/smogon/pokemon-showdown/blob/3a766f2cfb5e51c1e428cfe87d0dba91a8f01640/data/items.ts#L4989)
give eligible Quick Claw a 1/5 activation probability and a fractional order
override, with no Speed multiplier. The conditional adapter supports explicitly
evidenced active/inactive/unknown states; unknown activation is marginalized only
for an explicitly legal Quick Claw configuration. This probability is unrelated
to the prior probability of holding the item. The
[Champions item overrides](https://github.com/smogon/pokemon-showdown/blob/3a766f2cfb5e51c1e428cfe87d0dba91a8f01640/data/mods/champions/items.ts)
mark Custap Berry and Lagging Tail Past; inherited Full Incense is also Past.
They are not silently added to legal item domains. Quick Draw, Mycelium Might,
interacting overrides, forced action moves, conditional priority eligibility and
multi-turn preparation remain explicit unsupported contexts. Stall's move-last
branch is supported only in the conditional adapter. Gale Wings needs verified
full HP; Triage needs verified healing eligibility. Suppressed or transferred
abilities require additional evidence.

## Evidence levels

1. A preserved live `video_message` parsed as `move_execution` with the complete
   “使出了” grammar yields a recognized execution announcement. A selected move,
   log entry, prevented action, weather message or transformation does not.
2. Move resolution and actor receipt reliability are recorded independently of
   the whole event's status. Candidate events can have a confirmed dictionary
   move but an unresolved form. This is source recognition, not measured accuracy.
3. Priority support is conditional on the native form domain. Species-only
   actors union applicable Champions catalog forms. Uncertain native priority
   changers retain alternative brackets, including suppression. No base form is
   selected from species appearance alone.
4. Numeric admission additionally requires verified current forms, one ordering
   decision, contemporaneous modifier continuity, exception coverage and a legal
   own Speed reference. Stored last-observed state and counter readings do not
   satisfy these requirements automatically.

Every action keeps its source event and occurrence IDs, timestamp, local segment,
side, source instance, slot evidence, recognized move, priority hypotheses, source
confidence, raw-source hash chain, current snapshot and separate optional decision
snapshot. Unclosed/unassigned actions remain present. Sequence positions describe
recognized announcements; gaps are never filled with invented actions.
Duplicate occurrences are omitted from actions and retained as duplicate records.
Switches retain the source engine's instance IDs. Known source identity splits
are exposed; the sidecar does not merge them or pretend continuity was verified.

Relations preserve announcement chronology even without builds. An effective
Speed inequality is conditional on equal priority, no ordering override, a known
Trick Room state and queue context; ties remain possible. Opponent/opponent
relations stay available for a future joint hidden-state consumer. All relations
in one local turn share a dependence group. The adapter selects at most **one
admitted pair per whole local turn**, across all individuals, rather than
multiplying correlated pairwise ranks. This conservative subset omits information
intentionally. The existing engine also rejects repeated decisions and actions.

## Existing Bayesian engine compatibility

The sole inference-engine edit is nine lines in
`speed_inference/likelihood.py`: observations that explicitly include
`execution_model` dispatch to `speed_order/execution.py`. All original likelihood
code is unchanged. The adapter determines brackets and within-bracket overrides,
then calls the existing `effective_speed`; it is not another Speed calculator or
posterior engine. Normalization, persistent configuration weights, contradiction
handling, duplicate admission and summaries remain in `SpeedBelief`/`BeliefBank`.

Finite item/ability domains must be supplied explicitly with complete-given-
evidence provenance. An unresolved domain stays unresolved. The prior is uniform
over legal Speed-SP/numerical-alignment/explicit modifier configurations, not
uniform over Speed values, full builds or empirical team frequencies. Choice
Scarf/Quick Claw weights are conditional on that declared configuration space.
Unsupported positive-prior branches reject an update instead of disappearing.
All-zero likelihoods produce an undefined posterior and retain last-consistent
weights diagnostically; no smoothing/reset occurs.

`champions-evidence-only-v1` still refuses numeric updates. Selecting
`showdown-champions-reference-v1` explicitly allows conditional reference
calculations, not claims of independently certified game behavior. The
compatibility fixture stores the exact opt-in addition and before/after hashes.
The historical preservation test checks the original source hash after removing
exactly that addition; all other historical paths still require their old hashes.
No historical preservation baseline or output was resealed.

## Team video and attachment

`tests/fixtures/battle_evidence/sample-team7-reviewed.json` is an agent visual
transcription through the existing `TeamConfiguration` API, with video/frame
hashes and source timestamps. It is separate from `data/teams/my_team.json`.
Moves, items, abilities, six actual stats and displayed allocations are retained.
The numerical alignment is inferred from visible up/down arrows; no named nature,
IV or battle-time form is invented. All 36 actual stats reproduce exactly under
the maintained Champions calculator. The video describes configured base forms,
including Charizardite Y and Garchompite Z, not their transformed current stats.

The user explicitly confirmed that any recording with exactly those six species
uses these builds. `team7-roster-bindings.json` records this statement and separate
agent-reviewed complete rosters. Bindings require the complete six-species match
and source image hash; roster similarity alone is insufficient. Unique species
then map source individuals to configuration members without merging source IDs.
Configured ability/item values never overwrite current battle observations.
The local immutable profile is `sample_team_team7_20261021` in the existing
`.cache/team-profiles` registry.

## Commands and recovery

For an already prepared recording:

```sh
.venv/bin/python scripts/report_action_order.py --battle 6 --visual-version v2.2
```

Output is fingerprinted under
`.cache/battles/sample_battle_6/m341-actions/<fingerprint>/`; its manifest records
input hashes, implementation dependencies, selected profile, status, errors,
output hashes and cost. Changed inputs create another namespace; completed
compatible results are reused. Concise per-battle reports are in
`reports/battles/<battle_id>/M3.4.1-action-order-validation.md`.

Only Battles 11/12 needed initial acquisition. Inspect their existing execution
and stage manifests before resuming; do not launch another running process.

```sh
# Only if initial acquisition is missing:
.venv/bin/python scripts/run_production_evaluation.py --battle sample_battle_11 --run-id m341-actions-acquisition-v1
# If its execution manifest says failed/interrupted and its PID is gone, add --resume.
# Reuse acquisition to prepare missing state and frozen visual sidecars:
.venv/bin/python scripts/prepare_action_evidence.py --battle 11
.venv/bin/python scripts/report_action_order.py --battle 11 --visual-version v2.2
```

The same commands apply separately to Battle 12. Acquisition is sequential and
uses the existing default 2 FPS sampling policy; no sampling or recognizer change.
Frozen v2.2 is replayed with existing functions and isolated index routing.
These new recordings have no human turn-timing acceptance benchmark.

Later verified context/build attachments can call `analyse` or pass `--reviews`
without video work. Reviews contain `actions` keyed by original event ID and
`comparisons` keyed by stable relation ID. A comparison review supplies explicit
context, verification fields, sources, stat epoch and optional legal modifier
domains/execution model. Intervening events need individual source-backed
`verified_no_order_change` reviews; genuinely relevant mid-turn changes still
defer. No review can replace immutable source identities, moves or chronology.
See `tests/test_action_order.py` for synthetic deferred-reanalysis examples.

Missing verified modifier contexts, unsupported mechanics and incomplete source
individual/form bindings remain the work required before real numeric updates.
M3.4.2 and empirical priors are outside this milestone. No commit or push.
