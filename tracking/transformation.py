"""Temporary Transform coverage inside PokemonState's existing mechanics.

Species/original_identity remain the underlying individual. Copied appearance
and numerical inputs live in the per-entry snapshot; no hidden build is guessed.
"""
from copy import deepcopy
from dataclasses import asdict

from .battle_state import Fact, Stage, fact
from .mechanics import ensure, active

IMPOSTER = 'pokeapi:ability:150'
TRANSFORM = 'pokeapi:move:144'
KEY = 'temporary_transform'


def current(p):
    m = p.mechanics.get(KEY)
    return m if m and m.current.get('active', Fact()).value is True else None


def known_configuration(state, p, name):
    field = state.knowledge.get('team', {}).get('instances', {}).get(p.pokemon_instance_id, {}).get('fields', {}).get(name, {})
    if field.get('status') in {'observed', 'manual_verified', 'knowledge_resolved'} and not field.get('conflicts') and field.get('value') is not None:
        return fact(deepcopy(field['value']), dict(source='known_team_configuration', field=deepcopy(field)), 'derived')
    return Fact()


def copy_fact(value, event):
    from .state_engine import evidence_link
    result = deepcopy(value)
    result.provenance.append(dict(**evidence_link(event), rule='transform_snapshot'))
    if result.known:
        result.knowledge = 'derived'
    return result


