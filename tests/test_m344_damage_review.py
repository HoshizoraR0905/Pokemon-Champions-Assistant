"""Curated review facts and synthetic three-hit continuity, separate from OCR."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from battle_evidence.damage_review_history import stage_history
from battle_evidence.empirical_measure import catalog
from battle_evidence.move_legality import move_legality
from damage.joint import filter_joint,concrete_ids,project_joint
from test_hatterene_damage import config,observation

PATH=Path('tests/fixtures/battle_evidence/battle12-m344-damage-review.json')
REVIEW=json.loads(PATH.read_text())


def test_previous_review_prefix_is_frozen_and_hp_is_settled_not_animation():
    old=Path(REVIEW['frozen_prefix']['path']);assert hashlib.sha256(old.read_bytes()).hexdigest()==REVIEW['frozen_prefix']['sha256']
    assert REVIEW['events'][:2]==json.loads(old.read_text())['events']
    h=REVIEW['events'][-1]
    assert (h['pre_hp'],h['post_hp'],h['maximum_hp'])==(50,4,164)
    assert h['pre_hp']-h['post_hp']==46 and h['post_hp']>0
    assert h['sources'][h['post_source']]['timestamp']==h['available_at']==714.5033333333333
    assert all(s['timestamp']<=h['available_at'] for s in h['sources'].values())
    assert h['context']['defender_status']=='burn' and h['context']['attacker_stages']['special_attack']==-3
    assert h['defender_item_transition']['item']=='Sitrus Berry'
    assert h['item_evidence_exclusions']==['White Herb']
    assert h['item_exclusion_provenance']['origin']=='user_source_review'
    assert h['stage_history']['unresolved_items']==[]


def stage_case():
    r=deepcopy(REVIEW['events'][-1]);rows=[]
    for i,t in enumerate(r['stage_history']['transitions']):
        rows.append(dict(id=t['event_id'],timestamp=472+i*40,kind='stat_change',instance_id=r['attacker'],text='特攻降低了',sources=[next(iter(r['sources'].values()))]))
    return r,dict(timeline=rows)


def test_three_independent_source_drops_do_not_double_count_two_target_message():
    r,replay=stage_case();result=stage_history(r,replay)
    assert [t['stage'] for t in result['transitions']]==[-1,-2,-3]
    r['context']['attacker_stages']['special_attack']=-2
    with pytest.raises(ValueError,match='disagree'):stage_history(r,replay)


def test_stage_reset_requires_source_and_restarts_accumulation():
    r,replay=stage_case();reset=dict(id='switch',timestamp=500,kind='switch_out',instance_id=r['attacker'],sources=replay['timeline'][0]['sources'])
    replay['timeline'].insert(1,reset)
    with pytest.raises(ValueError,match='Unreviewed switch'):stage_history(r,replay)
    r['stage_history']['transitions'].insert(1,dict(kind='reset',event_id='switch'))
    r['context']['attacker_stages']['special_attack']=-2
    assert stage_history(r,replay)['stage']==-2


def test_soft_move_membership_cannot_substitute_for_move_legality():
    assert move_legality('pokeapi:species:858','Psyshock')['status']=='confirmed_possible'
    assert move_legality('pokeapi:species:858','not-a-move')['status']=='unverified'
    assert move_legality('pokeapi:species:858','Earthquake')['status']=='unverified'


def test_partial_template_does_not_disqualify_known_legal_core():
    row=dict(species='pokeapi:species:858',training_points=dict(hp=32,attack=0,defense=2,special_attack=32,special_defense=0,speed=0),
        alignment=dict(increase='special_attack',decrease='speed'),nature='nature:quiet',ability='pokeapi:ability:156',
        item='pokeapi:item:179',stat_issue=None,issues=[],observed_team_signature='one',build_id=None,
        configuration=dict(moves=['pokeapi:move:473',None,None,None]),publications=[dict(id='pub')])
    # Use a known legal item whose canonical ID does not depend on the synthetic test.
    from battle_evidence.speed_items import item_ids
    row['item']=item_ids()['Babiri Berry']
    population=dict(scope=dict(source='synthetic'),by_form={row['species']:dict(builds=[row])})
    c=catalog(population,row['species']);assert len(c['records'])==1 and len(c['cores'])==1
    assert not next(iter(c['records'].values()))['template']['complete']
    second=deepcopy(row);second['observed_team_signature']='two';second['configuration']['moves']=['pokeapi:move:94',None,None,None]
    population['by_form'][row['species']]['builds'].append(second)
    c=catalog(population,row['species']);assert len(c['records'])==2 and len(c['cores'])==1


def test_three_hit_filter_resumes_actual_same_core_independent_rolls_and_budget():
    c=config(points=[16]);hits=[observation(c,key='a',roll=0),observation(c,key='b',roll=15,second=True),observation(c,key='c',roll=4,critical=True,second=True)]
    hits[-1]['timestamp']=3
    prior=filter_joint([c],hits[:2]);resumed=filter_joint([c],hits,prior=prior)
    whole=filter_joint([c],hits)
    assert resumed['configurations']==whole['configurations']
    assert concrete_ids(resumed['configurations'])<=concrete_ids(prior['configurations'])
    assert resumed['configurations'][0]['training']['point_domains']['speed']==[32]
    assert [h['id'] for h in resumed['updates']]==['a','b','c']
    for h in resumed['updates']:assert h['selector']['offensive_stat']=='special_attack' and h['selector']['defensive_stat']=='defense'


def test_reviewed_white_herb_absence_is_item_evidence_not_numerical_exclusion():
    c=config('White Herb');o=observation(config());o['item_evidence_exclusions']=['White Herb']
    result=filter_joint([c],[o]);u=result['updates'][-1]
    assert not result['configurations'] and u['item_evidence_excluded_ids']==[c['id']]
    assert u['numerical_excluded_ids']==[] and u['move_membership_excluded_ids']==[]


@pytest.mark.local_artifacts
def test_all_curated_source_frame_hashes_and_stage_sources():
    if any(not Path(s['image']).exists() for e in REVIEW['events'] for s in e['sources'].values()):pytest.skip('Optional cached source frames unavailable')
    for e in REVIEW['events']:
        for s in e['sources'].values():assert hashlib.sha256(Path(s['image']).read_bytes()).hexdigest()==s['sha256']
    from battle_evidence.offensive import admit_review
    from battle_evidence.speed_replay_offline import select_actions,load_team
    from battle_artifacts import BattleArtifacts
    r=json.load(open(json.load(open('.cache/battles/sample_battle_12/m322-reviewed-speed/latest.json'))['path']))
    a,*_=select_actions(BattleArtifacts('sample_battle_12',Path.cwd()))
    _,builds,_,_,_=load_team(BattleArtifacts('sample_battle_12',Path.cwd()),a,root=Path.cwd())
    admitted=admit_review(r,REVIEW,builds,root=Path.cwd())
    assert [o['damage'] for o in admitted]==[126,100,46]
    assert admitted[-1]['stage_audit']['stage']==-3 and admitted[-1]['input']['defender']['item']=='none'
