"""Interval matching and human review artifact; never manufactures references."""
from collections import Counter
from functools import lru_cache
from pathlib import Path
import html
import json
import os
from copy import deepcopy
from battle_artifacts import BattleArtifacts
from speed_inference.offline import atomic_json,file_hash

TOLERANCE=1.6


def gap(a,b):return max(0,a[0]-b[1],b[0]-a[1])


def compare(reference,prediction,*,tolerance=TOLERANCE):
    if reference['battle_id']!=prediction['battle_id']:raise ValueError('Cross-battle comparison')
    if tolerance<0:raise ValueError('Negative matching tolerance')
    turns=reference['turns']
    refs=[dict(turn_id=t['id'],**t['command_start'],hud=t.get('hud_layout',{}).get('count')) for t in turns[1:]]
    definite=[r for r in refs if r.get('interval') is not None and r.get('confidence')!='uncertain' and r.get('disposition') not in ('uncertain','unobservable')]
    uncertain=[r for r in refs if r not in definite]
    preds=prediction['visual']['segments']
    # Order-preserving one-to-one maximum matching; a wide prediction interval
    # can match at most one reference and remains explicitly merge-qualified.
    @lru_cache(None)
    def solve(i,j):
        if i==len(definite) or j==len(preds):return (0,0.,())
        options=[solve(i+1,j),solve(i,j+1)]
        a=definite[i]['interval'];b=preds[j]['end']
        if gap(a,b)<=tolerance:
            n,c,pairs=solve(i+1,j+1)
            cost=gap(a,b)+abs(sum(a)/2-preds[j]['next_command_time'])*.01+(b[1]-b[0])*.001
            options.append((n+1,c-cost,((i,j),)+pairs))
        return max(options,key=lambda x:(x[0],x[1]))
    _,_,pairs=solve(0,0);matched_refs={i for i,j in pairs};matched_preds={j for i,j in pairs}
    matches=[]
    for i,j in pairs:
        r=definite[i];p=preds[j];point=p['next_command_time']
        matches.append(dict(reference=r['turn_id'],prediction=p['id'],prediction_status=p['status'],reference_interval=r['interval'],
            predicted_interval=p['end'],interval_gap=gap(r['interval'],p['end']),interval_overlap=gap(r['interval'],p['end'])==0,
            point_error_to_reference_interval=gap(r['interval'],[point,point]),
            prediction_interval_width=p['end'][1]-p['end'][0],reference_HUD_count=r['hud'],reference_status=reference['review_status']))
    uncertain_predictions=[];unmatched=[]
    for j,p in enumerate(preds):
        if j in matched_preds:continue
        row=dict(id=p['id'],time=p['next_command_time'],interval=p['end'],status=p['status'])
        if any(r.get('interval') and gap(r['interval'],p['end'])<=tolerance for r in uncertain):uncertain_predictions.append(row)
        else:unmatched.append(row)
    misses=[r for i,r in enumerate(definite) if i not in matched_refs]
    merges=[];splits=[]
    for p in preds:
        crossed=[r['turn_id'] for r in definite if p['command_start_time']<r['interval'][0] and r['interval'][1]<=p['next_command_time']+tolerance]
        if len(crossed)>1:merges.append(dict(prediction=p['id'],reference_returns=crossed,qualification='possible merged turns; source review required'))
    for r in definite:
        candidates=[p['id'] for p in preds if gap(r['interval'],p['end'])<=tolerance]
        if len(candidates)>1:splits.append(dict(reference=r['turn_id'],predictions=candidates,qualification='possible split or overly wide interval'))
    submenu_alerts=[]
    for p in unmatched:
        for s in reference.get('intervals',[]):
            if s['kind']=='command_submenu' and s.get('confidence')!='uncertain' and gap(s['interval'],[p['time'],p['time']])<=tolerance:
                submenu_alerts.append(dict(prediction=p['id'],time=p['time'],reviewed_submenu=s['interval'],qualification='unmatched return inside/near reviewed submenu; possible false new-turn or delayed anchor'))
    first=preds[0]['command_start_time'] if preds else None
    initial=turns[0]['command_start']['interval'] if turns else None
    approved=(reference.get('review_status')=='human-verified' and reference.get('human_approved') is True
        and all(t.get('human_approved') is True and t.get('command_start',{}).get('human_approved') is True for t in turns))
    metric=dict(precision=None,recall=None,reason='Agent-reviewed proposals are not independently human-verified ground truth')
    if approved:
        metric=dict(precision=len(matches)/(len(matches)+len(unmatched)) if matches or unmatched else None,
            recall=len(matches)/(len(matches)+len(misses)) if matches or misses else None,reason='Human-approved reference subset')
    phase_transitions=[]
    history=prediction['visual'].get('phase_history',[])
    for turn_index,turn in enumerate(turns):
        r=turn['resolution_start'];entry=dict(turn_id=turn['id'],phase_type='resolution_start',reference_interval=r.get('interval'))
        source=None
        # A matched return closes the preceding reference command's resolution.
        for i,j in pairs:
            if definite[i]['turn_id']==(turns[turn_index+1]['id'] if turn_index+1<len(turns) else None):source=preds[j];break
        actions=(source or {}).get('actions',[])
        tail=prediction['visual'].get('incomplete_tail') or {}
        if source is None and tail and gap(turn['command_start']['interval'],[tail['first_time'],tail['first_time']])<=tolerance:
            actions=prediction['visual'].get('unclosed_resolution_actions',[])
        timestamps=[a['timestamp'] for a in actions if a.get('timestamp') is not None]
        if r.get('interval') is None or r.get('confidence')=='uncertain':entry['status']='uncertain_reference_excluded'
        elif timestamps:
            time=min(timestamps);earlier=[h['timestamp'] for h in history if h['timestamp']<time]
            bounds=[max(earlier) if earlier else time,time]
            entry.update(predicted_interval=bounds,interval_gap=gap(r['interval'],bounds),
                status='interval_match' if gap(r['interval'],bounds)<=tolerance else 'resolution_start_late_or_missed')
        else:entry['status']='no_resolution_start_prediction'
        phase_transitions.append(entry)
        phase_transitions.append(dict(turn_id=turn['id'],phase_type='resolution_completion',reference_interval=turn.get('resolution_completion',{}).get('interval'),
            status='not_estimated_separately' if turn.get('resolution_completion',{}).get('interval') else 'uncertain_reference_excluded'))
    phase_types=dict(normal_command=dict(reference=len(definite),matched=len(matches)),
        command_submenu=dict(reviewed_intervals=sum(s['kind']=='command_submenu' for s in reference.get('intervals',[])),false_turn_review_alerts=len(submenu_alerts)),
        replacement_or_pivot=dict(uncertain_reference_intervals=sum(s['kind']=='replacement_or_pivot_selection' for s in reference.get('intervals',[])),
            qualification='uncertain references excluded from definite error metrics'),
        terminal_result=dict(reference_interval=reference.get('termination',{}).get('interval'),
            automatic_terminal_observed=prediction['visual'].get('terminal_observed',False),qualification='Human/agent result-frame review is separate from automatic terminal recognition'))
    return dict(battle_id=reference['battle_id'],reference_status=reference['review_status'],human_approved=approved,
        tolerance_seconds=tolerance,tolerance_definition='maximum gap between reference and prediction intervals; one-to-one chronological matching',
        matches=matches,unmatched_predictions=unmatched,missed_reference_boundaries=misses,
        uncertain_references=uncertain,uncertain_predictions=uncertain_predictions,
        possible_merges=merges,possible_splits=splits,submenu_false_turn_review_alerts=submenu_alerts,
        phase_type_summary=phase_types,phase_transition_comparisons=phase_transitions,
        counts=dict(reference_boundaries=len(definite),matched=len(matches),unmatched_predictions=len(unmatched),missed=len(misses),
            matched_confirmed=sum(m['prediction_status']=='confirmed' for m in matches),matched_uncertain=sum(m['prediction_status']!='confirmed' for m in matches)),
        by_reference_HUD_count={str(k):sum(m['reference_HUD_count']==k for m in matches) for k in sorted({r['hud'] for r in definite},key=str)},
        reduced_combatant_reference_coverage=sum(r['hud'] is not None and r['hud']<4 for r in definite),
        initial_anchor=dict(reference_interval=initial,predicted_time=first,error_to_interval=gap(initial,[first,first]) if initial and first is not None else None,
            qualification='Opening anchor evaluated separately from subsequent new-turn boundaries'),accuracy_metrics=metric)


