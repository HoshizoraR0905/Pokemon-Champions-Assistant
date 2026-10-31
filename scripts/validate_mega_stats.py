"""Saved Team7/B22 form-stat validation only; no video decoding or OCR."""
import argparse
from copy import deepcopy
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from recognition.video_sampling import atomic_json
from tracking.form_stats import calculate_member,form_evidence
from tracking.state_engine import StateEngine,EventRecord
from tracking.battle_state import from_dict


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-id',required=True);a=parser.parse_args()
    from battle_artifacts import canonical_id
    canonical_id(a.run_id)
    out=ROOT/'.cache/mega-stats-validation'/a.run_id;out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'.cache/battles/sample_battle_22/diagnosis/b22-followup-validation-v4/team-linked-replay.json'
    team_path=ROOT/'tests/fixtures/battle_evidence/sample-team7-reviewed.json'
    files=[source,team_path,*[ROOT/p for p in ['tracking/form_stats.py','tracking/state_engine.py','tracking/transformation.py',
        'tracking/knowledge_grounding.py','knowledge/champions_stats.py','knowledge/data/mega-stat-evidence-v1.json','scripts/validate_mega_stats.py']]]
    identity={str(p.relative_to(ROOT)):sha(p) for p in files};mp=out/'manifest.json'
    if mp.exists():
        m=read(mp)
        if m['identity']!=identity:raise ValueError('Changed validation input; preserve and use another run ID')
        if m['status']=='complete':
            for p,h in m['outputs'].items():assert sha(out/p)==h,p
            print('Reused Mega stat validation',out);return
        raise ValueError('Inspect incomplete manifest/process before a new run')
    m=dict(status='running',identity=identity,decoded_frames=0,ocr_calls=0);atomic_json(mp,m)
    try:
        team=read(team_path);native=[];mega=[]
        for member in team['members']:
            result=calculate_member(member);native.append(dict(name=member['fields']['species']['value'],**result))
            for variant,e in form_evidence().items():
                if e['species_id']==member['species_id']:
                    mega.append(dict(name=e['canonical_id'],canonical_variant=variant,**calculate_member(member,variant)))
        assert len(native)==6 and len(mega)==5
        atomic_json(out/'calculated-stats.json',dict(original_displayed_values_verified=36,original=native,mega=mega))
        saved=read(source);engine=StateEngine(from_dict(saved['initial_state']))
        engine.history=[EventRecord(**deepcopy(r)) for r in saved['history']]
        def progress(r,state):
            if r.delivery_index%50==0:
                m['processed_events']=r.delivery_index;atomic_json(mp,m);print('Saved B22 replay',r.delivery_index,flush=True)
        engine.replay(snapshot_callback=progress)
        d=next(p for p in engine.state.pokemon.values() if (p.original_identity.value or {}).get('species_id')==132)
        first=d.transformations[0]['snapshot']
        assert first['form']['value']=='pokeapi:pokemon:10309'
        assert {k:v['value'] for k,v in first['non_hp_stats'].items()}==dict(attack=135,defense=106,special_attack=212,special_defense=105,speed=203)
        def numeric(state):
            return {o['evidence']['event_id']:(o['observed_before'],o['after'],o['unit'],o['delta'])
                    for p in state['pokemon'].values() for o in p['hp']['observations'] if o.get('delta') and 'unit' in o}
        assert numeric(saved['state'])==numeric(engine.state.to_dict()) and len(numeric(saved['state']))==45
        assert d.hp.displayed_percent.value==0 and not d.hp.maximum.known
        assert len([ep for ep in engine.state.knowledge['active_entry_episodes'] if ep['instance_id']==d.pokemon_instance_id])==2
        assert sum(r.application_status=='deferred' for r in engine.history)==12
        atomic_json(out/'replay.json',engine.to_dict())
        atomic_json(out/'summary.json',dict(original_stats_verified=36,calculated_mega_forms=5,
            ditto_first_copy=first,preserved_nonzero_hp_segments=45,original_deferred=12,
            form_resolutions=[dict(event_id=r.event['event_id'],resolved=r.bindings['resolved_event']['attributes'])
                for r in engine.history if r.event['event_type']=='transformation' and r.bindings.get('resolved_event')],
            conflicts=engine.state.conflicts,scope='Saved evidence, not full-video benchmark or whole-match accuracy'))
        assert all(sha(ROOT/p)==h for p,h in identity.items())
        m.update(status='complete',outputs={p:sha(out/p) for p in ['calculated-stats.json','replay.json','summary.json']});atomic_json(mp,m)
        print('Mega stats complete: 36 native values; 5 forms; B22 Ditto copies Mega Z non-HP stats; 45 HP segments unchanged.')
    except BaseException as exc:
        m.update(status='failed',error=repr(exc));atomic_json(mp,m);raise


if __name__=='__main__':main()
