# 项目状态锚点

最后更新：2026-10-14（接手首日，第 1 轮）
维护方式：每轮工作结束时更新本文件。新对话靠本文件恢复状态，不靠聊天记录。

---

## 一、硬约束

| 项 | 值 |
|---|---|
| 中期检查截止 | 2026-10-15 前后（约 26 小时窗口，自 2026-10-14 21:00 起） |
| 生成模型 | 密钥可用，OpenAI 兼容接口（DeepSeek-V3 或同类） |
| 代码改动 | 先落在 `_repo_review`，甲方确认后合并原仓库 |
| 工作副本 | `E:/workbuddy-workplace/大创/_repo_review` |

## 二、进度锚点

| Block | 内容 | 状态 | 产出 / 下一步 |
|---|---|---|---|
| — | 建立本 skill | **已验证** | 仓库权威源 + 用户级镜像，`quick_validate.py` 通过 |
| — | 清除无效实验资产 | **已验证** | 5 个假实验 + 2 个 oracle 实验 + 22 个一次性脚本已删，见 D-030 |
| — | 精简测试套件 | **已验证** | 86 项 / 22 文件 → **45 项 / 13 文件** |
| 1 | 工程底座与可复现环境 | **已验证** | `.venv`、`setup_env.ps1`、`verify_all.ps1`、`ENVIRONMENT.md`；去绝对路径 |
| 2 | 判分口径修复 | 进行中 | 下一步：`app/backend/scoring_v2.py`、`docs/experiments/SCORING_PROTOCOL_V2.md` |
| 3 | 混合召回 + Cross-Encoder 重排序 | 未开始 | `app/backend/rerank.py`、`data/experiments/retrieval-v2.json`；同时处置 B/C/D 组泄漏 |
| 4 | 流程骨架抽取器 | 未开始 | `app/backend/flow_extractor.py`、`data/experiments/flow-extraction.json` |
| 5 | 基线 A/B/C + 本方法四配置对照 | 未开始 | `scripts/run_baselines.py`、`data/experiments/baselines-final.json` |
| 6 | 高风险坑题集与误差分析 | 未开始 | `data/evaluation/high-risk-set.jsonl`、`docs/experiments/ERROR_ANALYSIS.md` |
| 7 | 中期检查材料与仓库同步 | 未开始 | 更新后的中期检查表、工作报告 |

第二部分（中期检查后）：独立确认性验证 / 版本冲突做成真变量 / 系统联调与工程化 / 正式实验与统计 / 成果材料。详见 `docs/project/WORK_PLAN_2026-10.md`。

### 每轮收尾的强制门禁

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_all.ps1
```

当前基线：数据校验通过、评测内容校验通过（`sample_sha256` 未变）、单元测试 45 项通过。

## 三、继承的真实资产（保留，是本项目最值钱的部分）

- **来源层**：34 条来源记录、29 个本地来源文件（含 SHA-256）、版本分组与可定位锚点。
- **证据层**：309 条原子证据，8 类事项，可回到官方原文。
- **流程层**：13 条人工标注流程 —— **降为金标准，只用于评分**。
- **评测层**：200 条样本 + 200 条独立复核记录，版本 `1.0.1-frozen`。
  - 注意：这批问题的问法是**由声明反写而来**（对着答案出题），因此它只能算**开发/诊断集**，不能作为确认性验证集。真正的独立验证集属于第二部分 B1。
- **方法层**：稀疏/语义/混合三种检索器、声明绑定校验、流程约束上下文。
- **工具层**：`stage4_statistics.py`（配对自助区间 + 符号随机化 + Holm 校正）—— 通用，保留。
- **治理层**：项目记忆、决策日志、工作报告制度、数据校验脚本。

## 四、已作废的历史结论（不得再被引用）

- 阶段四"完整方法整体成功率 0.900，直接抽取 0.080"—— 循环论证，已删除相关代码与结果文件。
- 阶段三"稀疏/语义/混合 Recall@5 = 0.856 / 0.781 / 0.858"—— 该实验以样本的金标准 `process_id` 作为检索条件（oracle 条件检索），不是端到端检索成绩，已删除。
- 阶段四"六种变体消融 + Holm 校正通过"—— 同上，建立在同一循环之上，已删除。

## 五、关键文件位置

| 用途 | 路径 |
|---|---|
| 完整计划 | `docs/project/WORK_PLAN_2026-10.md` |
| 泄漏与冗余审查结论 | 本 skill `references/AUDIT_FINDINGS.md` |
| 数据校验 | `scripts/validate_research_data.py` |
| 评测集（诊断为开发集） | `data/evaluation/stage2_samples.jsonl` |
| 流程金标准 | `data/research/process_records.jsonl` |
| 原子证据 | `data/research/evidence_units.jsonl` |
| 来源记录 | `data/research/source_records.jsonl` |
| 在线原型（**含写死答案，待整改**） | `app/backend/rag_engine.py` |
| 统计工具（保留） | `app/backend/stage4_statistics.py` |
