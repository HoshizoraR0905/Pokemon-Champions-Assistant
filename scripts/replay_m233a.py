"""M2.3.3-A cache-only fusion. Default is one explicitly selected recording."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from battle_artifacts import BattleArtifacts
from battle_events.schema import BattleEvent, Evidence, stable_id
from scripts.m232_replay import reconstruct
from scripts.validate_m232 import save, digest
from tracking.battle_state import BattleState
from tracking.state_engine import StateEngine, EventRecord, ordering, event_from_dict
from tracking.hidden_state import HiddenEngine
from tracking.state_timeline import build_timeline, render_html, semantic_diff, field_diff, pack_timeline, unpack_timeline
from tracking.pokemon_knowledge import pokemon_knowledge

STEM = 'M2.3.3-A'


def cached_inputs(paths):
    source = paths.cache('m232/observations.json')
    survey = paths.cache('m232/survey.json')
    manifest = json.loads(paths.cache('m232/pipeline-manifest.json').read_text())
    if any(manifest['stages'].get(s, {}).get('status') != 'complete' for s in ('survey', 'recognize')):
        raise ValueError('Completed cached survey and OCR stages required')
    data = json.loads(source.read_text()); surveyed = json.loads(survey.read_text())
    if data['battle_id'] != paths.battle_id or surveyed['battle_id'] != paths.battle_id:
        raise ValueError('Cache ownership mismatch')
    if surveyed['video_fingerprint'] != manifest['video_fingerprint']:
        raise ValueError('Survey fingerprint differs from recorded recognition pipeline')
    identity = manifest['video_fingerprint']; video = ROOT / identity['path']
    if video.exists():
        st = video.stat()
        if st.st_size != identity['size_bytes'] or st.st_mtime_ns != identity['mtime_ns']:
            raise ValueError('Video file metadata changed; do not silently reuse cached evidence')
    sources = [source, survey, paths.cache('m232/pipeline-manifest.json')]
    snapshots = []
    # Existing battle-3 HUD OCR was separate from its raw message/log cache.
    if paths.battle_id == 'sample_battle_3':
        for p in sorted(paths.cache('m223-snapshots').glob('*.json')):
            snap = json.loads(p.read_text()); metadata = snap.get('capture_metadata', {})
            if metadata.get('sha256') and metadata.get('image'):
                snapshots.append(dict(source_id=snap['source'], timestamp=snap['timestamp'],
                    sha256=metadata['sha256'], image=metadata['image'], snapshot=snap))
                sources.append(p)
    return data, snapshots, sources, identity


def events_from_cache(data, extra_snapshots, bid):
    # Keep M2.3.2 message extraction/dedup and parser grammar unchanged.
    streams, _ = reconstruct(data, bid)
    messages = streams['video']
    for e in messages:
        e['attributes'].pop('sequence', None)
        e['attributes'].update(fusion_context=True,
            observation_time=e['evidence'][0]['details']['timestamp'])
    snapshots = {}
    for row in data['observations'] + data.get('additional_cached_observations', []) + extra_snapshots:
        if row.get('snapshot', {}).get('screen') in {'battle_screen', 'move_selection'}:
            snapshots.setdefault((row['source_id'], row['sha256']), row)
    hud = []
    for row in snapshots.values():
        for mon in row['snapshot'].get('pokemon', []):
            slot = mon.get('slot', '')
            if slot not in {'own_active_1', 'own_active_2', 'opponent_active_1', 'opponent_active_2'}:
                continue
            side = 'self' if slot.startswith('own') else 'opponent'
            position = 'left' if slot.endswith('1') else 'right'
            source_key = 'hud:' + row['sha256'] + ':' + slot
            species = deepcopy(mon.get('species') or {})
            attrs = dict(battle_id=bid, slot=position, observation_time=row['timestamp'],
                species=species, icon=deepcopy(mon.get('icon') or {}), hp=deepcopy(mon.get('hp') or {}))
            evidence = Evidence('cached_hud', row['source_id'], [row['sha256']],
                dict(timestamp=row['timestamp'], image=row['image'], frame_sha256=row['sha256'],
                     timestamp_meaning='observed state, not action onset',
                     confidence=species.get('confidence'), resolution_method=(species.get('resolution') or {}).get('method')))
            hud.append(BattleEvent(stable_id(bid,source_key),'hud_observation',side,None,None,
                f"HUD {side}/{position}: {species.get('raw_text','')} @ {row['timestamp']:.3f}s",
                {},None,[evidence],None,'supported',[],attrs).to_dict())
    events = sorted(messages + hud, key=lambda e: (e['attributes']['observation_time'],
        0 if e['event_type'] == 'hud_observation' else 1, e['event_id']))
    for index, e in enumerate(events, 1):
        e['attributes']['sequence'] = index
    return events


def replay(events, bid):
    engine = StateEngine(BattleState(bid)); snapshots = []
    for index, event in enumerate(events):
        engine.history.append(EventRecord(deepcopy(event), index, ordering(event_from_dict(event))))
    def capture(record, state):
        snapshots.append(dict(event_id=record.event['event_id'], application_status=record.application_status,
            state_hash=record.state_hash, state=state.to_dict()))
        if len(snapshots) % 50 == 0:
            print(f'{bid}: chronological replay {len(snapshots)}/{len(events)}',flush=True)
    engine.replay(snapshot_callback=capture)
    envelope = engine.to_dict()
    assert StateEngine.from_dict(envelope).to_dict() == envelope
    # Duplicate delivery must preserve state, history, and provenance exactly.
    for event in events:
        engine.apply(event)
    assert engine.to_dict() == envelope
    timeline = build_timeline(envelope['history'], envelope['initial_state'], snapshots, envelope['state'])
    timeline['mechanic_rules'] = envelope['mechanic_rules']
    hidden = HiddenEngine(); hidden.seed(envelope['initial_state'])
    before = None
    for index, entry in enumerate(timeline['entries']):
        if index:
            record = envelope['history'][index-1]
            effective = deepcopy(record['bindings'].get('resolved_event',record['event']))
            if effective['event_type'] == 'hud_observation' and 'identity' in record['bindings']:
                effective['actor'] = deepcopy(record['bindings']['identity'])
            hidden.apply(effective, instance_id=record['bindings'].get('actor',{}).get('pokemon_instance_id'),
                side=effective['side'], sequence=index, application_status=record['application_status'])
        entry['before'] = before
        entry['after'].setdefault('knowledge', {})['hidden_configuration'] = hidden.projection()
        entry['after']['knowledge']['pokemon_projection'] = pokemon_knowledge(entry['after']['pokemon'], hidden.projection())
        if before is not None:
            entry['changes'] = semantic_diff(before, entry['after'])
            entry['raw_changes'] = field_diff(before, entry['after'])
            entry['classification'] = ('gameplay' if any(c['category']=='gameplay' for c in entry['changes'])
                else 'knowledge' if entry['changes'] else 'no_change')
        before = entry['after']
    assert HiddenEngine.from_dict(hidden.to_dict()).to_dict() == hidden.to_dict()
    assert unpack_timeline(pack_timeline(timeline)) == timeline
    return envelope, hidden.to_dict(), timeline


def metrics(envelope, hidden, timeline):
    hud = [r for r in envelope['history'] if r['event']['event_type']=='hud_observation']
    messages = [r for r in envelope['history'] if r['event']['event_type']!='hud_observation']
    receipts = [r['bindings'].get('hud', {}) for r in hud]
    observed_slots = {}; slot_changes = 0
    for receipt in receipts:
        if receipt.get('status') != 'accepted':
            continue
        key = (receipt['side'],receipt['slot'])
        if key in observed_slots and observed_slots[key] != receipt['species_id']:
            slot_changes += 1
        observed_slots[key] = receipt['species_id']
    revealed = [r for r in messages if r['application_status']=='applied_partial']
    # Current endpoint HUD comparisons include the data just fused, not held-out accuracy.
    endpoints = []
    prefix_states = {e['event']['event_id']:e['after'] for e in timeline['entries'][1:]}
    slots = envelope['state'].get('knowledge',{}).get('hud_fusion',{}).get('slots',{})
    for key, observation in slots.items():
        side, slot = key.split(':'); pid = envelope['state']['sides'][side]['active_slots'].get(slot)
        final_species = envelope['state']['pokemon'][pid]['species']['value']['species_id'] if pid else None
        prefix = prefix_states[observation['event_id']]
        observed_pid = prefix['sides'][side]['active_slots'].get(slot)
        actual = prefix['pokemon'][observed_pid]['species']['value']['species_id'] if observed_pid else None
        superseding = [r['event']['event_id'] for r in envelope['history']
            if r['bindings'].get('resolved_event',r['event'])['event_type'] in {'switch_out','faint'}
            and r['application_status'] in {'applied_candidate','applied_confirmed'}
            and r['bindings'].get('actor',{}).get('pokemon_instance_id')==observed_pid
            and r['event']['attributes'].get('observation_time',-1)>observation['timestamp']]
        endpoints.append(dict(side=side,slot=slot,timestamp=observation['timestamp'],
            observed_species=observation['species_id'], replayed_species=actual,
            final_species=final_species, later_accepted_vacancy_events=superseding,
            status=observation['status'], match=actual==observation['species_id'] if observation['status']=='accepted' else None))
    return dict(hud_observations_eligible=len(hud),hud_identity_status=dict(Counter(r.get('status','rejected') for r in receipts)),
        hud_hp_status=dict(Counter(r.get('hp_status','deferred') for r in receipts)),
        observed_initial_occupancies=len(observed_slots),
        observed_slot_identity_changes=slot_changes,
        slot_identity_change_semantics='different species in successive accepted HUDs for the same side/slot; action timing and cause unknown',
        hp_absolute_observations_applied=sum(r.get('hp_status')=='accepted' for r in receipts),
        hp_percent_observations_applied=sum(r.get('hp_status')=='accepted_percent' for r in receipts),
        move_revelation_observations=len(revealed),distinct_instance_move_revelations=len({
            (r['bindings']['actor']['pokemon_instance_id'],r['bindings']['resolved_event']['canonical_references']['move']['canonical_id']) for r in revealed}),
        move_effects_applied_from_revelation=0,
        standalone_effect_messages_applied=sum(r['event']['event_type'] in {'stat_change','status_change','move_effect'}
            and r['application_status'] in {'applied_candidate','applied_confirmed'} for r in messages),
        message_status=dict(Counter(r['application_status'] for r in messages)),
        unresolved_actor_or_policy_cases=sum(r['application_status'] in {'deferred','rejected'} for r in messages),
        unresolved_targets_retained=sum('target_not_in_entry' in r['event']['uncertainty'] for r in messages),
        semantic_gameplay_entries=sum(e['classification']=='gameplay' for e in timeline['entries'][1:]),
        endpoint_identity_comparisons=endpoints, endpoint_checks_are_fused_input_consistency=True,
        deterministic_replay=True, repeated_delivery_idempotent=True, hidden_roundtrip=True,
        rules_profile=envelope['mechanic_rules']['profile_id'], new_ocr_calls=0, new_decoded_frames=0)


def run(paths):
    data, snapshots, sources, identity = cached_inputs(paths)
    dependencies = [*ROOT.joinpath('tracking').glob('*.py'),ROOT/'tracking/templates/state_timeline.html',
        ROOT/'scripts/replay_m233a.py',ROOT/'scripts/m232_replay.py',ROOT/'battle_events/parser.py',ROOT/'battle_events/schema.py',
        ROOT/'knowledge/data/manifest.json',*ROOT.joinpath('knowledge').glob('*.py'),
        ROOT/'recognition/battle_log.py',ROOT/'scripts/validate_m232.py',*ROOT.joinpath('data').glob('*rules*.json')]
    key = digest({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources+dependencies})
    manifest_path = paths.cache('m233a/pipeline-manifest.json')
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if manifest.get('input_hash') == key and manifest.get('status') == 'complete' and all(
        (ROOT/p).is_file() and hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in manifest.get('outputs',{}).items()) and manifest.get('outputs'):
        print(f'{paths.battle_id}: reused complete fusion checkpoint',flush=True)
        return json.loads(paths.report(f'{STEM}-validation.json').read_text())
    manifest.update(status='running',current_stage='chronological_fusion',battle_id=paths.battle_id,
        input_hash=key,video_fingerprint=identity,recognition_reused=True,
        sampling_policy='unchanged existing cache; 2 FPS target reserved for M2.3.3-B')
    save(manifest_path, manifest)
    try:
        print(f'{paths.battle_id}: using cached observations and {len(snapshots)} historical snapshots',flush=True)
        events = events_from_cache(data,snapshots,paths.battle_id)
        envelope, hidden, timeline = replay(events,paths.battle_id)
        timeline['notes'] += ['Progressive initialization from unknown recording start. HUD time is observation time, not switch time.',
            'Move revelation admits actor and move only; target and effects remain unresolved.',
            'New occupancy episodes are not merged across absences by species or OCR team_instance_id.',
            'Historical reviewed Battle 3 mechanics remain a separate regression oracle; this is automatic cached evidence.']
        result = dict(battle_id=paths.battle_id,input_hash=key,**metrics(envelope,hidden,timeline))
        outputs=[]
        for name,value in [('events',dict(battle_id=paths.battle_id,events=events)),('state',envelope),('hidden-state',hidden),('validation',result)]:
            target=paths.report(f'{STEM}-{name}.json');save(target,value);outputs.append(target)
        target=paths.report(f'{STEM}-timeline.html');target.write_text(render_html(timeline,artifact_root='../../../'));outputs.append(target)
        manifest.update(status='complete',current_stage='complete',outputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in outputs})
        manifest.pop('error',None);save(manifest_path,manifest)
        print(json.dumps(result,ensure_ascii=False),flush=True)
        return result
    except Exception as exc:
        manifest.update(status='failed',error=f'{type(exc).__name__}: {exc}');save(manifest_path,manifest);raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--battle-id',action='append',required=True,help='Explicit recording(s), processed sequentially')
    args=parser.parse_args()
    for bid in args.battle_id:
        run(BattleArtifacts(bid).prepare())
