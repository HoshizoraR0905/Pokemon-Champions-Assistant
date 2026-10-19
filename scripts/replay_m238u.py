"""M2.3.8-U: saved-only Battle 6 occupancy persistence comparison.

Stages are explicit. Source/input hashes and protected checkpoints prevent silent
reuse after invalidation. Existing stage outputs are never overwritten.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import replay_m238t as prior
from scripts.replay_m238s import sha,read,brief
from recognition.video_sampling import atomic_json

OWNER=prior.OWNER
RUN='m238-active-persistence-v1'
TITLE='M2.3.8-U-active-persistence-v1'
FOLDER=OWNER.cache('event-driven/'+RUN)
BASE=OWNER.cache('event-driven/m238-switch-continuity-v2')
OBS=OWNER.cache('event-driven/m238-scrolling-semantics-v4/observations.json')
REPORT=OWNER.report(TITLE)
SOURCES=prior.SOURCES+['tracking/active_persistence.py','scripts/replay_m238t.py','scripts/replay_m238u.py',
    'scripts/templates/m238u_review.html','tests/test_active_persistence.py']
SLOTS=prior.SLOTS
ORANGE='last_known_identity_current_evidence_unresolved'


def orange_counts(timeline):
    return {k:dict(intervals=sum(r['status']==ORANGE and r['end']>r['start'] for r in rows),
        seconds=round(sum(r['end']-r['start'] for r in rows if r['status']==ORANGE),6)) for k,rows in timeline.items()}


def at(timeline,key,t):
    return next((r for r in reversed(timeline[key]) if r['start']<=t<=r['end']),{})


def visibility(row,key,active_species=None):
    side,slot=key.split(':')
    region=('own' if side=='self' else 'opponent')+'_active_'+('1' if slot=='left' else '2')
    ui=next((r for r in row.get('ui',{}).get('regions',[]) if r['region_id']==region),None)
    mon=next((p for p in row.get('snapshot',{}).get('pokemon',[]) if p['slot']==region),None)
    # This is the cached UI detector's assertion, not independent human truth.
    if not ui or ui.get('visibility')!='visible':
        return dict(status='hud_not_visible' if not ui or ui.get('visibility')=='not_visible' else 'hud_visibility_uncertain',region=region)
    from tracking.evidence_fusion import identity_evidence
    ref,status,reason=identity_evidence((mon or {}).get('species',{}),(mon or {}).get('icon',{}),reliability=True)
    category='hud_visible_ocr_unresolved'
    if status=='accepted':category='hud_visible_consistent' if active_species==ref['species_id'] else 'hud_visible_supported_other_identity'
    elif status=='conflicting':category='hud_visible_source_conflict'
    return dict(status=category,region=region,raw=(mon or {}).get('species',{}).get('raw_text'),
        confidence=(mon or {}).get('species',{}).get('confidence'),identity_policy=reason)


def compare(old,new,observations,baseline):
    end=observations[-1]['timestamp'];timeline=prior.intervals(new['slot_states'],end)
    before=baseline['timeline'];hist={h['event']['event_id']:h for h in old['history']}
    rows_by_time={r['timestamp']:r for r in observations};triggers=[]
    for key,rows in before.items():
        for r in rows:
            if r['status']!=ORANGE or r['end']<=r['start']:continue
            h=hist[r['event_id']];b=h['bindings'].get('hud',{});o=rows_by_time.get(r['start'],{})
            sample=at(timeline,key,r['start'])
            triggers.append(dict(slot=key,start=r['start'],end=r['end'],seconds=r['end']-r['start'],name=r.get('name'),
                event_id=r['event_id'],raw=b.get('raw'),confidence=b.get('confidence'),species_id=b.get('species_id'),
                icon_species_id=b.get('icon_species_id'),old_policy_status=b.get('status'),old_policy_reason=b.get('reason'),
                cached_visibility=visibility(o,key,r.get('species_id')),
                after_status=sample.get('status'),same_instance=sample.get('instance_id')==r.get('instance_id'),
                entry_evidence=r.get('evidence'),evidence=prior.evidence_links(h['event']),
                cause='latest_unadmitted_HUD_vetoed_supported_episode',
                policy_path='tracking/evidence_fusion.py::episode_hud -> prepare_message / scripts/replay_m238t.py::slot_snapshot'))
    changes=[]
    for h in new['history']:
        previous=hist[h['event']['event_id']]
        if (h['application_status'],h['reason'])!=(previous['application_status'],previous['reason']):
            changes.append(dict(timestamp=h['event']['attributes']['observation_time'],before=brief(previous),after=brief(h),evidence=prior.evidence_links(h['event'])))
    # Compare actual authoritative identities through every saved prefix, not just
    # colors or the final state. New admission must not move any active episode.
    differences=[]
    for change in old['slot_states']+new['slot_states']:
        for key in SLOTS:
            a,b=at(before,key,change['timestamp']),at(timeline,key,change['timestamp'])
            if a.get('instance_id')!=b.get('instance_id'):
                differences.append(dict(timestamp=change['timestamp'],slot=key,before=a.get('instance_id'),after=b.get('instance_id')))
    checks=prior.extended_checks(new)
    checks.update(occupancy_identity_differences=differences,events_unchanged=[h['event']['event_id'] for h in old['history']]==[h['event']['event_id'] for h in new['history']],
        previous_admissions_preserved=all(h['application_status'] in {'applied_candidate','applied_partial','applied_confirmed'} for h in new['history'] if hist[h['event']['event_id']]['application_status'] in {'applied_candidate','applied_partial','applied_confirmed'}),
        cached_entry_model_observations=sum(h['event']['attributes'].get('source_kind')=='entry_model' for h in old['history']),
        coverage_gaps=sum(o.get('kind')=='coverage_gap' for o in new['state']['observations']),
        unresolved_contradictions=new['state']['knowledge'].get('occupancy_uncertainty',{}))
    assert not differences and checks['events_unchanged'] and checks['previous_admissions_preserved']
    assert not checks['episode_violations']
    count=lambda rows:dict(Counter(h['application_status'] for h in rows))
    causes=lambda rows:dict(Counter(h['reason'] for h in rows if h['application_status']=='deferred'))
    visibility_changes=[];last={}
    for row in observations:
        for key in SLOTS:
            active=at(timeline,key,row['timestamp']);v=visibility(row,key,active.get('species_id'))
            if v!=last.get(key):
                visibility_changes.append(dict(timestamp=row['timestamp'],slot=key,**v,occupancy_status=active.get('status'),
                    image=os.path.relpath(ROOT/row['image'],REPORT.parent),source_id=row['source_id']))
                last[key]=v
    links={h['event']['event_id']:prior.evidence_links(h['event']) for h in new['history']}
    # Prior utility returns paths relative to reports/, this report lives under battles/<id>/.
    for proof in [p for rows in links.values() for p in rows]+[p for x in triggers+changes for p in x['evidence']]:
        proof['image']=os.path.relpath(ROOT/'reports'/proof['image'],REPORT.parent)
    return dict(schema=RUN,battle_id=OWNER.battle_id,timeline=timeline,before_timeline=before,triggers=triggers,changes=changes,
        visibility=visibility_changes,event_evidence=links,active_entry_episodes=new['state']['knowledge']['active_entry_episodes'],
        validation=checks,counts=dict(events=len(new['history']),observations=len(observations),before=count(old['history']),after=count(new['history']),
            before_deferred_causes=causes(old['history']),after_deferred_causes=causes(new['history']),
            before_orange=orange_counts(before),after_orange=orange_counts(timeline),
            before_moves=count([h for h in old['history'] if h['event']['event_type']=='move_execution']),
            after_moves=count([h for h in new['history'] if h['event']['event_type']=='move_execution'])),
        limits=['Saved UI visibility assertions can be wrong: 337.007s is an animation with no HUD; 487.015s is a detail/menu overlay misrouted as HUD (manually checked existing frames). No routing/recognition fix applied.',
            'No cached entry-model identities exist. New optional entry_model visual evidence is tested synthetically; no recognizer or model is introduced or invoked.',
            'Model evidence requires an explicit entry-event association, distinct preserved observation IDs, cached_entry_model provenance, timestamp and confidence >= .95. Agreement corroborates; disagreement retains message identity and gates continuity. Model position never assigns a slot.',
            'Weak/unreadable HUDs remain unadmitted; their HP is not applied. HUD absence is not a coverage gap. Real gap events and unplaced/ambiguous entries still gate continuity.',
            'Accepted contradictory HUD identities use existing observed-occupancy policy: no invented withdrawal, cause or action time; no past interval is rewritten.',
            'Fourteen entry episodes, including six unproven same-individual re-entry relations, remain unchanged. Species alone never merges history.',
            'All mutations remain candidates. Replay invariants and tests do not establish an independently measured false-admission rate.'])


def make_report(manifest):
    old=read(BASE/'replay.json');new=read(FOLDER/'replay.json');observations=read(OBS)['observations']
    baseline=read(ROOT/'reports/M2.3.8-T-switch-continuity-v2.json')
    data=compare(old,new,observations,baseline)
    data['tests']=read(FOLDER/'tests.json') if (FOLDER/'tests.json').exists() else None
    data['protected_files']=len(manifest['protected'])
    for ext in ('.json','.html','.md'):
        if Path(str(REPORT)+ext).exists():raise FileExistsError('Preserve report; use a new version')
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    with Path(str(REPORT)+'.json').open('x') as f:json.dump(data,f,ensure_ascii=False,indent=2)
    template=(ROOT/'scripts/templates/m238u_review.html').read_text()
    with Path(str(REPORT)+'.html').open('x') as f:f.write(template.replace('__DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')).replace('__TITLE__',TITLE))
    lines=['# M2.3.8-U：基于事件的活动槽位持续性','',f'[离线比较]({TITLE}.html) · [JSON]({TITLE}.json)','',
        '基线为 T v2 sealed replay。相同 1190 个事件；1306 个原有观察帧作为 UI 诊断来源。未运行解码、OCR、图标识别或新模型。','',
        '根因：`episode_hud` 将最新未获接纳的 HUD 身份当成既有活动 episode 的否决条件；`prepare_message` 据此丢弃活动对象上下文，T 时间线同时转橙。缺少新确认不等于存在反证。','',
        '本轮 `active_persistence_v1` 将占位不确定性与 HUD 接纳质量分开：空白、残缺、低置信度、不足以接纳的 HUD 不否定派出；可靠且矛盾的完整名字或高可信来源冲突保留独立门控，后续空白不清除矛盾。新可靠观察只从其时间点开始恢复。覆盖缺口和未定位入场仍阻断绑定。','',
        '337.007s 手工检查原图：动画空场，旧 UI 把非 HUD 区域标 visible 并读出 H；487.015s 原图是状态/队伍菜单，旧 HUD 路由误读 _；519.520s 招式动画没有 HUD，消息清楚显示大嘴鸥使用暴风。以上人工观察只用于解释，没有回填预测或改写识别。','',
        '派出消息可独立建立 entry 和可证实槽位，模型为可选佐证，HP/状态仍须自己的证据。已有缓存没有 entry-model 结果；合成测试覆盖一致、冲突、不独立、低置信度、未关联、未来入场证据。没有声称实测模型能力。','',
        'U-turn / Parting Shot / 强制换人招式的宣布不腾位；实际撤回和 faint 保留独立离场原因。离场空位持续至后续可靠替换；多空位不猜测。','',
        '## 核实计数','', '```json',json.dumps(data['counts'],ensure_ascii=False,indent=2),'```','',
        '## 逐段橙色起点','', '| 槽位 | 原视频区间 | 原始 HUD | 旧门控 | 新状态 |','|---|---|---|---|---|']
    for r in data['triggers']:
        image=r['evidence'][0]['image'] if r['evidence'] else ''
        lines.append(f"| {r['slot']} | [{r['start']:.3f}–{r['end']:.3f}s]({image}) | `{r['raw']!r}` / {r['confidence']} | {r['old_policy_reason']} | {r['after_status']} |")
    lines+=['','## 回执变化','']
    for r in data['changes']:lines.append(f"- {r['timestamp']:.3f}s `{r['after']['raw']}`：{r['before']['receipt']} → {r['after']['receipt']}；{r['before']['reason']}。")
    lines+=['','## 验证与限制','', '```json',json.dumps(data['validation'],ensure_ascii=False,indent=2),'```','']
    lines+=['- '+x for x in data['limits']]
    lines+=['',f"保护 {data['protected_files']} 个原有文件，按 SHA256 核验；事件文件与 T sealed input 完全相同。",'',
        '精确命令（已完成阶段复用；源码或输入哈希变化要求新 namespace）：','', '```sh',
        'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/replay_m238u.py --stage prepare',
        'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/replay_m238u.py --stage replay',
        'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/replay_m238u.py --stage report',
        data['tests']['command'] if data['tests'] else 'tests pending','```','',
        '浏览器验收和最后完整性检查见命名空间中的 completion.json；不提交、不推送。本轮到此停止。','']
    with Path(str(REPORT)+'.md').open('x') as f:f.write('\n'.join(lines))
    return data['counts']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',required=True,choices=['prepare','replay','report']);args=p.parse_args()
    inputs={str(p.relative_to(ROOT)):sha(p) for p in [BASE/'events.json',BASE/'replay.json',BASE/'seal.json',OBS,ROOT/'reports/M2.3.8-T-switch-continuity-v2.json']}
    sources={n:sha(ROOT/n) for n in SOURCES};FOLDER.mkdir(parents=True,exist_ok=True);mp=FOLDER/'manifest.json'
    if mp.exists():
        m=read(mp)
        if (m['sources'],m['inputs'])!=(sources,inputs):raise ValueError('Source/input changed: preserve checkpoint and use new namespace')
        if args.stage in m['completed']:print('Completed stage reused:',args.stage);return
    else:
        protected=prior.preserved()
        for folder in [BASE,OWNER.cache('event-driven/m238-switch-continuity-v1')]:
            for f in folder.glob('*.json'):protected[str(f.relative_to(ROOT))]=sha(f)
        m=dict(schema=RUN,battle_id=OWNER.battle_id,sources=sources,inputs=inputs,protected=protected,completed=[],status='ready',ocr_calls=0,icon_calls=0,decoded_frames=0,profile=dict(active_persistence_v1=True,active_continuity_v1=True,reliability_v1=True,reliability_v2=True,identity_v1=True))
        atomic_json(mp,m)
        for n in SOURCES:
            target=FOLDER/'source'/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/n).read_bytes())
    m.update(stage=args.stage,status='running');atomic_json(mp,m)
    try:
        with ExitStack() as stack:
            for name in ('recognition.fast_video.CachedOCR.read','recognition.fast_video.CachedOCR.predict','recognition.fast_video.CachedIcons.identify','recognition.fast_video.decoded_frames','cv2.imread','cv2.VideoCapture'):
                stack.enter_context(patch(name,prior.forbid))
            if args.stage=='prepare':
                assert all(sha(BASE/n)==v for n,v in read(BASE/'seal.json')['files'].items())
                if (FOLDER/'events.json').exists():raise FileExistsError('events already exist')
                with (FOLDER/'events.json').open('xb') as f:f.write((BASE/'events.json').read_bytes())
                result=dict(events=len(read(FOLDER/'events.json')['events']),events_sha256=sha(FOLDER/'events.json'))
            elif args.stage=='replay':
                if 'prepare' not in m['completed']:raise ValueError('prepare first')
                if (FOLDER/'replay.json').exists():raise FileExistsError('preserve replay; new namespace required')
                with patch.object(prior,'FOLDER',FOLDER):result=prior.run_replay(profile=dict(active_persistence_v1=True))
            else:
                if 'replay' not in m['completed']:raise ValueError('replay first')
                result=make_report(m)
        assert all(sha(ROOT/n)==v for n,v in m['protected'].items())
        m['completed'].append(args.stage);m.update(status='complete' if args.stage=='report' else 'ready',result=result);atomic_json(mp,m)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except BaseException as exc:
        m.update(status='failed',error=repr(exc));atomic_json(mp,m);raise


if __name__=='__main__':main()
