"""Export saved M2.2 snapshots as an inspectable, offline transition timeline."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

MISSING = {'timeline_missing': True}


def field_diff(before, after, path=()):
    """Lossless leaf differences; lists are atomic to retain ordering/context."""
    if isinstance(before, dict) and isinstance(after, dict) and before != MISSING and after != MISSING:
        result = []
        for key in sorted(before.keys() | after.keys()):
            result.extend(field_diff(before.get(key, MISSING), after.get(key, MISSING), path + (key,)))
        return result
    if before == after:
        return []
    return [{'path': list(path), 'before': deepcopy(before), 'after': deepcopy(after)}]


def is_fact(value):
    return isinstance(value, dict) and 'knowledge' in value and 'value' in value


def semantic_diff(before, after, path=()):
    """Separate meaningful value changes from provenance/ledger bookkeeping."""
    if is_fact(before) or is_fact(after):
        b = before if is_fact(before) else {'value': None, 'knowledge': 'unknown'}
        a = after if is_fact(after) else {'value': None, 'knowledge': 'unknown'}
        if (b['value'], b['knowledge']) == (a['value'], a['knowledge']):
            return []
        # Revealed identity, stage bounds, and unknown -> known are knowledge.
        knowledge_field = any(k in path for k in ('species', 'original_identity', 'current_variant',
            'identity', 'current', 'known_slots', 'interval', 'remaining_available'))
        # HP.current is a physical endpoint, whereas ability.current is a revelation.
        if 'hp' in path and path[-1] == 'current':
            knowledge_field = False
        gameplay_field = any(k in path for k in ('location', 'fainted', 'active', 'active_slots',
            'hp', 'major_status', 'turn', 'phase', 'kind', 'resources', 'hazards', 'stages'))
        category = 'gameplay' if gameplay_field and not knowledge_field else 'knowledge'
        if a['value'] == b['value'] or a['knowledge'] == 'conflicting' or b['knowledge'] == 'conflicting':
            category = 'knowledge'
        return [{'path': list(path), 'category': category, 'before': deepcopy(b), 'after': deepcopy(a)}]
    if (isinstance(before, dict) and before != MISSING) or (isinstance(after, dict) and after != MISSING):
        b = before if isinstance(before, dict) and before != MISSING else {}
        a = after if isinstance(after, dict) and after != MISSING else {}
        result = []
        for key in sorted(b.keys() | a.keys()):
            if key in {'provenance', 'alternatives', 'pokemon_instance_id', 'side_id', 'battle_id',
                       'party_instance_ids', 'fainted_instance_ids', 'vacant_slots', 'initiated_by', 'last_tick'}:
                continue
            result.extend(semantic_diff(b.get(key, MISSING), a.get(key, MISSING), path + (key,)))
        return result
    if before == after:
        return []
    if isinstance(before, list) or isinstance(after, list):
        b = before if isinstance(before, list) else []
        a = after if isinstance(after, list) else []
        if strip_evidence(b) == strip_evidence(a):
            return []
        category = 'observation' if path and path[-1] in {'observations', 'hit_observations'} else 'knowledge'
        if path and (path[-1] == 'executed' or ('stages' in path and path[-1] == 'changes')):
            category = 'gameplay'
        if path and path[-1] == 'conflicts':
            category = 'knowledge'
        return [{'path': list(path), 'category': category,
                 'before': deepcopy(before), 'after': deepcopy(after)}]
    category = 'gameplay' if 'active_slots' in path else 'knowledge'
    return [{'path': list(path), 'category': category, 'before': deepcopy(before), 'after': deepcopy(after)}]


def strip_evidence(value):
    if isinstance(value, dict):
        return {k: strip_evidence(v) for k, v in value.items()
                if k not in {'evidence', 'provenance', 'event_id', 'knowledge_snapshot'}}
    if isinstance(value, list):
        return [strip_evidence(v) for v in value]
    return value


def state_hash(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def build_timeline(history, initial, snapshots, final=None):
    """Require chronological prefix snapshots, not arrival-order replay artifacts."""
    ids = [r['event']['event_id'] for r in history]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate logical event IDs in history')
    snap_ids = [s['event_id'] for s in snapshots]
    if len(snap_ids) != len(set(snap_ids)) or set(snap_ids) != set(ids):
        raise ValueError('Snapshots must match history event IDs exactly')
    domains = {r['ordering']['domain'] for r in history if r.get('ordering')}
    if len(domains) > 1:
        raise ValueError('Cannot display incomparable ordering domains chronologically')
    records = sorted(history, key=lambda r: (0, tuple(r['ordering']['key']))
                     if r.get('ordering') else (1, (r['delivery_index'],)))
    by_id = {s['event_id']: s for s in snapshots}
    entries = [{'sequence': 0, 'turn': initial['turn']['value'], 'event': None,
                'application_status': 'initial', 'before': None, 'after': deepcopy(initial),
                'changes': [], 'raw_changes': [], 'classification': 'initial'}]
    before = initial
    for sequence, record in enumerate(records, 1):
        e = record['event']; snapshot = by_id[e['event_id']]; after = snapshot['state']
        digest = state_hash(after)
        if snapshot.get('state_hash') != digest or (record.get('state_hash') and record['state_hash'] != digest):
            raise ValueError('Snapshot hash disagrees with state/history: ' + e['event_id'])
        if snapshot['application_status'] != record['application_status']:
            raise ValueError('Snapshot application status disagrees with history')
        changes = semantic_diff(before, after)
        gameplay = any(c['category'] == 'gameplay' for c in changes)
        classification = ('gameplay' if gameplay else 'observation_only'
                          if record['application_status'] == 'recorded_observation' else 'knowledge'
                          if changes else 'no_change')
        turns = {v['details'].get('turn') for v in e['evidence'] if v['details'].get('turn') is not None}
        turn = next(iter(turns)) if len(turns) == 1 else None if turns else after['turn']['value']
        entries.append({'sequence': sequence, 'turn': turn, 'event': deepcopy(e),
                        'application_status': record['application_status'], 'reason': record.get('reason'),
                        'bindings': deepcopy(record.get('bindings', {})), 'classification': classification,
                        'before': deepcopy(before), 'after': deepcopy(after), 'changes': changes,
                        'raw_changes': field_diff(before, after)})
        before = after
    if final is not None and before != final:
        raise ValueError('Final timeline state does not match serialized replay state')
    return {'schema_version': 1, 'battle_id': initial['battle_id'], 'entries': entries,
            'notes': ['Observation-only means no gameplay transition; evidence ledgers may change.',
                      'Values are last observed or derived facts, not continuous monitoring.',
                      'Unordered events appear after ordered events in delivery order.']}


def render_html(timeline):
    template = (Path(__file__).parent / 'templates/state_timeline.html').read_text()
    # Escaping prevents embedded text from closing the inert JSON script element.
    data = json.dumps(timeline, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    data = data.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    return template.replace('__TIMELINE_DATA__', data)
