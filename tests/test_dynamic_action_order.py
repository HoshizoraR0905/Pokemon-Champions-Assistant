"""Synthetic M3.2.1 cases; none are recognition accuracy measurements."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from speed_order import infer_speed, simulate_action_order, configuration_domain
from speed_order.core import identity_key
from speed_order.mechanics import effective_priority

PROFILE = 'showdown-champions-reference-v1'
BASE = json.loads(Path('examples/speed_order/compare.json').read_text())['input']['context']
E = dict(sources=['synthetic:M3.2.1'], basis='synthetic', confidence='declared exact synthetic input')


def participant(iid, speed, identity='Charizard', ability='Blaze', item='none'):
    p = deepcopy(BASE['own'])
    p.update(instance_id=iid, actual_speed=speed, identity=identity, form='base', ability=ability, item=item)
    return p


def action(iid, move='Flamethrower', activation='unknown', complete=False, changes=None):
    return dict(id=iid + ':move', individual=iid, kind='move', move=move, outcome='completed',
                activation=dict(state=activation, coverage_complete=complete, evidence=deepcopy(E)),
                changes=changes or [], evidence=deepcopy(E))


def change(target, **values):
    return dict(kind='set', target=target, values=values, evidence=deepcopy(E))


def state(*participants, weather='none', trick_room=False):
    field = deepcopy(BASE['field']); field.update(weather=weather, trick_room=trick_room)
    return dict(participants={p['instance_id']:p for p in participants}, field=field)


def observation(oid='turn1', own_speed=180, first='opp', identity='Charizard', move='Flamethrower'):
    return dict(id=oid, battle_id='synthetic', decision_id=oid, subject='opp',
                state=state(participant('own', own_speed), participant('opp', None, identity, None, None)),
                actions=[action('own'), action('opp', move)],
                sequence=[first+':move', ('own' if first=='opp' else 'opp')+':move'],
                initial_changes=[], alternatives=[], strict_speed=[], evidence=deepcopy(E))


def configurations(speeds, abilities=('Blaze',), items=('none',)):
    return [dict(id=f'{s}:{a}:{i}', speed=s, ability=a, item=i, training=None)
            for s in speeds for a in abilities for i in items]


def infer(observations, configs, **kwargs):
    return infer_speed(schema_version=2, observations=observations, configurations=configs, profile=PROFILE, **kwargs)


def simulate(s, actions, **kwargs):
    return simulate_action_order(state=s, actions=actions, profile=PROFILE, **kwargs)


def test_A_ordinary_tie_and_exact_discrete_gaps():
    result = infer([observation()], configurations(range(135, 201)))
    assert result['status'] == 'exact'
    assert result['feasible']['values'] == list(range(180, 201))
    assert result['tie_compatible'] == ['180:Blaze:none']
    result = infer([observation()], configurations([179, 180, 182, 200]))
    assert result['feasible']['intervals'] == [[180,180], [182,182], [200,200]]


def test_B_sun_chlorophyll_scarf_then_focus_sash_and_certified_strict():
    obs = observation(own_speed=214, identity='Venusaur', move='Earthquake')
    obs['state']['field']['weather'] = 'sun'
    configs = configurations(range(90,146), ('Overgrow','Chlorophyll'), ('none','Choice Scarf','Focus Sash'))
    result = infer([obs], configs)
    assert result['remaining_abilities'] == ['Chlorophyll','Overgrow']
    assert result['remaining_items'] == ['Choice Scarf','Focus Sash','none']
    obs['state']['participants']['opp']['item'] = 'Focus Sash'
    result = infer([obs], configs)
    assert result['feasible']['values'] == list(range(107,146))
    assert result['remaining_abilities'] == ['Chlorophyll']
    assert result['remaining_items'] == ['Focus Sash']
    assert '107:Chlorophyll:Focus Sash' in result['tie_compatible']
    obs['strict_speed'] = [['opp:move','own:move']]
    result = infer([obs], configs)
    assert result['feasible']['values'] == list(range(108,146))
    assert not result['tie_compatible']


def test_C_whimsicott_ambiguous_priority_retains_low_speeds():
    obs = observation(own_speed=214, identity='Whimsicott', move='Tailwind')
    obs['state']['field']['weather'] = 'sun'
    result = infer([obs], configurations([100,107,108,120], ('Prankster','Chlorophyll','Infiltrator')))
    assert result['feasible']['values'] == [100,107,108,120]
    assert result['remaining_abilities'] == ['Chlorophyll','Prankster']
    low = next(c for c in result['compatible_configurations'] if c['configuration']['speed']==100)
    assert low['configuration']['ability'] == 'Prankster'
    assert low['histories'][0]['turn1']['decisions'][0]['metrics']['opp:move']['priority']['effective'] == 1
    obs['actions'][1]['effective_priorities']=[0]
    result=infer([obs],configurations([100,107,108,120],('Prankster','Chlorophyll','Infiltrator')))
    assert result['status']=='exact'
    assert result['remaining_abilities']==['Chlorophyll']
    assert result['feasible']['values']==[107,108,120]


def test_D_dynamic_paralysis_after_raichu_then_pending_overtake():
    s = state(participant('raichu',200,'Raichu','Static'), participant('charizard',181),
              participant('other',100))
    actions = [action('raichu','Thunderbolt',changes=[change('charizard',status='paralysis')]),
               action('charizard'), action('other')]
    original = deepcopy(s)
    result = simulate(s, actions)
    assert result['status'] == 'exact'
    assert [t['sequence'] for t in result['traces']] == [['raichu:move','other:move','charizard:move']]
    steps = result['traces'][0]['steps']
    assert steps[0]['metrics']['charizard:move']['speed']['effective_speed'] == 181
    assert steps[1]['metrics']['charizard:move']['speed']['effective_speed'] == 90
    assert steps[0]['before']['participants']['charizard']['status'] == 'none'
    assert steps[0]['after']['participants']['charizard']['status'] == 'paralysis'
    assert steps[1]['pending_before'] == ['charizard:move','other:move']
    assert s == original
    s['participants']['other']['actual_speed'] = 90
    result = simulate(s, actions)
    assert {tuple(t['sequence']) for t in result['traces']} == {
        ('raichu:move','other:move','charizard:move'), ('raichu:move','charizard:move','other:move')}


@pytest.mark.parametrize('changes,expected', [
    ([change('slow',stage=2)], 160),
    ([change('slow',tailwind=True)], 160),
    ([change('field',weather='sun')], 160),
    ([change('field',terrain='electric'),change('slow',ability='Surge Surfer')], 160),
    ([change('slow',item='Choice Scarf')],120),
    ([change('slow',ability_active=False)],80),
])
def test_per_action_modifier_stage(changes, expected):
    s = state(participant('fast',200), participant('slow',80,'Venusaur','Chlorophyll'))
    result = simulate(s,[action('fast',changes=changes),action('slow','Earthquake')])
    assert result['traces'][0]['steps'][1]['metrics']['slow:move']['speed']['effective_speed']==expected


def test_trick_room_dynamic_update():
    s = state(participant('a',200),participant('b',150),participant('c',100))
    result = simulate(s,[action('a',changes=[change('field',trick_room=True)]),action('b'),action('c')])
    assert result['traces'][0]['sequence']==['a:move','c:move','b:move']


@pytest.mark.parametrize('branch,stone,ability', [
    ('Mega Charizard X','Charizardite X','Tough Claws'),
    ('Mega Charizard Y','Charizardite Y','Drought')])
def test_E_mega_identity_training_item_and_stats(branch,stone,ability):
    configs = configuration_domain(identity='Charizard',form='base',abilities=['Blaze'],items=[stone],
        known_training_points={'speed':12},alignments=[{'increase':None,'decrease':None}])['configurations']
    assert len(configs)==1
    config=configs[0]
    p=participant('one',config['speed'],item=stone);p['training']=config['training']
    transform=dict(kind='transform',target='one',values={'forms':[branch]},evidence=deepcopy(E))
    result=simulate(state(participant('fast',200),p),[action('fast',changes=[transform]),action('one')])
    assert result['status']=='exact',result['diagnostics']
    before=result['traces'][0]['steps'][0]['before']['participants']['one']
    after=result['traces'][0]['steps'][0]['after']['participants']['one']
    assert after['instance_id']==before['instance_id']=='one'
    assert after['training']==before['training']
    assert after['_current_form']==identity_key('Charizard',branch)
    assert after['item']==stone and after['ability']==ability
    assert after['actual_speed']==before['actual_speed']==132
    assert after['configuration_speed']==132
    assert after['form_stat_domains']['attack']!=before['form_stat_domains']['attack']
    assert len(result['traces'][0]['final_state']['participants'])==2


def test_E_unresolved_mega_branches_correlate_with_stone_and_carry_forms():
    configs=configuration_domain(identity='Charizard',form='base',abilities=['Blaze'],
        items=['Charizardite X','Charizardite Y'],known_training_points={'speed':0},
        alignments=[{'increase':None,'decrease':None}])['configurations']
    obs=observation(own_speed=100)
    obs['initial_changes']=[dict(kind='transform',target='opp',
        values={'forms':['Mega Charizard X','Mega Charizard Y']},evidence=deepcopy(E))]
    result=infer([obs],configs)
    assert result['status']=='exact',result['diagnostics']
    assert len(result['compatible_configurations'])==2
    assert set(result['per_form'])=={identity_key('Charizard','Mega Charizard X'),identity_key('Charizard','Mega Charizard Y')}
    # No training evidence: explicit unresolved instead of guessing a build.
    result=infer([obs],configurations([120],items=('Charizardite X',)))
    assert result['status']=='unresolved' and result['feasible'] is None


def test_wrong_mega_stone_excludes_branch_and_cross_species_is_unresolved():
    obs=observation(own_speed=100)
    configs=configuration_domain(identity='Charizard',form='base',abilities=['Blaze'],items=['Charizardite X'],
        known_training_points={'speed':0},alignments=[{'increase':None,'decrease':None}])['configurations']
    obs['initial_changes']=[dict(kind='transform',target='opp',values={'forms':['Mega Charizard Y']},evidence=deepcopy(E))]
    assert infer([obs],configs)['status']=='empty'
    obs['initial_changes'][0]['values']['forms']=['Mega Swampert']
    result=infer([obs],configs)
    assert result['status']=='unresolved' and result['feasible'] is None


def test_F_quick_claw_activation_nonactivation_unknown_and_coverage():
    obs=observation(own_speed=180)
    configs=configurations([90,180,200],items=('Quick Claw',))
    obs['actions'][1]['activation'].update(state='activated')
    result=infer([obs],configs)
    assert result['feasible']['values']==[90,180,200]
    assert not result['tie_compatible']
    assert all(h['histories'][0]['turn1']['decisions'][0]['metrics']['opp:move']['override']==1
               for h in result['compatible_configurations'])
    obs['actions'][1]['activation'].update(state='not_activated',coverage_complete=True)
    assert infer([obs],configs)['feasible']['values']==[180,200]
    obs['actions'][1]['activation']['coverage_complete']=False
    assert infer([obs],configs)['status']=='unresolved'
    obs['actions'][1]['activation']['state']='unknown'
    result=infer([obs],configs)
    assert result['feasible']['values']==[90,180,200]
    assert len(result['compatible_configurations'][-1]['histories'])==2


def test_F_quick_claw_never_crosses_priority_and_stays_fixed_across_decisions():
    s=state(participant('a',250),participant('b',50,item='Quick Claw'),participant('c',100))
    actions=[action('a','Protect'),action('b',activation='unknown'),action('c')]
    result=simulate(s,actions)
    assert {tuple(t['sequence']) for t in result['traces']}=={
        ('a:move','b:move','c:move'),('a:move','c:move','b:move')}
    assert all(t['steps'][0]['metrics']['a:move']['priority']['effective']==4 for t in result['traces'])
    # Removing the item does not erase an already resolved queued activation.
    actions[0]['changes']=[change('b',item='none')]
    result=simulate(s,actions)
    assert result['traces'][1]['sequence']==['a:move','b:move','c:move']


def test_G_shared_configuration_cross_turns_and_conflict_explanations():
    a=observation('a',140);b=observation('b',110,first='own')
    configs=configurations([100],items=('none','Choice Scarf'))
    result=infer([a,b],configs)
    assert result['status']=='empty' and result['feasible']['values']==[]
    assert result['conflict']['observation_ids']==['a','b']
    assert len(result['exclusions'])==2
    a=observation('a',214,identity='Venusaur',move='Earthquake')
    a['state']['field']['weather']='sun'
    b=observation('b',110,first='own',identity='Venusaur',move='Earthquake')
    b['state']['field']['trick_room']=True
    result=infer([a,b],configurations([100,107,108,120],('Overgrow','Chlorophyll'),('none','Choice Scarf')))
    assert result['status']=='exact'
    assert all(c['configuration']['ability']=='Chlorophyll' or c['configuration']['item']=='Choice Scarf'
               for c in result['compatible_configurations'])


def test_persistent_item_loss_requires_evidence_and_carries_between_observations():
    a=observation('a',100);a['actions'][1]['changes']=[change('opp',item='none')]
    b=observation('b',120,first='own');b['state']['participants']['opp']['item']='none'
    result=infer([a,b],configurations([100],items=('Choice Scarf',)))
    assert result['feasible']['values']==[100]
    a['actions'][1]['changes']=[]
    assert infer([a,b],configurations([100],items=('Choice Scarf',)))['status']=='empty'


def test_persistent_unburden_history_cannot_be_rechosen():
    a=observation('a',150,identity='Sneasler',move='Close Combat')
    a['state']['participants']['opp'].update(unburden_active=True,activation_evidence='Known prior loss')
    b=deepcopy(a);b.update(id='b',decision_id='b')
    b['state']['participants']['opp'].update(unburden_active=False,activation_evidence='No supporting reset')
    result=infer([a,b],configurations([100],('Unburden',)))
    assert result['status']=='empty'
    b['initial_changes']=[change('opp',unburden_active=False,activation_evidence='Documented reset')]
    # A snapshot before the documented change retains the previous state.
    b['state']['participants']['opp']['unburden_active']=True
    b['state']['participants']['own']['actual_speed']=90
    assert infer([a,b],configurations([100],('Unburden',)))['status']=='exact'


def test_mega_changed_speed_and_cross_observation_identity():
    configs=configuration_domain(identity='Swampert',form='base',abilities=['Torrent'],items=['Swampertite'],
        known_training_points={'speed':0},alignments=[{'increase':None,'decrease':None}])['configurations']
    a=observation('a',70,identity='Swampert',move='Earthquake')
    a['actions'][1]['changes']=[dict(kind='transform',target='opp',
        values={'forms':['Mega Swampert']},evidence=deepcopy(E))]
    b=observation('b',85,identity='Mega Swampert',move='Earthquake')
    b['state']['participants']['opp']['form']='as_named'
    result=infer([a,b],configs)
    assert result['status']=='exact',result['diagnostics']
    assert result['feasible']['values']==[80]
    assert result['per_form'][identity_key('Swampert','Mega Swampert')]['values']==[90]
    assert result['current_abilities']==['Swift Swim']


def test_stall_is_a_separate_order_override_and_ties_remain_possible():
    s=state(participant('a',200,ability='Stall'),participant('b',100))
    result=simulate(s,[action('a'),action('b')])
    assert result['traces'][0]['sequence']==['b:move','a:move']
    assert result['traces'][0]['steps'][0]['metrics']['a:move']['override']==-1
    s['participants']['b']['ability']='Stall';s['participants']['b']['actual_speed']=200
    assert len(simulate(s,[action('a'),action('b')])['traces'])==2


def test_unknown_temporal_alternatives_and_invalid_final_change():
    o=observation(own_speed=180)
    o['alternatives']=[dict(id='normal',participants={},field={}),
                       dict(id='boosted',participants={'opp':{'stage':2}},field={})]
    result=infer([o],configurations([90,180]))
    assert result['feasible']['values']==[90,180]
    s=state(participant('a',200))
    result=simulate(s,[action('a',changes=[change('a',stage=9)])])
    assert result['traces'] is None


@pytest.mark.parametrize('move,ability,extra,terrain,expected',[
    ('Protect','Blaze',{},'none',4),('Fake Out','Blaze',{},'none',3),
    ('Trick Room','Blaze',{},'none',-7),('Tailwind','Prankster',{},'none',1),
    ('Tailwind','Prankster',{'ability_active':False},'none',0),
    ('Air Slash','Gale Wings',{'hp_full':True},'none',1),
    ('Air Slash','Gale Wings',{'hp_full':False},'none',0),
    ('Recover','Triage',{},'none',3),('Giga Drain','Triage',{},'none',3),
    ('Flamethrower','Triage',{},'none',0),
    ('Grassy Glide','Overgrow',{'grounded':True},'grassy',1),
    ('Grassy Glide','Overgrow',{'grounded':False},'grassy',0)])
def test_effective_priority_catalog_and_conditional_rules(move,ability,extra,terrain,expected):
    p=participant('a',100,ability=ability);p.update(extra)
    f=deepcopy(BASE['field']);f['terrain']=terrain
    assert effective_priority(action('a',move),p,f)['effective']==expected


@pytest.mark.parametrize('mutate',[
    lambda s,a: s['participants']['a'].update(ability='Quick Draw'),
    lambda s,a: s['participants']['a'].update(item='Lagging Tail'),
    lambda s,a: s['participants']['a'].update(ability='Gale Wings'),
    lambda s,a: a[0].update(kind='forced'),
    lambda s,a: a[0].update(outcome='skipped'),
    lambda s,a: a[0].update(move='After You'),
    lambda s,a: s['participants']['a'].update(actual_speed=1000),
    lambda s,a: a[0].update(evidence={}),
])
def test_unsupported_branches_are_never_neutral(mutate):
    s=state(participant('a',100),participant('b',90));actions=[action('a','Air Slash'),action('b')]
    mutate(s,actions)
    result=simulate(s,actions)
    assert result['status']=='unresolved' and result['traces'] is None


def test_limits_and_one_unsupported_hypothesis_withhold_complete_answer():
    obs=observation(own_speed=100)
    result=infer([obs],configurations([100],('Blaze','Quick Draw')))
    assert result['status']=='unresolved' and result['feasible'] is None
    assert infer([obs],configurations([100,101]),max_evaluations=1)['status']=='unresolved'
    s=state(participant('a',100),participant('b',100))
    assert simulate(s,[action('a'),action('b')],max_branches=1)['traces'] is None
    assert simulate_action_order(state=s,actions=[action('a'),action('b')])['status']=='unresolved'


def test_cancellation_is_explicit_removal_without_a_speed_inequality():
    cancel=dict(kind='cancel',target='b:move',values={},evidence=deepcopy(E))
    result=simulate(state(participant('a',200),participant('b',100)),
                    [action('a',changes=[cancel]),action('b')])
    assert result['traces'][0]['sequence']==['a:move']
    assert result['traces'][0]['steps'][0]['changes']==[cancel]


def test_legal_configuration_domain_preserves_budget_and_unknown_alignments():
    result=configuration_domain(identity='Charizard',form='base',abilities=['Blaze'],items=['none'],
                                known_training_points={'hp':32,'attack':32})
    configs=result['configurations']
    assert {c['training']['point_domains']['speed'][0] for c in configs}=={0,1,2}
    assert len({json.dumps(c['training']['alignment'],sort_keys=True) for c in configs})==21
    with pytest.raises(ValueError,match='Non-native'):
        configuration_domain(identity='Charizard',form='base',abilities=['Prankster'],items=['none'])


def test_original_source_snapshots_still_match_pins():
    manifest=json.loads(Path('speed_order/data/sources-v1.json').read_text())
    for path,digest in manifest['snapshot_sha256'].items():
        if Path(path).exists():
            assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest


def test_json_cli_v2_and_runtime_isolation():
    import subprocess
    import sys
    request=json.loads(Path('examples/speed_order/v2/ordinary.json').read_text())
    code='''
import sys, json
from speed_order.__main__ import solve
result=solve(json.load(sys.stdin))
assert result['feasible']['minimum']==180
assert not any(k.split('.')[0] in {'recognition','tracking','battle_evidence','speed_inference','metagame','cv2'} for k in sys.modules)
print(result['status'])
'''
    completed=subprocess.run([sys.executable,'-c',code],input=json.dumps(request),text=True,capture_output=True)
    assert completed.returncode==0,completed.stderr
    assert completed.stdout.strip()=='exact'
    request['input']['profile']='champions-evidence-only-v1'
    completed=subprocess.run([sys.executable,'-m','speed_order'],input=json.dumps(request),text=True,capture_output=True)
    assert completed.returncode==2 and json.loads(completed.stdout)['status']=='unresolved'
