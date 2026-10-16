"""Cache-only Battle 6 reconstruction, audit and portable review delivery.

No OCR, no manually supplied answers, and no independent ground-truth claims.
"""
from bisect import bisect_right
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import re
import shutil
from functools import lru_cache

from scripts.process_m237 import ROOT, BID, P, R, PATHS, load, sha
from recognition.video_sampling import atomic_json, SamplingConfig


def compact_state(state):
    """Projection for presentation; authoritative state remains in replay.json."""
    def fact(v):
        return deepcopy(v)
    pokemon = {}
    for key, mon in state['pokemon'].items():
        pokemon[key] = dict(side=mon['side_id'], species=fact(mon['species']), variant=fact(mon['current_variant']),
            location=fact(mon['location']), fainted=fact(mon['fainted']), status=fact(mon['major_status']),
            hp={k:fact(mon['hp'][k]) for k in ['current','maximum','displayed_percent']},
            stages={k:fact(v['value']) for k,v in mon['stages'].items()},
            moves=deepcopy(mon['moves']),ability=deepcopy(mon['ability']),item=deepcopy(mon['item']))
    return dict(pokemon=pokemon,active_slots={s:deepcopy(v['active_slots']) for s,v in state['sides'].items()},
        weather=deepcopy(state['weather']),terrain=deepcopy(state['terrain']),trick_room=deepcopy(state['trick_room']),
        side_conditions={s:deepcopy(v['conditions']) for s,v in state['sides'].items()},
        unknowns=['Unoccupied or unbound slots are unknown, not confirmed empty.',
                  'Last observed HP may be stale between observations; see fact provenance.',
                  'Unknown status, stages, abilities and items remain unknown.'],
        authoritative_source='replay.json; chronological StateEngine prefix')


def turn_segments(rows, duration):
    """Command reappearance after live activity proposes, but never proves, a turn."""
    starts = []
    action_since = False
    last_menu = None
    for row in rows:
        ui=row['ui']
        menu=any(r['region_type']=='command_menu' and r['visibility']=='visible' for r in ui['regions'])
        if row['message'].get('selected') and row['message'].get('raw_text','').strip():
            action_since=True
        if menu:
            if not starts or (action_since and last_menu is not None and row['timestamp']-last_menu>2):
                starts.append(dict(start=row['timestamp'],evidence=[row['source_id']],
                                   basis='command menu observed after live-message interval' if starts else 'first observed command menu'))
                action_since=False
            last_menu=row['timestamp']
    segments=[]
    if not starts or starts[0]['start']>0:
        segments.append(dict(id='opening',number=None,start=0.,end=starts[0]['start'] if starts else duration,
                             boundary_status='unresolved',basis='opening / no proven turn boundary',evidence=[]))
    for i,start in enumerate(starts):
        segments.append(dict(id=f'turn-proposal-{i+1}',number=i+1,start=start['start'],
                             end=starts[i+1]['start'] if i+1<len(starts) else duration,
                             boundary_status='provisional',basis=start['basis'],evidence=start['evidence']))
    return segments


def coverage_cells(rows, duration, events):
    result=[]
    for start in range(0,math.ceil(duration),10):
        end=min(duration,start+10)
        frames=[r for r in rows if start<=r['timestamp']<end]
        cells={math.floor(r['timestamp']*2) for r in frames}
        expected={round(t*2) for t in SamplingConfig().targets(start,end)}
        messages=[r for r in frames if r['message'].get('selected')]
        emitted=[e for e in events if start<=e['attributes']['observation_time']<end and e['event_type'] not in {'hud_observation','preview_observation'}]
        status=('insufficiently_sampled' if expected-cells else 'sampled_with_event_candidates' if emitted else
                'sampled_unresolved_message_evidence' if messages else 'sampled_without_supported_live_message')
        result.append(dict(start=start,end=end,status=status,sampled_frames=len(frames),
            expected_cells=len(expected),missing_cells=sorted(expected-cells),selected_message_frames=len(messages),
            semantic_candidates=len(emitted),absence_of_battle_events_established=False,
            reason='No independent exhaustive visual audit; sampled silence does not prove no relevant event.',
            frame_ids=[frame_id(r) for r in frames]))
    return result


def frame_id(row):
    # A repeated pixel hash at a later PTS must remain a distinct review observation.
    return row['sha256']+':'+str(row['timestamp'])


def causal_identity_events(rows, roster, emitted, battle_id):
    """Reuse the legacy adapter while withholding its retrospective lookahead."""
    from recognition.identity_events import events_from_observations
    adapted=[]
    for row in rows:
        # Existing identity adapter for HUD/preview; live events use causal prefixes below.
        copy=dict(row)
        copy['snapshot']=deepcopy(row.get('snapshot',{}))
        copy['snapshot']['pokemon']=[m for m in copy['snapshot'].get('pokemon',[]) if '_active_' in m['slot']]
        copy['message']=dict(raw_text='',confidence=0.)
        copy.pop('log',None)  # Historical rows never replay as events at opening time.
        adapted.append(copy)
    events=events_from_observations(dict(observations=adapted,roster=roster),battle_id)
    # The legacy batch parser associates earlier moves with later HP messages.
    # Parse only the available prefix and retain newly observable events. Never
    # replace an earlier event with a reinterpreted version from a later prefix.
    prefix_messages=[]
    for row in rows:
        message_row=dict(row,snapshot={})
        message_row['message']=row['message'] if row['source_id'] in emitted else dict(raw_text='',confidence=0.)
        message_row.pop('log',None)
        prefix_messages.append(message_row)
        if row['source_id'] not in emitted:continue
        prefix_events=events_from_observations(dict(observations=prefix_messages,roster=[]),battle_id)
        events += [e for e in prefix_events if e['attributes']['observation_time']==row['timestamp']]

    return events


