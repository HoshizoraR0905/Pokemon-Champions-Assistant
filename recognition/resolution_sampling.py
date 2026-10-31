"""Scoped second-pass source decoding; ordinary acquisition remains 2 FPS.

Reuses the production PTS decoder, HUD visibility, refresh gate and numeric OCR.
A provisional mechanics reference may request inspection; it cannot confirm hits.
"""
from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path
from types import SimpleNamespace


def multi_hit_reference(move_id):
    from damage.data import database
    kb,data,manifest=database()
    documented=kb.resolution_effect(move_id)
    if documented and documented.get('hit_range'):
        return dict(reference_capable=True,hit_range=documented['hit_range'],
            verification=documented['verification'],champions_verified=False,
            champions_documented=True,sources=[documented])
    value=data['moves'].get(move_id,{}).get('multihit')
    return dict(reference_capable=bool(value),hit_range=value if isinstance(value,list) else [value,value] if value else None,
                verification='simulator_reference_only',champions_verified=False,
                sources=[dict(kind='pinned_reference',oracle=manifest['oracle'],files=manifest['files'])])


def dense_plans(engine, *, sample_fps=3., pre_roll=None):
    if not math.isfinite(sample_fps) or sample_fps<3:raise ValueError('Resolution sampling requires >=3 FPS')
    if pre_roll is not None and (not math.isfinite(pre_roll) or pre_roll<=0):raise ValueError('Positive pre-roll is required')
    from tracking.hp_causes import event_time, ADMITTED
    result=engine.hp_resolutions();plans=[]
    records=engine.history
    for action in result['actions']:
        if not action.get('admitted'):continue
        evidence=multi_hit_reference((action['source_move'] or {}).get('canonical_id'))
        episodes=[o for o in result['episodes'] if o['source_event_id']==action['event_id']]
        start=action['evidence']['time']
        if start is None:continue
        completion=action.get('completion_boundary')
        stops=[completion['time']] if completion and completion['time'] is not None else [o['resolution_end']['time'] for o in episodes if o['resolution_end'] and o['resolution_end']['time'] is not None]
        # Actions with no observed changes still deserve inspection if the
        # recognized move is a reference multi-hit candidate. Do not require an
        # already-known target or a successful low-rate HP animation trigger.
        following=[(r.bindings.get('resolved_event') or r.event) for r in records
                   if r.event['event_id']!=action['event_id']]
        ends=[event_time(e) for e in following if event_time(e) is not None and event_time(e)>start and
              e['event_type'] in {'move_execution','switch_out','send_out','command_checkpoint'}]
        stop=min(stops or ends or [start+20.])
        hits=[r for r in records if r.application_status in ADMITTED and r.event['event_type']=='multi_hit'
              and event_time(r.bindings.get('resolved_event') or r.event) is not None and
              start<event_time(r.bindings.get('resolved_event') or r.event)<stop and r.event['attributes'].get('hits',0)>1]
        if not evidence['reference_capable'] and not hits:continue
        baselines=[o['endpoints']['before']['time'] for o in episodes if o['endpoints']['before'] and o['endpoints']['before']['time'] is not None]
        previous=[event_time(e) for e in following if event_time(e) is not None and event_time(e)<start
                  and e['event_type'] in {'move_execution','side_condition_change','switch_out','send_out','phase_observation'}]
        # Retrospective seek starts at independently observed context/baseline,
        # rather than a fixed number of seconds after/before recognition.
        begin=max(0.,min([start]+baselines+([max(previous)] if previous else [])))
        if pre_roll is not None:begin=min(begin,max(0.,start-pre_roll))
        plans.append(dict(action_event_id=action['event_id'],start=begin,end=stop,sample_fps=sample_fps,
            trigger_time=start,pre_roll=pre_roll,method='targeted_original_video_second_pass',
            trigger_basis='independent_hit_announcement' if hits else 'documented_champions_capability' if evidence.get('champions_documented') else 'provisional_reference_requests_inspection',
            mechanics=evidence,hit_event_ids=[r.event['event_id'] for r in hits],
            target_instance_ids=action['target_instance_ids'],
            limitation='Seek can recover pre-trigger source frames; baseline completeness still requires visible HP evidence.'))
    return plans


