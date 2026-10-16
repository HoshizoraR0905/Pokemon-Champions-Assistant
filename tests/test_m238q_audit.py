"""Diagnostics must preserve uncertainty, chronology and reference gaps."""
from copy import deepcopy

from scripts.audit_m238q import (move_failure, observation_gaps, reference_coverage,
                                render, slot_timeline)
from battle_events.parser import EventParser


def row(t, text):
    return dict(timestamp=t, source_id=f'test.mp4#{t}', sha256=f'frame-{t}', image=f'frame-{t}.png',
                message=dict(selected=True, raw_text=text))


def occurrence(rows, emitted):
    return dict(id='occurrence', emitted=emitted, observations=[dict(r, confidence=.99) for r in rows])


def parsed(t, text, kind=None):
    e = EventParser().parse(dict(entry_id=str(t), source_id=f'test.mp4#{t}', raw_text=text,
                                ocr_confidence=.99), battle_id='test').to_dict()
    if kind:
        e['event_type'] = kind
    e['attributes'].update(observation_time=t, occurrence_id='occurrence')
    return e


def test_supported_semantic_change_is_missing_even_when_group_emitted():
    rows = [row(1, '对对手的轰擂金刚猩效果绝佳！'), row(2, '对手的轰擂金刚猩倒下了！'),
            row(2.5, '对手的轰擂金刚猩倒下了!')]
    original = dict(battle_id='test', events=[parsed(1, rows[0]['message']['raw_text'])])
    observations = dict(observations=rows, occurrences=[occurrence(rows, True)])
    # Convert row-shaped fixture to the actual saved occurrence record shape.
    for observation, r in zip(observations['occurrences'][0]['observations'], rows):
        observation['raw_text'] = r['message']['raw_text']
    before = deepcopy(original)
    gaps = observation_gaps(observations, original)
    assert len(gaps) == 1
    assert gaps[0]['kind'] == 'faint'
    assert gaps[0]['timestamp'] == 2
    assert gaps[0]['grouping']['readings'] == 2
    assert gaps[0]['admission']['code'] == 'occurrence_already_emitted_different_semantics'
    assert original == before


def test_battle_outcome_observation_is_not_promoted_to_state_event():
    rows = [row(5, '战胜了 REIKOU!')]
    group = occurrence(rows, False)
    group['observations'][0]['raw_text'] = rows[0]['message']['raw_text']
    result = observation_gaps(dict(observations=rows, occurrences=[group]), dict(battle_id='test', events=[]))
    assert result[0]['kind'] == 'battle_outcome_observation'
    assert result[0]['parser']['kind'] == 'unknown'
    assert result[0]['admission']['status'] == 'not_emitted'
    assert result[0]['binding']['actor'] is None


def test_repeated_semantic_reading_does_not_create_an_extra_event():
    rows = [row(1, '大嘴鸥使出了顺风！'), row(1.5, '大嘴鸥使出了顺风!')]
    group = occurrence(rows, True)
    for observation, r in zip(group['observations'], rows):
        observation['raw_text'] = r['message']['raw_text']
    p = dict(battle_id='test', events=[parsed(1, rows[0]['message']['raw_text'])])
    assert not observation_gaps(dict(observations=rows, occurrences=[group]), p)


def hud(t, pid, accepted=True):
    e = dict(event_id=f'hud-{t}', event_type='hud_observation', side='self', actor=None,
             attributes=dict(observation_time=t, slot='left', species={}))
    bindings = dict(hud=dict(status='accepted' if accepted else 'deferred', reason='test'))
    if accepted:
        bindings.update(actor=dict(pokemon_instance_id=pid), identity=dict(species_id=279, name='大嘴鸥'))
    return e, dict(event=e, bindings=bindings, application_status='applied_candidate' if accepted else 'recorded_observation', reason=None)


