"""Portable checkpoint semantics plus explicit optional real-screen validation."""
from copy import deepcopy
from pathlib import Path
import cv2
import pytest
from battle_events.schema import BattleEvent,Evidence
from recognition.command_checkpoint import CommandCheckpointSchedule,inspect_command,SLOT_REGIONS
from tracking.battle_state import BattleState
from tracking.state_engine import StateEngine
from tracking.identity_ledger import remember_alias
from tests.test_evidence_fusion import hud

NAMES={823:'钢铠鸦',530:'龙头地鼠',373:'暴飞龙',903:'大狃拉',248:'班基拉斯',205:'佛烈托斯'}


def engine():
    e=StateEngine(BattleState('test',knowledge=dict(identity_v1=True,reliability_v1=True,reliability_v2=True,
        active_continuity_v1=True,active_persistence_v1=True,command_reconciliation_v1=True)))
    for i,(side,slot,sid) in enumerate([('self','left',823),('self','right',530),('opponent','left',373),('opponent','right',903)],1):
        e.apply(hud(i,1,sid,side=side,slot=slot,hp=dict(current=50,maximum=100)),sequence=i)
    return e


def checkpoint(t=5,sids=(823,530,373,903),phase='p1'):
    observations=[]
    for (key,(side,slot,roi)),sid in zip(SLOT_REGIONS.items(),sids):
        observations.append(dict(region_id=key,side=side,slot=slot,visible=True,
            species=dict(raw_text=NAMES[sid],confidence=.99),icon={},timestamp=t,source_id='frame:'+str(t),
            sha256='hash:'+str(t),image='frame.png',name_roi=list(roi)))
    return BattleEvent('checkpoint:'+str(t),'command_checkpoint','field',None,None,'Command verification',{},None,
        [Evidence('command_hud_checkpoint','frame:'+str(t),['hash:'+str(t)],dict(timestamp=t,image='frame.png'))],
        None,'supported',[],dict(battle_id='test',observation_time=t,
            checkpoint=dict(phase_id=phase,stable=True,previous_timestamp=t-.5,inspection=dict(eligible=True)),observations=observations))


def add(e,event):return e.apply(event,sequence=len(e.history)+1)
def outcomes(r):return r.bindings['command_reconciliation']['outcomes']


def test_four_matches_do_not_mutate_pokemon_or_slots():
    e=engine();before=deepcopy(e.state.to_dict());r=add(e,checkpoint())
    assert [o['status'] for o in outcomes(r)]==['match']*4
    assert e.state.to_dict()['pokemon']==before['pokemon']
    assert all(e.state.to_dict()['sides'][s]==before['sides'][s] for s in ('self','opponent'))


def test_bad_ocr_is_inconclusive_and_never_retried_within_phase():
    e=engine();old=deepcopy(e.state.to_dict()['pokemon']);c=checkpoint();c.attributes['observations'][0]['species']['confidence']=.1
    r=add(e,c);assert outcomes(r)[0]['status']=='inconclusive'
    assert e.state.to_dict()['pokemon']==old
    r=add(e,checkpoint(6,(248,530,373,903)))
    assert r.bindings['command_reconciliation']['status']=='duplicate_phase_attempt_ignored'
    assert e.state.to_dict()['pokemon']==old


def test_single_correction_preserves_history_without_copying_hp_status_or_stages():
    e=engine();old=e.state.sides['self'].active_slots['left'];history=deepcopy([r.event for r in e.history]);old_hp=deepcopy(e.state.pokemon[old].hp)
    r=add(e,checkpoint(sids=(248,530,373,903)));o=outcomes(r)[0]
    assert o['status']=='conflict' and o['corrected'] and not o['historical_gap']['exact_transition_recovered']
    new=e.state.pokemon[e.state.sides['self'].active_slots['left']]
    assert new.species.value['species_id']==248 and new.pokemon_instance_id!=old
    assert not new.hp.current.known and not new.major_status.known and not new.moves.executed
    assert all(not stage.value.known for stage in new.stages.values())
    assert e.state.pokemon[old].hp==old_hp and not e.state.pokemon[old].location.known
    assert [h.event for h in e.history[:-1]]==history
    assert not any(h.event['event_type'] in {'switch_out','faint','move_execution','ability_activation'} for h in e.history)


