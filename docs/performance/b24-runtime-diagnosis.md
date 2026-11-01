# B24 runtime regression diagnosis — 2026-11-01

## Findings and confidence

B24's original cold production CLI took **1460.983723 s** for **1052.82 s** of video, PTR **1.387686**. B23 took **803.716960 s** for **787.28 s**. The increase is **657.266763 s**. Of that increase, **500.616337 s (76.17%)** lies in the broad reconstruction/package timer; **108.696208 s (16.54%)** is additional cumulative OCR call time; **23.683428 s (3.60%)** is additional icon call time; **24.270789 s (3.69%)** is the remaining accounting residual. These reconcile to the external wall difference, but are not four independently instrumented pipeline stages.

The regression combines increased workload with increased cost per receipt. B24 has 36.54% more receipts, whereas its broad reconstruction time is 139.85% higher; broad seconds/receipt rose 75.66%. OCR has 47.54% more calls and a **9.19% lower mean call time**, so slower OCR calls do not explain its increase. B24 additionally recognizes a complete own roster: 84 icon calls versus 12 and a bound own-team profile versus B23's unbound profile.

The strongest measured optimization lead is **repeated traversal of a much larger retained state**. Frozen production code copies the entire state and serializes/hashes it per processed receipt. New isolated component measurements on frozen final snapshots show B24 copy CPU cost about **2.10×** B23 and hash CPU cost about **2.36×**; dataclass conversion and JSON encoding account for most of the measured hash path. This supports the mechanism, but **does not assign a measured number of the historical 500.616 extra seconds to those functions**. The original production run was not function-profiled, and terminal snapshots are not the historical prefix series.

No runtime optimization was implemented. This report was completed only after the B24 Speed audit/report and its targeted validation. No video decoding, OCR, icon recognition, StateEngine replay, production CLI or historical benchmark was rerun or overwritten. All component experiments read saved states and write separate per-battle diagnostic namespaces.

Machine-readable evidence: `docs/performance/b24-runtime-diagnosis-measurements.json`, schema 2, embeds the recovered B21–B24 measurements, all source hashes, progress/checkpoint data and complete component profiles. Earlier `b24-runtime-measurements.json` is preserved unchanged. Publication rechecked **40 source hashes with zero mismatches**, all four original receipt counts/event-type distributions/state sizes, external/internal/broad timer values, and the component input/script hashes.

## Timer boundaries and reconciliation

The timing source is `scripts/run_fresh_video_benchmark.py::run_battle`. Each battle has one successful original attempt; profiler was disabled. `perf_counter()` starts immediately before `subprocess.Popen(main.py ...)`, ends after process exit, and includes imports/startup, acquisition, reconstruction, exports and final work. A 30-second `wait(timeout=30)` returns when the child exits; it does not round the measurement to 30 seconds. Source video header probes occur outside this subprocess interval. Subsequent `derived_projection`, sealing, validation and report generation are excluded. The projection-stage JSON explicitly marks them outside normal CLI time.

`recognition.fast_video.analyze` starts its `monotonic()` timer near entry. `cold_end_to_end_wall_seconds` is set after reconstruction/viewer packaging and saving the completed manifest, but before final output digest calculation and final manifest publication. Thus external minus internal includes work on both sides of that timer, not a measured startup-only stage. All four runs use the same definitions, 2 FPS setting, ARM64 macOS/Python 3.10.4 environment, and fresh per-battle acquisition namespaces; they are different recordings and versions, not controlled identical-input trials.

`recognition.event_report.reconstruct_and_package` starts the **broad** timer before `video_events` and initial StateEngine/profile construction. It includes event adaptation, history construction, `StateEngine.replay`, optional resolution inspection, engine/state export, receipt construction, command grouping, and writing three prediction/replay JSON files. `summary.replay_seconds` is sampled **before** summary writing, frame asset linking, HTML viewer generation and final seals. Hence 858.584 s must not be called isolated replay or exclusive StateEngine time. B24's adaptive multi-hit artifact records zero planned windows and zero completed attempts; it does not conceal an extra image-recognition pass.

The frozen function ordering is:

