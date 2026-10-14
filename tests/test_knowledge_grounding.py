from copy import deepcopy
import json
from pathlib import Path
import pytest
from tracking.battle_state import from_dict, Fact
from tracking.state_engine import StateEngine, event_from_dict
from tracking.mechanic_rules import showdown_champions_reference
from tracking.knowledge_grounding import initialize_team, MoveKnowledge
from scripts.replay_m224 import enrich, validate
ROOT=Path(__file__).resolve().parents[1]

def load(p):
    if p == 'reports/M2.2.3-battle-state.json':
        context=json.loads((ROOT/'tests/fixtures/m223_initial_context.json').read_text())
        events=json.loads((ROOT/'tests/fixtures/battles/sample_battle_3/reviewed_mechanic_events.json').read_text())['events']
        return {'initial_state':StateEngine(from_dict(context['state'])).initial.to_dict(),
                'history':[{'event':event} for event in events]}
    return json.loads((ROOT/p).read_text())

def setup_pair(provisional=True, stage=0, move=14):
    old=load('reports/M2.2.3-battle-state.json')
    initial=from_dict(old['initial_state']);initial.knowledge['move_grounding']=True
    events=[r['event'] for r in old['history']]
    use=deepcopy(next(e for e in events if e['event_type']=='move_execution' and e['canonical_references']['move']['canonical_id']=='pokeapi:move:14'))
    result=deepcopy(next(e for e in events if e['event_type']=='stat_change' and '大幅提高' in e['original_text']))
    use['canonical_references']['move']['canonical_id']=f'pokeapi:move:{move}'
    pid=use['attributes']['actor_instance_id']
    initial.pokemon[pid].stages['attack'].value=Fact() if stage is None else Fact(stage,'observed')
    initial.pokemon[pid].stages['attack'].interval=Fact()
    return StateEngine(initial,mechanic_rules=showdown_champions_reference() if provisional else None),use,result,pid

@pytest.mark.parametrize('baseline,expected',[(0,2),(5,6),(-6,-4),(None,None)])
def test_quantitative_and_bounds(baseline,expected):
    engine,use,result,pid=setup_pair(stage=baseline)
    engine.apply(use,sequence=1);assert not engine.state.pokemon[pid].stages['attack'].changes
    engine.apply(result,sequence=2)
    s=engine.state.pokemon[pid].stages['attack'];assert s.value.value==expected
    assert s.changes[-1]['amount']==2
    assert s.changes[-1]['mechanics']['rule']['verification']=='simulator_reference_only'
    if baseline is None:assert s.interval.value==[-4,6]
    assert StateEngine.from_dict(engine.to_dict()).to_dict()==engine.to_dict()

def test_default_no_provisional():
    engine,use,result,pid=setup_pair(False)
    engine.apply(use,sequence=1);engine.apply(result,sequence=2)
    assert engine.state.pokemon[pid].stages['attack'].value.value is None
    assert engine.state.pokemon[pid].stages['attack'].changes[-1]['amount'] is None

@pytest.mark.parametrize('outcome',['failed','blocked','selected','uncertain'])
def test_unsuccessful_announcement(outcome):
    engine,use,result,pid=setup_pair();use['attributes'].update(effect_outcome=outcome,interaction_checked=True)
    engine.apply(use,sequence=1);assert engine.state.pokemon[pid].stages['attack'].value.value==0

def test_explicit_duplicate_and_separate_boost():
    engine,use,result,pid=setup_pair();use['attributes'].update(effect_outcome='confirmed',interaction_checked=True)
    engine.apply(use,sequence=1);result['attributes']['effect_of']=use['event_id'];engine.apply(result,sequence=2)
    assert engine.state.pokemon[pid].stages['attack'].value.value==2
    duplicate=deepcopy(result);duplicate['event_id']='duplicate';engine.apply(duplicate,sequence=3)
    assert engine.state.pokemon[pid].stages['attack'].value.value==2
    use2=deepcopy(use);use2['event_id']='second';engine.apply(use2,sequence=4)
    result2=deepcopy(result);result2['event_id']='second-result';result2['attributes']['effect_of']='second';engine.apply(result2,sequence=5)
    assert engine.state.pokemon[pid].stages['attack'].value.value==4
    engine.retract('second',reason='test');assert engine.state.pokemon[pid].stages['attack'].value.value is None or engine.state.conflicts

def test_direct_exact_without_move_or_rule():
    engine,use,result,pid=setup_pair(False);result['attributes']['stages']=2;engine.apply(result,sequence=1)
    assert engine.state.pokemon[pid].stages['attack'].value.value==2

