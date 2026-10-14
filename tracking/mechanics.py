"""Scoped stateful mechanics, independent of OCR and event-source replay storage."""
from copy import deepcopy
from dataclasses import asdict
from typing import Protocol
from .battle_state import Fact, MechanicState, fact, Duration, MECHANIC_SCOPES
from .mechanic_rules import MechanicRules

PROTEAN = 'pokeapi:ability:168'
UNBURDEN = 'pokeapi:ability:84'
ENTRY_ABILITIES = {'pokeapi:ability:22', 'pokeapi:ability:70', 'pokeapi:ability:2', 'pokeapi:ability:227',
                   'pokeapi:ability:117', 'pokeapi:ability:229'}


def ability(p):
    return p.ability.current.value.get('canonical_id') if p.ability.current.known and p.ability.current.value else None


def active(p):
    return p.location.known and p.location.value['kind'] == 'active'


def ensure(owner, identifier, scope, *, activation=(), persistence=(), reset=()):
    if identifier not in owner.mechanics:
        owner.mechanics[identifier] = MechanicState(identifier, scope,
            activation_conditions=list(activation), persistence_conditions=list(persistence), reset_conditions=list(reset))
    m = owner.mechanics[identifier]
    if m.mechanic_id != identifier or m.scope != scope:
        raise ValueError('Mechanic scope/identifier mismatch')
    for name, conditions in (('activation_conditions', activation),
                             ('persistence_conditions', persistence), ('reset_conditions', reset)):
        if conditions and not getattr(m, name):
            setattr(m, name, list(conditions))
    return m


def read(m, key):
    return m.current.get(key, Fact())


def evidence(event, rules, *, inferred=False, inputs=None):
    return {'event_id': event.event_id, 'event_status': event.status,
            'sources': [asdict(e) for e in event.evidence],
            'rule_profile': rules.profile_id, 'rule_verification': rules.verification,
            'rule_sources': rules.sources if inferred else [], 'inputs': inputs or {}}


def update(m, key, value, event, rules, *, inferred=False, inputs=None):
    m.current[key] = fact(deepcopy(value), evidence(event, rules, inferred=inferred, inputs=inputs),
                          'derived' if inferred else 'observed')
    touch(m, event, rules)


def unknown(m, key, event, rules):
    m.current[key] = Fact(provenance=[evidence(event, rules)])
    touch(m, event, rules)


def touch(m, event, rules):
    if event.event_id not in m.trigger_event_ids:
        m.trigger_event_ids.append(event.event_id)
        m.provenance.append(evidence(event, rules))


def item_presence(p):
    status = p.item.status
    if status.known and status.value == 'known':
        return Fact(True, status.knowledge, deepcopy(status.provenance))
    if status.known and status.value in {'none', 'consumed', 'transferred'}:
        return Fact(False, status.knowledge, deepcopy(status.provenance))
    return Fact(provenance=deepcopy(status.provenance))


class Handler(Protocol):
    mechanic_id: str
    def on_event(self, state, before, pokemon, event, rules): ...


class EntryHandler:
    mechanic_id = 'field_entry'

    def on_event(self, state, before, p, event, rules):
        if p is None:
            return
        if event.event_type == 'send_out':
            m = ensure(p, self.mechanic_id, 'per_instance')
            count = read(m, 'observed_entry_count')
            update(m, 'observed_entry_count', count.value + 1 if count.known else 1, event, rules, inferred=True)
            update(m, 'entry_id', p.pokemon_instance_id + ':entry:' + event.event_id, event, rules, inferred=True)
            update(m, 'active', True, event, rules)
        elif event.event_type in {'switch_out', 'faint'}:
            m = ensure(p, self.mechanic_id, 'per_instance')
            update(m, 'active', False, event, rules)
            # Type reversion is not guessed from unknown native typing.
            p.current_types = Fact(provenance=[evidence(event, rules)])


