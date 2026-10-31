"""Production message parser → StateEngine → sequential resolution projection.

Synthetic timelines verify contracts, not real-video multi-hit/causal accuracy.
"""
from copy import deepcopy
import pytest
from recognition.message_occurrences import MessageOccurrences
from tracking.state_engine import StateEngine,EventRecord,ordering,hash_state
from tracking.battle_state import BattleState
from tests.test_evidence_fusion import hud
from speed_order.core import knowledge


class Battle:
    def __init__(self, own=768, foe=445, ally=None):
        self.e=StateEngine(BattleState('test'));self.mon={};self.n=0
        for key,sid,side,slot in [('own',own,'self','right'),('foe',foe,'opponent','right')]+([('ally',ally,'self','left')] if ally else []):
            name=knowledge().entities[f'pokeapi:species:{sid}'].label(True)
            self.mon[key]=dict(sid=sid,name=name,side=side,slot=slot)
            self.hp(key,1.,100)
    def hp(self,key,t,value,*,batch=False):
        m=self.mon[key];self.n+=1
        mon=dict(raw_text=m['name'],confidence=.99,resolution=dict(status='resolved',method='exact',
            species_id=m['sid'],confidence='strong',canonical_identity=f'pokeapi:pokemon:{m["sid"]}',identity_status='resolved_unique'))
        e=hud(self.n,t,m['sid'],side=m['side'],slot=m['slot'],mon=mon,
              hp=dict(current=value,maximum=200) if m['side']=='self' else value)
        if batch:self.e.history.append(EventRecord(e.to_dict(),len(self.e.history),ordering(e,sequence=self.n)))
        else:self.e.apply(e,sequence=self.n)
        return e.event_id
    def send(self,text,t,*,allow_deferred=False,attributes=None):
        row=dict(timestamp=t,sha256=str(t)+text,source_id=f'test.mp4#{t}',image='synthetic.png',
                 message=dict(selected=True,source_region_type='battle_message',raw_text=text,confidence=.99))
        events=MessageOccurrences('test').observe(row)['events'];assert events
        for event in events:
            if attributes:event['attributes'].update(attributes)
            self.n+=1;r=self.e.apply(event,sequence=self.n)
            if not allow_deferred:assert r.application_status in {'applied_candidate','applied_partial','recorded_observation'},(text,r.reason)
        return events[-1]['event_id']
    def move(self,key,move,t=2.):
        m=self.mon[key];return self.send(('对手的' if m['side']=='opponent' else '')+m['name']+'使出了'+move+'！',t)
    def close(self,t=20.):return self.move('foe','守住',t)
    def pid(self,key):
        m=self.mon[key]
        return next(pid for pid,p in self.e.state.pokemon.items() if p.side_id==m['side'] and p.species.value and p.species.value['species_id']==m['sid'])
    def result(self,**options):return self.e.hp_resolutions(**options)


def test_weather_ball_hud_target_then_stamina_defense_is_one_parent_action():
    b=Battle(own=6,foe=1018);source=b.move('own','气象球')
    b.hp('foe',3.,64);b.hp('foe',3.5,13)
    banner=b.send('对手的铝钢桥龙的持久力！',4.)
    b.send('对手的铝钢桥龙的防御提高了！',4.5)
    b.hp('foe',5.,13);b.close(6.)
    before=hash_state(b.e.state);result=b.result();assert hash_state(b.e.state)==before
    episode=result['episodes'][0];parent=result['actions'][0]
    assert (episode['before'],episode['after'],episode['delta'])==(100,13,-87)
    assert episode['unit']=='displayed_percent' and episode['cause']['source']['canonical_id']=='pokeapi:move:311'
    assert episode['actor_instance_id']==b.pid('own') and episode['target_instance_id']==b.pid('foe')
    assert parent['event_id']==source and parent['target_instance_ids']==[b.pid('foe')]
    stat=next(s for s in parent['resolution_steps'] if s['kind']=='stat_change')
    assert stat['immediate_cause_event_id']==banner
    assert len(result['episodes'])==1  # Stamina is not another HP-changing source.


