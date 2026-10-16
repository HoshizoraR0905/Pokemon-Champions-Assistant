"""Portable regressions for saved live-message semantics; no recognition calls."""
from copy import deepcopy
import pytest
from battle_events.parser import EventParser, BattleContext
from recognition.message_occurrences import MessageOccurrences
from recognition.visual_evidence import parse_popup
from recognition.event_report import video_events
from tests.test_event_driven import live_row
from tests.test_evidence_fusion import hud, active
from tracking.battle_state import BattleState
from tracking.state_engine import StateEngine, event_from_dict


def parse(text, region='battle_message', context=None):
    return EventParser().parse(dict(entry_id='x',source_id='frame',raw_text=text,
        ocr_confidence=.99,source_region_type=region),context,'test')


def row(t,text):
    r=live_row(t,text);r['sha256']=str(t)
    r['message']['rows']=[dict(text=x,confidence=.99,bounds=[0,i*30,500,(i+1)*30]) for i,x in enumerate(text.split('\n'))]
    return r


@pytest.mark.parametrize('prefix,side',[('','self'),('对手的','opponent')])
def test_complete_live_actor_grammar_keeps_same_species_sides(prefix,side):
    e=parse(prefix+'烈咬陆鲨使出了守住！')
    assert e.side==side and e.actor['species_id']==445
    assert parse('烈咬陆鲨使出了').event_type=='unknown'
    assert parse('烈咬陆鲨',region=None).side=='unknown'
    assert parse('烈咬陆鲨使出了守住！',region=None).side=='unknown'


@pytest.mark.parametrize('middle', [False,True])
def test_overlapping_three_rows_preserve_both_recipients_without_backdating(middle):
    group=MessageOccurrences('test',source_occurrence_ids=True)
    first='对手的赛富豪和\n对手的轰擂金刚猩的'
    assert not group.observe(row(1,first))['events']
    if middle:assert not group.observe(row(1.5,'对手的轰擂金刚猩的'))['events']
    result=group.observe(row(2,'对手的轰擂金刚猩的\n特攻降低了！'))
    assert len(result['events'])==2
    assert {e['actor']['species_id'] for e in result['events']}=={1000,812}
    assert all(e['side']=='opponent' and e['attributes']['observation_time']==2 for e in result['events'])
    assert all(e['attributes']['stats']==['special_attack'] for e in result['events'])
    assert {p['details']['timestamp'] for p in result['events'][0]['evidence']} >= {1,2}
    assert not group.observe(row(2.5,'对手的轰擂金刚猩的\n特攻降低了！'))['events']


@pytest.mark.parametrize('texts',[
 ['对手的烈咬陆鲨使出了守住！','烈咬陆鲨使出了守住！'],
 ['对手的烈咬陆鲨摆出了防守的架势！','烈咬陆鲨使出了守住！'],
 ['对对手的轰擂金刚猩效果绝佳！','对手的轰擂金刚猩倒下了！'],
 ['对手的赛富豪的特攻降低了！','对手的轰擂金刚猩的特攻降低了！']])
def test_distinct_semantics_are_not_duplicates(texts):
    g=MessageOccurrences('test',source_occurrence_ids=True)
    a=g.observe(row(1,texts[0])); b=g.observe(row(1.5,texts[1]))
    assert len(a['events'])==len(b['events'])==1
    assert a['occurrence']['id']!=b['occurrence']['id']
    assert not g.observe(row(2,texts[1]))['events']


def test_no_overlap_visibility_break_or_time_gap_never_concatenates():
    for mode in ('gap','hidden','unrelated'):
        g=MessageOccurrences('test',source_occurrence_ids=True)
        g.observe(row(1,'对手的赛富豪和\n对手的轰擂金刚猩的'))
        if mode=='hidden':
            r=row(1.5,'');r['message']['selected']=False;g.observe(r)
        text='对手的轰擂金刚猩的\n特攻降低了！' if mode!='unrelated' else '赛富豪使出了守住！'
        e=g.observe(row(4 if mode=='gap' else 2,text))['events']
        assert len(e)==1 and '和' not in e[0]['original_text']