def counter_checks(reference,prediction):
    groups={}
    for o in prediction['counter_observations']:
        if o.get('temporal_confirmation'):groups.setdefault((o['scope'],o['effect']),[]).append(o)
    ledger=prediction['reconstruction']['ledger'];checks=[]
    for a,b in zip(reference['turns'],reference['turns'][1:]):
        for (scope,effect),observations in sorted(groups.items()):
            selected=[]
            for turn in (a,b):
                lo=turn['command_start']['interval'][0];res=turn['resolution_start'].get('interval')
                hi=res[0] if res else reference['termination']['interval'][0]
                possible=[o for o in observations if lo<=o['timestamp']<hi]
                selected.append(possible[0] if possible else None)
            x,y=selected
            if not x or not y:continue
            row=dict(before_turn=a['id'],after_turn=b['id'],effect=effect,scope=scope,
                before_counter=x['id'],after_counter=y['id'],raw_before=x['raw_display'],raw_after=y['raw_display'])
            reset=any(e.get('kind')=='effect' and e.get('effect')==effect and e.get('change') in ('start','replace','end','expire')
                and e.get('timestamp') is not None and x['timestamp']<e['timestamp']<=y['timestamp'] for e in ledger)
            if scope=='unknown':row['status']='side_or_effect_instance_unresolved; raw observations only'
            elif reset or x.get('track_epoch')!=y.get('track_epoch'):row['status']='activation_or_epoch_changed; relation withheld'
            elif x.get('inferred_elapsed_turns') is None or y.get('inferred_elapsed_turns') is None:row['status']='semantics_unverified; raw observations only'
            else:
                delta=y['inferred_elapsed_turns']-x['inferred_elapsed_turns'];row.update(elapsed_delta=delta,status='supports_one_annotated_turn' if delta==1 else 'counter_conflict_requires_review')
            checks.append(row)
    return checks


