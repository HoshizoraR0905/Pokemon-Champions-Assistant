# Incineroar moveset, item and SP diagnostics

Read-only M3.5.3 follow-up using the exact 197 complete M3.5.1 Incineroar
occurrences. No source collection, no-SP predictor change, annotation write,
SP coefficient change, battle-engine change or replay change.

```sh
.venv/bin/python -m experiments.moveset_diagnostics.run
.venv/bin/python -m pytest -q tests/test_moveset_diagnostics.py tests/test_git_artifact_policy.py
```

Use the existing optional NumPy/Matplotlib environment, with pinned dependencies
in `../build_similarity/requirements.txt`. Run from the repository root. Inputs
are the completed `.cache/research/m351/7933afbb341cdbeddbe3/` artifacts and the
tracked M3.5.2 evidence summary. No database or network access is required.

## Fixed and new computations

The runner verifies source manifests and hashes, canonical species/move sets,
legal supplied SP, occurrence order, reference configuration and medoid identity.
It restores the saved 279-by-16 move vectors without fitting a full-population
embedding. The original SP-only, SP+learned and SP+Jaccard partitions are reused.
Restored learned distances plus the unchanged SP component must reproduce the
saved combined matrix; exact canonical Jaccard must reproduce its counterpart.

Only four new model families are fitted, each with deterministic PAM and average
linkage at K=1–4:

- Learned moves only: saved cosine dissimilarity / exact saved move scale.
- Jaccard moves only: four canonical move tokens.
- Jaccard moves + item: four typed move tokens plus a typed original-item token.
- Learned moves + item: normalized learned move distance + 0.5 × normalized
  item mismatch. The coefficient is the prior M3.5.1 categorical-ablation value;
  no nature term, new item embedding or tuned weight is introduced.

All 197 original items are known. Typed item tokens cannot collide with move
identities. Jaccard uses one minus intersection/union; its positive-median scale
only changes distance units. The learned item coefficient changes relative
influence and is an explicit sensitivity assumption.

The unchanged conservative PAM selection takes the smallest K with silhouette
≥0.25, all groups ≥max(3,ceil(0.1N)), and mean retained-anchor ARI ≥0.65 from three
available resamples. K=1 is the fallback. Average linkage is an independent
algorithmic diagnostic; no new selection criterion is invented for it.

Stability uses the original global 551 source-group pool, seeds 351–353 and 80%
sampling. Each subset refits the same embedding once for stability only, then
normalization and PAM. This repeats the existing pipeline-stability method,
not a full-data embedding replacement or a search for interpretable groups.
Resamples retain 158/155/159 Incineroar anchors. Existing baseline resampling
outputs are reused unchanged. Three subsamples cannot certify broad stability.

## Counts and statistics

Assignments join by immutable occurrence ID. Repeated published configurations
retain their multiplicity. ARI is the existing implementation. NMI uses
`2 * mutual_information / (entropy_left + entropy_right)`, natural logs, and
one for two constant partitions; constant-partition agreement is explicitly
marked uninformative. Cross-tab counts preserve all 197 occurrences.

Move tables rank occurrence count descending, with canonical-ID tie breaks.
Cluster frequency is count/cluster size, species frequency count/197, and lift
their ratio. Complete move-frequency totals are 400%, because every occurrence
contains four moves. Top tables list up to 15 actual moves. Overrepresentation
requires lift >1 and at least three within-cluster occurrences; ties use count
then canonical ID. Move-token entropy normalizes counts by 4N, while complete-set
entropy normalizes whole-set counts by N. Both use bits. Items are described
separately, never added as fictitious moves to the frequency tables.

Original Attack, Speed, HP, Defense, Special Defense and total defensive SP are
described with quartiles and full count distributions. Nature/alignment, items,
abilities, source groups, medoids, exact movesets and move/item packages are also
retained. Within-cluster dissimilarities use unordered off-diagonal pairs;
between-cluster summaries compare every member with every outside occurrence.
A singleton's within-cluster mean is undefined.

The feature-collision calculation sums the largest frozen-SP label count in
each exact move or move/item package. This is an optimistic empirical lookup
ceiling for these observations, not a new classifier, held-out evaluation,
probability prior or upper bound on future battles. It cannot be compared directly
with M3.5.3's fold-refitted label accuracy.

## Outputs and recoverability

[Read the report](../../milestone_reports/M3.5.3_Incineroar_Moveset_Clustering_Diagnostics.md).
The Markdown contains all top-15 tables, with collapsible sections to keep the
main comparison readable. Scientific figures and compact CSV/JSON exports live
under `milestone_reports/assets/m353-moveset-diagnostics/`. No distance matrix,
embedding, full global training population or human annotation is committed.

Local numerical outputs live under
`.cache/research/m353-moveset-diagnostics/<fingerprint>/`; `latest.json` identifies
the completed run. Atomic checkpoints, stage hashes/status/errors and exact resume
commands are recorded in `manifest.json`. A per-run OS lock prevents duplicate
jobs. Re-run the same command to reuse compatible stages. Completed stages survive
later failures. Report-only changes regenerate only presentation outputs. Existing
source/predictor/annotation files are hashed before and after execution; the
runner never opens the annotation database for writing. Concurrent human edits
can change those hashes and are reported for inspection, never overwritten.

Custom locations:

```sh
.venv/bin/python -m experiments.moveset_diagnostics.run \
  --study .cache/research/m351/7933afbb341cdbeddbe3 \
  --output .cache/research/m353-moveset-diagnostics \
  --report milestone_reports/M3.5.3_Incineroar_Moveset_Clustering_Diagnostics.md
```

Output paths inside the original study or the no-SP annotation namespace are
rejected. Keep the original M3.5.1 cache and all existing reviews. This experiment
stops at diagnostics; it neither redoes human review nor begins another milestone.
