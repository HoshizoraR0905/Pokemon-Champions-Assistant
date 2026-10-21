"""Controlled variable-HUD regressions; no claim of real reduced-combatant coverage."""
from copy import deepcopy
import pytest
from battle_evidence.visual import VisualPhaseEstimator,normal_command_support


def f(t,*,cards=2,controls=True,actions=(),timer=45,**extra):
    slots=['own_active_1','opponent_active_1'] if cards==2 else ['own_active_1','own_active_2','opponent_active_1'] if cards==3 else ['own_active_1','own_active_2','opponent_active_1','opponent_active_2'] if cards==4 else ['own_active_1'] if cards==1 else []
    return dict(id=f'f{t}',battle_id='b',source_id=f'v#{t}',timestamp=t,
        signals=dict(normal_controls=controls,native_dual_controls=controls,hud_cards=cards,hud_slots=slots,
            command_timer=timer,command_label=timer is not None,battle_view=True,cached_phase='battle_screen',**extra),
        actions=[dict(event_id=a,live_execution=True) for a in actions])


def start():
    v=VisualPhaseEstimator('b',profile='v2');v.consume(f(0,cards=0,controls=False,timer=None,initial_sendout=True));return v


@pytest.mark.parametrize('cards',[2,3,4])
def test_variable_HUD_full_cycle_uses_history_timer_geometry_and_hysteresis(cards):
    v=start()
    for t in (.5,1,1.5):v.consume(f(t,cards=cards))
    v.consume(f(2,cards=0,controls=False,timer=None,actions=['a']))
    v.consume(f(2.5,cards=0,controls=False,timer=None,actions=['b']))
    for t in (3,3.5,4):v.consume(f(t,cards=cards))
    assert len(v.segments)==1 and v.segments[0]['status']=='confirmed'
    assert v.segments[0]['next_command_time']==3


@pytest.mark.parametrize('change',[dict(command_timer=None),dict(native_dual_controls=False,normal_controls=False),dict(hud_slots=['own_active_1','own_active_2']),dict(battle_view=False,cached_phase='unknown')])
def test_two_cards_alone_never_qualify(change):
    signals=f(1)['signals'];signals.update(change)
    assert not normal_command_support(signals,established=True)['qualified']


def test_reduced_opening_without_history_is_unknown():
    assert not normal_command_support(f(1)['signals'])['qualified']


def test_one_visible_card_needs_verified_occupancy_for_both_sides():
    signals=f(1,cards=1)['signals']
    assert not normal_command_support(signals,established=True)['qualified']
    signals.update(active_slot_occupancy={'self':{'left':'own'},'opponent':{'left':'opp'}},occupancy_verified=True)
    assert normal_command_support(signals,established=True)['qualified']
    signals['active_slot_occupancy']['self']={}
    assert not normal_command_support(signals,established=True)['qualified']


def test_zero_HUD_is_not_a_new_anchor_even_with_geometry():
    assert not normal_command_support(f(1,cards=0)['signals'],established=True)['qualified']


def test_three_samples_for_reduced_HUD_not_two():
    v=start();v.consume(f(.5));v.consume(f(1));assert v.open is None
    v.consume(f(1.5));assert v.open['first_time']==.5


def test_reduced_submenu_return_does_not_increment():
    v=start()
    for t in (.5,1,1.5):v.consume(f(t))
    v.consume(f(2,controls=False,menu='move_selection'))
    for t in (2.5,3,3.5):v.consume(f(t))
    assert not v.segments


def test_faint_forced_selection_with_buttons_cannot_count_new_turn():
    v=start()
    for t in (.5,1,1.5):v.consume(f(t))
    v.consume(f(2,controls=False,cards=0,timer=None,actions=['a'],faint=True))
    v.consume(f(2.5,controls=False,menu='pokemon_selection'))
    for t in (3,3.5,4):v.consume(f(t))
    assert not v.segments


