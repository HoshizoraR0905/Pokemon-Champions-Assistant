"""Small source-specific HP-resolution supplement to existing canonical knowledge.

These assertions select compatible observed effects; they never calculate HP,
assert activation, infer equipped moves, or supply probabilities.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path

PATH=Path(__file__).parent/'data/52poke-resolution-v1.json'


@lru_cache(maxsize=1)
def supplement():
    raw=PATH.read_bytes();data=json.loads(raw)
    if data['schema_version']!=1 or data['game']!='Champions':raise ValueError('Unsupported resolution supplement')
    rules={r['canonical_id']:r for r in data['assertions']}
    if len(rules)!=len(data['assertions']):raise ValueError('Duplicate source assertions')
    return data,rules,hashlib.sha256(raw).hexdigest()


def query(kb, canonical_id):
    data,rules,digest=supplement()
    row=rules.get(canonical_id);identity=kb.entities.get(canonical_id)
    if not row or not identity:return None
    if identity.kind!=row['kind']:raise ValueError('Resolution supplement canonical kind mismatch')
    result=deepcopy(row)
    result.update(supplement_id=data['supplement_id'],supplement_sha256=digest,
                  license=data['license'],attribution=data['attribution'])
    return result
