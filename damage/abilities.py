"""Audited connected-hit neutrality; never an unknown-ability fallback."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path


@lru_cache(maxsize=1)
def ability_audit():
    path=Path(__file__).parent/'data/offensive-coverage-v1.json'
    raw=path.read_bytes()
    return json.loads(raw)['contextual_neutral_abilities'],hashlib.sha256(raw).hexdigest()


def neutral_ability_names():
    return set(ability_audit()[0])


def contextual_neutrality(ability, move, *, phase='connected_direct_hit', field=None):
    rule=ability_audit()[0].get(ability)
    if (not rule or phase!='connected_direct_hit' or move.get('category') not in ('Physical','Special')
            or (rule.get('exclude_reflectable') and move.get('flags',{}).get('reflectable'))
            or (rule.get('requires_weather') and (field or {}).get('weather') not in ('none','sun','rain','sand','snow'))):
        return None
    return dict(ability=ability,classification='contextual_no_direct_damage_effect',phase=phase,
                basis=rule['basis'],dependencies=rule['dependencies'],audit_sha256=ability_audit()[1])
