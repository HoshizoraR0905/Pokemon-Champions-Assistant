"""Two-second reference review and timing evaluation; frozen detectors are read only."""
from pathlib import Path
from fractions import Fraction
import argparse
import html
import json
import math
import os
import time
import cv2
import numpy as np
from battle_artifacts import BattleArtifacts
from speed_inference.offline import atomic_json, file_hash
from .visual_review import source_rows
from .visual_validation import compare, gap, counter_checks

VERSION = 'two-second-reference-v1'


def error_bounds(a, b):
    """Bounds on absolute error for two unknown instants in closed intervals."""
    if any(len(x) != 2 or not all(math.isfinite(v) for v in x) or x[0] > x[1] for x in (a, b)):
        raise ValueError('Invalid time interval')
    return [gap(a, b), max(abs(a[0]-b[1]), abs(a[1]-b[0]))]


def timing(a, b, point):
    lo, hi = error_bounds(a, b)
    return dict(reference_interval=a, prediction_interval=b, interval_compatible=lo <= 2,
                absolute_error_bounds=[lo, hi], point_error_bounds=error_bounds(a, [point, point]),
                prediction_interval_width=b[1]-b[0],
                timing_quality='within_2s' if hi <= 2 else 'outside_2s' if lo > 2 else 'insufficient_localization')


def sample(number, run=None):
    """Fixed zero-anchored grid, selecting cached source PTS without reading labels."""
    started = time.perf_counter()
    if run:
        battle = BattleArtifacts(f'sample_battle_{number}')
        source = battle.cache(f'event-driven/{run}/observations.json')
        data = json.loads(source.read_text()); battle.check_identity(data['battle_id']); rows = data['observations']
    else:
        battle, source, rows = source_rows(number)
    directory = battle.cache('m34-visual-v21/reference-grid'); directory.mkdir(parents=True, exist_ok=True)
    identity = dict(version=VERSION, source=str(source), source_sha256=file_hash(source),
                    sampler_sha256=file_hash(Path(__file__)), step_seconds=2,
                    policy='nearest available cached original source PTS to 0,2,4,...; no prediction/reference/UI input')
    manifest = directory/'manifest.json'
    if manifest.exists():
        old = json.loads(manifest.read_text())
        if old['identity'] == identity and old['status'] == 'complete' and all(Path(f['image']).is_file() and file_hash(f['image']) == f['image_sha256'] for f in old['frames']):
            return old
        raise ValueError('Existing grid invalidated; preserve it and use a new versioned namespace')
    atomic_json(manifest, dict(identity=identity, status='running'))
    frames=[]; sheets=[]; cells=[]
    for target in range(0, math.floor(rows[-1]['timestamp'])+1, 2):
        row=min(rows, key=lambda r:abs(r['timestamp']-target))
        if abs(row['timestamp']-target) > .55:
            raise ValueError(f'Missing grid cell at {target}: targeted acquisition required')
        pts=float(row['source_pts']*Fraction(row['source_time_base']))
        origin = row.get('seek_origin_seconds', row['timestamp']-pts)
        if abs(pts+origin-row['timestamp']) > 1e-7: raise ValueError('Source PTS mismatch')
        # Legacy cached_frames dropped seek origin. Preserve global timestamp and
        # expose the recovered offset rather than calling chunk-local PTS global.
        pts = row['timestamp']
        image=Path(row['image']); im=cv2.imread(str(image))
        if im is None: raise FileNotFoundError(image)
        f={k:row[k] for k in ('timestamp','image','source_id','source_pts','source_time_base')}
        f.update(target_timestamp=target, image_sha256=file_hash(image), index=len(frames),
                 seek_origin_seconds=origin, origin_provenance='source_row' if 'seek_origin_seconds' in row else 'recovered from preserved global timestamp minus chunk PTS'); frames.append(f)
        cell=np.zeros((222,440,3),np.uint8); cell[:202]=cv2.resize(im,(440,202))
        cv2.putText(cell,f'{len(frames)-1:03} | grid {target} | PTS {pts:.3f}',(5,217),cv2.FONT_HERSHEY_SIMPLEX,.48,(255,255,255),1)
        cells.append(cell)
        if len(cells)==24:
            p=directory/f'sheet-{len(sheets):02}.jpg';cv2.imwrite(str(p),np.vstack([np.hstack(cells[i:i+4]) for i in range(0,24,4)]));sheets.append(str(p));cells=[]
        if len(frames)%24==0:atomic_json(manifest,dict(identity=identity,status='running',frames=frames,sheets=sheets))
    if cells:
        while len(cells)%4: cells.append(np.zeros_like(cell))
        p=directory/f'sheet-{len(sheets):02}.jpg';cv2.imwrite(str(p),np.vstack([np.hstack(cells[i:i+4]) for i in range(0,len(cells),4)]));sheets.append(str(p))
    result=dict(identity=identity,status='complete',battle_id=battle.battle_id,frames=frames,sheets=sheets,
                seconds=time.perf_counter()-started,frames_sampled=len(frames),frames_newly_decoded=0,ocr_calls=0,
                storage_bytes=sum(Path(p).stat().st_size for p in sheets),manual_review_items=len(frames))
    atomic_json(manifest,result);return result


def evaluate(reference, prediction):
    result=compare(reference,prediction,tolerance=2.0)
    byid={p['id']:p for p in prediction['visual']['segments']}
    for match in result['matches']:
        p=byid[match['prediction']]
        match.update(timing(match['reference_interval'],p['end'],p['next_command_time']))
    # Association within 10s identifies a late/early counterpart, never a timing pass.
    outside=[];used=set()
    for r in result['missed_reference_boundaries']:
        candidates=[p for p in result['unmatched_predictions'] if p['id'] not in used and gap(r['interval'],p['interval'])<=10]
        if candidates:
            p=min(candidates,key=lambda p:gap(r['interval'],p['interval']));used.add(p['id'])
            outside.append(dict(reference=r['turn_id'],prediction=p['id'],**timing(r['interval'],p['interval'],p['time'])))
    result['outside_tolerance_associations']=outside
    result['counter_checks']=counter_checks(reference,prediction)
    initial=result['initial_anchor']
    if initial['predicted_time'] is not None and initial['reference_interval']:
        # Only a point is exposed for the initial anchor; do not invent its interval.
        initial.update(timing(initial['reference_interval'],[initial['predicted_time']]*2,initial['predicted_time']))
    result['timing_policy']='2s minimum interval distance for compatibility; maximum possible absolute error <=2s for bounded pass; otherwise insufficient localization. Outside associations <=10s are diagnostic only.'
    return result


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',type=int,required=True);p.add_argument('--run');a=p.parse_args()
    r=sample(a.battle,a.run);print(json.dumps({k:r[k] for k in ('battle_id','frames_sampled','seconds','storage_bytes')}))
