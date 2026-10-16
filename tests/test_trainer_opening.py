"""Trainer-label capture, opening context and temporal isolation; no real OCR."""
from collections import Counter
from copy import deepcopy
from types import SimpleNamespace
import numpy as np
import pytest

from battle_events.parser import EventParser, BattleContext
from battle_events.schema import Participant
from capture import Frame
from models import Observation
from recognition.event_report import video_events
from recognition.event_schedule import IdentitySchedule
from recognition.trainers import trainer_observation
from tests.test_event_driven import live_row
from tracking.battle_state import BattleState
from tracking.state_engine import StateEngine, event_from_dict


def trainer(raw='Visitor', confidence=.99, side='opponent', t=1):
    return trainer_observation(dict(raw_text=raw, display_name=raw, ocr_confidence=confidence,
        evidence=[dict(source='test.mp4#1', sha256='preview', timestamp=t, image='preview.png')]), 'test', side)


def preview(observation=None):
    r = live_row(1, ''); r['ui'].update(phase='team_preview', confidence=.9)
    r['trainer_observations'] = [observation if observation is not None else trainer()]
    return r


def opening(text='Visitor派出了钢铠鸦和龙头地鼠！', t=5):
    return live_row(t, text)


def sends(rows):
    return [e for e in video_events(rows, [], 'test') if e['event_type'] == 'send_out']


def test_explicit_preview_id_matches_at_message_time_preserving_opponent_order_and_slots():
    events = sends([preview(trainer('Ｖｉｓｉｔｏｒ')), opening('visitor派出了钢铠鸦和龙头地鼠！')])
    assert [e['side'] for e in events] == ['opponent', 'opponent']
    assert [e['attributes']['slot'] for e in events] == ['right', 'left']
    assert [e['actor']['species_id'] for e in events] == [823, 530]
    assert all(e['attributes']['observation_time'] == 5 for e in events)
    assert all(e['attributes']['opening_evidence']['trainer_evidence']['evidence'][0]['timestamp'] == 1 for e in events)


@pytest.mark.parametrize('observation', [trainer('Visit', .8), trainer('Visitor…'), trainer('SomeoneElse'), trainer('Vis')])
def test_uncertain_incomplete_or_mismatched_id_does_not_use_first_message_order(observation):
    events = sends([preview(observation), opening()])
    assert all(e['side'] == 'unknown' and 'side_unknown' in e['uncertainty'] for e in events)
    assert all('slot' not in e['attributes'] for e in events)


def test_mid_battle_start_and_missing_first_message_never_force_opponent():
    assert all(e['side'] == 'unknown' for e in sends([opening()]))
    rows = [preview(), opening('上吧！暴飞龙！大狃拉！', 3), opening(t=5)]
    events = sends(rows)
    assert [e['side'] for e in events] == ['self', 'self', 'unknown', 'unknown']
    assert events[0]['attributes']['opening_evidence']['ordering_support'] == 'missing_first_opening_message'


def test_self_format_follows_opponent_only_in_confirmed_opening():
    events = sends([preview(), opening(), opening('上吧！暴飞龙！大狃拉！', 7)])
    assert [e['side'] for e in events] == ['opponent', 'opponent', 'self', 'self']
    assert events[-1]['attributes']['opening_evidence']['ordering_support'] == 'self_follows_matched_opponent'


def test_intervening_battle_action_closes_opening_window():
    events = sends([preview(), live_row(3, '钢铠鸦使出了守住！'), opening()])
    assert all(e['side'] == 'unknown' for e in events)
    menu = live_row(3, ''); menu['ui'].update(phase='move_selection',confidence=.9)
    assert all(e['side'] == 'unknown' for e in sends([preview(),menu,opening()]))


def test_future_hud_and_future_trainer_observation_cannot_relabel_earlier_entry():
    first = sends([opening()])
    hud = live_row(8, ''); hud['snapshot'] = dict(pokemon=[])
    future = preview(); future['timestamp'] = 10
    assert sends([opening(), hud, future]) == first
    invalid = preview(trainer(t=9))
    assert all(e['side'] == 'unknown' for e in sends([invalid, opening()]))


