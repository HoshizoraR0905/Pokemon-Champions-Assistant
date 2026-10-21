"""Controlled fixtures; real-data acceptance is reported separately."""
from copy import deepcopy
import pytest
from battle_evidence.visual import VisualPhaseEstimator
from battle_evidence.ui_counters import parse_counter,CounterTimeline,reconcile_segments
from battle_evidence.turns import TurnReconstruction
from battle_evidence.durations import EffectDurations


def frame(t,*,main=False,actions=(),**signals):
    return dict(id=f'f{t}',battle_id='b',source_id=f'video#{t}',timestamp=t,
        signals=dict(normal_controls=main,hud_cards=4 if main else 0,battle_view=True,**signals),
        actions=[dict(event_id=a,live_execution=True) for a in actions])


def sequence(extra=(),gap=0):
    v=VisualPhaseEstimator('b')
    for f in [frame(0,main=True),frame(.5,main=True),*extra,frame(2,actions=['a']),frame(2.5,actions=['b']),
              frame(3+gap,main=True),frame(3.5+gap,main=True)]:v.consume(f)
    return v


def read(t,n,d=5,label='下雨状态',confidence=.99):
    return parse_counter(f'{label}{n}/{d}',source_id=f'v#{t}',timestamp=t,bounds=[267,26,556,57],confidence=confidence)


def test_complete_local_turn_and_bounds():
    v=sequence();s=v.segments[0]
    assert s['status']=='confirmed' and s['game_turn_number'] is None
    assert s['start']==[0,0] and s['end']==[2.5,3]
    assert s['actions'][0]['event_id']=='a'
    assert v.export()['uses_battle_log'] is False


def test_submenu_and_command_messages_never_increment():
    v=VisualPhaseEstimator('b')
    for f in [frame(0,main=True),frame(.5,main=True),frame(1,menu='move_selection'),frame(1.5,command_label=True),
              frame(2,main=True),frame(2.5,main=True)]:v.consume(f)
    assert not v.segments
    assert 'COMMAND_SUBMENU' in [r['phase'] for r in v.history]


def test_message_without_executed_action_never_resolution():
    v=VisualPhaseEstimator('b')
    for i in range(8):v.consume(frame(i*.5,main=i%3==0,command_label=True))
    assert not v.segments and not v.resolution


def test_action_with_controls_visible_does_not_close_command():
    v=VisualPhaseEstimator('b')
    for f in [frame(0,main=True),frame(.5,main=True),frame(1,main=True,actions=['Encore restriction']),frame(1.5,main=True)]:v.consume(f)
    assert not v.segments


def test_gap_is_incomplete_not_invented_turns():
    v=sequence(gap=5)
    assert len(v.segments)==1
    assert v.segments[0]['status']=='supported_but_incomplete'
    assert v.segments[0]['gaps'][0]['bounds']==[2.5,8]


def test_faint_return_without_sendout_remains_incomplete():
    v=sequence([frame(1,faint=True),frame(1.5,menu='pokemon_selection')])
    assert v.segments[0]['status']=='supported_but_incomplete'
    assert 'unresolved_faint_or_pivot_selection' in v.segments[0]['reasons']


def test_mid_resolution_forced_selection_no_extra_turn():
    v=VisualPhaseEstimator('b')
    fs=[frame(0,main=True),frame(.5,main=True),frame(1,actions=['pivot'],pivot_action=True),
        frame(1.5,menu='pokemon_selection'),frame(2,sendout=True),frame(2.5,actions=['b']),frame(3,main=True),frame(3.5,main=True)]
    for f in fs:v.consume(f)
    assert len(v.segments)==1 and v.segments[0]['status']=='confirmed'
    assert v.segments[0]['interruptions']==['f1.5']


def test_initial_sendout_and_terminal_partial():
    v=VisualPhaseEstimator('b')
    for f in [frame(0,pre_battle=True),frame(.5,initial_sendout=True),frame(1,main=True),frame(1.5,main=True),
              frame(2,actions=['a']),frame(2.5,battle_end=True)]:v.consume(f)
    assert not v.segments and v.resolution


