# Read-only storage audit: B9–B23

2026-10-31 (Asia/Shanghai). Repository: `/Users/yyi/Pokemon-Champions-Assistant`.
Only this report was saved. No recognition, decoding, OCR, tests, replay, compression, relocation, deletion, commit or push was performed. Existing working-tree changes were preserved.

## Findings

- **58.000 GiB logical / 58.617 GiB allocated** is attributable to individual retained battles: **209,070 distinct regular files at 239,557 paths**.
- Another **1.874 GiB logical / 1.890 GiB allocated**, 8,287 files, is related shared or unresolved-owner diagnostic/document storage. Including it gives **59.874 GiB logical / 60.507 GiB allocated**, 217,357 distinct files at 247,844 regular-file paths.
- Largest individual consumers: **B16 9.857 GiB**, **B12 9.612 GiB**, **B9 7.385 GiB**. B16 retains multiple frame-producing revisions; B12 has **4.436 GiB** in `m342-offensive/`; B9 retains seven event-driven run directories.
- Original MP4s: **16.036 GiB (27.6%)**, all 15 present at `tests/fixtures/sample_battle_<n>.mp4`. Remaining individually attributable data: **41.965 GiB**. This remainder includes protected curated/frozen evidence as well as technically regenerable output; it is **not** a deletion estimate.
- Frame PNGs dominate at **29.213 GiB**. Naively summing regular-file paths gives **90.557 GiB**, overstating unique logical content by **32.556 GiB** because of hard links.

## Measurement and scope

Metadata census used `os.walk(..., followlinks=False)`, `lstat`, and file identity `(st_dev, st_ino)`. Logical = `st_size`; allocated = `st_blocks * 512`, counted once per inode. No content hashing/deduplication was attempted: distinct copies remain distinct files even if their bytes match.

Canonical ownership follows `BattleArtifacts`: `.cache/battles/sample_battle_<n>/`, `reports/battles/sample_battle_<n>/`, and the registered MP4. Other outputs were attributed using unambiguous battle IDs in paths, curated fixture paths, or a saved browser validation's initial target URL/artifact. External outputs include B11/B12 browser profiles/screenshots, document-build copies, battle-specific docs and fixtures, and B22's saved Mega validation. Mixed-battle documents and generic diagnostic directories remain separate rather than allocating their bytes arbitrarily. The shared appendix covers the listed M3.2.2/M3.4.x diagnostic families, `.cache/diagnosis/`, and explicitly named combined B9+ docs/reports; it is not a census of every shared project-stage cache. Mixed earlier-battle stage evidence such as `.cache/m34-visual-v21/` and `.cache/m34-visual-v22/` is included only where a file has an explicit B9+ owner.

Git metadata, virtual environments, `node_modules`, and `__pycache__` were excluded; shared model/knowledge/research databases and unowned mixed `outputs/video/` files are outside the battle totals. Source files inside retained frozen run snapshots are included. No filesystem read errors occurred. This is a repository audit, not a whole-machine inventory.

Directory blocks, symlink payloads, extended attributes/resource forks, filesystem metadata, APFS snapshots and clone extent sharing are excluded from file totals. **Allocated bytes are not guaranteed reclaimable bytes.** A hard-linked file releases no data blocks while another link remains. All link names for individually attributed hard-linked files were accounted for within their battle's audited set; no cross-battle shared inodes were found. This still cannot measure APFS snapshot/clone retention or promise free-space recovery. Symlink targets were never traversed or charged again; 237 battle-attributed symlinks were observed. Counts below exclude symlinks.

## Per-battle storage, largest first

GiB (2³⁰ bytes). Each location is deduplicated internally. **Cache/report/other columns overlap** when the same inode appears in different locations; subtract the overlap column to obtain the unique total. File counts show unique inodes / regular-file paths. B<n> means `sample_battle_<n>`.