def test_snarl_two_hud_recipients_and_stat_drops_without_named_damage_message():
    b=Battle(own=6,foe=1018,ally=3)
    source=b.move('foe','大声咆哮');b.hp('own',3.,80);b.hp('ally',3.,73)
    b.hp('own',3.5,80);b.hp('ally',3.5,73)
    b.send('喷火龙和妙蛙花的特攻降低了！',4.);b.close(5.)
    result=b.result();episodes=result['episodes']
    assert len(episodes)==2 and {o['delta'] for o in episodes}=={-20,-27}
    assert all(o['source_event_id']==source and o['cause']['kind']=='move' for o in episodes)
    assert set(result['actions'][0]['target_instance_ids'])=={b.pid('own'),b.pid('ally')}
    assert len([s for s in result['actions'][0]['resolution_steps'] if s['kind']=='stat_change'])==2


def test_uturn_rough_skin_reaction_and_pivot_keep_holder_user_and_target_separate():
    b=Battle();source=b.move('own','急速折返')
    b.hp('foe',3.,80);b.hp('foe',3.5,80)
    banner=b.send('对手的烈咬陆鲨的粗糙皮肤！',4.)
    b.hp('own',5.,90);b.hp('own',5.5,90)
    b.send('具甲武者，回来！',6.);b.send('上吧！钢铠鸦！',7.);b.close(8.)
    result=b.result();direct,reaction=result['episodes']
    assert direct['delta']==-20 and reaction['delta']==-10
    assert direct['parent_action_id']==reaction['parent_action_id']==source
    assert reaction['source_event_id']==banner and reaction['cause']['kind']=='ability'
    assert reaction['actor_instance_id']==direct['target_instance_id']
    assert reaction['target_instance_id']==direct['actor_instance_id']
    steps=result['actions'][0]['resolution_steps']
    assert {s['kind'] for s in steps}>={'pivot_switch_out','pivot_send_out'}
    assert result['actions'][0]['target_instance_ids']==[b.pid('foe')]
    assert result['actions'][0]['totals']['self_damage']['amount']==10


@pytest.mark.parametrize('label,holder,recipient',[
 ('凸凸头盔','foe','own'),('生命宝珠','own','own'),('吃剩的东西','own','own')])
def test_documented_banner_requires_observed_scoped_effect_not_automatic_hp(label,holder,recipient):
    b=Battle();b.move('own','急速折返');b.hp('foe',3.,80);b.hp('foe',3.5,80)
    prefix='对手的' if holder=='foe' else ''
    b.send(prefix+b.mon[holder]['name']+'的'+label+'！',4.)
    assert all(o['source_event']['time']!=4. for o in b.result()['episodes'])
    after=110 if label=='吃剩的东西' else 90
    b.hp(recipient,5.,after);b.hp(recipient,5.5,after);b.close(6.)
    reaction=next(o for o in b.result()['episodes'] if o['source_event']['time']==4.)
    assert reaction['cause']['kind']=='item' and reaction['delta']==after-100
    assert reaction['actor_instance_id']==b.pid(holder)


def test_ally_uturn_recipient_comes_from_hud_not_side_or_switching_actor():
    b=Battle(own=812,ally=727);b.move('own','急速折返')
    b.hp('ally',3.,80);b.hp('ally',3.5,80)
    b.send('轰擂金刚猩，回来！',4.);b.send('上吧！钢铠鸦！',5.);b.close(6.)
    result=b.result();o=result['episodes'][0]
    assert o['actor_instance_id']==b.pid('own') and o['target_instance_id']==b.pid('ally')
    assert o['delta']==-20 and o['attribution_status']=='supported'
    assert result['actions'][0]['target_instance_ids']==[b.pid('ally')]


def test_ally_parting_shot_has_stat_and_pivot_steps_and_no_damage_episode():
    b=Battle(own=727,ally=812);source=b.move('own','抛下狠话')
    b.send('轰擂金刚猩的攻击降低了！',3.)
    b.send('轰擂金刚猩的特攻降低了！',4.)
    b.send('炽焰咆哮虎，回来！',5.);b.send('上吧！钢铠鸦！',6.);b.close(7.)
    result=b.result();assert result['episodes']==[]
    action=result['actions'][0]
    assert action['event_id']==source and action['target_instance_ids']==[b.pid('ally')]
    assert [s['kind'] for s in action['resolution_steps']].count('stat_change')==2
    assert {'pivot_switch_out','pivot_send_out'}<={s['kind'] for s in action['resolution_steps']}