@pytest.mark.parametrize('text,bounds', [('PP 2/5',[267,26,556,57]),('下雨状态2/5',[500,500,600,540]),
                                        ('下雨状态6/5',[267,26,556,57]),('2/5',[267,26,556,57])])
def test_strict_spatial_counter(text,bounds):
    assert parse_counter(text,source_id='f',timestamp=0,bounds=bounds,confidence=1) is None


def test_user_described_extension_sequence_not_real_fixture():
    c=CounterTimeline();history=[]
    for t,n,d in [(0,2,5),(1,1,5),(2,0,5),(3,3,8)]:history.append(c.consume(read(t,n,d)))
    assert [r['inferred_elapsed_turns'] for r in history]==[3,4,5,5]
    assert history[2]['possible_actual_remaining']==[0,3]
    assert history[2]['active_observation'] is True
    assert history[3]['revealed_total_duration']==8
    assert history[0]['revealed_total_duration'] is None
    assert c.observations[0]==history[0]
    assert c.constraints[-1]['elapsed_delta']==0


def test_confirmation_causal_and_identical_reads_no_tick():
    c=CounterTimeline();a=c.consume(read(0,2));b=c.consume(read(.5,2))
    assert not a['temporal_confirmation'] and b['temporal_confirmation']
    assert c.constraints[0]['elapsed_delta']==0
    assert c.as_of(.25)[0]['possible_actual_remaining'] is None
    assert c.as_of(.5)[0]['possible_actual_remaining']==[2,5]
    assert c.consume(read(.5,2))==dict(status='duplicate_ignored')
    changed=read(.5,1)
    changed['id']=read(.5,2)['id']
    with pytest.raises(ValueError):c.consume(changed)


@pytest.mark.parametrize('label,effect,scope',[
                                             ('光墙状态','light_screen','unknown'),('青草场地状态','grassy','field'),('沙暴状态','sandstorm','field')])
def test_effect_specific_semantics(label,effect,scope):
    c=CounterTimeline();o=c.consume(read(0,2,label=label))
    assert o['effect']==effect and o['scope']==scope
    assert o['semantics']=='unverified' and o['inferred_elapsed_turns'] is None


def test_reset_withholds_elapsed_relation():
    c=CounterTimeline();c.consume(read(0,1));o=c.consume(read(1,5))
    assert o['track_epoch']==2 and not c.constraints


def test_counter_gap_is_relation_not_turn_history():
    c=CounterTimeline();c.consume(read(0,5));c.consume(read(8,2));c.consume(read(8.5,2))
    assert c.constraints[0]['elapsed_delta']==3
    assert 'not invented individual turns' in c.constraints[0]['qualification']


def test_conflicting_counter_reconsiders_phase_turn():
    s=sequence().segments;c=CounterTimeline()
    for t,n in [(0,4),(.5,4),(3,4),(3.5,4)]:c.consume(read(t,n))
    out=reconcile_segments(s,c)
    assert out[0]['status']=='ambiguous' and s[0]['status']=='confirmed'


def test_counter_corroborates_one_turn():
    c=CounterTimeline()
    for t,n in [(0,4),(.5,4),(3,3),(3.5,3)]:c.consume(read(t,n))
    out=reconcile_segments(sequence().segments,c)
    assert out[0]['status']=='confirmed' and out[0]['counter_evidence'][0]['elapsed_delta']==1


def test_local_membership_does_not_fabricate_absolute_number_or_order():
    turns=TurnReconstruction('b')
    for i in ('a','b'):turns.consume(dict(id=i,battle_id='b',kind='action',timestamp=2,sources=['f']))
    turns.attach_visual(sequence().segments)
    assert turns.assignment['a']['status']=='confirmed_local_membership'
    assert turns.assignment['a']['number'] is None and turns.assignment['a']['order_verified'] is False
    assert turns.export()['visual_segments'][0]['game_turn_number'] is None


