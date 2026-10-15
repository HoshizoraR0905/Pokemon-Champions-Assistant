from copy import deepcopy
import hashlib,json,subprocess,sys
from pathlib import Path
import pytest
from speed_order import effective_speed,infer_speed,compare_speed

PROFILE='showdown-champions-reference-v1'
BASE=json.loads(Path('examples/speed_order/compare.json').read_text())['input']['context']
FIXTURE=json.loads(Path('tests/fixtures/speed_order/reference.json').read_text())


def observation(oid='order1',first='opponent',own_speed=100):
    c=deepcopy(BASE);c['own']['actual_speed']=own_speed
    return dict(id=oid,battle_id='synthetic',stat_epoch='original',sequence=[first,'own' if first=='opponent' else 'opponent'],evidence_kind='verified_action_order',context=c)


def infer(observations,candidates=range(50,250),**kwargs):return infer_speed(observations=observations,candidate_speeds=candidates,profile=PROFILE,**kwargs)

def compare(values,context=None,**kwargs):return compare_speed(context=deepcopy(context or BASE),opponent_speeds=values,profile=PROFILE,**kwargs)


@pytest.mark.parametrize('group',FIXTURE['groups'],ids=lambda g:g['id'])
def test_all_pinned_independent_speed_rows(group):
    for row in group['rows']:
        p=deepcopy(group['participant']);p['stage']=row['stage']
        r=effective_speed(actual_speed=row['actual_speed'],participant=p,field=group['field'],profile=PROFILE)
        if row['modern_cap_probe']!=row['effective_speed']:
            assert r['status']=='unsupported' and r['effective_speed'] is None
            continue
        assert r['status']=='exact_reference' and r['effective_speed']==row['effective_speed'],(group['id'],row,r)


@pytest.mark.parametrize('row',FIXTURE['order_cases'])
def test_executed_pinned_champions_trick_room_order(row):
    c=deepcopy(BASE);c['own']['actual_speed']=row['own_effective'];c['field']['trick_room']=row['trick_room']
    # Large effective values are obtained through supplied stage/Tailwind.
    if row['own_effective']>4095:
        c['own']['actual_speed']=2500;c['own']['stage']=2;c['own']['tailwind']=True
        c['opponent']['actual_speed']=3333;c['opponent']['item']='Choice Scarf';c['opponent']['stage']=2
        # 3333*2*1.5=9999, matching fixture.
        candidate=3333
    else:candidate=row['opponent_effective']
    r=compare([candidate],c)
    if row['own_effective']>999:
        assert r['status']=='unsupported' and not r['own_guaranteed_first']
        return
    assert r['possible_first']==sorted(row['orders'])


def test_inequalities_ties_and_trick_room():
    r=infer([observation()]);assert r['feasible']['values']==list(range(100,250))
    r=infer([observation(first='own')]);assert r['feasible']['values']==list(range(50,101))
    o=observation();o['context']['field']['trick_room']=True
    assert infer([o])['feasible']['values']==list(range(50,101))
    assert infer([observation()],[100])['feasible']['values']==[100]


def test_multiple_turns_stages_and_speed_boost_snapshot():
    a=observation();b=observation('next','own',180);b['context']['timing']['turn']=2;b['context']['timing']['decision_id']='turn2:start'
    b['context']['opponent']['stage']=1;b['context']['opponent']['ability']='Speed Boost'
    r=infer([a,b]);assert r['feasible']['values']==list(range(100,121))
    # Speed Boost itself is not a separate multiplier.
    p=deepcopy(BASE['opponent']);p['ability']='Speed Boost'
    assert effective_speed(actual_speed=100,participant=p,field=BASE['field'],profile=PROFILE)['effective_speed']==100


def test_unburden_requires_evidenced_activation_not_item_absence():
    p=deepcopy(BASE['opponent']);p['ability']='Unburden'
    assert effective_speed(actual_speed=100,participant=p,field=BASE['field'],profile=PROFILE)['status']=='insufficient_information'
    p['activation_evidence']='Verified inactive at ordering decision.'
    assert effective_speed(actual_speed=100,participant=p,field=BASE['field'],profile=PROFILE)['effective_speed']==100
    p.update(unburden_active=True,activation_evidence='Item lost before ordering decision.')
    assert effective_speed(actual_speed=100,participant=p,field=BASE['field'],profile=PROFILE)['effective_speed']==200
    p['item']='Choice Scarf'
    assert effective_speed(actual_speed=100,participant=p,field=BASE['field'],profile=PROFILE)['status']=='insufficient_information'


