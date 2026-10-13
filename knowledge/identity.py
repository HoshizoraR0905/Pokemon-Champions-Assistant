"""Canonical Pokémon variant identity from pinned PokéAPI form rows."""
from collections import defaultdict


class IdentityIndex:
    def __init__(self, payload):
        self.forms = {r.get('source_form_id', r['form_id']): r for r in payload.get('forms', [])}
        self.by_species = defaultdict(list)
        self.by_pokemon = defaultdict(list)
        for row in self.forms.values():
            self.by_species[row['species_id']].append(row)
            self.by_pokemon[row['pokemon_id']].append(row)

    def for_form(self, form_id):
        row = self.forms.get(form_id)
        if row is None:
            return self.unresolved()
        multiple = len(self.by_pokemon[row['pokemon_id']]) > 1
        if multiple:
            status = 'resolved_form'
        elif len(self.by_species[row['species_id']]) == 1:
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
        rows = self.by_species.get(species_id, [])
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
