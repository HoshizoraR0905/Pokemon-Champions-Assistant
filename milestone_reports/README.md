# Research and milestone reports

This directory collects selected research documents suitable for collaborator
review. Original project reports remain at their existing paths. These are
research snapshots: completed software/experiments do not imply independent
acceptance of mechanics, recognition quality or tactical interpretations.

| Report | Main research contribution | Formats | Status |
|---|---|---|---|
| [M3.5.4 — Team speed-control context and SP prediction](M3.5.4_Team_Speed_Control_and_SP_Prediction.md) | Source-grouped numeric regression, fixed capability features, permutation controls, learning curves and tactical case studies | GitHub Markdown, scientific figures and compact CSV/JSON | Completed controlled offline experiment; no robust basis for inference integration |
| [M3.5.3 follow-up — Moveset clustering diagnostics](M3.5.3_Incineroar_Moveset_Clustering_Diagnostics.md) | Moves-only and item-aware cluster comparisons against frozen SP groups, full top-15 move tables and exact-feature ambiguity | GitHub Markdown, scientific figures and compact CSV/JSON exports | Completed descriptive diagnostic; predictor and human annotations unchanged |
| [M3.5.3 — No-SP archetype review](M3.5.3_No_SP_Archetype_Review.md) | Read-only missing-SP audit, frozen Incineroar reference, grouped moves/item prediction and durable local human-review interface | GitHub Markdown, two figures and compact evidence summary | Offline experiment complete; minority recovery weak; human interpretation pending |
| [M3.5.1 — Build clustering](M3.5.1_Build_Clustering.md) | Primary milestone report: nonlinear SP comparison, Incineroar clustering, learned moveset experiment, held-out results and limits | GitHub Markdown with original figures | Completed offline experiment; tactical interpretations remain preliminary |
| [M3.5.2 — Supplementary research draft](M3.5.2_Midterm_Research_Report/README.md) | Broader synthesis of hidden-build feasibility and empirical usage through M3.5.1 | Optional [PDF](M3.5.2_Midterm_Research_Report/report.pdf), [LaTeX](M3.5.2_Midterm_Research_Report/report.tex), figures and compact evidence summary | Supplementary academic draft; awaiting human review |
| [M3.2.2 — Battle 11 Speed case study](Previous_Milestones/M3.2.2_Battle11_Speed/report.md) | Causal action-order evidence reduces joint Speed supports while preserving uncertainty; illustrates distinct empirical/reference layers | Markdown; references existing tracked case-study images/audit assets under `docs/assets/` | Preliminary research demonstration; source-reviewed conditions, independent acceptance not established |
| [M3.1.2 — Joint Champions stat feasibility](Previous_Milestones/M3.1.2_Stat_Feasibility/report.md) | Compact exact joint point-domain/budget representation; gaps and interactions between stat legality and inverse damage | Markdown | Completed conditional feasibility experiment under pinned reference rules; not official mechanics certification |

The earlier reports were chosen for mathematical or experimental substance.
Technical handoffs, debugging logs, cache receipts and broad validation dumps are
not archived as presentation documents. Historical counts and superseded limits
remain labeled as historical. Start with the build-clustering and no-SP review Markdown reports;
the midterm PDF is optional supplementary reading. The [detailed M3.5.1
experiment snapshot](Previous_Milestones/M3.5.1_Build_Similarity/report.md) remains
available for full numerical tables and method settings.

`Previous_Milestones/archive-provenance.json` identifies original and archived
content by SHA-256. Archive packaging adjusts relative links, bundles the earlier
study's scientific plots, and turns optional local-cache diagnostic links into
explicitly local references. Originals are never moved or edited. The Battle 11
case study references already tracked repository assets rather than duplicating
them. Some deeper historical implementation links may refer to work not included
in the reporting-only commit; the documents are not a standalone software release.

Regenerate the selected archive from this local working tree with:

```sh
.venv/bin/python milestone_reports/archive_selected.py
```

See the [midterm reproduction README](M3.5.2_Midterm_Research_Report/README.md) to
rebuild the shareable PDF from its bundled sources without access to study caches.
