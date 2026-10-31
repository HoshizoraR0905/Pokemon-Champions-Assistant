"""Focused Transform/Unnerve software regressions; no video or OCR required."""
from copy import deepcopy
from dataclasses import asdict

import pytest

from battle_events.parser import EventParser
from recognition.message_occurrences import MessageOccurrences
from tracking.battle_state import BattleState, PokemonState, Fact, Stage, fact, from_dict
from tracking.mechanics import ensure
from tracking.state_engine import StateEngine
from tracking.transformation import KEY, current
from tracking.unnerve import KEY as BERRIES

PROOF = {'source': 'synthetic software fixture, not actual Champions data'}


@pytest.fixture(scope='module')
def parser():
    return EventParser()


def initial(parser):
    s = BattleState('synthetic', knowledge={'active_continuity_v1': True})
    for pid, name, side, slot in [('ditto', '百变怪', 'opponent', 'left'),
                                  ('ally', '化石翼龙', 'opponent', 'right'),
                                  ('garchomp', '烈咬陆鲨', 'self', 'left'),
                                  ('pelipper', '大嘴鸥', 'self', 'right')]:
        p = PokemonState(pid, side)
        p.species = fact(parser.identity(name, 'species'), PROOF)
        p.original_identity = deepcopy(p.species)
        p.current_variant = fact(p.species.value['canonical_identity'], PROOF) if p.species.value.get('canonical_identity') else Fact()
        p.location = fact(dict(kind='active', slot=slot), PROOF)
        s.pokemon[pid] = p
        s.sides[side].party_instance_ids.append(pid)
        s.sides[side].active_slots[slot] = pid
    d = s.pokemon['ditto']; g = s.pokemon['garchomp']
    d.hp.current = fact(33, PROOF); d.hp.maximum = fact(150, PROOF)
    d.hp.displayed_percent = fact(22, PROOF)
    d.item.identity = fact(parser.identity('文柚果', 'item'), PROOF)
    d.item.status = fact('known', PROOF)
    d.ability.current = fact(parser.identity('变身者', 'ability'), PROOF)
    d.current_types = fact(['normal'], PROOF)
    d.moves.known_slots['1'] = fact(parser.identity('变身', 'move'), PROOF)
    d.moves.pp['pokeapi:move:144'] = fact(dict(current=12, maximum=12), PROOF)
    g.current_types = fact(['dragon', 'ground'], PROOF)
    g.ability.current = fact(parser.identity('沙隐', 'ability'), PROOF)
    g.stages['attack'].value = fact(2, PROOF)
    g.moves.known_slots['1'] = fact(parser.identity('龙之波动', 'move'), PROOF)
    g.moves.known_slots['3'] = fact(parser.identity('守住', 'move'), PROOF)
    # Synthetic applicable maximum values exercise the cap, not real move data.
    g.moves.pp['pokeapi:move:406'] = fact(dict(current=1, maximum=3), PROOF)
    g.moves.pp['pokeapi:move:182'] = fact(dict(current=1, maximum=12), PROOF)
    ensure(g, 'battle_stats', 'per_entry').current['attack'] = fact(137, PROOF)
    s.knowledge['team'] = {'instances': {'ditto': {'fields': {'level': dict(value=50, status='manual_verified')}}}}
    s.sides['opponent'].trainer = dict(display_name='Trainer', status='accepted')
    s.knowledge['identity_ledger'] = dict(aliases=[], entries=[], roster=[
        dict(battle_id=s.battle_id, side='opponent', preview_row=i + 1, species_id=sid,
             status='resolved', evidence=PROOF) for i, sid in enumerate([132, 142, 376, 302, 952, 1018])])
    from tracking.active_continuity import enter
    from tracking.state_engine import EventRecord, event_from_dict
    entry = event(parser, 0, 'send_out')
    enter(s, d, event_from_dict(entry), EventRecord(entry, 0, None), slot='left')
    return s


