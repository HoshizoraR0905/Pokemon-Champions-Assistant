"""M2.3.8-S saved-only repair replay. Each stage preserves completed outputs."""
import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import html
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json
from recognition.event_report import video_events,verify_seal
from recognition.message_occurrences import MessageOccurrences
from recognition.visual_evidence import parse_popup
from scripts.replay_trainer_opening import replay,forbidden

BATTLE='sample_battle_6'
RUN='m238-scrolling-semantics-v4'
TITLE='M2.3.8-S-scrolling-semantics-v4'
SOURCES=['recognition/fast_video.py','battle_events/parser.py','recognition/message_occurrences.py','recognition/visual_evidence.py',
         'recognition/event_report.py','tracking/evidence_fusion.py','tracking/state_engine.py']
CASES=[('Intimidate and two Attack drops',130.505,130.505),('Light Screen effect',176.513,176.513),
 ('First scrolling dual drop',192.032,193.032),('Life Orb banner and HP loss',228.505,230.505),
 ('Second scrolling dual drop',239.007,240.507),('Opponent withdrawal',247.508,247.508),
 ('Named effectiveness receiver',271.012,271.012),('Opponent Mega reaction',319.003,319.003),
 ('Opponent completed Mega',328.505,328.505),('Self withdrawal',335.507,335.507),
 ('Self Mega reaction',439.507,439.507),('Self completed Mega',449.008,449.008),
 ('Self Protect grouping',456.010,456.010),('Tailwind',465.012,465.012),('Opponent faint grouping',527.022,527.022)]
CAUSES={
 'scrolling':'MessageOccurrences parsed each two-row frame independently; no suffix/prefix reconstruction, so the first named recipient vanished.',
 'multi_target':'EventParser kept species_mentions()[0]; parse_many now splits complete named recipients and rebinds each child independently.',
 'ability_order':'The explicit target-side grammar was absent, so Attack drop failed side_unknown before/after the same-time banner; the drops now do not depend on the ability receipt.',
 'screen':'Generic 提高了 stat parsing consumed Light Screen wording; use the existing side condition with change=observe to preserve its activation clock.',
 'item':'parse_popup queried the legacy second-row key only as ability; exact two-configuration consensus now distinguishes item and ability.',
 'withdrawal':'要回到…的身边了 was absent from switch-out grammar.',
 'effectiveness':'starts-with 对手 missed 对对手的; now record named target and target_side without requiring an attacker.',
 'occurrence':'Fuzzy text similarity swallowed recognized semantic type/side/actor changes after emission.',
 'mega':'Reaction vocabulary accepted X/Y suffix but not the observed Z suffix; notice remains a non-mutating move_effect. Raw 全一环 is preserved, not silently corrected.',
 'hp':'Qualitative 削减 wording was absent; record a bound HP-loss observation with unknown numbers and cause.',
 'stale_hud':'prepare_message previously let a failed prebattle HUD block a later explicit active send-out; a provenance-backed later entry now supersedes only the older HUD failure.',
 'self_actor':'Literal live actor grammar is checked before side-owned alias substitution; opponent aliases no longer suppress a self actor. Only complete supported actor grammar in an explicit battle_message region supplies default self side. Fragments and ability/item banners do not.'}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):return json.loads(Path(path).read_text())


def paths():
    owner=BattleArtifacts(BATTLE,ROOT)
    return owner,owner.cache('event-driven/'+RUN)


def protected_inputs(owner):
    result={}
    for run in ('m238-live-1','m238-live-2','m238-live-3-diagnostic','m238-opponent-binding-v1','m238-trainer-opening-v3'):
        folder=owner.cache('event-driven/'+run)
        for name in ('observations.json','video-only.json','video-only-seal.json','events.json','replay.json','prediction.json','prediction-seal.json','manifest.json','trainers.json'):
            path=folder/name
            if path.exists():result[str(path.relative_to(ROOT))]=sha(path)
    for pattern in ('M2.3.7*.md','M2.3.8*.md','M2.3.8*.json','M2.3.8*.html'):
        for path in (ROOT/'reports').glob(pattern):
            if not path.name.startswith(TITLE):result[str(path.relative_to(ROOT))]=sha(path)
    return result


