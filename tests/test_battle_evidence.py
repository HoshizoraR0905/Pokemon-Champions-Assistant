"""Controlled reconstruction contracts; not video recognition accuracy tests."""
from copy import deepcopy
import json
import pytest
from battle_evidence import TurnReconstruction,EffectDurations,KnownBuilds,attribute_hp
from battle_evidence.snapshots import snapshot
from battle_evidence.adapter import compare_actions
from speed_inference import BeliefBank
from speed_inference.controlled import observation
from speed_inference.likelihood import VERIFICATIONS

SOURCES=[dict(source_id='controlled',verification='synthetic')]


def event(i,kind='action',turn=1,**kwargs):
    e=dict(id=f'e:{i}',battle_id='synthetic',position=i,timestamp=float(i),origin='synthetic',kind=kind,sources=deepcopy(SOURCES),
        side='self',turn_evidence=dict(number=turn,verified=True,sources=deepcopy(SOURCES),execution_order=i,
        execution_order_verified=True,decision_id=f'd:{turn}'))
    e.update(kwargs);return e


def boundary(i,turn,when):
    e=event(i,'boundary',turn,boundary=when);e['turn_evidence']['boundary']=when;return e


def apply(tracker,e):return tracker.consume(e,dict(number=e.get('turn_evidence',{}).get('number')))


def test_normal_turns_and_continuity_membership():
    t=TurnReconstruction('synthetic')
    for e in [boundary(1,1,'start'),event(2),boundary(3,1,'end'),boundary(4,2,'start'),event(5,turn=2),boundary(6,2,'end')]:t.consume(e)
    out=t.export();assert [x['status'] for x in out['turns']]==['complete','complete'];assert out['unassigned_actions']==[]
    assert out['turns'][0]['actions_by_verified_execution_order']==['e:2']
    t=TurnReconstruction('synthetic');t.consume(boundary(1,1,'start'));e=event(2);e.pop('turn_evidence')
    e['turn_continuity']=dict(verified=True,sources=SOURCES,execution_order=1,execution_order_verified=True,decision_id='d:1')
    assert t.consume(e)['number']==1


def test_command_battle_phase_and_forced_switch_do_not_number_turns():
    t=TurnReconstruction('synthetic')
    for i,kind in enumerate(['command_window','phase','forced_replacement','phase','action','command_window','action']):
        e=event(i,kind);e.pop('turn_evidence');t.consume(e)
    assert t.turns==[] and len(t.windows)==2 and len(t.unassigned)==2
    assert all(w['number'] is None for w in t.windows)


def test_partial_and_ambiguous_boundaries_regression_duplicate():
    t=TurnReconstruction('synthetic');e=event(1);t.consume(e)
    assert t.turns[0]['status']=='partial';dupe=deepcopy(e);dupe['position']=99
    assert t.consume(dupe)['status']=='duplicate_ignored'
    revised=deepcopy(e);revised['timestamp']=999
    with pytest.raises(ValueError):t.consume(revised)
    t.consume(boundary(3,2,'start'));assert t.consume(event(4,turn=1))['number'] is None
    assert t.issues[0]['reason']=='turn_number_regression'


def test_tailwind_turn_count_includes_activation_separate_sides_reapply():
    d=EffectDurations();apply(d,boundary(1,1,'start'))
    apply(d,event(2,'effect',effect='tailwind',family='tailwind',scope='opponent',change='start',verified=True))
    assert d.snapshot()[0]['remaining_support']==[4]
    apply(d,boundary(3,1,'end'));assert d.snapshot()[0]['remaining_support']==[3]
    apply(d,boundary(4,2,'start'));assert d.snapshot()[0]['remaining_support']==[3]
    apply(d,event(5,'effect',2,effect='tailwind',scope='self',change='start',verified=True))
    apply(d,boundary(6,2,'end'));assert {x['scope']:x['remaining_support'] for x in d.snapshot()}=={'opponent':[2],'self':[3]}
    apply(d,boundary(7,3,'start'));apply(d,boundary(8,3,'end'));apply(d,boundary(9,4,'start'));apply(d,boundary(10,4,'end'))
    assert next(x for x in d.snapshot() if x['scope']=='opponent')['active'] is False
    apply(d,event(11,'effect',5,effect='tailwind',scope='opponent',change='start',verified=True))
    assert next(x for x in d.snapshot() if x['scope']=='opponent')['remaining_support']==[4]


