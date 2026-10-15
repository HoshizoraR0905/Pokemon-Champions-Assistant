"""Build a canonical-ID supplement from the pinned local oracle; no network."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from knowledge import KnowledgeBase,normalize

def build():
    package=ROOT/'.cache/m31/oracle/node_modules/@smogon/calc'
    assert json.loads((package/'package.json').read_text())['version']=='0.12.0'
    js="const c=require(process.argv[1]),g=c.Generations.get(0);console.log(JSON.stringify({species:Array.from(g.species),moves:Array.from(g.moves),types:Array.from(g.types)}));"
    raw=json.loads(subprocess.check_output(['node','-e',js,str(package)]))
    kb=KnowledgeBase();species={};moves={};unmatched=[]
    byname={normalize(s['name']):s for s in raw['species']}
    for sid,fact in kb.facts['pokemon'].items():
        name=fact['upstream_name'];alias=name
        if name.startswith('Mega '):
            parts=name[5:].rsplit(' ',1);alias=parts[0]+'-Mega-'+parts[1] if len(parts)==2 and parts[1] in ['X','Y','Z'] else name[5:]+'-Mega'
        for prefix,suffix in [('Alolan ','-Alola'),('Galarian ','-Galar'),('Hisuian ','-Hisui'),('Paldean ','-Paldea')]:
            if name.startswith(prefix):alias=name[len(prefix):]+suffix
        value=byname.get(normalize(alias))
        if not value:unmatched.append(sid);continue
        species[sid]=dict(oracle_name=value['name'],types=value['types'],base_stats=value['baseStats'],local_types=fact['types'],type_agreement=value['types']==fact['types'])
    for value in raw['moves']:
        hits=kb.exact['move'].get(normalize(value['name']),[]);ids={e.canonical_id for e in hits}
        if len(ids)==1:
            sid=next(iter(ids));moves[sid]=dict(value,target=value.get('target','any'))
    data=dict(schema_version=1,profile='showdown-champions-reference-v1',oracle_version='0.12.0',generation=0,knowledge_snapshot=kb.snapshot_id,
        species=species,moves=moves,type_chart={t['name']:t['effectiveness'] for t in raw['types'] if t['name']!='???'},unmatched_local_species=unmatched)
    target=ROOT/'damage/data/reference-v1.json';target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    files=['dist/mechanics/champions.js','dist/mechanics/util.js','dist/data/moves.js','dist/data/species.js','dist/data/types.js']
    manifest=dict(schema_version=1,oracle=dict(package='@smogon/calc',version='0.12.0',generation=0,license='MIT',repository='https://github.com/smogon/damage-calc',inspected_commit='9c57e9b8c1d8a7403b71c10042136ea5e001593b',files={f:hashlib.sha256((package/f).read_bytes()).hexdigest() for f in files}),
        knowledge_snapshot=kb.snapshot_id,knowledge_manifest_sha256=hashlib.sha256((ROOT/'knowledge/data/manifest.json').read_bytes()).hexdigest(),
        files={'reference-v1.json':hashlib.sha256(target.read_bytes()).hexdigest()},counts=dict(species=len(species),moves=len(moves),unmatched_species=len(unmatched)),
        evidence='All formula/modifier/type data provisional community reference, not official Champions verification')
    (target.parent/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    assert (target.parent/'LICENSE.smogon.txt').is_file(), 'Pinned upstream LICENSE must be present'
    print(manifest['counts'])
if __name__=='__main__':build()
