# Document validation — M3.5.2

Prepared 24 October 2026 (Asia/Shanghai). Status: ready for human review;
scientific interpretation and earlier reviewed battle assumptions are not
independently accepted by these document checks.

- PDF compiled locally in three LaTeX passes: **20 pages**, **14 figure
  appearances**, no overfull boxes, LaTeX warnings, undefined references or
  missing graphics in the final log.
- Eleven original scientific images match their M3.5.1 SHA-256 hashes. Only three
  missing Incineroar SP-only presentation plots were generated from saved
  matrices/assignments. No clustering/inference algorithms or numerical results
  were modified or rerun.
- All **47 referenced study-stage output hashes** match the preserved completed
  study. Original archived reports and copied archive figures match recorded
  provenance; originals remain in place.
- The document validator passed: required sections, English text, exact figure
  inventory, source/figure hashes, saved Incineroar membership/count checks,
  nonblank pages and all extracted text within page bounds.
- Rendered all 20 pages with PyMuPDF. Visually inspected physical PDF pages
  **1, 5, 6, 10, 12, 13, 14, 17, 19 and 20**: title, SP/association equations,
  association chart, clustering/membership tables, side-by-side heatmaps and
  projections, SP boxplots, heldout results, conclusion and source references.
  Labels, captions and equations were legible; no clipping, overlap or missing
  figure was observed in the inspected pages. Landscape comparisons are
  explicitly distinct from the original dissimilarity space.
- `python -m pytest -q tests/test_git_artifact_policy.py`: **2 passed**.
- `git diff --check` passed. The index audit is run after explicit report-only
  staging: 40 added report/archive paths, approximately 2.85 MB of unique new
  Git blobs, no broken/untracked symlink targets and no ignored paths in the
  index. Caches, PDF previews, LaTeX auxiliaries and unrelated changes are excluded.

PDF SHA-256 at validation:
`c78e3d87e156cf1cf7907783d08be6001db17b1f22dd9a63cb9661737610d178`.
A fresh LaTeX build can change metadata/timestamps and thus this byte hash.

The numerical study's earlier 129 passing checks / 3 deselections are cited as
historical M3.5.1 evidence, not newly rerun tests for this writing milestone.
No recognition accuracy, universal tactical-role acceptance, independent
sample-size claim, calibrated probability or external validation is inferred.
The original full numerical caches and some cited working-tree implementation
files are intentionally outside the reporting-only commit; the bundled assets
are sufficient to reproduce the PDF, not to publish the complete software state.