def test_missing_end_inferred_at_confirmed_next_start_once():
    d=EffectDurations();apply(d,boundary(0,1,'start'));apply(d,event(1,'effect',effect='trick_room',scope='field',change='start',verified=True))
    apply(d,boundary(2,2,'start'));assert d.snapshot()[0]['remaining_support']==[4]
    apply(d,boundary(3,2,'end'));assert d.snapshot()[0]['remaining_support']==[3]
    apply(d,boundary(4,2,'end'));assert d.snapshot()[0]['remaining_support']==[3]
    apply(d,event(5,'effect',2,effect='trick_room',scope='field',change='end',verified=True))
    assert d.snapshot()[0]['active'] is False


@pytest.mark.parametrize('effect,initial',[('rain',[5,8]),('sun',[8]),('sandstorm',[5]),('snow',[5,8]),('grassy',[5,8]),('psychic',[5,8]),('light_screen',[5,8])])
def test_variable_and_extended_durations_require_explicit_documented_rule(effect,initial):
    d=EffectDurations();apply(d,boundary(0,1,'start'))
    e=event(1,'effect',effect=effect,scope='field',change='start',verified=True,initial_support=initial,
        duration_verified=True,duration_sources=SOURCES,decrement_at='turn_end')
    apply(d,e);assert d.snapshot()[0]['remaining_support']==initial
    apply(d,boundary(2,1,'end'));assert d.snapshot()[0]['remaining_support']==[x-1 for x in initial]
    apply(d,event(3,'effect',effect=effect,scope='field',change='extend',extension=3,duration_verified=True,duration_sources=SOURCES))
    assert d.snapshot()[0]['remaining_support']==[x+2 for x in initial]


def test_unknown_weather_and_unknown_activation_no_exact_countdown():
    d=EffectDurations();e=event(1,'effect',effect='rain',scope='field',change='start',verified=True);apply(d,e)
    assert d.snapshot()[0]['remaining_support'] is None
    e=event(2,'effect',effect='trick_room',scope='field',change='start',verified=True);e['turn_evidence']={};apply(d,e)
    assert next(x for x in d.snapshot() if x['effect']=='trick_room')['remaining_support']==[1,2,3,4,5]
    e=event(3);e['turn_evidence']={};apply(d,e)
    row=next(x for x in d.snapshot() if x['effect']=='trick_room');assert row['remaining_support']==[0,1,2,3,4,5] and row['active'] is None


def test_duration_gap_observe_preserves_count_and_replacement():
    d=EffectDurations();apply(d,boundary(0,1,'start'));apply(d,event(1,'effect',effect='tailwind',scope='self',change='start',verified=True))
    apply(d,boundary(2,1,'end'));apply(d,event(3,'effect',effect='tailwind',scope='self',change='observe',verified=True))
    assert d.snapshot()[0]['remaining_support']==[3]
    apply(d,boundary(4,5,'start'));assert d.snapshot()[0]['status']=='bounded'
    for i,name in enumerate(['rain','sun'],6):apply(d,event(i,'effect',5,effect=name,family='weather',scope='field',change='start',verified=True))
    assert next(x for x in d.snapshot() if x['effect']=='rain')['status']=='replaced'


def known_record():
    return dict(identity='Charizard',form='base',training_points={s:0 for s in ['hp','attack','defense','special_attack','special_defense','speed']},
        alignment=dict(increase=None,decrease=None),verified=True,evidence=deepcopy(SOURCES),ability='Blaze',item='none')


def test_exact_build_stats_and_unknown_combat_modifiers():
    k=KnownBuilds();r=known_record();original=deepcopy(r);k.register(battle_id='synthetic',instance_id='own:1',record=r)
    assert r==original;assert k.records['synthetic','own:1']['stats']['hp']==153;assert k.records['synthetic','own:1']['stats']['speed']==120
    o=observation();p=k.projection('synthetic','own:1',o['context']['own'],o['context']['field'],profile='showdown-champions-reference-v1')
    assert p['effective_speed']==120 and all(v is None for v in p['combat_stats'].values())
    p=k.projection('synthetic','own:1',{}, {},profile='champions-evidence-only-v1');assert p['effective_speed'] is None
    assert k.projection('other','own:1',{}, {},profile='champions-evidence-only-v1')['status']=='unknown'
    r['observed_stats']={'speed':999}
    with pytest.raises(ValueError):KnownBuilds().register(battle_id='x',instance_id='p',record=r)


