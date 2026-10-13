"""Phase evidence and timeline regressions; no battle-event assertions."""
from pathlib import Path
import cv2

from capture import Frame, load_image, video_frames
from models import Observation
from phase_timeline import build_timeline
from recognition.phases import classify_phase


FIXTURES = Path(__file__).parent/'fixtures'


def test_visual_phase_fixtures_and_ambiguous_target_menu():
    expected = {'team_configuration_moves':'team_configuration',
                'team_preview':'team_preview', 'battle_screen':'battle_screen',
                'move_selection':'move_selection', 'battle_message':'battle_message',
                'unsupported_status':'switch_selection'}
    for name, phase in expected.items():
        image = load_image(FIXTURES/f'{name}.png').image
        assert classify_phase(image)[0] == phase
    # This manually reviewed frame is a move-target chooser, not a switch menu.
    target=load_image(FIXTURES/'m14_target_selection.jpg').image
    assert classify_phase(target)[0] == 'move_target_selection'


def test_timeline_preserves_short_phase_and_uncertain_transition():
    images = [load_image(FIXTURES/f'{name}.png').image for name in
              ('move_selection','battle_message','move_selection')]
    frames = [Frame(image,'synthetic.mp4',index,timestamp,
                    {'timestamp_method':'video_position'})
              for image,index,timestamp in zip(images,(0,60,120),(0.,2.,4.))]
    timeline = build_timeline(frames,interval=2.,duration=6.)
    assert [s['phase'] for s in timeline['segments']] == [
        'move_selection','battle_message','move_selection']
    assert len(timeline['transitions']) == 2
    assert all(t['provenance']=='inferred_across_sampled_frames' for t in timeline['transitions'])
    assert timeline['transitions'][0]['uncertainty_seconds']==2.
    assert timeline['segments'][1]['observations'][0]['frame_index']==60
    assert 'turn' not in timeline['segments'][2]


def test_revival_message_keeps_selection_purpose_separate():
    message=load_image(FIXTURES/'battle_message.png').image
    selection=load_image(FIXTURES/'unsupported_status.png').image
    frames=[Frame(message,'synthetic.mp4',100,3.),Frame(selection,'synthetic.mp4',120,4.)]
    timeline=build_timeline(frames,interval=1.,message_reader=lambda image,bounds:
        Observation('巴布土拨使出了复生祈祷！',.95,bounds))
    selected=timeline['segments'][1]['observations'][0]
    assert selected['raw_phase']=='switch_selection'
    assert selected['phase']=='switch_selection'
    assert selected['selection_purpose']=='revival_target_selection'
    assert selected['purpose_evidence'][0]['frame_index']==100
    assert timeline['transitions'][0]['to']=='switch_selection'
    assert 'events' not in timeline


def test_video_adapter_with_phase_pipeline(tmp_path):
    path=tmp_path/'short.avi'
    first=load_image(FIXTURES/'move_selection.png').image
    second=load_image(FIXTURES/'unsupported_status.png').image
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),10,(1311,603))
    assert writer.isOpened()
    for image in (first,first,second,second):
        writer.write(cv2.resize(image,(1311,603)))
    writer.release()
    timeline=build_timeline(video_frames(path,.1),interval=.1,duration=.4)
    assert timeline['sample_count']==4
    assert [s['phase'] for s in timeline['segments']]==['move_selection','switch_selection']
    assert timeline['transitions'][0]['provenance']=='observed_adjacent_frames'


def test_explicit_target_uncertainty_is_not_smoothed(monkeypatch):
    import phase_timeline
    image = load_image(FIXTURES/'move_selection.png').image
    classifications = iter([
        ('move_selection', .9, ['move_selection'], []),
        ('unknown', 0., ['four_card_target_selection'], ['Target purpose unresolved']),
        ('move_selection', .9, ['move_selection'], []),
    ])
    monkeypatch.setattr(phase_timeline, 'classify_phase', lambda image: next(classifications))
    timeline = build_timeline([Frame(image, 'test', i, float(i)) for i in range(3)], interval=1.)
    assert [s['phase'] for s in timeline['segments']] == ['move_selection', 'unknown', 'move_selection']
    assert all(t['validation'] == 'unresolved' for t in timeline['transitions'])