def begin(state, p, event, record, *, trigger):
    """Ability uses HUD opposition; manual execution requires observed targeting."""
    from .state_engine import evidence_link
    m = ensure(p, KEY, 'per_entry', reset=['switch_out'], persistence=['same_entry'])
    if current(p):
        record.bindings['transformation'] = dict(status='already_active', source_event_id=m.trigger_event_ids[0])
        return
    target_id = None
    if trigger == 'imposter':
        slot = next((s for s, pid in state.sides[p.side_id].active_slots.items() if pid == p.pokemon_instance_id), None)
        opposite = 'self' if p.side_id == 'opponent' else 'opponent'
        # Both teams' slots are screen-HUD coordinates, not physical positions.
        target_id = state.sides[opposite].active_slots.get(slot)
    elif event.attributes.get('target_instance_id'):
        target_id = event.attributes['target_instance_id']
    elif event.target and event.attributes.get('target_observed') is True:
        team = state.sides.get(event.attributes.get('target_side'))
        matches = [pid for pid in (team.active_slots.values() if team else [])
                   if state.pokemon[pid].species.known and state.pokemon[pid].species.value.get('species_id') == event.target.get('species_id')]
        if len(matches) == 1:
            target_id = matches[0]
    target = state.pokemon.get(target_id)
    if (target and trigger == 'manual_transform' and event.attributes.get('target_side')
            and target.side_id != event.attributes['target_side']):
        target = None
    m.trigger_event_ids = [event.event_id]
    m.provenance = [evidence_link(event)]
    m.current = {'trigger': fact(trigger, evidence_link(event)),
                 'active': Fact(provenance=[evidence_link(event)]),
                 'target_instance_id': Fact(provenance=[evidence_link(event)])}
    if not target or target is p or not active(target):
        record.bindings['transformation'] = dict(status='target_unresolved', trigger=trigger)
        return
    proof = dict(**evidence_link(event), target_instance_id=target_id, targeting=(
        'same_screen_hud_slot_opposite_side' if trigger == 'imposter' else 'explicit_observed_move_target'))
    # Keep the native move layout separate from copied slots and later executions.
    native = dict(types=asdict(p.current_types), ability=asdict(p.ability.current),
                  suppressed=asdict(p.ability.suppressed), stages={k:asdict(v) for k,v in p.stages.items()},
                  known_slots={k:asdict(v) for k,v in p.moves.known_slots.items()}, pp={k:asdict(v) for k,v in p.moves.pp.items()},
                  unrevealed_slots=asdict(p.moves.unrevealed_slots))
    moves = deepcopy(target.moves)
    if current(target):
        membership = deepcopy(current(target).current['revealed_moves'].value)
    else:
        membership = {x['move']['canonical_id']: deepcopy(x['move']) for x in moves.executed if x.get('move_origin') != 'transformed'}
    membership.update({x.value['canonical_id']: deepcopy(x.value) for x in moves.known_slots.values() if x.known})
    copied_pp = {}
    for cid in membership:
        observed = moves.pp.get(cid, Fact())
        maximum = observed.value.get('maximum') if observed.known and isinstance(observed.value, dict) else None
        copied_pp[cid] = (fact(dict(current=min(5, maximum), maximum=min(5, maximum)), proof, 'derived')
                          if isinstance(maximum, int) and maximum > 0 else
                          Fact(provenance=[dict(**proof, rule='min(5, applicable maximum PP)', reason='applicable_maximum_unknown')]))
    appearance = deepcopy(target.species)
    form = deepcopy(target.current_variant)
    form_evidence = deepcopy(target.transformations)
    # Frozen Mega-Z reactions cannot certify the ordinary Mega canonical ID.
    z_evidence = [o for o in state.observations if o.get('attributes', {}).get('effect') == 'mega_stone_reaction_notice'
                  and o.get('attributes', {}).get('actor_instance_id') == target_id
                  and '进化石Z' in ''.join(s.get('details', {}).get('row_evidence', [{}])[0].get('text', '')
                                         for s in o.get('evidence', {}).get('sources', []))]
    target_stats=target.mechanics.get('battle_stats')
    verified_form=bool(target_stats and target_stats.current.get('form_verified',Fact()).value is True
                       and target_stats.current.get('canonical_variant',Fact()).value==target.current_variant.value)
    if z_evidence and not verified_form:
        form = Fact(provenance=[proof, dict(reason='mega_z_canonical_unresolved', evidence=deepcopy(z_evidence))])
        if appearance.known:
            reported = appearance.value.get('name')
            appearance.value = deepcopy(target.original_identity.value) if target.original_identity.known else {'species_id': appearance.value.get('species_id')}
            appearance.value.update(form_unresolved=True, reported_appearance=reported)
            for key in ('canonical_identity', 'pokemon_id', 'form_id'):
                appearance.value.pop(key, None)
    observed_stats = target.mechanics.get('battle_stats')
    stats = {name: copy_fact(observed_stats.current.get(name, Fact()) if observed_stats else
                            Fact() if target.transformations else known_configuration(state, target, name), event)
             for name in ('attack', 'defense', 'special_attack', 'special_defense', 'speed')}
    snapshot = dict(target_instance_id=target_id, target_identity=asdict(target.original_identity),
        species=asdict(copy_fact(appearance, event)), form=asdict(copy_fact(form, event)),
        form_evidence=form_evidence, unresolved_form_evidence=z_evidence,
        types=asdict(copy_fact(target.current_types, event)), ability=asdict(copy_fact(target.ability.current, event)),
        non_hp_stats={k: asdict(v) for k, v in stats.items()},
        stages={k: asdict(v) for k, v in target.stages.items()},
        moves=dict(known_slots={k: asdict(v) for k, v in moves.known_slots.items()},
                   revealed_members=membership, pp={k: asdict(v) for k, v in copied_pp.items()}),
        evidence=proof)
    m.current.update(active=fact(True, proof, 'derived'), target_instance_id=fact(target_id, proof, 'derived'),
                     snapshot=fact(snapshot, proof, 'derived'), native=fact(native, proof, 'derived'),
                     revealed_moves=fact(membership, proof, 'derived'))
    p.current_types = copy_fact(target.current_types, event)
    p.ability.current = copy_fact(target.ability.current, event)
    # Suppression is not evidence for a copied species/ability property.
    p.ability.suppressed = Fact(provenance=[proof])
    p.stages = deepcopy(target.stages)
    for stage in p.stages.values():
        stage.value = copy_fact(stage.value, event)
        stage.interval = copy_fact(stage.interval, event)
    p.moves.known_slots = {k: copy_fact(v, event) for k, v in moves.known_slots.items()}
    p.moves.pp = copied_pp
    p.moves.unrevealed_slots = copy_fact(moves.unrevealed_slots, event)
    p.transformations.append(dict(mechanic='transform', trigger=trigger, source_event_id=event.event_id,
                                 snapshot=deepcopy(snapshot), evidence=evidence_link(event), active=True))
    record.bindings['transformation'] = dict(status='snapshot_created', target_instance_id=target_id, trigger=trigger)


