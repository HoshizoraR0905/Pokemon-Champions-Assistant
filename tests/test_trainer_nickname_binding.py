"""Trainer consensus and independent entry visual proof, without acquisition."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from recognition.trainers import aggregate_trainer
from tests.test_trainer_opening import trainer
from battle_events.parser import BattleContext, EventParser
from battle_events.schema import BattleEvent, Evidence
from tracking.battle_state import BattleState
from tracking.identity_ledger import entry_visual_support


def parse(text,context=None):
    return EventParser().parse(dict(entry_id=text,raw_text=text,source_region_type='battle_message',
        ocr_confidence=.99),context,'test')


def observation(raw,t,confidence=.99):
    o=trainer(raw,confidence,t=t);o['evidence'][0]['sha256']=str(t)
    return o


def test_short_ids_require_distinct_frames_and_do_not_rewrite_ambiguous_glyphs():
    first=observation('J',1)
    c=aggregate_trainer(None,first)
    assert c['status']=='unresolved'
    assert aggregate_trainer(c,first)['status']=='unresolved'
    c=aggregate_trainer(c,observation('J',2))
    assert c['status']=='accepted' and c['display_name']=='J'
    c=aggregate_trainer(c,observation('1',3,.88))
    assert c['status']=='accepted' and c['display_name']=='J'
    assert set(c['candidates'])=={'j','1'} and len(c['observations'])==3
    assert aggregate_trainer(c,observation('1',4))['status']=='conflicting'


def test_multiple_crops_are_one_frame_and_single_bad_read_cannot_replace_consensus():
    o=observation('X',1);o['readings']=[dict(raw_text='X',ocr_confidence=.99)]*3
    assert aggregate_trainer(None,o)['status']=='unresolved'
    c=aggregate_trainer(None,observation('Visitor',1))
    c=aggregate_trainer(c,observation('Visitor',2))
    assert aggregate_trainer(c,observation('Other',3,.8))['display_name']=='Visitor'
    assert aggregate_trainer(c,observation('Other',3))['status']=='conflicting'


@pytest.mark.parametrize('text', ['Stranger派出了钢铠鸦！','Stranger换下了钢铠鸦！',
    '对手的钢铠鸦要回到Stranger的身边了！'])
def test_unknown_trainer_cannot_borrow_opponent_species_owner(text):
    c=BattleContext();c.active['opponent'].add('pokeapi:species:823')
    assert parse(text,c).side=='unknown'


def test_same_nickname_same_species_on_both_sides_uses_complete_literal_grammar():
    c=BattleContext()
    for side in ('self','opponent'):
        c.active[side].add('pokeapi:species:823')
        c.display_aliases['Mirror'+(' ' if side=='self' else '  ')]=dict(side=side,
            identity=dict(canonical_id='pokeapi:species:823',species_id=823,name='钢铠鸦'),
            instance_id=side,evidence=[dict(source='independent_icon')])
    for prefix,side in [('', 'self'),('对手的','opponent')]:
        e=parse(prefix+'Mirror使出了守住！',c)
        assert e.side==side and e.actor['species_id']==823
        assert {a['instance_id'] for a in e.attributes['display_alias_evidence']}=={side}
    assert parse('Mystery使出了守住！').side=='self'
    assert parse('Mirror使出了',c).side=='unknown'


def visual_fixture():
    state=BattleState('test',knowledge=dict(identity_v1=True,identity_ledger=dict(aliases=[],entries=[],roster=[
        dict(side='opponent',preview_row=i+1,status='resolved',species_id=sid,evidence=dict(timestamp=0))
        for i,sid in enumerate([205,448,115,350,302,937])])))
    entry=BattleEvent('entry','entry_observation','opponent',None,None,'Guest派出了获奖的Pebble和Mirror！',{},None,
        [Evidence('video_message','opening',['opening'],dict(timestamp=1))],.99,'supported',[],
        dict(observation_time=1,ordered_display_references=['获奖的Pebble','Mirror']))
    engine=SimpleNamespace(history=[SimpleNamespace(event=entry.to_dict(),bindings={},retracted=False)])
    def event(t=2,frame='frame1',sid=205):
        return BattleEvent(str(t),'hud_observation','opponent',None,None,'HUD',{},None,
            [Evidence('video_hud',str(t),[frame],dict(timestamp=t))],None,'supported',[],
            dict(observation_time=t,slot='right',species=dict(raw_text='Pebble',confidence=.99,
                resolution=dict(method='icon_only',species_id=sid)),
                icon=dict(status='resolved',species_id=sid,candidates=[dict(species_id=sid,similarity=.84)])))
    return engine,state,event


def test_entry_support_needs_independent_frames_and_never_selects_species_from_roster():
    engine,state,event=visual_fixture()
    assert entry_visual_support(engine,state,event()) is None
    assert entry_visual_support(engine,state,event(3)) is None # same frame
    proof=entry_visual_support(engine,state,event(4,'frame2'))
    assert proof['identity']['species_id']==205 and proof['raw_nickname']=='Pebble'
    assert proof['entry_event_id']=='entry' and not proof['selected_party_membership_proven']
    assert proof['identity']['identity_status']=='species_only'
    engine,state,event=visual_fixture()
    assert entry_visual_support(engine,state,event(sid=823)) is None
    assert not state.knowledge['identity_ledger'].get('entry_visual_observations')


@pytest.mark.parametrize('invalid', ['missing_roster','future_entry','wrong_slot','reused','conflicting_visual'])
def test_entry_support_abstains_on_incomplete_or_competing_proofs(invalid):
    engine,state,event=visual_fixture();first=event();second=event(4,'frame2')
    if invalid=='missing_roster':state.knowledge['identity_ledger']['roster'].pop()
    if invalid=='future_entry':engine.history[0].event['attributes']['observation_time']=10
    if invalid=='wrong_slot':first.attributes['slot']=second.attributes['slot']='left'
    if invalid=='reused':first.attributes['identity_reused_from']=second.attributes['identity_reused_from']='cached'
    assert entry_visual_support(engine,state,first) is None
    if invalid=='conflicting_visual':
        second.attributes['icon']['species_id']=448;second.attributes['icon']['candidates'][0]['species_id']=448
        second.attributes['species']['resolution']['species_id']=448
    assert entry_visual_support(engine,state,second) is None


def test_single_announced_replacement_needs_unique_vacancy_and_two_independent_frames():
    engine,state,event=visual_fixture()
    entry=engine.history[0].event
    entry.update(event_type='send_out',original_text='Guest派出了获奖的Pebble！')
    entry['attributes']['ordered_display_references']=['获奖的Pebble']
    state.sides['opponent'].vacant_slots=['right']
    assert entry_visual_support(engine,state,event()) is None
    assert entry_visual_support(engine,state,event(3)) is None
    proof=entry_visual_support(engine,state,event(4,'frame2'))
    assert proof['identity']['species_id']==205
    assert proof['prospective_only'] and not proof['historical_entry_applied']
    assert proof['established_at']==4


def test_single_replacement_establishes_current_identity_without_rewriting_announcement():
    from tracking.state_engine import StateEngine
    from tests.test_switch_continuity import apply_text
    _,state,event=visual_fixture()
    state.knowledge.update(reliability_v1=True,reliability_v2=True,active_continuity_v1=True)
    state.sides['opponent'].trainer=dict(status='accepted',display_name='Guest',observed_at=0,
                                       evidence=[dict(source='preview')])
    state.sides['opponent'].vacant_slots=['right']
    engine=StateEngine(state)
    announcement=apply_text(engine,1,'Guest派出了Pebble！')
    assert announcement.application_status=='applied_candidate'
    provisional_id=announcement.bindings['actor']['pokemon_instance_id']
    for t,frame in [(2,'frame1'),(3,'frame2')]:
        hud=event(t,frame);hud.attributes['battle_id']='test'
        engine.apply(hud,sequence=len(engine.history)+1)
    pid=engine.state.sides['opponent'].active_slots['right']
    assert pid==provisional_id
    assert engine.state.pokemon[pid].species.value['species_id']==205
    assert next(h for h in engine.history if h.event['event_id']==announcement.event['event_id']).application_status=='applied_candidate'
    move=apply_text(engine,4,'对手的Pebble使出了守住！')
    assert move.application_status=='applied_partial'


@pytest.mark.parametrize('invalid',['two_vacancies','occupied','wrong_side','low_confidence','future_order','retracted'])
def test_single_replacement_abstains_without_unambiguous_prefix_proof(invalid):
    engine,state,event=visual_fixture();h=engine.history[0]
    h.event['event_type']='send_out'
    h.event['attributes']['ordered_display_references']=['获奖的Pebble']
    state.sides['opponent'].vacant_slots=['right']
    h.ordering=dict(domain='sequence',key=[1])
    record=SimpleNamespace(ordering=dict(domain='sequence',key=[2]))
    if invalid=='two_vacancies':state.sides['opponent'].vacant_slots=['left','right']
    if invalid=='occupied':state.sides['opponent'].active_slots['right']='existing'
    if invalid=='wrong_side':h.event['side']='unknown'
    if invalid=='low_confidence':h.event['ocr_confidence']=.5
    if invalid=='future_order':h.ordering['key']=[3]
    if invalid=='retracted':h.retracted=True
    assert entry_visual_support(engine,state,event(),record=record) is None
    assert entry_visual_support(engine,state,event(4,'frame2'),record=record) is None


@pytest.mark.parametrize('prefix,side',[('','self'),('对手的','opponent')])
@pytest.mark.parametrize('status,value',[('灼伤','burn'),('麻痹','paralysis'),('中毒','poison')])
def test_passive_status_actor_does_not_include_grammar_particle(prefix,side,status,value):
    e=parse(prefix+'钢铠鸦被'+status+'了！')
    assert e.event_type=='status_change' and e.side==side
    assert e.actor['species_id']==823
    assert e.attributes['status']==value
    from tests.test_switch_continuity import engine,apply_text
    from tests.test_evidence_fusion import hud,active
    state=engine();state.apply(hud(1,1,823,side=side),sequence=1)
    receipt=apply_text(state,2,prefix+'钢铠鸦被'+status+'了！')
    assert receipt.application_status=='applied_candidate'
    assert active(state,side=side).major_status.value==value


def test_saved_status_reference_is_reparsed_from_original_text():
    from tests.test_switch_continuity import engine
    from tests.test_evidence_fusion import hud,active
    from tests.test_scrolling_semantics import row
    from recognition.event_report import video_events
    from tracking.state_engine import event_from_dict
    state=engine();state.apply(hud(1,1,823),sequence=1)
    event=video_events([row(2,'钢铠鸦被灼伤了！')],[],'test')[-1]
    event['attributes']['actor_display_reference']='钢铠鸦被'
    receipt=state.apply(event_from_dict(event),sequence=2)
    assert receipt.application_status=='applied_candidate'
    assert active(state).major_status.value=='burn'


@pytest.mark.parametrize('name,condition,kind',[('反射壁','reflect','物理'),('光墙','light_screen','特殊')])
@pytest.mark.parametrize('label,side',[('我方','self'),('对手','opponent'),('对方','opponent')])
def test_explicit_screen_activation_precedes_generic_stat_parsing(name,condition,kind,label,side):
    text=f'{name}使{label}的{kind}抗性提高了！'
    e=parse(text)
    assert e.event_type=='side_condition_change' and e.side==side
    assert e.attributes['condition']==condition and e.attributes['change']=='observe'
    from tests.test_switch_continuity import engine,apply_text
    state=engine();receipt=apply_text(state,2,text)
    assert receipt.application_status=='applied_candidate'
    effect=state.state.sides[side].conditions[condition]
    assert effect.active.value is True
    assert not effect.duration.remaining.known


def test_observed_trainer_prefix_routes_move_before_alias_lookup():
    c=BattleContext();c.participants['opponent'].display_name='Visitor'
    c.display_aliases['Pebble']=dict(side='opponent',identity=dict(canonical_id='pokeapi:species:205',species_id=205,name='佛烈托斯'),instance_id='opp',evidence=[dict(source='visual')])
    event=parse('Visitor的Pebble使出了守住！',c)
    assert event.side=='opponent' and event.actor['species_id']==205
    c.participants['self'].display_name='Visitor'
    assert parse('Visitor的Pebble使出了守住！',c).side=='unknown'


def test_clear_short_foreground_reads_survive_empty_low_confidence_panel_event():
    from recognition.event_report import video_events
    from tests.test_trainer_opening import preview
    from tests.test_event_driven import live_row
    from tracking.state_engine import StateEngine,event_from_dict
    rows=[]
    for t in (1,3):
        o=observation('',t,0);o['readings']=[dict(raw_text='',ocr_confidence=0),dict(raw_text='Q',ocr_confidence=.99)]
        r=live_row(t,'');r['ui'].update(phase='team_preview',confidence=.99);r['trainer_observations']=[o];rows.append(r)
    engine=StateEngine(BattleState('test',knowledge=dict(identity_v1=True)))
    for i,e in enumerate(video_events(rows,[],'test'),1):engine.apply(event_from_dict(e),sequence=i)
    claim=engine.state.sides['opponent'].trainer
    assert claim['status']=='accepted' and claim['display_name']=='Q'
    assert all(o['ocr_confidence']==0 for o in claim['observations'])