@pytest.mark.parametrize('text,kind,side',[
 ('光墙使我方的特殊抗性提高了！','side_condition_change','self'),
 ('从我方身后吹起了顺风！','side_condition_change','self'),
 ('对手的轰擂金刚猩要回到Visitor的身边了！','switch_out','opponent'),
 ('长毛巨魔要回到Host的身边了！','switch_out','self'),
 ('对手的赛富豪的生命被少量削减了！','hp_change','opponent'),
 ('对对手的赛富豪效果不好','effectiveness','opponent'),
 ('烈咬陆鲨的烈咬陆鲨进化石Z和Host的全一环起了反应！','move_effect','self')])
def test_observed_vocabulary(text,kind,side):
    e=parse(text); assert (e.event_type,e.side)==(kind,side)
    if kind=='effectiveness':assert e.actor is None and e.target['species_id']==1000
    if kind=='hp_change':assert e.attributes['qualitative_only'] and 'after' not in e.attributes
    if kind=='move_effect':assert e.attributes['completed_transformation'] is False


def test_item_banner_is_not_an_ability_and_low_or_conflicting_reads_stay_unknown():
    readings={k:[dict(text=text,confidence=.99,config_id=v) for v in ('native','double')]
              for k,text in [('species','赛富豪的'),('ability','生命宝珠')]}
    p=parse_popup(readings)
    assert p['status']=='supported' and p['item']['name']=='生命宝珠' and p['ability'] is None
    r=row(1,'');r['occurrence_decision']['events']=[]
    r['visual']=dict(parsed=[dict(p,kind='popup',screen_edge='ability:right')])
    e=video_events([r],[],'test')[0]
    assert e['event_type']=='item_activation' and e['side']=='unknown'
    assert not e['attributes'].get('consumption_observed')
    bad=deepcopy(readings);bad['ability'][1]['text']='威吓'
    assert parse_popup(bad)['status']=='unresolved'
    bad=deepcopy(readings);bad['ability'][1]['confidence']=.5
    assert parse_popup(bad)['status']=='unresolved'


def test_explicit_multi_target_attack_drops_do_not_need_ability_order():
    for banner_first in (False,True):
        engine=StateEngine(BattleState('test',knowledge=dict(reliability_v1=True,reliability_v2=True,identity_v1=True)))
        engine.apply(hud(1,1,823,side='self',slot='left'),sequence=1)
        engine.apply(hud(2,1,530,side='self',slot='right'),sequence=2)
        engine.apply(hud(3,1,373,side='opponent',slot='left'),sequence=3)
        r=row(2,'钢铠鸦和龙头地鼠的\n攻击降低了！')
        events=video_events([r],[],'test')
        assert len(events)==2
        banner=parse('对手的暴飞龙的威吓').to_dict()
        banner['attributes'].update(observation_time=2,fusion_context=True,source_region_type='ability_banner')
        ordered=[banner,*events] if banner_first else [*events,banner]
        for i,e in enumerate(ordered,4):
            receipt=engine.apply(event_from_dict(e),sequence=i)
            assert receipt.application_status=='applied_candidate'
        assert all(len(active(engine,slot).stages['attack'].changes)==1 for slot in ('left','right'))


def test_hp_loss_retains_qualitative_observation_without_inventing_damage():
    engine=StateEngine(BattleState('test',knowledge=dict(reliability_v1=True,reliability_v2=True,identity_v1=True)))
    engine.apply(hud(1,1,823,side='opponent'),sequence=1)
    r=row(2,'对手的钢铠鸦的生命被少量削减了！')
    e=video_events([r],[],'test')[0];receipt=engine.apply(event_from_dict(e),sequence=2)
    assert receipt.application_status=='recorded_observation'
    p=active(engine,side='opponent')
    assert not p.hp.current.known
    assert p.hp.observations[-1]['cause'] is None