| Battle | MP4 | Cache | Reports/viewers | Other owned | Cross-location overlap | Unique total | Allocated | Files unique / paths |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B16 | 1.316 | 8.401 | 5.643 | 0.003 | 5.506 | **9.857** | 10.029 | 54,214 / 60,534 |
| B12 | 1.481 | 6.362 | 1.552 | 1.748 | 1.530 | **9.612** | 9.648 | 14,199 / 15,673 |
| B9 | 0.778 | 6.447 | 5.868 | 0.001 | 5.709 | **7.385** | 7.494 | 38,617 / 43,889 |
| B11 | 1.087 | 1.917 | 1.074 | 1.335 | 1.057 | **4.356** | 4.389 | 13,431 / 14,433 |
| B22 | 1.505 | 2.096 | 1.838 | 0.008 | 1.805 | **3.642** | 3.679 | 12,003 / 13,698 |
| B10 | 1.446 | 1.991 | 1.557 | 0.005 | 1.535 | **3.464** | 3.491 | 9,181 / 10,611 |
| B15 | 1.449 | 1.943 | 1.590 | 0.000 | 1.540 | **3.443** | 3.474 | 11,798 / 14,636 |
| B23 | 1.376 | 1.739 | 1.672 | 0.000 | 1.641 | **3.147** | 3.180 | 10,646 / 12,206 |
| B21 | 1.229 | 1.529 | 1.459 | 0.000 | 1.410 | **2.807** | 2.834 | 8,858 / 10,237 |
| B17 | 0.927 | 1.243 | 1.145 | 0.000 | 1.099 | **2.216** | 2.240 | 7,729 / 9,820 |
| B20 | 0.841 | 1.084 | 1.014 | 0.000 | 0.975 | **1.964** | 1.986 | 7,060 / 8,006 |
| B18 | 0.736 | 1.070 | 0.965 | 0.000 | 0.861 | **1.911** | 1.930 | 6,600 / 9,088 |
| B19 | 0.684 | 0.914 | 0.869 | 0.000 | 0.851 | **1.617** | 1.639 | 6,788 / 7,564 |
| B13 | 0.612 | 0.666 | 0.647 | 0.000 | 0.611 | **1.315** | 1.327 | 4,064 / 4,681 |
| B14 | 0.569 | 0.672 | 0.654 | 0.000 | 0.628 | **1.266** | 1.278 | 3,882 / 4,481 |
| **Attributed total** | **16.036** | **38.074** | **27.548** | **3.100** | **26.758** | **58.000** | **58.617** | **209,070 / 239,557** |
| Related shared/unresolved | — | — | — | 1.874 | — | 1.874 | 1.890 | 8,287 / 8,287 |
| **Overall audited footprint** | | | | | | **59.874** | **60.507** | **217,357 / 247,844** |

For example, B16's cache/report location totals share **5.506 GiB**. B15 frames can have three links (cache, production viewer, review viewer). B17/B18 also hard-link saved observations/replays into diagnostic packages. These are counted once in battle/category totals; removing one viewer link would not reclaim those frames.

## Cache breakdown per battle

MiB (2²⁰ bytes), unique within each battle's **canonical cache**. PNG = sampled/frame PNG; OCR = OCR/icon JSON caches; Obs = observations/events; State = state projections and state/inference checkpoints; Replay = replay/reconstruction/inference artifacts; Diag = diagnostics, monitor JSON, benchmark records and diagnostic/evidence images; Source = frozen source snapshots; Other = remaining metadata/report assets. Categories are exclusive; totals reconcile before rounding. They classify file function, not protection status.

| Battle | PNG | OCR | Obs | State | Replay | Diag | Source | Other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B16 | 8031.27 | 3.31 | 212.95 | 38.77 | 111.82 | 95.34 | 79.43 | 29.30 |
| B12 | 1566.95 | 0.25 | 43.12 | 1406.20 | 3414.83 | 58.77 | 11.01 | 13.55 |
| B9 | 5845.96 | 3.62 | 194.64 | 41.14 | 173.49 | 234.31 | 77.03 | 31.30 |
| B11 | 1082.93 | 0.20 | 29.95 | 84.16 | 715.24 | 30.75 | 11.01 | 9.04 |
| B22 | 1968.25 | 0.37 | 44.30 | 8.89 | 44.97 | 68.47 | 11.21 | 0.16 |
| B10 | 1571.86 | 0.26 | 58.52 | 101.25 | 195.17 | 85.21 | 11.01 | 15.03 |
| B15 | 1576.79 | 0.52 | 41.54 | 0.31 | 15.85 | 344.05 | 11.02 | 0.03 |
| B23 | 1680.48 | 0.35 | 41.14 | 0.56 | 14.47 | 31.48 | 11.21 | 1.31 |
| B21 | 1444.23 | 0.29 | 32.32 | 0.52 | 27.58 | 49.58 | 11.15 | 0.53 |
| B17 | 1125.37 | 0.27 | 58.89 | 0.27 | 38.54 | 37.20 | 11.81 | 0.03 |
| B20 | 998.29 | 0.25 | 23.64 | 1.08 | 35.21 | 39.51 | 11.14 | 0.43 |
| B18 | 881.57 | 2.52 | 65.70 | 3.91 | 52.98 | 76.52 | 12.47 | 0.02 |
| B19 | 871.44 | 0.22 | 20.55 | 0.94 | 6.13 | 25.84 | 11.14 | 0.02 |
| B13 | 625.34 | 0.68 | 20.80 | 1.76 | 7.16 | 15.57 | 11.02 | 0.03 |
| B14 | 642.98 | 0.16 | 13.68 | 0.69 | 4.03 | 15.17 | 11.02 | 0.02 |
| **Total MiB** | **29913.73** | **13.26** | **901.75** | **1690.44** | **4857.45** | **1207.78** | **302.68** | **100.79** |

