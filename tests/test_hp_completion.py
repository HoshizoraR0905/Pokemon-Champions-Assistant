"""Portable endpoint/entry regressions; source values here are synthetic contracts."""
from copy import deepcopy
import pytest
from tests.test_sequential_resolution import Battle


def source_sample(b,key,t,value,*,onset=False,confidence=1.,maximum=None):
    m=b.mon[key];entry='hud:'+str(list(b.mon).index(key)+1)
    return dict(time=t,value=value,unit='absolute' if m['side']=='self' else 'displayed_percent',
        maximum=200 if m['side']=='self' else maximum,confidence=confidence,
        pokemon_instance_id=b.pid(key),binding_entry_event_id=entry,visibility_onset=onset,sample_fps=20,
        event_id='source:'+str(t),evidence=dict(source=dict(sha256=str(t),timestamp=t,image='synthetic.png'),
        observation=dict(hp=dict(value=value,confidence=confidence))))


def test_nonfull_animation_onset_recovers_baseline_without_changing_segments_or_state():
    b=Battle();initial=deepcopy(b.e.history[-1].event)
    initial['attributes']['hp']['value']=None
    b.e.correct('hud:2',initial,sequence=2,reason='identity observed without numeric HP')
    b.move('own','急速折返');b.hp('foe',3.5,12);b.hp('foe',4.,0);b.hp('foe',4.5,0);b.close(5.)
    raw=b.result()['episodes'][0];assert raw['delta'] is None
    samples=[source_sample(b,'foe',t,v,onset=n==0) for n,(t,v) in enumerate([
        (3.,25),(3.05,25),(3.1,25),(3.15,23),(3.2,20)])]
    before=deepcopy(b.e.to_dict());out=b.result(endpoint_samples=samples)['episodes'][0]
    assert (out['before'],out['after'],out['delta'])==(25,0,-25)
    assert out['components'][0]['baseline_basis']=='observed_source_animation_onset'
    assert out['endpoints']['before']['event_type']=='source_hp_observation'
    assert out['segment_event_ids']==raw['segment_event_ids'] and b.e.to_dict()==before


@pytest.mark.parametrize('fault',['no_onset','single_partial','duplicate_frames','wrong_instance','wrong_unit','low_confidence','retracted_binding','low_fps','multi_hit'])
def test_source_fragments_cannot_invent_a_baseline(fault):
    b=Battle();initial=deepcopy(b.e.history[-1].event)
    initial['attributes']['hp']['value']=None
    b.e.correct('hud:2',initial,sequence=2,reason='identity observed without numeric HP')
    b.move('own','急速折返');b.hp('foe',3.5,20);b.hp('foe',4.,12);b.hp('foe',4.5,12)
    samples=[source_sample(b,'foe',t,v,onset=n==0) for n,(t,v) in enumerate([
        (3.,25),(3.05,25),(3.1,25),(3.15,23)])]
    if fault=='no_onset':samples[0]['visibility_onset']=False
    if fault=='single_partial':samples=[samples[0],samples[-1]]
    if fault=='duplicate_frames':samples=[samples[0]]*3+[samples[-1]]
    if fault=='wrong_instance':
        for s in samples:s['pokemon_instance_id']=b.pid('own')
    if fault=='wrong_unit':
        for s in samples:s['unit']='absolute'
    if fault=='low_confidence':
        for s in samples:s['confidence']=.7
    if fault=='retracted_binding':
        for s in samples:s['binding_entry_event_id']='no-longer-present'
    if fault=='low_fps':
        for s in samples:s['sample_fps']=2
    if fault=='multi_hit':
        b.send('击中了2次！',4.7)
    b.close(5.)
    out=b.result(endpoint_samples=samples)['episodes'][0]
    assert out['before'] is None and out['delta'] is None


def test_source_plateau_completes_effect_without_banner_derived_amount():
    b=Battle();b.send('具甲武者受到了灼伤的伤害！',2.)
    b.hp('own',3.,90);b.close(5.)
    original=b.result()['episodes'][0];assert original['delta'] is None
    extra=[source_sample(b,'own',3.2,90),source_sample(b,'own',3.6,90)]
    out=b.result(endpoint_samples=extra)['episodes'][0]
    assert out['delta']==-10 and out['attribution_status']=='supported'
    assert out['segment_event_ids']==original['segment_event_ids']
    assert out['endpoints']['after']['event_type']=='source_hp_observation'


