"""Publish scoped B24 evaluation from sealed predictions and reviewed evidence.

No acquisition, OCR, replay or inference is performed here. Large traces stay
local; concise Markdown and source provenance are reviewable repository files.
"""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evaluate_b24 import OWNER, RUN, SOURCE, EVAL, verify, read, sha
from recognition.video_sampling import atomic_json
from scripts.trace_hidden_constraints import readable_update

VERSION = 'reviewed-context-20261101-v1'
DOC = ROOT / 'docs/b24-evaluation-20261101'
REPORT = ROOT / 'reports/B24-evaluation-20261101.md'
NAMES = {'班基拉斯':248, '怪颚龙':697, '喷火驼':323, '轰擂金刚猩':812,
         '大钢蛇':208, '智挥猩':765, '长毛巨魔':861, '烈咬陆鲨':445,
         '大嘴鸥':279, '铝钢桥龙':1018}
OWN = {861, 445, 279, 1018}


def values(domain):
    if not domain:
        return '?'
    return ', '.join(str(a) if a == b else f'{a}–{b}'
                     for a, b in domain['intervals'])


def compact_episode(ep):
    keys = ('episode_id', 'source_event_id', 'actor_instance_id',
            'target_instance_id', 'before', 'after', 'unit',
            'attribution_status', 'complete_endpoints', 'reasons')
    return {k: ep.get(k) for k in keys}


def hp_cases(reviewed, baseline, diagnostic, production):
    def species(ep):
        mon = production['state']['pokemon'].get(ep.get('target_instance_id'), {})
        return (mon.get('species', {}).get('value') or {}).get('species_id')

    result = []
    for row in reviewed['hp_reference_pairs']:
        sid = NAMES[row['species']]
        def candidates(projection):
            return [e for e in projection['episodes']
                    if species(e) == sid and e['unit'] == row['unit']
                    and e['after'] == row['after']
                    and e['before'] in (None, row['before'])]
        old, new = candidates(baseline), candidates(diagnostic)
        result.append(dict(reference_id=row['reference_id'], text=row['text'],
                           sources=row['sources'], baseline=[compact_episode(e) for e in old],
                           diagnostic=[compact_episode(e) for e in new],
                           endpoint_match=any(e['before'] == row['before'] for e in old),
                           diagnostic_endpoint_match=any(e['before'] == row['before'] for e in new),
                           diagnostic_supported_complete=any(e['before'] == row['before'] and e.get('complete_endpoints') is True and e.get('attribution_status') == 'supported' for e in new),
                           causal_review='See frozen HP adjudication; endpoint equality alone does not certify action attribution'))
    return result


def entity_audit(reviewed, production):
    """Check explicit source-text actors/targets; keep unmeasured effects open."""
    result = []
    for row in reviewed['matches']:
        text = row['text']; pred = row['semantic_match']['prediction']
        expected = []
        if '派出了' in text or text.startswith('上吧'):
            # Both members of compound opening messages require receipts.
            expected = [('actor', s) for n, s in NAMES.items() if n in text]
        elif text.startswith('对') and '效果' in text:
            expected = [('target', s) for n, s in NAMES.items() if n in text]
        elif '拍落了' in text:
            # item_change actor is the affected holder, not move executor.
            holder = text.split('拍落了', 1)[1]
            expected = [('actor', s) for n, s in NAMES.items() if n in holder]
        elif text.startswith('沙暴袭击了'):
            expected = [('actor', s) for n, s in NAMES.items() if n in text]
        elif text.startswith('根据对手的智挥猩的指示'):
            expected = [('actor', 697)]
        else:
            first = re.match(r'^(?:对手的)?(' + '|'.join(NAMES) + ')', text)
            if first:
                expected = [('actor', NAMES[first[1]])]
        related = []
        if pred:
            related = [pred]
            if '派出了' in text or text.startswith('上吧'):
                # Exact shared logical-message occurrence, not a species search
                # across all turns; preserve raw source receipt identities.
                related = [r.get('bindings', {}).get('resolved_event') or r['event']
                           for r in production['history']
                           if r['event']['original_text'] == pred['original_text']
                           and r['event']['event_type'] == 'send_out'
                           and r['application_status'] in {'applied_candidate', 'applied_confirmed', 'applied_partial'}]
        checks = []
        for field, sid in expected:
            side = 'self' if sid in OWN else 'opponent'
            matching = [e for e in related if (e.get(field) or {}).get('species_id') == sid and e.get('side') == side]
            checks.append(dict(field=field, expected_species_id=sid, expected_side=side,
                               matched=bool(matching), event_ids=[e['event_id'] for e in matching]))
        result.append(dict(reference_id=row['reference_id'], source_text=text,
                           prediction_event_id=pred['event_id'] if pred else None,
                           explicit_entity_checks=checks,
                           status='missing' if not pred else 'entity_match' if checks and all(c['matched'] for c in checks) else 'entity_mismatch' if checks else 'no_explicit_entity',
                           effects='Not certified by literal/entity match. Named moves remain move_revelation_only.'))
    return result