```python
began = time.monotonic()
events = video_events(rows, roster, paths.battle_id)
engine = StateEngine(initial_with_optional_roster_profile)
engine.history.append(...)  # one bulk history construction
engine.replay(snapshot_callback=progress)
# optional inspect_resolutions; zero windows for B24
replay = engine.to_dict()
# build receipts and command groupings
atomic_json(folder / 'video-only.json', prediction)
atomic_json(folder / 'replay.json', replay)
atomic_json(report / 'video-only.json', prediction)
summary['replay_seconds'] = time.monotonic() - began
# summary/assets/viewer/seals follow outside this timer
```

OCR and icon counts time model calls in `recognition.fast_video.CachedOCR.predict` and `CachedIcons.identify`. They exclude model construction and many adapter, crop, cache, gate and disk operations. Model calls are synchronous in the calling thread; FFmpeg runs concurrently. Summing model-call durations and the later broad timer gives a useful nonoverlapping accounting subtotal, but the remainder cannot be labelled decoder cost: it also includes initialization, other recognition, event assembly, serialization, output and startup/exit. Background decoder CPU overlaps model/other processing.

The accounting used in the tables is `external = broad + cumulative OCR + cumulative icons + residual`. It is an exact subtraction identity, not an invented function-level profile.

## Consistent B21–B24 measurements

<!-- Generated compact tables follow; detailed logs remain in the JSON. -->

| Measurement | B21 | B22 | B23 | B24 |
| --- | ---: | ---: | ---: | ---: |
| Video seconds | 703.210000 | 860.180000 | 787.280000 | 1052.820000 |
| External CLI seconds | 559.751187 | 850.076456 | 803.716960 | 1460.983723 |
| Internal pipeline seconds | 559.155573 | 849.307882 | 802.658021 | 1460.285742 |
| Outside internal timer seconds | 0.595615 | 0.768574 | 1.058939 | 0.697981 |
| PTR | 0.795994 | 0.988254 | 1.020878 | 1.387686 |
| Broad reconstruction seconds | 160.815247 | 387.361054 | 357.967342 | 858.583679 |
| OCR cumulative seconds | 212.847404 | 330.678575 | 319.898119 | 428.594328 |
| Icon cumulative seconds | 4.448823 | 4.767636 | 4.956419 | 28.639847 |
| Accounting residual seconds | 181.639712 | 127.269190 | 120.895080 | 145.165869 |
| Receipts | 1384 | 2212 | 2036 | 2780 |
| OCR calls | 4120 | 6333 | 5764 | 8504 |
| Mean OCR seconds/call | 0.051662 | 0.052215 | 0.055499 | 0.050399 |
| Icon calls | 12 | 12 | 12 | 84 |
| Broad seconds/receipt | 0.116196 | 0.175118 | 0.175819 | 0.308843 |
| Materialized 2 FPS frames | 1407 | 1721 | 1575 | 2106 |
| Inspected frames | 1385 | 1697 | 1566 | 2073 |
| Source decoded frames | 23380 | 33158 | 27260 | 43422 |

| Retained structure / static workload | B21 | B22 | B23 | B24 |
| --- | ---: | ---: | ---: | ---: |
| Initial compact state bytes | 9010 | 9010 | 9123 | 59059 |
| Final compact state bytes | 2167652 | 3474538 | 3085150 | 6722458 |
| Pokémon instances | 9 | 12 | 9 | 13 |
| Numeric HP observations | 921 | 1817 | 1553 | 2269 |
| Nonzero HP deltas | 48 | 45 | 68 | 38 |
| Active entry episodes | 9 | 12 | 9 | 18 |
| Episode bytes | 776166 | 1171540 | 1041059 | 2657993 |
| Identity ledger bytes | 45004 | 48309 | 44181 | 926752 |
| Return proofs | 0 | 0 | 0 | 5 |
| Ordering comparisons, one replay (static N²) | 1915456 | 4892944 | 4145296 | 7728400 |
| enrich trigger receipts | 1288 | 2078 | 1912 | 2579 |
| Prefix event references enumerated (static) | 897547 | 2300091 | 1952612 | 3626317 |
| Numeric-observation prefix visits (proxy) | 655161 | 1895457 | 1514790 | 2957911 |

