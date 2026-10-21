"""A uniform prior over explicit Speed-relevant configuration projections."""
from copy import deepcopy
from itertools import product
import hashlib
import json
from knowledge.champions_stats import ChampionsStats, alignment_patterns, adjustment_factors
from knowledge import normalize
from speed_order.core import knowledge, name


def encoded(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)


def digest(value):return hashlib.sha256(encoded(value).encode()).hexdigest()


def modifier_domain(value,kind,stats):
    if value is None:
        return [None],dict(status='unresolved',values=None,
            meaning='Unmodeled, not neutral; an observation must establish the current modifier or is ineligible')
    if not isinstance(value,dict) or set(value)!={'values','coverage','evidence'}:
        raise ValueError(kind+' domain requires values, coverage and evidence')
    if value['coverage']!='complete_given_evidence' or not isinstance(value['evidence'],list) or not value['evidence']:
        raise ValueError('Finite '+kind+' alternatives require explicit complete-given-evidence provenance')
    choices=value['values']
    if not isinstance(choices,list) or not 1<=len(choices)<=256:raise ValueError('Bounded '+kind+' alternatives required')
    choices=sorted(set(name(v,kind) for v in choices))
    kb=knowledge();fact=kb.facts['pokemon'][stats.identity]
    for choice in choices:
        if kind=='ability' and choice not in fact.get('ability_names',[]):
            raise ValueError('Ability is not asserted for this form in the pinned Champions catalog: '+choice)
        if kind=='item' and choice!='none':
            key=next(e.canonical_id for e in kb.exact[kind].get(normalize(choice),[]) if e.kind==kind)
            if key not in kb.facts.get('items',{}):raise ValueError('Item not available in the pinned Champions catalog')
        if kind=='item' and fact.get('required_item') and choice!=fact['required_item']:
            raise ValueError('Current form requires its source-reported item')
    return choices,dict(status='explicit_finite_conditional_domain',values=choices,
        coverage=value['coverage'],evidence=deepcopy(value['evidence']),
        verification='pinned Champions community catalog assertion, not independent in-game certification')


def configuration_space(*,identity,form,speed_points=None,alignments=None,known_other_points=None,
                        abilities=None,items=None,max_candidates=20000):
    """Enumerate (Stat Alignment, Speed SP, optional evidenced modifiers).

    Other SP are existentially quantified, not filled with zeros and not counted
    as extra prior multiplicity. This is not a uniform prior over full builds.
    """
    if type(max_candidates) is not int or not 1<=max_candidates<=200000:raise ValueError('Invalid candidate work limit')
    stats=ChampionsStats(identity,form=form)
    patterns=alignment_patterns() if alignments is None else alignments
    if not isinstance(patterns,list) or not 1<=len(patterns)<=21:raise ValueError('Supply 1..21 explicit alignment patterns')
    for pattern in patterns:adjustment_factors(pattern)
    if len({encoded(p) for p in patterns})!=len(patterns):raise ValueError('Duplicate alignment patterns would bias the prior')
    patterns=sorted(deepcopy(patterns),key=encoded)
    other={} if known_other_points is None else deepcopy(known_other_points)
    points=list(range(33)) if speed_points is None else speed_points
    projection=stats.attainable('speed',adjustments=['0.9','1.0','1.1'],point_domain=points,allocated_other=other)
    lookup={(r['training_points'],r['adjustment']):r['actual_stat'] for r in projection['configurations']}
    legal_points=sorted({p for p,a in lookup})
    ability_spec=deepcopy(abilities);item_spec=deepcopy(items)
    abilities,ability_meta=modifier_domain(abilities,'ability',stats)
    items,item_meta=modifier_domain(items,'item',stats)
    if len(legal_points)*len(patterns)*len(abilities)*len(items)>max_candidates:raise ValueError('Candidate work limit exceeded; narrow evidenced domains')
    rows=[]
    for p,pattern,ability,item in product(legal_points,patterns,abilities,items):
        value=dict(speed_sp=p,alignment=pattern,ability=ability,item=item,
            unmodified_speed=lookup[p,adjustment_factors(pattern)['speed']])
        value['id']=digest([stats.identity,value]);rows.append(value)
    if not rows:raise ValueError('No legal Speed projection extends the known SP allocation; no prior created')
    model=dict(version='speed-configuration-projection-v1',identity=stats.identity,form='as_named' if stats.identity.startswith('pokeapi:form:') else 'base',
        candidates=rows,known_other_points=other,modifier_domains=dict(ability=ability_meta,item=item_meta),
        prior=dict(kind='uniform_configuration_projection',candidate_count=len(rows),weight=1/len(rows),
            parameterization='One weight per numerical Stat Alignment / Speed SP / explicitly supplied modifier assignment; no multiplicity for unenumerated other-SP completions or interchangeable nature labels',
            empirical_data_used=False),
        provenance=stats.provenance,legality_scope='Existence of a completion under maintained Champions SP/alignment rules and pinned current-form catalog; not independent roster certification')
    model['specification']=dict(identity=model['identity'],form=model['form'],speed_points=legal_points,
        alignments=patterns,known_other_points=other,abilities=ability_spec,items=item_spec,max_candidates=max_candidates)
    model['fingerprint']=digest(model)
    return model
