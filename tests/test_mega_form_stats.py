"""Champions form calculation from saved SP/alignment, separate from HP/stages."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from battle_events.parser import EventParser
from tracking.form_stats import calculate_member,form_evidence,update_stats
from tracking.knowledge_grounding import initialize_team,attach_matching_roster_profile
from tracking.battle_state import fact
from tracking.state_engine import StateEngine,event_from_dict
from tests.test_ditto_unnerve import initial,event,apply,activation,PROOF

TEAM=json.loads(Path('tests/fixtures/battle_evidence/sample-team7-reviewed.json').read_text())


@pytest.mark.parametrize('member',TEAM['members'],ids=lambda m:m['fields']['species']['value'])
def test_six_native_displayed_stats_match_saved_points(member):
    before=deepcopy(member)
    assert calculate_member(member)['stats']=={s:member['fields'][s]['value'] for s in ['hp','attack','defense','special_attack','special_defense','speed']}
    assert member==before


def prepare():
    parser=EventParser();s=initial(parser)
    s=initialize_team(s,TEAM,bindings={'own_team_4':'garchomp'})
    g=s.pokemon['garchomp'];g.current_variant=fact('pokeapi:pokemon:445',PROOF)
    g.hp.current=fact(132,PROOF);g.hp.maximum=fact(184,PROOF)
    update_stats(s,g,event_from_dict(event(parser,0,'send_out','garchomp')))
    return parser,StateEngine(s)


def reaction(parser,stone):
    e=event(parser,1,'move_effect','garchomp',attrs=dict(effect='mega_stone_reaction_notice'))
    text='烈咬陆鲨的'+stone+'和Hoshi的全一环起了反应！'
    e['original_text']=text;e['evidence'][0]['details']['row_evidence']=[dict(text=text)]
    return e


@pytest.mark.parametrize('stone,variant,attack,spattack,speed',[
    ('烈咬陆鲨进化石','pokeapi:pokemon:10058',171,189,144),
    ('烈咬陆鲨进化石Z','pokeapi:pokemon:10309',135,212,203)])
def test_mega_and_z_keep_hp_identity_item_stages_and_copy_current_values(stone,variant,attack,spattack,speed):
    parser,engine=prepare();g=engine.state.pokemon['garchomp']
    hp=deepcopy(g.hp);item=deepcopy(g.item);original=deepcopy(g.original_identity);stages=deepcopy(g.stages)
    apply(engine,reaction(parser,stone))
    e=event(parser,2,'transformation','garchomp',attrs=dict(mechanic='mega_evolution',identity=parser.identity('超级烈咬陆鲨','species')))
    r=apply(engine,e);assert r.application_status=='applied_confirmed'
    g=engine.state.pokemon['garchomp'];m=g.mechanics['battle_stats']
    assert g.current_variant.value==variant
    assert [m.current[s].value for s in ['attack','special_attack','speed']]==[attack,spattack,speed]
    assert g.hp==hp and g.item==item and g.original_identity==original and g.stages==stages
    original_calc=engine.state.knowledge['team']['instances']['garchomp']['original_form_calculation']
    assert original_calc['stats']['special_attack']==145
    own=deepcopy(engine.state.pokemon['ditto'].hp)
    apply(engine,activation(parser,3));d=engine.state.pokemon['ditto']
    snap=d.mechanics['temporary_transform'].current['snapshot'].value
    assert snap['non_hp_stats']['special_attack']['value']==spattack
    assert snap['form']['value']==variant and snap['form']['knowledge']=='derived'
    assert d.hp==own and d.species.value['species_id']==132
    assert d.stages['attack'].value.value==stages['attack'].value.value
    engine.retract('2',reason='withdraw evolution')
    assert engine.state.pokemon['garchomp'].mechanics['battle_stats'].current['special_attack'].value==145


def test_generic_garchomp_without_stone_never_becomes_ordinary_mega_stats():
    parser,engine=prepare()
    e=event(parser,1,'transformation','garchomp',attrs=dict(mechanic='mega_evolution',identity=parser.identity('超级烈咬陆鲨','species')))
    apply(engine,e);g=engine.state.pokemon['garchomp']
    assert not g.current_variant.known and not g.mechanics['battle_stats'].current['attack'].known


def test_no_sp_reverse_fit_or_unknown_form_substitution():
    m=deepcopy(TEAM['members'][3]);m['fields']['allocation_attack_display']['value']=None
    with pytest.raises((ValueError,TypeError)):calculate_member(m)
    m=TEAM['members'][3]
    with pytest.raises(ValueError):calculate_member(m,'pokeapi:pokemon:999999')
    assert calculate_member(m,'pokeapi:pokemon:10309')['stats']['defense']==106
    assert calculate_member(m,'pokeapi:pokemon:10058')['stats']['defense']==136


def test_all_verified_form_bases_agree_with_pinned_knowledge():
    from knowledge.champions_stats import ChampionsStats
    for variant,evidence in form_evidence().items():
        assert ChampionsStats(variant).base_stats==evidence['base_stats']
        assert evidence['source']['revision_id'] and evidence['source']['retrieved_date']


def test_profile_linkage_does_not_guess_from_opponent_or_incomplete_self_roster(tmp_path):
    parser=EventParser();s=initial(parser)
    linked=attach_matching_roster_profile(s,[],root=tmp_path)
    assert linked.knowledge['team_profile_linkage']['status']=='unbound'