## Increased workload versus increased event cost

At B23’s average broad cost per receipt, the extra 744 B24 receipts would add **130.809 s**. The other **369.807 s** of the broad increase reflects cost/mix/state differences relative to that accounting counterfactual. This is not a causal decomposition: preview, HUD, switches and history-bearing receipts have different costs. Receipt counts alone cannot explain the observed ratio.

A pure N² scaling model gives 1.864× for receipt counts; the measured broad ratio is 2.398×, another 1.286× above that model. Four different battles cannot establish an empirical complexity exponent. The code does establish repeated state traversals and prefix loops; the model illustrates their plausible amplification, not a fitted production law.

B24 has 2570 HUD observations versus 1897, 18 send-outs versus 9, 12 switches versus 2, 48 preview observations versus 6, but only 34 named move executions versus 31. Most new receipts are UI/retained-history work, not more damage calculations. The production `reconstruct_and_package` never invokes the later hidden-stat `ChronologicalTrace`, inverse damage or Speed inference; the Speed repairs and later diagnostic contexts cannot be charged to the original production CLI.

## Replay scaling: what the logs can and cannot establish

The original log emits `Video-only replay: 100/2780`, then each 100 receipts. Those lines contain **no execution timestamps**. Their line numbers and event counts are preserved in the JSON, with elapsed intervals explicitly null. There is no valid per-100-event timing curve, no measured before/after-1600 slope and no basis for assigning seconds from line spacing. No timing intervals have been manufactured.

File modification timestamps corroborate broad stage boundaries but are not monotonic function timers. Offsets from the saved external subprocess epoch are:

| Output mtime offset (s) | B21 | B22 | B23 | B24 |
| --- | ---: | ---: | ---: | ---: |
| Recognition aggregate | 397.463 | 460.635 | 443.236 | 600.127 |
| Prediction cache | 557.889 | 847.444 | 800.662 | 1457.717 |
| Viewer | 559.525 | 849.720 | 802.912 | 1460.585 |

Recognition progress has internal elapsed wall readings (last B24: 598.8 s at source 1051.0 s, 2070 inspections, 8501 OCR calls). The recognition aggregate appears at CLI offset 600.127 s; prediction output near 1457.717 s; viewer near 1460.585 s. The approximately 858-second gap agrees with the broad timer, but is not a measurement of `StateEngine.replay` alone.

The user’s earlier approximately “900 seconds / 1600 events” observation lacks a saved clock origin and exact timestamp. If 900 means total CLI elapsed, roughly 300 seconds would have elapsed after the broad stage began; if it means pure production replay elapsed, it exceeds the entire recorded broad timer. It may describe a later diagnostic replay. It cannot safely anchor a production interval.

Separate reviewed-context checkpoint runs are preserved, not substituted for production timings:

| Context stage | Status | Saved final checkpoint | Complete stage wall (s) |
| --- | --- | --- | ---: |
| `contexts:da213a54b8e86b2e` | complete | 2750 receipts / 1031.034 s | 1053.9198589324951 |
| `contexts:8a25d0dd9e02c2d9` | interrupted | 1050 receipts / 124.338 s | unknown |
| `contexts:0853143dab85ff88` | interrupted | 1400 receipts / 1313.192 s | unknown |
| `contexts:119376ea8122799a` | complete | 2750 receipts / 1025.209 s | 1048.2694070339203 |

Completed context stages took about 1048–1054 s; both have only the last retained checkpoint at 2750 receipts, followed by 23 s for the last 30 receipts **plus flush/fsync and final context hashing**. Their earlier overwritten checkpoint history is unavailable. Interrupted stages differ in implementation/input/overlap and end at different receipt counts, so they must not be spliced into a time series. They include decision projections and JSONL/fsync callback work absent from production; the especially slow interrupted overlapping run cannot establish original replay scaling.

## Relevant hot paths and retained histories

