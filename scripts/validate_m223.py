"""Validate cached multi-turn replay against independent decision-screen HP.

Read saved predictions and replay states only: no OCR/model/media execution.
"""
from copy import deepcopy
import json
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.reconstruct_m223 import ROOT, save
from battle_artifacts import BattleArtifacts, add_arguments
from tracking.state_engine import StateEngine


def main():
    parser=argparse.ArgumentParser(description=__doc__);add_arguments(parser);args=parser.parse_args()
    paths=BattleArtifacts.select(args.battle_id,args.video,default="sample_battle_3").prepare()
    saved=json.loads((paths.report('M2.2.3-battle-state.json')).read_text())
    paths.check_identity(saved['initial_state']['battle_id'])
    engine=StateEngine.from_dict(saved)
    if json.loads(json.dumps(engine.to_dict()))!=saved:raise AssertionError('Serialized replay differs')
    snapshots=json.loads((paths.report('M2.2.3-state-snapshots.json')).read_text())['snapshots']
    checks=[];identities=[]
    for turn,frame_key in [(1,176),(2,254),(3,302),(4,364),(5,446),(6,508),(7,608)]:
        index=next(i for i,r in enumerate(saved['history']) if r['event']['event_type']=='turn_boundary' and
                   r['event']['attributes']['turn']==turn and r['event']['attributes']['boundary']=='end')
        state=snapshots[index]['state']
        observation=json.loads((paths.cache(f'm223-snapshots/{frame_key}.json')).read_text())
        for p in observation['pokemon']:
            side='self' if p['slot'].startswith('own_active_') else 'opponent'
            slot='left' if p['slot'].endswith('1') else 'right'
            pid=state['sides'][side]['active_slots'].get(slot)
            if not pid:
                identities.append({'turn':turn,'slot':p['slot'],'result':'missing_active_instance'})
                continue
            mon=state['pokemon'][pid];raw_name=p['species']['raw_text']
            # Explicit nickname annotation is separate from OCR text predictions.
            names={'GreatGeneral':983,'Sally':373}
            observed_sid=(p['species'].get('resolution') or {}).get('species_id') or names.get(raw_name)
            identities.append({'turn':turn,'slot':p['slot'],'observed_name':raw_name,'observed_species_id':observed_sid,
                'replayed_species_id':mon['species']['value']['species_id'],
                'result':'match' if observed_sid==mon['species']['value']['species_id'] else 'unresolved_or_conflict'})
            hp=p['hp']['value']
            if hp is None:
                checks.append({'turn':turn,'slot':p['slot'],'result':'OCR_endpoint_unresolved'})
                continue
            field='current' if side=='self' else 'displayed_percent'
            predicted=mon['hp'][field]['value'];observed=hp['current'] if side=='self' else hp
            source=observation['capture_metadata']
            checks.append({'turn':turn,'slot':p['slot'],'pokemon_instance_id':pid,'unit':field,
                'state_value':predicted,'independent_video_value':observed,
                'result':'match' if predicted==observed else 'missing_state_fact' if predicted is None else 'conflict',
                'image':source['image'],'timestamp':observation['timestamp'],'timestamp_uncertainty_seconds':2,
                'recognition_confidence':p['hp']['confidence'],'nickname_binding_manual':raw_name in names})
    result={'schema_version':1,'method':'independent HUD OCR compared against end-of-turn reconstructed states; initial/aliases/log ordering manually annotated',
            'hp_checks':checks,'identity_checks':identities,'deterministic_replay':True,
            'limitation':'Seven decision-screen checkpoints; not frame-by-frame ground truth or a complete accuracy estimate'}
    save(paths.report('M2.2.3-cross-source-validation.json'),result)
    conflicts=[v for v in checks if v['result']=='conflict']+[v for v in identities if v['result']=='unresolved_or_conflict']
    print(len(checks),'HP checkpoints;',len(identities),'identity checkpoints;',len(conflicts),'conflicts')
    if conflicts:print(json.dumps(conflicts,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
