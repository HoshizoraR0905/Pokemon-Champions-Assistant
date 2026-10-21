from copy import deepcopy
from battle_events.parser import EventParser
from scripts.evaluate_message_identity import literal_prediction, compare


def event(text='上吧！喷火龙！', **attrs):
    return dict(event_id='arrival', original_text=text, side='self', ocr_confidence=.99,
                evidence=[], attributes=dict(observation_time=1, slot='left', **attrs))


def hud(t=2, sid=6, slot='left', **attrs):
    from knowledge import KnowledgeBase
    kb=KnowledgeBase(); entity=kb.entities[f'pokeapi:species:{sid}']
    return dict(event_id=str(t), side='self', evidence=[], attributes=dict(
        observation_time=t, slot=slot,
        species=dict(raw_text=entity.names['zh-hans'], confidence=.99,
                     resolution=dict(status='resolved', method='exact', species_id=sid, confidence='strong')),
        icon={}, **attrs))


def test_complete_literal_only_and_no_title_or_nickname_guessing():
    parser=EventParser()
    assert literal_prediction(event(),parser)['identity']['species_id']==6
    for text in ['上吧！开始犯困的喷火龙！','上吧！Pebble！','上吧！喷火龙', '上吧！???！']:
        assert literal_prediction(event(text),parser)['identity'] is None
    p=event();p['ocr_confidence']=.8
    assert literal_prediction(p,parser)['identity'] is None


def test_first_independent_hud_is_frozen_even_if_later_hud_agrees():
    p=literal_prediction(event(),EventParser());original=deepcopy(p)
    rows=compare([p],[hud(sid=3),hud(3,sid=6)])
    assert rows[0]['comparison']=='mismatch' and rows[0]['hud']['timestamp']==2
    assert p==original


def test_unknown_not_repaired_reused_and_other_episode_excluded():
    p=literal_prediction(event('上吧！Pebble！'),EventParser())
    p['departure']=4
    assert compare([p],[hud()])[0]['comparison']=='inconclusive'
    p=literal_prediction(event(),EventParser());p['departure']=4
    for events in [[hud(1)], [hud(slot='right')], [hud(identity_reused_from='old')], [hud(4)], [hud(5)]]:
        assert compare([p],events)[0]['hud'] is None
    next_entry=deepcopy(p);next_entry['timestamp']=2
    assert compare([p,next_entry],[hud(3)])[0]['hud'] is None


def test_form_unknown_is_not_promoted_by_species_match():
    p=literal_prediction(event('上吧！喷火龙！'),EventParser())
    assert p['identity']['canonical_identity'] is None
    row=compare([p],[hud()])[0]
    assert row['comparison']=='match' and row['form_comparison']=='inconclusive'
