"""Arrival/placement is independent of species; identity upgrades are prospective."""
from copy import deepcopy
import pytest
from tests.test_switch_continuity import engine,trainers,apply_text
from tests.test_trainer_nickname_binding import visual_fixture
from tests.test_evidence_fusion import hud
from tracking.active_continuity import occupancy,current_episode
from tracking.state_engine import StateEngine


def arrival(*,vacancies=('right',),name='Pebble'):
    _,state,_=visual_fixture()
    state.knowledge.update(reliability_v1=True,reliability_v2=True,active_continuity_v1=True,
                           active_persistence_v1=True,command_reconciliation_v1=True)
    state.sides['opponent'].trainer=dict(status='accepted',display_name='Guest',observed_at=0,evidence=[dict(source='preview')])
    state.sides['opponent'].vacant_slots=list(vacancies)
    e=StateEngine(state);r=apply_text(e,1,f'Guest派出了{name}！')
    return e,r


def test_message_establishes_unknown_occupancy_without_any_hidden_facts():
    e,r=arrival();pid=e.state.sides['opponent'].active_slots['right'];p=e.state.pokemon[pid];ep=current_episode(e.state,pid)
    assert r.application_status=='applied_candidate'
    assert occupancy(e.state,'opponent','right')=='occupied_unidentified'
    assert ep['start']==1 and ep['display_reference']=='Pebble' and ep['species_resolution_time'] is None
    assert ep['entry_event_id']==r.event['event_id'] and ep['persistent_identity_status']=='unproven'
    assert all(not f.known for f in [p.species,p.original_identity,p.hp.current,p.major_status,p.ability.current,p.item.identity,p.current_types])
    assert not p.moves.executed and all(not f.known for f in p.hidden_configuration.values())
    assert e.decision_state()['sides']['opponent']['occupancy']['right']=='occupied_unidentified'
    assert e.evidence_projection(as_of=1)['occupancy']['opponent']['right']['occupancy']=='occupied_unidentified'


@pytest.mark.parametrize('vacancies',[(),('left','right')])
def test_ambiguous_placement_keeps_pending_arrival(vacancies):
    e,r=arrival(vacancies=vacancies)
    assert not e.state.sides['opponent'].active_slots
    assert occupancy(e.state,'opponent','right')=='placement_unresolved'
    assert len(e.state.pokemon)==1
    assert r.bindings['admissibility']['slot'] is False


@pytest.mark.parametrize('text,location',[('Guest换下了Pebble！','bench'),('对手的Pebble倒下了！','fainted')])
@pytest.mark.parametrize('vacancies',[('right',),('left','right')])
def test_departure_before_identity_closes_episode_without_inventing_species(text,location,vacancies):
    e,_=arrival(vacancies=vacancies);pid=next(iter(e.state.pokemon))
    r=apply_text(e,2,text)
    assert r.application_status=='applied_candidate'
    assert e.state.pokemon[pid].location.value['kind']==location and not e.state.pokemon[pid].species.known
    assert current_episode(e.state,pid) is None
    assert not e.state.sides['opponent'].active_slots


def test_two_independent_huds_resolve_existing_episode_and_keep_old_snapshot_unknown():
    e,r=arrival();pid=e.state.sides['opponent'].active_slots['right'];before=deepcopy(e.state.to_dict())
    _,_,event=visual_fixture()
    for t,frame in [(2,'frame1'),(3,'frame2')]:
        h=event(t,frame);h.attributes['battle_id']='test';e.apply(h,sequence=len(e.history)+1)
        if t==2:assert not e.state.pokemon[pid].species.known
    assert len(e.state.pokemon)==1 and e.state.sides['opponent'].active_slots['right']==pid
    ep=current_episode(e.state,pid)
    assert ep['start']==1 and ep['species_resolution_time']==3 and ep['species_id']==205
    assert before['pokemon'][pid]['species']['value'] is None
    assert before['knowledge']['active_entry_episodes'][-1]['species_resolution_time'] is None


