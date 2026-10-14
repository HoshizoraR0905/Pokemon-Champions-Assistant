"""Enrich cached M2.2.3 without decoding, OCR, or overwriting its artifacts."""
from copy import deepcopy
from dataclasses import asdict
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts, add_arguments
from tracking.battle_state import from_dict
from tracking.state_engine import StateEngine, EventRecord, event_from_dict, ordering
from tracking.knowledge_grounding import initialize_team
from tracking.mechanic_rules import MechanicRules, showdown_champions_reference
from tracking.state_timeline import build_timeline, render_html


ARTIFACTS=BattleArtifacts('sample_battle_3')
def read(path):
    path=Path(path)
    if path.parts[0]=='reports':path=ARTIFACTS.report(path.name)
    elif str(path)=='data/teams/sample_battle_3_opening.json':path=ARTIFACTS.input('opening_team.json')
    return json.loads((ROOT/path).read_text())
def save(name,value): ARTIFACTS.report(name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def enrich(*, provisional=False, battle_id='sample_battle_3'):
    global ARTIFACTS
    ARTIFACTS=BattleArtifacts(battle_id).prepare()
    if ARTIFACTS.battle_id!='sample_battle_3':raise ValueError('M2.2.4 enrichment requires the sample_battle_3-specific opening/selection fixture')
    old=read('reports/M2.2.3-battle-state.json')
    opening=read('data/teams/sample_battle_3_opening.json')
    saved=read('data/teams/my_team.json')
    initial=from_dict(old['initial_state'])
    ARTIFACTS.check_identity(initial.battle_id)
    bindings={f'own_team_{n}':f'{ARTIFACTS.battle_id}:self:preview:{n}' for n in (2,3,5,6)}
    initial=initialize_team(initial,opening,saved=saved,bindings=bindings)
    initial.knowledge['move_grounding']=True
    rules=showdown_champions_reference() if provisional else MechanicRules()
    engine=StateEngine(initial,mechanic_rules=rules)
    engine.history=[EventRecord(deepcopy(r['event']),r['delivery_index'],deepcopy(r['ordering']),
                               revisions=deepcopy(r['revisions']),retracted=r['retracted']) for r in old['history']]
    snapshots=[]
    engine.replay(snapshot_callback=lambda r,s:snapshots.append({'event_id':r.event['event_id'],
        'application_status':r.application_status,'state_hash':r.state_hash,'state':s.to_dict()}))
    return engine,snapshots,old


def validate(engine,snapshots,old):
    legacy=read('reports/M2.2.3-state-snapshots.json')['snapshots']
    hp=identity=0
    checkpoints=read('reports/M2.2.3-cross-source-validation.json')
    for check in checkpoints['hp_checks']:
        index=next(i for i,r in enumerate(old['history']) if r['event']['event_type']=='turn_boundary' and r['event']['attributes'].get('turn')==check['turn'] and r['event']['attributes'].get('boundary')=='end' )
        value=snapshots[index]['state']['pokemon'][check['pokemon_instance_id']]['hp'][check['unit']]['value']
        assert value==check['independent_video_value'];hp+=1
    for check in checkpoints['identity_checks']:
        index=next(i for i,r in enumerate(old['history']) if r['event']['event_type']=='turn_boundary' and r['event']['attributes'].get('turn')==check['turn'] and r['event']['attributes'].get('boundary')=='end')
        side='self' if check['slot'].startswith('own') else 'opponent';slot='left' if check['slot'].endswith('1') else 'right'
        state=snapshots[index]['state'];pid=state['sides'][side]['active_slots'][slot]
        assert state['pokemon'][pid]['species']['value']['species_id']==check['observed_species_id'];identity+=1
    for original,new in zip(legacy,snapshots):
        for pid,p in original['state']['pokemon'].items():
            q=new['state']['pokemon'][pid]
            assert p['location']==q['location'] and p['fainted']==q['fainted'] and p['hp']['current']==q['hp']['current'] and p['hp']['displayed_percent']==q['hp']['displayed_percent']
    assert all(r.application_status not in {'deferred','rejected'} for r in engine.history)
    envelope=engine.to_dict()
    assert StateEngine.from_dict(envelope).to_dict()==envelope
    return {'hp_checkpoints':hp,'identity_checkpoints':identity,'all_prefix_locations_faints_hp_preserved':True,'deterministic_replay':True,'events':len(snapshots),'conflicts':engine.state.conflicts}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--provisional',action='store_true');add_arguments(parser);args=parser.parse_args();selected=BattleArtifacts.select(args.battle_id,args.video,default='sample_battle_3')
    engine,snapshots,old=enrich(provisional=args.provisional,battle_id=selected.battle_id)
    metrics=validate(engine,snapshots,old)
    stem='M2.2.4-provisional' if args.provisional else 'M2.2.4-enriched'
    save(stem+'-battle-state.json',engine.to_dict());save(stem+'-snapshots.json',{'schema_version':2,'snapshots':snapshots})
    timeline=build_timeline(engine.to_dict()['history'],engine.initial.to_dict(),snapshots,engine.state.to_dict())
    timeline['mechanic_rules']=engine.mechanic_rules.to_dict()
    ARTIFACTS.report(stem+'-timeline.html').write_text(render_html(timeline,artifact_root='../../../'))
    save(stem+'-validation.json',metrics);print(json.dumps(metrics,ensure_ascii=False))

if __name__=='__main__': main()
