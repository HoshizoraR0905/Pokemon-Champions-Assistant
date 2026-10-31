# B21 首次运行耗时与部分 Battle Log 重建率

2026-10-29。完整视频 **703.21秒**，首次生产CLI耗时 **559.751秒**，即
**每1秒视频平均耗时0.795994秒（约0.796秒/视频秒）**。
独立核对的部分日志中，语义记录重建率为 **44/53＝83.02%**。
这是第1–4回合可见参考行的局部结果，不是整场准确率或完整状态验收。

## 运行时间：总体与逐视频秒

| 项目 | 实测值/口径 |
|---|---|
| 原视频 | `tests/fixtures/sample_battle_21.mp4`，703.21秒 |
| 完整生产CLI wall | 559.751187秒；外部perf_counter，从启动子进程到退出 |
| wall / 视频时长 | 0.7959943505秒/视频秒；包括初始化、解码、识别、重建和包装 |
| 采样 / 详细识别 | 1407 / 1385帧；2FPS采样，识别调度独立 |
| 源视频帧数 | 容器头和实际decoder均23380；平均33.2495064FPS，不假定恒定帧间隔 |
| OCR / 图标底层调用 | 4120 / 12次；图标高层请求6次 |
| 最后采样完成之前的累计发布间隔 | 397.113秒，包含初始化及其间解码/识别/检查点工作 |
| 最后采样之后至CLI退出 | 162.638秒；包括尾部解码、全局重建、序列化、viewer导出等 |
| 其中StateEngine replay跨度 | 160.815秒；已包含在上述尾部与总wall中，不能再相加 |
| 独立历史日志提取 | 18.216秒，在封存后执行；不属于生产CLI wall |

这是一个新命名空间、单次未中断运行，`cold_run/full_cold_timing_comparable=True`。
未导入其它视频或历史识别缓存，仅沿用固定共享模型、知识与图标资产。视频SHA256：
`ef9c6ac463dc496948271475387da5a48d5df9926d2078269c92f2e54c8ac809`，1319351968字节。
完整run为 `fresh-b21-context-v1`，外部执行/冻结记录在
`.cache/battles/sample_battle_21/fresh-benchmark/fresh-b21-context-v1/`。

逐秒结果共 **704行**：[seconds.csv](../../.cache/battles/sample_battle_21/fresh-benchmark/fresh-b21-context-v1/per-second/seconds.csv)，
以及[JSON](../../.cache/battles/sample_battle_21/fresh-benchmark/fresh-b21-context-v1/per-second/seconds.json)。
区间为[0,1)、[1,2)…[703,703.21)；最后一个区间只有0.21秒。
每行给出采样/识别帧数、该区间结束时的累计完成耗时、与上一完成区间之间的耗时，以及
按实际区间长度归一化的秒/视频秒。当前没有空采样区间；算法仍会将空区间标为unknown。

数据使用原子monitor/observation文件的原始mtime与CLI启动epoch锚点，不改识别器或插入
逐帧计时逻辑。详细帧以完成的observation发布时刻为准；未详细识别的帧以即将廉价跳过前
的monitor发布时刻近似。第一秒包含启动成本；全局重建不按视频秒平均摊入识别柱形图。
这些是文件完成墙钟间隔，不是每帧CPU计时；epoch与总monotonic间隔之差约−1.02毫秒。

最长完成区间出现在视频 **526–527秒，为81.524秒**；17–18秒区间为5.654秒。
这是已记录的wall间隔，可能包含调度/等待/文件操作；本次未剖析其内部原因或进行调优。

![B21逐秒完成耗时及累计曲线](../../.cache/battles/sample_battle_21/fresh-benchmark/fresh-b21-context-v1/per-second/runtime.png)

[可导出的SVG](../../.cache/battles/sample_battle_21/fresh-benchmark/fresh-b21-context-v1/per-second/runtime.svg)。
图中橙色尾部单列全局结算/包装；下图为对数纵轴，以便同时看到短区间和81.524秒峰值。

## 基于可见日志的重建率

先封存预测、回执、状态和HP投影，再查看参考。日志在两个保存窗口可见：
**272.013–278.530秒**与 **435.523–440.525秒**，共25张源图，展示第1、2、3、4回合。
逐图查看了全部面板及8张窗口前后相邻画面，按滚动重叠整理出73条可见行；
不宣称每个回合完整，也不为未展示的行或第5回合以后补标签。

[独立转录](log-reference.json)在读取生产事件内容或自动历史OCR文字之前固定，SHA256：
`5408c618f1d1b4696e86cea7082bbae404fd3f31f37af2ad1d0a8580e84c1bac`。
每行保留原图、源ID/哈希、观察时间、原文和可见字段。转录者是Codex的视觉检查，
**不是人类提供或复核的真值**。日志查看时间不当作原事件时间；参考中原事件时间保持null。

主要口径是 **完整匹配且被StateEngine接受的语义行 / 可读语义参考行**。
按时间顺序进行一对一匹配，核对事件种类、canonical种类身份、侧别及显式招式、能力、
道具、形态、天气/场地、状态变化字段。一个入场行含两只宝可梦时需两条回执同时匹配。
使用既有KnowledgeBase名字解析，不把不明确的信息补成参考事实。