def event(parser, n, kind, pid='ditto', attrs=None, refs=None):
    name = {'ditto': '百变怪', 'ally': '化石翼龙', 'garchomp': '烈咬陆鲨', 'pelipper': '大嘴鸥'}[pid]
    return dict(event_id=str(n), event_type=kind, side='opponent' if pid in {'ditto', 'ally'} else 'self',
        actor=parser.identity(name, 'species'), target=None, original_text=f'synthetic {n}',
        canonical_references=refs or {}, log_order=None,
        evidence=[dict(source_type='synthetic', source_id=f'synthetic#{n}', observation_ids=[str(n)], details={})],
        ocr_confidence=None, parsing_confidence='supported', uncertainty=[], status='confirmed',
        attributes=dict(actor_instance_id=pid, observation_time=n, **(attrs or {})))


def apply(engine, e):
    return engine.apply(e, sequence=int(e['event_id']))


def activation(parser, n=1):
    return event(parser, n, 'ability_activation', refs={'ability': parser.identity('变身者', 'ability')})


def result(parser, n=2, name='烈咬陆鲨'):
    return event(parser, n, 'transformation', attrs=dict(mechanic='transform', copied_identity=parser.identity(name, 'species')))


@pytest.mark.parametrize('text,kind,side', [
    ('对手的百变怪变身成了烈咬陆鲨！', 'transformation', 'opponent'),
    ('对手的百变怪变身成了大嘴鸥！', 'transformation', 'opponent'),
    ('我方因太紧张而无法食用树果！', 'move_effect', 'self'),
    ('对手因太紧张而无法食用树果！', 'move_effect', 'opponent'),
    ('百变怪使出了变身！', 'move_execution', 'self')])
def test_parser_and_occurrence_admission(parser, text, kind, side):
    occurrences = MessageOccurrences('synthetic')
    def row(t):
        return dict(timestamp=t, sha256=str(t), source_id=f'synthetic#{t}', image='fixture.png',
            message=dict(raw_text=text, confidence=.999, selected=True, source_region_type='battle_message'))
    first = occurrences.observe(row(1))['events']
    assert len(first) == 1 and first[0]['event_type'] == kind and first[0]['side'] == side
    assert not occurrences.observe(row(1.5))['events']


def test_snapshot_preserves_native_fields_and_does_not_recopy(parser):
    s = initial(parser); native = deepcopy(s.pokemon['ditto']); engine = StateEngine(s)
    r = apply(engine, activation(parser)); d = engine.state.pokemon['ditto']
    assert r.bindings['transformation']['target_instance_id'] == 'garchomp'
    assert d.species == native.species and d.original_identity == native.original_identity
    assert d.hp == native.hp and d.item == native.item and engine.state.knowledge['team'] == s.knowledge['team']
    assert d.current_types.value == ['dragon', 'ground'] and d.ability.current.value['name'] == '沙隐'
    assert d.stages['attack'].value.value == 2
    assert current(d).current['snapshot'].value['non_hp_stats']['attack']['value'] == 137
    assert current(d).current['snapshot'].value['non_hp_stats']['speed']['knowledge'] == 'unknown'
    assert d.moves.pp['pokeapi:move:406'].value == dict(current=3, maximum=3)
    assert d.moves.pp['pokeapi:move:182'].value['current'] == 5
    changed = event(parser, 2, 'stat_change', 'garchomp', attrs=dict(stats=['attack'], change='increment', stages=1))
    apply(engine, changed)
    apply(engine, result(parser, 3)); apply(engine, result(parser, 4))
    d = engine.state.pokemon['ditto']
    assert len(d.transformations) == 1 and d.stages['attack'].value.value == 2
    assert engine.state.pokemon['garchomp'].stages['attack'].value.value == 3
    apply(engine, activation(parser, 5))
    assert len(engine.state.pokemon['ditto'].transformations) == 1