def test_later_source_change_invalidates_an_earlier_native_plateau_until_settled():
    b=Battle();b.move('own','急速折返');b.hp('foe',3.,80);b.hp('foe',3.5,80);b.close(5.)
    assert b.result()['episodes'][0]['delta']==-20
    out=b.result(endpoint_samples=[source_sample(b,'foe',4.,70)])['episodes'][0]
    assert out['after']==70 and out['delta'] is None
    assert 'final_visible_plateau_unresolved' in out['reasons']


def test_trustworthy_last_read_followed_by_near_independent_action_can_finish():
    b=Battle();b.move('own','急速折返');b.hp('foe',3.,80);b.close(3.3)
    o=b.result()['episodes'][0]
    assert o['delta']==-20 and o['final_endpoint_basis']=='trusted_hp_then_independent_resolution'


def return_same_instance(b,*,explicit=True):
    b.send('具甲武者，回来！',4.)
    b.send('上吧！具甲武者！',5.,attributes={'actor_instance_id':b.pid('own')} if explicit else None)


def test_same_instance_carry_is_derived_and_observed_entry_can_correct_it():
    b=Battle();b.hp('own',2.,70);b.hp('own',2.5,70);return_same_instance(b)
    b.hp('own',5.5,80);b.move('foe','喷射火焰',6.)
    b.hp('own',7.,60);b.hp('own',7.5,60);b.close(8.)
    out=b.result();entry=out['switch_in_baselines'][-1]
    assert entry['carried_hp']==70 and entry['status']=='derived_same_instance_carry'
    assert entry['confirmation']['outcome']=='corrected'
    o=out['episodes'][-1];assert (o['before'],o['delta'])==(80,-20)


def test_same_instance_return_without_new_hud_can_use_settled_carry():
    b=Battle();b.hp('own',2.,70);b.hp('own',2.5,70);return_same_instance(b)
    b.move('foe','喷射火焰',6.);b.hp('own',7.,60);b.hp('own',7.5,60);b.close(8.)
    o=b.result()['episodes'][-1]
    assert o['delta']==-10 and o['components'][0]['baseline_basis']=='derived_same_instance_carry'
    assert b.result()['switch_in_baselines'][-1]['confirmation']['outcome']=='first_read_after_resolution_not_entry_confirmation'


def test_first_entry_full_hp_remains_a_conditional_hypothesis():
    b=Battle();b.send('具甲武者，回来！',4.);b.send('上吧！钢铠鸦！',5.)
    entry=b.result()['switch_in_baselines'][-1]
    assert entry['carried_hp'] is None
    assert entry['initial_full_hp_hypothesis']['value']==100
    assert entry['initial_full_hp_hypothesis']['usable_as_numeric_baseline'] is False


def test_unsettled_pre_departure_animation_cannot_be_carried_as_final_hp():
    b=Battle();b.hp('own',2.,70);return_same_instance(b)
    assert b.result()['switch_in_baselines'][-1]['carried_hp'] is None


def test_observed_offfield_effect_without_amount_invalidates_carry():
    b=Battle();b.hp('own',2.,70);b.hp('own',2.5,70)
    b.send('具甲武者，回来！',4.)
    # A bound qualitative occurrence has no numeric amount; no fractional heal is invented.
    event=deepcopy(b.e.history[-1].event);event.update(event_id='offfield-effect',event_type='hp_change')
    event['attributes'].update(actor_instance_id=b.pid('own'),observation_time=4.5,
        qualitative_only=True,direction='up',cause={'kind':'ability'})
    b.n+=1;b.e.apply(event,sequence=b.n)
    b.send('上吧！具甲武者！',5.,attributes={'actor_instance_id':b.pid('own')})
    assert b.result()['switch_in_baselines'][-1]['carried_hp'] is None


def test_explicit_offfield_numeric_change_updates_same_instance_carry():
    b=Battle();b.hp('own',2.,70);b.hp('own',2.5,70)
    b.send('具甲武者，回来！',4.)
    event=deepcopy(b.e.history[-1].event)
    event.update(event_id='offfield-numeric',event_type='hp_change',original_text='synthetic supported HP endpoints',
        parsing_confidence='supported',uncertainty=[])
    event['evidence'][0]['source_type']='synthetic_endpoint_fixture'
    event['attributes']=dict(actor_instance_id=b.pid('own'),observation_time=4.5,before=70,after=80,unit='absolute')
    b.n+=1;receipt=b.e.apply(event,sequence=b.n)
    assert receipt.application_status=='applied_candidate'
    b.send('上吧！具甲武者！',5.,attributes={'actor_instance_id':b.pid('own')})
    b.move('foe','喷射火焰',6.);b.hp('own',7.,60);b.hp('own',7.5,60);b.close(8.)
    out=b.result();assert out['switch_in_baselines'][-1]['carried_hp']==80
    assert out['episodes'][-1]['delta']==-20