The frozen B23/B24 `replay`, `hash_state`, `_hp`, `BattleState.to_dict`, HP `enrich` and `action_resolutions` AST fingerprints match. `_transition` and identity handling differ: B24 adds unique-roster persistent returns, alias lookup, battle-start/entry facts, switch stage resets and expanded profile grounding. This rules out blaming a change to the identical hashing loop itself; it does not make B23/B24 whole programs equivalent. The snapshots and AST hashes are embedded in the measurement JSON.

The important frozen `tracking/state_engine.py::StateEngine.replay` fragment is:

```python
# Initial duplicate-order detection scans all active records for each record.
duplicate_keys = {tuple(r.ordering["key"]) for r in active
                  if sum(a.ordering == r.ordering for a in active) > 1}
for record in ordered:
    observe(self.state, event)
    trial = deepcopy(self.state)
    # apply admitted transition or record a deferred/rejected observation
    processed.append(record)
    if event.event_type in {"hud_observation", "hp_change", "effectiveness"}:
        enrich(self, processed)
    record.state_hash = hash_state(self.state)

def hash_state(state):
    return hashlib.sha256(json.dumps(
        state.to_dict(), sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode()).hexdigest()
```

Revelation-only move receipts take a separate early path that also hashes state. Initial ambiguous/retracted records may bypass the loop, so “per receipt” means processed ordered receipts, not every possible input record under all policies. These runs have comparable single ordered domains and no demonstrated confusion-driven repeat: saved static records contain zero confusion-context requests/bindings. An automatic second replay is possible in the implementation but is not supported as the explanation for this B24 run.

`tracking.battle_state.BattleState.to_dict` begins with `dataclasses.asdict(self)`: the hash includes recursive dataclass conversion, dictionary/list traversal, deep copies of leaf values, sorted JSON encoding, UTF-8 encoding and SHA-256. Calling the entire operation “SHA hashing” obscures most of its work. A trial deepcopy preserves shared-object memoization; `asdict`/JSON can expand repeated referenced evidence into separate representations. Compact JSON size is a structural metric, not RSS or an exact count of deepcopy work.

B24 final state is **6,722,458 compact bytes versus 3,085,150 (2.179×)**, with 18 entry episodes versus 9 and five persistent return proofs versus zero. `tracking.active_continuity.depart` stores `historical_hp=asdict(p.hp)`, status and executed moves inside each departure. B24 departures occupy 1,900,763 bytes versus B23’s 1,014,836. `tracking.identity_ledger.unique_roster_return` deep-copies the prior departure into a proof, appends another proof copy to `knowledge.identity_ledger.persistent_returns`, and `active_continuity.enter` retains continuity evidence in the episode. B24 continuity evidence occupies 705,822 bytes; its entire identity ledger is 926,752 bytes versus 44,181. The five return proofs occupy 705,828 bytes **within that ledger**—do not add that number again when summing state size. Source assertions remain evidence, but copying their expanded history at every subsequent receipt amplifies processing work.

Numeric HP observations grow from 1553 to 2269 (1.461×), despite nonzero deltas falling from 68 to 38. Most retained numeric observations are baselines/unchanged HUD endpoints, not fresh damage events. `_hp` and HUD paths preserve evidence repeatedly, and departure/return structures retain historical copies. Their correctness/provenance requirements must be preserved by any future storage change; this diagnosis does not authorize discarding observations.

`tracking.hp_causes.enrich(engine, records)` rebuilds an event list/index for the entire processed prefix, then scans retained numeric HP histories, resetting causal fields and checking endpoints/causes. B24 has 2579 trigger receipts versus 1912. The statically reconstructed one-pass prefix enumeration increases from 1,952,612 to 3,626,317 references (1.857×), and final-retained numeric prefix-visit proxy rises from 1,514,790 to 2,957,911 (1.953×). These are structural counts, **not measured production call/CPU counters**; final retained observations omit possible transient histories and full per-HP cause searches. Enrichment deserves investigation but cannot be ranked ahead of copy/hash on these proxies alone.

## Isolated frozen-state component measurements

