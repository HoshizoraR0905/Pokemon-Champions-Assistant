"""Summarize frozen C measurements; no video, recognition or inference updates."""
import collections,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from recognition.video_sampling import atomic_json
from scripts.evaluate_m233c import classify


def main():
    labels=json.loads((ROOT/'tests/fixtures/battles/m233c_semantic_review.json').read_text());data=json.loads((ROOT/'.cache/m233c/results.json').read_text());summary=dict(intervals=[],battles={},supplemental=[])
    for interval in data['intervals']:
        bid=interval['battle_id'];m=interval['performance'];ref=json.loads((ROOT/f'.cache/battles/{bid}/m233c/reference.json').read_text())
        summary['intervals'].append(dict(battle_id=bid,occurrences=interval['occurrences'],captured=interval['captured'],selected=interval['selected'],correct_text=interval['correct_text'],correct_type=interval['correct_type'],correct_moves=interval['correct_move'],move_denominator=interval['move_denominator'],false_positive_selections=interval['scores'].get('false_positive_selections',0),false_move_assignments=interval['scores'].get('false_move_assignments',0),acquisition_seconds=m['acquisition_seconds'],selection_seconds=m['selection_seconds'],ocr=m['ocr_counts'],rss_bytes=m['process_peak_rss_bytes'],reference_seconds=ref['seconds'],policies=interval['policy_occurrences']))
    for bid,b in data['battles'].items():
        hud=[q for q in labels['hud_checkpoints'] if q['battle_id']==bid];es=json.loads((ROOT/f'reports/battles/{bid}/M2.3.3-A-events.json').read_text())['events'];direct=[]
        for q in hud:
            rows=[e for e in es if e['event_type']=='hud_observation' and q['sha256'] in e['evidence'][0]['observation_ids']]
            for slot in q['slots']:
                event=next((r for r in rows if r['side']==slot['side'] and r['attributes']['slot']==slot['slot']),None)
                if not event:direct.append(dict(identity='unmeasured_no_cached_ocr',hp='unmeasured_no_cached_ocr'));continue
                s=event['attributes']['species'];v=event['attributes']['hp'].get('value');observed_sid=(s.get('resolution') or {}).get('species_id')
                expected=slot['hp']['percent'] if 'percent' in slot['hp'] else slot['hp']
                direct.append(dict(identity=classify(observed_sid,slot['species_id']),hp=classify(v,expected),side=slot['side']))
        mode_counts={mode:{metric:dict(collections.Counter(r[metric] for q in qs for r in q['slots'])) for metric in ['identity','hp','attributed_hp']} for mode,qs in b['scores'].items() if mode!='current_persistence'}
        later=b['scores']['current_persistence'][-1] if len(hud)>1 else None
        summary['battles'][bid]=dict(hud_checkpoints=len(hud),direct={m:dict(collections.Counter(r[m] for r in direct)) for m in ['identity','hp']},prefixes=mode_counts,later_persistence={m:dict(collections.Counter(r[m] for r in later['slots'])) for m in ['identity','attributed_hp']} if later else 'unmeasured_only_one_checkpoint',replay_cost=b['replay_cost'])
    for q in labels['supplemental']:
        d=json.loads((ROOT/f'.cache/battles/{q["battle_id"]}/m233c/replay-current.json').read_text())['prefixes'][str(q['timestamp'])];state=d['state'];results=[]
        for f in q['facts']:
            mons=[p for p in state['pokemon'].values() if p['side_id']==f.get('side') and (p['species'].get('value') or {}).get('species_id')==f.get('species_id')]
            mon=mons[-1] if mons else None;observed=None;expected=f.get('name',f.get('value'));kind=f['kind']
            if kind=='field':
                if f['name']=='rain':observed=state['weather']['kind']['value'] if state['weather']['active']['value'] else None
                elif f['name']=='grassy':observed=state['terrain']['kind']['value'] if state['terrain']['active']['value'] else None
                else:observed='aurora_veil' if any(s['conditions'].get('aurora_veil',{}).get('active',{}).get('value') for s in state['sides'].values()) else None
            elif mon:
                if kind=='ability':observed=(mon['ability']['current']['value'] or {}).get('name')
                elif kind=='item':observed=(mon['item']['identity']['value'] or {}).get('name')
                elif kind=='form':observed=(mon['current_variant']['value'] or {}).get('name')
                elif kind=='stat_stage':observed=mon['stages'][f['stat']]['value']['value']
                elif kind=='hp':observed=[mon['hp']['current']['value'],mon['hp']['maximum']['value']];expected=[f['current'],f['maximum']]
                elif kind=='stat_direction':
                    changes=mon['stages'][f['stat']]['changes'];observed=changes[-1]['change'] if changes else None;expected='increment'
            results.append(dict(fact=f,actual=observed,result=classify(observed,expected)))
        summary['supplemental'].append(dict(battle_id=q['battle_id'],timestamp=q['timestamp'],independence=q['independence'],comparison='prefix before independently reviewed observation',results=results))
    atomic_json(ROOT/'.cache/m233c/summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