def test_light_screen_effect_observation_does_not_restart_existing_condition():
    engine=StateEngine(BattleState('test'))
    started=parse('光墙使我方的特殊抗性提高了！')
    started.attributes.update(change='start',observation_time=1)
    engine.apply(started,sequence=1)
    before=deepcopy(engine.state.sides['self'].conditions['light_screen'].initiated_by)
    observed=parse('光墙使我方的特殊抗性提高了！');observed.event_id='screen-observed';observed.attributes['observation_time']=2
    assert engine.apply(observed,sequence=2).application_status=='applied_candidate'
    assert engine.state.sides['self'].conditions['light_screen'].initiated_by==before


def test_weak_overlap_or_near_name_row_is_not_used_as_missing_recipient_proof():
    for weak in (False,True):
        g=MessageOccurrences('test',source_occurrence_ids=True)
        r=row(1,'对手的赛富豪和\n对手的轰擂金刚猩的')
        if weak:r['message']['confidence']=.5
        g.observe(r)
        text='对手的轰擂金刚猩的\n特攻降低了！' if weak else '对手的钢铠鸦的\n特攻降低了！'
        e=g.observe(row(1.5,text))['events']
        assert len(e)==1


def test_named_receiver_can_be_recorded_without_attacker_or_active_instance():
    engine=StateEngine(BattleState('test'))
    e=parse('对对手的赛富豪效果不好')
    assert engine.apply(e,sequence=1).application_status=='recorded_observation'
    assert not engine.state.pokemon


def test_mega_notice_trainer_conflict_is_not_resolved_by_actor_default():
    c=BattleContext();c.participants['opponent'].display_name='Visitor'
    e=parse('烈咬陆鲨的烈咬陆鲨进化石Z和Visitor的全一环起了反应！',context=c)
    assert e.side=='unknown' and 'trainer_name_conflict' in e.uncertainty


def test_same_species_move_binds_distinct_active_instances_and_missing_identity_stays_known_side():
    engine=StateEngine(BattleState('test',knowledge=dict(reliability_v1=True,reliability_v2=True,identity_v1=True)))
    engine.apply(hud(1,1,823,side='self'),sequence=1)
    engine.apply(hud(2,1,823,side='opponent'),sequence=2)
    events=video_events([row(2,'钢铠鸦使出了守住！'),row(3,'对手的钢铠鸦使出了守住！')],[],'test')
    bindings=[]
    for i,e in enumerate(events,3):
        receipt=engine.apply(event_from_dict(e),sequence=i)
        assert receipt.application_status=='applied_partial'
        bindings.append(receipt.bindings['actor']['pokemon_instance_id'])
    assert len(set(bindings))==2
    missing=video_events([row(4,'对手的烈咬陆鲨使出了守住！')],[],'test')[0]
    receipt=engine.apply(event_from_dict(missing),sequence=5)
    assert receipt.application_status=='deferred'
    assert receipt.bindings['resolved_event']['side']=='opponent'
    assert 'actor_instance_id' not in receipt.bindings['resolved_event']['attributes']
    assert len(engine.state.pokemon)==2


def test_saved_only_report_classification_separates_menu_noise_and_duplicates():
    from scripts.replay_m238s import classify_remaining
    rows=[row(0,'菜单标题'),row(1,'上吧！钢铠鸦！'),row(2,'x')]
    rows[2]['message']['confidence']=.2
    events=video_events([rows[1]],[],'test')
    history=[dict(event=e,bindings={},application_status='deferred',reason='unresolved_candidate_fields') for e in events]
    classified=classify_remaining(rows,history)
    assert classified[0]['category']=='prebattle_or_menu_irrelevant'
    assert classified[-1]['category']=='genuine_ocr_error_or_noise'


