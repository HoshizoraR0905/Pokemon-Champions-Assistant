# B22 首次生产基准：百变怪 / 变身者 / 变身

2026-10-30。**首次运行与封存完成，变身语义未通过验收。** 两次变身结果均已被 OCR 清楚读出，但解析为 unknown、未进入事件流。能力激活回执被接受，最终状态却没有任何百变怪变身记录。第二次入场分配了新的 encounter ID，持续身份只保留“可能关联”，没有恢复同一持久实例。

补充可见 Battle Log 的逐次核对：**消息记录复现率 100/104＝96.15%**；20条数值HP行单列，原始有序端点保留 **18/20＝90.00%**，结算组精确对应 **16/20＝80.00%**。这些均为可见参考行的局部结果，不是整场准确率或完整状态复现率。

本次没有修改生产解析器、身份处理、StateEngine、伤害、OCR、采样或性能代码，没有重跑全视频、提交或推送。原有工作区修改保留。

## 首次运行指标

| 项目 | 原始结果 |
|---|---:|
| 输入 | `tests/fixtures/sample_battle_22.mp4` |
| 容器视频时长 | 860.18 秒 |
| 外部生产 CLI wall | **850.076456 秒** |
| PTR：wall / 视频时长 | **0.988254 秒/视频秒** |
| 源帧数：容器头 / 实际解码 | 33,158 / 33,158 |
| 2 FPS 采样 / 详细识别帧 | 1,721 / 1,697 |
| OCR 底层调用 | 6,333 |
| 图标底层调用 / 高层 preview 请求 | 12 / 6 |
| StateEngine replay | 387.361054 秒，已包含在 CLI wall 中 |
| 独立 HP 投影 | 0.233800 秒，不包含在 CLI wall 中 |
| 事件 / 回执 | 2,212 / 2,212 |
| 回执状态 | 2,137 applied_candidate；28 applied_partial；35 recorded_observation；12 deferred |
| 冲突 | 3：2 maximum_hp_disagreement；1 ability visual_fact_disagreement |
| HP 结算组 | 22；完整端点 16；程序标为 supported 16、ambiguous 6 |
| 非零数值 HP 段 | 45；投影成员恰好出现一次；unmapped_changes=0 |

采样为正常 2 FPS；详细识别调度仍独立，其中部分帧走原有 1 FPS 调度。没有提高采样或增加定向高帧率处理。生产 summary 的 `video_duration=860.011667` 是最后采样时间，PTR 使用容器完整时长 860.18，未混用分母。`reconstructed_event_count=128` 是生产分类计数，不能当作独立验证的真实事件数；2,212 条中包括 2,068 条 HUD 观察。

12 条延期均是 `message_episode_occupancy_unresolved`，发生于 28.505、107.502–109.002 和 653.027–653.510 秒，不是变身失败计数。两次变身缺失均未产生 deferred 回执，不能用低延期数判断支持情况。三处冲突分别在 664.512、670.513、793.000 秒，未证明是百变怪引起，不归因到变身。

完整 run：`fresh-b22-ditto-20261030-v1`。外部命令为：

```sh
.venv/bin/python scripts/run_fresh_video_benchmark.py \
  --battles sample_battle_22 --run-id fresh-b22-ditto-20261030-v1
```

仅一次未中断生产尝试，lightweight，fresh namespace；没有 frame_cache、recognition_caches 或 recognition_stage_source 输入，只复用共享固定模型/知识/图标资产。输入 SHA256：`fbe9424827e02589d1e7a67d8e582006638e76771fafe90bca56ac42fdb32c23`。

## 封存与独立参考顺序

生产结束后于 **2026-10-30 15:49:56（北京时间）**完成 `initial-freeze.json`。11,574 个文件涵盖原始保存帧、OCR/图标读数、观察、源码身份哈希、事件、回执、BattleState、HP 投影及执行记录；核验后才开始该场差异审查。未回写这些预测。

随后先只按 UI overlay 分类定位并视觉检查全部 **44 张保存日志帧**，覆盖四段显示窗口：402.002–411.503、458.510–460.012、605.502–609.003、770.030–775.530 秒。按滚动重叠去重，固定 **124 条可读参考行**，之后才读取生产事件/回执内容。参考保留原图路径、哈希、source ID、观察时间和可见回合号。部分边缘行截断，未补写；第1–8回合也不宣称完整。

