# Battle archive proposal and B9/B12/B16 image cleanup

2026-10-31 (Asia/Shanghai). Both requested parts are complete within their respective scope: archive **design only**, and targeted generated-image removal under the user's later explicit authorization. No recognition/StateEngine/HP/mechanics/OCR/sampling code or existing M3 dataset was changed. No full-video processing, OCR, tests, full replay, commit or push was run.

## Archive design

- [Design, field/provenance contract, saved-data export workflow, M3 compatibility, validation, storage estimate and B9–B23 migration proposal](../docs/battle-archive-proposal/README.md).
- [Proposed versioned JSON Schema](../docs/battle-archive-proposal/battle-archive-v0.1.schema.json).
- [Synthetic partial-opponent example](../docs/battle-archive-proposal/partial-opponent.example.json).

The design preserves six preview members separately from selected four, supported persistent identity separately from entry episodes, partial native builds, chronological receipt/effect history, HP/individual-hit/aggregate evidence, Speed witnesses, source hashes and causal availability. Unknown item/moves/SP/selection remains unknown. Public build occurrences, public aggregate usage and censored battle observations remain separate populations. No new archive pipeline, archive migration, dataset import or model training was implemented.

Current read-only M-C/Doubles VGC data: **1,083 public teams**, of which **557** have six eligible complete SP vectors, **515** have none and **11** have mixed completeness. The design does not treat “500 with SP + 1,000 without SP” as two disjoint verified datasets. It retains per-field candidate compatibility and existing source/occurrence identities.

Planning estimate: **5–15 MiB per structured battle archive**, provisional **20 MiB allowance**, excluding video/images/shared data and large solver companions. This is grounded in saved receipt-plus-final-state payloads of 4.29–8.03 MiB for sampled B9/B12/B16/B23 inputs; no actual archive size or compression saving is claimed. Unknown/unmapped source data requires explicit residual preservation and can exceed that estimate.

Validation performed on proposal artifacts only: JSON parsed; internal references/unknown-null/partial-selection checks passed; **Draft 2020-12 schema and example validate with zero errors**, using the installed system validator with an explicit local resolver. No dependencies were installed. This is not exporter, recognition or semantic battle acceptance.

## Cleanup policy and executed plan

The initial conservative plan would have removed only 1,700 duplicate PNGs from unsealed failed B16 v2/v4 runs. **It deleted zero files**: preflight guards stopped on concurrent Finder metadata updates. The user then explicitly authorized deleting B9/B12/B16 screenshots, regenerating them when needed. The expanded executed plan supersedes that earlier plan and includes sealed-run frames, review/reference screenshots, viewer assets and uniquely owned external diagnostic images.

Retained: all original MP4s; all Git-tracked files; curated fixture trees; source snapshot assets; structured observations, labels, reviews, receipts, states, HP/Speed evidence, manifests and original seals; shared/unowned files; every non-target battle. Generated reference/review pixels were removed under the expanded authorization, while their structured labels and original image hashes remain. Tests/reviews needing those removed generated pixels now require explicit scoped regeneration.

Ownership used canonical BattleArtifacts roots and unambiguous battle IDs in external paths. The exact plan records each deleted path, device/inode/link count, size, allocated blocks and SHA-256. Every deleted inode's links were wholly contained in the deletion set; no shared/protected/out-of-repository link was assumed reclaimable. Hard links into multiple viewers were counted once for storage.

Executed plan: [plan.json](../.cache/targeted-image-cleanup-20261031/expanded/plan.json), SHA-256 `62f39beba082bdaad00564445b7bd3eeef317e9bcd36d323d529ad6c9c91667a`.
Deletion journal: [deleted.jsonl](../.cache/targeted-image-cleanup-20261031/expanded/deleted.jsonl).
Verification: [after.json](../.cache/targeted-image-cleanup-20261031/expanded/after.json).

