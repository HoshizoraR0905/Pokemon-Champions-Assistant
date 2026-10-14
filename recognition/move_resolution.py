"""Lexical move resolution; similarity proposes hypotheses, never confirmations."""
import re
from difflib import get_close_matches
from knowledge import normalize


def resolve_move(raw, knowledge, alternatives=()):
    token=re.sub(r'\s+','',raw).strip('！!。.,，')
    def exact(text):
        values=knowledge.exact['move'].get(normalize(text),[])
        ids={v.canonical_id for v in values}
        return next(iter(ids)) if len(ids)==1 else None
    primary=exact(token)
    readings=[]
    for a in alternatives:
        t=re.sub(r'\s+','',a.get('text','')).strip('！!。.,，')
        readings.append(dict(a,canonical_id=exact(t)))
    votes={r['canonical_id'] for r in readings if r['canonical_id'] and r.get('confidence',0)>=.9}
    canonical=primary;method='exact_dictionary' if primary else 'unresolved'
    # Repeated preprocessing is correlated: retain both raw readings and identify
    # the result as OCR corroboration, not calibrated confidence or independent frames.
    if not primary and len(votes)==1:
        voters=[r for r in readings if r['canonical_id'] in votes and r.get('confidence',0)>=.9 and r.get('source_sha256') and r.get('config_id')]
        if len({r['config_id'] for r in voters})>=2:
            canonical=next(iter(votes));method='concordant_image_ocr'
    if primary and votes-{primary}:
        canonical=None;method='conflicting_ocr'
    candidates=set(votes)
    if primary:candidates.add(primary)
    if not canonical:
        names={e.names.get('zh-hans'):e.canonical_id for e in knowledge.by_kind['move'] if e.names.get('zh-hans')}
        candidates.update(names[n] for n in get_close_matches(token,names,n=5,cutoff=.5))
    return dict(status='confirmed' if canonical else ('ambiguous' if len(candidates)>1 else 'unresolved'),
        canonical_id=canonical,raw_text=raw,normalized_text=token,method=method,
        candidates=sorted(candidates),alternatives=readings,knowledge_snapshot=knowledge.snapshot_id)
