"""Render an event-centered M2.3.6 review from frozen cached results only.

No recognition imports, replay, scoring, decoding, or fixture writes. Reviewed
occurrences and presentation-only intervals have separate denominator semantics.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
CACHE = ROOT / '.cache/battles/sample_battle_5/m236'
TARGET = ROOT / 'reports/M2.3.6-review'
TEMPLATE = ROOT / 'scripts/templates/m236_event_review.html'
TITLES = {
    'initial_opponent_entry': 'Initial opponent entry', 'initial_own_entry': 'Initial player entry',
    'own_reentry_candidate': 'Player entry / possible re-entry', 'mega_item': 'Mega Stone reaction notice',
    'mega_revelation': 'Big Mom’s Mega Evolution revelation', 'fake_out': 'Fake Out — identified and attributed',
    'not_effective': 'Not very effective — target context unresolved', 'two_hits': 'Two-hit notice',
    'flinch': 'Flinch — readable message without event semantics', 'coaching': 'Coaching — move text not recovered',
    'coaching_stages': 'Attack and Defense increased',
}
REASONS = {
    'low_ocr_confidence': 'OCR confidence was below the admission threshold. No semantic event was admitted.',
    'unresolved_candidate_fields': 'Required identity, side, move or effect information was unresolved; state mutation was withheld.',
    'move_revelation_only': 'Actor and executed move were supported. Targets and move effects were not established.',
    'move_actor_not_bound_to_observed_prefix': 'The move actor could not be bound using earlier observed evidence.',
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def receipt(record):
    event = record['bindings'].get('resolved_event', record['event'])
    status = record['application_status']
    alias_accepted=(record['bindings'].get('alias') or {}).get('status')=='accepted'
    unplaced_entry=(status=='recorded_observation' and event['event_type']=='send_out'
                    and bool(record['bindings'].get('actor')))
    admitted=status.startswith('applied') or alias_accepted or unplaced_entry
    outcome=('Nickname/species association accepted; active slot remains unresolved.' if alias_accepted else
             'Named arrival recorded as an unplaced episode; active slot and continuity remain unresolved.' if unplaced_entry else
             'Admitted to Battle State' if admitted else
             'Evidence retained only; no semantic state change' if status=='recorded_observation' else
             'Rejected / left unresolved; no semantic state change')
    return dict(id=record['event']['event_id'], timestamp=record['event']['attributes']['observation_time'],
                kind=event['event_type'], raw_text=record['event']['original_text'], status=status,
                admitted=admitted, outcome=outcome,
                reason=REASONS.get(record.get('reason'), record.get('reason') or
                    ('Only named identity is supported; placement and biological continuity are not established.' if alias_accepted or unplaced_entry else
                     'The supported observation passed the existing state policy.' if admitted else
                     'Stored as an observation; this does not establish an active slot or a mechanical effect.')),
                actor=event.get('actor'), target=event.get('target'),
                references=event['canonical_references'], uncertainty=event.get('uncertainty',[]),
                attributes={k:v for k,v in event['attributes'].items() if k in
                    {'effect','hits','stats','direction','stages','mechanic','binding_basis'}},
                evidence=event.get('evidence',[]))


def event_priority(occurrence):
    if occurrence['label']['kind']=='move_execution':
        if not occurrence['canonical_recognized']:return 2, 'Actual recognition failure'
        if not occurrence['actor_bound_correct']:return 3, 'Conservative unresolved actor'
    if not occurrence['canonical_recognized']:return 6, 'Missing event semantics'
    if not occurrence['admitted']:return 6, 'Conservative unresolved state'
    return 8, 'Supported occurrence'


def build(evaluations, history, seed):
    frames=[]
    receipts=[receipt(r) for r in history if r['event']['event_type'] not in {'preview_observation','coverage_observation'}]
    for evaluation in evaluations:
        for r in evaluation['frames']:
            mon=[]
            for p in r['snapshot']['pokemon']:
                icon=p.get('icon') or {}
                mon.append(dict(slot=p['slot'],species=p['species'],hp=p['hp'],
                    icon={**icon,'candidates':icon.get('candidates',[])[:5],
                          'independent_profiles':[{**v,'candidates':v.get('candidates',[])[:5]} for v in icon.get('independent_profiles',[])]}))
            frames.append(dict(id=r['sha256'],timestamp=r['timestamp'],split=r['split'],
                image=os.path.relpath(ROOT/r['image'],TARGET),message=r['message'],pokemon=mon,
                hud=r['reviewed_hud'],scheduling=r['scheduling'],entries=r.get('entry_windows',[]),
                occupancy={s:{k:dict(status=v['status'],current_instance_id=v['current_instance_id']) for k,v in slots.items()}
                           for s,slots in r['projection']['occupancy'].items()},
                receipts=[v for v in receipts if v['timestamp']==r['timestamp']],
                visibility_review=seed.get(r['sha256'])))
    frames.sort(key=lambda r:r['timestamp'])
    events=[];covered=set()
    def group(key,title,kind,split,rows,priority,category,question,**extra):
        if not rows:return
        rows=sorted(rows,key=lambda r:r['timestamp']);first,last=rows[0]['timestamp'],rows[-1]['timestamp']
        pool=[r for r in frames if r['split']==split]
        before=[r for r in pool if r['timestamp']<first];after=[r for r in pool if r['timestamp']>last]
        meaningful=[r for r in rows if any(v['admitted'] and v['kind']!='hud_observation' for v in r['receipts'])]
        seeded=[r for r in rows if r['visibility_review']]
        during=(seeded or meaningful or [rows[len(rows)//2]])[0]
        ids={r['id'] for r in rows}
        events.append(dict(id=key,title=title,kind=kind,split=split,start=first,end=last,
            frame_ids=[r['id'] for r in rows],representatives=dict(before=(before[-1] if before else rows[0])['id'],
            during=during['id'],after=(after[0] if after else rows[-1])['id']),priority=priority,category=category,
            question=question,receipts=[v for r in rows for v in r['receipts'] if
                (v['kind']=='hud_observation')==(kind in {'hud_hp','nickname'})],**extra))
        return ids
    for evaluation in evaluations:
        split=evaluation['split']
        for o in evaluation['occurrences']:
            label=o['label'];rows=[r for r in frames if r['split']==split and label['start']-.04<=r['timestamp']<=label['end']+.04]
            priority,category=event_priority(o)
            question=('Can you read the full move announcement? Enter the visible move and actor; leave the target unknown unless it is shown.'
                      if label['kind']=='move_execution' else
                      'Does the visible message support this event? Correct its text, actor or target, or choose Cannot determine.')
            covered.update(group('occurrence:'+label['id'],TITLES.get(label['id'],label['id']),label['kind'],split,rows,
                priority,category,question,reviewed_occurrence=True,review=o) or [])
        for window in sorted({tuple(r['window']) for r in evaluation['frames']}):
            rows=[r for r in frames if r['split']==split and window[0]<=r['timestamp']<window[1] and r['hud']]
            if rows:
                failed=any(not h['hp_current_correct'] for r in rows for h in r['hud'])
                wrong=any(h['current_wrong'] or h['admitted_wrong'] for r in rows for h in r['hud'])
                covered.update(group(f'hud:{split}:{window[0]}','Damage / HP observations' if split=='held_out' else 'HUD identities and HP after entry',
                    'hud_hp',split,rows,1 if wrong else 5 if failed else 8,
                    'Incorrect assertion' if wrong else 'Missing or unresolved HUD/HP' if failed else 'Supported observations',
                    'Is the HP value readable, and does it belong to this UI card? Enter the value and Pokémon; do not infer a damage cause.',
                    reviewed_occurrence=False) or [])
        names={h['label']['display_name'] for r in frames if r['split']==split for h in r['hud']
               if h['label']['side']=='opponent' and not h['current_correct']}
        for name in sorted(names):
            rows=[r for r in frames if r['split']==split and any(h['label']['display_name']==name and not h['current_correct'] for h in r['hud'])]
            group('nickname:'+split+':'+name,'Unresolved nickname: '+name,'nickname',split,rows,4,'Conservative unresolved identity',
                'Does the same HUD icon independently establish a species? Enter a species only if you can determine it; nickname text or roster membership alone is insufficient.',
                reviewed_occurrence=False,display_name=name)
    # Complement intervals are navigation groups, not inferred battle events or
    # ground-truth no-text labels. Low confidence alone never establishes no text.
    run=[]
    def background():
        if not run:return
        white=any(r['visibility_review'] and r['visibility_review']['classification']=='no_message' for r in run)
        group('interval:'+run[0]['id'],'Mega Evolution animation — no-text example' if white else 'Message visibility / transition interval',
            'background',run[0]['split'],run,7,'Reviewed rejected background noise' if white else 'Unclassified interval; optional review',
            'Is a battle message actually visible in this crop? Select No battle message visible for a blank frame. Rejected OCR noise is not a missed valid message.',
            reviewed_occurrence=False)
    for r in frames:
        if r['id'] in covered:
            background();run=[];continue
        if run and (run[-1]['split']!=r['split'] or r['timestamp']-run[-1]['timestamp']>.75):background();run=[]
        run.append(r)
    background()
    events.sort(key=lambda e:(e['priority'],e['start'],e['id']))
    return dict(schema='m236-event-review-data-v2',frames=frames,events=events,
        evaluations=[dict(split=e['split'],metrics=e['metrics'],occurrences=e['occurrences']) for e in evaluations],
        message_roi=[.22,.685,.64,.797])


def main():
    sources=[CACHE/f'{s}-evaluation.json' for s in ['development','held_out']]+[CACHE/'held_out-replay.json',
        ROOT/'tests/fixtures/battles/m236_review.json',CACHE/'implementation-seal.json',CACHE/'ocr-ledger.json',CACHE/'icon-ledger.json',
        CACHE/'development-observations.json',
        ROOT/'tests/fixtures/battles/m236_viewer_visibility.json']
    hashes={str(p.relative_to(ROOT)):digest(p) for p in sources}
    evaluations=[read(p) for p in sources[:2]]
    seeds=read(sources[-1])
    seal=read(CACHE/'implementation-seal.json')
    assert all(digest(ROOT/p)==h for p,h in seal['code'].items()),'Production code differs from the frozen evaluation'
    assert all(digest(ROOT/v['source_image'])==k for k,v in seeds['frames'].items()),'Visibility seed frame changed'
    known={r['sha256'] for e in evaluations for r in e['frames']}
    assert all(k in known for k in seeds['frames'])
    payload=build(evaluations,read(sources[2])['engine']['history'],seeds['frames'])
    preview=read(CACHE/'development-observations.json')['roster']
    for r in preview:r['evidence']['image']=os.path.relpath(ROOT/r['evidence']['image'],TARGET)
    payload['preview']=preview
    # Resolve presentation labels through the existing local identity database.
    # This reads pinned names only; it runs no recognition or mechanics inference.
    from knowledge import KnowledgeBase
    knowledge=KnowledgeBase()
    payload['species_names']={str(e.species_id):' / '.join(dict.fromkeys(
        n for n in [e.names.get('en'),e.names.get('zh-hans')] if n))
        for key,e in knowledge.entities.items() if key.startswith('pokeapi:species:')}
    TARGET.mkdir(parents=True,exist_ok=True)
    original=CACHE/'review-v1-preserved.html'
    if (TARGET/'review.html').exists() and not original.exists():original.write_bytes((TARGET/'review.html').read_bytes())
    data=json.dumps(payload,ensure_ascii=False).replace('<','\\u003c')
    (TARGET/'review.html').write_text(TEMPLATE.read_text().replace('__PAYLOAD__',data))
    assert all(digest(ROOT/p)==h for p,h in hashes.items()),'Review rendering modified frozen inputs'
    manifest=dict(status='complete',renderer_sha256=digest(__file__),template_sha256=digest(TEMPLATE),inputs=hashes,
        output_sha256=digest(TARGET/'review.html'),frames=len(payload['frames']),review_groups=len(payload['events']),
        reviewed_actual_occurrences=sum(len(e['occurrences']) for e in evaluations),new_ocr=0,new_video_processing=0,
        production_changes=False,review_annotations_modify_metrics=False,knowledge_snapshot=knowledge.snapshot_id)
    (CACHE/'review-v2-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k not in ['inputs']}))


if __name__=='__main__':main()
