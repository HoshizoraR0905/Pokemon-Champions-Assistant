"""Cache-only, prefix-local M2.3.6 evaluation and offline human review.

Labels are read here, never by recognition. Repeated frame facts are descriptive
counts, not independent trials. No recognition, inference or video decoding runs.
"""
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
import unicodedata

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json, fingerprint

BID='sample_battle_5'
P=BattleArtifacts(BID,ROOT).cache('m236')
FIXTURE=ROOT/'tests/fixtures/battles/m236_review.json'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def integrity():
    seal=json.loads((P/'initial-seal.json').read_text())
    bad=[p for p,h in seal['protected'].items() if not (ROOT/p).exists() or sha(ROOT/p)!=h]
    if bad:raise ValueError('Protected artifacts changed: '+repr(bad))
    review=json.loads((P/'review-seal.json').read_text())
    assert sha(FIXTURE)==review['sha256']
    assert sha(P/'evaluation-acquisition.json')==review['acquisition_sha256']
    acquisition=json.loads((P/'evaluation-acquisition.json').read_text())
    assert all(sha(ROOT/r['image'])==r['sha256'] for r in acquisition['frames'])
    return dict(protected_artifacts=len(seal['protected']),review_sha256=sha(FIXTURE),
        acquired_frames=len(acquisition['frames']),status='verified')


def replay(data):
    from recognition.identity_events import events_from_observations
    from tracking.state_engine import StateEngine,EventRecord,event_from_dict,ordering
    from tracking.battle_state import BattleState,from_dict
    engine=StateEngine(BattleState(BID,knowledge=dict(reliability_v1=True,reliability_v2=True,identity_v1=True)))
    for i,e in enumerate(events_from_observations(data,BID),1):
        e['attributes']['sequence']=i
        engine.history.append(EventRecord(e,i,ordering(event_from_dict(e))))
    snapshots={}
    engine.replay(snapshot_callback=lambda r,s:snapshots.update({r.event['attributes']['observation_time']:s.to_dict()}))
    projections={};alias_prefixes={}
    for row in data['observations']:
        t=row['timestamp'];prior=[v for v in snapshots if v<=t]
        prefix=StateEngine(from_dict(snapshots[max(prior)]) if prior else engine.initial)
        prefix.history=deepcopy([r for r in engine.history if r.event['attributes']['observation_time']<=t])
        projections[str(t)]=prefix.evidence_projection(as_of=t)
        alias_prefixes[str(t)]=deepcopy(prefix.state.knowledge.get('identity_ledger',{}).get('aliases',[]))
    return dict(engine=engine.to_dict(),projections=projections,alias_prefixes=alias_prefixes)


def normalized(text):
    return ''.join(unicodedata.normalize('NFKC',text).casefold().split()).rstrip('!。.')


def resolved_event(record):return record['bindings'].get('resolved_event',record['event'])


def score_hud(label,mon,receipt,projection):
    """Count a current fact only through the decision-facing projection."""
    resolution=(mon or {}).get('species',{}).get('resolution') or {}
    sid=resolution.get('species_id') if resolution.get('status')=='resolved' else None
    slot=projection['occupancy'][label['side']][label['slot']]
    pid=slot['current_instance_id'];p=projection['pokemon'].get(pid,{})
    current_sid=p.get('identity',{}).get('value') or {}
    current_sid=current_sid.get('species_id') if p.get('identity',{}).get('current_supported') else None
    bound_sid=receipt.get('species_id') if receipt.get('status')=='accepted' else None
    hp=label['hp'];actual=(mon or {}).get('hp',{}).get('value')
    if 'percent' in hp:raw_hp=actual==hp['percent']
    else:raw_hp=actual==hp
    current_hp={}
    for k,target in [('current','current'),('maximum','maximum'),('percent','displayed_percent')]:
        value=p.get('hp',{}).get(target,{})
        if value.get('current_supported'):current_hp[k]=value['value']
    hp_current=current_sid==label['species_id'] and all(current_hp.get(k)==v for k,v in hp.items())
    failure=('HUD not scheduled' if mon is None else 'Species unresolved' if sid is None
        else 'Incorrect species' if sid!=label['species_id'] else 'Identity admission withheld' if bound_sid is None
        else 'Current slot not supported' if current_sid is None else 'HP unresolved or differs' if not hp_current else 'None')
    profiles=(mon or {}).get('icon',{}).get('independent_profiles',[])
    default=profiles[0] if profiles else {}
    return dict(label=label,scheduled=mon is not None,
        nickname_transcribed=normalized((mon or {}).get('species',{}).get('raw_text',''))==normalized(label['display_name']),
        species_correct=sid==label['species_id'],species_wrong=sid is not None and sid!=label['species_id'],
        default_icon_correct=default.get('status')=='resolved' and default.get('species_id')==label['species_id'],
        combined_icon_correct=(mon or {}).get('icon',{}).get('status')=='resolved' and (mon or {}).get('icon',{}).get('species_id')==label['species_id'],
        admitted=bound_sid is not None,admitted_correct=bound_sid==label['species_id'],
        admitted_wrong=bound_sid is not None and bound_sid!=label['species_id'],
        bound_correct=bound_sid==label['species_id'] and bool(receipt.get('instance_id')),
        current_correct=current_sid==label['species_id'],
        current_wrong=current_sid is not None and current_sid!=label['species_id'],
        hp_read_correct=raw_hp,hp_current_correct=hp_current,
        instance_id=pid,current_species_id=current_sid,current_hp=current_hp,first_failure=failure)