def reconstruct():
    from recognition.identity_events import events_from_observations
    from recognition.visual_adapter import visual_events
    from tracking.battle_state import BattleState
    from tracking.state_engine import StateEngine, EventRecord, event_from_dict, ordering
    from scripts.build_m236_review import receipt
    frozen=load('baseline-prediction-seal.json')
    assert all(sha(ROOT/k)==v for k,v in frozen['outputs'].items())
    data=load('baseline-observations.json')
    rows=data['observations']
    emitted={d['source_id'] for d in data['prefix_decisions'] if d['events']}
    events=causal_identity_events(rows,data['roster'],emitted,BID)
    for row in rows:
        for parsed in row['visual']['parsed']:
            if parsed['kind']!='detail':
                continue  # Banner side remains unresolved in the existing U contract.
            request=dict(battle_id=BID,kind='detail',image=row['image'],sha256=row['sha256'],timestamp=row['timestamp'])
            events += [e.to_dict() for e in visual_events(dict(request=request,parsed=parsed,
                       readings=row['visual']['readings'],identity=dict(layout=row['ui']['profile'])),selection=row['visual'].get('selection'))]
        panel=row.get('party_panel')
        if panel:
            request=dict(battle_id=BID,kind='party_panel',image=row['image'],sha256=row['sha256'],timestamp=row['timestamp'])
            events += [e.to_dict() for e in visual_events(dict(request=request,parsed=panel['parsed'],readings=panel['readings'],
                       identity=dict(layout=panel['selection'])),selection=panel['selection'])]
    events.sort(key=lambda e:(e['attributes']['observation_time'],
                              {'coverage_observation':0,'preview_observation':1,'hud_observation':2,'entry_observation':3,'alias_observation':4}.get(e['event_type'],5),e['event_id']))
    # Duplicate event IDs are a baseline defect to report, not silently rewrite.
    duplicates={k:v for k,v in Counter(e['event_id'] for e in events).items() if v>1}
    engine=StateEngine(BattleState(BID,knowledge=dict(reliability_v1=True,reliability_v2=True,identity_v1=True)))
    for i,e in enumerate(events,1):
        e['attributes']['sequence']=i
        if e['event_type'] not in {'hud_observation','coverage_observation','preview_observation','visual_observation'}:
            e['attributes']['source_region_type']='battle_message'
        engine.history.append(EventRecord(e,i,ordering(event_from_dict(e))))
    prefixes={}
    def capture(record,state):
        timestamp=record.event['attributes']['observation_time']
        prefixes[timestamp]=compact_state(state.to_dict())
        if record.delivery_index%100==0:
            print('Replay',record.delivery_index,'/',len(events),flush=True)
    engine.replay(snapshot_callback=capture)
    atomic_json(P/'replay.json',engine.to_dict())
    receipts=[receipt(asdict(r)) for r in engine.history]
    duration=load('baseline-freeze.json')['video']['metadata']['duration_seconds']
    segments=turn_segments(rows,duration)
    times=sorted(prefixes)
    initial=compact_state(engine.initial.to_dict())
    def state_at(t, inclusive=True):
        candidates=[x for x in times if x<=t] if inclusive else [x for x in times if x<t]
        return deepcopy(prefixes[candidates[-1]] if candidates else initial)
    timeline=[]
    selected_prefixes={'initial':initial}
    def prefix_ref(t, inclusive):
        available=[x for x in times if x<=t] if inclusive else [x for x in times if x<t]
        if not available:return 'initial'
        key=str(available[-1]);selected_prefixes[key]=prefixes[available[-1]]
        return key
    for occurrence in data['occurrences']:
        observations=occurrence['observations']
        sources={o['source_id'] for o in observations}
        selected=[r for r in rows if r['source_id'] in sources]
        ids={r['sha256'] for r in selected}
        related=[r for r in receipts if any(ids.intersection(e.get('observation_ids',[])) for e in r['evidence']) and r['kind'] not in {'hud_observation','preview_observation','visual_observation'}]
        best=max(observations,key=lambda o:o['confidence'])
        kinds=[r['kind'] for r in related if r['kind']!='entry_observation']
        timeline.append(dict(id=occurrence['id'],start=occurrence['first_time'],end=occurrence['last_time'],
            kind=kinds[0] if kinds else 'unknown',raw_text=best['raw_text'],
            frame_ids=[frame_id(r) for r in selected],receipts=related,
            admitted=any(r['admitted'] for r in related),candidate_occurrence=True,
            uncertainty=['Automated candidate; no independent human verdict.',
                         'Sampled timestamps are observations, not action onsets.'],
            interpretation_time=occurrence['interpretation_time'],observations=observations,
            state_before_ref=prefix_ref(occurrence['first_time'],False),state_after_ref=prefix_ref(occurrence['last_time'],True)))
    last_hud={}
    for row in rows:
        for mon in row.get('snapshot',{}).get('pokemon',[]):
            if '_active_' not in mon['slot']:continue
            display=dict(slot=mon['slot'],display_name=mon['species']['raw_text'],
                         resolved_species=(mon['species'].get('resolution') or {}).get('canonical_id'),
                         hp=mon['hp'].get('value'),hp_confidence=mon['hp'].get('confidence'))
            if display==last_hud.get(mon['slot']):continue
            last_hud[mon['slot']]=display
            related=[r for r in receipts if r['timestamp']==row['timestamp'] and r['kind']=='hud_observation']
            timeline.append(dict(id='hud:'+frame_id(row)+':'+mon['slot'],start=row['timestamp'],end=row['timestamp'],
                kind='hud_hp',raw_text=display,frame_ids=[frame_id(row)],receipts=related,
                admitted=any(r['admitted'] for r in related),candidate_occurrence=False,
                uncertainty=['Changed UI display only; biological instance, damage source and action timing require receipt support.']))
    # Add non-message UI observations so menus/logs/abilities/negative frames remain reviewable.
    last_ui={}
    for row in rows:
        for region in row['ui']['regions']:
            if region['region_type'] in {'battle_message','active_hud'} or region['visibility'] not in {'visible','partial'}:
                continue
            kind=region['region_type']
            signature=(kind,region['visibility'],json.dumps(region.get('canonical'),sort_keys=True))
            if signature in last_ui and row['timestamp']-last_ui[signature]<5:
                continue
            last_ui[signature]=row['timestamp']
            timeline.append(dict(id='ui:'+frame_id(row)+':'+region['region_id'],start=row['timestamp'],end=row['timestamp'],
                kind=kind,raw_text=(region.get('ocr') or {}),frame_ids=[frame_id(row)],receipts=[],admitted=False,
                candidate_occurrence=False,u_category=kind,uncertainty=['UI observation only; no action inferred.']))
    coverage=coverage_cells(rows,duration,events)
    for cell in coverage:
        timeline.append(dict(id='coverage:'+str(cell['start']),start=cell['start'],end=cell['end'],kind='background',
            raw_text=cell['status'],frame_ids=cell['frame_ids'],receipts=[],admitted=False,candidate_occurrence=False,
            uncertainty=[cell['reason']]))
    timeline.sort(key=lambda e:(e['start'],e['id']))
    for segment in segments:
        segment['events']=[e for e in timeline if segment['start']<=e['start']<segment['end']]
        segment['starting_state']=state_at(segment['start'],False)
        segment['ending_state']=state_at(segment['end'],False)
        segment['recognition_audit']=dict(independent_reviewed_events=0,
            candidate_occurrences=sum(e['candidate_occurrence'] for e in segment['events']),
            unresolved_candidates=sum(e['candidate_occurrence'] and not e['admitted'] for e in segment['events']),
            confirmed_correct=None,confirmed_incorrect=None,missed_events=None)
        segment['uncertainty']=['Ordinal is a proposed command cycle, not an independently established in-game turn.',
                                'Damage source, move targets and end-of-turn ordering remain unknown without explicit evidence.']
        for e in segment['events']:
            e['turn_assignment']=dict(segment_id=segment['id'],proposed_number=segment['number'],status=segment['boundary_status'])
    metrics=dict(video_duration=duration,first_sample=rows[0]['timestamp'],last_sample=rows[-1]['timestamp'],
        sampled_frames=len(rows),base_grid_cells=math.ceil(duration*2),
        sampled_base_grid_cells=len({math.floor(r['timestamp']*2) for r in rows}),
        missing_base_grid_cells=sum(len(c['missing_cells']) for c in coverage),
        proposed_turns=sum(s['number'] is not None for s in segments),confirmed_turn_boundaries=0,
        ocr=load('ocr-ledger.json'),icons=load('icon-ledger.json'),
        raw_message_occurrences=len(data['occurrences']),semantic_candidates=len(events),
        event_kinds=dict(Counter(e['event_type'] for e in events)),
        receipt_statuses=dict(Counter(r['status'] for r in receipts)),duplicate_event_ids=duplicates,
        independently_reviewed_events=0,correct_move_transcriptions=None,correct_canonical_moves=None,
        correct_actor_bindings=None,correct_target_bindings=None,correct_executed_revelations=None,
        missed_moves=None,incorrect_or_duplicate_move_occurrences=None,incorrect_state_facts=None,
        correctness_denominator=0,coverage_is_not_accuracy=True,
        automatic_move_candidates=sum(r['kind']=='move_execution' for r in receipts),
        automatic_canonical_move_references=sum(r['kind']=='move_execution' and bool(r['references'].get('move')) for r in receipts),
        automatic_bound_move_actors=sum(r.event['event_type']=='move_execution' and bool(r.bindings.get('actor',{}).get('pokemon_instance_id')) for r in engine.history),
        automatic_bound_move_targets=sum(r.event['event_type']=='move_execution' and bool(r.bindings.get('target',{}).get('pokemon_instance_id')) for r in engine.history),
        automatic_admitted_move_receipts=sum(r['kind']=='move_execution' and r['admitted'] for r in receipts),
        unadmitted_semantic_receipts=sum(not r['admitted'] for r in receipts if r['kind'] not in {'hud_observation','preview_observation'}),
        independent_review_denominators={k:0 for k in ['move','switch','replacement','ability','identity','hp','field','state_assertion']},
        outcome=dict(winner=None,reason='No verified end-result extraction or independent review. Final evidence remains available.'))
    # Reservation details stay in local ledgers, not duplicated in the review payload.
    for key in ['ocr','icons']:
        metrics[key]={k:v for k,v in metrics[key].items() if k!='reservations'}
    result=dict(schema='m237-provisional-turns-v1',battle_id=BID,status='automated_provisional_unreviewed',
        video=load('baseline-freeze.json')['video'],video_sha256=load('baseline-freeze.json')['video_sha256'],
        metrics=metrics,turns=segments,coverage=coverage,timeline=timeline,
        receipts=receipts,roster=data['roster'],state_prefixes=selected_prefixes,independent_manual_review=False,
        baseline_seal_sha256=sha(P/'baseline-prediction-seal.json'),
        reconstruction_adapter=dict(path='scripts/report_m237.py',sha256=sha(__file__),
                                    state_profile=['reliability_v1','reliability_v2','identity_v1'],
                                    chronology='new-event admission from available prefixes; no retrospective target filling'))
    atomic_json(P/'reconstruction.json',result)
    atomic_json(P/'stages/evaluate.json',dict(status='complete',kind='coverage_and_abstention_only',independent_review_denominator=0,output_sha256=sha(P/'reconstruction.json')))
    print('Reconstruction',len(timeline),'groups;',metrics['proposed_turns'],'provisional cycles; zero independently reviewed events',flush=True)