def test_existing_team_configuration_import_requires_manual_fields_and_binding():
    from team_configuration import TeamConfiguration
    team=TeamConfiguration();team.correct('own_team_1','identity',canonical_id='pokeapi:pokemon:6',reviewer='controlled')
    team.correct('own_team_1','speed',value=120,reviewer='controlled');original=deepcopy(team.data)
    k=KnownBuilds();k.import_team(team,battle_id='synthetic',bindings={'own_team_1':'own:1'},binding_evidence=SOURCES)
    assert k.records['synthetic','own:1']['stats']['speed']==120 and k.records['synthetic','own:1']['stats']['hp'] is None
    assert team.data==original
    with pytest.raises(ValueError):k.import_team(team,battle_id='synthetic',bindings={},binding_evidence=[])


def reading(i,current,**kwargs):
    r=dict(battle_id='synthetic',instance_id='own:1',epoch='initial',position=i,timestamp=float(i),current=current,maximum=153,verified=True,sources=deepcopy(SOURCES));r.update(kwargs);return r


def attack(**kwargs):
    c=dict(kind='attack',verified=True,sources=deepcopy(SOURCES),attacker='opponent:1',receiver='own:1',move='Flamethrower',event_id='attack',position=2,resolution_snapshot_id='snapshot:resolution',target_instances=['own:1'],
        verification={k:True for k in ['attacker_identity','move_identity','receiver_identity','targeting','resolution_state','single_cause','coverage','no_redirection','single_hit']});c.update(kwargs);return c


def hp_case(causes=None,**after):return attribute_hp(reading(1,153),reading(3,100,**after),causes if causes is not None else [attack()],coverage=dict(complete=True,sources=SOURCES))


def test_clean_exact_attack_and_spread_per_target():
    assert hp_case()['exact_damage']==53
    c=attack(spread=True);assert not hp_case([c])['damage_inference_eligible']
    c['per_target_resolution']=True;assert hp_case([c])['damage_inference_eligible']


@pytest.mark.parametrize('cause',[attack(multi_hit=True),attack(verification={}),attack(receiver='other'),attack(verified=False)])
def test_ambiguous_attack_not_damage_measurement(cause):
    r=hp_case([cause]);assert r['raw_delta']==-53 and r['exact_damage'] is None and r['reasons']


@pytest.mark.parametrize('kind,delta',[('residual',-10),('recoil',-10),('self_damage',-10),('healing',10)])
def test_non_attack_causes_retained(kind,delta):
    r=attribute_hp(reading(1,100),reading(3,100+delta),[dict(kind=kind,verified=True,sources=SOURCES,event_id='cause',position=2,receiver='own:1')],coverage=dict(complete=True,sources=SOURCES))
    assert r['cause_confirmed'] and r['classification']==kind and not r['damage_inference_eligible']


def test_multiple_unknown_and_censored_hp_changes():
    assert hp_case([attack(),attack()])['classification']=='multiple_causes'
    assert hp_case([])['classification']=='unknown'
    for change in [dict(maximum=200),dict(epoch='different'),dict(instance_id='different'),dict(verified=False)]:assert hp_case(**change)['exact_damage'] is None
    r=attribute_hp(reading(1,100),reading(3,0),[attack()],coverage=dict(complete=True,sources=SOURCES));assert 'fainting_hp_loss_censors_actual_damage' in r['reasons']


def test_snapshot_immutable_and_state_at_action_vs_after_end():
    t=TurnReconstruction('synthetic');d=EffectDurations();e=event(1,'effect',effect='tailwind',scope='self',change='start',verified=True);a=t.consume(e);apply(d,e)
    state={'pokemon':{}};before=snapshot(e,'before',state,d,a);state['pokemon']['new']={};apply(d,boundary(2,1,'end'))
    assert before['observable']=={'pokemon':{}} and before['effects'][0]['remaining_support']==[4]
    assert d.snapshot()[0]['remaining_support']==[3]


