"""M2.3.8-T: cache-only switch/faint continuity audit, replay and offline review."""
import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json
from tracking.battle_state import BattleState
from tracking.state_engine import StateEngine,EventRecord,event_from_dict,ordering
from tracking.active_continuity import current_episode
from tracking.evidence_fusion import context_supported,episode_hud
from scripts.replay_m238s import sha,read,brief,semantic_checks

RUN='m238-switch-continuity-v2'
TITLE='M2.3.8-T-switch-continuity-v2'
OWNER=BattleArtifacts('sample_battle_6',ROOT)
FOLDER=OWNER.cache('event-driven/'+RUN)
BASE=OWNER.cache('event-driven/m238-scrolling-semantics-v4')
SLOTS=('self:left','self:right','opponent:left','opponent:right')
SOURCES=['battle_events/parser.py','battle_events/aliases.py','battle_events/schema.py','tracking/state_engine.py',
 'tracking/battle_state.py','tracking/identity_ledger.py','tracking/evidence_fusion.py','tracking/reliability.py',
 'tracking/active_continuity.py','recognition/event_report.py']
TRANSITIONS={'send_out','switch_out','faint'}
CAUSAL_PATHS={
 'first_refused_reentry':dict(timestamp=436.00666666666666,path='tracking/state_engine.py::_resolve(sending=True)',
   cause='A partial-party species match rejected biological identity reuse and also prevented admitting a new active-entry episode.',
   downstream='At 467.012s HUD created a new Rillaboom occupancy; historical aliases then competed with that current episode.'),
 'cross_side_withdrawal_alias':dict(timestamp=500.00166666666667,path='battle_events/parser.py::parse before substitutions',
   cause='Comma recall grammar did not select self aliases before substitution. Trainer-prefixed withdrawal also selected the trainer side after alias lookup.',
   downstream='500.002s and 506.518s withdrawals lost their actor; subsequent entries had no reliable vacant slot.'),
 'inactive_alias_competition':dict(timestamp=467.01166666666666,path='tracking/evidence_fusion.py::prepare_message / identity_ledger aliases',
   cause='Every historical alias competed with the current actor, including withdrawn instances; species identity and instance claims were collapsed.',
   downstream='527.022s faint lost Rillaboom identity despite one current opponent active episode.'),
 'unplaced_entry_poisoning':dict(timestamp=503.0183333333333,path='tracking/reliability.py::unplaced_entry / context_supported',
   cause='An unresolved earlier departure left both slots apparently occupied. A later named entry became unplaced and gated the whole side.',
   downstream='Moves, stat changes, fainting and further replacements became deferred.'),
 'unconfirmed_same_label_hud':dict(timestamp=None,path='tracking/evidence_fusion.py::episode_hud',
   cause='A later unsuccessful identity acquisition with the same exact label blocked an independently established active episode.',
   downstream='A failed HUD is not admitted by the repair; prior entry/occupancy evidence remains usable only without contradiction or a coverage gap.'),
}


def forbid(*args,**kwargs):raise AssertionError('M2.3.8-T cannot acquire video, OCR or icons')


def preserved():
    files={}
    for folder in [OWNER.cache('event-driven/m238-switch-continuity-v1'),BASE,OWNER.cache('event-driven/m238-live-1'),OWNER.cache('event-driven/m238-live-2'),
                   OWNER.cache('event-driven/m238-live-3-diagnostic'),OWNER.cache('event-driven/m238-trainer-opening-v3')]:
        for name in ('observations.json','events.json','replay.json','prediction.json','video-only.json','manifest.json',
                     'video-only-seal.json','prediction-seal.json','seal.json','manual-review.json','completion.json'):
            p=folder/name
            if p.exists():files[str(p.relative_to(ROOT))]=sha(p)
    for pattern in ('M2.3.7*.md','M2.3.8*.md','M2.3.8*.json','M2.3.8*.html'):
        for p in (ROOT/'reports').glob(pattern):
            if not p.name.startswith(TITLE):files[str(p.relative_to(ROOT))]=sha(p)
    return files


