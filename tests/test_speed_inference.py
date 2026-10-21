"""Portable controlled tests: these do not claim in-game ordering validation."""
from copy import deepcopy
import json
import math
import pytest
from speed_inference import SpeedBelief,BeliefBank,configuration_space,infer
from speed_inference.controlled import observation,experiment
from speed_inference.offline import audit_payload,atomic_json

REFERENCE='showdown-champions-reference-v1'
NEUTRAL=dict(increase=None,decrease=None)


def belief(*,profile=REFERENCE,**space):
    model=configuration_space(identity='Charizard',form='base',speed_points=[0,1,2],alignments=[NEUTRAL],**space)
    return SpeedBelief(model,battle_id='synthetic',instance_id='opponent:1',stat_epoch='initial',profile=profile)


def probs(b):return {r['speed']:r['probability'] for r in b.summary()['marginal_speed']}


def test_exact_bayes_and_contradiction():
    b=belief();r=b.update(observation())
    assert r['status']=='updated' and r['predictive_probability']==pytest.approx(.5)
    assert probs(b)==pytest.approx({121:1/3,122:2/3})
    assert b.summary()['mean']==pytest.approx(121+2/3)
    assert b.summary()['credible_interval']['lower']==121
    assert b.summary()['information_gain_nats']>0
    b.update(observation(2,own_speed=122));assert probs(b)=={122:1.}
    r=b.update(observation(3,own_speed=120,first='own'))
    assert r['status']=='contradiction' and not b.summary()['posterior_defined']
    assert b.summary()['distribution_scope']=='last_consistent_weights_for_diagnosis_only'
    assert probs(b)=={122:1.}
    assert b.update(observation(4))['status']=='ineligible'


def test_prior_configuration_uniform_not_speed_uniform():
    m=configuration_space(identity='Charizard',form='base')
    b=SpeedBelief(m,battle_id='x',instance_id='p',stat_epoch='initial')
    p=b.summary();assert len(m['candidates'])==693
    assert p['support'][0]==108 and p['support'][-1]==167
    assert max(r['probability'] for r in p['marginal_speed'])>min(r['probability'] for r in p['marginal_speed'])
    assert len({r['probability'] for r in p['configurations']})==1
    assert p['probability_sum']==pytest.approx(1)
    assert p['information_gain_nats']==0 and not p['empirical_prior_used']


def test_sp_budget_and_no_invented_completions():
    m=configuration_space(identity='Charizard',form='base',known_other_points={'hp':32,'attack':32},alignments=[NEUTRAL])
    assert [c['speed_sp'] for c in m['candidates']]==[0,1,2]
    assert m['known_other_points']=={'hp':32,'attack':32}
    with pytest.raises(ValueError):configuration_space(identity='Charizard',form=None)
    with pytest.raises(ValueError):configuration_space(identity='Charizard',form='base',alignments=[NEUTRAL,NEUTRAL])


@pytest.mark.parametrize('first,expected',[('own',{120:2/3,121:1/3}),('opponent',{121:1/3,122:2/3})])
def test_faster_slower_tie(first,expected):
    b=belief();assert b.update(observation(first=first))['status']=='updated';assert probs(b)==pytest.approx(expected)


def test_trick_room_reverses_preserves_tie():
    b=belief();o=observation();o['context']['field']['trick_room']=True
    assert b.update(o)['status']=='updated';assert probs(b)==pytest.approx({120:2/3,121:1/3})


@pytest.mark.parametrize('change,first,effective',[
    ({'tailwind':True},'opponent',[240,242,244]),
    ({'status':'paralysis'},'own',[60,60,61]),
    ({'stage':1},'opponent',[180,181,183]),
])
def test_modifiers_delegate(change,first,effective):
    b=belief();o=observation(first=first);o['context']['opponent'].update(change)
    r=b.update(o);assert r['status']=='updated',r['reasons']
    assert probs(b)==pytest.approx({120:1/3,121:1/3,122:1/3})
    assert [d['opponent_effective_speed'] for d in r['likelihood_details']]==effective


@pytest.mark.parametrize('mutate',[
    lambda o:o['verification'].update(actor_identity=False),
    lambda o:o['verification'].update(move_identity=False),
    lambda o:o['context']['own'].update(ability=None),
    lambda o:o['context']['opponent'].update(item=None),
    lambda o:o['context']['timing'].update(modifier_changes=['Tailwind expired']),
    lambda o:o['context'].update(comparable=False),
    lambda o:o['context']['own'].update(actual_speed=100),
    lambda o:o['context']['opponent'].update(ability='Solar Power'),
    lambda o:o['context']['opponent'].update(ability='Swift Swim'),
    lambda o:o['context']['actions']['opponent'].update(move='Protect',effective_priority=4),
    lambda o:o['context']['field'].update(trick_room=None),
])
def test_ineligible_preserves_weights(mutate):
    b=belief();before=probs(b);o=observation();mutate(o)
    r=b.update(o);assert r['status']=='ineligible',r;assert r['reasons'];assert probs(b)==before