def score_occurrence(label,rows,history,pokemon):
    start,end=label['start']-.04,label['end']+.04
    observations=[r for r in rows if start<=r['timestamp']<=end]
    records=[r for r in history if start<=r['event']['attributes']['observation_time']<=end
        and r['event']['event_type'] not in {'hud_observation','preview_observation','coverage_observation'}]
    literal=label.get('text') or label.get('text_contains','')
    transcribed=any(normalized(literal) in normalized(r['message']['raw_text']) for r in observations)
    if label.get('move'):
        canonical=[r for r in records if (resolved_event(r)['canonical_references'].get('move') or {}).get('canonical_id')==label['move']]
    else:
        kind={'item_reaction':'move_effect'}.get(label['kind'],label['kind'])
        canonical=[r for r in records if resolved_event(r)['event_type']==kind
            and (label['kind']!='item_reaction' or resolved_event(r)['attributes'].get('effect')=='mega_stone_reaction_notice')]
    admitted=[r for r in canonical if r['application_status'].startswith('applied')]
    bound=[]
    for r in admitted:
        pid=r['bindings'].get('actor',{}).get('pokemon_instance_id')
        species=resolved_event(r).get('actor') or {}
        if pid and species.get('species_id')==label.get('species_id'):bound.append(r)
    return dict(label=label,sampled_frames=len(observations),recognition_attempts=len(observations),
        transcribed=transcribed,canonical_recognized=bool(canonical),admitted=bool(admitted),
        actor_bound_correct=bool(bound),executed_move_revealed=bool(label.get('move') and any(
            r['bindings'].get('admissibility',{}).get('move') for r in bound)),
        events=[dict(event_id=r['event']['event_id'],text=r['event']['original_text'],
            kind=resolved_event(r)['event_type'],status=r['application_status'],reason=r['reason'],
            actor=resolved_event(r)['actor'],bindings=r['bindings']) for r in records])


def preview_score(data,reference):
    output=[]
    for row in data['roster']:
        sid=reference[row['preview_row']-1];icon=row['icon'];candidates=icon.get('candidates',[])
        output.append(dict(timestamp=row['evidence']['timestamp'],row=row['preview_row'],expected_species=sid,
            predicted_species=row['species_id'],status=row['status'],correct=row['species_id']==sid,
            wrong=row['species_id'] is not None and row['species_id']!=sid,
            top_candidates=candidates[:3],gap=candidates[0]['similarity']-candidates[1]['similarity'] if len(candidates)>1 else None))
    return output


def historical_regressions():
    """Previously exposed M2.3.5 cases; never independent held-out evidence."""
    import cv2
    from models import Observation,IconEvidence,IconCandidate
    from recognition.entities import EntityResolver
    from recognition.identity import combine_identity
    from recognition.identity_flow import hud_cards
    from tracking.evidence_fusion import identity_evidence
    audit=json.loads((BattleArtifacts(BID,ROOT).cache('m235d/43b850d82c3ccd2e/audit.json')).read_text())
    resolver=EntityResolver();contracts=[]
    for snap in audit['snapshots']:
        if not any(abs(snap['timestamp']-t)<.01 for t in [300.016667,380.03,452.01]):continue
        slot=next(s for s in snap['slots'] if s['hud_ui_slot']=='own_active_1')
        text=resolver.resolve(Observation(raw_text=slot['name']['raw_text'],value=slot['name']['raw_text'],
            confidence=slot['name']['confidence']),'species',region_kind='species')
        raw={k:v for k,v in slot['color_icon'].items() if k!='top_two_gap'}
        raw['candidates']=[IconCandidate(**c) for c in raw['candidates']]
        icon=IconEvidence(**raw);combined=combine_identity(text,icon,resolver.knowledge)
        ref,status,reason=identity_evidence(asdict(combined),asdict(icon),reliability=True)
        contracts.append(dict(timestamp=snap['timestamp'],species_id=ref['species_id'] if ref else None,status=status,
            reason=reason,text_method=combined.resolution.method,independent_icon_status=icon.status,
            conditional_evidence=combined.resolution.conditional_evidence))
    data=json.loads(BattleArtifacts(BID,ROOT).cache('m235/final-observations.json').read_text())
    scheduled=[]
    for t in [256.01,346.025,456.01]:
        row=next(r for r in data['observations'] if abs(r['timestamp']-t)<.02)
        scheduled.append(dict(timestamp=row['timestamp'],old_cards=len(row.get('snapshot',{}).get('pokemon',[])),
            eligible_cards=[dict(side=s,ui_index=i) for s,i,_,_ in hud_cards(cv2.imread(str(ROOT/row['image'])))],
            new_ocr=0,note='Eligibility only; no new recognition/admission is claimed'))
    return dict(exact_name_contract=contracts,hud_eligibility=scheduled)


