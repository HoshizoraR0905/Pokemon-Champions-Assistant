"""Build an offline name snapshot from pinned source checkouts; no runtime fetches.

Usage: python scripts/build_knowledge.py --champions PATH --pokeapi-csv PATH
       --unihan PATH --unicode-license PATH --output knowledge/data
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata
import zipfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from knowledge.roster import build_roster


def key(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKC',text).casefold() if c.isalnum())


def build(champions: Path, csv_root: Path, unihan: Path, unicode_license: Path, output: Path) -> None:
    output.mkdir(parents=True,exist_ok=True)
    def rows(filename):
        with (csv_root/filename).open(encoding='utf-8',newline='') as f:
            return list(csv.DictReader(f))
    langs = {r['id']:r['identifier'] for r in rows('languages.csv')}
    assert langs['12'] == 'zh-hans' and langs['9'] == 'en'
    entities = []
    dictionaries = {}
    source_files = []
    for kind, base, names_file, id_column in [
        ('species','pokemon_species.csv','pokemon_species_names.csv','pokemon_species_id'),
        ('move','moves.csv','move_names.csv','move_id'),
        ('ability','abilities.csv','ability_names.csv','ability_id'),
        ('item','items.csv','item_names.csv','item_id')]:
        source_files.extend([base,names_file])
        localized = {}
        for r in rows(names_file):
            if r['local_language_id'] in ('9','12'):
                localized.setdefault(r[id_column],{})[langs[r['local_language_id']]] = r['name']
        for r in rows(base):
            names = localized.get(r['id'],{})
            if not names.get('en'):
                continue
            entity = {'canonical_id':f'pokeapi:{kind}:{r["id"]}','kind':kind,
                      'names':names,'aliases':[], 'species_id':int(r['id']) if kind=='species' else None,
                      'form_id':None,'champions_entries':[],
                      'name_source':f'pokeapi/{names_file}:{r["id"]}'}
            entities.append(entity)
            dictionaries.setdefault(kind,{})[key(names['en'])] = entity
    species = {e['species_id']:e for e in entities if e['kind']=='species'}
    pokemon = {r['id']:r for r in rows('pokemon.csv')}
    localized_forms = {}
    for r in rows('pokemon_form_names.csv'):
        if r['local_language_id'] in ('9','12'):
            localized_forms.setdefault(r['pokemon_form_id'],{})[langs[r['local_language_id']]] = r
    for r in rows('pokemon_forms.csv'):
        sid = int(pokemon[r['pokemon_id']]['species_id'])
        s = species.get(sid)
        if s is None:
            continue
        # Bare species names do not identify default/gender/region/mega forms.
        if not r['form_identifier']:
            s['possible_form_ids'] = s.get('possible_form_ids',[]) + [int(r['id'])]
            continue
        ns, labels, aliases = {}, {}, []
        for lang, n in localized_forms.get(r['id'],{}).items():
            labels[lang] = n['form_name']
            if n['pokemon_name']:
                ns[lang] = n['pokemon_name']
            elif s['names'].get(lang) and s['names'][lang] in n['form_name']:
                ns[lang] = n['form_name']
            if n['form_name'] and s['names'].get(lang):
                aliases.append(s['names'][lang]+' ('+n['form_name']+')')
        # English identifiers are canonical source identifiers, not translations.
        aliases.append(r['identifier'])
        if not ns:
            ns['en'] = r['identifier']
        e = {'canonical_id':f'pokeapi:form:{r["id"]}','kind':'species','names':ns,
             'aliases':aliases,'species_id':sid,'form_id':int(r['id']),
             'form_labels':labels,'champions_entries':[],
             'name_source':f'pokeapi/pokemon_form_names.csv:{r["id"]}'}
        entities.append(e)
        s['possible_form_ids'] = s.get('possible_form_ids',[]) + [int(r['id'])]
        if ns.get('en'):
            dictionaries['species'][key(ns['en'])] = e
    source_files.extend(['languages.csv','pokemon.csv','pokemon_forms.csv','pokemon_form_names.csv'])
    unmapped, relationships = [], {}
    paths = {'species':'pokemon/roster.json','move':'moves/moves.json',
             'ability':'abilities/abilities.json','item':'items/items.json'}
    for kind,path in paths.items():
        data = json.loads((champions/path).read_text())
        for r in data:
            e = dictionaries[kind].get(key(r['name']))
            if e is None or (kind=='species' and e['species_id'] != r['dexNumber']):
                unmapped.append({'kind':kind,'name':r['name'],'reason':'no unique validated name/ID join'})
                continue
            e['champions_entries'].append({'name':r['name'],'form':r.get('form'),
                'inChampions':r.get('inChampions'),
                'championsVerified_source_claim':r.get('championsVerified',False)})
            if kind=='species':
                aids = [dictionaries['ability'][key(a)]['canonical_id']
                        for a in r['abilities'].values() if key(a) in dictionaries['ability']]
                relationships[e['canonical_id']] = {'abilities':sorted(set(aids)), 'moves':[]}
    learnsets = json.loads((champions/'learnsets/learnsets.json').read_text())
    for name, r in learnsets.items():
        e = dictionaries['species'].get(key(name))
        if e and e['canonical_id'] in relationships:
            relationships[e['canonical_id']]['moves'] = sorted({
                dictionaries['move'][key(m['name'])]['canonical_id'] for m in r['moves']
                if key(m['name']) in dictionaries['move']})
    # Generic radical/stroke evidence, never OCR-string-specific replacements.
    chars = set(''.join(n for e in entities for n in list(e['names'].values())+e['aliases']))
    radicals = {}
    with zipfile.ZipFile(unihan) as z:
        raw = z.read('Unihan_IRGSources.txt').decode('utf-8')
    for line in raw.splitlines():
        if not line.startswith('U+'):
            continue
        code,field,value = line.split('\t',2)
        char = chr(int(code[2:],16))
        if char in chars and field=='kRSUnicode':
            first = value.split()[0]
            match = re.fullmatch(r"(\d+)'?\.(\d+)",first)
            if match:
                radicals[char] = [int(match[1]),int(match[2])]
    payload = {'schema_version':1,'entities':entities,'relationships':relationships,'radicals':radicals}
    (output/'entities.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    sha = subprocess.check_output(['git','-C',str(champions),'rev-parse','HEAD'],text=True).strip()
    commit = subprocess.check_output(['git','-C',str(champions),'log','-1','--format=%cI'],text=True).strip()
    poke_commit = json.loads((csv_root/'commit.json').read_text())
    manifest = {'schema_version':1,'inspected_on':'2026-10-13',
        'champions':{'repository':'https://github.com/otterlyclueless/pokemon-champions-data',
            'commit':sha,'commit_date':commit,'license':'CC-BY-4.0',
            'metadata':json.loads((champions/'meta/version.json').read_text())},
        'localization':{'repository':'https://github.com/PokeAPI/pokeapi',
            'commit':poke_commit['sha'],'commit_date':poke_commit['commit']['committer']['date'],
            'license':'BSD-3-Clause','languages':{'9':'en','12':'zh-hans'},
            'validation':'Language IDs and canonical numeric joins validated; official-site species spot checks in validation.json. Not all translations independently verified.'},
        'unihan':{'source':'https://www.unicode.org/Public/18.0.0/ucd/Unihan.zip',
            'license':'Unicode-3.0','field':'kRSUnicode','sha256':hashlib.sha256(unihan.read_bytes()).hexdigest()},
        'files':{},'unmapped_champions_entries':unmapped,
        'entity_counts':{kind:sum(e['kind']==kind for e in entities) for kind in paths},
        'limitations':['No automatic data refresh or guarantee of game availability.',
            'Items lack game availability flags; forms and localization coverage are incomplete.',
            'Source championsVerified flags are claims, not recognition verification.']}
    roster = build_roster(entities, manifest['champions'], unmapped)
    (output/'champions_roster.json').write_text(json.dumps(roster, ensure_ascii=False, indent=2)+'\n')
    for entity in entities:
        if entity['kind'] == 'species':
            entity['champions_entries'] = []
    (output/'entities.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n')
    manifest['files']['champions_roster.json'] = hashlib.sha256((output/'champions_roster.json').read_bytes()).hexdigest()
    for path in list(paths.values())+['learnsets/learnsets.json','meta/version.json']:
        manifest['files']['champions/'+path] = hashlib.sha256((champions/path).read_bytes()).hexdigest()
    for path in sorted(set(source_files)):
        manifest['files']['pokeapi/'+path] = hashlib.sha256((csv_root/path).read_bytes()).hexdigest()
    manifest['files']['entities.json'] = hashlib.sha256((output/'entities.json').read_bytes()).hexdigest()
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    shutil.copyfile(champions/'LICENSE',output/'LICENSE.champions.txt')
    shutil.copyfile(csv_root/'LICENSE.md',output/'LICENSE.pokeapi.txt')
    shutil.copyfile(unicode_license,output/'LICENSE.unicode.txt')
    print(manifest['entity_counts'],'unmapped:',len(unmapped))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--champions',type=Path,required=True)
    p.add_argument('--pokeapi-csv',type=Path,required=True)
    p.add_argument('--unihan',type=Path,required=True)
    p.add_argument('--unicode-license',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path('knowledge/data'))
    a = p.parse_args()
    build(a.champions,a.pokeapi_csv,a.unihan,a.unicode_license,a.output)
