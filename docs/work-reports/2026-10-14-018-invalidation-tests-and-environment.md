# 018 接管项目：清除无效资产、精简测试、建立可复现环境

日期：2026-10-14
状态：已验证

## 本轮目标

用户将项目整体移交，并给出四条指令：① 对"完全糊弄的实验"直接删除而非降级保留；
② 允许在可控前提下并行子任务；③ 把工作包装成可跨会话续接的 skill；
④ 精简既有的冗余/过度防御性测试，且自身设计亦避免冗余。

## 实际完成

### 1. 建立项目 skill（跨会话续接 + 防目标漂移）

- 重写仓库权威源 `skills/advance-campus-rag-research/SKILL.md`：写入三条不可让步原则、
  状态恢复步骤、Block 顺序、明确禁止项、每轮收尾要求。
- 新增 `references/PROJECT_STATE.md`（进度锚点、继承资产、已作废结论）。
- 新增 `references/AUDIT_FINDINGS.md`（泄漏点、冗余测试、一次性脚本的完整审查结论，
  供新会话直接使用而无需重查）。
- 同步安装到用户级 `C:\Users\Lenovo\.workbuddy\skills\advance-campus-rag-research\`，
  通过 `quick_validate.py` 校验。

### 2. 清除循环论证的实验资产（删除，非降级）

删除代码与结果：`app/backend/stage4_pipeline.py`、`scripts/run_stage4_experiments.py`、
`configs/stage4-experiment.json`、`data/experiments/stage4-final-ablations.json`、
`docs/experiments/STAGE4_PROTOCOL.md`。
删除 oracle 条件检索：`scripts/run_stage3_formal.py`、`scripts/analyze_stage4_retrieval.py`、
`data/experiments/stage4-retrieval-analysis.json`、`data/audit/stage3-formal-sparse.json`、
`data/audit/stage3-formal-semantic-hybrid.json`。
保留 `app/backend/stage4_statistics.py`（通用统计工具，与实验设计无关）。
历史报告 `docs/work-reports/2026-10-12-017-*.md` 保留并加作废横幅，理由见 `DECISIONS.md` D-030。

删除 22 个一次性修补脚本（零引用），其中 `reconcile_stage2b_review_status.py` 重跑会将已
`verified` 的证据与流程状态回退为 `in_review`；`author_stage2_content.py` 等会整体重写已冻结样本。

### 3. 精简测试套件

由 86 项 / 22 文件精简至 **45 项 / 13 文件**：

- 整文件删除 9 个：依赖已删模块的、仅覆盖一次性修补脚本的、跨文件重复断言的、
  断言数据话术与配额魔数的。
- 零散删除 11 条：重复的防御式参数断言、与其它文件重复的排序契约。
- `tests/test_research_data_validation.py` 重写：删去 7 条一次性阶段迁移与数据配额断言，
  保留 6 条通用契约；把写死的 `6/8/1`、`34/29/309` 等魔数改为**自洽性断言**
  （如"全部证据均已核验且可定位"），避免数据正常扩充即挂测试。
- 新增 1 条流程记录校验器契约测试（替代被删文件的覆盖）。

### 4. 建立可复现环境（Block 1）

- 新增 `scripts/setup_env.ps1`：建立 `.venv` 并安装依赖，含导入自检。
- 新增 `scripts/verify_all.ps1`：数据校验 → 评测内容校验 → 单元测试，任一步失败即中断。
- 改写 `scripts/run_backend.ps1` / `run_frontend.ps1`：删除
  `C:\Users\Lenovo\Documents\Playground\...` 与
  `C:\Users\Lenovo\AppData\Local\Programs\Python\Python311\python.exe` 等本机绝对路径，
  改为基于 `$PSScriptRoot` 推导仓库根；脚本内容保持纯 ASCII 以避免 PowerShell 5.1 读取乱码。
- 新增 `docs/project/ENVIRONMENT.md`。

## 验证结果

- `scripts/setup_env.ps1`：`.venv` 建立成功，8 个依赖导入自检通过（耗时 2 分 35 秒）。
- `scripts/verify_all.ps1`：三步全部通过。
  - 数据校验通过（34 条来源、29 个本地文件、309 条证据、200 条样本）。
  - 评测内容校验通过，`sample_sha256` 未变（冻结集未被触碰）。
  - 单元测试 **45 项通过**。

## 尚未处置（已登记，属后续 Block 范围）

金标准泄漏尚存于以下位置，处置方案见 `references/AUDIT_FINDINGS.md`：

- `app/backend/research_data.py`（`supported_claims`）、`stage3_engine.py`（接收 `process_id`）、
  `flow_constraints.py`、`answer_strategy.py`、`claim_validation.py` → Block 3 / Block 4。
- `app/backend/rag_engine.py` 在线原型写死流程骨架、答案文本、事项→证据编号映射、seeded 冲突断言
  → Block 3 / Block 4。README 声称"不会退回写死答案"，与实现不符，需一并更正。

## 接续点

进入 **Block 2 判分口径修复**：新增 `app/backend/scoring_v2.py`，实现不依赖标注 `claim_id` 的
要素级匹配与引用支持性判定，并落地 LLM-as-judge 与人工校准切片。
