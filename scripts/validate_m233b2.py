"""Cache-only B2 audit, comparison and one-battle chronological replay."""
import argparse,collections,hashlib,json,re,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_events.parser import EventParser
from battle_events.schema import Evidence,stable_id
from recognition.video_sampling import atomic_json,fingerprint
from scripts.replay_m233a import replay
from scripts.benchmark_m233b1 import evaluation_key
from battle_artifacts import BattleArtifacts


def audit():
    groups=collections.defaultdict(list);totals=collections.Counter()
    for i in range(5):
        data=json.loads((ROOT/f'reports/battles/sample_battle_{i}/M2.3.3-A-events.json').read_text())
        for e in data['events']:
            if e['event_type']=='hud_observation':continue
            totals[e['event_type']]+=1
            if e['event_type']=='unknown':
                t=e['original_text']
                category=('mega_reaction_notice' if '起了反应' in t else 'item_removal' if '拍落了' in t else
                    'stat_restoration_item' if '复原了能力' in t else 'unsupported_trick_room' if '扭曲了时空' in t else
                    'ability_ui_without_actor' if '特性' in t else 'other_ambiguous_or_unsupported' if len(re.findall('[\u4e00-\u9fff]',t))>=4 else 'short_corrupt_or_irrelevant_ui')
                groups[category].append(dict(battle_id=data['battle_id'],text=t,event_id=e['event_id']))
    atomic_json(ROOT/'.cache/m233b2/audit.json',dict(type_counts=totals,unknown_groups=groups))
    print('Audit:',dict(totals),'unknown groups:',{k:len(v) for k,v in groups.items()})


def validate(bid):
    source=ROOT/f'reports/battles/{bid}/M2.3.3-A-events.json'
    recovery_path=ROOT/'.cache/m233b2/recovery.json'
    inputs=[source,recovery_path,ROOT/'battle_events/parser.py',ROOT/'recognition/move_resolution.py',
        ROOT/'tracking/evidence_fusion.py',ROOT/'tracking/state_engine.py',ROOT/'tracking/hidden_state.py',Path(__file__)]
    for name in ['results.json','results-manifest.json']:
        p=ROOT/f'.cache/battles/{bid}/m233b1/experiment/{name}'
        if p.exists():inputs.append(p)
    inputs += [ROOT/'tests/fixtures/battles/m233b1_selection_diagnostics.json',ROOT/'knowledge/data/manifest.json',
        ROOT/'scripts/replay_m233a.py',ROOT/'scripts/benchmark_m233b1.py']
    key=fingerprint({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
    folder=ROOT/f'.cache/battles/{bid}/m233b2/replay';manifest=folder/'manifest.json'
    if manifest.exists():
        old=json.loads(manifest.read_text())
        if old.get('input_hash')==key and old.get('status')=='complete' and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in old['outputs'].items()):
            print(bid,'reused complete cached B2 replay');return
    atomic_json(manifest,dict(status='running',input_hash=key,battle_id=bid))
    try:
        events=json.loads(source.read_text())['events'];alternatives=json.loads(recovery_path.read_text())['results']
        for e in events:
            if e['event_type']=='hud_observation':continue
            hashes={oid for s in e['evidence'] for oid in s['observation_ids']}
            alts=[a for a in alternatives if a['battle_id']==bid and a['source_sha256'] in hashes]
            if alts:e['attributes']['move_ocr_alternatives']=alts
        # Import B1's final hybrid diagnostic and 2 FPS interval results only.
        b1=ROOT/f'.cache/battles/{bid}/m233b1/experiment/results.json'
        if b1.exists():
            p=BattleArtifacts(bid);m=json.loads((b1.parent/'results-manifest.json').read_text())
            assert m['input_hash']==evaluation_key(p) and m['output_sha256']==hashlib.sha256(b1.read_bytes()).hexdigest()
            d=json.loads(b1.read_text());rows=d['diagnostic']['hybrid']['selected'][:]
            if '2' in d['schedules']:rows+=d['schedules']['2']['hybrid']['messages']
            existing={oid for e in events for s in e['evidence'] for oid in s['observation_ids']}
            diagnostic=json.loads((ROOT/'tests/fixtures/battles/m233b1_selection_diagnostics.json').read_text())['frames']
            for row in rows:
                sha=row.get('sha256')
                if not sha:
                    refs=[r for r in diagnostic if r['battle_id']==bid and r['timestamp']==row['timestamp']]
                    if not refs:continue
                    sha=refs[0]['sha256']
                if sha in existing:continue
                existing.add(sha);message=row['message']
                e=EventParser().parse(dict(entry_id='b1:'+sha,source_id=bid+'#'+str(row['timestamp']),observation_ids=[sha],
                    raw_text=message['raw_text'],ocr_confidence=message['confidence']),battle_id=bid)
                e.evidence[0].source_type='cached_b1_message';e.evidence[0].details.update(timestamp=row['timestamp'],ocr_key=message.get('ocr_key'))
                e.attributes.update(fusion_context=True,observation_time=row['timestamp'])
                events.append(e.to_dict())
        events.sort(key=lambda e:(e['attributes']['observation_time'],0 if e['event_type']=='hud_observation' else 1,e['event_id']))
        for i,e in enumerate(events,1):e['attributes']['sequence']=i
        envelope,hidden,_=replay(events,bid)
        records=[]
        for r in envelope['history']:
            e=r['bindings'].get('resolved_event',r['event'])
            if e['event_type']=='hud_observation':continue
            records.append(dict(event_id=e['event_id'],text=e['original_text'],type=e['event_type'],
                status=r['application_status'],reason=r['reason'],binding=r['bindings'].get('actor'),
                references=e['canonical_references'],attributes=e['attributes']))
        summary=dict(battle_id=bid,status_counts=dict(collections.Counter(r['status'] for r in records)),
            known_type=sum(r['type']!='unknown' for r in records),bound=sum(bool(r['binding']) for r in records),records=records)
        outputs=[]
        for name,data in [('state',envelope),('hidden',hidden),('summary',summary)]:
            p=folder/(name+'.json');atomic_json(p,data);outputs.append(p)
        atomic_json(manifest,dict(status='complete',input_hash=key,battle_id=bid,outputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in outputs}))
        print(bid,summary['status_counts'],'bound',summary['bound'])
    except Exception as exc:
        atomic_json(manifest,dict(status='failed',input_hash=key,error=f'{type(exc).__name__}: {exc}'));raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--battle-id',choices=[f'sample_battle_{i}' for i in range(5)]);ap.add_argument('--audit',action='store_true');args=ap.parse_args()
    if args.audit:audit()
    if args.battle_id:validate(args.battle_id)
    if not args.audit and not args.battle_id:ap.error('Select --audit or one --battle-id')