def test_switch_return_identity_new_snapshot_and_retractions(parser):
    engine = StateEngine(initial(parser))
    apply(engine, activation(parser)); apply(engine, result(parser))
    copied = event(parser, 3, 'move_execution', refs={'move': parser.identity('龙之波动', 'move')}, attrs=dict(move_slot=1))
    apply(engine, copied)
    assert engine.state.pokemon['ditto'].moves.executed[-1]['move_origin'] == 'transformed'
    assert engine.state.pokemon['ditto'].moves.pp['pokeapi:move:406'].knowledge == 'unknown'
    apply(engine, event(parser, 4, 'switch_out'))
    d = engine.state.pokemon['ditto']
    assert current(d) is None and d.ability.current.value['name'] == '变身者'
    assert d.moves.known_slots['1'].value['name'] == '变身' and d.hp.current.value == 33
    returned = event(parser, 5, 'send_out', attrs=dict(slot='left', trainer_display_text='Trainer'))
    returned['attributes'].pop('actor_instance_id')
    receipt = apply(engine, returned)
    assert receipt.bindings['actor']['pokemon_instance_id'] == 'ditto'
    assert receipt.bindings['entry_episode']['persistent_identity_status'] == 'independently_supported'
    assert len(engine.state.sides['opponent'].party_instance_ids) == 2
    # Change the opposite HUD occupant for the next entry.
    # Use an explicit position exchange so replay preserves that observation.
    exchange = event(parser, 6, 'position_change', 'pelipper', attrs=dict(mechanic='ally_switch', execution_observed=True))
    apply(engine, exchange); apply(engine, activation(parser, 7)); apply(engine, result(parser, 8, '大嘴鸥'))
    d = engine.state.pokemon['ditto']
    assert current(d).current['target_instance_id'].value == 'pelipper' and len(d.transformations) == 2
    assert len([ep for ep in engine.state.knowledge['active_entry_episodes'] if ep['instance_id'] == 'ditto']) == 2
    engine.retract('7', reason='software test: withdraw activation')
    assert current(engine.state.pokemon['ditto']) is None
    engine.correct('7', activation(parser, 7), sequence=7, reason='restore activation')
    assert current(engine.state.pokemon['ditto']).current['target_instance_id'].value == 'pelipper'
    engine.retract('8', reason='result-only retraction leaves independent activation')
    assert current(engine.state.pokemon['ditto']) is not None
    restored = StateEngine.from_dict(engine.to_dict())
    assert restored.state.to_dict() == engine.state.to_dict()


def test_manual_transform_observed_ally_and_missing_target(parser):
    e = event(parser, 1, 'move_execution', attrs=dict(target_instance_id='ally', target_side='opponent'),
              refs={'move': parser.identity('变身', 'move')})
    engine = StateEngine(initial(parser)); apply(engine, e)
    assert current(engine.state.pokemon['ditto']).current['target_instance_id'].value == 'ally'
    assert current(engine.state.pokemon['ditto']).current['trigger'].value == 'manual_transform'
    missing = deepcopy(e); missing['attributes'].pop('target_instance_id')
    other = StateEngine(initial(parser)); apply(other, missing)
    assert current(other.state.pokemon['ditto']) is None
    assert not other.state.pokemon['ditto'].transformations


def test_unobserved_activation_never_infers_imposter(parser):
    engine = StateEngine(initial(parser)); apply(engine, result(parser, 1))
    assert current(engine.state.pokemon['ditto']) is None
    assert engine.history[0].bindings['transformation']['status'] == 'observed_result_target_snapshot_unresolved'


@pytest.mark.parametrize('reason', ['incomplete_roster', 'duplicate_ditto', 'wrong_trainer', 'other_species'])
def test_no_unsupported_species_merge(parser, reason):
    s = initial(parser)
    if reason == 'incomplete_roster':s.knowledge['identity_ledger']['roster'].pop()
    if reason == 'duplicate_ditto':s.knowledge['identity_ledger']['roster'][1]['species_id'] = 132
    engine = StateEngine(s); apply(engine, event(parser, 1, 'switch_out'))
    e = event(parser, 2, 'send_out', attrs=dict(slot='left', trainer_display_text='Wrong' if reason == 'wrong_trainer' else 'Trainer'))
    e['attributes'].pop('actor_instance_id')
    if reason == 'other_species':e['actor'] = parser.identity('化石翼龙', 'species')
    r = apply(engine, e)
    assert 'persistent_continuity' not in r.bindings