def prepare(folder,owner):
    source=owner.cache('event-driven/m238-live-3-diagnostic');verify_seal(source)
    data=read(source/'observations.json');rows=deepcopy(data['observations'])
    header=read(owner.cache('event-driven/m238-trainer-opening-v3/trainers.json'))
    frame=next(r for r in rows if r['source_id']==header['frame']['source_id'])
    frame['trainer_observations']=header['trainer_observations']
    groups=MessageOccurrences(BATTLE,source_occurrence_ids=True)
    for r in rows:
        for v in r.get('visual',{}).get('parsed',[]):
            if v.get('kind')=='popup':
                # Reinterpret saved strings only: no image loading or acquisition.
                v.update(parse_popup(v.get('readings',{})))
        result=groups.observe(r)
        r['occurrence_decision']=dict(events=result['events'],reason=result['reason'],
                                      occurrence_id=(result.get('occurrence') or {}).get('id'))
    events=video_events(rows,data['roster'],BATTLE)
    # Retain temporal context for withdrawals; this asserts no move target/cause.
    previous=[]
    for e in events:
        if e['event_type']=='switch_out' and e.get('actor'):
            candidates=[m for m in previous if m.get('actor') and m['actor']['canonical_id']==e['actor']['canonical_id']
                and m['side']==e['side'] and 0<=e['attributes']['observation_time']-m['attributes']['observation_time']<=6]
            if candidates:
                m=candidates[-1];e['attributes']['preceding_move_context']=dict(event_id=m['event_id'],
                    timestamp=m['attributes']['observation_time'],move=m['canonical_references'].get('move'),
                    causal_assertion=False,target=None)
        if e['event_type']=='move_execution':previous.append(e)
    for i,e in enumerate(events,1):e['attributes']['sequence']=i
    atomic_json(folder/'observations.json',dict(data,observations=rows,occurrences=groups.groups))
    atomic_json(folder/'events.json',dict(battle_id=BATTLE,events=events))
    return dict(observations=len(rows),events=len(events),occurrences=len(groups.groups),ocr_calls=0,icon_calls=0,decoded_frames=0)


def brief(h):
    e=h['bindings'].get('resolved_event',h['event'])
    return dict(id=e['event_id'],timestamp=e['attributes']['observation_time'],kind=e['event_type'],
        raw=e['original_text'],logical_message=e['attributes'].get('reconstructed_logical_message',e['original_text']),
        side=e['side'],actor=e.get('actor'),target=e.get('target'),attributes=e['attributes'],
        bindings=h['bindings'],receipt=h['application_status'],reason=h['reason'],uncertainty=e['uncertainty'],evidence=e['evidence'])


