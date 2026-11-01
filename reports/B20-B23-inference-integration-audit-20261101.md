# B20–B23 推理接线审计与定点修复（2026-11-01）

本报告只重放保存的已识别事件、身份与 HP 证据。原始识别、OCR、图标识别、生产 CLI、录像与历史基准未重跑或改写。旧追踪完整保留，新输出位于 `hidden-integration-20261101-v1`，每次实现指纹有独立子目录。未提交或推送。

“数值评估”表示完整纳入该次参考模型允许的分支；“收窄”只计实际排除至少一个原本体能力值的事件。原身份连续性未修复：不同 encounter ID 分开约束，队员面板对未解决身份取并集。这里的无条件只指对已列举道具、特性、暴击分支取并集，所有数值仍以固定 Champions 社区参考和保存识别重建成立为条件，不是独立游戏机制认证。

四场 Team 7 均已验证并接入；28 个候选均拿到已核对的当前形态防守数值。共恢复 30 条本地同周期关系，其中 5 个同有效优先度比较可数值使用；11 条伤害关系完成反演。真正排除值的事件为速度 1 次、攻击 5 次、特攻 1 次；新增空候选集 0 个。按未解决来源身份取并集后，队员面板速度 0 名、攻击 2 名、特攻 1 名收窄。

| 场次 | 旧候选 / 新认证同周期关系 | 已数值评估且支持同有效优先度的速度关系 | 速度收窄事件 | 已求解伤害关系 | 攻击 / 特攻收窄事件 | 新矛盾 |
|---|---:|---:|---:|---:|---:|---:|
| B20 | 18 / 10 | 4 | 0 | 1 | 1 / 0 | 0 |
| B21 | 24 / 5 | 0 | 0 | 1 | 0 / 1 | 0 |
| B22 | 26 / 5 | 0 | 0 | 6 | 2 / 0 | 0 |
| B23 | 34 / 10 | 1 | 1 | 3 | 2 / 0 | 0 |

## Team 7 与历史接入

逐张检查四场保存的完整己方预览，行序均为妙蛙花、喷火龙、大嘴鸥、烈咬陆鲨、长毛巨魔、铝钢桥龙。使用既有 exact-six 用户同配置政策、`attach_verified_profile`、`bind_attached_profile`、`initialize_team` 和 `form_stats`；没有用出场种类重合替代六只验证，也未合并源身份。正常采集修复重用既有己方名字区域、OCR 接口与实体解析器；本次诊断只使用人工核对的旧截图，不调用新识别。

| 场次 | 完整六只证据 / 可用时间 | 上次约束实验收到配置 | 本次绑定己方来源实例数 | 首跑记录 |
|---|---|---|---:|---|
| B20 | [预览原图](/Users/yyi/Pokemon-Champions-Assistant/.cache/battles/sample_battle_20/event-driven/fresh-b20-postfix-v1/frames/000015.png) / 7.002s | 否 | 3 | 原文件保留 |
| B21 | [预览原图](/Users/yyi/Pokemon-Champions-Assistant/.cache/battles/sample_battle_21/event-driven/fresh-b21-context-v1/frames/000036.png) / 17.520s | 否 | 5 | 原文件保留 |
| B22 | [预览原图](/Users/yyi/Pokemon-Champions-Assistant/.cache/battles/sample_battle_22/event-driven/fresh-b22-ditto-20261030-v1/frames/000059.png) / 29.005s | 是，但未进入反演 | 5 | 原文件保留 |
| B23 | [预览原图](/Users/yyi/Pokemon-Champions-Assistant/.cache/battles/sample_battle_23/event-driven/mega-b23-20261030-v1/frames/000031.png) / 15.003s | 否 | 4 | B23 sealed team_profile_linkage=unbound 保留；新诊断附件另列 |