| 语义参考分类 | 已完整重建 / 参考行 | 比例 |
|---|---:|---:|
| 招式执行 | 12 / 12 | 100.00% |
| 定性HP通知：回复/反作用力 | 2 / 10 | 20.00% |
| 未命中通知 | 0 / 1 | 0.00% |
| 其余语义记录 | 30 / 30 | 100.00% |
| **合计** | **44 / 53** | **83.02%** |

44行对应46条匹配回执（两个双入场行各需两条）。接受包含revelation-only和观察回执，
不表示所有招式效果都已应用。重复相同招式采用顺序约束匹配，未独立标注原视频游戏回合
边界或事件起始帧；因此不声称精确回合归属正确率。未被展示的预测不纳入precision分母。
没有测量完整HUD位置、阶段值或整场决策状态准确率。

9条未重建的语义行已经回查原始保存文字：

- 8条“X的体力回复了！”：第1回合轰擂金刚猩/长毛巨魔，第2回合铝钢桥龙/
  轰擂金刚猩，第3回合铝钢桥龙/轰擂金刚猩，第4回合苍炎刃鬼/美纳斯。
  OCR已读到，已生成定性hp_change，但actor=None，回执为deferred/unresolved_candidate_fields。
- 第3回合“没有击中铝钢桥龙！”：保存OCR置信度0.994，仍为provisional_or_repeat，
  没有对应事件进入流。

这些不是9次确认的OCR漏读。详细源文字/置信度/回执见
`.cache/battles/sample_battle_21/fresh-benchmark/fresh-b21-context-v1/manual-review/mismatch-audit.json`。
本次没有按这些失败修正生产代码或重新运行B21。

## HP数值与结算支持：单独计算

20条数值HP行与53条语义行分开，不合并成一个整场“准确率”。

| HP口径 | 局部结果 | 含义 |
|---|---:|---|
| 同实例原始HP端点按顺序保留 | 18 / 20＝90.00% | 只证明数值可追溯，不证明动作分组或原因正确 |
| 投影有完全对应before/after/单位的组 | 18 / 20＝90.00% | 不要求该组的总量已被程序充分支持 |
| 上述组具有完整稳定端点标记 | 15 / 20＝75.00% | 其余仍保留终值平台未确认等限制 |
| 上述组被程序标为因果supported | 9 / 20＝45.00% | 是程序支持状态，不是独立因果正确率 |

两条未保留完整端点对：第2回合铝钢桥龙 **194→168**，第4回合苍炎刃鬼
**100%→30%**。现有投影均保存after，但before=None/pre_action_hp_missing；
不能因为日志现在可见就反向补写首次预测。其余一些回复已有数值变化，语义通知却延期，
因果/总量也可能仍为ambiguous，故不能用90%端点保留率代替83.02%语义重建率。

自动历史日志流水线另整理出40条候选、11处拼接问题：18 provisional_match、
12 ambiguous_alignment、8 missing_logged_event、2 historical_entry_incomplete，verified=0。
这些是机器OCR/拼接/对齐结果，不代替本次73行视觉参考。
[独立日志viewer](../../reports/battles/sample_battle_21/evaluation/fresh-b21-context-v1-logs/review.html)
与[原生产viewer](../../reports/battles/sample_battle_21/event-driven/fresh-b21-context-v1/review.html)分开保留。

## 完成范围、检查与复核

生产共1384条回执：1116 applied_candidate、21 applied_partial、28 recorded_observation、
219 deferred；未见rejected。延期包括200条占位未决和19条候选字段未决；另有2条
visual_fact_disagreement冲突。194条占位延期发生在441秒以后，未由本次日志参考验收。
全场HP投影有25组，19组完整端点、12组因果supported；这些都是描述性计数，不是准确率。

检查已完成：源视频帧数一致、精确事件重新适配一致、HP投影不改权威状态且非零段成员
恰好出现一次、逐秒会计/异常时钟边界的6个便携测试、参考原图哈希与一对一匹配检查。
未为这项计时/部分日志任务再做昂贵的全场第二次状态重放，不新增确定性重放成功声明。

处理没有改变识别/状态行为。源码改动仅为外部driver记录epoch锚点，以及既有报告辅助脚本
新增逐秒导出和6个相关测试；原有工作区修改保留。所有生成细节、CSV/图及检查点留在B21
自己的.cache命名空间；本目录只放精简报告、进度及独立参考。未提交或推送。

只读重算参考比较（不做视频/OCR）：

```sh
.venv/bin/python .cache/battles/sample_battle_21/fresh-benchmark/fresh-b21-context-v1/manual-review/evaluate.py
```

逐行comparison.json保留匹配ID、接收状态、HP支持状态和限制。**不要重跑正常生产CLI**；
相同身份的逐秒结果和各已完成阶段应复用。最终完整性复核通过：8423个B21封存文件、原生产报告/源码快照、视频和88个B16保护文件
均保持哈希一致；B17–B20各3个video-only封存文件也通过只读检查。所有处理任务已结束。
持久状态与复核命令见[progress.md](progress.md)。
