"""Reuse verified cached source joins, retaining labels outside predictor inputs."""
from collections import Counter
import json
from pathlib import Path
from copy import deepcopy
from metagame.common import sha
from experiments.no_sp_archetypes.frozen import file_hash
from .features import Mechanisms, observed, dictionary, DESIGN

ROOT=Path(__file__).resolve().parents[2]


def prepare(m353, m351):
    m353=Path(m353);m351=Path(m351)
    manifest=json.loads((m353/'manifest.json').read_text());old_manifest=json.loads((m351/'manifest.json').read_text())
    paths=[(m353/'frozen.json',manifest),(m351/'population.json',old_manifest)]
    if manifest['status']!='complete' or old_manifest['status']!='complete':raise ValueError('Completed cached source runs required')
    hashes={}
    for path,m in paths:
        stage=m['stages'][path.stem]
        if stage['status']!='complete' or file_hash(path)!=stage['sha256']:raise ValueError('Source-stage hash mismatch')
        hashes[str(path)]=file_hash(path)
    frozen=json.loads((m353/'frozen.json').read_text());original=json.loads((m351/'population.json').read_text())['targets']['Incineroar']
    if file_hash(m351/'population.json')!=frozen['source_hashes']['population.json']:raise ValueError('Source identity differs from frozen M3.5.3 reference')
    source=frozen['training'];byid={r['empirical_record_id']:r for r in original}
    if len(source)!=197 or len(byid)!=197 or {r['empirical_record_id'] for r in source}!=set(byid):raise ValueError('Expected exactly the original 197 occurrences')
    mechanics=Mechanisms();rows=[];targets=[];originals={}
    for r in source:
        old=byid[r['empirical_record_id']]
        if r['configuration']!=old['configuration'] or r['training_points']!=old['training_points']:raise ValueError('Frozen source configuration mismatch')
        if len(r['teammates'])!=5 or {m['ordinal'] for m in r['teammates']}!={i for i in range(6) if i!=r['member_ordinal']}:
            raise ValueError('Incorrect original teammate association')
        mates=[observed(m) for m in r['teammates']]
        own={k:deepcopy(r['configuration'][k]) for k in ('moves','item')}
        context,evidence=mechanics.extract(mates)
        interactions={spec['name']:mechanics.interaction(own,context,spec['name']) for spec in DESIGN['interactions']}
        rows.append(dict(id=r['empirical_record_id'],group=r['evaluation_group'],m351_group=old['evaluation_group'],
            publication_id=r['publication_id'],source_url=r['source_url'],source_title=r['source_title'],
            own=own,teammates=mates,context=context,interactions=interactions,evidence=evidence))
        p=r['training_points'];targets.append([p['speed'],p['attack'],p['hp']+p['defense']+p['special_defense']])
        originals[r['empirical_record_id']]=r
    groups={r['group'] for r in rows};old_groups={r['m351_group'] for r in rows}
    if len(groups)!=187 or len(old_groups)!=192:raise ValueError('Source grouping identity/count changed; inspect before choosing validation folds')
    mapping={}
    for r in rows:mapping.setdefault(r['m351_group'],set()).add(r['group'])
    if any(len(g)!=1 for g in mapping.values()):raise ValueError('Stronger grouping split an original connected group')
    return dict(rows=rows,targets=targets,originals=originals,feature_dictionary=dictionary(rows),
                source_hashes=hashes,n=197,groups=len(groups),m351_groups=len(old_groups),
                group_sizes=dict(Counter(Counter(r['group'] for r in rows).values())),
                source_group_policy='Original IDs preserved; stronger M3.5.3 publication/URL/key/hash/exact-observable-team connected groups used for validation',
                no_sp_application_records_used=0)