def setup_pair():
    t=TurnReconstruction('synthetic');first=event(1,instance_id='opponent:1',side='opponent',move='Flamethrower',move_verified=True,priority=0,priority_verified=True)
    second=event(2,instance_id='own:1',move='Flamethrower',move_verified=True,priority=0,priority_verified=True)
    for e in (first,second):t.consume(e)
    context=observation()['context'];context['own']['actual_speed']=120
    annotation=dict(verified=True,sources=SOURCES,decision_context=context,decision_id='d:1',stat_epoch='initial',continuity_verified=True,verification={k:True for k in VERIFICATIONS})
    s=snapshot(first,'before',{},EffectDurations(),t.assignment[first['id']],annotation=annotation)
    snapshots={first['id']:dict(before=s)};k=KnownBuilds();k.register(battle_id='synthetic',instance_id='own:1',record=known_record())
    return t,first,second,snapshots,k


def test_speed_adapter_supported_update_and_repeated_underlying_evidence():
    t,a,b,s,k=setup_pair();bank=BeliefBank();r=compare_actions(a,b,t,s,k,bank,profile='showdown-champions-reference-v1')
    assert r['status']=='updated' and r['update']['after']['information_gain_nats']>0
    assert compare_actions(a,b,t,s,k,bank,profile='showdown-champions-reference-v1')['status']=='duplicate_ignored'
    assert compare_actions(a,b,t,s,k,BeliefBank())['status']=='ineligible'
    assert 'belief_rule_profile_mismatch_requires_explicit_replay' in compare_actions(a,b,t,s,k,bank)['reasons']


@pytest.mark.parametrize('condition',['priority','hidden_item','continuity','unknown_build','switch','item_change','form_change'])
def test_speed_adapter_rejects_missing_or_changed_context(condition):
    t,a,b,s,k=setup_pair()
    if condition=='priority':b['priority_verified']=False
    elif condition=='hidden_item':s[a['id']]['before']['annotation']['decision_context']['opponent']['item']=None
    elif condition=='continuity':s[a['id']]['before']['annotation']['continuity_verified']=False
    elif condition=='unknown_build':k=KnownBuilds()
    elif condition in ('switch','item_change'):
        e=event(3,'switch' if condition=='switch' else 'state_change');e['position']=1.5;t.consume(e)
    else:s[a['id']]['before']['annotation']['decision_context']['own'].update(identity='Venusaur')
    r=compare_actions(a,b,t,s,k,BeliefBank(),profile='showdown-champions-reference-v1');assert r['status']=='ineligible' and r['reasons']


def test_deterministic_reconstruction_and_original_preservation():
    source=[boundary(1,1,'start'),event(2),boundary(3,1,'end')];original=deepcopy(source)
    outputs=[]
    for _ in range(2):
        t=TurnReconstruction('synthetic')
        for e in source:t.consume(e)
        outputs.append(json.dumps(t.export(),sort_keys=True))
    assert outputs[0]==outputs[1] and source==original


def test_pipeline_checkpoint_reuses_engine_stage_and_preserves_sources(tmp_path,monkeypatch):
    from tracking.battle_state import BattleState
    from tracking.state_engine import StateEngine
    import battle_evidence.offline as offline
    from speed_inference.offline import atomic_json,file_hash,RUNS
    run=tmp_path/'.cache/battles/sample_battle_9/event-driven'/RUNS[9]
    atomic_json(run/'video-only.json',dict(battle_id='sample_battle_9',events=[]))
    atomic_json(run/'replay.json',StateEngine(BattleState('sample_battle_9')).to_dict())
    atomic_json(run/'manifest.json',dict(status='complete'))
    originals={str(p):file_hash(p) for p in run.iterdir()}
    first=offline.run(9,root=tmp_path);assert first['counts']['speed_eligible']==0
    assert offline.run(9,root=tmp_path)['reused']
    # A source-envelope update invalidates reconstruction, but the replay input is unchanged.
    atomic_json(run/'video-only.json',dict(battle_id='sample_battle_9',events=[],note='same events, revised envelope'))
    second=offline.run(9,root=tmp_path);assert not second['reused'] and second['result']!=first['result']
    from pathlib import Path
    first_m=json.loads(Path(first['result']).with_name('manifest.json').read_text())
    second_m=json.loads(Path(second['result']).with_name('manifest.json').read_text())
    assert first_m['stages']['snapshots']['path']==second_m['stages']['snapshots']['path']
    assert file_hash(run/'replay.json')==originals[str(run/'replay.json')]
    assert file_hash(run/'manifest.json')==originals[str(run/'manifest.json')]