`diagnose_b24_runtime.py` loads each battle’s saved `replay.json` and **its own frozen** `tracking`/`battle_events` packages in a separate process. Exact initial/final schema round trips and unchanged input hashes are required. It times initial and final state deepcopy, `to_dict`, JSON encoding, complete `hash_state`, and a terminal full-prefix HP enrichment on a fresh copied final state. One warmup precedes five samples; setup/loading/copy-to-prepare-enrichment is excluded. Python GC stays at default settings. Each operation atomically checkpoints its result; no replay occurs. `cProfile` separately records one copy+hash pair, so its instrumented times must not be substituted for the unprofiled samples.

The first `runtime-components-v1` experiment had highly variable wall samples (B23 final `to_dict` 2.47–5.57 s), while source verification was also running. It had no CPU timer and cannot establish why it varied. All results and exact script bytes are preserved. The final **v2** experiment adds process CPU timing and stable samples; table below reports median seconds with wall ranges. They are present-day component probes, not historical production benchmarks or cold runs.

| Operation / snapshot | B23 median wall [range] | B23 median CPU | B24 median wall [range] | B24 median CPU | CPU ratio |
| --- | ---: | ---: | ---: | ---: | ---: |
| initial_state:deepcopy | 0.000553 [0.000526, 0.000590] | 0.000549 | 0.001637 [0.001516, 0.001847] | 0.001621 | 2.953× |
| initial_state:hash_state | 0.000471 [0.000465, 0.000551] | 0.000470 | 0.003180 [0.003002, 0.003358] | 0.003163 | 6.730× |
| state:deepcopy | 0.086701 [0.065669, 0.091506] | 0.086190 | 0.182602 [0.139530, 0.183572] | 0.181331 | 2.104× |
| state:to_dict | 0.129630 [0.128363, 0.154589] | 0.128628 | 0.318945 [0.316594, 0.325587] | 0.317777 | 2.471× |
| state:json_dumps_sorted | 0.028293 [0.027893, 0.029458] | 0.028195 | 0.058041 [0.057381, 0.060013] | 0.057596 | 2.043× |
| state:hash_state | 0.160960 [0.159446, 0.182969] | 0.159632 | 0.379065 [0.340875, 0.384958] | 0.377481 | 2.365× |
| final_prefix:hp_enrich | 0.032625 [0.032047, 0.033429] | 0.032515 | 0.024717 [0.024640, 0.026428] | 0.024673 | 0.759× |

These measurements confirm the cost of the **specific terminal snapshot operations**. On B24, final `to_dict` consumes about 0.319 s wall and JSON encoding about 0.058 s, close to the combined hash path’s 0.379 s; `to_dict` and JSON are nested inside hashing, so these numbers must not be added to `hash_state` again. The instrumented profile identifies `dataclasses._asdict_inner`, its container generators and `copy.deepcopy` recursion as major cumulative functions. Profile cumulative rows overlap; the combined copy/hash top-level `deepcopy` row also includes deepcopy calls made from `asdict`.

The terminal HP enrichment probe is **faster on B24** (about 0.025 s CPU versus 0.033), despite larger prefix/history counts. B23 has more nonzero HP changes and therefore a different cause-search workload. This directly limits the claim that HP enrichment is the leading runtime regression. It may still accumulate substantially across prefixes; no historical function-total measurement exists.

Do not multiply final copy/hash times by 2780 or assume linear interpolation from initial to final: state histories grow discontinuously at returns/departures and transient object sharing is unknown. No exact prefix snapshots with wall timings survive from original production. No per-function fraction of the 858.584-second broad stage, memory peak, GC time, disk-write time or decoder CPU utilization has been measured.

## Output and disk-I/O hypotheses

B23 generated 3,637,411,108 logical bytes and B24 4,991,129,010, principally image assets. Deduplicating hardlinks by inode yields 1,875,359,242 versus 2,582,401,751 bytes; neither figure measures filesystem compression, clones, I/O bandwidth or write latency. The viewer asset stage follows the broad timer, while prediction/replay JSON writing partly lies inside it. Larger output and decoding 43,422 versus 27,260 source frames can contribute, but their exclusive CPU/wait time is not recoverable. Output size alone does not explain a 500-second broad-stage increase. No storage bottleneck is proven.

## Next optimization priorities and required evidence

