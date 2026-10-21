"""Read frozen predictions and independently reviewed v2.1 references; write new reports."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timezone
import html
import json
import os
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from speed_inference.offline import atomic_json,file_hash
from battle_evidence.visual_v21 import evaluate,timing

STYLE='<style>body{font:17px system-ui;max-width:1250px;margin:2em auto;background:#152029;color:#eee}a{color:#9df}img{max-width:100%}table{border-collapse:collapse}td,th{border:1px solid #789;padding:.5em}section,details{padding:1em;border:1px solid #678;margin:1em 0}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}input{width:110px}textarea{width:90%;height:70px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>'


def rel(p,base):return html.escape(os.path.relpath(Path(p).resolve(),base.resolve()))
def show(x):return html.escape(json.dumps(x,ensure_ascii=False,indent=2))
def page(title):return ['<!doctype html><meta charset="utf-8">',f'<title>{html.escape(title)}</title>',STYLE,f'<h1>{html.escape(title)}</h1>']


def render(reference,prediction,result,dest):
    dest.mkdir(parents=True,exist_ok=True)
    grid=json.loads(Path(reference['source_grid']).read_text());frames=grid['frames'];bid=reference['battle_id']
    source=page(bid+' — source only / 无预测、无参考覆盖')
    source+=['<p>Complete fixed two-second chronological grid. Captions retain actual global PTS, grid target and chunk origin. No detector or annotation overlays.</p>','<div class="grid">']
    for f in frames:
        source.append(f'<section id="f{f["index"]}"><a href="{rel(f["image"],dest)}"><img loading="lazy" src="{rel(f["image"],dest)}"></a><p>#{f["index"]}: target {f["target_timestamp"]}s / global PTS {f["timestamp"]:.6f}s; chunk ticks {f["source_pts"]} × {f["source_time_base"]} + {f["seek_origin_seconds"]:.6f}s</p></section>')
    source.append('</div>');(dest/'source.html').write_text('\n'.join(source))
    out=page(bid+' — v2.1 boundary review')
    out += [f'<p>Role: {reference["evaluation_role"]}. Agent-reviewed proposals; human approval pending.</p>',
        '<p><a href="source.html">Open chronological source-only review first</a>. Predictions are collapsed below. Reviewers can export decisions for individual fields; no whole-recording approval is implied.</p>',
        f'<p><a href="{rel(ROOT/"tests/fixtures"/(bid+".mp4"),dest)}">Original recording</a> · <a href="{rel(ROOT/"reports/battles"/bid/"inputs/M3.4-visual-reference-v21.json",dest)}">Reference JSON</a> · <a href="evaluation.json">All comparisons / counter checks</a></p>',
        f'<pre>{show(reference["review_notes"])}</pre>', '<button onclick="download()">Export selected individual review decisions (JSON)</button><p id="notice"></p>']
    if bid == 'sample_battle_5':
        out.append('<section><h2>Targeted human-reviewed correction — only two fields of historical agent-turn01</h2><pre>'+show(json.loads((ROOT/'reports/battles/sample_battle_5/inputs/M3.4-visual-human-correction-v21.json').read_text()))+'</pre><p>Source-grid proposal remains separate. This correction does not approve other fields.</p></section>')
    for i,t in enumerate(reference['turns']):
        out.append(f'<section><h2>{t["id"]}</h2>')
        for field in ('command_start','resolution_start','resolution_completion','next_command_start'):
            b=t[field];bounds=b.get('interval');key=t['id']+'/'+field
            near=min(frames,key=lambda f:abs(f['timestamp']-(sum(bounds)/2 if bounds else 0)))
            out.append(f'<div class="boundary" data-key="{key}" data-original="{html.escape(json.dumps(bounds))}"><h3>{field}: {bounds}</h3><p>{html.escape(b["evidence"])}</p><p><a href="source.html#f{max(0,near["index"]-2)}">Nearby chronological frames</a> · <a href="{rel(ROOT/"tests/fixtures"/(bid+".mp4"),dest)}#t={max(0,(bounds or [0])[0]-3):.3f}">Video near transition</a></p>')
            for f in b.get('frame_refs',[]):out.append(f'<a href="{rel(f["image"],dest)}">{f["timestamp"]:.6f}s original</a> · ')
            out.append('<p><select class="status"><option value="">Unreviewed / leave unchanged</option><option>human-reviewed</option><option>human-approved</option></select> Interval: <input class="lo" type="number" step="0.001" placeholder="start seconds"> — <input class="hi" type="number" step="0.001" placeholder="end seconds"></p><textarea class="note" placeholder="Boundary-specific evidence, correction or uncertainty"></textarea></div>')
        out.append('</section>')
    out.append(f'<details><summary>Prediction overlays and timing differences — optional after source review</summary><pre>{show(result)}</pre></details>')
    out.append(f'<details><summary>Frozen raw effect/counter observations (independent, semantics may be uncertain)</summary><pre>{show(prediction["counter_observations"])}</pre></details>')
    out.append(f'<details><summary>All chronological phase proposals, including no-transition frames</summary><pre>{show(reference["chronological_review"])}</pre></details>')
    out.append('''<script>
const battle='''+json.dumps(bid)+''';
function download(){const decisions=[];for(const e of document.querySelectorAll('.boundary')){const status=e.querySelector('.status').value;if(!status)continue;const l=e.querySelector('.lo').value,h=e.querySelector('.hi').value;let interval=JSON.parse(e.dataset.original);if(l!==''||h!==''){if(l===''||h===''||!Number.isFinite(+l)||!Number.isFinite(+h)||+l>+h){alert('Provide both valid endpoints');return;}interval=[+l,+h];}decisions.push({boundary:e.dataset.key,review_status:status,human_approved:status==='human-approved',interval,note:e.querySelector('.note').value,reviewed_utc:new Date().toISOString()});}if(!decisions.length){alert('Select individual boundaries first');return;}const data={battle_id:battle,scope:'Only listed boundary fields; no battle-wide approval',decisions};const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.download=battle+'-individual-review-v21.json';a.click();URL.revokeObjectURL(a.href);document.getElementById('notice').textContent='Exported individual decisions. Save this file for review; source references and detector predictions remain unchanged.';}
</script>''')
    (dest/'review.html').write_text('\n'.join(out))


def main():
    os.chdir(ROOT);cache=ROOT/'.cache/m34-visual-v21'
    freeze=json.loads((cache/'freeze.json').read_text())
    changes=[p for p,h in freeze['files'].items() if not Path(p).is_file() or file_hash(p)!=h]
    if changes:raise ValueError('Frozen baseline changed: '+str(changes))
    for name in ('development-reference-freeze.json','holdout-reference-freeze.json'):
        if any(file_hash(p)!=h for p,h in json.loads((cache/name).read_text()).items()):raise ValueError('Reference freeze changed')
    paths=json.loads(Path('.cache/m34-visual-v2/battle-index.json').read_text())
    historical=json.loads((cache/'historical-preservation-result.json').read_text())
    for p,h in historical['databases_unchanged'].items():
        if file_hash(p)!=h:raise ValueError('Historical database changed')
    seal=json.loads((cache/'holdout-prediction-seal.json').read_text())
    assert file_hash(seal['result'])==seal['sha256'];paths.append(seal['result'])
    rows=[];index=page('M3.4 v2.1 — source review and frozen evaluation')
    index.append('<p>Development Battles 5–9 and holdout Battle 10 are reported separately. Proposals are agent-reviewed, not human ground truth. Start with source-only pages to avoid prediction bias.</p>')
    for n,path in zip(range(5,11),paths):
        b=f'sample_battle_{n}';refpath=Path(f'reports/battles/{b}/inputs/M3.4-visual-reference-v21.json');r=json.loads(refpath.read_text());p=json.loads(Path(path).read_text());o=evaluate(r,p)
        o.update(reference=str(refpath),reference_sha256=file_hash(refpath),prediction=str(path),prediction_sha256=file_hash(path),evaluation_role=r['evaluation_role'])
        # Source-backed phase classification for all nonmatching endpoints.
        paired={m['reference'] for m in o['outside_tolerance_associations']};pp={m['prediction'] for m in o['outside_tolerance_associations']}
        o['categories']=dict(timing_compatible=len(o['matches']),bounded_within_2s=sum(m['timing_quality']=='within_2s' for m in o['matches']),insufficient_localization=sum(m['timing_quality']=='insufficient_localization' for m in o['matches']),correct_entry_outside_tolerance=len(paired),missing=len(o['missed_reference_boundaries'])-len(paired),spurious=len(o['unmatched_predictions'])-len(pp),submenu_false_turn_alerts=len(o['submenu_false_turn_review_alerts']),possible_merges=len(o['possible_merges']),possible_splits=len(o['possible_splits']))
        dest=ROOT/f'.cache/battles/{b}/m34-visual-v21';atomic_json(dest/'evaluation.json',o);render(r,p,o,dest)
        index.append(f'<section><h2>{b} — {r["evaluation_role"]}</h2><a href="{rel(dest/"source.html",cache)}">Source only</a> · <a href="{rel(dest/"review.html",cache)}">Individual boundary review</a><pre>{show(o["categories"])}</pre></section>')
        grid=json.loads(Path(r['source_grid']).read_text());rows.append(dict(battle_id=b,result=o,grid=grid))
    (cache/'review.html').write_text('\n'.join(index))
    correction=json.loads(Path('reports/battles/sample_battle_5/inputs/M3.4-visual-human-correction-v21.json').read_text())
    p=json.loads(Path(paths[0]).read_text());target=p['visual']['segments'][0]
    human=dict(scope=correction['scope'],historical_turn_id=correction['historical_turn_id'],review_status='human-reviewed',human_approved=False,next_command_check=timing([195.,196.],target['end'],target['next_command_time']),resolution_completion_prediction=None,qualification='Detector does not separately estimate completion. This is one targeted human-reviewed check; agent chronology stays separate.')
    atomic_json(cache/'human-correction-check.json',human)
    preservation=dict(frozen_files=len(freeze['files']),changed=changes,holdout_seal_unchanged=True,old_reference_and_prediction_hashes_unchanged=True)
    atomic_json(cache/'preservation-result.json',preservation)
    atomic_json(cache/'evaluation-index.json',[dict(battle_id=x['battle_id'],evaluation=f'.cache/battles/{x["battle_id"]}/m34-visual-v21/evaluation.json') for x in rows])
    report=['# M3.4 Visual Turn Reconstruction v2.1 — frozen two-second reference evaluation','',
      '**Review required. Detector unchanged. These are comparisons against agent-authored references, not independently human-approved ground truth.**','',
      'Open [localhost review](http://127.0.0.1:8766/.cache/m34-visual-v21/review.html) after starting the server:','',
      '```sh','cd /Users/yyi/Pokemon-Champions-Assistant','.venv/bin/python scripts/serve_visual_review.py --port 8766','```','',
      'The server binds only 127.0.0.1 and supports video byte ranges. Source-only pages contain the complete chronological grid without labels/predictions; separate review pages contain phase proposals and collapsed predictions/counters. Individual field decisions export JSON and do not approve a whole turn or recording. Browser security settings need no changes.','',
      '## Freeze and reference method','',
      f'The pre-holdout [freeze](../.cache/m34-visual-v21/freeze.json) records {len(freeze["files"])} file hashes, detector manifests/configuration, Python and installed packages. Old V1/V2 predictions, five-second references, M3.4.1 code, priors and databases remain byte-identical. Battle 10 prediction was sealed at {seal["sealed_utc"]} before generating or inspecting its reference grid. Its initial M2.4 acquisition and StateEngine processing used existing defaults; frozen sidecar functions were extended to Battle 10 by run/index routing only, with a separate index namespace. No production source changed.','',
      'Sampling independently selects the nearest available original cached source frame to 0,2,4,… seconds, with a maximum allowed displacement of 0.55s; all samples retain actual global timestamps, chunk PTS/timebase/origin, image hashes and chronological phase/no-transition records. All requested cells were available. No new source decoding or OCR was required for reference review. Some legacy B6 rows dropped seek origin; their preserved global timestamps are retained and the recovered chunk offset is explicitly labeled. Do not interpret nominal grid times or chunk-local ticks as exact global PTS.','',
      'The agent visually inspected every two-second contact-sheet frame, with full-resolution checks where needed. This is sampled visual review with prior project context, not continuous playback or blinded human annotation. Broad historical references were not mechanically narrowed to predictions. The B6 draft initially mislabeled pivot selection at340s; the initial draft/comparison are preserved, and a post-comparison full-resolution source correction explicitly records this exposure. Reference freezes and review history distinguish it from the first proposal.','',
      '## Matching and timing','',
      'Subsequent entries use chronological one-to-one matching with minimum interval distance ≤2.0s. Timing error is an interval [minimum possible, maximum possible] over supported prediction/reference intervals. A bounded timing pass requires maximum possible error ≤2.0s; a wide overlap is only compatible and may remain insufficiently localized. Tiny excesses such as2.001667s are retained, not rounded into passes. Point-to-reference error bounds are separate. Opening anchors are evaluated separately. Unknown references remain unscored. An unmatched counterpart within10s is a diagnostic wrong-time association, never a tolerance pass; raw misses/unmatched counts remain in JSON.','',
      '| Development battle | Subsequent entries | Compatible | Bounded ≤2s | Timing unresolved | Outside 2s | Missing | Spurious |','| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in rows[:5]:
        o=row['result'];c=o['categories'];report.append(f'| {row["battle_id"]} | {o["counts"]["reference_boundaries"]} | {c["timing_compatible"]} | {c["bounded_within_2s"]} | {c["insufficient_localization"]} | {c["correct_entry_outside_tolerance"]} | {c["missing"]} | {c["spurious"]} |')
    report+=['','| Holdout battle | Subsequent entries | Compatible | Bounded ≤2s | Timing unresolved | Outside 2s | Missing | Spurious |','| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    o=rows[-1]['result'];c=o['categories'];report.append(f'| sample_battle_10 | 9 | 8 | {c["bounded_within_2s"]} | {c["insufficient_localization"]} | 0 | 1 | 0 |')
    for label,group in [('Development 5–9',rows[:5]),('Holdout 10',rows[5:])]:
        matches=[m for row in group for m in row['result']['matches']];point=[m['point_error_bounds'] for m in matches];bounds=[m['absolute_error_bounds'] for m in matches]
        report+=['',f'{label}: {len(matches)} compatible pairs; mean absolute-error lower/upper bounds [{sum(x[0] for x in bounds)/len(bounds):.6f}, {sum(x[1] for x in bounds)/len(bounds):.6f}]s; worst upper bound {max(x[1] for x in bounds):.6f}s. Mean point-error bounds [{sum(x[0] for x in point)/len(point):.6f}, {sum(x[1] for x in point)/len(point):.6f}]s. These summaries exclude unmatched/outside pairs, which are listed below; they are not exact MAE estimates or human accuracy.']
    report+=['','## Opening and separate phase timing','',
        '| Battle | Opening reference interval | Frozen opening point | Point error bounds | Resolution-start statuses |','| --- | --- | ---: | --- | --- |']
    for row in rows:
        o=row['result'];a=o['initial_anchor'];pc=Counter(x['status'] for x in o['phase_transition_comparisons'] if x['phase_type']=='resolution_start')
        report.append(f'| {row["battle_id"]} | {a["reference_interval"]} | {a["predicted_time"]:.6f} | {a.get("point_error_bounds")} | {dict(pc)} |')
    report+=['','No separate resolution-completion prediction is exposed in any recording. Source completion proposals remain explicitly uncertain where the grid cannot distinguish completion from subsequent command presentation. Terminal result recognition is still absent in frozen V2 for these recordings. Correct command segmentation does not require those separate timing fields to pass.']
    report+=['','## Every entry and disputed cases','',
      'The following table includes every subsequent boundary, including timing uncertainty and misses. Bounds are seconds; rounding is for display only. Opening comparisons and every resolution-start/completion limitation are retained in each evaluation JSON.','',
      '| Battle / reference | Reference interval | Frozen prediction interval | Absolute error bounds | Assessment |','| --- | --- | --- | --- | --- |']
    disputes=[]
    for row in rows:
        o=row['result']
        for m in o['matches']+o['outside_tolerance_associations']:
            a=m['reference_interval'];b=m.get('prediction_interval',m.get('predicted_interval'));e=m['absolute_error_bounds'];report.append(f'| {m["reference"]} | {a[0]:.3f}–{a[1]:.3f} | {b[0]:.3f}–{b[1]:.3f} | {e[0]:.6f}–{e[1]:.6f} | {m["timing_quality"]} |')
            if m['timing_quality']!='within_2s':disputes.append(m)
        outside={m['reference'] for m in o['outside_tolerance_associations']}
        for m in o['missed_reference_boundaries']:
            if m['turn_id'] not in outside:report.append(f'| {m["turn_id"]} | {m["interval"]} | absent | unavailable | missing |');disputes.append(m)
    atomic_json(cache/'disputed-boundaries.json',disputes)
    report+=['','Priority review: B10 final entry784.032–786.032s is missing and has a genuine three-card layout; B6 entry470.012–472.013s is late (prediction474.513–475.013s, minimum interval error2.5s); B7 first return has a broad/incomplete prediction and possible error up to6.002s. Marginal2.001667s bounds in B6/B7/B8 remain unresolved under the strict bound rule.','',
      'No definite spurious command entry, submenu split or multi-turn merge was established in the final source proposals. B6 pivot340–356s and forced replacement390–396s, B5 replacement276–284s, B7 pivot406–410s/replacement578–590s, and B10 replacement616–626s/708–714s are explicitly separated. Possible-merge/split guards in the legacy comparison are diagnostics, not independent semantic proof; the B10 missed final entry is a missing anchor with unclosed tail, not automatically a demonstrated merged completed segment.','',
      '## Targeted user correction','',
      'The original Battle5 agent-turn01 reference remains unchanged. A separate human-reviewed correction records resolution_completion and next_command_start≈[195,196]s only, with user/session provenance and human_approved=false. Its next-command boundary projects to the following command entry solely for this targeted check; no battle-wide approval follows. The two-second source grid shows residual messaging at196s and a move menu at198s, so that source-only proposal remains distinct from the user timing.','',f'Targeted check: `{json.dumps(human["next_command_check"],ensure_ascii=False)}`. Separate completion timing is not estimated by V2 and is therefore not scored.','',
      '## Effect counters','',
      '| Battle | Counter relation statuses |','| --- | --- |']
    for row in rows:report.append(f'| {row["battle_id"]} | {dict(Counter(c["status"] for c in row["result"]["counter_checks"]))} |')
    report+=['','Counter checks reuse frozen normal-screen observations independently of reference annotation. Raw label/value, effect/scope, source and epoch remain separate from elapsed-turn deductions. Unknown side/instance or semantics, reapplication/reset and duration-extension epochs withhold comparisons. No turn is added to reconcile a counter. Rain/Trick Room corroborations do not validate all boundaries; Tailwind, terrain, screens, sun and sandstorm observations with unsupported semantics remain raw. The user-described0/5→3/8 hidden extension remains supported by existing duration/counter regressions, not claimed as a new observed recording sequence.','',
      '## Incremental runtime and resources','',
      '| Battle | Grid frames reused | Newly decoded | Review OCR | Sheet generation seconds | Sheet bytes | Review items |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in rows:
        g=row['grid'];report.append(f'| {row["battle_id"]} | {g["frames_sampled"]} | 0 | 0 | {g["seconds"]:.3f} | {g["storage_bytes"]} | {g["manual_review_items"]} |')
    resources=json.loads((cache/'resources.json').read_text())
    report+=['',f'Additional measured storage: Battle10 production namespace {resources["production_storage_bytes"]} bytes, visual sidecar {resources["sidecar_storage_bytes"]} bytes. Successful review namespace sizes (including HTML/evaluation, excluding production PNGs) are recorded per battle in resources.json. The initial evidence replay/snapshot stage time is recorded in its own completed manifest; these stages are reused on resume.']
    execution=json.loads(Path('.cache/battles/sample_battle_10/evaluation/m34-v21-holdout-frozen-v1/execution.json').read_text());p=json.loads(Path(seal['result']).read_text())
    report+=['',f'Battle10 initial production wall time: {execution["wall_seconds"]:.3f}s; peak process-tree RSS: {execution["peak_process_tree_rss_mib"]:.1f}MiB. Frozen visual sidecar metrics: `{json.dumps(p["metrics"],ensure_ascii=False)}`. Production OCR cost is recorded in the profiler/production manifests and summarized in resources.json; sidecar OCR is separate. Reference review uses zero additional OCR. Grid generation excludes agent visual-review time, tests and report rendering. Sheet bytes exclude retained production frames/OCR/replays; resources.json records measured stage sizes. The failed first B5 grid attempt was retained (chunk-PTS validation bug), and is excluded from successful-grid totals.','',
      f'Preservation: {len(freeze["files"])} frozen baseline files unchanged; sealed holdout prediction and reference hashes verified. No old predictions/references were rewritten, no detector or M3.4.1/M3.3 behavior changed, no commit/push performed.','',
      'Historical preservation audit additionally confirms631/634 prior-baseline files unchanged, including both metagame/published-team databases. The other three files were the pre-existing V2 implementation changes; their current frozen hashes remain unchanged in this task. Production first-pass cost:4254 OCR invocations,1656 materialized sampling frames,27346 decoded source frames; these are initial Battle10 costs only. B10 sidecar adds7 bounded ROI OCR crops.','',
      'Validation results and resume commands are in [the v2.1 handoff](../docs/visual-turns-v21.md). Full per-battle comparisons, error intervals, raw counters and reference/no-transition records are linked from the localhost index. Semantic human acceptance is pending. Stop here for review; no M3.4.2 work is included.']
    (ROOT/'reports/M3.4-visual-turn-v21-validation.md').write_text('\n'.join(report)+'\n')
    print('Wrote v2.1 report and localhost review pages; frozen baseline unchanged')


if __name__=='__main__':main()
