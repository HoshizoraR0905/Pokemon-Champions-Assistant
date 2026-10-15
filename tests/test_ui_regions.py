"""Typed UI semantics, visual rows and occurrence prefix safety."""
from copy import deepcopy
from dataclasses import asdict
import numpy as np
import pytest
from battle_events.parser import EventParser
from tracking.state_engine import ApplicationPolicy,Deferred
from recognition.ui_regions import inspect_ui,regroup_tokens,read_message
from recognition.message_occurrences import MessageOccurrences


def message(t,text,confidence=.99,region='battle_message',visible=True):
    return dict(timestamp=t,sha256=str(t),source_id='test#'+str(t),image='frame.png',
                message=dict(selected=visible,source_region_type=region,raw_text=text,confidence=confidence,rows=[]))


@pytest.mark.parametrize('kind',['command_menu','party_overlay','status_overlay','battle_log_overlay','move_description_overlay','ability_banner','field_indicator'])
def test_nonlive_region_cannot_become_move_execution(kind):
    parser=EventParser();entry=dict(entry_id='x',raw_text='龙头地鼠使出了守住！',ocr_confidence=.99,source_region_type=kind)
    e=parser.parse(entry)
    assert e.event_type=='unknown' and e.canonical_references=={} and 'non_live_ui_region' in e.uncertainty
    live=parser.parse({**entry,'source_region_type':'battle_message'})
    live.attributes['source_region_type']=kind
    with pytest.raises(Deferred,match='live_message_region'):ApplicationPolicy().check(live)


def test_fragments_on_same_baseline_join_without_merging_genuine_rows():
    tokens=[dict(text='Big',box=[0,10,20,25]),dict(text='Mom',box=[30,11,50,25]),
            dict(text='使出了',box=[55,10,85,26]),dict(text='击掌奇袭',box=[0,40,70,56]),dict(text='unknown')]
    rows=regroup_tokens(tokens)
    assert [r['text'] for r in rows['rows']]==['BigMom使出了','击掌奇袭']
    assert rows['unplaced_tokens']==[dict(text='unknown')]


def test_blank_flash_blocks_ocr_without_changing_biological_state():
    ui=inspect_ui(np.full((603,1311,3),255,np.uint8));r=next(r for r in ui['regions'] if r['region_type']=='battle_message')
    class Forbidden:
        def read(self,*a,**k):raise AssertionError('Blank frame must not invoke OCR')
    assert r['visibility']=='absent' and not read_message(None,Forbidden(),r)['selected']
    assert all(r['visibility']=='absent' for r in ui['regions'] if r['region_type']=='active_hud')


def test_unverified_scale_disables_fixed_geometry():
    ui=inspect_ui(np.zeros((1206,2622,3),np.uint8))
    assert all(r['visibility']=='unknown_layout' for r in ui['regions'])


def test_two_corrupt_readings_then_correct_reading_emit_once_without_backdating():
    g=MessageOccurrences('test')
    assert not g.observe(message(1,'对手的BigMom使出了击堂奇龚出手可表！'))['events']
    prefix=deepcopy(g.groups)
    assert not g.observe(message(1.5,'对手的BigMom使出了击堂奇袭山手可表！'))['events']
    good=g.observe(message(2,'对手的Big Mom使出了击掌奇袭！'))
    assert len(good['events'])==1 and good['events'][0]['attributes']['observation_time']==2
    assert prefix[0]['interpretation_time'] is None
    assert len(g.groups)==1 and len(g.groups[0]['observations'])==3
    assert not g.observe(message(2.5,'对手的BigMom使出了击掌奇袭！'))['events']
    g.observe(message(3,'',visible=False))
    assert g.observe(message(4,'对手的BigMom使出了击掌奇袭！'))['events']


def test_different_moves_or_unsupported_regions_do_not_merge_executions():
    g=MessageOccurrences('test')
    assert g.observe(message(1,'龙头地鼠使出了守住！'))['events']
    assert g.observe(message(1.5,'龙头地鼠使出了地震！'))['events']
    assert len(g.groups)==2
    assert not g.observe(message(2,'龙头地鼠使出了地震！',region='move_description_overlay'))['events']
    with pytest.raises(ValueError):g.observe(message(1,'out of order'))


def test_flinch_message_is_observational_not_an_invented_execution():
    event=EventParser().parse(dict(entry_id='f',raw_text='龙头地鼠畏缩了，无法使出招式！',ocr_confidence=.99,
                                  source_region_type='battle_message'))
    assert event.event_type=='move_effect' and event.attributes['effect']=='flinch_prevented_action'
    assert event.attributes['observation_only'] and not event.canonical_references.get('move')


@pytest.mark.local_artifacts('.cache/m223-survey/000193.jpg','reports/M2.1-battle-log-evidence/log-full-374.png')
def test_verified_large_overlays_occlude_live_message_and_command_interpretation():
    import cv2
    for filename,kind in [('.cache/m223-survey/000193.jpg','status_overlay'),
                          ('reports/M2.1-battle-log-evidence/log-full-374.png','battle_log_overlay')]:
        data=inspect_ui(cv2.imread(filename))
        assert data['overlay']==kind
        assert all(r['visibility']=='occluded' for r in data['regions'] if r['region_type'] in {'battle_message','command_menu','active_hud'})
        assert not any(r['selected_for_ocr'] for r in data['regions'])


@pytest.mark.local_artifacts('.cache/battles/sample_battle_5/m236/held_out-observations.json',
                             '.cache/battles/sample_battle_5/m236u/regression-replay.json')
def test_saved_bad_bad_good_readings_and_new_replay_are_prefix_safe():
    import json
    from pathlib import Path
    p=Path('.cache/battles/sample_battle_5')
    data=json.loads((p/'m236/held_out-observations.json').read_text())
    rows=[min(data['observations'],key=lambda r:abs(r['timestamp']-t)) for t in [415.503,416.003,416.503]]
    grouping=MessageOccurrences('sample_battle_5');emitted=[]
    for index,row in enumerate(rows):
        candidate=deepcopy(row);candidate['message'].update(selected=True,source_region_type='battle_message')
        decision=grouping.observe(candidate);emitted+=decision['events']
        if index<2:assert not decision['events'] and decision['occurrence']['interpretation_time'] is None
    assert len(grouping.groups)==1 and len(emitted)==1
    assert emitted[0]['attributes']['observation_time']==rows[-1]['timestamp']
    replay=json.loads((p/'m236u/regression-replay.json').read_text())
    assert len(replay['executed_event_receipts'])==2
    assert sum(r['status']=='applied_partial' for r in replay['executed_event_receipts'])==1
    assert all(not moves for t,moves in replay['prefix_revealed_moves'].items() if float(t)<415.5)
