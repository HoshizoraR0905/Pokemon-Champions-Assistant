"""Evaluate saved OCR and parsers against reviewed labels, without recognition."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_events.parser import EventParser
from recognition.video_sampling import atomic_json


def run():
    fixture=json.loads((ROOT/'tests/fixtures/battles/m233b2_messages.json').read_text())
    recovery=json.loads((ROOT/'.cache/m233b2/recovery.json').read_text())['results']
    scores=dict(total=len(fixture['frames']),baseline_pattern_correct=0,b2_pattern_correct=0,
        move_examples=0,baseline_move_correct=0,b2_move_correct=0,false_canonical_assignments=0,results=[])
    for i,r in enumerate(fixture['frames']):
        # Labels are read only for scoring; recognition inputs come from raw OCR.
        alts=[a for a in recovery if a['source_sha256']==r['source_sha256'] and a['battle_id']==r['battle_id']]
        e=EventParser().parse(dict(entry_id=str(i),raw_text=r['raw_text'],ocr_confidence=r['ocr_confidence'],move_ocr_alternatives=alts))
        move=(e.canonical_references.get('move') or {}).get('canonical_id')
        scores['baseline_pattern_correct']+=r['baseline_type']==r['expected_type']
        scores['b2_pattern_correct']+=e.event_type==r['expected_type']
        if r['expected_move']:
            scores['move_examples']+=1;scores['baseline_move_correct']+=r['baseline_move']==r['expected_move'];scores['b2_move_correct']+=move==r['expected_move']
        scores['false_canonical_assignments']+=bool(move and move!=r['expected_move'])
        scores['results'].append(dict(index=i,type=e.event_type,move=move,uncertainty=e.uncertainty))
    atomic_json(ROOT/'.cache/m233b2/evaluation.json',scores)
    print({k:v for k,v in scores.items() if k!='results'})
    return scores
if __name__=='__main__':run()
