"""Resumable nine-species current Ranked pilot through documented endpoints."""
import json
import math
from pathlib import Path
import time
import uuid
from . import PARSER_VERSION, PILOT
from .common import atomic_json, now, sha
from .fetch import Fetcher
from .identity import Names
from .parser import parse_index, parse_battle
from .sources import SOURCE, source_url
from .store import Store, locked, prepare_root


def normalizer_identity(names):
    root = Path(__file__).resolve().parents[1]
    paths = ['metagame/parser.py', 'metagame/identity.py', 'metagame/sources.py',
             'knowledge/champions_stats.py', 'knowledge/identity.py',
             'knowledge/data/champions_stat_rules.json']
    identity = dict(parser_version=PARSER_VERSION, sources={p:sha((root/p).read_bytes()) for p in paths},
        knowledge_files={k:v for k,v in names.knowledge.manifest['files'].items()
            if k in ('entities.json','identity.json','identity_scopes.json')})
    return dict(identity, fingerprint=sha(json.dumps(identity,sort_keys=True).encode()))


def matching_entry(entries, name, names):
    if name in entries:
        return entries[name]
    query = names.resolve(name)
    if query['canonical_id'] is None:
        raise ValueError('Unresolved requested species/form: '+name)
    matches = [e for e in entries.values()
               if names.resolve(e['showdownName'])['canonical_id'] == query['canonical_id']]
    if len(matches) != 1:
        raise ValueError('Source index species/form is absent or ambiguous: '+name)
    return matches[0]


def load_receipt(receipt):
    raw = Path(receipt['raw_path']).read_bytes()
    if sha(raw) != receipt['raw_sha256']:
        raise ValueError('Raw snapshot checksum mismatch')
    return json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Non-finite JSON '+x)))


def ingest(root, *, species=PILOT, battle_format='Doubles', refresh_seconds=86400.,
           interval=2., retention_days=7., max_versions=2, force=False, fetcher=None, names=None):
    if (not math.isfinite(retention_days) or retention_days <= 0 or
            not math.isfinite(refresh_seconds) or refresh_seconds < 0 or
            refresh_seconds > retention_days*86400 or type(max_versions) is not int or not 1 <= max_versions <= 3):
        raise ValueError('Refresh interval must be within retention window')
    root = prepare_root(root)
    with locked(root):
        store = Store(root)
        names = names or Names()
        normalization = normalizer_identity(names)
        fetcher = fetcher or Fetcher(root, interval=interval)
        manifest_path = root/'runs'/(time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())+'-'+uuid.uuid4().hex[:8]+'.json')
        manifest = dict(schema_version=1, parser_version=PARSER_VERSION, status='running',
            started_at=now(), format=battle_format, source=SOURCE, requested_species=list(species),
            refresh_seconds=refresh_seconds, retention_days=retention_days, max_versions=max_versions,
            completed=[], errors=[], outputs=dict(database=str(root/'statistics.sqlite3')))
        atomic_json(manifest_path, manifest)
        started = time.monotonic()
        try:
            index_receipt = fetcher.get(source_url(), refresh_seconds=refresh_seconds, force=force)
            index_data = load_receipt(index_receipt)
            entries = parse_index(index_data)
            index_metadata = dict(season='Current', regulation=None, game_version=None,
                battle_format=battle_format, source_updated_at=None,
                index_generated_at=index_data['generatedAt'], index_data_version=index_data.get('dataVersion'),
                retrieved_at=index_receipt['retrieved_at'], sample_count=None,
                denominator_definition='not published', rating_bracket=None,
                eligibility_filter=None, weighting=None, source_type=SOURCE['population'],
                normalization=normalization)
            index_sid = store.save(index_receipt, index_metadata, names.knowledge.snapshot_id)
            manifest.update(index_snapshot=index_sid, indexed_species=len(entries),
                supported_format_species=sum(any(s.get('season')=='Current' and s.get('format')==battle_format
                    for s in e['battleDataCsvs']) for e in entries.values()))
            atomic_json(manifest_path, manifest)
            for name in species:
                try:
                    entry = matching_entry(entries, name, names)
                    sid = entry['showdownId']
                    source_paths = [s['path'] for s in entry['battleDataCsvs']
                                    if s.get('season')=='Current' and s.get('format')==battle_format]
                    if len(source_paths) != 1:
                        raise ValueError('No unique current source file in requested format')
                    receipt = fetcher.get(source_url(sid, battle_format), refresh_seconds=refresh_seconds, force=force)
                    data = load_receipt(receipt)
                    if data.get('source') != source_paths[0]:
                        raise ValueError('Index and battle source path mismatch')
                    records, warnings = parse_battle(data, sid, battle_format)
                    for rec in records:
                        if rec['category'] in ('move','item','ability','teammate'):
                            rec['identity'] = names.resolve(rec['original_name'],
                                'species' if rec['category']=='teammate' else rec['category'])
                    # Compare independent index summary fields without changing either value.
                    top = entry.get('summary', {}).get('battleSummary', {}).get('Current', {}).get(battle_format, {}).get('top', {})
                    comparisons = []
                    for category, expected in top.items():
                        actual = [r for r in records if r['source_category']==category and r['rank']==1]
                        fields = ['name','percentage_value', 'hp_points','attack_points','defense_points','sp_atk_points','sp_def_points','speed_points'] if category=='stat_points' else ['name','percentage_value']
                        comparisons.append(dict(category=category, matches=bool(actual) and
                            all(expected.get(k)==actual[0]['raw'].get(k) for k in fields)))
                    metadata = dict(index_metadata, index_snapshot=index_sid,
                        retrieved_at=receipt['retrieved_at'], source_url=receipt['url'],
                        source_file=data['source'], source_date=data.get('date'),
                        source_original_name=data['pokemon'], publication_timestamp=None,
                        warnings=warnings, index_summary_comparisons=comparisons,
                        source_season=data['season'], supported_population='current Ranked data as claimed by provider',
                        source_format=battle_format)
                    positions = {r['raw'].get('column_position') for r in records if r['raw'].get('column_position') is not None}
                    rank = next(iter(positions)) if len(positions)==1 else None
                    identity = names.resolve(entry['showdownName'])
                    identity['source_original_name'] = data['pokemon']
                    subject = dict(identity=identity, source_species=sid,
                                   source_name=entry['showdownName'], usage_rank=rank)
                    snapshot_id = store.save(receipt, metadata, names.knowledge.snapshot_id, subject=subject, records=records)
                    manifest['completed'].append(dict(requested_name=name, source_species=sid,
                        snapshot_id=snapshot_id, rows=len(records), warnings=warnings,
                        index_summary_matches=all(c['matches'] for c in comparisons)))
                    print(f'{len(manifest["completed"])}/{len(species)} {sid}: {len(records)} published rows cached', flush=True)
                except Exception as exc:
                    manifest['errors'].append(dict(species=name, error=str(exc)))
                    print(f'{name}: failed ({exc}); earlier species retained', flush=True)
                atomic_json(manifest_path, manifest)
            manifest['status'] = 'complete' if not manifest['errors'] else 'partial'
            if manifest['completed']:
                manifest['retention'] = store.prune(retention_days=retention_days, max_versions=max_versions)
        except Exception as exc:
            manifest.update(status='failed', error=str(exc))
        finally:
            manifest.update(finished_at=now(), elapsed_seconds=time.monotonic()-started,
                http_requests=fetcher.requests, fresh_cache_hits=fetcher.cache_hits)
            atomic_json(manifest_path, manifest)
            store.close()
        return manifest, manifest_path
