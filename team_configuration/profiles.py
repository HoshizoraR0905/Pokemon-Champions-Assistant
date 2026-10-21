"""Local immutable build profiles around TeamConfiguration v2, never battle state.

Register only complete manually verified configurations. Retrieval returns an
independent TeamConfiguration for existing explicit instance-binding consumers.
A profile ID identifies a build, not a species roster.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from team_configuration import TeamConfiguration, REQUIRED, _field, _now


class TeamProfiles:
    def __init__(self, directory):
        self.directory = Path(directory)

    def _path(self, profile_id):
        if not isinstance(profile_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', profile_id):
            raise ValueError('Profile ID must use 1–80 letters, digits, underscores or hyphens')
        return self.directory / (profile_id + '.json')

    @staticmethod
    def _validate(team):
        if not team.data['complete']:
            raise ValueError('All six members and required fields must be manually verified without unresolved conflicts')
        validator = TeamConfiguration(team.knowledge)
        for i, member in enumerate(team.data['members'], 1):
            if member['instance_id'] != f'own_team_{i}' or member['slot'] != i:
                raise ValueError('Profiles require six distinct ordered configuration slots')
            for name in REQUIRED:
                field = member['fields'][name]
                if not any(o.get('method') == 'manual_review' and o.get('reviewer')
                           for o in field['observations']):
                    raise ValueError('Required fields need explicit manual review evidence')
                # Reuse the established canonical-ID and numeric validators;
                # a complete flag alone cannot certify malformed imported data.
                validator.correct(member['instance_id'], name, value=field['value'],
                                  canonical_id=field['canonical_id'], reviewer='profile-schema-validation')

    def register(self, profile_id, team, *, reviewer, label=''):
        path = self._path(profile_id)
        if not reviewer.strip():
            raise ValueError('A reviewer is required')
        clean = TeamConfiguration(team.knowledge, data=deepcopy(team.data))
        self._validate(clean)
        for member in clean.data['members']:
            for name, field in member['fields'].items():
                # Unverified optional fields remain unknown, never imported as facts.
                if field['status'] != 'manual_verified':
                    member['fields'][name] = _field()
        clean._report()
        data = clean.data
        encoded = json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
        payload = dict(schema_version=1, profile_id=profile_id, label=label or profile_id,
                       reviewer=reviewer, registered_at_utc=_now(),
                       configuration_sha256=hashlib.sha256(encoded).hexdigest(), configuration=data)
        self.directory.mkdir(parents=True, exist_ok=True)
        # Publish a complete record atomically without replacing an existing build.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.directory,
                                             suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(json.dumps(payload, ensure_ascii=False, indent=2)+'\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return path

    def load(self, profile_id):
        payload = json.loads(self._path(profile_id).read_text())
        encoded = json.dumps(payload['configuration'], sort_keys=True, ensure_ascii=False).encode()
        if (payload.get('schema_version') != 1 or payload['profile_id'] != profile_id or
                payload['configuration_sha256'] != hashlib.sha256(encoded).hexdigest()):
            raise ValueError('Profile identity or configuration hash mismatch')
        team = TeamConfiguration(data=deepcopy(payload['configuration']))
        self._validate(team)
        return team

    def list(self):
        if not self.directory.exists():
            return []
        result = []
        for path in sorted(self.directory.glob('*.json')):
            team = self.load(path.stem)
            result.append(dict(profile_id=path.stem, team_id=team.data['team_id'],
                               roster=[m['canonical_identity'] for m in team.data['members']]))
        return result
