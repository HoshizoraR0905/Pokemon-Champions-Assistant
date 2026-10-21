"""Scoped, resumable visual evidence sidecar over preserved M3.4 snapshots.

Usage: python -m battle_evidence.visual_offline --battle 9
No video decoding, StateEngine replay, database mutation or Battle Log dependency.
"""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import argparse
import json
import time
import inspect
import cv2
from battle_artifacts import BattleArtifacts
from speed_inference.domains import digest
from speed_inference.offline import atomic_json,file_hash,RUNS
from recognition.command_checkpoint import inspect_command,VERSION as COMMAND_VERSION
from .visual import VisualPhaseEstimator
from .visual_controls import selected_fight,flexible_controls,VERSION as VARIANT_VERSION,FLEX_VERSION
from .ui_counters import CounterTimeline,parse_counter,reconcile_segments,ROI
from .turns import TurnReconstruction
from .durations import EffectDurations
from .adapter import speed_audit
from .builds import KnownBuilds

VERSION='normal-screen-sidecar-v2'
EVENT_SIGNALS=('faint','pivot_action','sendout','initial_sendout','sendout_sides','battle_end')


def fresh_feature(feature):
    """Cached geometry must not carry interpreted action/event state into a replay."""
    f=deepcopy(feature);f['actions']=[]
    for key in EVENT_SIGNALS:f['signals'].pop(key,None)
    return f


def cached_counter(row):
    """Use raw label/fraction OCR, not normalized guessed values."""
    results=[]
    for region in row.get('ui',{}).get('regions',[]):
        if region.get('region_type')!='field_indicator':continue
        raw=region.get('ocr',{});label=raw.get('label',{});fraction=raw.get('counter',{})
        if not label or not fraction:continue
        text=label.get('raw_text','')+fraction.get('raw_text','')
        bounds=region['bounds'];confidence=min(label.get('confidence',0),fraction.get('confidence',0))
        parsed=parse_counter(text,source_id=row['source_id'],timestamp=row['timestamp'],bounds=bounds,
            confidence=confidence,image=row['image'])
        results.append(dict(raw=deepcopy(raw),text=text,bounds=bounds,parsed=parsed,origin='preserved_field_ROI_OCR'))
    return results


def feature(row,inspection,battle_id):
    ui=row.get('ui',{});phase=ui.get('phase');command=row.get('command') or {}
    normal=inspection.get('normal_controls',False)
    return dict(id='visual:'+digest([battle_id,row['source_id']]),battle_id=battle_id,timestamp=row['timestamp'],
        source_id=row['source_id'],image=row['image'],signals=dict(normal_controls=normal,
        hud_cards=len(inspection.get('visible_slots',[])),overlay=None if normal else ui.get('overlay'),
        menu=phase if not normal and phase in ('move_selection','move_target_selection','pokemon_selection','switch_selection') else None,
        pre_battle=phase in ('team_preview','team_configuration'),battle_view=phase=='battle_screen',
        command_label=command.get('visible',False),cached_phase=phase,command_timer=command.get('countdown')),
        inspection=inspection,actions=[])


