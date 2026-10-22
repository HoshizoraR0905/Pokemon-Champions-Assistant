"""Synthetic projection contracts plus separately marked recorded-frame receipts."""
from copy import deepcopy
from pathlib import Path
import json

import pytest

from battle_evidence.speed_replay_projection import normalize, visible_transaction, support_layers
from knowledge.stat_feasibility import summary
from speed_order.core import knowledge
from speed_order.forms import training_stats
from test_dynamic_action_order import action, participant, simulate, state

ROOT=Path(__file__).resolve().parents[1]


def synthetic(events, raw=None):
    replay=dict(battle_id='synthetic:projection', timeline=events, turns=[dict(turn_id='synthetic:turn',
        local_index=1,command_interval=[0,1],next_command_interval=[50,51],actions=[])])
    review=dict(origin='recorded',battles={replay['battle_id']:dict(sources={},transformations=[])})
    return normalize(replay,dict(snapshots={}),raw or {},review,root=ROOT)


def event(i,t,kind,actor='a',text=''):
    return dict(id=i,timestamp=t,kind=kind,instance_id=actor,side='opponent',text=text,sources=[])


def test_transaction_masks_future_arrival_identity_sources_and_interval():
    e=dict(timestamp=2,interval=[2,5],incoming=dict(species='future'),arrival_time=5,
        source_event_ids=['out','in'],arrival_source_event_id='in',sources=[dict(timestamp=2),dict(timestamp=5)])
    v=visible_transaction(e,3)
    assert v['incoming'] is None and v['arrival_time'] is None
    assert v['source_event_ids']==['out'] and v['interval']==[2,None]
    assert v['sources']==[dict(timestamp=2)]
    assert visible_transaction(e,5)['incoming']==dict(species='future')
    assert e['incoming']==dict(species='future')


def test_multiple_recalls_preserve_source_chronology_and_explicit_unknowns():
    events=[event('out1',2,'switch_out',text='换下了'),event('in1',3,'send_out','b'),
            event('out2',4,'switch_out','c','回来'),event('in2',5,'send_out','d')]
    timeline,audit=synthetic(events)
    assert [e['kind'] for e in timeline]==['voluntary_switch']*2
    assert [e['observed_phase_position'] for e in timeline]==[1,2]
    assert [e['timestamp'] for e in timeline]==[2,4]
    assert all(e['incoming']['species'] is None and e['incoming']['unresolved'] for e in timeline)
    assert not any(e['speed_comparable'] for e in timeline)


def test_failed_pivot_never_manufactures_replacement():
    raw={'failed':dict(canonical_references=dict(move=dict(canonical_id='pokeapi:move:575')),outcome='failed')}
    timeline,_=synthetic([event('failed',2,'move_execution',text='抛下狠话失败')],raw)
    assert [e['kind'] for e in timeline]==['executed_move']
    assert not any('incoming' in e or e.get('pivot_transaction_id') for e in timeline)


def test_pivot_requires_explicit_departure_and_stays_in_move_resolution():
    events=[event('move',2,'move_execution'),event('out',4,'switch_out',text='要回到训练家的身边了'),event('in',8,'send_out','b')]
    raw={'move':dict(canonical_references=dict(move=dict(canonical_id='pokeapi:move:575')))}
    rows,_=synthetic(events,raw)
    move,tx=rows
    assert tx['kind']=='pivot_replacement' and tx['phase']=='move_resolution'
    assert tx['pivot_move_id']=='move' and move['pivot_transaction_id']==tx['id']
    assert not tx['speed_comparable']
    assert visible_transaction(tx,5)['incoming'] is None


def test_two_support_layers_retain_full_item_alternatives_and_joint_builds():
    branches=[dict(item=i,speed=summary(v)) for i,v in [('none',[100,102]),('Raichunite Y',[120]),
        ('Choice Scarf',[140]),('Iron Ball',[150]),('Quick Claw',[160])]]
    full=dict(branches=branches,speed=summary([100,102,120,140,150,160]),configuration_count=6)
    observed=dict(speed=summary([100]),configuration_count=1)
    layers=support_layers(full,observed,complete_before=2,incomplete=3,empirical_rows=['joint:one'],conditions=['declared'],unresolved=['unsupported_branch'])
    assert set(layers)=={'observed','full','conditions'}
    assert layers['full']['speed']['has_gaps']
    assert layers['observed']['builds']==['joint:one']
    assert layers['observed']['incomplete_excluded']==3
    assert layers['full']['status']=='unresolved'
    assert layers['full']['speed']['values']==[100,102,120,140,150,160]


def test_switch_then_multiple_megas_then_moves_keep_phase_and_speed_order():
    participants=[participant(i,speed) for i,speed in [('s1',80),('s2',100),('m1',150),('m2',200),('a',250)]]
    acts=[dict(action('s1'),kind='voluntary_switch',move=None),dict(action('s2'),kind='voluntary_switch',move=None),
          dict(action('m1'),kind='mega_evolution',move=None),dict(action('m2'),kind='mega_evolution',move=None),action('a','Fake Out')]
    r=simulate(state(*participants),acts)
    assert r['status']=='exact'
    assert r['traces'][0]['sequence']==['s2:move','s1:move','m2:move','m1:move','a:move']


@pytest.fixture(params=[10,11,12])
def recorded(request):
    n=request.param;p=ROOT/f'.cache/battles/sample_battle_{n}/m322-reviewed-speed/latest.json'
    if not p.exists():pytest.skip('Optional historical recorded replay absent')
    pointer=json.loads(p.read_text());return json.loads(Path(pointer['path']).read_text())


