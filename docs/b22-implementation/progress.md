# B22 定向实现交接

2026-10-30。用户已批准Ditto临时变身、仅百变怪的有证据回归身份及紧张感侧别限制实现；禁止生产重跑、覆盖旧基准、提交或推送。

源码变更前备份及哈希：`.cache/battles/sample_battle_22/diagnosis/b22-implementation-v1/`。其它工作树编辑保留。实现及22项定向测试已完成；最终报告见report.md。

最终保存证据验证命令：

```sh
.venv/bin/python scripts/validate_b22_implementation.py --run-id b22-focused-v6
```

该命令只读取原保存消息和必要HP平台边界，不解码或OCR；完整阶段有输入/源码/输出哈希，可直接复用。若中断，先检查进程和同目录manifest；未完成或输入变化时保留已有输出，在查明错误后另用新run-id。不要重新启动原生产CLI。

v4已通过：4条新增消息，唯一Ditto持久实例、两次复制、两次episodeID保留；45个非零HP变化一致，22组端点/净变化/支持标记一致，3处冲突和12条延期保留，11,729个原封存/保护文件及原诊断前后哈希通过。v5收紧执行后的剩余PP：有初始化规则但无剩余PP读数时保持未知。v6补测未知对位身份，结果观测不会把快照中的unknown偷偷补成已知。

最终回归范围和完整命令在report.md；涵盖解析、StateEngine、mechanics、hidden、fusion、语义状态、HP归因/结算、滚动及Git策略。此前332项通过、3个local_artifacts用例未选用，最后PP调整后复核结果以report.md及validation-summary.json为准。

剩余范围：Z形态canonical身份、隐藏属性/能力值/槽位/PP，原3处冲突/12条延期和逐击HP合并。未授权进入其它里程碑。

最终状态：b22-focused-v6完整通过并验证可复用；333 passed、3 deselected，22项定向用例包含在内。原封存与诊断未改，未提交或推送；本次范围已完成。
