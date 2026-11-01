"""Frozen B24 predictions against separately sealed source-pixel reference."""
import json,re
from pathlib import Path
from difflib import SequenceMatcher
from collections import Counter
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.evaluate_b24 import OWNER,RUN,SOURCE,EVAL,verify,read,sha
from recognition.video_sampling import atomic_json
from battle_events.parser import EventParser
from recognition.log_comparison import compact,align
from battle_evidence.constraint_trace import ACCEPTED

def main():
    verify();reference=OWNER.input('b24-battle-log-reference-20261101.json');seal=read(reference.with_name('b24-battle-log-reference-seal-20261101.json'));assert sha(reference)==seal['sha256']
    rows=read(reference)['rows'];parser=EventParser();entries=[];events=[];hp=[]
    for row in rows:
        match=re.fullmatch(r'(.+?) HP (\d+)(%)? → (\d+)(%)?',row['text'])
        if match:
            hp.append(dict(row,species=match[1],before=int(match[2]),after=int(match[4]),unit='displayed_percent' if match[3] else 'absolute'));continue
        entry=dict(entry_id=row['reference_id'],raw_text=row['text'],ocr_confidence=1.,source_id=row['sources'][0]['source_id'],turn=row['turn'],log_order=row['segment_order'],partial=False,observation_ids=[row['reference_id']])
        event=parser.parse(entry,battle_id=OWNER.battle_id).to_dict();entries.append(entry);events.append(event)
    production=read(SOURCE/'replay.json');records=production['history'];byid={r['event']['event_id']:r for r in records}
    predictions=[r.get('bindings',{}).get('resolved_event') or r['event'] for r in records]
    comparisons=align(entries,events,predictions)
    matches=[]
    for entry,event,c in zip(entries,events,comparisons['comparisons']):
        pred=c['prediction'];record=byid.get(pred['event_id']) if pred else None
        # Literal coverage is separate from parser routing and semantic matching.
        raw=sorted(((SequenceMatcher(None,compact(entry['raw_text']),compact(p['original_text'])).ratio(),p) for p in predictions if p['event_type'] not in {'hud_observation','preview_observation','entry_observation','coverage_observation','phase_observation'}),key=lambda x:x[0],reverse=True)
        best=raw[0] if raw else (0,None)
        matches.append(dict(reference_id=entry['entry_id'],turn=entry['turn'],text=entry['raw_text'],reference_event=event,
            semantic_match=c,receipt_status=record.get('application_status') if record else None,
            raw_text_best=dict(score=best[0],event_id=best[1]['event_id'] if best[1] else None,text=best[1]['original_text'] if best[1] else None),
            confirmed_after_review=False))
    out=EVAL/'reference-comparison';out.mkdir(exist_ok=True)
    atomic_json(out/'automatic-alignment.json',dict(reference_sha256=sha(reference),matches=matches,hp_reference_pairs=hp,
        status='provisional_alignment_requires_source_review',scope='119 independently source-transcribed rows; HP and message denominators kept separate',
        counts=dict(reference_rows=len(rows),message_or_semantic_rows=len(entries),HP_endpoint_pairs=len(hp),alignment_statuses=dict(Counter(c['status'] for c in comparisons['comparisons'])))))
    print('Rows',len(rows),'semantic',len(entries),'HP',len(hp))
    for m in matches:
        c=m['semantic_match'];p=c['prediction'];print(m['reference_id'],m['text'],'=>',c['status'],m['receipt_status'],p['event_id'] if p else '',p['original_text'].replace('\n','/') if p else '', 'raw',round(m['raw_text_best']['score'],2))
if __name__=='__main__':main()
