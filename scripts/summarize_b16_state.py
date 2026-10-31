"""Publish the measured B16 benchmark with separate event and state denominators."""
import json,re,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.benchmark_b16_state import OUT,LIVE,REPORT,OWNER,read,verify_seal,digest,atomic_json


def resolve_observations():
 """Reference-only duplicate/fragment inventory, reproducible from saved pixels/OCR."""
 from scripts.benchmark_b16_state import ANNOTATIONS
 raw=read(OUT/'log-extraction.json');labels=read(ANNOTATIONS);entries=labels['curated_entries'];rows=[]
 def compact(text):return re.sub(r'[\s！!。.，,]','',text)
 for view in raw['views']:
  for r in view['observations']:
   possible=[e['index'] for e in entries if e['turn']==view['turn'] and compact(e['raw_text'])==compact(r['raw_text'])]
   rows.append(dict(observation_id=r['observation_id'],source_id=view['source_id'],turn=view['turn'],source_image=view['image'],raw_text=r['raw_text'],partial=r['partial'],
    status='supports_unique_reference_row' if len(possible)==1 else 'ambiguous_repeated_wording' if len(possible)>1 else 'unresolved_fragment_or_ocr_variant',reference_indices=possible))
 summary=dict(raw_views=len(raw['views']),raw_row_observations=len(rows),counts=dict(Counter(r['status'] for r in rows)),
  auto_unique_rows=labels['automatic_unique_rows'],manual_recovered_rows=labels['manual_recovered_rows'],curated_unique_rows=len(entries),
  reference_rows_with_multiple_exact_views=sum(sum(e['index'] in r['reference_indices'] for r in rows)>1 for e in entries),
  duplicate_observations_beyond_first=sum(max(0,sum(e['index'] in r['reference_indices'] for r in rows)-1) for e in entries),
  limitations='Unresolved raw fragments retained, not extra evaluable events; readable distinct rows do not establish whole-match completeness.')
 atomic_json(OUT/'observation-resolution.json',dict(identity=dict(extraction_sha256=digest(OUT/'log-extraction.json'),annotations_sha256=digest(ANNOTATIONS),version='reference-observation-resolution-v1'),summary=summary,observations=rows))