def slot_snapshot(state,t):
    out={}
    for key in SLOTS:
        side,slot=key.split(':');pid=state.sides[side].active_slots.get(slot)
        if not pid:
            out[key]=dict(status='vacant' if slot in state.sides[side].vacant_slots else 'unknown',instance_id=None,episode_id=None)
            continue
        p=state.pokemon[pid];ep=current_episode(state,pid);last=episode_hud(state,side,slot,t)
        reliable=context_supported(state,side,slot,t) and (not last or last.get('status')=='accepted')
        out[key]=dict(status='supported_active' if reliable else 'last_known_identity_current_evidence_unresolved',
            instance_id=pid,episode_id=ep['episode_id'] if ep else None,species_id=p.species.value.get('species_id'),
            name=p.species.value.get('name'),persistent_identity_status=ep['persistent_identity_status'] if ep else 'unknown',
            evidence=deepcopy(p.location.provenance),fainted=p.fainted.value if p.fainted.known else None)
    return out


def frozen_slot_timeline(history,end):
    """Fold frozen receipts; never replay the baseline under new rules."""
    active={key:dict(status='unknown',instance_id=None,episode_id=None) for key in SLOTS}
    vacant=set();states=[dict(timestamp=0,event_id=None,slots=deepcopy(active))]
    for h in history:
        if h['application_status'] not in {'applied_candidate','applied_confirmed'}:continue
        e=h['bindings'].get('resolved_event',h['event']);kind=e['event_type'];pid=h['bindings'].get('actor',{}).get('pokemon_instance_id')
        old=deepcopy(active)
        if kind in {'switch_out','faint'} and pid:
            for key,item in active.items():
                if item.get('instance_id')==pid:active[key]=dict(status='vacant',instance_id=None,episode_id=None);vacant.add(key)
        elif kind in {'send_out','hud_observation'} and pid:
            side=e['side'];slot=e['attributes'].get('slot')
            available=[k.split(':')[1] for k in vacant if k.startswith(side+':')]
            if not slot and kind=='send_out' and len(available)==1:slot=available[0]
            if slot:
                key=side+':'+slot
                identity=h['bindings'].get('identity') or e.get('actor') or {}
                active[key]=dict(status='frozen_admitted_identity',instance_id=pid,name=identity.get('name'),species_id=identity.get('species_id'),episode_id=None)
                vacant.discard(key)
        if old!=active:states.append(dict(timestamp=e['attributes']['observation_time'],event_id=e['event_id'],slots=deepcopy(active)))
    return intervals(states,end)


def intervals(states,end):
    result={key:[] for key in SLOTS}
    for i,change in enumerate(states):
        stop=states[i+1]['timestamp'] if i+1<len(states) else end
        if stop<change['timestamp']:raise ValueError('Backdated timeline')
        for key,item in change['slots'].items():
            rows=result[key]
            if rows and all(rows[-1].get(k)==v for k,v in item.items()) and rows[-1]['end']==change['timestamp']:
                rows[-1]['end']=stop
            else:rows.append(dict(item,start=change['timestamp'],end=stop,event_id=change['event_id']))
    return result