def test_two_distinct_changed_slots_correct_independently_and_other_slots_persist():
    e=engine();right=e.state.sides['self'].active_slots['right'];r=add(e,checkpoint(sids=(248,530,205,903)))
    assert r.bindings['command_reconciliation']['corrections']==2
    assert e.state.sides['self'].active_slots['right']==right
    assert [o['status'] for o in outcomes(r)]==['conflict','match','conflict','match']


def test_same_species_across_sides_does_not_merge_instances_but_side_duplicates_abstain():
    e=engine();r=add(e,checkpoint(sids=(823,530,823,903)))
    assert outcomes(r)[2]['corrected']
    assert e.state.sides['self'].active_slots['left']!=e.state.sides['opponent'].active_slots['left']
    e=engine();r=add(e,checkpoint(sids=(248,248,373,903)))
    assert [o['status'] for o in outcomes(r)][:2]==['inconclusive','inconclusive']


def test_unknown_slot_gets_supported_occupancy_without_party_identity_merge():
    e=engine();e.initial=deepcopy(e.state);e.history=[]
    pid=e.initial.sides['self'].active_slots.pop('left');e.initial.pokemon[pid].location.value=dict(kind='bench',slot=None)
    e.replay();r=add(e,checkpoint())
    assert outcomes(r)[0]['status']=='unexpected_occupancy'
    assert e.state.sides['self'].active_slots['left']!=pid


def test_nickname_uses_only_past_side_owned_v_species_proof_without_current_occupant_bias():
    for future in (False,True):
        e=engine();e.initial=deepcopy(e.state);e.history=[]
        remember_alias(e.initial,'Pebble',dict(canonical_id='pokeapi:species:205',species_id=205,name='佛烈托斯'),
            [dict(sources=[dict(details=dict(timestamp=8 if future else 1))])],side='opponent',instance_id=None)
        e.replay();c=checkpoint();c.attributes['observations'][2]['species']['raw_text']='Pebble'
        r=add(e,c)
        assert outcomes(r)[2]['status']==('inconclusive' if future else 'conflict')
        if not future:assert outcomes(r)[2]['corrected']


def test_interval_starts_at_previous_verified_checkpoint_and_has_no_future_messages():
    e=engine();add(e,checkpoint(3));c=checkpoint(5,(248,530,373,903),phase='p2');r=add(e,c)
    gap=outcomes(r)[0]['historical_gap'];assert gap['start']==3 and gap['end']==5
    assert all(p['timestamp']<=5 for p in gap['message_and_coverage_evidence'])


def test_incomplete_view_cannot_correct_any_slot_and_future_window_cannot_apply():
    e=engine();old=deepcopy(e.state.to_dict()['pokemon']);c=checkpoint(sids=(248,530,373,903));c.attributes['checkpoint']['inspection']['eligible']=False
    r=add(e,c);assert all(o['status']=='inconclusive' for o in outcomes(r));assert e.state.to_dict()['pokemon']==old
    c=checkpoint(6);c.attributes['checkpoint']['previous_timestamp']=7
    assert add(e,c).application_status=='deferred'


def test_faint_and_sendout_after_correction_use_new_episode_without_old_hp():
    from tests.test_scrolling_semantics import row
    from recognition.event_report import video_events
    e=engine();add(e,checkpoint(sids=(248,530,373,903)));pid=e.state.sides['self'].active_slots['left']
    for t,text in [(6,'班基拉斯倒下了！'),(7,'上吧！钢铠鸦！')]:
        for ev in video_events([row(t,text)],[],'test'):r=add(e,ev)
        assert r.application_status=='applied_candidate'
    assert e.state.pokemon[pid].fainted.value is True
    assert e.state.sides['self'].active_slots['left']!=pid


def test_phase_stability_navigation_no_retry_and_serialized_resume():
    s=CommandCheckpointSchedule();ui=dict(normal_controls=True,eligible=True,command_context=True)
    def row(t,phase='battle_screen'):return dict(timestamp=t,source_id=str(t),ui=dict(phase=phase))
    assert s.observe(row(1),ui,{'a':[[1]]}) is None
    attempt=s.observe(row(1.5),ui,{'a':[[1]]});assert attempt['phase_id']=='command:1'
    restored=CommandCheckpointSchedule();restored.__dict__.update(deepcopy(s.__dict__))
    assert restored.observe(row(2,'move_selection'),dict(normal_controls=False),{}) is None
    assert restored.observe(row(3),ui,{'a':[[1]]}) is None
    assert restored.observe(row(3.5),ui,{'a':[[1]]}) is None
    r=row(4);r['occurrence_decision']=dict(events=[dict(event_type='move_execution')]);restored.observe(r,{},{});
    assert restored.observe(row(5),ui,{'a':[[1]]}) is None
    assert restored.observe(row(5.5),ui,{'a':[[1]]})['phase_id']=='command:2'