def main():
 verify_seal(LIVE)
 ref=read(OUT/'reference-facts.json');facts={f['fact_id']:f for f in ref['facts']}
 results=read(OUT/'event-comparisons.json');states=read(OUT/'state-comparisons.json');metrics=read(OUT/'metrics.json')
 replay=read(LIVE/'replay.json');histories={h['event']['event_id']:h for h in replay['history']}
 categories=defaultdict(Counter)
 for r in results:
  f=facts[r['fact_id']];correct=r['status']=='correct_applied'
  if r['status']=='recognized_not_applied':
   h=histories[r['live_event_id']];e=h['bindings'].get('resolved_event') or h['event']
   actor=e.get('actor') or e.get('target') or {}
   correct=(not f.get('side') or f['side']==e['side']) and (not f.get('species_id') or f['species_id']==actor.get('species_id'))
  r['event_fact_correct']=bool(correct)
  # An event-fact score can confirm a correctly structured announcement without
  # claiming that any resulting authoritative state was applied.
  categories[f['category']]['correct']+=bool(correct);categories[f['category']]['evaluable']+=1
 total=sum(v['correct'] for v in categories.values())
 metrics['event_fact_reconstruction']=dict(overall=dict(correct=total,evaluable=len(results),rate=total/len(results)),categories={k:dict(v) for k,v in categories.items()},
  definition='Complete expected event fields reproduced; includes recognized-but-not-applied only with matching known side/actor/target. Authoritative state application scored separately.')
 metrics['applied_event_facts']=metrics['event_facts']
 metrics['event_facts']=metrics['event_fact_reconstruction']
 metrics['normal_pipeline_performance']=read(OWNER.cache('evaluation/b16-semantic-state-20261027-v1/normal-process.json'))
 resolve_observations();metrics['reference_coverage']=read(OUT/'observation-resolution.json')['summary'];metrics['reference_source_classes']=ref['source_classes']
 metrics['state_fact_definition']='Transition checkpoint fields read from actual StateEngine snapshots; no unknown/absent field is credited. HP endpoints and their observed difference share supporting evidence, so fields are not independent samples.'
 atomic_json(OUT/'published-metrics.json',metrics);atomic_json(OUT/'event-fact-scores.json',results)
 for n in ['published-metrics.json','event-fact-scores.json','observation-resolution.json']:
  atomic_json(REPORT/n,read(OUT/n))
 # Machine-readable lists preserve source timestamps, instance bindings, reference
 # pixels and reasons. The concise report links those local artifacts.
 m=read(LIVE/'manifest.json');p=metrics['normal_pipeline_performance'];a=metrics['event_fact_reconstruction']['overall'];b=metrics['state_facts']['overall'];ap=metrics['applied_event_facts']['overall']
 lines=['# B16 semantic parsing and state reconstruction — development/regression',
  '', '2026-10-27. Phases 1–5 completed. No commit/push. B16 already guided development; this is not a held-out accuracy result.',
  '', '## Architecture and changes', '',
  'The existing BattleState remains authoritative. Raw OCR and evidence remain separate from normalized semantics. MessageOccurrences → EventParser → prefix identity/evidence fusion → StateEngine policy and atomic transitions → receipts/state snapshots. Fact distinguishes observed, derived, unknown and conflicting values. Missing side/instance/slot evidence still defers application.',
  '', 'Literal parsing now supports continued sleep/wake, sun/sand announcements, opponent Tailwind, Wide Guard side activation and bound per-action protection/absorption outcomes. Side conditions record onset event and known turn; durations remain unknown without evidence. Generic Mega completion records the transformation with X/Y form unknown. The canonical stone reaction permits contextual 丫→Y normalization while preserving raw text. Low-confidence semantic candidates remain auditable. HP announcements do not create an amount or attacker/move cause; no move cause is inferred from adjacency.',
  '', 'Modified production modules: `battle_events/parser.py`, new `battle_events/message_patterns.py`, `recognition/message_occurrences.py`, `tracking/state_engine.py`. New end-to-end tests: `tests/test_semantic_state.py`; evaluation tests: `tests/test_b16_state_benchmark.py`. The synthetic banner in `tests/test_scrolling_semantics.py` now supplies banner provenance rather than contradictory live-message provenance.',
  '', 'Example: “从对手身后吹起了顺风！” → side_condition_change(opponent, tailwind, start) → opponent.conditions.tailwind.active=true, initiated_by points to that event, duration unknown. A separate move_execution records the user using Tailwind; neither record invents a target or a four-turn timer.',
  '', '## Cleanup and normal production performance', '',
  'Exact inventory, deletion result and historical baseline are retained in `docs/b16-semantic-state/`. Deleted 11,733 verified B16-generated files (3,138,331,700 logical bytes); original 1,413,192,982-byte video SHA256 unchanged. No shared assets, repository sources/tests, unrelated battles or user inputs were deleted.',
  '', '| Metric | Measured value |', '|---|---:|',
  f"| Original video | {p['video_seconds']:.2f} s |",
  f"| Normal CLI wall, excluding reference/evaluation | {p['normal_cli_wall_seconds']:.3f} s |",
  f"| Normal pipeline PTR | **{p['PTR']:.4f}** |",
  f"| Internal pipeline wall | {p['internal_seconds']:.3f} s |",
  f"| Final replay/export stage | {m['results']['replay_seconds']:.3f} s |",
  f"| Source-decoded frames | {m['decoder']['source_decoded_frames']} |",
  f"| Sampling | 2 FPS; {m['counts']['frames_materialized_at_2fps']} materialized/monitored frames |",
  f"| Detailed inspections | {m['counts']['frames_sampled']} (1026 at 2 FPS; 250 at 1 FPS) |",
  f"| OCR model invocations | {m['counts']['ocr_invocations_performed']} |",
  f"| Icon model invocations | {m['counts']['icon_invocations_performed']} |",
  f"| Candidate events / deferred | {m['results']['source_event_candidates']} / {m['results']['receipt_statuses'].get('deferred',0)} |",
  '', 'Cold run `b16-semantic-state-20261027-v1`: full video, lightweight identity, PP-OCRv6_medium_rec ONNX CPU revision `50c7eacafc52fa7bcf4194e8cd08e46f8558504b`; no imported recognition/frame/state cache, manual team/state/identity injection or retrospective log input. Same-run exact crop reuse (1 hit) is not an imported cache. Default sampling is 2 FPS, with separate adaptive inspection and OCR schedules.',
  '', 'Old internal PTR≈2.3651 (1782.653s); old external CLI PTR≈2.3672 (1784.249s). New double-faint scheduling avoided all 20 ordinary prefix replays. Semantic code also changed, and the old run enabled call profiling while this run did not. macOS arm64, 8 logical CPUs; no controlled thermal/background-load or repeated-trial comparison. No controlled speedup multiplier is claimed. Final replay remains expensive.',
  '', '## Independent reference coverage', '',
  'After live sealing, a separate original-video 2-FPS scan found 51 log views / 303 row observations. Automatic assembly produced 90 rows and 11 overlap issues. Agent source-pixel review recovered another 28 readable rows at scroll boundaries, for **118 distinct chronological log records**. This includes records omitted from the previous 89-row audit, so denominators differ.',
  '', 'The reference uses actual turn headings, row order, boundary anchors and scroll positions; viewing timestamps are never action timestamps. All original source/event/observation IDs survive. 280 raw observations map exactly to curated rows, including 162 duplicate observations beyond the first; 104 rows have multiple exact views. The remaining 23 raw fragments/OCR variants remain unresolved and unscored as extra events. No unique readable reference row was discarded by a confidence threshold. This does not establish whole-match log completeness.',
  '', 'Reference semantics were independently annotated from pixels without calling EventParser or reading live predictions. Canonical identity resolution reuses KnowledgeBase only. Shared ONNX OCR/geometry still allow correlated errors; agent pixel review is not independent human ground truth. The reference was sealed before comparison.',
  '', f"The 118 log records yield 121 event facts; 3 separately decoded HUD-zero observations yield **124 evaluable event facts** and **191 supported state checkpoint fields**. Sources: Battle Log=121 event facts; HUD=3; facts requiring both=0. HUD navigation used prior audit times, with fresh original-pixel verification; no new live prediction was used to supply reference values.",
  '', 'Move targets, attribution of numeric damage to a move/attacker, absolute opponent HP, exact stage values/baselines, Mega X/Y identity, weather termination, Trick Room and terrain are not independently evaluable here. They receive no success credit. Tailwind activation and termination are both represented. Numeric HP includes own absolute values and opponent displayed percentages; percentage differences are percentage points, not absolute HP.',
  '', '## Event facts and actual state fields', '',
  f"**A. Event-fact reconstruction: {a['correct']}/{a['evaluable']} = {a['rate']:.2%}.** This includes complete recognized announcements that were not applied to authoritative state; those remain explicitly labeled.",
  f"**B. Key-state reproduction: {b['correct']}/{b['evaluable']} = {b['rate']:.2%}.** Micro-averaged field counts, not an average of category percentages.",
  '', f"Applied event facts: {ap['correct']}/{ap['evaluable']}; event comparison statuses: {json.dumps(ap['breakdown'],ensure_ascii=False)}. State comparison statuses: {json.dumps(b['breakdown'],ensure_ascii=False)}. No incorrect actor/target/value was established among aligned facts; that is not a whole-match false-positive claim. Unverifiable requested fields stay outside these supported denominators.",
  '', '| Category | Event facts correct / evaluable | Applied event facts | State fields correct / evaluable |', '|---|---:|---:|---:|']
 names={'move_execution':'Move execution','damage':'Numeric damage/HP loss','healing':'Numeric healing','ability_activation':'Ability activation','item_activation':'Item activation','weather':'Weather','tailwind':'Tailwind','status':'Status/recovery','stat_stages':'Stat change direction (exact stage unknown)','switching':'Switching/fainting','mega_evolution':'Mega completion (X/Y unknown)','protective_effects':'Protective effects','other_effects':'Other notices/effectiveness/absorption','qualitative_damage':'Explicit burn-damage notices (amount unknown)','hp_observation':'Independent HUD zero endpoints'}
 for k,v in metrics['event_fact_reconstruction']['categories'].items():
  state=metrics['state_facts']['categories'].get(k,dict(correct=0,evaluable=0));applied=metrics['applied_event_facts']['categories'][k]
  lines.append(f"| {names.get(k,k)} | {v['correct']}/{v['evaluable']} | {applied['correct']}/{applied['evaluable']} | {state['correct']}/{state['evaluable']} |")
 lines += ['| Move target / Trick Room / terrain | Not evaluable | — | Not evaluable |',
  '', 'Comparison uses chronological semantic/identity matching and reference entry episodes. Same-frame capture ties do not inherit an action order from lexicographic event IDs. No text-equality-only matching or log viewing timestamps are used. Numeric HP pairs require two applied endpoints in the same live instance within the supported chronological action window; no attacker or move is attributed. A supported endpoint can score its state field even when the full pair is missing.',
  '', 'State checkpoints come from a read-only replay using the existing StateEngine. Every per-event state hash, application status/reason and final state matched the sealed live output. Evaluation creates no replacement authoritative state. HP before/after/difference fields share evidence and are not independent statistical samples. Zero mismatches in deterministic replay are not recognition accuracy.',
  '', '## Remaining failures', '']
 failures=[r for r in results if r['status']!='correct_applied']
 grouped=defaultdict(list)
 for r in failures:grouped[(r['category'],r['status'])].append(r)
 for (category,status),rows in grouped.items():
  examples=[]
  for r in rows[:2]:
   f=facts[r['fact_id']]
   label=f.get('effect') or f.get('ability') or f.get('item') or f.get('weather') or (f"{f.get('before')}→{f.get('after')}" if 'before' in f else 'burn residual; amount unknown' if f['category']=='qualitative_damage' else 'HUD=0')
   examples.append(f"`{r['fact_id']}` ({f.get('side')}, species {f.get('species_id','field')}, {label})")
  lines.append(f"- **{names.get(category,category)} / {status}: {len(rows)}**. Examples: "+'; '.join(examples)+'. '+rows[0]['reason']+'.')
 lines += ['', 'The failures include activation-banner acquisition, at least one sunlight announcement not emitted, missing zero/baseline HP reads, unsupported burn-residual notices, and effectiveness/reaction records that remain observations without corresponding scoped state. No rules were tuned using this final comparison and relabeled as held-out results.',
  '', '## Validation and artifacts', '',
  'Pre-run relevant tests: 147 passed, 1 deselected. First portable sweep: 2591 passed, 1 synthetic-provenance fixture failure, 73 deselected; corrected the fixture and 56 related tests passed. Final portable sweep: 2592 passed, 73 deselected (302.27s); additional evaluator tie-order tests: 5 passed. Counts overlap. One environment ccache warning. No optional present artifact failures were suppressed; local_artifacts were explicitly excluded.',
  '', 'Machine-readable artifacts: [reference facts](reference-facts.json), [event-fact scores](event-fact-scores.json), [state comparisons](state-comparisons.json), [published metrics](published-metrics.json), [raw observation resolution](observation-resolution.json). Detailed snapshots, source/config fingerprints, stage manifests, timestamps, seals and logs remain in the matching `.cache/battles/sample_battle_16/` namespace. Prior evaluator output is retained under `state-benchmark/evaluation-revisions/v1/` with its correction reason.',
  '', 'Reproduce/resume only incomplete stages using `docs/b16-semantic-state/progress.md`; do not rerun the cold decoder or delete successful stages. Remaining semantic gaps above are reported, not silently patched after evaluation.',
  '', '## 两条中文简历指标', '',
  f"- 使用 PP-OCRv6 ONNX 与事件驱动轻量管线，对 753.74 秒完整录像执行冷启动解析，正常处理耗时 {p['normal_cli_wall_seconds']:.3f} 秒，实测 PTR={p['PTR']:.4f}（不含独立日志提取与评估）。",
  f"- 在 B16 开发回归评估中，以 118 条源像素审阅日志及 3 个独立 HUD 点建立参考，复现 {a['correct']}/{a['evaluable']} 个事件事实和 {b['correct']}/{b['evaluable']} 个关键状态字段（{b['rate']:.2%}），分别报告已应用、仅识别与缺失；非独立人工标注准确率。", '']
 REPORT.mkdir(parents=True,exist_ok=True);(REPORT/'report.md').write_text('\n'.join(lines))
 atomic_json(OUT/'publication-manifest.json',dict(status='complete',source_metrics_sha256=digest(OUT/'metrics.json'),script_sha256=digest(Path(__file__)),
  reference_sha256=digest(OUT/'reference-facts.json'),live_seal=read(LIVE/'video-only-seal.json'),outputs={n:digest(REPORT/n) for n in ['report.md','published-metrics.json','event-fact-scores.json']}))
 print(json.dumps(dict(event_facts=a,applied_event_facts=ap,state_facts=b,normal_PTR=p['PTR']),indent=2))
if __name__=='__main__':main()
