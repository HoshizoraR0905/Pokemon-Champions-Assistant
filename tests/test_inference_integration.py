"""Portable integration contracts; saved recording checks are run separately."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import subprocess

import pytest

from battle_events.parser import EventParser
from tracking.battle_state import BattleState, PokemonState, fact
from tracking.state_engine import StateEngine
from tracking.initial_conditions import entering
from battle_evidence.inference_integration import stat_pairs
from damage import calculate
from damage.inverse import infer_attack_stat
from tests.test_inverse_damage import BASE, observation


def parsed(text, t, slot=None):
    e=EventParser().parse(dict(entry_id=str(t),raw_text=text,ocr_confidence=.99,source_id='test#'+str(t)),battle_id='test')
    e.attributes.update(observation_time=t,battle_id='test')
    if slot:e.attributes['slot']=slot
    return e


def engine(review=True):
    e=parsed('上吧！大嘴鸥！',1,'left')
    state=BattleState('test')
    if review:state.knowledge['battle_start_review']=dict(event_id=e.event_id,covers_start=True,reviewer='synthetic',sources=['test#1'])
    result=StateEngine(state);result.apply(e,sequence=1)
    return result


def test_opening_neutral_and_unknown_are_distinct_and_roundtrip():
    known=engine();unknown=engine(False)
    assert known.state.weather.kind.value=='none' and known.state.terrain.kind.value=='none'
    assert known.state.trick_room.active.value is False
    assert all(s.conditions['tailwind'].active.value is False for s in known.state.sides.values())
    assert all(s.value.value==0 for p in known.state.pokemon.values() for s in p.stages.values())
    assert unknown.state.weather.kind.knowledge=='unknown'
    assert all(not s.value.known for p in unknown.state.pokemon.values() for s in p.stages.values())
    from tracking.battle_state import from_dict
    assert from_dict(known.state.to_dict()).to_dict()==known.state.to_dict()


def test_weather_terrain_tailwind_changes_endings_and_retraction():
    e=engine()
    e.apply(parsed('开始下雨了！',2),sequence=2)
    assert e.state.weather.kind.value=='rain'
    e.apply(parsed('脚下青草如茵！',3),sequence=3)
    assert e.state.terrain.kind.value=='grassy'
    e.apply(parsed('从我方身后吹起了顺风！',4),sequence=4)
    assert e.state.sides['self'].conditions['tailwind'].active.value is True
    for i,text in enumerate(['我方的顺风停止了！','雨停了！','脚下的青草消失了！'],5):
        e.apply(parsed(text,i),sequence=i)
    assert e.state.weather.kind.value=='none' and e.state.terrain.kind.value=='none'
    assert e.state.sides['self'].conditions['tailwind'].active.value is False
    e.retract(parsed('雨停了！',6).event_id,reason='synthetic correction')
    assert e.state.weather.kind.value=='rain'


def test_reference_stage_changes_switch_reset_idempotence_and_retraction():
    e=engine();boost=parsed('大嘴鸥的防御提高了！',2)
    pid=next(iter(e.state.pokemon));boost.side='self'
    boost.uncertainty=[u for u in boost.uncertainty if u!='side_unknown']
    boost.attributes['side_basis']=['synthetic explicit self binding']
    boost.attributes['actor_instance_id']=pid
    e.apply(boost,sequence=2)
    assert e.state.pokemon[pid].stages['defense'].value.value==1
    e.apply(boost,sequence=2)
    assert e.state.pokemon[pid].stages['defense'].value.value==1
    departure=parsed('上吧！大嘴鸥！',3,'left');departure.event_type='switch_out'
    departure.attributes['actor_instance_id']=pid
    e.apply(departure,sequence=3)
    assert e.state.pokemon[pid].stages['defense'].value.value==0
    e.retract(departure.event_id,reason='synthetic switch correction')
    assert e.state.pokemon[pid].stages['defense'].value.value==1
    e.retract(boost.event_id,reason='synthetic stat correction')
    assert e.state.pokemon[pid].stages['defense'].value.value==0


def test_known_inactive_trick_room_activation_and_explicit_duration_expiry():
    e=engine();start=parsed('扭曲的时空恢复了！',2)
    start.attributes.update(change='start',duration=dict(remaining=1,timing='turn_end'))
    e.apply(start,sequence=2)
    assert e.state.trick_room.active.value is True
    end=parsed('扭曲的时空恢复了！',3);end.event_type='turn_boundary'
    end.attributes=dict(observation_time=3,turn=1,boundary='end')
    e.apply(end,sequence=3)
    assert e.state.trick_room.active.value is False


def test_entry_reset_and_special_transfer_not_filled():
    e=engine();p=next(iter(e.state.pokemon.values()));p.stages['attack'].value=fact(-2,{'synthetic':True})
    entry=parsed('上吧！大嘴鸥！',4,'left')
    entering(e,e.state,p,entry,fresh=False)
    assert p.stages['attack'].value.value==0
    entry.attributes['stage_transfer_possible']=True
    entering(e,e.state,p,entry,fresh=False)
    assert not p.stages['attack'].value.known


def test_legacy_screen_activation_overrides_known_inactive_not_generic_observe():
    e=engine();screen=parsed('光墙使我方的特殊抗性提高了！',2)
    screen.attributes['change']='observe'
    assert e.apply(screen,sequence=2).application_status=='applied_candidate'
    assert e.state.sides['self'].conditions['light_screen'].active.value is True
    e.apply(parsed('我方的光墙消失了！',3),sequence=3)
    assert e.state.sides['self'].conditions['light_screen'].active.value is False


def test_genuine_coverage_gap_invalidates_neutral_context():
    from tracking.initial_conditions import coverage_gap
    e=engine();coverage_gap(e.state,parsed('missing interval',3))
    assert not e.state.weather.kind.known and not e.state.trick_room.active.known
    assert all(not s.value.known for p in e.state.pokemon.values() for s in p.stages.values())


def test_self_preview_acquisition_uses_names_and_resolver_with_bounded_reads():
    from collections import Counter
    from types import SimpleNamespace
    import numpy as np
    from models import Observation,EntityResolution
    from recognition.event_schedule import IdentitySchedule
    from tests.test_preview_switch_fixes import preview_recognizer,frame
    r,_,_=preview_recognizer();ids=[3,6,279,445,861,1018];calls=[]
    def read(image,bounds):
        i=round((bounds[1]/603-.13)/.117);calls.append(i)
        return Observation(value=str(ids[i]),confidence=.99,resolution=EntityResolution(species_id=ids[i],status='confirmed'))
    r.ocr=SimpleNamespace(read=read)
    s=IdentitySchedule();image=np.zeros((603,1311,3),dtype=np.uint8);counts=Counter()
    rows=s.acquire_team(r,frame(image,0),'team_preview','test',counts)
    assert [x['species_id'] for x in rows if x['side']=='self']==ids
    s.acquire_team(r,frame(image,.5),'team_preview','test',counts)
    assert len(calls)==6 and len(s.team['self'])==6


def test_certification_requires_four_opportunities_not_timestamp_proximity():
    from battle_evidence.turns import certify_saved_cycle
    recs=[]
    for i,pid in enumerate(['self:a','self:b','opponent:a','opponent:b']):
        recs.append(dict(event=dict(event_id=str(i),event_type='move_execution',attributes=dict(observation_time=1+i)),
            application_status='applied_candidate',bindings=dict(actor=dict(pokemon_instance_id=pid))))
    cycle=dict(start=0,source_id='command#0');ctx={'0':dict(sides=dict(self=dict(active_slots=dict(left='self:a',right='self:b')),opponent=dict(active_slots=dict(left='opponent:a',right='opponent:b'))))}
    assert certify_saved_cycle(recs,cycle,10,ctx)['status']=='certified_local_membership'
    assert certify_saved_cycle(recs[:-1],cycle,10,ctx)['status']=='unresolved'
    repeated=deepcopy(recs);repeated[3]['bindings']['actor']['pokemon_instance_id']='self:a'
    assert certify_saved_cycle(repeated,cycle,10,ctx)['status']=='unresolved'
    assert certify_saved_cycle(recs,cycle,float('inf'),ctx)['status']=='unresolved'
    historical=deepcopy(recs)
    historical[0]['reason']='move_revelation_only'
    historical[0]['event']['original_text']='记得招式：守住'
    historical[0]['event']['attributes']['source_region_type']='battle_log'
    assert certify_saved_cycle(historical,cycle,10,ctx)['status']=='unresolved'
    historical[0]['event']['original_text']='宝可梦使出了守住！'
    historical[0]['event']['attributes']['source_region_type']='battle_message'
    assert certify_saved_cycle(historical,cycle,10,ctx)['status']=='certified_local_membership'


def test_exact_six_profile_binding_is_timed_and_preserves_sealed_unbound(tmp_path):
    import hashlib
    from team_configuration import TeamConfiguration
    from team_configuration.profiles import TeamProfiles
    from tracking.knowledge_grounding import attach_matching_roster_profile,bind_attached_profile
    from tracking.battle_state import PokemonState
    team=TeamConfiguration.load('tests/fixtures/battle_evidence/sample-team7-reviewed.json')
    TeamProfiles(tmp_path/'.cache/team-profiles').register('team7',team,reviewer='synthetic')
    image=tmp_path/'preview.png';image.write_bytes(b'synthetic full six preview')
    evidence=dict(image='preview.png',sha256=hashlib.sha256(image.read_bytes()).hexdigest(),timestamp=10)
    roster=[dict(side='self',preview_row=i,species_id=sid,status='resolved',species=dict(confidence=.99),evidence=evidence)
        for i,sid in enumerate([3,6,279,445,861,1018],1)]
    source=BattleState('test',knowledge=dict(team_profile_linkage=dict(status='unbound')))
    original=source.to_dict();attached=attach_matching_roster_profile(source,roster,root=tmp_path)
    assert source.to_dict()==original
    assert attached.knowledge['team_profile_linkage']['team_id']=='sample_team_team7_20261021'
    p=PokemonState('own:pelipper','self');p.original_identity=fact(dict(species_id=279),{'synthetic':True})
    p.species=deepcopy(p.original_identity)
    p.current_variant=fact('pokeapi:pokemon:279',{'synthetic':True});attached.pokemon[p.pokemon_instance_id]=p
    bind_attached_profile(attached,p,parsed('上吧！大嘴鸥！',9,'left'))
    assert not attached.knowledge.get('team',{}).get('instances')
    bind_attached_profile(attached,p,parsed('上吧！大嘴鸥！',11,'left'))
    assert attached.knowledge['team']['instances'][p.pokemon_instance_id]['team_id']==team.data['team_id']
    assert source.to_dict()==original


def test_reference_stage_announcements_quantified_without_rewriting_source():
    from tracking.initial_conditions import quantified_stage_event
    for text,n in [('大嘴鸥的防御提高了！',1),('大嘴鸥的防御大幅降低了！',2),
                   ('对手的怪颚龙的攻击、特攻降低了！',1),('大嘴鸥的攻击、特攻大幅提高了！',2)]:
        e=parsed(text,2);before=e.to_dict();interpreted=quantified_stage_event(e)
        assert interpreted.attributes['stages']==n and e.to_dict()==before
    assert quantified_stage_event(parsed('防御也许提高了',2)).attributes.get('stages') is None
    assert quantified_stage_event(parsed('大嘴鸥的攻击、也许特攻降低了！',2)).attributes.get('stages') is None


def test_compound_stat_transition_quantifies_both_once_and_retracts():
    e=engine();pid=next(iter(e.state.pokemon))
    change=parsed('大嘴鸥的攻击、特攻降低了！',2)
    change.side='self';change.uncertainty=[]
    change.attributes.update(actor_instance_id=pid,side_basis=['synthetic explicit self binding'])
    source=change.to_dict()
    e.apply(change,sequence=2)
    assert [e.state.pokemon[pid].stages[s].value.value for s in ['attack','special_attack']]==[-1,-1]
    e.apply(change,sequence=2)
    assert [e.state.pokemon[pid].stages[s].value.value for s in ['attack','special_attack']]==[-1,-1]
    assert change.to_dict()==source
    e.retract(change.event_id,reason='synthetic correction')
    assert [e.state.pokemon[pid].stages[s].value.value for s in ['attack','special_attack']]==[0,0]


def test_real_b22_known_defender_unknown_item_inversion_and_no_future_input():
    from battle_evidence.inference_integration import invert_saved_hit
    f=json.loads(Path('tests/fixtures/inference_integration/b22-rock-slide.json').read_text())
    original=deepcopy(f)
    result=invert_saved_hit(f['episode'],f['context'],native=f['native'],retained=f['initial']['values'],stat='attack',battle_id='sample_battle_22')
    assert result['status']=='exact' and result['feasible']==f['expected']
    assert f==original and f['available_at']>=f['action_time']
    branch=result['branches'][0]
    assert 'Metronome' in branch['legal_items'] and 'Life Orb' in branch['legal_items']
    # Later final-state/item ledgers are not an input to this adapter. Its only
    # retained context is the contemporaneous snapshot with an unknown item.
    actor=f['context']['pokemon'][f['episode']['actor_instance_id']]
    assert actor['item']['identity']['knowledge']=='unknown'
    assert any(s['assignment'] for s in branch['scenarios'])


@pytest.mark.parametrize('status', ['consumed', 'none', 'lost', 'transferred'])
def test_defender_observed_empty_slot_survives_cleared_identity(status):
    from battle_evidence.inference_integration import invert_saved_hit
    f=json.loads(Path('tests/fixtures/inference_integration/b22-rock-slide.json').read_text())
    defender=f['context']['pokemon'][f['episode']['target_instance_id']]
    known=lambda v:dict(value=v,knowledge='observed')
    defender['item']['identity']=known('none')
    kwargs=dict(native=f['native'],retained=f['initial']['values'],stat='attack',battle_id='sample_battle_22')
    explicit=invert_saved_hit(f['episode'],f['context'],**kwargs)
    assert explicit['status']=='exact'
    defender['item']['identity']=dict(value=None,knowledge='unknown')
    defender['item']['status']=known(status)
    before=deepcopy(f)
    cleared=invert_saved_hit(f['episode'],f['context'],**kwargs)
    assert cleared['status']=='exact' and cleared['feasible']==explicit['feasible']
    assert f==before
    defender['item']['status']=dict(value=None,knowledge='unknown')
    unresolved=invert_saved_hit(f['episode'],f['context'],**kwargs)
    assert unresolved['status']=='unresolved'
    assert 'defender current ability/item unresolved' in unresolved['blockers']


def test_order_adapter_preserves_ties_and_unknown_order_item_alternatives():
    from battle_evidence.inference_integration import invert_saved_order
    def f(x):return dict(value=x,knowledge='observed')
    def mon(sid,ability,side,speed):
        return dict(side=side,species=f(dict(species_id=sid)),variant=f(f'pokeapi:pokemon:{sid}'),
            stages=dict(speed=dict(value=f(0))),status=f('none'),ability=dict(identity=f(ability)),item=dict(identity=f('none')),
            mechanics=dict(battle_stats=dict(current=dict(speed=f(speed)))))
    own='test:self:p';opp='test:opponent:p'
    context=dict(pokemon={own:mon(279,'Drizzle','self',121),opp:mon(6,'Blaze','opponent',None)},
        field=dict(weather=dict(kind=f('none')),terrain=dict(kind=f('none')),trick_room=dict(active=f(False))),
        sides={s:dict(conditions=dict(tailwind=dict(active=f(False)))) for s in ['self','opponent']})
    def rec(eid,pid,move):return dict(event=dict(event_id=eid,canonical_references=dict(move=dict(canonical_id=move))),bindings=dict(actor=dict(pokemon_instance_id=pid)))
    first=rec('a',opp,'pokeapi:move:53');second=rec('b',own,'pokeapi:move:542')
    proof=dict(action_event_ids=['a','b','c','d'],command_source='command#0')
    args=dict(subject=opp,native='pokeapi:species:6',retained=[120,121,122],battle_id='test',proof=proof)
    r=invert_saved_order(first,second,context,**args)
    assert r['status']=='exact' and r['feasible']['values']==[121,122] and r['tie_compatible']
    context['pokemon'][opp]['item']['identity']=dict(value=None,knowledge='unknown')
    r=invert_saved_order(first,second,context,**args)
    assert r['status']=='exact' and r['feasible']['values']==[120,121,122]
    context['pokemon'][own]['item']['identity']=dict(value=None,knowledge='unknown')
    for status in ('none','consumed','lost','transferred'):
        context['pokemon'][own]['item']['status']=dict(value=status,knowledge='observed')
        before=deepcopy(context)
        r=invert_saved_order(first,second,context,**args)
        assert r['status']=='exact' and r['feasible']['values']==[120,121,122]
        assert context==before
    context['pokemon'][own]['item']['status']=dict(value=None,knowledge='unknown')
    r=invert_saved_order(first,second,context,**args)
    assert r['status']=='unresolved' and 'known comparison item/ability unresolved' in r['blockers']


def test_mega_stat_mapping_keeps_sp_alignment_not_raw_stats():
    pairs=stat_pairs('pokeapi:pokemon:445','pokeapi:pokemon:10309','special_attack')
    assert (145,212) in pairs
    assert all(a!=b for a,b in pairs)


@pytest.mark.parametrize('trick_room',[False,True])
def test_order_form_alternatives_union_native_stats_and_preserve_unknown_items(trick_room):
    from battle_evidence.inference_integration import invert_saved_order
    from battle_evidence.configuration_domain import DEFAULT_RULE,initial_domain
    def f(v):return dict(value=v,knowledge='observed')
    own='test:self:grimmsnarl';opp='test:opponent:tyranitar'
    def mon(sid,ability,side,speed):
        return dict(side=side,species=f(dict(species_id=sid)),variant=f(None),
            ability=dict(identity=f(ability)),item=dict(identity=f('none')),
            stages=dict(speed=dict(value=f(0))),status=f('none'),
            mechanics=dict(battle_stats=dict(current=dict(speed=f(speed)))))
    ctx=dict(pokemon={own:mon(861,'Prankster','self',80),opp:mon(248,'Sand Stream','opponent',None)},
        field=dict(weather=dict(kind=f('sand')),terrain=dict(kind=f('none')),trick_room=dict(active=f(trick_room))),
        sides={s:dict(conditions=dict(tailwind=dict(active=f(False)))) for s in ['self','opponent']})
    ctx['pokemon'][own]['variant']=f('pokeapi:pokemon:861')
    def rec(eid,pid,move):return dict(event=dict(event_id=eid,canonical_references=dict(move=dict(canonical_id=move))),bindings=dict(actor=dict(pokemon_instance_id=pid)))
    first=rec('spirit',own,'pokeapi:move:789');second=rec('curse',opp,'pokeapi:move:174')
    retained=initial_domain('pokeapi:species:248')['stats']['speed']['values']
    args=dict(subject=opp,native='pokeapi:species:248',retained=retained,battle_id='test',
        proof=dict(action_event_ids=['spirit','curse','protect1','protect2'],command_source='command'),configuration_rule=DEFAULT_RULE)
    original=deepcopy(ctx)
    result=invert_saved_order(first,second,ctx,**args)
    assert result['status']=='exact' and len(result['form_branches'])==2
    assert result['feasible']['values']==([v for v in retained if v>=80] if trick_room else [72])
    assert ctx==original
    ctx['pokemon'][opp]['item']['identity']=f(dict(canonical_id='pokeapi:item:246'))
    result=invert_saved_order(first,second,ctx,**args)
    assert result['status']=='exact'
    assert result['feasible']['values']==([v for v in retained if v>=80] if trick_room else [72])
    ctx['pokemon'][opp]['item']['identity']=f(None)
    result=invert_saved_order(first,second,ctx,**args)
    assert result['status']=='exact' and result['feasible']['values']==(retained if trick_room else [72])
    blocked=invert_saved_order(second,first,ctx,**args)
    assert blocked['status']=='unresolved'
    assert any('pending-queue' in b for b in blocked['blockers'])


@pytest.mark.parametrize('count',range(6))
def test_metronome_integer_rolls_match_pinned_champions_oracle(tmp_path,count):
    request=deepcopy(BASE);request['attacker'].update(item='Metronome',metronome_count=count)
    cases=tmp_path/'cases.json';cases.write_text(json.dumps(dict(cases=[dict(id='m',input=request)])))
    if not Path('.cache/m31/oracle/node_modules/@smogon/calc').is_dir():pytest.skip('optional pinned oracle absent')
    oracle=json.loads(subprocess.check_output(['node','scripts/damage_metronome_oracle.cjs',str(cases)]))
    assert calculate(request)['distribution']['rolls']==oracle['cases'][0]['rolls']


def test_unknown_item_critical_counter_union_uses_existing_inverse():
    o=observation();o['input']['attacker']['metronome_count']=0
    variables=[dict(id=path,scope='observation',observation_ids=[o['id']],path=path,values=values)
        for path,values in [('attacker.item',['none','Life Orb','Metronome']),('field.critical',[False,True]),('attacker.metronome_count',list(range(6)))]]
    r=infer_attack_stat(observations=[o],candidate_stats=list(range(60,161)),ruleset=BASE['profile'],variables=variables)
    assert r['status']=='conditional'
    union=set()
    for scenario in r['scenarios']:union.update(scenario['feasible']['values'])
    assert set(r['feasible']['values'])==union
    assert calculate(dict(BASE,attacker=dict(BASE['attacker'],item='Metronome')))['status']=='incomplete_input'


@pytest.mark.parametrize('move,item,ability,defitem',[
    ('Hammer Arm','none','Tough Claws','none'),
    ('Body Slam','Normal Gem','none','none'),
    ('Flamethrower','none','Unnerve','Occa Berry'),
    ('Body Slam','none','Contrary','none'),
])
def test_scoped_hit_handlers_match_fixed_champions_oracle(tmp_path,move,item,ability,defitem):
    request=deepcopy(BASE);request['move']=move
    request['attacker'].update(ability=ability,item=item)
    request['defender']['item']=defitem
    if defitem=='Occa Berry':request['defender']['identity']='Venusaur'
    if not Path('.cache/m31/oracle/node_modules/@smogon/calc').is_dir():pytest.skip('optional pinned oracle absent')
    cases=tmp_path/'cases.json';cases.write_text(json.dumps(dict(cases=[dict(id='scoped',input=request)])))
    oracle=json.loads(subprocess.check_output(['node','scripts/damage_oracle.cjs',str(cases)]))
    assert calculate(request)['distribution']['rolls']==oracle['cases'][0]['rolls']