def test_torto_style_opening_uses_existing_reviewed_order_without_guessing_species():
    from battle_events.schema import BattleEvent,Evidence
    e=engine();trainers(e)
    # This is the unknown member emitted by the established ordered-entry
    # adapter after independently verified opponent opening qualification.
    child=BattleEvent('opening-child','send_out','opponent',None,None,'Guest派出了钢铠鸦和Pebble！',{},None,
        [Evidence('video_message','opening',['opening-frame'],dict(timestamp=1))],.99,'uncertain',['actor_unresolved'],
        dict(observation_time=1,source_region_type='battle_message',slot='left',display_reference='Pebble',
             ordered_display_references=['钢铠鸦','Pebble'],side_basis=['explicit_preview_trainer_id_match']))
    r=e.apply(child,sequence=1)
    assert r.application_status=='applied_candidate'
    assert occupancy(e.state,'opponent','left')=='occupied_unidentified'
    assert occupancy(e.state,'opponent','right')=='placement_unresolved'
    pid=e.state.sides['opponent'].active_slots['left']
    assert current_episode(e.state,pid)['start']==1


def test_repeated_nickname_after_departure_is_new_episode_not_biological_merge():
    e,_=arrival();old=e.state.sides['opponent'].active_slots['right']
    apply_text(e,2,'Guest换下了Pebble！');apply_text(e,3,'Guest派出了Pebble！')
    assert e.state.sides['opponent'].active_slots['right']!=old
    assert len(e.state.pokemon)==2 and not any(p.species.known for p in e.state.pokemon.values())


def test_duplicate_provisional_names_do_not_bind_departure_to_arbitrary_instance():
    e,_=arrival(vacancies=('left','right'));apply_text(e,2,'Guest派出了Pebble！')
    assert len(e.state.pokemon)==2
    assert apply_text(e,3,'Guest换下了Pebble！').application_status=='deferred'


def test_w_resolves_species_on_same_instance_without_correction_or_history_rewrite():
    from tests.test_command_reconciliation import checkpoint
    e,_=arrival();pid=e.state.sides['opponent'].active_slots['right']
    c=checkpoint(sids=(823,530,373,903));r=e.apply(c,sequence=len(e.history)+1)
    outcome=r.bindings['command_reconciliation']['outcomes'][-1]
    assert outcome['previous_occupancy']=='occupied_unidentified' and outcome['status']=='identity_resolved'
    assert not outcome['corrected'] and e.state.sides['opponent'].active_slots['right']==pid
    assert current_episode(e.state,pid)['species_resolution_time']==5


def test_low_confidence_or_unknown_trainer_never_establishes_provisional_occupancy():
    e=engine();trainers(e)
    assert apply_text(e,1,'Stranger派出了Pebble！').application_status=='deferred'
    assert not e.state.pokemon


def test_low_confidence_known_trainer_stays_deferred():
    from recognition.event_report import video_events
    from tests.test_scrolling_semantics import row
    from tracking.state_engine import event_from_dict
    e=engine();trainers(e)
    event=video_events([row(1,'Guest派出了Pebble！')],[],'test')[-1]
    event['ocr_confidence']=.8
    assert e.apply(event_from_dict(event),sequence=1).application_status=='deferred'
    assert not e.state.pokemon


def test_incomplete_high_confidence_sendout_does_not_assert_arrival():
    e=engine();trainers(e)
    r=apply_text(e,1,'Guest派出了Peb')
    assert r.application_status=='deferred' and not e.state.pokemon


def test_duplicate_species_occupy_distinct_episodes_without_party_merge():
    from tests.test_command_reconciliation import checkpoint
    e,_=arrival();first=e.state.sides['opponent'].active_slots['right']
    e.apply(checkpoint(t=2),sequence=len(e.history)+1)
    assert e.state.pokemon[first].species.value['species_id']==903
    apply_text(e,3,'Guest换下了Pebble！');apply_text(e,4,'Guest派出了Stone！')
    second=e.state.sides['opponent'].active_slots['right']
    c=checkpoint(t=5,phase='second-entry');e.apply(c,sequence=len(e.history)+1)
    assert e.state.pokemon[second].species.value['species_id']==903
    assert e.state.pokemon[first].species.value['species_id']==903
    assert second!=first


