"""Score the fixed visible B22 reference against frozen outputs; no replay/OCR.

Alignment below was reviewed per occurrence, including both opening send-outs.
This measures accepted message records, not complete mechanics or state accuracy.
"""
import json
import re

from audit import BENCH, OUT, PROD, ROOT, read, sha


# Reference row -> replay history indices. Never count entry/HUD observations as
# gameplay receipts, and never reuse a receipt for repeated text in later turns.
ALIGNMENT = """
1:19,20 2:22,23 3:24 4:- 5:26 6:27 7:315 8:317 9:318 10:319
11:320 13:327 14:332 15:334 16:339 19:356 20:365 21:366
23:660 24:661 25:662 27:670 28:675 29:676 30:677 31:679 32:680 33:-
34:729 35:731 36:732 37:733 38:734 39:735 40:736 41:737 43:745
44:750 45:752 46:757
48:986 49:988 50:989 51:990 52:991 55:1008 56:1017 57:1020 58:1027 59:1028
61:1200 62:1202 63:1203 64:1204 65:1205 66:1206 67:1207 69:1215
70:1220 71:1225 72:1226 74:1230
75:1351 76:1355 77:1357 78:- 79:1358 80:1359 81:1360 82:1361
83:1362 84:1363 85:1364
87:1595 88:1596 89:1597 90:1598 91:1599 92:1600 93:1601 95:1606
96:1611 97:1619 98:1620 99:1621
100:1888 101:1889 102:1890 105:1900 106:1904 108:1909 109:1914
110:1918 111:1920 112:1925 113:1926 114:1927 116:1937 117:1942
118:1943 120:1947 122:1952 123:1954 124:-
"""
HP_ALIGNMENT = {
    12: 0, 17: 2, 18: 1, 22: 3, 26: 4, 42: 5, 47: 6, 53: 8,
    54: 7, 60: 9, 68: 10, 73: 11, 86: 12, 94: 13, 103: 14,
    104: 14, 107: 15, 115: 16, 119: 17, 121: 18,
}
EXPECTED_TYPES = {
    'send_out': [1, 2, 8, 31, 35, 49, 62, 76, 97, 122],
    'switch_out': [7, 34, 48, 61, 75],
    'ability_activation': [3, 5, 14, 32, 44, 56, 77, 98, 110, 123],
    'weather_change': [6, 71, 99],
    'transformation': [10, 33, 80, 124],
    'move_execution': [11, 16, 23, 25, 29, 36, 38, 40, 50, 52, 63,
                       65, 67, 81, 83, 85, 87, 89, 91, 93, 100, 102, 106, 112],
    'effectiveness': [13, 19, 27, 43, 51, 55, 69, 95, 108, 116],
    'stat_change': [15, 45, 57, 70, 109, 111, 114],
    'item_activation': [21, 46, 59, 72, 118, 120],
    'side_condition_change': [24, 30, 74, 82, 90, 92, 101],
    'faint': [28, 96, 117],
    'move_effect': [4, 9, 20, 37, 39, 41, 58, 64, 66, 78, 79, 88, 113],
    'move_miss': [84],
    'multi_hit': [105],
}


def normalized(text):
    text = re.sub(r'（优先度\+\d）', '', text)
    return re.sub(r'[\s！!。，.,、…：:（）()]', '', text).casefold()