def sample_window(owner, run_id, *, start, end, sample_fps=3., side=None, slot=None, trigger=None):
    """Checkpoint frames first, then HP-only OCR; never alter saved predictions.

    Optional side/slot selects a physical ROI, not a supplied Pokémon identity or
    HP answer. Results remain source observations until normal identity/admission
    checks and episode endpoint matching accept them.
    """
    import cv2
    from capture import Frame
    from recognition.fast_video import decoded_frames, digest, CachedOCR
    from recognition.event_report import atomic_json
    from recognition.fast_profile import independent_cards
    from recognition.identity_modes import read_hp,hp_signature,hp_refresh
    if not all(math.isfinite(v) for v in (start,end,sample_fps)) or not 0<=start<end or sample_fps<3:
        raise ValueError('Require finite 0 <= start < end and sample_fps >=3')
    folder=owner.cache('hp-resolution-sampling/'+run_id);folder.mkdir(parents=True,exist_ok=True)
    manifest=folder/'manifest.json'
    dependencies=['recognition/resolution_sampling.py','recognition/fast_video.py','recognition/identity_modes.py',
                  'recognition/onnx_ocr.py','recognition/fast_profile.py','recognition/regions.py']
    identity=dict(battle_id=owner.battle_id,video_sha256=digest(owner.video()),start=start,end=end,
        sample_fps=sample_fps,side=side,slot=slot,trigger=trigger,
        model=digest(owner.root/'.cache/m15-onnx-medium/local-manifest.json'),
        sources={p:digest(owner.root/p) for p in dependencies},method='pts_second_pass_hp_rois_only_v1')
    old=json.loads(manifest.read_text()) if manifest.exists() else None
    if old and old['identity']!=identity:raise ValueError('Sampling identity changed; use a new run ID')
    if old and old['status']=='complete':return old
    m=old or dict(identity=identity,status='running',stage='frames',frames=[],counts={})
    counts=Counter(m['counts']);atomic_json(manifest,m)
    try:
        if m['stage']=='frames':
            (folder/'frames').mkdir(exist_ok=True)
            begin=(m['frames'][-1]['target_timestamp']+1/sample_fps if m['frames'] else start)
            if begin<end:
                for image,raw in decoded_frames(owner.video(),folder/'decode.log',start=begin,end=end,sample_fps=sample_fps):
                    n=len(m['frames']);path=folder/'frames'/f'{n:06d}.png'
                    if not cv2.imwrite(str(path),image):raise IOError('Failed to save source frame')
                    raw.update(image=str(path.relative_to(owner.root)),sha256=digest(path))
                    m['frames'].append(raw);counts['sampled_source_frames']+=1
                    m.update(counts=dict(counts));atomic_json(manifest,m)
                counts['source_decoded_frames']+=decoded_frames.last_metadata['source_decoded_frames']
            m.update(stage='hp_ocr',counts=dict(counts));atomic_json(manifest,m)
        counts=Counter(m['counts']);ocr=CachedOCR(folder,counts);recognizer=SimpleNamespace(ocr=ocr)
        (folder/'rows').mkdir(exist_ok=True)
        latest={};rows=[]
        for n,raw in enumerate(m['frames']):
            path=owner.root/raw['image']
            if digest(path)!=raw['sha256']:raise ValueError('Saved frame fingerprint mismatch')
            image=cv2.imread(str(path));t=raw['timestamp'];ocr.source=str(owner.video())+'#'+str(t);ocr.timestamp=t
            cards=[c for c in independent_cards(image) if (side is None or c[0]==side) and
                   (slot is None or c[1]==(0 if slot=='left' else 1))]
            counts['visible_hp_cards']+=len(cards)
            rowpath=folder/'rows'/f'{n:06d}.json'
            if rowpath.exists():
                row=json.loads(rowpath.read_text());counts['completed_hp_rows_reused']+=1
                # Start a new refresh baseline after interruption. Exact crop
                # caching still avoids repeating successful model predictions.
                rows.append(row);continue
            selected=[];reuse=[]
            for card in cards:
                s,i,offset,_=card;key=f'{s}:{i}';sig=hp_signature(image,s,offset)
                fresh,reason=hp_refresh(latest.get(key),sig,t,opportunity=True)
                if fresh:selected.append(card)
                else:
                    original=latest[key]
                    reuse.append(dict(card=key,reason=reason,original_timestamp=original['timestamp'],
                                      observation=deepcopy(original['observation'])))
            snapshot=read_hp(recognizer,Frame(image,ocr.source,n,t,raw),selected,counts)
            for card,obs in zip(selected,snapshot['pokemon']):
                s,i,offset,_=card;key=f'{s}:{i}'
                latest[key]=dict(signature=hp_signature(image,s,offset),timestamp=t,reliable=obs['hp']['value'] is not None,
                                 retries=0,observation=deepcopy(obs))
            for key in list(latest):
                if key not in {f'{c[0]}:{c[1]}' for c in cards}:latest.pop(key)
            row=dict(source=raw,snapshot=snapshot,reused_visible_hp=reuse,
                     note='Independent source HP ROI readings; no reference facts, identity or state injection.')
            atomic_json(rowpath,row);rows.append(row)
            m.update(counts=dict(counts),completed_hp_frames=n+1);atomic_json(manifest,m)
            if (n+1)%10==0:print(f'Dense HP: {n+1}/{len(m["frames"])} frames; {counts["ocr_invocations_performed"]} model predictions',flush=True)
        atomic_json(folder/'observations.json',rows)
        times=[r['timestamp'] for r in m['frames']]
        m.update(status='complete',stage='complete',counts=dict(counts),
            measured=dict(sampled_frames=len(times),frames_per_requested_second=len(times)/(end-start),
                max_pts_gap=max([b-a for a,b in zip(times,times[1:])] or [0]),
                ocr_read_requests=counts['ocr_read_requests'],ocr_model_predictions=counts['ocr_invocations_performed'],
                full_screen_ocr_calls=0,hp_reading_invocations=counts['hud_hp_reading_invocations']),
            outputs=[str(folder/'observations.json')],
            limitations=['A scoped engineering probe is not a multi-hit detection result.',
                        'Default ordinary acquisition sampling is unchanged.',
                        'Pre-trigger frames come from original-video seeking, not a live RAM buffer.'])
        atomic_json(manifest,m);return m
    except BaseException as exc:
        m.update(status='interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed',error=repr(exc),counts=dict(counts))
        atomic_json(manifest,m);raise