def test_conflicting_delta_keeps_direct_evidence():
    engine,use,result,pid=setup_pair();engine.apply(use,sequence=1);result['attributes']['stages']=1;engine.apply(result,sequence=2)
    assert engine.state.pokemon[pid].stages['attack'].value.value==1
    assert engine.state.conflicts[-1]['kind']=='observed_rule_delta_conflict'

@pytest.mark.parametrize('move,stats,delta',[(349,['attack','speed'],1),(347,['special_attack','special_defense'],1),(334,['defense'],2),(370,['defense','special_defense'],-1)])
def test_representative_effects(move,stats,delta):
    engine,use,result,pid=setup_pair(move=move)
    result['attributes'].update(stats=stats,direction='up' if delta>0 else 'down')
    engine.apply(use,sequence=1);engine.apply(result,sequence=2)
    for stat in stats:assert engine.state.pokemon[pid].stages[stat].changes[-1]['amount']==abs(delta)

def test_rule_query_and_unresolved():
    k=MoveKnowledge();assert k.query('pokeapi:move:45','showdown-champions-reference-v1')['stage_changes']=={'attack':-1}
    assert k.query('missing','showdown-champions-reference-v1') is None
    assert k.query('pokeapi:move:14','champions-evidence-only-v1') is None

def test_configuration_matching_missing_and_immutable():
    old=load('reports/M2.2.3-battle-state.json');opening=load('data/teams/sample_battle_3_opening.json');saved=load('data/teams/my_team.json')
    pid='sample_battle_3:self:preview:3';state=initialize_team(from_dict(old['initial_state']),opening,saved=saved,bindings={'own_team_3':pid})
    cfg=state.knowledge['team']['instances'][pid]['fields'];assert cfg['special_attack']['value']==146 and cfg['speed']['value']==105
    assert cfg['evs']['value'] is None and cfg['nature']['value'] is None
    assert len(state.pokemon[pid].moves.known_slots)==4
    assert state.knowledge['team']['reconciliation'][0]['kind']=='saved_configuration_unmatched'
    assert len(state.knowledge['team']['preview_roster'])==6 and len(state.sides['self'].party_instance_ids)==4
    with pytest.raises(ValueError):initialize_team(from_dict(old['initial_state']),opening,bindings={'own_team_2':pid})
    assert opening==load('data/teams/sample_battle_3_opening.json')

@pytest.mark.parametrize('provisional',[False,True])
@pytest.mark.local_artifacts('reports/M2.2.3-battle-state.json')
def test_cached_full_battle(provisional):
    engine,snapshots,old=enrich(provisional=provisional);metrics=validate(engine,snapshots,old)
    assert metrics['hp_checkpoints']==metrics['identity_checkpoints']==28
    pid='sample_battle_3:self:preview:3';assert engine.initial.knowledge['team']['instances'][pid]==engine.state.knowledge['team']['instances'][pid]
    from tracking.state_timeline import build_timeline, render_html
    html=render_html(build_timeline(engine.to_dict()['history'],engine.initial.to_dict(),snapshots,engine.state.to_dict()))
    assert '实际个体数值' in html and 'causal_actions' in html

def test_saved_verified_reconciliation_and_missing_stats():
    old=load('reports/M2.2.3-battle-state.json');opening=load('data/teams/sample_battle_3_opening.json');saved=deepcopy(opening)
    member=opening['members'][2];member['saved_instance_id']='own_team_3'
    member['fields']['speed']['value']=None
    pid='sample_battle_3:self:preview:3'
    state=initialize_team(from_dict(old['initial_state']),opening,saved=saved,bindings={'own_team_3':pid},saved_match_verified=True)
    assert state.knowledge['team']['instances'][pid]['fields']['speed']['value']==105
    member['fields']['special_attack']['value']=99
    state=initialize_team(from_dict(old['initial_state']),opening,saved=saved,bindings={'own_team_3':pid},saved_match_verified=True)
    assert state.conflicts[-1]['kind']=='configuration_conflict'
    state=initialize_team(from_dict(old['initial_state']),opening,bindings={'own_team_3':pid})
    assert state.knowledge['team']['instances'][pid]['fields']['speed']['value'] is None

