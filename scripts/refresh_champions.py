"""Build a factual Champions snapshot from audited, pinned checkouts (offline).

See reports/M1.1-data-audit.md for acquisition, provenance and review requirements.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from knowledge import normalize


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def apply_priority_corrections(facts):
    """Apply reviewed M-C fields while retaining the imported source assertion."""
    path = Path(__file__).resolve().parents[1]/'knowledge/data/champions_priority_corrections.json'
    receipt = json.loads(path.read_text())
    if facts['regulation'] != receipt['regulation']:
        return
    for cid, correction in receipt['moves'].items():
        row = facts['moves'][cid]
        if row['priority'] not in {correction['previous_priority'], correction['priority']}:
            raise ValueError(f'Upstream priority changed for {cid}; review the correction')
        row['priority'] = correction['priority']
        row['priority_provenance'] = {
            'correction_version': receipt['version'], 'game_version': receipt['game_version'],
            'regulation': receipt['regulation'], 'source_file': path.name,
            'source_sha256': digest(path), 'previous_priority': correction['previous_priority'],
            'previous_source': facts['source'], 'evidence': correction['evidence']}


def build(quark, pokedd, official, output, as_of):
    archive = output.parent/'archive'/'2026-04-16-v1.1.0'
    if not archive.exists():
        shutil.copytree(output, archive)
    baseline = json.loads((archive/'entities.json').read_text())
    old_manifest = json.loads((archive/'manifest.json').read_text())
    old_roster = json.loads((archive/'champions_roster.json').read_text())
    entities = baseline['entities']
    for e in entities:
        e['champions_entries'] = []
    indexes = {}
    for e in entities:
        for n in list(e['names'].values())+e['aliases']:
            indexes.setdefault((e['kind'], normalize(n)), set()).add(e['canonical_id'])
    by_id = {e['canonical_id']: e for e in entities}
    # Reviewed semantic aliases, with PokeAPI form IDs (never sprite IDs).
    form_aliases = {'Basculegion-F':10417, 'Maushold-Four':925,
                    'Squawkabilly-Yellow':10430, 'Tauros-Paldea-Aqua':10421,
                    'Tauros-Paldea-Blaze':10420, 'Tauros-Paldea-Combat':10419}
    for name, fid in form_aliases.items():
        cid = f'pokeapi:form:{fid}'
        assert cid in by_id
        indexes[('species',normalize(name))] = {cid}
    unresolved, conflicts = [], []
    mapping = {}
    def join(kind, r):
        # English is preferred; a localized form join also requires matching dex ID.
        candidates = indexes.get((kind, normalize(r['canonical'])), set())
        if not candidates:
            candidates = indexes.get((kind, normalize(r['display_name'] or '')), set())
        if kind == 'species':
            candidates = {cid for cid in candidates if by_id[cid]['species_id'] == r['national_dex_no']}
            if r['canonical'] != r['base_species']:
                candidates = {cid for cid in candidates if by_id[cid]['form_id'] is not None}
        if len(candidates) != 1:
            unresolved.append({'kind':kind, 'name':r['canonical'], 'candidates':sorted(candidates),
                               'reason':'no unique canonical name/dex/form join'})
            return None
        cid = next(iter(candidates))
        mapping[(kind, r['canonical'])] = cid
        e = by_id[cid]
        if e['names'].get('zh-hans') and r['display_name'] and normalize(e['names']['zh-hans']) != normalize(r['display_name']):
            conflicts.append({'kind':'localization', 'canonical_id':cid, 'retained':e['names']['zh-hans'], 'upstream':r['display_name']})
        # Keep existing reliable labels; upstream spelling is a lookup alias.
        e['aliases'] = sorted(set(e['aliases']+[r['canonical']]))
        if r['display_name']:
            if not e['names'].get('zh-hans'):
                e['names']['zh-hans'] = r['display_name']
                e['name_source'] += '; quark unique canonical/dex join'
            elif normalize(e['names']['zh-hans']) != normalize(r['display_name']):
                e['aliases'] = sorted(set(e['aliases']+[r['display_name']]))
        return cid
    dex_path = '.agents/skills/pokemon-champions-dex/data/champions_dex.sqlite'
    db = sqlite3.connect(f'file:{quark/dex_path}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    source = {'repository':'https://github.com/pmwl0128/Quark_Drive_Skills',
              'commit':git(quark,'rev-parse','HEAD'), 'commit_date':git(quark,'log','-1','--format=%cI'),
              'path':dex_path, 'sha256':digest(quark/dex_path),
              'file_commit':git(quark,'log','-1','--format=%H','--',dex_path),
              'file_commit_date':git(quark,'log','-1','--format=%cI','--',dex_path)}
    facts = {'schema_version':1,'snapshot_version':f'{as_of}-M-C.1','regulation':'M-C','source':source,
             'pokemon':{}, 'moves':{}, 'abilities':{}, 'items':{}}
    counts = {}
    for table,kind in [('pokemon','species'),('moves','move'),('abilities','ability'),('items','item')]:
        rows = [dict(r) for r in db.execute('select * from '+table)]
        counts[table] = len(rows)
        for r in rows:
            cid = join(kind,r)
            if cid is None:
                continue
            if table == 'pokemon':
                record = {'upstream_name':r['canonical'],'stats':json.loads(r['stats_json']),
                          'types':json.loads(r['types_json']),'weight_kg':r['weight'],
                          'ability_names':json.loads(r['abilities_json']), 'required_item':r['required_item']}
            elif table == 'moves':
                record = {k:r[k] if r[k] != '' else None for k in ['type','category','power','accuracy','pp','priority']}
            else:
                record = {'upstream_name':r['canonical']}
            record['evidence_type'] = 'community_catalog_assertion'
            facts[table][cid] = record
    apply_priority_corrections(facts)
    corrections = Path(__file__).resolve().parents[1]/'knowledge/data/champions_priority_corrections.json'
    if output.resolve() != corrections.parent.resolve():
        shutil.copyfile(corrections, output/corrections.name)
    relationships = {}
    for cid,r in facts['pokemon'].items():
        relationships[cid] = {'abilities': sorted({mapping[('ability',n)] for n in r['ability_names'] if ('ability',n) in mapping}), 'moves':[]}
    edges = 0
    for r in db.execute('select pokemon,move from learnsets'):
        sid,mid = mapping.get(('species',r[0])),mapping.get(('move',r[1]))
        if sid and mid:
            relationships[sid]['moves'].append(mid); edges += 1
        else:
            unresolved.append({'kind':'learnset','pokemon':r[0],'move':r[1], 'reason':'unmapped relationship endpoint'})
    for r in relationships.values(): r['moves'] = sorted(set(r['moves']))
    baseline['relationships'] = relationships
    raw = official.read_text()
    match = re.search(r'const pokemons = (\[.*?\]);',raw,re.S)
    if not match:
        raise ValueError('Official roster schema changed; review before importing')
    official_rows = json.loads(match[1])
    if len(official_rows) < 100:
        raise ValueError('Official roster unexpectedly short')
    official_source = {'url':'https://web-view.app.pokemonchampions.jp/battle/pages/events/rs178713870219xeaaio/en/pokemon.html',
                       'retrieved_on':as_of,'sha256':digest(official)}
    official_ids = {int(r[0].split('-')[0]) for r in official_rows}
    scope = f'{as_of}-M-C'
    entries = {cid:{'canonical_id':cid,'status':'confirmed_available','source':source,
                    'evidence_type':'community_catalog_assertion','independently_verified':False}
               for cid in facts['pokemon']}
    rules = []
    for e in entities:
        if e['kind'] != 'species' or e['form_id'] is not None: continue
        cid = e['canonical_id']
        legal = e['species_id'] in official_ids
        if legal:
            entries[cid] = {'canonical_id':cid,'status':'confirmed_available','source':official_source,
                            'evidence_type':'official_regulation_roster','independently_verified':True}
        rules.append({'canonical_id':cid,'status':'legal' if legal else 'illegal','source':official_source,
                      'scope':'species eligibility only; does not authorize all forms'})
    # Form legality is asserted only for exact official names; omissions remain unknown.
    for code,flag,name in official_rows:
        candidates = indexes.get(('species',normalize(name)),set())
        for cid in candidates:
            if by_id[cid]['form_id'] is not None and by_id[cid]['species_id'] == int(code.split('-')[0]):
                rules.append({'canonical_id':cid,'status':'legal','source':dict(official_source,official_form_code=code)})
    announcement_source = {'url':'https://champions-news.pokemon-home.com/en/page/816.html',
                           'retrieved_on':as_of,'evidence':'six explicitly newly allowed Mega Evolutions'}
    for name in ['Mega Absol Z','Mega Salamence','Mega Garchomp Z','Mega Lucario Z','Mega Golisopod','Mega Baxcalibur']:
        cid = mapping.get(('species',name))
        if cid:
            rules.append({'canonical_id':cid,'status':'legal','source':announcement_source})
    snapshot = {'scope_id':scope,'game_version':None,'dataset_version':facts['snapshot_version'],
                'as_of':as_of,'completeness':'community catalog; official species eligibility complete',
                'authoritative':False,'source':source,'entries':list(entries.values()),
                'regulations':[{'regulation_id':'M-C','entries':rules}], 'unmapped_entries':unresolved}
    roster = {'schema_version':1,'default_scope':scope,'snapshots':[snapshot]}
    write(output/'entities.json',baseline); write(output/'champions_roster.json',roster)
    write(output/'champions_facts.json',facts)
    shutil.copyfile(quark/'LICENSE',output/'LICENSE.quark.txt')
    shutil.copyfile(quark/'NOTICE',output/'NOTICE.quark.txt')
    manifest = dict(old_manifest)
    manifest.update(inspected_on=as_of,default_regulation='M-C',
        champions=dict(source,license='MIT (original code; third-party data rights not blanket-cleared)',
            metadata={'version':facts['snapshot_version'],'lastUpdated':source['file_commit_date'],
                      'json_built_at':json.loads((quark/dex_path.replace('.sqlite','.json')).read_text())['built_at'],
                      'counts':counts}), historical_champions=old_manifest['champions'])
    manifest['files'] = {p.name:digest(p) for p in output.iterdir() if p.suffix in ('.json','.txt') and p.name != 'manifest.json'}
    manifest['sources'] = {'quark':source,'pokedd':{'repository':'https://github.com/Seancheey/PokeDD',
        'commit':git(pokedd,'rev-parse','HEAD'),'commit_date':git(pokedd,'log','-1','--format=%cI'),
        'file_commit':git(pokedd,'log','-1','--format=%H','--','prisma/data/champions-mc.json'),
        'file_commit_date':git(pokedd,'log','-1','--format=%cI','--','prisma/data/champions-mc.json'),
        'override_sha256':digest(pokedd/'prisma/data/champions-mc.json'),
        'overrides_checked_on':json.loads((pokedd/'prisma/data/champions-mc.json').read_text())['checkedOn'],
        'license':'README claims MIT; no LICENSE file found; used for comparison only'},'official':official_source}
    manifest['metagame'] = json.loads((quark/'.agents/skills/pokemon-champions-meta/data/current.json').read_text())
    manifest['unmapped_champions_entries'] = unresolved
    manifest['entity_counts'] = {kind:sum(e['kind']==kind for e in entities) for kind in ['species','move','ability','item']}
    manifest['builder'] = {'path':'scripts/refresh_champions.py','sha256':digest(Path(__file__)),
                           'as_of':as_of,'regulation':'M-C','missing_is_unknown':True}
    manifest['limitations'] = ['Missing game catalog entries remain unknown; official omissions imply M-C illegality only.',
        'Upstream per-row source fields are empty; file dates are not independent fact verification.',
        'Unjoined forms and relationship endpoints are excluded; no sprite-ID to form-ID assumptions.',
        'Move PP/power/accuracy nulls retained, never backfilled from the historical dataset.',
        'Descriptions, sprites, raw scrape caches and usage statistics are not redistributed.']
    write(output/'manifest.json',manifest)
    # Compare independently tracked M-C overrides without importing them wholesale.
    overrides = json.loads((pokedd/'prisma/data/champions-mc.json').read_text())
    stat_keys = {'hp':'hp','atk':'at','def':'df','spa':'sa','spd':'sd','spe':'sp'}
    override_checks = []
    for form in overrides['forms']:
        name = 'Mega '+form['baseSlug'].capitalize()+(' Z' if form['slug'].endswith('-z') else '')
        cid = mapping.get(('species',name))
        if cid:
            expected = {v:form[k] for k,v in stat_keys.items()}
            matches = expected == facts['pokemon'][cid]['stats']
            override_checks.append({'name':name,'canonical_id':cid,'stats_match':matches})
            if not matches:
                conflicts.append({'kind':'stats','canonical_id':cid,'quark':facts['pokemon'][cid]['stats'],'pokedd':expected})
        else:
            override_checks.append({'name':name,'reason':'no mapped Quark form'})
    report = {'pokedd_override_checks':override_checks,'old':{'roster_assertions':len(old_roster['snapshots'][0]['entries']),
                     'relationships':len(json.loads((archive/'entities.json').read_text())['relationships']),
                     'source_counts':old_manifest['champions']['metadata']['counts']},
              'new':{'upstream_counts':counts,'mapped_counts':{k:len(facts[k]) for k in ['pokemon','moves','abilities','items']},
                     'learnset_edges_mapped':edges,'official_roster_rows':len(official_rows),'official_species':len(official_ids)},
              'unresolved':unresolved,'conflicts':conflicts,'official_records':official_rows}
    write(output/'coverage.json',report)
    manifest['files']['coverage.json'] = digest(output/'coverage.json'); write(output/'manifest.json',manifest)
    print(json.dumps(report['new'],indent=2))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--quark',type=Path,required=True);p.add_argument('--pokedd',type=Path,required=True)
    p.add_argument('--official-html',type=Path,required=True);p.add_argument('--as-of',required=True)
    p.add_argument('--output',type=Path,default=Path('knowledge/data'))
    a=p.parse_args();build(a.quark,a.pokedd,a.official_html,a.output,a.as_of)
