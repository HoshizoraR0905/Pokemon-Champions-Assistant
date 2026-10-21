"""Read sealed M2.4 timings; write a separate investigation (no acquisition)."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from battle_artifacts import BattleArtifacts


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in path.open()]


def contains(parent, child):
    return parent['execution_start'] <= child['execution_start'] and child['execution_end'] <= parent['execution_end']


def run(owner, mode, inputs):
    run_id = f'm24-{mode}-final-v1'
    acquisition = owner.cache('event-driven/' + run_id)
    evaluation = owner.cache('evaluation/' + run_id)
    profile = evaluation / 'profiler/segment-0000'
    performance_path = owner.report('evaluation/' + run_id + '-m24/segment-performance.json')
    execution = read(evaluation / 'execution.json')
    # Verify measured bytes, without invoking recognition, replay, or exports.
    for root, identities in [(acquisition, execution['sealed_outputs']), (evaluation, execution['profile_outputs'])]:
        for name, sha in identities.items():
            path = root / name
            assert digest(path) == sha, path
            inputs[str(path.relative_to(ROOT))] = sha
    for path in [performance_path, acquisition / 'observations.json', profile / 'frames.jsonl', profile / 'operations.jsonl', profile / 'profiler.json']:
        inputs[str(path.relative_to(ROOT))] = digest(path)
    performance = read(performance_path)
    ops = lines(profile / 'operations.jsonl')
    frames = lines(profile / 'frames.jsonl')
    rows = {r['timestamp']: r for r in read(acquisition / 'observations.json')['observations']}
    segments = [s for s in performance['segments'] if s['phase'] == 'COMMAND_TIME']
    waits = sorted((o for o in ops if o['module'] == 'decode_sampling_wait' and o.get('source')), key=lambda o: o['execution_start'])
    assert len(waits) == len(frames)
    by_time = {f['timestamp']: f for f in frames}
    results = []
    for segment in segments:
        s = {k: segment[k] for k in ['index', 'start', 'end', 'video_duration_seconds', 'processing_wall_seconds', 'sampled_frames', 'inspected_frames']}
        selected = [o for o in ops if segment['start'] <= (o.get('source') or {}).get('timestamp', -1) < segment['end']]
        # Nested verification replays refer to OLD source frames. Keep those
        # source diagnostics separate from the original disjoint wall allocation.
        delayed = [o for o in selected if o['module'] in {'state_event', 'adapt_frame'} and o['purpose'] != 'development_identity_verification']
        partition = Counter()
        for o in selected:
            if o['module'] == 'decode_sampling_wait':
                partition['decode_sampling_wait'] += o['inclusive_seconds']
        for o in delayed:
            partition[o['module']] += o['inclusive_seconds']
        ocr = defaultdict(Counter)
        modules = defaultdict(Counter)
        scoped_ops = []
        for i, wait in enumerate(waits):
            t = wait['source']['timestamp']
            if not segment['start'] <= t < segment['end']:
                continue
            frame = by_time[t]
            end = waits[i+1]['execution_start'] if i+1 < len(waits) else float('inf')
            current = [o for o in ops if o['execution_start'] >= wait['execution_end'] and o['execution_end'] <= end and o['stage'] != 'postprocessing']
            # Last-frame issue cannot affect these COMMAND_TIME segments.
            assert i+1 < len(waits)
            scopes = []
            for o in current:
                label = o['module']
                if label in {'ui_detection', 'command_label_detection', 'inspection_schedule', 'w_detection', 'identity_verification', 'verification_prefix_reconstruction', 'ocr_read', 'ocr_predict', 'icon_identify', 'message_reading', 'hud_hp_reading', 'message_occurrences', 'trainer_acquisition'}:
                    scopes.append(o)
            roots = [o for o in scopes if not any(p is not o and contains(p, o) for p in scopes)]
            measured = 0.
            for o in roots:
                partition['frame_' + o['module']] += o['inclusive_seconds']
                measured += o['inclusive_seconds']
            assert frame['processing_wall_seconds'] >= measured
            partition['frame_unseparated_remainder'] += frame['processing_wall_seconds'] - measured
            partition['frame_wall_diagnostic_only'] += frame['processing_wall_seconds']
            scoped_ops.extend(current)
            for o in current:
                modules[o['module']]['calls'] += 1
                modules[o['module']]['inclusive_seconds'] += o['inclusive_seconds']
                modules[o['module']]['exclusive_seconds'] += o['exclusive_seconds']
                if o['module'] not in {'ocr_read', 'ocr_predict', 'ocr_inference'}:
                    continue
                parent = next((p for p in current if p['module'] == 'ocr_read' and contains(p, o)), None)
                p = parent or o
                purpose = p['purpose']
                if purpose == 'unclassified' and parent:
                    purpose = 'field_label' if parent['bounds'] == [269,27,393,57] else 'field_counter' if parent['bounds'] == [511,27,556,57] else 'command_countdown'
                elif purpose == 'unclassified':
                    visual = rows.get(t, {}).get('visual', {}).get('readings', {})
                    purpose = 'ability_banner_variants' if any(k.startswith('ability:') for k in visual) else 'detail_panel_variants' if visual else 'unclassified'
                key = o['module']
                ocr[purpose][key + '_calls'] += 1
                ocr[purpose][key + '_inclusive_seconds'] += o['inclusive_seconds']
                for k,v in o.get('counters', {}).items():
                    ocr[purpose][k] += v
        s['partition_seconds'] = dict(partition)
        actual_sum = sum(v for k,v in partition.items() if k != 'frame_wall_diagnostic_only')
        assert abs(actual_sum - s['processing_wall_seconds']) < 1e-8, (mode, s['index'], actual_sum, s['processing_wall_seconds'])
        s['frame_context_modules'] = dict(modules)
        s['ocr_purposes'] = dict(ocr)
        s['delayed_state_hash_seconds_subset'] = sum(o['inclusive_seconds'] for o in selected if o['module'] == 'state_hash' and o['purpose'] != 'development_identity_verification')
        s['source_attributed_verification_replay_seconds_excluded'] = {k: sum(o['inclusive_seconds'] for o in selected if o['module'] == k and o['purpose'] == 'development_identity_verification') for k in ['adapt_frame', 'state_event']}
        s['largest_measured_partition'] = max((k for k in partition if k != 'frame_wall_diagnostic_only'), key=partition.get)
        results.append(s)
    totals = Counter()
    for s in results:
        totals.update(s['partition_seconds'])
    prefix = [o for o in ops if o['module'] == 'verification_prefix_reconstruction']
    return dict(run_id=run_id, segments=results, partition_totals=dict(totals), video_seconds=sum(s['video_duration_seconds'] for s in results), wall_seconds=sum(s['processing_wall_seconds'] for s in results), full_run_verification_prefix_calls=len(prefix), full_run_verification_prefix_inclusive_seconds=sum(o['inclusive_seconds'] for o in prefix), full_run_profiler=read(profile/'profiler.json'))


def fmt(value):
    return f'{value:.6f}'


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---']*len(headers)) + ' |'] + ['| ' + ' | '.join(map(str,row)) + ' |' for row in rows]) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-id', required=True)
    args = parser.parse_args()
    from battle_artifacts import canonical_id
    audit_id = canonical_id(args.audit_id)
    owner = BattleArtifacts('sample_battle_9')
    folder = owner.cache('evaluation/' + audit_id)
    target = owner.report('M2.4-command-segment-tables-' + audit_id + '.md')
    if folder.exists() or target.exists():
        raise ValueError('Choose a new audit-id; existing evidence is never overwritten')
    inputs = {}
    results = {mode: run(owner, mode, inputs) for mode in ['lightweight', 'development']}
    inputs[str(Path(__file__).resolve().relative_to(ROOT))] = digest(Path(__file__))
    folder.mkdir(parents=True)
    (folder/'cost-audit.json').write_text(json.dumps(dict(inputs=inputs, modes=results), indent=2)+'\n')
    text = '# M2.4 COMMAND_TIME: complete segment tables\n\nGenerated from sealed measurements; times are seconds. See [audit explanation](M2.4-technical-investigation-v1.md) for boundaries, limitations and recommendations. Six decimals expose small costs, not measurement precision.\n\n'
    for mode,result in results.items():
        text += f'## {mode.capitalize()}\n\n'
        text += 'S/I = materialized candidate samples / inspected frames. Frame wall includes all acquisition work. Decode, Adapt and State are disjoint delayed allocations. Hash is a subset of State, never additive. Save/preprocessing/serialization are unseparated in the frame remainder below.\n\n'
        text += table(['ID','Video start–end','Video duration','Wall','S/I','Frame wall','Decode wait','Adapt','State','Hash subset'], [[s['index'],f"{s['start']:.6f}–{s['end']:.6f}",fmt(s['video_duration_seconds']),fmt(s['processing_wall_seconds']),f"{s['sampled_frames']}/{s['inspected_frames']}",fmt(s['partition_seconds']['frame_wall_diagnostic_only']),fmt(s['partition_seconds'].get('decode_sampling_wait',0)),fmt(s['partition_seconds'].get('adapt_frame',0)),fmt(s['partition_seconds'].get('state_event',0)),fmt(s['delayed_state_hash_seconds_subset'])] for s in result['segments']])
        text += '\nAcquisition component cells are calls / inclusive seconds. These scopes are disjoint here; OCR column sums top-level `ocr_read` and standalone `ocr_predict` roots. Message/HP wrappers and scheduling appear under Other measured. Verification includes its nested OCR/icon adapter work. Icon matching model calls are zero in every segment; cached icon adapter calls, if any, are inside verification.\n\n'
        rr=[]
        for s in result['segments']:
            p=s['partition_seconds'];m=s['frame_context_modules']
            def cell(k):return f"{int(m.get(k,{}).get('calls',0))} / {fmt(p.get('frame_'+k,0))}"
            keys=['ui_detection','command_label_detection','w_detection','identity_verification','verification_prefix_reconstruction','ocr_read','ocr_predict']
            other=sum(v for k,v in p.items() if k.startswith('frame_') and k not in {'frame_wall_diagnostic_only','frame_unseparated_remainder',*('frame_'+k for k in keys)})
            icon=m.get('icon_identify',{})
            rr.append([s['index'],cell('ui_detection'),cell('command_label_detection'),fmt(p.get('frame_ocr_read',0)+p.get('frame_ocr_predict',0)),cell('w_detection'),cell('identity_verification'),cell('verification_prefix_reconstruction'),f"{int(icon.get('calls',0))} / {fmt(icon.get('inclusive_seconds',0))}",fmt(other),fmt(p['frame_unseparated_remainder'])])
        text += table(['ID','UI','COMMAND label','OCR roots s','W CV','Dev verify','Dev prefix','Icon adapter','Other measured s','Unseparated frame s'],rr)
        text += '\nOCR purposes: R = `read` API calls; P = `predict` API calls (often multiple preprocessing variants per read); reuse = region reuse; hit = exact prediction-cache hits. R time includes nested P time. Standalone visual variants have R=0. No model inference occurred. Dev OCR is a subset of verification, not additive to the partition.\n\n'
        text += table(['ID','Purpose','R / inclusive s','P / inclusive s','Region reuse / exact hit','Model calls / s'],[[s['index'],purpose,f"{int(c.get('ocr_read_calls',0))} / {fmt(c.get('ocr_read_inclusive_seconds',0))}",f"{int(c.get('ocr_predict_calls',0))} / {fmt(c.get('ocr_predict_inclusive_seconds',0))}",f"{int(c.get('ocr_region_reads_reused',0))} / {int(c.get('ocr_exact_cache_hits',0))}",f"{int(c.get('ocr_inference_calls',0))} / {fmt(c.get('ocr_inference_inclusive_seconds',0))}"] for s in result['segments'] for purpose,c in sorted(s['ocr_purposes'].items())])
        text += '\nTop ten by allocated processing wall; largest measured partition is identified without assigning the remainder to a guessed cause.\n\n'
        text += table(['Rank','ID','Video duration','Wall','Largest partition','Seconds'],[[rank,s['index'],fmt(s['video_duration_seconds']),fmt(s['processing_wall_seconds']),s['largest_measured_partition'],fmt(s['partition_seconds'][s['largest_measured_partition']])] for rank,s in enumerate(sorted(result['segments'],key=lambda s:s['processing_wall_seconds'],reverse=True)[:10],1)])
        text += '\nPartition totals (frame wall diagnostic is overlapping and excluded from the sum):\n\n```json\n'+json.dumps(result['partition_totals'],indent=2)+'\n```\n\n'
    text += f'Raw per-segment inclusive/exclusive frame-context module counters and input SHA-256 identities: `.cache/battles/sample_battle_9/evaluation/{audit_id}/cost-audit.json`. Reproduce with `.venv/bin/python scripts/audit_m24_command_costs.py --audit-id <new-id>`. This command only reads completed artifacts and writes its new namespace.\n'
    target.write_text(text)
    print(json.dumps({k:dict(video=v['video_seconds'],wall=v['wall_seconds'],partition=v['partition_totals']) for k,v in results.items()},indent=2))


if __name__ == '__main__':
    main()
