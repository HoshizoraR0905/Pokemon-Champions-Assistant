"""Read-only B21 occupancy evidence audit; no placement or identity corrections."""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import ast,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.event_report import atomic_json,verify_seal
from tracking.state_engine import StateEngine,EventRecord,ordering,event_from_dict
from tracking.battle_state import from_dict
from tracking.double_faint import pending_pair

def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stamp(e):return e['attributes'].get('observation_time',0)
def main():
    owner=BattleArtifacts('sample_battle_21');src=owner.cache('event-driven/fresh-b21-context-v1')
    out=owner.cache('diagnosis/recovery-miss-occupancy-20261029-v1');verify_seal(src)
    frozen=read(src/'replay.json');obs=read(src/'observations.json');events=frozen['history']
    deferred=[h for h in events if h['application_status']=='deferred']
    occupancy=[h for h in deferred if h['reason']=='message_episode_occupancy_unresolved']
    kinds={'trainer_observation','preview_observation','entry_observation','send_out','switch_out','faint','transformation'}
    kept=[deepcopy(h['event']) for h in events if h['event']['event_type'] in kinds]
    engine=StateEngine(from_dict(frozen['initial_state']))
    engine.history=[EventRecord(e,i+1,ordering(event_from_dict(e),i+1)) for i,e in enumerate(kept)]
    snapshots=[]
    def capture(r,state):
        def mon(pid):
            p=state.pokemon[pid]
            return dict(instance_id=pid,species=p.species.value,location=p.location.value)
        snapshots.append(dict(timestamp=stamp(r.event),event_id=r.event['event_id'],kind=r.event['event_type'],text=r.event['original_text'],
            status=r.application_status,reason=r.reason,
            sides={s:dict(active_slots={slot:mon(pid) for slot,pid in team.active_slots.items()},vacant_slots=team.vacant_slots) for s,team in state.sides.items()},
            unplaced_entries=deepcopy(state.knowledge.get('unplaced_entries',[])),
            opponent_double_faint_pair_ready=bool(pending_pair(state,'opponent'))))
    engine.replay(snapshot_callback=capture)
    assert {s:team.active_slots for s,team in engine.state.sides.items()}=={s:team['active_slots'] for s,team in frozen['state']['sides'].items()}
    def receipt(h):
        e=h['event'];r=h['bindings'].get('resolved_event') or e
        return dict(timestamp=stamp(e),event_id=e['event_id'],kind=e['event_type'],text=e['original_text'],side=e['side'],
            status=h['application_status'],reason=h['reason'],actor=r.get('actor'),uncertainty=r['uncertainty'],
            raw_ocr_confidence=e['ocr_confidence'],message_identity=r['attributes'].get('message_identity'),
            actor_binding=h['bindings'].get('actor'),hud_slot=e['attributes'].get('slot'),evidence=e['evidence'])
    selected=[h for h in events if (487<stamp(h['event'])<536 and h['event']['event_type']!='hud_observation') or
        h in occupancy[:3] or h in occupancy[6:8]]
    # Only inspect already saved metadata. Human image review is documented separately.
    hud=next(r for r in obs['observations'] if 536<r['timestamp']<536.1)
    protection=read(out/'protected.json')
    print('protection keys',list(protection))
    audit={}
    for key,value in protection.items():
        if isinstance(value,dict):
            for file,h in value.items():
                if isinstance(h,str) and len(h)==64 and (ROOT/file).is_file():audit[file]=digest(ROOT/file)==h
    # AST isolates the untouched resolver despite intentional HP/miss branch edits.
    now=ast.parse((ROOT/'tracking/state_engine.py').read_text())
    resolver=lambda tree:ast.dump(next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_resolve'))
    audit['StateEngine._resolve_AST_unchanged']=protection['resolve_ast']==resolver(now)
    assert all(audit.values()),audit
    result=dict(frozen_replay_sha256=digest(src/'replay.json'),scope='identity-transition-only projection; original frozen receipts authoritative; no HP replay or slot fixes',
        deferred_total=len(deferred),occupancy_total=len(occupancy),occupancy_after_441=sum(stamp(h['event'])>441 for h in occupancy),
        occupancy_counts_by_side=dict(Counter(h['event']['side'] for h in occupancy)),
        first_occupancy=receipt(occupancy[0]),persistent_first=receipt(occupancy[6]),persistent_last=receipt(occupancy[-1]),
        transition_snapshots=snapshots,evidence_receipts=[receipt(h) for h in selected],
        nonoccupancy_deferred=[receipt(h) for h in deferred if h not in occupancy],
        saved_command_hud=dict(timestamp=hud['timestamp'],source_id=hud['source_id'],sha256=hud['sha256'],image=hud['image'],
            command_inspection=hud['command_inspection'],cards=[dict(slot=m['slot'],species=m.get('species'),icon=m.get('icon'),hp=m.get('hp')) for m in hud['snapshot']['pokemon']]),
        protected_code=audit,decoded_frames=0,ocr_invocations=0)
    atomic_json(out/'occupancy-diagnosis.json',result)
    print('Deferrals',len(deferred),'occupancy',len(occupancy),'post441',result['occupancy_after_441'],'transition snapshots',len(snapshots),'code protection',audit)
if __name__=='__main__':main()
