"""M3.2.2 synthetic temporal/adapter truth tests, not real hidden ground truth."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from battle_evidence.speed_replay import (TimeIndex, available_time, causal_state, DeterministicHistory,
                                          current_identity, possible_forms, universe)
from battle_evidence.speed_adapter import audit_pair, own_form_speed, relevant_unknowns
from battle_evidence.speed_replay_offline import timed_review, chronological_audit
from speed_order.core import identity_key

PROFILE='showdown-champions-reference-v1'
E=dict(sources=['synthetic:fixture'],basis='synthetic',confidence='declared synthetic truth')
BASE=json.loads(Path('examples/speed_order/v2/ordinary.json').read_text())['input']['observations'][0]


def obs(oid='a',speed=120,first='opp'):
    value=deepcopy(BASE);value.update(id=oid,decision_id=oid)
    value['state']['participants']['own']['actual_speed']=speed
    value['sequence']=[first+':move',('own' if first=='opp' else 'opp')+':move']
    return value


def configs(speeds=(120,121,122),items=('none',),abilities=('Blaze',)):
    return [dict(id=f'{s}:{a}:{i}',speed=s,ability=a,item=i,training=None)
            for s in speeds for a in abilities for i in items]


def fact(value,source='old'):
    return dict(known=True,value=value,event_ids=[source])


def recognized():
    value=obs();result={}
    for n,role in enumerate(['own','opp']):
        aid=role+':move'
        result[aid]=dict(id=aid,event_id=role+':source',battle_id='synthetic',origin='synthetic',
            instance_id=role,side='self' if role=='own' else 'opponent',timestamp=10+n,
            turn_id='turn:1',actor_identity_reliable=True,move_identity_reliable=True,
            move='pokeapi:move:53',observed_species='pokeapi:species:6',
            membership=dict(status='confirmed_local_membership'),priority=dict(effective_priorities=[0],status='supported'),
            sources=[dict(source_id='synthetic:'+role,timestamp=10+n)],text='synthetic move')
    state=dict(pokemon={iid:dict(form=fact('pokeapi:pokemon:6'),ability=fact('pokeapi:ability:66'),
                                stages=dict(speed=fact(0)),status=fact('none')) for iid in ['own','opp']},
               trick_room=dict(active=fact(False)))
    builds={'own':dict(canonical_identity='pokeapi:species:6',stats=dict(speed=120),item='none')}
    relation=dict(id='comparison:1',action_ids=['own:move','opp:move'],intervening_event_ids=[])
    return result,state,builds,relation


def attachment():
    value=obs();state=value['state']
    return dict(verified=True,origin='synthetic',available_at=11,evidence=deepcopy(E),
        pending_coverage_complete=True,pending_action_ids=['own:move','opp:move'],subject='opp',
        state=state,initial_changes=[],alternatives=[],changes={},
        outcomes={a['id']:'completed' for a in value['actions']},
        activation={a['id']:a['activation'] for a in value['actions']},
        configuration_domain=dict(identity='Charizard',form='base',abilities=['Blaze'],items=['none'],
            known_training_points={'speed':0},alignments=[{'increase':None,'decrease':None}],
            complete_given_evidence=True,evidence=deepcopy(E),available_at=0))


def test_floor_seek_never_selects_future_frames_or_snapshots():
    index=TimeIndex([dict(timestamp=.5,image='a'),dict(timestamp=1.1,image='b'),dict(timestamp=3.7,image='c')])
    assert index.at(0) is None
    assert index.at(.5)['image']=='a'
    assert index.at(1.09)['image']=='a'
    assert index.at(1.1)['image']=='b'
    assert index.at(999)['timestamp']==3.7
    a=index.at(1.1);a['image']='changed'
    assert index.at(1.1)['image']=='b'
    with pytest.raises(ValueError):index.at(float('nan'))


def test_exact_source_pts_and_chunk_global_time_preserved():
    from battle_evidence.speed_replay_offline import frame_rows
    rows=frame_rows([dict(timestamp=61.75,source_id='chunk2#1.75',source_pts=1050,
        source_time_base='1/600',seek_origin_seconds=60,chunk_id='chunk2',chunk_timestamp=1.75,
        global_timestamp=61.75,image='source.png',sha256='abc',context_after={'future':'must not be used'})])
    assert rows[0]['source_pts']==1050 and rows[0]['chunk_timestamp']==1.75
    assert rows[0]['timestamp']==61.75 and 'context_after' not in rows[0]


def test_uncertain_time_does_not_apply_before_safe_source_bound():
    row=dict(timestamp=5,time_interval=[4,7],sources=[dict(timestamp=6)],available_at=8)
    assert available_time(row)==8
    with pytest.raises(ValueError):available_time(dict(timestamp=float('inf')))


def test_future_item_mega_and_unobserved_individual_filtered_from_saved_state():
    saved=dict(timestamp=5,observable=dict(pokemon={
        'opp':dict(side='opponent',identity=fact('pokeapi:species:6','old'),
                   form=fact('pokeapi:pokemon:6','old'),item=fact('Choice Scarf','future')),
        'future_individual':dict(side='opponent',form=fact('pokeapi:pokemon:727','future'))}))
    early=causal_state(saved,5,dict(old=1,future=10))
    assert early['pokemon']['opp']['item']['value'] is None
    assert 'future_individual' not in early['pokemon']
    assert current_identity(early['pokemon']['opp'])=='pokeapi:species:6'
    saved['observable']['pokemon']['opp']['form']=fact('pokeapi:form:10135','future')
    assert current_identity(causal_state(saved,5,dict(old=1,future=10))['pokemon']['opp']) is None
    with pytest.raises(ValueError,match='future saved state'):
        causal_state(dict(saved,timestamp=10),5,dict(old=1,future=10))


def test_history_revealed_item_applies_only_at_later_snapshot_backward_forward_identical():
    history=DeterministicHistory(configs((120,),items=('none','Choice Scarf')),profile=PROFILE)
    first=obs('first',speed=120);history.submit(first,10)
    second=obs('revelation',speed=180);second['state']['participants']['opp']['item']='Choice Scarf'
    result=history.submit(second,30)
    assert result['certified']['configuration_count']==1
    assert history.at(10)['certified']['configuration_count']==2
    assert history.at(29.999)['certified']['remaining_items']==['Choice Scarf','none']
    assert history.at(30)['certified']['remaining_items']==['Choice Scarf']
    backward=history.at(10);history.at(30)
    assert history.at(10)==backward


def test_repeated_observation_and_same_species_individuals_do_not_merge():
    history=DeterministicHistory(configs(),profile=PROFILE);a=obs()
    result=history.submit(a,10)
    assert history.submit(deepcopy(a),11)['status']=='duplicate_ignored'
    assert len(history.observations)==1 and len(history.rows)==1
    b=obs('different');b['state']['participants']['opp']['instance_id']='other'
    result=history.submit(b,12)
    assert not result['admitted'] and result['certified']==history.at(10)['certified']
    altered=deepcopy(a);altered['sequence'].reverse()
    with pytest.raises(ValueError,match='Revised evidence'):
        history.submit(altered,13)


def test_same_physical_decision_under_another_relation_id_is_not_resubmitted():
    history=DeterministicHistory(configs(),profile=PROFILE);a=obs('original')
    history.submit(a,10)
    duplicate=deepcopy(a);duplicate['id']='another_relation_same_actions'
    duplicate['evidence']['sources']=['synthetic:additional_review']
    result=history.submit(duplicate,11)
    assert result['status']=='duplicate_ignored' and result['duplicate_of']=='original'
    assert len(history.observations)==len(history.rows)==1


def test_switch_and_reentry_same_stable_individual_retains_constraints():
    history=DeterministicHistory(configs(),profile=PROFILE)
    history.submit(obs('before_switch',speed=121),10)
    result=history.submit(obs('after_reentry',speed=122),50)
    assert result['certified']['feasible']['values']==[122]
    assert history.at(20)['certified']['feasible']['values']==[121,122]


def test_contradiction_does_not_reset_and_unresolved_retains_certified_empty():
    history=DeterministicHistory(configs((120,122)),profile=PROFILE)
    history.submit(obs('faster',122),10)
    result=history.submit(obs('slower',120,first='own'),20)
    assert result['status']=='empty' and result['certified']['feasible']['values']==[]
    assert result['conflict']['observation_ids']==['faster','slower']
    unknown=obs('unknown');unknown['state']['field']['weather']=None
    later=history.submit(unknown,30)
    assert later['status'] in {'empty','unresolved'} and later['certified']['feasible']['values']==[]


def test_resource_exhaustion_never_presents_partial_enumeration_as_feasible():
    history=DeterministicHistory(configs(),profile=PROFILE,max_evaluations=1)
    result=history.submit(obs(),10)
    assert result['status']=='unresolved' and not result['admitted']
    assert result['certified']['feasible']['values']==[120,121,122]
    assert result['certified']['status']=='declared_initial_universe'
    full=universe('pokeapi:species:6')
    assert len(full['items'])==167 and full['underlying_item_configuration_count']==231462
    assert full['configuration_count']==8316 # Four order classes plus two compatible Mega stones.
    assert 'configuration_product_exceeds_v2_limit' not in full['unresolved_reasons']
    assert 'Quick Claw' in full['items'] and not full['unsupported_items']
    assert 'configuration_product_exceeds_v2_limit' in universe('pokeapi:species:6',max_configurations=100)['unresolved_reasons']


def test_same_priority_tie_and_gaps_persist_in_ledger():
    history=DeterministicHistory(configs((120,122)),profile=PROFILE)
    result=history.submit(obs(),10)
    assert result['certified']['feasible']['intervals']==[[120,120],[122,122]]
    assert result['certified']['tie_compatible']==['120:Blaze:none']


def test_tailwind_trick_room_and_prankster_alternatives_use_existing_solver():
    history=DeterministicHistory(configs((120,122)),profile=PROFILE)
    a=obs('wind',speed=241);a['state']['participants']['opp']['tailwind']=True
    assert history.submit(a,10)['certified']['feasible']['values']==[122]
    b=obs('room',speed=122);b['state']['field']['trick_room']=True
    assert history.submit(b,20)['certified']['feasible']['values']==[122]
    c=obs('priority',speed=214)
    c['state']['participants']['opp'].update(identity='Whimsicott',form='base')
    c['actions'][1]['move']='pokeapi:move:366';c['state']['field']['weather']='sun'
    history=DeterministicHistory(configs((100,108),abilities=('Prankster','Chlorophyll')),profile=PROFILE)
    result=history.submit(c,10)
    assert result['certified']['feasible']['values']==[100,108]


def test_quick_claw_unknown_not_misread_as_nonactivation():
    history=DeterministicHistory(configs((100,),items=('Quick Claw',)),profile=PROFILE)
    assert history.submit(obs(speed=180),10)['certified']['feasible']['values']==[100]
    a=obs('inactive',speed=180)
    a['actions'][1]['activation'].update(state='not_activated',coverage_complete=False)
    result=history.submit(a,20)
    assert result['status']=='unresolved' and result['certified']['feasible']['values']==[100]


def test_dynamic_paralysis_and_mega_before_after_updates_are_causal():
    from speed_order import configuration_domain
    values=configuration_domain(identity='Charizard',form='base',abilities=['Blaze'],items=['Charizardite Y'],
        known_training_points={'speed':0},alignments=[{'increase':None,'decrease':None}])['configurations']
    history=DeterministicHistory(values,profile=PROFILE)
    a=obs('base',100);history.submit(a,10)
    b=obs('mega',100);b['initial_changes']=[dict(kind='transform',target='opp',
        values={'forms':['Mega Charizard Y']},evidence=deepcopy(E))]
    result=history.submit(b,20)
    assert result['status']=='exact'
    assert history.at(10)['observation_id']=='base'
    # A documented effect after the first action changes the next pending metric.
    c=obs('paralysis',121,first='own')
    c['actions'][0]['changes']=[dict(kind='set',target='opp',values={'status':'paralysis'},evidence=deepcopy(E))]
    p=deepcopy(c['state']['participants']['own']);p.update(instance_id='third',actual_speed=70)
    c['state']['participants']['third']=p
    third=deepcopy(c['actions'][0]);third.update(id='third:move',individual='third',changes=[])
    c['actions'].append(third);c['sequence']=['own:move','third:move','opp:move']
    history=DeterministicHistory(configs((120,)),profile=PROFILE)
    assert history.submit(c,30)['status']=='exact'


def test_adapter_does_not_invent_pending_set_from_two_recognized_actions():
    actions,state,builds,relation=recognized()
    result=audit_pair(relation,actions,state,builds)
    assert result['status']=='deferred'
    assert 'pending_action_coverage_not_certified' in result['blockers']
    assert result['observation'] is None


def test_reviewed_adapter_calls_v2_without_unrelated_weather_hp_or_damage_fields():
    actions,state,builds,relation=recognized();review=attachment()
    review['state']['field'].update(weather=None,terrain=None)
    for p in review['state']['participants'].values():
        p.update(ability_active=None,unburden_active=None)
    result=audit_pair(relation,actions,state,builds,review=review)
    assert result['status']=='prepared',result['blockers']
    assert result['irrelevant_field_projections']
    history=DeterministicHistory(result['configurations'],profile=PROFILE)
    assert history.submit(result['observation'],result['timestamp'])['status']=='exact'
    assert 'defensive/offensive stats' in result['not_required']


def test_adapter_cannot_override_own_speed_or_recognized_move_and_no_cross_bracket_constraint():
    actions,state,builds,relation=recognized();review=attachment()
    review['state']['participants']['own']['actual_speed']=999
    assert audit_pair(relation,actions,state,builds,review=review)['status']=='deferred'
    actions['own:move'].update(move='pokeapi:move:182',priority=dict(effective_priorities=[4],status='supported'))
    result=audit_pair(relation,actions,state,builds,review=attachment())
    assert result['status']=='rejected' and result['observation'] is None


def test_build_binding_and_future_pending_action_delay_availability():
    actions,state,builds,relation=recognized();builds['own']['available_at']=20
    assert audit_pair(relation,actions,state,builds)['own_current_form_speed'] is None
    review=attachment();review['available_at']=20
    result=audit_pair(relation,actions,state,builds,review=review)
    assert result['status']=='prepared' and result['timestamp']==20
    actions['opp:move']['timestamp']=50;actions['opp:move']['sources'][0]['timestamp']=50
    assert audit_pair(relation,actions,state,builds,review=review)['timestamp']==50


def test_review_sources_cannot_certify_earlier_than_later_item_revelation():
    review=attachment();review.update(origin='recorded',reviewer=dict(kind='agent',id='synthetic-test-reviewer'))
    def replace(value):
        if isinstance(value,dict):
            if set(value)=={'sources','basis','confidence'}:
                value.update(sources=['late_item'],basis='direct')
            for v in value.values():replace(v)
        elif isinstance(value,list):
            for v in value:replace(v)
    replace(review)
    assert timed_review(review,dict(late_item=30),[])['available_at']==30
    with pytest.raises(ValueError,match='Unresolvable'):
        timed_review(review,{},[])


def test_relevance_is_actor_specific_and_never_fills_speed_relevant_unknowns():
    p={'own':dict(ability='Gale Wings',stage=0,tailwind=False,status='none',hp_full=None),
       'opp':dict(ability='Blaze',stage=0,tailwind=False,status='none')}
    fields=dict(trick_room=False,weather=None,terrain=None)
    assert not relevant_unknowns(p,fields,dict(own='pokeapi:move:89',opp='pokeapi:move:403'))
    assert 'own:priority_HP_condition_unknown' in relevant_unknowns(p,fields,dict(own='pokeapi:move:403',opp='pokeapi:move:89'))
    p['own']['ability']='Chlorophyll'
    assert 'relevant_weather_unknown' in relevant_unknowns(p,fields,dict(own='pokeapi:move:89',opp='pokeapi:move:89'))


def test_unknown_form_keeps_all_current_catalog_branches_without_selecting_base():
    mon=dict(identity=fact('pokeapi:species:6'),form=dict(known=False,value=None))
    assert current_identity(mon) is None
    assert set(possible_forms(mon))=={'pokeapi:species:6','pokeapi:form:10134','pokeapi:form:10135'}
    mon['form']=fact('pokeapi:form:10135')
    assert possible_forms(mon)==['pokeapi:form:10135']


def test_speed_neutral_items_share_branch_but_keep_specific_item_hypotheses():
    from battle_evidence.speed_items import item_classes
    classes=item_classes('pokeapi:species:6',['none','Light Clay','Focus Sash','Life Orb','Choice Scarf','Iron Ball','Quick Claw'])
    assert {c['representative'] for c in classes}=={'none','Choice Scarf','Iron Ball','Quick Claw'}
    neutral=next(c for c in classes if c['representative']=='none')
    assert neutral['members']==['Focus Sash','Life Orb','Light Clay','none']
    assert 'pokeapi:item:252' in neutral['member_ids']
    # Stones remain distinct despite neutral Speed, preserving the Mega branch.
    classes=item_classes('pokeapi:species:6',['Charizardite X','Charizardite Y','Focus Sash'])
    assert {c['representative'] for c in classes}=={'none','Charizardite X','Charizardite Y'}


def test_adapter_projects_items_before_v2_and_does_not_multiply_neutral_configurations():
    actions,state,builds,relation=recognized();review=attachment()
    review['configuration_domain']['items']=['none','Light Clay','Focus Sash','Life Orb','Choice Scarf','Iron Ball','Quick Claw']
    review['state']['participants']['own']['item']='Light Clay'
    result=audit_pair(relation,actions,state,builds,review=review)
    assert result['status']=='prepared'
    assert len(result['configurations'])==4
    assert result['observation']['state']['participants']['own']['item']=='none'
    assert next(c for c in result['item_equivalence_classes'] if c['representative']=='none')['members']==['Focus Sash','Life Orb','Light Clay','none']
    assert DeterministicHistory(result['configurations'],profile=PROFILE).submit(result['observation'],11)['status']=='exact'


def test_item_projection_does_not_hide_unburden_or_grassy_glide_conditions():
    from battle_evidence.speed_items import project_state_items
    state=obs()['state'];state['participants']['opp'].update(item='Focus Sash',unburden_active=True)
    with pytest.raises(ValueError,match='Unburden'):
        project_state_items(state)
    state['participants']['opp'].update(item='Air Balloon',unburden_active=False,grounded=None)
    projected,_=project_state_items(state)
    assert projected['participants']['opp']['grounded'] is None # Never invented by item equivalence.


def test_form_specific_own_speed_uses_original_training_and_stone():
    p=dict(canonical_identity=identity_key('Swampert','base'),stats=dict(speed=80),item='Swampertite',
           training_points={s:0 for s in ['hp','attack','defense','special_attack','special_defense','speed']},
           alignment=dict(increase=None,decrease=None))
    assert own_form_speed(p,identity_key('Swampert','Mega Swampert'))==(90,None)
    p['item']='Charizardite Y'
    assert own_form_speed(p,identity_key('Swampert','Mega Swampert'))[0] is None


def synthetic_audit(review_time=11):
    actions,observable,builds,relation=recognized()
    for iid,p in observable['pokemon'].items():p.update(side='opponent' if iid=='opp' else 'self',instance_id=iid)
    ledger=[dict(id='old',timestamp=0,source_event_type='send_out',instance_id='opp',position=0,sources=[],text='synthetic entry')]
    saved={'old':dict(after=dict(timestamp=0,observable=observable))}
    for n,a in enumerate(actions.values(),1):
        ledger.append(dict(id=a['event_id'],timestamp=a['timestamp'],source_event_type='move_execution',
            instance_id=a['instance_id'],position=n,sources=a['sources'],text=a['text']))
        saved[a['event_id']]=dict(before=dict(timestamp=a['timestamp'],observable=observable),
                                after=dict(timestamp=a['timestamp'],observable=observable))
    review=attachment();review['available_at']=review_time
    domain=review['configuration_domain'];domain.pop('known_training_points');domain['point_domains']={'speed':[0,1,2]}
    group=dict(turn_id='turn:1',local_index=1,membership_status='confirmed',action_ids=list(actions))
    visual=dict(schema='normal-screen-three-hud-v2.2',reconstruction=dict(ledger=ledger),
        visual=dict(segments=[dict(id='turn:1',local_index=1,status='confirmed',start=[1,1],end=[20,20])],
                    phase_history=[dict(frame_id='f0',timestamp=0,phase='UNKNOWN',possible_phases=['UNKNOWN'],source_id='frame0')]))
    for a in actions.values():a['confidence']={'interpretation':'synthetic truth'}
    return chronological_audit('synthetic',visual,dict(snapshots=saved),{},
        dict(actions=list(actions.values()),relations=[relation],groups=[group]),builds,
        [dict(timestamp=t,source_id=f'frame{t}',image=f'{t}.png',sha256='synthetic') for t in [0,10,11,30]],
        reviews={relation['id']:review})


def test_full_adapter_snapshot_pipeline_separates_recognition_admission_and_narrowing():
    result=synthetic_audit()
    assert result['counts']['recognized_actions']==2
    assert result['counts']['admitted']==result['counts']['narrowed']==1
    early=TimeIndex(result['snapshots']).at(10)
    late=TimeIndex(result['snapshots']).at(11)
    assert early['opponents']['opp']['certified_order_feasible'] is None
    assert late['opponents']['opp']['certified_order_feasible']['feasible']['values']==[120]
    assert late['frame']['timestamp']==11
    assert result['turns'][0]['actions'][0]['after_announcement']


def test_review_available_later_does_not_leak_narrowing_to_earlier_actions():
    result=synthetic_audit(review_time=30)
    index=TimeIndex(result['snapshots'])
    assert index.at(11)['opponents']['opp']['certified_order_feasible'] is None
    assert index.at(29.99)['opponents']['opp']['certified_order_feasible'] is None
    assert index.at(30)['opponents']['opp']['certified_order_feasible']['feasible']['values']==[120]


@pytest.mark.local_artifacts
@pytest.mark.parametrize('number',[10,11,12])
def test_saved_real_stage_a_has_causal_frames_actions_and_no_fabricated_constraints(number):
    from battle_evidence.speed_replay_offline import file_hash
    root=Path(f'.cache/battles/sample_battle_{number}/m322-speed-replay')
    pointer=root/'latest.json'
    if not pointer.exists():
        pytest.skip('Optional historical Stage A audit absent')
    manifest_path=Path(json.loads(pointer.read_text())['path']);manifest=json.loads(manifest_path.read_text())
    assert manifest['status']=='complete'
    for name,sha in manifest['outputs'].items():assert file_hash(manifest_path.parent/name)==sha
    result=json.loads((manifest_path.parent/'replay.json').read_text())
    assert result['stage_a_status']=='blocked_no_admitted_constraints'
    assert result['counts']['admitted']==result['counts']['narrowed']==0
    event_times={e['id']:e['timestamp'] for e in result['timeline']}
    action_times={a['id']:a['timestamp'] for turn in result['turns'] for a in turn['actions']}
    action_times.update({a['id']:a['timestamp'] for a in result['unassigned_actions']})
    for snapshot in result['snapshots']:
        assert snapshot['frame'] is None or snapshot['frame']['timestamp']<=snapshot['timestamp']
        assert snapshot['state_source_available_at'] is None or snapshot['state_source_available_at']<=snapshot['timestamp']
        assert all(action_times[aid]<=snapshot['timestamp'] for aid in snapshot['observed_action_ids'])
        assert all(p.get('certified_order_feasible') is None for p in snapshot['opponents'].values())
    assert all('context_after' not in row for row in result['frames'])
    assert result['metrics']['video_decodes']==result['metrics']['ocr_calls']==result['metrics']['state_engine_replays']==0
