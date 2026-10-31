"""Offline exact-distribution oracle comparisons and input safety."""
from copy import deepcopy
import json,subprocess,sys
from pathlib import Path
import pytest
from damage import calculate,calculate_scenarios
from damage.core import poke_round

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=json.loads((ROOT/'tests/fixtures/damage/reference-rolls.json').read_text())
SUPPORTED=[r for r in FIXTURE['cases'] if r['id'] not in {'ability-attacker-Galvanize','ability-defender-Storm Drain'}]
@pytest.mark.parametrize('row',SUPPORTED,ids=lambda r:r['id'])
def test_independent_full_rolls(row):
    result=calculate(row['input'])
    assert result['status']=='exact_reference',result
    assert result['distribution']['rolls']==row['rolls']
    assert sum(r['count'] for r in result['distribution']['frequencies'])==len(row['rolls'])
    assert all(r['probability']['denominator']==len(row['rolls']) for r in result['distribution']['frequencies'])

@pytest.fixture
def request_data():return deepcopy(FIXTURE['cases'][0]['input'])

@pytest.mark.parametrize('path',[('attacker','ability'),('defender','item'),('field','weather'),('field','reflect'),('field','terrain'),('field','critical')])
def test_unknown_is_not_neutral(request_data,path):
    request_data[path[0]][path[1]]=None
    r=calculate(request_data);assert r['status']=='incomplete_input' and r['distribution'] is None


def test_conflicting_modifier(request_data):
    request_data['field']['weather']={'state':'conflicting','values':['rain','sun']}
    assert calculate(request_data)['status']=='conflicting_input'

@pytest.mark.parametrize('value',[True,-1,0,1.5,65536])
def test_invalid_actual_stat(request_data,value):
    request_data['attacker']['stats']['attack']=value
    assert calculate(request_data)['status']=='invalid_input'

@pytest.mark.parametrize('value',[-7,7,True,'0'])
def test_invalid_stage(request_data,value):
    request_data['defender']['stages']['defense']=value
    assert calculate(request_data)['status']=='invalid_input'


def test_unknown_relevant_and_irrelevant_stats(request_data):
    request_data['attacker']['stats']['special_attack']=None
    request_data['attacker']['stages']['special_attack']=None
    assert calculate(request_data)['status']=='exact_reference'
    request_data['attacker']['stages']['attack']=None
    assert calculate(request_data)['status']=='incomplete_input'


def test_effective_stats_never_double_counted(request_data):
    request_data['attacker']['stat_basis']='effective'
    assert calculate(request_data)['status']=='unsupported'


def test_evidence_only_does_not_claim_champions_exact(request_data):
    request_data['profile']='champions-evidence-only-v1'
    result=calculate(request_data);assert result['status']=='unsupported' and result['distribution'] is None

@pytest.mark.parametrize('move',['Protect','Fissure','Bullet Seed','Gyro Ball','Knock Off','Super Fang','Psywave'])
def test_unaudited_exceptions_do_not_fall_through(request_data,move):
    request_data['move']=move
    result=calculate(request_data);assert result['distribution'] is None and result['status'] in {'unsupported','unresolved_input'}


def test_multiscale_requires_hp(request_data):
    request_data['defender']['ability']='Multiscale';request_data['defender']['current_hp']=None
    assert calculate(request_data)['status']=='incomplete_input'


def test_unknown_hp_does_not_invent_ko_probability(request_data):
    request_data['defender']['current_hp']=None;request_data['defender']['maximum_hp']=None
    result=calculate(request_data)
    assert result['status']=='exact_reference' and result['distribution']['ko_probability'] is None
    assert result['distribution']['percent_max_hp'] is None


def test_pokemon_form_and_move_resolution(request_data):
    expected=calculate(request_data)['distribution']
    request_data['attacker']['identity']='喷火龙';request_data['move']='泰山压顶'
    assert calculate(request_data)['distribution']==expected
    request_data['move']='pokeapi:move:34';assert calculate(request_data)['distribution']==expected
    request_data['move']='34';assert calculate(request_data)['status']=='invalid_input'
    request_data['attacker']['form']=None;assert calculate(request_data)['status']=='incomplete_input'


def test_conditional_scenarios_no_invented_weights(request_data):
    other=deepcopy(request_data);other['attacker']['status']='burn'
    result=calculate_scenarios(dict(scenarios=[dict(id='healthy',input=request_data),dict(id='burned',input=other)]))
    assert result['status']=='conditional_scenarios' and result['scenario_probabilities'] is None
    assert result['scenarios'][0]['result']['distribution']!=result['scenarios'][1]['result']['distribution']


def test_wiki_rounding_examples():
    byid={r['id']:r for r in FIXTURE['cases']}
    assert calculate(byid['wiki-ice-fang']['input'])['distribution']['rolls']==[168,168,168,172,172,172,180,180,180,184,184,184,192,192,192,196]
    assert calculate(byid['wiki-ice-fang-item-crit']['input'])['distribution']['rolls']==[268,276,276,280,288,288,292,292,300,300,304,304,312,312,316,324]
    assert poke_round(49*4096+2048)==49
    assert poke_round(49*4096+2049)==50


