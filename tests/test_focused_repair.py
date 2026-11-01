"""Focused unique-member, endpoint and direct-hit regressions; no recognition."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import subprocess

import pytest

from battle_events.parser import EventParser
from tracking.battle_state import BattleState,PokemonState,fact
from tracking.state_engine import StateEngine,EventRecord,event_from_dict
from tracking.active_continuity import enter
from tracking.resolution_endpoints import full_hp_baseline
from damage import calculate
from damage.inverse import infer_attack_stat
from tests.test_inverse_damage import BASE,observation


def event(n,kind,identity,*,pid=None,slot=None):
    return dict(event_id=str(n),event_type=kind,side='opponent',actor=identity,target=None,
        original_text='synthetic explicit identity event',canonical_references={},log_order=None,
        evidence=[dict(source_type='synthetic',source_id=str(n),observation_ids=[str(n)],details={})],
        ocr_confidence=None,parsing_confidence='supported',uncertainty=[],status='confirmed',
        attributes=dict(observation_time=n,**({'actor_instance_id':pid} if pid else {}),**({'slot':slot} if slot else {})))


@pytest.mark.parametrize('unreadable_sightings',[False,True])
@pytest.mark.parametrize('first,returned,sid',[
    ('炽焰咆哮虎','炽焰咆哮虎',727),('雷丘','雷丘（阿罗拉的样子）',26),('爱管侍（雄性的样子）','爱管侍（雌性的样子）',876)])
def test_unique_species_identity_preserves_hp_build_moves_and_separate_episodes(first,returned,sid,unreadable_sightings):
    parser=EventParser();identity=parser.identity(first,'species');other=parser.identity(returned,'species')
    assert identity and other and identity['species_id']==other['species_id']==sid
    p=PokemonState('persistent','opponent');p.species=fact(identity,{});p.original_identity=fact(identity,{})
    p.location=fact(dict(kind='active',slot='left'),{});p.hp.current=fact(37,{});p.hp.maximum=fact(194,{})
    p.item.identity=fact(parser.identity('文柚果','item'),{});p.item.status=fact('consumed',{})
    p.moves.executed=[dict(event_id='revealed',move=parser.identity('守住','move'))]
    p.stages['attack'].value=fact(2,{})
    state=BattleState('synthetic',knowledge=dict(active_continuity_v1=True))
    state.pokemon[p.pokemon_instance_id]=p;side=state.sides['opponent'];side.party_instance_ids=[p.pokemon_instance_id];side.active_slots={'left':p.pokemon_instance_id}
    state.knowledge['identity_ledger']=dict(roster=[dict(battle_id='synthetic',side='opponent',preview_row=i,species_id=s,status='resolved',evidence={'source':'synthetic roster'})
        for i,s in enumerate([sid,3,6,279,445,1018],1)])
    if unreadable_sightings:
        state.knowledge['identity_ledger']['roster'] += [dict(battle_id='synthetic',side='opponent',preview_row=i,status='unresolved',species_id=None,evidence={'source':'later unreadable preview'}) for i in range(1,7)]
    opening=event(1,'send_out',identity,pid=p.pokemon_instance_id,slot='left')
    enter(state,p,event_from_dict(opening),EventRecord(opening,0,None),slot='left')
    engine=StateEngine(state)
    engine.apply(event(2,'switch_out',identity,pid=p.pokemon_instance_id),sequence=2)
    r=engine.apply(event(3,'send_out',other,slot='left'),sequence=3)
    assert r.bindings['actor']['pokemon_instance_id']=='persistent'
    member=engine.state.pokemon['persistent']
    assert len(engine.state.pokemon)==1 and member.hp.current.value==37
    assert member.item.status.value=='consumed' and len(member.moves.executed)==1
    assert member.stages['attack'].value.value==0
    episodes=engine.state.knowledge['active_entry_episodes']
    assert len(episodes)==2 and episodes[0]['episode_id']!=episodes[1]['episode_id']
    assert episodes[1]['instance_id']==episodes[0]['instance_id']


def test_ditto_reentry_is_native_until_a_new_explicit_transform_event():
    from tests.test_ditto_unnerve import initial,activation,event as make,apply
    from tracking.transformation import current
    parser=EventParser();engine=StateEngine(initial(parser));apply(engine,activation(parser,1))
    assert current(engine.state.pokemon['ditto'])
    hp=deepcopy(engine.state.pokemon['ditto'].hp)
    apply(engine,make(parser,2,'switch_out'))
    returned=make(parser,3,'send_out',attrs=dict(slot='left'));returned['attributes'].pop('actor_instance_id')
    apply(engine,returned);p=engine.state.pokemon['ditto']
    assert current(p) is None and p.species.value['species_id']==132
    assert p.hp==hp and len(p.transformations)==1
    assert p.ability.current.value['canonical_id']==parser.identity('变身者','ability')['canonical_id']


def test_full_hp_unknown_maximum_is_percentage_not_invented_absolute():
    p=full_hp_baseline(displayed_percent=100,proof={'confirmed_by':'synthetic user'})
    assert p['unit']=='displayed_percent' and p['maximum'] is None and p['value']==100
    absolute=full_hp_baseline(maximum=194,proof={'confirmed_by':'synthetic verified build'})
    assert absolute['unit']=='absolute' and absolute['value']==194 and absolute['knowledge']=='derived'


@pytest.mark.parametrize('battle,before,after',[(20,194,152),(21,194,168),(22,194,178),(23,181,97)])
def test_real_saved_endpoints_repaired_without_changing_receipts(battle,before,after):
    from tracking.resolution_endpoints import repair_saved_endpoints
    f=json.loads(Path('tests/fixtures/focused_repair/endpoints.json').read_text())
    c=next(c for c in f['cases'] if c['battle']==battle);original=deepcopy(c)
    out,audits=repair_saved_endpoints(c['projection'],c['records'],c['contexts'],{})
    assert c==original and len(audits)==1
    ep=out['episodes'][0];assert (ep['before'],ep['after'],ep['delta'])==(before,after,after-before)
    assert ep['attribution_status']=='supported'
    if battle!=23:assert audits[0]['provenance']['not_a_hud_observation'] is True
    else:assert audits[0]['provenance']['plateau_end']<audits[0]['provenance']['burn_time']


def test_initial_baseline_not_reused_after_damage_or_reentry():
    from tracking.resolution_endpoints import repair_saved_endpoints
    c=json.loads(Path('tests/fixtures/focused_repair/endpoints.json').read_text())['cases'][0]
    entry=next(r for r in c['records'] if r['event']['event_type']=='send_out')
    repeated=deepcopy(entry);repeated['event']['event_id']='return';repeated['event']['attributes']['observation_time']+=1
    c['records'].append(repeated)
    out,audits=repair_saved_endpoints(c['projection'],c['records'],c['contexts'],{})
    assert not audits and out['episodes'][0]['before'] is None


def test_initial_state_hp_is_derived_not_a_synthetic_hud_and_never_heals_a_return():
    from tracking.initial_conditions import initialize_full_hp
    parser=EventParser();p=PokemonState('arch','self');p.original_identity=fact(parser.identity('铝钢桥龙','species'),{})
    state=BattleState('b')
    state.knowledge['initial_full_hp_rule']=dict(verified=True,species_ids=[1018],confirmed_by='synthetic user')
    state.knowledge['team']={'instances':{'arch':{'fields':{'hp':{'value':194}}}}}
    state.pokemon['arch']=p;e=event_from_dict(event(1,'send_out',p.original_identity.value,slot='left'))
    initialize_full_hp(state,p,e,fresh=True)
    assert p.hp.current.value==194 and p.hp.current.knowledge=='derived' and not p.hp.observations
    p.hp.current=fact(152,{})
    initialize_full_hp(state,p,e,fresh=False)
    assert p.hp.current.value==152


def test_real_dual_wingbeat_two_hits_with_shared_build_and_critical_patterns():
    from battle_evidence.inference_integration import invert_saved_hit
    f=json.loads(Path('tests/fixtures/focused_repair/dual-wingbeat.json').read_text())
    result=invert_saved_hit(f['episode'],f['context'],native=f['native'],retained=f['initial']['values'],stat='attack',battle_id='sample_battle_22')
    assert result['status']=='exact' and result['observation_count']==2
    assert result['worked_example']['per_hit_damage']==[21,24]
    assert result['worked_example']['aggregate_is_not_an_additional_observation']
    patterns={tuple(s['assignment']['critical_hits']) for s in result['branches'][0]['scenarios']}
    assert patterns=={(False,False),(False,True),(True,False),(True,True)}


@pytest.mark.parametrize('move', ['Wood Hammer','Grassy Glide','Shadow Sneak','Dual Wingbeat','Zap Cannon','Darkest Lariat'])
@pytest.mark.parametrize('critical',[False,True])
def test_new_direct_hit_integer_rolls_match_pinned_champions_oracle(tmp_path,move,critical):
    request=deepcopy(BASE);request['move']=move;request['field']['critical']=critical
    request['defender']['stages']['defense']=2
    if move=='Grassy Glide':request['field'].update(terrain='grassy',attacker_grounded=False,defender_grounded=True)
    if move=='Dual Wingbeat':request['hit_index']=1
    if not Path('.cache/m31/oracle/node_modules/@smogon/calc').is_dir():pytest.skip('optional pinned oracle absent')
    p=tmp_path/'input.json';p.write_text(json.dumps(dict(cases=[dict(id='scoped',input=request)])))
    expected=json.loads(subprocess.check_output(['node','scripts/damage_focused_oracle.cjs',str(p)]))
    result=calculate(request)
    assert result['status']=='exact_reference'
    assert result['distribution']['rolls']==expected['cases'][0]['rolls']
    assert request['defender']['stages']['defense']==2  # no secondary state mutation


def test_dual_wingbeat_inverse_shares_attack_and_does_not_add_aggregate():
    hits=[]
    for i in [1,2]:
        request=deepcopy(BASE);request['move']='Dual Wingbeat';request['hit_index']=i
        request['attacker']['stats']['attack']=130
        amount=calculate(request)['distribution']['rolls'][i-1]
        hits.append(observation('hit'+str(i),request,amount))
    result=infer_attack_stat(observations=hits,candidate_stats=list(range(80,151)),ruleset=BASE['profile'])
    assert result['status']=='exact' and 130 in result['feasible']['values']
    assert len(result['per_observation'])==2
    assert set(result['feasible']['values'])==set.intersection(*(set(s['feasible']['values']) for s in result['scenarios'][0]['per_observation']))
    assert calculate(dict(BASE,move='Dual Wingbeat'))['status']=='unsupported'


def test_original_item_uniqueness_is_per_persistent_member():
    from battle_evidence.team_items import six_member_exclusions
    members=[f'b:opponent:preview:{i}' for i in range(1,7)]
    claim=dict(owner=members[0],item='Sitrus Berry',sources=['synthetic'],original_equipped_verified=True,kind='initial_held')
    assert not six_member_exclusions(members,[claim,claim],battle_id='b',rule_verified=True)['contradictions']
    duplicate=dict(claim,owner=members[1])
    assert six_member_exclusions(members,[claim,duplicate],battle_id='b',rule_verified=True)['contradictions']


@pytest.mark.parametrize('ability,move',[
    ('Grassy Surge','Wood Hammer'),('Electric Surge','Zap Cannon'),
    ('Surge Surfer','Zap Cannon'),('Corrosion','Power Gem'),
    ('Toxic Debris','Power Gem'),('Clear Body','Shadow Sneak'),
    ('Rock Head','Wood Hammer'),('Reckless','Wood Hammer'),
    ('Flash Fire','Shadow Sneak'),('Weak Armor','Shadow Sneak')])
def test_scoped_ability_direct_damage_matches_oracle(tmp_path,ability,move):
    request=deepcopy(BASE);request['move']=move;request['attacker']['ability']=ability
    original=deepcopy(request)
    if not Path('.cache/m31/oracle/node_modules/@smogon/calc').is_dir():pytest.skip('optional pinned oracle absent')
    p=tmp_path/'input.json';p.write_text(json.dumps(dict(cases=[dict(id='ability',input=request)])))
    expected=json.loads(subprocess.check_output(['node','scripts/damage_focused_oracle.cjs',str(p)]))
    result=calculate(request)
    assert result['status']=='exact_reference'
    assert result['distribution']['rolls']==expected['cases'][0]['rolls']
    assert request==original


def test_shared_item_join_cannot_change_item_witness_between_returns():
    from battle_evidence.constraint_trace import ChronologicalTrace
    from knowledge.stat_feasibility import summary
    trace=ChronologicalTrace.__new__(ChronologicalTrace);line={'item_stat_support':{}}
    first={'Choice Band':summary({100,101}),'none':summary({110,111})}
    second={'Choice Band':summary({110,111}),'none':summary({100,101})}
    assert trace.joined_item_stats(line,'attack',first)['count']==4
    assert trace.joined_item_stats(line,'attack',second)['count']==0
    line['item_stat_support']={}  # accepted item lifecycle starts another epoch
    assert trace.joined_item_stats(line,'attack',second)['count']==4


def test_identity_repair_cannot_admit_frozen_deferred_hud(monkeypatch):
    import scripts.trace_hidden_constraints as runner
    monkeypatch.setattr(runner,'FOCUSED',True)
    monkeypatch.setattr(runner,'context_fingerprint',lambda p:'synthetic')
    payload={'history':[{'event':{'event_id':'accepted'}},{'event':{'event_id':'deferred'}}]}
    original=deepcopy(payload)
    manifest={'stages':{'contexts:synthetic':{'receipt_status_mismatches':[
        {'event_id':'deferred','source_status':'deferred','replay_status':'recorded_observation'},
        {'event_id':'accepted','source_status':'applied_confirmed','replay_status':'applied_partial'}]}}}
    out=runner.freeze_promoted_inputs(payload,manifest)
    assert payload==original
    assert [r['event']['event_id'] for r in out['history']]==['accepted']
    assert out['diagnostic_source_admission_guard']['excluded'][0]['event_id']=='deferred'


def test_first_ditto_entry_stays_ditto_until_explicit_imposter():
    from tests.test_ditto_unnerve import initial,activation,event as make,apply
    from tracking.transformation import current
    parser=EventParser();state=initial(parser)
    del state.pokemon['ditto'];state.sides['opponent'].party_instance_ids.remove('ditto')
    del state.sides['opponent'].active_slots['left'];state.knowledge['active_entry_episodes']=[]
    engine=StateEngine(state)
    entry=make(parser,1,'send_out',attrs={'slot':'left'});entry['attributes'].pop('actor_instance_id')
    receipt=apply(engine,entry);pid=receipt.bindings['actor']['pokemon_instance_id']
    p=engine.state.pokemon[pid]
    assert p.species.value['species_id']==132 and current(p) is None and not p.transformations
    explicit=activation(parser,2);explicit['attributes']['actor_instance_id']=pid
    receipt=apply(engine,explicit)
    assert receipt.bindings['transformation']['target_instance_id']=='garchomp'
    assert current(engine.state.pokemon[pid]) is not None