def main():
    reference_path = ROOT / 'docs/b22-ditto/log-reference.json'
    guard = read(OUT / 'log-reference-freeze.json')
    assert sha(reference_path) == guard['sha256']
    freeze = read(BENCH / 'initial-freeze.json')
    # Only read/verify the scored frozen artifacts; no production writes.
    paths = [PROD / 'replay.json', PROD / 'observations.json', BENCH / 'hp-resolutions.json']
    fingerprints = {}
    for path in paths:
        rel = str(path.relative_to(ROOT))
        assert sha(path) == freeze['files'][rel], rel
        fingerprints[rel] = sha(path)
    reference = read(reference_path)['rows']
    replay, observations, projection = [read(path) for path in paths]
    expected_types = {row: kind for kind, rows in EXPECTED_TYPES.items() for row in rows}
    alignment = {int(row): ([] if indices == '-' else list(map(int, indices.split(','))))
                 for row, indices in (pair.split(':') for pair in ALIGNMENT.split())}
    assert set(alignment) == set(expected_types)
    assert set(alignment).isdisjoint(HP_ALIGNMENT)
    assert set(alignment) | set(HP_ALIGNMENT) == set(range(1, len(reference) + 1))
    rows, hp_rows, used = [], [], set()
    cursor = -1
    for number, ref in enumerate(reference, 1):
        if number in HP_ALIGNMENT:
            continue
        receipts = []
        for index in alignment[number]:
            assert index > cursor and index not in used
            h = replay['history'][index]
            event = h['bindings'].get('resolved_event') or h['event']
            assert event['event_type'] == expected_types[number]
            assert normalized(event['original_text']) == normalized(ref['text'])
            assert h['application_status'] in {'applied_candidate', 'applied_partial', 'recorded_observation'}
            used.add(index)
            cursor = index
            attrs = event['attributes']
            receipts.append(dict(history_index=index, event_id=event['event_id'],
                event_type=event['event_type'], side=event['side'], actor=event['actor'],
                target=event['target'], canonical_references=event['canonical_references'],
                fields={k: attrs[k] for k in ['effect', 'mechanic', 'identity', 'stats',
                    'direction', 'stages', 'weather', 'condition', 'change', 'hits',
                    'trainer_display_text', 'actor_instance_id'] if k in attrs},
                observation_time=attrs['observation_time'], application_status=h['application_status']))
        if number in {1, 2}:
            assert len(receipts) == 2 and len({r['actor']['species_id'] for r in receipts}) == 2
        elif receipts:
            assert len(receipts) == 1
        missing = []
        if not receipts:
            missing = [dict(occurrence_id=g['id'], emitted=g['emitted'],
                            first_time=g['first_time'], types=sorted({o['event_type'] for o in g['observations']}))
                for g in observations['occurrences']
                if any(normalized(o['raw_text']) == normalized(ref['text']) for o in g['observations'])]
            # Same Unnerve text occurs twice: disambiguate by reviewed occurrence.
            if number == 4:
                missing = [g for g in missing if g['first_time'] < 200]
            if number == 78:
                missing = [g for g in missing if 500 < g['first_time'] < 600]
            assert len(missing) == 1 and not missing[0]['emitted'] and missing[0]['types'] == ['unknown']
        rows.append(dict(reference_id=ref['reference_id'], turn=ref['turn'], text=ref['text'],
                         matched=bool(receipts), receipts=receipts, missing_occurrences=missing))
    for number, index in HP_ALIGNMENT.items():
        ref = reference[number - 1]
        match = re.fullmatch(r'(.+) HP (\d+)(%?) → (\d+)(%?)', ref['text'])
        name, before, percent, after, _ = match.groups()
        before, after = int(before), int(after)
        unit = 'displayed_percent' if percent else 'absolute'
        ep = projection['episodes'][index]
        pid = ep['affected_instance_id']
        pokemon = replay['state']['pokemon'][pid]
        assert pokemon['original_identity']['value']['name'] == name
        assert pid.split(':')[1] == ('opponent' if percent else 'self')
        # Restrict endpoints to this action's interval, not another identical HP
        # value elsewhere in the match or a different entry instance.
        start = ep['source_event']['time']
        end = ep['resolution_end']['time']
        previous = [o for o in pokemon['hp']['observations'] if o.get('unit') == unit
                    and o['evidence']['sources'][0]['details']['timestamp'] < start]
        obs = previous[-1:] + [o for o in pokemon['hp']['observations'] if o.get('unit') == unit
               and start <= o['evidence']['sources'][0]['details']['timestamp'] <= end]
        pair = next(((a, b) for i, a in enumerate(obs) for b in obs[i + 1:]
                     if a['after'] == before and b['after'] == after), None)
        exact = ep['unit'] == unit and ep['before'] == before and ep['after'] == after
        hp_rows.append(dict(reference_id=ref['reference_id'], turn=ref['turn'], text=ref['text'],
            instance_id=pid, episode_id=ep['episode_id'],
            raw_ordered_endpoints=pair is not None,
            raw_endpoint_event_ids=[o['evidence']['event_id'] for o in pair] if pair else [],
            exact_projection=exact, complete_endpoints=exact and ep['complete_endpoints'],
            program_supported=exact and ep['attribution_status'] == 'supported',
            projection_before=ep['before'], projection_after=ep['after']))
    per_turn = {}
    for turn in range(1, 9):
        local = [r for r in rows if r['turn'] == turn]
        per_turn[turn] = dict(matched=sum(r['matched'] for r in local), total=len(local))
    summary = dict(semantic_records=dict(matched=sum(r['matched'] for r in rows), total=len(rows)),
        move_execution=dict(matched=sum(r['matched'] for r in rows if expected_types[int(r['reference_id'][4:])] == 'move_execution'),
                            total=len(EXPECTED_TYPES['move_execution'])),
        per_turn=per_turn, matched_receipts=len(used), hp_total=len(hp_rows),
        hp={key: sum(r[key] for r in hp_rows) for key in
            ['raw_ordered_endpoints', 'exact_projection', 'complete_endpoints', 'program_supported']})
    result = dict(method='Reviewed chronological one-to-one accepted message record alignment; not full-state accuracy or precision.',
        reference_sha256=sha(reference_path), frozen_inputs=fingerprints, summary=summary,
        limitations=['Codex visual reference, not human reviewed; visible rows only.',
            'Mega reaction notices do not encode stone identity; Garchomp Z form is unresolved.',
            'Accepted partial/revelation-only/observation receipts do not establish applied mechanics.',
            'No turn boundary or precise original-event-time ground truth; no precision denominator.'],
        semantic_rows=rows, hp_rows=hp_rows)
    target = ROOT / 'docs/b22-ditto/log-score.json'
    tmp = target.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(target)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