def test_triple_axel_ordered_hits_and_rough_skin_reactions_with_dense_receipts():
    b=Battle(own=908);source=b.move('own','三旋击')
    frames=[]
    for tick in range(10,38):
        t=tick/5
        if tick in {15,24,33}:b.send('对手的烈咬陆鲨的粗糙皮肤！',t)
        if tick==23:b.send('击中了要害！',t)
        target=100 if tick<11 else 96 if tick==11 else 91 if tick<20 else 82 if tick==20 else 73 if tick<29 else 60 if tick==29 else 46
        user=100 if tick<16 else 90 if tick<25 else 80 if tick<34 else 70
        eid=b.hp('foe',t,target,batch=True);b.hp('own',t,user,batch=True)
        frames.append(dict(event_id=eid,time=t,value=target,unit='displayed_percent',confidence=.99,
                           evidence={'synthetic_frame':tick}))
    b.send('击中了3次！',7.6);b.close(8.)
    result=b.result();direct=next(o for o in result['episodes'] if o['cause'] and o['cause']['kind']=='move')
    for f in frames:f['pokemon_instance_id']=b.pid('foe')
    result=b.result(dense_samples={direct['episode_id']:dict(sample_fps=5,samples=frames)})
    direct=next(o for o in result['episodes'] if o['cause'] and o['cause']['kind']=='move')
    reactions=[o for o in result['episodes'] if o['cause'] and o['cause']['kind']=='ability']
    assert direct['hit_resolution']['per_hit_damage']==[9,18,27]
    assert [h['critical_hit'] for h in direct['hit_resolution']['hits']]==[None,True,None]
    assert direct['delta']==-54 and len(reactions)==3
    assert [o['delta'] for o in reactions]==[-10,-10,-10]
    assert [o['triggered_by']['hit_index'] for o in reactions]==[1,2,3]
    assert all(o['parent_action_id']==source for o in reactions)
    assert result['actions'][0]['totals']['self_damage']['amount']==30
    assert len(result['actions'][0]['confirmed_hits'])==3
    assert any(s['kind']=='resume_parent' for s in result['actions'][0]['resolution_steps'])
    # Removing the independent count does not infer three actual hits merely
    # from a move name or three numerical plateaus.
    count=next(r for r in b.e.history if r.event['event_type']=='multi_hit')
    b.e.retract(count.event['event_id'],reason='count not supported')
    again=b.result(dense_samples={direct['episode_id']:dict(sample_fps=5,samples=frames)})
    direct=next(o for o in again['episodes'] if o['cause'] and o['cause']['kind']=='move')
    assert direct['delta']==-54 and direct['hit_resolution']['per_hit_damage'] is None


@pytest.mark.parametrize('notice,kind',[
 ('具甲武者受到了灼伤的伤害！','status'),('具甲武者受到了毒的伤害！','status'),
 ('具甲武者受到了沙暴的伤害！','weather'),('具甲武者受到了隐形岩的伤害！','entry_hazard'),
 ('具甲武者因闪焰冲锋受到了反作用力造成的伤害！','move_recoil'),
 ('具甲武者因腹鼓削减了自己的HP！','self_hp_cost')])
def test_explicit_effects_are_typed_steps_with_real_numeric_endpoints(notice,kind):
    b=Battle();b.move('own','闪焰冲锋');b.hp('foe',3.,80);b.hp('foe',3.5,80)
    b.send(notice,4.);b.hp('own',5.,90);b.hp('own',5.5,90);b.close(6.)
    effect=b.result()['episodes'][-1]
    assert effect['cause']['kind']==kind and effect['delta']==-10
    assert effect['cause']['kind']!='move'


