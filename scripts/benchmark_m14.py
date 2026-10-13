"""Compare archived and final sampled M1.4 timelines against sparse manual review."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capture import load_image
from recognition.phases import PHASES, classify_phase

ROOT = Path(__file__).resolve().parents[1]


def evaluate_timeline(timeline, annotations):
    samples = [o for s in timeline['segments'] for o in s['observations']]
    errors = []
    if len(samples) != timeline['sample_count']:
        errors.append('sample count differs from preserved observations')
    for previous, current in zip(samples, samples[1:]):
        if (current['timestamp'] <= previous['timestamp'] or
                current['frame_index'] <= previous['frame_index'] or
                current['source'] != previous['source']):
            errors.append('observations are not ordered within one source')
    for segment in timeline['segments']:
        observations = segment['observations']
        if segment['phase'] not in PHASES or any(o['phase'] != segment['phase'] for o in observations):
            errors.append('segment contains inconsistent phase evidence')
        if segment['start_timestamp'] != observations[0]['timestamp'] or segment['end_timestamp'] < observations[-1]['timestamp']:
            errors.append('segment bounds do not contain its evidence')
    expected_pairs = list(zip(timeline['segments'], timeline['segments'][1:]))
    if len(timeline['transitions']) != len(expected_pairs):
        errors.append('transition count differs from segment boundaries')
    for transition, (old, new) in zip(timeline['transitions'], expected_pairs):
        a, b = old['observations'][-1], new['observations'][0]
        expected_provenance = ('observed_adjacent_frames' if b['frame_index']-a['frame_index'] == 1
                               else 'inferred_across_sampled_frames')
        if (transition['from'] != old['phase'] or transition['to'] != new['phase'] or
                transition['earliest_timestamp'] != a['timestamp'] or
                transition['latest_timestamp'] != b['timestamp'] or
                transition['supporting_observations'] != [a, b] or
                transition['provenance'] != expected_provenance or
                transition['uncertainty_seconds'] != round(b['timestamp']-a['timestamp'], 3)):
            errors.append('transition does not match neighboring observations')
    points = []
    confusion = Counter()
    for point in annotations['reviewed_points']:
        nearest = min(samples, key=lambda o: abs(o['timestamp']-point['second']))
        offset = abs(nearest['timestamp']-point['second'])
        eligible = offset <= timeline['sampling_interval_seconds']/2 + .05
        matched = eligible and nearest['phase'] == point['phase']
        points.append({**point, 'predicted_phase': nearest['phase'],
                       'sample_timestamp': nearest['timestamp'], 'offset_seconds': round(offset, 4),
                       'within_tolerance': eligible, 'matched': matched})
        confusion[(point['phase'], nearest['phase'])] += 1
    intervals = []
    for interval in annotations.get('reviewed_intervals', []):
        selected = [o for o in samples if interval['start'] <= o['timestamp'] <= interval['end'] + .05]
        intervals.append({**interval, 'sample_count': len(selected),
                          'correct': sum(o['phase'] == interval['phase'] for o in selected)})
    boundaries = []
    for reviewed in annotations.get('reviewed_transitions', []):
        matches = [t for t in timeline['transitions'] if t['from'] == reviewed['from']
                   and t['to'] == reviewed['to']
                   and reviewed['earliest_timestamp']-.05 <= t['earliest_timestamp']
                   and t['latest_timestamp'] <= reviewed['latest_timestamp']+.05]
        boundaries.append({**reviewed, 'matched': bool(matches), 'matching_count': len(matches)})
    reconciled = [o for o in samples if o['phase'] != o.get('raw_phase', o['phase'])]
    raw_boundaries = [(a['frame_index'],b['frame_index']) for a,b in zip(samples,samples[1:])
                      if a.get('raw_phase',a['phase']) != b.get('raw_phase',b['phase'])]
    final_boundaries = [(a['frame_index'],b['frame_index']) for a,b in zip(samples,samples[1:])
                        if a['phase'] != b['phase']]
    raw_correct = 0
    for point in annotations['reviewed_points']:
        nearest = min(samples,key=lambda o: abs(o['timestamp']-point['second']))
        if (abs(nearest['timestamp']-point['second']) <= timeline['sampling_interval_seconds']/2+.05
                and nearest.get('raw_phase',nearest['phase']) == point['phase']):
            raw_correct += 1
    correct = sum(p['matched'] for p in points)
    return {'sample_count': len(samples), 'segment_count': len(timeline['segments']),
            'transition_count': len(timeline['transitions']), 'structural_errors': errors,
            'reviewed_point_count': len(points), 'correct': correct,
            'accuracy': correct/len(points) if points else None, 'points': points,
            'confusion': [{'expected': a, 'predicted': b, 'count': count}
                          for (a, b), count in sorted(confusion.items())],
            'reviewed_intervals': intervals, 'reviewed_transitions': boundaries,
            'false_classifications': [p for p in points if not p['matched'] and p['predicted_phase'] != 'unknown'],
            'unresolved_reviewed_points': [p for p in points if not p['matched'] and p['predicted_phase'] == 'unknown'],
            'unresolved_observation_count': sum(o['phase'] == 'unknown' for o in samples),
            'phase_counts': dict(Counter(o['phase'] for o in samples)),
            'missed_reviewed_transitions': [b for b in boundaries if not b['matched']],
            'smoothing': {'changed_sample_count':len(reconciled), 'raw_reviewed_correct':raw_correct,
                          'final_reviewed_correct':correct,
                          'raw_boundary_count':len(raw_boundaries), 'final_boundary_count':len(final_boundaries),
                          'suppressed_boundary_count':len(set(raw_boundaries)-set(final_boundaries)),
                          'introduced_boundary_count':len(set(final_boundaries)-set(raw_boundaries)),
                          'changes':[{'timestamp':o['timestamp'],'frame_index':o['frame_index'],
                                      'raw_phase':o['raw_phase'],'phase':o['phase'],
                                      'evidence':o['evidence']} for o in reconciled]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'reports/M1.4-follow-up-accuracy.json')
    args = parser.parse_args()
    truth = json.loads((ROOT/'tests/fixtures/m14_phase_ground_truth.json').read_text())
    result = {'schema_version': 1, 'method': 'Archived and final full-recording two-second samples compared with revised sparse manual labels. No all-frame accuracy claim.',
              'annotation_source': 'tests/fixtures/m14_phase_ground_truth.json', 'videos': {}}
    for name, annotations in truth['videos'].items():
        artifact = 'reports/M1.4-'+name.removesuffix('.mp4').replace('_', '-')+'-timeline.json'
        timeline = json.loads((ROOT/artifact).read_text())
        final_artifact = artifact.replace('M1.4-', 'M1.4-final-', 1)
        final_timeline = json.loads((ROOT/final_artifact).read_text())
        result['videos'][name] = {
            'before': {'timeline_source':artifact, **evaluate_timeline(timeline,annotations)},
            'after': {'timeline_source':final_artifact, **evaluate_timeline(final_timeline,annotations)},
            'coverage': {'method':final_timeline['processing_method'],
                         'duration_seconds':final_timeline['duration_seconds'],
                         'interval_seconds':final_timeline['sampling_interval_seconds'],
                         'classifier_fingerprint':final_timeline['classifier_fingerprint']}}

    fixtures = {'team_configuration_moves.png': 'team_configuration',
                'team_configuration_stats.png': 'team_configuration', 'team_preview.png': 'team_preview',
                'battle_screen.png': 'battle_screen', 'move_selection.png': 'move_selection',
                'battle_message.png': 'battle_message', 'unsupported_status.png': 'switch_selection',
                'm14_target_selection.jpg': 'move_target_selection',
                'm14_target_selection_520.jpg': 'move_target_selection', 'm14_device_overlay.jpg': 'unknown',
                'm14_target_selection_380.png': 'move_target_selection',
                'm14_target_selection_660.png': 'move_target_selection'}
    result['current_classifier_fixtures'] = [
        {'source': 'tests/fixtures/'+name, 'expected': expected,
         'predicted': classify_phase(load_image(ROOT/'tests/fixtures'/name).image)[0]}
        for name, expected in fixtures.items()]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    for stage in ['before','after']:
        correct = sum(v[stage]['correct'] for v in result['videos'].values())
        total = sum(v[stage]['reviewed_point_count'] for v in result['videos'].values())
        print(f'{stage}: {correct}/{total} revised review points matched')
    if any(v[stage]['structural_errors'] for v in result['videos'].values() for stage in ['before','after']):
        raise SystemExit('Timeline structural validation failed')


if __name__ == '__main__':
    main()