@pytest.mark.parametrize('ability',['Prankster','Gale Wings','Triage','Stall'])
def test_priority_abilities_explicitly_gated(ability):
    c=deepcopy(BASE);c['opponent']['ability']=ability
    assert compare([100],c)['status']=='unsupported'


@pytest.mark.parametrize('item',['Quick Claw','Custap Berry','Lagging Tail','Full Incense'])
def test_item_presence_does_not_establish_order(item):
    c=deepcopy(BASE);c['opponent']['item']=item
    assert compare([100],c)['status']=='unsupported'
    c['ordering_effects']=[dict(effect=item,actor='opponent',active=True,evidence='Evidenced ordering effect at this decision.')]
    r=compare([100],c);assert r['status']=='non_speed_ordering' and not r['own_guaranteed_first'] and not r['opponent_guaranteed_first']


def test_priority_is_non_speed_and_noninformative_for_inversion():
    o=observation();o['context']['actions']['own'].update(move='Quick Attack',effective_priority=1)
    r=compare([1,4095],o['context']);assert r['status']=='non_speed_ordering' and r['own_guaranteed_first']
    r=infer([o]);assert r['status']=='non_informative' and r['feasible']['count']==200


@pytest.mark.parametrize('kind',['switch','unable','entered_mid_turn','multi_action','forced'])
def test_uncomparable_actions_do_not_invent_speed_constraints(kind):
    o=observation();o['context']['actions']['own']['kind']=kind
    r=infer([o]);assert r['status']=='non_informative' and r['feasible']['count']==200


def test_animation_and_midturn_changes_are_not_order_snapshots():
    o=observation();o['evidence_kind']='animation_timestamps'
    assert infer([o])['status']=='non_informative'
    o=observation();o['context']['timing']['modifier_changes']=[dict(effect='Tailwind',at='after-first-action')]
    assert infer([o])['status']=='non_informative'
    assert compare([100],o['context'])['status']=='insufficient_information'


def test_shared_scarf_assignment_cannot_change_to_fit_each_hit():
    a=observation(own_speed=140);b=observation('second','own',110)
    for o in [a,b]:o['context']['opponent']['item']=None
    v=dict(id='item',scope='shared',observation_ids=['order1','second'],path='opponent.item',values=['none','Choice Scarf'])
    r=infer([a,b],[100],variables=[v]);assert r['status']=='empty'
    assert all(x['feasible']['count']==1 for x in r['per_observation'])
    assert r['conflict']['observation_ids']==['order1','second']
    v['scope']='observation'
    assert infer([a,b],[100],variables=[v])['status']=='insufficient_information'
    v['change_evidence']='Evidenced item change between the two order decisions.'
    r=infer([a,b],[100],variables=[v]);assert r['status']=='conditional' and r['feasible']['values']==[100]


def test_unknown_abilities_and_shared_weather_are_explicit():
    o=observation();o['context']['opponent']['ability']=None
    assert infer([o])['status']=='insufficient_information'
    v=dict(id='ability',scope='shared',observation_ids=['order1'],path='opponent.ability',values=['none','Swift Swim'])
    o['context']['field']['weather']='rain'
    assert infer([o],[50,100],variables=[v])['feasible']['values']==[50,100]


def test_decision_guarantees_quantify_all_candidates_and_scenarios():
    assert compare([99])['status']=='own_guaranteed_first'
    assert compare([101])['status']=='opponent_guaranteed_first'
    assert compare([99,101])['status']=='mixed_order_possible'
    tie=compare([99,100]);assert tie['status']=='speed_tie_possible' and tie['tie_only_uncertainty']
    tie=compare([99,100,101]);assert tie['status']=='speed_tie_possible' and tie['non_tie_order_varies']
    c=deepcopy(BASE);c['opponent']['item']=None
    v=dict(id='item',scope='shared',observation_ids=['query'],path='opponent.item',values=['none','Choice Scarf'])
    assert compare([90],c,variables=[v])['status']=='mixed_order_possible'
    v['values'].append('Quick Claw')
    r=compare([90],c,variables=[v]);assert r['status']=='unsupported' and not r['own_guaranteed_first']


