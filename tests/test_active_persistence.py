"""M2.3.8-U portable, prefix-local occupancy regressions; no media access."""
from dataclasses import asdict
import pytest
from tracking.evidence_fusion import episode_hud, context_supported
from tracking.state_engine import event_from_dict
from tests.test_switch_continuity import engine as previous_engine, apply_text
from tests.test_evidence_fusion import hud, active, species


def engine():
    e = previous_engine()
    e.initial.knowledge['active_persistence_v1'] = True
    e.replay()
    return e


def add(e, event):
    return e.apply(event, sequence=len(e.history)+1)


def opening(e):
    apply_text(e, 1, '上吧！钢铠鸦！龙头地鼠！')


@pytest.mark.parametrize('raw,confidence', [('', 0), ('_', .99), ('钢铠鸟', .96), ('钢铠鸦', .4)])
def test_failed_hud_does_not_revoke_entry_or_admit_identity_or_hp(raw, confidence):
    e = engine(); opening(e)
    pid = active(e, 'left').pokemon_instance_id
    r = add(e, hud(1, 2, 823, slot='left', mon=dict(raw_text=raw, confidence=confidence,
        resolution=dict(status='unresolved')), hp={'current':10,'maximum':100}))
    assert r.bindings['hud']['status'] == 'deferred'
    assert episode_hud(e.state, 'self', 'left', 2) is None
    assert not active(e, 'left').hp.current.known
    assert apply_text(e, 3, '钢铠鸦使出了守住！').application_status == 'applied_partial'
    assert active(e, 'left').pokemon_instance_id == pid


def test_partial_hud_updates_target_only_other_three_slots_persist():
    e = engine(); opening(e)
    for i, slot in enumerate(('left', 'right'), 1):
        add(e, hud(i, 2, 373 if slot=='left' else 903, side='opponent', slot=slot))
    before = {s:dict(t.active_slots) for s,t in e.state.sides.items()}
    add(e, hud(8, 20, 530, slot='right', hp={'current':50,'maximum':100}))
    assert {s:dict(t.active_slots) for s,t in e.state.sides.items()} == before
    assert not active(e,'left').hp.current.known
    assert apply_text(e, 30, '钢铠鸦使出了守住！').application_status == 'applied_partial'


def test_reliable_contradiction_survives_later_unreadable_hud_and_retraction():
    e = engine(); opening(e)
    # Strong, exact contradictory text but resolver cannot independently admit it.
    bad = species(373); bad['resolution']['status']='unresolved'
    add(e, hud(1, 2, 373, slot='left', mon=bad))
    add(e, hud(2, 3, 823, slot='left', mon=dict(raw_text='',confidence=0,resolution={})))
    assert episode_hud(e.state,'self','left',3)['timestamp'] == 2
    r = apply_text(e,4,'钢铠鸦使出了守住！')
    assert r.application_status == 'deferred'
    assert active(e,'left').species.value['species_id'] == 823
    add(e,hud(3,5,823,slot='left'))
    assert apply_text(e,6,'钢铠鸦使出了守住！').application_status == 'applied_partial'
    assert next(h for h in e.history if h.event['attributes'].get('observation_time')==4).application_status == 'deferred'
    e.retract('hud:1',reason='curated wrong HUD slot')
    assert next(h for h in e.history if h.event['attributes'].get('observation_time')==4).application_status == 'applied_partial'


def test_high_confidence_text_icon_disagreement_blocks_until_new_support():
    e=engine();opening(e)
    add(e,hud(1,2,823,slot='left',icon=dict(status='resolved',species_id=373)))
    assert episode_hud(e.state,'self','left',2)['status']=='conflicting'
    assert apply_text(e,3,'钢铠鸦倒下了！').application_status=='deferred'
    assert set(e.state.sides['self'].active_slots)=={'left','right'}


def test_missed_departure_new_supported_hud_observes_occupancy_without_inventing_switch():
    e=engine();opening(e);old=active(e,'left').pokemon_instance_id
    r=add(e,hud(1,10,373,slot='left'))
    assert active(e,'left').species.value['species_id']==373
    assert e.state.pokemon[old].location.knowledge=='unknown'
    assert r.bindings['hud']['occupancy_change']['cause'] is None
    assert not any(h.event['event_type']=='switch_out' for h in e.history)


def test_coverage_gap_blocks_even_when_no_hud_is_visible_then_new_observation_is_prospective():
    e=engine();opening(e)
    gap=hud(1,5,823).to_dict();gap.update(event_id='gap',event_type='coverage_observation',side='self')
    gap['attributes']=dict(battle_id='test',observation_time=5,start=2,status='gap',fields=['active_identity'])
    add(e,event_from_dict(gap))
    assert not context_supported(e.state,'self','left',6)
    assert apply_text(e,6,'钢铠鸦使出了守住！').application_status=='deferred'
    add(e,hud(2,7,823,slot='left'))
    assert apply_text(e,8,'钢铠鸦使出了守住！').application_status=='applied_partial'
    assert next(h for h in e.history if h.event['attributes'].get('observation_time')==6).application_status=='deferred'


@pytest.mark.parametrize('move', ['急速折返','抛下狠话','吼叫'])
def test_switching_move_announcement_never_executes_departure(move):
    e=engine();opening(e);old=dict(e.state.sides['self'].active_slots)
    apply_text(e,2,'钢铠鸦使出了'+move+'！')
    assert e.state.sides['self'].active_slots==old
    assert not e.state.sides['self'].vacant_slots
    assert all(not x.get('departure') for x in e.state.knowledge['active_entry_episodes'])


