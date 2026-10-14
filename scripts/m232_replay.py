"""Cache-only reconstruction. Log order and video observation order stay separate."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from battle_events.parser import EventParser, BattleContext
from recognition.battle_log import assemble_views
from tracking.battle_state import BattleState, PokemonState, fact
from tracking.state_engine import StateEngine, EventRecord, event_from_dict, ordering
from tracking.state_timeline import build_timeline, render_html, pack_timeline, unpack_timeline
from tracking.hidden_state import HiddenEngine
from scripts.validate_m232 import ROOT, save, digest

VERSION = 1


def reconstruct(data, bid):
    # Dense historical raw OCR is valid input; identical source frames are read once.
    observations = {}
    for row in data['observations'] + data.get('additional_cached_observations', []):
        key = (row['source_id'], row['sha256'])
        if key not in observations:
            observations[key] = row
        else:
            for name in ('message', 'log', 'snapshot'):
                if name in row:
                    observations[key].setdefault(name, row[name])
    rows = sorted(observations.values(), key=lambda x: (x['timestamp'], x['source_id']))
    parser = EventParser()
    messages = []; previous = None
    for row in rows:
        message = row.get('message')
        if not message or not message['raw_text'].strip():
            previous = None
            continue
        text = ''.join(message['raw_text'].split())
        if previous and previous[0] == text and row['timestamp'] - previous[1] <= 4:
            previous = (text, row['timestamp']); continue
        previous = (text, row['timestamp'])
        messages.append(dict(entry_id='message:' + row['sha256'], raw_text=message['raw_text'],
            ocr_confidence=message['confidence'], source_id=row['source_id'],
            observation_ids=[row['sha256']], timestamp=row['timestamp'], image=row['image']))
    views = [r['log'] for r in rows if r.get('log')]
    logs, issues = assemble_views(views, ignore_partial_overlap=True)
    partial_ids = {r['observation_id'] for v in views for r in v['observations'] if r.get('partial')}
    streams = {}
    for name, entries in [('video', messages), ('log', logs)]:
        events = parser.parse_sequence(entries, BattleContext(), bid)
        for index, (event, entry) in enumerate(zip(events, entries), 1):
            if name == 'video':
                event.attributes['sequence'] = index
                event.evidence[0].source_type = 'video_message'
                event.evidence[0].details.update(timestamp=entry['timestamp'], image=entry['image'],
                    timestamp_meaning='sampled observation; not action onset')
            elif entry['selected_observation_id'] in partial_ids:
                event.uncertainty.append('partial_log_row')
            # Historical log views have no proven placement among live messages.
            event.attributes['reconstruction_stream'] = name
        streams[name] = [e.to_dict() for e in events]
    return streams, dict(log_views=len(views), log_times=[v['timestamp'] for v in views],
        log_turns=sorted({v['turn'] for v in views if v.get('detected')}),
        overlap_issues=issues, raw_observations=len(rows), snapshot_checkpoints=sum('snapshot' in r for r in rows))


def initial_checkpoint(data, bid):
    """Only the first cached, independently resolved active HUD seeds instances."""
    initial = BattleState(bid)
    for row in data['observations']:
        snapshot = row.get('snapshot', {})
        if snapshot.get('screen') not in {'battle_screen','move_selection'}:
            continue
        for mon in snapshot.get('pokemon', []):
            slot = mon.get('slot', '')
            if slot not in {'own_active_1','own_active_2','opponent_active_1','opponent_active_2'}:
                continue
            species = mon.get('species') or {}; resolution = species.get('resolution') or {}
            if species.get('confidence',0) < .75 or resolution.get('status') != 'resolved':
                continue
            if resolution.get('method') != 'text_icon_agreement':
                continue
            ref = {k:resolution[k] for k in ('species_id','canonical_identity','identity_status') if k in resolution}
            if not ref.get('species_id'): continue
            ref.update(canonical_id=f"pokeapi:species:{ref['species_id']}",name=species['value'],kind='species')
            side = 'self' if slot.startswith('own') else 'opponent'
            position = 'left' if slot.endswith('1') else 'right'
            pid = f'{bid}:{slot}:initial'
            provenance = dict(source_id=row['source_id'],frame_sha256=row['sha256'],image=row['image'],
                timestamp=row['timestamp'],basis='cached_text_icon_agreement')
            pokemon = PokemonState(pid,side)
            pokemon.species=fact(ref,provenance);pokemon.original_identity=fact(ref,provenance)
            if ref.get('canonical_identity'):pokemon.current_variant=fact(ref['canonical_identity'],provenance)
            pokemon.location=fact(dict(kind='active',slot=position),provenance)
            hp=mon.get('hp') or {};value=hp.get('value') or {}
            if hp.get('confidence',0)>=.75 and isinstance(value,dict) and 0<=value.get('current',-1)<=value.get('maximum',-1) and value.get('maximum',0)>0:
                pokemon.hp.current=fact(value['current'],provenance);pokemon.hp.maximum=fact(value['maximum'],provenance)
            initial.pokemon[pid]=pokemon
            initial.sides[side].party_instance_ids.append(pid)
            initial.sides[side].active_slots[position]=pid
        if initial.pokemon:return initial,row['timestamp']
    return initial,None


def replay_stream(bid, events, initial=None):
    engine = StateEngine(initial or BattleState(bid))
    for index, event in enumerate(events):
        parsed = event_from_dict(event)
        engine.history.append(EventRecord(event, index, ordering(parsed)))
    snapshots = []
    engine.replay(snapshot_callback=lambda record, state: snapshots.append(dict(
        event_id=record.event['event_id'], application_status=record.application_status,
        state_hash=record.state_hash, state=state.to_dict())))
    # Unordered evidence remains inspectable and cannot mutate the replay state.
    seen = {s['event_id'] for s in snapshots}
    for record in engine.history:
        if record.event['event_id'] not in seen:
            snapshots.append(dict(event_id=record.event['event_id'], application_status=record.application_status,
                state_hash=engine.to_dict()['state_hash'], state=engine.state.to_dict()))
    envelope = engine.to_dict()
    assert StateEngine.from_dict(envelope).to_dict() == envelope
    for event in events:
        engine.apply(event)
    assert engine.to_dict() == envelope
    timeline = build_timeline(envelope['history'], envelope['initial_state'], snapshots, envelope['state'])
    hidden = HiddenEngine(); hidden.seed(envelope['initial_state'])
    prior = None
    for entry in timeline['entries']:
        if entry['event']:
            record = next(r for r in envelope['history'] if r['event']['event_id'] == entry['event']['event_id'])
            hidden.apply(record['event'], instance_id=record['bindings'].get('actor', {}).get('pokemon_instance_id'),
                side=record['event']['side'], sequence=entry['sequence'], application_status=record['application_status'])
        entry['before'] = prior
        entry['after'].setdefault('knowledge', {})['hidden_configuration'] = hidden.projection()
        prior = entry['after']
    assert HiddenEngine.from_dict(hidden.to_dict()).to_dict() == hidden.to_dict()
    assert unpack_timeline(pack_timeline(timeline)) == timeline
    return envelope, hidden.to_dict(), timeline


def run(paths):
    source = paths.cache('m232/observations.json')
    manifest_path = paths.cache('m232/pipeline-manifest.json')
    manifest = json.loads(manifest_path.read_text())
    if any(manifest['stages'].get(s, {}).get('status') != 'complete' for s in ('survey', 'recognize')):
        raise ValueError('Completed survey and recognition checkpoints required')
    data = json.loads(source.read_text())
    if data['battle_id'] != paths.battle_id:
        raise ValueError('Observation ownership mismatch')
    key = digest(dict(observations=hashlib.sha256(source.read_bytes()).hexdigest(),
        code={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
              ['scripts/m232_replay.py','tracking/state_engine.py','tracking/hidden_state.py',
               'tracking/state_timeline.py','tracking/templates/state_timeline.html','battle_events/parser.py','recognition/battle_log.py']}))
    prior = manifest['stages'].get('replay', {})
    if prior.get('input_hash') == key and all((ROOT/p).is_file() and hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in prior.get('outputs', {}).items()) and prior.get('outputs'):
        return json.loads(paths.report('M2.3.2-validation.json').read_text())
    manifest.update(current_stage='replay', status='running');save(manifest_path, manifest)
    try:
        streams, metrics = reconstruct(data, paths.battle_id)
        initial, initial_time = initial_checkpoint(data, paths.battle_id)
        metrics['initial_hud_time'] = initial_time
        metrics['initial_hud_instances'] = len(initial.pokemon)
        for event in streams['video']:
            if initial_time is not None and event['evidence'][0]['details']['timestamp'] < initial_time:
                event['uncertainty'].append('predates_initial_hud_checkpoint')
        save(paths.report('M2.3.2-events.json'), dict(battle_id=paths.battle_id, streams=streams, evidence=metrics))
        outputs = [paths.report('M2.3.2-events.json')]; counts = {}
        for name, events in streams.items():
            envelope, hidden, timeline = replay_stream(paths.battle_id, events, initial if name == 'video' else None)
            timeline['notes'] += ['Partial reconstruction from cached OCR. Unknown slots and ownership remain unresolved.',
                'Video observations and retrospective Battle Log have separate replays; neither is a complete battle.',
                'First resolved HUD seeds video replay; earlier messages are deferred. Later HUDs are retained for independent review.']
            for suffix, value in [('state', envelope), ('hidden-state', hidden)]:
                target=paths.report(f'M2.3.2-{name}-{suffix}.json');save(target,value);outputs.append(target)
            target=paths.report(f'M2.3.2-{name}-timeline.html');target.write_text(render_html(timeline,artifact_root='../../../'));outputs.append(target)
            counts[name] = dict(events=len(events), statuses=dict(Counter(r['application_status'] for r in envelope['history'])),
                reasons=dict(Counter(r['reason'] for r in envelope['history'] if r['reason'])),
                states=len(timeline['entries']), deterministic=True, idempotent=True, timeline_roundtrip=True)
        result=dict(battle_id=paths.battle_id, input_hash=key, streams=counts, evidence=metrics,
            recognition_calls=0, rules_profile='champions-evidence-only-v1',
            coverage='partial; independent semantic validation pending; structural checks passed')
        target=paths.report('M2.3.2-validation.json');save(target,result);outputs.append(target)
        manifest['stages']['replay']=dict(status='complete',input_hash=key,
            outputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in outputs})
        manifest.update(status='complete', rules_profile='champions-evidence-only-v1');manifest.pop('error',None);save(manifest_path,manifest)
        return result
    except Exception as exc:
        manifest.update(status='failed',error=f'{type(exc).__name__}: {exc}');save(manifest_path,manifest);raise