def classify_remaining(rows,history,manual_review=None):
    by_source={}
    for h in history:
        if h['event']['event_type'] in {'hud_observation','preview_observation','trainer_observation','entry_observation'}:continue
        for proof in h['event']['evidence']:by_source.setdefault(proof['source_id'],[]).append(h)
    reviewed={r['source_id']:r for r in (manual_review or {}).get('observations',[])}
    output=[]
    for r in rows:
        m=r['message'];raw=m.get('raw_text','')
        if not raw.strip():continue
        records=by_source.get(r['source_id'],[])
        emitted=r['occurrence_decision']['events']
        if any(h['application_status'] in {'applied_candidate','applied_confirmed','recorded_observation','applied_partial'} for h in records):
            category='admitted_or_recorded'
            if any(h['application_status'] in {'deferred','rejected'} for h in records):category='partly_admitted_missing_binding'
        elif any(h['application_status']=='deferred' for h in records):category='parsed_lacking_identity_or_target_evidence'
        elif any(h['application_status']=='rejected' for h in records):category='state_consistency_rejection'
        elif r['ui'].get('phase') in {'team_preview','team_selection','loading','title_screen'} or r['timestamp']<min(
            (h['event']['attributes']['observation_time'] for h in history if h['event']['event_type']=='send_out'),default=0):
            category='prebattle_or_menu_irrelevant'
        elif m.get('source_region_type')!='battle_message' or not m.get('selected'):category='ui_routing_or_visibility'
        elif m.get('confidence',0)<.75:category='genuine_ocr_error_or_noise'
        elif r['occurrence_decision'].get('occurrence_id'):
            group_id=r['occurrence_decision']['occurrence_id']
            admitted=[h for h in history if h['event']['attributes'].get('occurrence_id')==group_id]
            category='duplicate_or_supporting_reading' if admitted else ('incomplete_or_scrolling_fragment' if raw.rstrip().endswith(('的','和','出')) else 'unsupported_meaningful_wording_or_uncertain_fragment')
        else:category='ui_routing_or_occurrence_failure'
        if r['source_id'] in reviewed and not records:category=reviewed[r['source_id']]['category']
        output.append(dict(agent_visual_review=reviewed.get(r['source_id']),timestamp=r['timestamp'],source_id=r['source_id'],raw=raw,category=category,
            emitted_ids=[e['event_id'] for e in emitted],receipts=[dict(status=h['application_status'],reason=h['reason']) for h in records],
            image=os.path.relpath(ROOT/r['image'],ROOT/'reports')))
    return output


def semantic_checks(new):
    violations=[];bound=0
    pokemon=new['state']['pokemon']
    for h in new['history']:
        e=h['bindings'].get('resolved_event',h['event']);t=e['attributes']['observation_time']
        for p in e['evidence']:
            if p.get('details',{}).get('timestamp',t)>t:violations.append(dict(id=e['event_id'],issue='future_source'))
        pid=h['bindings'].get('actor',{}).get('pokemon_instance_id')
        if pid and h['application_status'] in {'applied_candidate','applied_confirmed','applied_partial','recorded_observation'}:
            bound+=1;mon=pokemon.get(pid)
            if not mon or mon['side_id']!=e['side']:violations.append(dict(id=e['event_id'],issue='instance_side_mismatch'))
            if mon and e.get('actor') and e['actor'].get('species_id') and mon['species']['value'].get('species_id')!=e['actor']['species_id']:
                violations.append(dict(id=e['event_id'],issue='instance_species_mismatch'))
    counts=Counter(t['mechanic'] for p in pokemon.values() for t in p.get('transformations',[]))
    result=dict(bound_admissions_checked=bound,violations=violations,completed_transformations=dict(counts),
        independently_measured_identity_accuracy=None,unsupported_identity_claim='Negative tests and binding invariants checked; no independent full-match accuracy claim')
    assert not violations,result
    return result