def run_replay(*, profile=None):
    events=read(FOLDER/'events.json')['events']
    engine=StateEngine(BattleState(OWNER.battle_id,knowledge=dict(identity_v1=True,reliability_v1=True,reliability_v2=True,active_continuity_v1=True,**(profile or {}))))
    prefix_failures=[]
    states=[dict(timestamp=0,event_id=None,slots=slot_snapshot(engine.state,0))]
    last_signature=json.dumps(states[-1]['slots'],sort_keys=True)
    for i,e in enumerate(events,1):engine.history.append(EventRecord(deepcopy(e),i,ordering(event_from_dict(e),sequence=i)))
    def progress(record,state):
        nonlocal last_signature
        t=record.event['attributes']['observation_time'];slots=slot_snapshot(state,t)
        # Exclude repeated provenance refreshes from the visual interval key.
        sig=json.dumps({k:{a:v for a,v in x.items() if a!='evidence'} for k,x in slots.items()},sort_keys=True)
        if sig!=last_signature:
            states.append(dict(timestamp=t,event_id=record.event['event_id'],slots=slots));last_signature=sig
        if record.application_status in {'deferred','rejected'} and record.event['event_type'] in TRANSITIONS|{'move_execution','stat_change'}:
            event=record.bindings.get('resolved_event',record.event)
            sid=(event.get('actor') or record.event.get('actor') or {}).get('species_id')
            candidates=[]
            for side,team in state.sides.items():
                if event['side'] not in {side,'unknown'}:continue
                for slot,pid in team.active_slots.items():
                    mon=state.pokemon[pid]
                    if sid is not None and mon.species.value.get('species_id')!=sid:continue
                    ep=current_episode(state,pid)
                    candidates.append(dict(instance_id=pid,slot=slot,side=side,name=mon.species.value.get('name'),
                        episode_id=ep['episode_id'] if ep else None,entry_event_id=ep['entry_event_id'] if ep else None,
                        current_hud=deepcopy(state.knowledge.get('hud_fusion',{}).get('slots',{}).get(side+':'+slot))))
            prefix_failures.append(dict(event_id=event['event_id'],timestamp=t,side=event['side'],species_id=sid,
                reason=record.reason,uncertainty=event['uncertainty'],candidates=candidates))
        if record.delivery_index%100==0:
            status=dict(completed=record.delivery_index,total=len(events),timestamp=t,slot_changes=len(states))
            atomic_json(FOLDER/'progress.json',status);atomic_json(FOLDER/'partial-slot-states.json',states)
            print(json.dumps(status),flush=True)
    engine.replay(snapshot_callback=progress)
    result=engine.to_dict();result['slot_states']=states;result['prefix_failures']=prefix_failures
    atomic_json(FOLDER/'replay.json',result)
    atomic_json(FOLDER/'seal.json',dict(files={n:sha(FOLDER/n) for n in ('events.json','replay.json')}))
    return dict(receipts=dict(Counter(h['application_status'] for h in result['history'])),episodes=len(engine.state.knowledge.get('active_entry_episodes',[])))


def evidence_links(event):
    return [dict(timestamp=p.get('details',{}).get('timestamp'),source_id=p['source_id'],
        image=os.path.relpath(ROOT/p['details']['image'],ROOT/'reports')) for p in event['evidence'] if p.get('details',{}).get('image')]


def first_failure(history):
    out=[]
    for h in history:
        unplaced=h.get('bindings',{}).get('admissibility',{}).get('slot') is False
        if h['application_status'] not in {'deferred','rejected'} and not unplaced:continue
        e=h['bindings'].get('resolved_event',h['event'])
        if e['event_type'] not in TRANSITIONS|{'move_execution','stat_change'}:continue
        attrs=e['attributes'];cause='current_actor_or_slot_evidence_unresolved'
        if h['reason']=='ambiguous_existing_instance_in_partial_or_duplicate_party':cause='first_refused_reentry'
        elif unplaced:cause='unplaced_entry_poisoning'
        elif e['event_type']=='switch_out' and 'ambiguous_display_alias' in e['uncertainty']:cause='cross_side_withdrawal_alias'
        elif 'ambiguous_display_alias' in e['uncertainty']:cause='inactive_alias_competition'
        elif h['event']['event_type']=='send_out' and h['bindings'].get('admissibility',{}).get('slot') is False:cause='unplaced_entry_poisoning'
        out.append(dict(timestamp=attrs['observation_time'],event_id=e['event_id'],kind=e['event_type'],side=e['side'],
            actor=e.get('actor'),reason=h['reason'],uncertainty=e['uncertainty'],earliest_causal_path=CAUSAL_PATHS.get(cause),cause=cause,
            evidence=evidence_links(e)))
    return out


