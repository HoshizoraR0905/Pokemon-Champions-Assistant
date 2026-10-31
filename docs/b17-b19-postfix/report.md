# B17/B18 三项修正与 B19 首轮评估

2026-10-28。原项目；未提交或推送。冻结的 `fresh-b17-b18-20261028-v1` 保持不变。所有复核复用保存观察/图片，不重跑 B17/B18 全视频或 OCR。

## A. 实施的修正

| 修正 | 文件/函数 | 最小实现与限制 |
|---|---|---|
| 明确的逃脱按键退场 | `battle_events/parser.py:EventParser.parse`；`tracking/state_engine.py:StateEngine._transition` | 匹配带或不带“对手的”的完整“X要用逃脱按键回去了！”；复用现有空白清理、literal actor/side 及 switch_out。cause=eject_button，不靠弹窗推退场。 |
| 道具消费与切换历史 | 同上；`knowledge/data/52poke-resolution-v1.json` 中 canonical `pokeapi:item:590` 单条来源断言 | 仅明确退场触发后复用 `_item(change=consume)`；标为 derived 并带规则出处。保留退出实例的 HP、moves 和历史；复用现有 invalidate_unverified_persistence，临时已修改阶段/效果失效，不虚构未验证的零阶段。 |
| 限制预览识别重试 | `recognition/event_schedule.py:IdentitySchedule.acquire_team/observe_phase`；`recognition/fast_video.py:analyze` | 稳定未知行10秒重试；同ROI签名差异≥.20视为明显内容变化，立即独立尝试，清除旧成功结果防止借用。稳定成功行跳过。新预览上下文允许未知行再试，并绕过外层unchanged门控；状态可经已有checkpoint序列化。没有降低识别阈值。 |
| 压缩预览状态 | `tracking/identity_ledger.py:preview_semantics/transition` | 按相同battle/side/row及语义保留首个完整payload；忽略像素匹配分数、候选排序、几何、耗时、来源变化。不同候选成员/形态、状态、方法、文字等仍保留；重复事件仍保留原ID和全量证据在history，状态仅增加轻量source引用。没有修改deepcopy/hash事务机制。 |

