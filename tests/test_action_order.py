"""Synthetic mechanics/adapter tests; reviewed video transcription is labeled."""
from copy import deepcopy
import json
import math
from pathlib import Path
import pytest
from battle_evidence.actions import reconstruct,category,action_priority
from battle_evidence.action_inference import analyse
from battle_evidence.builds import KnownBuilds
from battle_evidence.action_offline import bind_team
from speed_order.execution import pair_likelihood,priority,VERSION
from speed_order.core import REFERENCE
from speed_inference import SpeedBelief,configuration_space
from speed_inference.controlled import observation
from team_configuration import TeamConfiguration,STATS
from knowledge.champions_stats import ChampionsStats


def execution(o):
    o=deepcopy(o);o['execution_model']=dict(version=VERSION,sources=[{'kind':'synthetic conditional reference'}])
    return o


@pytest.mark.parametrize('move,expected',[('Fake Out',3),('Protect',4),('Trick Room',-7),('Flamethrower',0)])
def test_priority_catalog(move,expected):
    assert priority(move,observation()['context']['own'])==expected


def test_prankster_unknown_activation_and_alternatives():
    actor=observation()['context']['own'];actor['ability']='Prankster'
    assert priority('Tailwind',actor)==1
    assert priority('Flamethrower',actor)==0
    actor['ability_active']=False;assert priority('Tailwind',actor)==0
    actor['ability_active']=None
    with pytest.raises(ValueError):priority('Tailwind',actor)
    pr=action_priority('pokeapi:move:113',None,None,'pokeapi:species:861')
    assert pr['effective_priorities']==[0,1]


@pytest.mark.parametrize('state,expected',[('confirmed_active',1),('confirmed_inactive',0),('unknown',.2)])
def test_quick_claw_is_override_not_speed_multiplier(state,expected):
    o=execution(observation(own_speed=150));c=o['context'];c['opponent']['item']='Quick Claw'
    e=o['execution_model'];e['quick_claw']={'opponent':dict(state=state,sources=[{'kind':'synthetic explicit item hypothesis'}])}
    p,detail=pair_likelihood(c,120,'opponent',e,REFERENCE)
    assert p==expected
    assert detail['effective_speeds']['opponent']==120
    c['field']['trick_room']=True
    p,_=pair_likelihood(c,120,'opponent',e,REFERENCE);assert p==1


def test_unknown_item_and_unknown_activation_provenance_defer():
    o=execution(observation());o['context']['opponent']['item']=None
    assert pair_likelihood(o['context'],130,'opponent',o['execution_model'],REFERENCE)[0] is None
    o['context']['opponent']['item']='Quick Claw'
    assert pair_likelihood(o['context'],130,'opponent',o['execution_model'],REFERENCE)[0] is None


def test_confirmed_claw_activation_excludes_nonclaw_configuration():
    o=execution(observation());o['execution_model']['quick_claw']={'opponent':dict(state='confirmed_active',sources=[{'kind':'synthetic direct activation'}])}
    assert pair_likelihood(o['context'],130,'opponent',o['execution_model'],REFERENCE)[0]==0


@pytest.mark.parametrize('edit,opp_speed,expected',[
    (('own','tailwind',True),150,0), (('opponent','tailwind',True),100,1),
    (('own','status','paralysis'),100,1), (('opponent','stage',1),100,1),
    (('field','trick_room',True),150,0),
    (('opponent','item','Choice Scarf'),100,1),
    (('opponent','item','Iron Ball'),200,0),
])
def test_modifiers_reuse_maintained_speed(edit,opp_speed,expected):
    o=execution(observation(own_speed=121));role,key,v=edit;o['context'][role][key]=v
    assert pair_likelihood(o['context'],opp_speed,'opponent',o['execution_model'],REFERENCE)[0]==expected


@pytest.mark.parametrize('ability,field,value',[('Swift Swim','weather','rain'),('Chlorophyll','weather','sun'),('Sand Rush','weather','sand'),('Slush Rush','weather','snow'),('Surge Surfer','terrain','electric')])
def test_weather_and_terrain_reference(ability,field,value):
    o=execution(observation(own_speed=150));o['context']['opponent']['ability']=ability;o['context']['field'][field]=value
    assert pair_likelihood(o['context'],100,'opponent',o['execution_model'],REFERENCE)[0]==1


