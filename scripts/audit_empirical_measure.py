"""M3.4.4 alpha sensitivity on sealed published observations, no recollection."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_evidence.empirical_measure import catalog,tilt,inclusion,ALPHAS
from battle_evidence.move_legality import move_legality
from battle_evidence.speed_replay_offline import atomic,file_hash


def run(output):
    results=[];inputs={};source_scope=None
    for n in (11,12):
        pointer=json.loads((ROOT/f'.cache/battles/sample_battle_{n}/m342-offensive/latest-practical.json').read_text());path=Path(pointer['path'])
        r=json.loads(path.read_text());manifest=json.loads(path.with_name('manifest.json').read_text())
        assert manifest['status']=='complete' and file_hash(path)==manifest['outputs']['replay.json']
        if r.get('empirical_measure_model',{}).get('version')!='M3.4.4':raise ValueError('Generate M3.4.4 packages first')
        population=json.loads((ROOT/r['empirical_artifact']).read_text());inputs[str(path)]=file_hash(path)
        source_scope=population['scope']
        for form in ('pokeapi:form:10530','pokeapi:species:858','pokeapi:species:727'):
            if form not in r['empirical_core_catalogs']:continue
            cat=catalog(population,form)
            # All chronological states for the matching actor/form. Deduplicate
            # unchanged measures; moves are taken from actual source snapshots.
            seen=set();states=[]
            for snap in r['snapshots']:
                for iid,p in snap['opponents'].items():
                    if p.get('current_form')!=form:continue
                    s=r['support_catalog'][p['support_ref']]['observed'];key=s.get('measure_ref')
                    if key is None or key in seen:continue
                    seen.add(key);variants=r['empirical_measures'][key];states.append(dict(timestamp=snap['timestamp'],individual=iid,
                        moves=variants['0.5']['moves'],variants={a:dict(surviving_records=v['surviving_records'],surviving_cores=v['surviving_cores'],
                            effective_sample_size=v['effective_sample_size'],largest_record_share=v['largest_record_share'],top_cores=v['cores'][:5],frequencies=v['frequencies']) for a,v in variants.items()}))
            probes=[]
            available=sorted({m for rec in cat['records'].values() for m in rec['template']['moves'] if move_legality(form,m)['status']=='confirmed_possible'})
            candidates=[(inclusion(cat['frequency_rows'],m)['smoothed_frequency'],m) for m in available if inclusion(cat['frequency_rows'],m)['positive']>0]
            if candidates:
                _,rare=min(candidates)
                for alpha in ALPHAS:
                    measure=tilt(cat['records'],cat['frequency_rows'],[rare],alpha=alpha)
                    probes.append(dict(alpha=alpha,move=rare,frequency=measure['frequencies'][rare],top_cores=measure['cores'][:5],largest_record_share=measure['largest_record_share'],effective_sample_size=measure['effective_sample_size']))
            results.append(dict(move_frequencies={m:inclusion(cat['frequency_rows'],m) for m in sorted({m for r in cat['records'].values() for m in r['template']['moves']})},source_independent_rarity_probe=probes,rarity_probe_interpretation='Synthetic move revelation selected from real species templates, NOT an actual battle observation or inference constraint',battle=n,form=form,frequency_population=len(cat['frequency_rows']),frequency_observations=len(cat['frequency_rows']),eligible_observations=len(cat['records']),eligible_records=len(cat['records']),eligible_cores=len(cat['cores']),
                excluded_incomplete_cores=len(cat['core_ineligible']),observations_removed_by_deduplication=0,grouping=cat['grouping'],states=states))
    atomic(output,dict(milestone='M3.4.4',source_scope=source_scope,alphas=list(ALPHAS),initial_experimental_default=.5,smoothing=dict(a=.5,b=.5),inputs=inputs,contexts=results,
        calibration_diagnostic=dict(fixed_matching_multiplier=4,ten_nonmatching_vs_three_matching=dict(A=10,B=12,winner='B'),hundred_nonmatching_vs_three_matching=dict(A=100,B=12,winner='A'),interpretation='Controlled scoring diagnostic, not an override of empirical data'),
        interpretation='Sensitivity diagnostics; not calibrated probabilities or independent encounter observations'))
    for c in results:
        print(c['battle'],c['form'],'N',c['frequency_population'],'cores',c['eligible_cores'],'records',c['eligible_records'])
        for s in c['states']:
            if s is c['states'][-1] or len(s['moves'])>0:
                print(' ',round(s['timestamp'],3),s['moves'],[(a,round(v['largest_record_share'],4),v['surviving_records']) for a,v in s['variants'].items()])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);run(p.parse_args().output)
