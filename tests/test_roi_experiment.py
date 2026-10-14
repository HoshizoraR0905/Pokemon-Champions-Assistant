from pathlib import Path

import cv2
import numpy as np
import pytest
from capture import Frame,load_image
from recognition import box
from streaming.monitoring import ROIS
from streaming.recognition import RegionPlanner
from streaming.roi_experiment import (FocusedROIMonitor,fields_for,anchored_text,
                                      bar_signature,MESSAGE_LINES)

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.local_artifacts('reports/M1.4-evidence/m14_boundary_270.jpg','reports/M1.4-evidence/m14_boundary_282.jpg')
def test_verified_party_and_replacement_interfaces_are_separate():
    monitor=FocusedROIMonitor();rows={}
    for second in [268,270,280,282]:
        frame=load_image(ROOT/f'reports/M1.4-evidence/m14_boundary_{second}.jpg')
        frame.source='workflow';frame.timestamp=float(second);frame.index=second
        rows[second]=monitor.inspect(frame)
    groups={second:{r['label']:r for r in row['roi_observations']} for second,row in rows.items()}
    assert groups[270]['party_list']['visibility']=='entry'
    assert 'replacement_controls' not in groups[270]
    assert groups[280]['party_list']['visibility']=='visible'
    assert groups[280]['replacement_controls']['visibility']=='entry'
    assert groups[282]['party_list']['visibility']=='exit'
    assert groups[282]['replacement_controls']['visibility']=='exit'
    assert groups[280]['replacement_controls']['anchor_method']=='existing_M1.4_vertical_popover_scan'


def test_four_active_huds_have_distinct_name_number_bar_and_unresolved_indicator_guards():
    frame=load_image(ROOT/'tests/fixtures/battle_screen.png');frame.timestamp=0.
    row=FocusedROIMonitor().inspect(frame)
    huds=[r for r in row['roi_observations'] if r['label'].startswith('hud_')]
    assert len(huds)==4
    for hud in huds:
        assert {c['label'] for c in hud['components']}=={'name','hp_text','hp_bar','unresolved_indicator_pixels'}
        assert hud['residual_guard_required'] and hud['gameplay_event'] is False


def test_hp_bar_motion_preserves_intermediates_without_damage_events():
    # Controlled modifications of a real UI crop, not new natural-game labels.
    frame=load_image(ROOT/'tests/fixtures/battle_screen.png')
    roi=fields_for(frame.image,'battle_screen')['hud_own_0']['fields'][2][1]
    x1,y1,x2,y2=box(frame.image,roi)
    monitor=FocusedROIMonitor();levels=[];rows=[]
    for i,fraction in enumerate([.9,.7,.5]):
        image=frame.image.copy();image[y1:y2,x1:x2]=0
        image[y1:y2,x1:x1+round((x2-x1)*fraction)]=(0,255,0)
        row=monitor.inspect(Frame(image,'synthetic-bar',i,i*.2),phase='battle_screen')
        hud=next(r for r in row['roi_observations'] if r['label']=='hud_own_0')
        levels.append(hud['bar_levels']['hp_bar']['filled_column_fraction']);rows.append(hud)
        assert hud['gameplay_event'] is False and hud['proposal_trigger']
    assert levels==sorted(levels,reverse=True)
    assert all(r['observation_kind']=='bar_intermediate_or_display_change' for r in rows[1:])


def test_indicator_color_change_is_retained_as_unresolved_raw_fallback():
    frame=load_image(ROOT/'tests/fixtures/battle_screen.png');frame.source='indicator';frame.timestamp=0.
    monitor=FocusedROIMonitor();monitor.inspect(frame)
    image=frame.image.copy()
    # One pixel in the known own HUD portrait/indicator envelope, outside text/bar.
    x,y,_,_=box(image,fields_for(image,'battle_screen')['hud_own_0']['envelope'])
    image[y+2,x+2]=255-image[y+2,x+2]
    row=monitor.inspect(Frame(image,'indicator',1,.2),phase='battle_screen')
    hud=next(r for r in row['roi_observations'] if r['label']=='hud_own_0')
    residual=next(c for c in hud['components'] if c['label']=='unresolved_indicator_pixels')
    assert residual['changed'] and hud['conservative_trigger']
    assert hud['gameplay_event'] is False


