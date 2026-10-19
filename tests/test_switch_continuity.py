"""M2.3.8-T: side-local active entries are separate from party continuity."""
from copy import deepcopy
import pytest
from battle_events.parser import EventParser,BattleContext
from battle_events.schema import BattleEvent,Evidence
from recognition.event_report import video_events
from tests.test_scrolling_semantics import row
from tests.test_evidence_fusion import hud,active,message
from tracking.battle_state import BattleState,fact
from tracking.state_engine import StateEngine,event_from_dict
from tracking.identity_ledger import remember_alias


def engine():
    return StateEngine(BattleState('test',knowledge=dict(identity_v1=True,reliability_v1=True,reliability_v2=True,active_continuity_v1=True)))


def parse(text,context=None,region='battle_message'):
    return EventParser().parse(dict(entry_id=text,raw_text=text,source_region_type=region,ocr_confidence=.99),context,'test')


def apply_text(e,t,text,**attrs):
    events=video_events([row(t,text)],[],'test');out=[]
    for ev in events:
        ev['attributes'].update(attrs)
        out.append(e.apply(event_from_dict(ev),sequence=len(e.history)+1))
    return out[-1]


def trainers(e):
    for side,name in [('self','Host'),('opponent','Guest')]:
        e.initial.sides[side].trainer=dict(status='accepted',display_name=name,observed_at=0,evidence=[dict(source='preview')])
    e.replay()


@pytest.mark.parametrize('text,side,name',[
 ('钢铠鸦，回来！','self','钢铠鸦'),('钢铠鸦要回到Host的身边了！','self','钢铠鸦'),
 ('Guest换下了钢铠鸦！','opponent','钢铠鸦'),('对手的钢铠鸦要回到Guest的身边了！','opponent','钢铠鸦')])
def test_withdrawals_use_observed_trainer_side_and_active_instance(text,side,name):
    e=engine();trainers(e)
    for i,s in enumerate(('self','opponent'),1):e.apply(hud(i,1,823,side=s,slot='left',icon=dict(status='resolved',species_id=823)),sequence=i)
    c=BattleContext();c.participants['self'].display_name='Host';c.participants['opponent'].display_name='Guest'
    parsed=parse(text,c);assert parsed.side==side and parsed.actor['species_id']==823
    old=active(e,slot='left',side=side).pokemon_instance_id
    receipt=apply_text(e,2,text)
    assert receipt.application_status=='applied_candidate'
    assert receipt.bindings['departure']['slot']=='left'
    assert 'left' not in e.state.sides[side].active_slots
    assert e.state.pokemon[old].location.value['kind']=='bench'
    assert 'left' in e.state.sides[side].vacant_slots
    assert 'left' in e.state.sides['opponent' if side=='self' else 'self'].active_slots


def test_unmatched_trainer_prefix_cannot_borrow_species_owner_and_conflicts_remain_unknown():
    c=BattleContext();c.participants['self'].display_name='Host';c.participants['opponent'].display_name='Guest'
    c.active['opponent'].add('pokeapi:species:823')
    assert parse('GuestExtra换下了钢铠鸦！',c).side=='unknown'
    assert parse('对手的钢铠鸦要回到Host的身边了！',c).side=='unknown'
    assert parse('钢铠鸦，回来！',c,region='menu').event_type=='unknown'
    assert parse('钢铠鸦倒下',c).side=='unknown'


def test_reentry_creates_fresh_entry_episode_without_species_only_party_merge():
    e=engine();e.apply(hud(1,1,823,side='self',slot='left',hp=dict(current=50,maximum=100)),sequence=1)
    old=active(e,slot='left').pokemon_instance_id
    apply_text(e,2,'钢铠鸦使出了守住！')
    apply_text(e,3,'钢铠鸦，回来！')
    receipt=apply_text(e,4,'上吧！钢铠鸦！')
    assert receipt.application_status=='applied_candidate'
    new=active(e,slot='left').pokemon_instance_id
    assert new!=old
    assert len(e.state.pokemon[old].moves.executed)==1
    assert not e.state.pokemon[new].moves.executed and not e.state.pokemon[new].hp.current.known
    assert e.state.pokemon[old].hp.observations
    assert receipt.bindings['entry_episode']['persistent_identity_status']=='unproven'
    assert old in receipt.bindings['entry_episode']['possible_prior_instance_ids']
    assert apply_text(e,5,'钢铠鸦使出了守住！').application_status=='applied_partial'
    assert apply_text(e,6,'钢铠鸦的攻击降低了！').application_status=='applied_candidate'
    assert apply_text(e,7,'钢铠鸦倒下了！').application_status=='applied_candidate'
    assert e.state.pokemon[new].fainted.value is True and 'left' not in e.state.sides['self'].active_slots