@pytest.mark.parametrize('i',range(3))
def test_three_supplied_overlay_examples_never_qualify_even_with_command_and_many_names(i):
    image=cv2.imread(str(Path('tests/fixtures/Image_Illustration')/f'Command_Label_Location_{i}.png'))
    assert not inspect_command(cv2.resize(image,(1311,603)))['normal_controls']


@pytest.mark.parametrize('overlay,phase,complete,eligible',[
    ('status_overlay','battle_screen',True,True),
    ('status_overlay','battle_screen',False,False),
    ('battle_log_overlay','battle_screen',True,False),
    ('status_overlay','move_selection',True,False)])
def test_color_overlay_override_requires_native_controls_and_all_huds(monkeypatch,overlay,phase,complete,eligible):
    import numpy as np
    import recognition.command_checkpoint as module
    image=np.zeros((603,1311,3),dtype=np.uint8)
    for center in [(1141,353),(1092,474)]:
        cv2.circle(image,center,53,(255,255,255),-1)
        cv2.circle(image,center,43,(180,30,150),-1)
    cards=[('own',0,None,None),('own',1,None,None),('opponent',0,None,None),('opponent',1,None,None)]
    monkeypatch.setattr(module,'independent_cards',lambda image:cards if complete else cards[:3])
    monkeypatch.setattr('recognition.ui_regions.inspect_ui',lambda image:dict(overlay=overlay,phase=phase))
    assert inspect_command(image)['eligible'] is eligible
    image[:]=0
    assert not inspect_command(image)['eligible']


@pytest.mark.local_artifacts
def test_saved_color_vetoed_native_command_frames_qualify_without_new_recognition():
    import json
    path=Path('.cache/battles/sample_battle_7/event-driven/production-first-pass-v1/observations.json')
    if not path.exists():pytest.skip('Optional saved Battle 7 evidence absent')
    rows=json.loads(path.read_text())['observations']
    vetoed=[r for r in rows if r.get('command_inspection',{}).get('overlay')=='status_overlay']
    assert len(vetoed)==6
    for row in vetoed:
        image=cv2.imread(row['image'])
        assert image is not None
        assert inspect_command(image)['eligible'],row['timestamp']


@pytest.mark.local_artifacts
def test_real_normal_command_and_move_selection_have_distinct_controls():
    base=Path('.cache/battles/sample_battle_5/event-driven/m238-rc-b5-v1/frames')
    if not base.exists():pytest.skip('Optional saved Battle 5 frames are absent')
    assert inspect_command(cv2.imread(str(base/'000263.png')))['eligible']
    assert not inspect_command(cv2.imread(str(base/'000268.png')))['normal_controls']


@pytest.mark.parametrize('field,value', [('observation_time',float('inf')),('observation_time',float('nan')),('observation_time',True)])
def test_nonfinite_or_boolean_checkpoint_time_is_rejected(field,value):
    e=engine();c=checkpoint();c.attributes[field]=value
    assert add(e,c).application_status=='rejected'


@pytest.mark.parametrize('mutation', ['region','roi','source_pair','image','timestamp'])
def test_invalid_region_or_unbound_source_cannot_change_state(mutation):
    e=engine();old=deepcopy(e.state.to_dict()['pokemon']);c=checkpoint(sids=(248,530,373,903));o=c.attributes['observations'][0]
    if mutation=='region':o['region_id']='opponent_active_1'
    elif mutation=='roi':o['name_roi']=[0,0,1,1]
    elif mutation=='source_pair':
        # Both values occur somewhere, but never in the same evidence record.
        o['source_id']='other';c.evidence.append(Evidence('command_hud_checkpoint','other',['different'],dict(timestamp=5,image='frame.png')))
    elif mutation=='image':o['image']='other.png'
    else:c.evidence[0].details['timestamp']=6
    assert add(e,c).application_status=='rejected'
    assert e.state.to_dict()['pokemon']==old


def test_nonfinite_confidence_and_reused_identity_are_inconclusive():
    for field,value in [('confidence',float('nan')),('confidence',float('inf')),('identity_reused_from','earlier')]:
        e=engine();c=checkpoint(sids=(248,530,373,903));o=c.attributes['observations'][0]
        if field=='confidence':o['species'][field]=value
        else:o[field]=value
        assert outcomes(add(e,c))[0]['status']=='inconclusive'


