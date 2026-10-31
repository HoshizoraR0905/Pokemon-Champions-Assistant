"""Offline canonical lookup, sharing the repository's pinned knowledge index."""
from functools import lru_cache
import hashlib,json
from pathlib import Path
from knowledge import KnowledgeBase,normalize

class Diagnostic(Exception):
    def __init__(self,status,path,reason,candidates=None):
        self.status=status;self.path=path;self.reason=reason;self.candidates=candidates or []
    def as_dict(self):return dict(path=self.path,reason=self.reason,candidates=self.candidates)

@lru_cache(maxsize=1)
def database():
    kb=KnowledgeBase();root=Path(__file__).parent/'data';manifest=json.loads((root/'manifest.json').read_text());raw=(root/'reference-v1.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest['files']['reference-v1.json']:raise ValueError('Damage supplement checksum mismatch')
    current=hashlib.sha256((Path(__file__).resolve().parents[1]/'knowledge/data/manifest.json').read_bytes()).hexdigest()
    if current!=manifest['knowledge_manifest_sha256']:
        compatibility=json.loads((root/'knowledge-compatibility-v1.json').read_text())
        if (compatibility['original_manifest_sha256']!=manifest['knowledge_manifest_sha256'] or
                current not in compatibility['accepted_manifest_sha256']):
            raise ValueError('Pinned knowledge manifest changed without a damage compatibility audit')
    if kb.snapshot_id!=manifest['knowledge_snapshot']:raise ValueError('Damage and knowledge snapshots differ')
    return kb,json.loads(raw),manifest


def resolve(value,kind,path):
    kb,_,_=database()
    if not isinstance(value,str):raise Diagnostic('invalid_input',path,'Expected canonical ID or exact Chinese/English name')
    if value.isdecimal():raise Diagnostic('invalid_input',path,'Numeric IDs require an explicit namespace, e.g. pokeapi:move:89')
    explicit_variant=False
    if kind=='species' and value.startswith('pokeapi:pokemon:'):
        suffix=value.rsplit(':',1)[1]
        rows=kb.identities.by_pokemon.get(int(suffix),[]) if suffix.isdecimal() else []
        if len(rows)>1:raise Diagnostic('ambiguous_input',path,'Pokemon ID has multiple form rows; supply exact form ID',[f"pokeapi:form:{r.get('source_form_id',r['form_id'])}" for r in rows])
        if not rows:raise Diagnostic('unresolved_input',path,'Unknown canonical Pokemon ID')
        row=rows[0];form_key=f"pokeapi:form:{row.get('source_form_id',row['form_id'])}"
        value=form_key if form_key in kb.entities else f"pokeapi:species:{row['species_id']}" if row['pokemon_id']==row['species_id'] else form_key
        explicit_variant=True
    found=[kb.entities[value]] if value in kb.entities else kb.exact[kind].get(normalize(value),[])
    found={e.canonical_id:e for e in found if e.kind==kind}
    if not found:raise Diagnostic('unresolved_input',path,'No exact pinned dictionary match')
    if len(found)>1:raise Diagnostic('ambiguous_input',path,'Explicit disambiguation required',sorted(found))
    e=next(iter(found.values()));return dict(canonical_id=e.canonical_id,name=e.names.get('en'),chinese=e.names.get('zh-hans'),species_id=e.species_id,form_id=e.form_id,explicit_variant=explicit_variant)


def pokemon_data(mon,path):
    ref=resolve(mon.get('identity'),'species',path+'.identity');kb,data,_=database()
    form=mon.get('form')
    if ref['form_id'] is None and ref.get('explicit_variant'):
        if form not in (None,'base','as_named'):raise Diagnostic('invalid_input',path+'.form','Explicit Pokemon identity already fixes its form')
    elif ref['form_id'] is None:
        if form is None:raise Diagnostic('incomplete_input',path+'.form','Specify base or an explicit canonical form')
        if form!='base':
            chosen=resolve(form,'species',path+'.form')
            if chosen['species_id']!=ref['species_id'] or chosen['form_id'] is None:raise Diagnostic('invalid_input',path+'.form','Form does not belong to supplied species')
            ref=chosen
    elif form not in (None,'as_named'):
        raise Diagnostic('invalid_input',path+'.form','Explicit form identity already supplied; use as_named or omit form')
    record=data['species'].get(ref['canonical_id'])
    if record is None:raise Diagnostic('unsupported',path+'.identity','No pinned Champions reference form data')
    if not record['type_agreement']:raise Diagnostic('conflicting_input',path+'.identity','Local Champions and reference form types disagree')
    return ref,record