def test_retraction_recomputes_occupancy_and_resolution_without_future_backfill():
    e,r=arrival();pid=e.state.sides['opponent'].active_slots['right']
    assert not e.state.pokemon[pid].species.known
    e.retract(r.event['event_id'],reason='incorrect announcement')
    assert not e.state.pokemon and not e.state.sides['opponent'].active_slots


def test_human_entry_model_reference_cannot_resolve_identity():
    from dataclasses import asdict
    from battle_events.schema import Evidence
    from tracking.state_engine import event_from_dict
    e,r=arrival();pid=e.state.sides['opponent'].active_slots['right']
    ev=hud(20,2,823).to_dict();ev.update(event_id='human-model',event_type='visual_observation',actor=dict(species_id=823))
    ev['attributes']=dict(battle_id='test',source_kind='entry_model',entry_event_id=r.event['event_id'],observation_time=2,confidence=.99,
                         classification=dict(status='accepted',evidence_kind='human_reference',species_id=823))
    ev['evidence']=[asdict(Evidence('cached_entry_model','frame#2',['different-frame'],dict(timestamp=2)))]
    assert e.apply(event_from_dict(ev),sequence=len(e.history)+1).application_status=='deferred'
    assert not e.state.pokemon[pid].species.known


def test_forced_departure_observation_ends_provisional_episode_before_replacement():
    e,_=arrival();old=e.state.sides['opponent'].active_slots['right']
    # An observed departure can be marked forced; a Roar execution alone is
    # deliberately insufficient to infer its unobserved success.
    apply_text(e,2,'Guest换下了Pebble！',forced=True)
    apply_text(e,3,'Guest派出了钢铠鸦！')
    assert e.state.sides['opponent'].active_slots['right']!=old
    assert current_episode(e.state,old) is None


@pytest.mark.local_artifacts
@pytest.mark.parametrize('battle',['sample_battle_5','sample_battle_6','sample_battle_7'])
def test_saved_replays_preserve_all_existing_pokemon_facts_under_justified_episode_ids(battle):
    import json
    from pathlib import Path
    root=Path('.cache/battles')/battle;target=root/'evaluation/m238-provisional-entry-v2'
    if not (target/'manifest.json').exists():pytest.skip('Optional completed saved-entry validation absent')
    manifest=json.loads((target/'manifest.json').read_text());assert manifest['status']=='complete'
    baseline='evaluation/m238-final-acceptance-v1/replay.json' if battle=='sample_battle_7' else 'event-driven/m238-command-reconciliation-v2/replay.json'
    old=json.loads((root/baseline).read_text());new=json.loads((target/'replay.json').read_text())
    by_id={h['event']['event_id']:h for h in new['history']};assert set(by_id)=={h['event']['event_id'] for h in old['history']}
    mapping={}
    for h in old['history']:
        n=by_id[h['event']['event_id']];assert h['event']==n['event']
        if h['application_status'].startswith('applied'):assert n['application_status'].startswith('applied')
        for role in ['actor','target']:
            a=h['bindings'].get(role,{}).get('pokemon_instance_id');b=n['bindings'].get(role,{}).get('pokemon_instance_id')
            if a and b:
                if a in mapping:assert mapping[a]==b
                mapping[a]=b
    assert len(set(mapping.values()))==len(mapping)
    assert len(old['state']['pokemon'])==len(new['state']['pokemon'])
    for pid,p in old['state']['pokemon'].items():
        q=new['state']['pokemon'][mapping.get(pid,pid)]
        for field in ['hp','stages','item','ability','moves']:assert p[field]==q[field]
        for field in ['species','current_variant','major_status','fainted','current_types']:
            assert (p[field]['value'],p[field]['knowledge'])==(q[field]['value'],q[field]['knowledge'])
    for side,team in old['state']['sides'].items():
        assert {slot:mapping.get(pid,pid) for slot,pid in team['active_slots'].items()}==new['state']['sides'][side]['active_slots']
        assert team['conditions']==new['state']['sides'][side]['conditions']
