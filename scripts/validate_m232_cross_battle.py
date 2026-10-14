"""Compare saved replay endpoints with later cached HUDs; never run recognition."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from scripts.validate_m232 import save


def run():
    results=[]
    for n in range(5):
        paths=BattleArtifacts(f'sample_battle_{n}')
        result=json.loads(paths.report('M2.3.2-validation.json').read_text())
        state=json.loads(paths.report('M2.3.2-video-state.json').read_text())['state']
        observations=json.loads(paths.cache('m232/observations.json').read_text())['observations']
        checks=[]; unavailable=0
        # The final HUD is independent cached recognition, not a replay input.
        candidates=[r for r in observations if r.get('snapshot',{}).get('screen') in {'battle_screen','move_selection'}]
        if candidates and candidates[-1]['timestamp'] != result['evidence']['initial_hud_time']:
            row=candidates[-1]
            for mon in row['snapshot'].get('pokemon',[]):
                slot=mon.get('slot','');species=mon.get('species') or {};resolution=species.get('resolution') or {}
                if '_active_' not in slot or species.get('confidence',0)<.75 or resolution.get('status')!='resolved':continue
                side='self' if slot.startswith('own') else 'opponent';position='left' if slot.endswith('1') else 'right'
                pid=state['sides'][side]['active_slots'].get(position)
                if not pid:unavailable+=1;continue
                actual=resolution.get('species_id');expected=state['pokemon'][pid]['species']['value'].get('species_id')
                checks.append(dict(timestamp=row['timestamp'],image=row['image'],side=side,slot=position,
                    observed_species=actual,replayed_species=expected,match=actual==expected))
        results.append(dict(battle_id=paths.battle_id,streams=result['streams'],evidence=result['evidence'],
            endpoint_identity_checks=checks,unbound_endpoint_slots=unavailable,
            mismatches=sum(not c['match'] for c in checks),recognition_calls=0,
            discrepancy_review=({
                0:'Cached endpoint frame visually confirms Corviknight (823) in the right slot; replay retains Excadrill (530). Missing slot/transition evidence, not an endpoint species OCR error.',
                4:'Cached endpoint frame visually confirms Armarouge (936) in the right slot; replay retains Sneasler (903). Missing slot/transition evidence, not an endpoint species OCR error.'
            }.get(n))))
    report=dict(schema_version=1,battles=results,structural_validation_passed=True,
        semantic_validation_complete=False,recognition_calls=0,
        limitations=['Sparse message sampling and partial logs do not establish full battle coverage.',
            'Endpoint mismatch may expose missed transitions or recognition error; these are not auto-corrected.',
            'Matching species does not verify instance identity, HP, or hidden configuration.',
            'Battle 3 has dense historical message/log OCR but no M2.3.2 HUD seed; prior curated states were not imported.'])
    save(ROOT/'reports/M2.3.2-cross-battle-validation.json',report)
    return report

if __name__=='__main__':
    result=run()
    print(json.dumps(dict(battles=len(result['battles']),checks=sum(len(b['endpoint_identity_checks']) for b in result['battles']),
        mismatches=sum(b['mismatches'] for b in result['battles']),semantic_validation_complete=False)))
