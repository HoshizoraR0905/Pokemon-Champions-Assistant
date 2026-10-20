"""Append-only source evidence and independent canonical design entities."""
import json
from pathlib import Path
import sqlite3
from metagame.common import atomic_json,encode,sha,now
from . import SCHEMA_VERSION, VERSION

DDL='''
CREATE TABLE migrations(version INTEGER PRIMARY KEY,applied_at TEXT NOT NULL);
CREATE TABLE sources(id TEXT PRIMARY KEY,policy TEXT NOT NULL);
CREATE TABLE captures(id TEXT PRIMARY KEY,source_id TEXT REFERENCES sources(id),url TEXT NOT NULL,
 raw_sha256 TEXT NOT NULL,raw_path TEXT NOT NULL,retrieved_at TEXT NOT NULL,receipt TEXT NOT NULL);
CREATE TABLE publications(id TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES sources(id),
 source_key TEXT NOT NULL,source_url TEXT NOT NULL,population TEXT NOT NULL,regulation TEXT NOT NULL,
 format TEXT NOT NULL,title TEXT NOT NULL,original TEXT NOT NULL,record_sha256 TEXT NOT NULL,
 UNIQUE(source_id,source_key,record_sha256));
CREATE TABLE publication_captures(publication_id TEXT REFERENCES publications(id),capture_id TEXT REFERENCES captures(id),
 PRIMARY KEY(publication_id,capture_id));
CREATE TABLE algorithms(version TEXT PRIMARY KEY,definition_sha256 TEXT NOT NULL,definition TEXT NOT NULL);
CREATE TABLE compositions(id TEXT PRIMARY KEY,version TEXT NOT NULL REFERENCES algorithms(version),members TEXT NOT NULL);
CREATE TABLE exact_builds(id TEXT PRIMARY KEY,composition_id TEXT NOT NULL REFERENCES compositions(id),
 version TEXT NOT NULL REFERENCES algorithms(version),configuration TEXT NOT NULL);
CREATE TABLE pokemon_builds(id TEXT PRIMARY KEY,version TEXT NOT NULL REFERENCES algorithms(version),configuration TEXT NOT NULL);
CREATE TABLE team_members(build_id TEXT REFERENCES exact_builds(id),ordinal INTEGER NOT NULL,
 pokemon_build_id TEXT REFERENCES pokemon_builds(id),PRIMARY KEY(build_id,ordinal));
CREATE TABLE extractions(id TEXT PRIMARY KEY,publication_id TEXT NOT NULL REFERENCES publications(id),
 algorithm_version TEXT NOT NULL REFERENCES algorithms(version),adapter_version TEXT NOT NULL,
 status TEXT NOT NULL,composition_id TEXT REFERENCES compositions(id),build_id TEXT REFERENCES exact_builds(id),
 canonical TEXT NOT NULL,created_at TEXT NOT NULL,
 UNIQUE(publication_id,algorithm_version,adapter_version));
CREATE TABLE duplicate_candidates(left_extraction TEXT REFERENCES extractions(id),right_extraction TEXT REFERENCES extractions(id),
 reason TEXT NOT NULL,PRIMARY KEY(left_extraction,right_extraction));
CREATE INDEX publication_scope ON publications(population,regulation,format);
CREATE INDEX extraction_composition ON extractions(composition_id,algorithm_version);
'''


def prepare(root):
    root=Path(root).resolve();marker=root/'published-owner.json'
    expected=dict(owner='Pokemon-Champions-Assistant-published-designs',version=1)
    if marker.exists():
        if json.loads(marker.read_text())!=expected:raise ValueError('Published database owner mismatch')
    else:
        if root.exists() and any(root.iterdir()):raise ValueError('Refusing an unowned nonempty directory')
        root.mkdir(parents=True,exist_ok=True);atomic_json(marker,expected)
    return root


def algorithm_definition():
    root=Path(__file__).resolve().parents[2]
    paths=['published/canonical.py','published/natures.json']
    definition=dict(profile='six-core-build-fields; unordered species/form multiset and unordered move identities',
        code={p:sha((root/'metagame'/p).read_bytes()) for p in paths},
        stat_rule_sha256=sha((root/'knowledge/data/champions_stat_rules.json').read_bytes()))
    return definition,sha(encode(definition).encode())