def test_observation_is_trainer_state_not_pokemon_and_opening_slots_exist_before_hud():
    events = video_events([preview(), opening()], [], 'test')
    engine = StateEngine(BattleState('test', knowledge=dict(identity_v1=True, reliability_v1=True)))
    engine.apply(event_from_dict(events[0]), sequence=1)
    assert not engine.state.pokemon
    assert engine.state.sides['opponent'].trainer['normalized_matching_form'] == 'visitor'
    for i, e in enumerate(events[1:], 2): engine.apply(event_from_dict(e), sequence=i)
    assert set(engine.state.sides['opponent'].active_slots) == {'left', 'right'}
    assert not engine.state.sides['self'].active_slots


def test_saved_replay_adapter_orders_fresh_events_before_building_state(tmp_path):
    from scripts.replay_trainer_opening import replay
    r=preview();r['trainer_observations'][0]['battle_id']='sample_battle_6'
    message=opening()
    for e in message['occurrence_decision']['events']:e['attributes']['battle_id']='sample_battle_6'
    events=video_events([r,message],[],'sample_battle_6')
    assert all('sequence' not in e['attributes'] for e in events)
    result=replay(events,'sample_battle_6',tmp_path/'progress.json')
    assert set(result['state']['sides']['opponent']['active_slots'])=={'left','right'}
    assert result['first_slot_establishment']['opponent:right']['timestamp']==5
    assert not any(h['reason']=='missing_or_ambiguous_event_order' for h in result['history'])


def test_exact_trainer_match_rejects_prefix_collision_in_existing_parser():
    c = BattleContext(participants=dict(opponent=Participant('opponent', 'Vis'), self=Participant('self')))
    e = EventParser().parse(dict(entry_id='x', source_id='x', raw_text='Visitor派出了钢铠鸦！', ocr_confidence=.99), c)
    assert 'observed_trainer_display_name' not in e.attributes['side_basis']
    e = EventParser().parse(dict(entry_id='x', source_id='x', raw_text='Ｖｉｓ派出了钢铠鸦！', ocr_confidence=.99), c)
    assert e.side == 'opponent'


def test_shared_ids_are_ambiguous_and_cross_battle_observations_rejected():
    r = preview(); r['trainer_observations'].append(trainer(side='self'))
    assert all(e['side'] == 'unknown' for e in sends([r, opening()]))
    r['trainer_observations'][0]['battle_id'] = 'other'
    with pytest.raises(ValueError, match='another battle'): video_events([r, opening()], [], 'test')


def test_capture_retries_uncertain_reads_then_stops_and_survives_ui_disappearance(monkeypatch):
    import recognition.trainers as module
    calls = []
    def read(image, backend, **kwargs):
        calls.append(kwargs['sides'])
        return {side: dict(raw_text='Visitor', ocr_confidence=.8 if len(calls) == 1 else .99,
            evidence=[dict(source=kwargs['source'], timestamp=kwargs['timestamp'], sha256=kwargs['sha256'])])
            for side in kwargs['sides']}
    monkeypatch.setattr(module, 'recognize_preview_trainers', read)
    schedule = IdentitySchedule(); counts = Counter()
    frame = Frame(np.zeros((603,1311,3),np.uint8), 'test.mp4#1', 1, 1, dict(sha256='a',image='a.png'))
    assert all(x['status'] == 'unresolved' for x in schedule.acquire_trainers(SimpleNamespace(ocr=None),frame,'team_preview',.9,'test',counts))
    frame.timestamp = 2
    assert not schedule.acquire_trainers(SimpleNamespace(ocr=None),frame,'unknown',.1,'test',counts)
    frame.timestamp = 3
    assert all(x['status'] == 'accepted' for x in schedule.acquire_trainers(SimpleNamespace(ocr=None),frame,'team_preview',.9,'test',counts))
    frame.timestamp = 10
    assert not schedule.acquire_trainers(SimpleNamespace(ocr=None),frame,'team_preview',.9,'test',counts)
    assert len(calls) == 2 and counts['trainer_label_read_requests'] == 4
    restored = IdentitySchedule(); restored.__dict__.update(deepcopy(schedule.__dict__))
    assert not restored.acquire_trainers(SimpleNamespace(ocr=None),frame,'team_preview',.9,'test',counts)