def test_source_annotations_preserve_raw_and_reject_identity_rewrite():
    from battle_evidence.offline import normalize
    raw=dict(event_id='raw',event_type='move_execution',attributes=dict(battle_id='synthetic',observation_time=1,occurrence_id='occ'),
        side='self',status='candidate',original_text='raw OCR',canonical_references={},evidence=[],uncertainty=['actor_unknown'])
    original=deepcopy(raw);n=normalize(raw,{},1,dict(verified=True,sources=SOURCES,instance_id='bound',move_verified=False))
    assert n['text']=='raw OCR' and n['source_status']=='candidate' and n['underlying_action_id']=='occ' and raw==original
    with pytest.raises(ValueError):normalize(raw,{},1,dict(verified=True,sources=SOURCES,timestamp=999))


def test_substitute_and_damage_resolution_links_are_required():
    assert not hp_case([attack(substitute=True)])['damage_inference_eligible']
    assert not hp_case([attack(resolution_snapshot_id=None)])['damage_inference_eligible']
    assert not hp_case([attack(target_instances=[])])['damage_inference_eligible']


def test_unresolved_effect_identity_does_not_crash_or_guess():
    d=EffectDurations();apply(d,event(1,'effect',effect=None,family='terrain',scope='field',change='start',verified=False))
    assert d.snapshot()==[] and d.history[-1]['issue']=='effect_identity_unresolved'


def test_distinct_screens_can_coexist_after_normalization():
    from battle_evidence.offline import normalize
    d=EffectDurations()
    for i,name in enumerate(['light_screen','reflect']):
        raw=dict(event_id=str(i),event_type='side_condition_change',attributes=dict(battle_id='synthetic',observation_time=i,condition=name,change='start'),
            side='self',status='confirmed',original_text=name,canonical_references={},evidence=[],uncertainty=[])
        e=normalize(raw,{},i);apply(d,e)
    assert len(d.snapshot())==2 and all(x['active'] for x in d.snapshot())


def test_failed_downstream_stage_retains_successful_engine_checkpoint(tmp_path,monkeypatch):
    from tracking.battle_state import BattleState
    from tracking.state_engine import StateEngine
    import battle_evidence.offline as offline
    from speed_inference.offline import atomic_json,RUNS
    from pathlib import Path
    run=tmp_path/'.cache/battles/sample_battle_9/event-driven'/RUNS[9]
    atomic_json(run/'video-only.json',dict(battle_id='sample_battle_9',events=[]))
    atomic_json(run/'replay.json',StateEngine(BattleState('sample_battle_9')).to_dict())
    atomic_json(run/'manifest.json',dict(status='complete'))
    real=offline.speed_audit
    def fail(*a,**k):raise RuntimeError('controlled downstream failure')
    monkeypatch.setattr(offline,'speed_audit',fail)
    with pytest.raises(RuntimeError):offline.run(9,root=tmp_path)
    manifests=[p for p in (tmp_path/'.cache/battles/sample_battle_9/m34-evidence').glob('*/manifest.json')]
    m=json.loads(manifests[0].read_text());assert m['status']=='failed' and m['stages']['snapshots']['status']=='complete'
    projection=Path(m['stages']['snapshots']['path']);stamp=projection.stat().st_mtime_ns
    monkeypatch.setattr(offline,'speed_audit',real)
    assert not offline.run(9,root=tmp_path)['reused'] and projection.stat().st_mtime_ns==stamp


def test_historical_headings_do_not_manufacture_execution_times_or_live_bindings():
    from pathlib import Path
    from battle_evidence.historical import reconstruct
    reviews=json.loads(Path('tests/fixtures/battle_evidence/real-log-excerpts.json').read_text())
    for number,heading in [(5,1),(6,4),(8,3)]:
        result=reconstruct(f'sample_battle_{number}',reviews=reviews)
        assert len(result)==1 and result[0]['number']==heading
        assert result[0]['start'] is None and result[0]['original_execution_time'] is None
        assert result[0]['live_instance_bindings'] is None and not result[0]['speed_eligible']
    row=dict(entry_id='log:a',turn=4,log_order=1,inspection_timestamp=474,original_event_time=None,raw_text='controlled')
    result=reconstruct('synthetic',cached_log=dict(battle_id='synthetic',entries=[row,row]))
    assert len(result[0]['source_entries'])==1
    with pytest.raises(ValueError):reconstruct('synthetic',cached_log=dict(battle_id='other',entries=[]))