def known_value(f):
    return f.get('value') if isinstance(f,dict) and f.get('knowledge') in {'observed','derived'} else None


@lru_cache(maxsize=1)
def canonical_names():
    from knowledge import KnowledgeBase
    return {key:' / '.join(dict.fromkeys(n for n in [e.names.get('zh-hans'),e.names.get('en')] if n))
            for key,e in KnowledgeBase().entities.items()}


def friendly_ref(ref):
    if not ref:return 'unknown'
    if isinstance(ref,dict):
        ref=ref.get('name') or ref.get('canonical_id') or ref.get('species_id')
    if ref is None:return 'unknown'
    return canonical_names().get(str(ref),str(ref))


def state_text(state):
    lines=[]
    for side in ['self','opponent']:
        occupants=[]
        for slot,pid in state['active_slots'][side].items():
            mon=state['pokemon'].get(pid,{})
            species=known_value(mon.get('species',{}))
            hp=mon.get('hp',{})
            current,maximum,percent=(known_value(hp.get(k,{})) for k in ['current','maximum','displayed_percent'])
            value=f'{current}/{maximum}' if current is not None and maximum is not None else f'{percent}%' if percent is not None else 'unknown HP'
            occupants.append(f'{slot}: {friendly_ref(species)} ({pid}), last observed {value}; status {known_value(mon.get("status",{})) or "unknown"}; ability {friendly_ref(known_value(mon.get("ability",{}).get("current",{})))}; item {friendly_ref(known_value(mon.get("item",{}).get("identity",{})))}')
        lines.append(('Player' if side=='self' else 'Opponent')+': '+('; '.join(occupants) or 'active identities/slots unknown')+'.')
    known=[]
    for label in ['weather','terrain','trick_room']:
        effect=state[label]
        if known_value(effect['active']) is not None:
            known.append(f'{label}: {known_value(effect["kind"])} active={known_value(effect["active"])}')
    lines.append('Field: '+('; '.join(known) or 'unknown in admitted state')+'. Counters, remaining duration and unobserved abilities/items remain unknown.')
    revealed=[]
    for pid,mon in state['pokemon'].items():
        moves=mon['moves'].get('executed',[])
        if moves:
            revealed.append(pid+': '+', '.join((m.get('move') or {}).get('name',(m.get('move') or {}).get('canonical_id','unknown')) for m in moves))
    known_stages=[pid+': '+', '.join(k+'='+str(known_value(v)) for k,v in mon['stages'].items() if known_value(v) is not None) for pid,mon in state['pokemon'].items() if any(known_value(v) is not None for v in mon['stages'].values())]
    lines.append('Known stat stages: '+('; '.join(known_stages) or 'unknown')+'.')
    lines.append('Executed-move revelations: '+('; '.join(revealed) or 'none admitted at this prefix')+'.')
    return ' '.join(lines)


