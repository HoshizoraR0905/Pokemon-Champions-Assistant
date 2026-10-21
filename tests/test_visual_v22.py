"""Genuine source-sequence regressions, separate from controlled reduced-HUD cases."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from battle_evidence.visual import VisualPhaseEstimator
from battle_evidence.visual_v22 import VisualPhaseEstimatorV22
from speed_inference.offline import file_hash

FIXTURES=Path(__file__).parent/'fixtures/battle_evidence'


def real(number):
    return json.loads((FIXTURES/f'visual_v22_b{number}_real.json').read_text())


def feed(v, observations):
    for o in observations:v.consume(o)
    return v


def test_genuine_three_HUD_source_sequence_recovers_final_entry():
    fixture=real(10);v=feed(VisualPhaseEstimatorV22(fixture['battle_id']),fixture['observations'])
    assert len(v.segments)==1
    assert v.segments[0]['end']==fixture['expected']['next_command_interval']
    assert v.segments[0]['status']=='confirmed'
    assert v.reconciliations[0]['confirmed_at']==786.0316666666666
    assert len(v.segments[0]['actions'])==3
    frozen=feed(VisualPhaseEstimator(fixture['battle_id'],profile='v2'),fixture['observations'])
    assert not frozen.segments and frozen.pending
    assert all(len(o['image_sha256'])==64 for o in fixture['observations'])


def test_real_B6_recovery_log_interruption_and_unchanged_late_prediction():
    fixture=real(6);v=VisualPhaseEstimatorV22(fixture['battle_id'])
    for o in fixture['observations']:
        v.consume(o)
        if 468<=o['timestamp']<471:
            assert not o['signals']['normal_controls'] and not v.segments
        if o['timestamp']==471.0133333333333:
            assert len(v.candidate)==1 and not v.segments
        if 472<=o['timestamp']<475:
            assert o['signals']['overlay']=='battle_log_overlay'
            assert not v.candidate and not v.segments
    assert v.segments[0]['end']==fixture['expected']['next_command_interval']
    assert not v.reconciliations


@pytest.mark.local_artifacts
@pytest.mark.parametrize('number',[6,10])
def test_real_source_hashes_and_cached_recognition_really_match(number):
    fixture=real(number);paths=[Path(fixture['source_observations']),Path(fixture['source_prediction'])]
    if not all(p.exists() for p in paths):pytest.skip('Optional historical source artifacts absent')
    assert file_hash(paths[0])==fixture['source_observations_sha256']
    assert file_hash(paths[1])==fixture['source_prediction_sha256']
    rows={r['source_id']:r for r in json.loads(paths[0].read_text())['observations']}
    for o in fixture['observations']:
        row=rows[o['source_id']]
        assert row['timestamp']==o['timestamp'] and row['image']==o['image']
        assert Path(o['image']).is_file()  # Present but damaged evidence must fail.
        assert file_hash(Path(o['image']))==o['image_sha256']


# Controlled synthetic sequences below are counterexamples, not real-frame proof.
def f(t, *, cards=4, controls=True, timer=20, actions=(), **extra):
    slots=['own_active_1','own_active_2','opponent_active_2']
    if cards==4:slots.append('opponent_active_1')
    if cards==0:slots=[]
    s=dict(hud_cards=cards,hud_slots=slots,normal_controls=controls,native_dual_controls=controls,
           command_label=timer is not None,command_timer=timer,battle_view=cards==4,cached_phase='battle_screen' if cards==4 else 'battle_animation')
    s.update(extra)
    return dict(id=f'f{t}',source_id=f's{t}',battle_id='b',timestamp=t,signals=s,
                actions=[dict(event_id=a,live_execution=True) for a in actions])


def resolving(*, pivot=False, faint=True, resumed=True):
    v=VisualPhaseEstimatorV22('b')
    feed(v,[f(0),f(.5),f(1,cards=0,controls=False,timer=None,actions=['a'],faint=faint,pivot_action=pivot)])
    if resumed:v.consume(f(1.5,cards=0,controls=False,timer=None,actions=['b']))
    return v


def test_synthetic_three_HUD_return_needs_three_continuous_samples():
    v=resolving();v.consume(f(2,cards=3,timer=44));v.consume(f(2.5,cards=3,timer=44,controls=False))
    assert not v.segments
    v.consume(f(3,cards=3,timer=43,controls=False))
    assert len(v.segments)==1 and v.reconciliations


def test_synthetic_three_HUD_submenu_return_never_adds_a_turn():
    v=VisualPhaseEstimatorV22('b');feed(v,[f(0),f(.5),f(1,cards=3,controls=False,menu='move_selection')])
    feed(v,[f(t,cards=3,timer=44) for t in (1.5,2,2.5)])
    assert not v.segments


@pytest.mark.parametrize('mode',['pivot','forced','unresumed','timer_only','no_reset','no_history','no_occupancy','zero_HUD','missing','overlay','new_action','gap'])
def test_synthetic_reduced_HUD_safeguards(mode):
    v=resolving(pivot=mode=='pivot',resumed=mode!='unresumed')
    if mode=='forced':v.consume(f(1.75,cards=3,controls=False,menu='pokemon_selection',timer=44))
    if mode=='no_history':v.previous_slots=set()
    rows=[f(t,cards=3,timer=44) for t in (2,2.5,3)]
    for o in rows:
        if mode=='timer_only':o['signals'].update(normal_controls=False,native_dual_controls=False)
        if mode=='no_reset':o['signals']['command_timer']=19
        if mode=='no_occupancy':o['signals']['hud_slots']=['own_active_1','own_active_2','own_active_3']
        if mode=='zero_HUD':o['signals'].update(hud_cards=0,hud_slots=[])
    if mode=='missing':rows[1]['signals']['missing_image']=True
    if mode=='overlay':rows[1]['signals']['overlay']='battle_log_overlay'
    if mode=='new_action':rows[1]['actions']=[dict(event_id='c',live_execution=True)]
    if mode=='gap':rows[1]['timestamp']=4;rows[2]['timestamp']=4.5
    feed(v,rows)
    assert not v.segments


def test_original_four_HUD_anchor_and_submenu_behavior_unchanged():
    rows=[f(0),f(.5),f(1,cards=0,controls=False,timer=None,actions=['a']),
          f(1.5,cards=0,controls=False,timer=None,actions=['b']),f(2),f(2.5)]
    old=feed(VisualPhaseEstimator('b',profile='v2'),rows)
    new=feed(VisualPhaseEstimatorV22('b'),rows)
    assert old.segments==new.segments and old.history==new.history


@pytest.mark.local_artifacts
def test_frozen_results_references_pages_and_protected_sources_preserved():
    p=Path('.cache/m34-visual-v22/preservation-baseline.json')
    if not p.exists():pytest.skip('Optional preservation snapshot absent')
    baseline=json.loads(p.read_text())
    for path,sha in baseline.items():assert Path(path).exists() and file_hash(Path(path))==sha,path


def test_human_observations_do_not_approve_agent_localization_or_change_history():
    root=Path('reports/battles/sample_battle_6/inputs')
    observation=json.loads((root/'M3.4-visual-human-observation-v22.json').read_text())
    old=json.loads((root/'M3.4-visual-reference-v21.json').read_text())
    new=json.loads((root/'M3.4-visual-reference-v22.json').read_text())
    assert len(observation['user_observations'])==2 and not observation['human_approved']
    a=next(t for t in old['turns'] if t['id'].endswith(':06'))
    b=next(t for t in new['turns'] if t['id'].endswith(':06'))
    assert a['command_start']['interval']==[470.01166666666666,472.0133333333333]
    assert b['command_start']['interval']==[470.5133333333333,471.0133333333333]
    assert not b['command_start']['human_approved']


def test_contextually_normalized_observation_duplicate_and_revision_guards():
    v=resolving();o=f(2,cards=3,timer=44);v.consume(o)
    assert v.consume(deepcopy(o))==dict(status='duplicate_ignored')
    changed=deepcopy(o);changed['signals']['command_timer']=42
    with pytest.raises(ValueError,match='revision'):v.consume(changed)
    other=deepcopy(o);other['battle_id']='other'
    with pytest.raises(ValueError,match='Cross-battle'):v.consume(other)