[逐场图像 SHA-256、行序与开局证据](/Users/yyi/Pokemon-Champions-Assistant/docs/hidden-constraints-b20-b23/integration-review-20261101.json)
当前形态数值从既有 `battle_stats.current` 读取，不把配置的普通形态字段直接当 Mega 数值；Mega 烈咬陆鲨 Z 的防御 106、特防 105、速度 203 来自原 SP/修正方向与已验证形态计算。相关时刻实际使用的防御列在下表，复制数值仍不约束百变怪本体。绑定实例数包含未合并的再入场来源 ID，不表示实际选出了五只。

## 之前为何全为零

| 输入/断层 | 原因分类 | 修复及边界 |
|---|---|---|
| 未公告天气/场地、空间、顺风、屏障、初入场阶段、主要状态 | 1：源 StateEngine 未初始化 | 仅有保存预览→首次派出开局证据时建立中性基线；普通缺公告不清空已知事实；真实 coverage gap 使相关事实重新未知。无开局审查仍保持未知。 |
| 提高/降低后阶段变未知 | 1：原事件仅给方向、stages=None | 诊断参考解释完整中文公告：普通±1、大幅±2；上下限与增减仍由原 StateEngine 处理。默认未审查配置不改变。未识别完整公告或特殊继承仍未知。 |
| 光墙/反射壁启动被已知 inactive 拒绝 | 1：旧 parser 将启动标为 observe | 新解析为 start，旧保存公告按严格启动文本兼容；其他静态 observe 冲突仍保留。 |
| 己方配置未绑定、Mega 防御未进入伤害输入 | 2：采集/推理适配缺口 | 正常己方预览采集补齐；诊断经旧截图 exact-six 审查绑定；直接读取当前形态 battle_stats。 |
| 24 条伤害只生成条件关系 | 2：追踪器未调用反演器 | 接入原 infer_attack_stat，保留未知合法道具、原生特性、暴击、节拍器计数并集；击倒用伤害下界；地形下接地与道具/特性关联枚举。 |
| 102 个顺序候选被无条件标记 provisional | 2：没有认证接入 | 复用命令周期、既有 resolution_active_instance_ids 四原始机会和 end_of_turn_resolution_id；完整四行动且无内部边界/缺口才升级本地周期关系。不推断绝对回合号。 |
| 源状态在序列化丢失中性值 | 3：本次未发现 | 已覆盖 Fact/State round-trip，缺口位于初始化和读取，不归咎于序列化。 |
| 对手当前形态/原生特性、HP 阈值、未识别公告及未认证周期 | 4：证据或精确能力边界 | 未知保留；不从后续道具/形态公告倒填。多身份不相交；未知同优先度不强制严格大于，平速保留。 |

窄能力扩展：明确节拍器计数 0–5 的单次命中加成、一般宝石单次命中加成、紧张感对抗性树果的影响、已知阶段下若干不直接修改该次伤害的特性，以及臂锤已命中的直接伤害。均使用原伤害流程与固定对算参考；道具消费、臂锤降速与其他命中后效果继续属于原事件状态层。没有新增伤害计算器或防御/HP 联合引擎。

每一个旧追踪中未知的字段均有逐条审计（计数为字段，不是独立观测；分类 1/2/4 依次为源初始化/转换、适配/配置传播、仍未知，分类 3 本次未发现）：

| 场次 | 分类 1 / 2 / 4 | 逐字段旧值、新值、原因及事件 |
|---|---:|---|
| B20 | 50 / 6 / 9 | [modifier audit JSON](/Users/yyi/Pokemon-Champions-Assistant/.cache/battles/sample_battle_20/diagnosis/hidden-integration-20261101-v1/audits/modifiers-015342f1671951e2.json) |
| B21 | 102 / 15 / 9 | [modifier audit JSON](/Users/yyi/Pokemon-Champions-Assistant/.cache/battles/sample_battle_21/diagnosis/hidden-integration-20261101-v1/audits/modifiers-478b6f8bd3d07048.json) |
| B22 | 155 / 9 / 18 | [modifier audit JSON](/Users/yyi/Pokemon-Champions-Assistant/.cache/battles/sample_battle_22/diagnosis/hidden-integration-20261101-v1/audits/modifiers-96353e911e06decc.json) |
| B23 | 190 / 21 / 20 | [modifier audit JSON](/Users/yyi/Pokemon-Champions-Assistant/.cache/battles/sample_battle_23/diagnosis/hidden-integration-20261101-v1/audits/modifiers-3856c0737e2b64cf.json) |

