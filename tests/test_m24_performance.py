import pytest
from scripts.report_m24 import timeline_for, measure_segments


def event(kind,t):
    return dict(event_id=f'{kind}{t}',event_type=kind,side='self',attributes=dict(observation_time=t),evidence=[{'source_id':'source'}])


def frame(t,ui,**kw):
    return dict(timestamp=t,source_id=f'frame{t}',ui=dict(phase=ui,confidence=.99),processing_wall_seconds=1.,inspected=True,**kw)


def test_command_subviews_execution_return_and_uncertain_boundaries():
    fs=[frame(0,'team_preview'),frame(1,'team_preview'),frame(2,'move_selection'),frame(3,'move_target_selection'),
        frame(4,'battle_message'),frame(5,'battle_animation'),frame(6,'move_selection'),frame(7,'move_selection')]
    t=timeline_for(fs,[event('send_out',1)],8,[])
    assert [s['phase'] for s in t['samples']]==['PRE_BATTLE','PRE_BATTLE','COMMAND_TIME','COMMAND_TIME','BATTLE_TIME','BATTLE_TIME','COMMAND_TIME','COMMAND_TIME']
    assert t['intervals'][2]['phase']=='COMMAND_TIME'
    assert t['intervals'][3]['phase']=='UNKNOWN' and t['intervals'][3]['boundary_uncertainty_seconds']==1
    assert all(s['turn_number'] is None for s in t['segments'])


def test_forced_replacement_needs_observed_player_input():
    fs=[frame(0,'battle_message'),frame(1,'switch_selection'),frame(2,'switch_selection'),frame(3,'battle_animation')]
    t=timeline_for(fs,[event('send_out',0),event('faint',.5),event('send_out',3)],4,[])
    assert t['samples'][1]['phase']=='COMMAND_TIME' and t['samples'][1]['subtype']=='forced_replacement'
    fs[1]['ui']['phase']='battle_animation'
    t=timeline_for(fs,[event('send_out',0),event('faint',.5),event('send_out',3)],4,[])
    assert t['samples'][1]['phase']=='UNKNOWN'


def test_nested_cost_not_double_counted_startup_shared():
    fs=[frame(0,'move_selection'),frame(1,'move_selection')]
    t=timeline_for(fs,[event('send_out',0)],2,[])
    ops=[dict(module='ocr_inference',source=dict(timestamp=0),inclusive_seconds=.4,exclusive_seconds=.4),
         dict(module='pipeline',source=None,inclusive_seconds=10,exclusive_seconds=7),
         dict(module='state_event',source=dict(timestamp=0),inclusive_seconds=1,exclusive_seconds=1)]
    p=measure_segments(t,fs,ops,[],10)
    assert p['partition_sum']==pytest.approx(10)
    assert sum(s['processing_wall_seconds'] for s in p['segments'])==3
    assert p['shared_unallocated']['processing_wall_seconds']==7
    with pytest.raises(ValueError,match='Overlapping'):measure_segments(t,fs,ops,[],1)


def test_forced_replacement_subtype_survives_visible_command_label():
    fs=[frame(0,'battle_message'),frame(1,'switch_selection',command_label={'visible':True}),
        frame(2,'switch_selection',command_label={'visible':True}),frame(3,'battle_animation')]
    t=timeline_for(fs,[event('send_out',0),event('faint',.5),event('send_out',3)],4,[])
    assert t['samples'][1]['phase']=='COMMAND_TIME'
    assert t['samples'][1]['subtype']=='forced_replacement'


def test_lazy_model_initialization_remains_shared_with_trigger_provenance():
    fs=[frame(0,'move_selection'),frame(1,'move_selection')]
    t=timeline_for(fs,[event('send_out',0)],2,[])
    ops=[dict(module='ocr_model_load',source=dict(timestamp=0),inclusive_seconds=.5,exclusive_seconds=.5)]
    p=measure_segments(t,fs,ops,[],3)
    assert sum(s['processing_wall_seconds'] for s in p['segments'])==1.5
    assert p['shared_unallocated']['processing_wall_seconds']==1.5
    assert p['shared_unallocated']['initialization_triggers'][0]['source']['timestamp']==0
    assert p['partition_sum']==3


def test_opponent_faint_does_not_claim_own_selection_is_forced_replacement():
    fs=[frame(0,'battle_message'),frame(1,'switch_selection'),frame(2,'switch_selection'),frame(3,'battle_animation')]
    faint=event('faint',.5);faint['side']='opponent'
    arrival=event('send_out',3);arrival['side']='opponent'
    t=timeline_for(fs,[event('send_out',0),faint,arrival],4,[])
    assert t['samples'][1]['phase']=='COMMAND_TIME'
    assert t['samples'][1]['subtype'] is None


def test_interval_certainty_coverage_uses_current_timeline_intervals():
    fs=[frame(0,'move_selection'),frame(1,'move_selection'),frame(2,'battle_message')]
    t=timeline_for(fs,[event('send_out',0)],3,[])
    assert set(t['certainty_video_seconds'])=={i['certainty'] for i in t['intervals']}
    assert sum(t['certainty_video_seconds'].values())==3


def test_contiguous_segment_does_not_keep_one_turn_across_differing_evidence():
    fs=[frame(1,'move_selection'),frame(1.5,'move_selection'),frame(2,'move_selection'),frame(3,'move_selection')]
    a=event('turn_boundary',.5);a['attributes'].update(turn=1,boundary='start')
    b=event('turn_boundary',1.8);b['attributes'].update(turn=2,boundary='start')
    t=timeline_for(fs,[event('send_out',0),a,b],4,[])
    commands=[s for s in t['segments'] if s['phase']=='COMMAND_TIME']
    assert len(commands)==1 and commands[0]['turn_number'] is None
    assert t['verified_absolute_turns']==[1,2]