def test_unknown_activation_and_two_pending_sources_force_abstention():
    b=Battle();b.move('own','急速折返');b.hp('foe',3.,80);b.hp('foe',3.5,80)
    b.send('对手的烈咬陆鲨的粗糙皮肤！',4.)
    b.send('对手的烈咬陆鲨的凸凸头盔！',4.5)
    b.hp('own',5.,80);b.hp('own',5.5,80);b.close(6.)
    ambiguous=b.result()['episodes'][-1]
    assert ambiguous['cause'] is None and len(ambiguous['candidate_causes'])==2
    assert ambiguous['delta']==-20 and 'competing_immediate_causes' in ambiguous['reasons']
    b=Battle();b.move('own','急速折返');b.send('对手的烈咬陆鲨的压迫感！',3.)
    b.hp('foe',4.,80);b.hp('foe',4.5,80);b.close(5.)
    assert b.result()['episodes'][0]['cause'] is None


def test_no_successful_hit_and_unreadable_target_preserve_association_without_amount():
    b=Battle();b.move('own','急速折返')
    b.send('对手的烈咬陆鲨在攻击中守护住了自己！',3.)
    b.close(4.);assert b.result()['episodes']==[]
    b=Battle();b.move('foe','喷射火焰')
    b.send('具甲武者受到了伤害！',3.);b.close(4.)
    result=b.result();assert result['episodes']==[]
    assert any(a['affected_instance_id']==b.pid('own') and a['damage'] is None for a in result['target_associations'])


def test_missing_endpoint_and_status_move_do_not_become_invented_damage():
    b=Battle(own=727,ally=812);b.move('own','抛下狠话')
    b.hp('ally',3.,80);b.hp('ally',3.5,80);b.close(4.)
    o=b.result()['episodes'][0]
    assert o['delta']==-20 and o['cause'] is None  # observed loss, unsupported source
    b=Battle();b.move('own','急速折返');b.hp('foe',3.,80);b.close(4.)
    assert b.result()['episodes'][0]['delta'] is None


def test_duplicate_species_banner_cannot_choose_a_holder_from_hp_adjacency():
    b=Battle(ally=445);b.move('own','急速折返')
    b.hp('foe',3.,80);b.hp('foe',3.5,80)
    # No side-bearing holder reference: same species is active on both teams.
    b.send('烈咬陆鲨的粗糙皮肤！',4.,allow_deferred=True)
    b.hp('own',5.,90);b.hp('own',5.5,90);b.close(6.)
    reaction=b.result()['episodes'][-1]
    assert reaction['cause'] is None and reaction['attribution_status']=='ambiguous'
    assert any('activation_holder_unresolved' in c['reasons'] for c in reaction['candidate_causes'])


def test_holder_healing_scope_cannot_heal_some_other_instance():
    b=Battle();b.move('own','急速折返')
    b.send('具甲武者的吃剩的东西！',3.)
    b.hp('foe',4.,100);b.hp('foe',4.5,100)
    b.hp('foe',5.,90);b.hp('foe',5.5,90);b.close(6.)
    o=b.result()['episodes'][0]
    assert o['cause'] is None and 'effect_recipient_scope_conflict' in o['reasons']


def test_coverage_gap_vetoes_reaction_even_before_its_first_numeric_change():
    b=Battle();b.move('own','急速折返');b.hp('foe',3.,80);b.hp('foe',3.5,80)
    b.send('对手的烈咬陆鲨的粗糙皮肤！',4.)
    b.n+=1;gap=hud(b.n,4.5,823)
    gap.event_type='coverage_observation';gap.attributes=dict(battle_id='test',status='gap',start=4.1,observation_time=4.5,fields=['messages'])
    # An explicit gap need not be admitted as a state mutation to prevent the
    # causal projection from treating that interval as complete coverage.
    b.e.apply(gap,sequence=b.n)
    b.hp('own',5.,90);b.hp('own',5.5,90);b.close(6.)
    reaction=b.result()['episodes'][-1]
    assert reaction['cause'] is None and 'event_coverage_gap' in reaction['reasons']


def test_failed_result_after_numeric_observations_does_not_get_silently_ignored():
    b=Battle();b.move('own','急速折返');b.hp('foe',3.,80);b.hp('foe',3.5,80)
    b.send('对手的烈咬陆鲨在攻击中守护住了自己！',4.)
    b.close(5.)
    o=b.result()['episodes'][0]
    assert o['attribution_status']=='ambiguous' and 'blocked_or_failed_effect' in o['reasons']