## M3 输入合同对照

| 参数 | 保存状态/证据 | 原适配缺口 | 仍未知时的处理 / 求解能力 |
|---|---|---|---|
| 攻击者身份、当前形态 | 源 encounter ID 与 variant；部分仅 species-only | 没把可能形态、当前能力与本体 SP 对应关系送入求解 | 取兼容当前特性的固定目录形态并集；复制值不投影本体；缺少适用形态则 unresolved |
| 招式、类别、威力 | 已保存 canonical move；固定 Champions 参考数据 | 原仅记录类别/选择器，不构造 solver input | 原 DIRECT 审查外招式保持 unsupported，不把普通威力硬套特殊招式 |
| 防守方配置与当前防御 | B22 原已保存 Team 7 与 battle_stats；其他三场原未绑定 | 忽略当前形态 mechanic，只检查 configured 是否存在 | 本次配置经六只核对导入，取 form_verified 防御；不反拟合未知防御/HP |
| 阶段、状态、天气、地形 | 原有公告后的部分值已知，开局基线多为 unknown | 没建立有证据的起点；普通阶段公告仅存方向 | 本次补起点及参考级数；真正未知仍阻断完整投影；inverse 本身支持有限替代值 |
| 屏障、其他场地效果 | 原有 side conditions；旧 screen observe 不能覆盖 inactive | 正确基线暴露了启动转换缺陷 | 修复明确启动/结束；其他未建模效果与覆盖缺口不冒充无效；计算仍条件于已接受事件重建完整 |
| 特性、持有道具 | 公告或已核对己方配置可给当前值；对手多未知 | 未传有限备选，unknown 直接当阻断 | 用合法目录与原生特性枚举；地形下保持接地关联；不支持的分支使整条投影 unresolved |
| 暴击 | HP 投影保留明确公告，否则未知 | 只保存 false/true 描述，未运行分支 | 原 inverse 可对 false/true 取并集，本次接入，不给暴击概率 |
| HP 损失 | 24 条支持的绝对 HP 关系；4 条端点/归因不足 | 损失未进入计算；击倒损失被误当无法使用 | 非击倒用精确损失；击倒用 [损失,65535] 下界约束；4 条不足仍不可用 |
| 动作→目标因果 | 复用原 hp_resolutions 的 source/actor/target IDs | 没构造 direct_move_damage 与 stat_epoch | 只接受 supported + complete_endpoints，不把其他残留/回复 HP 当招式伤害 |

## 每条伤害输入审计

共 28 个动作—目标候选，其中原来因果支持 24 条。防御是当前形态的未加阶段值，阶段、天气/场地、屏障、状态、特性、道具及暴击分支均在完整 JSON 中。表中“已解”不等于收窄；同一动作两目标分别列出，不把其视为两个独立配置。原 HP 端点/归因不充分的 4 条保持不可用。

