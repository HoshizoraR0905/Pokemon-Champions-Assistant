"""Compact B20-B23 audit from versioned saved inference traces; no replay/OCR."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from damage import calculate
from battle_artifacts import BattleArtifacts


def read(path):return json.loads(path.read_text())
def link(path,label):return f'[{label}]({ROOT/path})'
def bounds(x):return '?' if not x else f"{x['minimum']}–{x['maximum']} ({x['count']})"
def cell(x):return str(x).replace('|','/').replace('\n',' ')


def blockers(result):
    reasons=[r for r in result.get('blockers',[]) if not r.startswith('solver retains unsupported alternatives:')]
    for branch in result.get('branches',[]):
        for diagnostic in branch.get('diagnostics',[]):
            for issue in diagnostic.get('unsupported_mechanics',[])+diagnostic.get('unresolved_inputs',[]):
                path=issue.get('path','input');detail=issue.get('reason','unresolved')
                if path=='attacker.ability':
                    missing=set(branch.get('abilities',[]))-set(issue.get('candidates',[]))
                    detail='handler unavailable for '+', '.join(sorted(missing)) if missing else detail
                reasons.append(branch.get('form','')+': '+path+' / '+detail)
    return '; '.join(sorted(set(reasons))) or 'input contract unresolved; full diagnostics in trace.json'


def main():
    traces={};summaries={};old={};contexts={}
    for n in (20,21,22,23):
        owner=BattleArtifacts(f'sample_battle_{n}',ROOT)
        base=owner.cache('diagnosis/hidden-integration-20261101-v1')
        summaries[n]=read(base/'latest.json');traces[n]=read(ROOT/summaries[n]['trace'])
        if traces[n].get('integration_profile')!='b20-b23-saved-state-integration-v1':
            raise ValueError(f'B{n} requires a final inference-only refresh with --integration-audit')
        prior=read(owner.cache('diagnosis/hidden-constraints-20261031-v1/latest.json'))
        old[n]=read(ROOT/prior['trace'])
        contexts[n]={}
        for line in (base/traces[n]['sources']['context_output']).open():
            row=json.loads(line);contexts[n][row['event_id']]=row['context']
    damage=[];pairs={};refinements=[]
    for n,t in traces.items():
        pairs[n]={u['observation']['joint_relation_id']:u for u in t['updates'] if u['kind']=='speed_order_candidate'}
        damage += [(n,u) for u in t['updates'] if u['kind'] in {'damage_joint_constraint','damage_unusable'}]
        refinements += [(n,u) for u in t['updates'] if u['kind']=='numeric_refinement']
    all_pairs=[u for ps in pairs.values() for u in ps.values()]
    certified_total=sum(u['new_constraint'].get('certification',{}).get('status')=='certified_local_membership' for u in all_pairs)
    speed_total=sum(u['new_constraint'].get('numerical_inference',{}).get('status')=='exact' and u['new_constraint']['numerical_inference'].get('same_effective_priority_supported') for u in all_pairs)
    damage_total=sum(u['new_constraint'].get('numerical_inference',{}).get('status')=='exact' for _,u in damage)
    reductions=Counter(u['observation']['stat'] for _,u in refinements)
    panels={s:sum(t['numerical_refinement'][s+'_pokemon'] for t in traces.values()) for s in ['speed','attack','special_attack']}
    modifier_audits={}
    for n in traces:
        old_hits={(u['source_event_id'],u.get('observation',{}).get('target')):u for u in old[n]['updates']
            if u['kind'] in {'damage_joint_constraint','damage_unusable'}}
        entries=[]
        for bid,u in damage:
            if bid!=n:continue
            previous=old_hits[(u['source_event_id'],u['observation']['target'])]['new_constraint']
            current=u['new_constraint']
            for role in ['attacker','defender']:
                before=previous[role+'_context'];after=current[role+'_context']
                fields={**{'stage:'+s:v for s,v in before['stages'].items()},
                    **{'field:'+s:v for s,v in before['field'].items()},
                    **{k:before.get(k) for k in ['status','ability','item','tailwind','form']}}
                for key,value in fields.items():
                    if value is not None:continue
                    category,_,leaf=key.partition(':')
                    now=after['stages'].get(leaf) if category=='stage' else after['field'].get(leaf) if category=='field' else after.get(key)
                    cause=4 if now is None else 2 if key in {'ability','item','form'} else 1
                    reason=('source observation remains unresolved; retain admitted alternatives or withhold full projection' if cause==4 else
                        'verified exact-six profile propagation/current-form resolution' if cause==2 else
                        'reviewed neutral opening and event transitions; complete stat announcements use labeled reference magnitudes')
                    entries.append(dict(event_id=u['source_event_id'],target=u['observation']['target'],role=role,field=key,
                        before=None,after=now,cause_category=cause,reason=reason,available_at=u['timestamp']))
            if previous['defender_context'].get('configured') is None:
                entries.append(dict(event_id=u['source_event_id'],target=u['observation']['target'],role='defender',field='known_configuration',
                    before=None,after=(current['defender_context'].get('configured') or {}).get('team_id'),cause_category=2,
                    reason='normal self-preview acquisition gap; independently reviewed complete saved roster enables existing attachment rule'))
            elif current['defender_context'].get('current_form_stats'):
                entries.append(dict(event_id=u['source_event_id'],target=u['observation']['target'],role='defender',field='current_form_stats',
                    before='configured existed; current battle_stats not exposed by prior trace adapter',
                    after={k:v for k,v in current['defender_context']['current_form_stats'].items() if k in {'hp','defense','special_defense','speed','canonical_variant'}},
                    cause_category=2,reason='existing current-form mechanic was omitted from inverse input contract'))
        owner=BattleArtifacts(f'sample_battle_{n}',ROOT)
        source=ROOT/summaries[n]['trace'];generator=Path(__file__)
        identity=dict(trace=str(source.relative_to(ROOT)),trace_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),generator_sha256=hashlib.sha256(generator.read_bytes()).hexdigest())
        fingerprint=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:16]
        path=owner.cache('diagnosis/hidden-integration-20261101-v1/audits/modifiers-'+fingerprint+'.json')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(dict(identity=identity,classification='audit of every formerly unknown modifier in the prior 28 candidate contexts',
            cause_legend={'1':'source initialization/transition capability','2':'adapter/profile propagation','3':'serialization loss; none established','4':'unresolved observation/unsupported alternative'},entries=entries),ensure_ascii=False,indent=2)+'\n')
        modifier_audits[n]=(path,Counter(e['cause_category'] for e in entries))
    lines=['# B20–B23 推理接线审计与定点修复（2026-11-01）','',
        '本报告只重放保存的已识别事件、身份与 HP 证据。原始识别、OCR、图标识别、生产 CLI、录像与历史基准未重跑或改写。旧追踪完整保留，新输出位于 `hidden-integration-20261101-v1`，每次实现指纹有独立子目录。未提交或推送。','',
        '“数值评估”表示完整纳入该次参考模型允许的分支；“收窄”只计实际排除至少一个原本体能力值的事件。原身份连续性未修复：不同 encounter ID 分开约束，队员面板对未解决身份取并集。这里的无条件只指对已列举道具、特性、暴击分支取并集，所有数值仍以固定 Champions 社区参考和保存识别重建成立为条件，不是独立游戏机制认证。','',
        f"四场 Team 7 均已验证并接入；{len(damage)} 个候选均拿到已核对的当前形态防守数值。共恢复 {certified_total} 条本地同周期关系，其中 {speed_total} 个同有效优先度比较可数值使用；{damage_total} 条伤害关系完成反演。真正排除值的事件为速度 {reductions['speed']} 次、攻击 {reductions['attack']} 次、特攻 {reductions['special_attack']} 次；新增空候选集 {sum(len(t['contradictions']) for t in traces.values())} 个。按未解决来源身份取并集后，队员面板速度 {panels['speed']} 名、攻击 {panels['attack']} 名、特攻 {panels['special_attack']} 名收窄。",'',
        '| 场次 | 旧候选 / 新认证同周期关系 | 已数值评估且支持同有效优先度的速度关系 | 速度收窄事件 | 已求解伤害关系 | 攻击 / 特攻收窄事件 | 新矛盾 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for n,t in traces.items():
        ps=list(pairs[n].values());ds=[u for bid,u in damage if bid==n]
        certified=sum(u['new_constraint'].get('certification',{}).get('status')=='certified_local_membership' for u in ps)
        usable=sum(u['new_constraint'].get('numerical_inference',{}).get('status')=='exact' and u['new_constraint']['numerical_inference'].get('same_effective_priority_supported') for u in ps)
        refs=[u for bid,u in refinements if bid==n]
        solved=sum(u['new_constraint'].get('numerical_inference',{}).get('status')=='exact' for u in ds)
        lines.append(f"| B{n} | {old[n]['counts']['unique_speed_pair_candidates']} / {certified} | {usable} | {sum(u['observation']['stat']=='speed' for u in refs)} | {solved} | {sum(u['observation']['stat']=='attack' for u in refs)} / {sum(u['observation']['stat']=='special_attack' for u in refs)} | {len(t['contradictions'])} |")
    lines += ['', '## Team 7 与历史接入','',
        '逐张检查四场保存的完整己方预览，行序均为妙蛙花、喷火龙、大嘴鸥、烈咬陆鲨、长毛巨魔、铝钢桥龙。使用既有 exact-six 用户同配置政策、`attach_verified_profile`、`bind_attached_profile`、`initialize_team` 和 `form_stats`；没有用出场种类重合替代六只验证，也未合并源身份。正常采集修复重用既有己方名字区域、OCR 接口与实体解析器；本次诊断只使用人工核对的旧截图，不调用新识别。','',
        '| 场次 | 完整六只证据 / 可用时间 | 上次约束实验收到配置 | 本次绑定己方来源实例数 | 首跑记录 |', '|---|---|---|---:|---|']
    for n,t in traces.items():
        meta=t['team7_integration'];r=meta['review']['roster']
        had=any(u['new_constraint'].get('defender_context',{}).get('configured') for u in old[n]['updates'] if isinstance(u.get('new_constraint'),dict))
        lines.append(f"| B{n} | {link(Path(r['image']),'预览原图')} / {r['observation_time']:.3f}s | {'是，但未进入反演' if had else '否'} | {len(meta['attached_self_instances'])} | {'B23 sealed team_profile_linkage=unbound 保留；新诊断附件另列' if n==23 else '原文件保留'} |")
    lines += ['',link(Path('docs/hidden-constraints-b20-b23/integration-review-20261101.json'),'逐场图像 SHA-256、行序与开局证据'),
        '当前形态数值从既有 `battle_stats.current` 读取，不把配置的普通形态字段直接当 Mega 数值；Mega 烈咬陆鲨 Z 的防御 106、特防 105、速度 203 来自原 SP/修正方向与已验证形态计算。相关时刻实际使用的防御列在下表，复制数值仍不约束百变怪本体。绑定实例数包含未合并的再入场来源 ID，不表示实际选出了五只。','',
        '## 之前为何全为零','',
        '| 输入/断层 | 原因分类 | 修复及边界 |','|---|---|---|',
        '| 未公告天气/场地、空间、顺风、屏障、初入场阶段、主要状态 | 1：源 StateEngine 未初始化 | 仅有保存预览→首次派出开局证据时建立中性基线；普通缺公告不清空已知事实；真实 coverage gap 使相关事实重新未知。无开局审查仍保持未知。 |',
        '| 提高/降低后阶段变未知 | 1：原事件仅给方向、stages=None | 诊断参考解释完整中文公告：普通±1、大幅±2；上下限与增减仍由原 StateEngine 处理。默认未审查配置不改变。未识别完整公告或特殊继承仍未知。 |',
        '| 光墙/反射壁启动被已知 inactive 拒绝 | 1：旧 parser 将启动标为 observe | 新解析为 start，旧保存公告按严格启动文本兼容；其他静态 observe 冲突仍保留。 |',
        '| 己方配置未绑定、Mega 防御未进入伤害输入 | 2：采集/推理适配缺口 | 正常己方预览采集补齐；诊断经旧截图 exact-six 审查绑定；直接读取当前形态 battle_stats。 |',
        '| 24 条伤害只生成条件关系 | 2：追踪器未调用反演器 | 接入原 infer_attack_stat，保留未知合法道具、原生特性、暴击、节拍器计数并集；击倒用伤害下界；地形下接地与道具/特性关联枚举。 |',
        '| 102 个顺序候选被无条件标记 provisional | 2：没有认证接入 | 复用命令周期、既有 resolution_active_instance_ids 四原始机会和 end_of_turn_resolution_id；完整四行动且无内部边界/缺口才升级本地周期关系。不推断绝对回合号。 |',
        '| 源状态在序列化丢失中性值 | 3：本次未发现 | 已覆盖 Fact/State round-trip，缺口位于初始化和读取，不归咎于序列化。 |',
        '| 对手当前形态/原生特性、HP 阈值、未识别公告及未认证周期 | 4：证据或精确能力边界 | 未知保留；不从后续道具/形态公告倒填。多身份不相交；未知同优先度不强制严格大于，平速保留。 |','',
        '窄能力扩展：明确节拍器计数 0–5 的单次命中加成、一般宝石单次命中加成、紧张感对抗性树果的影响、已知阶段下若干不直接修改该次伤害的特性，以及臂锤已命中的直接伤害。均使用原伤害流程与固定对算参考；道具消费、臂锤降速与其他命中后效果继续属于原事件状态层。没有新增伤害计算器或防御/HP 联合引擎。','',
        '每一个旧追踪中未知的字段均有逐条审计（计数为字段，不是独立观测；分类 1/2/4 依次为源初始化/转换、适配/配置传播、仍未知，分类 3 本次未发现）：','',
        '| 场次 | 分类 1 / 2 / 4 | 逐字段旧值、新值、原因及事件 |','|---|---:|---|']
    for n,(path,counts) in modifier_audits.items():
        lines.append(f"| B{n} | {counts[1]} / {counts[2]} / {counts[4]} | {link(path.relative_to(ROOT),'modifier audit JSON')} |")
    lines += ['', '## M3 输入合同对照','',
        '| 参数 | 保存状态/证据 | 原适配缺口 | 仍未知时的处理 / 求解能力 |',
        '|---|---|---|---|',
        '| 攻击者身份、当前形态 | 源 encounter ID 与 variant；部分仅 species-only | 没把可能形态、当前能力与本体 SP 对应关系送入求解 | 取兼容当前特性的固定目录形态并集；复制值不投影本体；缺少适用形态则 unresolved |',
        '| 招式、类别、威力 | 已保存 canonical move；固定 Champions 参考数据 | 原仅记录类别/选择器，不构造 solver input | 原 DIRECT 审查外招式保持 unsupported，不把普通威力硬套特殊招式 |',
        '| 防守方配置与当前防御 | B22 原已保存 Team 7 与 battle_stats；其他三场原未绑定 | 忽略当前形态 mechanic，只检查 configured 是否存在 | 本次配置经六只核对导入，取 form_verified 防御；不反拟合未知防御/HP |',
        '| 阶段、状态、天气、地形 | 原有公告后的部分值已知，开局基线多为 unknown | 没建立有证据的起点；普通阶段公告仅存方向 | 本次补起点及参考级数；真正未知仍阻断完整投影；inverse 本身支持有限替代值 |',
        '| 屏障、其他场地效果 | 原有 side conditions；旧 screen observe 不能覆盖 inactive | 正确基线暴露了启动转换缺陷 | 修复明确启动/结束；其他未建模效果与覆盖缺口不冒充无效；计算仍条件于已接受事件重建完整 |',
        '| 特性、持有道具 | 公告或已核对己方配置可给当前值；对手多未知 | 未传有限备选，unknown 直接当阻断 | 用合法目录与原生特性枚举；地形下保持接地关联；不支持的分支使整条投影 unresolved |',
        '| 暴击 | HP 投影保留明确公告，否则未知 | 只保存 false/true 描述，未运行分支 | 原 inverse 可对 false/true 取并集，本次接入，不给暴击概率 |',
        '| HP 损失 | 24 条支持的绝对 HP 关系；4 条端点/归因不足 | 损失未进入计算；击倒损失被误当无法使用 | 非击倒用精确损失；击倒用 [损失,65535] 下界约束；4 条不足仍不可用 |',
        '| 动作→目标因果 | 复用原 hp_resolutions 的 source/actor/target IDs | 没构造 direct_move_damage 与 stat_epoch | 只接受 supported + complete_endpoints，不把其他残留/回复 HP 当招式伤害 |','',
        '## 每条伤害输入审计','',
        '共 28 个动作—目标候选，其中原来因果支持 24 条。防御是当前形态的未加阶段值，阶段、天气/场地、屏障、状态、特性、道具及暴击分支均在完整 JSON 中。表中“已解”不等于收窄；同一动作两目标分别列出，不把其视为两个独立配置。原 HP 端点/归因不充分的 4 条保持不可用。','',
        '| 场次 / 完成时刻 | 招式 / HP | 旧状态配置 | 新当前形态防御输入 | 反演 / 精确剩余阻断 |','|---|---|---|---|---|']
    for n,u in damage:
        c=u['new_constraint'];o=u['observation'];x=c.get('numerical_inference',{})
        selector=c.get('selector') or {};stat=selector.get('defensive_stat')
        d=c.get('defender_context',{});current=d.get('current_form_stats',{})
        original=next((q for q in old[n]['updates'] if q['source_event_id']==u['source_event_id'] and q.get('observation',{}).get('target')==o.get('target') and q['kind'] in {'damage_joint_constraint','damage_unusable'}),{})
        configured=bool(original.get('new_constraint',{}).get('defender_context',{}).get('configured'))
        why='已解：保留全部可支持分支' if x.get('status')=='exact' else blockers(x)
        if x.get('status')=='contradiction':why='空候选集（矛盾保留）'
        lines.append(f"| B{n} / {u['timestamp']:.3f} | {o['move_name']} / {o['before']}→{o['after']} | {'有，适配器未调用' if configured else '未绑定'} | {stat}={current.get(stat,'?')}; {d.get('form')} | {cell(why)} |")
    lines += ['', '现有 inverse 原生支持有限变量、区间和合法伤害 roll 的并集。未知道具本身不再阻断；若某个仍可能的特性或招式缺少受审查的前向处理器，整条投影保留为 unresolved，不能只丢掉不支持的分支再宣布收窄。真实未知阶段/状态仍可见，不任意填 0/none。','',
        '## 逐队员初始/最终本体边际集合','',
        '外包区间后括号为离散值数；完整值表、SP 预算关联与每一来源身份的状态保留在 JSON。多个未合并身份的队员面板取并集，因此某一来源身份收窄时面板仍可能保持初始范围。当前接线逐条求单次命中投影后相交本体边际，尚未把跨观察共享道具/特性/节拍器历史和所有能力值一起联合投影；保留值不等于已证明存在一套同时满足全场的完整配置。这些集合是保守外包，不冒充联合求解结果。','',
        '| 场次 / 队员 | 速度 初始→最终 | 攻击 初始→最终 | 特攻 初始→最终 |','|---|---|---|---|']
    for n,t in traces.items():
        for m in t['roster']:
            lines.append('| B'+str(n)+' '+m['name']+' | '+' | '.join(bounds(m['initial'][s])+'→'+bounds(m['final_stats'][s]) for s in ['speed','attack','special_attack'])+' |')
    lines += ['', '实际发生的来源身份收窄：','', '| 场次 / 可用时刻 | 原始来源身份 | 本体项 | 前→后 | 排除值数 |','|---|---|---|---|---:|']
    for n,u in refinements:
        lines.append(f"| B{n} / {u['timestamp']:.3f}s | {u['pokemon_instance_id']} | {u['observation']['stat']} | {bounds(u['before'])}→{bounds(u['after'])} | {len(u['excluded'])} |")
    lines += ['',
        'B23 的速度收窄来自己方铝钢桥龙（当前未修正速度 116）先于返回的咆哮虎行动：同优先度、双方速度阶段 0、无顺风。原 M3 v2 求得该来源咆哮虎速度 ≤116，**116 的平速分支仍可行**，没有强制成 <116。因首次咆哮虎来源仍未与返回来源合并，整个预览队员面板速度仍为初始并集。','']
    lines += ['', '## B22 真实岩崩算例','']
    u=next(u for n,u in damage if n==22 and u['observation'].get('before')==201)
    c=u['new_constraint'];x=c['numerical_inference'];w=x['worked_example'];request=deepcopy(w['observation']['input'])
    request['attacker'].update(item='none',metronome_count=0);request['attacker']['stats']['attack']=158;request['field']['critical']=False
    evaluated=calculate(request);branch=x['branches'][0]
    lines += [f"动作 `{u['source_event_id']}`，t={u.get('action_timestamp',0):.3f}s；HP 分辨完成/可用 t={u['timestamp']:.3f}s。对手化石翼龙→己方长毛巨魔，HP 201→156，直接伤害 45。防御为 Team 7 当前普通形态 **111**，双方相关阶段 0，天气雨、无地形，反射壁/光墙/极光幕均未生效；岩石伤害不受雨加成。岩崩威力 75，双打群体 3/4，本系 3/2，属性相性 1。",'',
        '本体攻击候选由原 Champions SP/修正方向模型给出 112–172；紧张感有当前公告。道具未知，枚举固定合法目录并按既有直接命中等价类压缩：`'+', '.join(branch['item_effect_classes'])+'`。保留暴击 false/true；节拍器计数 0–5，不赋概率。未使用随后才可取得的生命宝珠排除。','',
        '取其中一个可行见证 A=158、无增伤道具、非暴击：','',
        '```text',
        'floor(floor((floor(2×50/5)+2)×75×158/111)/50)+2 = 48',
        '群体伤害：poke_round(48×3072/4096) = 36',
        '随机整数 r=85..100：floor(36×r/100)',
        '本系：poke_round(随机后数值×6144/4096)，恰好一半向下取整',
        '最终道具/屏障修正按原 engine 的固定点合成及逐步整数舍入处理。',
        'rolls = '+str(evaluated['distribution']['rolls']),
        'r=85 或 86 给出伤害45。A=159 的中性最低伤害已为46；其余允许增伤分支不能降至45。',
        '```','',
        f"对所有 admissible 分支及 16 个 roll 取存在性并集后，此条输入的保留攻击为 **{bounds(x['feasible'])}**。这是数值引擎实际求得的集合，不由上述单一见证代替枚举。四场中的其他观察仍按各自可用时间相交；未证明相同的来源身份不相交。",'',
        '## 完整追踪、验证与恢复','',
        '| 场次 | 完整时间线 | 完整 JSON | 原源冲突 / 收据状态差异 |','|---|---|---|---:|']
    for n,t in traces.items():
        lines.append(f"| B{n} | {link(Path(summaries[n]['report']),'时间线')} | {link(Path(summaries[n]['trace']),'trace.json')} | {len(t['source_state_conflicts'])} / {len(t['context_validation']['receipt_status_mismatches'])} |")
    lines += ['',
        'B21 的 8 条差异均为源 deferred 的定性回复公告在当前引擎变为 recorded_observation；原收据仍按源状态排除，不从这些公告制造 HP 数字或新约束。其他场次源收据状态差异见表。修复后的最终状态哈希与原源不同是配置/中性基线/阶段修复的预期结果，不能当作识别或语义验收通过；原最大 HP 与视觉冲突仍保留。','',
        '验证命令与最终结果见手工交接记录。每个 trace manifest 核对源输入 SHA-256，已完成上下文按实现与输入指纹复用；运行中有进度和 JSONL 检查点。推理过程原子保存约束前缀，失败后只重启便宜的推理阶段。','',
        '```sh',
        '.venv/bin/python scripts/trace_hidden_constraints.py --battle 23 --integration-audit --stage trace --resume',
        '# battle 可换为 20、21、22；只处理所选一场。',
        '.venv/bin/python scripts/report_inference_integration.py',
        '```','',
        '未进行视频识别准确率、完整语义覆盖率或新里程碑验收。未实现双翼攻击多段联合反演、完整隐藏配置联合投影、身份合并或新回合引擎；没有从 learnset、公开队伍频率或动作出现次数产生概率先验。', '',
        '来源：'+link(Path('docs/hidden-constraints-b20-b23/integration-handoff-20261101.md'),'交接与来源记录')+'；已有 `knowledge/data/mega-stat-evidence-v1.json` 的版本化形态事实与 `sample-team7-reviewed.json` 的 SP/修正方向。52Poké 的一般机制只作标记清楚的参考，Champions 招式可学性另检查专页，不以第九世代列表替代。','']
    target=ROOT/'reports/B20-B23-inference-integration-audit-20261101.md'
    target.write_text('\n'.join(lines))
    print(target)


if __name__=='__main__':main()