def report(folder,owner,manifest):
    old=read(owner.cache('event-driven/m238-trainer-opening-v3/replay.json'))
    new=read(folder/'replay.json');saved=read(folder/'observations.json');rows=saved['observations']
    cases=[]
    for label,start,end in CASES:
        within=lambda t:start-.04<=t<=end+.04
        readings=[]
        for r in rows:
            if within(r['timestamp']):
                readings.append(dict(timestamp=r['timestamp'],raw=r['message'].get('raw_text',''),
                    rows=r['message'].get('rows',[]),banners=r.get('visual',{}).get('readings',{}),
                    image=os.path.relpath(ROOT/r['image'],ROOT/'reports'),source_id=r['source_id']))
        before=[brief(h) for h in old['history'] if within(h['event']['attributes']['observation_time']) and h['event']['event_type']!='hud_observation']
        after=[brief(h) for h in new['history'] if within(h['event']['attributes']['observation_time']) and h['event']['event_type']!='hud_observation']
        unresolved=[h for h in after if h['receipt'] in {'deferred','rejected','applied_partial'}]
        cases.append(dict(label=label,start=start,end=end,readings=readings,before=before,after=after,
            assessment='observed_semantics_admitted_or_recorded' if after and not unresolved else 'partly_resolved_with_explicit_gaps',
            remaining=[dict(kind=h['kind'],side=h['side'],reason=h['reason'],uncertainty=h['uncertainty']) for h in unresolved]))
    manual_review=read(folder/'manual-review.json') if (folder/'manual-review.json').exists() else {}
    classified=classify_remaining(rows,new['history'],manual_review)
    by_receipt=lambda history:dict(Counter(h['application_status'] for h in history))
    by_cause=lambda history:dict(Counter(h['reason'] for h in history if h['application_status']=='deferred'))
    report_sources=['scripts/replay_m238s.py','scripts/templates/m238s_review.html','scripts/verify_m238s_review.cjs','tests/test_scrolling_semantics.py']
    for name in report_sources:
        target=folder/'source'/'report-final'/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write((ROOT/name).read_bytes())
    data=dict(report_sources={n:sha(ROOT/n) for n in report_sources},schema=RUN,battle_id=BATTLE,baseline='m238-trainer-opening-v3',
        status='saved_observation_diagnostic_not_independent_semantic_acceptance',
        counts=dict(saved_frames=len(rows),before_events=len(old['history']),after_events=len(new['history']),
            before_receipts=by_receipt(old['history']),after_receipts=by_receipt(new['history']),
            before_deferred_causes=by_cause(old['history']),after_deferred_causes=by_cause(new['history']),
            message_observation_categories=dict(Counter(r['category'] for r in classified)),
            move_receipts=dict(Counter(h['application_status'] for h in new['history'] if h['event']['event_type']=='move_execution'))),
        causal_paths=CAUSES,cases=cases,remaining_message_observations=classified,agent_visual_review=manual_review,
        timeline=[brief(h) for h in new['history'] if h['event']['event_type'] not in {'hud_observation','preview_observation','entry_observation'}],
        first_slots=new.get('first_slot_establishment'),tests=read(folder/'tests.json') if (folder/'tests.json').exists() else None,
        binding_validation=semantic_checks(new),replay_reused_from=manifest.get('replay_reused_from'),
        preservation=dict(checked_files=len(manifest['protected']),unchanged=all(sha(ROOT/p)==v for p,v in manifest['protected'].items())),
        limitations=['No recognition, decoding, or new frames; all timestamps refer to saved observations.',
            'Agent visual diagnosis of the saved 448.508s PNG identifies 成了→成子 OCR error; classification only, never replay input or independent human ground truth.',
            'Stat direction is directly observed. Stage magnitude remains unknown; no mechanic amount is imported.',
            'Intimidate and Snarl are chronological context; no causal stat mutations are inferred from banners/moves.',
            'Life Orb is a direct item revelation; qualitative HP loss has unknown numbers and unknown cause.',
            'Raw 全一环 and Z remain OCR strings; notices do not assert a new stone identity or a completed transformation.',
            'No independently verified whole-match game-turn reference exists; frozen Battle Log extraction is unchanged.'])
    assert data['preservation']['unchanged']
    prefix=ROOT/'reports'/TITLE
    with Path(str(prefix)+'.json').open('x') as stream:json.dump(data,stream,ensure_ascii=False,indent=2)
    template=(ROOT/'scripts/templates/m238s_review.html').read_text()
    document=template.replace('__TITLE__',TITLE).replace('__DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c'))
    with Path(str(prefix)+'.html').open('x') as stream:stream.write(document)
    lines=['# M2.3.8-S：滚动消息、道具横幅与事件语义','',
        '诊断输入：已保存的 sealed v3 观测；比较基线：`m238-trainer-opening-v3`。未解码、未执行 OCR / 图标识别。',
        '',f'[离线 HTML]({TITLE}.html) · [完整 JSON]({TITLE}.json) · 新命名空间 `{folder.relative_to(ROOT)}`。',
        '', '## 已核实计数','', '```json',json.dumps(data['counts'],ensure_ascii=False,indent=2),'```','',
        '## 指定时间的前后对照','', '| 视频时间（秒） | 案例 / 原始读数 | 完整逻辑消息 | 修复前 | 修复后 | 仍缺失 |','|---|---|---|---|---|---|']
    for c in cases:
        describe=lambda values:'; '.join(f"{h['kind']} / {h['side']} / {(h.get('actor') or h.get('target') or {}).get('name','—')}: {h['receipt']} ({h['reason'] or '—'})" for h in values) or '未生成事件'
        raw=' / '.join(dict.fromkeys(r['raw'].replace('\n',' ') for r in c['readings'] if r['raw']))
        logical=' / '.join(dict.fromkeys(h['logical_message'].replace('\n',' ') for h in c['after']))
        lines.append(f"| {c['start']:.3f}–{c['end']:.3f} | {c['label']}：{raw} | {logical} | {describe(c['before'])} | {describe(c['after'])} | "+('; '.join(str(x['reason']) for x in c['remaining']) or '无该事件的入场缺口；仍为候选/观测')+' |')
    lines+=['','## 具体原因与修正','']+[f'- **{k}**：{v}' for k,v in CAUSES.items()]
    lines+=['','## 修改入口','',
        '- `battle_events/parser.py`：完整 live actor 语法、先限定阵营再查询昵称、多个接收者与指定措辞。',
        '- `recognition/message_occurrences.py`：精确行重叠、语义变更分组、保留逐帧证据与完成时间。',
        '- `recognition/visual_evidence.py` / `recognition/event_report.py`：同一横幅第二行分别查证特性与道具；不按屏幕边缘猜阵营。',
        '- `tracking/evidence_fusion.py`：按 prefix 重新绑定；显式新入场覆盖更早的失败 HUD。',
        '- `tracking/state_engine.py`：定性 HP 削减记录为观察，不改写数值、不假定反伤原因。',
        '- `recognition/fast_video.py`：部分可见帧传入分组器，阻止跨不连续显示拼接；不改动识别调用。',
        '- `scripts/replay_m238s.py`、`scripts/templates/m238s_review.html`、`scripts/verify_m238s_review.cjs`、`tests/test_scrolling_semantics.py`：保存数据诊断、离线审阅与回归。']
    lines+=['','## 验证与限制','',json.dumps(data['tests'],ensure_ascii=False),'',
        '绑定一致性检查：'+json.dumps(data['binding_validation'],ensure_ascii=False),'',
        '回放复用记录：'+json.dumps(data['replay_reused_from'],ensure_ascii=False),'',
        f"原有 {len(manifest['protected'])} 个检查文件 SHA-256 保持不变。无提交、无推送；旧报告、预测、注释未改写。",'']
    lines += ['- '+s for s in data['limitations']]
    lines+=['','## 精确命令','', '```sh',
        'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/replay_m238s.py --stage prepare',
        'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/replay_m238s.py --stage replay',
        'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/replay_m238s.py --stage report','```','',
        '```sh',data['tests']['command'] if data['tests'] else 'tests pending','```','',
        '测试命令及结果保存于新命名空间 `tests.json` / `tests.log`。报告的 canonical events、逐帧原始行、绑定依据、回执均可在 HTML 展开；未入场观察按类别单列。','',
        '仅报告生成完成不代表整场语义验收。至此停止，等待人工复核。','']
    with Path(str(prefix)+'.md').open('x') as stream:stream.write('\n'.join(lines))
    return data['counts']


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',required=True,choices=['prepare','replay','report'])
    args=parser.parse_args();owner,folder=paths();folder.mkdir(parents=True,exist_ok=True)
    identity={p:sha(ROOT/p) for p in SOURCES};mp=folder/'manifest.json'
    if mp.exists():
        manifest=read(mp)
        if manifest['sources']!=identity:raise ValueError('Runtime sources changed: preserve this run and use a new namespace')
        if args.stage in manifest['completed']:
            expected=[ROOT/'reports'/(TITLE+ext) for ext in ('.md','.json','.html')]
            if args.stage=='report' and not all(p.exists() for p in expected):
                manifest['report_path_recovery']=dict(reason='Path.with_suffix truncated dotted milestone name; original attempt preserved',
                    preserved_attempts=['reports/M2.3.md','reports/M2.3.json','reports/M2.3.html'])
                manifest['completed']=[s if s!='report' else 'report-misnamed-initial' for s in manifest['completed']]
            else:print('Completed stage reused:',args.stage);return
    else:
        manifest=dict(schema=RUN,battle_id=BATTLE,sources=identity,protected=protected_inputs(owner),completed=[],status='ready',
            ocr_calls=0,icon_calls=0,video_decoding=0)
        atomic_json(mp,manifest)
        for p in SOURCES:
            target=folder/'source'/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/p).read_bytes())
    manifest.update(status='running',stage=args.stage);atomic_json(mp,manifest)
    try:
        with ExitStack() as stack:
            for name in ['recognition.fast_video.CachedOCR.read','recognition.fast_video.CachedOCR.predict',
                         'recognition.fast_video.CachedIcons.identify','recognition.fast_video.decoded_frames','cv2.imread','cv2.VideoCapture']:
                stack.enter_context(patch(name,forbidden))
            if args.stage=='prepare':result=prepare(folder,owner)
            elif args.stage=='replay':
                if 'prepare' not in manifest['completed']:raise ValueError('prepare first')
                prior=owner.cache('event-driven/m238-scrolling-semantics-v2')
                prior_manifest=read(prior/'manifest.json') if (prior/'manifest.json').exists() else {}
                compatible=(prior_manifest.get('status') in {'ready','complete'} and 'replay' in prior_manifest.get('completed',[])
                    and sha(folder/'events.json')==sha(prior/'events.json')
                    and all(prior_manifest.get('sources',{}).get(n)==manifest['sources'][n] for n in
                        ['tracking/evidence_fusion.py','tracking/state_engine.py','battle_events/parser.py']))
                if compatible:
                    for name,value in read(prior/'seal.json')['files'].items():
                        if sha(prior/name)!=value:raise ValueError('Reuse source seal mismatch')
                    result=read(prior/'replay.json')
                    manifest['replay_reused_from']=dict(namespace=prior.name,events_sha256=sha(prior/'events.json'),
                        replay_sha256=sha(prior/'replay.json'),basis='Byte-identical events and unchanged state/parser implementation; only grouping punctuation dedup changed')
                else:result=replay(read(folder/'events.json')['events'],BATTLE,folder/'progress.json')
                atomic_json(folder/'replay.json',result)
                atomic_json(folder/'seal.json',dict(files={n:sha(folder/n) for n in ['observations.json','events.json','replay.json']}))
                result=dict(receipts=dict(Counter(h['application_status'] for h in result['history'])))
            else:
                if 'replay' not in manifest['completed']:raise ValueError('replay first')
                result=report(folder,owner,manifest)
        assert all(sha(ROOT/p)==v for p,v in manifest['protected'].items())
        manifest['completed'].append(args.stage);manifest.update(status='complete' if args.stage=='report' else 'ready',last_result=result)
        atomic_json(mp,manifest);print(json.dumps(result,ensure_ascii=False,indent=2))
    except BaseException as exc:
        manifest.update(status='failed',error=repr(exc));atomic_json(mp,manifest);raise


if __name__=='__main__':main()
