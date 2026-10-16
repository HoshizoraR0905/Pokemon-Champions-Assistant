"""Existing-state replay, compact offline review and baseline comparison for fast runs."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from difflib import SequenceMatcher
import html
import json
import os
from pathlib import Path
import shutil
import time
from recognition.video_sampling import atomic_json
from recognition.fast_profile import VERSION


def fact_view(f):
    return dict(value=deepcopy(f.value),knowledge=f.knowledge,
                evidence=[{k:p[k] for k in ('event_id','source_id','kind','observation_ids') if k in p} for p in f.provenance])


def state_view(state):
    """Direct presentation projection. Authoritative state is serialized once."""
    return dict(active_slots={s:dict(v.active_slots) for s,v in state.sides.items()},
        pokemon={pid:dict(side=p.side_id,species=fact_view(p.species),variant=fact_view(p.current_variant),
            location=fact_view(p.location),hp={k:fact_view(getattr(p.hp,k)) for k in ['current','maximum','displayed_percent']},
            status=fact_view(p.major_status),fainted=fact_view(p.fainted),
            stages={k:fact_view(v.value) for k,v in p.stages.items()},
            ability=fact_view(p.ability.current),item=fact_view(p.item.identity),
            revealed_moves=[{k:v for k,v in m.items() if k in {'move_id','canonical_id','event_id','source_id','name'}} for m in p.moves.executed])
            for pid,p in state.pokemon.items()},weather=asdict(state.weather),terrain=asdict(state.terrain),
        unknown_policy='Unknown values remain unknown. Revealed membership does not establish equipped move slots.')


def canonical(receipt):
    return tuple(sorted((k,v.get('canonical_id')) for k,v in receipt.get('references',{}).items() if isinstance(v,dict)))


def compare_receipts(baseline,fast,tolerance=1.1):
    """One-to-one diagnostic alignment, not an accuracy judgment.

    Canonical fields must agree; literal evidence is required for non-move
    observations. Every unpaired baseline assertion remains in the report.
    """
    used=set();pairs=[];missing=[]
    for b in baseline:
        options=[]
        for i,f in enumerate(fast):
            if i in used or b['kind']!=f['kind'] or abs(b['timestamp']-f['timestamp'])>tolerance:continue
            if canonical(b)!=canonical(f):continue
            a=''.join(b.get('raw_text','').split());c=''.join(f.get('raw_text','').split())
            similarity=SequenceMatcher(None,a,c).ratio()
            if b['kind']!='move_execution' and similarity<.70:continue
            # Same move on another actor is a discrepancy, not a recovered event.
            ba=b.get('actor') or {};fa=f.get('actor') or {}
            if ba.get('species_id') and fa.get('species_id') and ba['species_id']!=fa['species_id']:continue
            options.append((abs(b['timestamp']-f['timestamp']),-similarity,i))
        if options:
            _,_,i=min(options);used.add(i);f=fast[i]
            pairs.append(dict(baseline_id=b['id'],fast_id=f['id'],baseline_time=b['timestamp'],fast_time=f['timestamp'],kind=b['kind'],
                baseline_admitted=b['admitted'],fast_admitted=f['admitted'],actor_equal=b.get('actor')==f.get('actor'),target_equal=b.get('target')==f.get('target')))
        else:missing.append(dict(b,comparison_status='no_equivalent_fast_assertion_within_tolerance',is_ground_truth_miss=False))
    return dict(tolerance_seconds=tolerance,matching='one-to-one, kind/canonical/literal/actor/time; baseline is not ground truth',
                pairs=pairs,baseline_only=missing,fast_only=[f for i,f in enumerate(fast) if i not in used])


def compare_occurrences(baseline,fast):
    used=set();out=[]
    for b in baseline:
        bt=max(b['observations'],key=lambda o:o['confidence'])['raw_text'];options=[]
        for i,f in enumerate(fast):
            if i in used or b['first_time']>f['last_time']+1.1 or f['first_time']>b['last_time']+1.1:continue
            ft=max(f['observations'],key=lambda o:o['confidence'])['raw_text']
            score=SequenceMatcher(None,''.join(bt.split()),''.join(ft.split())).ratio()
            if score>=.65:options.append((-score,abs(b['first_time']-f['first_time']),i))
        if options:
            _,_,i=min(options);used.add(i);f=fast[i]
            out.append(dict(baseline_id=b['id'],baseline_interval=[b['first_time'],b['last_time']],baseline_text=bt,
                fast_id=f['id'],fast_interval=[f['first_time'],f['last_time']],status='aligned_candidate',is_ground_truth=False))
        else:out.append(dict(baseline_id=b['id'],baseline_interval=[b['first_time'],b['last_time']],baseline_text=bt,
                fast_id=None,status='baseline_only_message_evidence',is_ground_truth=False))
    return dict(baseline_comparisons=out,fast_only_ids=[f['id'] for i,f in enumerate(fast) if i not in used])


def compare_regions(baseline_rows,fast_rows):
    """Keep all baseline banner, field and HP readings, including unreadable ones."""
    def records(rows):
        out=[]
        for row in rows:
            for mon in row.get('snapshot',{}).get('pokemon',[]):
                if '_active_' not in mon['slot']:continue
                out.append(dict(kind='hud',timestamp=row['timestamp'],source_id=row['source_id'],
                    key=mon['slot'],value=dict(name=mon['species'].get('raw_text'),hp=mon.get('hp',{}).get('value'))))
            for r in row.get('ui',{}).get('regions',[]):
                if r['region_type'] in {'field_indicator','ability_banner'} and r.get('ocr'):
                    out.append(dict(kind=r['region_type'],timestamp=row['timestamp'],source_id=row['source_id'],key=r['region_id'],
                        value=dict(canonical=r.get('canonical'),ocr=r['ocr'])))
        return out
    b=records(baseline_rows);f=records(fast_rows);comparisons=[]
    for evidence in b:
        options=[v for v in f if v['kind']==evidence['kind'] and v['key']==evidence['key'] and
                 v['timestamp']<=evidence['timestamp']+1.1 and v['timestamp']>=evidence['timestamp']-10 and v['value']==evidence['value']]
        match=max(options,key=lambda v:v['timestamp']) if options else None
        comparisons.append(dict(**evidence,fast_source_id=match['source_id'] if match else None,
            status='same_reading_nearby_or_retained' if match else 'baseline_only_or_changed_reading',is_ground_truth=False))
    return dict(comparisons=comparisons,fast_evidence=f,warning='Retained nearby readings are not independent repeat observations; all differing baseline values remain discrepancies.')


def reconstruct_and_package(paths,folder,report,rows,roster,occurrences):
    from scripts.report_m237 import causal_identity_events
    from recognition.visual_adapter import visual_events
    from tracking.battle_state import BattleState
    from tracking.state_engine import StateEngine,EventRecord,event_from_dict,ordering
    from scripts.build_m236_review import receipt
    began=time.monotonic();report.mkdir(parents=True,exist_ok=True)
    emitted={r['source_id'] for r in rows if r['occurrence_decision']['events']}
    events=causal_identity_events(rows,roster,emitted,paths.battle_id)
    for row in rows:
        for p in row['visual']['parsed']:
            if p['kind']!='detail':continue
            request=dict(battle_id=paths.battle_id,kind='detail',image=row['image'],sha256=row['sha256'],timestamp=row['timestamp'])
            events += [e.to_dict() for e in visual_events(dict(request=request,parsed=p,readings=row['visual']['readings'],identity=dict(layout=VERSION)),selection=row['visual'].get('selection'))]
    events.sort(key=lambda e:(e['attributes']['observation_time'],{'coverage_observation':0,'preview_observation':1,'hud_observation':2,'entry_observation':3,'alias_observation':4}.get(e['event_type'],5),e['event_id']))
    engine=StateEngine(BattleState(paths.battle_id,knowledge=dict(reliability_v1=True,reliability_v2=True,identity_v1=True)))
    for i,e in enumerate(events,1):
        e['attributes']['sequence']=i;engine.history.append(EventRecord(e,i,ordering(event_from_dict(e))))
    prefixes={'initial':state_view(engine.initial)}
    def capture(record,state):
        prefixes[str(record.event['attributes']['observation_time'])]=state_view(state)
        if record.delivery_index%100==0:print(f'Fast replay: {record.delivery_index}/{len(events)}',flush=True)
    engine.replay(snapshot_callback=capture)
    atomic_json(folder/'replay.json',engine.to_dict())
    receipts=[receipt(asdict(r)) for r in engine.history]
    for r,record in zip(receipts,engine.history):r['bindings']={k:v for k,v in record.bindings.items() if k!='resolved_event'}
    replay_seconds=time.monotonic()-began
    summary=dict(battle_id=paths.battle_id,profile=VERSION,video_duration=rows[-1]['timestamp'] if rows else 0,
        actual_event_occurrences_recovered=None,candidate_message_occurrences=len(occurrences),
        event_candidates=len(events),event_kinds=dict(Counter(e['event_type'] for e in events)),
        duplicate_event_ids={k:v for k,v in Counter(e['event_id'] for e in events).items() if v>1},
        receipt_statuses=dict(Counter(r['status'] for r in receipts)),
        canonical_move_candidates=sum(r['kind']=='move_execution' and bool(r['references'].get('move')) for r in receipts),
        bound_move_actors=sum(r['kind']=='move_execution' and bool(r['bindings'].get('actor',{}).get('pokemon_instance_id')) for r in receipts),
        bound_move_targets=sum(r['kind']=='move_execution' and bool(r['bindings'].get('target',{}).get('pokemon_instance_id')) for r in receipts),
        admitted_move_receipts=sum(r['kind']=='move_execution' and r['admitted'] for r in receipts),
        independent_reviewed_events=0,quality_acceptance='pending_independent_review',replay_seconds=replay_seconds)
    baseline=paths.cache('m237/baseline-observations.json');reconstruction=paths.cache('m237/reconstruction.json')
    comparison={}
    if baseline.exists() and reconstruction.exists():
        original=json.loads(baseline.read_text());base=json.loads(reconstruction.read_text())
        left=rows[0]['timestamp'] if rows else 0;right=rows[-1]['timestamp']+0.5 if rows else 0
        original['observations']=[r for r in original['observations'] if left<=r['timestamp']<right]
        original['occurrences']=[o for o in original['occurrences'] if o['last_time']>=left and o['first_time']<right]
        base['receipts']=[r for r in base['receipts'] if left<=r['timestamp']<right]
        summary['video_duration']=base['metrics']['video_duration']
        comparison=dict(interval_seconds=[left,right],baseline_is_ground_truth=False,independently_reviewed_events=0,
            receipts=compare_receipts(base['receipts'],receipts),occurrences=compare_occurrences(original['occurrences'],occurrences),
            region_evidence=compare_regions(original['observations'],rows),baseline_metrics=base['metrics'])
        atomic_json(report/'comparison.json',comparison)
        summary['baseline_message_occurrences']=len(original['occurrences'])
        summary['baseline_only_message_occurrences']=sum(r['fast_id'] is None for r in comparison['occurrences']['baseline_comparisons'])
        summary['baseline_only_assertions']=len(comparison['receipts']['baseline_only'])
        summary['baseline_only_move_assertions']=sum(r['kind']=='move_execution' for r in comparison['receipts']['baseline_only'])
        summary['baseline_canonical_move_candidates']=base['metrics']['automatic_canonical_move_references']
    atomic_json(report/'summary.json',summary);atomic_json(report/'receipts.json',receipts)
    assets=report/'assets';assets.mkdir(exist_ok=True)
    frames=[]
    for row in rows:
        source=paths.root/row['image'];target=assets/(row['sha256']+'.png')
        if not target.exists():
            try:os.link(source,target)
            except OSError:shutil.copy2(source,target)
        frames.append(dict(id=row['source_id'],timestamp=row['timestamp'],image='assets/'+target.name,phase=row['ui']['phase'],
            message=row['message'],regions=row['ui']['regions'],decisions=row['region_decisions'],
            unknown=row.get('unknown_fallback'),reuses=row.get('ocr_read_reuses',[])))
    # One inline data block works under file:// without network/fetch permissions.
    data=json.dumps(dict(summary=summary,frames=frames,receipts=receipts,occurrences=occurrences,prefixes=prefixes),ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
    template=(Path(__file__).resolve().parents[1]/'scripts/templates/fast_review.html').read_text()
    (report/'review.html').write_text(template.replace('__DATA__',data),encoding='utf-8')
    summary['packaging_and_comparison_seconds']=time.monotonic()-began-replay_seconds
    atomic_json(report/'summary.json',summary)
    return summary