def test_unsupported_reference_discrepancies_are_visible():
    for r in FIXTURE['cases']:
        if r['id'] in {'ability-attacker-Galvanize','ability-defender-Storm Drain'}:assert calculate(r['input'])['status']=='unsupported'


def test_json_cli_and_no_ocr_dependency():
    code='import sys,json;from damage import calculate;print(json.dumps(calculate(json.load(sys.stdin))));assert not any(k.startswith(("cv2","recognition","onnxruntime")) for k in sys.modules)'
    proc=subprocess.run([sys.executable,'-c',code],input=json.dumps(FIXTURE['cases'][0]['input']),text=True,capture_output=True,check=True,cwd=ROOT)
    assert json.loads(proc.stdout)['status']=='exact_reference'

COMBOS=json.loads((ROOT/'tests/fixtures/damage/combo-rolls.json').read_text())['cases']
@pytest.mark.parametrize('row',COMBOS,ids=lambda r:r['id'])
def test_mixed_modifiers_full_rolls(row):
    result=calculate(row['input'])
    assert result['status']=='exact_reference',result
    assert result['distribution']['rolls']==row['rolls']


def test_pinned_reference_fixtures_have_not_been_rewritten():
    import hashlib
    manifest=json.loads((ROOT/'tests/fixtures/damage/manifest.json').read_text())
    for name,digest in manifest['files'].items():assert hashlib.sha256((ROOT/'tests/fixtures/damage'/name).read_bytes()).hexdigest()==digest


def test_hp_loss_is_separate_from_potential_damage(request_data):
    request_data['defender']['current_hp']=1
    out=calculate(request_data)['distribution']
    assert out['minimum']>1 and out['hp_loss_rolls']==[1]*16
    assert out['ko_probability']==dict(numerator=16,denominator=16)


def test_reject_unsupported_pre_hit_boost_and_variable_power(request_data):
    for move in ['Electro Shot','Return']:
        request_data['move']=move
        result=calculate(request_data)
        assert result['distribution'] is None and result['status'] in {'unsupported','unresolved_input'}


def test_cli_machine_readable_failure_and_success():
    result=subprocess.run([sys.executable,'-m','damage',str(ROOT/'examples/damage/neutral.json')],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0 and json.loads(result.stdout)['status']=='exact_reference'
    bad=subprocess.run([sys.executable,'-m','damage'],input='not json',cwd=ROOT,capture_output=True,text=True)
    assert bad.returncode==2 and json.loads(bad.stdout)['status']=='invalid_input'

EXTRA=json.loads((ROOT/'tests/fixtures/damage/extra-rolls.json').read_text())['cases']
@pytest.mark.parametrize('row',EXTRA,ids=lambda r:r['id'])
def test_terrain_and_overflow_full_rolls(row):
    result=calculate(row['input'])
    assert result['status']=='exact_reference',result
    assert result['distribution']['rolls']==row['rolls']


def test_invalid_non_finite_json(request_data):
    request_data['field']['other_effects']=[float('nan')]
    result=calculate(request_data)
    assert result['status']=='invalid_input' and result['distribution'] is None


def test_conflicting_profile_still_serializable(request_data):
    request_data['profile']={'state':'conflicting','values':['a','b']}
    result=calculate(request_data)
    assert result['status']=='conflicting_input' and result['profile'] is None
    json.dumps(result,allow_nan=False)


def test_unknown_grounding_relevant_only_with_terrain(request_data):
    request_data['field']['attacker_grounded']=None
    assert calculate(request_data)['status']=='exact_reference'
    request_data['field']['terrain']='grassy'
    assert calculate(request_data)['status']=='incomplete_input'


def test_wrong_form_and_extra_effects_are_not_ignored(request_data):
    request_data['attacker']['form']='Mega Salamence'
    assert calculate(request_data)['status']=='invalid_input'
    request_data['attacker']['form']='base';request_data['field']['other_effects']=['gravity']
    assert calculate(request_data)['status']=='unsupported'


def test_sacred_sword_proves_defense_stage_irrelevant(request_data):
    request_data['move']='Sacred Sword'
    expected=calculate(request_data)['distribution']
    request_data['defender']['stages']['defense']=None
    assert calculate(request_data)['distribution']==expected


def test_explicit_new_mega_form(request_data):
    request_data['attacker']['identity']='超级妖火红狐';request_data['attacker']['form']='as_named'
    request_data['attacker']['ability']='none';request_data['move']='喷射火焰'
    r=calculate(request_data)
    assert r['status']=='exact_reference' and r['identities']['attacker']['canonical_id']=='pokeapi:form:10518'


def test_does_not_modify_callers_snapshot(request_data):
    original=deepcopy(request_data);calculate(request_data)
    assert request_data==original


def test_existing_canonical_pokemon_identity_mapping(request_data):
    expected=calculate(request_data)['distribution']
    request_data['attacker']['identity']='pokeapi:pokemon:6';request_data['attacker'].pop('form')
    assert calculate(request_data)['distribution']==expected
    request_data['attacker']['identity']='pokeapi:pokemon:10034'
    result=calculate(request_data)
    assert result['status']=='exact_reference' and result['identities']['attacker']['canonical_id']=='pokeapi:form:10134'
