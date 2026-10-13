"""Canonical Pokémon variant identity from pinned PokéAPI form rows."""
from collections import defaultdict


class IdentityIndex:
    def __init__(self, payload, *, scope=None):
        if scope is not None and not isinstance(scope, dict):
            raise ValueError('Identity scope must be a versioned rule record or None')
        self.scope = scope
        self.scope_id = scope['scope_id'] if scope else 'unrestricted'
        self.forms = {r.get('source_form_id', r['form_id']): r for r in payload.get('forms', [])}
        self.by_species = defaultdict(list)
        self.by_pokemon = defaultdict(list)
        for row in self.forms.values():
            self.by_species[row['species_id']].append(row)
            self.by_pokemon[row['pokemon_id']].append(row)

    def variant_applicability(self, row):
        """Current-scope candidate status; never alters source identity rows.

        Unknown rows remain candidates. The G-Max rule is an inference from
        the official M-C mechanics section, not a global availability claim.
        """
        if self.scope is None:
            return {'status': 'indeterminate', 'reason': 'no_game_regulation_scope'}
        availability = row.get('champions_availability', {})
        if availability.get('legality') == 'illegal' and availability.get('legality_source'):
            return {'status': 'confirmed_inapplicable', 'reason': 'explicit_regulation_illegality',
                    'source': availability['legality_source']}
        if (availability.get('legality') == 'legal' and availability.get('legality_source') or
                availability.get('reason') == 'exact_official_default_form_row'):
            return {'status': 'confirmed_applicable', 'reason': 'affirmative_form_evidence',
                    'source': availability.get('legality_source') or availability.get('source')}
        if availability.get('legality') == 'legal' or availability.get('status') == 'confirmed_available':
            return {'status': 'supported_applicable', 'reason': 'community_form_evidence',
                    'source': availability.get('source')}
        for rule in self.scope.get('mechanic_rules', []):
            if row['identifier'].endswith(rule['variant_identifier_suffix']):
                return {k: rule[k] for k in ('status', 'reason', 'source')}
        return {'status': 'unknown', 'reason': 'no_form_applicability_evidence'}

    def applicable_forms(self, species_id):
        return [r for r in self.by_species.get(species_id, []) if
                self.variant_applicability(r)['status'] not in
                ('confirmed_inapplicable', 'inferred_inapplicable')]

    def for_form(self, form_id):
        row = self.forms.get(form_id)
        if row is None:
            return self.unresolved()
        multiple = len(self.by_pokemon[row['pokemon_id']]) > 1
        applicable = self.applicable_forms(row['species_id'])
        if multiple:
            status = 'resolved_form'
        elif row in applicable and len(applicable) == 1:
            status = 'resolved_unique'
        elif row['pokemon_id'] == row['species_id']:
            status = 'resolved_default'
        else:
            status = 'resolved_variant'
        return {'species_id': row['species_id'], 'pokemon_id': row['pokemon_id'],
                'form_id': form_id if multiple else None,
                'canonical_identity': (f'pokeapi:form:{form_id}' if multiple
                                       else f"pokeapi:pokemon:{row['pokemon_id']}"),
                'identity_status': status}

    def for_species(self, species_id):
        rows = self.applicable_forms(species_id)
        if len(rows) == 1:
            return self.for_form(rows[0].get('source_form_id', rows[0]['form_id']))
        return {'species_id': species_id, 'pokemon_id': None, 'form_id': None,
                'canonical_identity': None, 'identity_status': 'species_only'}

    def for_entity(self, entity):
        if entity is None or entity.kind != 'species':
            return self.unresolved()
        return (self.for_form(entity.form_id) if entity.form_id is not None
                else self.for_species(entity.species_id))

    def for_key(self, key):
        if not isinstance(key, str):
            return self.unresolved()
        parts = key.split(':')
        if len(parts) != 3 or parts[0] != 'pokeapi' or not parts[2].isdigit():
            return self.unresolved()
        kind, number = parts[1], int(parts[2])
        if kind == 'form':
            return self.for_form(number)
        if kind == 'species':
            return self.for_species(number)
        if kind == 'pokemon':
            rows = self.by_pokemon.get(number, [])
            return (self.for_form(rows[0].get('source_form_id', rows[0]['form_id']))
                    if len(rows) == 1 else self.unresolved())
        return self.unresolved()

    @staticmethod
    def unresolved():
        return {'species_id': None, 'pokemon_id': None, 'form_id': None,
                'canonical_identity': None, 'identity_status': 'unresolved'}


def enrich_snapshots(identity_payload, visual_payload):
    """Add v2 keys while preserving the source PokeAPI form row IDs."""
    index = IdentityIndex(identity_payload)
    for form in identity_payload['forms']:
        source_form = form.get('source_form_id', form['form_id'])
        form['source_form_id'] = source_form
        form.update(index.for_form(source_form))
    for species in identity_payload['species']:
        mapped = index.for_species(species['species_id'])
        species.update({k: mapped[k] for k in ('pokemon_id','form_id','canonical_identity','identity_status')})
    for asset in visual_payload['assets']:
        source_form = asset.get('source_form_id', asset.get('form_id'))
        asset['source_form_id'] = source_form
        mapped = index.for_form(source_form) if source_form is not None else index.unresolved()
        asset.update({k: mapped[k] for k in ('pokemon_id','form_id','canonical_identity','identity_status')})
    identity_payload['schema_version'] = 2
    identity_payload['version'] = '2026-10-13-identity.2'
    visual_payload['schema_version'] = 2
    return identity_payload, visual_payload
