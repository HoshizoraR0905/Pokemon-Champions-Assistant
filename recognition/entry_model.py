"""Bounded entry-triggered scene-identity probe; no scene classifier installed.

UI sprite correlation is not calibrated for rendered 3D battle models. This
prototype records candidate scope and immutable frames, and always abstains.
Human labels and later HUD readings are deliberately absent from its inputs.
"""
from fractions import Fraction
import hashlib
import math
from pathlib import Path

VERSION='entry-scene-probe-abstain-v1'
# A future adapter must pin its validation artifact and classifier version here.
# No scene-domain classifier is validated by the current UI sprite assets.
VALIDATED_CLASSIFIERS={}


def preview_candidates(rows,side,entry_time):
    by_row={}
    for r in rows:
        t=r.get('evidence',{}).get('timestamp')
        if r.get('side')!=side or type(t) not in (int,float) or t>=entry_time:continue
        by_row.setdefault(r.get('preview_row'),[]).append(r)
    if set(by_row)!=set(range(1,7)):return []
    if any(any(r.get('status')!='resolved' or type(r.get('species_id')) is not int for r in group)
           or len({r['species_id'] for r in group})!=1 for group in by_row.values()):return []
    return sorted({group[0]['species_id'] for group in by_row.values()})


def probe_entry(receipt,rows,preview,root,*,max_frames=4,minimum_delay=2.,maximum_delay=4.):
    """One supported entry -> at most four saved frames, never roster guessing."""
    if not 1<=max_frames<=4 or not 0<=minimum_delay<=maximum_delay<=5:
        raise ValueError('Entry probe must remain bounded to four frames/five seconds')
    e=receipt.get('bindings',{}).get('resolved_event',receipt['event']);a=e['attributes']
    ep=receipt.get('bindings',{}).get('entry_episode')
    if (e['event_type']!='send_out' or not receipt['application_status'].startswith('applied') or not ep
            or ep['entry_event_id']!=e['event_id']):
        raise ValueError('Probe requires an applied entry episode')
    t=a.get('observation_time')
    if type(t) not in (int,float) or not math.isfinite(t):raise ValueError('Finite entry timestamp required')
    candidates=preview_candidates(preview,e['side'],t)
    result=dict(method=VERSION,entry_event_id=e['event_id'],entry_timestamp=t,side=e['side'],
        candidate_species_ids=candidates,candidate_scores=[dict(species_id=sid,score=None) for sid in candidates],
        status='abstained',species_id=None,confidence=None,acceptance_enabled=False,
        reason='scene_domain_classifier_and_calibrated_threshold_unavailable' if candidates else 'reliable_prefix_preview_unavailable',
        evidence_kind='automatic_abstention',recognition_calls=0,frames=[])
    if not candidates:return result
    root=Path(root)
    for r in rows:
        if not minimum_delay<=r['timestamp']-t<=maximum_delay:continue
        path=root/r['image'];actual=hashlib.sha256(path.read_bytes()).hexdigest()
        if actual!=r['sha256']:raise ValueError('Entry frame hash mismatch')
        pts_time=float(r['source_pts']*Fraction(r['source_time_base']))
        if abs(pts_time-r['timestamp'])>1e-6:raise ValueError('Entry source timestamp mismatch')
        result['frames'].append(dict(timestamp=r['timestamp'],source_pts=r['source_pts'],source_time_base=r['source_time_base'],
            source_id=r['source_id'],image=r['image'],sha256=actual,source_timestamp_verified=True))
        if len(result['frames'])==max_frames:break
    return result