def test_explicit_individual_reentry_keeps_moves_and_status_but_starts_new_episode():
    e=engine();e.apply(hud(1,1,823,side='self',slot='left',hp=dict(current=50,maximum=100)),sequence=1)
    p=active(e,slot='left');old=p.pokemon_instance_id
    apply_text(e,2,'钢铠鸦使出了守住！')
    apply_text(e,2.5,'钢铠鸦麻痹了！')
    apply_text(e,3,'钢铠鸦，回来！')
    receipt=apply_text(e,4,'上吧！钢铠鸦！',actor_instance_id=old)
    assert receipt.application_status=='applied_candidate'
    assert active(e,slot='left').pokemon_instance_id==old
    assert len(active(e,slot='left').moves.executed)==1
    assert active(e,slot='left').major_status.value=='paralysis'
    assert len([x for x in e.state.knowledge['active_entry_episodes'] if x['instance_id']==old])==2


@pytest.mark.parametrize('side,prefix',[('self',''),('opponent','对手的')])
def test_faint_vacates_only_bound_side_and_never_fabricates_hp_zero(side,prefix):
    e=engine()
    for i,s in enumerate(('self','opponent'),1):e.apply(hud(i,1,823,side=s,slot='left'),sequence=i)
    old=active(e,slot='left',side=side).pokemon_instance_id
    r=apply_text(e,2,prefix+'钢铠鸦倒下了！')
    assert r.application_status=='applied_candidate'
    assert r.bindings['departure']['reason']=='faint'
    assert e.state.pokemon[old].fainted.value is True
    assert not e.state.pokemon[old].hp.current.known
    assert not e.state.sides[side].active_slots
    assert e.state.sides['opponent' if side=='self' else 'self'].active_slots
    replacement='上吧！龙头地鼠！' if side=='self' else 'Guest派出了龙头地鼠！'
    if side=='opponent':trainers(e)
    assert apply_text(e,3,replacement).application_status=='applied_candidate'
    assert active(e,slot='left',side=side).species.value['species_id']==530
    bad=apply_text(e,4,'上吧！钢铠鸦！' if side=='self' else 'Guest派出了钢铠鸦！',actor_instance_id=old,slot='right')
    assert bad.application_status in {'deferred','rejected'}
    assert e.state.pokemon[old].fainted.value is True


def test_stale_alias_cannot_mask_new_current_episode_faint():
    e=engine();parser=EventParser()
    e.apply(hud(1,1,823,slot='left'),sequence=1);old=active(e,slot='left').pokemon_instance_id
    remember_alias(e.initial,'钢铠鸦',parser.identity('钢铠鸦','species'),[dict(source='old')],side='self',instance_id=old)
    apply_text(e,2,'钢铠鸦，回来！')
    apply_text(e,3,'上吧！钢铠鸦！')
    new=active(e,slot='left').pokemon_instance_id
    r=apply_text(e,4,'钢铠鸦倒下了！')
    assert r.application_status=='applied_candidate'
    assert r.bindings['actor']['pokemon_instance_id']==new and new!=old
    assert not e.state.pokemon[old].fainted.known


def test_two_active_duplicate_species_cannot_be_chosen_by_name():
    e=engine()
    e.apply(hud(1,1,823,slot='left'),sequence=1);e.apply(hud(2,1,823,slot='right'),sequence=2)
    r=apply_text(e,2,'钢铠鸦倒下了！')
    assert r.application_status=='deferred'
    assert r.bindings['resolved_event']['side']=='self'
    assert len(e.state.sides['self'].active_slots)==2
    assert all(not p.fainted.known for p in e.state.pokemon.values())


def test_two_vacancies_hold_entry_until_independent_hud_without_retroactive_binding():
    e=engine()
    e.apply(hud(1,1,823,slot='left'),sequence=1);e.apply(hud(2,1,530,slot='right'),sequence=2)
    apply_text(e,2,'钢铠鸦倒下了！');apply_text(e,2.5,'龙头地鼠，回来！')
    r=apply_text(e,3,'上吧！暴飞龙！')
    assert r.application_status=='recorded_observation' and not e.state.sides['self'].active_slots
    assert e.state.pokemon[r.bindings['actor']['pokemon_instance_id']].location.value['slot'] is None
    e.apply(hud(9,4,373,slot='right'),sequence=len(e.history)+1)
    assert set(e.state.sides['self'].active_slots)=={'right'}
    assert r.bindings['entry_episode']['slot'] is None


def test_retained_hud_from_earlier_episode_cannot_update_explicit_reentry():
    e=engine();source=hud(1,1,823,slot='left')
    e.apply(source,sequence=1);old=active(e,slot='left').pokemon_instance_id
    apply_text(e,2,'钢铠鸦，回来！');apply_text(e,3,'上吧！钢铠鸦！',actor_instance_id=old)
    stale=hud(9,4,823,slot='left',hp=dict(current=9,maximum=100));stale.attributes['identity_reused_from']=source.evidence[0].source_id
    r=e.apply(stale,sequence=len(e.history)+1)
    assert r.application_status=='deferred' and 'episode' in r.reason
    assert not active(e,slot='left').hp.current.known


def test_multiple_pending_same_species_hud_does_not_choose_one_or_create_third():
    e=engine()
    apply_text(e,1,'上吧！钢铠鸦！')
    apply_text(e,2,'上吧！钢铠鸦！')
    assert len(e.state.pokemon)==2
    r=e.apply(hud(9,3,823,slot='left'),sequence=len(e.history)+1)
    assert not e.state.sides['self'].active_slots and len(e.state.pokemon)==2
    assert r.bindings['hud']['occupancy_status']=='unresolved_multiple_entry_episodes'