def test_different_priorities_special_actions_midturn_and_ties():
    o=execution(observation());c=o['context'];e=o['execution_model']
    assert pair_likelihood(c,121,'opponent',e,REFERENCE)[0]==.5
    c['actions']['own'].update(move='Protect',effective_priority=4)
    assert pair_likelihood(c,121,'opponent',e,REFERENCE)[1]['reason']=='not_speed_informative_different_priority'
    c['actions']['own']['kind']='switch'
    assert pair_likelihood(c,121,'opponent',e,REFERENCE)[0] is None
    c=observation()['context'];c['timing']['modifier_changes']=[{'effect':'Tailwind'}]
    assert pair_likelihood(c,121,'opponent',e,REFERENCE)[0] is None
    c=observation()['context'];c['actions']['own']['kind']='unable'
    assert pair_likelihood(c,121,'opponent',e,REFERENCE)[0] is None


def domain(values):return dict(values=values,coverage='complete_given_evidence',evidence=[{'kind':'synthetic restricted domain, not empirical prior'}])


def belief(items):
    model=configuration_space(identity='Charizard',form='base',speed_points=[0,1,2],
        alignments=[dict(increase=None,decrease=None)],abilities=domain(['Blaze']),items=domain(items))
    return SpeedBelief(model,battle_id='synthetic',instance_id='opponent:1',stat_epoch='initial',profile=REFERENCE)


def test_choice_scarf_competing_hypothesis_posterior_and_normalization():
    b=belief(['none','Choice Scarf']);o=execution(observation(own_speed=150));o['context']['opponent']['item']=None
    assert b.update(o)['status']=='updated'
    s=b.summary();assert s['probability_sum']==pytest.approx(1)
    assert all(row['configuration']['item']=='Choice Scarf' for row in s['configurations'] if row['positive_support'])
    assert b.update(o)['status']=='duplicate_ignored'
    # Same ordering decision cannot be multiplied through another pair.
    o['id']='new-pair';o['action_ids']={'own':'another','opponent':'yet-another'}
    assert b.update(o)['status']=='ineligible'


def test_full_legal_ordinary_support_and_scarf_claw_alternatives():
    model=configuration_space(identity='Charizard',form='base',abilities=domain(['Blaze']),items=domain(['none','Choice Scarf','Quick Claw']))
    b=SpeedBelief(model,battle_id='synthetic',instance_id='opponent:1',stat_epoch='initial',profile=REFERENCE)
    o=execution(observation(own_speed=180));o['context']['own'].update(identity='Aerodactyl',ability='Pressure')
    for role in ('own','opponent'):o['context']['actions'][role]['move']='Rock Slide'
    o['context']['opponent']['item']=None
    o['execution_model']['quick_claw']={'opponent':dict(state='unknown',sources=[{'kind':'synthetic conditional item domain'}])}
    assert max(c['unmodified_speed'] for c in model['candidates'])<180
    assert b.update(o)['status']=='updated'
    weights={}
    for c in b.summary()['configurations']:
        item=c['configuration']['item'];weights[item]=weights.get(item,0)+c['probability']
    assert weights['none']==0
    assert 0<weights['Quick Claw']<weights['Choice Scarf']<1
    assert b.summary()['probability_sum']==pytest.approx(1)


def test_quick_claw_keeps_ordinary_speed_support_and_contradiction():
    b=belief(['none','Quick Claw']);o=execution(observation(own_speed=150));o['context']['opponent']['item']=None
    o['execution_model']['quick_claw']={'opponent':dict(state='unknown',sources=[{'kind':'synthetic eligible item state'}])}
    assert b.update(o)['status']=='updated'
    assert b.summary()['support']==[120,121,122]
    assert b.summary()['probability_sum']==pytest.approx(1)
    q=execution(observation(2,own_speed=150));q['context']['opponent']['item']='none'
    assert b.update(q)['status']=='contradiction'
    assert not b.summary()['posterior_defined']


