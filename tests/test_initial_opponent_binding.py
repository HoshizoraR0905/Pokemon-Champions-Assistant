"""Independent literal-label proof and prospective trainer-side calibration."""
from copy import deepcopy
from types import SimpleNamespace
import pytest

from battle_events.parser import EventParser
from recognition.event_report import video_events
from tests.test_event_driven import live_row
from tests.test_evidence_fusion import hud, species
from tracking.battle_state import BattleState
from tracking.evidence_fusion import identity_evidence, prepare_message
from tracking.identity_ledger import trainer_from_opening_hud
from tracking.state_engine import StateEngine, event_from_dict


def literal(sid=823):
    mon = species(sid)
    exact = deepcopy(mon['resolution'])
    mon['resolution'].update(method='icon_only', confidence='moderate', independent_text=dict(
        method='text_icon_agreement', status='resolved', species_id=sid, independent_text=exact))
    icon = dict(status='resolved', method='masked_multiscale_template', species_id=sid,
                canonical_identity=f'pokeapi:pokemon:{sid}', candidates=[dict(species_id=sid, similarity=.88)])
    return mon, icon


@pytest.mark.parametrize('sid', [823, 530])
def test_preserved_exact_text_and_independent_icon_support_literal_label(sid):
    mon, icon = literal(sid); before = deepcopy(mon)
    ref, status, reason = identity_evidence(mon, icon, reliability=True)
    assert status == 'accepted' and ref['species_id'] == sid
    assert reason == 'literal_label_independent_icon_agreement'
    assert mon == before and mon['resolution']['method'] == 'icon_only'
    assert identity_evidence(mon, icon, reliability=False)[1] == 'deferred'


@pytest.mark.parametrize('bad', ['no_text', 'fused_only', 'fuzzy', 'raw_other_species', 'low_confidence',
                                 'wrong_icon', 'conditioned_icon', 'wrong_top_candidate', 'conditional_text',
                                 'conflicting_text', 'variant_conflict'])
def test_visible_ocr_or_dependent_evidence_does_not_fabricate_agreement(bad):
    mon, icon = literal()
    leaf = mon['resolution']['independent_text']['independent_text']
    if bad == 'no_text': mon['resolution'].pop('independent_text')
    elif bad == 'fused_only': mon['resolution']['independent_text'].pop('independent_text')
    elif bad == 'fuzzy': leaf['method'] = 'fuzzy'
    elif bad == 'raw_other_species': mon['raw_text'] = '龙头地鼠'
    elif bad == 'low_confidence': mon['confidence'] = .8
    elif bad == 'wrong_icon': icon['species_id'] = 530
    elif bad == 'conditioned_icon': icon['method'] = 'text_species_filters_visual_candidates'
    elif bad == 'wrong_top_candidate': icon['candidates'][0]['species_id'] = 530
    elif bad == 'conditional_text': leaf['conditional_evidence'] = [dict(depends_on='icon')]
    elif bad == 'conflicting_text': mon['resolution']['independent_text']['status'] = 'conflict'
    elif bad == 'variant_conflict': leaf['canonical_identity'] = 'pokeapi:pokemon:other-form'
    assert identity_evidence(mon, icon, reliability=True)[1] != 'accepted'


def engine():
    return StateEngine(BattleState('test', knowledge=dict(identity_v1=True, reliability_v1=True, reliability_v2=True)))


def test_four_slots_then_trainer_binding_is_prospective_and_retractable():
    e = engine()
    events = video_events([live_row(1, 'Visitor派出了钢铠鸦和龙头地鼠！'),
                           live_row(2, '上吧！暴飞龙！大狃拉！')], [], 'test')
    for i, event in enumerate(events, 1): e.apply(event_from_dict(event), sequence=i)
    assert not e.state.sides['opponent'].trainer
    assert all(x['side'] == 'unknown' for x in events if x['event_type'] == 'send_out' and x['attributes']['observation_time'] == 1)
    for i, (side, slot, sid) in enumerate([('self', 'left', 373), ('self', 'right', 903),
                                          ('opponent', 'left', 530), ('opponent', 'right', 823)], 20):
        mon, icon = literal(sid)
        e.apply(hud(i, 5, sid, side=side, slot=slot, mon=mon, icon=icon), sequence=i)
    assert all(set(team.active_slots) == {'left', 'right'} for team in e.state.sides.values())
    claim = e.state.sides['opponent'].trainer
    assert claim['display_name'] == 'Visitor' and claim['observed_at'] == 5
    msg = event_from_dict(live_row(6, 'Visitor换下了钢铠鸦！')['occurrence_decision']['events'][0])
    assert prepare_message(e.state, msg).side == 'opponent'
    msg.attributes['observation_time'] = 4
    assert prepare_message(e.state, msg).side == 'unknown'
    e.retract('hud:23', reason='Bad source frame')
    assert not e.state.sides['opponent'].trainer


def trainer_fixture():
    state = BattleState('test')
    entry = video_events([live_row(1, 'Someone派出了钢铠鸦和龙头地鼠！')], [], 'test')[0]
    history = SimpleNamespace(event=entry, retracted=False, application_status='recorded_observation')
    current = hud(9, 5, 823)
    sources = dict(sources=[dict(source_id=current.evidence[0].source_id)])
    slots = {}
    for side, names in [('self', ['暴飞龙', '大狃拉']), ('opponent', ['龙头地鼠', '钢铠鸦'])]:
        for slot, name in zip(('left', 'right'), names):
            slots[side + ':' + slot] = dict(status='accepted', timestamp=5, raw=name, evidence=deepcopy(sources))
    state.knowledge['hud_fusion'] = dict(slots=slots)
    return state, SimpleNamespace(history=[history]), current, SimpleNamespace(bindings={})


@pytest.mark.parametrize('bad', ['missing_slot', 'same_pair_both_sides', 'stale_frame', 'partial_pair',
                                 'weak_entry', 'generic_trainer', 'intervening_move'])
def test_trainer_mapping_withholds_ambiguous_incomplete_or_post_action_evidence(bad):
    state, engine, current, record = trainer_fixture()
    slots = state.knowledge['hud_fusion']['slots']; entry = engine.history[0].event
    if bad == 'missing_slot': slots.pop('self:right')
    elif bad == 'same_pair_both_sides':
        slots['self:left']['raw'] = '钢铠鸦'; slots['self:right']['raw'] = '龙头地鼠'
    elif bad == 'stale_frame': slots['opponent:left']['timestamp'] = 4
    elif bad == 'partial_pair': entry['attributes']['ordered_display_references'] = ['钢铠鸦']
    elif bad == 'weak_entry': entry['ocr_confidence'] = .8
    elif bad == 'generic_trainer': entry['original_text'] = '训练家派出了钢铠鸦和龙头地鼠！'
    elif bad == 'intervening_move':
        engine.history.append(SimpleNamespace(retracted=False, application_status='deferred', event=dict(
            event_type='move_execution', attributes=dict(observation_time=3))))
    trainer_from_opening_hud(engine, state, current, record)
    assert all(not team.trainer for team in state.sides.values())


def test_trainer_name_is_not_shared_across_battles():
    state, e, current, record = trainer_fixture()
    trainer_from_opening_hud(e, state, current, record)
    assert state.sides['opponent'].trainer['display_name'] == 'Someone'
    assert not BattleState('other').sides['opponent'].trainer