class ProtectHandler:
    mechanic_id = 'protect_chain'

    def on_event(self, state, before, p, event, rules):
        if p is None:
            return
        kind = event.event_type
        move_id = event.canonical_references.get('move', {}).get('canonical_id')
        attempted = kind == 'protection_attempt' or kind == 'move_execution' and move_id in rules.protect_move_ids
        existing = p.mechanics.get(self.mechanic_id)
        if not attempted and kind not in {'protection_outcome', 'mechanic_reset', 'send_out'} and existing is None:
            return
        if kind == 'mechanic_reset' and event.attributes.get('mechanic_id') != self.mechanic_id:
            return
        m = ensure(p, self.mechanic_id, 'per_instance', activation=('executed protection attempt', 'observed outcome'),
                   persistence=('supported consecutive protection outcomes without history gaps',),
                   reset=('verified stall failure', 'observed non-family action with supported rules', 'switch', 'verified expiry'))
        if attempted:
            if not active(p):
                raise ValueError('Protection attempt while inactive')
            if move_id not in rules.protect_move_ids:
                raise ValueError('Protection family is unresolved under selected rules')
            # A lost outcome or unobserved intervening turn invalidates continuity.
            if read(m, 'pending').known and read(m, 'pending').value:
                unknown(m, 'success_count', event, rules)
            last_turn = read(m, 'last_success_turn')
            if last_turn.known and state.turn.known and state.turn.value > last_turn.value + 1:
                unknown(m, 'success_count', event, rules)
            update(m, 'attempted', True, event, rules)
            update(m, 'pending', True, event, rules)
            update(m, 'attempt_event_id', event.event_id, event, rules)
            update(m, 'attempt_entry_id', read(p.mechanics.get('field_entry', MechanicState('field_entry', 'per_instance')), 'entry_id').value, event, rules)
            unknown(m, 'last_outcome', event, rules)
        elif kind == 'protection_outcome':
            if not read(m, 'pending').known or not read(m, 'pending').value:
                raise ValueError('Protection outcome without pending executed attempt')
            if event.attributes.get('attempt_event_id') != read(m, 'attempt_event_id').value:
                raise ValueError('Protection outcome does not identify pending attempt')
            outcome = event.attributes.get('outcome')
            if outcome not in {'success', 'failure'}:
                raise ValueError('Invalid protection outcome')
            update(m, 'pending', False, event, rules)
            update(m, 'last_outcome', outcome, event, rules)
            if outcome == 'success':
                count = read(m, 'success_count')
                if count.known:
                    update(m, 'success_count', count.value + 1, event, rules, inferred=True,
                           inputs={'previous_count': asdict(count)})
                else:
                    unknown(m, 'success_count', event, rules)
                if state.turn.known:
                    update(m, 'last_success_turn', state.turn.value, event, rules)
                else:
                    unknown(m, 'last_success_turn', event, rules)
            elif rules.protect_resets and event.attributes.get('failure_reason') == 'stall_check':
                update(m, 'success_count', 0, event, rules, inferred=True)
            else:
                unknown(m, 'success_count', event, rules)
        elif kind == 'mechanic_reset':
            if not event.attributes.get('reason'):
                raise ValueError('Mechanic reset requires evidence reason')
            update(m, 'success_count', 0, event, rules)
            update(m, 'pending', False, event, rules)
        elif kind in {'switch_out', 'faint', 'send_out'}:
            if rules.protect_resets:
                update(m, 'success_count', 0, event, rules, inferred=True)
            else:
                unknown(m, 'success_count', event, rules)
            update(m, 'pending', False, event, rules, inferred=True)
        elif kind == 'move_execution' and move_id not in rules.protect_move_ids:
            # This is an explicit completed non-family action, not a UI selection.
            if rules.protect_resets and event.attributes.get('action_completed') is True:
                update(m, 'success_count', 0, event, rules, inferred=True)
                update(m, 'pending', False, event, rules, inferred=True)
            else:
                unknown(m, 'success_count', event, rules)
        elif kind == 'turn_boundary':
            # A boundary alone is insufficient to prove no action occurred.
            if event.attributes.get('action_coverage_complete') is True and event.attributes.get('boundary') == 'end':
                last = read(m, 'last_success_turn')
                if rules.protect_resets and last.known and event.attributes['turn'] > last.value:
                    update(m, 'success_count', 0, event, rules, inferred=True)
            elif event.attributes.get('history_gap') is True:
                unknown(m, 'success_count', event, rules)