def test_rejected_message_text_does_not_establish_selection_purpose():
    frames = [Frame(load_image(FIXTURES/'battle_message.png').image, 'test', 0, 0.),
              Frame(load_image(FIXTURES/'unsupported_status.png').image, 'test', 1, 1.)]
    timeline = build_timeline(frames, interval=1., message_reader=lambda image, bounds:
        Observation(None, .95, bounds, raw_text='复生祈祷'))
    assert timeline['segments'][-1]['observations'][0]['selection_purpose'] == 'unknown'


def test_timeline_validates_order_and_tracks_last_observation():
    import pytest
    image = load_image(FIXTURES/'move_selection.png').image
    frames = [Frame(image, 'test', 0, 0.), Frame(image, 'test', 10, 2.)]
    timeline = build_timeline(frames, interval=2., duration=3.)
    assert timeline['segments'][0]['last_observed_timestamp'] == 2.
    assert timeline['segments'][0]['end_timestamp'] == 3.
    for invalid in ([frames[1], frames[0]], [Frame(image, 'test')],
                    [frames[0], Frame(image, 'other', 10, 2.)]):
        with pytest.raises(ValueError):
            build_timeline(invalid, interval=2.)
    with pytest.raises(ValueError):
        build_timeline(frames, interval=2., duration=1.)


def test_preserved_timeline_structure_and_sparse_accuracy():
    import copy
    import json
    from scripts.benchmark_m14 import evaluate_timeline
    root = FIXTURES.parent.parent
    truth = json.loads((FIXTURES/'m14_phase_ground_truth.json').read_text())
    for name, annotation in truth['videos'].items():
        artifact = 'M1.4-'+name.removesuffix('.mp4').replace('_', '-')+'-timeline.json'
        timeline = json.loads((root/'reports'/artifact).read_text())
        evaluation = evaluate_timeline(timeline, annotation)
        assert not evaluation['structural_errors']
        assert all(point['within_tolerance'] for point in evaluation['points'])
        # Validate the validator: inconsistent boundaries must be reported.
        broken = copy.deepcopy(timeline)
        broken['transitions'][0]['latest_timestamp'] += 1
        assert evaluate_timeline(broken, annotation)['structural_errors']


def test_seeked_target_and_device_overlay():
    for name, expected in [('m14_target_selection_520.jpg', 'move_target_selection'),
                           ('m14_device_overlay.jpg', 'unknown')]:
        for scale in [.5, 1., 1.25]:
            image = load_image(FIXTURES/name).image
            image = cv2.resize(image, None, fx=scale, fy=scale)
            assert classify_phase(image)[0] == expected


def test_reviewed_workflow_and_manual_context():
    import json
    root = FIXTURES.parent.parent
    annotations = json.loads((FIXTURES/'m14_selection_context.json').read_text())
    frames = [Frame(load_image(root/'reports/M1.4-evidence'/f'm14_boundary_{t}.jpg').image,
                    'tests/fixtures/sample_battle_1.mp4', i, float(t))
              for i,t in enumerate([268,270,280,282])]
    timeline = build_timeline(frames, interval=2., context_annotations=annotations)
    assert [s['phase'] for s in timeline['segments']] == [
        'move_selection', 'pokemon_selection', 'switch_selection', 'battle_animation']
    for segment in timeline['segments']:
        sample = segment['observations'][0]
        assert sample['switching_context'] == 'voluntary'
        assert sample['context_provenance'] == 'user_manual_review'
        assert sample['context_evidence']
    assert timeline['segments'][1]['observations'][0]['purpose_evidence'][-1]['raw_phase'] == 'pokemon_selection'
    assert 'events' not in timeline and 'turn' not in timeline
    # UI predictions do not require or depend on the review's timestamps.
    shifted = [Frame(f.image, 'other.mp4', f.index, f.timestamp+1000) for f in frames]
    independent = build_timeline(shifted, interval=2.)
    assert [s['phase'] for s in independent['segments']] == [s['phase'] for s in timeline['segments']]
    assert independent['segments'][1]['observations'][0]['selection_purpose'] == 'unknown'