def effect_audit(reviewed):
    # Source-text adjudication of these 16 explicit transitions; the reference
    # parser is not used to establish their expected mechanics.
    expected = {
        't1:8': ('side_condition_change', {'condition':'reflect', 'change':'start'}),
        't1:12': ('trick_room_change', {'change':'start'}),
        't2:9': ('stat_change', {'stats':['special_attack'], 'direction':'down'}),
        't3:8': ('stat_change', {'stats':['attack','special_attack'], 'direction':'down'}),
        't3:12': ('weather_change', {'weather':'rain', 'change':'start'}),
        't3:17': ('stat_change', {'stats':['defense'], 'direction':'up'}),
        't3:18': ('side_condition_change', {'condition':'reflect', 'change':'end'}),
        't5:6': ('side_condition_change', {'condition':'tailwind', 'change':'start'}),
        't5:11': ('trick_room_change', {'change':'end'}),
        't6:9': ('stat_change', {'stats':['defense'], 'direction':'up'}),
        't6:10': ('item_change', {'change':'remove'}),
        't6:16': ('weather_change', {'weather':'rain', 'change':'start'}),
        't7:7': ('stat_change', {'stats':['special_attack'], 'direction':'up'}),
        't8:13': ('side_condition_change', {'condition':'tailwind', 'change':'end'}),
        't9:2': ('side_condition_change', {'condition':'reflect', 'change':'start'}),
        't9:11': ('stat_change', {'stats':['defense'], 'direction':'up'}),
    }
    rows = []
    for row in reviewed['matches']:
        key = row['reference_id'].split(':', 1)[1]
        if key not in expected:
            continue
        typ, attrs = expected[key]; pred = row['semantic_match']['prediction'] or {}
        actual = pred.get('attributes', {})
        matched = pred.get('event_type') == typ and all(
            sorted(actual.get(k, [])) == sorted(v) if isinstance(v, list) else actual.get(k) == v
            for k, v in attrs.items())
        rows.append(dict(reference_id=row['reference_id'], text=row['text'],
                         expected_type=typ, expected_attributes=attrs, matched=matched,
                         actual_attributes={k:actual.get(k) for k in attrs},
                         quantitative_stage=actual.get('stages') if typ == 'stat_change' else 'not_applicable',
                         scope='Explicit transition type/direction only; numeric stage and full move-effects separate'))
    return rows


