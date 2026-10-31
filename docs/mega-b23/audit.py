"""Read-only B23 review stages; never decodes video, runs OCR, or replays state."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from recognition.video_sampling import atomic_json

RUN = 'mega-b23-20261030-v1'
BASE = ROOT / '.cache/battles/sample_battle_23'
PROD = BASE / 'event-driven' / RUN
BENCH = BASE / 'fresh-benchmark' / RUN
OUT = Path(__file__).resolve().parent


def read(p):
    return json.loads(p.read_text())


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def sealed(p):
    freeze = read(BENCH / 'initial-freeze.json')
    assert freeze['status'] == 'sealed'
    assert sha(p) == freeze['files'][str(p.relative_to(ROOT))], p
    return read(p)


def log_index():
    # Only UI classifications, timing and image provenance. Do not read events,
    # selected messages, OCR contents, receipts or final state before reference.
    sealed(PROD / 'adaptive-multi-hit.json')
    adaptive_folder = BASE / 'hp-resolution-sampling' / (RUN + '-adaptive-multi-hit')
    adaptive_guard = BENCH / 'adaptive-freeze.json'
    if not adaptive_guard.exists():
        atomic_json(adaptive_guard, dict(files={str(p.relative_to(ROOT)):sha(p)
            for p in sorted(adaptive_folder.rglob('*')) if p.is_file()},
            note='Separate production adaptive output namespace; sealed before prediction review.'))
    rows = sealed(PROD / 'observations.json')['observations']
    frames = [dict(source_id=r['source_id'], timestamp=r['timestamp'],
                   image=r['image'], sha256=r['sha256'])
              for r in rows if r['ui'].get('overlay') == 'battle_log_overlay']
    windows = []
    for frame in frames:
        if not windows or frame['timestamp'] - windows[-1]['end'] > 1.1:
            windows.append(dict(start=frame['timestamp'], end=frame['timestamp'], frames=0))
        windows[-1]['end'] = frame['timestamp']
        windows[-1]['frames'] += 1
    atomic_json(BENCH / 'log-frame-index.json', dict(frames=frames, windows=windows,
        method='UI overlay classification only; no prediction text inspected'))
    print(json.dumps(dict(windows=windows, frames=len(frames)), indent=2))


def metrics():
    replay = sealed(PROD / 'replay.json')
    projection = sealed(BENCH / 'hp-resolutions.json')
    execution = sealed(BENCH / 'execution.json')
    manifest = sealed(PROD / 'manifest.json')
    summary = read(ROOT / 'reports/battles/sample_battle_23/event-driven' / RUN / 'summary.json')
    history = replay['history']; state = replay['state']
    deferred = [h for h in history if h['application_status'] == 'deferred']
    def short(h):
        e = h['bindings'].get('resolved_event') or h['event']
        return dict(event_id=e['event_id'], timestamp=e['attributes'].get('observation_time'),
                    type=e['event_type'], text=e['original_text'], status=h['application_status'],
                    reason=h['reason'], bindings=h['bindings'])
    atomic_json(BENCH / 'deferred-diagnostics.json', [short(h) for h in deferred])
    instances = []
    for pid, p in state['pokemon'].items():
        m = p['mechanics'].get('battle_stats', {}).get('current', {})
        instances.append(dict(instance_id=pid, side=p['side_id'],
            original=p['original_identity']['value'], current_variant=p['current_variant']['value'],
            hp={k:p['hp'][k]['value'] for k in ['current','maximum','displayed_percent']},
            item=p['item']['identity']['value'],
            calculated_stats={k:v['value'] for k,v in m.items()},
            transformations=[dict(event_id=t.get('event_id'), mechanic=t.get('mechanic'),
                                   form=t.get('form')) for t in p['transformations']]))
    episodes = projection['episodes']
    adaptive = sealed(PROD / 'adaptive-multi-hit.json') if (PROD / 'adaptive-multi-hit.json').exists() else {}
    dense_path = BASE / 'hp-resolution-sampling' / (RUN + '-adaptive-multi-hit') / 'episodes-with-dense-hits.json'
    if dense_path.exists():
        assert sha(dense_path) == read(BENCH/'adaptive-freeze.json')['files'][str(dense_path.relative_to(ROOT))]
        dense = read(dense_path)
    else:
        dense = None
    details = []
    for ep in (dense or projection)['episodes']:
        if ep.get('hit_resolution', {}).get('hit_count') or ep.get('hit_resolution', {}).get('is_multi_hit'):
            details.append(ep)
    atomic_json(BENCH / 'multi-hit-diagnostics.json', dict(adaptive=adaptive, episodes=details,
        note='Dense outputs are separate from the baseline HP projection.'))
    result = dict(run_id=RUN, performance=execution, production_counts=manifest['counts'],
        production_summary=summary,
        event_types=dict(Counter(h['event']['event_type'] for h in history)),
        receipt_statuses=dict(Counter(h['application_status'] for h in history)),
        deferred_reasons=dict(Counter(h['reason'] for h in deferred)),
        conflicts=state['conflicts'],
        hp=dict(episodes=len(episodes), complete_endpoints=sum(e['complete_endpoints'] for e in episodes),
                attribution_statuses=dict(Counter(e['attribution_status'] for e in episodes)),
                hit_statuses=dict(Counter(e.get('hit_resolution',{}).get('per_hit_status') for e in episodes)),
                projection_stage=sealed(BENCH / 'projection-stage.json')),
        team_profile_linkage=state['knowledge'].get('team_profile_linkage'),
        configured_instances=list(state['knowledge'].get('team',{}).get('instances',{})),
        instances=instances, adaptive=dict(planned_windows=adaptive.get('planned_windows'),
            completed=adaptive.get('completed'), dense_episode_ids=adaptive.get('dense_episode_ids')),
        accuracy_measured=False)
    atomic_json(OUT / 'benchmark-summary.json', result)
    print(json.dumps({k:result[k] for k in ['receipt_statuses','deferred_reasons','hp','adaptive']}, ensure_ascii=False, indent=2))


def verify():
    freeze = read(BENCH / 'initial-freeze.json')
    guard = read(BENCH / 'b16-b22-protected.json')
    files = dict(guard['files'])
    files.update(read(BENCH / 'adaptive-freeze.json')['files'])
    for name, expected in freeze['files'].items():
        assert name not in files or files[name] == expected
        files[name] = expected
    manifest = read(PROD / 'manifest.json')
    files.update(manifest['identity']['sources'])
    files.update(manifest['outputs'])
    files[execution_video := str(Path(read(BENCH/'execution.json')['input']['path']).relative_to(ROOT))] = manifest['identity']['video_sha256']
    began = time.perf_counter()
    checkpoint = BENCH / 'integrity-verification.json'
    atomic_json(checkpoint, dict(status='running', checked=0, total=len(files)))
    try:
        for n, (name, expected) in enumerate(files.items(), 1):
            assert sha(ROOT / name) == expected, name
            if n % 2000 == 0:
                atomic_json(checkpoint, dict(status='running', checked=n, total=len(files)))
                print('Integrity', n, '/', len(files), flush=True)
        atomic_json(checkpoint, dict(status='complete', checked=len(files),
            protected_b16_b22_files=len(guard['files']), first_run_files=len(freeze['files']),
            wall_seconds=time.perf_counter()-began, source_video=execution_video))
    except BaseException as exc:
        atomic_json(checkpoint, dict(status='failed', checked=n-1, error=repr(exc)))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=['log-index','metrics','verify'])
    a = p.parse_args()
    {'log-index':log_index,'metrics':metrics,'verify':verify}[a.stage]()
