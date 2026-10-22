"""Published original abilities survive Mega; active abilities and stats change."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from battle_evidence.speed_reviewed import empirical_configs
from battle_evidence.speed_replay import universe
from knowledge.champions_stats import ChampionsStats
from metagame.published.speed_support import SpeedSupportIndex
from speed_order.core import identity_key
from speed_order.forms import published_ability

ROOT=Path(__file__).resolve().parents[1]
RAICHU='pokeapi:species:26'
MEGA='pokeapi:form:10530'


def member(ability, species=MEGA, stone='Raichunite Y'):
    points=dict(hp=32,attack=0,defense=0,special_attack=10,special_defense=0,speed=24)
    alignment=dict(increase='speed',decrease='attack')
    return dict(species=species,ability=ability,item=stone,complete=True,
                nature='nature:timid',alignment=alignment,training_points=points,
                speed=ChampionsStats(species,form='as_named').calculate(points,alignment)['stats']['speed'],
                speed_sp=24,observed_team_signature='team',build_id='joint-id',
                configuration=dict(original='untouched'),publications=[])


@pytest.mark.parametrize('ability',['Lightning Rod','Static'])
def test_original_raichu_ability_and_joint_training_survive_mega(ability):
    row=member(ability);saved=deepcopy(row);index=SpeedSupportIndex([row],{})
    before,issues=empirical_configs(index,RAICHU,universe(RAICHU)['item_equivalence_classes'])
    assert not issues and len(before)==1
    after,issues=empirical_configs(index,MEGA,universe(MEGA)['item_equivalence_classes'])
    assert not issues and len(after)==1
    a,b=before[0],after[0]
    assert (a['ability'],b['ability'])==(ability,'No Guard')
    assert (a['speed'],b['speed'])==(169,191)
    assert a['id']==b['id']=='team:joint-id'
    assert a['item']==b['item']=='Raichunite Y'
    assert a['training']==b['training']
    assert b['training']['point_domains']['speed']==[24]
    assert b['observed_build']==a['observed_build']==saved
    assert row==saved and index.rows==[saved]
    assert b['ability_state']['original_ability']==ability


def test_post_mega_source_does_not_invent_pre_mega_ability():
    row=member('No Guard');index=SpeedSupportIndex([row],{})
    after,issues=empirical_configs(index,MEGA,universe(MEGA)['item_equivalence_classes'])
    assert not issues and after[0]['ability']=='No Guard'
    assert after[0]['ability_state']['original_ability'] is None
    assert set(after[0]['ability_state']['original_ability_alternatives'])=={'Static','Lightning Rod'}
    before,issues=empirical_configs(index,RAICHU,universe(RAICHU)['item_equivalence_classes'])
    assert before==[] and issues[0]['reason']=='Published post-Mega ability does not identify original ability'


@pytest.mark.parametrize('ability,stone,reason',[
    ('Blaze','Raichunite Y','Source ability legal in neither'),
    ('Static','Raichunite X','lacks its required stone')])
def test_independent_illegal_source_assertions_are_explained(ability,stone,reason):
    rows,issues=empirical_configs(SpeedSupportIndex([member(ability,stone=stone)],{}),MEGA,universe(MEGA)['item_equivalence_classes'])
    assert rows==[] and reason in issues[0]['reason']


def test_same_mapping_handles_other_mega_species():
    target=identity_key('Mega Charizard Y','as_named');base=identity_key('Charizard','base')
    row=member('Blaze',target,'Charizardite Y');index=SpeedSupportIndex([row],{})
    before,_=empirical_configs(index,base,universe(base)['item_equivalence_classes'])
    after,issues=empirical_configs(index,target,universe(target)['item_equivalence_classes'])
    assert not issues and after[0]['ability']=='Drought'
    assert before[0]['ability']=='Blaze' and before[0]['id']==after[0]['id']
    assert before[0]['speed']==after[0]['speed']
    assert after[0]['observed_build']['ability']=='Blaze'


@pytest.mark.local_artifacts
def test_recorded_b11_all_complete_members_and_causal_ability_restore():
    pointer=ROOT/'.cache/battles/sample_battle_11/m322-reviewed-speed/latest.json'
    if not pointer.exists():pytest.skip('Optional local replay absent')
    path=Path(json.loads(pointer.read_text())['path']);d=json.loads(path.read_text())
    empirical=json.loads(path.with_name('empirical.json').read_text())['by_form'][MEGA]
    rows=[r for r in empirical['builds'] if r['complete']]
    def at(time):return next(s for s in reversed(d['snapshots']) if s['timestamp']<=time)
    iid='sample_battle_11:opponent:encounter:3a97ce2b12c2c2fe'
    before=deepcopy(at(147));after=at(160)['opponents'][iid]
    support=d['support_catalog'][after['support_ref']]['observed']
    assert len(rows)==68 and support['complete_after']==68
    assert len({d['observed_builds'][i]['build_id'] for i in support['builds']})==51
    assert not support['eligibility_issues']
    assert {m['active_ability'] for m in support['ability_mappings'].values()}=={'No Guard'}
    assert all(d['observed_builds'][i] in rows for i in support['builds'])
    for s in d['snapshots']:
        if s['timestamp']>=158.02666666666667:continue
        if iid not in s['opponents']:continue
        p=s['opponents'][iid];layers=d['support_catalog'][p['support_ref']]
        assert all(b['ability']!='No Guard' for b in layers['full']['branches'])
        assert all(m['active_ability']!='No Guard' for m in layers['observed']['ability_mappings'].values())
    assert at(147)==before
    assert at(502)['opponents'][iid]['current_form']==MEGA