消费依据来自[52Poké逃脱按键的Champions版本说明](https://wiki.52poke.com/wiki/逃脱按键（道具）)：确认该版本使用一次后会在本场消失。文章revision **2635531**，检索日2026-10-28；现有supplement保留CC BY-NC-SA 3.0和作者署名。运行使用本地来源断言，不联网。未从通用世代或Showdown替代Champions消费规则。

新增 `tests/test_preview_switch_fixes.py`：8项portable tests，覆盖空白/换行句式、重复消息仅一次退场、HP历史保留、敌方唯一空槽、消费来源、成功/未知行重试、图标变化不继承旧身份、候选/形态/status变化保留、重复preview压缩、撤回首观察和确定性重放。

测试分批结果：最初185 passed、1 optional historical test deselected（72.87秒）；采集上下文门控补齐后79 passed（33.16秒）；Champions消费补齐后122 passed（38.20秒）。最后补充知识来源、HP与Git策略回归94 passed、2 optional historical tests deselected（28.40秒）。这些集合重叠，不相加成独立测试数。相关原有测试原地运行，未重组无关测试。

## B. B17 保存输入回归

仅重新运行 MessageOccurrences、video_events 和 StateEngine。第一次成功结果保留于 `diagnosis/three-fixes-20261028-v1/reparse/`；补齐消费后的最终结果位于 **`.cache/battles/sample_battle_17/diagnosis/three-fixes-20261028-v2/reparse/`**。输入来自冻结recognition；不修改旧数据。

| 关键点 | 修复前 | 修复后 |
|---|---|---|
| 341.507前 | 敌左千面避役、敌右踏冰人偶 | 相同 |
| 341.507明确退场后 | 踏冰人偶错误留在右槽，无switch_out | 一条支持的switch_out；千左保留，偶到bench，右槽空 |
| 347.508喷火龙入场后 | 偶仍占右，喷火龙slot=None | 唯一空槽安置喷火龙到敌右；千仍敌左 |
| 360.510 | 双槽HUD延期 | 千左/喷右，与同一保存源图的四HUD一致；无需未来HUD倒灌 |
| 占位延期 | 211 | **9** |
| 其他延期 | 7 | **1** |
| 总延期 | 218 | **10** |

原202条级联HUD回执全部恢复，原6条active_identity_context_unresolved战斗消息全部获准；原9条我方无当前占位观察的事件ID逐条保持延期，不强行绑定。剩余1条是278.013秒烈咬陆鲨畏缩消息的side_unknown。三个独立状态冲突（光墙重建、目标面板2/4数字、相同道具引用字典差异）不在本次修复范围，未顺手修改。

喷火龙两次encounter仍不按species强行合并；位置恢复不等于证明其持久个体连续性。HP和历史保留在退出实例；Eject Button的消费有独立derived来源链，不把item banner本身等同消费/退场。

## C. B18 保存帧与同输入状态回归

### 图标：实际匹配测量

保存帧实验：`.cache/battles/sample_battle_18/diagnosis/three-fixes-20261028-v1/icons/`。读取保存的177个预览候选帧，使用实际模板与轮廓匹配器、独立空crop缓存；没有OCR/解码。

| 指标 | 冻结运行 | 保存帧新逻辑实测 |
|---|---:|---:|
| 高层图标请求 | 358 | **28** |
| 底层匹配调用 | 692 | **56** |
| 图标工作跨度 | 249.852 s | **20.608 s** |
| 整个保存帧实验（含读图/进度I/O） | 不适用 | 23.445 s |
| 真实预览：高层/底层 | 356/688 | **22/44** |
| 220.020假预览：高层/底层 | 2/4 | **6/12** |

真实预览中成功行1/3/4/6的species IDs **1018/768/279/445全部保留**；行2/5仍未知，没有降低阈值。220.020状态面板假预览是已有独立问题：新逻辑会在明显不同内容上重新尝试成功行，故该帧由4增至12次底层调用；仍远小于总体减少量。未在本次范围修改phase分类。

实际保存图标的15组跨行内容比较差异均>.20（最小.274），而稳定未知行相对首图的差异最大.10446/.14805；局部门控在这些真实样本上可区分背景变化与不同图标，不宣称覆盖所有相近形态。

这不是“B18全流程现在只需20秒”；只是图标子操作的保存帧实测，不能从它推算完整视频wall或B19收益。最终采集门控补齐只影响预览重现的外层放行；保存帧实验原本逐预览帧调用acquire_team，不受该返回值影响，兼容性AST审计保留在 `acquisition-compatibility.json`。

### 状态：原358条观察作为相同输入

`.cache/battles/sample_battle_18/diagnosis/three-fixes-20261028-v1/package/` 保留新剖析与重放。比较基线是已有 `performance-root-baseline-20261028-v1` 保存数据剖析，非冻结751.730秒整段视频wall。使用相同观察和对应静态knowledge预热口径。

| 指标 | 已有基线剖析 | 压缩后 |
|---|---:|---:|
| ledger.roster完整条目 | 358 | **145** |
| 完整state的JSON UTF-8字节数（同分隔口径） | 3,566,546 | **2,305,338** |
| 包装至summary | 242.308 s | **134.125 s** |
| 整个包装/导出 | 242.933 s（末尾seal失败） | **134.844 s，成功** |
| StateEngine.replay | 239.359 s | **131.840 s** |
| 整状态deepcopy | 1112次/70.810 s | **1112次/38.451 s** |
| hash_state | 1109次/165.760 s | **1109次/89.512 s** |
| BattleState.to_dict/asdict | 1111次/139.554 s | **1111次/75.010 s** |

父子跨度有重叠，不能相加。旧剖析末尾seal错误与完整生产运行无关；旧replay已完成且与冻结输出相等。新剖析不要求整份replay等于旧结果，因为preview ledger、轻量repeat链接和hash有意改变；应验证非preview事实保留和新实现自重放一致。

145不是“145只宝可梦”，而是保守保留的候选集合/状态等不同观察；有真实新候选不强压成6条。先前358次重试中的全部事件ID与原候选证据仍在history。整状态复制/哈希仍是大头，本次没有改事务/审计契约；新预览采集仅28次请求会进一步限制进入事件流的数量，但没有把两种实验的时间节省相加。

最终确定性复核通过：第二次完整replay与新保存结果的状态、所有回执和hash逐项相等；非preview回执及其余最终状态事实与旧冻结结果逐项相等。第一次check误把native tuple与JSON list直接比较，失败记录保留；已改为与既有verification相同的JSON规范化比较，并在断言前保存第二次replay。此修正仅在诊断检查器。

## D. B19 首轮结果

原录像唯一匹配为 `tests/fixtures/sample_battle_19.mp4`，2622×1206、734,869,029 bytes；SHA-256 `5ecba3f7f3770860b9ea00c281345425da841ddb071fabe9ca5875b9eb34963d`。未使用旧识别/帧缓存或人工事件。实际命令经现有外层driver运行：

```sh
.venv/bin/python main.py --video tests/fixtures/sample_battle_19.mp4 \
  --profile event-driven --identity-mode lightweight --sample-fps 2 \
  --run-id fresh-b19-postfix-v1
```

仅一个未中断生产attempt；计时从CLI子进程启动前到完整正常导出后退出，包含启动、哈希/采样/解码、OCR、图标、解析和StateEngine。参考提取、派生HP投影、封存、后验重放不计入317.365秒。没有定向高FPS补帧。

### 正常生产性能

| 指标 | B16 冻结 | B17 冻结 | B18 冻结 | **B19 首轮** |
|---|---:|---:|---:|---:|
| 录像时长 s | 753.740 | 529.710 | 421.580 | **391.810** |
| 源平均FPS | 40.089690 | 44.933022 | 30.039973 | **37.230730** |
| 源帧/实际解码帧 | 30,216 | 23,799 | 12,663 | **14,587** |
| 2 FPS实际采样帧 | 1,508 | 1,060 | 844 | **784** |
| 详细检查帧 | 1,276 | 1,052 | 831 | **776** |
| OCR调用 | 4,204 | 4,307 | 3,033 | **3,508** |
| OCR工作跨度 s | 324.307 | 249.805 | 182.810 | **176.201** |
| 图标底层匹配调用 | 126 | 12 | 692 | **12** |
| 图标工作跨度 s | 39.478 | 4.386 | 249.852 | **4.394** |
| 包装至summary跨度 s | 178.869 | 141.197 | 241.492 | **83.158** |
| 完整正常CLI wall s | 666.124 | 474.530 | 751.730 | **317.365** |
| ms/采样帧 | 441.727 | 447.670 | 890.675 | **404.803** |
| ms/详细检查帧 | 522.041 | 451.074 | 904.608 | **408.976** |
| PTR | .8838 | .8958 | 1.7831 | **.8100** |
| 有效采样帧/wall秒 | 2.264 | 2.234 | 1.123 | **2.470** |

`ms/sample=1000×wall/实际采样帧`；`PTR=wall/录像时长`；有效吞吐=实际采样帧/wall。源FPS只描述源，不充当处理帧分母。B19内部pipeline wall316.812秒，比外层wall少.553秒。

实现分别为B16 `event-driven-v1`、B17/B18 `event-driven-banner-hp-v2`、B19 **`event-driven-preview-bounded-v3`**，都名义2 FPS/lightweight，但源码和录像内容不同。B19的六行预览首次即全部解析，不经历B18的持续未知行；**不能把B19与B18的完整wall差值都归功于修复**。可控制的修复证据是上节相同B18保存输入/帧的实验。OCR/icon跨度是现有墙钟包围计时，不是CPU独占分解。

### B19 无Battle Log：不适用日志参考评分

用户随后确认：先前视频说明对应错误，**B19没有Battle Log，B20才有部分回合日志**。因此B19的日志召回不适用，不再作为待补验收项。

此前独立扫描全部776张保存检查帧得到0个log view/0条entry，与本次更正一致；原扫描及检查记录保留，不伪造参考标签。B19可评估日志facts、正确facts、覆盖边界和event-fact recall均为 **N/A（无日志参考）**，不是0%或100%。B19全段0–391.810秒只报告正常生产性能、描述性重建及源图局部复核，不声明日志准确率。

部分日志的独立参考评分转至B20，在其首轮预测封存之后进行。B19首轮不重跑、冻结结果不改。

### 描述性事件、状态和HP

- **1110条回执**：recorded_observation16、applied_candidate1068、applied_partial12、deferred13、rejected1。两条state conflicts包含那1条rejected，不是两条rejected。
- **招式执行12条解析、12条接纳，但全部仅为move_revelation_only**，不等于已完整应用招式机械效果；send_out5（4只开场+铝钢桥龙替补）、switch_out0、faint1（173.530秒妙蛙花）。
- **13条延期全部是我右HUD**，177.530–183.532秒，发生在妙蛙花173.530倒下至铝钢桥龙185.532入场的间隙。没有把空槽读数强行绑定，也没有B17那种持续对手双槽级联。
- 最终已知四槽（最近可见状态，不是已验证比赛结局）：

| 侧 | 左槽 | 右槽 |
|---|---|---|
| self | 喷火龙，146/184 | 铝钢桥龙，83/194 |
| opponent | 沙奈朵，87% | 皮卡丘，26% |

敌方HP保持显示百分比，不推绝对HP/隐藏配置。共有5个encounter；妙蛙花记录为fainted，保留其历史，不从已知种类枚举对方隐藏队伍。

- **941条数值HP观察、24条非零段**：我方14段下降/4段上升（绝对HP），对手6段下降（显示百分比）。这些包括动画内多段变化，不是24次独立招式。
- 动作—目标HP组 **11**，完整稳定端点 **10/11**，支持完整因果总量 **10/11**。剩余组是桥的吃剩的东西候选恢复71→83，`resolution_window_still_open`；不把候选值充当已定稳的最终总量。全部非零段恰好投影一次，端点ID/单位/数值复核通过。
- 能力激活解析6条：91.015复制；92.015叶绿素（被拒绝）；229.005日照；249.508/337.023/345.525持久力。道具激活2条：268.012/356.510桥的吃剩的东西。没有因为“激活”自动创造数值HP量。
- **最终天气、场地及双方side conditions仍为unknown**，不代表不存在；source实际368.028秒清楚显示“大晴天状态”，OCR两次约.99986，但`parse_detail`只支持下雨/极光幕/青草，且visual transition只处理rain/grassy，遗漏sunny事实。未因本次发现改码，也不把3/5 UI计数擅自解为已验证剩余回合。

### 封存后确认的失败与限制

| 源时间/证据 | 结果与责任点 |
|---|---|
| 91.015与92.015，源帧000183/000185均明确显示“沙奈朵的复制”后“沙奈朵的叶绿素” | 第二条被当`ability_activation`，当前能力已是复制，`StateEngine._consistent_fact`报conflicting_current，整条拒绝；最终当前特性仍为复制。属于变化能力与当前特性语义问题，不是OCR读错；未推测复制目标或隐藏原生特性。 |
| 368.028，源帧000730，详情清楚显示喷火龙“日照” | 与229.005日照同canonical `pokeapi:ability:70`，引用结构有kind与species_id/form_id差异；全dict比较造成visual_fact_disagreement，当前特性变conflicting。与B17相同道具表示问题同类。 |
| 同一368.028详情“大晴天状态” | OCR正确而语义适配未覆盖，天气未进入状态，见上。 |

这些源图review都在`initial-freeze.json`之后进行，只写独立报告/证据，不修改首轮预测、日志参考或生产识别规则。原片最后保存帧391.500仍是选择招式界面；用户说明的投降结局未在本次可见末帧建立，不能由尾帧虚构胜负。

### 保存位置与验证

- 正常首轮：`.cache/battles/sample_battle_19/event-driven/fresh-b19-postfix-v1/`。
- 外部计时/源视频与模型、配置、源码指纹/原始全输出inventory：`.cache/battles/sample_battle_19/fresh-benchmark/fresh-b19-postfix-v1/`，含execution、input、initial-freeze、projection-stage和verification/v1。
- 已生成[逐事件与状态报告](../../reports/battles/sample_battle_19/evaluation/fresh-b19-postfix-v1/report.md)、metrics、final-state-summary；这些仍是预测描述，不能当日志真值。独立参考扫描及已更正为不适用的coverage记录在同battle的`evaluation/fresh-b19-postfix-v1/auto-reference/`与`reference-review/`。
- 冻结后事件适配1110条完全一致；第二次replay完整序列化/每回执/最终hash一致（76.214秒）；派生HP投影一致，数值成员/端点无丢失；这证明可复现性，不是语义准确率。

一次旧汇总CLI的固定输出路径短暂写到了旧B17/B18总报告，已用原冻结metrics精确恢复；SHA-256重新等于原记录 **f7876e8129131ea67aa68c4bc07f787d2b274a00e7183a318e1da4af24966c80**。最终完整inventory检查通过：B17检查7604个文件、B18检查6352个文件、B19检查5970个文件，以及88个B16保护文件。原视频、冻结识别/状态及原报告最终字节不变；后续B19报告仅写独立目录。

## E. 建议

1. **在B20首轮封存后评估其实际部分Battle Log**，独立建立覆盖边界与逐fact对照；B19无日志，不再等待其参考。
2. 下一项生产修正优先考虑**按canonical ID比较同类身份事实，同时保留各源属性与冲突证据**。B17的道具与B19的日照都已证实是表示差异伪冲突，影响多个来源且可局部验证；不是合并不同canonical ID。
3. 随后分别审查**复制后的当前特性变化**以及**详情面板大晴天语义**。两者都已有明确正确OCR与源图，前者错误拒绝事实，后者漏入状态；不涉及猜测隐藏配置。
4. 性能上先观察有未知预览行的新视频；剩余整状态复制/哈希仍昂贵，但本任务不改事务机制。不依据单个B19的较小wall直接启动重构。

以上新问题仅建议，均未自动实施。当前已完成三项修正、B17/B18保存数据回归及B19首轮性能/状态交付；B19无日志参考评分不适用；部分日志评估继续到B20。