- [独立转录文本](log-transcription.txt)、[逐行参考与原图证据](log-reference.json)。这是 Codex 视觉转录，**未经人类复核**。
- 参考中 original_event_time 保持 null，日志查看时间不是原事件时间。
- `diagnosis/log-text-candidates.json` 提供去空白/标点后的精确文字候选，重复文本可能匹配多个回合；它不是逐发生次数的语义对齐或准确率。数值 HP 行需要另按实例与端点核对。
- 首版只给百变怪相关对照；现补充下面的逐次消息记录与HP核对，不把局部日志当作全场真值。

原生产 [viewer](../../reports/battles/sample_battle_22/event-driven/fresh-b22-ditto-20261030-v1/review.html) 保持封存状态。

## 可见 Battle Log 的局部复现率（补充）

固定参考124行分为 **104条语义消息、20条数值HP**。按参考顺序逐次核对封存生产回执；重复消息不能跨发生次数复用，同一双入场行必须匹配两条send_out。排除entry/HUD观察，接受applied_candidate、applied_partial和recorded_observation；100条匹配行共对应102条回执。

| 参考分类 | 已有对应记录 / 参考行 | 比例 |
|---|---:|---:|
| 招式执行 | 24 / 24 | 100.00% |
| 变身者触发后的变身结果 | 0 / 2 | 0.00% |
| 紧张感禁止食用树果通知 | 0 / 2 | 0.00% |
| 其余消息记录 | 76 / 76 | 100.00% |
| **消息记录合计** | **100 / 104** | **96.15%** |

按可见回合号分组为：第1回合17/18，第2回合9/10，第3回合12/12，第4回合10/10，第5回合12/12，第6回合10/11，第7回合12/12，第8回合18/19。不宣称各回合参考完整，也未独立标注原视频回合边界；这些分组不等于精确回合归属正确率。

四条缺失均已被保存OCR读出，occurrence为unknown、emitted=False：

- 第1、6回合“我方因太紧张而无法食用树果！”：142.523、555.510秒。
- 第2、8回合“对手的百变怪变身成了烈咬陆鲨/大嘴鸥！”：314.520、767.030秒。

**96.15%衡量消息记录复现，不是逐字段完整语义正确率。** 除文字归一化外，逐行审查了事件种类、侧别、主体/接收者及招式、能力、道具激活、阶段方向、场地变化和命中次数等已有结构字段。两个进化石反应通知虽有已接受记录，却没有结构化进化石身份；烈咬陆鲨的Z形态绑定仍未解决。因此这里没有把100条称为全部字段正确，也不能与B21报告的“完整语义行”指标直接等同。revelation-only和观察回执也不能证明招式效果、复制状态或持久身份正确；两次百变怪变身状态验收仍是0/2。未展示的预测没有完整参考，未计算precision或整场复现率。

| 数值HP口径 | 结果 | 限制 |
|---|---:|---|
| 同一encounter、对应动作区间内的原始有序端点 | 18 / 20＝90.00% | 可含动画中间值，不证明稳定结算或原因正确 |
| before/after/单位完全对应的结算组 | 16 / 20＝80.00% | 不将合并两击的总量当成逐击复现 |
| 上述精确组有完整稳定端点标记 | 13 / 20＝65.00% | 是程序端点判定 |
| 上述精确组被程序标为supported | 13 / 20＝65.00% | 不是独立因果正确率 |

两条原始端点不完整：第3回合我方铝钢桥龙194→178，首次HUD只读到188；第6回合回归化石翼龙100%→43%，新encounter首次只读到47%，不借用此前encounter的100%。另两条第8回合大嘴鸥72→51、51→27均保留原始端点，但投影合并为72→27，不能算两条逐击精确结算。第5回合铝钢桥龙193→194、第8回合大嘴鸥27→68及铝钢桥龙150→162虽有精确组，程序未标完整稳定端点，故后两项分母中仍保留、分子不计。

逐行回执、缺失occurrence、HP端点事件ID和封存输入哈希见 [log-score.json](log-score.json)。运行 `.venv/bin/python docs/b22-ditto/score.py` 可复核：校验三个评分输入和原参考封存哈希、124行分区完整、回执不复用且顺序一致、双入场成员数、消息种类/文字/接受状态，以及同实例动作区间内的HP端点。仅生成评分文件，不解码、不调用OCR、不重放或回写生产结果；本次复核通过。

## 槽位约定：固定对位前需要换算

现有 `recognition/event_schedule.py:106` 明确将槽位定义为 **screen-HUD left/right**；`recognition/event_report.py:123` 把 `opponent_active_1` 写为 `slot=left`。任务给定的固定对位则以两侧相对站位表示。报告以我方 HUD 左右为基准，将对手屏幕 HUD 左卡换算为规则的 `opponent.right`，右卡换算为 `opponent.left`：