## All attributable categories, largest first

Includes cache, reports and other owned outputs, with global inode deduplication. Cache is preferred as the category representative when its frame is linked into a report. A benchmark's frames, reads, checkpoint and source snapshot remain in their functional categories; “Diagnostics/benchmark records” is the residual records, logs and browser cache, not the whole sealed run.

| Category | Logical GiB | Allocated GiB | Unique files |
|---|---:|---:|---:|
| Sampled/frame PNG | 29.213 | 29.265 | 27,517 |
| Original MP4 | 16.036 | 16.036 | 15 |
| Replay/inference artifacts | 4.751 | 4.752 | 623 |
| Diagnostics/benchmark records | 4.054 | 4.190 | 47,153 |
| State/inference checkpoints | 1.651 | 1.651 | 294 |
| Observations/events | 1.126 | 1.174 | 27,105 |
| Diagnostic/evidence images | 0.366 | 0.373 | 3,712 |
| Report/viewer/reference files | 0.361 | 0.362 | 183 |
| Frozen source snapshots | 0.296 | 0.302 | 2,939 |
| Other metadata/outputs | 0.134 | 0.138 | 1,440 |
| OCR/icon caches | 0.013 | 0.375 | 98,089 |
| **Total** | **58.000** | **58.617** | **209,070** |

The **98,089 OCR/icon cache files** contain only **13.26 MiB** of logical data but consume **383.70 MiB** of allocated blocks. This is small-file allocation overhead, distinct from PNG volume.

Related shared/unresolved storage, not charged to individual battles:

| Directory | Logical MiB | Allocated MiB | Files |
|---|---:|---:|---:|
| `.cache/m345/` (unassigned portion) | 824.18 | 829.89 | 2,795 |
| `.cache/m345a/` (unassigned portion) | 539.79 | 542.30 | 1,239 |
| `.cache/m322/` (unassigned portion) | 477.33 | 483.63 | 3,255 |
| `.cache/m342/` (unassigned portion) | 59.07 | 60.78 | 895 |
| `.cache/diagnosis/` (unassigned portion) | 12.93 | 12.98 | 18 |
| `.cache/m344/` (unassigned portion) | 3.27 | 3.38 | 44 |
| `.cache/m343b/` (unassigned portion) | 1.65 | 1.70 | 25 |
| `.cache/m343a/` (unassigned portion) | 0.31 | 0.32 | 7 |
| Mixed-battle docs/reports | 0.12 | 0.15 | 9 |
| **Shared total** | **1918.65** | **1935.13** | **8,287** |

These include multi-battle UI review records/profiles, failed or incomplete browser attempts without a conclusive owner, combined benchmark results and B17–B19 reports. Some are reproducibility/acceptance evidence. They have not been classified as safe to discard.

## B16–B23 cost per minute and sampled frame

Durations come only from existing metadata: B16's `evaluation/b16-semantic-state-20261027-v1/normal-process.json:video_seconds`; B17–B23's `fresh-benchmark/<run>/input.json:duration_seconds`. No media tool was invoked. Per-minute costs cover **all retained individually attributable revisions** of that battle. Derived = unique battle total minus original MP4; protected evidence is included.

The frame comparison uses one production run per battle: B16 `b16-semantic-state-20261027-v1`; B17/B18 `fresh-b17-b18-20261028-v1`; B19 `fresh-b19-postfix-v1`; B20 `fresh-b20-postfix-v1`; B21 `fresh-b21-context-v1`; B22 `fresh-b22-ditto-20261030-v1`; B23 `mega-b23-20261030-v1`.

| Battle | Video min | 2 FPS samples / retained PNGs | Video MiB/min | Derived MiB/min | Total MiB/min | Allocated MiB/min | PNG MiB/retained frame | Run MiB/2 FPS sample |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B16 | 12.562 | 1508 / 1276 | 107.28 | 696.18 | 803.46 | 817.46 | 1.105 | 0.981 |
| B17 | 8.829 | 1060 / 1052 | 107.54 | 149.46 | 257.00 | 259.83 | 1.070 | 1.115 |
| B18 | 7.026 | 844 / 831 | 107.30 | 171.15 | 278.45 | 281.21 | 1.061 | 1.134 |
| B19 | 6.530 | 784 / 776 | 107.32 | 146.27 | 253.59 | 257.02 | 1.123 | 1.167 |
| B20 | 8.017 | 962 / 947 | 107.42 | 143.45 | 250.87 | 253.66 | 1.054 | 1.090 |
| B21 | 11.720 | 1407 / 1385 | 107.36 | 137.87 | 245.23 | 247.59 | 1.043 | 1.071 |
| B22 | 14.336 | 1721 / 1697 | 107.48 | 152.67 | 260.14 | 262.80 | 1.089 | 1.122 |
| B23 | 13.121 | 1575 / 1566 | 107.39 | 138.17 | 245.56 | 248.16 | 1.073 | 1.115 |