| 场次 / 完成时刻 | 招式 / HP | 旧状态配置 | 新当前形态防御输入 | 反演 / 精确剩余阻断 |
|---|---|---|---|---|
| B20 / 199.500 | Close Combat / 184→66 | 未绑定 | defense=106; pokeapi:pokemon:10309 | 已解：保留全部可支持分支 |
| B20 / 375.513 | Power Gem / 164→18 | 未绑定 | special_defense=132; pokeapi:pokemon:279 | pokeapi:species:970: attacker.ability / handler unavailable for Corrosion, Toxic Debris |
| B20 / 455.510 | Power Gem / None→152 | 未绑定 | special_defense=109; pokeapi:pokemon:1018 | direct absolute HP endpoints not supported |
| B21 / 186.515 | Wood Hammer / 201→6 | 未绑定 | defense=111; pokeapi:pokemon:861 | existing forward move handler unavailable |
| B21 / 237.523 | Grassy Glide / 18→0 | 未绑定 | defense=111; pokeapi:pokemon:861 | existing forward move handler unavailable |
| B21 / 250.008 | Ice Beam / None→168 | 未绑定 | special_defense=109; pokeapi:pokemon:1018 | direct absolute HP endpoints not supported |
| B21 / 311.002 | Wood Hammer / 164→0 | 未绑定 | defense=121; pokeapi:pokemon:279 | existing forward move handler unavailable |
| B21 / 477.030 | Ice Beam / 184→123 | 未绑定 | special_defense=105; pokeapi:pokemon:10309 | 已解：保留全部可支持分支 |
| B21 / 482.532 | Shadow Sneak / 123→83 | 未绑定 | defense=106; pokeapi:pokemon:10309 | existing forward move handler unavailable |
| B22 / 230.005 | Rock Slide / 164→72 | 有，适配器未调用 | defense=121; pokeapi:pokemon:279 | 已解：保留全部可支持分支 |
| B22 / 230.005 | Rock Slide / 184→132 | 有，适配器未调用 | defense=106; pokeapi:pokemon:10309 | 已解：保留全部可支持分支 |
| B22 / 385.532 | Rock Slide / None→178 | 有，适配器未调用 | defense=166; pokeapi:pokemon:1018 | direct absolute HP endpoints not supported |
| B22 / 452.010 | Rock Slide / 190→181 | 有，适配器未调用 | defense=166; pokeapi:pokemon:1018 | 已解：保留全部可支持分支 |
| B22 / 452.010 | Rock Slide / 201→156 | 有，适配器未调用 | defense=111; pokeapi:pokemon:861 | 已解：保留全部可支持分支 |
| B22 / 648.008 | Iron Head / 156→0 | 有，适配器未调用 | defense=111; pokeapi:pokemon:861 | 已解：保留全部可支持分支 |
| B22 / 714.520 | Dual Wingbeat / 72→27 | 有，适配器未调用 | defense=121; pokeapi:pokemon:279 | existing forward move handler unavailable |
| B22 / 724.522 | Hammer Arm / 194→150 | 有，适配器未调用 | defense=166; pokeapi:pokemon:1018 | 已解：保留全部可支持分支 |
| B22 / 817.005 | Hurricane / 68→31 | 有，适配器未调用 | special_defense=132; pokeapi:pokemon:279 | copied stats do not constrain native offense |
| B23 / 178.030 | Fake Out / 201→181 | 未绑定 | defense=111; pokeapi:pokemon:861 | 已解：保留全部可支持分支 |
| B23 / 261.510 | Flare Blitz / 181→97 | 未绑定 | defense=111; pokeapi:pokemon:861 | direct absolute HP endpoints not supported |
| B23 / 301.017 | Fake Out / 184→168 | 未绑定 | defense=106; pokeapi:pokemon:10309 | pokeapi:form:10202: attacker.ability / handler unavailable for Surge Surfer; pokeapi:form:10529: attacker.ability / handler unavailable for Electric Surge |
| B23 / 317.020 | Flare Blitz / 85→23 | 未绑定 | defense=111; pokeapi:pokemon:861 | 已解：保留全部可支持分支 |
| B23 / 441.508 | Focus Blast / 194→94 | 未绑定 | special_defense=109; pokeapi:pokemon:1018 | pokeapi:form:10202: attacker.ability / handler unavailable for Surge Surfer; pokeapi:form:10529: attacker.ability / handler unavailable for Electric Surge |
| B23 / 594.000 | Zap Cannon / 168→138 | 未绑定 | special_defense=105; pokeapi:pokemon:10309 | existing forward move handler unavailable |
| B23 / 681.015 | Focus Blast / 130→54 | 未绑定 | special_defense=109; pokeapi:pokemon:1018 | pokeapi:form:10202: attacker.ability / handler unavailable for Surge Surfer; pokeapi:form:10529: attacker.ability / handler unavailable for Electric Surge |
| B23 / 706.518 | Flare Blitz / 54→45 | 未绑定 | defense=166; pokeapi:pokemon:1018 | 已解：保留全部可支持分支 |
| B23 / 747.510 | Zap Cannon / 164→52 | 未绑定 | special_defense=132; pokeapi:pokemon:279 | existing forward move handler unavailable |
| B23 / 771.030 | Darkest Lariat / 45→15 | 未绑定 | defense=166; pokeapi:pokemon:1018 | existing forward move handler unavailable |

