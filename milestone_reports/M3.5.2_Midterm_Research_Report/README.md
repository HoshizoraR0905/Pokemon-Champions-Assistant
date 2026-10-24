# M3.5.2 — Supplementary Midterm Research Draft

The primary milestone deliverable is the [GitHub Markdown build-clustering
report](../M3.5.1_Build_Clustering.md). This academic PDF/LaTeX draft is preserved
as optional supplementary material.

**Inferring Hidden Pokémon Builds from Competitive Team Data: Constraint-Based
Inference and Unsupervised Archetype Discovery**

*Midterm Research Report — October 2026*

- [Publication-style PDF](report.pdf)
- [Editable LaTeX source](report.tex) and [generated numerical tables](results_tables.tex)
- [All 14 scientific figures](figures/): 11 original images and 3 new SP-only comparisons
- [Compact evidence and provenance summary](evidence-summary.json)

Status: document prepared for human review. The underlying M3.5.1 offline
experiment is complete; neither its clusters nor the reviewed battle assumptions
have been independently accepted as ground truth. No model, inference engine,
empirical weights, evidence, clustering assignments or existing study outputs
were changed by this reporting milestone.

## Build the PDF without research caches

Requirements: a standard LaTeX installation with `pdflatex`, Latin Modern,
AMS math, geometry, graphicx, booktabs, caption/subcaption, microtype, fancyhdr,
pdflscape, enumitem, hyperref and xurl. The document was built locally with pdfTeX
1.40.24 (TeX Live 2022). Figures and table source are bundled; no research Python
modules, database, videos, OCR or numerical matrices are needed to compile.

From the repository root:

```sh
milestone_reports/M3.5.2_Midterm_Research_Report/build.sh
```

The script runs LaTeX three times, places temporary logs/auxiliaries under
`.cache/document-build/m352/`, and copies only the finished `report.pdf` here.
For standalone use, copy this directory and run `pdflatex report.tex` three times
from inside it. PDF timestamps/engine metadata can change the byte hash when
rebuilt; this is document regeneration, not numerical refitting.

## Optional: refresh presentation assets from the preserved local study

```sh
.venv/bin/python milestone_reports/M3.5.2_Midterm_Research_Report/prepare_report.py
```

This optional command requires NumPy 2.2.6, Matplotlib 3.10.9 and the original
completed M3.5.1 cache referenced by `.cache/research/m351/latest.json` (or pass
`--study PATH`). It validates source-stage hashes, copies the original eleven
figures byte-for-byte, exports compact statistics/medoid provenance and numerical
LaTeX tables, and draws only the three missing Incineroar SP-only figures from
saved distance matrices and assignments. Classical MDS is used solely for a
presentation projection. It does not import the clustering implementation or
run fitting, optimization, evidence processing, collection or inference.

The numerical source fingerprint is `7933afbb341cdbeddbe3`. Full matrices and
observation dumps remain local in `.cache/research/m351/`; they are deliberately
excluded from the report commit. `evidence-summary.json` preserves source hashes,
exact source IDs/full configurations for referenced medoids, aggregate errors,
sensitivity results, the cross-partition occurrence table and figure provenance.
Original publication URLs remain attached to those representative builds. Some
source reports/implementation files exist only in the current working tree and
are not included by this reporting-only commit; this package documents that
research state without claiming to publish its software implementation.

## Interpretation and validation

The report distinguishes Incineroar SP-only selected K=3 (31/24/142) from learned
combined diagnostic K=3 (34/7/156); the latter's conservative selected count is
K=1. The seven-observation group is coherent but small. The study finds no numeric
target improvement from learned moveset association over SP-only. Similarity
memberships are not calibrated posterior probabilities. These mixed/negative
findings are retained rather than tuned away.

Run document checks with PyMuPDF 1.28.2 in the existing Python environment:

```sh
.venv/bin/python milestone_reports/M3.5.2_Midterm_Research_Report/validate_document.py
.venv/bin/python -m pytest -q tests/test_git_artifact_policy.py
.venv/bin/python scripts/review_git_tracking.py
```

Representative pages are rendered to the ignored document-build cache for visual
inspection. `validation.md` records completed checks, visual review and remaining
limits. Human review of scientific interpretations, readability and source-review
assumptions remains outstanding. No further research milestone is started.