class ProteanHandler:
    mechanic_id = 'protean'

    def on_event(self, state, before, p, event, rules):
        if p is None:
            return
        relevant = ability(p) == PROTEAN or self.mechanic_id in p.mechanics
        if not relevant:
            return
        m = ensure(p, self.mechanic_id, 'per_entry', activation=('observed Protean activation',),
                   persistence=('same field entry and ability instance; suppression does not reset activation',),
                   reset=('verified re-entry', 'explicit ability instance replacement'))
        kind = event.event_type
        if kind == 'send_out':
            update(m, 'entry_id', read(p.mechanics['field_entry'], 'entry_id').value, event, rules, inferred=True)
            m.current.pop('resulting_types', None)
            if rules.protean_once_per_entry:
                update(m, 'activated', False, event, rules, inferred=True)
            else:
                unknown(m, 'activated', event, rules)
        elif kind == 'ability_activation' and ability(p) == PROTEAN:
            if not active(p):
                raise ValueError('Protean activation while inactive')
            if rules.protean_once_per_entry and read(m, 'activated').known and read(m, 'activated').value:
                raise ValueError('Protean repeated activation in same ability/entry instance')
            update(m, 'activated', True, event, rules)
            update(m, 'entry_id', read(p.mechanics['field_entry'], 'entry_id').value, event, rules, inferred=True)
            if event.attributes.get('resulting_types') is not None:
                set_types(p, event.attributes['resulting_types'], event, rules)
                m.current['resulting_types'] = deepcopy(p.current_types)
        elif kind == 'ability_attempt' and event.attributes.get('mechanic_id') == self.mechanic_id:
            touch(m, event, rules)  # Attempt is not a new activation.
        elif kind == 'type_change' and event.attributes.get('cause') == 'protean':
            if ability(p) != PROTEAN or not read(m, 'activated').known or read(m, 'activated').value is not True:
                raise ValueError('Protean type change without supported activation')
            m.current['resulting_types'] = deepcopy(p.current_types)
            touch(m, event, rules)
        elif kind == 'ability_change' and event.attributes.get('new_ability_instance') is True:
            # Mega evolution alone doesn't prove an ability instance reset.
            if rules.protean_once_per_entry:
                update(m, 'activated', False, event, rules, inferred=True)
            else:
                unknown(m, 'activated', event, rules)
        elif kind in {'switch_out', 'faint'}:
            unknown(m, 'eligibility', event, rules)
        eligible = read(m, 'activated')
        if active(p) and ability(p) == PROTEAN and rules.protean_once_per_entry and eligible.known:
            if p.ability.suppressed.known:
                update(m, 'eligibility', not eligible.value and not p.ability.suppressed.value, event, rules, inferred=True)
            elif eligible.value:
                update(m, 'eligibility', False, event, rules, inferred=True)
            else:
                unknown(m, 'eligibility', event, rules)
        else:
            unknown(m, 'eligibility', event, rules)


def set_types(p, types, event, rules):
    valid = {'normal','fire','water','electric','grass','ice','fighting','poison','ground','flying',
             'psychic','bug','rock','ghost','dragon','dark','steel','fairy'}
    if not isinstance(types, list) or not 1 <= len(types) <= 2 or len(set(types)) != len(types) or any(t not in valid for t in types):
        raise ValueError('Invalid observed Pokémon types')
    p.current_types = fact(types, evidence(event, rules))