| 屏幕 HUD 坐标（原封存字段） | 本报告规则坐标 |
|---|---|
| self.left / self.right | self.left / self.right |
| opponent.left / opponent.right | opponent.right / opponent.left |

这是诊断中的坐标归一化，**没有更改原状态字段**。两次百变怪均占对手左侧 HUD 卡，原状态均记 `opponent.left`；换算为规则 `opponent.right` 后，固定指向 `self.left`，与变身文本和画面一致。若将用户的交叉映射直接用于仓库未经换算的 HUD 字段，第一次会错误选到大嘴鸥，第二次会错误选到铝钢桥龙。后续实现必须明确坐标边界，不能因此引入随机选目标或静默改写全部既有槽位。

## 第一次入场与变身：复制烈咬陆鲨

| 核对项 | 证据及冻结结果 |
|---|---|
| 入场 | **307.018 秒**，“Tickle wikle 派出了百变怪！”；帧 `000609.png` |
| 原始实例 | `sample_battle_22:opponent:encounter:953d14c88dcaadc1`，下称 D1；original_identity 与 species 均为百变怪 |
| 槽位 | 对手左 HUD 卡；原状态 opponent.left；规则 opponent.right |
| 触发 | **311.035 秒**，百变怪/变身者能力横幅；`000617.png`；回执 `event:0dd2d6ef0402ad94e903be43` accepted/applied_candidate |
| 固定目标 | 规则 opponent.right → self.left；我方当时是烈咬陆鲨，实例 `sample_battle_22:self:encounter:c812d2333b451851` |
| 结果 | **314.520–315.520 秒**连续三帧：“对手的百变怪 / 变身成了烈咬陆鲨！”；`000624–000626.png`；3D 外形从百变怪变为与对位目标一致的超级形态 |
| HUD 名称 | 318.020 秒 `000631.png` 仍写“百变怪”，图标也是百变怪；外形复制不代表 HUD 名称一定更换 |
| parser / admission | OCR 置信度 0.9988；三次均为 unknown；occurrence `event:27dce19f643c5d8985386b6d` 的 emitted=False；没有 transformation 事件或回执 |
| 实例是否存续 | 这次变身前后 D1 存续，没有创建“对手烈咬陆鲨”实例，也未与我方真实烈咬陆鲨合并；但没有任何临时变身状态 |
| HP / 道具 | D1 保存自身 100%→22%，最大 HP/绝对 HP 未知；没有复制目标的 132/184。D1 item.identity 仍 unknown，没有证据确认其具体持有物，也没有把目标进化石复制过去 |
| 复制属性 | D1 的 transformations=[]、current_types unknown、known_slots={}、pp={}；ability.current 仍为激活时的变身者，没有复制目标能力/非HP能力值/阶段快照或引用 |
| 后续行动 | 367.512、436.507、500.518 秒三次龙之波动均绑定 D1，applied_partial/move_revelation_only；仅保存执行记录，未建立复制招式集或 PP。不能把 executed 列表当作确定招式槽 |
| 阶段变化 | 512.520 秒“对手的百变怪的特攻降低了！”被接受，D1 留有变化历史；这不证明初始复制阶段已建模。换下后当前阶段失效为 unknown，未凭空补中性阶段 |

[首次变身源图](../../.cache/battles/sample_battle_22/event-driven/fresh-b22-ditto-20261030-v1/frames/000624.png)。独立日志第2回合有“派出了百变怪”“百变怪的变身者”“变身成了烈咬陆鲨”；前两项有生产回执，最后一项完全缺失。第3–5回合仍以百变怪名称执行龙之波动，与原始身份保持一致，不应按显示外形创建新个体。