def test_ui_merge_preserves_activation_and_zero_is_presence():
    d=EffectDurations();d.consume(dict(id='activate',kind='effect',effect='rain',family='weather',scope='field',
        change='start',verified=True),dict(number=7))
    c=CounterTimeline();o=c.consume(read(1,0));d.observe_ui_counter(o)
    row=d.snapshot()[0]
    assert row['activation_event']=='activate' and row['start_turn']==7
    assert row['ui_active_observation'] and row['ui_remaining_support']==[0,3]
    assert row['active'] is True


def test_unscoped_side_counter_does_not_apply_to_both_sides():
    d=EffectDurations();c=CounterTimeline();d.observe_ui_counter(c.consume(read(0,2,label='顺风状态')))
    assert not d.snapshot()


def test_real_frame_supported_room_semantics_are_specific():
    c=CounterTimeline();o=c.consume(read(0,4,label='戏法空间'))
    assert o['inferred_elapsed_turns']==1 and o['possible_actual_remaining']==[4]
    assert o['revealed_total_duration']==5


def test_command_anchor_persists_into_immediate_move_menu():
    v=VisualPhaseEstimator('b')
    for f in [frame(0,main=True),frame(.5,main=True),frame(1,actions=['a']),frame(1.5,actions=['b']),
              frame(2,main=True),frame(2.5,menu='move_selection',command_label=True)]:v.consume(f)
    assert v.segments[0]['status']=='confirmed'
    assert v.segments[0]['end']==[1.5,2]


def test_too_many_executions_with_missing_command_remains_ambiguous():
    v=VisualPhaseEstimator('b')
    for f in [frame(0,main=True),frame(.5,main=True),frame(1,actions=['a','b','c','d','e']),
              frame(1.5,main=True),frame(2,main=True)]:v.consume(f)
    assert v.segments[0]['status']=='ambiguous'


def test_local_duration_clock_uses_documented_rules_without_absolute_turn():
    d=EffectDurations();d.consume(dict(id='start',kind='effect',effect='trick_room',family='trick_room',scope='field',
        change='start',verified=True,timestamp=2.1),dict(number=None))
    segment=sequence().segments[0];d.advance_visual_boundary(segment)
    row=d.snapshot()[0]
    assert row['start_turn'] is None and row['activation_timestamp']==2.1
    assert row['visual_clock']['remaining_support']==[4]
    d.advance_visual_boundary(segment)
    assert len(d.snapshot()[0]['visual_clock']['segments'])==1
    next_segment=dict(segment,id='next',command_start_time=3,next_command_time=6)
    d.advance_visual_boundary(next_segment)
    assert d.snapshot()[0]['visual_clock']['remaining_support']==[3]
    gap=dict(segment,id='gap',command_start_time=9,next_command_time=12)
    d.advance_visual_boundary(gap)
    assert d.snapshot()[0]['visual_clock']['remaining_support']==[0,1,2,3]


def test_cached_reader_preserves_raw_text_and_minimum_confidence():
    from battle_evidence.visual_offline import cached_counter
    row=dict(source_id='f',timestamp=1,image='frame.png',ui=dict(regions=[dict(region_type='field_indicator',
        bounds=[267,26,556,57],ocr=dict(label=dict(raw_text='下雨状态',confidence=.99),counter=dict(raw_text='2/5',confidence=.91)))]))
    raw=cached_counter(row)[0]
    assert raw['parsed']['ocr_confidence']==.91 and raw['parsed']['raw_display']=='2/5'
    assert raw['raw']['label']['raw_text']=='下雨状态'


def test_elapsed_relation_with_activation_is_withheld():
    c=CounterTimeline()
    for t,n in [(0,4),(.5,4),(3,3),(3.5,3)]:c.consume(read(t,n))
    out=reconcile_segments(sequence().segments,c,[dict(kind='effect',effect='rain',change='start',timestamp=2)])
    assert out[0]['counter_evidence'][0]['status'].startswith('activation_or_counter_epoch_changed')


def test_uncertain_local_segment_does_not_tick_documented_duration():
    d=EffectDurations();d.consume(dict(id='start',kind='effect',effect='tailwind',family='tailwind',scope='self',
        change='start',verified=True,timestamp=2.1),dict(number=None))
    segment=sequence(gap=5).segments[0];d.advance_visual_boundary(segment)
    assert 'visual_clock' not in d.snapshot()[0]