**Trend:** there is no monotonic storage improvement. Average retained PNG size is 1.105 MiB in B16 and 1.073 MiB in B23 (**2.9% lower**); B13–B16 pooled = 1.087 MiB versus B17–B23 pooled = 1.072 MiB (**1.3% lower**). However, full production-run storage per monitored 2 FPS sample rises from 0.981 MiB in B16 to 1.115 MiB in B23 (**13.7% higher**); pooled B13–B16 = 0.988 MiB versus B17–B23 = 1.113 MiB (**12.6% higher**).

The denominators differ: manifests count monitored/materialized samples, while only selected detailed-inspection PNGs remain on disk (B16: 1,276 / 1,508; B23: 1,566 / 1,575). Thus the figures measure retained storage under each run's save/inspection policy and visual content, not PNG compression efficiency at fixed content. B20's manifest is `cold_run=false`; its retained footprint is measurable, but it is not an uninterrupted cold-run timing comparator. B16's high all-revision MiB/min reflects accumulated revisions and focused samples, not the cost of a single fresh pass.

## Evidence that remains necessary

No deletion candidates are proposed. “Derived” describes origin; it does not remove evidence or reproducibility obligations.

- **Original recordings:** retain all 15 registered MP4s for source-pixel review, acquisition regression and reproducible evaluation. OCR text/state cannot reconstruct the original visual evidence. Their saved hashes and container-duration metadata establish input identity.
- **Portable regression evidence:** retain curated `reports/battles/*/inputs/`, `tests/fixtures/battle_evidence/battle10-*.json`, `battle11-*.json`, `battle12-*.json`, B16's `tests/fixtures/battles/sample_battle_16/` references and `banner_hp_v1/*.png` with provenance, and `tests/fixtures/b20-confusion-messages.json`. `tests/test_banner_hp_tracking.py` reads actual B16 pixels. `tests/test_m344_damage_review.py` explicitly hashes `battle12-damage-review.json` as the frozen prefix. Shared reviewed team fixtures are dependencies but are not assigned to one battle's storage total.
- **Optional historical regression inputs:** local-artifact tests depend on B10–B12 `m322-reviewed-speed/latest.json` and their target packages; B11/B12 `m342-offensive/latest*.json`, replay packages and curated review sources support damage, item, empirical-ability and speed-projection checks. Relevant callers include `test_speed_replay_projection.py`, `test_mega_empirical_abilities.py`, `test_offensive_damage.py`, `test_hatterene_damage.py`, `test_m344_damage_review.py` and `test_team_items.py`. Preserve transitive manifests, observations, checkpoints and evidence images needed by those exact package identities. An optional-test marker is not permission to remove its evidence.
- **Frozen first-run benchmarks:** B17–B23 `fresh-benchmark/<run>/initial-freeze.json` records respectively **7,597 / 6,345 / 5,970 / 6,671 / 8,423 / 11,574 / 10,602** file hashes. Preserve those manifests and their referenced raw frames, reads, icons, monitor/observation files, source snapshots, events, receipts/state, execution/input metadata, HP projection and logs. `scripts/run_fresh_video_benchmark.py:freeze` seals the entire production run, not merely its summary. A newly generated equivalent-looking file does not preserve first-run evidence or its measured execution. These counts were read from saved seals, not rehashed or semantically validated.
- **B16 and earlier sealed comparisons:** retain `video-only-seal.json`, its listed observations/events/replay, source snapshot, input identity, evaluation/reference files and comparison baselines for any frozen claim still relied on. B10's `m34-v21-holdout-frozen-v1`, B13–B15's `fresh-heldout-20261026-v1`, and B16's first production run and banner/HP acceptance revisions are not interchangeable fresh outputs.
- **Review/evaluation provenance:** preserve B17–B23 log transcriptions, log-reference image hashes, source reviews, versioned validation summaries and unresolved-result records. In particular, B23's frozen unbound team-linkage result must remain distinguishable from later corrected calculations.
- **Technically regenerable outputs:** unprotected decoded/sampled images, OCR/icon memoization, replays/projections, HTML viewers and temporary browser profiles can be recreated only with the original MP4, matching source/models/rules/configuration and any required human annotations. They are not established as unprotected by this category audit. Many frames are hard links to protected/viewer evidence, and frozen source/cache files preserve evaluation identity. A full dependency/protection closure would be required before making any file-level disposal recommendation.

This audit measures retained bytes and identified dependency classes. It does not rerun acceptance checks, verify every saved hash, measure recognition accuracy, or certify a minimal regression/evaluation retention set.
