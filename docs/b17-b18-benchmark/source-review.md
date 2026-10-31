# Post-seal source observations and limits

Scope: initial `fresh-b17-b18-20261028-v1` predictions, reviewed only after both
initial freezes existed. These observations are reporting diagnostics. They are
not injected into recognition/state, do not correct the first run, and do not
constitute an independent annotation set or an accuracy estimate.

## B17 evidence requiring separate investigation

- 276.513333 s, receipt `event:bf71efbb7a3a3133f3ea3c00`: the saved source frame
  visibly contains the Light Screen message “光墙使我方的特殊抗性提高了”. The
  `side_condition_change` receipt is rejected with
  `observed_effect_conflicts_with_current_state`. This confirms that the message
  is visible; determining which state/effect assertion should win requires a
  separate reconciliation review. No state correction was applied.
- 319.503333 s, receipt `event:f78fa880fa19da33a4f46509`: the frame is a four-card
  status overlay, including own Archaludon displayed at 182/194. Its processing
  produced a `maximum_hp_disagreement` conflict. This is a localized observed
  conflict to investigate, not a count of independently labelled recognition
  errors.
- 367.011667 s, receipt `event:f340f12c2b371da31ed72f63`: a selected-detail panel
  visibly shows Archaludon at 194/194 with ability/item labels and field effects.
  The corresponding `visual_observation` produced `visual_fact_disagreement`.
  The panel contents were inspected but not used to patch state or infer an HP
  recovery cause. Existing conflicting assertions and evidence are preserved.

Evidence paths relative to the repository:

```text
.cache/battles/sample_battle_17/event-driven/fresh-b17-b18-20261028-v1/frames/000554.png
.cache/battles/sample_battle_17/event-driven/fresh-b17-b18-20261028-v1/frames/000639.png
.cache/battles/sample_battle_17/event-driven/fresh-b17-b18-20261028-v1/frames/000733.png
```

B17 has 218 deferred receipts: 211 with
`message_episode_occupancy_unresolved`, 7 with `unresolved_candidate_fields`.
There are three state conflicts and one rejected event. B18 has three deferred
receipts, all `message_episode_occupancy_unresolved`, and no state conflicts or
rejected events. These remain part of the initial results, even though both
production commands exit successfully and their replays are deterministic.

## Recording tails and UI classification

The last sampled/inspected source frames at B17 **529.505 s** and B18
**421.505 s** show the phone's Control Center covering the game. The stored
production phase for both frames is `battle_animation`. This is a directly
source-reviewed mismatch at these particular tail frames; it does not establish
an overall UI classification error rate. Final reconstructed state therefore
must not be presented as an independently verified actual battle outcome.
Unsupported overlays and hidden observations remain an evidence limitation.

```text
.cache/battles/sample_battle_17/event-driven/fresh-b17-b18-20261028-v1/frames/001052.png
.cache/battles/sample_battle_18/event-driven/fresh-b17-b18-20261028-v1/frames/000831.png
```

## Special move examples

Neither sealed prediction inventory contains a `multi_hit` count notice, a
documented contact-damage reaction HP episode, or a move HP association targeting
a different instance on the same side. No actual multi-hit/contact-reaction/ally
sequence is independently verified in this benchmark. This is not evidence that
such sequences are absent from either video. No capability/learnset reference or
move name is treated as proof of an actual execution/hit/target.
All action target inventories, including non-HP stat/pivot associations, were
also checked; they contain no different-instance same-side target association.

## Performance and coverage interpretation

B18's scheduler classified 177 detailed frames as team preview, versus 96 in
B17. Recorded icon recognition calls were 692 versus 12, and their existing wall
spans were 249.852 s versus 4.386 s. The packaging/reconstruction span through
summary creation was 241.492 s versus 141.197 s. B18 actually performed fewer
OCR calls (3033 versus 4307). These measured workload differences help describe
the result; they are not an isolated causal profile or tuning experiment.
Preview events and encounter instances are not unique biological team counts.

HP coverage uses the same observed action/target grouping definition as B16:
B17 **6/11** fully supported causal groups (9/11 complete endpoints), B18
**3/4** (3/4 complete endpoints). The remaining groups retain missing baselines,
unsettled/open endpoints or unsupported source/actor information. They are not
silently dropped from the denominator. Entirely unseen HP events cannot be
counted, so these fractions are not recall or correctness.

The latest B16 HP-completion result used separate targeted source passes after
diagnostic review. These B17/B18 first runs use untouched ordinary production
sampling and no supplementary endpoint passes. Comparing their HP coverage
directly with B16's source-completed 21/21 does not measure an accuracy change.
Similarly, B16's normal PTR 0.8838 refers to an earlier implementation and
different video content. All original durations, code/model fingerprints,
external/internal times and frame/OCR denominators remain available in the
benchmark manifests for a properly scoped later comparison.
