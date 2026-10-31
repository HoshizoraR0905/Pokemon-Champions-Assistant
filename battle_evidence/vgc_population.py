"""Read existing VGC canonical exports without publication-family compression.

Every eligible member occurrence in every selected VGC team record has one
vote, including identical builds and identical teams. Equality diagnostics never
change weights. Original publication/extraction/member IDs are retained.
No collection or DB writes.
"""
from collections import defaultdict
from copy import deepcopy
import json

from knowledge.champions_stats import ChampionsStats, STATS
from metagame.published import VERSION
from metagame.published.observed import eligibility
from metagame.published.speed_support import alignment
from metagame.published.store import Teams
from speed_order.core import knowledge
from .empirical_measure import full_record_signature, digest


def load_vgc(root):
    db=Teams(root,readonly=True)
    try:
        publications=sorted((r for r in db.scoped('tournament_published','M-C','Doubles',VERSION)
                             if r['source_id']=='vgcmulticalc'),key=lambda r:r['id'])
    finally:db.close()
    complete=[];incomplete=[];raw_payloads=defaultdict(list)
    for p in publications:
        if p.get('record_sha256'):raw_payloads[p['record_sha256']].append(p['id'])
        canonical=json.loads(p['canonical'])
        for ordinal,m in enumerate(canonical['members']):
            n=m['normalized'];valid=eligibility(m)
            a=alignment(n['nature']) if valid['nature'] else None
            points=dict(zip(STATS,n['sp']['values'])) if valid['sp'] else None
            speed=None;issue=None
            if points is not None and a is not None and n['species']:
                try:
                    form='as_named' if knowledge().entities[n['species']].form_id else 'base'
                    speed=ChampionsStats(n['species'],form=form).calculate(points,a)['stats']['speed']
                except (ValueError,NotImplementedError) as e:issue=str(e)
            original_id=f"{p['id']}:{p['extraction_id']}:member:{ordinal}"
            row=dict(species=n['species'],item=n['item'] if valid['item'] else None,
                ability=n['ability'] if valid['ability'] else None,nature=n['nature'] if valid['nature'] else None,
                alignment=a,training_points=points,speed=speed,configuration=deepcopy(n),
                complete=bool(m['exact_complete'] and speed is not None),build_id=m.get('pokemon_build_id'),
                observed_team_signature=canonical.get('exact_build_id') or digest(canonical['composition']),
                empirical_record_id='vgc-occurrence:'+original_id,original_record_ids=[original_id],missing=m['missing'],issues=m['issues'],stat_issue=issue,
                publications=[dict(id=p['id'],extraction_id=p['extraction_id'],member_ordinal=ordinal,
                    original_record_id=original_id,url=p['source_url'],source_key=p['source_key'],source_id=p['source_id'])])
            (complete if row['complete'] else incomplete).append(row)
    # Equality is diagnostic ONLY. Independent identical uses still count.
    identical=defaultdict(list)
    for row in complete:identical[full_record_signature(row)].append(row['empirical_record_id'])
    by=defaultdict(lambda:dict(builds=[]))
    for row in complete:by[row['species']]['builds'].append(row)
    scope=dict(source='vgcmulticalc',population='tournament_published',regulation='M-C',format='Doubles',
        canonical_version=VERSION,observation_unit='eligible_pokemon_occurrence_per_selected_vgc_team_observation',
        identity='original publication ID + active extraction ID + member ordinal; build equality does not merge IDs',
        initial_mass='equal per eligible occurrence; no deduplication or publication-family weighting',
        raw_publications=len(publications),raw_member_records=len(complete)+len(incomplete),
        selected_complete_raw_records=len(complete),incomplete_records_excluded=len(incomplete),
        observations_removed_by_deduplication=0,retained_eligible_occurrences=len(complete),
        distinct_training_cores=len({digest({k:v for k,v in r['configuration'].items() if k!='moves'}) for r in complete}))
    return dict(scope=scope,by_form=dict(by),identical_build_diagnostic=dict(interpretation='Equality only; does not establish technical ingestion duplication; no occurrences removed or reweighted',groups=[dict(signature=k,occurrence_ids=v) for k,v in identical.items() if len(v)>1],equal_build_excess_occurrences=sum(len(v)-1 for v in identical.values()),identical_raw_payload_groups=[dict(record_sha256=k,publication_ids=v) for k,v in raw_payloads.items() if len(v)>1]),
        incomplete_record_audit=[dict(original_record_ids=r['original_record_ids'],missing=r['missing'],issues=r['issues'],stat_issue=r['stat_issue']) for r in incomplete])
