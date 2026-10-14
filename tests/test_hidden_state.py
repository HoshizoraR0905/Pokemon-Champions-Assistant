"""Evidence or explicitly labeled reference inference; no probabilistic assumptions."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import shutil
import pytest
from battle_events.schema import BattleEvent, Evidence
from tracking.hidden_state import HiddenEngine, HiddenRules, Constraint
ROOT=Path(__file__).resolve().parents[1]
PID='opponent:salamence'

def event(n,kind='move_execution',*,side='opponent',pid=PID,refs=None,attrs=None,turn=1):
    return BattleEvent(f'e{n}',kind,side,{'species_id':373,'canonical_id':'pokeapi:species:373','name':'暴飞龙'},None,'synthetic observed event',
        refs or {'move':{'canonical_id':'pokeapi:move:14','name':'剑舞'}},None,[Evidence('synthetic_fixture',f'fixture:{n}',[f'fixture:{n}'],{'turn':turn})],None,'supported',[],
        {'sequence':n,'actor_instance_id':pid,**(attrs or {})},'confirmed')

def apply(engine,e):engine.apply(e,sequence=e.attributes['sequence'])
def new(reference=False):return HiddenEngine(rules=HiddenRules('showdown-champions-reference-v1' if reference else 'champions-evidence-only-v1'))
def field(engine,key,pid=PID):return engine.state['pokemon'][pid]['fields'][key]
def mega(n=1,side='opponent',pid=PID,target='pokeapi:pokemon:10089'):
    return event(n,'transformation',side=side,pid=pid,refs={},attrs={'mechanic':'mega_evolution','identity':{'canonical_identity':target,'species_id':373}})

def test_move_revelation_repeated_cross_turn_switches():
    e=new();apply(e,event(1));apply(e,event(2,'switch_out'));apply(e,event(3,'send_out',turn=2));apply(e,event(4,turn=2))
    assert field(e,'moves')['members']==['pokeapi:move:14']
    assert field(e,'moves')['slots']=={}
    assert len([x for x in e.state['pokemon'][PID]['revelations'] if x['field']=='moves'])==1
    assert len([c for c in e.state['pokemon'][PID]['constraints'] if c['variable']=='moves'])==2

@pytest.mark.parametrize('attrs',[{'execution_status':'selected'},{'effect_outcome':'selected'},{'move_origin':'copied'},{'move_origin':'external'},{'move_origin':'called'},{'move_origin':'temporary'}])
def test_selected_and_external_moves_do_not_become_configured(attrs):
    e=new();apply(e,event(1,attrs=attrs));assert field(e,'moves')['members']==[]

def test_display_is_not_execution():
    e=new();apply(e,event(1,'move_observation',attrs={'move_slot':1}));assert field(e,'moves')['members']==[]

def test_slot_and_count_conflicts():
    e=new(True)
    for n in range(1,6):apply(e,event(n,refs={'move':{'canonical_id':f'pokeapi:move:{n}'}}))
    assert field(e,'moves')['status']=='conflicting' and len(field(e,'moves')['members'])==5
    x=new();apply(x,event(1,attrs={'move_slot':1}));apply(x,event(2,attrs={'move_slot':1},refs={'move':{'canonical_id':'pokeapi:move:182'}}))
    assert field(x,'moves')['status']=='conflicting'


def test_ability_activation_native_effective_and_replacement():
    e=new();refs={'ability':{'canonical_id':'pokeapi:ability:22'}}
    apply(e,event(1,'ability_activation',refs=refs));assert field(e,'observed_ability')['members']==['pokeapi:ability:22']
    assert field(e,'native_ability')['status']=='unknown'
    apply(e,event(2,'ability_activation',refs=refs,attrs={'ability_origin':'native'}));assert field(e,'native_ability')['value']=='pokeapi:ability:22'
    apply(e,event(3,'ability_change',refs={'ability':{'canonical_id':'pokeapi:ability:84'}}));apply(e,event(4,'ability_activation',refs={'ability':{'canonical_id':'pokeapi:ability:84'}}))
    assert field(e,'native_ability')['value']=='pokeapi:ability:22'
    assert field(e,'observed_ability')['members']==['pokeapi:ability:22','pokeapi:ability:84']


def test_seed_consumption_does_not_prove_unburden_or_start_item():
    e=new();refs={'item':{'canonical_id':'pokeapi:item:914'}}
    apply(e,event(1,'item_activation',refs=refs));apply(e,event(2,'item_change',refs=refs,attrs={'change':'consume'}))
    assert field(e,'held_item')['value']=='pokeapi:item:914' and field(e,'item_at_start')['status']=='unknown'
    assert field(e,'native_ability')['status']=='unknown'
    assert e.state['pokemon'][PID]['dynamic_reference']['item_path']==['pokemon',PID,'item']

@pytest.mark.parametrize('side,pid',[('opponent',PID),('self','self:salamence')])
def test_reference_mega_requirement_correct_side(side,pid):
    e=new(True);apply(e,mega(side=side,pid=pid))
    d=field(e,'item_before_transformation:e1',pid)
    assert d['status']=='unknown' and d['provisional']['value']=='pokeapi:item:810'
    assert d['provisional']['status']=='provisional_inference'
    assert e.state['pokemon'][pid]['side']==side
    assert e.state['pokemon'][pid]['constraints'][-1]['rule_profile']=='showdown-champions-reference-v1'
    assert field(e,'item_at_start',pid)['status']=='unknown'
    if side=='self':assert PID not in e.state['pokemon']


def test_default_and_ambiguous_mega_no_stone():
    e=new();apply(e,mega());assert field(e,'held_item')['status']=='unknown'
    assert field(e,'transformation_requirements')['unresolved']
    x=new(True);apply(x,mega(target=None));assert field(x,'held_item')['provisional'] is None


def test_synthetic_verified_rule_and_disjunctive_prerequisites():
    r=deepcopy(HiddenRules('showdown-champions-reference-v1').transformations[0]);r.update(profiles=['champions-evidence-only-v1'],verification='champions_verified',provenance=['synthetic_test_only_not_actual_game_verification'])
    e=HiddenEngine(rules=HiddenRules(transformations=[r]));apply(e,mega());assert field(e,'held_item')['value']=='pokeapi:item:810'
    r['prerequisite_options']=[{'held_item':'pokeapi:item:810'},{'mechanism':'alternative'}]
    x=HiddenEngine(rules=HiddenRules(transformations=[r]));apply(x,mega());assert field(x,'held_item')['status']=='unknown'
    assert len(field(x,'item_before_transformation:e1')['unresolved'][0]['value'])==2


def test_conflicting_item_and_item_exchange_epochs():
    e=new();apply(e,event(1,'item_activation',refs={'item':{'canonical_id':'pokeapi:item:191'}}));apply(e,event(2,'item_activation',refs={'item':{'canonical_id':'pokeapi:item:211'}}))
    assert field(e,'held_item')['status']=='conflicting' and field(e,'held_item')['last_consistent']['candidates']==['pokeapi:item:191']
    x=new();apply(x,event(1,'item_activation',refs={'item':{'canonical_id':'pokeapi:item:191'}}));apply(x,event(2,'item_change',refs={'item':{'canonical_id':'pokeapi:item:211'}},attrs={'change':'receive'}))
    assert field(x,'held_item')['value']=='pokeapi:item:191' and field(x,'held_item_epoch:1')['value']=='pokeapi:item:211'


def test_incomplete_and_complete_legality_domains():
    e=new();apply(e,event(1));e.candidate_domain(PID,'native_ability',['a','b'],complete=False,verification='community_reference',provenance={'source':'fixture'})
    assert field(e,'native_ability')['status']=='unknown'
    e.candidate_domain(PID,'nature',['a','b'],complete=True,verification='champions_verified',provenance={'source':'synthetic_test'})
    assert field(e,'nature')['status']=='possible'
    e.add(Constraint('exclude',PID,'nature','exclude',['b'],reason='verified fixture exclusion'))
    assert field(e,'nature')['candidates']==['a'] and field(e,'nature')['status']=='constrained'
    assert HiddenEngine.from_dict(e.to_dict()).to_dict()==e.to_dict()


def test_numeric_domain_intersection_conflict_and_unknown_investment():
    e=new();apply(e,event(1))
    e.add(Constraint('range1',PID,'speed','interval',[90,150]));e.add(Constraint('range2',PID,'speed','interval',[120,160]))
    assert field(e,'speed')['interval']==[120,150]
    e.add(Constraint('range3',PID,'speed','interval',[1,10]));assert field(e,'speed')['status']=='conflicting'
    assert field(e,'training_allocation')['status']==field(e,'ivs')['status']==field(e,'nature')['status']=='unknown'
    assert HiddenEngine.from_dict(e.to_dict()).to_dict()==e.to_dict()


def test_exact_maximum_not_percentage_or_stat_stages():
    e=new();apply(e,event(1,'hp_change',attrs={'unit':'displayed_percent','after':100}));assert field(e,'max_hp')['status']=='unknown'
    apply(e,event(2,'hp_change',attrs={'unit':'absolute','after':100,'maximum':197}));assert field(e,'max_hp')['value']==197
    apply(e,event(3,'stat_change',attrs={'stats':['speed'],'stages':2,'direction':'up'}));assert field(e,'speed')['status']=='unknown'


def test_conditional_propagation_and_disjunction_elimination():
    e=new();apply(e,event(1))
    e.add(Constraint('if',PID,'rule_requirement','conditional',{'if':{'variable':'nature','equals':'a'},'then':{'variable':'speed','operation':'interval','value':[100,130]}}))
    assert field(e,'speed')['status']=='unknown'
    e.add(Constraint('nature',PID,'nature','equal','a'));assert field(e,'speed')['interval']==[100,130]
    e.add(Constraint('or',PID,'alternatives','any_of',[{'nature':'a'},{'nature':'b'}]));assert len(e.state['pokemon'][PID]['relations'][-1]['eliminated'])==1


def test_dedup_correction_retraction_and_order_replay():
    e=new();a=event(1);apply(e,a);before=e.to_dict();apply(e,a);assert e.to_dict()==before
    changed=deepcopy(a);changed.canonical_references['move']['canonical_id']='pokeapi:move:182';e.correct(a.event_id,changed,reason='fixture correction');assert field(e,'moves')['members']==['pokeapi:move:182']
    e.retract(a.event_id,reason='fixture retract');assert e.state['pokemon']=={}
    x=new();apply(x,event(2));apply(x,event(1));assert HiddenEngine.from_dict(x.to_dict()).to_dict()==x.to_dict()


def test_legacy_observable_restore():
    legacy={'initial_state':{},'history':[],'state':{}};assert HiddenEngine.from_dict(legacy).state['pokemon']=={}

@pytest.mark.parametrize('reference',[False,True])
@pytest.mark.local_artifacts('reports/M2.2.4-enriched-battle-state.json','reports/M2.2.4-provisional-battle-state.json','reports/M2.2.4-enriched-timeline.html','reports/M2.2.4-provisional-timeline.html')
def test_cached_full_battle_and_compact_html(reference,tmp_path):
    from scripts.replay_m231 import run
    from tracking.state_timeline import render_html,pack_timeline,unpack_timeline
    e,timeline,metrics=run(provisional=reference)
    assert metrics['hp_checkpoints']==metrics['identity_checkpoints']==28
    assert unpack_timeline(pack_timeline(timeline))==timeline
    html=render_html(timeline);assert len(html.encode())<3_000_000 and '隐藏配置' in html
    assert len([p for p in e.state['pokemon'].values() if p['side']=='opponent'])==4
    if shutil.which('node'):
        path=tmp_path/'hidden.html';path.write_text(html)
        result=subprocess.run(['node',str(ROOT/'scripts/benchmark_state_timeline.cjs'),str(path)],check=True,capture_output=True,text=True)
        assert json.loads(result.stdout)['states']==197


def test_knowledge_observations_keep_chronological_replay_position():
    e=new();apply(e,event(1));e.candidate_domain(PID,'native_ability',['a'],complete=False,verification='incomplete',provenance={'source':'fixture'})
    apply(e,event(2));assert HiddenEngine.from_dict(e.to_dict()).to_dict()==e.to_dict()


def test_decision_facing_projection_does_not_scan_history():
    from tracking.state_engine import StateEngine
    e=new();apply(e,event(1));e.history=[]
    projection=e.decision_projection();assert projection['opponent'][PID]['confirmed']['moves']==['pokeapi:move:14']
    from tracking.battle_state import BattleState
    observable=StateEngine(BattleState('synthetic'))
    decision=observable.decision_state(hidden_engine=e)
    assert decision['hidden_state_belief']['distribution'] is None and decision['hidden_configuration']['opponent'][PID]['confirmed']['moves']==['pokeapi:move:14']


def test_candidate_observation_not_promoted():
    e=new();a=event(1);a.status='candidate';apply(e,a)
    assert e.state['pokemon']=={} and e.state['unresolved'][0]['event_id']=='e1'


def test_provisional_item_inference_conflict_preserves_direct_item():
    e=new(True);apply(e,event(1,'item_activation',refs={'item':{'canonical_id':'pokeapi:item:191'}}));apply(e,mega(n=2))
    d=field(e,'held_item');assert d['value']=='pokeapi:item:191' and d['status']=='confirmed'
    assert d['provisional']['status']=='conflicting'


def test_wrong_species_transform_does_not_infer_stone():
    e=new(True);a=mega();a.actor['species_id']=478;apply(e,a);assert field(e,'held_item')['provisional'] is None


def test_displayed_verified_configuration_not_execution():
    e=new();apply(e,event(1,'move_observation',attrs={'configuration_confirmed':True,'move_slot':2}))
    assert field(e,'moves')['members']==['pokeapi:move:14'] and field(e,'moves')['slots']=={'2':'pokeapi:move:14'}


def test_disjunctive_conflict_and_direct_observation_not_hidden():
    e=new();apply(e,event(1));e.add(Constraint('nature',PID,'nature','equal','x'))
    e.add(Constraint('or',PID,'alternatives','any_of',[{'nature':'a'},{'nature':'b'}]))
    assert field(e,'alternatives')['status']=='conflicting' and field(e,'nature')['value']=='x'


def test_unverified_normalized_rule_cannot_become_hard_in_default():
    e=new();apply(e,event(1,'mechanic_observation',attrs={'hidden_constraints':[{'variable':'speed','operation':'interval','value':[100,110],
        'strength':'hard','rule':{'rule_id':'fixture-reference','verification':'simulator_reference_only','profiles':['showdown-champions-reference-v1']}}]}))
    assert field(e,'speed')['status']=='unknown' and field(e,'speed')['unresolved']


def test_invalid_constraint_event_is_atomic():
    e=new();before=e.to_dict()
    with pytest.raises(ValueError):apply(e,event(1,'mechanic_observation',attrs={'hidden_constraints':[{'variable':'speed','operation':'interval','value':[100,10]}]}))
    assert e.to_dict()==before


def test_conflicting_prerequisite_retracts_derived_constraint():
    e=new();apply(e,event(1))
    e.add(Constraint('if',PID,'requirement','conditional',{'if':{'variable':'nature','equals':'a'},'then':{'variable':'speed','operation':'interval','value':[100,130]}}))
    e.add(Constraint('a',PID,'nature','equal','a'));assert field(e,'speed')['interval']==[100,130]
    e.add(Constraint('b',PID,'nature','equal','b'));assert field(e,'nature')['status']=='conflicting' and field(e,'speed')['status']=='unknown'
    assert HiddenEngine.from_dict(e.to_dict()).to_dict()==e.to_dict()


def test_invalid_correction_rolls_back():
    e=new();a=event(1);apply(e,a);before=e.to_dict();bad=deepcopy(a)
    bad.attributes['hidden_constraints']=[{'variable':'speed','operation':'interval','value':[2,1]}]
    with pytest.raises(ValueError):e.correct(a.event_id,bad,reason='invalid fixture')
    assert e.to_dict()==before


def test_legality_added_after_evidence_stays_constrained_and_replayable():
    e=new();apply(e,event(1));e.add(Constraint('exclude',PID,'nature','exclude',['b'],reason='supported exclusion'))
    e.candidate_domain(PID,'nature',['a','b'],complete=True,verification='champions_verified',provenance={'source':'fixture'})
    assert field(e,'nature')['status']=='constrained'
    assert field(e,'nature')['eliminations'][0]['reason']=='supported exclusion'
    assert HiddenEngine.from_dict(e.to_dict()).to_dict()==e.to_dict()