def test_complete_party_does_not_prove_reconciled_individual_continuity():
    from tracking.battle_state import Fact
    e=engine();e.initial=deepcopy(e.state);e.history=[]
    e.initial.sides['self'].party_complete=Fact(True,'observed')
    e.replay();o=outcomes(add(e,checkpoint(sids=(530,823,373,903))))[0]
    ep=next(x for x in e.state.knowledge['active_entry_episodes'] if x['episode_id']==o['active_episode_id'])
    assert ep['persistent_identity_status']=='unproven' and ep['possible_prior_instance_ids']


def test_production_checkpoint_boundary_is_bounded_and_resumes_without_more_reads(monkeypatch):
    import json
    from collections import Counter
    import numpy as np
    import recognition.command_checkpoint as module
    from models import Observation
    ui=dict(normal_controls=True,eligible=True,command_context=True,visible_slots=list(SLOT_REGIONS))
    monkeypatch.setattr(module,'inspect_command',lambda image:deepcopy(ui))
    class Reader:
        calls=[]
        def read(self,image,bounds,**kwargs):
            self.calls.append((bounds,kwargs));return Observation(raw_text='钢铠鸦',confidence=.99)
    backend=Reader();schedule=CommandCheckpointSchedule();counts=Counter();image=np.zeros((603,1311,3),dtype=np.uint8)
    def row(t):return dict(timestamp=t,source_id=str(t),sha256=str(t),image='frame.png',ui=dict(phase='battle_screen'))
    module.schedule_checkpoint(row(1),image,schedule,backend,counts)
    r=row(1.5);module.schedule_checkpoint(r,image,schedule,backend,counts)
    assert len(backend.calls)==4 and all(k['independent'] for _,k in backend.calls)
    assert counts['command_checkpoint_attempts']==1
    restored=CommandCheckpointSchedule();restored.__dict__.update(json.loads(json.dumps(schedule.__dict__)))
    module.schedule_checkpoint(row(2),image,restored,backend,counts)
    assert len(backend.calls)==4
    from recognition.event_report import video_events
    from tests.test_event_driven import live_row
    base=live_row(1.5,'');base.update(r);r=base
    events=video_events([r],[],'test')
    same_frame=[e['event_type'] for e in events if e['attributes']['observation_time']==1.5]
    assert same_frame[0]=='command_checkpoint'


def test_missing_name_capture_preserves_unreadable_same_frame_and_replaces_reused(monkeypatch):
    import numpy as np
    from models import Observation
    from recognition.command_checkpoint import capture_checkpoint_huds
    class Reader:
        calls=0
        def read(self,*args,**kwargs):
            self.calls+=1;assert kwargs['independent'];return Observation(raw_text='钢铠鸦',confidence=.99)
    b=Reader();r=dict(command_checkpoint={},snapshot=dict(pokemon=[
        dict(slot='own_active_1',species=dict(raw_text='',confidence=.1)),
        dict(slot='own_active_2',species=dict(raw_text='旧文字',confidence=1),identity_reused_from='old')]))
    capture_checkpoint_huds(r,np.zeros((603,1311,3),dtype=np.uint8),b)
    assert b.calls==3
    assert r['command_checkpoint']['hud_observations'][0]['species']['confidence']==.1
    assert not r['command_checkpoint']['hud_observations'][1].get('identity_reused_from')


def test_independent_ocr_bypasses_fuzzy_region_reuse_but_keeps_exact_predict_cache(tmp_path,monkeypatch):
    import numpy as np
    from collections import Counter
    from models import Observation
    from recognition.fast_video import CachedOCR
    ocr=CachedOCR(tmp_path,Counter());image=np.zeros((20,20,3),dtype=np.uint8)
    calls=[]
    monkeypatch.setattr(ocr.backend,'read',lambda *args,**kwargs:(calls.append(1) or Observation(raw_text='钢铠鸦',confidence=1)))
    ocr.read(image,(0,0,20,20));ocr.timestamp=1
    ocr.read(image,(0,0,20,20));assert len(calls)==1
    ocr.read(image,(0,0,20,20),independent=True);assert len(calls)==2


