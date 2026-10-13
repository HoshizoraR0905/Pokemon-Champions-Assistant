"""Extend M1.1 with an independently versioned form and visual identity index.

No visual pixels are redistributed. Inputs: pinned PokeAPI CSVs and Champions
sprite checkout. Cache population is explicit; recognition never downloads assets.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from knowledge import normalize, KnowledgeBase

POKEAPI_COMMIT='81d20919845b6a445969b9265aab5cec6b04cece'
SPRITES_COMMIT='0dc105d5b12416932f29b594078282ab4be045f5'
CHAMPIONS_COMMIT='4953be0b8f2eee5415255c4e0bb2bdec6065c75b'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def slug(name):return re.sub(r'[^a-z0-9-]','',name.lower().replace(' ','-').replace('_','-'))


def build(csv_root,champions,cache,output):
    commit=subprocess.check_output(['git','-C',str(champions),'rev-parse','HEAD'],text=True).strip()
    if commit != CHAMPIONS_COMMIT:raise ValueError('Unreviewed sprite revision; update pin only after auditing')
    base=json.loads((output/'entities.json').read_text());manifest=json.loads((output/'manifest.json').read_text())
    kb=KnowledgeBase(output)
    historical=json.loads((output.parent/'archive'/'2026-04-16-v1.1.0'/'manifest.json').read_text())
    for name in ['pokemon.csv','pokemon_forms.csv','pokemon_form_names.csv']:
        if sha(csv_root/name)!=historical['files']['pokeapi/'+name]:
            raise ValueError('Unreviewed PokeAPI CSV input: '+name)
    species={e['species_id']:e for e in base['entities'] if e['kind']=='species' and e['form_id'] is None}
    existing={e['canonical_id']:e for e in base['entities']}
    official=json.loads((output/'coverage.json').read_text())['official_records']
    official_defaults={int(code[:4]) for code,flag,name in official
                       if code.endswith('-000') and name==species.get(int(code[:4]),{}).get('names',{}).get('en')}
    official_source=manifest['sources']['official']
    def rows(name):return list(csv.DictReader((csv_root/name).open()))
    pokemon={r['id']:r for r in rows('pokemon.csv')}
    form_names={}
    for r in rows('pokemon_form_names.csv'):
        if r['local_language_id'] in ['9','12']:
            form_names.setdefault(r['pokemon_form_id'],{})['en' if r['local_language_id']=='9' else 'zh-hans']=r
    records=[];form_slugs={}
    for r in rows('pokemon_forms.csv'):
        sid=int(pokemon[r['pokemon_id']]['species_id']);s=species[sid];fid=int(r['id']);cid=f'pokeapi:form:{fid}'
        e=existing.get(cid);loc=form_names.get(r['id'],{})
        names={k:v['pokemon_name'] for k,v in loc.items() if v['pokemon_name']}
        if e:names.update(e['names'])
        if not r['form_identifier'] and not names:
            names=dict(s['names'])
        labels={k:v['form_name'] for k,v in loc.items() if v['form_name']}
        source={'repository':'https://github.com/PokeAPI/pokeapi','commit':POKEAPI_COMMIT,
                'path':'data/v2/csv/pokemon_forms.csv','row_id':fid}
        record={'canonical_id':cid,'species_id':sid,'form_id':fid,'pokemon_id':int(r['pokemon_id']),
                'identifier':r['identifier'],'species_names':s['names'],'names':names,
                'form_names':labels,'aliases':e['aliases'] if e else [r['identifier']],
                'is_default':r['is_default']=='1','is_mega':r['is_mega']=='1','source':source,'visual_assets':[],
                'champions_availability':kb.availability(cid)}
        if (record['is_default'] and record['pokemon_id']==sid and sid in official_defaults
                and record['champions_availability']['status']=='unknown'):
            record['champions_availability']={'status':'confirmed_available','legality':'legal',
                'regulation':'M-C','source':official_source,
                'reason':'exact_official_default_form_row'}
        records.append(record);form_slugs.setdefault(r['identifier'],[]).append(record)
    # Resolve filename conventions using PokeAPI identifiers or reviewed form semantics.
    named={}
    for e in base['entities']:
        if e['kind']!='species':continue
        for n in [e['names'].get('en','')]+e['aliases']:
            variants={slug(n)}
            if n.startswith('Mega '):
                parts=n[5:].split();variants.add(slug(parts[0])+'-mega'+('-'+slug(' '.join(parts[1:])) if len(parts)>1 else ''))
            for region in ['Alolan','Galarian','Hisuian','Paldean']:
                if n.startswith(region+' '):variants.add(slug(n[len(region)+1:])+'-'+region[:5].lower().rstrip('n'))
            for v in variants:named.setdefault(v,set()).add(e['canonical_id'])
    refs=[];unmapped=[];cache.mkdir(parents=True,exist_ok=True)
    for p in sorted((champions/'sprites').glob('*.png')):
        # Exact PokeAPI identifier is the first authority for form mapping.
        forms=form_slugs.get(p.stem,[])
        if not forms:
            candidates=named.get(p.stem,set())
            if len(candidates)==1:
                e=existing[next(iter(candidates))]
                if e['form_id']:forms=[r for r in records if r['form_id']==e['form_id']]
                else:forms=[r for r in records if r['species_id']==e['species_id'] and r['is_default'] and r['pokemon_id']==e['species_id']]
        if len(forms)!=1:
            unmapped.append({'file':p.name,'reason':'no unique reviewed form join'})
        form=forms[0] if len(forms)==1 else None
        cid=None
        if form:
            cid=form['canonical_id'] if form['canonical_id'] in existing else f"pokeapi:species:{form['species_id']}"
        ref={'file':p.name,'canonical_id':cid,'species_id':form['species_id'] if form else None,
             'form_id':form['form_id'] if form else None,'sha256':sha(p),
             'url':f'https://raw.githubusercontent.com/KevinToodlepoot/pokemon-champions-sprites/{commit}/sprites/{p.name}'}
        refs.append(ref)
        if form:form['visual_assets'].append(ref)
        shutil.copyfile(p,cache/p.name)
    index={'schema_version':1,'source':{'repository':'https://github.com/KevinToodlepoot/pokemon-champions-sprites',
             'commit':commit,'commit_date':subprocess.check_output(['git','-C',str(champions),'log','-1','--format=%cI'],text=True).strip(),
             'origin_claim':'Bulbapedia','license':'No license found; local retrieval only; not redistributed'},
           'assets':refs,'unmapped':unmapped}
    write(output/'visual_assets.json',index);write(cache/'index.json',index)
    identity={'schema_version':1,'version':'2026-10-13-identity.1','localization_source':manifest['localization'],
        'sources':{'forms':{'commit':POKEAPI_COMMIT,'repository_head_date':'2026-10-13T00:08:32Z',
                'file_commit_dates':{'pokemon_forms.csv':'2026-08-18T09:39:23Z',
                                     'pokemon_form_names.csv':'2026-06-24T03:26:43Z'},'files':{name:sha(csv_root/name) for name in ['pokemon.csv','pokemon_forms.csv','pokemon_form_names.csv']}},
                   'pokeapi_sprites':{'repository':'https://github.com/PokeAPI/sprites','commit':SPRITES_COMMIT,'repository_head_date':'2026-10-12T00:07:47Z',
                       'license':'CC0 repository; Pokémon Company copyright on images',
                       'role':'secondary references; not used for Champions icon matching'}},
        'species':[{'canonical_id':e['canonical_id'],'species_id':e['species_id'],'names':e['names'],
                     'champions_availability':kb.availability(e['canonical_id'])} for e in species.values()],
        'forms':records,'coverage':{'species':len(species),'forms':len(records),
            'forms_with_complete_zh_name':sum(bool(r['names'].get('zh-hans')) for r in records),
            'forms_with_zh_form_label':sum(bool(r['form_names'].get('zh-hans')) for r in records),
            'visual_files':len(refs),'visual_files_mapped':len(refs)-len(unmapped)},
        'limitations':['Names and form labels missing upstream remain missing; species Chinese names are available separately.',
                        'Visual coverage does not establish Champions availability or regulation legality.']}
    write(output/'identity.json',identity)
    for name in ['visual_assets.json','identity.json']:manifest['files'][name]=sha(output/name)
    manifest['identity_version']=identity['version'];write(output/'manifest.json',manifest)
    print(identity['coverage']);print('unmapped sprites',len(unmapped))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pokeapi-csv',type=Path,required=True)
    p.add_argument('--champions-sprites',type=Path,required=True)
    p.add_argument('--cache',type=Path,default=Path('.cache/champions-icons'))
    p.add_argument('--output',type=Path,default=Path('knowledge/data'))
    a=p.parse_args();build(a.pokeapi_csv,a.champions_sprites,a.cache,a.output)