def review_html(reference,comparisons,destination):
    """Local-only proposal viewer; export edits without asserting human approval."""
    dest=Path(destination);dest.parent.mkdir(parents=True,exist_ok=True)
    def link(path):return html.escape(os.path.relpath(Path(path).absolute(),dest.parent))
    def transition(label,t):
        if not t or not t.get('interval'):return f'<p>{label}: unobservable</p>'
        refs=t['frame_refs'];images=''.join(f'<a href="{link(r["image"])}"><img loading="lazy" src="{link(r["image"])}"><span>{r["timestamp"]:.3f}s</span></a>' for r in refs)
        return f'<h4>{label}: {t["interval"][0]:.3f}–{t["interval"][1]:.3f}s</h4><p>{html.escape(t["evidence"])}</p><div class="frames">{images}</div>'
    content=['<!doctype html><meta charset="utf-8"><title>Agent-reviewed turn proposals</title>',
        '<style>body{background:#16191d;color:#eee;font:16px system-ui;max-width:1400px;margin:auto}a{color:#9cf}.frames{display:flex;gap:10px}.frames a{width:48%}img{width:100%}section{border:1px solid #678;padding:1em;margin:1em 0}textarea{width:96%;height:4em}pre{white-space:pre-wrap}video{width:70%}</style>',
        f'<h1>{reference["battle_id"]}: agent-reviewed proposals</h1><p>Human approval pending. Reference annotations were authored before v2 predictions. No independently measured human accuracy is claimed.</p>',
        '<p>Review each transition in the original video or linked PNGs. Enter corrections/notes and export them for review; exporting does not approve or overwrite annotations.</p>',
        f'<video controls preload="none" src="{link(reference["source"]["video"])}"></video>',
        '<p>Video files and frames stay local. A browser may require serving the repository locally to play the video.</p>']
    content.append(transition('Initial send-out completion',reference['initial_sendout_completion']))
    for turn in reference['turns']:
        content.append(f'<section><h2>{turn["id"]}</h2>')
        for name in ('command_start','resolution_start','resolution_completion','next_command_start'):content.append(transition(name,turn.get(name)))
        content.append(f'<label>Correction/notes for {turn["id"]}<textarea data-turn="{turn["id"]}"></textarea></label></section>')
    content.append(transition('Terminal result',reference['termination']))
    content.append('<h2>Other reviewed phases</h2>')
    for phase in reference.get('intervals',[]):content.append(transition(phase['kind']+' ('+phase['confidence']+')',phase))
    content.append('<h2>v1 and v2 comparison against proposals</h2><pre>'+html.escape(json.dumps({k:v['counts'] for k,v in comparisons.items()},indent=2))+'</pre>')
    content.append('<button id="export">Export correction notes</button><script>document.getElementById("export").onclick=()=>{const edits=[...document.querySelectorAll("textarea")].map(e=>({turn_id:e.dataset.turn,notes:e.value})).filter(e=>e.notes.trim());const data={schema:"human-review-notes-v1",human_approved:false,edits};const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"}));a.download="turn-review-corrections.json";a.click();URL.revokeObjectURL(a.href)};</script>')
    dest.write_text('\n'.join(content))


