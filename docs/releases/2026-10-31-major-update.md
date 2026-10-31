# October 2026 major update: recorded-battle recognition and M3 inference

This update consolidates the accumulated production, inference, evaluation and
documentation changes through B23. It adds Ditto/Transform handling, evidence-backed
multi-hit HP resolution, broader damage/build inference and recent-video reports.
It does not declare a new accepted milestone or whole-match accuracy guarantee.

## Recent video evidence

| Recording / comparison | Result | Interpretation |
|---|---:|---|
| B22 visible Battle Log message reference | **100/104 = 96.15%** | Message-record reproduction on the readable partial reference; 102 corresponding accepted receipts |
| B22 numerical HP reference | 18/20 raw ordered endpoint pairs; 16/20 exact resolution groups | Separate HP denominators, not included in the 96.15% message figure |
| B23 visible Battle Log message reference | **65/69 = 94.20%** | Accepted corresponding semantic records on the partial reference |
| B23 move executions within that reference | 21/21 | Scoped move records, not all events in the recording |
| B23 ordered HP endpoints / exact aggregate groups | 15/15 each | Only 12/15 groups are program-marked complete and causally supported |
| B23 production run | 787.28 s video; 803.717 s external CLI wall | PTR 1.020878 s/video-second; includes reconstruction and export |

These figures preserve the original reference definitions. They do not establish
whole-video precision/recall, full per-field semantic correctness or complete
mechanical state reconstruction. B22 and B23 have different partial references;
their headline fractions are not pooled into a global accuracy estimate.

Sources: [B22 first-run report](../b22-ditto/report.md),
[B23 benchmark and comparison](../mega-b23/report.md).

## Recognition and observable state

- Consolidate the event-driven/lightweight production path, configurable 2/3 FPS
  acquisition and monitoring, independent detailed-inspection scheduling, crop
  reuse and durable per-battle processing. Experimental adapters remain separate.
- Improve preview/team-profile acquisition, identity admission, banner/HP refresh,
  zero-HP handling, confusion/Struggle messages and double-faint arrival recovery.
- Support Ditto's copied appearance, ability, types, non-HP stats, stages and
  source-qualified moves. Preserve its own HP/item/native identity, restore native
  state on departure and handle repeated transformation messages without copying
  twice. Supported return evidence links one persistent Ditto to two entry episodes.
- Preserve original encounter/episode identifiers and uncertainty. Copied moves
  do not become confirmed native equipped slots; unknown PP and targets stay unknown.
- Calculate reviewed Champions native/Mega statistics from saved SP/alignment,
  keeping form changes separate from HP and stat stages. B23's first production run
  remained **unbound to Team 7**; later calculations are not relabelled as runtime inputs.

Sources: [B16 banner/HP validation](../b16-banner-hp/progress.md),
[B21 double-faint recovery](../b21-double-faint/report.md),
[B22 Transform/Unnerve implementation](../b22-implementation/report.md),
[Mega statistics](../mega-b23/report.md).

## Damage, multi-hit evidence and M3 inference

- Group sequential HP evidence by parent action and immediate cause. Preserve
  endpoint units, attribution uncertainty, recovery/recoil/residual effects and
  exact segment membership; animation readings do not automatically become hits.
- Inspect admitted multi-hit windows locally at 3 FPS, with 4 FPS fallback when
  required, through existing sampling/OCR/resolution adapters. B22 Dual Wingbeat
  resolves **72→51→27 HP**, two hits of **21 and 24 HP**, aggregate **45 HP**.
  This is a scoped validated example, not measured reliability for all multi-hit moves.
- Extend offensive/defensive stat selection, contextual ability/item effects,
  joint damage/Speed/SP constraints, item policies, source-qualified move legality
  and causal rewind of supported candidates.
- Keep public build occurrences, candidate feasibility, conditional sample shares
  and exploratory similarity distinct. Preserve source IDs and incomplete fields;
  unknown opponent builds and unobserved selections receive no invented prior.
- Expand replay presentation and offline build-association research with saved
  provenance, source-group evaluation and explicit limitations.

Sources: [B22 per-hit validation](../b22-followup/report.md),
[offensive inference](../../reports/M3.4.2-offensive-stat-inference.md),
[item policy](../../reports/M3.4.3b-item-policy.md),
[empirical move evidence](../../reports/M3.4.4-soft-move-evidence.md),
[team-item review](../../reports/M3.4.5a-team-items-and-stat-review.md),
[build similarity](../../reports/M3.5.1-build-similarity.md).

## Storage, evidence and archive design

The B9–B23 audit distinguishes logical size, inode allocation and hard-link aliases.
The user-authorized B9/B12/B16 cleanup removed 28,479 generated-image paths,
15,414 unique image inodes and 15.306 GiB of inode-accounted allocation. Immediate
filesystem free space increased by 14.553 GiB; later system-wide free space varied.
Original MP4s and structured evidence remain local; source/fixture dependencies remain.

Affected frozen bundles are explicitly **image-incomplete** under a recorded
reduced-retention policy. Original structured seals were retained unchanged. A
structured seal passing does not imply the original pixels are still available.
Generated-image-dependent reviews/tests require scoped regeneration when needed.

The proposed long-term archive preserves partial opponent rosters/selections,
persistent identities, actions, HP/Speed constraints and source provenance. It
includes a JSON Schema and synthetic example; **no archive exporter or migration
has been implemented**. Public build data, aggregate usage and censored battle
evidence remain separate populations.

Sources: [storage audit](../../reports/storage-audit-b9-onward-20261031.md),
[cleanup and archive report](../../reports/battle-archive-and-image-cleanup-20261031.md),
[archive proposal](../battle-archive-proposal/README.md).

## Validation for this push

Focused portable regressions: **370 passed, 5 deselected in 299.26 seconds**.
The five deselections are explicitly marked optional local-artifact checks;
no failed present artifact was treated as missing. The selected suites cover
Ditto/Unnerve, Mega stats, HP attribution/completion/resolutions, sequential and
multi-hit evidence, double-faint arrivals, confusion/Struggle, preview/switch fixes,
offensive damage, item/team-item policies, empirical measures, build similarity
and Git artifact policy. No historical-video recognition or OCR was run.

Static checks passed for all **127 staged Python files**, **38 staged JSON files**,
and the three changed/new replay JavaScript/CJS files. Staged whitespace review
passed. Git tracking review found no ignored paths in the index and no broken or
untracked symlink targets. This is focused regression coverage, not a full-suite
or whole-match semantic-accuracy claim.

Original videos, decoded frames, OCR caches, full-state snapshots and large
generated inventories are excluded from the commit. The historical generated
B16 cleanup inventory is explicitly ignored; its compact result and reports remain.