def episode_dense_samples(owner, engine, episode, sampled):
    """Bind HP-only rows using the episode's existing stable encounter receipts.

    Raw side/slot readings cannot create an identity. This adapter rejects
    incomplete/gapped encounters and never supplies invented baseline samples.
    Dense data supplements hit timing only; it cannot replace StateEngine HP.
    """
    if not episode['complete_endpoints']:return None
    byid={r.event['event_id']:r for r in engine.history}
    endpoints=episode['endpoints'];before=endpoints['before'];after=endpoints['after']
    if not before or not after:return None
    pid=episode['affected_instance_id'];first=byid[before['event_id']];last=byid[after['event_id']]
    if any(r.bindings.get('actor',{}).get('pokemon_instance_id')!=pid for r in (first,last)):return None
    e=first.bindings.get('resolved_event') or first.event
    side='own' if e['side']=='self' else 'opponent';slot=e['attributes'].get('slot')
    if slot not in {'left','right'}:return None
    card=side+':'+str(0 if slot=='left' else 1)
    label=side+'_active_'+str(1 if slot=='left' else 2)
    rows=json.loads(Path(sampled['outputs'][0]).read_text())
    bound=[];end=episode['resolution_end']['time'] if episode['resolution_end'] else None
    for row in rows:
        raw=row['source'];t=raw['timestamp']
        if t<before['time'] or end is not None and t>=end:continue
        original=next((o for o in row['snapshot']['pokemon'] if o['slot']==label),None)
        reuse=next((o for o in row['reused_visible_hp'] if o['card']==card),None)
        observation=original or (reuse['observation'] if reuse else None)
        if not observation:continue
        hp=observation['hp'];value=hp['value']
        if value is None or hp.get('confidence',0)<.75:continue
        maximum=None
        if episode['unit']=='absolute':
            if not isinstance(value,dict):continue
            maximum=value['maximum'];value=value['current']
        elif not isinstance(value,(int,float)):continue
        bound.append(dict(time=t,value=value,pokemon_instance_id=pid,unit=episode['unit'],
            event_id='dense:'+raw['sha256']+':'+str(t),confidence=hp['confidence'],maximum=maximum,
            evidence=dict(source=deepcopy(raw),observation=deepcopy(observation),
                          visible_unchanged_reuse=deepcopy(reuse),identity_endpoints=[before['event_id'],after['event_id']])))
    return dict(sample_fps=sampled['identity']['sample_fps'],samples=bound,
                baseline_carry_supported=episode['complete_endpoints'] and episode['attribution_status']=='supported')


