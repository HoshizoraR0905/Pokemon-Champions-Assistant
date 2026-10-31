"""Video-only replay and immutable prediction seal. Historical extraction is separate."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import time
from battle_events.schema import BattleEvent, Evidence, stable_id
from recognition.video_sampling import atomic_json


def require_live_rows(rows):
    for row in rows:
        if any(k in row for k in ('log','battle_log','reference','annotations','ground_truth')):
            raise ValueError('Pass A accepts live observations only')
        if row['ui'].get('overlay')=='battle_log_overlay' and row.get('message',{}).get('selected'):
            raise ValueError('Historical log cannot supply live-message evidence')
        for event in row['occurrence_decision']['events']:
            if any(e['source_type']=='battle_log' for e in event['evidence']):
                raise ValueError('Historical evidence in video-only candidate')


def banner_side_evidence(row, visual):
    """Calibrated fixed layout; a bare screen-edge label is insufficient.

    B16 source-pixel calibration: docs/b16-banner-hp/banner-side-calibration.json.
    Normal unique-active-species binding still resolves the individual, so
    duplicate same-species actives on one side remain ambiguous.
    """
    layouts={'ability:left':('self',[105,187,472,277]),
             'ability:right':('opponent',[839,187,1232,277])}
    candidate=layouts.get(visual['screen_edge'])
    if candidate is None:return None
    side,bounds=candidate
    region=next((r for r in row.get('ui',{}).get('regions',[]) if r['region_id']==visual['screen_edge']
        and r['region_type']=='ability_banner' and r['visibility']=='visible' and r['bounds']==bounds),None)
    if region is None:return None
    return dict(calibration_id='champions-banner-1311x603-v1',side=side,region_id=region['region_id'],
        bounds=deepcopy(bounds),source_id=row['source_id'],timestamp=row['timestamp'])


def video_events(rows, roster, battle_id):
    from recognition.event_schedule import ordered_entries,entry_slots
    from battle_events.parser import EventParser
    from recognition.trainers import OpeningSequence
    parser=EventParser()
    opening=OpeningSequence()
    require_live_rows(rows)
    events=[]
    for row in roster:
        proof=row['evidence'];t=proof['timestamp']
        events.append(BattleEvent(stable_id(battle_id,'team:'+proof['sha256']+':'+row['side']+':'+str(row['preview_row'])),
            'preview_observation',row['side'],None,None,'Observed team row',{},None,
            [Evidence('team_ui',proof['source'],[proof['sha256']],dict(timestamp=t,image=proof['image']))],None,'supported',[],
            dict(battle_id=battle_id,observation_time=t,row=deepcopy(row))).to_dict())
    banner_sessions={};command_session=False
    for row in rows:
        t=row['timestamp']
        active=row.get('command',{}).get('active',False)
        if not active:command_session=False
        if (active and not command_session and
                row.get('command_inspection',{}).get('reason')=='normal_four_hud_command'):
            command_session=True
            events.append(BattleEvent(stable_id(battle_id,'resolution-command:'+row['source_id']),
                'phase_observation','field',None,None,'Observed normal command UI',{},None,
                [Evidence('video_ui',row['source_id'],[row['sha256']],dict(timestamp=t,image=row['image']))],
                None,'supported',[],dict(battle_id=battle_id,observation_time=t,phase='command',
                    resolution_cycle_start=True,basis='normal_four_hud_command')).to_dict())
        from recognition.command_checkpoint import checkpoint_event
        checkpoint=checkpoint_event(row,battle_id)
        if checkpoint:events.append(checkpoint)
        opening.observe(row)
        for trainer in row.get('trainer_observations',[]):
            if trainer.get('battle_id')!=battle_id:raise ValueError('Trainer observation belongs to another battle')
            events.append(BattleEvent(stable_id(battle_id,'trainer:'+row['source_id']+':'+trainer['side']),
                'trainer_observation',trainer['side'],None,None,trainer['raw_text'],{},None,
                [Evidence('team_preview_trainer',row['source_id'],[row['sha256']],dict(timestamp=t,image=row['image']))],
                # Raw reads (including empty panel / clear foreground retry)
                # must reach consensus. Per-reading confidence stays in trainer.
                None,'supported',[],dict(battle_id=battle_id,observation_time=t,
                trainer=deepcopy(trainer))).to_dict())
        visible_edges={r['region_id'] for r in row.get('ui',{}).get('regions',[])
            if r['region_type']=='ability_banner' and r['visibility']=='visible'}
        visible_edges.update(v['screen_edge'] for v in row.get('visual',{}).get('parsed',[]) if v['kind']=='popup')
        for edge in visible_edges:
            if edge not in banner_sessions or t-banner_sessions[edge]['last_visible']>1.1:
                banner_sessions[edge]=dict(last_visible=t,emitted_semantic=None)
            banner_sessions[edge]['last_visible']=t
        # Reuse established visual adapter for explicitly selected detail panels.
        from recognition.visual_adapter import visual_events
        for visual in row.get('visual',{}).get('parsed',[]):
            if visual.get('status')!='supported':continue
            proof=Evidence('video_'+visual['kind'],row['source_id'],[row['sha256']],
                dict(timestamp=row['timestamp'],image=row['image'],readings=deepcopy(visual.get('readings',{}))))
            if visual['kind']=='popup':
                kind='item' if visual.get('item') else 'ability'
                ref=visual.get(kind)
                binding=banner_side_evidence(row,visual)
                semantic=(visual['species']['canonical_id'],kind,ref['canonical_id'])
                session=banner_sessions[visual['screen_edge']]
                if session['emitted_semantic']==semantic:continue
                session['emitted_semantic']=semantic
                # Validated local layout supplies side; otherwise prefix-local
                # active context may bind a unique named species conservatively.
                raw=visual['species']['name']+'的'+ref['name']
                events.append(BattleEvent(stable_id(battle_id,'banner:'+row['source_id']+':'+visual['screen_edge']),
                    kind+'_activation','unknown',deepcopy(visual['species']),None,raw,
                    {kind:deepcopy(ref)},None,[proof],None,'uncertain',['side_unknown'],
                    dict(battle_id=battle_id,observation_time=row['timestamp'],fusion_context=True,
                        source_region_type=kind+'_banner',screen_edge=visual['screen_edge'],
                        banner_side_evidence=binding,consumption_observed=False)).to_dict())
            elif visual['kind']=='detail':
                request=dict(battle_id=battle_id,image=row['image'],sha256=row['sha256'],timestamp=row['timestamp'],kind='detail')
                events.extend(e.to_dict() for e in visual_events(dict(request=request,parsed=visual,
                    readings=row['visual']['readings'],identity=dict(layout='event-driven-v1')),selection=row['visual'].get('selection')))
        for mon in row.get('snapshot',{}).get('pokemon',[]):
            slot=mon['slot']
            if '_active_' not in slot:continue
            side='self' if slot.startswith('own') else 'opponent'
            attrs=dict(battle_id=battle_id,observation_time=row['timestamp'],slot='left' if slot.endswith('1') else 'right',
                species=deepcopy(mon.get('species')),icon=deepcopy(mon.get('icon')),hp=deepcopy(mon.get('hp')),
                hp_read_status=mon.get('hp_read_status','observed' if (mon.get('hp') or {}).get('value') is not None else 'unreadable'))
            if mon.get('double_faint_hud'):attrs['double_faint_hud']=deepcopy(mon['double_faint_hud'])
            if mon.get('identity_reused_from'):attrs['identity_reused_from']=mon['identity_reused_from']
            events.append(BattleEvent(stable_id(battle_id,'hud:'+row['source_id']+':'+slot),'hud_observation',side,None,None,
                'HUD reading',{},None,[Evidence('video_hud',row['source_id'],[row['sha256']],dict(timestamp=row['timestamp'],image=row['image']))],
                None,'supported',[],attrs).to_dict())
        for event in row['occurrence_decision']['events']:
            event=deepcopy(event)
            refs=ordered_entries(event['original_text']) if event['event_type']=='send_out' else []
            qualification=opening.qualify(event,refs)
            if event['event_type']=='send_out':
                event['attributes']['opening_evidence']=qualification
                if qualification.get('confirmed') and qualification.get('side')=='opponent':
                    event['side']='opponent'
                    event['uncertainty']=[u for u in event['uncertainty'] if u not in {'side_unknown','trainer_id_not_observed'}]
                    event['attributes']['side_basis']=['explicit_preview_trainer_id_match']
            if event['event_type']=='send_out':
                event['attributes']['ordered_display_references']=refs
                event['attributes']['announcement_slot_mapping']='Battle 5 literal-order / HUD-card visual review; screen-HUD left/right'
                observed=deepcopy(event);observed['event_id']=stable_id(battle_id,event['event_id']+':entry')
                observed.update(event_type='entry_observation',actor=None,target=None,uncertainty=[],parsing_confidence='supported')
                observed['attributes']['fusion_context']=False
                events.append(observed)
                if len(refs)==2:
                    for i,(literal,slot) in enumerate(zip(refs,entry_slots(event['side'],refs))):
                        child=deepcopy(event);child['event_id']=stable_id(battle_id,event['event_id']+':member:'+str(i))
                        child['actor']=parser.identity(literal,'species')
                        child['attributes'].update(fusion_context=False,announced_order=i,display_reference=literal)
                        if slot is not None:child['attributes']['slot']=slot
                        child['uncertainty']=[u for u in child['uncertainty'] if u not in {'actor_unresolved','actor_variant_unresolved'}]
                        if child['actor'] is None:child['uncertainty'].append('actor_unresolved')
                        elif child['actor'].get('identity_status')=='species_only':child['uncertainty'].append('actor_variant_unresolved')
                        events.append(child)
                    continue
            events.append(event)
    if any(row.get('identity_mode') for row in rows):
        from recognition.identity_modes import message_identity
        from knowledge.message_names import MessageNames
        from tracking.state_engine import event_from_dict
        names=MessageNames()
        events=[message_identity(event_from_dict(e),names).to_dict() if e['event_type']=='send_out' else e for e in events]
    return sorted(events,key=lambda e:(e['attributes']['observation_time'],
        {'preview_observation':0,'command_checkpoint':.5,'hud_observation':1,'entry_observation':2}.get(e['event_type'],
            2.5 if e['attributes'].get('source_region_type') in {'ability_banner','item_banner'} else 3),
        e['attributes'].get('announced_order',0),e['event_id']))


def reconstruct_and_package(paths,folder,report,rows,roster,occurrences,*,adaptive_multi_hit=False):
    from recognition.fast_report import state_view
    from recognition.fast_video import digest
    from scripts.build_m236_review import receipt
    from tracking.battle_state import BattleState
    from tracking.state_engine import StateEngine,EventRecord,event_from_dict,ordering
    began=time.monotonic();report.mkdir(parents=True,exist_ok=True)
    if (folder/'video-only-seal.json').exists():
        verify_seal(folder)
        return json.loads((report/'summary.json').read_text())
    events=video_events(rows,roster,paths.battle_id)
    mode=json.loads((folder/'manifest.json').read_text())['identity'].get('identity_mode')
    initial=BattleState(paths.battle_id,knowledge=dict(message_identity_v1=bool(mode),reliability_v1=True,reliability_v2=True,identity_v1=True,active_continuity_v1=True,active_persistence_v1=True,command_reconciliation_v1=True))
    from tracking.knowledge_grounding import attach_matching_roster_profile
    initial=attach_matching_roster_profile(initial,roster,root=paths.root)
    engine=StateEngine(initial)
    for i,event in enumerate(events,1):
        event['attributes']['sequence']=i
        engine.history.append(EventRecord(event,i,ordering(event_from_dict(event))))
    def progress(record,state):
        if record.delivery_index%100==0:print(f'Video-only replay: {record.delivery_index}/{len(events)}',flush=True)
    engine.replay(snapshot_callback=progress)
    adaptive=None
    if adaptive_multi_hit:
        from recognition.resolution_sampling import inspect_resolutions
        adaptive=inspect_resolutions(paths,folder.name+'-adaptive-multi-hit',engine,initial_fps=3.,maximum_fps=4.)
        atomic_json(folder/'adaptive-multi-hit.json',adaptive)
    replay=engine.to_dict();receipts=[receipt(asdict(r)) for r in engine.history]
    for r,record in zip(receipts,engine.history):
        r['bindings']=deepcopy(record.bindings);r['turn']=None
        r['turn_status']='unknown; no historical log consulted'
    # Command cycles are review groupings only, never game turn numbers.
    cycles=[];activity=False;last_command=None
    for row in rows:
        if row['occurrence_decision']['events']:activity=True
        if row.get('command',{}).get('active'):
            if last_command is None or activity and row['timestamp']-last_command>3:
                cycles.append(dict(ordinal=len(cycles)+1,start=row['timestamp'],game_turn=None,
                    boundary_status='provisional_command_cycle',source_id=row['source_id']))
                activity=False
            last_command=row['timestamp']
    run_manifest=json.loads((folder/'manifest.json').read_text())
    prediction=dict(battle_id=paths.battle_id,events=events,receipts=receipts,command_cycles=cycles,teams=roster,
        adapter_version='m238-video-adapter-v3',
        reference_previously_available=run_manifest.get('reference_previously_available',False),
        independent_reference_used=False,game_turn_numbers_verified=False,
        coverage=dict(first=rows[0]['timestamp'] if rows else None,last=rows[-1]['timestamp'] if rows else None),
        limitations=['Command cycles do not prove turns.','Announcement slot ordering has one agent-reviewed Battle 5 opening; no independent human verification.',
            'Recognition/cache context existed before this experiment; this is not a held-out accuracy evaluation.',
            'Historical log frames are excluded from live messages.'])
    if adaptive is not None:prediction['adaptive_multi_hit']=adaptive
    atomic_json(folder/'video-only.json',prediction);atomic_json(folder/'replay.json',replay)
    atomic_json(report/'video-only.json',prediction)
    summary=dict(profile='event-driven-v1',battle_id=paths.battle_id,video_duration=rows[-1]['timestamp'] if rows else 0,
        sampled_frames=len(rows),source_event_candidates=len(events),reconstructed_event_count=sum(
            e['event_type'] not in {'hud_observation','preview_observation','entry_observation'} for e in events),
        receipt_statuses=dict(Counter(r['application_status'] for r in replay['history'])),
        command_cycles=len(cycles),verified_game_turns=0,battle_log_event_coverage=None,
        acceptance='partial; independent comparison and human review required',replay_seconds=time.monotonic()-began)
    atomic_json(report/'summary.json',summary)
    frames=[];assets=report/'assets';assets.mkdir(exist_ok=True)
    for row in rows:
        src=paths.root/row['image'];dst=assets/(row['sha256']+'.png')
        if not dst.exists():
            try:os.link(src,dst)
            except OSError:shutil.copy2(src,dst)
        frames.append(dict(timestamp=row['timestamp'],source_id=row['source_id'],image='assets/'+dst.name,
            message=row['message'],command=row.get('command'),decisions=row['region_decisions'],inspection_fps=row['inspection_fps'],
            visual=row.get('visual'),snapshot=row.get('snapshot'),regions=row['ui'].get('regions')))
    atomic_json(report/'frames.json',frames)
    monitoring=[json.loads(p.read_text()) for p in sorted((folder/'monitor').glob('*.json'))]
    atomic_json(report/'monitoring.json',monitoring)
    data=dict(summary=summary,prediction=prediction,frames=frames,monitoring=monitoring,comparison=None,reference=None)
    write_viewer(report,data)
    # Prediction is durable and sealed before the separate reference command can run.
    atomic_json(folder/'video-only-seal.json',dict(stage='video_only_frozen',battle_id=paths.battle_id,
        frozen_at=datetime.now(timezone.utc).isoformat(),
        files={name:digest(folder/name) for name in ['video-only.json','observations.json','replay.json']},
        reference_allowed_after_this_seal=True))
    return summary


def verify_seal(folder):
    from recognition.fast_video import digest
    seal=json.loads((folder/'video-only-seal.json').read_text())
    if seal['stage']!='video_only_frozen':raise ValueError('Pass A is not frozen')
    for name,sha in seal['files'].items():
        if digest(folder/name)!=sha:raise ValueError('Frozen Pass A changed: '+name)
    return seal


def reconstruct_cached(paths,folder,report,source,identity):
    """Reuse a compatible completed recognition stage, preserving its prediction.

    Only replay/report code may change. All actual recognition dependencies and
    source observations must match; historical reference data is never copied.
    """
    from recognition.fast_video import digest
    verify_seal(source)
    parent=json.loads((source/'manifest.json').read_text())
    if identity.get('identity_mode') != parent['identity'].get('identity_mode'):
        raise ValueError('Historical recognition cannot reproduce M2.4 identity policy; use a separately named acquisition diagnostic')
    if parent['status']!='complete' or parent['identity']['version'] not in {'event-driven-v1',identity['version']}:
        raise ValueError('A completed event-driven recognition stage is required')
    if parent['identity']['video_sha256']!=identity['video_sha256']:raise ValueError('Video source changed')
    allowed={'recognition/event_report.py','recognition/fast_report.py','recognition/log_comparison.py',
             'recognition/fast_video.py','main.py','scripts/templates/event_review.html',
             # This optional HP-history metadata is never an acquisition input.
             # Reader, geometry, parser and scheduling changes still invalidate.
             'tracking/hp_causes.py'}
    dependencies={k:v for k,v in parent['identity']['sources'].items() if k not in allowed}
    if any(identity['sources'].get(k)!=v for k,v in dependencies.items()):
        raise ValueError('Recognition dependency changed; cached interpretations cannot be reused')
    started=time.monotonic();manifest_path=folder/'manifest.json'
    manifest=dict(status='running',identity=identity,cold_run=False,completed_stages=['recognition_reused'],
        recognition_source=str(source),recognition_source_counts=parent.get('recognition_source_counts',parent['counts']),
        reference_previously_available=(source/'reference/battle-log.json').exists() or parent.get('reference_previously_available',False),
        counts=dict(ocr_invocations_performed=0,icon_invocations_performed=0,source_decoded_frames=0))
    atomic_json(manifest_path,manifest)
    try:
        shutil.copy2(source/'observations.json',folder/'observations.json')
        shutil.copytree(source/'monitor',folder/'monitor',dirs_exist_ok=True)
        data=json.loads((folder/'observations.json').read_text());require_live_rows(data['observations'])
        result=reconstruct_and_package(paths,folder,report,data['observations'],data['roster'],data['occurrences'])
        manifest.update(status='complete',active_seconds=time.monotonic()-started,results=result,
            completed_stages=['recognition_reused','reconstruction','viewer_packaging'])
        atomic_json(manifest_path,manifest)
        return manifest
    except BaseException as exc:
        manifest.update(status='failed',error=repr(exc),active_seconds=time.monotonic()-started)
        atomic_json(manifest_path,manifest);raise


def write_viewer(report,data):
    from recognition.fast_video import digest
    data=dict(data,prediction_sha256=digest(report/'video-only.json'))
    template=(Path(__file__).resolve().parents[1]/'scripts/templates/event_review.html').read_text()
    payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
    (report/'review.html').write_text(template.replace('__DATA__',payload),encoding='utf-8')