目标形态另有必须保留的限制：日志可见“烈咬陆鲨进化石Z”和复制后的外形，而结果消息只写“烈咬陆鲨”。生产此前 208.002 秒把目标 Mega 绑定为 `pokeapi:pokemon:10058`。52Poké 区分普通 Mega 与Ｚ形态；本次不把这个旧 canonical 绑定当作Ｚ形态已正确识别的证明，也不据此套用普通 Mega 的能力/数值。该相邻形态问题未修复，未来复制应保留目标形态证据及未决状态。参见 [52Poké 烈咬陆鲨](https://wiki.52poke.com/index.php?title=烈咬陆鲨&oldid=2637261)。

## 换下与第二次入场：复制大嘴鸥

| 核对项 | 证据及冻结结果 |
|---|---|
| 换下 | **549.025 秒**，“Tickle wikle 换下了百变怪！”；`001082.png`；回执 `event:83d525a8764ba7fe457ac83b` 绑定 D1，applied_candidate；画面收回的是复制烈咬陆鲨后的外形 |
| 换下清除 | D1 进入 bench，HP 22% 保留；因从未创建变身状态，不能声称已正确清除变身/恢复自身能力与招式。只有原 species 一直为百变怪，造成表面上像已恢复 |
| 再入场 | **760.028 秒**，同一训练家“派出了百变怪！”；`001502.png`；762.028 秒 `001506.png` 再次是原百变怪外形 |
| 身份连续性 | 生产分配 `sample_battle_22:opponent:encounter:ada26cd86ace72ee`，下称 D2；basis=`new_entry_without_species_only_party_merge`；保留 possible_prior_instance_ids=[D1]，persistent_identity_status=unproven，并未断言是另一个生物个体 |
| 槽位 | 仍为对手左 HUD 卡；原字段 opponent.left；规则 opponent.right |
| 触发 | **763.528 秒**，变身者横幅；`001509.png`；回执 `event:f1cc94501018f2e2f66d006d` 绑定 D2，applied_candidate |
| 固定目标 | 规则 opponent.right → self.left；此时为我方大嘴鸥，当前 encounter `sample_battle_22:self:encounter:cddd4f82f09160aa`；不是另一槽的铝钢桥龙 |
| 结果 | **767.030–768.030 秒**三帧“对手的百变怪 / 变身成了大嘴鸥！”；`001516–001518.png`；3D 外形为大嘴鸥；769.030 秒左 HUD 卡仍名“百变怪” |
| parser / admission | OCR 0.997143–0.997714；均 unknown；occurrence `event:6a234642fd9a8feac555abf8` emitted=False；没有 transformation 事件或回执 |
| HP / 道具 | D2 的首个自身 HP 读数仍是22%，未复制我方大嘴鸥68/164；D2 item.identity unknown。D1 的22%与D2的22%分别保存，没有统一持久HP/道具历史 |
| 复制属性 | transformations=[]；types unknown；复制招式槽、PP、非HP能力/阶段快照或目标引用全缺失；ability.current 仍为变身者，没有表示复制后的能力。目标在660.012秒有降雨激活证据，793秒详情观察另引起能力冲突，不能将后来的争议反向当作先前复制时已确定的值 |
| 行动及结局 | **811.003 秒**百变怪使出暴风，绑定D2，applied_partial；**838.508 秒**百变怪倒下，绑定D2，applied_candidate。D2最终0%，D1仍在bench且22%。没有观察到第二次变身后的再次换下 |

[第二次变身源图](../../.cache/battles/sample_battle_22/event-driven/fresh-b22-ditto-20261030-v1/frames/001516.png)。独立日志第6回合确认换下百变怪，第8回合确认再入场、变身者及变成大嘴鸥。日志与HUD22%支持这条回归链，但当前生产策略只作候选连续性关联；不能把两个 encounter 当作已验证的两个队伍成员。恢复同一持久实例需要利用有来源的队伍/回归连续性证据，不能全局放宽为同种必合并。

本录像核对到的两次都是 **Imposter**，没有观测到手动使用 **Transform**；后者的目标解析与队友目标支持未获本片验证，不能用本次固定对位结果代替它的验收。

## 第一个失败及下游影响

1. **能力应用缺少变身后果。** 311.035 秒变身者被当作普通能力激活接受；没有目标实例引用和复制状态。变身结果在314.520秒可见后，缺失仍持续。
2. **明确的 parser → occurrence 丢失。** `battle_events/parser.py:238` 的 transformation 分支只处理“超级进化成了”；“变身成了”未支持。`recognition/message_occurrences.py:61` 要求所有解析类型非unknown才发出事件。因此高置信度文本未进入StateEngine，并不留下deferred；第二次同样失败。不是漏OCR、低置信度或目标随机性。
3. **现有状态处理不足以直接复用 Mega 逻辑。** `PokemonState` 已有 original_identity、species/current_variant、transformations、volatile、mechanics、HP/item/ability/moves/stages，无需新建一套状态架构。`StateEngine._transform` 当前替换species/current_variant并留历史，未实现临时复制目标、招式PP、能力/阶段/非HP数值引用或换下恢复；简单把新消息接入此分支仍不完整。
4. **入场 episode 与持久身份未统一。** `StateEngine._resolve:273–299` 在未验证完整party且缺少独立连续性证据时，为同种回归分配新encounter；这不是变身时直接创建复制物种，但760.028秒使本场百变怪历史分裂。D1三次龙之波动与D2暴风、HP变化及最后倒下分属两个记录。化石翼龙、巨金怪和我方大嘴鸥也有同类候选回归拆分，说明是既有通用策略边界，不应全归咎于Ditto。

没有看到“百变怪变成真实目标实例”或跨侧合并。当前实际的静默错误是：**临时变身完全缺席，回执仍大多接受；回归身份只作候选关联，最终视图可能同时显示一个22%后备百变怪和一个倒下的百变怪。** HP组被标supported也只代表当前程序的归因条件，不能证明变身形态、目标能力或伤害输入正确。

## 最小修复提案（未实施）

1. 扩展既有解析/occurrence路径，分别保留变身者激活、显式变身结果和手动“使出了变身”；同一次变身的横幅/结果只应用一次，有来源关联。仅入场且无激活不能推定变身或柔软。Imposter经明确槽位换算使用用户固定映射；Transform使用实际观察目标，允许己方目标，目标缺失保持未决。
2. 在既有 PokemonState 的 transformation/mechanics/volatile 表达内扩展临时覆盖及历史，复用Fact与来源；保留original_identity、persistent ID、自己的HP/道具/等级。复制目标当时形态、属性、能力、非HP能力/阶段和招式的已知或不确定信息，不把目标后续变化作为活链接同步。招式PP初始化为min(5,适用最大PP)，不复制目标剩余PP；未知槽保持未知，不猜IV/EV/性格/数值。变身期间观察的复制招式与自身长期招式证据要区分。
3. 复用现有入场episode/身份账本，将有独立证据的回归关联到原持久个体；不足时保留候选，不制造两个已确认生物个体。换下明确结束临时覆盖，保留自身HP/道具；下一次观察到激活时，按当前对位目标建立新快照。
4. 以本次冻结文本/事件和少量保存帧做局部回归：两次目标、同实例跨回归、自身HP/道具/等级保留、阶段与PP初始化、换下清除、无激活不推断、手动队友目标、去重/撤回，以及Mega既有行为。实施前先审核上述方案；无需整片试错或改动其他机制。

## 验证、出处与交接

已执行只读审计 [audit.py](audit.py)，通过：11,574个初始封存文件哈希、245个运行前生产Python源文件哈希、155个B16–B21既有manifest/seal/精简报告哈希；视频SHA一致；单次生产尝试；事件/回执数一致；正常采样与identity设置；无跨run识别输入；45个非零HP段恰好分组一次；两次高置信度unknown变身消息均未发出事件。

生产源未改，未新增实现测试或再跑全场StateEngine；这次验证不声明确定性重放一致性、整场识别准确率或语义覆盖。未做独立伤害计算、隐藏配置推断或全场状态真值标注。保存帧中收回动画未直接展示在bench还原外形；再次入场可见原百变怪，支持视觉还原，但程序清理机制仍未通过。

本次有范围地查阅52Poké的 [百变怪/Champions招式表](https://wiki.52poke.com/index.php?title=百变怪/Champions招式表&oldid=2608731) 与 [变身者](https://wiki.52poke.com/index.php?title=变身者（特性）&oldid=2561888)：前者列变身、PP12；后者有Champions说明及对位触发描述。自然可学招式不能用来否定变身后的龙之波动/暴风，也不能推断原始装备槽或概率。复制/保留规则按本任务明确给定规则审查；未引入其他世代的数值规则。检索日期2026-10-30，版本与适用范围见[rules-sources.json](rules-sources.json)。52Poké内容署名原贡献者，依CC BY-NC-SA 3.0；本次仅保存简短研究摘要，未导入运行时KnowledgeBase或新建爬虫。

持久输出：`.cache/battles/sample_battle_22/fresh-benchmark/fresh-b22-ditto-20261030-v1/`，其中`execution.json`、`initial-freeze.json`为首次计时/封存；`diagnosis/metrics.json`、`ditto-audit.json`、`log-reference-freeze.json`、`log-text-candidates.json`和`integrity.json`为独立诊断。源码运行前快照为`production-sources-before.tar.gz`。不要重跑生产命令；只读复核：

```sh
.venv/bin/python docs/b22-ditto/audit.py
```

本任务的基准与诊断已完成，后续变身实现等待单独授权。