def test_unnerve_restriction_sources_suppression_and_no_item_hp_status_effect(parser):
    engine = StateEngine(initial(parser)); before = deepcopy(engine.state.pokemon)
    a = event(parser, 1, 'ability_activation', 'ally', refs={'ability': parser.identity('紧张感', 'ability')})
    apply(engine, a)
    e = event(parser, 2, 'move_effect', attrs=dict(effect=BERRIES, cause=dict(kind='ability',ability='unnerve'), affected_side='self'))
    e.update(side='self', actor=None);e['attributes'].pop('actor_instance_id')
    r = apply(engine, e)
    assert r.application_status == 'applied_confirmed' and r.bindings['ability_sources'][0]['instance_id'] == 'ally'
    for pid, p in engine.state.pokemon.items():
        assert p.item == before[pid].item and p.hp == before[pid].hp and p.major_status == before[pid].major_status
    effect = lambda: engine.state.sides['self'].temporary_effects[BERRIES]
    assert effect().active.value is True
    apply(engine, event(parser, 3, 'ability_change', 'ally', attrs=dict(suppressed=True)))
    assert effect().active.value is False
    apply(engine, event(parser, 4, 'ability_change', 'ally', attrs=dict(suppressed=False)))
    assert effect().active.value is True
    apply(engine, event(parser, 5, 'switch_out', 'ally'))
    assert effect().active.value is False
    engine.retract('5', reason='withdraw switch')
    assert effect().active.value is True
    apply(engine, event(parser, 6, 'ability_change', 'ally', refs={'ability': parser.identity('降雨', 'ability')}))
    assert effect().active.value is False


def test_unnerve_unknown_owner_is_observation_without_invented_item(parser):
    engine = StateEngine(initial(parser))
    e = event(parser, 1, 'move_effect', attrs=dict(effect=BERRIES, cause=dict(kind='ability',ability='unnerve')))
    e.update(side='self', actor=None);e['attributes'].pop('actor_instance_id')
    r = apply(engine, e)
    assert r.application_status == 'applied_confirmed' and r.bindings['ability_sources'] == []
    effect = engine.state.sides['self'].temporary_effects[BERRIES]
    assert effect.active.value is True and effect.initiated_by.knowledge == 'unknown'
    assert engine.state.pokemon['ditto'].item.identity.value['name'] == '文柚果'
    engine.retract('1', reason='remove observed notice')
    assert BERRIES not in engine.state.sides['self'].temporary_effects


def test_imposter_right_hud_and_unavailable_target(parser):
    s = initial(parser)
    s.sides['opponent'].active_slots = dict(left='ally', right='ditto')
    s.pokemon['ditto'].location = fact(dict(kind='active', slot='right'), PROOF)
    s.pokemon['ally'].location = fact(dict(kind='active', slot='left'), PROOF)
    engine = StateEngine(s); apply(engine, activation(parser))
    assert current(engine.state.pokemon['ditto']).current['target_instance_id'].value == 'pelipper'
    # No fallback to the remaining slot when the directly facing slot is empty.
    s.sides['self'].active_slots.pop('right')
    s.pokemon['pelipper'].location = fact(dict(kind='bench', slot=None), PROOF)
    engine = StateEngine(s); r = apply(engine, activation(parser))
    assert r.application_status == 'applied_confirmed'
    assert current(engine.state.pokemon['ditto']) is None


def test_unknown_move_slots_and_pp_stay_unknown(parser):
    s = initial(parser); g = s.pokemon['garchomp']
    g.moves.known_slots = {}; g.moves.pp = {}
    g.moves.executed = [dict(move=parser.identity('龙之波动', 'move'), event_id='earlier', evidence=PROOF)]
    engine = StateEngine(s); apply(engine, activation(parser))
    d = engine.state.pokemon['ditto']
    assert not d.moves.known_slots and d.moves.pp['pokeapi:move:406'].knowledge == 'unknown'
    assert list(current(d).current['revealed_moves'].value) == ['pokeapi:move:406']
    assert d.stages['speed'].value.knowledge == 'unknown'