def test_active_status_does_not_establish_an_actual_residual_occurrence():
    b=Battle();b.send('具甲武者灼伤了！',2.)
    b.hp('own',3.,90);b.hp('own',3.5,90);b.close(4.)
    assert b.result()['episodes'][0]['cause'] is None


def test_full_scale_first_visible_hp_can_supply_pre_animation_endpoint():
    b=Battle();b.e.retract('hud:2',reason='no old foe HP observation')
    b.move('own','急速折返')
    b.hp('foe',3.,100);b.hp('foe',3.5,80);b.hp('foe',4.,80);b.close(5.)
    o=b.result()['episodes'][0]
    assert (o['before'],o['after'],o['delta'])==(100,80,-20)
    assert o['components'][0]['baseline_basis']=='observed_full_scale_before_decrease'


def test_knowledge_effects_are_offline_categorical_assertions_not_amount_rules():
    from datetime import date
    from knowledge.resolution_effects import supplement
    data,rows,_=supplement()
    for cid,row in rows.items():
        resolved=knowledge().resolution_effect(cid)
        assert resolved['source']['revision_id']
        assert date.fromisoformat(resolved['source']['retrieved'])
        assert knowledge().entities[cid].kind==row['kind']
        assert 'fraction' not in row and 'probability' not in row
    assert knowledge().resolution_effect('pokeapi:ability:192')['hp_effect'] is False
    assert knowledge().resolution_effect('pokeapi:move:813')['hit_range']==[1,3]
    assert knowledge().resolution_effect('unresolved:unknown') is None


def test_adaptive_dense_rates_respect_source_limits_and_parent_boundaries():
    from recognition.resolution_sampling import adaptive_rates,dense_plans
    assert adaptive_rates(30)==[5,10,20]
    assert adaptive_rates(15)==[5,10,15]
    with pytest.raises(ValueError):adaptive_rates(4)
    b=Battle(own=908);b.move('own','三旋击');b.hp('foe',3.,80);b.hp('foe',3.5,80)
    b.send('对手的烈咬陆鲨的粗糙皮肤！',4.);b.hp('own',5.,90);b.hp('own',5.5,90)
    b.close(6.)
    plan=dense_plans(b.e)[0]
    assert plan['end']==6. and plan['start']<2.  # not cut at the first reaction banner
    assert plan['trigger_basis']=='documented_champions_capability'


def test_generic_damage_message_does_not_turn_parting_shot_into_a_damage_move():
    b=Battle(own=727,ally=812);b.move('own','抛下狠话')
    b.send('轰擂金刚猩受到了伤害！',3.)
    b.hp('ally',4.,80);b.hp('ally',4.5,80);b.close(5.)
    assert b.result()['episodes'][0]['cause'] is None


def test_same_frame_source_change_does_not_supply_subframe_order():
    b=Battle();b.move('own','急速折返',2.)
    b.hp('foe',2.,80);b.hp('foe',2.5,80);b.close(3.)
    o=b.result()['episodes'][0]
    assert o['cause'] is None and 'source_change_time_tie' in o['reasons']


def test_ally_contact_reaction_has_no_opponent_only_rule():
    b=Battle(own=812,foe=373,ally=445);b.move('own','急速折返')
    b.hp('ally',3.,80);b.hp('ally',3.5,80)
    b.send('烈咬陆鲨的粗糙皮肤！',4.)
    b.hp('own',5.,90);b.hp('own',5.5,90);b.close(6.)
    direct,reaction=b.result()['episodes']
    assert direct['target_instance_id']==b.pid('ally')
    assert reaction['actor_instance_id']==b.pid('ally') and reaction['target_instance_id']==b.pid('own')
    assert reaction['cause']['kind']=='ability'