def main():
    verify()
    out = OWNER.cache('diagnosis/b24-' + VERSION)
    latest = read(out / 'latest.json'); trace_path = ROOT / latest['trace']
    trace = read(trace_path); manifest = read(out / 'manifest.json')
    if trace.get('context_validation'):
        raise ValueError('Diagnostic receipt status differences require review')
    if not trace_path.is_file() or sha(trace_path) != manifest['stages']['inference:' + latest['fingerprint']]['outputs'][str(trace_path.relative_to(out))]:
        raise ValueError('Inference output seal mismatch')
    reviewed_path = EVAL / 'reference-comparison/reviewed-comparison.json'
    if sha(reviewed_path) != read(EVAL / 'baseline-quality-seal.json')['sha256']:
        raise ValueError('Frozen baseline comparison changed')
    reference = OWNER.input('b24-battle-log-reference-20261101.json')
    if sha(reference) != read(OWNER.input('b24-battle-log-reference-seal-20261101.json'))['sha256']:
        raise ValueError('Independent reference seal mismatch')
    reviewed = read(reviewed_path); production = read(SOURCE / 'replay.json')
    baseline = read(OWNER.cache('fresh-benchmark/' + RUN + '/hp-resolutions.json'))
    diagnostic = read(trace_path.with_name('hp-projection.json'))
    timing = read(OWNER.cache('fresh-benchmark/' + RUN + '/execution.json'))
    acquisition_counts = read(SOURCE / 'checkpoint.json')['counts']
    adaptive = read(SOURCE / 'adaptive-multi-hit.json')
    production_summary = read(OWNER.report('event-driven/' + RUN + '/summary.json'))
    details = EVAL / 'final'; details.mkdir(exist_ok=True); DOC.mkdir(parents=True, exist_ok=True)
    hp = hp_cases(reviewed, baseline, diagnostic, production)
    entities = entity_audit(reviewed, production)
    effects = effect_audit(reviewed)
    deferred = [dict(event_id=r['event']['event_id'], event_type=r['event']['event_type'],
                     text=r['event']['original_text'], reason=r['reason'])
                for r in production['history'] if r['application_status'] == 'deferred']
    metrics = deepcopy(reviewed['metrics'])
    metrics['body_messages'] = dict(recognized=86, denominator=93, excluded_banner_rows=11)
    metrics['entity_fields'] = dict(statuses=dict(Counter(r['status'] for r in entities)),
                                    matched=sum(c['matched'] for r in entities for c in r['explicit_entity_checks']),
                                    denominator=sum(len(r['explicit_entity_checks']) for r in entities),
                                    scope='Explicit source-text identity and side only; no full-effect accuracy claim')
    metrics['diagnostic_hp_endpoint_pairs'] = sum(r['diagnostic_endpoint_match'] for r in hp)
    metrics['diagnostic_hp_denominator'] = len(hp)
    metrics['diagnostic_hp_supported_complete'] = sum(r['diagnostic_supported_complete'] for r in hp)
    metrics['explicit_transitions'] = dict(matched=sum(r['matched'] for r in effects), denominator=len(effects),
                stat_stage_messages=sum(r['expected_type']=='stat_change' for r in effects),
                quantitative_stages_missing=sum(r['quantitative_stage'] is None for r in effects),
                missing_other_effect_notices=7, full_effect_coverage=None)
    atomic_json(details / 'metrics.json', metrics)
    atomic_json(details / 'hp-cases.json', hp)
    atomic_json(details / 'entity-cases.json', entities)
    atomic_json(details / 'effect-cases.json', effects)
    atomic_json(details / 'deferred.json', deferred)
    atomic_json(details / 'stat-domains.json', dict(rule=trace['configuration_rule'],
                fallback_used=trace['fallback_used'], roster=trace['roster'],
                limitations=trace['limitations'], contradictions=trace['contradictions']))
    damage_rows = []
    for u in trace['updates']:
        if u['kind'] not in {'damage_joint_constraint', 'damage_unusable'}:
            continue
        obs = u['observation']; constraint = u['new_constraint']
        numeric = constraint.get('numerical_inference') or {}
        damage_rows.append(dict(source_event_id=u['source_event_id'],
            action_timestamp=u.get('action_timestamp', u['timestamp']),
            resolution_timestamp=u['timestamp'], observation=obs,
            status=numeric.get('status', 'unresolved'), feasible=numeric.get('feasible'),
            blockers=numeric.get('blockers') or constraint.get('unresolved', [])))
    atomic_json(details / 'damage-cases.json', damage_rows)
    sources = read(EVAL / 'source-reference/index.json')
    for source in sources:
        if source.get('error') or sha(ROOT / source['path']) != source['sha256']:
            raise ValueError('Source snapshot incomplete or changed: ' + source['title'])
    atomic_json(DOC / 'sources.json', dict(retrieved='2026-11-01', articles=sources,
                learnset_table_review=dict(path=str((EVAL / 'source-reference/learnset-row-review.json').relative_to(ROOT)),
                                          sha256=sha(EVAL / 'source-reference/learnset-row-review.json')),
                runtime='Pinned local KnowledgeBase and Champions calc0.12.0; no live lookup',
                scope='Learnability is possibility only; generic move descriptions corroborate the pinned executable reference, not independent Champions certification'))
    # One readable chronological record per preview member, including unselected.
    for member in trace['roster']:
        rows = [u for u in trace['updates'] if u['opponent_roster_id'] == member['roster_id']]
        lines = [f"# {member['name']} — B24 saved-evidence trace", '',
                 'Native marginal outer bounds; all times are source-video seconds. No probability weights.', '']
        for u in rows:
            lines.extend([f"## {u['timestamp']:.3f}s — {u['kind']} / {u['classification']}", '',
                          f"Source `{u['source_event_id']}`; instance `{u['pokemon_instance_id']}`.", '',
                          '\n\n'.join(readable_update(u)), ''])
        if not rows:
            lines.extend(['No admitted appearance or action; initial domain retained.', ''])
        (details / f"species-{member['species_id']}-trace.md").write_text('\n'.join(lines))
    lines = ['# B24 三层评估 — 2026-11-01', '',
             '首次生产识别已封存。后续只复用保存证据、审查配置和现有状态/伤害引擎；未重跑识别、未提交或推送。', '',
             '## 运行与识别基线', '',
             f"视频 FFmpeg 时长 {timing['input']['duration_seconds']:.2f}s；首次 CLI 外部耗时 {timing['normal_cli_wall_seconds']:.3f}s，PTR {timing['PTR']:.4f}。2 FPS；{timing['sampled_frames']} 个采样帧、{timing['detailed_inspection_frames']} 个检查帧、{timing['source_decoded_frames']} 个解码帧。计时包括进程启动至导出退出，后续诊断另计。", '',
             f"OCR {acquisition_counts['ocr_invocations_performed']} 次 / {acquisition_counts['ocr_seconds']:.3f}s；图标 {acquisition_counts['icon_invocations_performed']} 次 / {acquisition_counts['icon_seconds']:.3f}s；重建与序列化至video-only输出 {production_summary['replay_seconds']:.3f}s（不含后续viewer打包，不能当成纯状态更新CPU时间）。", '',
             f"2 FPS指帧物化/监测；实际细检含 {acquisition_counts.get('inspected_frames_at_1fps', 0)} 个既有自适应1 FPS帧，采样与OCR调用频率独立。多段命中补采样配置启用，本场计划窗口 {adaptive['planned_windows']}，未产生密集episode。", '',
             '独立保存图像对照涵盖日志回合1–9、26个页面、119行：93条正文消息、11条特性/道具横幅、15条HP关系。不是整场准确率。', '',
             '| 项目 | 首跑结果 |', '|---|---:|',
             '| 正文消息识别 | 86/93 |', '| 加横幅的语义行识别 | 97/104 |',
             '| 命名招式公告识别 | 25/25（全部仅部分接受） |',
             '| HP数字/单位/物种端点正确 | 13/15 |',
             '| HP动作来源正确 | 11/15 |', '| 完整且因果支持的HP关系 | 10/15 |', '',
             '缺失：号令结果通知、3条沙暴启动、2条沙暴残留、1条要害。命名招式接受为 move_revelation_only，不代表效果或目标全部正确。', '',
             f"显式实体/侧别检查：{metrics['entity_fields']['matched']}/{metrics['entity_fields']['denominator']} 个字段；逐行结果包含缺失和未测字段，见详细 JSON。12条延期回执保持公开。", '',
             f"16条已识别的明确状态转换中，类型/方向字段匹配 {sum(r['matched'] for r in effects)}/16；6条能力阶级公告在首跑结构中均未给出数值阶段。另有上述7条效果通知缺失。此检查不涵盖全部招式效果，整体效果覆盖率未测。", '',
             '## 诊断修复与数值推理', '',
             '保留已解析的完整队伍身份，未解析的后续预览不会撤销它；有证据的回场合并保持HP与招式历史。明确扬沙发动通过受审查规则推导沙暴，仍保留来源；不制造缺失天气公告。首入场铝钢桥龙最大HP194是已验证己方配置与满血规则的推导。', '',
             '七个新增直接伤害契约：十万马力、灵魂冲击、气象球、电光束、精神之牙、拍落、重磅冲撞，另有沙之力。精神之牙按该次命中破墙；拍落区分可移除道具；电光束使用已观察的蓄力后阶级；重磅冲撞读既有当前形态体重。后续效果不重复应用。', '',
             f"诊断HP端点与独立日志相符 {metrics['diagnostic_hp_endpoint_pairs']}/15；这不是新的自动识别准确率。推理阶段总耗时 {trace['inference_wall_seconds']:.3f}s（包含已缓存上下文读取和HP投影）。", '',
             f"其中诊断投影标为完整且supported的匹配端点 {metrics['diagnostic_hp_supported_complete']}/15；该标记不替代独立因果审查，仍公开剩余归因问题。", '',
             f"来源有14个临时命令周期；推理保存 {trace['counts'].get('unique_speed_pair_candidates', 0)} 个去重速度关系候选，产生 {trace['counts'].get('usable_unconditional_speed_observations', 0)} 次无条件速度数值收窄。日志可读回合号和临时周期不互相替代。", '',
             '用户默认域 user-default-down-zero-sp-v1：被降低的非HP能力训练值仅0，中性/提升为0–32；共同性格修正和总SP≤66。已知己方精确配置保持原值。无频率先验、无静默放宽。整数集合是保守边际，仍未证明道具/特性/所有伤害关系存在同一个完整联合解。', '',
             '| 对手成员 | 速度 初始→最终 | 攻击 初始→最终 | 特攻 初始→最终 |', '|---|---|---|---|']
    for member in trace['roster']:
        cells = [values(member['initial'][s]) + ' → ' + values(member['final_stats'][s])
                 for s in ('speed', 'attack', 'special_attack')]
        lines.append('| ' + member['name'] + ' | ' + ' | '.join(cells) + ' |')
    lines.extend(['', '对手伤害关系（完成评估不一定收窄）：', '',
                  '| 动作时间 / 招式 | HP关系 | 数值状态 | 保留集合或阻塞 |', '|---|---|---|---|'])
    for row in damage_rows:
        obs = row['observation']
        result = values(row['feasible']) if row['status'] == 'exact' else '; '.join(row['blockers'])
        lines.append(f"| {row['action_timestamp']:.3f}s / {obs['move_name']} | {obs['before']}→{obs['after']} {obs['unit']} | {row['status']} | {result} |")
    unavailable = [u for u in trace['updates'] if u['kind'] == 'damage_unavailable']
    lines.extend(['', f"另有 {len(unavailable)} 条对手执行没有绑定可用HP关系；详见时间线，不计为已完成反演。"])
    lines.extend(['', f"推理矛盾 {len(trace['contradictions'])}；来源状态冲突 {len(trace['source_state_conflicts'])}；诊断接受状态差异 {len(trace['context_validation'])}。", '',
                  '## 逐条结果与限制', '',
                  f"完整数值结果、SP/修正分支、15条HP对照、实体字段检查、延期事件和逐成员时间线见 [本地详细结果]({details})；[完整推理trace]({trace_path})。", '',
                  '首跑HP问题保留：首次铝钢桥龙与怪颚龙回场缺基线；大嘴鸥和烈咬陆鲨的沙暴损伤被归给顺风；生命宝珠54%→44%平台不确定；额外8%→6%自损片段没有独立支持。端点恢复不自动解决所有归因。百分比未知最大HP不反推防御/HP。', '',
                  '未选择/未出现成员保留初始集合。未认证行动周期不冒充有效速度比较；未知机制和缺失上下文保持条件或未解。算术对算一致只说明符合固定Champions执行参考。', '',
                  '修复前只有伤害handler覆盖基线5/17，未运行完整数值反演；不把缺失上下文等阻塞都计为计算器错误，也不声称数值反演的前后提升比例。', '',
                  '恢复过程中修复了配置加载时间戳导致的缓存指纹漂移、有证据的空道具槽被当作未知、并列能力公告未量化三处问题；既有完整上下文通过精确指纹验证后复用，实际阶级解释改变后另建上下文。原始回执与各版trace均保留。', '',
                  '最终相关可移植回归241通过、1项按local_artifacts排除。此前更广回归1163通过、4项排除，运行在最后两项局部修复之前；两组有重叠，不相加为独立测试总数。', '',
                  '来源及版本见 [52Poké记录](../docs/b24-evaluation-20261101/sources.json)。测试、完整性与恢复命令见 [交接](../docs/b24-evaluation-20261101/handoff.md)。'])
    REPORT.write_text('\n'.join(lines) + '\n')
    preflight = read(EVAL / 'preflight.json')
    checked = dict(preflight['protected_previous'])
    checked.update({str(ROOT / p): h for p, h in read(OWNER.cache('fresh-benchmark/' + RUN + '/initial-freeze.json'))['files'].items()})
    checked.update({str(reference): sha(reference), str(reviewed_path): sha(reviewed_path)})
    for stage in manifest['stages'].values():
        if stage['status'] != 'complete':
            continue
        if stage.get('output'):
            checked[str(out / stage['output'])] = stage['sha256']
        for key in ('diagnostic_replay', 'derived_hp_projection'):
            if stage.get(key):
                checked[str(out / stage[key]['path'])] = stage[key]['sha256']
        checked.update({str(out / p): h for p, h in stage.get('outputs', {}).items()})
    mismatches = [p for p, h in checked.items() if sha(Path(p)) != h]
    movie = timing['input']
    movie_ok = sha(Path(movie['path'])) == movie['sha256']
    atomic_json(DOC / 'integrity.json', dict(checked_files=len(checked), mismatches=mismatches,
                movie_sha256=movie['sha256'], movie_matches=movie_ok,
                frozen_baseline_and_reference_verified=True,
                current_outputs={str(p.relative_to(ROOT)):sha(p) for p in details.iterdir() if p.is_file()},
                trace=str(trace_path.relative_to(ROOT)), trace_sha256=sha(trace_path)))
    if mismatches or not movie_ok:
        raise ValueError('Final integrity check failed')
    print('Report:', REPORT)
    print('Entity fields:', metrics['entity_fields'])
    print('Diagnostic HP endpoints:', metrics['diagnostic_hp_endpoint_pairs'], '/', len(hp))


if __name__ == '__main__':
    main()