def evaluate(split):
    check=integrity();data=json.loads((P/f'{split}-observations.json').read_text());fixture=json.loads(FIXTURE.read_text())
    if split=='held_out':
        seal=json.loads((P/'implementation-seal.json').read_text())
        if seal['evaluator']!=sha(__file__):
            amendment=json.loads((P/'evaluator-amendment.json').read_text())
            assert amendment['original_sha256']==seal['evaluator'] and amendment['corrected_sha256']==sha(__file__)
        assert all(sha(ROOT/f)==h for f,h in seal['code'].items())
        assert sha(ROOT/'scripts/process_m236.py')==seal['runner']
    # Both runtime and projection use chronological evidence only. Development
    # observations precede held-out, separated by an explicit coverage gap.
    runtime=deepcopy(data)
    if split=='held_out':
        dev=json.loads((P/'development-observations.json').read_text())
        assert dev['recipe']==data['recipe']
        runtime['observations']=dev['observations']+data['observations']
    result=replay(runtime);history=result['engine']['history'];byhash={r['sha256']:r for r in data['observations']}
    receipts={}
    for record in history:
        if record['event']['event_type']=='hud_observation':
            a=record['event']['attributes'];receipt=deepcopy(record['bindings'].get('hud',{}))
            receipt['instance_id']=record['bindings'].get('actor',{}).get('pokemon_instance_id')
            receipts[(a['observation_time'],record['event']['side'],a['slot'])]=receipt
    frames=[];facts=[]
    for label in fixture['frames']:
        if label['split']!=split:continue
        row=byhash[label['sha256']];p=result['projections'][str(row['timestamp'])];scored=[]
        for h in label['hud']:
            slot=('own' if h['side']=='self' else 'opponent')+'_active_'+('1' if h['slot']=='left' else '2')
            mon=next((m for m in row['snapshot']['pokemon'] if m['slot']==slot),None)
            score=score_hud(h,mon,receipts.get((row['timestamp'],h['side'],h['slot']),{}),p)
            facts.append(score);scored.append(score)
        frames.append(dict(**row,reviewed_hud=scored,projection=p,
            aliases=result['alias_prefixes'][str(row['timestamp'])]))
    occurrences=[score_occurrence(o,data['observations'],history,result['engine']['state']['pokemon'])
        for o in fixture['occurrences'] if o['split']==split]
    metrics={k:sum(bool(f[k]) for f in facts) for k in ['scheduled','nickname_transcribed','species_correct','species_wrong',
        'default_icon_correct','combined_icon_correct','admitted','admitted_correct','admitted_wrong','bound_correct',
        'current_correct','current_wrong','hp_read_correct','hp_current_correct']}
    moves=[o for o in occurrences if o['label'].get('move')]
    metrics.update(reviewed_hud_facts=len(facts),acquired_frames=len(data['observations']),
        scheduled_cards=sum(r['scheduling']['scheduled_cards'] for r in data['observations']),
        skipped_reviewed_hud_facts=sum(not f['scheduled'] for f in facts),
        unresolved_current=sum(not f['current_correct'] and not f['current_wrong'] for f in facts),
        reviewed_occurrences=len(occurrences),reviewed_move_occurrences=len(moves),
        move_transcribed=sum(o['transcribed'] for o in moves),move_canonical=sum(o['canonical_recognized'] for o in moves),
        move_actor_bound=sum(o['actor_bound_correct'] for o in moves),move_revealed=sum(o['executed_move_revealed'] for o in moves))
    preview=preview_score(data,fixture['preview_reference']['species_by_ui_row'])
    baseline=json.loads((P/'preview-baseline.json').read_text());baseline_rows=[]
    for r in baseline['results']:
        for i,m in enumerate(r['opponent']):
            icon=m['icon'];c=icon['candidates'];baseline_rows.append(dict(timestamp=r['request']['timestamp'],row=i+1,
                expected_species=fixture['preview_reference']['species_by_ui_row'][i],predicted_species=icon['species_id'],
                status=icon['status'],correct=icon['status']=='resolved' and icon['species_id']==fixture['preview_reference']['species_by_ui_row'][i],
                top_candidates=c[:3],gap=c[0]['similarity']-c[1]['similarity'] if len(c)>1 else None))
    # Audit alias admissions only where frozen labels actually establish mapping.
    expected={(h['side'],normalized(h['display_name'])):h['species_id'] for r in fixture['frames'] for h in r['hud']}
    expected.update({(o['side'],normalized(o['display_name'])):o['species_id'] for o in fixture['occurrences']
        if o.get('display_name') and o.get('species_id')})
    aliases=result['engine']['state']['knowledge'].get('identity_ledger',{}).get('aliases',[])
    reviewed=[a for a in aliases if (a['side'],normalized(a['raw_nickname'])) in expected]
    metrics['reviewed_alias_claims']=len(reviewed)
    metrics['false_alias_claims']=sum(a['identity']['species_id']!=expected[(a['side'],normalized(a['raw_nickname']))] for a in reviewed)
    metrics['unreviewed_alias_claims']=len(aliases)-len(reviewed)
    out=dict(status='complete',split=split,integrity=check,metrics=metrics,
        recipe=data['recipe'],observations_sha256=sha(P/f'{split}-observations.json'),evaluator_sha256=sha(__file__),
        failures=dict(Counter(f['first_failure'] for f in facts)),occurrences=occurrences,
        preview=preview,preview_baseline=baseline_rows,frames=frames,aliases=aliases,
        recognition_cache=dict(ocr_hits=data['ocr_cache_hits'],icon_hits=data['icon_cache_hits']),
        event_statuses=dict(Counter(r['application_status'] for r in history)))
    atomic_json(P/f'{split}-evaluation.json',out);atomic_json(P/f'{split}-replay.json',result)
    print(split,json.dumps(metrics),flush=True)
    return out


