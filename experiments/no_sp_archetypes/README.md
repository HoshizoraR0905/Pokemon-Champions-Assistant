# M3.5.3 — No-SP Incineroar review

Offline research only. Uses existing cached VGC M-C Doubles publications and the
frozen M3.5.1 SP-only K=3 partition (31/24/142). No network collection, battle
inference, replay modification, teammate features or synthetic SP.

From the repository root:

```sh
.venv/bin/python -m pip install -r experiments/build_similarity/requirements.txt
.venv/bin/python -m experiments.no_sp_archetypes.study
.venv/bin/python -m experiments.no_sp_archetypes.review
```

Open **http://127.0.0.1:8353** in a desktop browser. Stop the server with Ctrl+C;
relaunching restores durable annotations, filter/sort settings and the last record.
Use **Save review** or **Save & next** before leaving a case. Unsaved edits trigger
a warning. Reviews express plausibility, never verified true SP.

The numerical study needs these existing, intentionally untracked inputs:

- `.cache/metagame/published-teams/teams.sqlite3` (read-only);
- `.cache/research/m351/7933afbb341cdbeddbe3/` with completed manifest,
  `population.json` and `incineroar-sp.json`;
- tracked M3.5.2 `evidence-summary.json` for frozen source-hash verification.

The lightweight M3.5.1 `core.py` dependency is included to reuse its unchanged SP
configuration, distance and deterministic PAM implementation. Other unfinished
research/battle-engine changes in the working tree are not part of this milestone.
NumPy 2.2.6 and Matplotlib 3.10.9 are the existing optional study dependencies;
the review server and durable store use Python's standard library.

## Paths, resume and exports

Runs live in `.cache/research/m353/<fingerprint>/`. `latest.json` points to the
latest successfully completed run. The manifest records source/implementation
identity, atomic stage statuses, hashes and errors. Run the same study command to
reuse valid stages. A per-run OS lock prevents duplicate jobs. Successful stages
survive later failures. A report-only code change invalidates presentation assets
without refitting numerical stages; original M3.5.1 files are never overwritten.

Stages are `audit`, `frozen`, `evaluation`, `application`, `review-data`, and
`report`. Full observations, source joins, per-fold predictions and application
scores remain local. Small report figures and aggregate evidence are intentional
presentation artifacts under `milestone_reports/assets/m353/`.

Persistent reviews and session state live in:

```text
.cache/research/m353/reviews.sqlite3
```

Review revisions append to SQLite, keyed by model fingerprint and immutable
observation ID. Each revision stores the server's original prediction weights,
assessment, optional preferred cluster, notes and UTC timestamp. Predictions and
source records are never modified. The page's **Export JSON / Export CSV** links
use `/api/export.json` and `/api/export.csv` and download the latest assessment per
record for the active model. Old revisions remain in SQLite. Exported timestamps
are UTC; the page displays the browser's local time. CSV escapes formula-like
notes for spreadsheets; original notes remain unchanged in SQLite/JSON.

Custom paths and a separate test/demo annotation store:

```sh
.venv/bin/python -m experiments.no_sp_archetypes.study \
  --database .cache/metagame/published-teams \
  --study .cache/research/m351/7933afbb341cdbeddbe3 \
  --output .cache/research/m353
.venv/bin/python -m experiments.no_sp_archetypes.review \
  --port 8353 --annotations .cache/research/m353/reviews.sqlite3
```

`review --run PATH` opens a particular completed fingerprint directory. All
server routes bind to loopback only. The app exposes fixed assets/predictions,
annotation and export APIs, and the three original SP-only Incineroar plots.
It does not serve arbitrary repository/cache paths. No browser localStorage is
required. Changing the model fingerprint keeps previous reviews intact and starts
a separate active review/session view.

## Method and checks

`data.py` reuses the established canonical identities, source scope, field
eligibility, stat validator, native-ability and required-item facts. It preserves
original normalized and raw assertions and joins teammates by publication/member
ordinal. Missing-SP selection bypasses the complete-build adapter without
bypassing assessable non-SP conflicts. Compatibility checks do not certify
Champions learnsets, all item availability or independent source identity.

`model.py` averages smoothed subset-conditional cluster distributions. Fixed
subset-size weights are 0.1/0.2/0.3/0.4, smoothing mass is 5 occurrences, and
item/subset joint counts shrink toward a smoothed item-only distribution.
Overlapping likelihoods are never multiplied. Unknown items preserve moves-only
scores. No hyperparameter tuning is performed. `weak_evidence` marks cases with
fewer than three supporting pair-or-larger occurrences or moves-only L1 shift
from the prior below 0.1. `rare_complete_set` means fewer than three exact
training matches; unseen moves are separately flagged as out of distribution.
A large margin is a model preference, not calibrated confidence.

`evaluate.py` performs three deterministic grouped three-fold splits. Train-only
SP clustering defines fold labels, held-out SP is used solely for nearest-training-
medoid evaluation labels, and reference medoids only name columns by permutation.
`frozen.py` verifies the unchanged application reference without refitting it.
`study.py` preserves every eligible application record and constructs a separate
20-case, contrast-seeking queue with distinct moveset/item patterns. Unavailable
categories remain empty and are counted explicitly.

```sh
.venv/bin/python -m pytest -q tests/test_no_sp_archetypes.py tests/test_git_artifact_policy.py
```

The [milestone report](../../milestone_reports/M3.5.3_No_SP_Archetype_Review.md)
contains the actual population counts, evaluation results and limits. Human review
is pending. No next research milestone or online integration is authorized here.

For the optional real-browser workflow check, launch a separate annotation store
and use a fresh screenshot directory (requires local Google Chrome and Node 22+):

```sh
.venv/bin/python -m experiments.no_sp_archetypes.review \
  --port 8354 --annotations .cache/document-build/m353-ui/test-reviews.sqlite3
# In a second terminal:
node scripts/verify_no_sp_review.cjs http://127.0.0.1:8354 \
  .cache/document-build/m353-ui/browser-check
```

The browser checker refuses to annotate a store whose path does not include
`test-reviews`. Its automated notes are not human research assessments.