现有 inverse 原生支持有限变量、区间和合法伤害 roll 的并集。未知道具本身不再阻断；若某个仍可能的特性或招式缺少受审查的前向处理器，整条投影保留为 unresolved，不能只丢掉不支持的分支再宣布收窄。真实未知阶段/状态仍可见，不任意填 0/none。

## 逐队员初始/最终本体边际集合

外包区间后括号为离散值数；完整值表、SP 预算关联与每一来源身份的状态保留在 JSON。多个未合并身份的队员面板取并集，因此某一来源身份收窄时面板仍可能保持初始范围。当前接线逐条求单次命中投影后相交本体边际，尚未把跨观察共享道具/特性/节拍器历史和所有能力值一起联合投影；保留值不等于已证明存在一套同时满足全场的完整配置。这些集合是保守外包，不冒充联合求解结果。

| 场次 / 队员 | 速度 初始→最终 | 攻击 初始→最终 | 特攻 初始→最终 |
|---|---|---|---|
| B20 姆克鹰 | 108–167 (58)→108–167 (58) | 126–189 (62)→137–166 (30) | 63–112 (49)→63–112 (49) |
| B20 喷火龙 | 108–167 (58)→108–167 (58) | 93–149 (56)→93–149 (56) | 116–177 (60)→116–177 (60) |
| B20 烈咬陆鲨 | 109–169 (60)→109–169 (60) | 135–200 (64)→135–200 (64) | 90–145 (55)→90–145 (55) |
| B20 风妖精 | 122–184 (62)→122–184 (62) | 78–130 (52)→78–130 (52) | 87–141 (54)→87–141 (54) |
| B20 晶光花 | 95–151 (56)→95–151 (56) | 67–117 (50)→67–117 (50) | 135–200 (64)→135–200 (64) |
| B20 爱管侍 | ?→? | ?→? | ?→? |
| B21 姆克鹰 | 108–167 (58)→108–167 (58) | 126–189 (62)→126–189 (62) | 63–112 (49)→63–112 (49) |
| B21 雷丘 | 117–178 (60)→117–178 (60) | 99–156 (57)→99–156 (57) | 99–156 (57)→99–156 (57) |
| B21 轰擂金刚猩 | 94–150 (56)→94–150 (56) | 130–194 (64)→130–194 (64) | 72–123 (51)→72–123 (51) |
| B21 赛富豪 | 93–149 (56)→93–149 (56) | 72–123 (51)→72–123 (51) | 137–203 (65)→137–203 (65) |
| B21 苍炎刃鬼 | 94–150 (56)→94–150 (56) | 130–194 (64)→130–194 (64) | 72–123 (51)→72–123 (51) |
| B21 美纳斯 | 90–146 (56)→90–146 (56) | 72–123 (51)→72–123 (51) | 108–167 (58)→117–143 (27) |
| B22 百变怪 | 61–110 (49)→61–110 (49) | 61–110 (49)→61–110 (49) | 61–110 (49)→61–110 (49) |
| B22 勾魂眼 | 63–112 (49)→63–112 (49) | 85–139 (54)→85–139 (54) | 76–128 (52)→76–128 (52) |
| B22 铝钢桥龙 | 94–150 (56)→94–150 (56) | 112–172 (60)→112–172 (60) | 130–194 (64)→130–194 (64) |
| B22 化石翼龙 | 135–200 (64)→135–200 (64) | 112–172 (60)→112–172 (60) | 72–123 (51)→72–123 (51) |
| B22 巨金怪 | 81–134 (53)→81–134 (53) | 139–205 (66)→139–205 (66) | 103–161 (58)→103–161 (58) |
| B22 狠辣椒 | 85–139 (54)→85–139 (54) | 115–176 (60)→115–176 (60) | 115–176 (60)→115–176 (60) |
| B23 雷丘 | 117–178 (60)→117–178 (60) | 99–156 (57)→99–156 (57) | 99–156 (57)→99–156 (57) |
| B23 轰擂金刚猩 | 94–150 (56)→94–150 (56) | 130–194 (64)→130–194 (64) | 72–123 (51)→72–123 (51) |
| B23 火神蛾 | 108–167 (58)→108–167 (58) | 72–123 (51)→72–123 (51) | 139–205 (66)→139–205 (66) |
| B23 炽焰咆哮虎 | 72–123 (51)→72–123 (51) | 121–183 (62)→121–145 (25) | 90–145 (55)→90–145 (55) |
| B23 赛富豪 | 93–149 (56)→93–149 (56) | 72–123 (51)→72–123 (51) | 137–203 (65)→137–203 (65) |
| B23 烈咬陆鲨 | 109–169 (60)→109–169 (60) | 135–200 (64)→135–200 (64) | 90–145 (55)→90–145 (55) |

