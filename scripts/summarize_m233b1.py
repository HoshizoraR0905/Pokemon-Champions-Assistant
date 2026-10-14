"""Summarize sealed scoped B1 experiments and manually reviewed labels; no OCR."""
import json
from pathlib import Path
import sys
from collections import Counter
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from knowledge import normalize
from recognition.message_selection import SelectionConfig
from recognition.video_sampling import atomic_json


def summarize():
    labels=json.loads((ROOT/'tests/fixtures/battles/m233b1_interval_labels.json').read_text())
    diagnostics=json.loads((ROOT/'tests/fixtures/battles/m233b1_selection_diagnostics.json').read_text())['frames']
    result=dict(diagnostic_composition=dict(Counter(r['label'] for r in diagnostics)),policies={},intervals={},recoveries=[],
        ocr=dict(new_read_calls=0,predicted_crops=0,inference_batches=0,inference_seconds=0.),peak_python_rss_bytes=0)
    for n in [0,1,2,4]:
        bid=f'sample_battle_{n}';raw=json.loads((ROOT/f'.cache/battles/{bid}/m233b1/experiment/results.json').read_text())
        for key in result['ocr']:result['ocr'][key]+=raw['ocr_counts'][key]
        result['peak_python_rss_bytes']=max(result['peak_python_rss_bytes'],raw['process_peak_rss_bytes'])
        for policy,entry in raw['diagnostic'].items():
            counts=result['policies'].setdefault(policy,dict(selected_by_label={},diagnostic_actual_new_calls=0))
            for k,v in entry['selected_by_label'].items():counts['selected_by_label'][k]=counts['selected_by_label'].get(k,0)+v
            counts['diagnostic_actual_new_calls']+=entry['actual_new_read_calls']
        for frame in raw['diagnostic']['hybrid']['selected']:
            if frame['label']!='visible_message':continue
            message=frame['message'];matched=normalize(frame['expected_token']) in normalize(message['raw_text'])
            result['recoveries'].append(dict(battle_id=bid,timestamp=frame['timestamp'],expected_token=frame['expected_token'],
                raw_text=message['raw_text'],confidence=message['confidence'],key_phrase_recovered=matched))
        if bid not in labels:continue
        lookup={r['sha256']:r for r in labels[bid]['frames']}
        acquired=json.loads((ROOT/f'.cache/battles/{bid}/m233b1/experiment/acquisition.json').read_text())
        intervals=result['intervals'].setdefault(bid,{})
        for rate,policies in raw['schedules'].items():
            source=acquired['schedules'][rate];visible=[lookup[x['sha256']] for x in source if lookup[x['sha256']]['label']=='visible_message']
            row=dict(frames_acquired=len(source),visible_frames=len(visible),visible_occurrences=len({x['occurrence'] for x in visible}),
                acquisition_seconds=acquired['acquisition_seconds'][rate],policies={})
            for policy,entry in policies.items():
                selected=[lookup[x['sha256']] for x in entry['selection'] if x['selected']]
                positives=[x for x in selected if x['label']=='visible_message']
                occurrences={x['occurrence'] for x in positives}
                recovered={lookup[x['sha256']]['occurrence'] for x in entry['messages']
                    if lookup[x['sha256']]['label']=='visible_message' and normalize(lookup[x['sha256']]['expected_token']) in normalize(x['message']['raw_text'])}
                row['policies'][policy]=dict(candidates=entry['ocr_candidates'],selected_visible_frames=len(positives),
                    occurrences_selected=len(occurrences),occurrences_key_phrase_readable=len(recovered),
                    false_positive_selections=sum(x['label']=='no_message' for x in selected),
                    ambiguous_fade_selections=sum(x['label']=='ambiguous_fade' for x in selected),
                    repeated_occurrence_selections=len(positives)-len(occurrences),
                    duplicate_identical_crop_requests=entry['duplicated_crop_requests'],unique_crop_requests=entry['unique_crop_requests'],
                    actual_new_read_calls=entry['actual_new_read_calls'],selection_seconds=entry['selection_seconds'],ocr_wall_seconds=entry['ocr_wall_seconds'])
            intervals[rate]=row
    result['recommended_selection']=asdict(SelectionConfig())
    result['repeated_frame_controls']=json.loads((ROOT/'.cache/m233b1-repeat-probe.json').read_text())
    result['measurement_limits']=['Purposive inspected intervals only; no full-battle recall/accuracy.',
        'Actual new calls are allocated by sequential evaluation order and cache sharing, not independent cold-policy cost.',
        'Peak RSS is Python process high-water mark; FFmpeg child RSS unmeasured.',
        'Key-phrase recovery is weaker than complete correct actor/move text.']
    atomic_json(ROOT/'reports/M2.3.3-B1-validation.json',result)
    return result

if __name__=='__main__':
    r=summarize();print(json.dumps(dict(ocr=r['ocr'],recovered=sum(x['key_phrase_recovered'] for x in r['recoveries']),positives=len(r['recoveries']))))
