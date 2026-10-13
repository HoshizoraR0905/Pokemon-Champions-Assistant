"""Observed recognition context, separate from explicitly verified team records."""
from dataclasses import dataclass, field
import json
from pathlib import Path
from knowledge import KnowledgeBase, normalize
from models import Observation, Recognition
from recognition.entities import EntityContext


@dataclass
class TeamMember:
    instance_id: str
    species_id: str
    fields: dict[str,str] = field(default_factory=dict)
    source: str = ''


class RecognitionContext:
    def __init__(self, knowledge: KnowledgeBase | None = None):
        self.knowledge = knowledge
        self.verified_team: dict[str,TeamMember] = {}
        self.observed_team: dict[str,TeamMember] = {}
        self.opponent_preview: set[str] = set()
        self.previous: dict[str,tuple[str,str,int]] = {}
        self.complete_verified_roster = False
        self.last_source: str | None = None
        self.last_index: int | None = None

    def load_verified(self, path: Path, knowledge: KnowledgeBase) -> None:
        """Explicit user-provided records; an upstream 'verified' flag is not enough."""
        payload = json.loads(path.read_text())
        if payload.get('schema_version') != 1 or not isinstance(payload.get('members'),list):
            raise ValueError('Verified team requires schema_version=1 and a members list')
        members = {}
        for row in payload['members']:
            if not isinstance(row,dict) or not isinstance(row.get('instance_id'),str) or not isinstance(row.get('species_id'),str) or not isinstance(row.get('fields',{}),dict):
                raise ValueError('Each verified member requires string instance_id/species_id and fields object')
            member = TeamMember(row['instance_id'],row['species_id'],row.get('fields',{}),row.get('source',''))
            if not member.source or not member.instance_id or member.instance_id in members:
                raise ValueError('Verified members require unique instance IDs and evidence sources')
            entity = knowledge.entities.get(member.species_id)
            if entity is None or entity.kind != 'species':
                raise ValueError(f'Unknown verified species/form ID: {member.species_id}')
            for field_name, canonical in member.fields.items():
                kind = 'move' if field_name.startswith('move_') else {'ability':'ability','held_item':'item'}.get(field_name)
                target = knowledge.entities.get(canonical)
                if kind is None or target is None or target.kind != kind:
                    raise ValueError(f'Invalid verified field {field_name}: {canonical}')
            members[member.instance_id] = member
        self.verified_team = members
        self.knowledge = knowledge
        self.complete_verified_roster = bool(payload.get('complete_roster',False))

    def begin_frame(self, source: str, index: int) -> None:
        # Discontinuous file inputs must not masquerade as consecutive video evidence.
        if self.last_source != source or (self.last_index is not None and index <= self.last_index):
            self.previous.clear()
        self.last_source, self.last_index = source,index

    def for_field(self, slot: str, kind: str, field_name: str = 'species') -> EntityContext:
        key = f'{slot}:{field_name}'
        prior = self.previous.get(key)
        verified = self.verified_team.get(slot)
        roster = list(self.observed_team.values()) if slot.startswith('own') else []
        verified_roster = list(self.verified_team.values()) if slot.startswith('own') else []
        ctx = EntityContext(source='recognition_context',previous_id=prior[0] if prior else None,
                            repeat_count=prior[2] if prior else 0)
        if verified:
            ctx.source += f'+explicit_verification:{verified.source}'
        if kind=='species':
            ctx.preferred_ids = {m.species_id for m in roster}
            ctx.verified_preferred_ids = {m.species_id for m in verified_roster}
            if slot.startswith('opponent'):
                ctx.preferred_ids |= self.opponent_preview
            if verified:
                ctx.verified_id = verified.species_id
            if slot.startswith('own') and self.complete_verified_roster:
                ctx.allowed_ids = ctx.verified_preferred_ids.copy()
                # A verified form also supports a bare species name, without asserting form.
                if self.knowledge:
                    ctx.allowed_ids |= {f'pokeapi:species:{self.knowledge.entities[i].species_id}'
                                        for i in ctx.verified_preferred_ids}
        else:
            ctx.preferred_ids = {v for m in roster for k,v in m.fields.items()
                                 if k==field_name or (kind=='move' and k.startswith('move_'))}
            ctx.verified_preferred_ids = {v for m in verified_roster for k,v in m.fields.items()
                                 if k==field_name or (kind=='move' and k.startswith('move_'))}
            if verified:
                ctx.verified_id = verified.fields.get(field_name)
        return ctx

    def remember(self, result: Recognition) -> None:
        observed_keys = set()
        def save(slot: str, field_name: str, obs: Observation):
            resolution = obs.resolution
            key = f'{slot}:{field_name}'
            if resolution is None or resolution.status != 'resolved':
                return
            observed_keys.add(key)
            canonical = resolution.canonical_id
            raw = normalize(obs.raw_ocr.text if obs.raw_ocr else obs.raw_text)
            previous = self.previous.get(key)
            repeats = previous[2]+1 if previous and previous[:2]==(canonical,raw) and resolution.method=='exact' else 1
            self.previous[key] = (canonical,raw,repeats)
        for pokemon in result.pokemon:
            save(pokemon.slot,'species',pokemon.species)
            for k,v in pokemon.configuration.items():
                save(pokemon.slot,k,v)
            identification = pokemon.species.resolution
            if identification and identification.status=='resolved':
                if pokemon.slot.startswith('own_team_'):
                    fields = {k:v.resolution.canonical_id for k,v in pokemon.configuration.items()
                              if v.resolution and v.resolution.status=='resolved'}
                    previous = self.observed_team.get(pokemon.slot)
                    if previous and previous.species_id==identification.canonical_id:
                        fields = previous.fields | fields
                    self.observed_team[pokemon.slot] = TeamMember(pokemon.slot,identification.canonical_id,fields,'visible_ocr')
                elif pokemon.slot.startswith('opponent_team_'):
                    self.opponent_preview.add(identification.canonical_id)
        for move in result.moves:
            save('own_move_menu',f'move_{move.slot}',move.name)
        self.previous = {k:v for k,v in self.previous.items() if k in observed_keys}