def result(state, p, event, record):
    from .state_engine import evidence_link, Contradiction
    m = p.mechanics.get(KEY)
    copied = event.attributes.get('copied_identity') or {}
    if current(p):
        snapshot = m.current['snapshot'].value
        target_species = (snapshot['species']['value'] or {}).get('species_id')
        if copied.get('species_id') and target_species and target_species != copied['species_id']:
            raise Contradiction('transform_result_target_disagreement')
        if event.event_id not in m.trigger_event_ids:
            m.trigger_event_ids.append(event.event_id)
            m.provenance.append(evidence_link(event))
        m.current['result_observed'] = fact(True, evidence_link(event))
        if copied:
            m.current['reported_identity'] = fact(deepcopy(copied), evidence_link(event))
        record.bindings['transformation'] = dict(status='result_linked_without_recopy',
            target_instance_id=snapshot['target_instance_id'], source_event_id=m.trigger_event_ids[0])
    else:
        # The result establishes an appearance, not the trigger/target instance.
        m = ensure(p, KEY, 'per_entry', reset=['switch_out'])
        m.current['reported_identity'] = fact(deepcopy(copied), evidence_link(event))
        m.current['result_observed'] = fact(True, evidence_link(event))
        record.bindings['transformation'] = dict(status='observed_result_target_snapshot_unresolved')
    state.observations.append(dict(event_id=event.event_id, event_type='transformation',
                                   attributes=deepcopy(event.attributes), evidence=evidence_link(event)))


def end(p, event):
    from .state_engine import evidence_link
    m = current(p)
    if not m:
        return
    native = m.current.pop('native').value
    p.current_types = Fact(**native['types'])
    p.ability.current = Fact(**native['ability'])
    p.ability.suppressed = Fact(**native['suppressed'])
    p.stages = {k:Stage(value=Fact(**v['value']),interval=Fact(**v['interval']),changes=v['changes']) for k,v in native['stages'].items()}
    p.moves.known_slots = {k:Fact(**v) for k,v in native['known_slots'].items()}
    p.moves.pp = {k:Fact(**v) for k,v in native['pp'].items()}
    p.moves.unrevealed_slots = Fact(**native['unrevealed_slots'])
    m.current['active'] = fact(False, evidence_link(event))
    for row in reversed(p.transformations):
        if row.get('mechanic') == 'transform' and row.get('active'):
            row.update(active=False, ended_by=evidence_link(event))
            break


def execution(state, p, event, record):
    """Tag copied membership without inventing native slots or usages/priors."""
    from .state_engine import evidence_link
    m = current(p)
    if m:
        event.attributes['move_origin'] = 'transformed'
        event.attributes['transformation_source_event_id'] = m.trigger_event_ids[0]
        ref = event.canonical_references.get('move')
        if ref:
            m.current['revealed_moves'].value[ref['canonical_id']] = deepcopy(ref)
            for row in reversed(p.moves.executed):
                if row['event_id'] == event.event_id:
                    row.update(move_origin='transformed', transformation_source_event_id=m.trigger_event_ids[0])
                    break
            pp = p.moves.pp.get(ref['canonical_id'])
            if pp and pp.known and isinstance(pp.value, dict):
                # Initialization is specified by the approved Transform rule;
                # an execution alone does not establish its actual PP cost.
                # Preserve a directly observed remaining PP value when supplied.
                if event.attributes.get('pp') is None:
                    p.moves.pp[ref['canonical_id']] = Fact(provenance=[
                        *deepcopy(pp.provenance), dict(**evidence_link(event),
                            reason='remaining_pp_unobserved_after_execution', initialized_pp=deepcopy(pp.value))])
    if event.canonical_references.get('move', {}).get('canonical_id') == TRANSFORM and not m:
        begin(state, p, event, record, trigger='manual_transform')
