"""Focused saved B21 evidence replay. Never decodes video, invokes OCR or writes benchmark inputs."""
from copy import deepcopy
from itertools import groupby
from pathlib import Path
import hashlib,json,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.event_report import atomic_json,video_events,verify_seal
from recognition.message_occurrences import MessageOccurrences
from tracking.battle_state import from_dict
from tracking.state_engine import StateEngine,EventRecord,ordering,event_from_dict
from battle_events.schema import stable_id

RUN='fresh-b21-context-v1'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def timestamp(e):return e['attributes'].get('observation_time',0)

def main():
    owner=BattleArtifacts('sample_battle_21');source=owner.cache('event-driven/'+RUN)
    target=owner.cache('diagnosis/'+sys.argv[1]);target.mkdir(parents=True,exist_ok=True)
    dependencies=['battle_events/parser.py','battle_events/message_patterns.py','battle_events/schema.py',
        'recognition/event_report.py','tracking/state_engine.py','tracking/evidence_fusion.py','tracking/hp_causes.py',
        'tracking/resolution_context.py','knowledge/data/52poke-resolution-v1.json','scripts/validate_b21_focused.py']
    verify_seal(source)
    identity=dict(inputs={n:digest(source/n) for n in ['replay.json','observations.json','video-only-seal.json']},
        sources={n:digest(ROOT/n) for n in dependencies},scope='original non-HUD prefix through 435s; per-numeric-run edge samples; new normal-command phase and explicit miss only')
    path=target/'focused-manifest.json'
    if path.exists():
        prior=read(path)
        if prior['identity']!=identity:raise ValueError('Changed validation identity; preserve completed run and use another namespace')
        if prior['status']=='complete':
            for n,h in prior['outputs'].items():assert digest(target/n)==h,n
            print('Reused completed focused validation');return
        raise ValueError('Incomplete stage: inspect saved error/process before resuming')
    m=dict(identity=identity,status='running',ocr_invocations=0,decoded_frames=0);atomic_json(path,m)
    try:
        frozen=read(source/'replay.json');obs=read(source/'observations.json');raw=[h['event'] for h in frozen['history']]
        selected=set()
        # Preserve the two first and two last reads of each unchanged HP run:
        # final plateaus remain supported, animation samples remain observations.
        for mon in frozen['state']['pokemon'].values():
            numeric=[o for o in mon['hp']['observations'] if 'unit' in o]
            for key,group in groupby(numeric,key=lambda o:(o['unit'],o['after'])):
                g=list(group)
                selected.update(o['evidence']['event_id'] for o in g[:2]+g[-2:])
        original=[deepcopy(e) for e in raw if timestamp(e)<=435 and
            (e['event_type']!='hud_observation' or e['event_id'] in selected)]
        rows=[r for r in obs['observations'] if r['timestamp']<=435]
        extra=[e for e in video_events(rows,obs['roster'],owner.battle_id) if e['event_type']=='phase_observation' and e['attributes'].get('resolution_cycle_start')]
        missrow=next(r for r in rows if 318.4<r['timestamp']<318.6)
        decision=MessageOccurrences(owner.battle_id,source_occurrence_ids=True).observe(missrow)
        misses=[e for e in decision['events'] if e['event_type']=='move_miss'];assert len(misses)==1
        for e in misses:
            e['attributes']['source_occurrence_event_id']=e['event_id']
            e['event_id']=stable_id(owner.battle_id,e['event_id']+':move_miss')
        extra+=misses
        assert not {e['event_id'] for e in extra}&{e['event_id'] for e in raw}
        combined=sorted(original+extra,key=lambda e:(timestamp(e),0 if e['event_type']=='hud_observation' else 1,
            next((i for i,r in enumerate(raw) if r['event_id']==e['event_id']),len(raw)),e['event_id']))
        engine=StateEngine(from_dict(frozen['initial_state']))
        engine.history=[EventRecord(e,i+1,ordering(event_from_dict(e),i+1)) for i,e in enumerate(combined)]
        m.update(selected_events=len(combined),preserved_events=len(original),added_events=len(extra));atomic_json(path,m)
        def progress(r,state):
            if r.delivery_index%50==0:
                m['processed_events']=r.delivery_index;atomic_json(path,m);print(r.delivery_index,'/',len(combined),flush=True)
        engine.replay(snapshot_callback=progress)
        assert all(next(r.event for r in engine.history if r.event['event_id']==e['event_id'])==e for e in original)
        projection=engine.hp_resolutions();before={h['event']['event_id']:h for h in frozen['history']}
        summary=[]
        for r in engine.history:
            e=r.event;resolved=r.bindings.get('resolved_event') or e
            if e['event_type']=='hp_change' and e['attributes'].get('qualitative_only') and '体力回复了' in e['original_text'].replace('\n','') or e['event_type']=='move_miss':
                old=before.get(e['event_id']);a=resolved['attributes']
                summary.append(dict(timestamp=timestamp(e),event_id=e['event_id'],text=e['original_text'],
                    before_status=old['application_status'] if old else 'no_structured_event',before_reason=old['reason'] if old else 'provisional_or_repeat',
                    after_status=r.application_status,after_reason=r.reason,actor=resolved['actor'],target=resolved['target'],
                    actor_binding=r.bindings.get('actor'),target_binding=r.bindings.get('target'),attributes=a,
                    hp_episodes=[x for x in projection['episodes'] if x['source_event_id']==e['event_id']]))
        atomic_json(target/'focused-replay.json',engine.to_dict())
        atomic_json(target/'focused-hp-resolutions.json',projection)
        atomic_json(target/'focused-summary.json',summary)
        atomic_json(target/'added-events.json',extra)
        assert len(summary)==9,len(summary)
        assert all(r['after_status']=='recorded_observation' for r in summary),[(r['timestamp'],r['after_status'],r['after_reason']) for r in summary]
        assert identity['inputs']=={n:digest(source/n) for n in identity['inputs']}
        m.update(status='complete',outputs={n:digest(target/n) for n in ['focused-replay.json','focused-hp-resolutions.json','focused-summary.json','added-events.json']},
            semantic_records_recovered=9,whole_match_accuracy_measured=False)
        atomic_json(path,m)
        print([(r['timestamp'],r['after_status'],r['attributes'].get('cause'),len(r['hp_episodes'])) for r in summary])
    except BaseException as exc:
        m.update(status='failed',error=repr(exc));atomic_json(path,m);raise
if __name__=='__main__':main()
