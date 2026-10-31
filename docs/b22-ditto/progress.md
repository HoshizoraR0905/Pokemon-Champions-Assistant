# B22 Ditto 首次基准与诊断

范围：仅原样生产基准、冻结及证据诊断；不修改生产逻辑、不提交。

- 输入：tests/fixtures/sample_battle_22.mp4
- run：fresh-b22-ditto-20261030-v1
- 初始检查：无 B22 缓存，无活动生产任务；既有工作树修改保留。
- 运行命令：`.venv/bin/python scripts/run_fresh_video_benchmark.py --battles sample_battle_22 --run-id fresh-b22-ditto-20261030-v1`
- 阶段：即将开始单次生产；先完成 initial-freeze.json，再查看预测差异。
- 恢复：先检查进程及 fresh-benchmark 下 execution.json、event-driven 下 manifest.json；已有活动任务不得重复启动，完成的采样/OCR 不重跑。

运行中检查点：生产 manifest last_timestamp=277.0133333333333；初始冻结尚未完成，未查看该场预测差异。

## 封存后核对计划

1. 校验 initial-freeze 所列哈希；仅从封存帧的 UI 分类定位 Battle Log，先独立视觉转录可读行并记录图像哈希，再读取预测内容。
2. 从保存帧和消息定位两次变身及所有百变怪进出场，记录自身身份、槽位、触发证据和目标。变身者目标使用用户给定的固定对位；手动变身须用实际招式目标。
3. 对照已封存事件、回执、最终状态及身份/占位账本，记录首个失败与下游影响；只读源代码解释原因。
4. 导出初始指标与精简诊断报告，复核生产源码及 B16–B21 保护哈希。禁止修复或整场重跑。

## 已完成

- 单次生产退出0，external wall850.076456s，PTR0.988254；StateEngine387.361054s包含在wall内。
- 初始11,574个文件封存，随后视觉转录44张日志帧的124条可读行，再查看事件/回执。
- 两次变身者：311.035/763.528；两次结果文本314.520/767.030被OCR读到却unknown且未发事件。
- 再入场760.028分配新encounter并保留possible prior；未创建临时变身。
- 报告docs/b22-ditto/report.md；局部审计命令`.venv/bin/python docs/b22-ditto/audit.py`。
- 245个生产源文件、155个B16–B21既有元数据文件和初始封存哈希检查通过。没有生产修复、全场重跑、commit/push。
- 当前无待完成采样/OCR/重放；不要重新启动首次生产。下一步仅在用户授权后实施最小修复。

## 可见日志评分补充（2026-10-30）

- 用户要求补充复现率；继续复用原124行参考与首次封存生产，不修改生产实现。
- 消息记录100/104＝96.15%，其中招式24/24；四条缺失为两次紧张感树果限制、两次变身结果，均有OCR但unknown且未发出。
- 此口径是已接受消息记录；进化石身份/Z形态、临时复制状态和持久身份仍有限制，不称为完整语义或状态准确率。
- HP原始有序端点18/20，精确组16/20，精确且完整端点13/20，精确且程序supported13/20；逐击合并仍计失败。
- 复核命令：`.venv/bin/python docs/b22-ditto/score.py`；通过三个评分输入及参考哈希、逐次回执匹配与HP端点检查。输出`docs/b22-ditto/log-score.json`，结论已补入report.md。