def test_entry_hazard_and_attack_have_distinct_sources_and_correct_post_hazard_baseline():
    b=Battle();b.hp('own',2.,70);b.hp('own',2.5,70);return_same_instance(b)
    b.send('具甲武者受到了隐形岩的伤害！',5.5)
    b.hp('own',6.,60);b.hp('own',6.5,60)
    b.move('foe','喷射火焰',7.);b.hp('own',8.,40);b.hp('own',8.5,40);b.close(9.)
    hazard,attack=b.result()['episodes'][-2:]
    assert (hazard['before'],hazard['after'],hazard['delta'])==(70,60,-10)
    assert hazard['cause']['kind']=='entry_hazard'
    assert (attack['before'],attack['after'],attack['delta'])==(60,40,-20)
    assert attack['cause']['kind']=='move' and attack['source_event_id']!=hazard['source_event_id']


def test_source_adapter_binds_only_the_existing_occupied_interval_and_checks_hashes(tmp_path):
    import json
    from battle_artifacts import BattleArtifacts
    from recognition.fast_video import digest
    from recognition.resolution_sampling import endpoint_source_samples
    b=Battle();b.e.initial.knowledge['active_continuity_v1']=True;b.e.replay()
    b.send('对手的烈咬陆鲨倒下了！',2.)
    owner=BattleArtifacts('test',tmp_path);video=tmp_path/'tests/fixtures/test.mp4'
    video.parent.mkdir(parents=True);video.write_bytes(b'synthetic video identity')
    frame=tmp_path/'frame.png';frame.write_bytes(b'synthetic source frame')
    obs=dict(slot='opponent_active_2',hp=dict(value=80,confidence=1.))
    rows=[dict(source=dict(timestamp=t,image='frame.png',sha256=digest(frame)),
        snapshot=dict(pokemon=[obs]),reused_visible_hp=[]) for t in [1.5,2.5]]
    output=tmp_path/'rows.json';output.write_text(json.dumps(rows))
    manifest=dict(status='complete',identity=dict(battle_id='test',video_sha256=digest(video),sample_fps=5.),outputs=[str(output)])
    before=deepcopy(b.e.to_dict());samples=endpoint_source_samples(owner,b.e,manifest)
    assert [s['time'] for s in samples]==[1.5]
    assert samples[0]['pokemon_instance_id']==b.pid('foe')
    assert b.e.to_dict()==before
    wrong=deepcopy(manifest);wrong['identity']['battle_id']='different-battle'
    with pytest.raises(ValueError):endpoint_source_samples(owner,b.e,wrong)
    frame.write_bytes(b'changed')
    with pytest.raises(ValueError):endpoint_source_samples(owner,b.e,manifest)


def test_source_adapter_uses_observed_exchange_receipts_without_future_slot_leakage(tmp_path):
    import json
    from battle_artifacts import BattleArtifacts
    from recognition.fast_video import digest
    from recognition.resolution_sampling import endpoint_source_samples
    b=Battle(ally=812);b.e.initial.knowledge['active_continuity_v1']=True;b.e.replay()
    event=deepcopy(b.e.history[-1].event)
    event.update(event_id='exchange',event_type='position_change',side='self',actor=None)
    event['attributes']=dict(observation_time=2.,mechanic='ally_switch',execution_observed=True)
    b.n+=1;assert b.e.apply(event,sequence=b.n).application_status=='applied_candidate'
    owner=BattleArtifacts('test',tmp_path);video=tmp_path/'tests/fixtures/test.mp4'
    video.parent.mkdir(parents=True);video.write_bytes(b'synthetic video identity')
    frame=tmp_path/'frame.png';frame.write_bytes(b'synthetic source frame')
    obs=dict(slot='own_active_2',hp=dict(value={'current':80,'maximum':200},confidence=1.))
    rows=[dict(source=dict(timestamp=t,image='frame.png',sha256=digest(frame)),
        snapshot=dict(pokemon=[obs]),reused_visible_hp=[]) for t in [1.5,2.5]]
    output=tmp_path/'rows.json';output.write_text(json.dumps(rows))
    manifest=dict(status='complete',identity=dict(battle_id='test',video_sha256=digest(video),sample_fps=5.),outputs=[str(output)])
    samples=endpoint_source_samples(owner,b.e,manifest)
    assert [s['pokemon_instance_id'] for s in samples]==[b.pid('own'),b.pid('ally')]