class UnburdenHandler:
    mechanic_id = 'unburden'

    def on_event(self, state, before, p, event, rules):
        if p is None:
            return
        if ability(p) != UNBURDEN and self.mechanic_id not in p.mechanics:
            return  # Psychic Seed does not establish ability identity.
        m = ensure(p, self.mechanic_id, 'per_entry', activation=('supported item loss with established ability',),
                   persistence=('latched trigger in same entry and ability instance', 'effect requires no held item and unsuppressed ability'),
                   reset=('switch/faint', 'ability instance ends'),)
        entry = p.mechanics.get('field_entry')
        if entry and read(entry,'entry_id').known:
            m.current['entry_id'] = deepcopy(read(entry,'entry_id'))
        update(m, 'ability_established', ability(p) == UNBURDEN, event, rules, inferred=True)
        m.current['has_item'] = item_presence(p)
        old = before.pokemon.get(p.pokemon_instance_id)
        loss = (event.event_type == 'item_change' and event.attributes.get('change') in {'consume','remove','transfer'}
                and event.attributes.get('actor_instance_id', p.pokemon_instance_id) == p.pokemon_instance_id)
        if loss:
            update(m, 'last_item_change', event.attributes['change'], event, rules)
            established = old is not None and item_presence(old).known and item_presence(old).value is True
            if rules.unburden_item_loss and established and ability(p) == UNBURDEN and active(p) and p.ability.suppressed.known and not p.ability.suppressed.value:
                update(m, 'condition_established', True, event, rules, inferred=True,
                       inputs={'prior_item': asdict(item_presence(old)), 'ability': asdict(p.ability.current)})
                update(m, 'trigger_latched', True, event, rules, inferred=True)
            else:
                unknown(m, 'condition_established', event, rules)
                unknown(m, 'trigger_latched', event, rules)
        elif event.event_type == 'mechanic_observation' and event.attributes.get('mechanic_id') == self.mechanic_id:
            pass  # Explicit mechanic observations already applied by the registry.
        elif event.event_type in {'send_out', 'switch_out', 'faint'} or (event.event_type == 'ability_change' and
                (ability(p) != UNBURDEN or event.attributes.get('new_ability_instance') is True)):
            if rules.unburden_item_loss:
                update(m, 'trigger_latched', False, event, rules, inferred=True)
            else:
                unknown(m, 'trigger_latched', event, rules)
        elif event.event_type == 'item_change' and event.attributes.get('change') in {'replace', 'reveal'}:
            update(m, 'last_item_change', 'reacquired_or_revealed', event, rules)
        latch, present = read(m, 'trigger_latched'), item_presence(p)
        if not rules.unburden_item_loss:
            # Explicit observations are retained, but no rule-derived multiplier.
            if not (event.event_type == 'mechanic_observation' and event.attributes.get('mechanic_id') == self.mechanic_id):
                unknown(m, 'effect_active', event, rules)
            unknown(m, 'speed_multiplier', event, rules)
        elif not active(p) or ability(p) != UNBURDEN or present.known and present.value or p.ability.suppressed.known and p.ability.suppressed.value or latch.known and not latch.value:
            update(m, 'effect_active', False, event, rules, inferred=True)
            update(m, 'speed_multiplier', 1, event, rules, inferred=True)
        elif latch.known and latch.value and present.known and not present.value and p.ability.suppressed.known:
            update(m, 'effect_active', True, event, rules, inferred=True)
            update(m, 'speed_multiplier', 2, event, rules, inferred=True)
        else:
            unknown(m, 'effect_active', event, rules)
            unknown(m, 'speed_multiplier', event, rules)


