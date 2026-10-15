"""Identity contracts: independent observations, aliases, gaps and retractions."""
from copy import deepcopy
from dataclasses import asdict
import numpy as np
import cv2
from models import Observation,IconEvidence,IconCandidate
from recognition.entities import EntityResolver
from recognition.identity import combine_identity
from recognition.sprite_shape import silhouette,shape_score,roster_ranking
from recognition.identity_flow import EntryWindows,hud_cards,preview_rows
from battle_events.aliases import alias_key
from battle_events.parser import EventParser,BattleContext
from battle_events.schema import BattleEvent,Evidence
from tracking.battle_state import BattleState
from tracking.state_engine import StateEngine
from tracking.identity_ledger import remember_alias
from tests.test_evidence_fusion import hud,message,active


def engine():
    return StateEngine(BattleState('test',knowledge=dict(reliability_v1=True,reliability_v2=True,identity_v1=True)))


def test_ambiguous_icon_does_not_erase_independent_exact_name_or_assert_form():
    resolver=EntityResolver();text=resolver.resolve(Observation('龙头地鼠',.99,raw_text='龙头地鼠'),'species',region_kind='species')
    original=asdict(text.resolution)
    icon=IconEvidence(status='ambiguous',candidates=[IconCandidate('pokeapi:species:530',530,None,'a',.897,1.,(0,0),530,'pokeapi:pokemon:530')])
    result=combine_identity(text,icon,resolver.knowledge)
    assert result.resolution.method=='exact' and result.resolution.independent_text==original
    assert result.resolution.conditional_evidence[0]['depends_on']=='independent_text'
    assert icon.status=='ambiguous' and text.resolution.conditional_evidence==[]
    e=engine();r=e.apply(hud(1,1,530,mon=asdict(result),icon=asdict(icon)),sequence=1)
    assert r.bindings['hud']['status']=='accepted'


def test_unicode_spaces_case_and_punctuation_have_one_lookup_contract():
    assert alias_key('Ｂｉｇ\u3000Mom')==alias_key('big MOM')=='bigmom'
    assert alias_key("Mr. Mime")!=alias_key('Mr Mime')
    kb=EventParser();identity=kb.identity('钢铠鸦','species');c=BattleContext()
    c.display_aliases['Big Nugget']=dict(identity=identity,evidence=[{'source':'same HUD'}],side='opponent',instance_id='a')
    event=kb.parse(dict(entry_id='1',source_id='frame',raw_text='对手的ＢＩＧ NUGGET使出了守住！',ocr_confidence=.99),c)
    assert event.actor['species_id']==823 and event.canonical_references['move']['canonical_id']=='pokeapi:move:182'


def test_normalization_collision_is_not_an_identity_merge():
    kb=EventParser();c=BattleContext()
    for raw,name,pid in [('A B','钢铠鸦','one'),('AB','龙头地鼠','two')]:
        c.display_aliases[raw]=dict(identity=kb.identity(name,'species'),evidence=[{}],instance_id=pid)
    event=kb.parse(dict(entry_id='x',raw_text='对手的AB使出了守住！'),c)
    assert event.actor is None and 'ambiguous_display_alias' in event.uncertainty


def test_identical_nicknames_on_opposite_sides_keep_separate_claims():
    from tracking.evidence_fusion import prepare_message
    e=engine();parser=EventParser()
    remember_alias(e.state,'Shared',parser.identity('龙头地鼠','species'),[{'source':'opponent HUD'}],side='opponent')
    remember_alias(e.state,'Shared',parser.identity('钢铠鸦','species'),[{'source':'own HUD'}],side='self')
    parsed=prepare_message(e.state,message(1,1,'对手的Shared使出了守住！'))
    assert parsed.actor['species_id']==530
    assert len(e.state.knowledge['identity_ledger']['aliases'])==2


def alias_event(number,text='对手的Example Name超级进化成了超级袋兽！'):
    return BattleEvent(f'alias:{number}','alias_observation','opponent',None,None,text,{},None,
        [Evidence('message',f'test#{number}',[str(number)],dict(timestamp=number))],.99,'supported',[],
        dict(battle_id='test',observation_time=number))


