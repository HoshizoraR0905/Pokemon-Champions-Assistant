"""Scoped, cache-first B20 saved-message validation; no video/OCR or benchmark writes."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.event_report import atomic_json,verify_seal
from recognition.fast_video import digest
from recognition.message_occurrences import MessageOccurrences
from tracking.battle_state import from_dict
from tracking.state_engine import StateEngine,EventRecord
from battle_events.schema import stable_id

RUN='fresh-b20-postfix-v1'
WINDOWS={'applied':(200,210,216),'continued':(300,231,235),'self-hit':(400,279,306)}
DEPENDENCIES=['battle_events/parser.py','battle_events/message_patterns.py','recognition/message_occurrences.py',
 'tracking/state_engine.py','tracking/evidence_fusion.py','tracking/hp_causes.py','tracking/resolution_context.py',
 'knowledge/resolution_effects.py','knowledge/data/52poke-resolution-v1.json','scripts/validate_confusion_struggle.py']


def read(p):return json.loads(p.read_text())
def timestamp(e):return e['attributes'].get('observation_time',0)


def run_stage(owner,name,experiment,*,omit_confusion_notice=False):
    source=owner.cache('event-driven/'+RUN);seal=verify_seal(source)
    target=owner.cache('diagnosis/'+experiment+'/'+name);target.mkdir(parents=True,exist_ok=True)
    checkpoint,start,end=WINDOWS[name]
    snapshot=owner.cache(f'fresh-benchmark/{RUN}/verification/recovery-v1/snapshots/{checkpoint:06d}.json')
    identity=dict(frozen_seal_sha256=digest(source/'video-only-seal.json'),snapshot_sha256=digest(snapshot),
        observations_sha256=digest(source/'observations.json'),replay_sha256=digest(source/'replay.json'),
        window=[start,end],omit_confusion_notice=omit_confusion_notice,sources={s:digest(ROOT/s) for s in DEPENDENCIES})
    path=target/'manifest.json'
    if path.exists():
        prior=read(path)
        if prior['identity']!=identity:raise ValueError('Stage identity changed; preserve prior outputs and use a new --experiment')
        if prior['status']=='complete':
            for file,sha in prior['outputs'].items():assert digest(target/file)==sha,file
            print(name,'reusing compatible completed validation',flush=True);return prior
        raise ValueError('Prior incomplete stage: inspect process/error before resuming in a new experiment')
    m=dict(status='running',identity=identity,stage='seed',window=[start,end],ocr_invocations=0,
           video_frames_decoded=0,frozen_benchmark_modified=False)
    atomic_json(path,m);began=time.perf_counter()
    try:
        frozen=read(source/'replay.json');all_events=[h['event'] for h in frozen['history']]
        seed_events=[e for e in all_events[checkpoint:] if timestamp(e)<start]
        engine=StateEngine(from_dict(read(snapshot)))
        engine.history=[EventRecord(deepcopy(e),i+1,None) for i,e in enumerate(seed_events)]
        # Explicit local ordering; preserve original payload/IDs and their relative order.
        from tracking.state_engine import ordering,event_from_dict
        for i,r in enumerate(engine.history):r.ordering=ordering(event_from_dict(r.event),i+1)
        engine.replay();seed=engine.state.to_dict();atomic_json(target/'seed.json',seed)
        rows=[deepcopy(r) for r in read(source/'observations.json')['observations'] if start<=r['timestamp']<=end]
        occurrences=MessageOccurrences(owner.battle_id,source_occurrence_ids=True);new=[]
        for row in rows:
            decision=occurrences.observe(row)
            for e in decision['events']:
                a=e['attributes']
                if (e['event_type']=='volatile_change' and a.get('condition')=='confusion' or
                        (a.get('cause') or {}).get('kind')=='confusion_self_damage'):
                    if omit_confusion_notice and e['event_type']=='volatile_change':continue
                    # Old unknown fragments could later refine into an ordinary
                    # move under the same occurrence ID. Preserve that immutable
                    # original event; give this newly split finding its own ID.
                    a['source_occurrence_event_id']=e['event_id']
                    e['event_id']=stable_id(owner.battle_id,e['event_id']+':confusion:'+e['event_type']+':'+a.get('change','self_hit'))
                    new.append(e)
        original=[deepcopy(e) for e in all_events if start<=timestamp(e)<=end]
        assert not ({e['event_id'] for e in new}&{e['event_id'] for e in original})
        combined=sorted(original+new,key=lambda e:(timestamp(e),0 if e['event_type']=='hud_observation' else 1,
                                                 e['attributes'].get('sequence',10**9),e['event_id']))
        atomic_json(target/'new-events.json',new);m.update(stage='replay',seed_events=len(seed_events),
            original_events=len(original),new_events=len(new),selected_observations=len(rows));atomic_json(path,m)
        engine=StateEngine(from_dict(seed))
        engine.history=[EventRecord(e,i+1,ordering(event_from_dict(e),i+1)) for i,e in enumerate(combined)]
        def progress(record,state):
            if record.delivery_index%20==0:
                m['processed_events']=record.delivery_index;atomic_json(path,m)
                print(name,record.delivery_index,'/',len(combined),flush=True)
        engine.replay(snapshot_callback=progress)
        assert all(r.application_status in {'applied_candidate','applied_confirmed','applied_partial','recorded_observation'}
                   for r in engine.history if r.event['event_id'] in {e['event_id'] for e in new})
        projection=engine.hp_resolutions()
        if name=='self-hit':
            hits=[o for o in projection['episodes'] if (o.get('cause') or {}).get('kind')=='confusion_self_damage']
            assert len(hits)==1
            hit=hits[0];assert (hit['before'],hit['after'],hit['delta'],hit['unit'])==(17,10,-7,'displayed_percent')
            assert hit['actor_instance_id']==hit['affected_instance_id'] and hit['parent_action_id'] is None
            assert hit['attribution_status']=='supported' and hit['source_move'] is None
            m['self_hit']=dict(before=17,after=10,delta=-7,unit='displayed_percent',actor=hit['actor_instance_id'],
                cause=hit['cause'],source_event_id=hit['source_event_id'],segment_event_ids=hit['segment_event_ids'])
            receipt=next(r for r in engine.history if r.event['event_id']==hit['source_event_id'])
            m['self_hit']['binding_basis']=receipt.bindings['resolved_event']['attributes']['binding_basis']
            if omit_confusion_notice:assert m['self_hit']['binding_basis']=='unique_observed_confusion_hp_decrease'
        for e in original:
            assert next(r.event for r in engine.history if r.event['event_id']==e['event_id'])==e
        atomic_json(target/'replay.json',engine.to_dict());atomic_json(target/'hp-resolutions.json',projection)
        assert verify_seal(source)==seal
        m.update(status='complete',stage='complete',wall_seconds=time.perf_counter()-began,
            original_event_ids_and_payloads_preserved=True,outputs={f:digest(target/f) for f in
                ['seed.json','new-events.json','replay.json','hp-resolutions.json']},
            limitation='Local snapshot-seeded window, not full-match replay/accuracy or Struggle footage validation. Historical HP before the seed is not revalidated.')
        atomic_json(path,m);print(name,'complete',m.get('self_hit'),flush=True);return m
    except BaseException as exc:
        m.update(status='failed',error=repr(exc),wall_seconds=time.perf_counter()-began);atomic_json(path,m);raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',choices=['all',*WINDOWS],default='all')
    p.add_argument('--omit-confusion-announcement',action='store_true',help='Saved-data ablation only; preserve source observations')
    p.add_argument('--experiment',default='confusion-struggle-20261029-v1');a=p.parse_args()
    owner=BattleArtifacts('sample_battle_20',ROOT)
    if a.omit_confusion_announcement and a.stage!='self-hit':p.error('Announcement ablation requires --stage self-hit')
    for name in WINDOWS if a.stage=='all' else [a.stage]:run_stage(owner,name,a.experiment,omit_confusion_notice=a.omit_confusion_announcement)
