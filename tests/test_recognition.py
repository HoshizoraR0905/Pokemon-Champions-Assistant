from dataclasses import replace
from pathlib import Path
import json
import cv2
import numpy as np
import pytest
from capture import Frame, load_image, video_frames
from models import Observation, Pokemon, Recognition
from recognition import Recognizer, annotate, classify
from recognition.ocr import OCR
from recognition.parsers import ratio, percentage
from tracking import Tracker

FIXTURES = Path(__file__).parent / 'fixtures'


class UnavailableOCR:
    warnings = ['Test OCR unavailable']
    def read(self, image, box, numeric=False, multiline=False, italic=False):
        return Observation(region=box)


@pytest.mark.parametrize('name', ['team_preview','battle_screen','move_selection',
                                 'team_configuration_moves','team_configuration_stats',
                                 'unsupported_status'])
@pytest.mark.parametrize('scale', [.5, 1, 1.25])
def test_fixture_classification(name, scale):
    image = load_image(FIXTURES / f'{name}.png').image
    image = cv2.resize(image,None,fx=scale,fy=scale)
    expected = ('team_configuration' if name.startswith('team_configuration') else
                'switch_selection' if name == 'unsupported_status' else name)
    assert classify(image)[0] == expected


@pytest.mark.parametrize('shape',[(460,1000,3),(600,800,3)])
def test_unknown(shape):
    result = Recognizer(UnavailableOCR()).recognize(Frame(np.zeros(shape,dtype=np.uint8),'blank'))
    assert result.screen == 'unknown'
    assert not result.pokemon


def test_pipeline_and_annotation(tmp_path):
    frame = load_image(FIXTURES/'move_selection.png')
    result = Recognizer(UnavailableOCR()).recognize(frame)
    assert len(result.moves) == 4 and len(result.pokemon) == 4
    assert all(p.species.value is None for p in result.pokemon)
    assert 'battle_screen' in result.components
    json.dumps(result.to_dict())
    path = tmp_path/'annotated.png'
    annotate(frame,result,path)
    annotated = cv2.imread(str(path))
    assert annotated.shape == frame.image.shape
    assert np.any(annotated != frame.image)
    h,w = frame.image.shape[:2]
    assert all(0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h for x1,y1,x2,y2 in result.regions.values())


@pytest.mark.parametrize('text,expected', [('185/185',{'current':185,'maximum':185}),
    ('0 / 173',{'current':0,'maximum':173}),('200/100',None),('1/0',None),('abc',None)])
def test_ratio(text,expected):
    assert ratio(Observation(text,.9)).value == expected


@pytest.mark.parametrize('text,expected',[('94%',94),('100 %',100),('101%',None),('40',None)])
def test_percentage(text,expected):
    assert percentage(Observation(text,.9)).value == expected


def test_tracking_duplicates_unknown_and_switch():
    tracker = Tracker()
    state = Recognition('test',0,0,screen='battle_screen',pokemon=[Pokemon('own_active_1',
        Observation('Example species',.9),Observation({'current':100,'maximum':100},.9))])
    assert tracker.update(state) == []
    assert tracker.update(state) == []
    changed = replace(state,frame_index=1,timestamp=1,pokemon=[replace(state.pokemon[0],hp=Observation({'current':75,'maximum':100},.9))])
    assert tracker.update(changed)[0].kind == 'hp_change'
    assert tracker.update(Recognition('test',2,2)) == []
    assert tracker.update(changed) == []
    switch = replace(state,frame_index=3,pokemon=[Pokemon('own_active_1',Observation('Other species',.9),Observation({'current':80,'maximum':80},.9))])
    assert [e.kind for e in tracker.update(switch)] == ['species_change']
    message = Recognition('test',4,4,message=Observation('A visible message',.9))
    assert len(tracker.update(message)) == 1
    assert tracker.update(message) == []


def test_invalid_inputs(tmp_path):
    with pytest.raises(ValueError): load_image(tmp_path/'missing.png')
    with pytest.raises(ValueError): list(video_frames(tmp_path/'missing.mp4'))
    with pytest.raises(ValueError): list(video_frames(FIXTURES/'sample_battle.mp4',0))


def test_video_adapter(tmp_path):
    path = tmp_path/'video.avi'
    writer = cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),10,(160,80))
    assert writer.isOpened()
    for _ in range(10): writer.write(np.zeros((80,160,3),np.uint8))
    writer.release()
    frames = list(video_frames(path,.3,3))
    assert [f.index for f in frames] == [0,3,6]
    assert [f.timestamp for f in frames] == pytest.approx([0,.3,.6])
    assert frames[0].metadata['fps'] == 10