def test_adaptive_inspection_escalates_temporal_failure_and_reuses_completed_stages(tmp_path):
    import json
    from battle_artifacts import BattleArtifacts
    from recognition.resolution_sampling import inspect_resolutions
    from recognition.event_report import atomic_json
    b=Battle(own=908);b.move('own','三旋击');b.hp('foe',3.,73);b.hp('foe',3.5,73)
    b.send('击中了2次！',4.);b.close(5.)
    owner=BattleArtifacts('test',tmp_path);calls=[]
    def sampler(owner,run_id,**kwargs):
        calls.append(kwargs['sample_fps'])
        folder=owner.cache('hp-resolution-sampling/'+run_id);folder.mkdir(parents=True,exist_ok=True)
        atomic_json(folder/'rows.json',[])
        value=dict(status='complete',identity=dict(sample_fps=kwargs['sample_fps']),
                   measured=dict(ocr_model_predictions=0,sampled_frames=0),outputs=[str(folder/'rows.json')])
        atomic_json(folder/'manifest.json',value);return value
    before=hash_state(b.e.state)
    result=inspect_resolutions(owner,'adaptive-test',b.e,source_fps=12,window_sampler=sampler)
    assert calls==[3,4] and result['status']=='complete'
    assert all(not attempt['per_hit_resolved'] for attempt in result['completed'])
    assert hash_state(b.e.state)==before
    again=inspect_resolutions(owner,'adaptive-test',b.e,source_fps=12,window_sampler=sampler)
    assert again==result and calls==[3,4]


@pytest.mark.parametrize('move,banner,reason',[
    ('气象球','对手的烈咬陆鲨的粗糙皮肤！','contact_mechanics_not_confirmed'),
    ('急速折返','对手的烈咬陆鲨的生命宝珠！','post_attack_holder_not_parent_actor'),
])
def test_banner_cannot_override_missing_trigger_prerequisite(move,banner,reason):
    b=Battle();b.move('own',move);b.hp('foe',3.,80);b.hp('foe',3.5,80)
    b.send(banner,4.)
    recipient='own' if '粗糙皮肤' in banner else 'foe'
    b.hp(recipient,5.,70);b.hp(recipient,5.5,70);b.close(6.)
    effect=b.result()['episodes'][-1]
    assert effect['cause'] is None and effect['attribution_status']=='ambiguous'
    assert any(reason in c['reasons'] for c in effect['candidate_causes'])


def test_healing_banner_with_observed_loss_keeps_numeric_loss_without_cause():
    b=Battle();b.send('具甲武者的吃剩的东西！',2.)
    b.hp('own',3.,90);b.hp('own',3.5,90);b.close(4.)
    effect=b.result()['episodes'][0]
    assert effect['delta']==-10 and effect['cause'] is None
    assert 'immediate_effect_direction_conflict' in effect['reasons']


def test_next_move_does_not_inherit_previous_contact_reaction():
    b=Battle();b.move('own','急速折返');b.hp('foe',3.,80);b.hp('foe',3.5,80)
    b.send('对手的烈咬陆鲨的粗糙皮肤！',4.)
    source=b.move('foe','喷射火焰',5.)
    b.hp('own',6.,90);b.hp('own',6.5,90);b.close(7.)
    effect=b.result()['episodes'][-1]
    assert effect['source_event_id']==source and effect['cause']['kind']=='move'
    assert all(c['cause']['kind']=='move' for c in effect['candidate_causes'])


def test_retracting_reaction_banner_rebuilds_without_stale_parent_or_cause():
    b=Battle();b.move('own','急速折返');b.hp('foe',3.,80);b.hp('foe',3.5,80)
    banner=b.send('对手的烈咬陆鲨的粗糙皮肤！',4.)
    b.hp('own',5.,90);b.hp('own',5.5,90);b.close(6.)
    assert b.result()['episodes'][-1]['cause']['kind']=='ability'
    b.e.retract(banner,reason='unverified activation')
    before=deepcopy(b.e.to_dict());result=b.result()
    assert b.e.to_dict()==before
    effect=next(o for o in result['episodes'] if o['affected_instance_id']==b.pid('own'))
    assert effect['delta']==-10 and effect['cause'] is None
    assert banner not in effect['cause_event_ids']
    assert result['actions'][0]['totals']['self_damage'] is None
    assert b.pid('own') in result['actions'][0]['totals']['unresolved_hp_by_instance']