def feature_audit(rows, result):
    """Each requested capability retains its own unverified evidence denominator."""
    kinds=result['metrics']['event_kinds']
    region_counts=Counter(r['region_type'] for row in rows for r in row['ui']['regions'] if r['visibility']=='visible')
    phases=Counter(row['ui']['phase'] for row in rows)
    mons=[m for r in rows for m in r.get('snapshot',{}).get('pokemon',[])]
    hud=[m for m in mons if '_active_' in m['slot']]
    icons=[m['icon'] for m in mons if m.get('icon')]
    messages=[r for r in rows if r['message'].get('selected')]
    literal_fields=[r['canonical'] for row in rows for r in row['ui']['regions']
                    if r['region_type']=='field_indicator' and r.get('canonical')]
    snapshots=[r['snapshot'] for r in rows if r.get('snapshot')]
    groups=load('baseline-observations.json')['occurrences']
    specs={
        'Team-preview species recognition':phases.get('team_preview',0),
        'Six-member roster identification':len({r['preview_row'] for r in result['roster']}),
        'Initial active Pokémon':kinds.get('hud_observation',0),
        'Entry recognition':kinds.get('send_out',0),
        'Switch / replacement recognition':kinds.get('switch_out',0)+kinds.get('send_out',0),
        'Nickname OCR':sum(bool(m['species'].get('raw_text')) for m in hud if m['slot'].startswith('opponent')),
        'Nickname-to-species association':kinds.get('alias_observation',0),
        'Independent icon matching':sum(bool(i.get('independent_profiles')) for i in icons),
        'Roster-conditioned icon matching':sum(bool(i.get('conditioned')) for i in icons),
        'Mega Evolution':kinds.get('transformation',0),
        'Form identification':sum(bool((m['species'].get('resolution') or {}).get('canonical_id')) for m in mons),
        'Logical active-slot assignment':kinds.get('hud_observation',0),
        'Persistent individual identity / re-entry':kinds.get('send_out',0),
        'Duplicate species handling':len(result['roster']),
        'Ambiguous identity handling':sum(i.get('status')=='ambiguous' for i in icons),
        'Player HUD':sum(m['slot'].startswith('own') for m in hud),
        'Opponent HUD':sum(m['slot'].startswith('opponent') for m in hud),
        'HUD Pokémon names':sum(bool(m['species'].get('raw_text')) for m in hud),
        'HUD Pokémon icons':sum(bool(m.get('icon')) for m in hud),
        'Numeric HP':sum(isinstance(m['hp'].get('value'),dict) for m in hud if m['slot'].startswith('own')),
        'Percentage HP':sum(m['hp'].get('value') is not None for m in hud if m['slot'].startswith('opponent')),
        'Partial HUD':sum(r['visibility']=='partial' for row in rows for r in row['ui']['regions'] if r['region_type']=='active_hud'),
        'Isolated HUD':sum(sum(r['region_type']=='active_hud' and r['visibility']=='visible' for r in row['ui']['regions'])==1 for row in rows),
        'Grey HUD':0,
        'Fading HUD':0,
        'Status indicators':kinds.get('status_change',0)+kinds.get('visual_observation',0),
        'HP changes':kinds.get('hp_change',0),
        'Unavailable versus obscured UI':sum(r['visibility']=='occluded' for row in rows for r in row['ui']['regions']),
        'Current versus historical HP':kinds.get('visual_observation',0)+region_counts.get('battle_log_overlay',0),
        'Visual-row segmentation':len(messages),
        'One-line battle messages':sum(len(r['message']['rows'])==1 for r in messages),
        'Genuine two-line messages':sum(len(r['message']['rows'])==2 for r in messages),
        'OCR transcription':len(messages),
        'Chinese text with English nicknames':sum(bool(re.search('[A-Za-z]',r['message']['raw_text']) and re.search('[\u4e00-\u9fff]',r['message']['raw_text'])) for r in messages),
        'Temporal fusion':sum(len(g['observations'])>1 for g in groups),
        'Repeated-message deduplication':sum(len(g['observations'])>1 for g in groups),
        'Canonical move-name resolution':kinds.get('move_execution',0),
        'Move execution':kinds.get('move_execution',0),
        'Actor attribution':sum(r['kind']=='move_execution' and bool(r['actor']) for r in result['receipts']),
        'Target attribution':sum(r['kind']=='move_execution' and bool(r['target']) for r in result['receipts']),
        'Damage messages':kinds.get('hp_change',0),
        'Effectiveness messages':kinds.get('effectiveness',0),
        'Multi-hit messages':kinds.get('multi_hit',0),
        'Flinch / other battle effects':kinds.get('move_effect',0),
        'Stat changes':kinds.get('stat_change',0),
        'Fainting':kinds.get('faint',0),
        'Replacement announcements':kinds.get('send_out',0),
        'Move-selection menu':phases.get('move_selection',0),
        'Switching / party-selection menu':sum(phases.get(p,0) for p in ['pokemon_selection','switch_selection']),
        'Target-selection menu':region_counts.get('target_selection',0),
        'Available move PP / displayed move information':sum(len(s.get('moves',[])) for s in snapshots),
        'Move-description overlay':region_counts.get('move_description_overlay',0),
        'Pokémon / Party Overlay':region_counts.get('party_overlay',0),
        'Check Status Overlay':region_counts.get('status_overlay',0),
        'Battle Log Overlay':region_counts.get('battle_log_overlay',0),
        'Detailed Pokémon information':phases.get('team_configuration',0)+region_counts.get('status_overlay',0),
        'Displayed choices separated from execution':region_counts.get('command_menu',0)+region_counts.get('target_selection',0),
        'Historical log opening separated from live events':region_counts.get('battle_log_overlay',0),
        'Ability activation banners':region_counts.get('ability_banner',0),
        'Ability-to-Pokémon attribution':kinds.get('ability_activation',0),
        'Held-item revelation':kinds.get('item_activation',0)+kinds.get('item_change',0),
        'Weather':kinds.get('weather_change',0)+len(literal_fields),
        'Terrain':kinds.get('terrain_change',0),
        'Trick Room':kinds.get('trick_room_change',0),
        'Tailwind':0,
        'Aurora Veil':kinds.get('side_condition_change',0),
        'Other field / side conditions':kinds.get('visual_observation',0),
        'Literal displayed field counters':len(literal_fields),
        'Remaining-duration uncertainty':len(literal_fields),
        'Condition activation / expiration':sum(kinds.get(k,0) for k in ['weather_change','terrain_change','side_condition_change','trick_room_change']),
        'False OCR on animation/background':sum(not r['message'].get('selected') for r in rows),
        'Double send-out announcements':sum(e['kind']=='send_out' and len(e.get('receipts',[]))>2 for e in result['timeline']),
        'Missing actor binding after coverage gaps':sum(r['kind']=='move_execution' and not r['admitted'] for r in result['receipts']),
        'End-of-battle result':0,
    }
    return [dict(feature=name,candidate_observations=count,
        status='observed_but_unresolved' if count else 'not_evaluated_due_to_insufficient_semantic_review',
        note='Candidate opportunities, not verified positives/correctness; the named capability needs an independent judgment.' if count else
             'No specific automatic positive; appearance/absence in this recording is unverified.') for name,count in specs.items()]


def presentation_state(node):
    """Keep fact values and source links; avoid repeating OCR arrays in every fact."""
    if isinstance(node,list):return [presentation_state(v) for v in node]
    if not isinstance(node,dict):return node
    out={}
    for key,value in node.items():
        if key=='provenance' and isinstance(value,list):
            out[key]=[{k:presentation_state(v) for k,v in proof.items() if k!='sources'} |
                dict(sources=[dict(source_type=s.get('source_type'),source_id=s.get('source_id'),observation_ids=s.get('observation_ids',[]),
                                   timestamp=(s.get('details') or {}).get('timestamp'),
                                   sha256=(s.get('details') or {}).get('sha256')) for s in proof.get('sources',[])])
                for proof in value]
        else:out[key]=presentation_state(value)
    return out


def diagnostic_report(result):
    diagnostic=result.get('post_baseline_agent_diagnostics')
    if not diagnostic:return []
    lines=['','## Post-baseline visual diagnostic account — provisional, not independent ground truth','',
        'Hoshi is shown as **WIN** and REIKOU as **LOSE** at 750.010s. The baseline recognized neither result semantics nor a winner; this same-frame agent visual reading is a separate diagnostic proposal. The preceding surrender sentence does not itself identify which side surrendered. Device controls cover the final frame.','',
        'The original baseline has 11 command-cycle proposals, including suspected mid-action splits. The eight groups below are a **post-baseline agent regrouping**, supported by chronological message/selection evidence and the visible historical “回合4” heading at 473s. All boundaries remain provisional, especially transitions around replacement and log/selection interfaces. No human-confirmed turn count is claimed.','']
    for t in diagnostic.get('turn_proposals',[]):
        lines += [f'### Diagnostic provisional turn {t["number"]} — {t["start"]:.2f}–{t["end"]:.2f}s','',
            '**Starting participants (provisional).** '+t['starting_context'],'',
            '**Chronological account.** '+t['actions'],'',
            '**Ending participants / field limits.** '+t['ending_context']+' Exact boundary HP, status and unrevealed abilities/items remain unknown unless a linked frame/receipt supplies them.','',
            '**Recognition audit.** '+t['audit'],'']
    lines += ['### Concrete diagnostic failures and state conflicts','',diagnostic['failure_mechanism'],'',
        'Seven additional move-announcement examples are identified visually (451, 520, 567, 571, 578, 637 and 646 seconds). These are **agent diagnostic examples, not an independent recall denominator**. The same scan exposes missed player transformation, withdrawals, Gholdengo fainting and several condition transitions. It is not an exhaustive independent census of all omissions.','',
        'The final baseline projection still marks grassy terrain and rain active despite readable ending messages at approximately 535.023s and 665.512s. Tailwind stop/restart and Light Screen expiration also lack supported transition handling. The engine states printed below are preserved program outputs with these diagnostic conflicts; they must not be treated as verified current battle states.','',
        'A continuously visible late Pelipper Tailwind announcement spans a frame the selector rejects between two automatic occurrence groups (733.007/734.023s). This is a suspected duplicate split; zero duplicate stable IDs does not establish zero duplicated real actions.','',
        '| Observed at | Agent visual reading | Baseline / interpretation |','|---|---|---|']
    for n in diagnostic['notes']:
        text=n['literal_or_panel_reading'].replace('|','\\|')
        lines.append(f'| {n["timestamp"]:.3f}s | {text} | {n["kind"]}; selected={n["baseline_message_selected"]}, overlay={n["baseline_ui_overlay"]}. {n["interpretation"]} |')
    lines += ['', 'All diagnostic records retain source PTS timestamps, frame hashes and image references in the JSON and offline viewer. They are not inserted into recognizer dictionaries, raw baseline outputs, StateEngine history, frozen labels or human annotations.','']
    return lines


