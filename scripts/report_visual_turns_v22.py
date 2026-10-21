"""Cache-only, checkpointed v2.2 replay and post-holdout regression review."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import html
import json
import sys
import time
import resource
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from speed_inference.offline import atomic_json,file_hash
from battle_evidence.visual import VisualPhaseEstimator
from battle_evidence.visual_v22 import VisualPhaseEstimatorV22,replay_observations,VERSION
from battle_evidence.visual_v21 import evaluate
from battle_evidence.ui_counters import CounterTimeline,reconcile_segments
from battle_evidence.turns import TurnReconstruction
from battle_evidence.durations import EffectDurations
from scripts.report_visual_turns_v21 import render,page,rel,show

CACHE=ROOT/'.cache/m34-visual-v22'


def preservation():
    baseline=json.loads((CACHE/'preservation-baseline.json').read_text())
    changed=[p for p,h in baseline.items() if not Path(p).is_file() or file_hash(Path(p))!=h]
    if changed:raise ValueError('Historical files changed: '+str(changed))
    return dict(files_verified=len(baseline),changed=changed)


def categories(e):
    outside=e['outside_tolerance_associations']
    return dict(matches=len(e['matches']),bounded=sum(x['timing_quality']=='within_2s' for x in e['matches']),
        unresolved=sum(x['timing_quality']=='insufficient_localization' for x in e['matches']),
        outside=len(outside),missing=len(e['missed_reference_boundaries'])-len(outside),
        spurious=len(e['unmatched_predictions'])-len(outside),
        merge_alerts=len(e['possible_merges']),split_alerts=len(e['possible_splits']),
        submenu_alerts=len(e['submenu_false_turn_review_alerts']))


def replay(p, estimator):
    for o in replay_observations(p):estimator.consume(o)
    return estimator.export()


def run(n):
    started=time.perf_counter();bid=f'sample_battle_{n}'
    old_e=Path(f'.cache/battles/{bid}/m34-visual-v21/evaluation.json')
    frozen_eval=json.loads(old_e.read_text());input_path=Path(frozen_eval['prediction']);p=json.loads(input_path.read_text())
    dest=ROOT/f'.cache/battles/{bid}/m34-visual-v22';dest.mkdir(exist_ok=True)
    output=dest/'visual-evidence.json';manifest=dest/'manifest.json'
    deps=['battle_evidence/visual_v22.py','battle_evidence/visual.py','battle_evidence/visual_v21.py',
          'battle_evidence/ui_counters.py','battle_evidence/durations.py','battle_evidence/turns.py',__file__]
    identity=dict(version=VERSION,input=str(input_path),input_sha256=file_hash(input_path),
                  dependencies={str(x):file_hash(Path(x)) for x in deps})
    if manifest.exists():
        m=json.loads(manifest.read_text())
        if m['identity']!=identity:raise ValueError('Preserve prior run and version namespace before invalidated replay')
        if m['status']=='complete' and output.exists() and file_hash(output)==m['output_hash']:
            return json.loads(output.read_text()),m['metrics']
    atomic_json(manifest,dict(identity=identity,status='running',stage='sealed-input-replay'))
    try:
        baseline=replay(p,VisualPhaseEstimator(bid,profile='v2'))
        assert baseline['phase_history']==p['visual']['phase_history'], 'Temporal input reconstruction lost evidence'
        assert [(s['id'],s['end'],s['status']) for s in baseline['segments']]==[(s['id'],s['end'],s['status']) for s in p['visual']['segments']]
        visual=replay(p,VisualPhaseEstimatorV22(bid));ct=CounterTimeline()
        for o in p['counter_observations']:ct.consume(o)
        assert ct.observations==p['counter_observations'], 'Counter observations changed'
        turns=TurnReconstruction(bid)
        for e in p['reconstruction']['ledger']:turns.consume(e)
        live=[e for e in turns.ledger if e.get('timestamp') is not None and not e.get('source_retracted') and not e.get('source_revision_requires_review')]
        live.sort(key=lambda e:e['timestamp'])
        visual['segments']=reconcile_segments(visual['segments'],ct,live);turns.attach_visual(visual['segments'])
        effects=EffectDurations();bi=ci=0;boundaries=visual['segments']
        for e in live:
            while bi<len(boundaries) and boundaries[bi]['next_command_time']<=e['timestamp']:
                effects.advance_visual_boundary(boundaries[bi]);bi+=1
            while ci<len(ct.observations) and ct.observations[ci]['timestamp']<=e['timestamp']:
                effects.observe_ui_counter(ct.observations[ci]);ci+=1
            effects.consume(e,turns.assignment[e['id']])
        while bi<len(boundaries):effects.advance_visual_boundary(boundaries[bi]);bi+=1
        while ci<len(ct.observations):effects.observe_ui_counter(ct.observations[ci]);ci+=1
        result=dict(schema=VERSION,battle_id=bid,input_identity=identity,visual=visual,
                    reconstruction=turns.export(),counter_observations=ct.observations,
                    counter_constraints=ct.constraints,effects=effects.snapshot(),effect_history=effects.history,
                    scope='Visual segmentation and relative effect clocks only; no StateEngine or speed/Bayesian replay')
        if n<10:
            assert visual['phase_history']==p['visual']['phase_history']
            assert visual['segments']==p['visual']['segments']
            assert result['effects']==p['effects']
        else:
            assert visual['segments'][:8]==p['visual']['segments']
            assert len(visual['segments'])==9
        atomic_json(output,result)
        metrics=dict(seconds=time.perf_counter()-started,observations_replayed=len(visual['phase_history']),
                     new_frames=0,video_decodes=0,ocr_calls=0,state_engine_replays=0,
                     source_frame_reads=0,baseline_replay_verified=True,peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024/1024)
        atomic_json(manifest,dict(identity=identity,status='complete',output_hash=file_hash(output),metrics=metrics))
        print(json.dumps(dict(battle_id=bid,stage='complete',**metrics)),flush=True)
        return result,metrics
    except Exception as exc:
        atomic_json(manifest,dict(identity=identity,status='failed',error=repr(exc)));raise


def main():
    import os
    os.chdir(ROOT);preservation();rows=[];index=page('M3.4 v2.2 — targeted post-holdout regression')
    index+=['<p>Two-second reference standard and 2s tolerance retained. B10 is post-holdout regression, not an independent holdout. B6 remains genuinely late after a brief visible command frame before Battle Log.</p>',
            '<p><a href="../m34-visual-v21/review.html">Preserved v2.1 review</a></p>']
    for n in range(5,11):
        bid=f'sample_battle_{n}';dest=ROOT/f'.cache/battles/{bid}/m34-visual-v22'
        p,metrics=run(n)
        frozen=json.loads(Path(f'.cache/battles/{bid}/m34-visual-v21/evaluation.json').read_text())
        refpath=Path(f'reports/battles/{bid}/inputs/M3.4-visual-reference-v21.json')
        ref=json.loads(refpath.read_text());historical=evaluate(ref,p)
        corrected_path=Path('reports/battles/sample_battle_6/inputs/M3.4-visual-reference-v22.json') if n==6 else refpath
        current_ref=json.loads(corrected_path.read_text());e=evaluate(current_ref,p)
        e.update(reference=str(corrected_path),reference_sha256=file_hash(corrected_path),prediction=str(dest/'visual-evidence.json'),
                 categories=categories(e),evaluation_role='targeted post-holdout regression' if n==10 else 'development regression')
        frozen_p=json.loads(Path(frozen['prediction']).read_text())
        corrected_old=evaluate(current_ref,frozen_p)
        # Report counts and source-backed false-positive checks separately from
        # broad interval merge/split diagnostics.
        ranges=[x for x in current_ref.get('intervals',[]) if x['kind']=='replacement_or_pivot_selection']
        forced=[dict(prediction=s['id'],time=s['next_command_time'],reviewed_interval=x['interval'])
                for s in p['visual']['segments'] for x in ranges
                if x['interval'][0]<=s['next_command_time']<x['interval'][1]]
        audit=dict(frozen_v21=categories(frozen),v22_against_historical_reference=categories(historical),
            v21_against_current_reference=categories(corrected_old),v22_against_current_reference=categories(e),
            segment_statuses=dict(Counter(s['status'] for s in p['visual']['segments'])),
            forced_selection_boundary_alerts=forced,
            segment_counter_relations=dict(Counter(c['status'] for s in p['visual']['segments'] for c in s['counter_evidence'])),
            reference_counter_checks=dict(Counter(c['status'] for c in e['counter_checks'])),
            raw_counters_unchanged=p['counter_observations']==frozen_p['counter_observations'],
            effects_unchanged=p['effects']==frozen_p['effects'],metrics=metrics)
        atomic_json(dest/'evaluation.json',e);atomic_json(dest/'historical-reference-evaluation.json',historical)
        atomic_json(dest/'regression-audit.json',audit)
        render(current_ref,p,e,dest)
        review=(dest/'review.html').read_text().replace('v2.1 boundary review','v2.2 boundary review').replace('-individual-review-v21.json','-individual-review-v22.json')
        if n==6:
            review=review.replace('M3.4-visual-reference-v21.json','M3.4-visual-reference-v22.json')
            review=review.replace('<button onclick="download()">','<p><a href="'+rel(ROOT/'reports/battles/sample_battle_6/inputs/M3.4-visual-human-observation-v22.json',dest)+'">Scoped human observations and chronology</a></p><button onclick="download()">')
        (dest/'review.html').write_text(review)
        index.append(f'<section><h2>{bid}</h2><a href="{rel(dest/"source.html",CACHE)}">Source only</a> · <a href="{rel(dest/"review.html",CACHE)}">Individual boundary review</a> · <a href="{rel(dest/"regression-audit.json",CACHE)}">v2.1/v2.2 audit</a><pre>{show(audit)}</pre></section>')
        rows.append(dict(battle_id=bid,**audit))
    (CACHE/'review.html').write_text('\n'.join(index))
    atomic_json(CACHE/'comparison.json',rows);atomic_json(CACHE/'preservation-result.json',preservation())
    print('Completed six cache-only replays and review pages; historical files unchanged')

if __name__=='__main__':main()
