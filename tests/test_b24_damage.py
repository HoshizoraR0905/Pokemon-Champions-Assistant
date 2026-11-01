"""Directly encountered B24 contracts; production predictions stay frozen."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import pytest
from damage import calculate
from damage.data import database
from tests.test_inverse_damage import BASE


def oracle(tmp_path,request):
    if not Path('.cache/m31/oracle/node_modules/@smogon/calc').is_dir():pytest.skip('optional pinned oracle unavailable')
    p=tmp_path/'input.json';p.write_text(json.dumps({'cases':[{'id':'B24','input':request}]}))
    return json.loads(subprocess.check_output(['node','scripts/damage_b24_oracle.cjs',str(p)]))['cases'][0]['rolls']


@pytest.mark.parametrize('critical',[False,True])
@pytest.mark.parametrize('move',['High Horsepower','Spirit Break','Weather Ball','Electro Shot','Psychic Fangs','Knock Off','Heavy Slam'])
def test_encountered_damage_exact_rolls_and_no_secondary_mutation(tmp_path,move,critical):
    p=deepcopy(BASE);p['move']=move;p['field'].update(critical=critical,reflect=True,light_screen=True)
    if move=='Electro Shot':p['attacker']['stages']['special_attack']=1
    if move=='Knock Off':p['defender']['item']='Leftovers'
    original=deepcopy(p);result=calculate(p)
    assert result['status']=='exact_reference',result
    assert result['distribution']['rolls']==oracle(tmp_path,p)
    assert p==original


@pytest.mark.parametrize('weather',['none','sun','rain','sand','snow'])
def test_weather_ball_type_and_integer_damage(tmp_path,weather):
    p=deepcopy(BASE);p['move']='Weather Ball';p['field']['weather']=weather
    result=calculate(p);assert result['status']=='exact_reference'
    assert result['distribution']['rolls']==oracle(tmp_path,p)


def test_real_current_form_weights_and_sand_force(tmp_path):
    p=deepcopy(BASE);kb,_,_=database()
    for role,ident,ability in [('attacker','pokeapi:form:10174','Sand Force'),('defender','pokeapi:form:10534','Levitate')]:
        p[role].update(identity=ident,form='as_named',ability=ability,item=kb.facts['pokemon'][ident]['required_item'])
    p['move']='Heavy Slam';p['field']['weather']='sand'
    result=calculate(p);assert result['status']=='exact_reference',result
    assert result['distribution']['rolls']==oracle(tmp_path,p)
    assert any(t.get('base_power')==120 for t in result['trace'])
    assert any(m['name']=='Sand Force' for m in result['applied_modifiers'])


@pytest.mark.parametrize('item',['none','Leftovers'])
def test_knock_off_removability(tmp_path,item):
    p=deepcopy(BASE);p['move']='Knock Off';p['defender']['item']=item
    result=calculate(p);assert result['distribution']['rolls']==oracle(tmp_path,p)
    assert any(m['name']=='Knock Off removable held item' for m in result['applied_modifiers'])==(item!='none')


def test_knock_off_does_not_boost_against_matching_mega_stone(tmp_path):
    p=deepcopy(BASE);p['move']='Knock Off'
    p['defender'].update(identity='pokeapi:form:10534',form='as_named',ability='Levitate',item='Garchompite Z')
    result=calculate(p);assert result['status']=='exact_reference'
    assert not any(m['name']=='Knock Off removable held item' for m in result['applied_modifiers'])
    assert result['distribution']['rolls']==oracle(tmp_path,p)


@pytest.mark.parametrize('weather',['none','rain'])
def test_weather_ball_is_not_changed_by_aerilate(tmp_path,weather):
    p=deepcopy(BASE);p['move']='Weather Ball';p['attacker']['ability']='Aerilate';p['field']['weather']=weather
    result=calculate(p);assert result['status']=='exact_reference'
    assert result['distribution']['rolls']==oracle(tmp_path,p)


@pytest.mark.parametrize('weight,power',[(199.9,40),(200,60),(299.9,60),(300,80),(399.9,80),(400,100),(499.9,100),(500,120)])
def test_heavy_slam_exact_weight_boundaries(monkeypatch,weight,power):
    from damage.data import resolve
    p=deepcopy(BASE);p['move']='Heavy Slam';kb,_,_=database()
    attacker=resolve(p['attacker']['identity'],'species','attacker')['canonical_id']
    defender=resolve(p['defender']['identity'],'species','defender')['canonical_id']
    monkeypatch.setitem(kb.facts['pokemon'][attacker],'weight_kg',weight)
    monkeypatch.setitem(kb.facts['pokemon'][defender],'weight_kg',100)
    result=calculate(p);assert result['status']=='exact_reference'
    assert next(t['base_power'] for t in result['trace'] if t.get('handler')=='Heavy Slam')==power