def test_gap_links_only_prior_ordered_message_coverage_including_same_timestamp():
    e=engine()
    def evidence_event(name,t):
        return BattleEvent(name,'coverage_observation','field',None,None,'Saved message coverage',{},None,
            [Evidence('video_message',name,[name],dict(timestamp=t,image='frame.png'))],None,'supported',[],dict(battle_id='test',observation_time=t))
    e.apply(evidence_event('earlier',4),sequence=5)
    e.apply(evidence_event('future_same_timestamp',5),sequence=7)
    r=e.apply(checkpoint(sids=(248,530,373,903)),sequence=6)
    links=outcomes(r)[0]['historical_gap']['message_and_coverage_evidence']
    assert [x['event_id'] for x in links]==['earlier']


@pytest.mark.parametrize('location',['bench','unplaced_entry'])
def test_unplaced_or_benched_same_species_is_not_merged_into_new_occupancy(location):
    e=engine();e.initial=deepcopy(e.state);e.history=[]
    pid=e.initial.sides['self'].active_slots.pop('left')
    e.initial.pokemon[pid].location.value=dict(kind=location,slot=None)
    e.replay();r=add(e,checkpoint());o=outcomes(r)[0]
    assert o['corrected_instance_id']!=pid
    ep=next(x for x in e.state.knowledge['active_entry_episodes'] if x['episode_id']==o['active_episode_id'])
    assert pid in ep['possible_prior_instance_ids']


def test_correction_without_prior_episode_and_partial_attack_cannot_verify():
    e=engine();e.initial=deepcopy(e.state);e.history=[]
    e.initial.knowledge.pop('active_entry_episodes',None);e.replay()
    assert outcomes(add(e,checkpoint(sids=(248,530,373,903))))[0]['corrected']
    s=CommandCheckpointSchedule()
    for t in [1,1.5,2]:
        assert s.observe(dict(timestamp=t,source_id=str(t),ui=dict(phase='battle_animation')),
            dict(normal_controls=False,eligible=False,visible_slots=['own_active_1']),{}) is None


def test_audit_compatibility_accepts_capture_only_changes_and_rejects_detector_changes(tmp_path,monkeypatch):
    import scripts.report_m238w as report
    root=tmp_path/'repo';folder=root/'cached';path=root/'recognition/command_checkpoint.py'
    path.parent.mkdir(parents=True);(folder/'source/recognition').mkdir(parents=True)
    original='VERSION="v1"\ndef inspect_command(image):return True\nclass CommandCheckpointSchedule:pass\ndef capture_checkpoint_huds():return 1\n'
    path.write_text(original);(folder/'source/recognition/command_checkpoint.py').write_text(original)
    (folder/'audit-manifest.json').write_text(__import__('json').dumps(dict(identity={'recognition/command_checkpoint.py':report.sha(path)})))
    monkeypatch.setattr(report,'ROOT',root)
    path.write_text(original.replace('return 1','return 2'))
    assert report.audit_compatibility(folder)['status']=='compatible'
    path.write_text(original.replace('return True','return False'))
    with pytest.raises(AssertionError,match='UI detection'):report.audit_compatibility(folder)


def strict_checkpoint(t=5):
    c=checkpoint(t=t);c.attributes['checkpoint'].update(stable=False,previous_timestamp=None,window_mode='single_frame_strict')
    c.attributes['checkpoint']['inspection'].update(normal_controls=True,eligible=True,
        reason='normal_four_hud_command',visible_slots=list(SLOT_REGIONS),control_bounds=[[[1,2,101,102]],[[1,2,101,102]]])
    for o in c.attributes['observations']:o['icon']=dict(status='resolved',species_id=next(k for k,v in NAMES.items() if v==o['species']['raw_text']))
    return c


def test_strict_single_frame_corrects_only_supported_slot_and_does_not_retry():
    e=engine();c=strict_checkpoint();c.attributes['observations'][0]['species']['raw_text']=NAMES[248]
    c.attributes['observations'][0]['icon']['species_id']=248
    before=deepcopy(e.state.to_dict());r=add(e,c)
    assert outcomes(r)[0]['corrected'] and r.bindings['command_reconciliation']['corrections']==1
    for side,slot in [('self','right'),('opponent','left'),('opponent','right')]:
        pid=before['sides'][side]['active_slots'][slot]
        assert e.state.to_dict()['pokemon'][pid]==before['pokemon'][pid]
    c=strict_checkpoint(6);assert add(e,c).bindings['command_reconciliation']['status']=='duplicate_phase_attempt_ignored'