def test_slot_intervals_do_not_backfill_announcements_or_vacate_on_bad_hud():
    announcement = parsed(10, '上吧！大嘴鸥！')
    a = dict(event=announcement, bindings=dict(actor=dict(pokemon_instance_id='pelipper')),
             application_status='recorded_observation', reason=None)
    e, h = hud(20, 'pelipper')
    bad, hb = hud(25, None, False)
    timeline = slot_timeline(dict(events=[announcement, e, bad]), dict(history=[a, h, hb]), [], 40)
    items = timeline['intervals']['self:left']
    assert items[0]['instance_id'] is None and items[0]['end'] == 10
    assert not any(x['instance_id'] for x in items if x['start'] < 20)
    assert items[-2]['start'] == 20
    assert items[-1]['start'] == 25 and items[-1]['status'] == 'unknown_current_binding'
    assert items[-1]['instance_id'] == 'pelipper'
    assert timeline['intervals']['opponent:left'][0]['end'] == 40


def saved_view(t, top, texts):
    r = row(t, '')
    observations = [dict(observation_id=f'row-{t}-{i}', source_id=r['source_id'], timestamp=t,
                         raw_text=text, partial=False, ocr_confidence=.99, color='purple') for i, text in enumerate(texts)]
    return r, dict(source_id=r['source_id'], timestamp=t, turn=4, detected=True,
                   header_ocr=dict(raw_text='回合4', confidence=.99),
                   geometry=dict(scroll_top=top, scroll_height=220), observations=observations)


def test_disconnected_reference_is_retained_without_fabricating_an_overlap_or_times():
    r1, v1 = saved_view(100, 60, ['对手的烈咬陆鲨使出了守住！', '对手的烈咬陆鲨摆出了防守的架势！'])
    r2, v2 = saved_view(101, 301, ['烈咬陆鲨使出了守住！', '烈咬陆鲨摆出了防守的架势！'])
    reference = dict(views=[v1, v2], entries=[{}, {}], assembly_issues=[dict(reason='no_reliable_scroll_overlap')])
    before = deepcopy(reference)
    result = reference_coverage(reference, {r['source_id']: r for r in [r1, r2]})
    assert len(result['components']) == 2
    assert result['retained_component_entries'] == 4
    assert result['observed_turns'] == [4]
    assert result['full_turn_coverage'] is False
    assert not any(c['contiguous_with_other_components'] for c in result['components'])
    assert all('original_event_time' not in e for c in result['components'] for e in c['entries'])
    assert reference == before


def test_move_failure_follows_stale_alias_even_after_retained_hud_read():
    first, h1 = hud(20, 'new-pelipper')
    latest, h2 = hud(25, 'new-pelipper')
    h2['bindings'].pop('identity')
    event = parsed(30, '大嘴鸥使出了暴风！')
    event['side'] = 'self'
    event['uncertainty'] = [u for u in event['uncertainty'] if u != 'side_unknown']
    event['attributes']['source_region_type'] = 'battle_message'
    event['attributes']['display_alias_evidence'] = [dict(instance_id='old-pelipper')]
    history = dict(bindings=dict(resolved_event=event), application_status='deferred',
                   reason='move_actor_not_bound_to_observed_prefix')
    result = move_failure(event, history, {'self:left': h2}, [h1, h2])
    assert result['category'] == 'side_or_active_instance_binding_failure'
    assert result['first_failure_time'] == 20
    assert result['causal_chain'][-1]['instance_id'] == 'new-pelipper'


def test_partial_admission_is_not_reported_as_supported_targets_or_effects():
    event = parsed(1, '大嘴鸥使出了顺风！')
    result = move_failure(event, dict(bindings={}, application_status='applied_partial'), {}, [])
    assert result['category'] == 'no_failure_partial_supported_admission'
    assert 'withheld' in result['reason']


def test_html_payload_cannot_close_script_and_contains_offline_filters():
    text = render(dict(payload='</script><img src=x onerror=alert(1)>'))
    assert '\\u003c/script>' in text
    assert '</script><img src=x' not in text
    for status in ['missing', 'deferred', 'ambiguous', 'duplicate', 'partially_applied']:
        assert f'<option>{status}</option>' in text
    assert 'https://' not in text
