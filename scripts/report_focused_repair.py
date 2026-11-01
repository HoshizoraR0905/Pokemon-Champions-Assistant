"""Render the focused B20–B23 audit from completed, fingerprinted saved traces."""
import json
import hashlib
from pathlib import Path
from collections import Counter
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.report_inference_integration import blockers

def read(p):return json.loads(p.read_text())
def sets(domain):
    if not domain:return '?'
    values=sorted(set(domain['values']));runs=[]
    for v in values:
        if runs and v==runs[-1][-1]+1:runs[-1].append(v)
        else:runs.append([v])
    return ', '.join(str(r[0]) if len(r)==1 else f'{r[0]}–{r[-1]}' for r in runs) or '∅'
def cell(v):return str(v).replace('|','/').replace('\n',' ')
def link(p,label):return f'[{label}]({ROOT/p})'
def hits(t):return {(u['source_event_id'],u['observation']['target']):u for u in t['updates'] if u['kind'] in {'damage_joint_constraint','damage_unusable'}}

def main():
    traces={};prior={};manifests={};paths={}
    for n in (20,21,22,23):
        base=ROOT/f'.cache/battles/sample_battle_{n}/diagnosis'
        latest=read(base/'focused-repair-20261101-v1/latest.json');paths[n]=latest['trace'];traces[n]=read(ROOT/paths[n])
        prior[n]=read(ROOT/read(base/'hidden-integration-20261101-v1/latest.json')['trace'])
        manifests[n]=read(base/'focused-repair-20261101-v1/manifest.json')
    old_count=sum(u['new_constraint'].get('numerical_inference',{}).get('status')=='exact' for t in prior.values() for u in hits(t).values())
    new_count=sum(u['new_constraint'].get('numerical_inference',{}).get('status')=='exact' for t in traces.values() for u in hits(t).values())
    total=sum(len(hits(t)) for t in traces.values())
    lines=['# B20–B23 Focused Repair — 2026-11-01','',f'保存的 {total} 条对手动作–目标伤害关系中，完成数值评估从 {old_count} 条增加到 {new_count} 条。仅重建保存事件的诊断状态并调用既有 M3 正反算；未解码视频、OCR 或执行生产流程。没有提交或推送。','',
    '## 身份与连续历史','',
    '六只队伍的共同 species ID 决定成员身份，地区及性别形态不构成第二个成员。完整名单、同侧身份和已建立的换出证据支持回场合并；来源 encounter/event/receipt ID 原样保留，新增 alias 指向持久成员。HP、已用招式、原始道具事实持续保留，在场片段分别记录；回场重置能力阶级等已支持的临时效果。','',
    '百变怪登场仍为百变怪。只有明确的变身者发动证据或变身招式及其目标/结果证据建立复制，退场结束临时复制；再次登场不会自动复制。复制能力、外观及非 HP 能力值不建立第二个队伍成员，也不限制百变怪本体训练值。','',
    '| 场次 | 原来源 encounter → 持久成员（后缀） | HP / 招式历史 |','|---|---|---|']
    for n,t in traces.items():
        stages=[s for k,s in manifests[n]['stages'].items() if k.startswith('contexts:') and s['status']=='complete']
        stage=next(s for s in stages if s['output']==t['sources']['context_output'])
        if not t['focused_repair']['aliases']:lines.append(f'| B{n} | 无新增分裂合并 | 原有连续身份保留 |')
        for alias,pid in t['focused_repair']['aliases'].items():
            h=stage.get('persistent_histories',{}).get(pid,{})
            lines.append(f"| B{n} | `{alias.rsplit(':',1)[-1]}` → `{pid.rsplit(':',1)[-1]}` ({h.get('original_identity',{}).get('name','?')} / {pid.split(':')[1]}) | {len(h.get('hp_observation_event_ids',[]))} 条 HP 历史、{len(h.get('revealed_move_event_ids',[]))} 条执行证据，持久共享 |")
    lines+=['','每个完整历史的证据 ID 列表保存在各场 manifest 的 `persistent_histories`，完整能力值更新在 trace 中。道具约束在同一未改变的持有期要求相同命名道具见证；观察到消耗/移除/转移后另开持有期。当前持有和原始装备仍分别表达，只有原始所有权证据支持时才无条件应用六成员道具互斥。','',
    '## HP 端点','', '| 场次 | 恢复 | 来源与归因 |','|---|---|---|']
    for n,t in traces.items():
        for repair in t['focused_repair']['hp_repairs']:
            new=repair['repaired'];proof=repair['provenance']
            origin='推导起点：首次入场 + 已验证最大 HP194 + 用户满血确认' if proof['kind']=='verified_initial_full_hp' else '直接数字端点 + 稳定平台/独立灼伤事件的因果推导'
            lines.append(f"| B{n} | {new['before']}→{new['after']}（{abs(new['delta'])}） / `{repair['source_event_id']}` | {origin}；逐观察来源在 repaired-hp-projection.json |")
    lines+=['','B20 宝石力量 194→152（42）、B21 冰冻光束 194→168（26）、B22 岩崩 194→178（16）：194 来自用户确认满血、Team7 已验证最大 HP、首次入场及无中间伤害检查，属于推导，末端数字来自保存读数。未制造 HUD 观察。B23 闪焰冲锋 181→97（84）：稳定 97 平台在灼伤事件之前；后续 97→85 灼伤和攻击者反伤单列，不计入直接伤害。返回场地不会满血，最大 HP 未知的 100% 仍为百分比。','',
    '## 招式与特性','',
    '| 招式 | 修复的直接伤害契约 |','|---|---|',
    '| 木槌 | 120 威力常规直接伤害；反伤独立；舍身仅修正适用反伤招式威力 |',
    '| 青草滑梯 | 55 威力，既有青草场地和接地修正；优先度交给既有速度模块 |',
    '| 影子偷袭 | 40 威力；优先度不混入伤害 |',
    '| 双翼 | 两个 40 威力独立命中、独立随机数/要害分支，共享攻击配置；保存的 21+24 只建立两条观察，总计 45 不再建立第三条约束 |',
    '| 电磁炮 | 120 威力直接命中；麻痹及命中率不混入目标 HP 损失 |',
    '| ＤＤ金勾臂 | 85 威力，忽略防守方防御阶级；不忽略基础防御或特性修正 |','',
    '补齐的攻击侧特性契约：青草制造者、电气制造者、冲浪之尾、腐蚀、毒满地、恒净之躯、坚硬脑袋、舍身、碎裂铠甲，以及非火招式下的引火。它们需要调用者提供行动时场地/阶级/状态，计算器不重复模拟入场、反伤或后续效果。引火的火招式激活分支仍明确不支持。茂盛/猛火/激流/虫之预感使用已知绝对 HP 或安全的显示百分比阈值；33% 或未知时保留两种分支。雷丘形态按已钉住知识分支保留，本体、阿罗拉、Mega X（电气制造者）和 Mega Y（无防守）不互相代替。','',
    '数据核对依据：适用的 [52Poké Champions 招式表及检索版本](../docs/focused-repair-20261101/sources.json)，运行时只读本地已钉住知识和 Champions calc 0.12.0。精确整数对照代表该执行参考的一致性，尚不等于独立的 Champions 实测认证。','',
    '## 28 条动作–目标关系逐项评估','', '| 场次 / 时间 | 招式 / 来源动作 ID | 目标后缀 / HP | 原状态 → 新状态 | 剩余阻塞或结果 |','|---|---|---|---|']
    for n,t in traces.items():
        previous=hits(prior[n])
        for key,u in hits(t).items():
            obs=u['observation'];num=u['new_constraint'].get('numerical_inference',{});old=previous.get(key,{}).get('new_constraint',{}).get('numerical_inference',{})
            detail=sets(num.get('feasible')) if num.get('status')=='exact' else blockers(num)
            lines.append(f"| B{n} / {u['timestamp']:.2f} | {cell(obs.get('move_name'))} / `{u['source_event_id']}` | `{(obs.get('target') or '').rsplit(':',1)[-1]}` / {obs.get('before')}→{obs.get('after')} {obs.get('unit')} | {old.get('status','unresolved')} → {num.get('status','unresolved')} | {cell(detail)} |")
    lines+=['','成功评估表示所有准入分支都可计算；不意味着一定缩小范围。没有完整绝对 HP、复制本体投影或未知机制的关系继续保留条件约束，未移除不支持分支以制造收窄。',
    '另有 '+str(sum(t['counts'].get('damage_unavailable',0) for t in traces.values()))+' 条已接受攻击执行未绑定可用的保存 HP 关系，未计入上述28条，仍不作反推；逐动作记录见各 trace 的 damage_unavailable。暴风的剩余限制是本体投影边界，不是遗漏常规伤害 handler。','',
    '## 原生能力值可行集合','',
    '以下是无权重的整数集合（包含不连续区间），不是概率分布。前值是上次 integration audit 的队伍成员保守并集；后值已在有证明的持久成员内交集。尚未投影的联合约束仍可能使这些边际集合过宽；不宣称每个整数都有完整六项训练值/道具/特性联合解。','',
    '| 场次 / 成员 | Speed 前 → 后 | Attack 前 → 后 | Special Attack 前 → 后 |','|---|---|---|---|']
    for n,t in traces.items():
        old={m['roster_id']:m for m in prior[n]['roster']}
        for m in t['roster']:
            before=old[m['roster_id']]['final_stats'];after=m['final_stats']
            columns=[sets(before[s])+' → '+sets(after[s]) for s in ['speed','attack','special_attack']]
            lines.append(f"| B{n} / {m['name']} | "+' | '.join(columns)+' |')
    lines+=['','## 版本、完整性与限制','', '| 场次 | 新 trace | 回执状态差异 / 原来源冲突 / 推断矛盾 |','|---|---|---|']
    for n,t in traces.items():
        lines.append(f"| B{n} | {link(paths[n],'完整 trace')} | {len(t['context_validation']['receipt_status_mismatches'])} / {len(t['source_state_conflicts'])} / {len(t['contradictions'])} |")
    lines+=['','B21 身份修复曾使8条来源延期 HUD 在诊断重放中变得可绑定。旧诊断尝试已保留，最终上下文输入排除这8条，source_admission_guard 在 manifest 记录原状态和排除原因；来源回执本身不变。最终回执状态差异为零。','', '诊断状态因为身份、初始 HP 和状态修复与原冻结终态哈希不同，原回执仍权威，未重写原 state_hash；保存来源冲突和未接受事件继续公开。冻结来源未绑定的队伍元数据也没有改成已绑定；Team7 属于带 provenance 的诊断附件。','',
    '验证：相关回归1384通过、10项按 local_artifacts 标记排除；最新聚焦及百变怪套件61通过。冻结来源/声明输入/完成输出共175个文件哈希检查零差异，其中62个既有推断 JSON 输出均保留。详见 [完整性记录](../docs/focused-repair-20261101/integrity.json)。',
    '验证与确切恢复命令见 [handoff](../docs/focused-repair-20261101/handoff.md)。每场 stage manifest 保留输入 SHA、依赖版本、进度和输出 SHA；旧 trace 和报告均保留。','']
    path=ROOT/'reports/B20-B23-focused-repair-20261101.md';path.write_text('\n'.join(lines))
    print(json.dumps(dict(report=str(path),candidates=total,previous_exact=old_count,now_exact=new_count),ensure_ascii=False))

if __name__=='__main__':main()