def endpoint_source_samples(owner,engine,sampled):
    """Bind physical HP reads to existing entry/placement intervals, without replay.

    Unlike the per-hit adapter this may recover incomplete endpoints. It cannot
    create an individual identity or merge two encounters by species.
    """
    from tracking.hp_causes import ADMITTED,event_time
    from recognition.fast_video import digest
    if (sampled['status']!='complete' or sampled['identity'].get('battle_id')!=owner.battle_id or
        engine.state.battle_id!=owner.battle_id or sampled['identity']['video_sha256']!=digest(owner.video())):
        raise ValueError('Require completed source-matched sampling')
    records={r.event['event_id']:r for r in engine.history if not r.retracted}
    exchanges=sorted((r for r in records.values() if r.event['event_type']=='position_change'),
                     key=lambda r:event_time(r.event) if event_time(r.event) is not None else float('inf'))
    episodes=engine.state.knowledge.get('active_entry_episodes',[])
    result=[];visible=set()
    for row in json.loads(Path(sampled['outputs'][0]).read_text()):
        raw=row['source'];t=raw['timestamp']
        if digest(owner.root/raw['image'])!=raw['sha256']:raise ValueError('Source frame changed')
        observations=[(o,None) for o in row['snapshot']['pokemon']]+[
            (r['observation'],r) for r in row['reused_visible_hp']]
        current=set()
        for obs,reuse in observations:
            label=obs['slot'];side='self' if label.startswith('own_') else 'opponent'
            slot='left' if label.endswith('_1') else 'right';key=(side,slot);current.add(key)
            matches=[]
            for ep in episodes:
                departure=(ep.get('departure') or {}).get('timestamp',float('inf'))
                placements=[p for p in ep.get('placements',[]) if p['timestamp']<=t]
                actual_slot=placements[-1]['slot'] if placements else ep.get('slot')
                placed_at=placements[-1]['timestamp'] if placements else ep['start']
                for change in exchanges:
                    when=event_time(change.event)
                    if change.event['side']!=side or when is None or not placed_at<when<=t:continue
                    mapping=change.bindings.get('exchange',{}).get('after',{})
                    slots=[s for s,pid in mapping.items() if pid==ep['instance_id']]
                    actual_slot=slots[0] if change.application_status in ADMITTED and len(slots)==1 else None
                r=records.get(ep['entry_event_id'])
                if ep['start']<t<departure and ep['side']==side and actual_slot==slot and r and r.application_status in ADMITTED:
                    matches.append(ep)
            if len(matches)!=1:continue
            hp=obs['hp'];v=hp['value'];maximum=None;unit='displayed_percent'
            if isinstance(v,dict):maximum=v['maximum'];v=v['current'];unit='absolute'
            if v is None:continue
            result.append(dict(time=t,value=v,maximum=maximum,unit=unit,confidence=hp['confidence'],
                pokemon_instance_id=matches[0]['instance_id'],binding_entry_event_id=matches[0]['entry_event_id'],
                visibility_onset=key not in visible,sample_fps=sampled['identity']['sample_fps'],
                event_id='source-hp:'+raw['sha256']+':'+label,
                evidence=dict(source=deepcopy(raw),observation=deepcopy(obs),visible_unchanged_reuse=deepcopy(reuse),
                    binding_episode_id=matches[0]['episode_id'],sample_manifest_identity=deepcopy(sampled['identity']))))
        visible=current
    return result


def adaptive_rates(source_fps, *, initial_fps=5., maximum_fps=20.):
    """Escalation schedule bounded by actual source metadata, never by a hit name."""
    if not all(math.isfinite(x) for x in (source_fps,initial_fps,maximum_fps)) or initial_fps<3 or maximum_fps<initial_fps:
        raise ValueError('Invalid dense sampling limits')
    cap=min(source_fps,maximum_fps)
    if cap<initial_fps:raise ValueError('Source FPS is below the requested minimum')
    values=[float(initial_fps)]
    while values[-1]<cap:
        values.append(min(cap,values[-1]*2))
    return values


