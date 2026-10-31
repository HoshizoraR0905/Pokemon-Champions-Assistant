"""M3.4.4: tilted empirical records and their joint-core pushforward.

P gives equal mass to every eligible VGC member occurrence.
Identical teams/builds retain their multiplicity; core grouping is UI-only.
Beta(a,b) is only finite-sample scoring regularization, not an opponent prior.
"""
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import math
from time import perf_counter
from knowledge.champions_stats import ChampionsStats,STATS
from speed_order.core import knowledge,name
from speed_order.forms import mega_base_form,published_ability

ALPHAS=(0.,.25,.5,.6,.75,1.)
DEFAULT_ALPHA=.5


def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]


def template(row):
    moves=row.get('configuration',{}).get('moves',[])
    contested=any('move' in x or 'build_export_disagreement' in x for x in row.get('issues',[]))
    known=sorted(set(x for x in moves if x)) if not contested else []
    return dict(moves=known,complete=not contested and len(known)==4,uncertain=contested,
                publications=deepcopy(row.get('publications',[])))


def record_key(row):
    return row.get('empirical_record_id') or row['observed_team_signature']+':'+str(row.get('build_id') or digest(row['configuration']))


def full_record_signature(row):
    configuration=deepcopy(row['configuration'])
    configuration['moves']=sorted(configuration.get('moves',[]),key=lambda m:m or '')
    return hashlib.sha256(json.dumps(configuration,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def inclusion(rows,move,*,a=.5,b=.5,alpha=.5):
    if a<=0 or b<=0 or not math.isfinite(a+b) or alpha<0 or not math.isfinite(alpha):raise ValueError('Finite positive smoothing and nonnegative alpha required')
    known=[template(r) for r in rows]
    counts=[1 for r in rows]
    successes=sum(n for t,n in zip(known,counts) if move in t['moves'])
    failures=sum(n for t,n in zip(known,counts) if t['complete'] and move not in t['moves'])
    sample=sum(counts)
    n=successes+failures;p=(successes+a)/(n+a+b)
    return dict(move=move,sample_size=sample,compressed_template_count=len(rows),positive=successes,negative=failures,denominator=n,
        unknown=sample-n,raw_frequency=successes/n if n else None,smoothed_frequency=p,
        effective_weight=math.exp(-alpha*math.log(p)),smoothing=dict(method='Beta-binomial posterior mean for score regularization',a=a,b=b))


def tilt(records,frequency_rows,observed_moves,*,alpha=.5,a=.5,b=.5,surviving_ids=None,unresolved_ids=()):
    """Q ∝ 1_H P exp(alpha Σ_{distinct matches} -log(p_hat))."""
    start=perf_counter();moves=sorted(set(observed_moves));freq={m:inclusion(frequency_rows,m,a=a,b=b,alpha=alpha) for m in moves}
    if alpha<0 or not math.isfinite(alpha):raise ValueError('Invalid alpha')
    live=set(records) if surviving_ids is None else set(surviving_ids);unknown=set(unresolved_ids)
    tilts={rid:alpha*sum(-math.log(freq[m]['smoothed_frequency']) for m in moves if m in rec['template']['moves']) for rid,rec in records.items() if rid in live}
    logs=tilts.copy()
    population=len(records)
    maximum=max(logs.values(),default=0);scaled={rid:math.exp(v-maximum) for rid,v in logs.items()};den=sum(scaled.values())
    evaluated_den=sum(v for rid,v in scaled.items() if rid not in unknown)
    weighted=[];groups={}
    for rid,rec in records.items():
        mass=scaled.get(rid,0)/den if den else 0
        matched=sorted(set(moves)&set(rec['template']['moves']))
        row=dict(id=rid,core_id=rec['core_id'],share=mass,empirical_count=1,base_mass=1/population if population else None,evaluated_share=(scaled.get(rid,0)/evaluated_den if rid not in unknown else 0.) if evaluated_den else None,log_tilt=tilts.get(rid),matched=matched,
                 hard_excluded=rid not in live,support='provisional_unresolved' if rid in unknown else 'evaluated' if rid in live else 'excluded')
        weighted.append(row)
        if rid not in live:continue
        c=groups.setdefault(rec['core_id'],dict(core_id=rec['core_id'],share=0.,evaluated_share=0. if evaluated_den else None,records=[],matched_moves=set(),matching_source_records=0,provisional=False))
        if evaluated_den:c['evaluated_share']+=row['evaluated_share']
        c['matching_source_records']+=bool(matched)
        c['share']+=mass;c['records'].append(rid);c['matched_moves'].update(matched);c['provisional'] |= rid in unknown
    for c in groups.values():
        c['matched_moves']=sorted(c['matched_moves']);c['compressed_records']=len(c['records']);c['source_records']=len(c['records'])
    cores=sorted(groups.values(),key=lambda c:(-c['share'],c['core_id']))
    return dict(alpha=alpha,moves=moves,frequencies=freq,records=weighted,cores=cores,
        base_observation_mass=1/population if population else None,population_observations=population,effective_sample_size=1/sum(r['share']**2/r['empirical_count'] for r in weighted) if den else 0.,largest_record_share=max((r['share']/r['empirical_count'] for r in weighted),default=0.),
        evaluated_records=len(set(logs)-unknown),provisional_records=len(set(logs)&unknown),eligible_records=len(records),surviving_observations=len(logs),surviving_records=len(logs),surviving_cores=len(cores),
        status='empirical_exhausted' if not den else 'retained_with_unresolved_mechanics' if live&unknown else 'conditional_empirical_measure',
        interpretation='Share of reweighted published sample conditional on supplied evidence; ranking measure, not calibrated opponent probability',
        seconds=perf_counter()-start)


def context_rows(population,form):
    """Match current form. Base↔Mega pooling requires the SAME required stone."""
    by=population['by_form'];base=mega_base_form(form);required=knowledge().facts['pokemon'][form].get('required_item')
    forms=[form]
    if base:forms.append(base)
    else:forms += [f for f in by if f!=form and mega_base_form(f)==form]
    rows=[r for f in forms for r in by.get(f,{}).get('builds',[]) if not base or r.get('item') and name(r['item'],'item')==required]
    return rows,[]


def catalog(population,form):
    from damage.items import candidate_applicable
    frequency_rows,duplicates=context_rows(population,form);records={};cores={};excluded=[]
    for row in frequency_rows:
        rid=record_key(row)
        try:
            if not row.get('training_points') or not row.get('alignment') or not row.get('nature') or not row.get('item') or not row.get('ability') or row.get('stat_issue'):raise ValueError('Incomplete or conflicting training core')
            points=row['training_points'];alignment=row['alignment'];item=name(row['item'],'item')
            state=published_ability(row['species'],row['ability'],form)
            if not candidate_applicable(item,form):raise ValueError('Species/form/item incompatible')
            required=knowledge().facts['pokemon'][row['species']].get('required_item')
            if required and required!=item:raise ValueError('Published Mega lacks required stone')
            stats=ChampionsStats(form,form='as_named' if knowledge().entities[form].form_id else 'base').calculate(points,alignment)['stats']
            core=dict(form=form,nature=row['nature'],alignment=alignment,training_points=points,item=item,
                      ability=state['active_ability'],original_ability=state.get('original_ability'),stats=stats)
            cid=digest(core);cores[cid]=core
            records[rid]=dict(core_id=cid,observation_count=1,original_record_ids=row.get('original_record_ids',[]),template=template(row),observed_team_signature=row['observed_team_signature'],source_build_id=row.get('build_id'))
        except (ValueError,KeyError,NotImplementedError) as e:excluded.append(dict(id=rid,reason=str(e)))
    return dict(form=form,records=records,cores=cores,frequency_rows=[r for r in frequency_rows if record_key(r) in records],duplicates=duplicates,core_ineligible=excluded,
        population_scope=population['scope'],grouping='current form plus base/Mega only under required-stone compatibility; unrelated forms/species never pooled')


def compatible(core,rows):
    for c in rows:
        t=c['training'];p=core['training_points']
        if c['ability']==core['ability'] and core['item'] in c.get('item_options',[c['item']]) and t['alignment']==core['alignment'] and all(p[s] in t['point_domains'][s] for s in STATS):return True
    return False


def upgrade_empirical_support(replay,population):
    """Read cached M3.3 rows, separate templates, join cores to causal Speed rows."""
    from .offensive import speed_configuration_domain
    out=deepcopy(replay);catalogs={};seen=set();start=perf_counter()
    out['empirical_scope']=deepcopy(population.get('scope',{}))
    for snapshot in replay['snapshots']:
        for p in snapshot['opponents'].values():
            form=p.get('current_form');ref=p.get('support_ref')
            if not form or not ref or (form,ref) in seen:continue
            cat=catalogs.setdefault(form,None)
            if cat is None:cat=catalogs[form]=catalog(population,form)
            binary_allowed=None
            try:legal=speed_configuration_domain(replay,p)
            except ValueError as e:
                if 'cross-individual Speed witnesses' not in str(e):raise
                original=replay['support_catalog'][ref]['observed']
                binary_allowed={digest({k:v for k,v in replay['observed_builds'][rid]['configuration'].items() if k!='moves'}) for rid in original['builds']}
                legal=[]
                out['support_catalog'][ref]['observed']['core_eligibility_boundary']='Training-core equality maps distinct VGC records to sealed cross-individual Speed witnesses; moves do not constrain this relation; new unwitnessed cores deferred'
            # Index alignment/Speed/ability without expanding concrete items/SP.
            buckets=defaultdict(list)
            for c in legal:
                a=c['training']['alignment']
                for sp in c['training']['point_domains']['speed']:buckets[(a['increase'],a['decrease'],sp,c['ability'])].append(c)
            ids=[];mappings={}
            for rid,rec in cat['records'].items():
                core=cat['cores'][rec['core_id']];a=core['alignment']
                possible=buckets.get((a['increase'],a['decrease'],core['training_points']['speed'],core['ability']),[])
                source=next(r for r in cat['frequency_rows'] if record_key(r)==rid)
                if binary_allowed is not None:
                    if digest({k:v for k,v in source['configuration'].items() if k!='moves'}) not in binary_allowed:continue
                elif not compatible(core,possible):continue
                out['observed_builds'][rid]=dict(source,core_configuration=core,published_move_template=rec['template'])
                ids.append(rid);mappings[rid]=dict(published_ability(source['species'],source['ability'],form),speed=core['stats']['speed'])
            section=out['support_catalog'][ref]['observed']
            section.update(builds=ids,ability_mappings=mappings,complete_before=len(cat['records']),complete_after=len(ids),
                incomplete_excluded=len(cat['core_ineligible']),scope='Joint published training cores; recorded moves are soft templates, not slot constraints')
            seen.add((form,ref))
    out['empirical_core_catalogs']={f:{k:v for k,v in c.items() if k!='frequency_rows'} for f,c in catalogs.items()}
    return out,catalogs,perf_counter()-start


def attach_measures(replay,catalogs,*,a=.5,b=.5,default_alpha=DEFAULT_ALPHA):
    """Precompute six alpha choices once per causal support/revealed-move set."""
    start=perf_counter();catalog={};revealed=defaultdict(set);actions=sorted(replay['action_timeline'],key=lambda e:e['timestamp']);pos=0
    for snap in replay['snapshots']:
        while pos<len(actions) and actions[pos]['timestamp']<=snap['timestamp']:
            e=actions[pos];pos+=1
            if e['kind']=='executed_move' and e.get('side')=='opponent' and e.get('move'):revealed[e['individual']].add(e['move'])
        for iid,p in snap['opponents'].items():
            form=p.get('current_form');ref=p.get('support_ref')
            if form not in catalogs or not ref:continue
            from .move_legality import move_legality
            checks={m:move_legality(form,m) for m in sorted(revealed[iid])}
            moves=sorted(m for m,v in checks.items() if v['status']=='confirmed_possible');key=digest([iid,form,ref,moves])
            # A source support_ref is also used before/after a move reveal. Fork
            # presentation support only; the solver/configuration domains stay put.
            newref='measure:'+key
            if newref not in replay['support_catalog']:
                section=deepcopy(replay['support_catalog'][ref]);cat=catalogs[form];live=section['observed']['builds']
                issues=section['observed'].get('offensive',{}).get('unresolved',[])
                # Issue summaries cannot recover record IDs; solver stores a
                # separate supported/provisional ID list below.
                unknown=section['observed'].get('unresolved_record_ids',[])
                catalog[key]={format(alpha,'g'):tilt(cat['records'],cat['frequency_rows'],moves,alpha=alpha,a=a,b=b,surviving_ids=live,unresolved_ids=unknown) for alpha in ALPHAS}
                section['observed']['move_legality']=checks
                section['observed']['measure_ref']=key;replay['support_catalog'][newref]=section
            p['support_ref']=newref
    replay['empirical_measures']=catalog
    replay['empirical_measure_model']=dict(version='M3.4.4',alphas=list(ALPHAS),default_alpha=default_alpha,smoothing=dict(a=a,b=b),
        sampling='all_eligible_vgc_occurrences_no_deduplication',
        definition='Q_t(record) proportional to 1_H P(record) product p_hat(move)^(-alpha) for distinct revealed matches; core share is pushforward sum',
        probability_claim=False)
    return perf_counter()-start
