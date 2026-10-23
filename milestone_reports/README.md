# Research and milestone reports

This directory collects selected research documents suitable for collaborator
review. Original project reports remain at their existing paths. These are
research snapshots: completed software/experiments do not imply independent
acceptance of mechanics, recognition quality or tactical interpretations.

| Report | Main research contribution | Formats | Status |
|---|---|---|---|
| [M3.5.2 — Midterm research report](M3.5.2_Midterm_Research_Report/README.md) | Joint hidden-build feasibility and empirical usage; nonlinear SP distance, learned moveset association, species-specific clustering and grouped prediction, with explicit SP-only/combined comparisons | [PDF](M3.5.2_Midterm_Research_Report/report.pdf), [LaTeX](M3.5.2_Midterm_Research_Report/report.tex), bundled figures and compact numerical/provenance summary | Awaiting human review; synthesis of completed experiments |
| [M3.5.1 — Build similarity learning and archetype discovery](Previous_Milestones/M3.5.1_Build_Similarity/report.md) | Occurrence-preserving offline association/clustering study with mixed findings; learned moves do not beat SP-only numeric reconstruction | Markdown and 11 bundled scientific figures | Completed experiment; interpretations preliminary, no independently accepted tactical archetypes |
| [M3.2.2 — Battle 11 Speed case study](Previous_Milestones/M3.2.2_Battle11_Speed/report.md) | Causal action-order evidence reduces joint Speed supports while preserving uncertainty; illustrates distinct empirical/reference layers | Markdown; references existing tracked case-study images/audit assets under `docs/assets/` | Preliminary research demonstration; source-reviewed conditions, independent acceptance not established |
| [M3.1.2 — Joint Champions stat feasibility](Previous_Milestones/M3.1.2_Stat_Feasibility/report.md) | Compact exact joint point-domain/budget representation; gaps and interactions between stat legality and inverse damage | Markdown | Completed conditional feasibility experiment under pinned reference rules; not official mechanics certification |

The earlier reports were chosen for mathematical or experimental substance.
Technical handoffs, debugging logs, cache receipts and broad validation dumps are
not archived as presentation documents. Historical counts and superseded limits
remain labeled as historical; use the midterm report for the current synthesis.

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