def test_legal_speed_gaps_and_joint_training_budget():
    o=observation();o['context']['opponent']['identity']='Charizard';o['context']['own']['actual_speed']=1
    r=infer_speed(observations=[o],profile=PROFILE,champions=dict(identity='Charizard',form='base'))
    assert r['feasible']['has_gaps'] and r['compatible_training']['branches']
    r=infer_speed(observations=[o],profile=PROFILE,champions=dict(identity='Charizard',form='base',known_training_points={'hp':32,'attack':32},alignments=[dict(increase=None,decrease=None)]))
    assert r['feasible']['values']==[120,121,122]


@pytest.mark.parametrize('values',[[],[True],[0],[4096],[1.5],None,range(1000000)])
def test_invalid_domains(values):assert infer([observation()],values)['status']=='insufficient_information'


def test_cross_instance_epoch_and_unknown_modifiers():
    a=observation();b=observation('other');b['context']['opponent']['instance_id']='other'
    assert infer([a,b])['status']=='insufficient_information'
    b=observation('other');b['stat_epoch']='changed'
    assert infer([a,b])['status']=='insufficient_information'
    a['context']['opponent']['tailwind']=None
    assert infer([a])['status']=='insufficient_information'
    a=observation();a['context']['opponent']['item']={'state':'conflicting','values':['none','Choice Scarf']}
    assert infer([a])['status']=='insufficient_information'


def test_evidence_profile_limits_and_repeatability():
    o=observation();original=deepcopy(o)
    assert infer_speed(observations=[o],candidate_speeds=[100])['status']=='unsupported'
    assert infer([o])==infer([o]) and o==original
    assert infer([o],max_evaluations=1)['status']=='insufficient_information'


def test_oracle_pins_and_cli():
    for name,digest in json.loads(Path('tests/fixtures/speed_order/manifest.json').read_text())['files'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest
    p=subprocess.run([sys.executable,'-m','speed_order','examples/speed_order/compare.json'],capture_output=True,text=True)
    assert p.returncode==0 and json.loads(p.stdout)['status']=='speed_tie_possible'


@pytest.mark.parametrize('effect',['After You','Quash'])
def test_forced_order_is_not_speed_evidence(effect):
    o=observation();o['context']['ordering_effects']=[dict(effect=effect,actor='opponent',active=True,evidence='Verified forced-order effect.')]
    assert infer([o])['status']=='non_informative'
    assert compare([100],o['context'])['status']=='non_speed_ordering'


def test_conditional_priority_and_unknown_effect_are_gated():
    c=deepcopy(BASE);c['actions']['opponent']['move']='Grassy Glide'
    assert compare([100],c)['status']=='unsupported'
    c=deepcopy(BASE);c['ordering_effects']=[dict(effect='unknown mechanic',actor='own',active=True,evidence='Explicit uncertainty.')]
    assert compare([100],c)['status']=='unsupported'


def test_cached_values_and_provenance_cannot_be_mutated_by_callers():
    args=dict(actual_speed=101,participant=BASE['own'],field=BASE['field'],profile=PROFILE)
    r=effective_speed(**args);r['provenance'].clear();r['modifiers'].append('bogus')
    r=effective_speed(**args)
    assert r['provenance'] and 'bogus' not in r['modifiers']


def test_speed_import_has_no_recognition_dependencies():
    code="import speed_order,sys; assert not any(n.split('.')[0] in {'cv2','recognition','pytesseract','capture'} for n in sys.modules)"
    assert subprocess.run([sys.executable,'-c',code],capture_output=True).returncode==0


def test_explicit_numerical_speed_does_not_require_base_stat_data(monkeypatch):
    from speed_order import core
    from knowledge import KnowledgeBase
    kb=KnowledgeBase();kb.facts['pokemon'].pop('pokeapi:species:6',None)
    monkeypatch.setattr(core,'knowledge',lambda:kb);core.identity_key.cache_clear()
    assert compare([99])['status']=='own_guaranteed_first'
    core.identity_key.cache_clear()
