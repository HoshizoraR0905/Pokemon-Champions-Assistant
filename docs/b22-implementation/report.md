# B22：变身、持久身份和紧张感的定向实现

2026-10-30。授权范围内的实现与保存证据验证完成。两条变身结果、两条紧张感限制消息均从 `unknown / 未发出` 恢复为 `applied_candidate`；百变怪保留同一持久实例和两次入场 episode。**这是四条局部语义恢复，不是新的整场准确率或100%语义复现率。**

首次基准及原诊断保持不变，继续见 [原报告](../b22-ditto/report.md)。本次没有解码视频、调用OCR/图标、运行原生产CLI或修改伤害计算，没有提交或推送。

## 消息与状态结果

| 视频时间 | 原消息 | 修复前 | 修复后 |
|---|---|---|---|
| 142.523s | 我方因太紧张而无法食用树果 | unknown，未发出 | self侧 berry_consumption_prevention，原因unnerve，已接受 |
| 314.520s | 对手的百变怪变身成了烈咬陆鲨 | unknown，未发出 | transformation / transform，确认311.035s快照，不重复复制 |
| 555.510s | 我方因太紧张而无法食用树果 | unknown，未发出 | self侧同类限制，已接受 |
| 767.030s | 对手的百变怪变身成了大嘴鸥 | unknown，未发出 | 确认763.528s新快照，不重复复制 |

四条事件保留原 source ID、帧哈希和 occurrence ID，使用既有 MessageOccurrences 发出稳定事件ID。两个紧张感限制分别关联当时独立激活该能力的化石翼龙 encounter；没有凭这条侧别通知猜道具、个体状态或能力拥有者。

### 百变怪时间线

- **307.018s入场**：持久ID仍为 `sample_battle_22:opponent:encounter:953d14c88dcaadc1`（D1）。
- **311.035s变身者**：按仓库screen-HUD槽位，同名左右槽面对面；opponent.left → self.left，目标为 `self:encounter:c812d2333b451851` 烈咬陆鲨，不是右槽大嘴鸥。314.520s结果确认同一快照。
- **549.025s换下**：清除临时覆盖，恢复原类型、能力、招式配置与PP等本体表示；自己的22% HP、道具和持久身份保留，历史复制记录保留并标记结束。
- **760.028s再入场**：完整可观察六行预览中只有一只百变怪，同一已确认训练家、唯一后备候选及先前明确换下共同支持回归D1。没有给其他物种添加合并策略；预览不完整、重复百变怪、训练家不匹配均不能触发此规则。两次入场episode及其原ID保留，旧D2 encounter ID作为第二次episode的encounter_id保留。
- **763.528s第二次变身者**：仍为opponent.left → self.left，目标 `self:encounter:cddd4f82f09160aa` 大嘴鸥，不是右槽铝钢桥龙。767.030s确认第二个独立快照，自己的HP仍为22%。
- **838.508s倒下**：同一D1为0%并倒下；不再同时存在一个22%后备百变怪和另一个倒下百变怪。未观察到第二次复制后的换下，第二条历史仍标记未由switch_out结束；其location/fainted另行表示倒下。

### 复制内容及未决值

| 属性 | 第一次：烈咬陆鲨 | 第二次：大嘴鸥 |
|---|---|---|
| 物种/外观 | 基础物种445；保留超级外观、进化石Z文字及旧普通Mega绑定的冲突来源；复制canonical form保持unknown | 物种279，已知canonical形态 `pokeapi:pokemon:279` |
| 能力 | 目标Mega后的能力未知，复制后也未知；不继续把变身者当有效复制后能力 | 复制660.012s独立激活的降雨；793s目标能力争议不会回写快照 |
| 属性、非HP数值 | 保存证据没有支持的当前属性/数值，保持unknown | 同样unknown |
| 阶段 | 保留目标当时的未知状态，不补全中性阶段 | 同样保持unknown |
| 当时已揭示招式成员 | 大地之力；没有证明槽位 | 广域防守；没有证明槽位 |
| 复制PP | 适用最大PP无证据，保持unknown并记录 `min(5, applicable maximum PP)` 规则 | 同样unknown |

第一次复制后执行的三次龙之波动及第二次复制后执行的暴风均标记 `move_origin=transformed`，关联相应复制源事件；它们不会变成本体确定招式槽。已知目标槽位和适用最大PP的定向软件测试验证了复制槽位及PP上限初始化；执行后缺少剩余PP读数时保持未知，不假定固定扣1PP。没有拿其它世代PP或Champions自然可学性填补本片隐藏配置。自己的绝对HP、最大HP、道具与等级在本片未被确认的部分仍未知；测试另外验证已有这些字段时不会被目标覆盖。

## 实现边界与兼容性

- `battle_events/parser.py`：识别显式变身结果和侧别紧张感通知；继续区分能力激活、结果及变身招式执行。现有occurrence路径即可发出四条消息，无需调整OCR/采样。
- `tracking/transformation.py`：是既有StateEngine的局部辅助实现；复用 `PokemonState.mechanics['temporary_transform']`、transformations、类型、能力、招式和阶段。快照与本体备份放在既有per-entry mechanic中，没有新建状态层或身份数据库。`species/current_variant/original_identity`保留本体；临时外观通过快照及决策投影的 `copied_appearance` 表示。换下恢复本体，事件撤回/纠正由既有重放重建。
- `tracking/state_engine.py`、`tracking/evidence_fusion.py`：在能力、显式结果、手动变身执行和换下处接入；手动变身必须有明确观察目标，可为队友，不套用变身者位置规则。目标未知只保留未决，不随机选取。重复结果不再次复制；执行历史和hidden层所用resolved事件均保留临时招式来源。
- `tracking/identity_ledger.py`、`tracking/active_continuity.py`：仅加入有上述独立证据的百变怪回归路径，保留episode历史与原引用。非百变怪政策不变。
- `tracking/unnerve.py`：复用side.temporary_effects和Effect，保存观测及已知能力来源；来源换下、倒下、能力移除/覆盖或受抑制后更新有效性，多来源仍有一只有效时继续限制。来源不明时不指定拥有者，后续来源变化无法跟踪时保留未知。不会消费树果或制造HP、回复、损伤、治愈。
- `tracking/decision_state.py`：从同一快照投影复制外观和非HP数值，不独立维护第二套事实。未更改伤害计算及其调用方，不将本次状态支持当作伤害计算支持。