@pytest.mark.parametrize('departure',['钢铠鸦，回来！','钢铠鸦倒下了！'])
def test_departure_vacancy_survives_animation_and_replacement_without_hud(departure):
    e=engine();opening(e);right=active(e,'right').pokemon_instance_id
    apply_text(e,2,departure)
    assert e.state.sides['self'].vacant_slots==['left']
    r=apply_text(e,20,'上吧！暴飞龙！')
    assert r.application_status=='applied_candidate'
    assert active(e,'left').species.value['species_id']==373
    assert active(e,'right').pokemon_instance_id==right


def test_simultaneous_vacancies_do_not_guess_replacement_model_screen_position():
    e=engine();opening(e)
    apply_text(e,2,'钢铠鸦倒下了！');apply_text(e,3,'龙头地鼠，回来！')
    r=apply_text(e,4,'上吧！暴飞龙！',model_screen_position='left')
    assert r.application_status=='recorded_observation'
    assert not e.state.sides['self'].active_slots
    add(e,hud(1,5,373,slot='right'))
    assert set(e.state.sides['self'].active_slots)=={'right'}



@pytest.mark.parametrize('sid,expected', [(823,'agreement'),(373,'disagreement')])
def test_independent_cached_model_corroborates_entry_without_overriding_message(sid,expected):
    from battle_events.schema import Evidence
    e=engine();opening(e)
    entry=e.state.knowledge['active_entry_episodes'][0]
    ev=hud(20,2,sid).to_dict()
    ev.update(event_id='model',event_type='visual_observation',actor={'species_id':sid})
    ev['attributes']=dict(battle_id='test',source_kind='entry_model',entry_event_id=entry['entry_event_id'],
        observation_time=2,confidence=.99,screen_position='right')
    ev['evidence']=[asdict(Evidence('cached_entry_model','frame#2',['independent-model'],dict(timestamp=2)))]
    r=add(e,event_from_dict(ev))
    assert r.application_status=='recorded_observation'
    assert r.bindings['entry_model']['status']==expected
    assert active(e,'left').species.value['species_id']==823
    assert active(e,'right').species.value['species_id']==530
    assert (episode_hud(e.state,'self','left',2) is None)==(expected=='agreement')
    assert e.state.knowledge['active_entry_episodes'][0]['entry_evidence'] != r.bindings['entry_model']['evidence']


@pytest.mark.parametrize('fault',['unassociated','low_confidence','same_observation','future_entry'])
def test_model_requires_reliable_independent_prefix_local_entry_association(fault):
    from battle_events.schema import Evidence
    e=engine();opening(e);ep=e.state.knowledge['active_entry_episodes'][0]
    ev=hud(20,2,373).to_dict();ev.update(event_id='model',event_type='visual_observation',actor={'species_id':373})
    ev['attributes']=dict(battle_id='test',source_kind='entry_model',entry_event_id=ep['entry_event_id'],observation_time=2,confidence=.99)
    ids=['model']
    if fault=='unassociated':ev['attributes']['entry_event_id']='missing'
    if fault=='low_confidence':ev['attributes']['confidence']=.5
    if fault=='same_observation':ids=ep['entry_evidence']['sources'][0]['observation_ids']
    if fault=='future_entry':ev['attributes']['observation_time']=.5
    ev['evidence']=[asdict(Evidence('cached_entry_model','frame#2',ids,dict(timestamp=ev['attributes']['observation_time'])))]
    assert add(e,event_from_dict(ev)).application_status=='deferred'
    assert episode_hud(e.state,'self','left',3) is None
    assert len(e.state.pokemon)==2


def test_retained_identity_cannot_erase_contradiction_or_apply_hp():
    e=engine();source=hud(1,1,823,slot='left');add(e,source)
    bad=species(373);bad['resolution']['status']='unresolved'
    add(e,hud(2,2,373,slot='left',mon=bad))
    stale=hud(3,3,823,slot='left',hp={'current':50,'maximum':100})
    stale.attributes['identity_reused_from']=source.evidence[0].source_id
    r=add(e,stale)
    assert r.reason=='retained_hud_occupancy_uncertain'
    assert not active(e,'left').hp.current.known
    assert episode_hud(e.state,'self','left',3) is not None


def test_diagnostic_visibility_distinguishes_missing_unresolved_consistent_other_identity():
    from scripts.replay_m238u import visibility
    assert visibility({},'self:left')['status']=='hud_not_visible'
    row=dict(ui=dict(regions=[dict(region_id='own_active_1',visibility='visible')]),snapshot=dict(pokemon=[]))
    assert visibility(row,'self:left',823)['status']=='hud_visible_ocr_unresolved'
    row['snapshot']['pokemon']=[dict(slot='own_active_1',species=species(823))]
    assert visibility(row,'self:left',823)['status']=='hud_visible_consistent'
    assert visibility(row,'self:left',373)['status']=='hud_visible_supported_other_identity'


def test_diagnostic_orange_counts_exclude_zero_length_intervals():
    from scripts.replay_m238u import orange_counts,ORANGE
    rows={'self:left':[dict(start=1,end=3,status=ORANGE),dict(start=3,end=3,status=ORANGE),dict(start=3,end=6,status='supported_active')]}
    assert orange_counts(rows)=={'self:left':dict(intervals=1,seconds=2)}