@pytest.mark.parametrize('failure',['low','missing','partial','ambiguous','icon_conflict','no_controls','few_icons','future_nickname'])
def test_strict_single_frame_cannot_correct_with_any_insufficient_identity(failure):
    e=engine();c=strict_checkpoint();obs=c.attributes['observations']
    obs[0]['species']['raw_text']=NAMES[248];obs[0]['icon']['species_id']=248
    if failure=='low':obs[1]['species']['confidence']=.97
    elif failure=='missing':obs[1]['species']['raw_text']=''
    elif failure=='partial':obs[1]['visible']=False
    elif failure=='ambiguous':obs[1]['species']['raw_text']='Unknown nickname'
    elif failure=='icon_conflict':obs[1]['icon']['species_id']=248
    elif failure=='no_controls':c.attributes['checkpoint']['inspection']['control_bounds']=[]
    elif failure=='few_icons':
        for o in obs[:2]:o['icon']={}
    else:
        e.initial=deepcopy(e.state);e.history=[]
        remember_alias(e.initial,'Later',dict(species_id=530),[dict(sources=[dict(details=dict(timestamp=9))])],side='self',instance_id=None)
        e.replay();obs[1]['species']['raw_text']='Later'
    before=deepcopy(e.state.to_dict()['pokemon']);r=add(e,c)
    assert all(o['status']=='inconclusive' for o in outcomes(r))
    assert e.state.to_dict()['pokemon']==before


@pytest.mark.local_artifacts
def test_real_saved_single_frame_observation_detects_controlled_state_error_without_new_recognition():
    import json,hashlib
    from recognition.command_checkpoint import checkpoint_event
    base=Path('.cache/battles/sample_battle_6/event-driven')
    path=base/'m238-scrolling-semantics-v4/observations.json'
    if not path.exists():pytest.skip('Optional saved Battle 6 observations absent')
    rows=json.loads(path.read_text())['observations']
    row=deepcopy(next(r for r in rows if r['image'].endswith('/000269.png')))
    image_path=Path(row['image']);assert hashlib.sha256(image_path.read_bytes()).hexdigest()==row['sha256']
    schedule=CommandCheckpointSchedule();inspection,attempt=schedule.inspect(row,cv2.imread(str(image_path)))
    assert attempt and attempt['window_mode']=='single_frame_strict'
    row['command_checkpoint']=attempt
    e=StateEngine(BattleState('test',knowledge=dict(identity_v1=True,reliability_v1=True,reliability_v2=True,
        active_continuity_v1=True,active_persistence_v1=True,command_reconciliation_v1=True)))
    for i,(side,slot,sid) in enumerate([('self','left',861),('self','right',1018),('opponent','left',727),('opponent','right',1000)],1):
        e.apply(hud(i,1,sid,side=side,slot=slot,hp=dict(current=50,maximum=100),
            mon=dict(raw_text={861:'长毛巨魔',1018:'铝钢桥龙',727:'炽焰咆哮虎',1000:'赛富豪'}[sid],confidence=.99,
                resolution=dict(status='resolved',method='exact',species_id=sid,confidence='strong',
                    canonical_identity=f'pokeapi:pokemon:{sid}',identity_status='resolved_unique'))),sequence=i)
    correct_prediction=deepcopy(e.state)
    incorrect_prediction=deepcopy(correct_prediction)
    wrong=incorrect_prediction.pokemon[incorrect_prediction.sides['self'].active_slots['left']]
    wrong.species.value.update(species_id=823,canonical_id='pokeapi:species:823',name='钢铠鸦')
    e=StateEngine(incorrect_prediction)
    before=deepcopy(e.state.to_dict());history=deepcopy([h.event for h in e.history])
    r=add(e,checkpoint_event(row,'test'));result=outcomes(r)
    assert [o['status'] for o in result]==['conflict','match','match','match']
    assert result[0]['observed']['species_id']==861 and result[0]['corrected']
    assert [h.event for h in e.history[:-1]]==history
    new=e.state.pokemon[e.state.sides['self'].active_slots['left']];assert not new.hp.current.known
    for side,slot in [('self','right'),('opponent','left'),('opponent','right')]:
        pid=before['sides'][side]['active_slots'][slot];assert e.state.to_dict()['pokemon'][pid]==before['pokemon'][pid]

    assert correct_prediction.pokemon[correct_prediction.sides['self'].active_slots['left']].species.value['species_id']==861