def test_live_ocr_hp():
    ocr = OCR()
    if not ocr.language or 'Missing OCR languages' in ' '.join(ocr.warnings):
        pytest.skip('Requires Tesseract with chi_sim and eng')
    result = Recognizer(ocr).recognize(load_image(FIXTURES/'battle_screen.png'))
    assert [p.hp.value for p in result.pokemon[:2]] == [
        {'current':185,'maximum':185},{'current':157,'maximum':157}]
    assert result.pokemon[2].hp.value == 100
    assert result.pokemon[3].hp.value in (None,100)


def test_pokemon_selection_status_view_is_switch_selection():
    frame = load_image(FIXTURES/'unsupported_status.png')
    assert Recognizer(UnavailableOCR()).recognize(frame).screen == 'switch_selection'


def test_configuration_pipeline_unknown_fields():
    result = Recognizer(UnavailableOCR()).recognize(load_image(FIXTURES/'team_configuration_moves.png'))
    assert result.screen == 'team_configuration'
    assert len(result.pokemon) == 6
    assert all(p.configuration['nature'].value is None for p in result.pokemon)
    assert all(len([k for k in p.configuration if k.startswith('move_')]) == 4 for p in result.pokemon)


def test_configuration_merge():
    tracker = Tracker()
    species = Observation('Example',.9)
    a = Recognition('test',0,0,pokemon=[Pokemon('own_team_1',species,configuration={'ability':Observation('Visible ability',.9)})])
    b = Recognition('test',1,1,pokemon=[Pokemon('own_team_1',species,configuration={'ability':Observation(), 'hp':Observation(100,.9)})])
    tracker.update(a)
    tracker.update(b)
    assert tracker.team['own_team_1']['ability'].value == 'Visible ability'
    assert tracker.team['own_team_1']['hp'].value == 100


def test_explicit_move_message_event():
    tracker = Tracker()
    state = Recognition('test',10,2.5,screen='battle_message',
                        message=Observation('对手的示例宝可梦使出了 示例招式！',.9))
    events = tracker.update(state)
    assert [e.kind for e in events] == ['battle_message','move_execution']
    assert events[1].after == {'move':'示例招式','side':'opponent'}
    assert events[1].evidence == state.message
    assert tracker.update(state) == []
    tracker.update(Recognition('test',11,3,screen='battle_screen'))
    assert len(tracker.update(state)) == 2


def test_live_move_pp_and_message():
    ocr = OCR()
    if not ocr.language or ocr.warnings:
        pytest.skip('Requires Tesseract with chi_sim and eng')
    recognizer = Recognizer(ocr)
    moves = recognizer.recognize(load_image(FIXTURES/'move_selection.png'))
    assert [m.pp.value for m in moves.moves] == [{'current':12,'maximum':12}]*3 + [{'current':8,'maximum':8}]
    assert all(m.name.value is not None for m in moves.moves)
    message = recognizer.recognize(load_image(FIXTURES/'battle_message.png'))
    assert message.screen == 'battle_message'
    assert message.message.confidence >= .8


def test_actual_battle_screenshot_roster_regression():
    ocr = OCR()
    if not ocr.language or ocr.warnings:
        pytest.skip('Requires Tesseract with chi_sim and eng')
    result = Recognizer(ocr).recognize(load_image(FIXTURES/'battle_screen.png'))
    by_slot = {p.slot:p.species for p in result.pokemon}
    for slot,sid,status in [('own_active_1',530,'confirmed_available'),
                            ('own_active_2',903,'confirmed_available'),
                            ('opponent_active_1',376,'confirmed_available')]:
        resolution = by_slot[slot].resolution
        assert resolution.canonical_id==f'pokeapi:species:{sid}'
        assert resolution.candidates[0].availability['status']==status
    # Gholdengo is visibly present, but severely corrupted OCR must stay rejected.
    assert by_slot['opponent_active_2'].value is None
    for observation in by_slot.values():
        assert all(c.similarity > 0 for c in observation.resolution.candidates)


def test_recorded_actual_screenshot_ocr_regression():
    from recognition.entities import EntityResolver
    import hashlib
    evidence = json.loads((FIXTURES/'battle_roster_ocr.json').read_text())
    assert hashlib.sha256((FIXTURES/evidence['fixture']).read_bytes()).hexdigest()==evidence['sha256']
    resolver = EntityResolver()
    for case in evidence['cases']:
        result = resolver.resolve(Observation(None,case['confidence'],raw_text=case['raw_text']),
                                  'species',region_kind='species')
        assert result.resolution.canonical_id==case['expected_canonical_id']
