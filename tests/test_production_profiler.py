import json
from types import SimpleNamespace
import pytest
from scripts.production_profiler import Recorder,event_source


def test_nested_exclusive_timing_and_unchanged_values_and_errors(tmp_path):
    tick=[0.]
    def clock():return tick[0]
    r=Recorder(tmp_path,clock=clock)
    def inner():tick[0]+=2;return object_value
    object_value=object()
    obj=SimpleNamespace(inner=inner)
    def outer():tick[0]+=1;result=obj.inner();tick[0]+=3;return result
    obj.outer=outer;r.patch(obj,'inner','inner');r.patch(obj,'outer','outer')
    assert obj.outer() is object_value
    r.close('complete')
    ops=[json.loads(line) for line in (tmp_path/'operations.jsonl').read_text().splitlines()]
    assert [(o['module'],o['inclusive_seconds'],o['exclusive_seconds']) for o in ops]==[('inner',2,2),('outer',6,4)]
    assert obj.inner is inner and obj.outer is outer


def test_source_attribution_survives_late_execution_and_shared_sources_abstain(tmp_path):
    r=Recorder(tmp_path);r.source=dict(timestamp=2,source_id='video#2');r.stage='reconstruction'
    with r.span('delayed'):pass
    r.close('complete')
    row=json.loads((tmp_path/'operations.jsonl').read_text())
    assert row['source']['timestamp']==2 and row['stage']=='reconstruction'
    e=dict(event_id='event',attributes=dict(observation_time=10),evidence=[
        dict(source_id='a',details=dict(timestamp=2)),dict(source_id='b',details=dict(timestamp=10))])
    source=event_source(e)
    assert source['timestamp'] is None and source['interval']==[2,10]


def test_exception_is_not_swallowed_and_hooks_are_restored(tmp_path):
    r=Recorder(tmp_path)
    def bad():raise ValueError('original')
    obj=SimpleNamespace(bad=bad);r.patch(obj,'bad','failure')
    with pytest.raises(ValueError,match='original'):obj.bad()
    r.close('failed');assert obj.bad is bad


def test_actual_state_replay_is_unchanged_under_observation(tmp_path):
    from tracking.state_engine import StateEngine
    from tracking.battle_state import BattleState
    from tests.test_evidence_fusion import hud
    def replay():
        engine=StateEngine(BattleState('test'))
        engine.apply(hud(1,1,823),sequence=1)
        return engine.to_dict()
    expected=replay();r=Recorder(tmp_path);r.install()
    try:actual=replay()
    finally:r.close('complete')
    assert actual==expected
    operations=[json.loads(line) for line in (tmp_path/'operations.jsonl').read_text().splitlines()]
    assert any(o['module']=='state_event' and o['source']['timestamp']==1 for o in operations)
