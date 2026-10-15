"""Independent, cache-only scoring. Labels never feed the reconstruction adapters."""
from collections import Counter
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_events.parser import EventParser
from recognition.visual_adapter import visual_events, selected_panel_side, move_alternatives
from recognition.video_sampling import atomic_json
from scripts.evaluate_m233c import compact


def score():
    import cv2
    rows=json.loads((ROOT/'.cache/m234/visual-results.json').read_text())['results']
    labels=json.loads((ROOT/'tests/fixtures/battles/m234_visual_review.json').read_text())['examples']
    move=Counter();popup=Counter();detail=Counter();cases=[]
    for label in labels:
        row=next(r for r in rows if r['request']['sha256']==label['sha256'] and r['request']['kind']==label['kind'])
        req=row['request'];expected=label['expected'];kind=req['kind'];p=row['parsed']
        if kind=='message':
            e=EventParser().parse(dict(entry_id=req['sha256'],raw_text=req['original_text'],ocr_confidence=.99,move_ocr_alternatives=move_alternatives(row)))
            actual=(e.canonical_references.get('move') or {}).get('canonical_id')
            if expected['canonical_move']:
                move['positive_frames']+=1;move['correct']+=actual==expected['canonical_move'];move['unresolved']+=actual is None
            else:move['negative_frames']+=1
            move['false_revelations']+=bool(actual and actual!=expected['canonical_move'])
            cases.append(dict(timestamp=req['timestamp'],kind=kind,expected=expected,actual=actual))
        else:
            selection=selected_panel_side(cv2.imread(str(ROOT/req['image']))) if kind=='detail' else None
            events=visual_events(row,selection=selection)
            counts=popup if kind=='popup' else detail
            if 'visual_events' in expected:
                counts['negative_frames']+=1;counts['false_events']+=len(events)
            else:
                counts['positive_frames']+=1;counts['events']+=len(events)
                for e in events:
                    counts['species_correct']+=e.actor['species_id']==expected['species_id']
                    counts['side_correct']+=e.side==expected['side']
                    fields=e.attributes['fields']
                    for name,value in expected.items():
                        if name in {'side','species_id'}:continue
                        if name in {'ability','item'}:actual=(fields.get(name) or {}).get('canonical_id')
                        elif name=='field':actual=sorted(fields.get('field',{}));value=sorted(value)
                        else:actual=fields.get(name)
                        counts[name+'_correct']+=actual==value
                        counts[name+'_unresolved']+=actual is None
            cases.append(dict(timestamp=req['timestamp'],kind=kind,expected=expected,event_count=len(events),selection=selection))
    # Same original C occurrence labels. Text recovery and canonical admission are
    # scored separately; low-confidence visually correct Protect text stays unbound.
    original=json.loads((ROOT/'tests/fixtures/battles/m233c_semantic_review.json').read_text())['intervals']
    text_good=set();move_good=set();positive=set();all_occurrences=set();false_moves=0
    for interval in original:
        for row in rows:
            if row['request']['kind']!='message' or row['request']['battle_id']!=interval['battle_id']:continue
            nearest=min(interval['frames'],key=lambda r:abs(r['timestamp']-row['request']['timestamp']))
            gt=next((o for o in interval['occurrences'] if o['occurrence_id']==nearest['occurrence_id']),None)
            if not gt:continue
            oid=gt['occurrence_id'];all_occurrences.add(oid)
            if gt['canonical_move']:positive.add(oid)
            native=''.join(readings[0]['text'] for readings in row['readings'].values() if readings)
            if compact(native)==compact(gt['expected_text']):text_good.add(oid)
            e=EventParser().parse(dict(entry_id='score',raw_text=row['request']['original_text'],move_ocr_alternatives=move_alternatives(row)))
            actual=(e.canonical_references.get('move') or {}).get('canonical_id')
            if gt['canonical_move'] and actual==gt['canonical_move']:move_good.add(oid)
            false_moves+=bool(actual and actual!=gt['canonical_move'])
    # Previously tuned B2 inputs remain a distinct regression population.
    old=json.loads((ROOT/'tests/fixtures/battles/m233b2_messages.json').read_text())['frames']
    reads=json.loads((ROOT/'.cache/m233b2/recovery.json').read_text())['results'];legacy=Counter()
    for i,r in enumerate(old):
        alts=[a for a in reads if a['source_sha256']==r['source_sha256'] and a['battle_id']==r['battle_id']]
        e=EventParser().parse(dict(entry_id=str(i),raw_text=r['raw_text'],ocr_confidence=r['ocr_confidence'],move_ocr_alternatives=alts))
        actual=(e.canonical_references.get('move') or {}).get('canonical_id')
        legacy['frames']+=1;legacy['pattern_correct']+=e.event_type==r['expected_type']
        legacy['move_examples']+=bool(r['expected_move']);legacy['move_correct']+=bool(r['expected_move'] and actual==r['expected_move'])
        legacy['false_moves']+=bool(actual and actual!=r['expected_move'])
    freshness=Counter();integration=[];opponent_expected={(i['battle_id'],o['canonical_move']) for i in original for o in i['occurrences'] if o['side']=='opponent' and o['canonical_move']};opponent_revealed=set()
    for i in range(5):
        bid=f'sample_battle_{i}'
        strict=json.loads((ROOT/f'.cache/battles/{bid}/m234/replay-strict.json').read_text())
        for entry in strict['scores']:
            projection=strict['prefixes'][str(entry['timestamp'])]['projection']
            for row in entry['rows']:
                o=projection['occupancy'][row['side']][row['slot']]
                freshness[o['status']]+=1
                freshness['supported_incorrect']+=bool(o['current_instance_id'] and row['identity']!='correct')
        d=json.loads((ROOT/f'.cache/battles/{bid}/m234/replay-augmented.json').read_text())
        for r in d['history']:
            if r['event_type']=='visual_observation':integration.append(dict(battle_id=bid,**r))
            e=r['bindings'].get('resolved_event',{})
            if r['status']=='applied_partial' and e.get('side')=='opponent' and r['bindings'].get('actor'):
                key=(bid,(e.get('canonical_references',{}).get('move') or {}).get('canonical_id'))
                if key in opponent_expected:opponent_revealed.add(key)
    result=dict(status='complete',ocr_calls=0,original_C_occurrences=dict(total=len(all_occurrences),text_correct=len(text_good),canonical_move_correct=len(move_good),move_denominator=len(positive),false_moves=false_moves),
        opponent_move_revelations=dict(correct=len(opponent_revealed),total=len(opponent_expected)),
        geometry_messages=dict(move),popup=dict(popup),detail=dict(detail),legacy_B2=dict(legacy),freshness=dict(freshness),integration=integration,cases=cases)
    assert not move['false_revelations'] and not popup['false_events'] and not detail['false_events']
    assert not freshness['supported_incorrect']
    atomic_json(ROOT/'.cache/m234/semantic-scores.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in {'cases','integration'}},indent=2));return result

if __name__=='__main__':score()