def domain(values):return dict(values=values,coverage='complete_given_evidence',evidence=['Synthetic finite domain, not inferred from battle data'])


def test_hidden_item_and_unsupported_branch():
    b=belief(items=domain(['none','Choice Scarf']));o=observation();o['context']['opponent']['item']=None
    r=b.update(o);assert r['status']=='updated',r['reasons']
    assert sum(x['probability'] for x in b.summary()['configurations'] if x['configuration']['item']=='Choice Scarf')==pytest.approx(2/3)
    b=belief(items=domain(['none','Quick Claw']));before=probs(b)
    assert b.update(o)['status']=='ineligible' and probs(b)==before
    with pytest.raises(ValueError):belief(abilities=domain(['Swift Swim']))
    with pytest.raises(ValueError):belief(abilities=domain(['none']))


def test_known_scarf_and_native_ability():
    b=belief();o=observation();o['context']['opponent']['item']='Choice Scarf'
    r=b.update(o);assert r['status']=='updated';assert not r['marginal_changed']
    assert b.summary()['information_gain_nats']==pytest.approx(0)
    b=belief(abilities=domain(['Blaze']));o=observation();o['context']['opponent']['ability']=None
    assert b.update(o)['status']=='updated'


def test_strict_mechanics_not_silently_certified():
    b=belief(profile='champions-evidence-only-v1');before=probs(b)
    r=b.update(observation());assert r['status']=='ineligible';assert 'independently certified' in ' '.join(r['reasons']);assert probs(b)==before


def test_deduplication_dependencies_chronology():
    b=belief();o=observation();b.update(o);before=probs(b)
    assert b.update(o)['status']=='duplicate_ignored'
    revision=deepcopy(o);revision['sequence'].reverse();assert b.update(revision)['status']=='evidence_revision_requires_explicit_replay'
    repeated=observation(2);repeated['action_ids']=o['action_ids'];assert 'underlying_action_evidence_already_used' in b.update(repeated)['reasons']
    pair=observation();pair['id']='different-pair';pair['action_ids']={'own':'different','opponent':'other'};pair['context']['timing']['decision_id']='relabelled'
    assert 'dependent_pair_at_same_ordering_decision_already_used' in b.update(pair)['reasons']
    assert probs(b)==before
    b.update(observation(4,own_speed=122));assert 'out_of_order_observation_requires_explicit_replay' in b.update(observation(3))['reasons']


def test_bank_continuity_and_separation():
    bank=BeliefBank();b=bank.register(belief().model,battle_id='synthetic',instance_id='opponent:1',stat_epoch='initial',profile=REFERENCE)
    bank.update(observation());before=probs(b)
    bank.register(b.model,battle_id='synthetic',instance_id='opponent:2',stat_epoch='initial',profile=REFERENCE)
    assert bank.update(observation(5,own_speed=122))['status']=='updated' # same individual after a synthetic switch gap
    assert probs(b)=={122:1.} and before!={122:1.}
    assert bank.beliefs[('synthetic','opponent:2','initial')].summary()['status']=='prior_only'
    for key,val in [('battle_id','another'),('stat_epoch','mega')]:
        o=observation(6);o[key]=val;assert bank.update(o)['status']=='ineligible'
    with pytest.raises(ValueError):bank.register(b.model,battle_id='synthetic',instance_id='opponent:1',stat_epoch='initial')


def test_restore_determinism_and_input_immutability():
    request=experiment();original=deepcopy(request);r=infer(**request)
    assert request==original
    b=SpeedBelief.restore(json.loads(json.dumps(r)));assert b.export()==r
    r['posterior']['mean']=0
    with pytest.raises(ValueError):SpeedBelief.restore(r)


def test_long_log_weight_sequence_retains_positive_support():
    b=belief()
    for turn in range(1,1101):b.update(observation(turn))
    s=b.summary();assert s['support']==[121,122];assert s['probability_sum']==pytest.approx(1.)
    low=s['marginal_speed'][0];assert math.isfinite(low['log_probability']) and low['display_underflow']


