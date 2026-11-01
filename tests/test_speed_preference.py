"""User preference is cumulative, generic and distinct from an item fact."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from battle_evidence.configuration_domain import initial_domain
from battle_evidence.speed_preference import SavedSpeedInference, current_stat


def fixture(sid=248,ability='Sand Stream',item=None,**rules):
    native=f'pokeapi:species:{sid}';domain=initial_domain(native)
    own='test:self:comparator';subject='test:opponent:subject'
    def f(v):return dict(value=v,knowledge='observed')
    def mon(species,ab,side,speed,held):
        return dict(side=side,species=f(dict(species_id=species)),variant=f(f'pokeapi:pokemon:{species}'),
            ability=dict(identity=f(ab)),item=dict(identity=f(held)),stages=dict(speed=dict(value=f(0))),
            status=f('none'),mechanics=dict(battle_stats=dict(current=dict(speed=f(speed)))))
    context=dict(pokemon={own:mon(279,'Drizzle','self',100,'none'),subject:mon(sid,ability,'opponent',None,item)},
        field=dict(weather=dict(kind=f('none')),terrain=dict(kind=f('none')),trick_room=dict(active=f(False))),
        sides={s:dict(conditions=dict(tailwind=dict(active=f(False)))) for s in ['self','opponent']})
    ledger=SavedSpeedInference(native=native,stat_constraints={},battle_id='test',**rules)
    def add(speed,subject_first=False):
        c=deepcopy(context);c['pokemon'][own]['mechanics']['battle_stats']['current']['speed']=f(speed)
        n=len(ledger.orders)
        def rec(pid,index):return dict(event=dict(event_id=f'{n}:{index}',canonical_references=dict(move=dict(canonical_id='pokeapi:move:182'))),
            bindings=dict(actor=dict(pokemon_instance_id=pid)))
        first,second=rec(own,0),rec(subject,1)
        if subject_first:first,second=second,first
        return ledger.add(first,second,c,subject=subject,proof=dict(status='certified_local_membership',
            action_event_ids=[first['event']['event_id'],second['event']['event_id']],command_source=f'command:{n}'))
    return native,domain,context,ledger,add


@pytest.mark.parametrize('sid,ability',[(248,'Sand Stream'),(6,'Blaze'),(279,'Drizzle')])
def test_non_ball_explanation_wins_generically(sid,ability):
    _,domain,ctx,ledger,add=fixture(sid,ability)
    before=deepcopy(ctx);minimum=domain['stats']['speed']['minimum']
    r=add(minimum)
    assert r['status']=='exact' and r['feasible']['values']==[minimum]
    assert r['policy']['non_iron_ball_feasible'] is True
    assert r['policy']['iron_ball_fallback_necessary'] is False
    assert all(b['item']!='Iron Ball' for b in r['configuration_branches'])
    assert ctx==before and ledger.args['stat_constraints']=={}


@pytest.mark.parametrize('sid,ability',[(248,'Sand Stream'),(6,'Blaze')])
def test_fallback_only_when_needed_and_zero_sp(sid,ability):
    native,domain,_,_,add=fixture(sid,ability)
    r=add(domain['stats']['speed']['minimum']-1)
    assert r['status']=='exact'
    assert r['policy']['non_iron_ball_feasible'] is False
    assert r['policy']['iron_ball_fallback_necessary'] is True
    assert {b['item'] for b in r['configuration_branches']}=={'Iron Ball'}
    assert {b['speed_sp'] for b in r['configuration_branches']}=={0}
    expected={current_stat(native,f,0) for f in ('0.9','1.0','1.1')}
    assert set(r['feasible']['values'])==expected
    assert r['joint_domain']['stat_points']['speed']['values']==[0]


def test_observed_iron_ball_is_a_fact_not_speculative_sp_preference():
    _,domain,_,_,add=fixture(item='Iron Ball')
    r=add(domain['stats']['speed']['minimum'])
    assert r['status']=='exact' and r['feasible']==domain['stats']['speed']
    assert r['policy']['explicit_iron_ball'] and not r['policy']['iron_ball_fallback_necessary']
    assert any(b['speed_sp']>0 for b in r['configuration_branches'])


def test_later_observed_iron_ball_replaces_preference_without_overriding_facts():
    _,domain,ctx,_,add=fixture()
    first=add(domain['stats']['speed']['minimum'])
    ctx['pokemon']['test:opponent:subject']['item']['identity']=dict(value='Iron Ball',knowledge='observed')
    later=add(domain['stats']['speed']['minimum'])
    assert later['status']=='exact' and later['policy']['explicit_iron_ball']
    assert later['feasible']==domain['stats']['speed']
    assert len(first['feasible']['values'])==1


def test_observed_non_ball_item_cannot_be_replaced_by_fallback():
    _,domain,_,_,add=fixture(item='none')
    r=add(domain['stats']['speed']['minimum']-1)
    assert r['status']=='contradiction'
    assert not r['policy']['iron_ball_fallback_necessary']
    assert not r['policy']['speculative_iron_ball_eligible']


def test_accumulation_can_reopen_previously_disfavored_intrinsic_speeds():
    native,domain,_,ledger,add=fixture()
    first=add(domain['stats']['speed']['minimum'])
    assert len(first['feasible']['values'])==1
    # A later, stricter bound requires the fallback. Recompute from the hard
    # domain rather than intersecting the earlier preferred singleton.
    upper=current_stat(native,'1.1',0)//2
    second=add(upper)
    assert second['policy']['iron_ball_fallback_necessary']
    assert len(second['feasible']['values'])>1
    third=add(current_stat(native,'1.0',0)//2,subject_first=True)
    assert third['status']=='exact' and third['policy']['iron_ball_fallback_necessary']
    assert all(b['item']=='Iron Ball' and b['speed_sp']==0 for b in third['configuration_branches'])
    assert len(third['source_constraints'])==3
    assert len(ledger.results)==3 and ledger.results[0]==first
    assert current_stat(native,'0.9',0) not in third['feasible']['values']


def test_contradictory_accumulated_bounds_do_not_reselect_items_per_pair():
    _,domain,_,_,add=fixture()
    add(domain['stats']['speed']['minimum']-1)
    r=add(domain['stats']['speed']['maximum']+1,subject_first=True)
    assert r['status']=='contradiction' and r['feasible']['values']==[]
    assert len(r['source_constraints'])==2


def test_fallback_preserves_shared_alignment_and_budget():
    native,domain,_,ledger,add=fixture()
    ledger.args['stat_constraints']={'attack':dict(values=[domain['stats']['attack']['maximum']])}
    r=add(domain['stats']['speed']['minimum']-1)
    assert r['status']=='exact'
    assert '1.1' not in r['joint_domain']['alignment_modifiers']['speed']
    for b in r['joint_domain']['configurations']['branches']:
        assert sum(min(p['training_points'] for p in rows) for rows in b['stat_point_domains'].values())<=66


def test_excluded_item_and_team_unique_ownership_prevent_illegal_fallback():
    _,domain,_,_,add=fixture(excluded_items=['Iron Ball'])
    assert add(domain['stats']['speed']['minimum']-1)['status']=='contradiction'
    domains={'test:opponent:subject':{'none','Iron Ball'},'test:opponent:teammate':{'Iron Ball'}}
    _,domain,_,_,add=fixture(team_item_domains=domains,team_member='test:opponent:subject',item_clause_enabled=True)
    assert add(domain['stats']['speed']['minimum']-1)['status']=='contradiction'


def test_unresolved_modifiers_do_not_trigger_an_iron_ball_fallback():
    _,domain,ctx,_,add=fixture()
    ctx['field']['trick_room']['active']=dict(value=None,knowledge='unknown')
    r=add(domain['stats']['speed']['minimum']-1)
    assert r['status']=='unresolved' and r['policy']['non_iron_ball_feasible'] is None
    assert not r['policy']['iron_ball_fallback_necessary']


def test_saved_b24_spirit_break_curse_prefers_speed_72_without_changing_evidence():
    f=json.loads((Path(__file__).parent/'fixtures/inference_integration/b24-speed-preference-v1.json').read_text())
    original=deepcopy(f)
    ledger=SavedSpeedInference(native=f['native'],stat_constraints={},battle_id=f['battle_id'])
    r=ledger.add(f['first'],f['second'],f['context'],subject=f['subject'],proof=f['proof'])
    assert r['status']=='exact' and r['feasible']['values']==[72]
    assert r['policy']['non_iron_ball_feasible'] and not r['policy']['iron_ball_fallback_necessary']
    assert r['joint_domain']['alignment_modifiers']['speed']==['0.9']
    assert r['joint_domain']['stat_points']['speed']['values']==[0]
    assert r['source_constraints'][0]['event_ids']==['event:b04c832694bde680a01262e4','event:5785e44cdf6b514c0d4a86d5']
    assert f==original


def test_trace_interface_and_joint_projection_use_the_same_accumulated_policy(monkeypatch):
    from battle_evidence.constraint_trace import ChronologicalTrace
    from battle_evidence.configuration_domain import DEFAULT_RULE
    from scripts.evaluate_b24 import joint_projection
    import battle_evidence.turns as turns
    f=json.loads((Path(__file__).parent/'fixtures/inference_integration/b24-speed-preference-v1.json').read_text())
    roster=[dict(preview_row=i+1,species_id=sid) for i,sid in enumerate([248,697,323,812,208,765])]
    records=[dict(deepcopy(f[k]),application_status='applied_partial',reason='move_revelation_only') for k in ['first','second']]
    for record in records:record['event']['event_type']='move_execution'
    state=dict(pokemon={f['subject']:dict(side_id='opponent',species=f['context']['pokemon'][f['subject']]['species'])})
    trace=ChronologicalTrace(f['battle_id'],roster,records,state,integrate=True,
        persistent_aliases=f['context']['source_instance_aliases'],configuration_rule=DEFAULT_RULE)
    # Certification itself is covered with complete four-opportunity fixtures;
    # this test supplies the saved certificate to exercise the downstream link.
    monkeypatch.setattr(turns,'certify_saved_cycle',lambda *a:deepcopy(f['proof']))
    trace.speed_pairs(records,{f['first']['event']['event_id']:f['context'],f['second']['event']['event_id']:f['context']},
        [dict(start=897.0016666666667,end=954.5266666666666,source_id=f['proof']['command_source'])])
    line=next(iter(trace.lineages.values()))
    assert line['stats']['speed']['values']==[72]
    hard=deepcopy(line['speed_hard_stats'])
    joint_projection(trace,954.5266666666666,records[-1])
    assert line['joint_default_configuration']['stats']['speed']['values']==[72]
    assert line['speed_hard_stats']==hard
    assert len(hard['speed']['values'])>1
