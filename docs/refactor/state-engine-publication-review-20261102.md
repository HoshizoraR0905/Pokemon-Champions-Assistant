# StateEngine refactor — final publication review, 2026-11-02

Reviewed branch: `refactor/battle-state-architecture`, based on published pre-refactor commit `cb8bc7c1ecb49eae316fd9535e294aebd0eee10a`. Baseline annotated tag `pre-state-engine-refactor-20261101` has tag object `b029110ed1f1fa3157a7a4b05f77c998736ad30d`. The baseline branch/tag are preserved. This review records the validation accompanying the refactor publication; the resulting commit is identifiable in Git history by `refactor: separate immutable battle evidence from mutable state`.

## Review findings

No material correctness defect or unrelated implementation change was found. The implementation matches the fingerprints in the accepted measurements. Gameplay mechanics, damage rules, hidden-stat domains, Speed alignment/SP assumptions and Iron Ball preference were not changed. Sharing is limited to committed immutable evidence values; reference sequences and mutable current facts are independently copied. HP causal revisions replace records; correction/retraction rebuilds from initial state. Ended episodes and departure snapshots remain historical records, while persistent identity ownership remains in existing state structures. Legacy exports and public returned receipts detach their mutable containers. Canonical hashing keeps schema-2 semantics and deterministic sorted JSON. Bounded string encoding memoization does not hold mutable battle authority; compact evidence tables are local to each export.

Reviewed StateEngine/BattleState, shared evidence/history, HP enrichment, identity continuity, decision/evidence exports, tests, benchmark/comparison scripts, reports and summaries. Existing regressions cover trial rollback, history immutability, identity/HP continuity, retractions/corrections, cross-battle isolation, damage inference, and B24 Tyranitar `{72}` with the last-resort Iron Ball preference.

No implementation correction was necessary. Documentation finalization labels the restart prompt as historical and normalizes its workspace path; its original is preserved under `.cache/baselines/state-architecture-publication-20261102-v1/restart-prompt-original.md`. The completed architecture report now links this publication review instead of describing current work as unpublished.

## Final validation

**1,826 portable regressions passed; 15 optional local-artifact tests deselected in 166.17 seconds.** See [exact command/results](state-engine-publication-review-20261102-validation.json). Original implementation-run validation remains preserved separately.

Saved benchmark manifests, original input hashes, recorded output hashes, complete legacy replay exports (including every receipt hash), decision prefixes, HP projections and compact export/expand round trips were reverified across **9,339 B20–B24 receipts**. The newly verified summary equals the accepted measured summary exactly. No replay measurement was rerun and no new performance result replaces the accepted 3.77×–7.00× observations. B24 frozen/historical declared files passed their integrity verifier.

Commands:

```sh
.venv/bin/python scripts/summarize_state_architecture.py --output .cache/baselines/state-architecture-publication-20261102-v1/verified-measurements.json
.venv/bin/python scripts/evaluate_b24.py --stage verify
# Exact pytest argument list is in the validation JSON.
git diff --check
.venv/bin/python scripts/review_git_tracking.py
```

The recorded memory/storage and semantic acceptance limits still apply: RSS increased on B22–B24; complete compact packets grew on B20–B23; 267 source receipts remain deferred; optional tests were deliberately deselected. Replay parity does not establish recognition accuracy, full mechanic coverage or production PTR improvement. See [architecture report](state-engine-architecture-20261102.md) and [measurements](state-engine-architecture-20261102-measurements.json).

## Publication scope and local artifacts

Only reviewed source, tests, reproducibility scripts, documentation and small validation/measurement summaries belong in this commit. Credential-pattern/home-path scanning found no matches in the proposed files. Full benchmark replay JSON, compact evidence tables, prefix JSONL, videos, extracted frames, OCR/model caches, baseline source archive and detailed logs remain ignored and local. No local artifact was deleted or force-added. The benchmark requires those saved local inputs; GitHub alone does not contain the bulk evidence.

The authorized publication sequence pushes the refactor branch, verifies the remote commit SHA, then creates local `dev/post-state-engine-refactor` at exactly that commit. The development branch is left unpushed. No new development task is part of this publication review.