def test_verified_complete_party_reuses_unique_individual_but_not_duplicate_species():
    for duplicate in (False,True):
        e=engine();e.apply(hud(1,1,823,slot='left'),sequence=1)
        old=active(e,slot='left').pokemon_instance_id
        if duplicate:e.apply(hud(2,1,823,slot='right'),sequence=2)
        apply_text(e,2,'钢铠鸦，回来！',actor_instance_id=old)
        e.initial.sides['self'].party_complete=fact(True,{'source':'independent verified party fixture'})
        # Initial party membership must be independently supplied, not set on the current replay result.
        # Correct the synthetic initial fixture to include the observed party before replay.
        e.initial=deepcopy(e.state);e.history=[]
        e.initial.sides['self'].party_complete=fact(True,{'source':'independent verified party fixture'})
        r=apply_text(e,3,'上吧！钢铠鸦！')
        if duplicate:assert r.application_status=='deferred'
        else:assert r.application_status=='applied_candidate' and active(e,slot='left').pokemon_instance_id==old


@pytest.mark.parametrize('raw,icon_sid,admitted',[('钢铠鸦',None,True),('龙头地鼠',None,False),('钢铠鸦',530,False)])
def test_unconfirmed_matching_hud_is_not_a_new_identity_or_departure(raw,icon_sid,admitted):
    e=engine();apply_text(e,1,'上吧！钢铠鸦！龙头地鼠！')
    mon=dict(raw_text=raw,confidence=.99,resolution=dict(status='unresolved',method='literal_display_name_unidentified'))
    icon=dict(status='resolved',species_id=icon_sid) if icon_sid else {}
    h=e.apply(hud(9,2,823,slot='left',mon=mon,icon=icon),sequence=len(e.history)+1)
    assert h.bindings['hud']['status']=='deferred'
    r=apply_text(e,3,'钢铠鸦，回来！')
    assert (r.application_status=='applied_candidate')==admitted
    if not admitted:assert r.bindings['resolved_event']['side']=='self'


@pytest.mark.parametrize('prefix,side',[('','self'),('对手的','opponent')])
def test_faint_side_survives_unresolved_nickname_and_two_current_alias_candidates(prefix,side):
    e=engine();parser=EventParser()
    for i,(slot,sid) in enumerate([('left',823),('right',530)],1):
        e.apply(hud(i,1,sid,side=side,slot=slot),sequence=i)
        pid=active(e,side=side,slot=slot).pokemon_instance_id
        remember_alias(e.initial,'Shared',parser.identity('钢铠鸦' if sid==823 else '龙头地鼠','species'),
                       [{'source':'independent current fixture'}],side=side,instance_id=pid)
    receipt=apply_text(e,2,prefix+'Shared倒下了！')
    assert receipt.application_status=='deferred'
    assert receipt.bindings['resolved_event']['side']==side
    assert len(e.state.sides[side].active_slots)==2
    assert all(not p.fainted.known for p in e.state.pokemon.values())


def test_named_self_faint_does_not_borrow_opponent_nickname_even_if_only_one_is_known():
    e=engine();e.apply(hud(1,1,823,side='opponent',slot='left'),sequence=1)
    pid=active(e,side='opponent',slot='left').pokemon_instance_id
    remember_alias(e.initial,'Buddy',EventParser().identity('钢铠鸦','species'),[{'source':'opponent fixture'}],side='opponent',instance_id=pid)
    receipt=apply_text(e,2,'Buddy倒下了！')
    assert receipt.application_status=='deferred'
    assert receipt.bindings['resolved_event']['side']=='self'
    assert not e.state.pokemon[pid].fainted.known


def test_report_keeps_unknown_intervals_and_never_backdates_future_placements():
    from scripts.replay_m238t import intervals
    states=[dict(timestamp=0,event_id=None,slots={'self:left':dict(status='unknown')}),
            dict(timestamp=3,event_id='entry',slots={'self:left':dict(status='unknown')}),
            dict(timestamp=5,event_id='hud',slots={'self:left':dict(status='supported_active',instance_id='a')})]
    result=intervals(states,9)
    assert result['self:left'][0]['start']==0 and result['self:left'][0]['end']==5
    assert result['self:left'][1]['instance_id']=='a' and result['self:left'][1]['start']==5
    with pytest.raises(ValueError,match='Backdated'):intervals(list(reversed(states)),9)


def test_recorded_unplaced_arrival_is_an_unresolved_continuity_case_in_report():
    from scripts.replay_m238t import first_failure
    event=parse('上吧！钢铠鸦！').to_dict();event['attributes']['observation_time']=3
    history=[dict(event=event,application_status='recorded_observation',reason=None,
                  bindings=dict(admissibility=dict(identity=True,slot=False,continuity=False)))]
    diagnostic=first_failure(history)
    assert diagnostic[0]['cause']=='unplaced_entry_poisoning'
    assert diagnostic[0]['side']=='self'