def inspect_resolutions(owner,run_id,engine,*,initial_fps=3.,maximum_fps=4.,window_sampler=None,source_fps=None):
    """Sample one action at a time, escalate unresolved timing, preserve stages."""
    import cv2
    from recognition.event_report import atomic_json
    from recognition.fast_video import digest
    plans=dense_plans(engine,sample_fps=initial_fps)
    folder=owner.cache('hp-resolution-sampling/'+run_id);folder.mkdir(parents=True,exist_ok=True)
    if source_fps is None and plans:
        cap=cv2.VideoCapture(str(owner.video()))
        try:source_fps=float(cap.get(cv2.CAP_PROP_FPS))
        finally:cap.release()
    schedule=adaptive_rates(source_fps,initial_fps=initial_fps,maximum_fps=maximum_fps) if plans else []
    import hashlib
    from tracking.state_engine import hash_state
    history_identity=[dict(event=r.event,ordering=r.ordering,retracted=r.retracted) for r in engine.history]
    identity=dict(plans=plans,schedule=schedule,source_fps=source_fps,
        implementation=digest(Path(__file__)),state_hash=hash_state(engine.state),
        replay_sha256=hashlib.sha256(json.dumps(history_identity,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
    manifest=folder/'inspection-manifest.json'
    old=json.loads(manifest.read_text()) if manifest.exists() else None
    if old and old['identity']!=identity:raise ValueError('Inspection identity changed; select a new run ID')
    if old and old['status']=='complete':return old
    m=old or dict(status='running',identity=identity,completed=[])
    sampler=window_sampler or sample_window
    dense={};base=engine.hp_resolutions()
    atomic_json(manifest,m)
    try:
        for i,plan in enumerate(plans):
            for rate in schedule:
                attempt=next((x for x in m['completed'] if x['action_event_id']==plan['action_event_id'] and x['fps']==rate),None)
                if attempt:
                    sampled=json.loads(Path(attempt['manifest']).read_text())
                else:
                    child=run_id+f'/action-{i:03d}-{rate:g}fps'
                    sampled=sampler(owner,child,start=plan['start'],end=plan['end'],sample_fps=rate,trigger=plan['trigger_time'])
                    child_manifest=owner.cache('hp-resolution-sampling/'+child+'/manifest.json')
                    attempt=dict(action_event_id=plan['action_event_id'],fps=rate,measured=sampled['measured'],manifest=str(child_manifest))
                    m['completed'].append(attempt);atomic_json(manifest,m)
                for ep in base['episodes']:
                    if ep['parent_action_id']!=plan['action_event_id']:continue
                    bound=episode_dense_samples(owner,engine,ep,sampled)
                    if bound is not None:dense[ep['episode_id']]=bound
                projection=engine.hp_resolutions(dense_samples=dense)
                relevant=[ep for ep in projection['episodes'] if ep['source_event_id']==plan['action_event_id']]
                resolved=bool(relevant) and all(ep['hit_resolution']['per_hit_status']=='supported' for ep in relevant)
                attempt['per_hit_resolved']=resolved;atomic_json(manifest,m)
                if resolved:break
                # More frames cannot manufacture missing identity/cause evidence
                # or an independent count. Escalate temporal failures only.
                timing={'dense_sampling_required','final_hit_plateau_unresolved',
                        'dense_endpoint_or_identity_mismatch','independent_hit_count_and_boundaries_not_both_resolved'}
                can_help=any(ep['hit_resolution'].get('hit_count') and set(ep['hit_resolution']['reasons'])&timing for ep in relevant)
                if not can_help:break
        projection=engine.hp_resolutions(dense_samples=dense)
        atomic_json(folder/'episodes-with-dense-hits.json',projection)
        m.update(status='complete',dense_episode_ids=list(dense),planned_windows=len(plans),
                 outputs=[str(folder/'episodes-with-dense-hits.json')])
        atomic_json(manifest,m);return m
    except BaseException as exc:
        m.update(status='interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed',error=repr(exc));atomic_json(manifest,m);raise
