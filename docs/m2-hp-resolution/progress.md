# M2 action resolution — completed handoff

Final evaluation: `b16-action-resolution-20261028-v4`.
Original source stages remain sealed and complete: banner/HP acquisition v5,
reconstruction v6, numeric attribution v5. The source reference remains
`b16-semantic-state-20261027-v1`; no denominator, annotation or source prediction
was rewritten. Other dirty-tree edits were preserved. No commit/push.

Stages completed:

1. Inspect existing event receipts, timestamps, identities and HP records.
2. Derive 21 action/target windows from all 41 prior nonzero numeric segments.
   This is a read-only StateEngine projection, not a second state store. Keep
   25 move executions in the action inventory, including no-change observations.
3. Keep related critical/effectiveness/count messages inside the move window;
   separate explicit recoil, item/ability, residual and healing effects. Handle
   between-hit damage to another instance without losing the primary total;
   abstain on inseparable same-target effects.
4. Reuse the existing PTS decoder / visibility / HP refresh / numeric OCR for
   targeted >=5 FPS source inspection. Ordinary acquisition stays 2 FPS.
5. Perform one 360–369 s normal-attack source probe at 5 FPS: 45 sampled / 271
   source-counted frames, 8 pre-trigger frames, 30 ROI requests, 13 model
   predictions, zero full-screen OCR. Frames, OCR reads, row checkpoints, exact
   PTS and hashes remain owned by this battle. No successful stage was deleted.
6. Run B16 multi-hit inspection: zero eligible predicted actions, zero windows,
   zero additional frames/OCR. No actual multi-hit or critical success claim.
7. Verify unchanged complete StateEngine state and every receipt; 16 complete
   stable endpoint episodes, 10 known sources, 6 complete supported totals.
   Fifteen episodes remain unresolved; five have endpoint-boundary limitations.
8. Portable focused regressions: 256 passed, 3 deselected in 55.59 s;
   compilation and whitespace checks passed.

Re-evaluate only the cheap derived stage (completed matching outputs are reused):

```sh
.venv/bin/python scripts/evaluate_hp_resolutions.py evaluate --run-id b16-action-resolution-20261028-v4 --probe-run-id b16-resolution-probe-20261028-v1
```

The inspection command plans only recognized reference-capable or independently
announced multi-hit moves and processes one source window at a time. Saved rows
are bound to action endpoints through existing encounter/slot receipts; they
can supplement hit timing without overwriting authoritative HP.

```sh
.venv/bin/python scripts/evaluate_hp_resolutions.py inspect --run-id b16-multi-hit-inspection-20261028-v1 --fps 5
```

A genuinely new scoped acquisition can use an explicit range, physical ROI and
higher configurable FPS. The completed historical probe must be reused, not
rerun to obtain the already measured numbers:

```sh
.venv/bin/python scripts/evaluate_hp_resolutions.py probe --run-id NEW_RUN_ID --start 360 --end 369 --fps 5 --side own --slot right --trigger-time 361.51166666666666
```

On interruption: check processes first, then the battle-owned sampling manifest.
Do not start a duplicate process. Frames and HP OCR are separate checkpointed
stages; resume the identical probe arguments/run ID. Saved successful frame and
row files plus exact-crop predictions are reused. Each row records provenance
and reuse, and the manifest records counts, identity, stage and errors. An
implementation/input mismatch requires a new run ID with an explicit reason;
do not erase the completed source stage.

All large artifacts are under `.cache/battles/sample_battle_16/`; generated JSON
remains ignored. Source evaluation and reference fingerprints are recorded in
`hp-resolutions/b16-action-resolution-20261028-v4/manifest.json`, with source
snapshots and separate derived episode output. The actual source probe lives in
`hp-resolution-sampling/b16-resolution-probe-20261028-v1/`, including a real
`binding-check.json` showing 84→0 stays supported while dense HP begins at 79
and per-hit amounts stay unknown.

A later planning-only admission check and added binding adapter change the
sampling module's whole-file hash. The exact successful sampling implementation
was preserved and verified against its original manifest digest; the evaluator
compares its sampling-function AST with the current function before accepting
those measurements. Frame decoding, OCR implementation, thresholds and the
sampling function itself were not changed. No decode/OCR was repeated for a
planning-only source change.

Evaluation v1–v3 are preserved intermediate development projections; all are
cheap views of the same saved evidence. v4 is final and includes strict final
visible plateaus, the full-action legacy comparison, and per-target handling of
confirmed multi-hit interruptions. Initial synthetic tests that assumed widely
spaced/hidden equal reads proved a stable plateau were corrected to supply actual
nearby visible observations; no B16 reference endpoint was altered.

See [results.md](results.md) and the linked 21-row source evidence report. There
is no remaining active job to resume and no next milestone has been started.
