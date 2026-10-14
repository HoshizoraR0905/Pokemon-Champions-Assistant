"""M2.2 offline state oracle and transition/replay regressions (no OCR/video)."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from tracking.battle_state import Fact, fact, from_dict
from tracking.state_engine import ApplicationPolicy, StateEngine, hash_state
from scripts.replay_m22 import run

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / 'tests/fixtures/battles/sample_battle_2/reviewed_events.json'
INITIAL = ROOT / 'tests/fixtures/m22_initial_context.json'


@pytest.fixture
def initial():
    return from_dict(json.loads(INITIAL.read_text())['state'])


@pytest.fixture
def events():
    return json.loads(EVENTS.read_text())['event_candidates']


def pokemon(state, species, side='self'):
    return next(p for p in state.pokemon.values()
                if p.side_id == side and p.species.value['species_id'] == species)


def synthetic(events, kind, attrs, *, side='self', species=1018, number=1):
    e = deepcopy(events[12])
    e.update(event_id=f'test:{number}', event_type=kind, side=side,
             target=None, uncertainty=[], status='confirmed', attributes=attrs,
             canonical_references={}, log_order=None)
    e['actor'] = next(deepcopy(x['actor']) for x in events
                      if x['side'] == side and x['actor'] and x['actor']['species_id'] == species)
    for evidence in e['evidence']:
        evidence['details'].pop('turn', None)
    return e


def test_cached_context_checksums_and_unknown_baselines(initial):
    assert all(stage.value.knowledge == 'unknown' for p in initial.pokemon.values()
               for stage in p.stages.values())
    assert initial.weather.kind.value == 'snow'
    assert initial.weather.duration.remaining.knowledge == 'unknown'


def test_twenty_events_independent_turn_two_oracle(initial, events):
    engine, snapshots = run(EVENTS, INITIAL)
    s = engine.state
    assert len(events) == len(engine.history) == len(snapshots) == 20
    assert [r.application_status for r in engine.history].count('applied_candidate') == 18
    assert [r.application_status for r in engine.history].count('recorded_observation') == 2
    assert not s.conflicts
    assert s.turn.value == 2 and s.phase.knowledge == 'unknown'
    expected = {'self': {'left': 186, 'right': 1018},
                'opponent': {'left': 876, 'right': 903}}
    for side, slots in expected.items():
        assert {slot: s.pokemon[pid].species.value['species_id']
                for slot, pid in s.sides[side].active_slots.items()} == slots
        assert not s.sides[side].vacant_slots
    for species, hp, maximum, fainted, location in [
        (812, 207, 207, False, 'bench'), (1018, 197, 197, False, 'active'),
        (478, 0, 177, True, 'fainted'), (186, 173, 197, False, 'active')]:
        p = pokemon(s, species)
        assert (p.hp.current.value, p.hp.maximum.value, p.fainted.value,
                p.location.value['kind']) == (hp, maximum, fainted, location)
        assert p.pokemon_instance_id == pokemon(initial, species).pokemon_instance_id
    armarouge = pokemon(s, 936, 'opponent')
    assert armarouge.hp.displayed_percent.value == 0 and armarouge.fainted.value
    assert armarouge.hp.current.knowledge == armarouge.hp.maximum.knowledge == 'unknown'
    assert pokemon(s, 26, 'opponent').location.value['kind'] == 'bench'
    for species in (876, 903):
        p = pokemon(s, species, 'opponent')
        assert p.hp.unit.knowledge == 'unknown' and p.fainted.value is False
    assert s.weather.kind.value == 'rain' and s.terrain.kind.value == 'psychic'
    for effect in (s.weather, s.terrain):
        assert effect.active.value is True
        assert effect.duration.remaining.knowledge == effect.duration.expires_at_turn.knowledge == 'unknown'
    sneasler = pokemon(s, 903, 'opponent')
    assert len(sneasler.item.activations) == len(sneasler.stages['special_defense'].changes) == 1
    assert sneasler.item.identity.value['name'] == '精神种子'
    assert sneasler.item.status.knowledge == 'unknown'
    assert snapshots[18]['state']['pokemon'][sneasler.pokemon_instance_id]['stages']['special_defense']['changes'] == []
    for p, stat, bounds in [(sneasler, 'special_defense', [-5, 6]),
                            (pokemon(s, 1018), 'special_attack', [-5, 6]),
                            (armarouge, 'defense', [-6, 5]),
                            (armarouge, 'special_defense', [-6, 5])]:
        assert p.stages[stat].value.knowledge == 'unknown'
        assert p.stages[stat].interval.value == bounds
        assert p.stages[stat].changes[0]['amount'] is None
    assert s.sides['self'].remaining_available.value == 3
    assert s.sides['opponent'].remaining_available.knowledge == 'unknown'
    assert all(p.major_status.knowledge == 'unknown' for p in s.pokemon.values())
    assert len(pokemon(s, 1018).moves.executed) == 1
    assert len(armarouge.moves.executed) == 1


def test_reverse_delivery_duplicate_and_serialization(initial, events):
    normal, _ = run(EVENTS, INITIAL)
    engine = StateEngine(initial)
    for e in reversed(events):
        engine.apply(e)
    assert hash_state(engine.state) == hash_state(normal.state)
    assert {r.event['event_id']: r.bindings for r in engine.history} == {
        r.event['event_id']: r.bindings for r in normal.history}
    saved = engine.to_dict()
    for e in events:
        engine.apply(e)
    assert engine.to_dict() == saved
    assert StateEngine.from_dict(json.loads(json.dumps(saved))).to_dict() == saved
    engine.replay()
    assert engine.to_dict() == saved


def test_correction_retraction_and_payload_collision(events):
    engine, _ = run(EVENTS, INITIAL)
    replacement = deepcopy(events[9])
    replacement['attributes']['after'] = 170
    with pytest.raises(ValueError, match='use correct'):
        engine.apply(replacement)
    engine.correct(replacement['event_id'], replacement, reason='corrected HP endpoint')
    assert pokemon(engine.state, 186).hp.current.value == 170
    assert len(engine.history[9].revisions) == 1
    assert StateEngine.from_dict(engine.to_dict()).to_dict() == engine.to_dict()
    engine.retract(replacement['event_id'], reason='unsupported observation')
    assert pokemon(engine.state, 186).hp.current.value == 197
    assert engine.apply(replacement).application_status == 'retracted'
    engine.correct(replacement['event_id'], events[9], reason='restore original')
    assert pokemon(engine.state, 186).hp.current.value == 173


def test_identity_return_switch_and_partial_party(initial, events):
    engine = StateEngine(initial)
    for e in events[:6]:
        engine.apply(e)
    for n, species, kind in [(1, 186, 'switch_out'), (2, 812, 'send_out')]:
        e = synthetic(events, kind, {}, species=species, number=n)
        # Continue in the existing turn/log ordering domain.
        e['log_order'] = 20 + n
        e['evidence'][0]['details']['turn'] = 2
        assert engine.apply(e).application_status == 'applied_confirmed'
    assert engine.state.sides['self'].active_slots['left'] == pokemon(initial, 812).pokemon_instance_id
    assert len(engine.state.pokemon) == 7
    engine = StateEngine(initial)
    engine.apply(events[0])
    e = deepcopy(events[0]); e.update(event_id='return-raichu', event_type='send_out', log_order=2)
    assert engine.apply(e).reason == 'ambiguous_existing_instance_in_partial_or_duplicate_party'
    e['attributes']['actor_instance_id'] = pokemon(initial, 26, 'opponent').pokemon_instance_id
    engine.correct(e['event_id'], e, reason='instance explicitly established')
    assert engine.state.sides['opponent'].active_slots['left'] == pokemon(initial, 26, 'opponent').pokemon_instance_id


@pytest.mark.parametrize('mode,reason', [
    ('no_order', 'missing_or_ambiguous_event_order'),
    ('low_confidence', 'low_ocr_confidence'),
    ('uncertainty', 'unresolved_candidate_fields'),
    ('no_evidence', 'missing_provenance')])
def test_conservative_policy(initial, events, mode, reason):
    e = deepcopy(events[0])
    if mode == 'no_order': e['log_order'] = None
    if mode == 'low_confidence': e['ocr_confidence'] = .1
    if mode == 'uncertainty': e['uncertainty'] = ['actor_unresolved']
    if mode == 'no_evidence': e['evidence'] = []
    engine = StateEngine(initial)
    assert engine.apply(e, sequence=1 if mode == 'no_evidence' else None).reason == reason
    assert engine.state.to_dict() == engine.initial.to_dict()


def test_ties_and_mixed_order_domains(initial, events):
    engine = StateEngine(initial)
    engine.apply(events[0])
    e = deepcopy(events[1]); e['log_order'] = 1
    engine.apply(e)
    assert all(r.reason == 'ambiguous_order_tie' for r in engine.history)
    assert engine.apply(events[2]).reason == 'earlier_order_tie'
    engine = StateEngine(initial)
    engine.apply(events[0]); engine.apply(events[1], sequence=2)
    assert all(r.reason == 'incomparable_order_domains' for r in engine.history)
    assert engine.state.to_dict() == engine.initial.to_dict()


def test_hp_rejection_is_atomic_and_animation_not_endpoint(initial, events):
    engine = StateEngine(initial)
    e = synthetic(events, 'hp_change', {'unit': 'absolute', 'before': 1, 'after': 100})
    assert engine.apply(e, sequence=1).reason == 'hp_before_mismatch'
    assert pokemon(engine.state, 1018).hp.current.value == 197
    assert engine.state.turn.knowledge == 'unknown'
    assert len(engine.state.conflicts) == 1
    e = synthetic(events, 'hp_change', {'intermediate': True, 'after': 120}, number=2)
    assert engine.apply(e, sequence=2).application_status == 'recorded_observation'
    assert pokemon(engine.state, 1018).hp.current.value == 197


def test_unknown_and_known_stat_baselines(initial, events):
    engine = StateEngine(initial)
    for n, attrs, value, bounds in [
        (1, {'stats': ['attack'], 'direction': 'up', 'stages': 2}, None, [-4, 6]),
        (2, {'stats': ['attack'], 'change': 'reset'}, 0, [0, 0]),
        (3, {'stats': ['attack'], 'direction': 'down', 'stages': 2}, -2, [-2, -2]),
        (4, {'stats': ['attack'], 'change': 'replace', 'value': 6}, 6, [6, 6]),
        (5, {'stats': ['attack'], 'direction': 'up', 'stages': 2}, 6, [6, 6])]:
        engine.apply(synthetic(events, 'stat_change', attrs, number=n), sequence=n)
        stage = pokemon(engine.state, 1018).stages['attack']
        assert stage.value.value == value and stage.interval.value == bounds


def test_status_item_ability_and_volatile_handlers(initial, events):
    engine = StateEngine(initial)
    for n, kind, attrs in [(1, 'status_change', {'change': 'apply', 'status': 'poison'}),
                           (2, 'status_change', {'change': 'remove', 'status': 'poison'}),
                           (3, 'ability_change', {'suppressed': True}),
                           (4, 'volatile_change', {'condition': 'confusion', 'change': 'start'}),
                           (5, 'volatile_change', {'condition': 'confusion', 'change': 'end'})]:
        assert engine.apply(synthetic(events, kind, attrs, number=n), sequence=n).application_status == 'applied_confirmed'
    p = pokemon(engine.state, 1018)
    assert p.major_status.value == 'none' and p.ability.suppressed.value is True
    assert p.volatile['confusion'].active.value is False
    ref = deepcopy(events[18]['canonical_references'])
    e = synthetic(events, 'item_change', {'change': 'reveal'}, number=6)
    e['canonical_references'] = ref
    engine.apply(e, sequence=6)
    e = synthetic(events, 'item_change', {'change': 'consume'}, number=7)
    engine.apply(e, sequence=7)
    assert pokemon(engine.state, 1018).item.status.value == 'consumed'
    e = synthetic(events, 'item_activation', {}, number=8); e['canonical_references'] = ref
    assert engine.apply(e, sequence=8).application_status == 'rejected'


def test_effect_duration_only_ticks_explicit_boundaries(initial, events):
    initial.turn = fact(2, {'source': 'test'})
    engine = StateEngine(initial)
    cases = [(1, 'side_condition_change', {'condition': 'tailwind', 'change': 'start',
              'duration': {'remaining': 2, 'timing': 'turn_end'}}),
             (2, 'turn_boundary', {'turn': 2, 'boundary': 'end'}),
             (3, 'turn_boundary', {'turn': 2, 'boundary': 'end'}),
             (4, 'turn_boundary', {'turn': 3, 'boundary': 'start'}),
             (5, 'turn_boundary', {'turn': 3, 'boundary': 'end'})]
    for n, kind, attrs in cases:
        engine.apply(synthetic(events, kind, attrs, number=n), sequence=n)
        effect = engine.state.sides['self'].conditions['tailwind']
        assert effect.duration.remaining.value == (2 if n == 1 else 0 if n == 5 else 1)
    assert effect.active.value is False
    assert engine.state.weather.duration.remaining.knowledge == 'unknown'


def test_transformation_keeps_instance_and_resources(initial, events):
    engine = StateEngine(initial)
    p = pokemon(initial, 1018)
    identity = deepcopy(p.species.value); identity['canonical_identity'] = 'test:observed-form'
    e = synthetic(events, 'transformation', {'identity': identity, 'mechanic': 'mega_evolution',
                  'actor_instance_id': p.pokemon_instance_id})
    assert engine.apply(e, sequence=1).application_status == 'applied_confirmed'
    transformed = pokemon(engine.state, 1018)
    assert transformed.pokemon_instance_id == p.pokemon_instance_id
    assert transformed.original_identity == p.original_identity
    assert transformed.hp == p.hp and transformed.location == p.location
    assert transformed.current_variant.value == 'test:observed-form'
    assert engine.state.sides['self'].resources['mega_evolution'].value is True
    assert all(v.knowledge == 'unknown' for v in transformed.hidden_configuration.values())


def test_duplicate_species_requires_explicit_instance(initial, events):
    original = pokemon(initial, 1018)
    duplicate = deepcopy(original)
    duplicate.pokemon_instance_id = 'duplicate-archaludon'
    duplicate.location = fact({'kind': 'active', 'slot': 'left'}, {'source': 'test'})
    former = pokemon(initial, 812)
    former.location = fact({'kind': 'bench', 'slot': None}, {'source': 'test'})
    initial.pokemon[duplicate.pokemon_instance_id] = duplicate
    initial.sides['self'].party_instance_ids.append(duplicate.pokemon_instance_id)
    initial.sides['self'].active_slots['left'] = duplicate.pokemon_instance_id
    engine = StateEngine(initial)
    e = synthetic(events, 'stat_change', {'stats': ['speed'], 'change': 'reset'})
    assert engine.apply(e, sequence=1).reason == 'ambiguous_or_missing_active_instance'
    e['attributes']['actor_instance_id'] = original.pokemon_instance_id
    engine.correct(e['event_id'], e, sequence=1, reason='explicit instance binding')
    assert engine.state.pokemon[original.pokemon_instance_id].stages['speed'].value.value == 0
    assert engine.state.pokemon[duplicate.pokemon_instance_id].stages['speed'].value.knowledge == 'unknown'


def test_item_transfer_preserves_revelation_history(initial, events):
    engine = StateEngine(initial)
    e = synthetic(events, 'item_change', {'change': 'reveal'})
    e['canonical_references'] = deepcopy(events[18]['canonical_references'])
    engine.apply(e, sequence=1)
    e = synthetic(events, 'item_change', {'change': 'transfer', 'target_side': 'self',
                  'target_instance_id': pokemon(initial, 812).pokemon_instance_id}, number=2)
    assert engine.apply(e, sequence=2).application_status == 'applied_confirmed'
    source, target = pokemon(engine.state, 1018), pokemon(engine.state, 812)
    assert source.item.identity.value is None and source.item.status.value == 'transferred'
    assert len(source.item.revealed) == 1
    assert target.item.identity.value['name'] == '精神种子' and target.item.status.value == 'known'
    assert target.stages['special_defense'].changes == []


def test_hazards_trick_room_and_effect_removal(initial, events):
    engine = StateEngine(initial)
    for n, kind, attrs in [
        (1, 'side_condition_change', {'condition': 'spikes', 'category': 'hazard', 'layers': 2, 'change': 'start'}),
        (2, 'trick_room_change', {'change': 'start'}),
        (3, 'side_condition_change', {'condition': 'spikes', 'category': 'hazard', 'change': 'remove'}),
        (4, 'trick_room_change', {'change': 'end'})]:
        assert engine.apply(synthetic(events, kind, attrs, number=n), sequence=n).application_status == 'applied_confirmed'
    assert engine.state.sides['self'].hazards['spikes'].value == 0
    assert engine.state.trick_room.active.value is False


def test_rejected_event_correction_rebuilds_conflicts(initial, events):
    engine = StateEngine(initial)
    e = synthetic(events, 'hp_change', {'unit': 'absolute', 'before': 1, 'after': 100})
    assert engine.apply(e, sequence=1).application_status == 'rejected'
    e['attributes']['before'] = 197
    engine.correct(e['event_id'], e, sequence=1, reason='fix stale baseline')
    assert not engine.state.conflicts
    assert pokemon(engine.state, 1018).hp.current.value == 100
    assert engine.history[0].revisions[0]['event']['attributes']['before'] == 1


def test_explicit_faint_and_zero_hp_are_separate_observations(initial, events):
    engine = StateEngine(initial)
    e = synthetic(events, 'hp_change', {'unit': 'absolute', 'before': 197, 'after': 0})
    engine.apply(e, sequence=1)
    assert pokemon(engine.state, 1018).fainted.value is False
    engine.apply(synthetic(events, 'faint', {}, number=2), sequence=2)
    p = pokemon(engine.state, 1018)
    assert p.fainted.value is True and p.location.value['kind'] == 'fainted'
    assert engine.state.sides['self'].vacant_slots == ['right']
    assert engine.state.sides['self'].remaining_available.value == 2


def test_candidate_disabled_and_fact_validation(initial, events):
    engine = StateEngine(initial, ApplicationPolicy(allow_candidates=False))
    assert engine.apply(events[0]).reason == 'candidate_policy_disabled'
    with pytest.raises(ValueError):
        Fact(0)
    with pytest.raises(ValueError):
        Fact(None, 'invented')
    assert Fact(0, 'observed').known and Fact(False, 'derived').known
    assert not Fact(1, 'conflicting', alternatives=[{'value': 2}]).known


@pytest.mark.local_artifacts('reports/M2.2-context-evidence/party-266.png','reports/M2.2-context-evidence/active-267.5.png')
def test_local_source_frame_checksums():
    fixture = json.loads(INITIAL.read_text())
    for source in fixture['annotations']['source_frames'].values():
        assert hashlib.sha256((ROOT / source['image']).read_bytes()).hexdigest() == source['sha256']