def test_explicit_revelation_is_prospective_unplaced_and_retractable():
    e=engine();before=e.apply(message(1,1,'对手的Example Name使出了守住！'),sequence=1)
    assert before.application_status=='deferred'
    e.apply(alias_event(2),sequence=2)
    assert not e.state.sides['opponent'].active_slots
    r=e.apply(message(3,3,'对手的example name使出了守住！'),sequence=3)
    assert r.application_status=='applied_partial'
    p=e.state.pokemon[r.bindings['actor']['pokemon_instance_id']]
    assert p.species.value['species_id']==115 and len(p.moves.executed)==1 and not p.hp.current.known
    assert e.history[0].application_status=='deferred'
    e.retract('alias:2',reason='wrong revelation')
    assert not e.state.pokemon and not e.state.knowledge.get('identity_ledger',{}).get('aliases')
    assert e.history[-1].application_status=='deferred'


def test_alias_species_does_not_bridge_coverage_gap_or_choose_duplicate_individual():
    e=engine();e.apply(alias_event(1),sequence=1)
    gap=BattleEvent('gap','coverage_observation','opponent',None,None,'gap',{},None,
        [Evidence('coverage','test',['g'],dict(timestamp=3))],None,'supported',[],
        dict(battle_id='test',observation_time=3,start=2,status='gap',fields=['occupancy']))
    e.apply(gap,sequence=2);r=e.apply(message(3,4,'对手的Example Name使出了守住！'),sequence=3)
    assert r.application_status=='deferred'
    assert not next(iter(e.state.pokemon.values())).moves.executed


def test_evidenced_reentry_restores_revelations_but_not_old_hp():
    e=engine();e.apply(hud(1,1,530,hp=dict(current=50,maximum=185)),sequence=1);pid=active(e).pokemon_instance_id
    e.apply(message(2,2,'龙头地鼠使出了守住！'),sequence=2)
    e.apply(hud(3,3,823),sequence=3)
    r=e.apply(hud(4,4,530,continuity=dict(instance_id=pid,evidence=[{'explicit':'individual ID'}])),sequence=4)
    assert active(e).pokemon_instance_id==pid and len(active(e).moves.executed)==1
    assert not active(e).hp.current.known
    e.retract(r.event['event_id'],reason='unsupported reidentification')
    assert active(e).species.value['species_id']==823


def test_preview_rows_keep_duplicates_without_active_slots():
    from models import Recognition,Pokemon
    icon=IconEvidence(status='resolved',species_id=25,canonical_id='pokeapi:species:25')
    snap=Recognition('f',0,1,pokemon=[Pokemon('opponent_team_1',icon=icon),Pokemon('opponent_team_2',icon=icon)],capture_metadata={'sha256':'hash','timestamp':1})
    rows=preview_rows(snap,'test')
    assert len({r['member_occurrence'] for r in rows})==2
    assert all(r['active_slot'] is None and r['nickname'] is None for r in rows)


def test_partial_hud_and_entry_windows_ignore_scene_positions():
    image=np.zeros((200,440,3),np.uint8);image[169:178,61:100]=(200,0,100)
    # HSV panel hue, not any model region, controls scheduling.
    image[169:178,61:100]=cv2.cvtColor(np.full((9,39,3),(128,220,200),np.uint8),cv2.COLOR_HSV2BGR)
    cards=hud_cards(image);assert any(c[0]=='own' and c[1]==0 for c in cards)
    altered=image.copy();altered[40:150]=255;assert hud_cards(altered)==cards
    windows=EntryWindows(3);assert windows.observe('上吧！某宝可梦！',1,'source')[0]['slot'] is None
    windows.seen_hud(5,[]);assert windows.windows[0]['status']=='expired_unresolved'


