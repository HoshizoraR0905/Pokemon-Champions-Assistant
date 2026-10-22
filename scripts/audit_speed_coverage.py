"""Build a conservative ordering receipt from pinned executable references.

No fetching. Callback-bearing moves require review; absent entries stay unknown.
This certifies ordering only, never learnability or automatic effect execution.
"""
import hashlib
import json
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from knowledge import KnowledgeBase

ROOT = Path(__file__).resolve().parents[1]
# Redirection callbacks for Follow Me / Rage Powder do not alter the action queue.
REVIEWED = set('Weather Ball|Light Screen|Reflect|Encore|Parting Shot|Earth Power|Flare Blitz|Psyshock|Spirit Break|Snarl|Dragon Pulse|Soak|Hurricane|Follow Me|Rage Powder'.split('|'))
NEUTRAL = set('Stamina|Sturdy|Intimidate|Frisk|Swarm|Adaptability|Rough Skin|Sand Veil|Intrepid Sword|Water Absorb|Rock Head|Sheer Force|Mold Breaker|Good as Gold|Competitive|Defiant|Clear Body|Inner Focus|Solid Rock|Filter|Flame Body|Levitate|Sand Force'.split('|'))
SPECIAL = set('After You|Quash|Instruct|Copycat|Sleep Talk|Metronome|Me First|Nature Power|Assist|Dancer|Shell Trap|Beak Blast|Focus Punch|Pursuit|Sucker Punch|Upper Hand'.split('|'))


def entries(path):
    return {re.search(r'\bname: "([^"]+)"', m[2])[1]: m[2]
            for m in re.finditer(r'^\t(\w+): \{\n(.*?)^\t\},', path.read_text(), re.M | re.S)
            if re.search(r'\bname: "([^"]+)"', m[2])}


def build():
    kb = KnowledgeBase()
    paths = [ROOT / '.cache/m321/sources/moves.ts',
             ROOT / '.cache/m341-actions/sources/ps-data-abilities.ts',
             ROOT / '.cache/m322/sources/champions-moves.ts']
    moves, abilities = map(entries, paths[:2])
    overrides = {m[1]:m[2] for m in re.finditer(r'^\t(\w+): \{\n(.*?)^\t\},', paths[2].read_text(), re.M | re.S)}
    result = dict(version=1, profile='showdown-champions-reference-v1',
                  attribution='Pokémon Showdown contributors; MIT',
                  revision='3a766f2cfb5e51c1e428cfe87d0dba91a8f01640',
                  scope='Pinned reference ordering, not independent Champions certification or learnability',
                  sources={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                  moves={}, neutral_abilities=[])
    for e in kb.by_kind['move']:
        label = e.names['en']; body = moves.get(label)
        if body is None:
            continue
        key = re.sub('[^a-z0-9]', '', label.lower())
        override = overrides.get(key, '')
        flags_match = re.search(r'^\t\tflags: \{([^}]*)\}', body, re.M)
        flags = re.findall(r'(\w+): 1', flags_match[1]) if flags_match else []
        callbacks = sorted(set(re.findall(r'\b(on\w+|\w+Callback)\s*\(', body)))
        special = label in SPECIAL or bool(set(flags) & {'charge', 'recharge'}) or 'twoTurnMove' in body or 'lockedmove' in body
        supported = not special and (not callbacks or label in REVIEWED)
        # Champions callbacks replace inherited semantics; unaudited overrides
        # are withheld. Reviewed Encore changes a pending selected move; its own
        # priority is ordinary, its target action must be independently resolved.
        if re.search(r'\bon\w+\s*\(', override) and label not in REVIEWED:
            supported = False
        fact = kb.facts['moves'].get(e.canonical_id, {})
        priority = re.search(r'^\t\tpriority: (-?\d+)', body, re.M)
        override_priority = re.search(r'^\t\tpriority: (-?\d+)', override, re.M)
        priority = override_priority or priority
        if not priority or fact.get('priority') != int(priority[1]):
            supported = False
        result['moves'][label] = dict(supported=supported, flags=flags, callbacks=callbacks,
            category='special_or_multiturn' if special else 'ordinary_with_explicit_effects' if supported else 'unaudited_callbacks',
            pivot='selfSwitch: true' in body, speed_side_effect=bool(re.search(r'\bspe:', body)),
            champions_override=bool(override), effects='Explicit source changes required; selected-action replacement is not automatically simulated')
        result['moves'][label].update(catalog_priority=fact.get('priority'),
            reference_priority=int(priority[1]) if priority else None,
            priority_conflict=bool(priority and fact.get('priority')!=int(priority[1])))
    result['neutral_abilities'] = sorted(label for label in NEUTRAL if label in abilities)
    return result


if __name__ == '__main__':
    path = ROOT / 'speed_order/data/ordering-coverage-v1.json'
    path.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n')
    print(path)
