"""Scoped 3/4 FPS multi-hit and verified team attachment contracts."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from battle_events.parser import EventParser
from recognition.resolution_sampling import adaptive_rates,dense_plans
from tracking.hp_causes import resolve_hits
from tracking.knowledge_grounding import attach_verified_profile,bind_attached_profile
from tracking.battle_state import Fact,fact
from tests.test_ditto_unnerve import initial,event,PROOF
from tests.test_sequential_resolution import Battle

CAP=dict(verification='champions_verified',hit_range=[2,2],sources=[dict(kind='synthetic_software_fixture')])


def samples(fps=3):
    values=[72,64,51,51,51,46,27,27,27]
    return [dict(time=i/fps,value=v,event_id=f'frame:{i}') for i,v in enumerate(values)]


@pytest.mark.parametrize('fps',[3,4])
def test_two_plateaus_at_local_rates_preserve_aggregate(fps):
    result=resolve_hits(samples(fps),sampling_fps=fps,capability=CAP,hit_count=2)
    assert result['per_hit_damage']==[21,24] and sum(result['per_hit_damage'])==45
    assert [(x['before'],x['after']) for x in result['hits']]==[(72,51),(51,27)]


def test_critical_notification_is_not_completion():
    result=resolve_hits(samples(),sampling_fps=3,capability=CAP,
                        critical_events=[dict(event_id='critical',hit_index=None)])
    assert result['hit_count'] is None and result['hits'] is None
    assert len(result['hit_candidates'])==2
    with_count=resolve_hits(samples(),sampling_fps=3,capability=CAP,hit_count=2,
                            critical_events=[dict(event_id='critical',hit_index=None)])
    assert with_count['per_hit_damage']==[21,24]
    assert all(h['critical_hit'] is None for h in with_count['hits'])
    assert 'critical_hit_hit_index_unknown' in with_count['reasons']


def test_single_animation_and_sparse_pts_do_not_manufacture_hits():
    sequence=[dict(time=i/3,value=v,event_id=str(i)) for i,v in enumerate([72,64,58,51,46,39,27,27,27])]
    assert resolve_hits(sequence,sampling_fps=3,capability=CAP,hit_count=2)['hits'] is None
    sparse=samples();sparse[4]['time']+=.2
    assert resolve_hits(sparse,sampling_fps=3,capability=CAP,hit_count=2)['hits'] is None


def test_critical_does_not_stop_parent_and_missing_count_stops_at_next_action():
    b=Battle(own=142);source=b.move('own','双翼')
    b.hp('foe',3,80);b.hp('foe',3.5,80)
    critical=b.send('击中了要害！',4)
    b.hp('foe',4.5,60);b.hp('foe',5,60)
    end=b.close(6)
    projection=b.result();parent=next(a for a in projection['actions'] if a['event_id']==source)
    ep=next(e for e in projection['episodes'] if e['source_event_id']==source)
    assert parent['completion_boundary']['event_id']==end
    assert ep['delta']==-40 and ep['hit_resolution']['hits'] is None
    assert ep['hit_resolution']['hit_count'] is None
    assert ep['hit_resolution']['completion_confirmed'] is False
    assert ep['hit_resolution']['completion_event_ids']==[]
    assert critical in ep['critical_event_ids']
    b.send('击中了2次！',7)  # belongs after the independent next action boundary
    assert next(e for e in b.result()['episodes'] if e['source_event_id']==source)['hit_resolution']['hit_count'] is None


def test_retrospective_boundaries_and_3_then_4_schedule():
    assert adaptive_rates(30,initial_fps=3,maximum_fps=4)==[3,4]
    b=Battle(own=142);b.move('own','双翼',2);b.hp('foe',3,80);b.hp('foe',3.5,80)
    b.send('击中了2次！',4);b.close(5)
    plan=dense_plans(b.e)[0]
    assert plan['start']==1 and plan['start']<plan['trigger_time'] and plan['end']==5
    assert plan['hit_event_ids'] and plan['sample_fps']==3


def test_only_verified_leading_baseline_carry_can_bridge_hidden_hud():
    sequence=samples()
    for value in sequence[1:]:value['time']+=8
    assert resolve_hits(sequence,sampling_fps=3,capability=CAP,hit_count=2)['hits'] is None
    assert resolve_hits(sequence,sampling_fps=3,capability=CAP,hit_count=2,baseline_carry_supported=True)['per_hit_damage']==[21,24]
    sequence[5]['time']+=.2
    assert resolve_hits(sequence,sampling_fps=3,capability=CAP,hit_count=2,baseline_carry_supported=True)['hits'] is None


def team_attachment(tmp_path):
    team=json.loads(Path('tests/fixtures/battle_evidence/sample-team7-reviewed.json').read_text())
    source=tmp_path/'preview.png';source.write_bytes(b'synthetic source fixture')
    review=dict(battle_id='synthetic',species_ids=[3,6,279,445,861,1018],matches_team7=True,
                reviewer='synthetic',image='preview.png',sha256=hashlib.sha256(source.read_bytes()).hexdigest(),observation_time=0)
    return team,review


def test_verified_profile_uses_existing_team_path_and_preserves_live_facts(tmp_path):
    parser=EventParser();s=initial(parser);team,review=team_attachment(tmp_path)
    s=attach_verified_profile(s,team,review,root=tmp_path);p=s.pokemon['pelipper']
    p.item.identity=fact(None,PROOF);p.item.status=fact('consumed',PROOF)
    p.ability.current=fact(dict(canonical_id='synthetic:modified_ability'),PROOF)
    from tracking.state_engine import event_from_dict
    bind_attached_profile(s,p,event_from_dict(event(parser,1,'send_out','pelipper')))
    fields=s.knowledge['team']['instances']['pelipper']['fields']
    assert fields['special_attack']['value']==115 and fields['speed']['value']==91
    assert len(p.moves.known_slots)==4
    assert p.item.identity.value is None and p.item.status.value=='consumed'
    assert p.ability.current.value['canonical_id']=='synthetic:modified_ability'


def test_profile_requires_complete_roster_source_and_user_policy(tmp_path):
    parser=EventParser();team,review=team_attachment(tmp_path)
    for variant in ['missing_species','changed_source','no_policy']:
        t=deepcopy(team);r=deepcopy(review)
        if variant=='missing_species':r['species_ids'].pop()
        elif variant=='changed_source':r['sha256']='wrong'
        else:t.pop('binding_policy')
        with pytest.raises(ValueError):attach_verified_profile(initial(parser),t,r,root=tmp_path)


def test_configured_and_visual_same_canonical_identity_corroborate():
    from tracking.reliability import visual_transition
    from tracking.state_engine import StateEngine,EventRecord,event_from_dict
    parser=EventParser();s=initial(parser)
    p=s.pokemon['pelipper'];p.ability.current=fact(dict(canonical_id='pokeapi:ability:2',name='降雨'),PROOF)
    engine=StateEngine(s)
    e=event(parser,1,'visual_observation','pelipper',attrs=dict(battle_id='synthetic',source_kind='selected_detail_panel',
        fields=dict(ability=dict(canonical_id='pokeapi:ability:2',name='降雨',species_id=None,knowledge_snapshot='synthetic'))))
    record=EventRecord(e,0,None)
    visual_transition(engine,s,event_from_dict(e),record)
    assert not s.conflicts and p.ability.current.known and len(p.ability.current.provenance)==2
    e['attributes']['fields']['ability']['canonical_id']='pokeapi:ability:127'
    visual_transition(engine,s,event_from_dict(e),record)
    assert s.conflicts and p.ability.current.knowledge=='conflicting'