| Battle | Image paths removed | Distinct image inodes | Unique logical GiB removed | Inode allocated GiB removed | Logical GiB before | Logical GiB remaining | Allocated GiB remaining |
|---|---:|---:|---:|---:|---:|---:|---:|
| B9 | 10,797 | 5,526 | 5.739 | 5.750 | 7.385 | **1.645** | 1.744 |
| B12 | 3,964 | 2,490 | 1.625 | 1.630 | 9.612 | **7.987** | 8.019 |
| B16 | 13,718 | 7,398 | 7.912 | 7.927 | 9.857 | **1.944** | 2.102 |
| **Total** | **28,479** | **15,414** | **15.277** | **15.306** | **26.853** | **11.577** | **11.865** |

Remaining totals include original MP4, canonical cache/reports and battle-attributable external outputs, deduplicated by inode. New retention sidecars are included. The earlier [B9–B23 storage audit](storage-audit-b9-onward-20261031.md) is a **pre-cleanup historical snapshot**, not current storage.

B12 remains the largest of these three because its structured replay/inference/checkpoint packages and browser-profile data were deliberately retained; its `m342-offensive/` package family was about 4.436 GiB before cleanup and contains no targeted screenshot removal. Image cleanup does not authorize deleting those structured packages.

## Measured free space and limits

| Measurement | Bytes | GiB |
|---|---:|---:|
| Free immediately before unlinking, after planning/hashing | 34,277,974,016 | 31.924 |
| Free immediately after unlinking | 49,904,570,368 | 46.477 |
| **Immediate observed free-space increase** | **15,626,596,352** | **14.553** |
| Deleted unique inodes' recorded allocated blocks | 16,434,438,144 | 15.306 |
| Allocated-block estimate minus immediate free increase | 807,841,792 | 0.752 |
| Later post-verification free-space sample | 49,212,211,200 | 45.832 |
| Later sample minus pre-unlink free space | 14,934,237,184 | 13.909 |

Thus **15.306 GiB of inode-accounted allocation was unlinked**, while the immediate filesystem free-space increase was **14.553 GiB**. The 0.752 GiB discrepancy is not attributed to one proven cause: APFS clone/snapshot/compression accounting, delayed reclamation, concurrent system activity and audit writes can affect free space. The later lower free-space sample demonstrates continued system variation. These measurements do not establish exclusive physical extent ownership or promise permanent free-space recovery.

Local audit/checkpoint artifacts occupy about **141.17 MiB** (both superseded and executed plans, pre-state metadata, hashes and journal), outside battle totals. Most planning artifacts existed before the pre-unlink free-space measurement. They are ignored local outputs, not curated inputs, and were not compressed.

## Frozen artifact status: explicitly reduced retention

Original manifests and prediction seals were **not rewritten** or regenerated. Their hashes still describe the original structured data. The current full artifact bundles **are no longer image-complete**; a structured three-file seal passing would not establish complete bundle retention.

Each affected battle now has an explicit `image-retention-20261031.json` sidecar in its canonical cache root, recording the user's authorization, missing-image capability, exact deletion ledger and affected frozen runs:

- [B9 retention status](../.cache/battles/sample_battle_9/image-retention-20261031.json)
- [B12 retention status](../.cache/battles/sample_battle_12/image-retention-20261031.json)
- [B16 retention status](../.cache/battles/sample_battle_16/image-retention-20261031.json)

For the runs below, manifest = `.cache/battles/sample_battle_<n>/event-driven/<run>/manifest.json`; seal = the same directory's `video-only-seal.json`. Sizes are bytes; source-frame sizes are MiB before removal, excluding duplicate viewer links.