def remaining_diagnostics(new,timeline):
    by_id={h['event']['event_id']:h for h in new['history']}
    result=[]
    for failure in new.get('prefix_failures',[]):
        for candidate in failure['candidates'] or [dict(instance_id=None,episode_id=None,side=failure['side'],name='身份未解析',slot=None)]:
            key=candidate['side']+':'+str(candidate.get('slot'))
            rows=[r for r in timeline.get(key,[]) if r.get('instance_id')==candidate.get('instance_id')
                  and r['start']<=failure['timestamp'] and 'unresolved' in r['status']]
            current=next((r for r in rows if r['start']<=failure['timestamp']<r['end']),None)
            hud=candidate.get('current_hud') or {}
            proofs=evidence_links(by_id[failure['event_id']]['event'])
            for source in hud.get('evidence',{}).get('sources',[]):
                if source.get('details',{}).get('image'):
                    proofs.append(dict(source_id=source['source_id'],timestamp=source['details'].get('timestamp'),
                        image=os.path.relpath(ROOT/source['details']['image'],ROOT/'reports')))
            result.append(dict(side=candidate['side'],name=candidate['name'],instance_id=candidate.get('instance_id'),
                episode_id=candidate.get('episode_id'),entry_event_id=candidate.get('entry_event_id'),
                first_failed_message_time=failure['timestamp'],first_uncertain_interval=rows[0] if rows else None,
                current_gate_interval=current,blocking_hud_timestamp=hud.get('timestamp'),blocking_raw=hud.get('raw'),
                blocking_confidence=hud.get('confidence'),reason=failure['reason'],candidates=failure['candidates'],
                earliest_causal_path='tracking/evidence_fusion.py::episode_hud / prepare_message',
                earliest_causal_explanation=('The active entry is known, but the saved HUD at '+str(hud.get('timestamp'))+
                    's reads '+repr(hud.get('raw'))+' with confidence '+str(hud.get('confidence'))+
                    '. It is not an independently supported current identity or a qualifying consistent exact label. '+
                    'The original known side is retained; no later HUD is used to bind this earlier move.'),
                evidence=proofs))
    return result


