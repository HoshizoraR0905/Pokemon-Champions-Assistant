"""Attach hidden constraints to the compact cached timeline; no observable replay/media."""
from copy import deepcopy
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts, add_arguments
from scripts.optimize_state_timeline import payload
from tracking.state_timeline import unpack_timeline, render_html, field_diff
from tracking.hidden_state import HiddenEngine, HiddenRules
from knowledge import KnowledgeBase
from tracking.pokemon_knowledge import pokemon_knowledge


ARTIFACTS=BattleArtifacts('sample_battle_3')
def read(name):return json.loads(ARTIFACTS.report(Path(name).name).read_text())


def run(*,provisional=False,battle_id='sample_battle_3'):
    global ARTIFACTS
    ARTIFACTS=BattleArtifacts(battle_id).prepare()
    if ARTIFACTS.battle_id!='sample_battle_3':raise ValueError('This cached validation replay uses sample_battle_3 checkpoints; HiddenEngine itself accepts any recording')
    source_stem='M2.2.4-provisional' if provisional else 'M2.2.4-enriched'
    old=read(f'{source_stem}-battle-state.json')
    ARTIFACTS.check_identity(old['initial_state']['battle_id'])
    source=unpack_timeline(payload(ARTIFACTS.report(f'{source_stem}-timeline.html').read_text()))
    engine=HiddenEngine(rules=HiddenRules('showdown-champions-reference-v1' if provisional else 'champions-evidence-only-v1'))
    if source['mechanic_rules'] != old['mechanic_rules']:
        raise ValueError('Cached observable state and timeline rules differ')
    if len(source['entries']) != len(old['history']) + 1:
        raise ValueError('Cached observable event prefixes differ')
    for record, entry in zip(old['history'], source['entries'][1:]):
        if record['event'] != entry['event']:
            raise ValueError('Cached observable event streams differ')
    if engine.rules.profile != old['mechanic_rules']['profile_id']:
        raise ValueError('Hidden and observable rules profiles differ')
    engine.seed(old['initial_state']);timeline={k:deepcopy(v) for k,v in source.items() if k!='entries'};timeline['entries']=[]
    kb=KnowledgeBase();names={}
    for r in old['history']:
        e=r['event']
        for ref in [e.get('actor'),e['attributes'].get('identity'),*e['canonical_references'].values()]:
            if isinstance(ref,dict) and ref.get('canonical_id') and ref.get('name'):
                names[ref['canonical_id']]=ref['name']
                if ref.get('canonical_identity'):names[ref['canonical_identity']]=ref['name']
    for cid in ['pokeapi:item:810','pokeapi:item:2240']:
        names[cid]=kb.entities[cid].names['zh-hans']
    referenced=set()
    def references():
        for pid,mon in engine.state['pokemon'].items():
            if mon['side']!='opponent' or pid in referenced:continue
            sid=mon['fields']['species']['value'];catalog=kb.facts.get('pokemon',{}).get(sid,{})
            abilities=[]
            for name in catalog.get('ability_names',[]):
                abilities.extend(x.canonical_id for x in kb.by_kind['ability'] if name in x.names.values())
            if abilities:engine.candidate_domain(pid,'native_ability',abilities,complete=False,verification='community_catalog_assertion',provenance=kb.facts['source'])
            species_id=int(sid.rsplit(':',1)[1]) if sid else None
            forms=[row for row in kb.identities.by_species.get(species_id,[]) if row.get('champions_availability',{}).get('status')=='confirmed_available']
            if forms:
                engine.candidate_domain(pid,'available_forms_reference',[row['canonical_identity'] for row in forms],complete=False,
                    verification='partial_champions_form_availability',provenance={'knowledge_snapshot':kb.snapshot_id,'rows':[{'identity':row['canonical_identity'],'source':row['champions_availability']['source']} for row in forms]})
                for row in forms:names[row['canonical_identity']]=row['names'].get('zh-hans',row['names'].get('en','未解析名称'))
            referenced.add(pid)
    references()
    previous=None
    def attach(entry):
        nonlocal previous
        state=dict(entry['after']);state['knowledge']=dict(state.get('knowledge',{}))
        hidden=engine.projection();hidden['labels']=names
        state['knowledge']['hidden_configuration']=hidden
        state['knowledge']['pokemon_projection']=pokemon_knowledge(state['pokemon'],hidden)
        new={**entry,'after':state,'before':previous}
        if previous is not None:
            before=previous['knowledge']['hidden_configuration']['pokemon'];after=hidden['pokemon'];changes=[]
            for pid,p in after.items():
                prior=before.get(pid,{}).get('fields',{})
                for key,d in p['fields'].items():
                    if key.startswith(('item_at:','ability_at:')):continue
                    old_domain=prior.get(key)
                    # A revelation is a domain change, not another observation of the same move.
                    core=lambda x:None if x is None else {k:x.get(k) for k in ['status','value','candidates','interval','members','provisional']}
                    if core(old_domain)!=core(d) and (d['status']!='unknown' or d.get('provisional')):
                        changes.append({'path':['knowledge','hidden_configuration','pokemon',pid,'fields',key],
                                        'category':'knowledge','before':old_domain,'after':d})
            new['changes']=entry['changes']+changes
            if changes and entry['classification'] in {'no_change','observation_only'}:new['classification']='knowledge'
            new['raw_changes']=entry['raw_changes']+field_diff(before,after,('knowledge','hidden_configuration','pokemon'))
        timeline['entries'].append(new);previous=state
    attach(source['entries'][0])
    for record,entry in zip(old['history'],source['entries'][1:]):
        binding=record['bindings'].get('actor',{})
        engine.apply(record['event'],instance_id=binding.get('pokemon_instance_id'),
                     side=record['event']['side'],sequence=record['ordering']['key'][0],application_status=record['application_status'])
        references()
        attach(entry)
        restored=dict(previous);restored['knowledge']=dict(restored['knowledge']);restored['knowledge'].pop('hidden_configuration');restored['knowledge'].pop('pokemon_projection')
        assert restored==entry['after']  # Every observable field and provenance survives.
    assert HiddenEngine.from_dict(engine.to_dict()).to_dict()==engine.to_dict()
    checks=read('reports/M2.2.3-cross-source-validation.json')
    for check in checks['hp_checks']:
        entry=next(x for x in timeline['entries'] if x['event'] and x['event']['event_type']=='turn_boundary' and x['event']['attributes'].get('turn')==check['turn'] and x['event']['attributes'].get('boundary')=='end')
        assert entry['after']['pokemon'][check['pokemon_instance_id']]['hp'][check['unit']]['value']==check['independent_video_value']
    for check in checks['identity_checks']:
        entry=next(x for x in timeline['entries'] if x['event'] and x['event']['event_type']=='turn_boundary' and x['event']['attributes'].get('turn')==check['turn'] and x['event']['attributes'].get('boundary')=='end')
        state=entry['after'];side='self' if check['slot'].startswith('own') else 'opponent';slot='left' if check['slot'].endswith('1') else 'right';pid=state['sides'][side]['active_slots'][slot]
        assert state['pokemon'][pid]['species']['value']['species_id']==check['observed_species_id']
    return engine,timeline,{'events':len(old['history']),'states':len(timeline['entries']),'hp_checkpoints':28,'identity_checkpoints':28,'all_observable_prefixes_unchanged':True,'hidden_replay_deterministic':True,'observable_source':source_stem,'observable_rule_profile':old['mechanic_rules']['profile_id']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--provisional',action='store_true');add_arguments(parser);args=parser.parse_args();selected=BattleArtifacts.select(args.battle_id,args.video,default='sample_battle_3')
    engine,timeline,metrics=run(provisional=args.provisional,battle_id=selected.battle_id)
    stem='M2.3.1-provisional' if args.provisional else 'M2.3.1'
    ARTIFACTS.report(f'{stem}-hidden-state.json').write_text(json.dumps(engine.to_dict(),ensure_ascii=False,indent=2)+'\n')
    html=render_html(timeline,artifact_root='../../../');metrics['html_bytes']=len(html.encode());metrics['rule_profile']=engine.rules.profile
    ARTIFACTS.report(f'{stem}-hidden-state-timeline.html').write_text(html)
    ARTIFACTS.report(f'{stem}-validation.json').write_text(json.dumps(metrics,indent=2)+'\n')
    print(json.dumps(metrics))

if __name__=='__main__':main()
