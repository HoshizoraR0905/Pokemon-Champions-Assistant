"""Form continuity through canonical KB facts and existing stat feasibility."""
from copy import deepcopy
from itertools import product
from knowledge.champions_stats import ChampionsStats, adjustment_factors
from knowledge.stat_feasibility import champions_attainable_stats
from .core import ABILITIES, identity_key, knowledge, name


def mega_base_form(target):
    """Resolve the pre-Mega catalog form, without assuming all forms are base species."""
    kb = knowledge()
    fact = kb.facts['pokemon'].get(target, {})
    if not fact.get('upstream_name', '').startswith('Mega ') or not fact.get('required_item'):
        return None
    species = kb.entities[target].species_id
    candidates = [key for key, f in kb.facts['pokemon'].items()
                  if key in kb.entities and kb.entities[key].species_id == species
                  and not f.get('upstream_name', '').startswith('Mega ')]
    base = f'pokeapi:species:{species}'
    if base in candidates:
        return base
    if len(candidates) == 1:
        return candidates[0]
    raise ValueError('Pre-Mega form unresolved in canonical catalog')


def published_ability(source_form, source_ability, current_form):
    """Map a source assertion to the current native ability; never edit the source.

    Published Mega records can assert either an original ability or the Mega
    ability. A post-Mega assertion does not identify the original ability.
    """
    kb = knowledge(); ability = name(source_ability, 'ability')
    base = mega_base_form(source_form)
    if base:
        base_abilities = kb.facts['pokemon'][base]['ability_names']
        mega_abilities = kb.facts['pokemon'][source_form]['ability_names']
        if len(mega_abilities) != 1:
            raise ValueError('Mega active ability unresolved')
        if ability in base_abilities:
            original = ability
            stage = 'original_base_form'
        elif ability in mega_abilities:
            original = None
            stage = 'post_mega_form'
        else:
            raise ValueError('Source ability legal in neither pre-Mega nor Mega form')
        if current_form == source_form:
            active = mega_abilities[0]
        elif current_form == base:
            if original is None:
                raise ValueError('Published post-Mega ability does not identify original ability')
            active = original
        else:
            raise ValueError('Current form incompatible with published Mega form')
        return dict(source_ability=ability, source_ability_stage=stage,
                    original_form=base, original_ability=original,
                    original_ability_alternatives=[original] if original else list(base_abilities),
                    current_form=current_form, active_ability=active)
    if source_form != current_form or ability not in kb.facts['pokemon'][source_form]['ability_names']:
        raise ValueError('Source ability conflicts with native base-form domain')
    return dict(source_ability=ability, source_ability_stage='original_base_form',
                original_form=source_form, original_ability=ability,
                original_ability_alternatives=[ability], current_form=current_form, active_ability=ability)


def training_stats(identity, training):
    """Compact full training domain, not a fabricated zero-filled full build."""
    model = ChampionsStats(identity, form='as_named' if knowledge().entities[identity].form_id else 'base')
    factors = adjustment_factors(training['alignment'])
    domains = training['point_domains']
    if set(domains) != set(model.base_stats):
        raise ValueError('Full compact training domains required')
    rows = {stat: model.attainable(stat, adjustments=[factors[stat]], point_domain=values)['configurations']
            for stat, values in domains.items()}
    if any(not values for values in rows.values()):
        raise ValueError('Empty training domain')
    minima = {s: min(r['training_points'] for r in values) for s, values in rows.items()}
    if sum(minima.values()) > 66:
        raise ValueError('Infeasible training budget')
    stats = {s: sorted({r['actual_stat'] for r in values
                       if sum(minima.values()) - minima[s] + r['training_points'] <= 66})
             for s, values in rows.items()}
    if len(stats['speed']) != 1:
        raise ValueError('Each configuration must fix Speed training and alignment')
    return stats


def configuration_domain(*, identity, form, abilities, items, max_configurations=10000, **constraints):
    """Complete projection over legal SP/alignment branches and supplied item domains.

    Other stat domains stay correlated by one alignment and the <=66 budget.
    Caller-supplied ability domains must be native; replacement is explicit state
    evidence in the simulation. This is not regulation/roster certification.
    """
    key = identity_key(identity, form)
    if not isinstance(abilities, list) or not abilities or not isinstance(items, list) or not items:
        raise ValueError('Explicit finite item/ability domains required')
    abilities = sorted({name(a, 'ability') for a in abilities})
    items = sorted({name(i, 'item') for i in items})
    fact = knowledge().facts['pokemon'].get(key, {})
    if not set(abilities) <= set(fact.get('ability_names', [])):
        raise ValueError('Non-native ability domain requires replacement evidence')
    legal = champions_attainable_stats(identity=identity, form=form, stat='speed', **constraints)
    if legal['configurations'] is None:
        raise ValueError(str(legal['diagnostics']))
    branches = legal['configurations']['branches']
    count = sum(len(b['stat_point_domains']['speed']) for b in branches) * len(abilities) * len(items)
    if type(max_configurations) is not int or not 1 <= max_configurations <= 100000 or count > max_configurations:
        raise ValueError('Configuration limit exceeded; no configurations truncated')
    rows = []
    for branch in branches:
        for speed, ability, item in product(branch['stat_point_domains']['speed'], abilities, items):
            if fact.get('required_item') and item != fact['required_item']:
                continue
            points = {s: sorted({r['training_points'] for r in values})
                      for s, values in branch['stat_point_domains'].items()}
            points['speed'] = [speed['training_points']]
            rows.append(dict(id=str(len(rows)), speed=speed['actual_stat'], ability=ability, item=item,
                             form=key, training=dict(alignment=deepcopy(branch['alignment']), point_domains=points)))
    return dict(configurations=rows, legal=legal, scope=legal['provenance']['legality_scope'])


def transform(participant, target):
    """One legal Mega branch; unknown branches are enumerated by the caller."""
    kb = knowledge(); before = participant['_current_form']; target = identity_key(target, 'as_named')
    old = kb.entities[before]; new = kb.entities[target]
    fact = kb.facts['pokemon'].get(target, {})
    if (old.species_id != new.species_id or not fact.get('upstream_name', '').startswith('Mega ')
            or kb.facts['pokemon'].get(before, {}).get('required_item')):
        raise ValueError('Unsupported transformation or repeated Mega transformation')
    required = fact.get('required_item')
    if not required or name(participant['item'], 'item') != required:
        return None  # Incompatible hidden stone/form branch, not an unsupported rule.
    if len(fact.get('ability_names', [])) != 1:
        raise ValueError('Transformed native ability unresolved')
    from .mechanics import NEUTRAL_ABILITIES, ordering_coverage
    if fact['ability_names'][0] not in ABILITIES | NEUTRAL_ABILITIES | set(ordering_coverage()['neutral_abilities']):
        raise ValueError('Transformed ability side effects outside the audited subset')
    if not participant.get('training'):
        raise ValueError('Form transformation needs preserved training configuration')
    result = deepcopy(participant)
    stats = training_stats(target, result['training'])
    result.update(identity=target, form='as_named', _current_form=target,
                  actual_speed=stats['speed'][0], ability=fact['ability_names'][0],
                  form_stat_domains=stats)
    # Mega replaces the native ability. Existing explicit suppression is retained;
    # complex ability-lock/suppression interactions remain outside this subset.
    return result
