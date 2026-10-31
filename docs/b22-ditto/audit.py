"""Read-only frozen B22 audit. No decoding, OCR, StateEngine replay or repairs."""
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from battle_artifacts import BattleArtifacts

RUN = 'fresh-b22-ditto-20261030-v1'
OWNER = BattleArtifacts('sample_battle_22', ROOT)
PROD = OWNER.cache('event-driven/' + RUN)
BENCH = OWNER.cache('fresh-benchmark/' + RUN)
OUT = BENCH / 'diagnosis'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save(name, value):
    path = OUT / name
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def brief(h):
    e = h['event']
    resolved = h['bindings'].get('resolved_event') or e
    return dict(event_id=e['event_id'], timestamp=e['attributes'].get('observation_time'),
                event_type=e['event_type'], text=e['original_text'], side=resolved['side'],
                status=h['application_status'], reason=h['reason'],
                actor_binding=h['bindings'].get('actor'),
                image=next((x.get('details', {}).get('image') for x in e['evidence']
                            if x.get('details', {}).get('image')), None))


def key(text):
    text = re.sub(r'（优先度\+\d）', '', text)
    return re.sub(r'[\s！!。，,、…：:（）()]', '', text).casefold()


def main():
    OUT.mkdir(exist_ok=True)
    checks = {}
    for name in ['initial-freeze.json', 'production-source-guard.json', 'b16-b21-protected.json']:
        guard = read(BENCH / name)
        for path, expected in guard['files'].items():
            assert sha(ROOT / path) == expected, path
        checks[name] = len(guard['files'])
    reference_guard = read(OUT / 'log-reference-freeze.json')
    assert sha(ROOT / reference_guard['path']) == reference_guard['sha256']
    execution = read(BENCH / 'execution.json')
    manifest = read(PROD / 'manifest.json')
    replay = read(PROD / 'replay.json')
    observations = read(PROD / 'observations.json')
    prediction = read(PROD / 'video-only.json')
    projection = read(BENCH / 'hp-resolutions.json')
    summary = read(OWNER.report('event-driven/' + RUN + '/summary.json'))
    history = replay['history']
    assert len(history) == len(prediction['events']) == len(prediction['receipts']) == 2212
    assert not any(k in manifest['identity'] for k in ['frame_cache', 'recognition_caches', 'recognition_stage_source'])
    assert manifest['identity']['sample_fps'] == 2 and manifest['identity']['identity_mode'] == 'lightweight'
    assert manifest['status'] == 'complete' and len(execution['attempts']) == 1
    memberships = [eid for ep in projection['episodes'] for eid in ep['segment_event_ids']]
    numeric = {x['evidence']['event_id'] for p in replay['state']['pokemon'].values()
               for x in p['hp']['observations'] if x.get('delta') and 'unit' in x}
    assert len(memberships) == len(set(memberships)) and set(memberships) == numeric
    counts = manifest['counts']
    metrics = dict(battle_id=OWNER.battle_id, run_id=RUN,
        duration_seconds=execution['input']['duration_seconds'],
        external_cli_wall_seconds=execution['normal_cli_wall_seconds'], PTR=execution['PTR'],
        source_decoded_frames=counts['source_decoded_frames'], sampled_frames=execution['sampled_frames'],
        detailed_inspection_frames=execution['detailed_inspection_frames'],
        ocr_invocations=counts['ocr_invocations_performed'],
        icon_underlying_invocations=counts['icon_invocations_performed'],
        icon_high_level_preview_requests=counts.get('preview_icon_requests', 0),
        StateEngine_replay_seconds=summary['replay_seconds'],
        hp_projection_seconds=read(BENCH / 'projection-stage.json')['wall_seconds'],
        events=len(prediction['events']), receipts=len(history),
        reconstructed_event_count=summary['reconstructed_event_count'],
        event_types=dict(Counter(h['event']['event_type'] for h in history)),
        receipt_statuses=dict(Counter(h['application_status'] for h in history)),
        deferred_reasons=dict(Counter(h['reason'] for h in history if h['application_status'] == 'deferred')),
        conflicts=replay['state']['conflicts'],
        hp=dict(episodes=len(projection['episodes']), complete_endpoints=sum(bool(e['complete_endpoints']) for e in projection['episodes']),
                attribution_statuses=dict(Counter(e['attribution_status'] for e in projection['episodes'])),
                nonzero_segments=len(numeric), unmapped_changes=len(projection['unmapped_changes']),
                exact_segment_membership=True),
        acceptance='Descriptive production counts; no whole-match accuracy or semantic acceptance measured.')
    save('metrics.json', metrics)
    ditto = {}
    for pid, p in replay['state']['pokemon'].items():
        if (p['original_identity'].get('value') or {}).get('species_id') != 132:
            continue
        ditto[pid] = dict(species=p['species'], original_identity=p['original_identity'],
            current_variant=p['current_variant'], transformations=p['transformations'],
            current_types=p['current_types'], item=p['item'], ability=p['ability'],
            stages=p['stages'], moves=p['moves'], hp=p['hp'], location=p['location'])
    episodes = [{k:ep.get(k) for k in ['episode_id','instance_id','side','species_id','start','slot',
                 'persistent_identity_status','possible_prior_instance_ids','distinct_biological_individual_asserted']}
                for ep in replay['state']['knowledge']['active_entry_episodes']]
    groups = [{k:g.get(k) for k in ['id','first_time','last_time','emitted','interpretation_time','observations']}
              for g in observations['occurrences'] if any('变身成了' in x['raw_text'] for x in g['observations'])]
    assert len(groups) == 2 and all(not g['emitted'] for g in groups)
    assert all(x['event_type'] == 'unknown' for g in groups for x in g['observations'])
    assert len(ditto) == 2 and all(not p['transformations'] for p in ditto.values())
    related = [brief(h) for h in history if '百变怪' in h['event']['original_text'] or '变身' in h['event']['original_text']]
    save('ditto-audit.json', dict(instances=ditto, entry_episodes=episodes,
                                transformation_message_occurrences=groups, receipts=related))
    reference = read(ROOT / 'docs/b22-ditto/log-reference.json')
    comparisons = []
    for ref in reference['rows']:
        matches = [brief(h) for h in history if h['event']['event_type'] not in {'hud_observation','entry_observation'}
                   and key(h['event']['original_text']) == key(ref['text'])]
        comparisons.append(dict(reference_id=ref['reference_id'], turn=ref['turn'], text=ref['text'],
            exact_text_candidates=matches,
            verdict='Candidates for review only; repeated text across turns is not occurrence alignment. HP rows require endpoint checks.'))
    save('log-text-candidates.json', dict(method='Whitespace/punctuation/priority removal then exact text match; no semantic score.', rows=comparisons))
    checks.update(video_sha256=sha(OWNER.video()), reference_rows=len(reference['rows']),
                  no_cross_run_recognition=True, single_production_attempt=True,
                  event_receipt_counts_equal=True, hp_segment_membership_exact=True,
                  production_sources_unchanged=True, prior_battle_metadata_unchanged=True)
    assert checks['video_sha256'] == execution['input']['sha256']
    save('integrity.json', checks)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print('Integrity checks:', json.dumps(checks, ensure_ascii=False))


if __name__ == '__main__':
    main()