实际发生的来源身份收窄：

| 场次 / 可用时刻 | 原始来源身份 | 本体项 | 前→后 | 排除值数 |
|---|---|---|---|---:|
| B20 / 199.500s | sample_battle_20:opponent:encounter:33c958b45c7ec610 | attack | 126–189 (62)→137–166 (30) | 32 |
| B21 / 477.030s | sample_battle_21:opponent:encounter:4adb8c1aecada18d | special_attack | 108–167 (58)→117–143 (27) | 31 |
| B22 / 452.010s | sample_battle_22:opponent:encounter:9a2e99a27bfb75ce | attack | 112–172 (60)→112–158 (47) | 13 |
| B22 / 724.522s | sample_battle_22:opponent:encounter:1efc511d2d254d17 | attack | 139–205 (66)→170–205 (35) | 31 |
| B23 / 178.030s | sample_battle_23:opponent:encounter:c11de1e8665ea33e | attack | 121–183 (62)→121–145 (25) | 37 |
| B23 / 613.503s | sample_battle_23:opponent:encounter:fc33d523176fa46c | speed | 72–123 (51)→72–116 (45) | 6 |
| B23 / 706.518s | sample_battle_23:opponent:encounter:fc33d523176fa46c | attack | 121–183 (62)→121–138 (18) | 44 |

B23 的速度收窄来自己方铝钢桥龙（当前未修正速度 116）先于返回的咆哮虎行动：同优先度、双方速度阶段 0、无顺风。原 M3 v2 求得该来源咆哮虎速度 ≤116，**116 的平速分支仍可行**，没有强制成 <116。因首次咆哮虎来源仍未与返回来源合并，整个预览队员面板速度仍为初始并集。


## B22 真实岩崩算例

动作 `event:054f71a42009bf3956b8f270`，t=440.007s；HP 分辨完成/可用 t=452.010s。对手化石翼龙→己方长毛巨魔，HP 201→156，直接伤害 45。防御为 Team 7 当前普通形态 **111**，双方相关阶段 0，天气雨、无地形，反射壁/光墙/极光幕均未生效；岩石伤害不受雨加成。岩崩威力 75，双打群体 3/4，本系 3/2，属性相性 1。

本体攻击候选由原 Champions SP/修正方向模型给出 112–172；紧张感有当前公告。道具未知，枚举固定合法目录并按既有直接命中等价类压缩：`Air Balloon, Expert Belt, Hard Stone, Iron Ball, Leftovers, Life Orb, Metronome, Muscle Band, Sitrus Berry, White Herb, none`。保留暴击 false/true；节拍器计数 0–5，不赋概率。未使用随后才可取得的生命宝珠排除。

取其中一个可行见证 A=158、无增伤道具、非暴击：

```text
floor(floor((floor(2×50/5)+2)×75×158/111)/50)+2 = 48
群体伤害：poke_round(48×3072/4096) = 36
随机整数 r=85..100：floor(36×r/100)
本系：poke_round(随机后数值×6144/4096)，恰好一半向下取整
最终道具/屏障修正按原 engine 的固定点合成及逐步整数舍入处理。
rolls = [45, 45, 46, 46, 48, 48, 48, 49, 49, 49, 51, 51, 51, 52, 52, 54]
r=85 或 86 给出伤害45。A=159 的中性最低伤害已为46；其余允许增伤分支不能降至45。
```