@pytest.mark.local_artifacts
def test_recorded_every_occupant_edge_and_switch_source_is_accounted_for(recorded):
    d=recorded;assert 'transition_audit' in d
    assert d['transition_audit']['missed_occupant_edges']==0
    assert all(e['transaction_id'] or e['gaps'] for e in d['transition_audit']['occupant_edges'])
    covered={eid for e in d['action_timeline'] for eid in e.get('source_event_ids',[])}
    for e in d['timeline']:
        if e['kind'] in {'switch_out','send_out','transformation'}:assert e['id'] in covered
    for e in d['action_timeline']:
        if e['kind'] in {'voluntary_switch','pivot_replacement','forced_replacement','unresolved_transition'}:
            assert 'outgoing' in e and 'incoming' in e
            assert e['incoming'] is not None or e['unresolved']
        for s in e.get('sources',[]):
            assert (ROOT/s['image']).is_file()


def load_b11():
    p=ROOT/'.cache/battles/sample_battle_11/m322-reviewed-speed/latest.json'
    if not p.exists():pytest.skip('Optional Battle 11 replay absent')
    return json.loads(Path(json.loads(p.read_text())['path']).read_text())


def at(d,time):return [s for s in d['snapshots'] if s['timestamp']<=time][-1]


@pytest.mark.local_artifacts
def test_recorded_raichu_form_stone_training_and_causal_restoration():
    d=load_b11();iid='sample_battle_11:opponent:encounter:3a97ce2b12c2c2fe'
    before=deepcopy(at(d,147));p=before['opponents'][iid]
    assert p['species']=='pokeapi:species:26' and p['current_form'] is None
    assert all(not knowledge().facts['pokemon'][f]['upstream_name'].startswith('Mega ') for f in p['possible_forms'])
    assert 'No Guard' not in {b['ability'] for b in d['support_catalog'][p['support_ref']]['full']['branches']}
    assert at(d,148.525)['opponents'][iid]['observed_item']=='Raichunite Y'
    e=next(e for e in d['action_timeline'] if e['kind']=='mega_evolution' and e['individual']==iid)
    assert e['resulting_form']=='pokeapi:form:10530' and e['interval'][0]==148.525
    assert at(d,e['timestamp']-.001)['opponents'][iid]['current_form'] is None
    assert at(d,e['timestamp'])['opponents'][iid]['current_form']=='pokeapi:form:10530'
    current=at(d,e['timestamp'])['opponents'][iid]
    assert current['universe_ref']=='pokeapi:form:10530' and 'universe_refs' not in current
    assert 'current_form_unresolved' not in current['unresolved_reasons']
    assert current['configuration_count']==d['support_catalog'][current['support_ref']]['full']['configuration_count']
    assert at(d,502)['opponents'][iid]['current_form']=='pokeapi:form:10530'
    assert at(d,147)==before
    support=d['form_configuration_support'][e['id']]
    assert support['training_preserved'] and support['required_item']=='Raichunite Y'
    for c in support['configurations'][::100]:
        assert c['speed']==training_stats('pokeapi:form:10530',c['training'])['speed'][0]
        assert c['ability']=='No Guard' and c['item']=='Raichunite Y'
        assert c['original_form']=='pokeapi:species:26'


@pytest.mark.local_artifacts
def test_recorded_b11_switch_pivot_empirical_joint_builds_and_exact_gaps():
    d=load_b11();switch=next(e for e in d['action_timeline'] if e['timestamp']==210.00166666666667)
    assert switch['kind']=='voluntary_switch' and switch['outgoing']['species']=='pokeapi:species:637'
    assert switch['incoming']['species']=='pokeapi:species:727' and switch['arrival_time']==213.50333333333333
    assert all(a['timestamp']>switch['arrival_time'] for t in d['turns'] if t['turn_id']==switch['segment_id'] for a in t['actions'])
    assert switch['incoming']['individual'] not in at(d,211)['occupancy']['opponent']
    assert switch['incoming']['individual'] in at(d,214)['occupancy']['opponent']
    pivots=[e for e in d['action_timeline'] if e['kind']=='pivot_replacement'];assert len(pivots)==1
    assert pivots[0]['incoming']['species']=='pokeapi:species:637'
    assert pivots[0]['pivot_move_id']=='event:99a11f9b11c3a3f6fea9943e'
    late=[e for e in d['action_timeline'] if e['kind']=='voluntary_switch' and e['timestamp']>560]
    assert len(late)==2 and all(e['segment_id'] is None and e['membership_gap'] for e in late)
    assert [e['observed_phase_position'] for e in late]==[1,2]
    p=at(d,200)['opponents']['sample_battle_11:opponent:encounter:d44d3edfc6ac6181'];support=d['support_catalog'][p['support_ref']]
    assert set(support)=={'observed','full','conditions'}
    assert support['full']['speed']==d['reviewed_inference']['updates'][0]['after']['volcarona']['speed']
    assert support['observed']['complete_after']==29 and len(support['observed']['builds'])==29
    assert support['observed']['incomplete_excluded']==48
    for bid in support['observed']['builds']:
        row=d['observed_builds'][bid]
        assert row['complete'] and row['alignment'] is not None and row['speed_sp'] is not None
        assert row['item'] and row['ability'] and row['publications'] and row['configuration']