def test_alias_instance_and_ability_item_boundary():
    engine,use,result,pid=setup_pair()
    engine.apply(use,sequence=1)
    assert engine.history[-1].bindings['actor']['pokemon_instance_id']==pid
    assert 'GreatGeneral' in use['original_text']
    saved=load('reports/M2.2.3-battle-state.json')
    activation=deepcopy(next(r['event'] for r in saved['history'] if r['event']['event_type']=='item_activation'))
    for evidence in activation['evidence']: evidence['details']['turn']=1
    engine.apply(activation,sequence=2);engine.apply(result,sequence=3)
    assert engine.state.pokemon[pid].stages['attack'].changes[-1]['amount'] is None

def test_correction_replays_rule_and_duplicate_delivery():
    engine,use,result,pid=setup_pair();engine.apply(use,sequence=1);engine.apply(result,sequence=2)
    before=engine.to_dict();engine.apply(result,sequence=2);assert before==engine.to_dict()
    corrected=deepcopy(result);corrected['attributes']['stages']=1
    engine.correct(result['event_id'],corrected,sequence=2,reason='direct evidence')
    assert engine.state.pokemon[pid].stages['attack'].value.value==1
    engine.retract(result['event_id'],reason='invalid outcome');assert engine.state.pokemon[pid].stages['attack'].value.value==0

def test_failed_effect_message_prevents_rule():
    engine,use,result,pid=setup_pair();engine.apply(use,sequence=1)
    fail=deepcopy(result);fail.update(event_id='failure',event_type='move_effect');fail['attributes']={'effect_of':use['event_id'],'outcome':'blocked'}
    engine.apply(fail,sequence=2);engine.apply(result,sequence=3)
    assert engine.state.pokemon[pid].stages['attack'].changes[-1]['amount'] is None
    assert engine.state.conflicts[-1]['kind']=='result_after_failed_action'

def test_observed_stamina_coexists_with_registry():
    engine,use,result,pid=setup_pair();old=load('reports/M2.2.3-battle-state.json')
    activation=deepcopy(next(r['event'] for r in old['history'] if r['event']['event_type']=='ability_activation' and r['event']['canonical_references']['ability']['canonical_id']=='pokeapi:ability:192'))
    pid=activation['attributes']['actor_instance_id'];result=deepcopy(result);result['actor']=activation['actor'];result['side']=activation['side'];result['attributes'].update(actor_instance_id=pid,stats=['defense'])
    for evidence in result['evidence']: evidence['details']['turn']=2
    engine.apply(activation,sequence=1);engine.apply(result,sequence=2)
    assert engine.state.pokemon[pid].stages['defense'].value.value==1
    assert engine.state.pokemon[pid].ability.current.value['canonical_id']=='pokeapi:ability:192'
    assert engine.mechanic_registry.handlers

def test_ambiguous_result_does_not_assume_independent_boost():
    engine,use,result,pid=setup_pair();engine.apply(use,sequence=1);engine.apply(result,sequence=2)
    more=deepcopy(result);more['event_id']='ambiguous';engine.apply(more,sequence=3)
    stage=engine.state.pokemon[pid].stages['attack'];assert stage.value.value is None and stage.interval.value==[2,6]
    assert len(stage.changes)==1

def test_direct_result_replaces_conflicting_generated_delta():
    engine,use,result,pid=setup_pair();use['attributes'].update(effect_outcome='confirmed',interaction_checked=True)
    engine.apply(use,sequence=1);result['attributes'].update(effect_of=use['event_id'],stages=1)
    engine.apply(result,sequence=2)
    assert engine.state.pokemon[pid].stages['attack'].value.value==1
    assert engine.state.conflicts[-1]['kind']=='observed_rule_delta_conflict'

def test_configuration_exposed_to_decision_projection():
    old=load('reports/M2.2.3-battle-state.json');opening=load('data/teams/sample_battle_3_opening.json')
    pid='sample_battle_3:self:preview:3'
    state=initialize_team(from_dict(old['initial_state']),opening,bindings={'own_team_3':pid})
    engine=StateEngine(state);projection=engine.decision_state()
    assert projection['pokemon'][pid]['known_configuration']['fields']['speed']['value']==105
    assert state.pokemon[pid].moves.unrevealed_slots.value==0
    assert 'known_configuration' not in projection['pokemon']['sample_battle_3:opponent:preview:3']

def test_lowering_boundary():
    engine,use,result,pid=setup_pair(move=370)
    engine.initial.pokemon[pid].stages['defense'].value=Fact(-6,'observed')
    result['attributes'].update(stats=['defense'],direction='down')
    engine.apply(use,sequence=1);engine.apply(result,sequence=2)
    assert engine.state.pokemon[pid].stages['defense'].value.value==-6