def test_mega_z_form_remains_unresolved(parser):
    s = initial(parser); g = s.pokemon['garchomp']
    g.current_variant = fact('pokeapi:pokemon:10058', PROOF)
    g.species = fact(dict(species_id=445, name='超级烈咬陆鲨', canonical_id='pokeapi:form:10158', canonical_identity='pokeapi:pokemon:10058'), PROOF)
    g.transformations = [dict(mechanic='mega_evolution', after=deepcopy(g.species.value), evidence=PROOF)]
    s.observations.append(dict(attributes=dict(effect='mega_stone_reaction_notice', actor_instance_id='garchomp'),
        evidence=dict(sources=[dict(details=dict(row_evidence=[dict(text='烈咬陆鲨的烈咬陆鲨进化石Z和')]))])))
    engine = StateEngine(s); apply(engine, activation(parser))
    snapshot = current(engine.state.pokemon['ditto']).current['snapshot'].value
    assert snapshot['form']['knowledge'] == 'unknown' and snapshot['unresolved_form_evidence']
    assert snapshot['species']['value']['canonical_id'] == 'pokeapi:species:445'
    assert snapshot['species']['value']['reported_appearance'] == '超级烈咬陆鲨'
    assert 'canonical_identity' not in snapshot['species']['value']


def test_switch_retraction_and_active_state_round_trip(parser):
    engine = StateEngine(initial(parser)); apply(engine, activation(parser)); apply(engine, result(parser))
    active_state = from_dict(engine.state.to_dict())
    apply(engine, event(parser, 3, 'switch_out'))
    assert current(engine.state.pokemon['ditto']) is None
    engine.retract('3', reason='withdraw switch')
    assert current(engine.state.pokemon['ditto']) is not None
    restored = StateEngine(active_state); apply(restored, event(parser, 4, 'switch_out'))
    assert current(restored.state.pokemon['ditto']) is None
    assert restored.state.pokemon['ditto'].moves.known_slots['1'].value['name'] == '变身'


def test_manual_transform_fusion_keeps_observed_target_and_marks_copied_moves(parser):
    engine = StateEngine(initial(parser))
    e = event(parser, 1, 'move_execution', attrs=dict(fusion_context=True, source_region_type='battle_message', target_instance_id='ally', target_side='opponent'), refs={'move': parser.identity('变身', 'move')})
    r = apply(engine, e)
    assert current(engine.state.pokemon['ditto']).current['target_instance_id'].value == 'ally'
    assert r.bindings['admissibility']['effects'] == 'transform_snapshot_only'
    copied = event(parser, 2, 'move_execution', attrs=dict(fusion_context=True, source_region_type='battle_message'), refs={'move': parser.identity('岩崩', 'move')})
    r = apply(engine, copied)
    assert r.bindings['resolved_event']['attributes']['move_origin'] == 'transformed'
    assert engine.state.pokemon['ditto'].moves.known_slots == {}


def test_unnerve_two_sources_survive_one_departure(parser):
    engine = StateEngine(initial(parser))
    ability = {'ability': parser.identity('紧张感', 'ability')}
    apply(engine, event(parser, 1, 'ability_change', 'ally', refs=ability))
    apply(engine, event(parser, 2, 'ability_change', 'ditto', refs=ability))
    assert len(engine.state.sides['self'].temporary_effects[BERRIES].initiated_by.value) == 2
    apply(engine, event(parser, 3, 'switch_out', 'ally'))
    assert engine.state.sides['self'].temporary_effects[BERRIES].active.value is True
    apply(engine, event(parser, 4, 'faint', 'ditto'))
    assert engine.state.sides['self'].temporary_effects[BERRIES].active.value is False


def test_unknown_facing_identity_keeps_unknown_snapshot_on_result(parser):
    s = initial(parser)
    s.pokemon['garchomp'].species = Fact()
    s.pokemon['garchomp'].original_identity = Fact()
    engine = StateEngine(s)
    apply(engine, activation(parser))
    r = apply(engine, result(parser))
    assert r.application_status == 'applied_confirmed'
    m = current(engine.state.pokemon['ditto'])
    assert m.current['snapshot'].value['species']['knowledge'] == 'unknown'
    assert m.current['reported_identity'].value['species_id'] == 445