def extended_checks(new):
    checks=semantic_checks(new)
    state=new['state'];episodes=state['knowledge'].get('active_entry_episodes',[])
    histories={h['event']['event_id']:h for h in new['history']}
    violations=[]
    for ep in episodes:
        entry=histories[ep['entry_event_id']]
        if ep['start_kind']=='send_out' and entry['application_status'] not in {'applied_candidate','applied_confirmed','recorded_observation'}:
            violations.append(dict(episode=ep['episode_id'],reason='entry_not_admitted'))
        if ep.get('departure'):
            departure=ep['departure']
            if departure['timestamp']<ep['start']:violations.append(dict(episode=ep['episode_id'],reason='departure_before_entry'))
            if departure['reason']=='faint' and state['pokemon'][ep['instance_id']]['fainted']['value'] is not True:
                violations.append(dict(episode=ep['episode_id'],reason='faint_not_preserved'))
        if ep['persistent_identity_status']=='unproven':
            if ep['instance_id'] in ep['possible_prior_instance_ids']:
                violations.append(dict(episode=ep['episode_id'],reason='species_only_individual_merge'))
            for move in state['pokemon'][ep['instance_id']]['moves']['executed']:
                event=histories.get(move['event_id'])
                if event and event['event']['attributes']['observation_time']<ep['start']:
                    violations.append(dict(episode=ep['episode_id'],reason='historical_move_copied_without_identity_proof'))
    checks.update(episode_violations=violations,entry_episodes=len(episodes),
        unresolved_historical_individual_relations=sum(e['persistent_identity_status']=='unproven' for e in episodes),
        remaining_party_counts_unknown=all(s['remaining_available']['knowledge']=='unknown' for s in state['sides'].values()),
        no_independent_false_admission_rate_available=True)
    from tracking.evidence_projection import source_times
    for h in new['history']:
        event=h['bindings'].get('resolved_event',h['event'])
        t=event['attributes']['observation_time']
        times=source_times(event['attributes'].get('binding_sources',[]))
        if any(v>t for v in times):violations.append(dict(event_id=event['event_id'],reason='future_binding_source'))
    named_entry=lambda t:next(e for e in episodes if e['start_kind']=='send_out' and abs(e['start']-t)<.04)
    departure=lambda t:next(h for h in new['history'] if h['bindings'].get('departure') and abs(h['event']['attributes']['observation_time']-t)<.04)
    # These named Battle 6 assertions are diagnostic checks, never runtime rules.
    # Portable synthetic inputs used by tests omit those times and skip this block.
    if any(abs(e['start']-436.007)<.04 for e in episodes):
        reentry=named_entry(436.007);faint=departure(527.022)
        checks['rillaboom_entry_precedes_later_hud']=reentry['start']<467.012 and reentry['slot']=='right'
        checks['faint_527_is_current_436_episode']=faint['bindings']['actor']['pokemon_instance_id']==reentry['instance_id']
        checks['forced_replacement_541_uses_fainted_slot']=named_entry(541.525)['slot']==faint['bindings']['departure']['slot']=='right'
        checks['self_replacement_393_uses_fainted_slot']=named_entry(393.0)['slot']==departure(377.513)['bindings']['departure']['slot']=='right'
        assert all(checks[k] for k in ('rillaboom_entry_precedes_later_hud','faint_527_is_current_436_episode',
            'forced_replacement_541_uses_fainted_slot','self_replacement_393_uses_fainted_slot'))
    assert not violations,violations
    return checks


