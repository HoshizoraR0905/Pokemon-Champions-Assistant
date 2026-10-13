"""Persistent, evidence-preserving own-team configuration observations."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re

from knowledge import KnowledgeBase


STATS = ('hp', 'attack', 'defense', 'special_attack', 'special_defense', 'speed')
MOVES = tuple(f'move_{i}' for i in range(1, 5))
REQUIRED = ('species', 'form', 'ability', 'held_item', *MOVES, *STATS)
OPTIONAL = ('level', 'gender', 'nature', 'evs', 'ivs')
FIELDS = (*REQUIRED, *OPTIONAL, *(f'allocation_{s}_display' for s in STATS))
KINDS = {'species': 'species', 'form': 'species', 'ability': 'ability', 'held_item': 'item',
         **{m: 'move' for m in MOVES}}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _field() -> dict:
    return {'value': None, 'canonical_id': None, 'status': 'unknown', 'confidence': 0.0,
            'observations': [], 'conflicts': []}


def _member(slot: int) -> dict:
    return {'instance_id': f'own_team_{slot}', 'slot': slot,
            'fields': {name: _field() for name in FIELDS}, 'missing_fields': list(REQUIRED),
            'conflicting_fields': []}


def _source(result, cache: dict[str, str | None]) -> dict:
    path = Path(result.source)
    if result.source not in cache:
        if path.is_file():
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            cache[result.source] = digest.hexdigest()
        else:
            cache[result.source] = None
    sha = cache[result.source]
    return {'path': result.source, 'sha256': sha, 'frame_index': result.frame_index,
            'video_second': result.timestamp, 'screen': result.screen,
            'page': next((c for c in result.components if c.startswith('configuration_')), None),
            'processed_at_utc': _now()}


class TeamConfiguration:
    def __init__(self, knowledge: KnowledgeBase | None = None, *, team_id='my_team', data=None):
        self.knowledge = knowledge or KnowledgeBase()
        self.data = data if data is not None else {
            'schema_version': 1, 'team_id': team_id, 'created_at_utc': _now(),
            'knowledge_snapshot_sha256': self.knowledge.snapshot_id,
            'regulation': self.knowledge.regulation, 'sources': [],
            'members': [_member(i) for i in range(1, 7)], 'complete': False,
            'missing_fields': {}, 'conflicts': {}}
        if self.data.get('schema_version') != 1 or len(self.data.get('members', [])) != 6:
            raise ValueError('Unsupported team configuration schema')
        self._source_hashes: dict[str, str | None] = {}
        self._report()

    @classmethod
    def load(cls, path: str | Path, knowledge: KnowledgeBase | None = None):
        return cls(knowledge, data=json.loads(Path(path).read_text(encoding='utf-8')))

    def save(self, path: str | Path):
        self._report()
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        temp = dest.with_suffix(dest.suffix + '.tmp')
        temp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temp.replace(dest)

    def _candidate(self, obs, source_id: int) -> dict | None:
        if obs is None or (obs.value is None and not obs.raw_text and not obs.resolution):
            return None
        resolution = obs.resolution
        candidate_id = resolution.canonical_id if resolution and resolution.status == 'resolved' else None
        status = 'knowledge_resolved' if candidate_id else 'observed' if obs.value is not None else 'unknown'
        if resolution and resolution.status in ('conflict', 'unresolved'):
            status = 'ambiguous' if resolution.candidates else 'unknown'
        if resolution and resolution.method in ('fuzzy', 'context_fuzzy'):
            status = 'ambiguous'
        return {'value': obs.value if status not in ('ambiguous', 'unknown') else None,
                'canonical_id': candidate_id if status != 'ambiguous' else None,
                'status': status, 'confidence': obs.confidence,
                'evidence': {'source_id': source_id, 'raw_text': obs.raw_text,
                             'region': obs.region, 'confidence': obs.confidence,
                             'ocr_engine': obs.raw_ocr.engine if obs.raw_ocr else None,
                             'provenance': obs.provenance,
                             'resolution_method': resolution.method if resolution else None,
                             'candidate_ids': [c.canonical_id for c in resolution.candidates[:3]] if resolution else []}}

    def _put(self, member: dict, name: str, candidate: dict | None):
        if candidate is None:
            return
        field = member['fields'][name]
        evidence = candidate['evidence']
        if evidence not in field['observations']:
            field['observations'].append(evidence)
        if candidate['status'] in ('unknown', 'ambiguous'):
            if candidate['status'] == 'ambiguous' and field['status'] == 'unknown':
                field['status'] = 'ambiguous'
            return
        new_key = candidate['canonical_id'] or candidate['value']
        old_key = field['canonical_id'] or field['value']
        if field['status'] == 'unknown' or (field['status'] == 'ambiguous' and old_key is None):
            field.update({k: candidate[k] for k in ('value', 'canonical_id', 'status', 'confidence')})
        elif old_key != new_key:
            conflict = {'value': candidate['value'], 'canonical_id': candidate['canonical_id'],
                        'status': candidate['status'], 'evidence': evidence, 'resolved': False}
            if conflict not in field['conflicts']:
                field['conflicts'].append(conflict)
            field['status'] = 'conflicting' if field['status'] != 'manual_verified' else 'manual_verified'
        elif field['status'] not in ('manual_verified', 'conflicting'):
            field['confidence'] = max(field['confidence'], candidate['confidence'])

    def ingest(self, result) -> bool:
        if result.screen != 'team_configuration':
            return False
        source = _source(result, self._source_hashes)
        key = (source['path'], source['sha256'], source['frame_index'], source['page'])
        for existing in self.data['sources']:
            if (existing['path'], existing['sha256'], existing['frame_index'], existing['page']) == key:
                return False
        source_id = len(self.data['sources'])
        self.data['sources'].append(source)
        for pokemon in result.pokemon:
            match = re.fullmatch(r'own_team_([1-6])', pokemon.slot)
            if not match:
                continue
            member = self.data['members'][int(match.group(1))-1]
            species = self._candidate(pokemon.species, source_id)
            identified = self.knowledge.entities.get(species['canonical_id']) if species else None
            if identified and identified.form_id is not None:
                form = dict(species)
                form['value'] = identified.form_id
                species = dict(species)
                base_id = f'pokeapi:species:{identified.species_id}'
                base = self.knowledge.entities.get(base_id)
                species['canonical_id'] = base_id
                species['value'] = base.label(True) if base else pokemon.species.value
            old_species = member['fields']['species']['canonical_id']
            new_species = species['canonical_id'] if species else None
            if old_species and new_species and old_species != new_species:
                self._put(member, 'species', species)
                continue  # Team order may have changed; never attach this card's fields.
            self._put(member, 'species', species)
            if identified and identified.form_id is not None:
                old_form = member['fields']['form']['canonical_id']
                if (old_form and old_form != form['canonical_id']) or (
                    member['fields']['form']['status'] == 'manual_verified' and old_form is None):
                    self._put(member, 'form', form)
                    continue  # A different visible form can indicate a different instance.
                self._put(member, 'form', form)
            for name, obs in pokemon.configuration.items():
                if name in member['fields'] and name != 'form':
                    self._put(member, name, self._candidate(obs, source_id))
        self._report()
        return True

    def correct(self, instance_id: str, field_name: str, *, value=None, canonical_id=None,
                reviewer: str, note: str = ''):
        if not reviewer.strip():
            raise ValueError('A reviewer name is required')
        if field_name not in FIELDS:
            raise ValueError(f'Unknown team field: {field_name}')
        members = {m['instance_id']: m for m in self.data['members']}
        if instance_id not in members:
            raise ValueError(f'Unknown team instance: {instance_id}')
        kind = KINDS.get(field_name)
        if field_name == 'form' and canonical_id is None and value == 'base':
            # Explicit manual review can confirm an unnumbered base form.
            # Keep the canonical form ID null rather than inventing one.
            value = None
        elif kind:
            entity = self.knowledge.entities.get(canonical_id)
            if not entity or entity.kind != kind:
                raise ValueError(f'{field_name} requires a known {kind} canonical_id')
            if field_name == 'species' and entity.form_id is not None:
                raise ValueError('Use a species ID for species and a separate form ID for form')
            if field_name == 'form' and entity.form_id is None:
                raise ValueError('Use an explicit form ID, or leave form unknown')
            if field_name == 'form':
                species = members[instance_id]['species_id']
                if species is not None and entity.species_id != species:
                    raise ValueError('Form belongs to a different species')
            value = entity.form_id if field_name == 'form' else entity.label(True)
        elif canonical_id is not None:
            raise ValueError(f'{field_name} does not accept canonical_id')
        elif field_name in STATS or field_name == 'level':
            if type(value) is not int or value <= 0:
                raise ValueError(f'{field_name} requires a positive integer')
        elif field_name == 'gender' and value not in ('male', 'female', 'genderless'):
            raise ValueError('gender must be male, female, or genderless')
        elif value is None:
            raise ValueError('Correction value is required')
        field = members[instance_id]['fields'][field_name]
        for conflict in field['conflicts']:
            conflict['resolved'] = True
            conflict['resolved_by'] = reviewer
            conflict['resolved_at_utc'] = _now()
        old_key = field['canonical_id'] or field['value']
        new_key = canonical_id or value
        if old_key is not None and old_key != new_key:
            conflict = {'value': field['value'], 'canonical_id': field['canonical_id'],
                        'status': field['status'], 'evidence': {'manual_override': True},
                        'resolved': True, 'resolved_by': reviewer, 'resolved_at_utc': _now()}
            if conflict not in field['conflicts']:
                field['conflicts'].append(conflict)
        field.update(value=value, canonical_id=canonical_id, status='manual_verified', confidence=1.0)
        field['observations'].append({'reviewer': reviewer, 'note': note,
                                      'verified_at_utc': _now(), 'method': 'manual_review'})
        self._report()

    def _report(self):
        missing, conflicts = {}, {}
        for member in self.data['members']:
            fields = member['fields']
            member['missing_fields'] = [name for name in REQUIRED
                                        if fields[name]['status'] != 'manual_verified']
            member['conflicting_fields'] = [name for name, f in fields.items()
                                            if any(not c.get('resolved',False) for c in f['conflicts'])]
            sid = fields['species']['canonical_id']
            entity = self.knowledge.entities.get(sid)
            member['species_id'] = entity.species_id if entity else None
            member['form_id'] = fields['form']['value']
            member['names'] = {'zh-hans': entity.names.get('zh-hans') if entity else None,
                               'en': entity.names.get('en') if entity else None}
            missing[member['instance_id']] = member['missing_fields']
            if member['conflicting_fields']:
                conflicts[member['instance_id']] = member['conflicting_fields']
        self.data['missing_fields'] = missing
        self.data['conflicts'] = conflicts
        self.data['complete'] = not any(missing.values()) and not conflicts
        self.data['updated_at_utc'] = _now()

    def summary(self) -> str:
        lines = [f"Team {self.data['team_id']} · {'complete' if self.data['complete'] else 'needs verification'}"]
        for member in self.data['members']:
            name = member['names']['zh-hans'] or 'unresolved'
            fields = member['fields']
            observed = sum(fields[f]['value'] is not None for f in REQUIRED)
            verified = len(REQUIRED) - len(member['missing_fields'])
            unobserved = [f for f in REQUIRED if fields[f]['value'] is None]
            ambiguous = [f for f in REQUIRED if fields[f]['status'] == 'ambiguous']
            lines.append(f"  {member['slot']}. {name}: {observed}/{len(REQUIRED)} observed, "
                         f"{verified}/{len(REQUIRED)} verified" +
                         (f" · unobserved: {', '.join(unobserved)}" if unobserved else '') +
                         (f" · ambiguous: {', '.join(ambiguous)}" if ambiguous else '') +
                         (f" · conflicts: {', '.join(member['conflicting_fields'])}" if member['conflicting_fields'] else ''))
        return '\n'.join(lines)