def write_report(data, result, features):
    m=result['metrics'];media=result['video'];protocol=load('protocol.json')
    acquisition_path=P/'acquisition.json'
    extra_intervals=json.loads(acquisition_path.read_text()).get('targeted_intervals',[]) if acquisition_path.exists() else []
    extra_duration=sum(b-a for a,b in extra_intervals)
    lines=['# M2.3.7 — Battle 6 full-match recognition review','',
        '**Automated/provisional; no independent human ground truth. Semantic acceptance is incomplete.**', '',
        '[Open the offline review](M2.3.7-battle-6-review/review.html). [Machine-readable turns](M2.3.7-battle-6-turns.json).', '',
        '## Recording and frozen baseline','',
        f'Video: `{media["path"]}`; SHA-256 `{result["video_sha256"]}`; {m["video_duration"]:.2f}s; display {media["metadata"]["width"]}×{media["metadata"]["height"]}; average {media["metadata"]["fps"]:.6f} FPS (variable timestamps).', '',
        'FFmpeg reports coded 1206×2622 with a 90° display-matrix rotation; extraction uses its 2622×1206 display orientation. Container duration is 753.75s; the count/average-rate estimate is separately retained. Actual source PTS, requested grid times and uncertainty are distinct.', '',
        f'Baseline source freeze: `{P.relative_to(ROOT)}/baseline-freeze.json`; prediction seal: `baseline-prediction-seal.json`. No Battle 6 manual answers, nickname mappings or species choices enter recognition. Existing recognizers/parser/StateEngine are unchanged. No diagnostic tuning is folded into this baseline.', '',
        f'Sampling: {protocol["sample_fps"]} FPS throughout, width 328 survey and 1311×603 recognition; targeted {protocol["targeted_fps"]} FPS near UI transitions. HUD/interface anchors are at most {protocol["hud_interval_seconds"]}s apart when stable, plus detected UI transitions. All supported live-message rows are read. Prediction budgets: {protocol["ocr_budget"]} OCR, {protocol["icon_budget"]} icon calls. Exact-pixel caches and per-frame checkpoints are reused.', '',
        f'Extra 3-FPS acquisition covers {extra_duration:.3f}s in {len(extra_intervals)} planned windows, selected chronologically within the frozen 20% duration cap. The later unselected transitions retain the full 2-FPS baseline and are not claimed as enhanced temporal coverage. All planned and decoded target times are retained in acquisition.json.','',
        'Recognition configuration: existing PP-OCRv6 medium ONNX on CPU, batch 1, literal read threshold .75 and supported-occurrence threshold .90. Icons use unchanged default and silhouette profiles; independent-profile disagreement abstains. Existing StateEngine reliability_v1, reliability_v2 and identity_v1 are enabled. Exact source, model revision/checksums and icon source are pinned in the freeze and runtime manifests. Confidence is not measured correctness.','',
        '## Entire-recording coverage and interpretation','',
        f'{m["sampled_frames"]} distinct source-PTS frames; {m["sampled_base_grid_cells"]}/{m["base_grid_cells"]} base grid cells represented; {m["missing_base_grid_cells"]} empty cells. First sample {m["first_sample"]:.6f}s; last sample {m["last_sample"]:.6f}s. This is sampling coverage, not event recall. Sub-frame events and unrecognized regions can still be missed.', '',
        f'{m["proposed_turns"]} proposed command cycles; **0 independently confirmed turn boundaries**. Command menus after live text propose boundaries; animation, switches, two Pokémon selections and unsupported overlays can make that heuristic wrong. Ordinals below are provisional and editable.', '',
        'A complete chronological inventory of sampled intervals is included below. No interval is automatically certified as containing no relevant event. Baseline outcome/winner remains **unknown**: the existing pipeline has no independently validated result extraction for this video.', '',
        '## Opening team preview and identities','',
        'The following are frozen automatic icon proposals, not manually verified roster members. Rows retain form/game identity and duplicate occurrences. Preview membership does not establish an active slot or nickname.', '',
        '| Observed at | Opponent row | Automatic species ID | Status |','|---|---|---|---|']
    seen=set()
    for row in data['roster']:
        key=(row['preview_row'],row['species_id'],row['status'])
        if key in seen:continue
        seen.add(key)
        lines.append(f'| {row["evidence"]["timestamp"]:.3f}s | {row["preview_row"]} | {row["species_id"]} | {row["status"]} |')
    lines += ['', 'Player roster baseline proposals (first observed record for each displayed row):','',
              '| Row | Observed at | Automatic OCR | Canonical proposal |', '|---|---|---|---|']
    own_seen=set()
    for row in data['observations']:
        for mon in row.get('snapshot',{}).get('pokemon',[]):
            if not mon['slot'].startswith('own_team_') or mon['slot'] in own_seen:continue
            own_seen.add(mon['slot'])
            lines.append(f'| {mon["slot"]} | {row["timestamp"]:.3f}s | {mon["species"]["raw_text"]} | {friendly_ref((mon["species"].get("resolution") or {}).get("canonical_id"))} |')
    lines.extend(diagnostic_report(result))
    lines += ['', 'Player roster/name/item OCR and all independent icon scores remain in the technical appendix and per-frame viewer. Nicknames are not translated into species by lookup guesses. Stable individual identity and re-entry are only those admitted by existing receipts. Canonical naming does not establish Champions learnability, an equipped move slot or a usage probability; no new legality assumptions or external knowledge imports are introduced.', '',
              '## Full chronological account','',
              'Quoted text is raw automatic OCR, including errors. A canonical event below is a program proposal with its admission receipt, not a verified action. Unknown targets, outcomes, damage causes and end-of-turn order stay unknown. Starting and ending states are chronological prefixes; later evidence is never backdated.', '']
    for turn in result['turns']:
        title=f'Baseline provisional cycle {turn["number"]}' if turn['number'] is not None else 'Opening / turn unresolved'
        lines += [f'### {title} — {turn["start"]:.3f}–{turn["end"]:.3f}s','',
                  f'Boundary: {turn["boundary_status"]}; {turn["basis"]}.','',
                  '**Starting state.** '+state_text(turn['starting_state']),'','**Chronological observations.**','']
        actions=[e for e in turn['events'] if e['candidate_occurrence'] or e['kind']=='hud_hp']
        if not actions:
            lines.append('- No supported live-message occurrence in this interval. This does not establish that no action occurred.')
        for e in actions:
            if e['kind']=='hud_hp':
                display=e['raw_text']
                lines.append(f'- {e["start"]:.3f}s HUD `{display["slot"]}`: automatic name reading “{display["display_name"]}”; automatic HP {display["hp"]}; resolved species {display["resolved_species"] or "unknown"}. This is display evidence, not proof of damage cause or persistent instance.')
                continue
            text=e['raw_text'].replace('\n',' / ').replace('|','\\|')
            status='; '.join(f'{r["kind"]}: {r["status"]}; move {friendly_ref(r["references"].get("move"))}; actor {friendly_ref(r["actor"])}; target {friendly_ref(r["target"])} ({r["reason"]})' for r in e['receipts']) or 'No supported semantic state receipt; unresolved.'
            lines.append(f'- {e["start"]:.3f}–{e["end"]:.3f}s: “{text}” — `{e["kind"]}`. {status} Actor/target/effects are limited to the attached receipt; unbound information stays unknown. [Evidence](M2.3.7-battle-6-review/review.html#{e["id"]}).')
        fields=[e for e in turn['events'] if e['kind']=='field_indicator' and isinstance(e['raw_text'],dict)]
        if fields:
            literal=[]
            for e in fields:
                o=e['raw_text'];label=(o.get('label') or {}).get('raw_text','');counter=(o.get('counter') or {}).get('raw_text','')
                if label:literal.append(f'{e["start"]:.3f}s: {label} {counter}')
            if literal:lines += ['', 'Literal field-header OCR (not a trigger/duration deduction): '+ '; '.join(dict.fromkeys(literal))+'.']
        lines += ['', '**Ending engine projection (unverified).** '+state_text(turn['ending_state']),'',
                  '**Recognition audit.** '+f'{turn["recognition_audit"]["candidate_occurrences"]} message candidates; {turn["recognition_audit"]["unresolved_candidates"]} without an admitted semantic conclusion. Correct, incorrect and missed-event counts are unmeasured (0 independently reviewed). UI, HP observations, unresolved reads and coverage cards are inspectable in the viewer.','']
    lines += ['## Move, HP, ability, item and field accounting','',
              'The JSON preserves every event receipt, prefix state, evidence reference and proposed turn assignment. Executed moves belong only to the instance bound by StateEngine at that prefix. Menu options and PP are observations, not executions. Historical log rows stay a separate stream; opening the log emits no move. Banner screen edge alone does not bind a Pokémon/side. Literal field counters do not prove remaining turns.', '',
              '## Baseline metrics and review status','',
              '| Measure | Count / result |','|---|---|',
              f'| Raw message occurrence candidates | {m["raw_message_occurrences"]} |',
              f'| Semantic/state observation candidates | {m["semantic_candidates"]} |',
              f'| Automatic move candidates / canonical references | {m["automatic_move_candidates"]} / {m["automatic_canonical_move_references"]} |',
              f'| Automatic instance-bound move actors / targets | {m["automatic_bound_move_actors"]} / {m["automatic_bound_move_targets"]} |',
              f'| Automatically admitted move receipts | {m["automatic_admitted_move_receipts"]} (not independently verified) |',
              f'| Unadmitted semantic receipts | {m["unadmitted_semantic_receipts"]} |',
              f'| OCR attempts / budget | {m["ocr"]["total"]} / {m["ocr"]["limit"]} |',
              f'| Icon attempts / budget | {m["icons"]["total"]} / {m["icons"]["limit"]} |',
              '| Independently reviewed move/event occurrences | 0 |',
              '| Correct transcription / canonical move / actor / target / instance HP | Unknown; correctness denominator 0 |',
              '| Missed moves / false assertions / duplicate real events | Unknown; requires independent review |',
              f'| Duplicate stable candidate IDs | {len(m["duplicate_event_ids"])} |','',
              'Candidate kinds: '+json.dumps(m['event_kinds'],ensure_ascii=False)+'.','',
              'Admission statuses: '+json.dumps(m['receipt_statuses'],ensure_ascii=False)+'. Internal consistency and admission are not correctness metrics. Unknown/unresolved state facts remain in the prefix facts and receipts. Blank review notes are unreviewed, never accepted.', '',
              '## Feature-by-feature evidence availability','',
              'Counts are automatic candidate observations, often shared by several capabilities. They are not independently reviewed denominators or proof that every constituent feature works. No unobserved feature is credited as tested.', '',
              '| Feature | Automatic candidates | Evaluation status |','|---|---|---|']
    lines += [f'| {f["feature"]} | {f["candidate_observations"]} | {f["status"]} |' for f in features]
    if result.get('post_baseline_agent_diagnostics'):
        lines += ['', 'Post-baseline agent visual findings (independent verification still pending): move-description overlay **observed but failed** (misrouted as status); live move/switch/faint messages **observed but failed** in the cited examples; condition expiration and result semantics **observed but failed**; repeated-message deduplication **observed but unresolved / suspected duplicate**; turn boundaries **observed but unresolved**. The historical log has a readable turn-4 heading; it is not a newly executed action. These findings supplement the baseline evidence-availability table and do not create an independent accuracy denominator.']
    lines += ['', '## Known Battle 5 failure modes and remaining priorities','',
              'Retain regression coverage for background OCR, visual-row splitting, double send-outs, fading/grey cards, ability banners, move descriptions, nickname/icons, coverage-gap actor binding, repeated text and historical logs. Battle 6 candidate frames exercise only the detector-positive cases listed above; absent positives and lack of independent review prevent a new-video correctness claim.', '',
              'Highest priorities: independently review turn boundaries and the complete action sequence; inspect unknown message candidates and unscheduled text; verify opening roster/instance binding; review ability-banner and field routing; establish fainting, replacement and final-result coverage. Do not weaken admission to hide these gaps.', '',
              '## Processing costs, cache usage and resume','']
    for stage in ['freeze','survey','acquire','recognize','reconstruct']:
        path=P/'stages'/(stage+'.json')
        if path.exists():
            stage_data=json.loads(path.read_text());lines.append(f'- {stage}: {stage_data.get("status")}; {stage_data.get("seconds",0):.3f}s in its recorded invocation.')
    recognition_stage=P/'stages/recognize.json'
    checkpoint_reuse=0
    if recognition_stage.exists():
        started=json.loads(recognition_stage.read_text()).get('started',0)
        checkpoint_reuse=sum(f.stat().st_mtime<started for f in (P/'observations').glob('*.json'))
    lines += [f'- Reused {checkpoint_reuse} per-frame recognition/context checkpoints from the initial cost probe or an earlier compatible invocation.', f'- Final recognition invocation reused {data["ocr_cache_hits"]} OCR and {data["icon_cache_hits"]} icon predictions; probe/resume caches remain intact.', '',
              'Resume/check commands (only this recording):','', '```sh',
              '.venv/bin/python scripts/process_m237.py --stage verify',
              '.venv/bin/python scripts/process_m237.py --stage reconstruct',
              '.venv/bin/python scripts/process_m237.py --stage deliver',
              '```','',
              'For an interrupted acquisition or recognition, use `--stage acquire` or `--stage recognize`. Completed compatible stages validate their output hashes and return. Per-frame predictions and successful OCR are preserved if a later stage fails. A budget exception is an incomplete stage, never a reduced-coverage completion.', '',
              '## Validation and acceptance','',
              'The previously documented M2.3.4 source-freeze/allowlist incompatibility remains outside this change; its historical seal was not relaxed or resealed. The new baseline pins the current source state. The focused regression suite does not replace the earlier broad milestone suite.','',
              'See `validation.json` in the Battle 6 cache for executed tests/browser checks. Reports generated before that receipt exists must not be interpreted as having passed those checks. Battle 5 frozen files, seals and annotations are checked separately by `--stage verify`. No commit/push, damage/Speed change, priors, recommendations or rule relaxation is part of this work.', '',
              '**Deliverable generation is separate from semantic acceptance.** This full-video automated inventory remains provisional until a human independently reviews it. It does not establish a verified complete battle, true turn count, winner or recognition accuracy.', '',
              '## Coverage appendix','', '| Interval (s) | Status | Sampled / expected base cells |', '|---|---|---|']
    lines += [f'| {c["start"]}–{c["end"]:.2f} | {c["status"]} | {c["expected_cells"]-len(c["missing_cells"])}/{c["expected_cells"]} |' for c in result['coverage']]
    lines += ['', '<details><summary>Technical evidence and provenance</summary>', '',
              'The offline viewer contains expandable OCR rows/tokens, independent and roster-conditioned icon scores, HUD observations, raw region visibility, state receipts and chronological prefix states. `reports/battles/sample_battle_6/M2.3.7/turns.json` is the canonical structured account; `.cache/battles/sample_battle_6/m237/replay.json` is the authoritative existing-engine replay. `baseline-observations.json` is sealed raw prediction output. No manual annotation is merged into these files.', '', '</details>', '']
    validation_path=P/'validation.json'
    if validation_path.exists():
        validation=json.loads(validation_path.read_text())
        if validation.get('status')=='complete':
            test=validation['tests'];browser=validation['browser'];preserved=validation['preservation']
            summary=f'Executed validation: **{test["passed"]} focused regression tests passed** ({test["seconds"]:.2f}s); offline Chrome **passed** for all {browser["decoded_assets"]} unique frame assets and {browser["representative_groups"]} representative groups, plus real JSON download/import, persistence and the human overlay-review override. No unexpected browser errors. Historical preservation verified {preserved["historical_paths"]} paths and {preserved["frozen_sources"]} frozen source dependencies. This validates the workflow, not semantic accuracy.'
            position=lines.index('## Validation and acceptance')+2
            lines[position:position]=[summary,'']
    adjustment_path=P/'acquisition-adjustment.json'
    if adjustment_path.exists():
        prior=json.loads(json.loads(adjustment_path.read_text())['prior_error'])
        position=lines.index('## Processing costs, cache usage and resume')+2
        lines[position:position]=[f'The original acquisition attempt ended in the documented fractional-seek error after {prior.get("seconds",0):.3f}s. Its successful full 2-FPS chunks were reused; the acquisition time below is the resumed invocation, not total cold decoding cost. The 30-second OCR probe cost 34.357s and its 81 per-frame checkpoints were reused. Stage times are recorded invocation wall times, not an end-to-end real-time claim.','']
    text='\n'.join(lines)
    (R/'full-review.md').write_text(text)


