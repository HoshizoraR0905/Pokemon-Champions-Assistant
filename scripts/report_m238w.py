"""Offline W diagnostics from sealed scoped stages; never acquires recognition.

Run after validate_m238w.py's audit/acquire/replay stages. Compatibility receipts
preserve old audits when only acquisition helpers changed after the audit.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json

RUN='m238-command-reconciliation-v1'

def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def audit_compatibility(folder):
    """Only permit unchanged UI audit code, UI functions, constants and imports.

    Full dependency hashes are retained. Other changes are rejected. The
    compatibility record is separate; sealed manifests are never rewritten.
    """
    manifest=read(folder/'audit-manifest.json');checks=[]
    for name,expected in manifest['identity'].items():
        current=ROOT/name
        if sha(current)==expected:continue
        assert name=='recognition/command_checkpoint.py',f'Unreviewed audit dependency change: {name}'
        saved=folder/'source'/name;assert sha(saved)==expected
        def relevant(path):
            tree=ast.parse(path.read_text())
            return [ast.dump(n,include_attributes=False) for n in tree.body
                if isinstance(n,(ast.Import,ast.ImportFrom,ast.Assign)) or getattr(n,'name',None) in {'inspect_command','CommandCheckpointSchedule'}]
        assert relevant(saved)==relevant(current),'UI detection/scheduling changed; audit must use a new namespace'
        checks.append(dict(path=name,original_sha256=expected,current_sha256=sha(current),
            reason='Unchanged imports, constants, inspect_command and CommandCheckpointSchedule AST; changes limited to capture and production boundary helpers'))
    return dict(status='compatible',audit_manifest_sha256=sha(folder/'audit-manifest.json'),changed_dependencies=checks,
                sealed_audit_modified=False)


def build(owner,run_id=RUN):
    folder=owner.cache('event-driven/'+run_id);report=owner.report_dir
    stages={stage:read(folder/(stage+'-manifest.json')) for stage in ('audit','acquire','replay')}
    assert all(m['status']=='complete' for m in stages.values())
    for stage,output,key in [('audit','audit.json','audit_sha256'),('acquire','captures.json','captures_sha256'),('replay','summary.json','summary_sha256'),('replay','replay.json','replay_sha256')]:
        assert sha(folder/output)==stages[stage][key],f'{output} changed after completion'
    compatibility=audit_compatibility(folder)
    atomic_json(folder/'audit-compatibility.json',compatibility)
    audit=read(folder/'audit.json');captures=read(folder/'captures.json');summary=read(folder/'summary.json')
    def link_image(value):
        if not value:return None
        path=(ROOT/value).resolve();assert path.is_relative_to(ROOT)
        return os.path.relpath(path,report)
    frames=[]
    for r in audit['frames']:
        frames.append(dict(timestamp=r['timestamp'],source_id=r['source_id'],image=link_image(r['image']),
            sha256=r['sha256'],cached_phase=r['cached_phase'],inspection=r['inspection'],checkpoint=r['checkpoint']))
    receipts=json.loads(json.dumps(summary['receipts']))
    for receipt in receipts:
        for o in receipt['outcomes']:
            o['observation']['image']=link_image(o['observation']['image'])
            for e in o.get('historical_gap',{}).get('message_and_coverage_evidence',[]):
                for p in e['evidence']:
                    if p.get('details',{}).get('image'):p['details']['image']=link_image(p['details']['image'])
    examples=[dict(r,image=link_image(r['image'])) for r in audit['reference_examples']]
    data=dict(battle_id=owner.battle_id,counts=audit['counts'],summary={k:v for k,v in summary.items() if k!='receipts'},
        receipts=receipts,frames=frames,examples=examples,costs=dict(audit_wall_seconds=audit['wall_seconds'],
        acquire={k:v for k,v in captures.items() if k not in {'captures','exact_cache_sources'}},replay_wall_seconds=summary['wall_seconds']),
        audit_compatibility=compatibility,
        limitations=['Native 1311×603 layout only; sparse saved sampling limits stable-window coverage.',
            'Species/slot agreement does not prove individual or form continuity.',
            'Nickname associations use only previously accepted side-owned V evidence.',
            ('Observed corrections are current-occupancy repairs with unresolved historical gaps.' if summary['corrections'] else 'No real discrepancies or corrections were observed; correction behavior is covered by synthetic tests.'),
            'No full production video acquisition was run. Production scheduling/capture boundary and resume were tested with mocked recognition.',
            'Images are relative links to existing local artifacts. Keep this checkout and caches available for offline review.'])
    template=ROOT/'scripts/templates/m238w_review.html'
    version=run_id.rsplit('-',1)[-1]
    html=report/f'M2.3.8-W-command-reconciliation-{version}.html';md=report/f'M2.3.8-W-completion-{version}.md'
    report.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    html.write_text(template.read_text().replace('__DATA__',payload))
    c=summary['classification'];cost=captures['counts'];counts=audit['counts']
    gap_note=('Current occupancy was corrected only where independent evidence supported it; the exact missing transition remains unresolved.' if summary['corrections'] else 'No real discrepancy means no recovered missing message or historical interval is claimed.')
    compatibility_note=('`audit-compatibility.json` records matching UI detector/scheduler AST despite later acquisition-only helper changes; no audit was repeated.' if compatibility['changed_dependencies'] else 'All completed audit dependency hashes match the current source; its results are reused unchanged.')
    rows=['| Time (s) | Phase | Slot | Result | Basis | Predicted → observed species |',
          '|---:|---|---|---|---|---|']
    for r in receipts:
        for o in r['outcomes']:
            observed=(o['observed'] or {}).get('species_id','unknown')
            rows.append(f"| {r['timestamp']:.3f} | {r['phase_id']} | {o['key']} | {o['status']} | {o['basis']} | {o['previous_species_id']} → {observed} |")
    md.write_text(f'''# M2.3.8-W — {owner.battle_id}

Status: scoped saved-evidence validation completed; milestone review pending. Validation preceded user authorization for Git publication.

[Offline diagnostic review]({html.name})

Audited {counts['frames']} saved frames: {counts['normal_controls']} normal-control frames, {counts['eligible_frames']} complete four-HUD frames, {summary['checkpoints']} stable checkpoint attempts. Results: {c.get('match',0)} matches, {c.get('inconclusive',0)} inconclusive slots, {c.get('conflict',0)} conflicts, {c.get('unexpected_occupancy',0)} unexpected occupancies, {summary['corrections']} actual corrections. All three supplied overlay/selection examples were rejected. Exclusion reasons: `{json.dumps(counts['exclusion_causes'])}`.

{chr(10).join(rows) if receipts else 'No stable checkpoint was available. Eligible isolated frames remain audit candidates, not successful verification or reconciliation.'}

{gap_note} Synthetic tests exercise corrections, unresolved historical gaps, prefix-only message links, party ambiguity and subsequent faint/send-out behavior. Replay found {len(summary['regressions'])} previously applied-event status regressions, {len(summary['invariants'])} duplicate-active-instance violations and {len(summary['rejected'])} rejected events. Replay success is not measured recognition accuracy or complete semantic acceptance.

Resource cost: audit {audit['wall_seconds']:.3f}s, scoped acquisition {captures['wall_seconds']:.3f}s, replay {summary['wall_seconds']:.3f}s. New OCR calls: {cost.get('ocr_invocations_performed',0)}; exact OCR cache hits: {cost.get('ocr_exact_cache_hits',0)}; same-frame saved HUD names retained where present. OCR inference time: {cost.get('ocr_seconds',0):.3f}s. Video decoding: 0; icon calls: 0; replay recognition calls: 0. Audit peak RSS: {audit['peak_process_rss_mb']:.1f} MiB; acquisition peak RSS: {captures['peak_process_rss_mb']:.1f} MiB. Times/RSS are per process/stage, not whole-project performance estimates.

The completed audit and captures remain sealed. {compatibility_note} Original events and image evidence remain unchanged. Scoped stage manifests retain the exact implementation hashes used for each stage. Original W validation is recorded in [the milestone completion](../../M2.3.8-W-completion.md); subsequent strict-single-frame validation is recorded in [the final evaluation](../../M2.3.8-W-final-validation-and-B7.md).

Limitations: {' '.join(data['limitations'])}
''')
    atomic_json(folder/'report-manifest.json',dict(status='complete',inputs={n:sha(folder/n) for n in ['audit.json','captures.json','summary.json','audit-compatibility.json']},
        sources={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),template]},outputs={str(p.relative_to(ROOT)):sha(p) for p in [html,md]}))
    print(html.relative_to(ROOT),flush=True)
    return data


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',required=True,choices=['sample_battle_5','sample_battle_6']);p.add_argument('--run-id',default=RUN)
    a=p.parse_args();build(BattleArtifacts(a.battle,ROOT),a.run_id)
if __name__=='__main__':main()