@pytest.mark.parametrize('later_hud',[False,True])
def test_new_observed_entry_supersedes_prebattle_hud_failure_but_not_later_failure(later_hud):
    engine=StateEngine(BattleState('test',knowledge=dict(reliability_v1=True,reliability_v2=True,identity_v1=True)))
    bad=dict(raw_text='0/4',confidence=.99,resolution={})
    engine.apply(hud(1,.1,823,slot='left',mon=bad),sequence=1)
    for i,e in enumerate(video_events([row(1,'上吧！钢铠鸦！龙头地鼠！')],[],'test'),2):
        engine.apply(event_from_dict(e),sequence=i)
    if later_hud:engine.apply(hud(9,1.5,823,slot='left',mon=bad),sequence=9)
    events=video_events([row(2,'钢铠鸦和龙头地鼠的攻击降低了！')],[],'test')
    receipts=[engine.apply(event_from_dict(e),sequence=i) for i,e in enumerate(events,10)]
    assert sum(r.application_status=='applied_candidate' for r in receipts)==(1 if later_hud else 2)


def test_visual_diagnostic_ocr_label_does_not_change_replay_inputs():
    from scripts.replay_m238s import classify_remaining
    r=row(2,'钢铠鸦超级进化成子钢铠鸦！');before=deepcopy(r)
    observation=dict(source_id=r['source_id'],category='genuine_ocr_error')
    classified=classify_remaining([r],[],dict(observations=[observation]))
    assert classified[0]['category']=='genuine_ocr_error'
    assert r==before


def test_punctuation_only_variations_of_complete_readings_are_one_occurrence():
    g=MessageOccurrences('test',source_occurrence_ids=True)
    assert len(g.observe(row(1,'对手的钢铠鸦的攻击降低了！'))['events'])==1
    assert not g.observe(row(1.5,'对手的钢铠鸦的攻击降低了'))['events']


def test_complete_self_actor_grammar_filters_opponent_alias_before_instance_binding():
    from battle_events.schema import Evidence
    engine=StateEngine(BattleState('test',knowledge=dict(reliability_v1=True,reliability_v2=True,identity_v1=True)))
    for i,side in enumerate(('self','opponent'),1):
        icon=dict(status='resolved',method='masked_multiscale_template',species_id=823,
                  candidates=[dict(species_id=823,similarity=.99)])
        engine.apply(hud(i,1,823,side=side,icon=icon),sequence=i)
    event=video_events([row(2,'钢铠鸦使出了守住！')],[],'test')[0]
    receipt=engine.apply(event_from_dict(event),sequence=3)
    assert receipt.application_status=='applied_partial'
    assert receipt.bindings['actor']['pokemon_instance_id']==active(engine,side='self').pokemon_instance_id
    assert all(a['side']=='self' for a in receipt.bindings['resolved_event']['attributes'].get('display_alias_evidence',[]))


@pytest.mark.parametrize('bad',['side','species','future'])
def test_report_binding_checks_distinguish_consistency_from_accuracy(bad):
    from scripts.replay_m238s import semantic_checks
    event=parse('钢铠鸦使出了守住！').to_dict();event['attributes']['observation_time']=2
    record=dict(event=event,bindings=dict(actor=dict(pokemon_instance_id='p')),application_status='applied_partial')
    state=dict(pokemon={'p':dict(side_id='self',species=dict(value=dict(species_id=823)),transformations=[])})
    new=dict(history=[record],state=state)
    assert semantic_checks(new)['independently_measured_identity_accuracy'] is None
    if bad=='side':state['pokemon']['p']['side_id']='opponent'
    elif bad=='species':state['pokemon']['p']['species']['value']['species_id']=530
    else:event['evidence'][0]['details']['timestamp']=3
    with pytest.raises(AssertionError):semantic_checks(new)
