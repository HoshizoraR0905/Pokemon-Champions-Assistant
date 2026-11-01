"""User configuration assumptions do not replace Champions mechanical rules."""
from battle_evidence.configuration_domain import DEFAULT_RULE,initial_domain,project_domain,point_domain
from knowledge.champions_stats import ChampionsStats,STATS


def test_default_domain_exact_integer_rule_for_all_non_hp_stats():
    identity='pokeapi:species:132';model=ChampionsStats(identity,form='base')
    result=initial_domain(identity)
    assert result['status']=='exact' and not result['fallback_used']
    for stat in STATS:
        if stat=='hp':continue
        expected=set()
        for factor in ['0.9','1.0','1.1']:
            expected.update(r['actual_stat'] for r in model.attainable(stat,adjustments=[factor],point_domain=point_domain(factor,DEFAULT_RULE))['configurations'])
        assert set(result['stats'][stat]['values'])==expected
    assert point_domain('0.9',DEFAULT_RULE)==[0]


def test_global_alignment_and_budget_are_shared():
    identity='pokeapi:species:132';initial=initial_domain(identity)
    maximum={s:{'values':[initial['stats'][s]['maximum']]} for s in ['attack','special_attack']}
    assert project_domain(identity,maximum)['status']=='contradiction'  # two simultaneous raised alignments
    # Raised Attack SP32 plus HP SP32 and neutral Defense SP3 exceeds66.
    model=ChampionsStats(identity,form='base')
    neutral={s:model.attainable(s,adjustments=['1.0'],point_domain=[32 if s in ['hp','attack'] else 3])['configurations'][0]['actual_stat'] for s in ['hp','attack','defense']}
    neutral['attack']=initial['stats']['attack']['maximum']
    result=project_domain(identity,{s:{'values':[v]} for s,v in neutral.items()})
    assert result['status']=='contradiction'


def test_no_silent_mechanically_unrestricted_fallback():
    initial=initial_domain('pokeapi:species:132')
    result=project_domain('pokeapi:species:132',{'speed':{'values':[999]}})
    assert result['status']=='contradiction' and result['fallback_used'] is False
    assert initial['rule']==DEFAULT_RULE


def test_native_current_mapping_keeps_the_same_default_sp_rule():
    from battle_evidence.inference_integration import stat_pairs
    expected=set(initial_domain('pokeapi:species:132')['stats']['speed']['values'])
    pairs=stat_pairs('pokeapi:species:132','pokeapi:species:132','speed',DEFAULT_RULE)
    assert {a for a,b in pairs}==expected and all(a==b for a,b in pairs)


def test_sand_stream_deduction_is_opt_in_derived_and_retractable():
    from tests.test_inference_integration import engine,parsed
    from tracking.battle_state import fact
    from battle_events.parser import EventParser
    e=engine();p=next(iter(e.state.pokemon.values()))
    # Stable opt-in initial metadata survives retraction/replay.
    e.initial.knowledge['ability_field_reference']={'pokeapi:ability:45':{'weather':'sandstorm','sources':['synthetic Champions-specific rule evidence']}}
    e.initial.weather.kind=fact('rain',{});e.initial.weather.active=fact(True,{})
    activation=parsed('大嘴鸥的扬沙',2);activation.event_type='ability_activation';activation.side='self';activation.uncertainty=[]
    activation.attributes.update(actor_instance_id=p.pokemon_instance_id)
    activation.canonical_references={'ability':EventParser().identity('扬沙','ability')}
    e.apply(activation,sequence=2)
    assert e.state.weather.kind.value=='sandstorm' and e.state.weather.kind.knowledge=='derived'
    assert e.history[-1].bindings['derived_field_transition']['source_event_id']==activation.event_id
    e.retract(activation.event_id,reason='synthetic correction')
    assert e.state.weather.kind.value=='none'  # reviewed opening re-establishes neutral
