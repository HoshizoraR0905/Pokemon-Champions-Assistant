"""Versioned item audit and explicit-state connected-hit equivalence.

No default neutrality for unknown items. Legality, effect applicability and
practical candidate selection are separate queries.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path


@lru_cache(maxsize=1)
def registry():
    data=json.loads((Path(__file__).parent/'data/item-classification-v1.json').read_text())
    facts=Path(__file__).resolve().parents[1]/'knowledge/data/champions_facts.json'
    if hashlib.sha256(facts.read_bytes()).hexdigest()!=data['sources']['canonical']['sha256']:
        raise ValueError('Item registry requires re-audit')
    return data


def rule(item):
    return registry()['items'].get(item)


def effect_applicable(item, form):
    from speed_order.core import knowledge
    r=rule(item)
    if not r:return item=='none'
    return r['applicable_species']=='all' or 'pokeapi:species:'+str(knowledge().entities[form].species_id) in r['applicable_species']


def candidate_applicable(item, form):
    """Stone-generation restriction; ineffective Light Ball may still be held."""
    from speed_order.core import knowledge
    required=knowledge().facts['pokemon'][form].get('required_item')
    if required:return item==required
    r=rule(item)
    return item=='none' or bool(r and (r['forward_coverage']!='current_form_stone' or effect_applicable(item,form)))


def hit_handler(item, form, role):
    r=rule(item)
    if item=='none':return 'existing_modifier'
    if not r:return 'unresolved'
    handler=r['forward_coverage']
    if handler=='light_ball' and not effect_applicable(item,form):return 'contextual_connected_hit'
    # These survival handlers change lethal HP outcomes; ordinary raw damage is
    # not an audited inverse representation of their target-side survival.
    if role=='defender' and item in {'Focus Band','Focus Sash'}:return 'unresolved'
    return handler


def damage_equivalent(item, form, ability, move):
    """Only share calculations whose audited connected-hit behavior is equal."""
    from .engine import TYPE_ITEMS,BERRIES
    if hit_handler(item,form,'attacker')=='contextual_connected_hit':return 'none'
    if item in BERRIES:return 'none'  # supplied attacker HP/status/stages unchanged
    if rule(item) and rule(item)['forward_coverage']=='current_form_stone':return 'none'
    typ=move.get('type')
    if typ=='Normal':typ={'Aerilate':'Flying','Pixilate':'Fairy','Refrigerate':'Ice'}.get(ability,typ)
    if item=='Normal Gem' and typ!='Normal':return 'none'
    if item in TYPE_ITEMS and TYPE_ITEMS[item]!=typ:return 'none'
    if item=='Muscle Band' and move.get('category')!='Physical':return 'none'
    if item=='Wise Glasses' and move.get('category')!='Special':return 'none'
    return item