def _compatible(a,b):
    """Known fields may agree: a candidate, never proof of exact equality."""
    def mon_match(x,y):
        x=x['normalized'];y=y['normalized']
        for k in ('species','item','ability','nature'):
            if x[k] is not None and y[k] is not None and x[k]!=y[k]:return False
        if x['sp']['kind']==y['sp']['kind']=='champions_sp':
            if any(u is not None and v is not None and u!=v for u,v in zip(x['sp']['values'],y['sp']['values'])):return False
        if x['moves'] and y['moves'] and None not in x['moves']+y['moves']:
            if len(x['moves'])==len(y['moves'])==4 and x['moves']!=y['moves']:return False
        for k in x['configuration'].keys() & y['configuration'].keys():
            if x['configuration'][k] is not None and y['configuration'][k] is not None and x['configuration'][k]!=y['configuration'][k]:return False
        return True
    def match(left,right):
        if not left:return not right
        return any(mon_match(left[0],m) and match(left[1:],right[:i]+right[i+1:]) for i,m in enumerate(right))
    return match(a['members'],b['members'])


class Teams:
    def __init__(self,root,readonly=False):
        self.root=Path(root).resolve();path=self.root/'teams.sqlite3'
        self.db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) if readonly else sqlite3.connect(path)
        self.db.row_factory=sqlite3.Row;self.db.execute('PRAGMA foreign_keys=ON')
        version=self.db.execute('PRAGMA user_version').fetchone()[0]
        if version==0 and not readonly:
            with self.db:
                self.db.executescript('BEGIN IMMEDIATE;'+DDL)
                self.db.execute('INSERT INTO migrations VALUES(?,?)',(1,now()))
                self.db.execute('PRAGMA user_version=1')
            version=1
        if version==1 and not readonly:
            with self.db:
                self.db.execute('''CREATE TABLE publication_supersessions(
                    publication_id TEXT PRIMARY KEY REFERENCES publications(id),
                    corrected_publication_id TEXT NOT NULL REFERENCES publications(id),
                    reason TEXT NOT NULL,created_at TEXT NOT NULL)''')
                self.db.execute('INSERT INTO migrations VALUES(?,?)',(2,now()))
                self.db.execute('PRAGMA user_version=2')
            version=2
        if version==2 and not readonly:
            from .observed import observation
            with self.db:
                self.db.execute('''CREATE TABLE observed_configurations(
                    extraction_id TEXT NOT NULL REFERENCES extractions(id), version TEXT NOT NULL,
                    signature TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(extraction_id,version))''')
                self.db.execute('CREATE INDEX observed_signature ON observed_configurations(signature,version)')
                for row in self.db.execute('SELECT id,canonical FROM extractions').fetchall():
                    o=observation(json.loads(row['canonical']))
                    self.db.execute('INSERT INTO observed_configurations VALUES(?,?,?,?)',
                        (row['id'],o['version'],o['signature'],encode(o['payload'])))
                self.db.execute('INSERT INTO migrations VALUES(?,?)',(3,now()))
                self.db.execute('PRAGMA user_version=3')
            version=3
        if version==3 and not readonly:
            from .observed import observation,definition_digest,VERSION as OBSERVED_VERSION
            with self.db:
                self.db.execute('CREATE TABLE observed_algorithms(version TEXT PRIMARY KEY,definition_sha256 TEXT NOT NULL)')
                for row in self.db.execute('''SELECT o.payload,e.canonical FROM observed_configurations o
                    JOIN extractions e ON e.id=o.extraction_id WHERE o.version=?''',(OBSERVED_VERSION,)).fetchall():
                    if row['payload']!=encode(observation(json.loads(row['canonical']))['payload']):
                        raise ValueError('Observed configuration implementation changed; increment observed version')
                self.db.execute('INSERT INTO observed_algorithms VALUES(?,?)',(OBSERVED_VERSION,definition_digest()))
                self.db.execute('INSERT INTO migrations VALUES(?,?)',(4,now()))
                self.db.execute('PRAGMA user_version=4')
            version=4
        if version!=SCHEMA_VERSION:
            self.close();raise ValueError('Unsupported published-team database schema version')
        from .observed import definition_digest,VERSION as OBSERVED_VERSION
        previous=self.db.execute('SELECT definition_sha256 FROM observed_algorithms WHERE version=?',(OBSERVED_VERSION,)).fetchone()
        if previous and previous[0]!=definition_digest():
            self.close();raise ValueError('Observed configuration implementation changed; increment observed version')
        if previous is None and not readonly:
            from .observed import observation
            with self.db:
                self.db.execute('INSERT INTO observed_algorithms VALUES(?,?)',(OBSERVED_VERSION,definition_digest()))
                for row in self.db.execute('SELECT id,canonical FROM extractions').fetchall():
                    o=observation(json.loads(row['canonical']))
                    self.db.execute('INSERT INTO observed_configurations VALUES(?,?,?,?)',
                        (row['id'],o['version'],o['signature'],encode(o['payload'])))

    def close(self):self.db.close()

    def capture(self,source,policy,receipt):
        path=Path(receipt['raw_path']).resolve()
        if not path.is_relative_to(self.root/'raw') or sha(path.read_bytes())!=receipt['raw_sha256']:
            raise ValueError('Capture raw hash or ownership mismatch')
        cid=sha(encode([source,receipt['url'],receipt['raw_sha256']]).encode())
        with self.db:
            # This is the adapter's current policy, not a publication. Prior
            # policies remain in the immutable run/capture provenance.
            self.db.execute('INSERT INTO sources VALUES(?,?) ON CONFLICT(id) DO UPDATE SET policy=excluded.policy',(source,encode(policy)))
            self.db.execute('INSERT OR IGNORE INTO captures VALUES(?,?,?,?,?,?,?)',
                (cid,source,receipt['url'],receipt['raw_sha256'],str(path),receipt['retrieved_at'],encode(receipt)))
        return cid

    def add(self,source,record,canonical,capture_id,adapter_version):
        from . import POPULATIONS
        if record['population'] not in POPULATIONS:raise ValueError('Not a published team population')
        capture=self.db.execute('SELECT source_id FROM captures WHERE id=?',(capture_id,)).fetchone()
        if capture is None or capture[0]!=source:raise ValueError('Publication/capture source mismatch')
        definition,digest=algorithm_definition();version=canonical['version']
        previous=self.db.execute('SELECT definition_sha256 FROM algorithms WHERE version=?',(version,)).fetchone()
        if previous and previous[0]!=digest:raise ValueError('Fingerprint implementation changed; increment algorithm version instead of replacing old identities')
        record_hash=sha(encode(record).encode());pid=sha(encode([source,record['source_key'],record_hash]).encode())
        eid=sha(encode([pid,version,adapter_version]).encode())
        existing=self.db.execute('SELECT canonical FROM extractions WHERE id=?',(eid,)).fetchone()
        if existing and existing[0]!=encode(canonical):
            raise ValueError('Existing extraction changed under the same version; retain it and increment the normalizer version')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO algorithms VALUES(?,?,?)',(version,digest,encode(definition)))
            self.db.execute('INSERT OR IGNORE INTO publications VALUES(?,?,?,?,?,?,?,?,?,?)',
                (pid,source,record['source_key'],record['source_url'],record['population'],record['regulation'],
                 record['format'],record['title'],encode(record),record_hash))
            self.db.execute('INSERT OR IGNORE INTO publication_captures VALUES(?,?)',(pid,capture_id))
            if source=='pokedaily' and record['format']=='Unknown':
                # Correct the initial pilot's unsupported format assignment.
                # Retain both records and an explicit append-only correction;
                # never erase the old raw export or a real changed build.
                for prior in self.db.execute("SELECT id,original FROM publications WHERE source_id=? AND source_key=? AND format='Doubles'",
                    (source,record['source_key'])).fetchall():
                    old=json.loads(prior['original'])
                    if old.get('metadata',{}).get('original_export')==record.get('metadata',{}).get('original_export'):
                        self.db.execute('INSERT OR IGNORE INTO publication_supersessions VALUES(?,?,?,?)',
                            (prior['id'],pid,'Format metadata correction: rental page does not explicitly state Doubles',now()))
            if canonical['composition_id']:
                self.db.execute('INSERT OR IGNORE INTO compositions VALUES(?,?,?)',
                    (canonical['composition_id'],version,encode(canonical['composition'])))
            if canonical['exact_build_id']:
                self.db.execute('INSERT OR IGNORE INTO exact_builds VALUES(?,?,?,?)',
                    (canonical['exact_build_id'],canonical['composition_id'],version,encode(canonical['exact_build'])))
                for i,mon in enumerate(sorted(canonical['members'],key=lambda m:encode(m['normalized']))):
                    self.db.execute('INSERT OR IGNORE INTO pokemon_builds VALUES(?,?,?)',
                        (mon['pokemon_build_id'],version,encode(mon['normalized'])))
                    self.db.execute('INSERT OR IGNORE INTO team_members VALUES(?,?,?)',
                        (canonical['exact_build_id'],i,mon['pokemon_build_id']))
            self.db.execute('INSERT OR IGNORE INTO extractions VALUES(?,?,?,?,?,?,?,?,?)',
                (eid,pid,version,adapter_version,canonical['status'],canonical['composition_id'],canonical['exact_build_id'],
                 encode(canonical),now()))
            from .observed import observation,definition_digest
            observed=observation(canonical)
            prior=self.db.execute('SELECT definition_sha256 FROM observed_algorithms WHERE version=?',(observed['version'],)).fetchone()
            if prior and prior[0]!=definition_digest():raise ValueError('Observed configuration implementation changed; increment observed version')
            self.db.execute('INSERT OR IGNORE INTO observed_algorithms VALUES(?,?)',(observed['version'],definition_digest()))
            self.db.execute('INSERT OR IGNORE INTO observed_configurations VALUES(?,?,?,?)',
                (eid,observed['version'],observed['signature'],encode(observed['payload'])))
            if len(canonical['members'])==6 and canonical['status']!='conflicting':
                for other in self.db.execute('''SELECT id,canonical,status,build_id FROM extractions
                    WHERE algorithm_version=? AND id!=? AND (composition_id=? OR composition_id IS NULL OR ? IS NULL)''',
                    (version,eid,canonical['composition_id'],canonical['composition_id'])).fetchall():
                    if other['status']=='conflicting' or canonical['exact_build_id'] and other['build_id']:continue
                    original=json.loads(other['canonical'])
                    if len(original['members'])==6 and _compatible(canonical,original):
                        left,right=sorted([eid,other['id']])
                        self.db.execute('INSERT OR IGNORE INTO duplicate_candidates VALUES(?,?,?)',
                            (left,right,'same composition and compatible known fields; exact equality unproven'))
        return dict(publication_id=pid,extraction_id=eid,status=canonical['status'],
            composition_id=canonical['composition_id'],exact_build_id=canonical['exact_build_id'])

    def scoped(self,population,regulation,battle_format,version=VERSION):
        from . import POPULATIONS
        if population not in POPULATIONS:raise ValueError('Explicit community_published or tournament_published population required; no Ranked/pooled data')
        if not regulation or battle_format not in ('Doubles','Singles','Unknown'):raise ValueError('Explicit regulation and format required')
        rows=[dict(r) for r in self.db.execute('''SELECT p.*,e.id AS extraction_id,e.status,e.composition_id,e.build_id,e.canonical,
            e.algorithm_version,e.adapter_version FROM publications p JOIN extractions e ON p.id=e.publication_id
            WHERE p.population=? AND p.regulation=? AND p.format=? AND e.algorithm_version=?
            AND e.id=(SELECT latest.id FROM extractions latest WHERE latest.publication_id=p.id
                AND latest.algorithm_version=e.algorithm_version ORDER BY latest.created_at DESC,latest.id DESC LIMIT 1)
            AND NOT EXISTS(SELECT 1 FROM publication_supersessions x WHERE x.publication_id=p.id)''',
            (population,regulation,battle_format,version))]
        from .population import exclusion
        return [r for r in rows if not exclusion(json.loads(r['original']))]