def deliver():
    from scripts.package_m236_review import package
    from knowledge import KnowledgeBase
    result=load('reconstruction.json')
    diagnostic_path=P/'agent-visual-diagnostics.json'
    if diagnostic_path.exists():result['post_baseline_agent_diagnostics']=json.loads(diagnostic_path.read_text())
    data=load('baseline-observations.json')
    rows=data['observations']
    R.mkdir(parents=True,exist_ok=True)
    target=R/'review';target.mkdir(exist_ok=True)
    features=feature_audit(rows,result)
    result['feature_audit']=features
    atomic_json(R/'turns.json',result)
    write_report(data,result,features)
    bytime={r['timestamp']:r for r in rows}
    frames=[]
    for row in rows:
        receipts=[r for r in result['receipts'] if r['timestamp']==row['timestamp']]
        mons=[m for m in row.get('snapshot',{}).get('pokemon',[]) if m.get('icon')]
        frames.append(dict(id=frame_id(row),timestamp=row['timestamp'],split='baseline',image=row['image'],
            message=row['message'],pokemon=mons,hud=[],occupancy={},receipts=receipts,entries=[],scheduling=row['scheduling'],visibility_review=None,
            u=dict(ui=row['ui'],message=row['message'],baseline=row['message'],receipts=receipts,
                   explanation='Frozen independent M236-U capability applied to new Battle 6; no verified labels.',profile='frozen_baseline')))
    for note in result.get('post_baseline_agent_diagnostics',{}).get('notes',[]):
        result['timeline'].append(dict(id=note['id'],start=note['timestamp'],end=note['timestamp'],
            kind='agent_visual_diagnostic',raw_text=note['literal_or_panel_reading'],frame_ids=[note['frame_id']],
            receipts=[],admitted=False,candidate_occurrence=False,diagnostic=True,
            uncertainty=['Post-baseline agent visual reading; not independent ground truth or an admitted state fact.'],
            diagnostic_note=note))
    result['timeline'].sort(key=lambda e:(e['start'],e['id']))
    ordered=[f['id'] for f in frames]
    index={key:i for i,key in enumerate(ordered)}
    timeline=[]
    for e in result['timeline']:
        if not e['frame_ids']:continue
        copy=deepcopy(e);first=index[e['frame_ids'][0]];last=index[e['frame_ids'][-1]]
        copy.update(title=(('AGENT DIAGNOSTIC · ' if e.get('diagnostic') else '')+str(e['raw_text']).replace('\n',' / ')[:105] if e['candidate_occurrence'] or e.get('diagnostic') else e['kind'].replace('_',' ')+' · '+str(round(e['start'],3))+'s'),
                    split='baseline',representatives=dict(before=ordered[max(0,first-1)],during=ordered[first],after=ordered[min(len(ordered)-1,last+1)]),
                    priority=3 if e['kind']=='move_execution' and not e['admitted'] else 6 if e['candidate_occurrence'] else 7,
                    category='Post-baseline agent visual diagnostic · not independent truth' if e.get('diagnostic') else 'Unreviewed automatic message candidate' if e['candidate_occurrence'] else 'UI / coverage evidence',
                    question='Inspect actual pixels and correct the event, turn, actor, target and state. No independent verdict exists.',
                    reviewed_occurrence=False)
        timeline.append(copy)
    knowledge=KnowledgeBase()
    payload=dict(frames=frames,events=timeline,preview=deepcopy(result['roster']),evaluations=[],message_roi=[.22,.685,.64,.797],
        species_names={str(e.species_id):' / '.join(dict.fromkeys(n for n in [e.names.get('en'),e.names.get('zh-hans')] if n))
                       for key,e in knowledge.entities.items() if key.startswith('pokeapi:species:')},
        turns=[presentation_state({k:v for k,v in t.items() if k!='events'}) for t in result['turns']],
        metrics=result['metrics'],prefixes=presentation_state(result.get('state_prefixes',{})),agent_diagnostics=result.get('post_baseline_agent_diagnostics'),
        raw={frame_id(r):{k:v for k,v in r.items() if k!='ui'} for r in rows})
    # Reuse byte-identical cache assets with hard links, falling back to copies.
    assets=target/'assets';assets.mkdir(exist_ok=True)
    for row in rows:
        source=ROOT/row['image'];dest=assets/(row['sha256']+source.suffix)
        if not dest.exists():
            try:os.link(source,dest)
            except OSError:shutil.copyfile(source,dest)
    package(payload,target)
    template=(target/'review.html').read_text()
    template=template.replace('M2.3.6-U','Frozen typed UI baseline').replace('M2.3.6','M2.3.7').replace('Battle 5','Battle 6')
    template=template.replace('sample_battle_5','sample_battle_6').replace('m236-human-review-v2','m237-human-review-v1').replace('m236-human-review-v1','m237-legacy-unused')
    template=template.replace('m236-event-review-v2','m237-event-review-v1').replace('m236-review-notes','m237-legacy-unused').replace('m236-event-review-annotations.json','m237-event-review-annotations.json')
    template=template.replace('Review battle events, not OCR scraps','Battle 6 · full-match provisional review')
    template=template.replace('Move Description Overlay — untested','Move Description Overlay — no verified positive')
    template=re.sub(r'<details><summary>What do these counts mean\?</summary>.*?</details>',
        '<details><summary>What do these counts mean?</summary><p>These are unreviewed baseline proposals. Sampling coverage is separate from correctness. No independent human ground truth has been supplied for Battle 6.</p><div id="moveResults"></div></details>',template,count=1)
    template=re.sub(r'<select id="split".*?</select>','<select id="split"><option value="all">Entire independent baseline</option></select>',template,count=1)
    lines=template.splitlines()
    for i,line in enumerate(lines):
        if line.startswith('function renderDenominators()'):
            lines[i]="function renderDenominators(){const m=DATA.metrics;for(const [label,value] of [['Source duration',m.video_duration+'s'],['Sampled PTS frames',m.sampled_frames],['Proposed turn cycles',m.proposed_turns+' · 0 confirmed'],['Independent human event verdicts','0 · accuracy unmeasured']]){const p=el('div',null,$('denominators'));p.className='stat';el('small',label,p);el('strong',value,p)}}"
        elif line.startswith('function reviewProgress()'):
            lines[i]="function reviewProgress(){const candidates=DATA.events.filter(e=>e.candidate_occurrence),judged=candidates.filter(e=>annotations.events[e.id]?.verdict&&!['cannot_determine',''].includes(annotations.events[e.id].verdict)).length;const reviewed=new Set(Object.entries(annotations.frames).filter(([,v])=>hasFeedback(v)).map(([id])=>id));$('reviewProgress').textContent=`Partial human notes: ${judged}/${candidates.length} automatic message candidates with verdicts; ${reviewed.size}/${DATA.frames.length} frames. Unreviewed candidates are not independently established actual occurrences.`}"
        elif line.startswith('listed=listed.filter'):
            lines[i]="if(typeof turnPicker!=='undefined'&&turnPicker.value!=='all'){const t=DATA.turns.find(t=>t.id===turnPicker.value);listed=listed.filter(e=>e.start>=t.start&&e.start<t.end);}"+line
        elif line.startswith('function renderUSummary()'):
            lines[i]='function renderUSummary(){}'
    template='\n'.join(lines)
    # Lexical TDZ: initial render runs before extension declares turnPicker.
    template=template.replace("typeof turnPicker!=='undefined'&&turnPicker.value!=='all'", "document.getElementById('turnPicker')&&document.getElementById('turnPicker').value!=='all'")
    template=template.replace("e.reviewed_occurrence?'One previously reviewed actual event occurrence':'Presentation / review group; excluded from actual-event denominators'", "e.candidate_occurrence?'Unreviewed automatic occurrence candidate':'UI / interval review group'")
    template=template.replace('Preview recognition used icons with OCR disabled.','Opponent preview proposals use independent icons; player-name OCR is retained separately.')
    template=template.replace('Scores remain frozen.','Baseline remains frozen; independent accuracy is unmeasured.')
    extension=(ROOT/'scripts/templates/m237_review_extension.js').read_text()
    template=template.replace('</script></html>',extension+'\n</script></html>')
    (target/'review.html').write_text(template)
    readme='''# Battle 6 offline review

Open `review.html` in Chrome with `assets/` alongside it. No server/network is needed. This extends the repaired M236 portable viewer; the frozen automatic baseline has no independent ground truth.

Use the provisional-turn sidebar to select intervals, then chronological events or Advanced: all frames. Before/during/after buttons show cached source pixels inline. Open evidence details for OCR, icon candidates, receipts and state prefixes. Unknown targets and final outcome are not filled by assumptions.

Use the event controls for verdicts, event type, text, actor, target, identity, HP, status, ability/item, field conditions, fainting/switches, order and duplicate references. Turn controls preserve corrected boundaries and ordering separately. “Save missed-event review note” records an omitted action without altering the baseline.

The sidebar preserves the 11 baseline cycle proposals. The separate diagnostic summary proposes eight provisional action groups; its notes are not independent ground truth. If a false overlay label disables message controls, tick **Override predicted overlay for this frame review** to record what is actually visible. This changes review notes only.

Export annotations regularly as `m237-event-review-annotations.json`; import to resume. Browser storage may be unavailable. No annotation file is overwritten by generation. Unknown fields and blank values survive import/export. Human judgments do not change raw predictions, state or baseline metrics.

All turn numbers and narrative conclusions are automated/provisional until independently reviewed. A sampled background interval does not prove no battle event occurred. Logs are historical, menu choices are not executions, and field counters have no inferred duration meaning.

Resume presentation only:

```sh
.venv/bin/python scripts/process_m237.py --stage deliver
```

Canonical report/JSON: `reports/battles/sample_battle_6/M2.3.7/`. Requested top-level names are compatibility links to these files. Assets are hash-addressed original PNG bytes, hard-linked to compatible caches when supported. Generated HTML/JSON/assets remain local under the existing Git policy. No commit/push.
'''
    (target/'README.md').write_text(readme)
    aliases={'M2.3.7-battle-6-full-review.md':R/'full-review.md','M2.3.7-battle-6-turns.json':R/'turns.json',
             'M2.3.7-battle-6-review':target,
             str((R/'M2.3.7-battle-6-review').relative_to(ROOT/'reports')):target,
             str((R/'M2.3.7-battle-6-turns.json').relative_to(ROOT/'reports')):R/'turns.json'}
    for name,dest in aliases.items():
        alias=ROOT/'reports'/name
        if alias.is_symlink():
            assert alias.resolve()==dest.resolve(), 'Refuse to replace unrelated alias'
        elif alias.exists():
            raise ValueError('Refuse to overwrite unrelated output: '+str(alias))
        else:alias.symlink_to(os.path.relpath(dest,alias.parent),target_is_directory=dest.is_dir())
    atomic_json(P/'delivery.json',dict(status='generated_not_semantically_accepted',html_sha256=sha(target/'review.html'),
        report_sha256=sha(R/'full-review.md'),json_sha256=sha(R/'turns.json'),frames=len(frames),groups=len(timeline),
        manual_reviewed_events=0,assets=len(list(assets.glob('*.png'))),
        renderer_sha256=sha(__file__),template_sha256=sha(ROOT/'scripts/templates/m236_event_review.html') if (ROOT/'scripts/templates/m236_event_review.html').exists() else None,
        extension_sha256=sha(ROOT/'scripts/templates/m237_review_extension.js'),
        reconstruction_sha256=sha(P/'reconstruction.json'),baseline_observations_sha256=sha(P/'baseline-observations.json')))
    atomic_json(P/'stages/viewer.json',dict(status='complete',html_sha256=sha(target/'review.html'),independent_manual_review=False))
    atomic_json(P/'stages/diagnostics.json',dict(status='generated',report_sha256=sha(R/'full-review.md'),validation_receipt='validation.json',semantic_acceptance='incomplete'))
    print('Delivered canonical Battle 6 artifacts and requested aliases',flush=True)
