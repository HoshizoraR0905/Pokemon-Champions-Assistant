"""Equal-design estimators. Never represent Ranked encounter probabilities."""
from collections import Counter
from itertools import combinations
import json
from metagame.common import encode
from . import VERSION
from .canonical import Canonicalizer
from .store import Teams


def ratio(k,n):
    return dict(numerator=k,denominator=n,estimate=k/n if n else None,
        status='observed_design_frequency' if n else 'insufficient_data',
        small_sample=n<20,sampling_interval=None,
        uncertainty='Finite selected corpus; no random-sampling model, independent sample claim or Ranked encounter interpretation')


def _links(rows):
    return [dict(publication_id=r['id'],source_url=r['source_url'],source_key=r['source_key'],
        title=r['title'],source=r['source_id'],status=r['status'],
        extraction_id=r.get('extraction_id'),
        **{k:json.loads(r['original']).get('metadata',{}).get(k) for k in
            ('attribution','creator','event','placement','source_date','published_date','paste_id','replica_code','source_scope')}) for r in rows]


def _distinct(rows,unit):
    key='build_id' if unit=='unique_build' else 'composition_id'
    groups={}
    for r in rows:
        if not r[key]:continue
        if unit=='unique_build' and r['status']=='conflicting':continue
        if unit=='unique_composition' and json.loads(r['canonical']).get('composition_conflicting'):continue
        groups.setdefault(r[key],[]).append(r)
    return groups


def coverage(root,*,population,regulation,battle_format='Doubles',version=VERSION,source=None):
    db=Teams(root,readonly=True)
    try:
        rows=db.scoped(population,regulation,battle_format,version)
        if source:rows=[r for r in rows if r['source_id']==source]
        from .observed import distinct,eligibility,FIELDS
        observed,family_audit=distinct(rows,with_audit=True)
        builds=_distinct(rows,'unique_build');comps=_distinct(rows,'unique_composition')
        children={cid:sorted({r['build_id'] for r in group if r['build_id']}) for cid,group in comps.items()}
        candidates=db.db.execute('SELECT left_extraction,right_extraction,reason FROM duplicate_candidates').fetchall()
        eligible_ids={r['extraction_id'] for r in rows}
        candidates=[dict(r) for r in candidates if r['left_extraction'] in eligible_ids and r['right_extraction'] in eligible_ids]
        members=[m for r in rows for m in json.loads(r['canonical'])['members']]
        return dict(population=population,regulation=regulation,format=battle_format,algorithm_version=version,
            source_publications=len({(r['source_id'],r['source_key']) for r in rows}),
            publication_revisions=len({r['id'] for r in rows}),extraction_records=len(rows),
            unique_compositions=len(comps),unique_builds=len(builds),
            source=source,distinct_observed_configurations=len(observed),
            distinct_observed_complete_rosters=sum(bool(json.loads(group[0]['canonical'])['composition_id']) for group in observed.values()),
            publication_family_audit=family_audit,
            observed_configuration_publications={s:_links(p) for s,p in observed.items()},
            team_field_completeness={field:sum(len(data['members'])==6 and all(eligibility(m)[field] for m in data['members'])
                for data in (json.loads(r['canonical']) for r in rows)) for field in FIELDS},
            teams_with_all_core_fields=sum(len(data['members'])==6 and all(all(eligibility(m)[f] for f in ('moves','item','ability','nature'))
                for m in data['members']) for data in (json.loads(r['canonical']) for r in rows)),
            replica_code_publications=sum(bool(json.loads(r['original']).get('metadata',{}).get('replica_code')) for r in rows),
            record_statuses=dict(Counter(r['status'] for r in rows)),
            unique_build_excluded_publication_revisions=len({r['id'] for r in rows if not r['build_id'] or r['status']=='conflicting'}),
            unique_composition_excluded_publication_revisions=len({r['id'] for r in rows if not r['composition_id'] or json.loads(r['canonical']).get('composition_conflicting')}),
            composition_children=children,exact_build_publications={bid:_links(group) for bid,group in builds.items()},
            composition_publications={cid:_links(group) for cid,group in comps.items()},
            partial_records=[dict(publication_id=r['id'],source_url=r['source_url'],status=r['status'],
                missing=json.loads(r['canonical'])['missing'],conflicts=json.loads(r['canonical'])['conflicts'])
                for r in rows if r['status']!='exact_complete'],potential_duplicate_candidates=candidates,
            extraction_field_completeness=dict(pokemon_records=len(members),
                complete_sp_vectors=sum(m['stat_validation'].get('validation')=='valid_under_pinned_profile' for m in members),
                missing_or_invalid_sp_vectors=sum(m['stat_validation'].get('validation')!='valid_under_pinned_profile' for m in members),
                scope='Extraction records, for data completeness only; not estimator weights'),
            estimator_comparison='unique_build counts each verified core exact configuration once; unique_composition counts each six-form multiset once without selecting a child build',
            approximate_family_grouping='not_implemented; no SP distance threshold',
            extraction_selection='Latest adapter extraction per immutable publication revision and selected fingerprint version; prior extractions retained',
            database_superseded_publication_revisions=db.db.execute('SELECT count(*) FROM publication_supersessions').fetchone()[0],
            bias='Selected public designs; publication multiplicity is metadata, not weight; neither estimator is Ranked usage')
    finally:db.close()


