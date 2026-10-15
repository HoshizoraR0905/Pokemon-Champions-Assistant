"""M2.3.5-D: read saved evidence, diagnose losses, build an offline review viewer.

No recognition, OCR, model inference, video decoding or StateEngine replay.
All counterfactuals are arithmetic on saved candidates, not new classifications.
"""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
P=BattleArtifacts('sample_battle_5',ROOT).cache('m235')
D=BattleArtifacts('sample_battle_5',ROOT).cache('m235d')
TEMPLATE=ROOT/'scripts/templates/m235d-review.html'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def read(path):return json.loads(Path(path).read_text())


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temp.replace(path)


def inventory():
    files=set(p for p in P.rglob('*') if p.is_file())
    seal=read(P/'implementation-seal.json')
    files.update(ROOT/k for k in seal['identity']['code'])
    files.update(ROOT/k for k in read(P/'prechange.json')['preserve'])
    files.update(ROOT/k for k in ['AGENTS.md','recognition/identity.py','recognition/entities.py','recognition/__init__.py','recognition/context.py','recognition/phases.py','tracking/__init__.py','scripts/replay_m233a.py','tests/fixtures/battles/m235_review.json','reports/M2.3.5-new-battle-generalization.md','reports/M2.3.4-recognition-and-state-reliability.md'])
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(files)}


def compact_icon(icon):
    candidates=icon.get('candidates',[])
    return {**{k:icon.get(k) for k in ['status','reason','species_id','canonical_identity','identity_status','method','source_commit','region']},'candidates':candidates,
            'top_two_gap':round(candidates[0]['similarity']-candidates[1]['similarity'],5) if len(candidates)>1 else None}


def static_icon_gate(icon,minimum=.80,margin=.10):
    cs=icon.get('candidates',[])
    if not cs or cs[0]['similarity']<minimum:return dict(status='unresolved',species_id=None,reason='below_similarity_threshold')
    near=[c for c in cs if cs[0]['similarity']-c['similarity']<margin]
    if not cs[0].get('canonical_id') or any(c['species_id'] is None for c in near):return dict(status='unresolved',species_id=None,reason='unmapped_visual_identity')
    if len({c['species_id'] for c in near})!=1:return dict(status='ambiguous',species_id=None,reason='small_species_margin')
    if len({c.get('canonical_identity') for c in near})!=1 or not cs[0].get('canonical_identity'):return dict(status='ambiguous',species_id=cs[0]['species_id'],reason='forms_visually_ambiguous')
    return dict(status='resolved',species_id=cs[0]['species_id'],reason='')


def event_index(replay):
    result={}
    for r in replay['engine']['history']:
        e=r['event']
        if e['event_type']!='hud_observation':continue
        for s in e['evidence']:
            for oid in s['observation_ids']:result[(oid,e['side'],e['attributes']['slot'])]=r
    return result


def projection_fields(projection,side,slot):
    o=projection['occupancy'][side][slot];pid=o.get('current_instance_id');last=o.get('last_observed_instance_id');mon=projection['pokemon'].get(last,{})
    def value(name):return mon.get(name,{}).get('value')
    return dict(current_instance_id=pid,last_observed_instance_id=last,current_species_id=(value('identity') or {}).get('species_id') if pid else None,
                historical_species_id=(value('identity') or {}).get('species_id'),status=o['status'],location=mon.get('location'),
                current_variant=mon.get('form'),fainted=mon.get('fainted'),ability=mon.get('ability'),item=mon.get('item'),
                hp=mon.get('hp'),latest_hud=o.get('latest_hud'))


def record(r,projection,side,slot):
    if not r:return dict(hud_event=None,admitted=False,bound=False,state=projection_fields(projection,side,slot))
    e=r['event'];b=r['bindings'];hud=b.get('hud',{})
    return dict(hud_event=e['event_id'],application_status=r['application_status'],admission_status=hud.get('status'),admission_reason=hud.get('reason'),
                admitted=hud.get('status')=='accepted',bound=bool(b.get('actor')),instance_binding=b.get('actor'),identity=b.get('identity'),
                hp_admission=hud.get('hp_status'),hp_reason=hud.get('hp_reason'),corroboration=hud.get('corroboration'),
                evidence=e['evidence'],state=projection_fields(projection,side,slot))


