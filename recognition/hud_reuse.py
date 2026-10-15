"""Exact crop equivalence reuses OCR; no perceptual similarity or clock expiry."""
from copy import deepcopy
import hashlib
from recognition import box


def digest(image,bounds):
    x,y,X,Y=bounds;crop=image[y:Y,x:X]
    return hashlib.sha256(crop.tobytes()).hexdigest() if crop.size else None


def reuse(prior,prior_image,row,image):
    """A new source frame may directly re-observe unchanged name/icon/HP pixels.

    This proves only sampled display equivalence, never biological individual
    identity or continuous coverage between sampled timestamps.
    """
    snapshot=deepcopy(prior['snapshot']);kept=[]
    for mon in snapshot.get('pokemon',[]):
        slot=mon['slot']
        if '_active_' not in slot:continue
        side='self' if slot.startswith('own') else 'opponent';index=int(slot[-1])-1
        offset=index*(.168 if side=='self' else .166)
        species=mon.get('species') or {};icon=mon.get('icon') or {};hp=mon.get('hp') or {}
        regions=[species.get('region'),icon.get('region'),hp.get('region')]
        # Own HP's combined observation region is insufficient to include every
        # numeric source cell; explicitly cover the complete ratio area.
        if side=='self':regions[-1]=box(image,(.176+offset,.915,.243+offset,.955))
        if any(not b or digest(prior_image,b)!=digest(image,b) for b in regions):continue
        mon['sample_equivalence']=dict(anchor_sha256=prior['sha256'],source_sha256=row['sha256'],regions=regions,
            region_sha256=[digest(image,b) for b in regions],basis='exact name/icon/HP crop bytes; sampled frame only')
        kept.append(mon)
    if not kept:return None
    snapshot.update(source=row['source_id'],timestamp=row['timestamp'],capture_metadata=deepcopy(row),pokemon=kept)
    return snapshot
