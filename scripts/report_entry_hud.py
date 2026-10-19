"""Review completed saved-event runs against an explicit semantic baseline.

No acquisition or recognition runs. Raw events and historical namespaces stay
immutable; acceptance is an explicit review decision rather than a count match.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.fast_video import digest
from recognition.video_sampling import atomic_json
def values(value):
    if isinstance(value,dict):
        if 'value' in value and 'provenance' in value:return values(value['value'])
        return {k:values(v) for k,v in value.items() if k not in {'provenance','evidence','observations','history'}}
    if isinstance(value,list):return [values(v) for v in value]
    return value


FACT_FIELDS=('species','original_identity','current_variant','location','fainted','hp',
             'major_status','status_counters','stages','item','ability','volatile',
             'transformations','current_types','mechanics','hidden_configuration')


def read(path):return json.loads(path.read_text())


def compare(before,after):
    changes=[]
    for pid,p in before['state']['pokemon'].items():
        q=after['state']['pokemon'].get(pid)
        if q is None:
            changes.append(dict(instance_id=pid,field='instance_missing'));continue
        for field in FACT_FIELDS:
            a=values(p[field]);b=values(q[field])
            if a!=b:changes.append(dict(instance_id=pid,field=field,before=a,after=b))
        a={m['event_id'] for m in p['moves']['executed']};b={m['event_id'] for m in q['moves']['executed']}
        if a!=b:changes.append(dict(instance_id=pid,field='executed_move_event_ids',lost=sorted(a-b),added=sorted(b-a)))
        for field in ('known_slots','pp','unrevealed_slots'):
            a=values(p['moves'][field]);b=values(q['moves'][field])
            if a!=b:changes.append(dict(instance_id=pid,field='moves.'+field,before=a,after=b))
    for side,team in before['state']['sides'].items():
        new=after['state']['sides'][side]
        for field in ('active_slots','vacant_slots','conditions','fainted_instance_ids','remaining_available',
                      'hazards','temporary_effects','resources','mechanics','party_instance_ids','party_complete','trainer'):
            if values(team[field])!=values(new[field]):changes.append(dict(side=side,field=field,before=values(team[field]),after=values(new[field])))
    def role_id(receipt,role):
        event=receipt['bindings'].get('resolved_event',receipt['event'])
        return receipt['bindings'].get(role,{}).get('pokemon_instance_id') or event['attributes'].get(role+'_instance_id')
    for old,new in zip(before['history'],after['history']):
        for role in ('actor','target'):
            previous=role_id(old,role);current=role_id(new,role)
            if previous and previous!=current:
                changes.append(dict(event_id=old['event']['event_id'],timestamp=old['event']['attributes'].get('observation_time'),
                    field=role+'_binding',before=previous,after=current))
    assert [h['event'] for h in before['history']]==[h['event'] for h in after['history']]
    return changes


def review(owner,diagnostic,baseline):
    target=owner.cache('evaluation/'+diagnostic);manifest=read(target/'manifest.json');assert manifest['status']=='complete'
    for name,h in manifest['outputs'].items():assert digest(target/name)==h
    before=read(owner.cache(baseline));after=read(target/'replay.json');summary=read(target/'summary.json')
    changes=compare(before,after)
    old_receipts=before['state']['knowledge'].get('command_reconciliation',{}).get('receipts',[])
    proof_frames={}
    for ep in summary['entry_episodes']:
        audit=ep.get('hud_binding',{})
        for proof in [audit.get('first_eligible_evidence'),audit.get('corroborating_observation')]:
            if not proof:continue
            for source in proof['evidence']['sources']:
                image=source.get('details',{}).get('image')
                if image:
                    expected=source['observation_ids'][0];assert digest(ROOT/image)==expected
                    proof_frames[image]=expected
        name=ep.get('hud_display_name')
        if name:
            assert name['established_at']>=name['observation_time']>ep['start']
            assert name['value'] in [c['raw'] for c in audit['candidates'] if c['eligible']]
            frames=[set(c['frames']) for c in audit['candidates'] if c['eligible'] and c['raw']==name['value']]
            assert any(a.isdisjoint(b) for a in frames for b in frames)
    assert not summary['invariants']
    result=dict(status='review_required' if changes else 'equivalent',battle_id=owner.battle_id,
        baseline=baseline,baseline_sha256=digest(owner.cache(baseline)),replay_sha256=digest(target/'replay.json'),
        raw_events_preserved=True,changes=changes,proof_frames=proof_frames,
        before_w=dict(outcomes=dict(Counter(o['status'] for r in old_receipts for o in r['outcomes'])),corrections=sum(r['corrections'] for r in old_receipts)),
        after_w=dict(outcomes=summary['command_outcomes'],corrections=summary['corrections']),
        accepted=None,reason='Each changed supported fact requires evidence review; receipt-count equality is not semantic acceptance.')
    # This is a new namespace's review, never a replacement for an older result.
    atomic_json(target/'semantic-comparison.json',result)
    # Presentation is a separate stage. Original sealed runner HTML is retained.
    from scripts.replay_entry_hud import timeline_html
    frames={}
    for receipt in after['history']:
        for source in receipt['event']['evidence']:
            details=source.get('details',{});image=details.get('image');t=details.get('timestamp')
            if image and t is not None and source['observation_ids'] and source['source_type'] in {'video_hud','video_message'}:
                item=dict(timestamp=t,image=image,sha256=source['observation_ids'][0])
                if t in frames:assert frames[t]==item
                frames[t]=item
    html=owner.report('evaluation/'+diagnostic+'/hud-proof-timeline.html')
    timeline_html(target,html,read(target/'timeline.json'),summary,list(frames.values()))
    atomic_json(target/'review-manifest.json',dict(status='complete',
        inputs={name:digest(target/name) for name in ['replay.json','timeline.json','summary.json']},
        outputs={str(html.relative_to(ROOT)):digest(html),str((target/'semantic-comparison.json').relative_to(ROOT)):digest(target/'semantic-comparison.json')},
        source=digest(Path(__file__)),recognition_calls=0))
    return summary,result


def verify_saved_run(owner,diagnostic):
    """Verify historical outputs; do not assert current-source compatibility."""
    folder=owner.cache('evaluation/'+diagnostic);manifest=read(folder/'manifest.json')
    assert manifest['status']=='complete'
    for name,expected in manifest['outputs'].items():assert digest(folder/name)==expected
    html=owner.report('evaluation/'+diagnostic+'/timeline.html')
    assert digest(html)==manifest['report_sha256']
    return dict(status='verified',battle_id=owner.battle_id,diagnostic=diagnostic,
        manifest_sha256=digest(folder/'manifest.json'),replay_performed=False,
        recognition_calls=0,current_source_compatibility_asserted=False)


def main():
    if len(sys.argv)==1:
        # Preserve the former no-argument v4 command without rewriting history.
        report=ROOT/'reports/battles/sample_battle_7/M2.3.8-entry-hud-final-stabilization-v4.md'
        frozen=read(ROOT/'.cache/battles/sample_battle_7/evaluation/m238-entry-hud-v4/task-manifest.json')
        assert digest(report)==frozen['outputs'][str(report.relative_to(ROOT))]
        print(report);return
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--battle',required=True,action='append');p.add_argument('--diagnostic-id',required=True)
    p.add_argument('--baseline');p.add_argument('--report',type=Path)
    p.add_argument('--verify-only',action='store_true',help='Verify saved hashes without claiming current-source compatibility')
    args=p.parse_args()
    if args.verify_only:
        for bid in args.battle:print(json.dumps(verify_saved_run(BattleArtifacts(bid),args.diagnostic_id)))
        return
    if not args.baseline or not args.report:p.error('--baseline and --report are required for a semantic review')
    lines=['# HUD-authoritative identity — saved-evidence semantic review','',
        f'Diagnostic: `{args.diagnostic_id}`. Baseline: `{args.baseline}`. No acquisition or recognition was performed.','',
        '## Semantic comparisons','',
        '| Battle | Records | Before → after statuses | Changed semantic fields | W before → after |',
        '|---|---:|---|---:|---|']
    results=[]
    for bid in args.battle:
        owner=BattleArtifacts(bid);summary,result=review(owner,args.diagnostic_id,args.baseline);results.append((summary,result))
        lines.append(f"| {bid} | {summary['records']} | `{summary['before']}` → `{summary['after']}` | {len(result['changes'])} | `{result['before_w']}` → `{result['after_w']}` |")
    lines+=['','## Entry/HUD proof chains','',
        '| Battle / message reference | HUD name | Possible prefix | Arrival | First candidate | First eligible | Confirmation | Species |','|---|---|---|---:|---:|---:|---:|---:|']
    for summary,result in results:
        for ep in summary['provisional_episodes']:
            audit=ep.get('hud_binding',{});name=ep.get('hud_display_name') or {};f=lambda v:'unknown' if v is None else f'{v:.6f}s'
            lines.append(f"| {summary['battle_id']} / {ep['display_reference']} | {name.get('value','unknown')} | {name.get('possible_title_segment') or 'none'} | {f(ep['start'])} | {f(audit.get('first_candidate_time'))} | {f(audit.get('first_eligible_time'))} | {f(name.get('established_at'))} | {ep.get('species_id')} |")
    lines+=['','## Review status','',
        'The raw comparisons and source-frame hashes are stored in each recording-owned `semantic-comparison.json`. A generated report does not by itself authorize cleanup. See the task acceptance record for the explicit quality-gate decision and individually justified differences.','',
        'The message reference is preserved verbatim. A HUD display name becomes authoritative only after two independent eligible frames agree. A suffix relation additionally requires a supported live send-out, an independently placed logical slot, continuous current episode, reliable HUD OCR and independent icon evidence, and no competing active interpretation. No title vocabulary or 的-based rule is used. Title-like strings remain part of the display name when the HUD displays them in full.','',
        'Earlier snapshots remain species-unknown. The 30-second entry horizon and three-second confirmation bound remain in force; expired associations require fresh current-continuity evidence and are labelled prospective. W remains an auxiliary command-phase check. No 3D scene recognition or broader mechanics are introduced.']
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text('\n'.join(lines)+'\n')
    print(args.report)
    for summary,result in results:print(summary['battle_id'],'semantic differences',len(result['changes']),'raw events preserved')


if __name__=='__main__':main()