def test_pivot_resume_stays_same_resolution_until_true_command():
    v=start()
    for t in (.5,1,1.5):v.consume(f(t))
    v.consume(f(2,controls=False,cards=0,timer=None,actions=['pivot'],pivot_action=True))
    v.consume(f(2.5,controls=False,menu='pokemon_selection'))
    v.consume(f(3,controls=False,sendout=True,timer=None))
    v.consume(f(3.5,controls=False,cards=0,timer=None,actions=['b']))
    for t in (4,4.5,5):v.consume(f(t))
    assert len(v.segments)==1 and v.segments[0]['next_command_time']==4


def test_short_native_anchor_followed_by_move_menu_keeps_native_sample_requirement():
    v=start()
    for t in (.5,1):v.consume(f(t,cards=4))
    v.consume(f(1.5,cards=0,controls=False,timer=None,actions=['a']))
    v.consume(f(2,cards=0,controls=False,timer=None,actions=['b']))
    v.consume(f(2.5,cards=4));v.consume(f(3,cards=4,controls=False,menu='move_selection'))
    assert len(v.segments)==1 and v.segments[0]['next_command_time']==2.5


def test_status_overlay_after_native_anchor_confirms_continuity_but_never_bootstraps():
    v=start()
    for t in (.5,1):v.consume(f(t,cards=4))
    v.consume(f(1.5,cards=0,controls=False,timer=None,actions=['a']))
    v.consume(f(2,cards=0,controls=False,timer=None,actions=['b']))
    v.consume(f(2.5,cards=4));v.consume(f(3,cards=0,controls=False,timer=None,overlay='status_overlay'))
    assert len(v.segments)==1 and v.segments[0]['next_command_time']==2.5
    other=start()
    for t in (.5,1,1.5):other.consume(f(t,cards=0,controls=False,overlay='status_overlay'))
    assert other.open is None


def test_refreshed_status_panel_after_native_anchor_is_context_only():
    v=start()
    for t in (.5,1):v.consume(f(t,cards=4))
    v.consume(f(1.5,cards=0,controls=False,timer=None,actions=['a']))
    v.consume(f(2,cards=0,controls=False,timer=None,actions=['b']))
    v.consume(f(2.5,cards=4))
    panel=f(3,cards=0,controls=False,command_panel='status_overlay');panel['signals']['battle_view']=False
    v.consume(panel)
    assert v.segments[0]['next_command_time']==2.5


def test_unknown_classifier_with_same_command_timer_and_independent_cards_preserves_native_anchor():
    v=start()
    for t in (.5,1):v.consume(f(t,cards=4))
    v.consume(f(1.5,cards=0,controls=False,timer=None,actions=['a']))
    v.consume(f(2,cards=0,controls=False,timer=None,actions=['b']))
    v.consume(f(2.5,cards=4))
    next_frame=f(3,cards=4,controls=False);next_frame['signals'].update(battle_view=False,cached_phase='unknown')
    v.consume(next_frame)
    assert v.segments[0]['next_command_time']==2.5


@pytest.mark.local_artifacts
def test_real_native_buttons_survive_controlled_HUD_occlusion():
    from pathlib import Path
    import cv2
    from recognition.command_checkpoint import inspect_command
    from battle_evidence.visual_controls import flexible_controls
    path=Path('.cache/battles/sample_battle_8/event-driven/m239-production-first-pass-v1/frames/000245.png')
    if not path.exists():pytest.skip('optional original B8 frame')
    image=cv2.imread(str(path))
    # Deliberate controlled occlusion; not an observed two-combatant recording.
    image[497:579,325:540]=0;image[18:95,956:1171]=0
    result=flexible_controls(image,inspect_command(image),dict(phase='battle_screen',overlay=None))
    assert result['native_dual_controls']
    assert set(result['independent_visible_slots'])=={'own_active_1','opponent_active_1'}
    s=f(1)['signals'];s.update(native_dual_controls=result['native_dual_controls'],hud_slots=result['independent_visible_slots'])
    assert normal_command_support(s,established=True)['qualified']


def test_verified_occupancy_conflict_also_blocks_four_card_anchor():
    signals=f(1,cards=4)['signals'];signals.update(occupancy_verified=True,active_slot_occupancy={'self':{},'opponent':{'left':'opp'}})
    assert not normal_command_support(signals,established=True)['qualified']
