"""Champions availability assertions, separate from canonical name dictionaries."""
import hashlib
import json
from pathlib import Path

STATUSES = {'confirmed_available', 'confirmed_unavailable', 'unknown'}


def build_roster(entities, provenance, unmapped):
    """Import positive community roster assertions without inventing negative ones."""
    source = {k: provenance[k] for k in ('repository', 'commit', 'commit_date')}
    source.update(path='pokemon/roster.json', dataset_version=provenance['metadata']['version'])
    return {'schema_version': 1, 'default_scope': 'upstream-unversioned', 'snapshots': [{
        'scope_id': 'upstream-unversioned', 'game_version': None,
        'dataset_version': provenance['metadata']['version'],
        'as_of': provenance['metadata']['lastUpdated'], 'completeness': 'unverified',
        'authoritative': False, 'source': source,
        'unmapped_entries': [r for r in unmapped if r['kind'] == 'species'],
        'entries': [{'canonical_id': e['canonical_id'],
                     'status': 'confirmed_available', 'source': source,
                     'evidence_type': 'community_roster_assertion',
                     'independently_verified': False}
                    for e in entities if e['kind'] == 'species' and e['champions_entries']],
        'regulations': []}]}


class ChampionsRoster:
    def __init__(self, directory: Path, manifest, entities):
        raw = (directory/'champions_roster.json').read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest['files']['champions_roster.json']:
            raise ValueError('Champions roster checksum does not match manifest')
        self.data = json.loads(raw)
        if self.data['schema_version'] != 1:
            raise ValueError('Unsupported roster schema')
        for snapshot in self.data['snapshots']:
            ids = set()
            for entry in snapshot['entries']:
                if entry['canonical_id'] not in entities or entities[entry['canonical_id']].kind != 'species':
                    raise ValueError('Invalid canonical roster ID')
                if entry['status'] not in STATUSES or not entry.get('source'):
                    raise ValueError('Invalid roster availability assertion')
                if entry['canonical_id'] in ids:
                    raise ValueError('Duplicate roster assertion')
                ids.add(entry['canonical_id'])
            for regulation in snapshot['regulations']:
                for entry in regulation['entries']:
                    if entry['canonical_id'] not in entities or entry['status'] not in {'legal','illegal','unknown'} or not entry.get('source'):
                        raise ValueError('Invalid regulation assertion')

    def availability(self, canonical_id, *, game_version=None, regulation=None):
        snapshots = [s for s in self.data['snapshots'] if
                     (s['game_version'] == game_version if game_version is not None
                      else s['scope_id'] == self.data['default_scope'])]
        result = {'status': 'unknown', 'game_version': game_version,
                  'regulation': regulation, 'legality': 'unknown', 'source': None,
                  'reason': 'no_matching_game_version'}
        if not snapshots:
            return result
        if len(snapshots) != 1:
            raise ValueError('Ambiguous roster game version')
        snapshot = snapshots[0]
        result.update(scope_id=snapshot['scope_id'], source=snapshot['source'],
                      reason='no_explicit_availability_evidence')
        entry = next((e for e in snapshot['entries'] if e['canonical_id'] == canonical_id), None)
        if entry:
            result.update(entry)
            result['reason'] = 'explicit_source_assertion'
        if regulation is not None:
            for rules in snapshot['regulations']:
                if rules['regulation_id'] == regulation:
                    rule = next((e for e in rules['entries'] if e['canonical_id'] == canonical_id), None)
                    if rule:
                        result.update(legality=rule['status'], legality_source=rule['source'])
        return result