def test_shape_is_palette_invariant_and_negative_shapes_remain_different():
    a=np.full((80,70,3),(90,20,170),np.uint8)
    points=np.array([[23,10],[35,22],[48,8],[45,45],[55,65],[16,65],[22,40]])
    cv2.fillPoly(a,[points],(20,170,220));b=a.copy();b[(a[:,:,1]>100)]=(170,130,20)
    q=silhouette(a);r=silhouette(b);assert q is not None and shape_score(q,r)==1
    disk=np.zeros_like(q);cv2.circle(disk,(disk.shape[1]//2,disk.shape[0]//2),10,1,-1)
    assert shape_score(q,disk)<.8
    assert silhouette(np.zeros_like(a)) is None


def test_roster_conditioning_is_never_independent_or_forced():
    icon=IconEvidence(status='unresolved',candidates=[IconCandidate('pokeapi:species:25',25,None,'a',.6,1,(0,0))])
    ranking=roster_ranking(icon,[dict(species_id=25,status='resolved',evidence='preview')])
    assert len(ranking['candidates'])==1 and ranking['admission']=='ranking_only'
    assert not ranking['independent_observation'] and icon.status=='unresolved'


def test_evaluator_requires_current_projected_identity_and_hp():
    from scripts.evaluate_m236 import score_hud
    e=engine();event=hud(1,1,530,hp=dict(current=50,maximum=185));r=e.apply(event,sequence=1)
    label=dict(side='self',slot='right',species_id=530,display_name='龙头地鼠',hp=dict(current=50,maximum=185))
    mon=dict(species=event.attributes['species'],hp=event.attributes['hp'],icon={})
    receipt={**r.bindings['hud'], 'instance_id':r.bindings['actor']['pokemon_instance_id']}
    current=score_hud(label,mon,receipt,e.evidence_projection(as_of=1))
    assert current['bound_correct'] and current['current_correct'] and current['hp_current_correct']
    stale=score_hud(label,mon,receipt,e.evidence_projection(as_of=2))
    assert stale['species_correct'] and stale['bound_correct'] and not stale['current_correct'] and not stale['hp_current_correct']


def test_historical_unplaced_entry_does_not_veto_new_hud_across_gap():
    e=engine();e.apply(message(1,1,'上吧！龙头地鼠！'),sequence=1)
    old=e.history[0].bindings['actor']['pokemon_instance_id']
    gap=BattleEvent('gap','coverage_observation','field',None,None,'gap',{},None,
        [Evidence('coverage','test',['g'],dict(timestamp=3))],None,'supported',[],
        dict(battle_id='test',observation_time=3,start=2,status='gap',fields=['occupancy']))
    e.apply(gap,sequence=2);e.apply(hud(3,4,530,hp=dict(current=50,maximum=185)),sequence=3)
    current=e.evidence_projection(as_of=4)['occupancy']['self']['right']['current_instance_id']
    assert current is not None and current!=old
    assert e.state.pokemon[old].location.value==dict(kind='unplaced_entry',slot=None)
    assert e.state.pokemon[current].hp.current.value==50


def test_new_review_split_keeps_occurrences_and_hashes_separate():
    import json
    from pathlib import Path
    fixture=json.loads(Path('tests/fixtures/battles/m236_review.json').read_text())
    development={r['sha256'] for r in fixture['frames'] if r['split']=='development'}
    held_out={r['sha256'] for r in fixture['frames'] if r['split']=='held_out'}
    assert not development & held_out
    assert len(held_out)==56 and len(development)==64
    assert sum(o['kind']=='move_execution' for o in fixture['occurrences'] if o['split']=='held_out')==2
    assert max(o['end'] for o in fixture['occurrences'] if o['split']=='development') < min(
        o['start'] for o in fixture['occurrences'] if o['split']=='held_out')


def test_ocr_budget_reserves_failed_attempt_before_call(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import json
    from scripts import process_m236 as runner
    monkeypatch.setattr(runner,'P',tmp_path)
    calls=[]
    def failing(crops):calls.append(crops);raise ValueError('inference failed')
    backend=SimpleNamespace(predict=failing)
    cache=SimpleNamespace(load=lambda:backend,budget=1,identity={},paths=SimpleNamespace(cache=lambda key:tmp_path/key))
    runner.budget_ocr(cache)
    import pytest
    with pytest.raises(ValueError,match='inference failed'):backend.predict([np.zeros((4,4,3),dtype='uint8')])
    with pytest.raises(RuntimeError,match='budget exhausted'):backend.predict([np.zeros((4,4,3),dtype='uint8')])
    ledger=json.loads((tmp_path/'ocr-ledger.json').read_text())
    assert ledger['total']==1 and ledger['reservations'][0]['status']=='error' and len(calls)==1


def test_evaluator_retains_unrecognized_move_in_denominator():
    from scripts.evaluate_m236 import score_occurrence
    event=message(1,1,'对手的Example使出了无法识别的招式！').to_dict()
    event['canonical_references']['move']=None
    record=dict(event=event,bindings={},application_status='deferred',reason='unresolved_move')
    label=dict(start=1,end=2,kind='move_execution',move='pokeapi:move:182',text='对手的Example使出了无法识别的招式！')
    scored=score_occurrence(label,[dict(timestamp=1,message=dict(raw_text=event['original_text']))],[record],{})
    assert scored['transcribed'] and not scored['canonical_recognized'] and not scored['executed_move_revealed']
