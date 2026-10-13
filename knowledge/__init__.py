"""Offline, versioned entity names. Recognition never fetches network data."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any
import unicodedata
from .roster import ChampionsRoster


def normalize(text: str) -> str:
    """Ignore formatting, not characters: no species-specific substitutions."""
    return ''.join(c for c in unicodedata.normalize('NFKC',text).casefold() if c.isalnum())


@dataclass(frozen=True)
class Entity:
    canonical_id: str
    kind: str
    names: dict[str,str]
    aliases: tuple[str,...]
    species_id: int | None
    form_id: int | None
    name_source: str
    champions_entries: tuple[dict[str,Any],...]

    def label(self, chinese: bool) -> str:
        return self.names.get('zh-hans' if chinese else 'en') or self.names.get('en') or self.canonical_id


class KnowledgeBase:
    def __init__(self, directory: Path | None = None, *, game_version: str | None = None, regulation: str | None = None):
        directory = directory or Path(__file__).parent/'data'
        self.manifest = json.loads((directory/'manifest.json').read_text())
        raw = (directory/'entities.json').read_bytes()
        if hashlib.sha256(raw).hexdigest() != self.manifest['files']['entities.json']:
            raise ValueError('Knowledge snapshot checksum does not match manifest')
        data = json.loads(raw)
        if data.get('schema_version') != 1:
            raise ValueError('Unsupported knowledge snapshot schema')
        self.entities = {r['canonical_id']:Entity(r['canonical_id'],r['kind'],r['names'],
            tuple(r['aliases']),r['species_id'],r['form_id'],r['name_source'],tuple(r['champions_entries']))
            for r in data['entities']}
        self.by_kind: dict[str,list[Entity]] = {k:[] for k in ['species','move','ability','item']}
        self.exact: dict[str,dict[str,list[Entity]]] = {k:{} for k in self.by_kind}
        for e in self.entities.values():
            self.by_kind[e.kind].append(e)
            for name in set(e.names.values()) | set(e.aliases):
                norm = normalize(name)
                if e.form_id is not None:
                    base = self.entities.get(f'pokeapi:species:{e.species_id}')
                    if base and norm in {normalize(n) for n in base.names.values()}:
                        # Punctuation-only form labels (e.g. ??? Arceus) must
                        # not compete with an unqualified species name.
                        continue
                if norm:
                    self.exact[e.kind].setdefault(norm,[]).append(e)
        self.roster = ChampionsRoster(directory, self.manifest, self.entities)
        self.game_version = game_version
        self.regulation = regulation if regulation is not None else self.manifest.get('default_regulation')
        self.facts = {}
        facts_path = directory/'champions_facts.json'
        if facts_path.exists():
            facts_raw = facts_path.read_bytes()
            if hashlib.sha256(facts_raw).hexdigest() != self.manifest['files'].get('champions_facts.json'):
                raise ValueError('Champions facts checksum does not match manifest')
            self.facts = json.loads(facts_raw)
        self.identity = {}
        identity_path = directory/'identity.json'
        if identity_path.exists():
            identity_raw = identity_path.read_bytes()
            if hashlib.sha256(identity_raw).hexdigest() != self.manifest['files'].get('identity.json'):
                raise ValueError('Identity snapshot checksum does not match manifest')
            self.identity = json.loads(identity_raw)
        self.radicals = data['radicals']
        self.relationships = data['relationships']
        self.version = self.manifest['champions']['metadata']['version']
        self.snapshot_id = self.manifest['files']['entities.json']

    def availability(self, canonical_id):
        entity = self.entities.get(canonical_id)
        if entity and entity.kind != 'species':
            table = {'move':'moves', 'ability':'abilities', 'item':'items'}[entity.kind]
            present = canonical_id in self.facts.get(table, {}) and self.game_version is None
            return {'status':'confirmed_available' if present else 'unknown',
                    'source':self.facts.get('source') if present else None,
                    'regulation':self.regulation, 'legality':'unknown',
                    'reason':'community_catalog_assertion' if present else 'no_explicit_availability_evidence'}
        return self.roster.availability(canonical_id, game_version=self.game_version, regulation=self.regulation)