def synthetic_input():
    o=observation();events=[];snapshots={};raw={};assignment={}
    for i,role in enumerate(('own','opponent')):
        side='self' if role=='own' else role;eid=f'event:{i}'
        e=dict(id=eid,battle_id='synthetic',origin='synthetic',timestamp=10+i,position=i,kind='action',source_event_type='move_execution',
            side=side,instance_id=f'{role}:1',binding={'pokemon_instance_id':f'{role}:1'},
            text='喷火龙使出了喷射火焰！',move='pokeapi:move:53',move_verified=True,underlying_action_id=eid,
            source_status='confirmed',sources=[dict(source_type='video_message',source_id=f'synthetic#{i}')])
        events.append(e);assignment[eid]=dict(turn_id='local:1',local_segment_index=1,status='confirmed_local_membership')
        mon=dict(identity=dict(known=True,value={'canonical_id':'pokeapi:species:6'}),form=dict(known=True,value='pokeapi:pokemon:6'),location=dict(known=True,value={'slot':'left'}))
        snapshots[eid]={'before':dict(observable={'pokemon':{f'{role}:1':mon}})}
    p=dict(schema='normal-screen-three-hud-v2.2',battle_id='synthetic',
        visual={'segments':[dict(id='local:1',local_index=1,status='confirmed')]},reconstruction=dict(ledger=events,assignment=assignment))
    return p,snapshots,raw


def test_partial_duplicate_sequences_missing_build_and_preservation():
    p,s,raw=synthetic_input();original=deepcopy(p);p['reconstruction']['ledger'].append(deepcopy(p['reconstruction']['ledger'][0]))
    result=reconstruct(p,s);assert len(result['actions'])==2;assert len(result['duplicates'])==1
    assert result['groups'][0]['partial']
    r=analyse(result,KnownBuilds());assert r['speed']['eligible_updates']==0
    assert 'verified_own_speed_missing' in r['relations'][0]['numeric_reasons']
    assert p['reconstruction']['ledger'][:2]==original['reconstruction']['ledger']
    assert category(dict(source_event_type='move_execution',text='喷火龙使出了喷射火焰！',sources=[{'source_type':'battle_log'}]))=='unverified_move_announcement'
    assert category(dict(text='畏缩而不能动！'))=='prevented_action'


def test_deferred_binding_reanalysis_existing_engine_and_continuity():
    p,s,_=synthetic_input();r=reconstruct(p,s);builds=KnownBuilds()
    builds.register(battle_id='synthetic',instance_id='own:1',record=dict(identity='Charizard',form='base',verified=True,evidence=[{'kind':'synthetic binding'}],observed_stats={'speed':121}))
    o=execution(observation());o['context']['actions']['own']['move']='pokeapi:move:53';o['context']['actions']['opponent']['move']='pokeapi:move:53'
    relation=r['relations'][0];review=dict(verified=True,sources=o['provenance'],origin='synthetic',context=o['context'],verification=o['verification'],stat_epoch='initial',execution_model=o['execution_model'])
    updated=analyse(r,builds,profile=REFERENCE,comparisons={relation['id']:review})
    assert updated['speed']['eligible_updates']==1
    assert r['actions']==reconstruct(p,s)['actions']  # Reanalysis never rewrites extraction.
    assert updated['actions'][0]['instance_id']=='own:1'
    assert updated['speed']['posteriors'][0]['summary']['probability_sum']==pytest.approx(1)


def test_reviewed_team_video_transcription_matches_existing_calculator():
    t=TeamConfiguration.load('tests/fixtures/battle_evidence/sample-team7-reviewed.json')
    assert t.data['complete'];assert t.data['binding_policy']['asserted_by']=='user'
    for m in t.data['members']:
        f=m['fields'];points={s:f['allocation_'+s+'_display']['value'] for s in STATS}
        calc=ChampionsStats(f['identity']['canonical_id'],form='as_named').calculate(points,m['reviewed_stat_alignment'])
        assert calc['stats']=={s:f[s]['value'] for s in STATS}


