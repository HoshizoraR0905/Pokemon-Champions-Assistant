"""Two order-invariant identities with strict, explicit completeness guards."""
import json
from pathlib import Path
from knowledge import normalize
from metagame.common import encode, sha
from metagame.identity import Names
from metagame.parser import stat_vector
from . import VERSION


class Canonicalizer:
    def __init__(self, names=None, version=VERSION):
        self.names=names or Names()
        self.version=version
        raw=(Path(__file__).parent/'natures.json').read_bytes()
        self.nature_source=json.loads(raw)
        self.nature_hash=sha(raw)
        self.natures={normalize(n):'nature:'+k for k,r in self.nature_source['rows'].items() for n in r['names']}

    def nature(self, value):
        if isinstance(value,str) and value.startswith('nature:'):
            return value if value[7:] in self.nature_source['rows'] else None
        return self.natures.get(normalize(value)) if isinstance(value,str) else None

    def mon(self, raw):
        issues=[]
        def entity(value, kind):
            if not isinstance(value,str) or not value.strip():return None
            result=self.names.resolve(value,kind)
            if result['canonical_id'] is None:issues.append('unresolved_'+kind+':'+value)
            return result['canonical_id']
        species=entity(raw.get('species'),'species')
        if 'form' in raw:
            if raw['form'] is None:
                species=None
            else:
                form=self.names.resolve(raw['form'])
                base=self.names.resolve(raw.get('species') or '')
                if form.get('species_id')!=base.get('species_id') or form['canonical_id'] is None:
                    issues.append('species_form_disagreement');species=None
                else:species=form['canonical_id']
        item=entity(raw.get('item'),'item')
        ability=entity(raw.get('ability'),'ability')
        nature=self.nature(raw.get('nature'))
        moves=raw.get('moves') or []
        resolved=[entity(v,'move') for v in moves]
        moves_complete=len(resolved)==4 and None not in resolved and len(set(resolved))==4
        vector=raw.get('sp') or dict(kind='unknown',values=[None]*6)
        try:sp=stat_vector(vector['kind'],vector['values'])
        except (ValueError,KeyError,TypeError) as exc:
            issues.append('invalid_stat_vector:'+str(exc));sp=dict(kind='unknown',values=[None]*6,validation='invalid')
        extra=raw.get('configuration',{})
        if not isinstance(extra,dict):
            issues.append('invalid_configuration');extra={}
        if raw.get('unsupported_fields'):issues.append('unsupported_gameplay_fields')
        if raw.get('conflicts'):issues.extend(raw['conflicts'])
        if sp.get('validation')=='invalid_under_pinned_profile':issues.append('invalid_sp_allocation')
        complete=bool(species and item and ability and nature and moves_complete and
            sp.get('kind')=='champions_sp' and sp.get('validation')=='valid_under_pinned_profile' and
            not issues and all(v is not None for v in extra.values()))
        # The exact named canonical species/form identity is preserved; never
        # collapse a Mega/regional/female form to its base species ID.
        normalized=dict(species=species,item=item,ability=ability,nature=nature,
            moves=sorted(resolved) if None not in resolved else resolved,
            sp=dict(kind=sp['kind'],values=sp['values']),configuration=extra)
        missing=[k for k in ('species','item','ability','nature') if normalized[k] is None]
        if not moves_complete:missing.append('complete_four_moves')
        if sp.get('validation')!='valid_under_pinned_profile':missing.append('verified_complete_champions_sp')
        if any(v is None for v in extra.values()):missing.append('configuration')
        return dict(normalized=normalized,original=raw,exact_complete=complete,issues=issues,
            missing=missing,stat_validation=sp,
            pokemon_build_id=sha(encode([self.version,'pokemon',normalized]).encode()) if complete else None)

    def team(self, raw):
        members=[self.mon(m) for m in raw.get('pokemon',[])]
        known=[m['normalized']['species'] for m in members if m['normalized']['species']]
        composition_complete=len(members)==6 and len(known)==6
        conflicts=list(raw.get('conflicts',[]))+[i for m in members for i in m['issues']
            if not i.startswith('unresolved_') and i!='unsupported_gameplay_fields']
        # Six species/form MULTISET, retaining multiplicity, not a set.
        composition=sorted(known) if composition_complete else None
        comp_id=sha(encode([self.version,'composition',composition]).encode()) if composition else None
        complete=composition_complete and all(m['exact_complete'] for m in members) and not conflicts
        exact=sorted((m['normalized'] for m in members),key=encode) if complete else None
        exact_id=sha(encode([self.version,'exact',exact]).encode()) if exact else None
        status='conflicting' if conflicts else 'exact_complete' if complete else 'composition_complete' if composition_complete else 'partial'
        return dict(version=self.version,status=status,composition_complete=composition_complete,
            composition_conflicting=any('species' in problem or 'form_disagreement' in problem for problem in conflicts),
            composition_id=comp_id,composition=composition,exact_build_id=exact_id,exact_build=exact,
            members=members,conflicts=conflicts,
            knowledge_snapshot=self.names.knowledge.snapshot_id,nature_source_sha256=self.nature_hash,
            missing=[dict(member=i,fields=m['missing'],issues=m['issues']) for i,m in enumerate(members) if m['missing'] or m['issues']])
