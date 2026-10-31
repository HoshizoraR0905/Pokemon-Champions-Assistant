"""Calculated unmodified form stats in existing mechanics, not effective stages."""
from copy import deepcopy
from dataclasses import asdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import unicodedata

from knowledge.champions_stats import ChampionsStats, STATS
from .battle_state import Fact, fact
from .mechanics import ensure


@lru_cache(maxsize=1)
def form_evidence():
    raw=(Path(__file__).resolve().parents[1]/'knowledge/data/mega-stat-evidence-v1.json').read_bytes()
    data=json.loads(raw)
    return {f['canonical_variant']:dict(f,assertion_sha256=hashlib.sha256(raw).hexdigest()) for f in data['forms']}


def calculate_member(member, identity=None):
    """Use actual displayed SP and reviewed arrows; never reverse-fit a build."""
    fields=member['fields']
    points={s:fields['allocation_'+s+'_display']['value'] for s in STATS}
    if any(fields['allocation_'+s+'_display'].get('status') not in {'observed','manual_verified'}
           or fields['allocation_'+s+'_display'].get('conflicts') for s in STATS):
        raise ValueError('SP allocation is not independently verified')
    alignment=member.get('reviewed_stat_alignment')
    if alignment is None:raise ValueError('Reviewed stat alignment missing')
    base=ChampionsStats(member['canonical_identity']).calculate(points,alignment)
    if any(base['stats'][s]!=fields[s]['value'] for s in STATS):
        raise ValueError('Original six displayed stats do not reproduce')
    if identity is None or identity==member['canonical_identity']:return base
    evidence=form_evidence().get(identity)
    if not evidence or evidence['species_id']!=member['species_id']:
        raise ValueError('Exact current-form base stats not verified')
    model=ChampionsStats(identity)
    if model.base_stats!=evidence['base_stats']:raise ValueError('Pinned and source-specific form base stats disagree')
    result=model.calculate(points,alignment)
    result['provenance']['form_assertion']=deepcopy(evidence)
    return result


def update_stats(state,p,event):
    from .state_engine import evidence_link
    configured=state.knowledge.get('team',{}).get('instances',{}).get(p.pokemon_instance_id)
    if not configured:return
    member=dict(species_id=(p.original_identity.value or {}).get('species_id'),
                canonical_identity=configured['canonical_identity'],fields=configured['fields'],
                reviewed_stat_alignment=configured.get('stat_alignment'))
    m=p.mechanics.get('battle_stats') or ensure(p,'battle_stats','per_instance')
    proof=dict(**evidence_link(event),configuration_sources=deepcopy(configured['sources']))
    try:
        original=calculate_member(member)
        configured.setdefault('original_form_calculation',deepcopy(original))
        identity=p.current_variant.value if p.current_variant.known else None
        if not identity:raise ValueError('Current canonical form unresolved')
        result=calculate_member(member,identity)
    except (ValueError,KeyError,TypeError) as exc:
        m.current={s:Fact(provenance=[dict(**proof,reason=str(exc))]) for s in STATS}
        m.current['form_verified']=fact(False,proof,'derived')
        return
    proof['calculation']=deepcopy(result)
    m.current={s:fact(result['stats'][s],proof,'derived') for s in STATS}
    m.current.update(canonical_variant=fact(identity,proof,'derived'),form_verified=fact(True,proof,'derived'),
                     stat_basis=fact('unmodified_form_separate_from_stages',proof,'derived'))
    # A calculated HP display/max is not a current HP observation. No HPState
    # field, item, underlying identity or stage is changed here.


def resolve_mega(state,p,event):
    """Resolve generic result by its same-actor observed stone reaction only."""
    from battle_events.parser import EventParser
    from .state_engine import evidence_link
    event=deepcopy(event);a=event.attributes
    if a.get('mechanic')!='mega_evolution':return event
    sid=(p.original_identity.value or {}).get('species_id')
    reactions=[]
    for obs in state.observations:
        attrs=obs.get('attributes',{})
        if attrs.get('effect')!='mega_stone_reaction_notice' or attrs.get('actor_instance_id')!=p.pokemon_instance_id:continue
        text=''.join(row.get('text','') for source in obs.get('evidence',{}).get('sources',[])
                     for row in source.get('details',{}).get('row_evidence',[]))
        reactions.append((unicodedata.normalize('NFKC',text),obs['evidence']))
    selected=[]
    for text,proof in reactions[-1:]:
        for variant,row in form_evidence().items():
            if row['species_id']==sid and row['stone']+'和' in text:
                selected.append((row,proof))
    if len(selected)==1:
        row,proof=selected[0]
        explicit=(a.get('identity') or {}).get('name','')
        # A literal X/Y/Z result cannot silently disagree with another stone.
        suffix=unicodedata.normalize('NFKC',explicit)[-1:]
        if suffix in {'X','Y','Z'} and not row['stone'].endswith(suffix):
            a.update(identity=None,form_unresolved=True,completed_transformation=True,
                     reported_form='超级'+(p.original_identity.value or {}).get('name',''))
        else:
            parser=EventParser();e=parser.kb.entities[row['canonical_id']]
            a.update(identity=parser.identity(e.names['zh-hans'],'species'),form_unresolved=False,
                     form_resolution=dict(rule='observed_stone_reaction_and_completed_mega',
                        reaction_evidence=deepcopy(proof),form_assertion=deepcopy(row),result=evidence_link(event)))
    elif sid==445 and (a.get('identity') or {}).get('canonical_identity')=='pokeapi:pokemon:10058':
        # The generic Garchomp result does not distinguish ordinary Mega/Z.
        a.update(identity=None,form_unresolved=True,completed_transformation=True,reported_form='超级烈咬陆鲨')
    return event