def test_offline_does_not_promote_announcements_or_guess_form(tmp_path):
    e=lambda i,side:dict(event_id=i,event_type='move_execution',side=side,attributes={'battle_id':'sample_battle_9','observation_time':1},actor=None,evidence=[])
    events=[e('a','self'),e('b','opponent')]
    replay=dict(state=dict(battle_id='sample_battle_9',turn=None,pokemon={'p':dict(side_id='opponent',current_variant={'value':None,'knowledge':'unknown'})}),history=[])
    r=audit_payload('sample_battle_9',events,replay)
    assert r['applied_updates']==0 and r['subjects'][0]['status']=='no_prior'
    assert len(r['diagnostic_adjacent_opposite_side_pairs'])==1
    assert 'actor_instance_binding_missing' in r['move_announcements'][0]['exclusion_reasons']
    atomic_json(tmp_path/'output.json',r);assert json.loads((tmp_path/'output.json').read_text())==r
    with pytest.raises(ValueError):audit_payload('sample_battle_5',events,replay)


def test_weather_ability_and_unburden_explicit_history():
    for identity,ability,weather in [('Venusaur','Chlorophyll','sun'),('Sneasler','Unburden','none')]:
        m=configuration_space(identity=identity,form='base',speed_points=[0,1,2],alignments=[NEUTRAL])
        b=SpeedBelief(m,battle_id='synthetic',instance_id='opponent:1',stat_epoch='initial',profile=REFERENCE)
        o=observation();p=o['context']['opponent'];p.update(identity=identity,ability=ability)
        o['context']['field']['weather']=weather
        o['context']['actions']['opponent']['move']='Earthquake' if identity=='Venusaur' else 'Close Combat'
        if ability=='Unburden':p.update(unburden_active=True,activation_evidence='Synthetic item consumed before ordering snapshot')
        r=b.update(o);assert r['status']=='updated',r['reasons']
        assert all(d['opponent_effective_speed']==2*c['unmodified_speed'] for d,c in zip(r['likelihood_details'],m['candidates']))
        if ability=='Unburden':
            o=observation(2);o['context']['opponent'].update(identity=identity,ability=ability,unburden_active=True)
            assert b.update(o)['status']=='ineligible'


def test_form_change_needs_new_explicit_epoch_and_no_illegal_native_ability():
    b=belief();o=observation();o['context']['opponent'].update(identity='Charizard-Mega-Y',form='as_named')
    assert b.update(o)['status']=='ineligible'
    m=configuration_space(identity='pokeapi:pokemon:10064',form='as_named')
    b=SpeedBelief(m,battle_id='x',instance_id='y',stat_epoch='mega')
    assert b.summary()['status']=='prior_only'


def test_work_limits_and_invalid_input():
    with pytest.raises(ValueError):configuration_space(identity='Charizard',form='base',max_candidates=1)
    request=experiment();request['observations']=[observation()]*10001
    with pytest.raises(ValueError):infer(**request)
    b=belief();o=observation();o['context']=None
    assert b.update(o)['status']=='ineligible'


def test_offline_checkpoint_reuse_and_source_invalidation(tmp_path):
    from speed_inference.offline import audit_battle,RUNS
    run=tmp_path/'.cache/battles/sample_battle_9/event-driven'/RUNS[9]
    atomic_json(run/'video-only.json',dict(battle_id='sample_battle_9',events=[]))
    atomic_json(run/'replay.json',dict(state=dict(battle_id='sample_battle_9',turn=None,pokemon={}),history=[]))
    atomic_json(run/'manifest.json',dict(status='complete'))
    first=audit_battle(9,root=tmp_path);assert not first['reused']
    again=audit_battle(9,root=tmp_path);assert again['reused'] and again['result']==first['result']
    atomic_json(run/'manifest.json',dict(status='complete',revision=2))
    changed=audit_battle(9,root=tmp_path);assert not changed['reused'] and changed['result']!=first['result']
    from pathlib import Path
    assert Path(first['result']).exists()


def test_cli_and_inference_require_no_network_or_metagame_access(tmp_path):
    import subprocess,sys
    code='''
import builtins,socket,json
original=builtins.__import__
def guarded(name,*args,**kwargs):
    if name.startswith(('metagame','recognition','tracking')):raise AssertionError(name)
    return original(name,*args,**kwargs)
builtins.__import__=guarded
socket.create_connection=lambda *a,**k:(_ for _ in ()).throw(AssertionError('network'))
from speed_inference.controlled import experiment
from speed_inference import infer
assert infer(**experiment())['posterior']['support']==[122]
'''
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    result=subprocess.run([sys.executable,'-m','speed_inference','infer','examples/speed_inference/controlled.json','--output',str(tmp_path/'result.json')],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads((tmp_path/'result.json').read_text())['posterior']['support']==[122]
