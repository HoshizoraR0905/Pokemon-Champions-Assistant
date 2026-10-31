# M3.5.1 offline build association study

Run from the repository root using the existing cached published-team database:

```sh
.venv/bin/python -m pip install -r experiments/build_similarity/requirements.txt
.venv/bin/python -m pytest -q tests/test_build_similarity.py
.venv/bin/python -m experiments.build_similarity.study
```

The study reads `.cache/metagame/published-teams/teams.sqlite3` in read-only mode.
It never collects source data or imports the results into inference. Optional
NumPy/Matplotlib dependencies are isolated here; there is no new runtime import
from the battle system. Matplotlib is used only by report generation.

Outputs:

- `reports/M3.5.1-build-similarity.md`: local report with static scientific plots.
- `.cache/research/m351/latest.json`: pointer to a completed fingerprint directory.
- Each fingerprint directory: manifest, complete original observations and
  provenance, move statistics/embeddings, 39 configuration/species result files,
  source-group resampling, target-masked held-out predictions and PNG figures.

Full diagnostic JSON and images stay local under the existing Git artifact policy;
the Markdown report, source and portable tests can be reviewed independently.
Clustering uses every eligible occurrence, including identical configurations.
Distinct-build/core counts and connected source groups are diagnostic/evaluation
structures only. No deduplication changes empirical observation weights.

`core.SPConfig` exposes all nonlinear parameters, scales and defensive formulations.
`core.MoveModel` exposes embedding dimension, additive smoothing, rarity shrinkage,
association cap and pooling. `core.BuildDistance` exposes the move baseline and
four component weights. `study.variants()` declares the small, fixed experimental
grid. `soft_membership` accepts a temperature; these scores are uncalibrated
similarity memberships, not posterior probabilities. Default experiments use
mean pooling, dimension 16, temperature 1 and three source-group folds/resamples.
No parameter is selected by optimizing the held-out predictions.

To use another cached database or output location:

```sh
.venv/bin/python -m experiments.build_similarity.study \
  --database .cache/metagame/published-teams \
  --output .cache/research/m351 \
  --report reports/M3.5.1-build-similarity.md
```

Resume with exactly the same command. The runner acquires an exclusive OS lock,
records each running/completed/failed stage atomically, and validates output hashes
before reuse. A disconnected shell does not invalidate stages. Successful stages
survive later failures. Source/rule/data/implementation fingerprints isolate changed
experiments; existing directories are preserved. Report-only changes regenerate
plots/report without refitting the numerical stages. Check the log and manifest
for the first incomplete stage before resuming; do not start duplicate jobs.

The report describes empirical structure, model assumptions, tiny clusters,
nonmetric dissimilarities, rare-pair uncertainty and conditional reconstruction
limits. Full-data descriptive fits and train-only held-out fits are distinct.
The conservative display K is only a descriptive screen. K=1 remains valid, and
all candidate partitions and original full medoids are exported.

No commit/push, next milestone, posterior prior, synthetic build generation,
strategy recommendation or battle UI change is part of this experiment.
