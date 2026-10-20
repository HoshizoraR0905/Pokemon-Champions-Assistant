"""Known publication identities, without equating arbitrary compatible designs.

Only explicit source identity, paste ID or replica code links a family. A richer
assertion can represent its compatible partial copies; conflicts are retained and
excluded from this estimator until resolved. No stored source record is filled.
"""
import json


def _dominates_member(a,b):
    if a==b:return True
    x=a['normalized'];y=b['normalized']
    if a['issues'] or b['issues']:return False
    for field in ('species','item','ability','nature'):
        if y[field] is not None and x[field]!=y[field]:return False
    if None in y['moves'] or not set(y['moves'])<=set(x['moves']):return False
    if any(v is not None for v in y['sp']['values']):
        if x['sp']['kind']!=y['sp']['kind']:return False
        if any(v is not None and u!=v for u,v in zip(x['sp']['values'],y['sp']['values'])):return False
    if any(v is not None and x['configuration'].get(k)!=v for k,v in y['configuration'].items()):return False
    return a['original'].get('unsupported_fields',[])==b['original'].get('unsupported_fields',[])


def _dominates(a,b):
    if len(a['members'])!=len(b['members']):return False
    def match(left,right):
        if not left:return not right
        return any(_dominates_member(left[0],m) and match(left[1:],right[:i]+right[i+1:]) for i,m in enumerate(right))
    return not a['conflicts'] and not b['conflicts'] and match(a['members'],b['members'])


def families(rows):
    """Return (representative, source publications) and an explicit exclusion audit."""
    parent=list(range(len(rows)));seen={}
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    def union(i,j):parent[find(i)]=find(j)
    for i,r in enumerate(rows):
        metadata=json.loads(r['original']).get('metadata',{})
        keys=[('publication',r['source_key'])]
        for field in ('paste_id','replica_code','rental_code'):
            value=metadata.get(field)
            if value:
                normalized=str(value).strip()
                if field!='paste_id':normalized=normalized.upper()
                keys.append(('replica_code' if field=='rental_code' else field,normalized))
        for key in keys:
            key=(r['source_id'],r['regulation'],r['format'],*key)
            if key in seen:union(i,seen[key])
            else:seen[key]=i
    groups={}
    for i,r in enumerate(rows):groups.setdefault(find(i),[]).append(r)
    result=[];audit=dict(linked_families=[],conflicting_families=[],dominated_publication_records=0)
    for group in groups.values():
        if len(group)==1:result.append((group[0],group));continue
        data={r['id']:json.loads(r['canonical']) for r in group}
        candidates=[r for r in group if all(_dominates(data[r['id']],data[s['id']]) for s in group)]
        links=[dict(publication_id=r['id'],source_key=r['source_key'],source_url=r['source_url']) for r in group]
        if not candidates:
            audit['conflicting_families'].append(dict(publications=links,
                reason='Known publication identity has conflicting or incomparable assertions; no arbitrary source or field is selected'))
            continue
        representative=min(candidates,key=lambda r:r['id'])
        result.append((representative,[representative]+[r for r in group if r['id']!=representative['id']]))
        audit['linked_families'].append(dict(representative_publication_id=representative['id'],publications=links))
        audit['dominated_publication_records']+=len(group)-1
    return result,audit