def test_cross_battle_and_revised_frames_rejected():
    v=VisualPhaseEstimator('b');f=frame(0,main=True);v.consume(f)
    assert v.consume(f)==dict(status='duplicate_ignored')
    with pytest.raises(ValueError):v.consume(dict(f,signals={}))
    with pytest.raises(ValueError):v.consume(dict(frame(1),battle_id='other'))


def test_ui_counter_does_not_tick_or_duplicate_on_repeat_source():
    d=EffectDurations();c=CounterTimeline();o=c.consume(read(1,0))
    d.observe_ui_counter(o);before=d.snapshot();d.observe_ui_counter(o)
    assert d.snapshot()==before


@pytest.mark.local_artifacts
def test_real_pressed_fight_variant():
    import cv2
    from pathlib import Path
    from recognition.command_checkpoint import inspect_command
    from battle_evidence.visual_controls import selected_fight
    path=Path('.cache/battles/sample_battle_7/event-driven/production-first-pass-v1/frames/000884.png')
    if not path.exists():pytest.skip('optional preserved B7 native frame')
    image=cv2.imread(str(path));base=inspect_command(image)
    assert not base['normal_controls']
    improved=selected_fight(image,base,dict(phase='battle_screen',overlay=None))
    assert improved['normal_controls'] and len(improved['visible_slots'])==4
    assert not selected_fight(image,base,dict(phase='pokemon_selection',overlay=None))['normal_controls']


def test_cross_battle_and_overlapping_visual_membership_rejected():
    turns=TurnReconstruction('b');s=sequence().segments[0]
    with pytest.raises(ValueError):turns.attach_visual([dict(s,battle_id='other')])
    with pytest.raises(ValueError):turns.attach_visual([s,dict(s,id='overlap')])
    assert not turns.visual_segments


def test_missing_image_qualifies_regular_timestamp_segment():
    v=sequence([frame(1,missing_image=True)])
    assert v.segments[0]['status']=='supported_but_incomplete'
    assert v.segments[0]['gaps'][0]['reason']=='missing_cached_frame'


def test_feature_reuse_cannot_duplicate_actions_or_retain_event_interpretations():
    from battle_evidence.visual_offline import fresh_feature
    old=frame(1,main=True,actions=['a'],faint=True,sendout=True)
    reused=fresh_feature(old)
    assert reused['actions']==[] and 'faint' not in reused['signals'] and 'sendout' not in reused['signals']
    assert reused['signals']['normal_controls'] and old['actions']
    assert fresh_feature(reused)==reused


def test_terminal_battle_never_acquires_later_menu_as_next_turn():
    v=VisualPhaseEstimator('b')
    for f in [frame(0,main=True),frame(.5,main=True),frame(1,actions=['a']),frame(1.5,actions=['b']),
              frame(2,battle_end=True),frame(2.5,main=True),frame(3,main=True)]:v.consume(f)
    assert not v.segments and v.export()['terminal_observed']
    assert v.history[-1]['phase']=='POST_TURN_TRANSITION'


@pytest.mark.parametrize('label,scope',[('顺风状态','unknown'),('我方顺风状态','self'),('对手顺风状态','opponent')])
def test_real_supported_tailwind_semantics_do_not_resolve_unlabeled_side(label,scope):
    c=CounterTimeline();o=c.consume(read(0,3,d=4,label=label))
    assert o['scope']==scope and o['displayed_remaining']==3
    assert o['inferred_elapsed_turns']==1 and o['possible_actual_remaining']==[3]


def test_unanchored_move_menu_is_not_falsely_called_forced_replacement():
    v=VisualPhaseEstimator('b')
    for f in [frame(0,main=True),frame(.5,main=True),frame(1,actions=['a']),frame(1.5,actions=['b']),
              frame(2,menu='move_selection'),frame(2.5,main=True),frame(3,main=True)]:v.consume(f)
    assert v.history[4]['phase']=='POST_TURN_TRANSITION'
    s=v.segments[0]
    assert s['status']=='supported_but_incomplete' and s['end']==[1.5,2.5]
    assert s['reasons']==['unanchored_command_menu_before_native_return']