def make_report(manifest):
    old=read(BASE/'replay.json');new=read(FOLDER/'replay.json');events=read(FOLDER/'events.json')['events']
    by_old={h['event']['event_id']:h for h in old['history']}
    switches=[];changes=[]
    for h in new['history']:
        e=h['event'];prior=by_old[e['event_id']]
        if e['event_type'] in TRANSITIONS:
            before=brief(prior);after=brief(h)
            switches.append(dict(timestamp=e['attributes']['observation_time'],raw=e['original_text'],kind=e['event_type'],
                before=before,after=after,evidence=evidence_links(e),
                resolved=h['application_status'] in {'applied_candidate','applied_confirmed'},
                episode=h['bindings'].get('entry_episode'),departure=h['bindings'].get('departure')))
        if e['event_type'] in {'move_execution','faint'} and (prior['application_status']!=h['application_status'] or prior['reason']!=h['reason']):
            changes.append(dict(timestamp=e['attributes']['observation_time'],before=brief(prior),after=brief(h),evidence=evidence_links(e)))
    count=lambda hs:dict(Counter(h['application_status'] for h in hs))
    causes=lambda hs:dict(Counter(h['reason'] for h in hs if h['application_status']=='deferred'))
    checks=extended_checks(new)
    faint527=next(h for h in new['history'] if h['event']['event_type']=='faint' and abs(h['event']['attributes']['observation_time']-527.022)<.04)
    pid=faint527['bindings'].get('actor',{}).get('pokemon_instance_id')
    checks['faint_527']=dict(receipt=faint527['application_status'],instance_id=pid,
        fainted=new['state']['pokemon'][pid]['fainted']['value'] if pid else None,departure=faint527['bindings'].get('departure'))
    all_departures=[h for h in new['history'] if h['bindings'].get('departure')]
    checks['bound_departures']=len(all_departures)
    checks['faint_numeric_zero_invented']=any(h['bindings']['departure']['historical_hp']['current']['knowledge']=='unknown'
        and new['state']['pokemon'][h['bindings']['actor']['pokemon_instance_id']]['hp']['current'].get('value')==0
        for h in all_departures if h['event']['event_type']=='faint')
    assert not checks['faint_numeric_zero_invented']
    end=read(BASE/'observations.json')['observations'][-1]['timestamp']
    first_by_instance={}
    for item in new.get('prefix_failures',[]):
        keys=[c['instance_id'] for c in item['candidates']] or [item['side']+':unresolved-species:'+str(item['species_id'])]
        for key in keys:first_by_instance.setdefault(key,item)
    timeline=intervals(new['slot_states'],end)
    remaining=remaining_diagnostics(new,timeline)
    data=dict(event_evidence={e['event_id']:evidence_links(e) for e in events},remaining_instance_diagnostics=remaining,first_failure_by_instance=first_by_instance,prefix_failures=new.get('prefix_failures',[]),schema=RUN,battle_id=OWNER.battle_id,source_prediction='m238-scrolling-semantics-v4',
        status='saved_only_diagnostic_candidates_not_independent_identity_accuracy',
        counts=dict(events=len(events),before_receipts=count(old['history']),after_receipts=count(new['history']),
            before_deferred_causes=causes(old['history']),after_deferred_causes=causes(new['history']),
            before_moves=count([h for h in old['history'] if h['event']['event_type']=='move_execution']),
            after_moves=count([h for h in new['history'] if h['event']['event_type']=='move_execution']),
            before_faints=count([h for h in old['history'] if h['event']['event_type']=='faint']),
            after_faints=count([h for h in new['history'] if h['event']['event_type']=='faint']),
            preserved_previous_admissions=sum(h['application_status'] in {'applied_candidate','applied_confirmed','applied_partial'} for h in new['history'] if by_old[h['event']['event_id']]['application_status'] in {'applied_candidate','applied_partial'}),
            before_transitions=count([h for h in old['history'] if h['event']['event_type'] in TRANSITIONS]),
            after_transitions=count([h for h in new['history'] if h['event']['event_type'] in TRANSITIONS])),
        timeline=timeline,before_timeline=frozen_slot_timeline(old['history'],end),
        switches=switches,changed_moves_and_faints=changes,
        unresolved_before=first_failure(old['history']),unresolved_after=first_failure(new['history']),
        active_entry_episodes=new['state']['knowledge'].get('active_entry_episodes',[]),causal_paths=CAUSAL_PATHS,
        validation=checks,report_tests=read(FOLDER/'report-tests.json') if (FOLDER/'report-tests.json').exists() else None,tests=read(FOLDER/'tests.json') if (FOLDER/'tests.json').exists() else None,
        preserved_files=len(manifest['protected']),
        limits=['SideState.party_instance_ids can contain episode-local observed identity placeholders while party_complete is unknown; its cardinality is not the selected-party size. No remaining-party count is inferred.',
            'New active episodes do not prove different biological party members. Same-species re-entry never copies old moves/status/HP without independent continuity evidence.',
            'Persistent individual reuse requires an evidenced explicit instance link or a unique species in an independently verified complete party.',
            'A failed HUD that repeats a consistent exact label is not admitted as new identity evidence. Prior active entry evidence supports continuity; conflicts/gaps still block binding.',
            'No future HUD backfills an earlier slot. Multiple vacancies or competing pending entries stay unplaced until independent HUD evidence.',
            'Faint is distinct from switch_out, vacates only a supported active slot, preserves history and does not fabricate numeric zero HP.',
            'All state mutations remain candidates. Tests and replay invariants do not establish independent full-match recognition accuracy.'])
    report_files=[Path(str(ROOT/'reports'/TITLE)+ext) for ext in ('.md','.json','.html')]
    if any(p.exists() for p in report_files):raise FileExistsError('Preserve existing report outputs; choose a new report version')
    if not (ROOT/'scripts/templates/m238t_review.html').exists():raise FileNotFoundError('Complete and validate the HTML template first')
    for name in ('scripts/replay_m238t.py','scripts/templates/m238t_review.html','scripts/verify_m238t_review.cjs','tests/test_switch_continuity.py'):
        target=FOLDER/'source'/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write((ROOT/name).read_bytes())
    target=ROOT/'reports'/TITLE
    with Path(str(target)+'.json').open('x') as f:json.dump(data,f,ensure_ascii=False,indent=2)
    template=(ROOT/'scripts/templates/m238t_review.html').read_text()
    with Path(str(target)+'.html').open('x') as f:f.write(template.replace('__TITLE__',TITLE).replace('__DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')))
    lines=['# M2.3.8-T：切换、倒下与活动实例连续性','',f'[离线四槽位审阅]({TITLE}.html) · [完整 JSON]({TITLE}.json)。',
        '', '基线：`m238-scrolling-semantics-v4`；使用原有 1190 个事件和保存的原始观测，不运行视频解码、OCR、图标识别。',
        '', '24 条离场 / 入场全部得到候选接纳；527.022s faint 绑定 436.007s 的新活动 episode，腾出 opponent:right，541.525s 后续派出占该空位。三条 faint 均不补造 HP=0。',
        '14 个入场 episode 不是 14 只队伍成员；6 次回场与旧个体的关系仍未被独立证明。保持旧历史，不按物种合并。',
        '', '## 核实计数','', '```json',json.dumps(data['counts'],ensure_ascii=False,indent=2),'```','',
        '## 全部派出 / 撤回 / 倒下对照','', '| 视频秒数 | 原文 | 基线 | 本轮 | 阵营 / 对象 / 槽位 |','|---|---|---|---|---|']
    for r in switches:
        a=r['after'];b=r['before'];p=a['bindings'].get('actor',{}).get('pokemon_instance_id')
        slot=(r['departure'] or r['episode'] or {}).get('slot')
        lines.append(f"| {r['timestamp']:.3f} | {r['raw'].replace(chr(10),' ')} | {b['receipt']} / {b['reason'] or '—'} | {a['receipt']} / {a['reason'] or '—'} | {a['side']} / {(a.get('actor') or {}).get('name','未知')} / {slot or '未知'} / `{p or '实例未知'}` |")
    lines+=['','## 最早因果路径','']+[f"- **{k}** (`{v['path']}`)：{v['cause']} {v['downstream']}" for k,v in CAUSAL_PATHS.items()]
    lines+=['','## 队伍个体与入场 episode','',
        '四槽位与 PokémonState 仍是当前可观察状态的权威来源；`active_entry_episodes` 仅保存入场、放置、离场与证据历史。',
        '队伍不完整时，同物种返回创建新的入场身份记录，并把旧非活动实例列为未证实的连续性候选；不会自动继承旧招式、状态或 HP，也不宣称它们必定是不同个体。旧记录及其历史保持可查。',
        '有明确个体关联或独立验证的完整队伍且物种唯一时，可复用持久个体，同时创建新的入场 episode。旧 HP 作为历史证据保存，新 episode 的当前 HP 等待新观察。',
        '', '## 验证','',json.dumps(data['tests'],ensure_ascii=False),'',json.dumps(data['report_tests'],ensure_ascii=False),'',
        f"527.022s faint：{checks['faint_527']['receipt']}；实例 `{pid}`；fainted={checks['faint_527']['fainted']}。",'',
        f"受检 {len(manifest['protected'])} 个历史文件哈希未变。绑定不一致 {len(checks['violations'])}；未补造 faint HP=0。",'']
    lines+=['','## 仍未绑定的活动实例','', '| 第一次未入场消息 | 现存身份 / 侧 / 槽位 | 最早相关缺口 / 阻挡 HUD | 原因 |','|---|---|---|---|']
    for item in remaining:
        interval=item['current_gate_interval'] or item['first_uncertain_interval'] or {}
        lines.append(f"| {item['first_failed_message_time']:.3f} | {item['name']} / {item['side']} / `{item['instance_id']}` | {interval.get('start','未知')}s；{item['blocking_hud_timestamp']}s raw={item['blocking_raw']!r}, confidence={item['blocking_confidence']} | {item['reason']} |")
    lines+=['','此处保留原有阵营，但不使用未来 HUD 回填较早的实例绑定。另有 86 条 retained HUD 源身份未解决，以及 588.515s 畏缩观察因阵营证据不足而 deferred；均未扩展为本轮 parser/recognition 修复。','',
        '兼容性：`active_continuity_v1` 是版本化的可观察状态策略；本轮及后续新建 event-driven replay 开启，旧冻结记录不重写；原 profile 未启用该标志时保留既有行为。未更改 PokémonState / SideState 的序列化结构。','']
    lines+=['- '+x for x in data['limits']]
    lines+=['','## 精确命令与恢复','', '```sh',
        'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/replay_m238t.py --stage prepare',
        'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/replay_m238t.py --stage replay',
        'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/replay_m238t.py --stage report',
        data['tests']['command'] if data['tests'] else 'tests pending',
        data['report_tests']['command'] if data['report_tests'] else 'report tests pending','```','',
        f'命名空间：`{FOLDER.relative_to(ROOT)}`。已完成阶段直接复用；运行时源码哈希变化则须新建版本。新 viewer 复用既有 PNG，不复制图片。',
        '未提交、未推送。该范围到此停止，等待人工审阅。','']
    with Path(str(target)+'.md').open('x') as f:f.write('\n'.join(lines))
    return dict(counts=data['counts'],validation=checks)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',required=True,choices=['prepare','replay','report']);args=parser.parse_args()
    FOLDER.mkdir(parents=True,exist_ok=True);mp=FOLDER/'manifest.json';identity={n:sha(ROOT/n) for n in SOURCES}
    if mp.exists():
        manifest=read(mp)
        if manifest['sources']!=identity:raise ValueError('Sources changed; preserve checkpoint and use a new namespace')
        if args.stage in manifest['completed']:print('Completed stage reused:',args.stage);return
    else:
        manifest=dict(schema=RUN,battle_id=OWNER.battle_id,sources=identity,protected=preserved(),completed=[],status='ready',
            profile=dict(identity_v1=True,reliability_v1=True,reliability_v2=True,active_continuity_v1=True),ocr_calls=0,icon_calls=0,decoded_frames=0)
        atomic_json(mp,manifest)
        for name in SOURCES:
            target=FOLDER/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    manifest.update(stage=args.stage,status='running');atomic_json(mp,manifest)
    try:
        with ExitStack() as stack:
            for name in ('recognition.fast_video.CachedOCR.read','recognition.fast_video.CachedOCR.predict','recognition.fast_video.CachedIcons.identify',
                         'recognition.fast_video.decoded_frames','cv2.imread','cv2.VideoCapture'):
                stack.enter_context(patch(name,forbid))
            if args.stage=='prepare':
                for name,value in read(BASE/'seal.json')['files'].items():assert sha(BASE/name)==value,name
                events=read(BASE/'events.json')
                atomic_json(FOLDER/'events.json',events);result=dict(events=len(events['events']),source_events_sha256=sha(BASE/'events.json'))
            elif args.stage=='replay':
                if 'prepare' not in manifest['completed']:raise ValueError('prepare first')
                result=run_replay()
            else:
                if 'replay' not in manifest['completed']:raise ValueError('replay first')
                result=make_report(manifest)
        assert all(sha(ROOT/n)==v for n,v in manifest['protected'].items())
        manifest['completed'].append(args.stage);manifest.update(status='complete' if args.stage=='report' else 'ready',result=result)
        atomic_json(mp,manifest);print(json.dumps(result,ensure_ascii=False,indent=2))
    except BaseException as exc:
        manifest.update(status='failed',error=repr(exc));atomic_json(mp,manifest);raise


if __name__=='__main__':main()