def test_anchored_foreground_suppresses_distant_background_but_keeps_short_text_change():
    image=np.zeros((30,300,3),np.uint8)
    cv2.putText(image,'A',(2,24),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,255,255),1)
    first=anchored_text(image)
    background=image.copy();background[3:20,260:280]=255
    assert np.array_equal(first,anchored_text(background))
    changed=image.copy();cv2.putText(changed,'B',(24,24),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,255,255),1)
    assert not np.array_equal(first,anchored_text(changed))


def test_consecutive_same_message_after_clear_is_not_merged():
    frame=load_image(ROOT/'tests/fixtures/m15_message_move.png');frame.source='message';frame.timestamp=0.
    monitor=FocusedROIMonitor();monitor.inspect(frame,phase='battle_animation')
    clear=frame.image.copy()
    for roi in MESSAGE_LINES:
        x1,y1,x2,y2=box(clear,roi);clear[y1:y2,x1:x2]=0
    blank=monitor.inspect(Frame(clear,'message',1,.2),phase='battle_animation')
    reappear=monitor.inspect(Frame(frame.image,'message',2,.4),phase='battle_animation')
    for row in [blank,reappear]:
        message=next(r for r in row['roi_observations'] if r['label']=='messages')
        assert message['proposal_trigger'] and message['conservative_trigger']


@pytest.mark.parametrize('name',['m14_target_selection_380.png','m14_target_selection_660.png'])
def test_target_cards_and_both_banner_anchors_preserve_existing_geometry(name):
    frame=load_image(ROOT/'tests/fixtures'/name);frame.timestamp=0.
    planned=RegionPlanner(decision_regions=True).plan(frame,'move_target_selection',include_icons=False)
    planned_bounds={tuple(r['bounds']) for r in planned if r['label'].startswith('target_')}
    fields=fields_for(frame.image,'move_target_selection')['target_controls']['fields']
    assert len(fields)==10
    assert {box(frame.image,roi) for _,roi,_ in fields}==planned_bounds


def test_static_move_menu_reuses_foreground_and_phase_entry_still_triggers():
    frame=load_image(ROOT/'tests/fixtures/move_selection.png');frame.source='menu';frame.timestamp=0.
    monitor=FocusedROIMonitor();first=monitor.inspect(frame)
    assert next(r for r in first['roi_observations'] if r['label']=='move_controls')['proposal_trigger']
    image=frame.image.copy();image[200:300,200:300]=0  # arena, outside menu/HUD/message
    second=monitor.inspect(Frame(image,'menu',1,.2))
    menu=next(r for r in second['roi_observations'] if r['label']=='move_controls')
    assert not menu['proposal_trigger'] and not menu['raw_trigger']
    assert 'controls' in ROIS  # conservative monitor remains unmodified


def test_bar_color_change_with_same_fill_geometry_is_preserved():
    green=np.zeros((10,100,3),np.uint8);green[:,:70]=(0,255,0)
    yellow=np.zeros_like(green);yellow[:,:70]=(0,255,255)
    green_sig,green_level=bar_signature(green)
    yellow_sig,yellow_level=bar_signature(yellow)
    assert green_level['filled_column_fraction']==yellow_level['filled_column_fraction']
    assert green_sig!=yellow_sig
    assert yellow_level['dominant_color_candidate']=='yellow'


@pytest.mark.local_artifacts('reports/M1.4-evidence/m14_boundary_268.jpg')
def test_verified_move_highlight_is_a_separate_field():
    frame=load_image(ROOT/'reports/M1.4-evidence/m14_boundary_268.jpg')
    from streaming.roi_experiment import crop,highlight_signature
    fields=fields_for(frame.image,'move_selection')['move_controls']['fields']
    highlighted={name:highlight_signature(crop(frame.image,roi)) for name,roi,mode in fields if mode=='highlight'}
    assert highlighted['highlight_0']=='green_border_candidate'
    assert all(highlighted[f'highlight_{i}']=='no_green_border_candidate' for i in [1,2,3])