def evaluate(number):
    import time
    started=time.perf_counter();battle=BattleArtifacts(f'sample_battle_{number}',Path.cwd())
    ref_path=battle.report('inputs/M3.4-visual-reference-v2.json');reference=json.loads(ref_path.read_text())
    freeze=json.loads(Path('.cache/m34-visual-v2/reference-freeze.json').read_text())['references']
    key=str(ref_path.relative_to(Path.cwd()))
    if freeze[key]!=file_hash(ref_path):raise ValueError('Reference revised after freeze; explicit independent review revision required')
    indices={v:json.loads((Path('.cache/m34-visual-v2')/('battle-index.json' if v=='v2' else 'v1-index.json')).read_text()) for v in ('v1','v2')}
    sources={v:next(p for p in paths if Path(p).is_relative_to(battle.cache_dir)) for v,paths in indices.items()}
    predictions={v:json.loads(Path(p).read_text()) for v,p in sources.items()}
    identity=dict(reference=file_hash(ref_path),predictions={v:file_hash(Path(p)) for v,p in sources.items()},
        implementation=file_hash(Path(__file__)),tolerance=TOLERANCE)
    from speed_inference.domains import digest
    directory=battle.cache('m34-visual-v2-validation/'+digest(identity)[:16]);directory.mkdir(parents=True,exist_ok=True)
    m=battle.guard_output(directory/'manifest.json');result_path=battle.guard_output(directory/'evaluation.json')
    if m.exists():
        saved=json.loads(m.read_text())
        if saved.get('status')=='complete' and result_path.exists() and saved['output_hash']==file_hash(result_path):return str(result_path)
    atomic_json(m,dict(status='running',identity=identity))
    comparisons={v:compare(reference,prediction) for v,prediction in predictions.items()}
    checks=counter_checks(reference,predictions['v2'])
    result=dict(battle_id=battle.battle_id,reference=str(ref_path),reference_status=reference['review_status'],human_approved=False,
        comparisons=comparisons,counter_checks=checks,counter_conflicts=[r for r in checks if r['status']=='counter_conflict_requires_review'],
        metrics=dict(seconds=time.perf_counter()-started,new_frames=0,new_OCR=0),
        review_html=str(directory/'review.html'),review_required=True)
    review_html(reference,comparisons,battle.guard_output(directory/'review.html'))
    atomic_json(result_path,result);atomic_json(m,dict(status='complete',identity=identity,output_hash=file_hash(result_path),seconds=time.perf_counter()-started))
    print(json.dumps(dict(battle_id=battle.battle_id,comparisons={v:c['counts'] for v,c in comparisons.items()},review_html=result['review_html'],counter_conflicts=len(result['counter_conflicts']))),flush=True)
    return str(result_path)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',required=True,type=int,choices=range(5,10));a=p.parse_args();evaluate(a.battle)
