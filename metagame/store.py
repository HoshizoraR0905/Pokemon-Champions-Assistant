"""Versioned SQLite projection for a bounded current application cache."""
from contextlib import contextmanager
import fcntl
import json
import math
from pathlib import Path
import re
import sqlite3
import time
from . import PARSER_VERSION, SCHEMA_VERSION
from .common import atomic_json, encode, now, sha
from .sources import SOURCE, SOURCE_ID

DDL = '''
CREATE TABLE migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE sources(id TEXT PRIMARY KEY, metadata TEXT NOT NULL);
CREATE TABLE snapshots(
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
 url TEXT NOT NULL, raw_sha256 TEXT NOT NULL, raw_path TEXT NOT NULL,
 parser_version TEXT NOT NULL, knowledge_snapshot TEXT NOT NULL,
 checked_epoch REAL NOT NULL, checked_at TEXT NOT NULL, metadata TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('index','battle')));
CREATE INDEX snapshot_url ON snapshots(url, checked_epoch);
CREATE TABLE subjects(
 snapshot_id TEXT PRIMARY KEY REFERENCES snapshots(id) ON DELETE CASCADE,
 source_species TEXT NOT NULL, canonical_id TEXT, identity TEXT NOT NULL,
 source_name TEXT NOT NULL, usage_rank INTEGER);
CREATE INDEX subject_identity ON subjects(canonical_id);
CREATE TABLE metrics(
 snapshot_id TEXT NOT NULL REFERENCES subjects(snapshot_id) ON DELETE CASCADE,
 ordinal INTEGER NOT NULL, category TEXT NOT NULL,
 record TEXT NOT NULL, PRIMARY KEY(snapshot_id,ordinal));
CREATE INDEX metric_category ON metrics(snapshot_id,category);
'''


def prepare_root(root):
    root = Path(root).resolve()
    marker = root/'cache-owner.json'
    expected = dict(owner='Pokemon-Champions-Assistant-M3.3-current-cache', version=1)
    if marker.exists():
        if json.loads(marker.read_text()) != expected:
            raise ValueError('Cache ownership mismatch')
    else:
        if root.exists() and any(root.iterdir()):
            raise ValueError('Refusing to adopt a nonempty unowned cache directory')
        root.mkdir(parents=True, exist_ok=True)
        atomic_json(marker, expected)
    return root


@contextmanager
def locked(root):
    with (Path(root)/'writer.lock').open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Another ingestion writer is active for this cache') from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


class Store:
    def __init__(self, root, *, readonly=False):
        self.root = Path(root).resolve()
        path = self.root/'statistics.sqlite3'
        self.db = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) if readonly else sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        version = self.db.execute('PRAGMA user_version').fetchone()[0]
        if version > SCHEMA_VERSION:
            self.close()
            raise ValueError('Cache database has a newer schema version')
        if version == 0 and not readonly:
            # Initial migration. Future upgrades add ordered migrations, not drops.
            with self.db:
                self.db.executescript('BEGIN IMMEDIATE;\n'+DDL)
                self.db.execute('INSERT INTO migrations VALUES(?,?)', (1, now()))
                self.db.execute('PRAGMA user_version=1')
        elif version != SCHEMA_VERSION:
            self.close()
            raise ValueError('Cache migration required; run ingestion with supported code')
        if not readonly:
            self.db.execute('INSERT OR IGNORE INTO sources VALUES(?,?)', (SOURCE_ID, encode(SOURCE)))
            self.db.commit()

    def close(self):
        self.db.close()

    def save(self, receipt, metadata, knowledge, *, subject=None, records=()):
        sid = sha(encode([receipt['url'], receipt['raw_sha256'], PARSER_VERSION, knowledge,
                         metadata.get('normalization', {}).get('fingerprint')]).encode())
        raw_path = Path(receipt['raw_path']).resolve()
        if not raw_path.is_relative_to(self.root/'raw') or sha(raw_path.read_bytes()) != receipt['raw_sha256']:
            raise ValueError('Raw hash/ownership mismatch before database projection')
        with self.db:
            self.db.execute('''INSERT INTO snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET checked_epoch=excluded.checked_epoch,
                checked_at=excluded.checked_at,metadata=excluded.metadata''',
                (sid, SOURCE_ID, receipt['url'], receipt['raw_sha256'], str(raw_path),
                 PARSER_VERSION, knowledge, receipt['checked_epoch'], receipt['checked_at'],
                 encode(metadata), 'battle' if subject else 'index'))
            if subject:
                identity = subject['identity']
                self.db.execute('INSERT OR IGNORE INTO subjects VALUES(?,?,?,?,?,?)',
                    (sid, subject['source_species'], identity['canonical_id'], encode(identity),
                     subject['source_name'], subject['usage_rank']))
                self.db.executemany('INSERT OR IGNORE INTO metrics VALUES(?,?,?,?)',
                    [(sid, rec['ordinal'], rec['category'], encode(rec)) for rec in records])
        return sid

    def snapshots(self):
        return [dict(r) for r in self.db.execute('''SELECT s.id,s.source_id,s.checked_at,s.raw_sha256,
            t.source_species,t.source_name FROM snapshots s JOIN subjects t ON t.snapshot_id=s.id
            ORDER BY s.checked_epoch DESC''')]

    def prune(self, *, retention_days=7., max_versions=2, clock=time.time):
        if not math.isfinite(retention_days) or retention_days <= 0 or type(max_versions) is not int or not 1 <= max_versions <= 3:
            raise ValueError('Bounded retention requires positive days and 1..3 versions per URL')
        # Only this owned current-cache root is eligible. Never touch audit or battle caches.
        prepare_root(self.root)
        cutoff = clock()-retention_days*86400
        old, counts = [], {}
        for row in self.db.execute('SELECT id,url,checked_epoch FROM snapshots ORDER BY checked_epoch DESC,id'):
            counts[row['url']] = counts.get(row['url'], 0)+1
            if row['checked_epoch'] < cutoff or counts[row['url']] > max_versions:
                old.append(row['id'])
        with self.db:
            self.db.executemany('DELETE FROM snapshots WHERE id=?', [(sid,) for sid in old])
        keep = {r[0] for r in self.db.execute('SELECT raw_sha256 FROM snapshots')}
        for path in (self.root/'http').glob('*.json'):
            receipt = json.loads(path.read_text())
            if receipt['checked_epoch'] < cutoff:
                path.unlink()
            else:
                keep.add(receipt['raw_sha256'])
        removed = 0
        for path in (self.root/'raw').glob('*.bin'):
            if re.fullmatch('[0-9a-f]{64}', path.stem) and path.stem not in keep:
                path.unlink()
                removed += 1
        # Bounded manifests and error receipts; retain only this package's files.
        for folder in ('runs','http-errors'):
            paths = sorted((self.root/folder).glob('*.json'), key=lambda p:p.stat().st_mtime, reverse=True)
            for i, path in enumerate(paths):
                if i >= 20 or path.stat().st_mtime < cutoff:
                    path.unlink()
        # Reclaim deleted pages instead of growing an unbounded history in free pages.
        if old:
            self.db.execute('VACUUM')
        return dict(removed_snapshots=len(old), removed_raw_files=removed)