## 验证与原始证据保护

最终命令：

```sh
.venv/bin/python scripts/validate_b22_implementation.py --run-id b22-focused-v6
.venv/bin/python -m pytest -q tests/test_ditto_unnerve.py tests/test_battle_state.py tests/test_event_driven.py tests/test_stateful_mechanics.py tests/test_hidden_state.py tests/test_evidence_fusion.py tests/test_semantic_state.py tests/test_hp_attribution.py tests/test_hp_completion.py tests/test_hp_resolutions.py tests/test_sequential_resolution.py tests/test_scrolling_semantics.py tests/test_git_artifact_policy.py -m 'not local_artifacts'
```

**333 passed，3 deselected**。新增22项定向用例覆盖左右HUD目标、目标缺失、未知槽/PP、Z形态未决、手动复制队友、快照独立性、重复消息、换下/回归、原生配置恢复、撤回/纠正/序列化、紧张感未知/多来源、抑制/能力替换/离场与不改变道具HP状态。三个未选用项是local_artifacts历史证据用例，没有把失败历史证据当缺失跳过。

局部验证共 **325个事件：321个原事件＋4个新事件**。保留所有原非HUD事件、非零数值变化、数字平台与动作边界平台的首尾读数、原冲突及未接受HUD；省略无新增信息的重复读数。局部StateEngine耗时记录在manifest中，是验证耗时，不能替换首次生产wall/PTR。

- 321个保留原事件的接受状态和reason均不变；没有丢弃旧deferred来改善统计。
- 原 **45个非零数值HP段** 的事件ID、observed_before、after、单位及delta完全一致；D2对应的后半程HP归到D1，新增连续性不是新增HP观测。
- **22个HP结算组** 的源动作、before/after/单位、净变化、完整端点和程序支持标记均不变；仍为16个完整端点/程序supported、6个ambiguous。这是原投影一致性，不是独立因果正确率或逐击完备性。
- **3处旧冲突保留**：664.512、670.513秒maximum_hp_disagreement，793.000秒能力visual_fact_disagreement。**12条旧deferred保留**，均为message_episode_occupancy_unresolved；本次没有新增延期。
- 开始和结束均核验首次封存11,574个文件及B16–B21保护155个文件；原B22计时/诊断JSON和 `docs/b22-ditto/` 文件另做前后哈希保护。原生产源文件已有获授权改动，不能再声称“运行前生产源码完全未变”。

详细输出在 `.cache/battles/sample_battle_22/diagnosis/b22-focused-v6/`：manifest、added-events、checkpoints、replay、hp-resolutions、summary；[精简验证摘要](validation-summary.json)保留关键结果和输入/实现哈希。完整状态不纳入版本控制。

可直接复用上述最终命令的完整阶段；manifest输入/源码哈希不符时会要求另开run-id，不覆盖已完成结果。中间尝试也保留：v1暴露新cause字段与既有字典接口不兼容，已使用既有结构表达；v2发现冲突HUD被精简；v3完成语义及数值核对，但动作平台读数不足使两个支持标记下降。v4补回原已缓存的平台边界证据后完成所有一致性检查，v5进一步收紧执行后剩余PP的证据边界，v6补测对位个体身份未识别时的结果处理：快照保留unknown，结果的报告身份另存为观测。未修改生产HP规则，也未删这些中间输出。

## 机制出处与剩余范围

规则以本次用户批准的Champions任务为实现约束。另按范围核对：[52Poké紧张感，revision 2561869](https://wiki.52poke.com/index.php?title=紧张感（特性）&oldid=2561869) 的Champions说明支持禁止对手吃树果，一般机制章节记录离场解除及特性可抑制；[Bulbapedia Unnerve，revision 4579248](https://bulbapedia.bulbagarden.net/w/index.php?title=Unnerve_(Ability)&oldid=4579248) 独立列有Champions禁止吃树果说明。均检索于2026-10-30；没有把例外树果机制或其它世代细节导入运行时。

[52Poké变身，revision 2610644](https://wiki.52poke.com/index.php?title=变身（招式）&oldid=2610644) 的Champions说明区分HP与其它能力；通用PP正文不替代Champions适用最大PP。百变怪Champions自然招式表与变身者的先前已封存研究见 [原出处记录](../b22-ditto/rules-sources.json)，本次没有覆盖它。52Poké摘要署名其贡献者，依CC BY-NC-SA 3.0；这里只保存短摘要/引用，不导入新知识库或爬虫，运行不需要联网。

未解决原目标烈咬陆鲨的Z形态身份、隐藏能力值/招式槽/PP，以及原3处冲突、12条延期或逐击HP合并问题。完整BattleState、整场识别准确率、伤害计算及后续里程碑均未在本次验收范围内。
