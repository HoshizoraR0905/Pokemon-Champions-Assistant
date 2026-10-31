"""Scoped initial items, matching correlations, and causal reviewed evidence."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from battle_evidence.team_items import RULE_ID,exclusions,matching,propagate,original_assignments
from battle_evidence.item_policy import item_state,action_item,filter_policy_joint,refine_revealed
from battle_evidence.life_orb import reviewed_message
from damage.joint import filter_joint,concrete_ids
from damage.explanations import explain_items
from test_item_policy import event,domain
from test_hatterene_damage import config,observation

B='battle';A=B+':opponent:incineroar';H=B+':opponent:hatterene';C=B+':opponent:third'


def initial(actor=A,item='Life Orb',available=3):
    return dict(event(item,'initial_held',time=1,available=available),battle_id=B,
        individual=actor,team_rule=RULE_ID,initial_ownership_review={'unchanged_since_start':True})


def test_three_member_matching_preserves_correlations_and_prunes_hall_failure():
    domains={A:['Life Orb','Sitrus Berry'],H:['Life Orb','Sitrus Berry'],C:['Life Orb','Sitrus Berry','Wise Glasses']}
    allowed=propagate(domains,enabled=True)
    assert allowed[C]==['Wise Glasses']
    assert matching({A:['Life Orb'],H:['Life Orb'],C:['Wise Glasses']}) is None
    assert matching({A:['Life Orb'],H:['Sitrus Berry'],C:['Wise Glasses']})=={A:'Life Orb',H:'Sitrus Berry',C:'Wise Glasses'}
    assert propagate(domains,enabled=False)==domains
    assert matching({A:['none'],H:['none']})=={A:'none',H:'none'}


def test_initial_owner_disjunction_is_mandatory_without_asserting_holder():
    domains={A:['Life Orb','Normal Gem'],C:['Life Orb','Sitrus Berry'],H:['Life Orb','Wise Glasses']}
    reservations={'Life Orb':{A,C}}
    assert propagate(domains,enabled=True,reservations=reservations)[H]==['Wise Glasses']
    assert matching({A:['Normal Gem'],C:['Sitrus Berry'],H:['Wise Glasses']},reservations=reservations) is None
    assert matching(domains,(A,'Normal Gem'),reservations=reservations)[C]=='Life Orb'
    assert matching(domains,(A,'Life Orb'),reservations=reservations)[A]=='Life Orb'


def test_reviewed_current_possession_can_keep_compatible_original_transfer_branch():
    e=initial();e.update(kind='activated',timestamp=2,action_id='fakeout',activation_basis='reviewed_item_message',compatible_initial_items=['Life Orb','Normal Gem'])
    assert action_item('Normal Gem',[e],battle_id=B,individual=A,at=3,available_at=3)=='Life Orb'
    assert action_item('Normal Gem',[e],battle_id=B,individual=A,at=2,available_at=3)=='unknown'
    assert item_state([e],battle_id=B,individual=A,at=3)['current_item']=='Life Orb'
    assert 'initial_item' not in item_state([e],battle_id=B,individual=A,at=3)


def test_consumption_transfer_and_cross_battle_do_not_release_original_item():
    claim=initial();consumed=dict(event('Life Orb','consumed',time=4),battle_id=B,individual=A)
    assert exclusions([claim,consumed],battle_id=B,individual=H,at=5)=={'Life Orb'}
    assert exclusions([claim],battle_id='other',individual='other:opponent:hatterene',at=5)==set()
    assert exclusions([claim],battle_id=B,individual=B+':self:member',at=5)==set()
    assert exclusions([claim],battle_id=B,individual=H,at=2)==set()
    assert item_state([claim,consumed],battle_id=B,individual=A,at=5)['initial_item']=='Life Orb'
    assert item_state([claim,consumed],battle_id=B,individual=A,at=5)['current_item']=='none'


def test_current_holder_never_proves_original_assignment_without_review():
    held=dict(event('Life Orb',time=1),battle_id=B,individual=A)
    assert not exclusions([held],battle_id=B,individual=H,at=5)
    e=initial();e['initial_ownership_review']['unchanged_since_start']=False
    with pytest.raises(ValueError,match='continuity'):original_assignments([e],battle_id=B,individual=A,at=5)


def test_legal_transfer_changes_current_not_original_and_unresolved_is_unknown():
    original=initial(available=1)
    out=dict(event('Life Orb','transferred_out',time=4),battle_id=B,individual=A)
    received=dict(event('Sitrus Berry','transferred_in',time=4),battle_id=B,individual=A)
    events=[original,out,received]
    assert action_item('Life Orb',events,battle_id=B,individual=A,at=5,available_at=5)=='Sitrus Berry'
    assert action_item('Sitrus Berry',events,battle_id=B,individual=A,at=5,available_at=5) is None
    state=item_state(events,battle_id=B,individual=A,at=5)
    assert state['initial_item']=='Life Orb' and state['current_item']=='Sitrus Berry'
    assert exclusions(events,battle_id=B,individual=H,at=5)=={'Life Orb'}
    unknown=dict(event('Life Orb','unresolved_transfer',time=2),battle_id=B,individual=H)
    held=dict(event('Life Orb',time=3),battle_id=B,individual=H)
    for item in ('none','Life Orb'):
        assert action_item(item,[unknown],battle_id=B,individual=H,at=4,available_at=4)=='unknown'
        assert action_item(item,[unknown,held],battle_id=B,individual=H,at=4,available_at=4)=='Life Orb'
    o=observation(config());o.update(battle_id=B,attacker=H,timestamp=4,damage=999)
    result=filter_joint(domain(['none','Life Orb']),[o],item_events=[unknown])
    assert result['configurations'] and result['unresolved']
    assert not result['updates'][0]['numerical_excluded_ids']


@pytest.mark.parametrize('profile',['practical','comprehensive'])
def test_hard_item_restrictions_and_causal_rewind_are_shared_by_profiles(profile):
    rows=domain(['none','Life Orb']);o=observation(config());o.update(battle_id=B,attacker=H,timestamp=4)
    e=initial()
    result=filter_policy_joint(rows,[o],profile=profile,item_events=[e])
    assert all('Life Orb' not in c.get('item_options',[c['item']]) for c in result['configurations'])
    ex=explain_items(result,[o],original_configurations=rows)
    orb=next(i for i in ex['items'] if i['item']=='Life Orb')
    assert orb['states']==['excluded_by_team_uniqueness']
    assert not set(result['updates'][0]['team_item_excluded_ids'])&set(result['updates'][0]['numerical_excluded_ids'])
    early=filter_joint(rows,[])
    before=refine_revealed(early,[e],battle_id=B,individual=H,at=2)
    after=refine_revealed(early,[e],battle_id=B,individual=H,at=3)
    assert 'parent@Life Orb' in concrete_ids(before['configurations'])
    assert 'parent@Life Orb' not in concrete_ids(after['configurations'])
    rewind=refine_revealed(early,[e],battle_id=B,individual=H,at=2)
    assert concrete_ids(rewind['configurations'])==concrete_ids(before['configurations'])


def test_message_wording_actor_and_action_are_bound():
    args=dict(actor_name='炽焰咆哮虎',individual=A,action_id='fakeout')
    generic=reviewed_message('对手的炽焰咆哮虎受到了反作用力造成的伤害！',**args)
    assert generic['kind']=='generic_recoil' and not generic['confirms_life_orb']
    specific=reviewed_message('对手的炽焰咆哮虎的生命被少量削减了！',**args)
    assert specific['confirms_life_orb'] and specific['individual']==A and specific['action_id']=='fakeout'
    assert reviewed_message('对手的炽焰咆哮虎的生命被少量削减了！',**dict(args,actor_name='布莉姆温',individual=H)) is None
    assert reviewed_message('炽焰咆哮虎的生命宝珠',**dict(args,action_id=None)) is None
    e=dict(event('Life Orb','activated',action_id='fakeout',activation_basis='reviewed_item_message'),
        exact_wording='对手的炽焰咆哮虎受到了反作用力造成的伤害！',actor_name='炽焰咆哮虎')
    with pytest.raises(ValueError,match='Generic recoil'):item_state([e],battle_id='synthetic',individual='persistent-hatterene',at=5)


def test_source_fixture_is_additive_battle12_not_battle11():
    root=Path(__file__).resolve().parents[1]
    extra=json.loads((root/'tests/fixtures/battle_evidence/battle12-m345a-team-item-review.json').read_text())
    base=json.loads((root/extra['base_review']).read_text());original=base['events'][0];e=extra['events'][0]
    assert original['battle_id']==e['battle_id']=='sample_battle_12'
    assert original['individual']==e['individual']=='sample_battle_12:opponent:encounter:13602f7dde98f1c5'
    assert original['sources'][0] in e['sources']
    assert e['exact_wording']=='炽焰咆哮虎的\n生命宝珠'
    assert exclusions([e],battle_id='sample_battle_12',individual='sample_battle_12:opponent:encounter:29f64303ef101514',at=168)=={'Life Orb'}
    assert not exclusions([e],battle_id='sample_battle_11',individual='sample_battle_11:opponent:encounter:3a97ce2b12c2c2fe',at=168)


def test_incremental_checkpoint_keeps_team_reason_separate_from_damage():
    rows=domain(['none','Life Orb']);first=observation(config('Life Orb'),point=32);first.update(battle_id=B,attacker=H,timestamp=2)
    second=deepcopy(first);second.update(id='second',timestamp=4)
    checkpoint=filter_policy_joint(rows,[first],profile='comprehensive')
    assert 'Life Orb' in checkpoint['requirements']['items']
    result=filter_policy_joint(rows,[first,second],profile='comprehensive',item_events=[initial()],prior=checkpoint)
    last=result['updates'][-1]
    assert last['team_item_excluded_ids'] and not set(last['team_item_excluded_ids'])&set(last['numerical_excluded_ids'])
    assert result['updates'][0]==checkpoint['updates'][0]


@pytest.mark.local_artifacts
@pytest.mark.parametrize('profile',['practical','comprehensive'])
def test_recorded_team_projection_source_and_occurrences(profile):
    from battle_evidence.item_policy import validate_item_review
    from battle_evidence.speed_replay_offline import file_hash
    root=Path(__file__).resolve().parents[1]
    pointer=root/f'.cache/battles/sample_battle_12/m342-offensive/latest-{profile}.json'
    if not pointer.exists():pytest.skip('Optional Battle12 package absent')
    source=Path(json.loads(pointer.read_text())['path']);seal=json.loads(source.with_name('manifest.json').read_text())
    assert seal['status']=='complete' and file_hash(source)==seal['outputs']['replay.json']
    r=json.loads(source.read_text())
    assert r.get('team_item_relations'), 'Present package must contain current team projection'
    validate_item_review(r['offensive_inference']['item_events'],r,root=root)
    inc='sample_battle_12:opponent:encounter:13602f7dde98f1c5';hat='sample_battle_12:opponent:encounter:29f64303ef101514'
    def support(actor,time):
        snap=next(s for s in reversed(r['snapshots']) if s['timestamp']<=time)
        return r['support_catalog'][snap['opponents'][actor]['support_ref']]
    assert support(inc,166)['observed']['complete_after']==197
    assert support(inc,168)['observed']['complete_after']==4
    assert support(inc,168)['full']['items']==['Life Orb','Normal Gem']
    assert support(hat,365)['observed']['complete_after']==1
    assert len(r['empirical_core_catalogs']['pokeapi:species:858']['records'])==13
    assert r['empirical_scope']['observations_removed_by_deduplication']==0
    first=r['offensive_inference']['updates'][0]['observed']['updates'][0]
    assert len(first['team_item_excluded_ids'])==12 and not first['numerical_excluded_ids']
    assert r['empirical_measure_model']['default_alpha']==.5
    assert 'Life Orb' not in support(hat,365)['full']['items']
    assert next(i for i in support(hat,715)['full']['item_explanations']['items'] if i['item']=='Life Orb')['states']==['excluded_by_team_uniqueness']
    from damage import calculate
    for u in r['offensive_inference']['updates']:
        assert u['observation']['damage'] in [126,100,46]
        for w in u['full']['item_explanations']['witnesses']:
            if w['witness'] is None:continue
            proof=w['witness'];assert proof['total_sp']<=66
            for hit in proof['hits']:
                assert calculate(hit['forward_input'])['distribution']['rolls'][hit['roll']-85]==hit['predicted_damage']