对所有 admissible 分支及 16 个 roll 取存在性并集后，此条输入的保留攻击为 **112–158 (47)**。这是数值引擎实际求得的集合，不由上述单一见证代替枚举。四场中的其他观察仍按各自可用时间相交；未证明相同的来源身份不相交。

## 完整追踪、验证与恢复

| 场次 | 完整时间线 | 完整 JSON | 原源冲突 / 收据状态差异 |
|---|---|---|---:|
| B20 | [时间线](/Users/yyi/Pokemon-Champions-Assistant/reports/battles/sample_battle_20/diagnosis/hidden-integration-20261101-v1/trace-45cd17a5c6d27cf8.md) | [trace.json](/Users/yyi/Pokemon-Champions-Assistant/.cache/battles/sample_battle_20/diagnosis/hidden-integration-20261101-v1/traces/45cd17a5c6d27cf8/trace.json) | 13 / 0 |
| B21 | [时间线](/Users/yyi/Pokemon-Champions-Assistant/reports/battles/sample_battle_21/diagnosis/hidden-integration-20261101-v1/trace-caef77ef5352d093.md) | [trace.json](/Users/yyi/Pokemon-Champions-Assistant/.cache/battles/sample_battle_21/diagnosis/hidden-integration-20261101-v1/traces/caef77ef5352d093/trace.json) | 2 / 8 |
| B22 | [时间线](/Users/yyi/Pokemon-Champions-Assistant/reports/battles/sample_battle_22/diagnosis/hidden-integration-20261101-v1/trace-55fab5974892884e.md) | [trace.json](/Users/yyi/Pokemon-Champions-Assistant/.cache/battles/sample_battle_22/diagnosis/hidden-integration-20261101-v1/traces/55fab5974892884e/trace.json) | 2 / 0 |
| B23 | [时间线](/Users/yyi/Pokemon-Champions-Assistant/reports/battles/sample_battle_23/diagnosis/hidden-integration-20261101-v1/trace-620764d13e957a59.md) | [trace.json](/Users/yyi/Pokemon-Champions-Assistant/.cache/battles/sample_battle_23/diagnosis/hidden-integration-20261101-v1/traces/620764d13e957a59/trace.json) | 1 / 0 |

B21 的 8 条差异均为源 deferred 的定性回复公告在当前引擎变为 recorded_observation；原收据仍按源状态排除，不从这些公告制造 HP 数字或新约束。其他场次源收据状态差异见表。修复后的最终状态哈希与原源不同是配置/中性基线/阶段修复的预期结果，不能当作识别或语义验收通过；原最大 HP 与视觉冲突仍保留。

验证命令与最终结果见手工交接记录。每个 trace manifest 核对源输入 SHA-256，已完成上下文按实现与输入指纹复用；运行中有进度和 JSONL 检查点。推理过程原子保存约束前缀，失败后只重启便宜的推理阶段。

```sh
.venv/bin/python scripts/trace_hidden_constraints.py --battle 23 --integration-audit --stage trace --resume
# battle 可换为 20、21、22；只处理所选一场。
.venv/bin/python scripts/report_inference_integration.py
```

未进行视频识别准确率、完整语义覆盖率或新里程碑验收。未实现双翼攻击多段联合反演、完整隐藏配置联合投影、身份合并或新回合引擎；没有从 learnset、公开队伍频率或动作出现次数产生概率先验。

来源：[交接与来源记录](/Users/yyi/Pokemon-Champions-Assistant/docs/hidden-constraints-b20-b23/integration-handoff-20261101.md)；已有 `knowledge/data/mega-stat-evidence-v1.json` 的版本化形态事实与 `sample-team7-reviewed.json` 的 SP/修正方向。52Poké 的一般机制只作标记清楚的参考，Champions 招式可学性另检查专页，不以第九世代列表替代。
