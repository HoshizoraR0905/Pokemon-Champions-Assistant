"""Shared historical values behind the mutable state compatibility view.

Committed records are immutable. Trial states copy their reference lists, not
their payloads; a historical revision replaces a record. Legacy exports return
ordinary detached containers. Canonical fragments retain the schema-2 hash.
"""
from copy import deepcopy
from dataclasses import fields, is_dataclass
from functools import lru_cache
import hashlib
import json


def _immutable(*args, **kwargs):
    raise TypeError('Historical evidence is immutable; replace the record')


class EvidenceDict(dict):
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _immutable

    def __deepcopy__(self, memo):
        return self


class EvidenceArray(list):
    __setitem__ = __delitem__ = append = clear = extend = insert = pop = remove = reverse = sort = __iadd__ = __imul__ = _immutable

    def __deepcopy__(self, memo):
        return self


IMMUTABLE = (EvidenceDict, EvidenceArray)


@lru_cache(maxsize=4096)
def _string(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()


def freeze(value):
    if isinstance(value, IMMUTABLE):
        return value
    if is_dataclass(value):
        return EvidenceDict((f.name, freeze(getattr(value, f.name))) for f in fields(value))
    if isinstance(value, dict):
        return EvidenceDict((k, freeze(v)) for k, v in value.items())
    if isinstance(value, list):
        return EvidenceArray(freeze(v) for v in value)
    if isinstance(value, tuple):
        return tuple(freeze(v) for v in value)
    return value


class EvidenceHistory(list):
    """Mutable sequence of references; new records stay editable until seal()."""
    def __init__(self, values=()):
        super().__init__(freeze(v) for v in values)
        self._sealed = len(self)

    def seal(self):
        for i in range(self._sealed, len(self)):
            list.__setitem__(self, i, freeze(self[i]))
        self._sealed = len(self)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._sealed = 0  # replacement/slice edits may revise an older record

    def __delitem__(self, key):
        super().__delitem__(key)
        self._sealed = 0

    def insert(self, index, value):
        super().insert(index, value)
        self._sealed = 0

    def clear(self):
        super().clear()
        self._sealed = 0

    def pop(self, index=-1):
        result = super().pop(index)
        self._sealed = 0
        return result

    def remove(self, value):
        super().remove(value)
        self._sealed = 0

    def reverse(self):
        super().reverse()
        self._sealed = 0

    def sort(self, *args, **kwargs):
        super().sort(*args, **kwargs)
        self._sealed = 0

    def __imul__(self, count):
        super().__imul__(count)
        self._sealed = 0
        return self

    def __deepcopy__(self, memo):
        result = EvidenceHistory()
        memo[id(self)] = result
        list.extend(result, self[:self._sealed])
        list.extend(result, (deepcopy(v, memo) for v in self[self._sealed:]))
        result._sealed = self._sealed
        return result


def export(value):
    """Detached schema-compatible tree, including every historical payload."""
    if is_dataclass(value):
        return {f.name: export(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        return {k: export(v) for k, v in value.items()}
    if isinstance(value, list):
        return [export(v) for v in value]
    if isinstance(value, tuple):
        return tuple(export(v) for v in value)
    return deepcopy(value)


def canonical(value):
    """Exact sorted compact JSON; immutable evidence fragments are cached."""
    if isinstance(value, IMMUTABLE):
        cached = getattr(value, '_canonical', None)
        if cached is None:
            cached = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
            value._canonical = cached
        return cached
    if is_dataclass(value):
        value = {f.name: getattr(value, f.name) for f in fields(value)}
    if isinstance(value, dict):
        def key(k):
            # json.dumps permits scalar mapping keys and quotes them in JSON.
            if isinstance(k, str):
                return canonical(k)
            if k is None or isinstance(k, (int, float, bool)):
                return canonical(json.dumps(k, ensure_ascii=False, separators=(',', ':')))
            raise TypeError('Unsupported JSON mapping key')
        return b'{' + b','.join(key(k) + b':' + canonical(value[k]) for k in sorted(value)) + b'}'
    if isinstance(value, (list, tuple)):
        return b'[' + b','.join(canonical(v) for v in value) + b']'
    if isinstance(value, str):
        return _string(value)
    if value is None:
        return b'null'
    if isinstance(value, bool):
        return b'true' if value else b'false'
    if isinstance(value, int):
        return str(value).encode()
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()


HISTORY_FIELDS = {
    'Fact': ('provenance', 'alternatives'),
    'HPState': ('observations',), 'Stage': ('changes',),
    'ItemState': ('revealed', 'activations', 'changes'),
    'AbilityState': ('revealed', 'modifications'),
    'MoveState': ('executed', 'hit_observations'),
    'MechanicState': ('provenance',),
    'BattleState': ('observations', 'conflicts'),
}


def seal_state(value):
    """Seal history fields only; current values and open episodes stay mutable."""
    if is_dataclass(value):
        if type(value).__name__ == 'BattleState':
            # Ended episodes can no longer be HUD-resolved. Persistent return
            # proofs are historical assertions, never a second identity owner.
            episodes = value.knowledge.get('active_entry_episodes', [])
            for i, episode in enumerate(episodes):
                if episode.get('departure') is not None:
                    episodes[i] = freeze(episode)
                else:
                    for owner, key in ((episode, 'placements'), (episode.get('hud_binding', {}), 'candidates')):
                        if key in owner:
                            history = owner[key]
                            if not isinstance(history, EvidenceHistory):
                                history = EvidenceHistory(history)
                                owner[key] = history
                            history.seal()
            ledger = value.knowledge.get('identity_ledger', {})
            for key in ('persistent_returns', 'roster', 'entries'):
                if key in ledger:
                    history = ledger[key]
                    if not isinstance(history, EvidenceHistory):
                        history = EvidenceHistory(history)
                        ledger[key] = history
                    history.seal()
        histories = HISTORY_FIELDS.get(type(value).__name__, ())
        for f in fields(value):
            child = getattr(value, f.name)
            if f.name in histories:
                if not isinstance(child, EvidenceHistory):
                    child = EvidenceHistory(child)
                    setattr(value, f.name, child)
                child.seal()
            else:
                seal_state(child)
    elif isinstance(value, IMMUTABLE):
        return
    elif isinstance(value, dict):
        for child in value.values():
            seal_state(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            seal_state(child)


def compact_export(state):
    """Versioned transport: current state references a lossless evidence table.

    A reference has an explicit envelope, so user/evidence dictionaries cannot
    collide with it. The table is local to this export, never a global database.
    """
    evidence = {}

    def project(value):
        if isinstance(value, (EvidenceHistory, *IMMUTABLE)):
            raw = canonical(value)
            key = hashlib.sha256(raw).hexdigest()
            if key not in evidence:
                if isinstance(value, dict):
                    evidence[key] = {'node': 'object', 'fields': {k: project(v) for k, v in value.items()}}
                else:
                    evidence[key] = {'node': 'array', 'items': [project(v) for v in value]}
            return {'node': 'evidence', 'sha256': key}
        if is_dataclass(value):
            return {'node': 'object', 'fields': {f.name: project(getattr(value, f.name)) for f in fields(value)}}
        if isinstance(value, dict):
            return {'node': 'object', 'fields': {k: project(v) for k, v in value.items()}}
        if isinstance(value, (list, tuple)):
            return {'node': 'array', 'items': [project(v) for v in value]}
        return {'node': 'value', 'value': value}

    return {'schema_version': 1, 'current': project(state), 'evidence': evidence}


def expand_compact(packet):
    if packet['schema_version'] != 1:
        raise ValueError('Unsupported compact state schema')

    resolved = {}
    resolving = set()

    def expand(node):
        kind = node['node']
        if kind == 'evidence':
            key = node['sha256']
            if key not in resolved:
                if key in resolving:
                    raise ValueError('Cyclic evidence reference')
                resolving.add(key)
                value = expand(packet['evidence'][key])
                if hashlib.sha256(canonical(value)).hexdigest() != key:
                    raise ValueError('Evidence digest mismatch')
                resolved[key] = value
                resolving.remove(key)
            return export(resolved[key])
        if kind == 'object':
            return {k: expand(v) for k, v in node['fields'].items()}
        if kind == 'array':
            return [expand(v) for v in node['items']]
        if kind == 'value':
            return deepcopy(node['value'])
        raise ValueError('Unsupported compact node')

    result = expand(packet['current'])
    if not result.get('knowledge'):
        result.pop('knowledge', None)
    return result
