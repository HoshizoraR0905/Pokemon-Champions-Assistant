"""Item equivalence for the existing Speed engine, retaining concrete hypotheses.

Not a battle/item simulator: indirect effects must be explicit action-time state.
"""
from functools import lru_cache
from pathlib import Path
from copy import deepcopy
import hashlib
import json

from speed_order.core import knowledge, name


@lru_cache(maxsize=1)
def audit():
    data=json.loads(Path(__file__).with_name('speed-item-projection-v1.json').read_text())
    facts=Path(__file__).resolve().parents[1]/'knowledge/data/champions_facts.json'
    if hashlib.sha256(facts.read_bytes()).hexdigest()!=data['knowledge_facts_sha256']:
        raise ValueError('Item projection needs re-audit for this knowledge snapshot')
    return data


@lru_cache(maxsize=1)
def item_ids():
    kb=knowledge()
    return {name(i,'item'):i for i in kb.facts['items']}


@lru_cache(maxsize=256)
def species_stones(identity):
    kb=knowledge();sid=kb.entities[identity].species_id
    return frozenset(f['required_item'] for key,f in kb.facts['pokemon'].items()
                     if f.get('required_item') and key in kb.entities and kb.entities[key].species_id==sid)


def representative(item, identity):
    label=name(item,'item')
    if label=='none' or label in species_stones(identity):
        return label
    if item_ids().get(label) in audit()['no_direct_speed_order_callback_items']:
        return 'none'
    return label # Relevant or unverified mechanics are never neutralized.


def item_classes(identity, items):
    groups={}
    for item in items:
        label=name(item,'item');rep=representative(label,identity)
        groups.setdefault(rep,set()).add(label)
    return [dict(representative=rep,members=sorted(members),
                 member_ids=sorted(item_ids()[m] if m!='none' else 'none' for m in members),
                 condition='Equivalent only under supplied HP/status/grounding/activation history; compatible stones kept separate')
            for rep,members in sorted(groups.items())]


def project_state_items(state):
    result=deepcopy(state);receipts=[]
    from speed_order.core import identity_key
    for iid,p in result['participants'].items():
        if p.get('item') is None:
            continue
        if p.get('unburden_active') is True and name(p['item'],'item')!='none':
            raise ValueError('Active Unburden cannot be neutralized with a still-held item; item-loss history required')
        identity=identity_key(p['identity'],p['form']);original=p['item'];projected=representative(original,identity)
        p['item']=projected
        if name(original,'item')!=projected:
            receipts.append(dict(individual=iid,original=original,representative=projected,
                                 scope=audit()['scope'],version=audit()['version']))
    return result,receipts


def project_changes(changes, state):
    result=deepcopy(changes)
    from speed_order.core import identity_key
    for change in result:
        if change['kind']=='set' and 'item' in change['values']:
            p=state['participants'][change['target']]
            if change['values'].get('unburden_active',p.get('unburden_active')) is True and name(change['values']['item'],'item')!='none':
                raise ValueError('Active Unburden conflicts with the documented held-item change')
            change['values']['item']=representative(change['values']['item'],identity_key(p['identity'],p['form']))
    return result
