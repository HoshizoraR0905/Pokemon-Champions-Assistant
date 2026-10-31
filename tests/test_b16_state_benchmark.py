"""Portable evaluation contracts; no recording/OCR or historical artifacts."""
from scripts.benchmark_b16_state import align_facts,signature


def h(eid,move='m',side='self',sid=6,kind='move_execution'):
    return dict(event=dict(event_id=eid,event_type=kind,side=side,actor=dict(species_id=sid),
        canonical_references=dict(move=dict(canonical_id=move)),attributes={}),bindings={})


def f(i,move='m',side='self',sid=6):
    return dict(fact_id=str(i),category='move_execution',canonical_id=move,side=side,species_id=sid)


def test_repeated_moves_match_distinct_ordered_occurrences_without_text_or_view_timestamps():
    refs=[f(1),f(2,move='n'),f(3)]
    live=[h('a'),h('extra',move='other'),h('b',move='n'),h('c')]
    assert align_facts(refs,live)=={'1':'a','2':'b','3':'c'}
    # Missing middle fact cannot reuse another move just because actor agrees.
    assert '2' not in align_facts(refs,[h('a'),h('c')])


def test_observed_hp_and_effect_do_not_establish_an_executed_move():
    ref=f(1)
    assert not signature(ref,h('hp',kind='hp_change')['event'])
    assert not signature(ref,h('effect',kind='move_effect')['event'])


def test_resolved_prefix_event_is_used_and_side_agreement_guides_alignment():
    refs=[f(1)]
    wrong=h('wrong',side='opponent')
    good=h('good');good['bindings']['resolved_event']=good['event'];good['event']=dict(good['event'],event_type='unknown')
    assert align_facts(refs,[wrong,good])=={'1':'good'}


def test_same_capture_time_does_not_invent_order_from_event_ids():
    refs=[dict(fact_id='ability',category='ability_activation',side='self',species_id=6,canonical_id='drought'),
          dict(fact_id='weather',category='weather',side='field',weather='sun',active=True)]
    weather=h('a',kind='weather_change');weather['event'].update(side='field',actor=None,attributes=dict(observation_time=10,weather='sun',change='start'))
    ability=h('z',kind='ability_activation');ability['event'].update(attributes=dict(observation_time=10),canonical_references=dict(ability=dict(canonical_id='drought')))
    assert align_facts(refs,[weather,ability])=={'ability':'z','weather':'a'}
    # Different observed times do establish order; don't reorder those events.
    ability['event']['attributes']['observation_time']=11
    assert len(align_facts(refs,[weather,ability]))==1


def test_later_repeated_weather_can_follow_same_frame_ability_without_reusing_event():
    refs=[dict(fact_id='rain1',category='weather',side='field',weather='rain',active=True),
          dict(fact_id='ability',category='ability_activation',side='self',species_id=6,canonical_id='drizzle'),
          dict(fact_id='rain2',category='weather',side='field',weather='rain',active=True)]
    def rain(eid,t):
        event=h(eid,kind='weather_change');event['event'].update(side='field',actor=None,attributes=dict(observation_time=t,weather='rain',change='start'));return event
    ability=h('ability',kind='ability_activation');ability['event'].update(attributes=dict(observation_time=10),canonical_references=dict(ability=dict(canonical_id='drizzle')))
    assert align_facts(refs,[rain('early',1),rain('later',10),ability])=={'rain1':'early','ability':'ability','rain2':'later'}
    assert len(align_facts(refs,[rain('early',1)]))==1
