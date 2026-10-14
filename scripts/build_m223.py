"""Reconcile cached full-battle observations with an explicit annotation overlay.

OCR predictions are generated before this script reads annotations. Replay uses
the existing state engine, rule default, and timeline renderer; no media decoding.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from difflib import SequenceMatcher
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts, add_arguments, historical_reference
from battle_events import EventParser, BattleContext, Participant
from battle_events.schema import stable_id
from recognition.battle_log import assemble_views, compact
from tracking.battle_state import from_dict
from tracking.state_engine import StateEngine, EventRecord, event_from_dict, ordering, hash_state
from tracking.state_timeline import build_timeline, render_html
from scripts.reconstruct_m223 import save


def read(path):return json.loads(path.read_text())


def collect(cache):
    values=[]
    for p in sorted(cache.glob('m223-ocr-*/observations.json')):
        values.extend(read(p)['observations'])
    return values


def replay(initial, events):
    engine=StateEngine(from_dict(initial));snapshots=[]
    for n,event in enumerate(events,1):
        event['attributes']['sequence']=n
        parsed=event_from_dict(event)
        engine.history.append(EventRecord(parsed.to_dict(),n-1,ordering(parsed)))
    def snapshot(record,state):
        if record.application_status in {'deferred','rejected'}:
            print(record.application_status,record.event['original_text'],record.reason,flush=True)
        snapshots.append({'event_id':record.event['event_id'],'application_status':record.application_status,
                          'state_hash':record.state_hash,'state':state.to_dict()})
        if len(snapshots)%20==0:print(f'Replayed {len(snapshots)}/{len(events)} events',flush=True)
    engine.replay(snapshot_callback=snapshot)
    envelope=engine.to_dict()
    assert StateEngine.from_dict(envelope).to_dict()==envelope
    for event in events:engine.apply(event)
    assert engine.to_dict()==envelope
    return engine,snapshots


def build(args):
    if args.paths.battle_id!='sample_battle_3':raise ValueError('This reconciler uses sample_battle_3-specific checked annotations; use the generic event/replay tools for another recording')
    args.paths.check_identity(read(args.initial)['state']['battle_id'])
    observations=collect(args.cache)
    by_image={v['image']:v for v in observations}
    evidence_dir=args.paths.report('M2.2.3-evidence')
    evidence_dir.mkdir(parents=True,exist_ok=True)
    def evidence_frame(value):
        original=ROOT/value['image']
        filename=original.parent.name+'-'+original.name
        destination=evidence_dir/filename
        if not destination.exists():shutil.copyfile(original,destination)
        digest=hashlib.sha256(destination.read_bytes()).hexdigest()
        expected=value.get('sha256',value.get('frame_sha256'))
        if expected and expected!=digest:raise ValueError('Evidence checksum mismatch')
        return {'image':historical_reference(destination),'sha256':digest,'timestamp':value['timestamp'],
                'timestamp_uncertainty_seconds':value.get('timestamp_uncertainty_seconds',.25),
                'source_id':value['source_id'],'original_cached_image':value['image']}
    views=[deepcopy(v['log']) for v in observations if 'log' in v and Path(v['image']).parent.name.startswith('m223-log-')]
    for view in views:
        # Earlier cached observations used a more conservative edge-row flag.
        for row in view['observations']:row['partial']=row['box'][3]-row['box'][1]<65
    entries,issues=assemble_views(views,ignore_partial_overlap=True)
    parser=EventParser();context=BattleContext()
    trainers=read(args.cache/'m223-snapshots/40.json')['trainers']
    for side,trainer in trainers.items():
        context.participants[side]=Participant(side,trainer['display_name'],None,trainer['evidence'])
        if trainer['ocr_confidence']>=.75:context.color_sides[trainer['evidence'][0]['color']]=side
    initial=read(args.initial)['state']
    for side,team in initial['sides'].items():
        context.active[side]={initial['pokemon'][pid]['species']['value']['canonical_id'] for pid in team['active_slots'].values()}
    automatic=parser.parse_sequence(entries,deepcopy(context),args.battle_id)
    save(args.output.parent/'M2.2.3-automatic-log-events.json',{'schema_version':1,'views':views,'entries':entries,
         'assembly_issues':issues,'event_candidates':[e.to_dict() for e in automatic],
         'method':'existing recognizer and assembler, observed trainer calibration; no transcription overlay or nickname bindings'})
    annotations=read(args.annotations)
    alias_image=by_image['.cache/m223-survey/000048.jpg']
    alias_evidence=evidence_frame(alias_image)
    context.display_aliases={'GreatGeneral':{'identity':parser.identity('仆刀将军','species'),'evidence':[alias_evidence],
                                            'method':'manual icon/display-name binding'},
                             'Sally':{'identity':parser.identity('暴飞龙','species'),
                                      'evidence':[evidence_frame(by_image['.cache/m223-survey/000179.jpg'])],
                                      'method':'manual icon/display-name binding'}}
    checked=[]
    for rows in annotations['turns'].values():
        for row in rows:
            checked.append(dict(row,raw_text=row['checked_text']))
    parsed=parser.parse_sequence(checked,deepcopy(context),args.battle_id)
    video_messages=[v for v in observations if v.get('message',{}).get('confidence',0)>=.8 and
                    v['message']['raw_text'].strip()]
    bounds={1:(94,176.28),2:(176.28,248.4),3:(248.4,290.43),4:(290.43,356.54),
            5:(356.54,444.59),6:(444.59,504.7),7:(504.7,608.82),8:(608.82,690.55)}
    decision_frames={1:94,2:176,3:250,4:302,5:356,6:446,7:504,8:608}
    resolution_frames={1:132,2:200,3:260,4:316,5:394,6:472,7:530,8:652}
    events=[];alignment=[];instances={}
    for pid,p in initial['pokemon'].items():instances[(p['side_id'],p['species']['value']['species_id'])]=pid
    def side_for(actor, fallback='unknown'):
        if not actor:return fallback
        sides={side for side,sid in instances if sid==actor['species_id']}
        return next(iter(sides)) if len(sides)==1 else fallback
    def bind(e):
        actor=e.get('actor');side=e['side']
        if not actor or side not in {'self','opponent'}:return
        key=(side,actor['species_id'])
        if key in instances:e['attributes']['actor_instance_id']=instances[key]
        elif e['event_type']=='send_out':
            instances[key]=f'{args.battle_id}:{side}:encounter:'+hashlib.sha256(e['event_id'].encode()).hexdigest()[:16]
    def synthetic(kind,turn,text,source,side='field',actor=None,attrs=None,refs=None,suffix=''):
        frame=evidence_frame(source)
        e={'event_id':stable_id(args.battle_id,f'{kind}:{turn}:{source["source_id"]}:{suffix}'),
           'event_type':kind,'side':side,'actor':actor,'target':None,'original_text':text,'canonical_references':refs or {},
           'log_order':None,'evidence':[{'source_type':'manual_video_annotation','source_id':source['source_id'],
               'observation_ids':[source['source_id']],'details':dict(frame,turn=turn)}],
           'ocr_confidence':None,'parsing_confidence':'supported','uncertainty':[],
           'attributes':dict(attrs or {},annotation_method='manual video observation / explicit reconciliation'),
           'status':'confirmed','associated_video_evidence':[]}
        bind(e);return e
    def near(t):return min(observations,key=lambda v:abs(v['timestamp']-t))
    for turn in range(1,9):
        start,end=bounds[turn]
        events.append(synthetic('turn_boundary',turn,f'回合 {turn} 开始（按动作序列与日志标题校对）',near(start),
                                attrs={'turn':turn,'boundary':'start','action_coverage_complete':turn<8}))
        events.append(synthetic('phase_observation',turn,'决策机会：已观察到指令界面',near(decision_frames[turn]),attrs={'phase':'decision'}))
        if turn==1:
            # Move menus reveal moves/PP; they never count as execution.
            menu=read(args.cache/'m223-snapshots/102.json');source=near(menu['timestamp'])
            for move in menu['moves']:
                ref=parser.identity(move['name']['value'],'move')
                events.append(synthetic('move_observation',turn,'招式菜单观察：'+move['name']['raw_text'],source,'self',
                    parser.identity('雪妖女','species'),{'move_slot':move['slot'],'pp':move['pp']['value']},{'move':ref},str(move['slot'])))
            events.append(synthetic('ability_change',turn,'状态菜单：雪妖女的咒术之躯',near(106),'self',
                                   parser.identity('雪妖女','species'),refs={'ability':parser.identity('咒术之躯','ability')}))
            events.append(synthetic('type_change',turn,'状态菜单：雪妖女为冰／幽灵属性',near(106),'self',
                                   parser.identity('雪妖女','species'),{'types':['ice','ghost']}))
        if turn==5:
            source=near(384);actor=parser.identity('铝钢桥龙','species')
            for name,value in {'attack':-1,'defense':1,'special_attack':2,'special_defense':0,'speed':0,'accuracy':0,'evasion':0}.items():
                events.append(synthetic('stat_change',turn,f'状态面板观察：铝钢桥龙 {name} {value}',source,'self',actor,
                                        {'stats':[name],'change':'replace','value':value},suffix=name))
            events.append(synthetic('type_change',turn,'状态面板：铝钢桥龙为钢／龙属性',source,'self',actor,{'types':['steel','dragon']}))
            events.append(synthetic('item_change',turn,'状态面板：铝钢桥龙持有吃剩的东西',source,'self',actor,
                                    {'change':'reveal'},{'item':parser.identity('吃剩的东西','item')}))
        if turn in {5,7,8}:
            source=near({5:384,7:510,8:636}[turn])
            # Remaining counts are visible in status UI. End timing is verified
            # by the later UI counts and the logged expiration, not a guessed
            # five-turn game default or an inferred held-item modifier.
            weather,remaining={5:('rain',2),7:('snow',3),8:('rain',4)}[turn]
            events.append(synthetic('weather_change',turn,f'状态面板：{weather} 剩余 {remaining}/5',source,
                                    attrs={'weather':weather,'change':'observe','duration':{'remaining':remaining,'timing':'turn_end'}}))
            veil={5:1,7:4,8:3}[turn]
            events.append(synthetic('side_condition_change',turn,f'状态面板：极光幕剩余 {veil}/5',source,'self',
                                    attrs={'condition':'aurora_veil','change':'observe','duration':{'remaining':veil,'timing':'turn_end'}}))
            if turn<8:
                grass={5:3,7:1}[turn]
                events.append(synthetic('terrain_change',turn,f'状态面板：青草场地剩余 {grass}/5',source,
                                        attrs={'terrain':'grassy','change':'observe','duration':{'remaining':grass,'timing':'turn_end'}}))
            if turn==7:
                actor=parser.identity('铝钢桥龙','species')
                events.append(synthetic('stat_change',turn,'状态面板：铝钢桥龙防御 +2',source,'self',actor,
                                        {'stats':['defense'],'change':'replace','value':2}))
                events.append(synthetic('item_change',turn,'状态面板：铝钢桥龙持有吃剩的东西',source,'self',actor,
                                        {'change':'reveal'},{'item':parser.identity('吃剩的东西','item')}))
            if turn==8:
                actor=parser.identity('雪妖女','species')
                events.append(synthetic('stat_change',turn,'状态面板：雪妖女所有阶级均为 0',source,'self',actor,
                                        {'stats':['attack','defense','special_attack','special_defense','speed','accuracy','evasion'],
                                         'change':'replace','value':0}))
                events.append(synthetic('type_change',turn,'状态面板：超级雪妖女为冰／幽灵属性',source,'self',actor,
                                        {'types':['ice','ghost']}))
        pending={}
        for row,parsed_event in zip(checked,parsed):
            if row['turn']!=turn:continue
            if row['log_order']==(3 if turn==1 else 1):
                events.append(synthetic('phase_observation',turn,'对战结算：已观察到动作或效果播报',near(resolution_frames[turn]),
                                        attrs={'phase':'battle_resolution'}))
            original=next(a for a in annotations['turns'][str(turn)] if a['entry_id']==row['entry_id'])
            e=parsed_event.to_dict();source=by_image[row['image']];frame=evidence_frame(source)
            e['evidence'][0]['details'].update(frame,log_order=row['log_order'],raw_ocr_text=original['raw_text'],
                 annotation_method=original['annotation_basis'],checked_text=row['checked_text'],text_corrected=compact(original['raw_text'])!=compact(row['checked_text']))
            e['evidence'].append({'source_type':'manual_log_annotation','source_id':row['source_id'],
                                 'observation_ids':row['observation_ids'],'details':{'turn':turn,'annotation_file':historical_reference(args.annotations)}})
            e['status']='confirmed'
            if turn==1 and row['log_order']<=3:
                e['event_type']='move_effect';e['attributes']['effect']='initial_send_out_reaffirmation' if row['log_order']<=2 else 'mega_evolution_preparation'
            elif '进化石和' in row['raw_text']:
                e['event_type']='move_effect';e['attributes']['effect']='mega_evolution_preparation'
            if e['side']=='unknown' and e['actor']:
                e['side']=side_for(e['actor'])
                if e['side']=='unknown' and '对手' in row['raw_text']:e['side']='opponent'
                e['attributes']['side_basis'].append('manual video active-side reconciliation')
            if e['event_type']=='send_out':
                # The engine binds a send-out to the single observed vacancy;
                # replacements can occur on either side of the field.
                if row.get('slot'):e['attributes']['slot']=row['slot']
                if e['side']=='unknown':e['side']='opponent'
            if e['event_type']=='switch_out':
                e['attributes']['invalidate_unverified_persistence']=True
            if '用白色香草' in row['raw_text']:
                e['event_type']='stat_change';e['side']='opponent';e['attributes'].update(stats=['defense','special_defense'],change='reset')
            if e['event_type']=='unknown':
                e['event_type']='move_effect';e['attributes']['effect']='unresolved_log_observation'
            # Explicit two-actor stat message applies once to each named owner.
            expanded=[e]
            if e['event_type']=='stat_change' and '轰擂金刚猩和铝钢桥龙' in row['raw_text']:
                expanded=[]
                for name in ['轰擂金刚猩','铝钢桥龙']:
                    child=deepcopy(e);child['event_id']=e['event_id']+':'+str(parser.identity(name,'species')['species_id'])
                    child['actor']=parser.identity(name,'species');child['side']='self';expanded.append(child)
            for child in expanded:
                bind(child)
                if child['event_type']=='move_execution' and child['canonical_references'].get('move',{}).get('canonical_id')=='pokeapi:move:182':
                    pending[child['attributes'].get('actor_instance_id')]=child['event_id']
                elif child['event_type']=='move_effect' and child['attributes'].get('effect')=='protection_established':
                    attempt=pending.get(child['attributes'].get('actor_instance_id'))
                    if attempt:child['event_type']='protection_outcome';child['attributes'].update(attempt_event_id=attempt,outcome='success')
                candidates=[v for v in video_messages if start<=v['timestamp']<end]
                matches=[]
                for v in candidates:
                    score=SequenceMatcher(None,compact(row['raw_text']),compact(v['message']['raw_text'])).ratio()
                    if score>=.73:matches.append((score,v))
                if matches:
                    _,best=max(matches,key=lambda pair:pair[0]);child['associated_video_evidence']=[dict(evidence_frame(best),
                       raw_text=best['message']['raw_text'],ocr_confidence=best['message']['confidence'],association='manual-turn-bounded text alignment; not exact onset')]
                alignment.append({'event_id':child['event_id'],'turn':turn,'log_order':row['log_order'],
                                  'category':'video_text_match_candidate' if matches else 'log_only_or_ambiguous_video',
                                  'manual_annotation':True})
                events.append(child)
            if turn==6 and e['event_type']=='send_out':
                roster=[pid for (side,sid),pid in instances.items() if side=='opponent']
                events.append(synthetic('party_observation',turn,'四只对手出战宝可梦均已分别观察到',source,'opponent',
                                        attrs={'selected_instance_ids':roster,'complete':True}))
        if turn in {4,6}:
            # Logs omit these entrants' initial HP. Establish it from an actual
            # HUD reading, not from a full-health-on-send-out assumption.
            t,name={4:(356,'暴飞龙'),6:(504,'轰擂金刚猩')}[turn]
            observation=read(args.cache/f'm223-snapshots/{t}.json')
            hp=next(p['hp']['value'] for p in observation['pokemon'] if p['slot']=='opponent_active_1')
            e=synthetic('hp_change',turn,f'视频 HUD：对手{name} 显示 {hp}%',near(t),'opponent',
                        parser.identity(name,'species'),{'after':hp,'unit':'displayed_percent','observation_kind':'settled_display'})
            events.append(e);alignment.append({'event_id':e['event_id'],'turn':turn,'category':'video_only_HP_observation','manual_annotation':True})
        if turn==8:
            events.append(synthetic('phase_observation',turn,'对战结算：已观察到动作播报',near(resolution_frames[turn]),
                                    attrs={'phase':'battle_resolution'}))
            # No log was opened for this turn. These are independently visible
            # messages; menus and animation frames cannot create move events.
            selected=[(652.03,'move_execution','opponent','暴飞龙','对手的Sally使出了守住！',{'move':parser.identity('守住','move')},{}),
                      (655.53,'protection_outcome','opponent','暴飞龙','对手的Sally摆出了防守的架势！',{},{}),
                      (657.53,'move_execution','self','铝钢桥龙','铝钢桥龙使出了守住！',{'move':parser.identity('守住','move')},{}),
                      (660.53,'protection_outcome','self','铝钢桥龙','铝钢桥龙摆出了防守的架势！',{},{}),
                      (664.53,'move_execution','self','雪妖女','雪妖女使出了暴风雪！',{'move':parser.identity('暴风雪','move')},{}),
                      (666.53,'move_effect','opponent','暴飞龙','对手的Sally在攻击中守护住了自己！',{}, {'effect':'protected_from_attack'}),
                      (673.53,'effectiveness','opponent','轰擂金刚猩','对对手的轰擂金刚猩效果绝佳！',{}, {'effect':'super_effective'}),
                      (675.03,'faint','opponent','轰擂金刚猩','对手的轰擂金刚猩倒下了！',{},{}),
                      (686.1,'move_effect','field',None,'有一方选择了投降。',{}, {'effect':'forfeit_announcement'}),
                      (687.6,'phase_observation','field',None,'战胜了 willbnguyn！',{}, {'phase':'battle_end','outcome':'self_win_by_opponent_forfeit'})]
            for t,kind,side,name,text,refs,attrs in selected:
                source=near(t);actor=parser.identity(name,'species') if name else None
                e=synthetic(kind,turn,text,source,side,actor,attrs,refs)
                pid=e['attributes'].get('actor_instance_id')
                if kind=='move_execution' and refs.get('move',{}).get('canonical_id')=='pokeapi:move:182':pending[pid]=e['event_id']
                if kind=='protection_outcome':e['attributes'].update(attempt_event_id=pending[pid],outcome='success')
                events.append(e);alignment.append({'event_id':e['event_id'],'turn':turn,'category':'video_only','manual_annotation':True})
        if turn<8:
            events.append(synthetic('turn_boundary',turn,f'回合 {turn} 结束（后续决策界面佐证）',near(end),
                                    attrs={'turn':turn,'boundary':'end','action_coverage_complete':True}))
    save(args.output.parent/'M2.2.3-reconciled-events.json',{'schema_version':1,'event_candidates':events,'alignment':alignment,
         'method':'human-assisted checked log ordering, explicit nickname binding and video-only observations; evidence-only mechanics'})
    engine,snapshots=replay(initial,events)
    envelope=engine.to_dict()
    save(args.output.parent/'M2.2.3-battle-state.json',envelope)
    save(args.output.parent/'M2.2.3-state-snapshots.json',{'schema_version':2,'snapshots':snapshots})
    timeline=build_timeline(envelope['history'],envelope['initial_state'],snapshots,envelope['state'])
    timeline['mechanic_rules']=engine.mechanic_rules.to_dict()
    timeline['notes'].append('M2.2.3: human-assisted reconstruction; source timestamps are observation times, not exact action onsets.')
    args.output.write_text(render_html(timeline,artifact_root='../../../'))
    save(args.output.parent/'M2.2.3-validation-metrics.json',{'video_metadata':read(args.cache/'m223-survey/frames.json')['video_metadata'],
        'survey_frames':len(read(args.cache/'m223-survey/frames.json')['frames']), 'log_views':len(views),
        'automatic_entries':len(entries),'checked_entries':len(checked),'assembly_issues':Counter(i['reason'] for i in issues),
        'entries_by_turn':Counter(e['turn'] for e in checked),'alignment_categories':Counter(a['category'] for a in alignment),
        'event_count':len(events),'application_statuses':Counter(r.application_status for r in engine.history),
        'transition_categories':Counter(e['classification'] for e in timeline['entries'][1:]),
        'final_hash':hash_state(engine.state),'conflicts':engine.state.conflicts,
        'deferred':[{'event':r.event['original_text'],'reason':r.reason} for r in engine.history if r.application_status=='deferred'],
        'automatic_unresolved':Counter(u for e in automatic for u in e.uncertainty),
        'deterministic_replay':True,'duplicate_delivery_idempotent':True})
    print(len(events),'events;',Counter(r.application_status for r in engine.history),flush=True)
    for r in engine.history:
        if r.application_status in {'deferred','rejected'}:print(r.application_status,r.event['original_text'],r.reason,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',type=Path,default=None)
    p.add_argument('--initial',type=Path,default=None)
    p.add_argument('--annotations',type=Path,default=None)
    p.add_argument('--output',type=Path,default=None)
    add_arguments(p)
    args=p.parse_args();args.paths=BattleArtifacts.select(args.battle_id,args.video,default='sample_battle_3').prepare();args.battle_id=args.paths.battle_id
    args.cache=args.cache or args.paths.cache_dir
    args.initial=args.initial or args.paths.input('m223_initial_context.json')
    args.annotations=args.annotations or args.paths.input('m223_annotations.json')
    args.output=args.paths.guard_output(args.output or args.paths.report('M2.2.3-full-battle-timeline.html'))
    build(args)


if __name__=='__main__':main()