def test_unconfirmed_roster_does_not_bind():
    p,s,_=synthetic_input();r=reconstruct(p,s);t=TeamConfiguration.load('tests/fixtures/battle_evidence/sample-team7-reviewed.json')
    b,status=bind_team(r,t,[]);assert not b.records;assert status['status']=='unbound'


def test_conservative_group_uses_only_one_pair_and_keeps_relations():
    p,s,_=synthetic_input();ledger=p['reconstruction']['ledger']
    extra=deepcopy(ledger[0]);extra.update(id='event:2',underlying_action_id='event:2',timestamp=12,position=2,
        instance_id='own:2',binding={'pokemon_instance_id':'own:2'})
    ledger.append(extra);p['reconstruction']['assignment']['event:2']=deepcopy(p['reconstruction']['assignment']['event:0'])
    s['event:2']=deepcopy(s['event:0']);s['event:2']['before']['observable']['pokemon']['own:2']=s['event:2']['before']['observable']['pokemon'].pop('own:1')
    r=reconstruct(p,s);assert len(r['relations'])==3
    builds=KnownBuilds()
    for pid in ('own:1','own:2'):
        builds.register(battle_id='synthetic',instance_id=pid,record=dict(identity='Charizard',form='base',verified=True,evidence=[{'kind':'synthetic binding'}],observed_stats={'speed':121}))
    reviews={}
    actions={a['id']:a for a in r['actions']}
    for relation in r['relations']:
        pair=[actions[x] for x in relation['action_ids']]
        if {a['side'] for a in pair}!={'self','opponent'}:continue
        own=next(a for a in pair if a['side']=='self');o=execution(observation());o['context']['own']['instance_id']=own['instance_id']
        for role in ('own','opponent'):o['context']['actions'][role]['move']='pokeapi:move:53'
        reviews[relation['id']]=dict(verified=True,sources=o['provenance'],origin='synthetic',context=o['context'],verification=o['verification'],stat_epoch='initial',execution_model=o['execution_model'])
    updated=analyse(r,builds,profile=REFERENCE,comparisons=reviews)
    assert updated['speed']['eligible_updates']==1
    assert len(updated['relations'])==3
    assert any(x['quantitative_status']=='dependent_relation_omitted' for x in updated['relations'])


def test_switch_and_effect_messages_do_not_fabricate_actions():
    p,s,_=synthetic_input();ledger=p['reconstruction']['ledger'];switch=deepcopy(ledger[0])
    switch.update(id='switch',kind='switch',source_event_type='switch_out',timestamp=10.5,position=.5,text='喷火龙，回来！')
    ledger.append(switch);r=reconstruct(p,s)
    assert len(r['actions'])==2
    assert r['actions'][0]['instance_id']=='own:1'
    assert r['relations'][0]['intervening_event_ids']==['switch']
    assert any(e['category']=='switching' for e in r['non_actions'])


@pytest.mark.local_artifacts
def test_cached_real_action_reports_and_manifest_reuse_preserve_sources():
    from battle_evidence.action_offline import run
    from speed_inference.offline import file_hash
    index=Path('.cache/m341-actions/battle-index.json')
    if not index.exists():pytest.skip('Optional real-battle action experiment absent')
    rows=json.loads(index.read_text());assert len(rows)==8
    for row in rows:
        path=Path(row['result']);saved=json.loads(path.read_text());manifest=json.loads(path.with_name('manifest.json').read_text())
        assert manifest['status']=='complete'
        for source,sha in manifest['identity']['inputs'].items():assert file_hash(source)==sha
        for output,sha in manifest['outputs'].items():assert file_hash(path.parent/output)==sha
        n=int(row['battle_id'].rsplit('_',1)[1]);again=run(n)
        assert again['reused'] and again['result']==str(path)
        assert saved['speed']['eligible_updates']==0  # Measured current audit, not an inference guarantee.
        assert saved['speed']['information_gain_nats']==0
        assert saved['build_binding']['status']==('unbound' if n==5 else 'user_confirmed_roster_bound')