def query(root,species,*,population,regulation,unit='unique_build',battle_format='Doubles',
          teammates=(),exclude_teammates=(),given_move=None,move_pair=None,version=VERSION,min_multiple_context=5,source=None):
    if unit=='distinct_observed_configuration':
        from .observed import query as observed_query
        return observed_query(root,species,source=source,population=population,regulation=regulation,
            battle_format=battle_format,teammates=teammates,exclude_teammates=exclude_teammates,
            given_move=given_move,move_pair=move_pair,version=version,min_multiple_context=min_multiple_context)
    if unit not in ('unique_build','unique_composition'):raise ValueError('Unknown observation unit')
    if type(min_multiple_context) is not int or min_multiple_context<1:raise ValueError('Positive multi-teammate minimum required')
    c=Canonicalizer()
    def resolve(name,kind='species'):
        r=c.names.resolve(name,kind)['canonical_id']
        if r is None:raise ValueError('Unknown/ambiguous '+kind+': '+name)
        return r
    target=resolve(species);mates=[resolve(t) for t in teammates]
    excluded=[resolve(t) for t in exclude_teammates]
    if target in mates or len(mates)!=len(set(mates)):raise ValueError('Condition on distinct other teammates')
    if target in excluded or set(mates)&set(excluded):raise ValueError('Invalid excluded teammate context')
    move=resolve(given_move,'move') if given_move else None
    pair=tuple(resolve(v,'move') for v in move_pair) if move_pair else None
    if pair and (len(pair)!=2 or pair[0]==pair[1]):raise ValueError('Two distinct moves required')
    if unit=='unique_composition' and (move or pair):raise ValueError('Composition estimator cannot supply build-field probabilities')
    db=Teams(root,readonly=True)
    try:rows=db.scoped(population,regulation,battle_format,version)
    finally:db.close()
    if source:rows=[r for r in rows if r['source_id']==source]
    elif len({r['source_id'] for r in rows})>1:
        raise ValueError('Multiple sources in this population; select one source instead of automatically pooling')
    groups=_distinct(rows,unit)
    units=[]
    for identifier,group in groups.items():
        data=json.loads(group[0]['canonical'])
        units.append(dict(id=identifier,group=group,data=data,members=data['composition']))
    containing=[u for u in units if target in u['members']]
    selected=[u for u in containing if all(m in u['members'] for m in mates) and not any(m in u['members'] for m in excluded)]
    result=dict(population=population,regulation=regulation,format=battle_format,source=source,
        observation_unit=unit,algorithm_version=version,species=dict(original=species,canonical_id=target),
        conditioning_teammates=mates,excluded_teammates=excluded,total_eligible_designs=len(units),species_designs=len(containing),
        context_designs=len(selected),source_publications=len({(r['source_id'],r['source_key']) for r in rows}),
        excluded_publication_revisions=len({r['id'] for r in rows if not r['build_id' if unit=='unique_build' else 'composition_id']
            or (r['status']=='conflicting' if unit=='unique_build' else json.loads(r['canonical']).get('composition_conflicting'))}),
        species_frequency=ratio(len(containing),len(units)),teammate_context_frequency=ratio(len(selected),len(containing)),
        source_links=_links([r for u in selected for r in u['group']]),
        interpretation='Frequency among distinct published designs in this selected corpus, not Ranked encounters',
        status='observed_design_frequencies' if selected else 'insufficient_data')
    if len(mates)>1 and len(selected)<min_multiple_context:
        result.update(status='insufficient_multiple_teammate_sample',minimum_required=min_multiple_context,
            withheld_estimates=True)
        result['teammate_context_frequency']['estimate']=None
        return result
    teammate_counts=Counter()
    for u in selected:teammate_counts.update(set(u['members'])-{target})
    result['teammates']=[]
    for partner,k in sorted(teammate_counts.items(),key=lambda kv:(-kv[1],kv[0])):
        baseline=sum(partner in u['members'] for u in units)
        co=sum(target in u['members'] and partner in u['members'] for u in units)
        result['teammates'].append(dict(canonical_id=partner,frequency=ratio(k,len(selected)),
            population_baseline=ratio(baseline,len(units)),cooccurrence=ratio(co,len(units)),
            # Lift uses the same unconditioned population and P(B|A), not an
            # additional teammate-conditioned numerator against a wrong baseline.
            lift=(co/len(containing))/(baseline/len(units)) if containing and baseline else None,
            lift_scope='unconditioned target/partner association in the selected design population; six-slot descriptive baseline, not causation'))
    if unit=='unique_composition':
        result['build_statistics']=dict(status='unavailable_under_composition_estimator',
            reason='One composition can contain multiple exact builds; no child is arbitrarily selected')
        return result
    eligible=[];ambiguous=[]
    for u in selected:
        mons=[m for m in u['data']['exact_build'] if m['species']==target]
        if len(mons)!=1:ambiguous.append(u['id']);continue
        if move and move not in mons[0]['moves']:continue
        eligible.append((u,mons[0]))
    result.update(eligible_target_builds=len(eligible),multiple_target_instances_excluded=ambiguous,
                  given_move=move,given_move_scope='Build-field estimates only; teammate/lift summaries retain their stated design context',field_distributions={})
    if not eligible:result['status']='insufficient_data'
    for field in ('moves','item','ability','nature','sp'):
        count=Counter()
        for u,mon in eligible:
            values=mon['moves'] if field=='moves' else [encode(mon['sp']) if field=='sp' else mon[field]]
            count.update(set(values))
        result['field_distributions'][field]=[dict(value=json.loads(v) if field=='sp' else v,
            **ratio(k,len(eligible))) for v,k in sorted(count.items(),key=lambda kv:(-kv[1],kv[0]))]
    result['move_move_associations']=[dict(moves=list(pair_),**ratio(k,len(eligible)))
        for pair_,k in sorted(Counter(tuple(p) for u,m in eligible for p in combinations(m['moves'],2)).items())]
    if pair:result['requested_move_pair']=dict(moves=pair,**ratio(sum(all(p in m['moves'] for p in pair) for u,m in eligible),len(eligible)))
    result['sp_missingness']=dict(eligible_complete=len(eligible),missing_within_estimator=0,
        excluded_incomplete_source_publications=result['excluded_publication_revisions'],
        scope='Complete-build estimator excludes incomplete teams, even if the target Pokémon itself is known')
    return result
