# B0–B8 历史数据清理审计

日期：2026-10-30（Asia/Shanghai）。按用户授权执行；未修改业务代码、Git 历史，未运行视频识别。

删除 **84,455** 个文件/符号链接，无删除错误。包括 B0–B8 的 9 份 `tests/fixtures/sample_battle_<id>.mp4` 原始录像、B0 旧名符号链接，以及已确认归属的帧、OCR、状态、检查点、实验缓存和旧报告图片资源。仓库枚举未发现额外实体录像副本；外部视频索引中没有找到同尺寸且内容一致的副本。

删除前可用：**5.052 GiB**；删除后：**29.459 GiB**；即时可用空间增加：**24.407 GiB**（26,207,215,616 字节）。待删除文件逻辑大小 **28.118 GiB**，按 inode/硬链接计算的预计回收块 **24.391 GiB**。实际空间差包含系统并发磁盘活动的影响。

| Battle | 已删除文件/链接数 | 逻辑大小 GiB（含硬链接路径，非实际释放量） |
|---|---:|---:|
| B0 | 893 | 1.732 |
| B1 | 907 | 1.688 |
| B2 | 720 | 1.046 |
| B3 | 1,546 | 1.695 |
| B4 | 670 | 1.162 |
| B5 | 9,630 | 3.022 |
| B6 | 55,625 | 15.203 |
| B7 | 9,090 | 1.717 |
| B8 | 5,372 | 0.855 |

另删除两个有明确旧录像来源的共享历史处理记录；逐路径明细见 `deletions.jsonl`。

保留项目源代码、源码/fixture 快照、模型、人工标注、报告正文、算法文档、最终总结与聚合指标；保留 **104 个 Git 跟踪文件**。本次没有删除任何已跟踪文件，原有已跟踪工作区状态不变。

保护性依赖包括：

- `tests/fixtures/battles/m233b1_selection_diagnostics.json` 引用的 51 张 B0/B1/B2/B4 回归图片及必要兼容别名。
- B5 `m236` 已保存评估/识别/回放输入，以及 `m236u/regression-replay.json`。
- B5–B7 provisional-entry 回放、B7 保存验收和 entry-HUD 测试数据及其证据依赖。
- B6 `visual_v22_b6_real.json` 指向的识别观察、预测和证据图片；`preservation-baseline.json` 中被测试校验的历史文件。
- B7 `production-first-pass-v1/frames/000884.png`、B8 `m239-production-first-pass-v1/frames/000245.png` 等明确测试输入；与保留文件共享 inode 的旧链接也保守保留。

本次对 B9 及之后的 **228,225 个路径**核对存在性、inode、大小和 mtime：零变化；保留清单零缺失；Git 跟踪文件零删除。没有运行识别或额外视频处理。

少量无充分归属证据的目录外图片（例如 `outputs/video/` 的混合输出）保留，未按名称或时间猜测归属。外部检查范围为仓库完整枚举与系统视频索引，不宣称遍历了整台机器所有未索引目录。

审计文件：`ownership-evidence.json`、`video-identities.json`、`before.json`、`delete-plan.json`、`retained.json`、`deletions.jsonl`、`after.json`、`verification.json`、`progress.json`。大清单受 `.gitignore` 保护；未提交或推送。
