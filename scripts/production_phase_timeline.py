"""Evidence-led phase labels, conservative boundary intervals, unnumbered cycles.

No recognition is run here. The prototype can read saved evidence, but cannot
manufacture acquisition timings. Absolute turns require explicit turn evidence.
"""
from bisect import bisect_right
from collections import Counter
from copy import deepcopy

PHASES=('PRE_BATTLE','TEAM_PREVIEW','COMMAND','TURN_EXECUTION','FORCED_REPLACEMENT','POST_BATTLE','UNKNOWN')
ACTIONS={'move_execution','switch_out'}
CONDITIONS={'status_change','weather_change','terrain_change','side_condition_change','trick_room_change','stat_change','volatile_change'}


def build_timeline(frames,events,duration,*,receipts=None,measurement='saved_evidence_prototype'):
    by_id={h['event']['event_id']:h for h in receipts or []}
    events=[{**e,'side':(by_id.get(e['event_id'],{}).get('bindings',{}).get('resolved_event') or e)['side']} for e in events]
    events=sorted(events,key=lambda e:e['attributes']['observation_time'])
    arrivals=[e['attributes']['observation_time'] for e in events if e['event_type']=='send_out']
    opening=min(arrivals) if arrivals else None
    endings=[e['attributes']['observation_time'] for e in events if e['event_type'] in {'battle_end','battle_outcome','battle_result'}]
    # A literal terminal OCR observation can label this profiling view even when
    # the unchanged production event parser abstained. Never infer a winner.
    terminal_text=[]
    for f in frames:
        msg=f.get('message') or {}
        if msg.get('confidence',0)>=.95 and ''.join(msg.get('raw_text','').split()).rstrip('！!。.')=='有一方选择了投降':
            endings.append(f['timestamp']);terminal_text.append(dict(timestamp=f['timestamp'],source_id=f.get('source_id'),raw_text=msg['raw_text'],kind='literal_unparsed_terminal_observation'))
    ending=min(endings) if endings else None
    # Replacement provenance comes from existing episode/departure receipts,
    # never an elapsed-time threshold or a command-screen count.
    replacements=[]
    known_faints=[]
    for e in events:
        if e['event_type']=='faint' and e['side'] in {'self','opponent'}:known_faints.append(e)
        if e['event_type']=='send_out':
            before=[f for f in known_faints if f['side']==e['side']]
            if before:
                faint=before[-1];replacements.append(dict(start=faint['attributes']['observation_time'],
                    end=e['attributes']['observation_time'],side=e['side'],faint_event=faint['event_id'],arrival_event=e['event_id'],
                    status='provisional_same_side_faint_then_arrival; exact vacancy/slot needs receipt evidence'))
                known_faints=[f for f in known_faints if f is not faint]
    samples=[];cursor=0;observed=[];cycle=0;executed=False
    for f in sorted(frames,key=lambda r:r['timestamp']):
        t=f['timestamp']
        while cursor<len(events) and events[cursor]['attributes']['observation_time']<=t:
            e=events[cursor];observed.append(e)
            if cycle and e['event_type'] in ACTIONS:executed=True
            cursor+=1
        ui=f.get('ui') or {};ui_phase=ui.get('phase','unknown');confidence=ui.get('confidence',0)
        label=f.get('command_label') or {};w=f.get('w_detection') or {}
        active_replacement=next((r for r in replacements if r['start']<=t<r['end']),None)
        phase='UNKNOWN';certainty='unknown';basis=[]
        if confidence>=.9 and ui_phase=='team_preview':phase='TEAM_PREVIEW';certainty='direct';basis=['verified_team_preview_ui']
        elif confidence>=.9 and ui_phase=='team_configuration':phase='PRE_BATTLE';certainty='direct';basis=['verified_configuration_ui']
        elif ending is not None and t>=ending and ui_phase!='unknown':phase='POST_BATTLE';certainty='contextual';basis=['observed_terminal_event']
        elif opening is not None and t<opening and ui_phase in {'pokemon_selection','switch_selection','move_selection'}:
            phase='PRE_BATTLE';certainty='direct' if confidence>=.9 else 'provisional';basis=['selection_ui_before_observed_opening']
        elif active_replacement and not label.get('visible') and not w.get('normal_controls') and ui_phase in {'pokemon_selection','switch_selection','battle_animation','battle_screen'}:
            phase='FORCED_REPLACEMENT';certainty='provisional';basis=['same_side_observed_faint_then_arrival',active_replacement['faint_event'],active_replacement['arrival_event']]
        elif label.get('visible') or w.get('normal_controls'):
            phase='COMMAND';certainty='direct';basis=['literal_COMMAND_template' if label.get('visible') else 'independent_normal_controls']
        elif opening is not None and t>=opening and ui_phase in {'move_selection','move_target_selection','pokemon_selection','switch_selection'}:
            phase='COMMAND';certainty='provisional';basis=['battle_selection_panel_without_confirmed_normal_controls']
        elif opening is not None and t>=opening and ui_phase in {'battle_message','battle_animation','battle_screen'}:
            phase='TURN_EXECUTION';certainty='contextual';basis=['battle_ui_after_observed_arrival_without_command_controls']
        # Same command view and replacement activity do not create numbered turns.
        if phase=='COMMAND' and certainty=='direct' and (not cycle or executed):
            cycle+=1;executed=False
        explicit=[e for e in observed if e['event_type']=='turn_boundary' and type(e.get('attributes',{}).get('turn')) is int
                  and e['attributes'].get('boundary') in {'start','end'} and e['evidence']]
        turn=explicit[-1]['attributes']['turn'] if explicit else None
        samples.append(dict(timestamp=t,source_id=f.get('source_id'),source_pts=f.get('source_pts'),source_time_base=f.get('source_time_base'),
            image=f.get('image'),sha256=f.get('sha256'),ui_phase=ui_phase,ui_confidence=confidence,phase=phase,certainty=certainty,
            basis=basis,cycle_id=f'C{cycle}' if cycle else None,turn_number=turn,turn_evidence=explicit[-1]['event_id'] if explicit else None,
            provisional_phase=naive_label(ui_phase,label),inspected=f.get('inspected'),processing_wall_seconds=f.get('processing_wall_seconds')))
    intervals=[]
    if samples and samples[0]['timestamp']>0:intervals.append(dict(start=0.,end=samples[0]['timestamp'],phase='UNKNOWN',certainty='unknown',basis=['unobserved_leading_interval'],sources=[]))
    for a,b in zip(samples,samples[1:]):
        same=a['phase']==b['phase'] and a['phase']!='UNKNOWN'
        # No claim is made about a hidden precise transition between the frames.
        intervals.append(dict(start=a['timestamp'],end=b['timestamp'],phase=a['phase'] if same else 'UNKNOWN',
            certainty=('direct' if a['certainty']==b['certainty']=='direct' else 'provisional') if same else 'uncertain_boundary',
            candidates=None if same else list(dict.fromkeys([a['phase'],b['phase']])),
            basis=['agreeing_adjacent_observed_frames'] if same else ['transition_or_unknown_between_source_frames'],
            cycle_id=a['cycle_id'] if a['cycle_id']==b['cycle_id'] else None,
            sources=[dict(timestamp=s['timestamp'],source_id=s['source_id'],source_pts=s['source_pts'],image=s['image'],sha256=s['sha256']) for s in [a,b]]))
    tail=samples[-1]['timestamp'] if samples else 0.
    if tail<duration:intervals.append(dict(start=tail,end=duration,phase='UNKNOWN',certainty='unknown',basis=['unobserved_terminal_interval'],sources=[]))
    coverage=Counter();certainty_seconds=Counter()
    for r in intervals:
        r['duration_seconds']=r['end']-r['start'];coverage[r['phase']]+=r['duration_seconds'];certainty_seconds[r['certainty']]+=r['duration_seconds']
    return dict(schema_version=1,measurement=measurement,video_duration_seconds=duration,samples=samples,intervals=intervals,
        phase_video_seconds={p:coverage[p] for p in PHASES},certainty_video_seconds=dict(certainty_seconds),
        forced_replacement_candidates=replacements,terminal_observations=terminal_text,verified_absolute_turns=sorted({s['turn_number'] for s in samples if s['turn_number'] is not None}),
        cycles=[dict(cycle_id=f'C{i}',turn_number=None,status='provisional_decision_execution_group_not_game_turn') for i in range(1,cycle+1)],
        limitations=['Adjacent sample agreement bounds observed coverage; it does not prove every source frame.',
            'Phase changes are represented as uncertain intervals, never midpoint boundaries.',
            'UI-based cycle groups are not game turn numbers. Forced replacement candidates require independent slot/episode confirmation.',
            'Source-frame labels and operation durations are stored independently; relabeling cannot change recorded timings.'])


def naive_label(ui,label):
    if label.get('visible'):return 'COMMAND'
    return {'team_preview':'TEAM_PREVIEW','team_configuration':'PRE_BATTLE','battle_message':'TURN_EXECUTION','battle_animation':'TURN_EXECUTION'}.get(ui,'UNKNOWN')


def sample_at(timeline,timestamp):
    samples=timeline['samples']
    if timestamp is None or not samples:return None
    i=bisect_right([s['timestamp'] for s in samples],timestamp)-1
    # An operation belongs to its exact sampled frame. Source-decoded counts use
    # interval lookup separately; never borrow a nearest frame for a late event.
    if i>=0 and abs(samples[i]['timestamp']-timestamp)<1e-7:return samples[i]
    return None
