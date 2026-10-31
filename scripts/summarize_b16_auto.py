"""Read-only detailed analysis of completed automatic B16 evaluation artifacts."""
from collections import Counter
import csv
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.event_report import verify_seal
from recognition.fast_video import digest
from recognition.video_sampling import atomic_json


def main():
    owner=BattleArtifacts('sample_battle_16');run='b16-auto-eval-20261026-v1'
    out=owner.report('evaluation/'+run);cache=owner.cache('evaluation/'+run)
    source=owner.cache('event-driven/'+run)
    read=lambda p:json.loads(p.read_text())
    result=read(out/'validation.json');perf=read(out/'performance.json')
    reference=read(cache/'auto-reference/reference.json')
    events=list(csv.DictReader((out/'event_validation.csv').open(encoding='utf-8-sig')))
    bins=list(csv.DictReader((out/'processing_per_10s.csv').open(encoding='utf-8-sig')))
    assert abs(sum(float(b['processing_seconds']) for b in bins)-perf['pipeline_wall_seconds'])<1e-6
    assert sum(int(b['sampled_frames']) for b in bins)==perf['sampled_frames']
    assert len({r['prediction_id'] for r in events if r['prediction_id']})==result['live_gameplay_candidates']
    assert len({r['reference_id'] for r in events if r['reference_id']})==result['reference_entries']
    execution=read(cache/'execution.json')
    assert all(digest(source/n)==h for n,h in execution['sealed_outputs'].items())
    verify_seal(source)
    reasons=Counter(reason for r in events for reason in r['mismatch_reason'].split(';') if r['validation_status']!='TP')
    observed_turns=sorted({e['turn'] for e in reference['entries']})
    details=['','## 自动诊断补充','',
        f"实际日志覆盖的回合号：{observed_turns}；拼接异常 {len(reference['assembly_issues'])} 项。记录数不等于整场事件分母。13/89（{13/89:.1%}）是参考记录进入当前自动评分的比例；12/80（15.0%）是正常主要事件候选被匹配核验的比例。二者不是整场准确率。",'',
        '自动原因统计（同条记录可有多项）：','']
    for reason,count in reasons.most_common():details.append(f'- `{reason}`：{count} 条。')
    details+=['','唯一候选 FN：第2回合日志 `铝钢桥龙的 / 吃剩的东西`，日志查看时间400.0s，正常通道无支持的有序匹配。原行动视频时间、side 仍未知；可能是正常管线遗漏，也可能是日志标签被共享解析器解释为 activation 的相关错误，因此不能认定为人工确认的漏检。原始结构化双方结果已导出。',
        '角色归属错误或顺序错误：没有足够独立证据可报告确定数量，不能按0错误解释；11条 ambiguous_alignment 保留为对齐不确定。未匹配预测19条因日志范围不明标记 unverified，不能定为误检。', '',
        '复杂场景以正常管线事件候选定位，自动证据不足时不下正确/错误结论：','',
        '| 视频区间 | 主要候选 | PTR | 自动核验限制 |','|---|---|---:|---|']
    chosen={180,190,350,370,380,420,430,460,520,550,620,630,660,690,720}
    for b in bins:
        if int(float(b['video_start'])) not in chosen:continue
        types=json.loads(b['major_events'])
        notes=''
        if 'transformation' in types:notes='Mega候选；两条日志 transformation 均 uncertain'
        elif 'status_change' in types:notes='异常状态；仅已匹配字段可核验，其余见CSV'
        elif any(k in types for k in ('switch_out','send_out')):notes='连续离场/入场候选；日志侧/时间或对齐仍有缺口'
        elif 'faint' in types:notes='倒下候选；仅3条日志 faint 获得自动匹配'
        details.append(f"| {b['video_start']}–{b['video_end']} | {b['major_events']} | {float(b['PTR']):.3f} | {notes} |")
    replay=read(source/'replay.json')
    faints=[(r['event']['attributes']['observation_time'],r['event']['side']) for r in replay['history'] if r['event']['event_type']=='faint']
    details+=['',f'已识别 faint 时间/侧：{faints}。未从这批候选建立“双方同时击倒”的独立验证，不能宣称该场景已通过。',
        '最高PTR区间590–600s仅有1条招式候选，不能用事件数量解释最高开销。前缀验证多次重放历史事件，本评测把每次重放成本累计到被重放事件的原时间区间；所以早期区间也会承担后续触发的重放成本。这是源事件成本归属，不是当时在线延迟。',
        f"状态哈希独占 {perf['stages']['state_hash']['total']:.3f}s（占总管线 {perf['stages']['state_hash']['total']/perf['pipeline_wall_seconds']:.1%}），事件更新外围独占 {perf['stages']['state_event']['total']:.3f}s，OCR模型推理 {perf['stages']['ocr_inference']['total']:.3f}s。pipeline剩余独占开销含未细分预处理/序列化/调度，不能冒充纯图像预处理耗时。模块完整分布见performance.json。",'',
        '全视频时长采用FFmpeg容器duration 753.74s；OpenCV平均FPS×总帧数对应753.71s，约0.03s容器/时间基差异，未混用两种分母。',
        '已自动检查：76个区间耗时之和等于管线wall；采样帧之和1508；80个正常主要事件候选和89个参考ID各自唯一；所有封存输出哈希不变。工具测试41项和新增参考有效性测试1项通过。没有人工标注、人工核验或规则修复。',
        '复现：先执行README中的正常解析命令（完成结果必须复用），随后 `scripts/evaluate_b16_auto.py --run-id b16-auto-eval-20261026-v1`，最后 `.venv/bin/python scripts/summarize_b16_auto.py`。参考图像/读数缓存及身份指纹已保存。']
    report=out/'report.md';body=report.read_text().split('\n## 自动诊断补充')[0];report.write_text(body+'\n'.join(details)+'\n')
    atomic_json(out/'verification.json',dict(status='complete',source_seal_unchanged=True,bin_count=len(bins),event_rows=len(events),
        output_hashes={n:digest(out/n) for n in ['event_validation.csv','processing_per_10s.csv','validation.json','performance.json','report.md']},
        analysis_source_sha256=digest(Path(__file__))))
    print('Verified totals, unique IDs, source seal and report outputs.')
if __name__=='__main__':main()
