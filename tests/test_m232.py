"""Cache-only replay regressions, using synthetic evidence rather than media."""
from scripts.m232_replay import reconstruct, replay_stream, initial_checkpoint


def test_message_and_log_order_are_not_fused():
    data = {'observations': [dict(source_id='sample_battle_0.mp4#10',sha256='abc',image='frame.jpg',timestamp=10,
        message=dict(raw_text='开始下雨了！',confidence=.99))]}
    streams, metrics = reconstruct(data,'sample_battle_0')
    assert streams['log'] == []
    event = streams['video'][0]
    assert event['evidence'][0]['source_type'] == 'video_message'
    assert event['evidence'][0]['details']['turn'] is None
    state, hidden, timeline = replay_stream('sample_battle_0',streams['video'])
    assert state['state']['weather']['kind']['value'] == 'rain'
    assert len(timeline['entries']) == 2


def test_partial_initial_checkpoint_does_not_guess_instances():
    initial, timestamp = initial_checkpoint({'observations':[]},'sample_battle_4')
    assert initial.pokemon == {}
    assert timestamp is None


def test_separated_repeated_messages_survive():
    rows=[dict(source_id=f'video#{t}',sha256=str(t),image='frame.jpg',timestamp=t,
        message=dict(raw_text='开始下雨了！',confidence=.99)) for t in [10,12,30]]
    streams,_=reconstruct({'observations':rows},'sample_battle_0')
    assert len(streams['video']) == 2
