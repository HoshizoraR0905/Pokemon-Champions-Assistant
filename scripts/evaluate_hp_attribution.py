"""Replay sealed B16 predictions only; compare against immutable baseline metrics.

No decoding, OCR, reference construction or prediction injection. Run IDs must
be new; compatible completed runs are reused by source/content identity.
"""
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from battle_artifacts import BattleArtifacts
from tracking.state_engine import StateEngine, EventRecord
from tracking.battle_state import from_dict
from recognition.event_report import atomic_json, verify_seal

ROOT=Path(__file__).resolve().parents[1]
FIELDS={'cause','cause_event_ids','candidate_causes','attribution_status','attribution_reasons','source_instance_id'}


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def behavior(value):
    # Historical HP snapshots carry the same optional metadata as the live ledger.
    if isinstance(value,dict):
        numeric='unit' in value and 'after' in value and 'evidence' in value
        return {k:behavior(v) for k,v in value.items() if not (numeric and k in FIELDS)}
    if isinstance(value,list):return [behavior(v) for v in value]
    return value


def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);a=p.parse_args()
    owner=BattleArtifacts('sample_battle_16',ROOT)
    source=owner.cache('event-driven/b16-banner-hp-20261028-v6')
    out=owner.cache('hp-attribution/'+a.run_id)
    report=owner.report('evaluation/'+a.run_id)
    verify_seal(source)
    identity=dict(source_sha256=digest(source/'replay.json'),sources={s:digest(ROOT/s) for s in
        ['tracking/hp_causes.py','tracking/state_engine.py','scripts/evaluate_hp_attribution.py']},
        reference_sha256=digest(owner.report('evaluation/b16-semantic-state-20261027-v1/reference-facts.json')))
    manifest=out/'manifest.json'
    if manifest.exists():
        old=json.loads(manifest.read_text())
        if old['identity']!=identity:raise ValueError('Run identity changed; choose a new run ID')
        if old['status']=='complete':print('Compatible completed result:',report);return
    out.mkdir(parents=True,exist_ok=True);report.mkdir(parents=True,exist_ok=True)
    for name in identity['sources']:
        snapshot=out/'source'/name;snapshot.parent.mkdir(parents=True,exist_ok=True);snapshot.write_bytes((ROOT/name).read_bytes())
    atomic_json(manifest,dict(status='running',identity=identity,resume_command=f'.venv/bin/python scripts/evaluate_hp_attribution.py --run-id {a.run_id}'))
    old=json.loads((source/'replay.json').read_text())
    engine=StateEngine(from_dict(old['initial_state']))
    engine.history=[EventRecord(r['event'],r['delivery_index'],r['ordering'],retracted=r['retracted']) for r in old['history']]
    def progress(record,state):
        if record.delivery_index%100==0:
            print(f'Replay {record.delivery_index}/{len(engine.history)}',flush=True)
            atomic_json(out/'partial-state.json',state.to_dict())
            atomic_json(manifest,dict(status='running',identity=identity,processed=record.delivery_index,
                partial_state=str(out/'partial-state.json'),resume_command=f'.venv/bin/python scripts/evaluate_hp_attribution.py --run-id {a.run_id}'))
    engine.replay(snapshot_callback=progress)
    new=engine.to_dict();atomic_json(out/'replay.json',new)
    assert behavior(new['state'])==behavior(old['state']), 'Non-attribution state changed'
    assert [(r['application_status'],r['reason']) for r in new['history']]==[(r['application_status'],r['reason']) for r in old['history']], 'Receipt behavior changed'
    byid={r['event']['event_id']:r for r in new['history']}
    changes=[];missing=[]
    for pid,m in new['state']['pokemon'].items():
        for o in m['hp']['observations']:
            if 'unit' not in o:continue
            if o.get('delta') is None:missing.append(dict(pid=pid,event_id=o['evidence']['event_id']))
            if not o.get('delta'):continue
            def trace(eid):
                r=byid[eid];e=r['bindings'].get('resolved_event') or r['event']
                return dict(event_id=eid,time=e['attributes'].get('observation_time'),sequence=r['delivery_index'],
                            text=e['attributes'].get('reconstructed_logical_message'),evidence=e['evidence'])
            changes.append(dict(pid=pid,species=m['species']['value'],**o,
                endpoints=[trace(o['baseline_event_id']),trace(o['evidence']['event_id'])],
                causal_events=[trace(eid) for eid in o['cause_event_ids']]))
    statuses=Counter(o['attribution_status'] for o in changes)
    breakdown=Counter(o['cause']['kind'] for o in changes if o['cause'])
    categories=Counter()
    for o in changes:
        if not o['cause']:continue
        kind=o['cause']['kind']
        category='healing' if o['delta']>0 else {'move':'move_damage','move_recoil':'recoil','entry_hazard':'hazard'}.get(kind,kind)
        categories[category]+=1
    categories={k:categories[k] for k in ['move_damage','recoil','self_hp_cost','item','ability','status','weather','hazard','instant_faint','healing']}
    metrics=dict(observed_numeric_changes=len(changes),complete_endpoint_pairs=len(changes),
        observations_without_baseline=len(missing),statuses=dict(statuses),supported_by_kind=dict(breakdown),supported_by_category=categories,
        causal_coverage=statuses['supported']/len(changes),causal_correctness=None,
        independently_verified_causal_labels=0,event_facts='120/124',state_fields='175/191',
        non_attribution_state_identical=True,receipt_statuses_identical=True,
        limitations=['Observed changes count nonzero adjacent numeric deltas, including HUD animation segments; not 21 reference episodes.',
                    'No independent causal labels: correctness and whole-match false association rate unmeasured.',
                    'All prior reference event/state metrics preserved by identical receipts and non-attribution state.'])
    atomic_json(report/'metrics.json',metrics);atomic_json(report/'causal-links.json',changes)
    atomic_json(report/'missing-baselines.json',missing)
    lines=['# M2 — B16 evidence-based HP attribution','',f'Run `{a.run_id}`; sealed v6 events and endpoints, v5 acquisition; no OCR or reference edits.','',
           f'Observed numeric changes: **{len(changes)}**, complete adjacent endpoint pairs: **{len(changes)}**. Supported: **{statuses["supported"]}**; ambiguous: **{statuses["ambiguous"]}**; unknown: **{statuses["unknown"]}**. Causal coverage: **{metrics["causal_coverage"]:.1%}**.',
           '',f'Cause categories: `{categories}`.',
           '', 'Counts include animation segments. Observations without a baseline are separately listed; they cannot establish a change. The sealed reference stays at 124 event facts, 191 state fields and 21 endpoint episodes; these are distinct denominators.',
           '', 'Every receipt status/reason and all final non-attribution state fields equal v6. Existing reconstruction metrics remain **120/124**, **175/191**, numeric reference endpoint pairs **18/21**, observed HUD zeros **3/3**. State hashes change because HP histories now include causal metadata.',
           '', 'Causal correctness is unmeasured: no independently verified numeric causal labels exist. No detected conflict is established by this replay comparison; an incorrect-link rate cannot be inferred. Synthetic tests verify contracts only.',
           '', '| Affected instance | Before → after | Unit | Status / cause | Endpoint times | Evidence IDs / unresolved reason |',
           '|---|---:|---|---|---|---|']
    for o in changes:
        times=' → '.join(str(x['time']) for x in o['endpoints'])
        cause=o['cause'];label=o['attribution_status']+(' / '+cause['kind']+' '+str((cause.get('source') or {}).get('name','')) if cause else '')
        evidence=', '.join(o['cause_event_ids']) if cause else ', '.join(o['attribution_reasons'])
        lines.append(f'| {o["pid"]} | {o["observed_before"]} → {o["after"]} ({o["delta"]:+}) | {o["unit"]} | {label} | {times} | {evidence} |')
    lines.extend(['','Full source-event → prefix-bound instance → endpoint → causal evidence → applied HP-history traces: [causal-links.json](causal-links.json).',
                  '', 'Remaining gaps: no named recipient in many actions; aggregate windows containing several effects; unreadable/hidden HUDs; missing baselines. Item/ability activation alone does not establish a numeric HP occurrence. Later target evidence can revise earlier animation segments only within an uninterrupted action. No damage formulas or move-name target assumptions are used.',
                  '', 'Next priorities: review the proposed links independently and collect scoped evidence for unresolved effects. No further milestone is started.'])
    (report/'report.md').write_text('\n'.join(lines)+'\n')
    atomic_json(manifest,dict(status='complete',identity=identity,outputs=[str(out/'replay.json'),str(report/'report.md')],metrics=metrics))
    print(json.dumps(metrics,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