def slot_key(mon):return ('self' if mon['slot'].startswith('own') else 'opponent','left' if mon['slot'].endswith('1') else 'right')


def run(verify_only=False):
    print('Verifying existing M2.3.5 seals and capturing protected inputs',flush=True)
    before=inventory();seal=read(P/'implementation-seal.json');revision=ROOT/read(P/'milestone-manifest.json')['revision']
    assert all(sha(ROOT/k)==v for k,v in seal['outputs'].items())
    assert all(sha(ROOT/k)==v for k,v in seal['identity']['code'].items())
    review_seal=read(P/'review-seal.json');assert sha(ROOT/review_seal['fixture'])==review_seal['sha256']
    bs=read(P/'baseline-seal.json');assert all(sha(ROOT/k)==v for k,v in bs['outputs'].items())
    ci=read(P/'completion-integrity.json');assert all(sha(ROOT/k)==v for k,v in ci['outputs'].items())
    prediction_inventory={p.name:sha(p) for p in sorted((P/'reads').glob('*.json'))}
    assert len(prediction_inventory)==450 and prediction_inventory==ci['prediction_files']
    code_identity=dict(script_sha256=sha(__file__),template_sha256=sha(TEMPLATE),implementation_seal_sha256=sha(P/'implementation-seal.json'),review_seal_sha256=sha(P/'review-seal.json'))
    revision_id=hashlib.sha256(json.dumps(code_identity,sort_keys=True).encode()).hexdigest()[:16];out=D/revision_id
    if verify_only:
        existing=read(out/'audit.json');assert existing['input_hashes']==before and existing['diagnostic_identity']==code_identity
        assert all(sha(ROOT/k)==v for k,v in read(out/'manifest.json')['outputs'].items())
        print('Verified diagnostic outputs and all protected inputs; 450 predictions unchanged');return out
    if (out/'manifest.json').exists() and read(out/'manifest.json')['status']=='complete':
        return run(verify_only=True)
    out.mkdir(parents=True,exist_ok=True)
    write(out/'manifest.json',dict(status='running',diagnostic_identity=code_identity,stage='extract_saved_evidence'))
    labels=read(ROOT/review_seal['fixture'])['examples'];label_by_hash={r['sha256']:r for r in labels}
    baseline_rows=read(P/'baseline-observations.json')['observations'];color_rows=read(revision/'observations.json')['observations'];default_rows=read(P/'final-observations.json')['observations']
    byhash={r['sha256']:r for r in color_rows};old_byhash={r['sha256']:r for r in baseline_rows};default_byhash={r['sha256']:r for r in default_rows}
    snapshot_rows=[r for r in color_rows if r.get('snapshot')];assert len(snapshot_rows)==7
    print('Reading three saved replays once; extracting compact snapshot/checkpoint evidence',flush=True)
    # Trim large replay snapshots immediately; this audit needs saved history and projections only.
    def load_replay(path):
        d=read(path);return dict(engine=dict(history=d['engine']['history']),projections=d['projections'],identity=d.get('identity'))
    base=load_replay(P/'baseline-replay.json');color=load_replay(revision/'replay.json');default=load_replay(P/'final-replay.json')
    indices=[event_index(r) for r in [base,default,color]];snapshots=[];flat=[]
    for row in snapshot_rows:
        t=str(row['timestamp']);label=label_by_hash.get(row['sha256']);gts={(g['side'],g['slot']):g for g in label['hud']} if label else {}
        sample=dict(timestamp=row['timestamp'],target_timestamp=row['target_timestamp'],sha256=row['sha256'],image=row['image'],source_id=row['source_id'],screen=row['snapshot']['screen'],split=label['split'] if label else 'not_in_frozen_review',occurrence_group=label['occurrence_group'] if label else None,slots=[])
        for mon,old,defmon in zip(row['snapshot']['pokemon'],old_byhash[row['sha256']]['snapshot']['pokemon'],default_byhash[row['sha256']]['snapshot']['pokemon']):
            assert mon['slot']==old['slot']==defmon['slot'];side,slot=slot_key(mon);gt=gts.get((side,slot));s=mon['species'];raw=s.get('raw_ocr') or {}
            assert old['icon']==defmon['icon'] and old['species']==defmon['species'],'Default recognition changed'
            records=[record(idx.get((row['sha256'],side,slot)),rep['projections'][t],side,slot) for idx,rep in zip(indices,[base,default,color])]
            entry=dict(timestamp=row['timestamp'],sha256=row['sha256'],side=side,logical_slot=slot,hud_ui_slot=mon['slot'],reviewed=gt,
                       reviewed_form=None,form_note='Frozen HUD labels establish species only; no independent form label',
                       regions={k:mon[k].get('region') for k in ['species','icon','hp']},numeric_source_regions={k:v for k,v in row['snapshot']['regions'].items() if k.startswith(('own_hp_'+('0' if slot=='left' else '1'),'opponent_hp_'+('0' if slot=='left' else '1')))},
                       name=dict(raw_text=s['raw_text'],confidence=s['confidence'],raw_ocr=raw,baseline_resolution=old['species'].get('resolution'),color_resolution=s.get('resolution')),
                       hp_observation=mon['hp'],default_icon=compact_icon(old['icon']),color_icon=compact_icon(mon['icon']),
                       baseline=records[0],saved_unversioned_default_replay=records[1],final=records[2],
                       camera=dict(hud_to_model_association='none in audited evidence path',model_coordinates=None,root_cause='not implicated in saved score/admission differences',ui_slot_mapping='inferred fixed HUD layout, not rendered world position'))
            entry['same_frame_name_icon_corroboration']=dict(default=old['icon']['status']=='resolved' and old['icon'].get('species_id')==old['species'].get('resolution',{}).get('species_id'),color=mon['icon']['status']=='resolved' and mon['icon'].get('species_id')==s.get('resolution',{}).get('species_id'))
            if not entry['final']['admitted']:
                if s.get('resolution',{}).get('species_id'):
                    primary='admission_threshold_failure';detail='Correct canonical text transformed to text_icon_agreement while independent saved icon remains ambiguous; exact-text branch is no longer eligible'
                    secondary=['icon_matching_failure','other']
                else:
                    primary='icon_matching_failure';detail='Nickname transcribed, canonical species unresolved; cached icon does not independently resolve it';secondary=['insufficient_evidence']
            else:primary=None;detail='Admitted, instance-bound and directly supported at this timestamp';secondary=[]
            entry['first_loss']=dict(primary=primary,secondary=secondary,detail=detail)
            entry['counterfactual_icon_margin_0_09']=static_icon_gate(entry['color_icon'],margin=.09)
            assert static_icon_gate(entry['color_icon'])['status']==entry['color_icon']['status']
            sample['slots'].append(entry);flat.append(entry)
        snapshots.append(sample)
    held=[];reviewed=[]
    for label in labels:
        row=byhash[label['sha256']];t=str(row['timestamp']);snapshot=next((x for x in snapshots if x['sha256']==row['sha256']),None)
        for gt in label['hud']:
            e=next((x for x in (snapshot['slots'] if snapshot else []) if x['side']==gt['side'] and x['logical_slot']==gt['slot']),None)
            f=dict(timestamp=row['timestamp'],target_timestamp=row['target_timestamp'],sha256=row['sha256'],image=row['image'],side=gt['side'],slot=gt['slot'],expected=gt,split=label['split'],occurrence_group=label['occurrence_group'],frame_acquired=True,candidate_regions=e['regions'] if e else None,snapshot_present=e is not None)
            for name,rep in [('baseline',base),('saved_unversioned_default_replay',default),('final',color)]:f[name]=projection_fields(rep['projections'][t],gt['side'],gt['slot'])
            if e:f.update(name=e['name'],default_icon=e['default_icon'],color_icon=e['color_icon'],admitted=e['final']['admitted'],bound=e['final']['bound'],first_loss=e['first_loss'])
            else:
                f.update(name=None,default_icon=None,color_icon=None,admitted=False,bound=False,first_loss=dict(primary='acquisition_gap',secondary=['insufficient_evidence','temporal_continuity_failure'] if f['final']['last_observed_instance_id'] else ['insufficient_evidence'],detail='Frame is acquired and HUD visibly reviewed, but no qualifying HUD observation/crops/OCR were scheduled; not a video-frame acquisition gap'))
            f['correct_current']=f['final']['current_species_id']==gt['species_id'];f['baseline_correct_current']=f['baseline']['current_species_id']==gt['species_id']
            f['camera_root_cause']='No confirmed 3D association; missing HUD scheduling or saved UI recognition/admission explains the loss'
            reviewed.append(f)
            if label['split']=='held_out':held.append(f)
    assert len(reviewed)==31 and len(held)==17 and sum(x['correct_current'] for x in held)==3
    def retention(facts):
        n=len(facts);candidate=[f for f in facts if f['snapshot_present']];recognized=[f for f in candidate if f['name']['color_resolution'].get('status')=='resolved' and f['name']['color_resolution'].get('species_id') is not None];admitted=[f for f in candidate if f['admitted']];bound=[f for f in admitted if f['bound']];current=[f for f in facts if f['final']['current_instance_id']]
        return dict(reviewed_visible=n,acquired_frames_for_facts=n,candidate_regions=len(candidate),raw_name_transcribed=sum(bool(f['name']['raw_text']) for f in candidate),canonical_recognition=len(recognized),canonical_correct=sum(f['name']['color_resolution']['species_id']==f['expected']['species_id'] for f in recognized),state_admitted=len(admitted),side_slot_bound=len(bound),current_supported=len(current),current_correct=sum(f['correct_current'] for f in facts),primary_losses=dict(Counter(f['first_loss']['primary'] for f in facts if not f['correct_current'])),raw_hp_present=sum(f['snapshot_present'] and f['sha256'] in byhash and next(m for m in byhash[f['sha256']]['snapshot']['pokemon'] if slot_key(m)==(f['side'],f['slot']))['hp'].get('value') is not None for f in facts))
    groups=defaultdict(list)
    for f in held:groups[(f['occurrence_group'],f['side'],f['slot'])].append(f)
    grouped=[]
    for (group,side,slot),facts in groups.items():
        resolved=any(f['correct_current'] for f in facts)
        # First observed loss within one frozen occurrence; later missing samples do not add an independent failure.
        first=min(facts,key=lambda f:f['timestamp'])
        grouped.append(dict(occurrence_group=group,side=side,slot=slot,checkpoints=len(facts),any_current_correct=resolved,first_loss=None if resolved else first['first_loss']['primary']))
    cf=dict(description='Post-hoc static sensitivity only; no new classifier, replay, threshold deployment or truth-selected candidate.',margin_0_09=dict(current_resolved=sum(x['color_icon']['status']=='resolved' for x in flat),hypothetical_resolved=sum(x['counterfactual_icon_margin_0_09']['status']=='resolved' for x in flat),newly_resolved=[dict(timestamp=x['timestamp'],side=x['side'],slot=x['logical_slot'],species_id=x['counterfactual_icon_margin_0_09']['species_id']) for x in flat if x['color_icon']['status']!='resolved' and x['counterfactual_icon_margin_0_09']['status']=='resolved']),freshness=dict(direct_same_frame_admitted=sum(f['admitted'] for f in held),final_current_supported=sum(bool(f['final']['current_instance_id']) for f in held),naive_historical_visible=[dict(timestamp=f['timestamp'],side=f['side'],slot=f['slot'],species_id=f['final']['historical_species_id'],matches_review=f['final']['historical_species_id']==f['expected']['species_id']) for f in held if f['final']['historical_species_id'] is not None]))
    cf['default_icon_minimum_0_70_margin_0_10']=[dict(timestamp=x['timestamp'],side=x['side'],slot=x['logical_slot'],**static_icon_gate(x['default_icon'],minimum=.70),reviewed_species=x['reviewed']['species_id'] if x['reviewed'] else None) for x in flat]
    cf['name_threshold_0_90']=dict(saved_name_confidence_minimum=min(x['name']['confidence'] for x in flat),below_current_0_95=0,newly_eligible_from_confidence_alone=0,note='No confidence-floor change fixes nickname canonicalization or the fused-method/independent-icon contract')
    display_hashes={r['sha256'] for r in snapshot_rows}|{l['sha256'] for l in labels if l['hud']}
    viewer=[]
    for row in color_rows:
        if row['sha256'] not in display_hashes:continue
        label=label_by_hash.get(row['sha256']);sample=next((x for x in snapshots if x['sha256']==row['sha256']),None)
        neighbors=[r for r in color_rows if r['sha256']!=row['sha256'] and abs(r['timestamp']-row['timestamp'])<=1.01]
        frames=[dict(timestamp=r['timestamp'],sha256=r['sha256'],image=r['image'],delta_seconds=r['timestamp']-row['timestamp'],hud_snapshot_available=bool(r.get('snapshot'))) for r in neighbors]
        viewer.append(dict(timestamp=row['timestamp'],sha256=row['sha256'],image=row['image'],source_id=row['source_id'],split=label['split'] if label else 'not reviewed',occurrence_group=label.get('occurrence_group') if label else None,hud_snapshot_available=bool(sample),slots=sample['slots'] if sample else [],reviewed_visible_hud=label['hud'] if label else None,checkpoint_facts=[f for f in reviewed if f['sha256']==row['sha256']],neighbors=frames,visual_phase=row['visual_phase']))
    thresholds=dict(icon_minimum=.80,icon_margin=.10,icon_near_rule='winner similarity - candidate similarity < margin, including candidates individually below minimum',raw_ocr_floor=.75,unique_raw_exact_strong=.95,hp_floor=.75,nickname_ocr=.95,nickname_icon_minimum=.85,nickname_high_margin_minimum=.90,nickname_high_margin=.20,nickname_repeat='past same raw name/species, confidence >= .75, not conflicting',text_filtered_icon_minimum=.80,text_filtered_variant_margin=.10,canonical_move=.90,corroboration_window_seconds=30)
    result=dict(schema_version=1,milestone='M2.3.5-D',status='complete',diagnostic_identity=code_identity,input_hashes=before,source_revision=str(revision.relative_to(ROOT)),new_ocr_predictions=0,video_processing=False,state_replay=False,ground_truth_modified=False,prediction_count=450,
                provenance_notes=['Default matcher observations equal frozen baseline observations for every audited HUD slot','Saved pre-recovery default replay lacks dependency identity; not a controlled current-code default-matcher experiment','No form labels, 3D model coordinates or biological instance ground truth added'],thresholds=thresholds,
                snapshots=snapshots,held_out_facts=held,all_reviewed_facts=reviewed,retention=dict(all_reviewed=retention(reviewed),held_out=retention(held)),held_out_occurrence_slot_groups=grouped,counterfactuals=cf,
                counts=dict(hud_snapshots=7,hud_slot_observations=len(flat),reviewed_snapshot_slot_facts=sum(x['reviewed'] is not None for x in flat),default_icon_status=dict(Counter(x['default_icon']['status'] for x in flat)),color_icon_status=dict(Counter(x['color_icon']['status'] for x in flat)),baseline_hud_admitted=sum(x['baseline']['admitted'] for x in flat),final_hud_admitted=sum(x['final']['admitted'] for x in flat),held_out_positive_frames=len({x['sha256'] for x in held}),held_out_group_slots=len(groups),held_out_group_failures=dict(Counter(x['first_loss'] for x in grouped if not x['any_current_correct']))),viewer_frames=viewer)
    after=inventory();assert before==after,'Protected source/evidence changed during diagnostic'
    write(out/'audit.json',result)
    html=TEMPLATE.read_text();data=json.dumps(dict(frames=viewer,thresholds=thresholds),ensure_ascii=False).replace('<','\\u003c');html=html.replace('__AUDIT_DATA__',data).replace('__WORKSPACE_ROOT__',os.path.relpath(ROOT,out))
    # Images stay in their original cache; no extraction, duplication or external server.
    for r in viewer:
        assert sha(ROOT/r['image'])==r['sha256']
    (out/'review.html').write_text(html)
    outputs={str((out/name).relative_to(ROOT)):sha(out/name) for name in ['audit.json','review.html']}
    write(out/'manifest.json',dict(status='complete',diagnostic_identity=code_identity,outputs=outputs,protected_files=len(before),protected_inputs_unchanged=True,new_ocr_predictions=0,predictions=450))
    print(json.dumps(dict(output=str(out.relative_to(ROOT)),counts=result['counts'],retention=result['retention'],counterfactuals=cf),ensure_ascii=False,indent=2))
    return out

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify',action='store_true');args=parser.parse_args();run(args.verify)
