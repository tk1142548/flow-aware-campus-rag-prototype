# 第一部分完成情况核对

日期：2026-10-15
对照文件：`docs/project/WORK_PLAN_2026-10.md` 第一部分（Block 1–7）
方法：逐 Block 取计划中的**验收标准**，回到仓库找对应产物或实现，不以"做过了"为准。

---

## 逐 Block 结论

| Block | 验收标准 | 结论 | 证据 |
|---|---|---|---|
| 1 工程底座 | 新环境按文档可完成安装、测试、启动 | **达成** | `.venv`、`scripts/setup_env.ps1`、`scripts/verify_all.ps1`、`docs/project/ENVIRONMENT.md`；启动脚本已去本机绝对路径 |
| 2 判分口径 | 新判分不依赖任何标注 ID | **达成** | `app/backend/scoring_v2.py`；三处表示空间统一（claim 文本、响应方式 6 档、槽位按内容匹配） |
| 2 判分口径 | LLM 判官落地 + 60 题人工校准切片 | **本轮补齐** | `scripts/run_judge_calibration.py`；`data/experiments/judge-calibration.{json,csv}`（90 条，三配置各 30） |
| 3 混合召回 + 重排序 | 明确回答"重排序有无增益"并给配对检验 | **达成** | `data/experiments/retrieval-v2.json`；四档 Recall@5/MRR@10/nDCG@5 + 配对 + Holm |
| 4 流程骨架抽取器 | 各维度可计算，且能定位失误来自检索还是抽取 | **达成（本轮补齐两个维度）** | `app/backend/flow_extractor.py`、`data/experiments/flow-extraction.json`；现有步骤覆盖、材料覆盖、**时限覆盖**、**入口覆盖**、顺序一致性、步骤有据率、绑定率 |
| 5 基线 A/B/C + 本方法 | 四行数字齐备，H1/H2/H3 各有一组可解释对照 | **超额** | `scripts/run_baselines.py`；八配置，含 `ablation_no_flow` / `ablation_no_skeleton` / `ablation_no_verify` / `method_v2` |
| 5 基线 A/B/C + 本方法 | **任务完成率**（抽 60 题人工标注） | **本轮补齐工具，标注待做** | `scripts/build_task_completion_sheet.py` 生成 60 行分层标注表；`scripts/evaluate_task_completion.py` 汇总并做配对检验 |
| 6 高风险坑题集 | 四类风险各有样本；失败样本可归因到某一层 | **达成** | `data/evaluation/high-risk-set.jsonl` 84 条：信息缺失 32、对象错配 24、版本冲突 24、过期入口 4；`error_taxonomy.py` 分层归因 |
| 7 中期检查材料 | 表内每一项都能在仓库找到对应文件 | **达成** | 中期检查表二/三/四栏已按八配置结果重写；封面字段与导师邮箱已填 |

---

## 与计划预期的出入

**一、结论方向与计划的隐含预期相反。** 计划把 H1（流程中间表示）当作"最实质的方法贡献"。八配置对照的结果是：交互控制单独贡献 +0.2150（p=0.0001），流程骨架放进生成提示词为 −0.0200（p=0.58），断言核验 +0.0050（p=1.0）。计划里"三者都能得到检验"的目标达成了，但检验结果是其中两项未显示正效应。

**二、判分口径的缺陷在计划编写时未被预见。** 计划只识别出 `claim_id` 一处表示不匹配，实际存在三处（另两处为响应方式档位、槽位闭集 ID）。三处都会把整类样本压成结构性 0 分。处置记录见 `REPRESENTATION_AUDIT.md`。

**三、两处计划内动作因前置变化而调整。**
- Block 1 的"86 项测试仍全通过"：测试套件按要求精简，现为 50 项（含新增 3 项判分守门测试）。
- Block 2 的"在旧确定性输出上回归"：旧输出已随假实验删除，改为在统一表示口径下对既有预测做反事实重算（`REPRESENTATION_AUDIT.md` 第四节）。

**四、重排序路线与计划的退路不同。** 计划预留"资源不足时退化为 LLM 重排"；实际使用百炼 `gte-rerank-v2`（真实交叉编码器接口），优于预留退路。

**五、测试集角色的表述需要小心。** 计划沿用"冻结集"的叫法。该批 200 条在方法迭代中已被多轮使用，只能作为开发/诊断集；确认性结论要等独立验证集（第二部分 B1）。

---

## 本轮补齐的三个产物

1. `scripts/run_judge_calibration.py` + 90 条校准切片（含 CSV，供逐条人工核对）。
   当前判官给出的平均无据比例为 基线C 0.1051 / 无骨架 0.0532 / 改造后方法 0.1297。
   **该读数在人工核对完成前不能作为结论**——TREC 2024 RAG Track 测得 GPT-4o 与人工的支持性判定一致率仅 56%。
2. 流程抽取的时限覆盖率（routed 0.6513）与入口覆盖率（routed 0.7228）。两项明显低于步骤覆盖（0.8709），说明"什么时候办"和"去哪儿办"这两类要素的抽取仍需加强。
3. 任务完成率标注工具链（60 行分层表 + 汇总脚本）。

## 待人工完成

- 任务完成率标注表：`data/evaluation/task-completion-sheet.csv`，逐行填"完成/部分/未完成"后运行 `scripts/evaluate_task_completion.py`。
- 判官校准：核对 `data/experiments/judge-calibration.csv` 的"人工判定"两列，据此计算判官与人工的一致率。
