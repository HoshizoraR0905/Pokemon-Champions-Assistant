"""Independent rolls, compact joint budgets and received-HP inference contracts."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from damage import calculate
from damage.joint import filter_joint, allocation_count, restrict_budget, legal_damage_items
from damage.selectors import select_stats
from knowledge.champions_stats import STATS, ChampionsStats
from speed_order import configuration_domain

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=json.loads((ROOT/'tests/fixtures/damage/m342-rolls.json').read_text())


@pytest.mark.parametrize('row',FIXTURE['cases'],ids=lambda r:r['id'])
def test_pinned_champions_full_rolls_with_stat_selectors(row):
    result=calculate(row['input'])
    assert result['status']=='exact_reference',result
    assert result['distribution']['rolls']==row['rolls']


@pytest.mark.parametrize('move,category,owner,offense,defense',[
    ('Dragon Claw','Physical','attacker','attack','defense'),
    ('Flamethrower','Special','attacker','special_attack','special_defense'),
    ('Body Press','Physical','attacker','defense','defense'),
    ('Psyshock','Special','attacker','special_attack','defense'),
    ('Psystrike','Special','attacker','special_attack','defense'),
    ('Foul Play','Physical','defender','attack','defense')])
def test_explicit_stat_ownership(move,category,owner,offense,defense):
    s=select_stats(move,category)
    assert (s['offensive_owner'],s['offensive_stat'],s['defensive_stat'])==(owner,offense,defense)


def test_psystrike_selector_does_not_invent_champions_availability():
    r=request('Psystrike');z=calculate(r)
    assert z['status']=='unsupported' and z['distribution'] is None
    c=config();o=observation(c);o['input']['move']='Psystrike'
    result=filter_joint([c],[o]);assert result['configurations']==[c]
    assert result['status']=='partial_reference' and result['updates'][0]['selector'] is None


def request(move='Dragon Claw'):
    r=deepcopy(FIXTURE['cases'][0]['input']);r['move']=move
    for side in ('attacker','defender'):
        r[side].update(current_hp=500,maximum_hp=500)
        r[side]['stages']=dict.fromkeys(r[side]['stages'],0)
    r['attacker'].update(identity='Garchomp',form='base',ability='Rough Skin',item='none')
    r['field'].update(critical=False,format='doubles',reflect=False,light_screen=False)
    return r


def config(key='joint',item='none',ability='Rough Skin',**points):
    values=dict.fromkeys(STATS,0);values.update(points)
    return dict(id=key,form='pokeapi:species:445',item=item,ability=ability,
                training=dict(alignment=dict(increase=None,decrease=None),point_domains={s:[v] for s,v in values.items()}))


def observation(c,move='Dragon Claw',key='hit',time=1):
    r=request(move);stats=ChampionsStats(c['form'],form='base').calculate({s:v[0] for s,v in c['training']['point_domains'].items()},c['training']['alignment'])['stats']
    r['attacker']['stats']={s:v for s,v in stats.items() if s!='hp'};r['attacker']['item']=c['item'];r['attacker']['ability']=c['ability']
    result=calculate(r);assert result['status']=='exact_reference',result
    return dict(id=key,timestamp=time,admitted=True,target_side='self',target='own',source_event_id=key,
                damage=result['distribution']['rolls'][-1],input=r)


def test_type_items_legal_and_no_older_choice_item_branches():
    assert {'Charcoal','Magnet','Mystic Water','Life Orb'}<=set(legal_damage_items())
    assert not {'Choice Band','Choice Specs'}&set(legal_damage_items())
    with pytest.raises(ValueError,match='nonlegal'):filter_joint([config(item='Choice Band')],[])


def test_audited_flinch_item_is_connected_hit_neutral_not_absent():
    assert 'King’s Rock' in legal_damage_items()
    c=config(item='King’s Rock');o=observation(config())
    result=filter_joint([c],[o])
    assert result['configurations'] and result['status']=='conditional_reference'
    assert result['configurations'][0]['item']=='King’s Rock'


def test_damage_retains_same_speed_row_and_full_budget():
    c=config(speed=32);c['training']['point_domains']['attack']=list(range(33))
    c['training']['point_domains']['hp']=[32]
    assert restrict_budget(c['training'])
    assert c['training']['point_domains']['attack']==[0,1,2]
    o=observation(config(speed=32,hp=32,attack=2))
    result=filter_joint([c],[o]);assert result['configurations']
    kept=result['configurations'][0]
    assert kept['id']=='joint' and kept['training']['point_domains']['speed']==[32]
    assert max(kept['training']['point_domains']['attack'])<=2
    assert result['updates'][0]['after']['speed']['values']==[154]
    assert not result['certified_champions_eliminations']


def test_budget_count_retains_joint_constraint_instead_of_cartesian_marginals():
    t=config(speed=32)['training'];t['point_domains']['hp']=[31,32];t['point_domains']['attack']=[1,2,3]
    assert allocation_count(t)==5
    bad=config(speed=32,hp=32,attack=3)
    with pytest.raises(ValueError,match='feasible'):filter_joint([bad],[])


def test_multi_event_intersection_and_no_independent_build_substitution():
    a=config('a',attack=0,special_attack=32);b=config('b',attack=32,special_attack=0)
    physical=observation(b);special=observation(a,'Flamethrower',key='special',time=2)
    assert filter_joint([a,b],[physical])['configurations']
    assert filter_joint([a,b],[special])['configurations']
    assert filter_joint([a,b],[physical,special])['configurations']==[]


def test_special_damage_filters_special_attack_with_shared_speed_budget():
    c=config(speed=32,hp=32)
    c['training']['point_domains']['special_attack']=list(range(33))
    hit=observation(config(speed=32,hp=32,special_attack=2),'Flamethrower')
    result=filter_joint([c],[hit])
    assert result['configurations']
    kept=result['configurations'][0]
    assert kept['id']==c['id']
    assert max(kept['training']['point_domains']['special_attack'])<=2
    assert result['updates'][0]['selector']['offensive_stat']=='special_attack'


def test_offensive_projection_keeps_both_stats_and_their_own_evidence():
    from battle_evidence.offensive import offensive_projections
    a=config('low',attack=0,special_attack=0)
    b=config('high',attack=32,special_attack=32)
    hit=observation(b,'Flamethrower',key='special')
    result=filter_joint([a,b],[hit])
    assert [c['id'] for c in result['configurations']]==['high']
    stats=offensive_projections(result['configurations'],result)
    assert set(stats)=={'attack','special_attack'}
    assert stats['special_attack']['direct_constraint']
    assert stats['special_attack']['evidence_ids']==['special']
    assert not stats['attack']['direct_constraint']
    assert stats['attack']['evidence_ids']==[]
    assert stats['attack']['ids']==stats['special_attack']['ids']==['high']
    physical=observation(b,key='physical',time=2)
    result=filter_joint([a,b],[hit,physical])
    stats=offensive_projections(result['configurations'],result)
    assert stats['attack']['evidence_ids']==['physical']
    assert stats['special_attack']['evidence_ids']==['special']


def test_foul_play_does_not_constrain_attacker_attack():
    a=config('a',attack=0);b=config('b',attack=32)
    result=filter_joint([a,b],[observation(a,'Foul Play')])
    assert [c['id'] for c in result['configurations']]==['a','b']
    assert result['updates'][0]['after'] is None


def test_body_press_filters_offensive_defense_not_attack():
    a=config('a',attack=32,defense=0);b=config('b',defense=32)
    result=filter_joint([a,b],[observation(b,'Body Press')])
    assert result['updates'][0]['selector']['offensive_stat']=='defense'
    assert [c['id'] for c in result['configurations']]==['b']


def test_unsupported_and_work_limit_retain_candidates_without_claimed_elimination():
    a=config();o=observation(a);o['input']['field']['other_effects']=['unknown_damage_effect']
    r=filter_joint([a],[o]);assert r['configurations']==[a] and r['status']=='partial_reference'
    r=filter_joint([a],[observation(a)],max_evaluations=0)
    assert r['configurations']==[a] and not r['requirements']['exhaustive']


def test_life_orb_requires_attack_bound_coverage_for_absence():
    orb=config('orb',item='Life Orb');plain=config('plain')
    o=observation(orb);o['damage']=next(iter(set(calculate(observation(plain)['input'])['distribution']['rolls'])&set(calculate(o['input'])['distribution']['rolls'])),o['damage'])
    # Even if damage itself distinguishes them, absent message coverage cannot.
    o['life_orb']=dict(observed=False,coverage_complete=False,sources=['partial'])
    first=filter_joint([orb,plain],[o]);assert first['requirements']['necessary_item'] is None
    assert any(c['item']=='Life Orb' for c in first['configurations'])
    absent=deepcopy(o);absent['life_orb'].update(coverage_complete=True,basis='reviewed_post_attack_hp_window',attack_event_id=o['source_event_id'],other_hp_changes_excluded=True,hp_before=100,hp_after=100,conditions=dict(ability_active=True,maximum_hp=160,successful_hit=True,item_active=True,forced_switch=False,after_move_hook_reached=True))
    assert all(c['item']!='Life Orb' for c in filter_joint([orb,plain],[absent])['configurations'])
    o['life_orb'].update(observed=True,basis='reviewed_item_message',attack_event_id=o['source_event_id'])
    r=filter_joint([orb,plain],[o]);assert all(c['item']=='Life Orb' for c in r['configurations'])
    o['life_orb']['attack_event_id']='different'
    with pytest.raises(ValueError,match='different attack'):filter_joint([orb],[o])


def test_censored_or_ambiguous_hp_cannot_eliminate_candidates():
    c=config();o=observation(c);o['damage']=o['input']['defender']['current_hp']
    assert filter_joint([c],[o])['configurations']==[c]
    o['target_side']='opponent'
    with pytest.raises(ValueError,match='own received'):filter_joint([c],[o])


def test_resist_berry_is_consumed_for_same_target_on_next_hit():
    c=config();o=observation(c,'Flamethrower');o['input']['defender'].update(identity='Venusaur',ability='none',item='Occa Berry')
    o['damage']=calculate(o['input'])['distribution']['rolls'][0]
    second=deepcopy(o);second.update(id='second',source_event_id='second',timestamp=2)
    without=deepcopy(second['input']);without['defender']['item']='none'
    second['damage']=calculate(without)['distribution']['rolls'][-1]
    result=filter_joint([c],[o,second]);assert result['configurations']
    assert result['consumed_items']['joint']['own']=='Occa Berry'


def test_necessary_modifier_is_only_conditional_on_exhaustive_supported_domain():
    orb=config('orb',item='Life Orb');plain=config('plain');o=observation(orb)
    partial=filter_joint([orb,plain],[o]);assert partial['requirements']['necessary_item'] is None
    exhaustive=filter_joint([orb,plain],[o],exhaustive_legal_alternatives=True)
    assert exhaustive['requirements']['necessary_item']=='Life Orb'
    assert exhaustive['requirements']['required_modifier_choices']==['Life Orb']
    assert exhaustive['requirements']['without_offensive_boost_possible'] is False


def test_empirical_move_templates_do_not_exclude_joint_training_cores():
    a=config('team-a:build-a');b=config('team-b:build-b')
    for c,moves in [(a,['pokeapi:move:337','pokeapi:move:53','pokeapi:move:182','pokeapi:move:414']),
                    (b,['pokeapi:move:89','pokeapi:move:53','pokeapi:move:182','pokeapi:move:414'])]:
        c['observed_build']=dict(complete=True,species=c['form'],ability=c['ability'],build_id=c['id'],configuration=dict(moves=moves))
    saved=deepcopy(a['observed_build']);result=filter_joint([a,b],[observation(a)])
    assert [c['id'] for c in result['configurations']]==['team-a:build-a','team-b:build-b']
    assert result['configurations'][0]['observed_build']==saved
    assert result['updates'][0]['move_membership_excluded_ids']==[]


def test_damage_epoch_and_illegal_original_mega_ability_are_not_substituted():
    c=config();o=observation(c);o['input']['attacker']['identity']='Charizard'
    with pytest.raises(ValueError,match='epoch/form mismatch'):filter_joint([c],[o])
    c.update(form='pokeapi:form:10530',ability='No Guard',item='Raichunite Y',original_ability='No Guard')
    with pytest.raises(ValueError,match='original pre-Mega'):filter_joint([c],[])


@pytest.mark.local_artifacts
def test_real_source_bound_overlay_is_causal_and_preserves_empirical_identity():
    pointer=ROOT/'.cache/battles/sample_battle_11/m342-offensive/latest.json'
    if not pointer.exists():pytest.skip('Optional M3.4.2 package absent')
    d=json.loads(Path(json.loads(pointer.read_text())['path']).read_text());u=d['offensive_inference']['updates'][0]
    assert u['observation']['damage']==16
    assert u['observation']['hp_attribution']['before']['current']==184
    assert u['observation']['hp_attribution']['after']['current']==168
    actor=u['attacker']
    def state(t):return next(s for s in reversed(d['snapshots']) if s['timestamp']<=t)
    def support(t):return d['support_catalog'][state(t)['opponents'][actor]['support_ref']]
    before=deepcopy(support(162.53));assert 'offensive' not in before['full']
    assert set(before['observed']['offensive_stats'])=={'attack','special_attack'}
    assert all(not s['direct_constraint'] and not s['evidence_ids']
               for s in before['observed']['offensive_stats'].values())
    after=support(163.03)
    assert after['full']['offensive']['values']['values']==list(range(108,119))
    for layer in ('observed','full'):
        stats=after[layer]['offensive_stats']
        assert stats['attack']['direct_constraint']
        assert not stats['special_attack']['direct_constraint']
        assert stats['special_attack']['evidence_ids']==[]
        assert stats['attack']['ids']==stats['special_attack']['ids']
    assert after['observed']['offensive_stats']['special_attack']['values']['values']==[180,181,182,185,212]
    assert after['full']['speed']['minimum']==150
    assert len(after['observed']['builds'])==(72 if d.get('empirical_measure_model',{}).get('version')=='M3.4.4' else 52)
    assert all(d['observed_builds'][i]['nature']=='nature:timid' for i in after['observed']['builds'])
    assert support(162.53)==before and support(502)['full']['offensive']==after['full']['offensive']


@pytest.mark.local_artifacts
def test_battle12_review_admits_psyshock_before_berry_recovery():
    from battle_artifacts import BattleArtifacts
    from battle_evidence.offensive import admit_review, observed_configuration_domain
    from battle_evidence.speed_replay_offline import load_team, select_actions
    from scripts.build_offensive_replay import inverse_diagnostics

    battle=BattleArtifacts('sample_battle_12',ROOT)
    pointer=battle.cache('m322-reviewed-speed/latest.json')
    review=json.loads((ROOT/'tests/fixtures/battle_evidence/battle12-damage-review.json').read_text())
    sources=[ROOT/s['image'] for e in review['events'] for s in e['sources'].values()]
    if not pointer.exists() or any(not p.exists() for p in sources):
        pytest.skip('Optional Battle 12 source evidence absent')
    replay=json.loads(Path(json.loads(pointer.read_text())['path']).read_text())
    actions,*_=select_actions(battle)
    _,builds,_,_,_=load_team(battle,actions,root=ROOT)
    obs=admit_review(replay,review,builds,root=ROOT)
    assert len({o['attacker'] for o in obs})==1
    assert [o['damage'] for o in obs]==[126,100]
    assert [o['hp_attribution']['after']['current'] for o in obs]==[58,19]
    assert [o['input']['defender']['stats']['defense'] for o in obs]==[99,121]
    assert all(o['damage']<o['input']['defender']['current_hp'] for o in obs)
    assert all(o['field_alternatives']==[{'critical':False},{'critical':True}] for o in obs)
    participant=next(s for s in reversed(replay['snapshots']) if s['timestamp']<=obs[0]['timestamp'])['opponents'][obs[0]['attacker']]
    configs=observed_configuration_domain(replay,participant)
    result=filter_joint(configs,obs)
    assert len(configs)==13 and len(result['configurations'])==1
    assert result['updates'][0]['move_membership_excluded_ids']==[]
    assert len(result['updates'][0]['numerical_excluded_ids'])==12
    assert result['work']['forward_evaluations']>0
    before=deepcopy(obs)
    diagnostics=inverse_diagnostics(replay,obs)[obs[0]['attacker']]
    assert obs==before
    assert len(diagnostics['observed']['configurations'])==1
    assert set(diagnostics['native_ability_probes'])=={'Healer','Anticipation','Magic Bounce'}
    for probe in diagnostics['native_ability_probes'].values():
        assert probe['status']=='conditional' and probe['feasible']['values']
        assert {198,206}<=set(probe['feasible']['values'])
        assert not probe['diagnostics']