def run(number,*,profile='v2'):
    if profile not in ('v1','v2'):raise ValueError('Unknown visual profile')
    started=time.monotonic();battle_id=f'sample_battle_{number}'
    battle=BattleArtifacts(battle_id,Path.cwd())
    root=battle.cache_dir.relative_to(Path.cwd())
    prior=next(x for x in json.loads(Path('.cache/m34e/battle-index.json').read_text()) if x['battle_id']==battle_id)
    prior_path=Path(prior['result']);old=json.loads(prior_path.read_text());battle.check_identity(old['battle_id'])
    if old.get('own_builds',{}).get('bound_instances'):raise ValueError('Serialized verified own build records required; source summary contains bindings only')
    run_name='m238-live-1' if number==6 else RUNS[number]
    observations=root/'event-driven'/run_name/'observations.json'
    inputs={str(p):file_hash(p) for p in (prior_path,observations)}
    dependencies=[Path(__file__),Path(__file__).with_name('visual.py'),Path(__file__).with_name('ui_counters.py'),
        Path(__file__).with_name('turns.py'),Path(__file__).with_name('durations.py'),Path(__file__).with_name('adapter.py'),Path(__file__).with_name('visual_controls.py'),
        Path('recognition/command_checkpoint.py'),Path('recognition/fast_profile.py'),Path('recognition/ui_regions.py')]
    identity=dict(artifact_policy=file_hash(Path('battle_artifacts.py')),version=VERSION,profile=profile,inputs=inputs,dependencies={str(p):file_hash(p) for p in dependencies},
        ocr_implementation=file_hash(Path('recognition/onnx_ocr.py')),model_manifest=file_hash(Path('.cache/m15-onnx-medium/local-manifest.json')),max_gap=1.6,counter_roi=ROI,ocr_policy='cached-first; missing main-screen first-row only; max40 crops')
    dest=root/('m34-visual-v2' if profile=='v2' else 'm34-visual')/digest(identity)[:16];dest.mkdir(parents=True,exist_ok=True)
    manifest=battle.guard_output(dest/'manifest.json');output=battle.guard_output(dest/'visual-evidence.json')
    if manifest.exists():
        m=json.loads(manifest.read_text())
        if m.get('status')=='complete' and output.exists() and m.get('output_hash')==file_hash(output):
            print(json.dumps(dict(battle_id=battle_id,reused=True,result=str(output))),flush=True);return str(output)
    m=dict(identity=identity,status='running',stage='features',battle_id=battle_id)
    atomic_json(manifest,m)
    raw_observations=json.loads(observations.read_text());battle.check_identity(raw_observations['battle_id'])
    rows=raw_observations['observations']
    extraction_identity=dict(input=str(observations),input_hash=inputs[str(observations)],version='field-main-reader-v2',command_detector_version=COMMAND_VERSION,
        detector_dependencies={str(p):file_hash(p) for p in dependencies[-3:]},
        extractor=digest(inspect.getsource(feature)+inspect.getsource(cached_counter)))
    checkpoint=dest/'features.json'
    reused_features=None
    if not checkpoint.exists():
        for prior_stage in sorted([*(root/'m34-visual-v2').glob('*/manifest.json'),*(root/'m34-visual').glob('*/manifest.json')],key=lambda p:p.stat().st_mtime,reverse=True):
            previous=json.loads(prior_stage.read_text());candidate=prior_stage.parent/'features.json'
            oldid=previous.get('identity',{})
            if previous.get('status')!='complete' or not candidate.exists():continue
            if oldid.get('inputs',{}).get(str(observations))!=inputs[str(observations)]:continue
            if any(oldid.get(k,identity[k])!=identity[k] for k in ('model_manifest','ocr_implementation')):continue
            if any(oldid.get('dependencies',{}).get(str(p))!=file_hash(p) for p in dependencies[-3:]):continue
            prior_extraction=previous.get('extraction_identity')
            if prior_extraction is not None and prior_extraction.get('input_hash')!=extraction_identity['input_hash']:continue
            # v1 legacy checkpoint upgrade: the extraction function and detector are
            # unchanged; all new temporal interpretation occurs after this stage.
            atomic_json(checkpoint,json.loads(candidate.read_text()));reused_features=str(candidate);break
    m['extraction_identity']=extraction_identity;m['reused_features']=reused_features
    atomic_json(manifest,m)
    saved=json.loads(checkpoint.read_text()) if checkpoint.exists() else dict(features=[],raw_counters=[],frames_inspected=0,new_ocr_crops=0,missing_images=[])
    saved.setdefault('variant_frame_inspections',0)
    initial_costs=dict(frames=saved['frames_inspected'],ocr=saved['new_ocr_crops'],variants=saved['variant_frame_inspections'],flex=saved.get('v2_extra_frame_inspections',0))
    backend=None;last_ocr=-100
    try:
        for i,row in enumerate(rows):
            upgrading=i<len(saved['features'])
            if upgrading and saved['features'][i]['inspection'].get('version')==COMMAND_VERSION:continue
            image=cv2.imread(row['image']);inspection=row.get('command_inspection')
            if image is None:
                saved['missing_images'].append(row['image']);inspection={}
            else:
                saved['frames_inspected']+=1
                if inspection is None or inspection.get('version')!=COMMAND_VERSION:inspection=inspect_command(image)
            f=feature(row,inspection,battle_id)
            if upgrading:
                saved['features'][i]=f
                if (i+1)%100==0:
                    atomic_json(checkpoint,saved)
                    print(json.dumps(dict(battle_id=battle_id,stage='upgrade_detector_version',frames=i+1)),flush=True)
                continue
            reads=cached_counter(row)
            # New bounded reads only if the cache has no field-region read at all.
            if not reads and image is not None and inspection.get('normal_controls') and saved['new_ocr_crops']<40 and row['timestamp']-last_ocr>=2:
                if backend is None:
                    from recognition.onnx_ocr import ONNXOCRBackend
                    backend=ONNXOCRBackend('.cache/m15-onnx-medium',provider='cpu',batch_size=1)
                bounds=[265,26,562,61];x,y,X,Y=bounds
                raw=backend.predict([image[y:Y,x:X]])[0];saved['new_ocr_crops']+=1;last_ocr=row['timestamp']
                reads=[dict(raw=raw,text=raw['text'],bounds=bounds,origin='new_bounded_ROI_OCR',parsed=parse_counter(raw['text'],
                    source_id=row['source_id'],timestamp=row['timestamp'],bounds=bounds,confidence=raw['confidence'],image=row['image']))]
            saved['features'].append(f)
            for read in reads:saved['raw_counters'].append(dict(frame_id=f['id'],timestamp=row['timestamp'],**read))
            if (i+1)%100==0:
                atomic_json(checkpoint,saved);m.update(progress=i+1,total=len(rows));atomic_json(manifest,m)
                print(json.dumps(dict(battle_id=battle_id,stage='features',frames=i+1,total=len(rows))),flush=True)
        atomic_json(checkpoint,saved);m['stage']='reconstruction';atomic_json(manifest,m)
        estimator=VisualPhaseEstimator(battle_id,profile=profile);counters=CounterTimeline();turns=TurnReconstruction(battle_id);effects=EffectDurations()
        ledger=old['reconstruction']['ledger']
        for e in ledger:turns.consume(e)
        live=[e for e in ledger if e.get('timestamp') is not None and not e.get('source_retracted') and not e.get('source_revision_requires_review')]
        live.sort(key=lambda e:e['timestamp']);j=0;seen_actions=set()
        saved.setdefault('v2_extra_frame_inspections',0)
        saved['features']=[fresh_feature(f) for f in saved['features']]
        for row,f in zip(rows,saved['features']):
            inspection=f['inspection'];controls=inspection.get('control_bounds',[])
            f['signals']['missing_image']=row['image'] in saved['missing_images']
            if f.get('variant_checked')!=VARIANT_VERSION and not inspection.get('normal_controls') and len(controls)==2 and not controls[0] and len(controls[1])==1 and row.get('ui',{}).get('phase')=='battle_screen':
                image=cv2.imread(row['image']);saved['variant_frame_inspections']+=1
                if image is not None:
                    improved=selected_fight(image,inspection,row['ui'])
                    f.update(feature(row,improved,battle_id))
                f['variant_checked']=VARIANT_VERSION
            if profile=='v2':
                flex_identity=FLEX_VERSION+':'+file_hash(Path(__file__).with_name('visual_controls.py'))
                candidate=(row.get('ui',{}).get('phase') in ('battle_screen','battle_animation','unknown') and row.get('ui',{}).get('overlay') in (None,'status_overlay') and (row.get('ui',{}).get('phase')=='battle_screen' or (row.get('command') or {}).get('visible')))
                if f.get('flexible_checked')!=flex_identity and candidate and not f['inspection'].get('normal_controls'):
                    image=cv2.imread(row['image']);saved['v2_extra_frame_inspections']+=1
                    if image is not None:
                        improved=flexible_controls(image,f['inspection'],row['ui'])
                        f.update(feature(row,improved,battle_id))
                    else:
                        f['signals']['missing_image']=True
                    f['flexible_checked']=flex_identity
                inspection=f['inspection']
                controls=inspection.get('control_bounds',[])
                f['signals']['native_dual_controls']=bool(inspection.get('native_dual_controls') or (len(controls)==2 and all(len(c)==1 for c in controls)))
                slots=set(inspection.get('independent_visible_slots',inspection.get('visible_slots',[])))
                slots.update(r['region_id'] for r in row.get('ui',{}).get('regions',[]) if r.get('region_type')=='active_hud' and r.get('visibility')=='visible')
                f['signals']['hud_slots']=sorted(slots)
                f['signals']['command_panel']=inspection.get('command_panel')
            # A cached detector may intentionally inspect only native-button frames.
            # Independent cached HUD regions provide command persistence evidence.
            f['signals']['hud_cards']=max(f['signals']['hud_cards'],sum(r.get('region_type')=='active_hud' and r.get('visibility')=='visible' for r in row.get('ui',{}).get('regions',[])))
            t=f['timestamp'];events=[]
            while j<len(live) and live[j]['timestamp']<=t:
                events.append(live[j]);j+=1
            for e in events:
                text=e.get('text') or '';sig=f['signals']
                if e['kind']=='action' and '使出了' in text and any(s.get('source_type')=='video_message' for s in e['sources']):
                    action_id=e.get('underlying_action_id',e['id'])
                    if action_id not in seen_actions:
                        f['actions'].append(dict(event_id=e['id'],underlying_action_id=action_id,live_execution=True,
                            source_status=e['source_status'],move_verified=e['move_verified'],sources=e['sources']))
                        seen_actions.add(action_id)
                    if any(word in text for word in ('抛下狠话','急速折返','伏特替换','快速折返')):sig['pivot_action']=True
                if e.get('source_event_type')=='faint':sig['faint']=True
                if e.get('source_event_type')=='send_out':sig['sendout']=True
                if any(word in text for word in ('赢得了对战','输掉了对战')):sig['battle_end']=True
            if f['signals'].get('sendout') and not estimator.open:f['signals']['initial_sendout']=True
            estimator.consume(f)
        atomic_json(checkpoint,dict(saved,features=[fresh_feature(f) for f in saved['features']]))
        for r in saved['raw_counters']:
            if r['parsed']:counters.consume(r['parsed'])
        visual=estimator.export();visual['segments']=reconcile_segments(visual['segments'],counters,live)
        turns.attach_visual(visual['segments'])
        # Causal, separate overlays reference original immutable action snapshots.
        overlays={};ci=0;observed=counters.observations;bi=0
        boundaries=visual['segments']
        for e in sorted(live,key=lambda e:e['timestamp']):
            while bi<len(boundaries) and boundaries[bi]['next_command_time']<=e['timestamp']:
                effects.advance_visual_boundary(boundaries[bi]);bi+=1
            while ci<len(observed) and observed[ci]['timestamp']<=e['timestamp']:
                effects.observe_ui_counter(observed[ci]);ci+=1
            effects.consume(e,turns.assignment[e['id']])
            if e['kind']=='action':
                pair=old['snapshots'].get(e['id'],{})
                overlays[e['id']]=dict(timestamp=e['timestamp'],original_snapshot_ids={k:v.get('id') for k,v in pair.items()},
                    turn=deepcopy(turns.assignment[e['id']]),ui_effect_counters=counters.as_of(e['timestamp']),
                    durations=effects.snapshot(),replay_validation=old['replay_validation'],
                    limitation='Last-observed UI support is not a certified current countdown; no future reads or absolute turn invented')
        while bi<len(boundaries):effects.advance_visual_boundary(boundaries[bi]);bi+=1
        while ci<len(observed):effects.observe_ui_counter(observed[ci]);ci+=1
        speed=speed_audit(turns,old['snapshots'],KnownBuilds())
        status=Counter(s['status'] for s in visual['segments']);dt=[b['timestamp']-a['timestamp'] for a,b in zip(rows,rows[1:])]
        result=dict(schema=VERSION,battle_id=battle_id,input_identity=identity,visual=visual,
            reconstruction=turns.export(),counter_observations=observed,counter_constraints=counters.constraints,
            action_snapshot_overlays=overlays,effects=effects.snapshot(),speed=speed,
            previous_replay_validation=old['replay_validation'],
            metrics=dict(incremental_ocr_crops=saved['new_ocr_crops']-initial_costs['ocr'],incremental_frame_inspections=saved['frames_inspected']-initial_costs['frames']+saved['variant_frame_inspections']-initial_costs['variants']+saved['v2_extra_frame_inspections']-initial_costs['flex'],observation_rows=len(rows),frames_inspected=saved['frames_inspected'],cached_OCR_regions=sum(r['origin']=='preserved_field_ROI_OCR' for r in saved['raw_counters']),
                new_ocr_crops=saved['new_ocr_crops'],new_extracted_frames=0,video_decodes=0,state_engine_replays=0,
                missing_images=saved['missing_images'],v2_extra_frame_inspections=saved['v2_extra_frame_inspections'],variant_frame_inspections=saved['variant_frame_inspections'],features_reused_from=reused_features,max_frame_gap=max(dt),seconds=time.monotonic()-started,
                segments=dict(status),parsed_counters=len(observed),confirmed_counter_reads=sum(o['temporal_confirmation'] for o in observed),
                local_action_memberships=sum(a['status']=='confirmed_local_membership' for a in turns.assignment.values()),speed_eligible=speed['eligible_updates']))
        atomic_json(output,result);m.update(status='complete',stage='complete',output_hash=file_hash(output),metrics=result['metrics']);atomic_json(manifest,m)
        print(json.dumps(dict(battle_id=battle_id,result=str(output),metrics=result['metrics'])),flush=True);return str(output)
    except Exception as exc:
        m.update(status='failed',error=repr(exc));atomic_json(manifest,m);raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--battle',type=int,required=True,choices=range(5,10));parser.add_argument('--profile',choices=['v1','v2'],default='v2');args=parser.parse_args();run(args.battle,profile=args.profile)