1. **Measure receipt-level inclusive/exclusive spans around `StateEngine.replay`, its whole-state `deepcopy`, `hash_state`, `BattleState.to_dict` and HP `enrich`, with elapsed timestamps and state/history sizes.** Use only saved replay inputs in isolated namespaces. This is the first experiment needed for historical-like function attribution; do not time video recognition to answer it. Retain the existing hash/receipt/state checks as semantic equivalence criteria. The current terminal probes establish priority, not expected production speedup.
2. **Reduce repeated state traversal only after equivalence checks:** investigate `tracking.state_engine.hash_state` / `BattleState.to_dict` and the trial copy. Possible future designs include immutable evidence references, copy-on-write state, or cached canonical serialization with explicit invalidation. Preserve correction/retraction, deterministic receipt hashes, cross-battle isolation and evidence availability. No such change is implemented here.
3. **Review historical payload ownership in `active_continuity.depart`, `identity_ledger.unique_roster_return` and `active_continuity.enter`.** Stable references to immutable historical evidence may prevent repeated expanded departure/return copies. Measure retained bytes and object graphs across actual receipt prefixes before choosing a representation; compatibility and history APIs must be documented.
4. **Profile and consider incremental HP attribution in `hp_causes.enrich`**, keyed to changed endpoints/events rather than every HUD receipt. Preserve corrected/retracted causes and the baseline/endpoint semantics; the terminal benchmark does not support assuming this is the largest regression. Investigate unchanged HP observation representation separately from dropping evidence.
5. **Replace duplicate-order N² scanning only if its measured share warrants it**, preserving ambiguous-tie barriers and retractions. It is a clear complexity risk but lacks production CPU attribution. Event adaptation/receipt export, profile grounding and output writes should remain separately timed to avoid attributing all broad work to replay.

## Evidence paths and reproducible handoff

Original production runs:

| Battle | Run ID | Benchmark log directory |
| --- | --- | --- |
| B21 | `fresh-b21-context-v1` | `.cache/battles/sample_battle_21/fresh-benchmark/fresh-b21-context-v1` |
| B22 | `fresh-b22-ditto-20261030-v1` | `.cache/battles/sample_battle_22/fresh-benchmark/fresh-b22-ditto-20261030-v1` |
| B23 | `mega-b23-20261030-v1` | `.cache/battles/sample_battle_23/fresh-benchmark/mega-b23-20261030-v1` |
| B24 | `fresh-b24-20261101-v1` | `.cache/battles/sample_battle_24/fresh-benchmark/fresh-b24-20261101-v1` |

Each benchmark directory contains `execution.json`, `normal-pipeline-attempt-1.log` and separate `projection-stage.json`. Original source snapshots and manifest/checkpoint/observations/replay are under `.cache/battles/sample_battle_<N>/event-driven/<run>/`; final summary/viewer are under `reports/battles/sample_battle_<N>/event-driven/<run>/`. All 40 direct source-file hashes and exact command lines/hardware metadata are embedded in the JSON. Its filesystem timestamps preserve their units and epoch basis.

The final component manifests are `.cache/battles/sample_battle_23/diagnosis/runtime-components-v2/manifest.json` and the corresponding B24 path. Each directory preserves the exact instrument script; `measurements` has every wall/CPU sample, and `copy_hash_profile_top_cumulative` contains function/file/line/call/cumulative/self counters. Frozen source paths in these profiles are explicit. No component result is merged into the historical benchmark numbers.

```sh
# Read-only revalidation / reuse of completed component experiments:
.venv/bin/python scripts/diagnose_b24_runtime.py --battle 23
.venv/bin/python scripts/diagnose_b24_runtime.py --battle 24
.venv/bin/python scripts/report_b24_runtime_diagnosis.py
.venv/bin/python scripts/evaluate_b24.py --stage verify
git diff --check
```

The component runner reuses an identical complete experiment and rejects differing/incomplete identities. Use a new `--experiment` name for a justified new measurement, never overwrite v1/v2. There is no active expensive replay to resume. Performance diagnosis is complete within these measurement limits; function-level production attribution and optimization remain future work. No commit, push or milestone advancement occurred.