def viewer(evaluations):
    """Relative assets, no external JavaScript and no writes to ground truth."""
    target=ROOT/'reports/M2.3.6-review';target.mkdir(parents=True,exist_ok=True)
    cards=[]
    for evaluation in evaluations:
        for r in evaluation['frames']:
            cards.append(dict(id=r['sha256'],split=r['split'],timestamp=r['timestamp'],
                image=os.path.relpath(ROOT/r['image'],target),message=r['message'],pokemon=r['snapshot']['pokemon'],
                reviewed_hud=r['reviewed_hud'],scheduling=r['scheduling'],aliases=r['aliases'],
                occupancy=r['projection']['occupancy'],entries=r.get('entry_windows',[])))
    preview=json.loads((P/'development-observations.json').read_text())['roster']
    for r in preview:r['evidence']['image']=os.path.relpath(ROOT/r['evidence']['image'],target)
    payload=json.dumps(dict(frames=cards,preview=preview,evaluations=[dict(split=e['split'],metrics=e['metrics'],
        preview=e['preview'],preview_baseline=e['preview_baseline'],occurrences=e['occurrences'],failures=e['failures']) for e in evaluations]),ensure_ascii=False).replace('<','\\u003c')
    template=(ROOT/'scripts/templates/m236_review.html').read_text()
    (target/'review.html').write_text(template.replace('__PAYLOAD__',payload))
    (target/'README.md').write_text('''# M2.3.6 local human review

Open [review.html](review.html) directly in a browser. Frames use relative links
to the existing battle cache; keep this directory and `.cache/battles/` in place.
No server, network, OCR, or video decoding is required. Use the selector and
arrow buttons to inspect every acquired frame, including frames without HUDs.
The Preview tab shows all 24 automatic row observations and raw candidates.
HUD crop boxes refer to UI cards, never to rendered 3D models. Logical slots
follow the fixed UI layout; biological continuity remains unproven.

Annotations are saved in browser storage and exported/imported with JSON buttons.
They are separate review notes. Import never changes frozen labels or runtime
outputs. Reopen exported notes in another browser using Import annotations.

Regenerate from compatible cached observations:
`.venv/bin/python scripts/evaluate_m236.py --split all`
''')
    print('Viewer:',target/'review.html',flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--split',choices=['development','held_out','all'],required=True)
    args=parser.parse_args();splits=['development','held_out'] if args.split=='all' else [args.split]
    manifest=P/'stages/evaluation.json';atomic_json(manifest,dict(status='running',evaluator=sha(__file__),splits=splits))
    try:
        evaluations=[evaluate(s) for s in splits]
        if args.split=='all':
            atomic_json(P/'historical-regressions.json',historical_regressions())
            viewer(evaluations)
        atomic_json(manifest,dict(status='complete',evaluator=sha(__file__),splits=splits))
    except Exception as exc:
        atomic_json(manifest,dict(status='error',error=repr(exc),resume=f'.venv/bin/python scripts/evaluate_m236.py --split {args.split}'));raise


if __name__=='__main__':main()
