# Git tracking cleanup after battle migration

The staging area tracks source/tests, shared knowledge databases, curated screenshots, manual initialization/annotation inputs, Markdown documentation and explicitly listed concise validation JSON. All other `reports/` files are ignored by default. HTML, complete replay states/snapshots, OCR dumps, extracted images and JSONL traces are local artifacts; `.cache/` and recorded videos remain ignored.

303 previously tracked generated paths were removed from the index only. Their local files, canonical battle directories and historical aliases remain available. Existing application changes are retained and staged; no reset, restore, commit or push was performed. Removal from the index does not purge old Git history.

## Proposed tracking

- Application and migration source: `battle_artifacts.py`, `tracking/`, `scripts/`, existing application packages.
- Tests: existing tests, artifact isolation/hidden-state/quantitative regression tests, Git policy/setup tests and explicit local-integration prerequisites in `tests/conftest.py`.
- Curated initialization/annotation inputs: `reports/battles/sample_battle_{0,1,2,3}/inputs/*.json`, with precise ignore exceptions and their historical fixture/configuration aliases tracked together. Largest curated input: 175,424 bytes. The original input blob contents are unchanged.
- Portable event test oracles: `tests/fixtures/battles/sample_battle_2/reviewed_events.json` (23,848 bytes; twenty reviewed events) and `tests/fixtures/battles/sample_battle_3/reviewed_mechanic_events.json` (9,968 bytes; four selected mechanics events). These are frozen test expectations against existing manual annotations, not full-state/OCR output.
- Compatibility definitions: `data/battle_artifact_aliases.json`; shared Pokémon databases and rules remain outside recording directories.
- README, migration/milestone documentation, this summary and explicitly allowed small validation files.

Run `python scripts/review_git_tracking.py` to inspect the current index. `reports/git-tracking-review.json` contains the complete proposed tracked-file list, every staged change, total blob sizes, largest files and symlink checks; this machine review is intentionally local/ignored.

## Compatibility and clean clones

`python scripts/setup_battle_workspace.py` recreates historical aliases only when canonical targets exist. It is deterministic, refuses conflicts and never creates dangling links, decodes recordings or runs OCR. Existing local aliases remain intact. `scripts/migrate_battle_artifacts.py` is for a checkout with legacy local data, not for an empty clone lacking recordings.

Portable replay tests regenerate states/timelines in memory from curated inputs and event fixtures, rather than loading ignored reports. The existing quantitative Swords Dance, hidden-state and decision-projection tests remain portable. Complete historical reconstruction/HTML/recording checks are explicitly marked `local_artifacts` and skip only when a declared prerequisite is absent; they continue to run against available local caches. Source-frame checksum validation is a separate local integration check, while initialization assertions always run. The real OCR team-configuration check declares its existing icon-cache dependency as well as its existing model dependency.

A fresh tree exported directly from the staging area has all 24 retained symlink targets tracked and available. Videos, caches and generated reports are absent in that test tree. Selected historical provenance paths in curated annotations intentionally refer to absent local screenshots; they are evidence addresses, not required portable test fixtures.

## Largest retained files

| File | Git bytes | Purpose |
| --- | ---: | --- |
| `knowledge/data/identity.json` | 4,094,541 | Shared identity database |
| `tests/fixtures/move_selection.png` | 3,737,756 | Existing curated recognition test screenshot |
| `tests/fixtures/battle_screen.png` | 3,676,482 | Existing curated recognition test screenshot |
| `tests/fixtures/team_preview.png` | 3,476,537 | Existing curated recognition test screenshot |
| `tests/fixtures/m12_video_preview.png` | 3,053,145 | Existing curated recognition test screenshot |

These are existing necessary knowledge/test assets, not new extracted frame collections. The complete retained tree is about 39.5 MiB; new or changed blob contents compared with HEAD are about 0.5 MiB before Git compression. The numerous deleted generated paths account for most changed-file entries and approximately 12.2 million removed lines. Review application changes separately with `git diff --cached -- .gitignore README.md battle_artifacts.py scripts tracking tests data`.

## Final staging and validation

- 219 tracked files; 406 proposed changed paths: 50 additions, 33 modifications, 20 regular-file-to-symlink changes and 303 index-only deletions. The link changes have their canonical targets staged.
- HEAD's tracked blob total: 889,463,848 bytes; proposed tracked blob total: approximately 41.38 MB (39.5 MiB). Unique new/changed blob contents are approximately 0.52 MiB; unchanged curated inputs and documentation moved to canonical paths reuse existing blob objects. Exact refreshed values are in the machine review.
- Staged-tree export: all 24 retained symlinks resolve to included files; no missing required portable fixtures and no ignored paths remain in the index. Optional media/cache evidence is intentionally absent and explicitly reported by compatibility setup.
- Clean staged-tree full suite: **373 passed, 34 skipped** in 64.60s. Skips identify optional local integration/model prerequisites. One existing Paddle ccache warning does not affect results.
- Local artifact-path, hidden-state, quantitative-grounding and milestone suites: **88 passed** in 135.82s. Final focused path/M2.3.1/Git-policy/initialization/checksum checks: **27 passed** in 9.76s.
- `git diff --cached --check` passed; application modifications are retained, with no unstaged tracked-file changes after preparation. Compatibility setup is a no-op in this local checkout and does not create dangling links in the clean exported tree.
- All five local recordings remain present (approximately 0.79–1.36 GB each), along with local generated reports, extracted frames and caches. Git index cleanup used `git update-index --force-remove`; it did not remove working files. No historical battle decoding or OCR pipeline was rerun for migration. The clean full test suite may exercise installed OCR test backends against curated fixture screenshots.

The staging area is ready for review only. Nothing was committed or pushed. Git history/reflog objects are unchanged; this cleanup controls the proposed commit and future tracking, not historical repository size.