| Battle | Run | Manifest bytes | Seal bytes | Direct run PNGs removed | Direct PNG MiB |
|---|---|---:|---:|---:|---:|
| B9 | `m239-message-baseline-v1` | 14,574 | 453 | 754 | 835.14 |
| B9 | `m239-phase-profile-v1` | 14,779 | 453 | 754 | 835.14 |
| B9 | `m24-development-final-v1` | 15,490 | 453 | 754 | 835.14 |
| B9 | `m24-development-v2` | 14,862 | 453 | 754 | 835.14 |
| B9 | `m24-lightweight-final-v1` | 15,414 | 453 | 754 | 835.14 |
| B9 | `m24-lightweight-v1` | 14,782 | 453 | 754 | 835.14 |
| B9 | `m24-lightweight-v2` | 14,785 | 453 | 754 | 835.14 |
| B12 | `m341-actions-acquisition-v1` | 14,838 | 454 | 1,479 | 1566.95 |
| B16 | `b16-banner-hp-20261028-v1` | 16,181 | 454 | 1,276 | 1409.70 |
| B16 | `b16-banner-hp-20261028-v3` | 16,180 | 454 | 1,276 | 1409.70 |
| B16 | `b16-banner-hp-20261028-v5` | 16,100 | 454 | 1,276 | 1409.70 |
| B16 | `b16-banner-hp-20261028-v6` | 14,537 | 454 | 0 | 0.00 |
| B16 | `b16-semantic-state-20261027-v1` | 15,597 | 454 | 1,276 | 1409.70 |

B16 v6 stores no direct frame PNGs but depends on v5/source-run frames and viewer assets that were removed. Its **transitive image completeness is also false**, documented in the B16 sidecar and [retention-dependency-corrections.json](../.cache/targeted-image-cleanup-20261031/expanded/retention-dependency-corrections.json). A zero direct-image count is not proof that its original bundle survived intact. The original executed plan is kept immutable; the companion correction clarifies its direct-scope classification.

No significant screenshot volume remains blocked by frozen-image protection after the user's explicit policy override. Unresolved/shared outputs and original fixture/source assets remain protected.

## Verification and protected remainder

- All **87,766** protected hashes matched after deletion: tracked files and targeted structured/source/reference files, including original manifests/seals. No structured observation, receipt, BattleState, HP/Speed record or original MP4 was removed.
- All retained guarded preexisting paths retained their identity/size/mtime/link metadata. **Zero unexpected missing files and zero non-Finder changed preexisting files.**
- **116,536** explicitly battle-attributed paths across B10–B11, B13–B15 and B17–B23 were unchanged, alongside all other guarded preexisting files. No non-target image path was removed.
- Finder changed **20** existing `.DS_Store` files and created some new directory-view metadata; these OS metadata changes are recorded separately. The first post-delete result flagged that drift; [the initial result](../.cache/targeted-image-cleanup-20261031/expanded/after-initial-finder-drift.json) is retained. No battle data/source file was exempted from verification.
- Zero untracked generated target-image candidates remain under the ownership policy. Source/fixture bitmaps remain as follows:

| Protected bitmap group | Files | Logical bytes |
|---|---:|---:|
| B16: fixture | 6 | 629,353 |
| B9: source snapshot | 14 | 122,857 |
| B16: source snapshot | 14 | 122,857 |
| B12: source snapshot | 2 | 17,551 |

The B16 fixture images include banner/gray-zero-HUD regressions with provenance in `tests/fixtures/battles/sample_battle_16/banner_hp_v1/`. Frozen source snapshots retain their `recognition/assets/command_label_0.png` / `command_label_1.png` source assets. These are fixtures/source dependencies, not accumulated battle screenshots. The preservation of all Git-tracked files was hash-checked.

Existing labels/reviews still retain their original image identifiers/hashes; those generated image paths can now be missing. Original video, source PTS/time base, observation metadata, source/profile snapshots and the deletion hash ledger provide the regeneration inputs. Any future regeneration should be explicitly scoped to needed frames and versioned separately, verifying geometry/encoding/pixel identity; it must not silently relabel a new extraction as the original frozen run or original cold timing. No regeneration was performed.

Durable completion/resume status is [progress.json](../.cache/targeted-image-cleanup-20261031/expanded/progress.json). Cleanup is complete; do not repeat deletion or regenerate the plan. If a later independent verification is needed, the saved helper's `verify` action writes audit results only; it runs no recognition/OCR/replay. The archive migration remains a future proposal requiring separate authorization.
