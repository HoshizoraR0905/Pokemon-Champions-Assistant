"""Production cleanup: candidate gating, preserved resume context and sampling."""
from copy import deepcopy
from collections import Counter
import sys
from types import SimpleNamespace

import pytest

from recognition.double_faint import DoubleFaintVerifier
from recognition.context import RecognitionContext, TeamMember, context_dump, context_restore
from recognition.event_schedule import EventConfig, EventInspection
from tests.test_double_faint import scenario


def rows_for(engine):
    rows = [dict(timestamp=0,source_id='preview',sha256='preview',image='unused.png',ui={},
        occurrence_decision=dict(events=[]),trainer_observations=[dict(battle_id='test',side=side,
            raw_text=name,entity_kind='trainer',ocr_confidence=.99,evidence=[dict(timestamp=0,source='preview',sha256='preview')])
            for side,name in [('self','Host'),('opponent','Guest')]])]
    for record in engine.history:
        event = deepcopy(record.event)
        if event['event_type'] == 'entry_observation':continue
        t = event['attributes'].get('observation_time', len(rows))
        rows.append(dict(timestamp=t, source_id=f'frame#{t}', sha256=str(t), image='unused.png',
            identity_mode='lightweight', ui={}, occurrence_decision=dict(events=[event])))
    return rows


def test_same_side_pair_is_replayed_once_and_admitted_without_changing_evidence():
    rows = rows_for(scenario())
    before = deepcopy(rows)
    verifier = DoubleFaintVerifier('test')
    for n in range(1, len(rows)+1):
        verifier.observe_prefix(rows[:n], [])
    assert verifier.counts['candidate_prefix_replays'] == 1
    assert 'opponent' in verifier.pending
    assert {ep['species_id'] for ep in verifier.pending['opponent']} == {903, 373}
    verifier.observe_prefix(rows, [])
    assert verifier.counts['candidate_prefix_replays'] == 1
    assert rows == before
    # Resume rebuilds the scheduling cursor from immutable evidence exactly once.
    resumed = DoubleFaintVerifier('test'); resumed.observe_prefix(rows, [])
    assert resumed.pending == verifier.pending


def test_ordinary_topology_and_opposite_side_faints_never_replay(monkeypatch):
    from tracking.state_engine import StateEngine
    rows = rows_for(scenario())
    faint = [r for r in rows if r['occurrence_decision']['events'] and r['occurrence_decision']['events'][0]['event_type']=='faint']
    faint[1]['occurrence_decision']['events'][0]['side'] = 'self'
    def forbidden(*args, **kwargs):
        raise AssertionError('No same-side double faint: replay forbidden')
    monkeypatch.setattr(StateEngine, 'replay', forbidden)
    verifier = DoubleFaintVerifier('test')
    for n in range(1, len(rows)+1):verifier.observe_prefix(rows[:n], [])
    assert not verifier.pending
    assert not verifier.counts['candidate_prefix_replays']
    # Empty pending work must not even access the recognizer/frame/row.
    verifier.verify(None, None, None, None, None)


def test_single_faint_then_replacement_is_not_a_double_faint(monkeypatch):
    from tracking.state_engine import StateEngine
    rows = rows_for(scenario())
    # Move first replacement between the two departures.
    indices = [i for i,r in enumerate(rows) if r['occurrence_decision']['events'] and r['occurrence_decision']['events'][0]['event_type']=='faint']
    rows.insert(indices[1], rows.pop(indices[1]+1))
    monkeypatch.setattr(StateEngine, 'replay', lambda *a, **k: pytest.fail('ordinary replacement replayed'))
    verifier = DoubleFaintVerifier('test'); verifier.observe_prefix(rows, [])
    assert not verifier.counts['candidate_prefix_replays']


def test_context_roundtrip_keeps_checkpoint_schema_and_evidence():
    context = RecognitionContext()
    context.observed_team['one'] = TeamMember('one','pokeapi:species:25',source='visible_ocr')
    context.opponent_preview = {'pokeapi:species:903'}
    context.preview_observations = [dict(source_id='frame#1', species_id=903)]
    context.previous = {'own:species': ('id','literal',2)}
    context.last_source = 'frame#1'; context.last_index = 4
    saved = context_dump(context)
    restored = RecognitionContext(); context_restore(restored, deepcopy(saved))
    assert context_dump(restored) == saved


def test_three_fps_monitoring_stays_independent_of_command_inspection():
    scheduler = EventInspection(EventConfig(active_fps=3))
    scheduler.monitor(0, dict(visible=False))
    assert scheduler.advance(0,phase='battle',message_visible=False,changed=False) == 3
    assert scheduler.next_time == 1/3
    scheduler.monitor(1/3,dict(visible=True))
    assert scheduler.advance(1/3,phase='command',message_visible=False,changed=False) == 1
    assert scheduler.monitor(2/3,dict(visible=True),message_visible=True)
    assert scheduler.advance(2/3,phase='command',message_visible=True,changed=False) == 3


def test_production_rejects_previously_ignored_ocr_and_interval(monkeypatch):
    import main
    for option in ['--interval', '--ocr']:
        monkeypatch.setattr(sys, 'argv', ['main.py','--video','unused.mp4','--profile','event-driven',
            option, '1' if option=='--interval' else 'tesseract'])
        with pytest.raises(SystemExit) as exc:main.main()
        assert exc.value.code == 2


@pytest.mark.parametrize('fps', [2.,3.])
def test_ffmpeg_sampling_grid_uses_configured_rate(tmp_path, fps):
    import subprocess
    import imageio_ffmpeg
    from recognition.fast_video import decoded_frames
    video = tmp_path/'tiny.mp4'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-loglevel','error','-f','lavfi','-i',
        'color=c=black:s=64x32:r=12:d=1','-c:v','libx264','-pix_fmt','yuv420p',str(video)],check=True)
    rows = list(decoded_frames(video,tmp_path/'decode.log',sample_fps=fps))
    assert [r['target_timestamp'] for _,r in rows] == [i/fps for i in range(int(fps))]
    assert all(target <= r['timestamp'] < target + 1/fps for target,(_,r) in zip([i/fps for i in range(int(fps))],rows))


def test_other_side_switch_does_not_discard_a_pending_pair():
    rows = rows_for(scenario())
    verifier = DoubleFaintVerifier('test'); verifier.observe_prefix(rows, [])
    pair = deepcopy(verifier.pending['opponent'])
    event = deepcopy(rows[-1]['occurrence_decision']['events'][0])
    event.update(event_id='own-switch',event_type='switch_out',side='self')
    event['attributes']['observation_time'] = 7
    rows.append(dict(timestamp=7,occurrence_decision=dict(events=[event])))
    verifier.observe_prefix(rows, [])
    assert verifier.pending['opponent'] == pair
    assert verifier.counts['candidate_prefix_replays'] == 1
