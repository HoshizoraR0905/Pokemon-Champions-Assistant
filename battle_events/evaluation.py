"""Reference-only scoring, independent of recognition and parser decisions."""
import unicodedata
from recognition.battle_log import compact


def fraction(correct,total):return {'correct':correct,'total':total,'accuracy':correct/total if total else None}

def vertical_iou(a,b):
    overlap=max(0,min(a[3],b[3])-max(a[1],b[1]))
    return overlap/max(1,max(a[3],b[3])-min(a[1],b[1]))


def evaluate(raw,result,truth):
    expected={e['order']:e for e in truth['events']};viewtruth={v['timestamp']:v for v in truth['views']}
    obs_to_order={};raw_mismatches=[];occurrences=[];unmatched=[]
    for view in raw['views']:
        annotations=viewtruth.get(view['timestamp'],{}).get('rows',[])
        for obs in view['observations']:
            candidates=[r for r in annotations if vertical_iou(obs['box'],r['box'])>=.8]
            if len(candidates)!=1:
                unmatched.append(obs['observation_id']);continue
            label=candidates[0];order=label['order'];obs_to_order[obs['observation_id']]=order
            exact=compact(obs['raw_text'])==compact(expected[order]['raw_text'])
            occurrences.append({'observation_id':obs['observation_id'],'reference_order':order,'exact':exact,'readability':label['readability']})
            if not exact:raw_mismatches.append({'observation_id':obs['observation_id'],'reference_order':order,'timestamp':view['timestamp'],
                'expected_text':expected[order]['raw_text'],'actual_text':obs['raw_text'],'ocr_confidence':obs['ocr_confidence'],
                'readability':label['readability'],'selected':any(e['selected_observation_id']==obs['observation_id'] for e in result['entries'])})
    mapping=[obs_to_order.get(e['selected_observation_id']) for e in result['entries']]
    recovered=set(mapping)-{None};pairs=[(a,b) for i,a in enumerate(mapping) for b in mapping[i+1:] if a and b]
    comparisons=[];fields={k:[0,0] for k in ['event_type','actor','target','side','canonical_identity','attributes']}
    text_exact=0;nfkc_exact=0;unresolved=[];incorrect=[]
    for entry,event,order in zip(result['entries'],result['event_candidates'],mapping):
        if order is None:continue
        want=expected[order];errors=[]
        exact=compact(entry['raw_text'])==compact(want['raw_text']);text_exact+=exact
        nfkc=unicodedata.normalize('NFKC',compact(entry['raw_text']))==unicodedata.normalize('NFKC',compact(want['raw_text']));nfkc_exact+=nfkc
        def score(field,prediction,reference,eligible=True):
            if not eligible:return
            fields[field][1]+=1;correct=prediction==reference;fields[field][0]+=correct
            if not correct:
                error={'order':order,'field':field,'expected':reference,'actual':prediction}
                errors.append(error);(unresolved if prediction is None or prediction=='unknown' else incorrect).append(error)
        score('event_type',event['event_type'],want['event_type']);score('side',event['side'],want['side'])
        for role in ('actor','target'):
            predicted=event[role]['canonical_id'] if event[role] else None
            score(role,predicted,want[role],want[role] is not None)
            score('canonical_identity',predicted,want[role],want[role] is not None)
            if want[role] is None and predicted is not None:
                error={'order':order,'field':role,'expected':None,'actual':predicted};errors.append(error);incorrect.append(error)
        for kind,ref in want['canonical_references'].items():
            predicted=(event['canonical_references'].get(kind) or {}).get('canonical_id')
            score('canonical_identity',predicted,ref)
        for k,value in want['attributes'].items():
            pred=event['attributes'].get(k)
            if k=='stats':pred=sorted(pred or []);value=sorted(value)
            score('attributes',pred,value)
        comparisons.append({'reference_order':order,'event_id':event['event_id'],'ocr_exact':exact,'nfkc_exact':nfkc,'field_errors':errors,'uncertainty':event['uncertainty']})
    detected={v['timestamp'] for v in raw['views'] if v['detected']};positive=set(truth['expected_ui_timestamps']);negative=set(truth['expected_no_ui_timestamps'])
    readable=[r for r in occurrences if r['readability']=='readable']
    return {'matching_method':'manual viewport row geometry (vertical IoU >= 0.8), no OCR/reference text used for matching',
        'ui_detection':{'true_positives':len(detected&positive),'false_positives':len(detected&negative),'false_negatives':len(positive-detected),'true_negatives':len(negative-detected)},
        'entry_detection_recall':fraction(len(recovered),len(expected)),
        'entry_false_positives':len(mapping)-len(recovered),'unmatched_observations':unmatched,
        'readable_row_detection_recall':fraction(len(readable),sum(len(v['rows']) for v in truth['views'] if not v['overlay'])),
        'ocr_exact_text':fraction(text_exact,len(expected)),
        'ocr_nfkc_text':fraction(nfkc_exact,len(expected)),
        'ocr_readable_occurrence_exact':fraction(sum(r['exact'] for r in readable),len(readable)),
        'chronological_order':{'ordered_reference_ids':mapping,'exact_sequence':mapping==list(expected),
            'correct_positions':sum(a==i for i,a in enumerate(mapping,1)),'pairwise':fraction(sum(a<b for a,b in pairs),len(pairs))},
        'fields':{k:fraction(*v) for k,v in fields.items()},'unresolved_fields':unresolved,'incorrect_fields':incorrect,
        'comparisons':comparisons,'raw_ocr_mismatches':raw_mismatches,
        'limitations':['One development battle, no holdout.','Actor and target scores count eligible non-null reference fields; spurious fields reported separately.',
            'Canonical accuracy scores species identifiers and named move/ability/item references; unobserved forms are not guessed.',
            'Whitespace ignored for exact OCR; punctuation retained. NFKC score is separate.',
            'Video evidence is attached only after scoring via manual reference mapping; never used for OCR or parsing.']}