def test_unknown_continuity_and_outside_interval_cause_cannot_measure_damage():
    assert hp_case(epoch=None)['exact_damage'] is None
    assert hp_case([attack(position=0)])['exact_damage'] is None


def test_replay_drift_is_reported_not_silently_repaired():
    from tracking.battle_state import BattleState
    from tracking.state_engine import StateEngine
    from battle_evidence.snapshots import project
    from battle_evidence.diagnostics import replay_validation
    engine=StateEngine(BattleState('synthetic'));saved=engine.to_dict();p=project(engine.state)
    result=replay_validation(saved,p,dict(saved_final_hash='a',replayed_final_hash='b'))
    assert not result['full_final_state_matches'] and result['projected_final_state_matches']
    p['occupancy']['self']['left']='different'
    assert not replay_validation(saved,p,dict(saved_final_hash='a',replayed_final_hash='b'))['projected_final_state_matches']


def test_status_move_cannot_be_attributed_as_damaging_attack():
    result=hp_case([attack(move='Protect')])
    assert not result['damage_inference_eligible'] and 'move_not_cataloged_as_damaging_attack' in result['reasons']


def test_conflicted_team_field_does_not_become_known_speed():
    from team_configuration import TeamConfiguration
    team=TeamConfiguration();team.correct('own_team_1','identity',canonical_id='pokeapi:pokemon:6',reviewer='controlled')
    team.correct('own_team_1','speed',value=120,reviewer='controlled')
    team.data['members'][0]['fields']['speed']['conflicts']=[dict(resolved=False)]
    k=KnownBuilds();k.import_team(team,battle_id='synthetic',bindings={'own_team_1':'own:1'},binding_evidence=SOURCES)
    assert k.records['synthetic','own:1']['stats']['speed'] is None


def test_speed_adapter_uses_projected_snapshot_without_a_prebuilt_context():
    t,a,b,s,k=setup_pair();view=s[a['id']]['before'];ann=view['annotation'];context=ann.pop('decision_context')
    f=lambda v:dict(value=v,known=True)
    state=dict(pokemon={},weather=dict(kind=f('none')),terrain=dict(kind=f('none')),trick_room=dict(active=f(False)))
    ann.update(actor_modifiers={},field_other_effects=[],ordering_effects=[],comparable=True)
    for side in ('own','opponent'):
        actor=context[side];pid=actor['instance_id']
        state['pokemon'][pid]=dict(form=f('pokeapi:pokemon:6'),item_status=f('none'),item=f(None),ability=f('Blaze'),status=f('none'),stages=dict(speed=f(0)))
        ann['actor_modifiers'][pid]={key:actor[key] for key in ('tailwind','ability_active','unburden_active','activation_evidence','other_effects')}
    view['observable']=state
    r=compare_actions(a,b,t,s,k,BeliefBank(),profile='showdown-champions-reference-v1')
    assert r['status']=='updated'
    state['pokemon']['own:1']['form']['known']=False
    assert compare_actions(a,b,t,s,k,BeliefBank(),profile='showdown-champions-reference-v1')['status']=='ineligible'
    state['pokemon']['own:1']['form']['known']=True
    ann['actor_modifiers']['opponent:1'].pop('tailwind')
    assert compare_actions(a,b,t,s,k,BeliefBank(),profile='showdown-champions-reference-v1')['status']=='ineligible'


def test_retracted_or_revised_source_stays_in_ledger_without_reactivation():
    from battle_evidence.offline import normalize
    raw=dict(event_id='raw',event_type='move_execution',attributes=dict(battle_id='synthetic',observation_time=1),
        side='self',status='confirmed',original_text='raw',canonical_references={},evidence=[],uncertainty=[])
    for receipt in [dict(retracted=True),dict(revisions=[{'reason':'corrected upstream'}])]:
        e=normalize(raw,receipt,1);t=TurnReconstruction('synthetic');result=t.consume(e)
        assert result['status']=='inactive_source_requires_review' and len(t.ledger)==1 and t.turns==[]
        d=EffectDurations();apply(d,e);assert d.snapshot()==[]
        with pytest.raises(ValueError):normalize(raw,receipt,1,dict(verified=True,sources=SOURCES,kind='action'))
