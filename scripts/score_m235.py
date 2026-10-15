"""Frozen-label evaluation; scoring never writes recognition inputs or runtime code."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.finalize_m235 import P,identity,revision_dir
from scripts.process_m235 import sha
from recognition.video_sampling import atomic_json
from battle_events.parser import EventParser


def measure(counter,expected,actual,attributed=True):
    """Only non-null reviewed facts enter the identification denominator."""
    if expected is None:
        counter['unknown_targets']+=1;counter['unsupported_admissions']+=actual is not None;return
    counter['facts']+=1
    if actual is None:counter['unresolved']+=1
    elif actual!=expected:counter['incorrect']+=1;counter['false_admissions']+=1
    elif attributed is None:counter['unresolved_attribution']+=1
    elif not attributed:counter['misattributed']+=1;counter['false_admissions']+=1
    else:counter['correct']+=1
    counter['identified']+=actual is not None


def metrics(c):
    d=dict(c);n=c['facts'];identified=c['identified']
    d.update(accuracy=c['correct']/n if n else None,coverage=identified/n if n else None,attributed_precision=c['correct']/identified if identified else None)
    return d


def score_variant(labels,observations,replay):
    rows={r['sha256']:r for r in observations['observations']};counts={k:Counter() for k in ['hud_species','hud_hp_reading','hud_hp_attributed','current_occupancy','visual_fields','visual_state_fields','message_pattern','move_identity','move_attribution','move_state_revelation','negative_admissions']};cases=[];groups={}
    for label in labels:
        row=rows[label['sha256']];time=row['timestamp'];projection=replay['projections'][str(time)];history=[r for r in replay['engine']['history'] if any(label['sha256'] in s['observation_ids'] for s in r['event']['evidence'])]
        case=dict(timestamp=time,occurrence_group=label['occurrence_group'],hud=[],visual=[],message=None)
        for gt in label['hud']:
            slot=('own' if gt['side']=='self' else 'opponent')+'_active_'+('1' if gt['slot']=='left' else '2')
            mon=next((m for m in row.get('snapshot',{}).get('pokemon',[]) if m['slot']==slot),{})
            res=(mon.get('species') or {}).get('resolution') or {};sid=res.get('species_id') if res.get('status')=='resolved' else None
            measure(counts['hud_species'],gt['species_id'],sid)
            hp=(mon.get('hp') or {}).get('value');expected_hp=gt['hp'];actual_hp=hp
            if 'percent' in expected_hp:expected_hp=expected_hp['percent']
            measure(counts['hud_hp_reading'],expected_hp,actual_hp)
            measure(counts['hud_hp_attributed'],expected_hp,actual_hp,attributed=sid==gt['species_id'] if sid is not None else None)
            occ=projection['occupancy'][gt['side']][gt['slot']];pid=occ['current_instance_id'];p=projection['pokemon'].get(pid,{})
            current_sid=(p.get('identity',{}).get('value') or {}).get('species_id') if pid else None
            measure(counts['current_occupancy'],gt['species_id'],current_sid)
            case['hud'].append(dict(side=gt['side'],slot=gt['slot'],species_id=sid,current_species_id=current_sid,hp=hp))
        for kind,key in [('panel','party_panel'),('popup','popup')]:
            gt=label.get(kind)
            visual=[r for r in history if r['event']['event_type']=='visual_observation' and r['event']['attributes']['source_kind']==('party_configuration_panel' if kind=='panel' else 'ability_popup')]
            if gt:
                parsed=row.get(key,{}).get('parsed') if kind=='panel' else next((p for p in row['visual']['parsed'] if p['kind']=='popup' and p.get('side')==gt['side']),None)
                if not parsed or parsed.get('status')!='supported':parsed={}
                expected={k:gt[k] for k in ['species_id','ability','item','hp'] if k in gt}
                receipt=next((r for r in visual if r['application_status'] not in {'deferred','rejected','retracted'}),None)
                actor=receipt['event']['actor'] if receipt else {};binding=receipt['bindings'].get('actor') if receipt else None
                attributed=bool(receipt and binding and actor.get('species_id')==gt['species_id'] and receipt['event']['side']==gt['side'])
                for field,value in expected.items():
                    actual=(parsed.get('species') or {}).get('species_id') if field=='species_id' else (parsed.get(field) or {}).get('canonical_id') if field in {'ability','item'} else parsed.get(field)
                    measure(counts['visual_fields'],value,actual)
                    fields=receipt['event']['attributes']['fields'] if receipt else {}
                    bound=actor.get('species_id') if field=='species_id' else (fields.get(field) or {}).get('canonical_id') if field in {'ability','item'} else fields.get(field)
                    measure(counts['visual_state_fields'],value,bound,attributed=attributed)
                    case['visual'].append(dict(kind=kind,field=field,expected=value,actual=actual,state=bound,attributed=attributed))
            else:
                counts['negative_admissions']['visual_negative_frames']+=1
                counts['negative_admissions']['false_visual_events']+=len(visual)
        gt=label.get('move_message');message=row.get('message') or {};alts=row.get('recovery',{}).get('alternatives',[])
        event=EventParser().parse(dict(entry_id='score:'+row['sha256'],raw_text=message.get('raw_text',''),ocr_confidence=message.get('confidence'),move_ocr_alternatives=alts))
        move=(event.canonical_references.get('move') or {}).get('canonical_id') if event.event_type=='move_execution' else None
        expected_move=gt.get('move') if gt else None
        if gt:
            measure(counts['message_pattern'],gt['event_type'],event.event_type if event.event_type!='unknown' else None)
        if expected_move:
            measure(counts['move_identity'],expected_move,move)
            actor_sid=(event.actor or {}).get('species_id')
            attribution=(event.side==gt['side'] and actor_sid==gt['actor_species_id']) if event.side in {'self','opponent'} and actor_sid is not None else None
            measure(counts['move_attribution'],expected_move,move,attributed=attribution)
            admitted=[]
            for r in history:
                e=r['bindings'].get('resolved_event',r['event'])
                if e['event_type']=='move_execution' and r['application_status'] not in {'deferred','rejected','retracted'} and r['bindings'].get('actor'):
                    admitted.append((e.get('canonical_references',{}).get('move') or {}).get('canonical_id'))
            measure(counts['move_state_revelation'],expected_move,admitted[0] if admitted else None)
            group=groups.setdefault(label['occurrence_group'],dict(expected=expected_move,recognized=False,attributed=False,revealed=False))
            group['recognized']|=move==expected_move;group['attributed']|=move==expected_move and attribution is True;group['revealed']|=expected_move in admitted
        elif label['negative_move_announcement']:
            counts['negative_admissions']['move_negative_frames']+=1;counts['negative_admissions']['false_move_identifications']+=move is not None
        if not label['hud']:
            counts['negative_admissions']['no_hud_frames']+=1
            counts['negative_admissions']['unsupported_current_slots']+=sum(bool(o['current_instance_id']) for side in projection['occupancy'].values() for o in side.values())
        case['message']=dict(type=event.event_type,move=move,side=event.side,actor=(event.actor or {}).get('species_id'));cases.append(case)
    return dict(frames=len(labels),metrics={k:metrics(v) if k!='negative_admissions' else dict(v) for k,v in counts.items()},move_occurrences=dict(total=len(groups),recognized=sum(g['recognized'] for g in groups.values()),attributed=sum(g['attributed'] for g in groups.values()),revealed=sum(g['revealed'] for g in groups.values())),cases=cases)


def run(split):
    target=revision_dir();seal_path=P/'implementation-seal.json'
    if split=='held_out':
        seal=json.loads(seal_path.read_text());assert seal['identity']==identity()
        assert all(sha(ROOT/k)==v for k,v in seal['outputs'].items())
        assert seal['evaluation_code_sha256']==sha(__file__)
    review=json.loads((P/'review-seal.json').read_text());assert sha(ROOT/review['fixture'])==review['sha256']
    labels=[r for r in json.loads((ROOT/review['fixture']).read_text())['examples'] if r['split']==split]
    result=dict(status='complete',split=split,implementation_identity=identity(),evaluation_code_sha256=sha(__file__),ocr_predictions=0,baseline=score_variant(labels,json.loads((P/'baseline-observations.json').read_text()),json.loads((P/'baseline-replay.json').read_text())),m235=score_variant(labels,json.loads((target/'observations.json').read_text()),json.loads((target/'replay.json').read_text())))
    output=target/(split+'-scores-'+sha(__file__)[:12]+'.json')
    if output.exists():assert json.loads(output.read_text())==result,'Scoring changed under frozen identity'
    else:atomic_json(output,result)
    print(json.dumps({k:{s:v[s] for s in ['frames','metrics','move_occurrences']} for k,v in result.items() if k in {'baseline','m235'}},indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--split',choices=['development','held_out'],required=True);run(p.parse_args().split)