class EntryAbilityHandler:
    mechanic_id = 'entry_triggers'

    def on_event(self, state, before, p, event, rules):
        if p is None:
            return
        if event.event_type == 'send_out' and self.mechanic_id in p.mechanics:
            m = p.mechanics[self.mechanic_id]
            m.current = {'entry_id': deepcopy(read(p.mechanics['field_entry'],'entry_id'))}
            update(m, 'activation_count', 0, event, rules, inferred=True)
            return
        if event.event_type != 'ability_activation' or ability(p) not in ENTRY_ABILITIES:
            return
        if not active(p):
            raise ValueError('Entry ability activation while inactive')
        m = ensure(p, self.mechanic_id, 'per_entry', activation=('observed ability activation',),
                   persistence=('activation record retained for the current field entry',), reset=('entry identifier change',))
        entry_id = read(p.mechanics['field_entry'], 'entry_id')
        if read(m, 'entry_id').value != entry_id.value:
            m.current = {}
        m.current['entry_id'] = deepcopy(entry_id)
        update(m, 'ability', ability(p), event, rules)
        count = read(m, 'activation_count')
        update(m, 'activation_count', count.value + 1 if count.known else 1, event, rules, inferred=True)
        # Weather, terrain, and stat consequences remain separate event handlers.


class MechanicRegistry:
    def __init__(self, handlers=None):
        self.handlers = list(handlers) if handlers is not None else [EntryHandler(), ProtectHandler(), ProteanHandler(), UnburdenHandler(), EntryAbilityHandler()]

    def register(self, handler):
        if any(h.mechanic_id == handler.mechanic_id for h in self.handlers):
            raise ValueError('Duplicate mechanic handler')
        self.handlers.append(handler)

    def initialize(self, state):
        for p in state.pokemon.values():
            if active(p) and 'field_entry' not in p.mechanics:
                m = ensure(p, 'field_entry', 'per_instance')
                source = {'rule': 'initial_active_location_is_partial_entry', 'location': asdict(p.location)}
                m.current = {'entry_id': fact(p.pokemon_instance_id + ':initial-entry', source, 'derived'),
                             'active': deepcopy(p.location), 'observed_entry_count': fact(0, source, 'derived')}
                m.current['active'] = fact(True, source, 'derived')
            if ability(p) == PROTEAN:
                ensure(p, 'protean', 'per_entry')
            if ability(p) == UNBURDEN:
                ensure(p, 'unburden', 'per_entry')

    def after_event(self, state, before, event, record, rules):
        pid = record.bindings.get('actor', {}).get('pokemon_instance_id')
        p = state.pokemon.get(pid)
        if event.event_type == 'type_change' and p is None:
            raise ValueError('Type change needs a Pokémon instance')
        if event.event_type == 'type_change':
            set_types(p, event.attributes.get('types'), event, rules)
        if event.event_type == 'mechanic_observation':
            self.observe(state, p, event, rules)
        if event.event_type == 'mechanic_reset' and event.attributes.get('mechanic_id') != 'protect_chain':
            self.reset(state, p, event, rules)
        self.initialize(state)
        self.expire(state, before, event, rules)
        if event.event_type == 'turn_boundary':
            for pokemon in state.pokemon.values():
                for handler in self.handlers:
                    handler.on_event(state, before, pokemon, event, rules)
        else:
            for handler in self.handlers:
                handler.on_event(state, before, p, event, rules)
            # Transfers change two owners; refresh the recipient's conditional effect.
            target_id = record.bindings.get('target', {}).get('pokemon_instance_id')
            if event.event_type == 'item_change' and event.attributes.get('change') == 'transfer' and target_id:
                target = state.pokemon[target_id]
                for handler in self.handlers:
                    if handler.mechanic_id == 'unburden':
                        recipient_event = deepcopy(event)
                        recipient_event.attributes['change'] = 'replace'
                        handler.on_event(state, before, target, recipient_event, rules)

    def observe(self, state, p, event, rules):
        a = event.attributes; scope = a.get('scope'); identifier = a.get('mechanic_id')
        if scope not in MECHANIC_SCOPES or not isinstance(identifier, str) or not identifier:
            raise ValueError('Mechanic observation requires typed scope and identifier')
        owner = state if scope == 'global' else state.sides.get(event.side) if scope == 'per_side' else p
        if owner is None:
            raise ValueError('Missing scoped mechanic owner')
        if identifier in {'field_entry', 'protect_chain', 'protean', 'entry_triggers'}:
            raise ValueError('Use dedicated lifecycle/outcome events for built-in counters')
        if identifier == 'unburden':
            if p is None or ability(p) != UNBURDEN or scope != 'per_entry':
                raise ValueError('Unburden observation requires supported ability identity')
            if set(a.get('facts', {})) - {'condition_established', 'trigger_latched', 'effect_active'}:
                raise ValueError('Unsupported Unburden observation fact')
        m = ensure(owner, identifier, scope, activation=a.get('activation_conditions', ()),
                   persistence=a.get('persistence_conditions', ()), reset=a.get('reset_conditions', ()))
        for key, payload in a.get('facts', {}).items():
            if not isinstance(payload, dict) or 'knowledge' not in payload:
                raise ValueError('Mechanic facts require explicit knowledge status')
            value = Fact(**deepcopy(payload))
            value.provenance.append(evidence(event, rules))
            m.current[key] = value
        if 'expiration' in a:
            exp = a['expiration']
            if not isinstance(exp, dict) or set(exp) - {'remaining','expires_at_turn','timing','modifiers'}:
                raise ValueError('Invalid mechanic expiration fields')
            m.expiration = Duration(**{k: Fact(**v) for k, v in exp.items()})
            for k in ('remaining','expires_at_turn'):
                f = getattr(m.expiration,k)
                if f.known and (not isinstance(f.value,int) or isinstance(f.value,bool) or f.value < 0):
                    raise ValueError('Invalid mechanic expiration count')
            if m.expiration.timing.known and m.expiration.timing.value not in {'turn_start','turn_end'}:
                raise ValueError('Invalid mechanic expiration timing')
        touch(m, event, rules)

    def reset(self, state, p, event, rules):
        a = event.attributes
        identifier, scope = a.get('mechanic_id'), a.get('scope')
        owner = state if scope == 'global' else state.sides.get(event.side) if scope == 'per_side' else p
        if owner is None or identifier not in owner.mechanics or not a.get('reason'):
            raise ValueError('Explicit reset needs an existing mechanic and evidence reason')
        if identifier in {'field_entry', 'protean', 'unburden', 'entry_triggers'}:
            raise ValueError('Built-in reset requires its dedicated lifecycle event')
        observation = deepcopy(event)
        observation.attributes = dict(a, expiration={})
        self.observe(state, p, observation, rules)
        owner.mechanics[identifier].current['expired'] = fact(False, evidence(event,rules), 'derived')

    def expire(self, state, before, event, rules):
        if event.event_type != 'turn_boundary':
            return
        boundary = 'turn_' + event.attributes['boundary']
        turn = event.attributes['turn']
        owners = [state, *state.sides.values(), *state.pokemon.values()]
        for owner in owners:
            for m in owner.mechanics.values():
                d = m.expiration
                if not d.timing.known or d.timing.value != boundary:
                    continue
                if d.last_tick.known and d.last_tick.value[1] >= turn:
                    continue
                if before.turn.known and turn > before.turn.value + 1:
                    d.remaining = Fact(provenance=[evidence(event, rules)])
                elif d.remaining.known:
                    d.remaining = fact(max(0, d.remaining.value - 1), evidence(event, rules), 'derived')
                if (d.remaining.known and d.remaining.value == 0 or
                        d.expires_at_turn.known and turn >= d.expires_at_turn.value):
                    update(m, 'expired', True, event, rules, inferred=True)
                d.last_tick = fact([boundary, turn], evidence(event, rules), 'derived')