def test_highlighted_move_row_and_party_list_at_multiple_resolutions():
    root = FIXTURES.parent.parent
    for second, expected in [(268,'move_selection'), (270,'pokemon_selection'), (280,'switch_selection')]:
        image = load_image(root/'reports/M1.4-evidence'/f'm14_boundary_{second}.jpg').image
        for scale in [.5,1.,1.25,2.]:
            assert classify_phase(cv2.resize(image, None, fx=scale, fy=scale))[0] == expected


def test_target_like_grid_without_move_banner_is_unresolved():
    from recognition import box
    image = load_image(FIXTURES/'m14_target_selection.jpg').image.copy()
    x1,y1,x2,y2 = box(image, (.565,.46,.685,.51))
    image[y1:y2,x1:x2] = (80,80,80)
    assert classify_phase(image)[0] == 'unknown'
    assert 'ambiguous_target_panel' in classify_phase(image)[2]


def test_context_purposes_do_not_change_ui_or_create_events():
    image = load_image(FIXTURES.parent.parent/'reports/M1.4-evidence/m14_boundary_270.jpg').image
    for purpose in ['voluntary','move_triggered','faint_replacement','revival_target_selection','unknown']:
        timeline = build_timeline([Frame(image,'test',0,0.)], interval=1., context_annotations=[
            {'source':'test','start':0.,'end':1.,'purpose':purpose,'provenance':'manual_review',
             'evidence':[{'note':'test context'}]}])
        sample = timeline['segments'][0]['observations'][0]
        assert sample['phase'] == 'pokemon_selection'
        assert sample['selection_purpose'] == purpose
        assert 'events' not in timeline


def test_short_target_phase_survives_temporal_segmentation():
    images = [load_image(FIXTURES/name).image for name in
              ['move_selection.png','m14_target_selection.jpg','move_selection.png']]
    timeline = build_timeline([Frame(im,'test',i,float(i)) for i,im in enumerate(images)], interval=1.)
    assert [s['phase'] for s in timeline['segments']] == ['move_selection','move_target_selection','move_selection']
    assert all(o['phase'] == o['raw_phase'] for s in timeline['segments'] for o in s['observations'])


def test_smoothing_changes_only_unsupported_near_identical_frame(monkeypatch):
    import phase_timeline
    image = load_image(FIXTURES/'move_selection.png').image
    evidence = iter([('move_selection',.85,['move_selection'],[]),
                     ('unknown',0.,['no_supported_visual_evidence'],['Phase unresolved']),
                     ('move_selection',.85,['move_selection'],[])])
    monkeypatch.setattr(phase_timeline,'classify_phase',lambda image:next(evidence))
    timeline = build_timeline([Frame(image,'test',i,float(i)) for i in range(3)], interval=1.)
    assert len(timeline['segments']) == 1
    observation = timeline['segments'][0]['observations'][1]
    assert observation['raw_phase'] == 'unknown'
    assert observation['confidence'] <= .55
    assert 'near_identical_neighbor_frames' in observation['evidence']


def test_same_message_avoids_repeated_ocr_and_revival_context_expires():
    image = load_image(FIXTURES/'battle_message.png').image
    party = load_image(FIXTURES.parent.parent/'reports/M1.4-evidence/m14_boundary_270.jpg').image
    reads = []
    def reader(image,bounds):
        reads.append(bounds)
        return Observation('复生祈祷',.95,bounds)
    timeline = build_timeline([Frame(image,'test',0,0.), Frame(image,'test',1,1.),
                               Frame(party,'test',2,12.)], interval=1., message_reader=reader)
    assert len(reads) == 1
    assert timeline['segments'][-1]['observations'][0]['selection_purpose'] == 'unknown'


def test_left_anchored_target_banners_and_missing_banner_uncertainty():
    from recognition import box
    for name in ['m14_target_selection_380.png','m14_target_selection_660.png']:
        image = load_image(FIXTURES/name).image
        for scale in [.5,1.,1.25,2.]:
            assert classify_phase(cv2.resize(image,None,fx=scale,fy=scale))[0] == 'move_target_selection'
        obscured = image.copy()
        for region in [(.355,.46,.475,.51),(.565,.46,.685,.51)]:
            x1,y1,x2,y2 = box(obscured,region)
            obscured[y1:y2,x1:x2] = (80,80,80)
        assert classify_phase(obscured)[0] == 'unknown'
        assert 'ambiguous_target_panel' in classify_phase(obscured)[2]
