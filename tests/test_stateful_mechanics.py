"""M2.2.2 software tests; reference rules are not official Champions verification."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

import pytest

from tracking.battle_state import Fact, MechanicState, from_dict, fact
from tracking.state_engine import StateEngine, hash_state
from tracking.mechanic_rules import MechanicRules, showdown_champions_reference
from tracking.mechanics import MechanicRegistry, ensure, update, read, PROTEAN, UNBURDEN
from tracking.decision_state import protection_probability, decision_state
from tracking.state_timeline import semantic_diff, field_diff, build_timeline, render_html

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def initial():
    return from_dict(json.loads((ROOT/'tests/fixtures/m22_initial_context.json').read_text())['state'])


def pid(state, n=2):
    return state.sides['self'].party_instance_ids[n-1]


def event(state, n, kind, attributes=None, refs=None, *, party=2, side='self', turn=None):
    identifier = pid(state, party)
    attrs = dict(attributes or {})
    if side not in {'field'}:
        attrs['actor_instance_id'] = identifier
    evidence = {'source_type':'synthetic','source_id':'m222-software-test','observation_ids':[f'test:{n}'],
                'details':{'turn':turn} if turn is not None else {}}
    return dict(event_id=f'm222:{n}',event_type=kind,side=side,
                actor=deepcopy(state.pokemon[identifier].species.value) if side != 'field' else None,
                target=None,original_text=f'软件测试事件 {n}',canonical_references=refs or {},
                log_order=None,evidence=[evidence],ocr_confidence=None,parsing_confidence='supported',
                uncertainty=[],attributes=attrs,status='confirmed',associated_video_evidence=[])


def apply(engine, n, kind, attrs=None, refs=None, **kw):
    return engine.apply(event(engine.initial,n,kind,attrs,refs,**kw),sequence=n)


def ref(identifier):
    return {'canonical_id':identifier,'name':identifier}


def prepare(initial, ability_id=None, item=False, reference=True):
    p = initial.pokemon[pid(initial)]
    if ability_id:
        p.ability.current = fact(ref(ability_id), {'source':'synthetic annotation'})
        p.ability.suppressed = fact(False, {'source':'synthetic annotation'})
    if item:
        p.item.identity = fact(ref('pokeapi:item:900'), {'source':'synthetic annotation'})
        p.item.status = fact('known', {'source':'synthetic annotation'})
    return StateEngine(initial,mechanic_rules=showdown_champions_reference() if reference else MechanicRules())


def mechanic(engine, name, party=2):
    return engine.state.pokemon[pid(engine.state,party)].mechanics[name]


def establish_chain(engine):
    assert apply(engine,1,'mechanic_reset',{'mechanic_id':'protect_chain','reason':'verified fresh chain'}).application_status=='applied_confirmed'


def attempt(engine,n,party=2,turn=None):
    return apply(engine,n,'move_execution',refs={'move':ref('pokeapi:move:182')},party=party,turn=turn)


def outcome(engine,n,attempt_n,success=True,party=2,turn=None):
    return apply(engine,n,'protection_outcome',{'attempt_event_id':f'm222:{attempt_n}',
                 'outcome':'success' if success else 'failure','failure_reason':'stall_check'},party=party,turn=turn)


def test_protect_first_and_consecutive_chain_probability_cap(initial):
    engine=prepare(initial); establish_chain(engine)
    for count in range(8):
        query=protection_probability(engine.state.pokemon[pid(engine.state)],engine.mechanic_rules)
        assert query['probability']=={'numerator':1,'denominator':min(3**count,729)}
        assert query['authoritative_champions'] is False
        n=2+count*2;attempt(engine,n)
        assert protection_probability(engine.state.pokemon[pid(engine.state)],engine.mechanic_rules)['knowledge']=='unknown'
        assert read(mechanic(engine,'protect_chain'),'success_count').value==count
        outcome(engine,n+1,n)
        assert read(mechanic(engine,'protect_chain'),'success_count').value==count+1


def test_unknown_initial_attempt_is_not_success(initial):
    engine=prepare(initial)
    q=protection_probability(engine.state.pokemon[pid(engine.state)],engine.mechanic_rules)
    assert q['knowledge']=='unknown' and q['range']==[1/729,1]
    attempt(engine,1);outcome(engine,2,1)
    assert not read(mechanic(engine,'protect_chain'),'success_count').known
    assert read(mechanic(engine,'protect_chain'),'last_outcome').value=='success'


def test_failed_protect_and_nonfamily_reset(initial):
    engine=prepare(initial);establish_chain(engine);attempt(engine,2);outcome(engine,3,2)
    attempt(engine,4);outcome(engine,5,4,False)
    assert read(mechanic(engine,'protect_chain'),'success_count').value==0
    attempt(engine,6);outcome(engine,7,6)
    apply(engine,8,'move_execution',{'action_completed':True},{'move':ref('pokeapi:move:33')})
    assert read(mechanic(engine,'protect_chain'),'success_count').value==0


def test_protect_ui_selection_and_frame_phase_do_not_reset(initial):
    engine=prepare(initial);establish_chain(engine);attempt(engine,2);outcome(engine,3,2)
    apply(engine,4,'phase_observation',{'phase':'move_selection','selected_move':'Protect'})
    assert read(mechanic(engine,'protect_chain'),'success_count').value==1
    assert read(mechanic(engine,'protect_chain'),'attempt_event_id').value=='m222:2'


def test_protect_unknown_pending_outcome_and_unlinked_result(initial):
    engine=prepare(initial);establish_chain(engine);attempt(engine,2);attempt(engine,3)
    assert not read(mechanic(engine,'protect_chain'),'success_count').known
    assert outcome(engine,4,2).application_status=='rejected'
    assert read(mechanic(engine,'protect_chain'),'pending').value is True


def test_protect_switch_and_return_stable_instance_new_entry(initial):
    engine=prepare(initial);establish_chain(engine);attempt(engine,2);outcome(engine,3,2)
    original=pid(engine.state);old=read(mechanic(engine,'field_entry'),'entry_id').value
    apply(engine,4,'switch_out');apply(engine,5,'send_out',{'slot':'right'})
    assert pid(engine.state)==original
    assert read(mechanic(engine,'field_entry'),'entry_id').value!=old
    assert read(mechanic(engine,'protect_chain'),'success_count').value==0
    assert read(mechanic(engine,'field_entry'),'observed_entry_count').value==1


def test_fresh_entry_protect_chain_and_family_sharing(initial):
    engine=prepare(initial)
    apply(engine,1,'send_out',{'slot':'extra'},party=4)
    assert read(mechanic(engine,'protect_chain',4),'success_count').value==0
    apply(engine,2,'protection_attempt',refs={'move':ref('pokeapi:move:197')},party=4)
    outcome(engine,3,2,party=4)
    apply(engine,4,'protection_attempt',refs={'move':ref('pokeapi:move:182')},party=4)
    outcome(engine,5,4,party=4)
    assert read(mechanic(engine,'protect_chain',4),'success_count').value==2


def test_incomplete_turn_history_not_silently_reset(initial):
    engine=prepare(initial);establish_chain(engine)
    attempt(engine,2,turn=2);outcome(engine,3,2,turn=2)
    apply(engine,4,'turn_boundary',{'turn':3,'boundary':'start'})
    assert read(mechanic(engine,'protect_chain'),'success_count').value==1
    attempt(engine,5,turn=5)
    assert not read(mechanic(engine,'protect_chain'),'success_count').known


def test_coverage_supported_turn_expiry(initial):
    engine=prepare(initial);establish_chain(engine)
    attempt(engine,2,turn=2);outcome(engine,3,2,turn=2)
    apply(engine,4,'turn_boundary',{'turn':3,'boundary':'end','action_coverage_complete':True})
    assert read(mechanic(engine,'protect_chain'),'success_count').value==0


def test_default_rules_do_not_publish_probabilities_or_resets(initial):
    engine=prepare(initial,reference=False);establish_chain(engine);attempt(engine,2);outcome(engine,3,2)
    q=protection_probability(engine.state.pokemon[pid(engine.state)],engine.mechanic_rules)
    assert q['probability'] is None and q['range']==[0,1]
    apply(engine,4,'switch_out')
    assert not read(mechanic(engine,'protect_chain'),'success_count').known


def test_default_protean_observation_does_not_infer_once_per_entry(initial):
    engine = prepare(initial, PROTEAN, reference=False)
    apply(engine, 1, 'ability_activation', refs={'ability':ref(PROTEAN)})
    assert read(mechanic(engine, 'protean'), 'activated').value is True
    assert not read(mechanic(engine, 'protean'), 'eligibility').known
    assert apply(engine, 2, 'ability_activation', refs={'ability':ref(PROTEAN)}).application_status == 'applied_confirmed'
    apply(engine, 3, 'switch_out')
    apply(engine, 4, 'send_out', {'slot':'right'})
    assert not read(mechanic(engine, 'protean'), 'activated').known


def test_default_unburden_loss_has_no_inferred_speed_multiplier(initial):
    engine = prepare(initial, UNBURDEN, item=True, reference=False)
    apply(engine, 1, 'item_change', {'change':'consume'})
    m = mechanic(engine, 'unburden')
    assert not read(m, 'condition_established').known
    assert not read(m, 'effect_active').known
    assert not read(m, 'speed_multiplier').known


def test_protean_activation_type_change_and_repeated_attempt(initial):
    engine=prepare(initial,PROTEAN)
    assert apply(engine,1,'ability_activation',{'resulting_types':['fire']},{'ability':ref(PROTEAN)}).application_status=='applied_confirmed'
    assert read(mechanic(engine,'protean'),'activated').value is True
    assert engine.state.pokemon[pid(engine.state)].current_types.value==['fire']
    assert read(mechanic(engine,'protean'),'eligibility').value is False
    assert apply(engine,2,'ability_attempt',{'mechanic_id':'protean'}).application_status=='applied_confirmed'
    assert apply(engine,3,'ability_activation',refs={'ability':ref(PROTEAN)}).application_status=='rejected'
    assert len(engine.state.conflicts)==1


def test_protean_reentry_resets_and_initial_eligibility_unknown(initial):
    engine=prepare(initial,PROTEAN)
    assert not read(mechanic(engine,'protean'),'activated').known
    apply(engine,1,'ability_activation',refs={'ability':ref(PROTEAN)})
    before=pid(engine.state)
    apply(engine,2,'switch_out');apply(engine,3,'send_out',{'slot':'right'})
    assert pid(engine.state)==before
    assert read(mechanic(engine,'protean'),'activated').value is False
    assert read(mechanic(engine,'protean'),'eligibility').value is True
    apply(engine,4,'ability_activation',refs={'ability':ref(PROTEAN)})
    assert read(mechanic(engine,'protean'),'activated').value is True


def test_type_change_does_not_infer_protean(initial):
    engine=prepare(initial)
    apply(engine,1,'type_change',{'types':['water']})
    p=engine.state.pokemon[pid(engine.state)]
    assert p.current_types.value==['water'] and not p.ability.current.known
    assert 'protean' not in p.mechanics
    assert apply(engine,2,'type_change',{'types':['fire'],'cause':'protean'}).application_status=='applied_confirmed'
    assert 'protean' not in engine.state.pokemon[pid(engine.state)].mechanics


def test_unburden_item_loss_separate_from_speed_stage(initial):
    engine=prepare(initial,UNBURDEN,item=True)
    stages=deepcopy(engine.state.pokemon[pid(engine.state)].stages)
    apply(engine,1,'item_change',{'change':'consume'})
    m=mechanic(engine,'unburden')
    assert read(m,'effect_active').value is True and read(m,'speed_multiplier').value==2
    assert read(m,'has_item').value is False and read(m,'condition_established').value is True
    assert engine.state.pokemon[pid(engine.state)].stages==stages
    assert read(m,'speed_multiplier').knowledge=='derived'
    assert read(m,'speed_multiplier').provenance[0]['rule_verification']=='simulator_reference_only'


@pytest.mark.parametrize('unknown', ['ability','item','suppression'])
def test_unburden_unknown_prerequisite_does_not_establish_effect(initial,unknown):
    if unknown=='ability':
        engine=prepare(initial,item=True)
    else:
        p=initial.pokemon[pid(initial)];p.ability.current=fact(ref(UNBURDEN),{'source':'test'})
        p.ability.suppressed=Fact() if unknown=='suppression' else fact(False,{'source':'test'})
        if unknown=='suppression': p.item.status=fact('known',{'source':'test'});p.item.identity=fact(ref('item'),{'source':'test'})
        engine=prepare(initial)
    apply(engine,1,'item_change',{'change':'consume'})
    m=engine.state.pokemon[pid(engine.state)].mechanics.get('unburden')
    assert m is None or not read(m,'effect_active').known


def test_unburden_reacquire_switch_reloss_and_ability_end(initial):
    engine=prepare(initial,UNBURDEN,item=True)
    apply(engine,1,'item_change',{'change':'consume'})
    apply(engine,2,'item_change',{'change':'replace'},{'item':ref('pokeapi:item:901')})
    assert read(mechanic(engine,'unburden'),'effect_active').value is False
    apply(engine,3,'item_change',{'change':'remove'})
    assert read(mechanic(engine,'unburden'),'effect_active').value is True
    apply(engine,4,'switch_out');apply(engine,5,'send_out',{'slot':'right'})
    assert read(mechanic(engine,'unburden'),'effect_active').value is False
    apply(engine,6,'item_change',{'change':'replace'},{'item':ref('pokeapi:item:901')})
    apply(engine,7,'item_change',{'change':'consume'})
    assert read(mechanic(engine,'unburden'),'effect_active').value is True
    apply(engine,8,'ability_change',{'change':'remove'})
    assert read(mechanic(engine,'unburden'),'effect_active').value is False
    assert read(mechanic(engine,'unburden'),'trigger_latched').value is False


def test_unburden_suppression_pauses_latent_effect(initial):
    engine=prepare(initial,UNBURDEN,item=True)
    apply(engine,1,'item_change',{'change':'consume'})
    apply(engine,2,'ability_change',{'suppressed':True})
    assert read(mechanic(engine,'unburden'),'effect_active').value is False
    assert read(mechanic(engine,'unburden'),'trigger_latched').value is True
    apply(engine,3,'ability_change',{'suppressed':False})
    assert read(mechanic(engine,'unburden'),'effect_active').value is True


def test_transfer_to_unburden_holder_refreshes_recipient_effect(initial):
    donor = initial.pokemon[pid(initial, 1)]
    donor.item.identity = fact(ref('pokeapi:item:901'), {'source':'test'})
    donor.item.status = fact('known', {'source':'test'})
    engine = prepare(initial, UNBURDEN, item=True)
    apply(engine, 1, 'item_change', {'change':'consume'})
    assert read(mechanic(engine, 'unburden'), 'effect_active').value is True
    result = apply(engine, 2, 'item_change', {'change':'transfer',
                   'target_instance_id':pid(initial), 'target_side':'self'}, party=1)
    assert result.application_status == 'applied_confirmed'
    m = mechanic(engine, 'unburden')
    assert read(m, 'trigger_latched').value is True
    assert read(m, 'effect_active').value is False
    assert read(m, 'speed_multiplier').value == 1


def test_entry_activation_on_bench_rejected_atomically(initial):
    engine = prepare(initial)
    before = asdict(engine.state.pokemon[pid(initial, 4)])
    result = apply(engine, 1, 'ability_activation', refs={'ability':ref('pokeapi:ability:2')}, party=4)
    assert result.application_status == 'rejected'
    assert asdict(engine.state.pokemon[pid(initial, 4)]) == before


def test_lifecycle_conditions_independently_serialized(initial):
    engine = prepare(initial, UNBURDEN, item=True)
    apply(engine, 1, 'item_change', {'change':'consume'})
    m = mechanic(engine, 'unburden')
    assert m.activation_conditions and m.persistence_conditions and m.reset_conditions
    projected = engine.decision_state()['pokemon'][pid(initial)]['mechanics']['unburden']
    assert projected['persistence_conditions'] == m.persistence_conditions
    assert StateEngine.from_dict(engine.to_dict()).to_dict() == engine.to_dict()


def test_seed_activation_alone_neither_consumes_nor_infers_unburden(initial):
    engine=prepare(initial,item=True)
    apply(engine,1,'item_activation',refs={'item':ref('pokeapi:item:900')})
    p=engine.state.pokemon[pid(engine.state)]
    assert not p.item.status.known and 'unburden' not in p.mechanics


def test_entry_abilities_reactivate_without_implicit_consequences(initial):
    engine=prepare(initial)
    for n in (1,4):
        if n==4:
            apply(engine,2,'switch_out');apply(engine,3,'send_out',{'slot':'right'})
        assert apply(engine,n,'ability_activation',refs={'ability':ref('pokeapi:ability:2')}).application_status=='applied_confirmed'
        assert engine.state.weather.kind.value=='snow'
        assert read(mechanic(engine,'entry_triggers'),'activation_count').value==1
    apply(engine,5,'weather_change',{'weather':'rain','change':'start'},side='field')
    assert engine.state.weather.kind.value=='rain'
    assert len(engine.state.weather.kind.provenance)==1


def test_independent_mechanics_coexist_and_transform_persists(initial):
    engine=prepare(initial,UNBURDEN,item=True)
    establish_chain(engine);attempt(engine,2);outcome(engine,3,2)
    apply(engine,4,'item_change',{'change':'consume'})
    p=engine.state.pokemon[pid(engine.state)]
    identity=deepcopy(p.species.value);identity['canonical_identity']='test:form'
    apply(engine,5,'transformation',{'identity':identity,'mechanic':'observed_form_change'})
    assert read(mechanic(engine,'protect_chain'),'success_count').value==1
    assert read(mechanic(engine,'unburden'),'effect_active').value is True
    assert 'field_entry' in engine.state.pokemon[pid(engine.state)].mechanics


def test_replay_correction_retraction_dedup_and_serialization(initial):
    engine=prepare(initial);establish_chain(engine);attempt(engine,2);outcome(engine,3,2)
    payload=engine.to_dict()
    assert StateEngine.from_dict(json.loads(json.dumps(payload))).to_dict()==payload
    e=event(engine.initial,3,'protection_outcome',{'attempt_event_id':'m222:2','outcome':'success','failure_reason':'stall_check'})
    engine.apply(e,sequence=3);assert engine.to_dict()==payload
    e['attributes']['outcome']='failure'
    engine.correct('m222:3',e,sequence=3,reason='correct observed outcome')
    assert read(mechanic(engine,'protect_chain'),'success_count').value==0
    engine.retract('m222:3',reason='outcome unsupported')
    assert read(mechanic(engine,'protect_chain'),'pending').value is True
    saved=engine.to_dict();engine.replay();assert engine.to_dict()==saved


def test_extensible_custom_handler_no_core_schema_change(initial):
    class ActionCounter:
        mechanic_id='extension_example'
        def on_event(self,state,before,p,e,rules):
            if p is not None and e.event_type=='move_execution':
                m=ensure(p,self.mechanic_id,'per_instance')
                count=read(m,'count')
                update(m,'count',count.value+1 if count.known else 1,e,rules,inferred=True)
    registry=MechanicRegistry();registry.register(ActionCounter())
    engine=StateEngine(initial,mechanic_registry=registry)
    attempt(engine,1)
    assert read(mechanic(engine,'extension_example'),'count').value==1
    clone=StateEngine.from_dict(engine.to_dict(),mechanic_registry=registry)
    assert clone.to_dict()==engine.to_dict()


@pytest.mark.parametrize('scope',['per_action','per_turn','per_entry','per_instance','per_side','global'])
def test_generic_scopes_conflicting_facts_reset_expire(initial,scope):
    engine=prepare(initial)
    side='field' if scope=='global' else 'self'
    attrs={'mechanic_id':'custom_cooldown','scope':scope,'facts':{'counter':{'value':2,'knowledge':'observed'}},
           'activation_conditions':['observed trigger'],'reset_conditions':['explicit reset'],
           'expiration':{'remaining':{'value':1,'knowledge':'observed'},'timing':{'value':'turn_end','knowledge':'observed'}}}
    assert apply(engine,1,'mechanic_observation',attrs,side=side).application_status=='applied_confirmed'
    owner=engine.state if scope=='global' else engine.state.sides['self'] if scope=='per_side' else engine.state.pokemon[pid(engine.state)]
    assert owner.mechanics['custom_cooldown'].current['counter'].value==2
    apply(engine,2,'turn_boundary',{'turn':2,'boundary':'end'})
    owner=engine.state if scope=='global' else engine.state.sides['self'] if scope=='per_side' else engine.state.pokemon[pid(engine.state)]
    assert read(owner.mechanics['custom_cooldown'],'expired').value is True
    attrs={'mechanic_id':'custom_cooldown','scope':scope,'reason':'observed reset',
           'facts':{'counter':{'value':0,'knowledge':'conflicting','alternatives':[{'value':1}]}}}
    assert apply(engine,3,'mechanic_reset',attrs,side=side).application_status=='applied_confirmed'
    owner=engine.state if scope=='global' else engine.state.sides['self'] if scope=='per_side' else engine.state.pokemon[pid(engine.state)]
    assert read(owner.mechanics['custom_cooldown'],'counter').knowledge=='conflicting'


def test_projection_uses_current_mechanics_without_history(initial):
    engine=prepare(initial,UNBURDEN,item=True)
    apply(engine,1,'item_change',{'change':'consume'})
    projection=decision_state(engine.state,engine.mechanic_rules)
    p=projection['pokemon'][pid(engine.state)]
    assert p['mechanics']['unburden']['current']['speed_multiplier']['value']==2
    assert p['action_constraints']['protect']['knowledge']=='unknown'
    assert 'history' not in projection and 'observations' not in p['hp']
    assert 'executed' not in p['moves']
    assert projection['hidden_state_belief']['distribution'] is None
    assert projection['limitations']


def test_upgrade_old_fixture_without_data_loss(initial):
    raw=json.loads((ROOT/'tests/fixtures/m22_initial_context.json').read_text())['state']
    restored=from_dict(raw).to_dict()
    def retain_original(original,upgraded):
        if isinstance(original,dict):
            for key,value in original.items():retain_original(value,upgraded[key])
        else: assert original==upgraded
    retain_original(raw,restored)
    engine=StateEngine(initial)
    # Simulate a v1 engine envelope with pre-mechanic schema fields omitted.
    value=engine.to_dict();value['schema_version']=1;value.pop('mechanic_rules')
    value['initial_state']=raw
    clone=StateEngine.from_dict(value)
    retain_original(raw,clone.initial.to_dict())
    assert all(read(p.mechanics['field_entry'],'entry_id').known for p in clone.state.pokemon.values() if p.location.value['kind']=='active')


def test_actual_turn_two_conservative_and_viewer_mechanic_diffs():
    from scripts.replay_m22 import run
    engine,snapshots=run(ROOT/'tests/fixtures/battles/sample_battle_2/reviewed_events.json',ROOT/'tests/fixtures/m22_initial_context.json')
    assert len(engine.history)==20 and not engine.state.conflicts
    sneasler=next(p for p in engine.state.pokemon.values() if p.species.value['species_id']==903)
    assert 'unburden' not in sneasler.mechanics
    assert not sneasler.ability.current.known
    assert len(sneasler.stages['special_defense'].changes)==len(sneasler.item.activations)==1
    timeline=build_timeline(engine.to_dict()['history'],engine.initial.to_dict(),snapshots,engine.state.to_dict())
    assert any('mechanics' in c['path'] for e in timeline['entries'] for c in e['raw_changes'])
    assert 'field_entry' in render_html(timeline)
    assert 'mechanics' in timeline['entries'][-1]['after']['pokemon'][sneasler.pokemon_instance_id]
