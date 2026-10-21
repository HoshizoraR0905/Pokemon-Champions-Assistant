"""One-battle staged reconstruction from preserved events, with no OCR or decoding."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from collections import Counter
import json
import time
import inspect
import os
from battle_artifacts import BattleArtifacts
from speed_inference.offline import RUNS,atomic_json,file_hash
from speed_inference.domains import digest
from .turns import TurnReconstruction
from .durations import EffectDurations
from .builds import KnownBuilds
from .snapshots import project,snapshot
from .hp import attribute_hp
from .adapter import speed_audit
from .historical import reconstruct as historical_turns
from .diagnostics import replay_validation


def normalize(e,receipt,position,annotation=None):
    a=e.get('attributes',{});binding=receipt.get('bindings',{});resolved=binding.get('resolved_event',e);r=resolved.get('attributes',{})
    source=[dict(source_type=s.get('source_type'),source_id=s.get('source_id'),observation_ids=s.get('observation_ids',[]),
        timestamp=s.get('details',{}).get('timestamp'),image=s.get('details',{}).get('image')) for s in e.get('evidence',[])]
    kind={'move_execution':'action','switch_out':'switch','send_out':'switch','turn_boundary':'boundary',
        'weather_change':'effect','terrain_change':'effect','trick_room_change':'effect','side_condition_change':'effect',
        'hud_observation':'hp_observation','phase_observation':'phase','command_checkpoint':'command_checkpoint'}.get(e['event_type'],'state_change')
    b=binding.get('actor',{});move=resolved.get('canonical_references',{}).get('move') or {}
    out=dict(id=e['event_id'],underlying_action_id=a.get('occurrence_id') or e['event_id'],source_position=position,battle_id=a.get('battle_id'),position=position,timestamp=a.get('observation_time'),
        origin='recorded',kind=kind,source_event_type=e['event_type'],side=resolved.get('side'),instance_id=b.get('pokemon_instance_id'),
        sources=source,original_event_sha256=digest(e),source_status=e['status'],uncertainty=deepcopy(e.get('uncertainty',[])),
        text=e.get('original_text'),binding=deepcopy(b),application_status=receipt.get('application_status'),
        move=move.get('canonical_id'),move_verified=e['status']=='confirmed' and bool(move),priority=a.get('effective_priority'),priority_verified=False)
    if kind=='effect':
        field={'weather_change':'weather','terrain_change':'terrain','trick_room_change':'trick_room','side_condition_change':'condition'}[e['event_type']]
        name=a.get(field,'trick_room' if field=='trick_room' else 'unknown')
        out.update(effect=name,family=name if field=='condition' else field,scope=out['side'] if field=='condition' else 'field',
            change=a.get('change','observe'),verified=e['status']=='confirmed')
    if kind=='boundary':out['boundary']=a.get('boundary')
    if e['status']=='confirmed' and source:
        turns={s.get('details',{}).get('turn') for s in e.get('evidence',[]) if type(s.get('details',{}).get('turn')) is int}
        if kind=='boundary' and type(a.get('turn')) is int:turns.add(a['turn'])
        if len(turns)==1:
            out['turn_evidence']=dict(number=next(iter(turns)),boundary=a.get('boundary'),verified=True,sources=source,
                execution_order=e.get('log_order'),execution_order_verified=e.get('log_order') is not None,decision_id=a.get('decision_id'))
    hp=a.get('hp',{}).get('value');hud=binding.get('hud',{})
    if kind=='hp_observation' and out['side']=='self' and isinstance(hp,dict) and hud.get('hp_status')=='accepted':
        out['hp']=dict(current=hp.get('current'),maximum=hp.get('maximum'),confidence=a.get('hp',{}).get('confidence'),
            instance_id=out['instance_id'],epoch=binding.get('active_episode_id') or hud.get('episode_id'),
            battle_id=out['battle_id'],position=position,timestamp=out['timestamp'],sources=source,verified=e['status']=='confirmed',
            event_id=out['id'],source='accepted_saved_HUD_receipt')
    if receipt.get('retracted') or receipt.get('revisions'):
        out['source_retracted']=bool(receipt.get('retracted'))
        out['source_revision_requires_review']=bool(receipt.get('revisions'))
        out['kind']='inactive_source_observation'
        out.pop('hp',None)
    if annotation:
        if annotation.get('verified') is not True or not annotation.get('sources'):raise ValueError('Annotation requires provenance')
        forbidden=set(annotation)&{'id','battle_id','position','timestamp','sources','original_event_sha256','origin','text','source_status','source_event_type','source_position','underlying_action_id'}
        if forbidden-{'sources'}:raise ValueError('Annotation cannot rewrite immutable source identity/time')
        out['annotation_sources']=deepcopy(annotation['sources'])
        if out.get('source_retracted') or out.get('source_revision_requires_review'):
            if set(annotation)-{'verified','sources','snapshot'}:raise ValueError('Retracted/revised source requires explicit source replay, not annotation reactivation')
        for k,v in annotation.items():
            if k not in ('sources','snapshot'):out[k]=deepcopy(v)
    return out


def replay_projections(saved,out,checkpoint):
    """Generate the missing stage once, using the maintained observable state engine."""
    from tracking.state_engine import StateEngine,ApplicationPolicy,EventRecord
    from tracking.battle_state import from_dict
    from tracking.mechanic_rules import MechanicRules
    config=deepcopy(saved['policy']);config['allowed_uncertainties']=tuple(config['allowed_uncertainties'])
    engine=StateEngine(from_dict(saved['initial_state']),ApplicationPolicy(**config),mechanic_rules=MechanicRules(**saved.get('mechanic_rules',{})))
    if saved.get('mechanic_handlers') is not None and saved['mechanic_handlers']!=[h.mechanic_id for h in engine.mechanic_registry.handlers]:raise ValueError('Mechanics registry changed')
    engine.history=[EventRecord(**deepcopy(r)) for r in saved['history']]
    rows=[];previous=project(engine.initial);count=0;start=time.perf_counter();frontier=None
    def capture(record,state):
        nonlocal previous,count,frontier
        current=project(state);now=record.event.get('attributes',{}).get('observation_time')
        before_frontier=frontier
        if type(now) in (int,float):frontier=max(now,frontier) if frontier is not None else now
        rows.append(dict(event_id=record.event['event_id'],before=previous,after=current,before_frontier=before_frontier,after_frontier=frontier,
            status=record.application_status,reason=record.reason,bindings=deepcopy({k:v for k,v in record.bindings.items() if k!='resolved_event'})))
        previous=current;count+=1
        if count%100==0:
            checkpoint(dict(completed_events=count,elapsed_seconds=time.perf_counter()-start))
            # Durable compact projections; no full-state snapshot dump.
            atomic_json(out,rows)
    engine.replay(snapshot_callback=capture);atomic_json(out,rows)
    return dict(events=count,seconds=time.perf_counter()-start,
        saved_final_hash=saved.get('state_hash'),replayed_final_hash=__import__('tracking.state_engine',fromlist=['hash_state']).hash_state(engine.state))


def hp_transitions(events):
    samples=[]
    for e in events:
        p=e.get('hp')
        if p and p.get('instance_id') and all(type(p.get(k)) is int for k in ('current','maximum')) and 0<=p['current']<=p['maximum']:
            samples.append(deepcopy(p))
    grouped={}
    for p in samples:grouped.setdefault((p['instance_id'],p['epoch']),[]).append(p)
    transitions=[]
    for group in grouped.values():
        runs=[]
        for p in group:
            if runs and (p['current'],p['maximum'])==(runs[-1][-1]['current'],runs[-1][-1]['maximum']):runs[-1].append(p)
            else:runs.append([p])
        for run in runs:
            ids={s['source_id'] for p in run for s in p['sources']};supported=len(ids)>=2 and all((p.get('confidence') or 0)>=.98 for p in run)
            for p in run:
                p['verified']=p['verified'] or supported;p['recognition_support']=dict(distinct_sources=len(ids),policy='two agreeing accepted exact HUD sources at confidence >= .98',independent_manual_validation=False)
        for left,right in zip(runs,runs[1:]):
            before=left[-1];after=right[0]
            if before['current']==after['current'] and before['maximum']==after['maximum']:continue
            prior_actions=[e for e in events if e['position']<=before['position'] and e['kind']=='action']
            possible=[e for e in events if before['position']<e['position']<after['position'] and e['kind']=='action']
            if prior_actions:possible.insert(0,prior_actions[-1])
            from speed_order.core import knowledge
            candidates=[dict(kind='attack' if knowledge().facts['moves'].get(e.get('move'),{}).get('category') in ('Physical','Special') else 'unknown',attacker=e.get('instance_id'),move=e.get('move'),receiver=after['instance_id'],verified=False,
                event_id=e['id'],sources=e['sources'],reason='Temporal candidate only; execution target and causal coverage not established')
                for e in possible]
            other=[dict(kind='unknown',event_id=e['id'],verified=False,sources=e['sources']) for e in events
                if before['position']<e['position']<after['position'] and e['source_event_type'] in ('hp_change','item_activation','ability_activation','faint','transformation')]
            transitions.append(attribute_hp(before,after,candidates+other,coverage=None))
    return samples,transitions


def run(number,*,root=None,annotations=None,build_records=None,historical_reviews=None):
    root=Path(root or Path(__file__).resolve().parents[1]).resolve();battle=BattleArtifacts(f'sample_battle_{number}',root)
    directory=battle.cache('event-driven/'+RUNS[number]);events_path=directory/('events.json' if number==6 else 'video-only.json')
    sources=[events_path,directory/'replay.json',directory/'manifest.json']
    for path in [directory/'observations.json',root/'data/teams/my_team.json']:
        if path.is_file():sources.append(path)
    review_path=Path(historical_reviews) if historical_reviews else root/'tests/fixtures/battle_evidence/real-log-excerpts.json'
    log_path=battle.cache('event-driven/m238-live-2/reference/battle-log.json') if number==6 else None
    for path in (review_path,log_path):
        if path is not None and path.is_file():sources.append(path)
    if review_path.is_file():
        for review in json.loads(review_path.read_text()).get('excerpts',[]):
            image=root/review['image']
            if review['battle_id']==battle.battle_id and image.is_file():sources.append(image)
    hashes={str(p.relative_to(root)) if p.is_relative_to(root) else str(p):file_hash(p) for p in sources}
    code_root=Path(__file__).resolve().parents[1];dependencies={}
    for name in ('battle_evidence','speed_inference','tracking','battle_events','recognition','knowledge','damage'):
        for p in (code_root/name).rglob('*'):
            if p.is_file() and p.suffix in ('.py','.json'):dependencies[str(p.relative_to(code_root))]=file_hash(p)
    dependencies['battle_artifacts.py']=file_hash(code_root/'battle_artifacts.py')
    fingerprint=digest(dict(inputs=hashes,dependencies=dependencies,annotations=annotations,build_records=build_records,version=1))
    dest=battle.cache('m34-evidence/'+fingerprint[:16]);manifest=dest/'manifest.json'
    m=json.loads(manifest.read_text()) if manifest.exists() else dict(battle_id=battle.battle_id,fingerprint=fingerprint,inputs=hashes,dependencies=dependencies,stages={})
    cached_stage=m.get('stages',{}).get('snapshots',{})
    valid_stage=cached_stage.get('path') and Path(cached_stage['path']).is_file() and file_hash(cached_stage['path'])==cached_stage.get('sha256')
    if valid_stage and m.get('status')=='complete' and m.get('outputs') and all((dest/p).is_file() and file_hash(dest/p)==sha for p,sha in m.get('outputs',{}).items()):
        return dict(battle_id=battle.battle_id,reused=True,result=str(dest/'reconstruction.json'))
    started=time.perf_counter();m['status']='running';atomic_json(manifest,m)
    def progress(p):m['progress']=p;atomic_json(manifest,m);print(json.dumps(dict(battle_id=battle.battle_id,stage='snapshots',**p)),flush=True)
    try:
        data=json.loads(events_path.read_text());saved=json.loads(sources[1].read_text())
        if data.get('battle_id')!=battle.battle_id or saved['state']['battle_id']!=battle.battle_id:raise ValueError('Source ownership mismatch')
        if json.loads(sources[2].read_text()).get('status')!='complete':raise ValueError('Input run incomplete')
        replay_dependencies={k:v for k,v in dependencies.items() if k.split('/')[0] in ('tracking','battle_events','recognition','knowledge','damage') or k=='battle_evidence/snapshots.py'}
        replay_fingerprint=digest(dict(replay_input=hashes[str(sources[1].relative_to(root))],dependencies=replay_dependencies,function=inspect.getsource(replay_projections)))
        replay_dir=battle.cache('m34-evidence/stages/'+replay_fingerprint[:16]);projection_path=replay_dir/'state-projections.json';replay_manifest=replay_dir/'manifest.json'
        stage=json.loads(replay_manifest.read_text()) if replay_manifest.exists() else {}
        if not (stage.get('status')=='complete' and projection_path.exists() and file_hash(projection_path)==stage.get('sha256')):
            atomic_json(replay_manifest,dict(status='running',fingerprint=replay_fingerprint))
            try:
                result=replay_projections(saved,projection_path,progress)
                stage=dict(status='complete',fingerprint=replay_fingerprint,sha256=file_hash(projection_path),**result)
                atomic_json(replay_manifest,stage)
            except Exception as exc:
                atomic_json(replay_manifest,dict(status='failed',fingerprint=replay_fingerprint,error=repr(exc),partial_output=str(projection_path)));raise
        m['stages']['snapshots']=dict(stage,path=str(projection_path));atomic_json(manifest,m)
        projection_rows=json.loads(projection_path.read_text())
        validation=replay_validation(saved,projection_rows[-1]['after'] if projection_rows else project(__import__('tracking.battle_state',fromlist=['from_dict']).from_dict(saved['initial_state'])),stage)
        projections={r['event_id']:r for r in projection_rows}
        receipts={r['event']['event_id']:r for r in saved['history']};annotations=annotations or {};events=[]
        if set(annotations)-{e['event_id'] for e in data['events']}:raise ValueError('Annotation references unknown source events')
        for i,e in enumerate(data['events']):
            if e.get('attributes',{}).get('battle_id') not in (None,battle.battle_id):raise ValueError('Cross-battle event')
            ne=normalize(e,receipts.get(e['event_id'],{}),i,annotations.get(e['event_id']));ne['battle_id']=battle.battle_id;events.append(ne)
        # UI command starts are bounded ambiguous windows, not inferred game-turn boundaries.
        for i,cycle in enumerate(data.get('command_cycles',[])):
            events.append(dict(id=f'{battle.battle_id}:command-window:{i}',battle_id=battle.battle_id,position=-1,timestamp=cycle.get('start'),
                kind='command_window',origin='recorded',side='unknown',sources=[dict(source_id=cycle.get('source_id'))],source_event_type='command_cycle',
                uncertainty=['game_turn_unverified'],source_status='candidate'))
        events.sort(key=lambda e:(e['timestamp'] is None,e['timestamp'] if e['timestamp'] is not None else e['position'],e['position'],e['id']))
        for i,e in enumerate(events):
            e['position']=i
            if 'hp' in e:e['hp']['position']=i
        turns=TurnReconstruction(battle.battle_id);effects=EffectDurations();snapshots={};builds=KnownBuilds()
        for b in build_records or []:builds.register(battle_id=battle.battle_id,instance_id=b['instance_id'],record=b['record'])
        unknown_state=project(__import__('tracking.battle_state',fromlist=['from_dict']).from_dict(saved['initial_state']))
        for e in events:
            assignment=turns.consume(e);states=projections.get(e['id'],dict(before=unknown_state,after=unknown_state))
            if type(e.get('timestamp')) in (int,float):
                for when in ('before','after'):
                    if states.get(when+'_frontier') is not None and states[when+'_frontier']>e['timestamp']:
                        states[when]=dict(battle_id=battle.battle_id,pokemon={},unknown='Saved delivery order contains future evidence; chronological snapshot withheld')
            before=snapshot(e,'before',states['before'],effects,assignment,annotation=annotations.get(e['id'],{}).get('snapshot'),builds=builds)
            effects.consume(e,assignment)
            after=snapshot(e,'after',states['after'],effects,assignment,builds=builds)
            for view in (before,after):
                view['engine_replay_validation']=validation
                view['id']='snapshot:'+digest({k:v for k,v in view.items() if k!='id'})
            if e['kind'] in ('action','effect','boundary','switch','forced_replacement') or e.get('hp'):
                snapshots[e['id']]=dict(before=before,after=after)
            unknown_state=states['after']
        samples,changes=hp_transitions(events);speed=speed_audit(turns,snapshots,builds)
        historical=historical_turns(battle.battle_id,root=root,reviews=json.loads(review_path.read_text()) if review_path.is_file() else None,
            cached_log=json.loads(log_path.read_text()) if log_path and log_path.is_file() else None)
        out=dict(schema_version=1,replay_validation=validation,battle_id=battle.battle_id,input_hashes=hashes,reconstruction=turns.export(),
            historical_turns=historical,snapshots=snapshots,effects=effects.history,hp_samples=samples,hp_transitions=changes,speed=speed,
            own_builds=dict(bound_instances=list(pid for battle_id,pid in builds.records),
                limitation='Roster previews/HP alone do not establish configured Speed, SP, alignment, items or abilities'),
            counts=dict(events=len(data['events']),actions=sum(e['kind']=='action' for e in events),
                partial_historical_turns=len(historical),complete_turns=sum(t['status']=='complete' for t in turns.turns),partial_numbered_turns=sum(t['status']!='complete' for t in turns.turns),
                ambiguous_windows=len(turns.windows),unassigned_actions=len(turns.unassigned),snapshots=2*len(snapshots),
                effect_events=sum(e['kind']=='effect' for e in events),hp_samples=len(samples),exact_observed_hp_transitions=len(changes),
                attack_attributed=sum(c['cause_confirmed'] and c['classification']=='attack' for c in changes),
                damage_eligible=sum(c['damage_inference_eligible'] for c in changes),damage_rejected=sum(not c['damage_inference_eligible'] for c in changes),
                speed_eligible=speed['eligible_updates']),
            verification='Recognition-derived observations and conditional deductions, not human ground truth')
        atomic_json(dest/'reconstruction.json',out)
        m['stages']['reconstruction']=dict(status='complete');m.update(status='complete',seconds=time.perf_counter()-started,
            outputs={'reconstruction.json':file_hash(dest/'reconstruction.json')})
        atomic_json(manifest,m)
        return dict(battle_id=battle.battle_id,reused=False,result=str(dest/'reconstruction.json'),seconds=m['seconds'],counts=out['counts'])
    except Exception as exc:m.update(status='failed',error=repr(exc));atomic_json(manifest,m);raise
