# 审查结论：泄漏点、冗余测试、一次性脚本

审查日期：2026-10-14。方法：全仓 grep + 逐条核对 `file:line` + 可疑短语在 200 条样本中的命中分布比对。
**结论可直接使用，不要重查。** 若需复核，重新执行的检索式为：
`grep -rn "gold\|allowed_claims\|process_id\|scenario_type\|difficulty\|version_risk\|source_version_ids" app/ scripts/ tests/`

---

## 一、金标准 / 评测标签泄漏进推理链路（共 32 处，分四组）

### A 组　`app/backend/stage4_pipeline.py`（已整体删除）

除已知的"读 `allowed_claims` 当回答"外，同文件还有：用 `applicable_step_ids` 反推步骤、材料取自 `process['materials']`、追问文本取自 `follow_up_rules`、`ROUTING_HINTS` 事项关键词表、`OUT_OF_SCOPE_TERMS` 越界词表、`UNCERTAINTY_RE / WRONG_ACTION_RE / VERSION_RE / OBJECT_RE` 四张正则表、逐事项写死的 `_should_emit_steps / _should_emit_materials`、`'DIPLOMA' in process_id` 硬编码。

**决定性证据**：`WRONG_ACTION_RE` 中 `复印件由别人` 只命中 `S2E-CR-004`、`当天就直接` 只命中 `S2E-CR-016`、`各几份` 只命中 `S2E-CR-018`、`照片信息和注册栏` 只命中 `S2E-SR-024`、`2026年新规则` 只命中 `S2E-WD-012` —— 这些表是**按冻结测试集问法逐题定制**的。该文件的意图判定与 `gold.response_mode` 同口径，等于用题库特征直接产出评测标签。

### B 组　backend 同族模块（把金标准流程转成推理输入，**尚未处置**）

| 文件 | 行 | 内容 | 严重 |
|---|---|---|---|
| `app/backend/research_data.py` | 46-50 | `supported_claims()` 直接返回 `process["allowed_claims"]` | 高 |
| `app/backend/stage3_engine.py` | 18-41 | `query(..., process_id=...)` 接收金标准流程号并据此取声明与上下文 | 高 |
| `app/backend/flow_constraints.py` | 5-19 | `supported_process_context()` 由 `allowed_claims` 派生 claims/steps/materials | 中 |
| `app/backend/answer_strategy.py` | 5-18 | `build_answer_context()` 以金标准 claim_ids 构造回答上下文 | 中 |
| `app/backend/claim_validation.py` | 5-29 | 以 `allowed_claims` 逐字比对，把"复述金标准"当作正确性 | 中 |
| `app/backend/error_taxonomy.py` | 11-20 | `scenario_type` 作为入参穿透（当前调用方传 None，未实际泄漏） | 低 |

处置方向：这些模块要么只允许评分侧调用（改名 + 加约束），要么改为基于证据蕴含判定。**推理入口不得接收 `process_id`。**

### C 组　运行脚本用样本金标准字段当检索条件（**尚未处置**）

| 文件 | 行 | 内容 |
|---|---|---|
| `scripts/run_stage3_formal.py` | 53, 60 | 检索与校验直接用 `x['process_id']` —— "已知答案所在流程"的 oracle 条件检索 |
| `scripts/run_stage3_unified.py` | 27, 45-58 | `--process` 由人工传入金标准流程号 |
| `scripts/run_stage3_sparse.py` | 34 | 输出全部流程的 `allowed_claims` 供查阅（低风险诊断输出） |

处置方向：oracle 条件检索的结果（`data/audit/stage3-formal-*.json`）不得作为检索成绩；Block 3 重新做无 oracle 的端到端检索。

### D 组　`app/backend/rag_engine.py` 在线原型写死答案（**尚未处置，属 Block 2/3 范围**）

| 行 | 内容 | 严重 |
|---|---|---|
| 521-580 | `_fallback_flow_skeleton` 按事项硬编码整段流程骨架，并写死证据编号 `UGP001..UGP011`、`UGS001..UGS019` | 高 |
| 656-670 | `_fallback_answer` 硬编码最终答案文本，含 `第一周周三`、`020-85220035`、`行政办公楼129室`、`2000至2006年` 等事实 | 高 |
| 715-725 | 针对"第二周"问法的 seeded 冲突断言，写死 `UGS012/UGS019` 与结论 | 高 |
| 434-485、27-30 | `build_official_links` / `OFFICIAL_DOWNLOAD_URLS`：事项→固定 evidence_id / URL 映射 | 中 |
| 340-345、347-394、140-158、161-162、294-334、235-238、279-287 | 意图词表、校区/事由列表、时间正则、受众惩罚项、省略式追问短语表、证据过滤写死规则 | 中 |

**注意**：`README.md` 声称"模型不可用时退回证据驱动回答，不会退回写死答案"，与实现相反。处置方向：删除硬编码骨架与答案，默认走 LLM 分支；离线时退回**由检索证据拼装**，而不是字面量。

### E 组　文档与实现矛盾（支撑证据）

`configs/stage4-experiment.json:15` 声明 `gold_access: scoring_only`；`docs/experiments/STAGE4_PROTOCOL.md:9`、`docs/work-reports/2026-10-12-017-*.md:9`、`scripts/run_stage4_experiments.py:147` 均声明"金标准只参与评分"——全部与实现不符。相关文件已删除，历史工作报告保留但需写失效记录。

### 已确认干净的范围

`app/backend/main.py`、`app/frontend/*`（仅 `page.js:27` 有 UI 默认事项，低）、`sparse_retrieval.py`、`semantic_retrieval.py`、`hybrid_retrieval.py`、`retrieval_metrics.py`、`experiment_logging.py`、`config.py`、`llm_client.py`、`stage4_statistics.py`
`scripts/run_stage4_experiments.py:98-110` 的推理入参只有 query + provided_slots，且 24 条 `provided_slots` 取值全部出现在对话原文中，不构成泄漏。
数据构造脚本（`build_stage2a_blueprint.py`、`build_stage2_content.py`、`author_stage2_content.py`）问句与金标准成对编写属构造流程本身，不算推理泄漏 —— 但这正是"评测集是开发集"的原因。

---

## 二、测试套件精简（86 → 目标 42）

### 整文件删除（9 个，共 31 条）

| 文件 | 理由 |
|---|---|
| `tests/test_stage4_pipeline.py` | 依赖已删模块 |
| `tests/test_process_records.py` | 与 `test_research_data_validation.py` 重复断言同一快照契约；断言错误消息子串；测试内重造数据迁就实现 |
| `tests/test_jsonl_boundary_repair.py` | 只为一次性修补脚本存在，绑定其内部实现 |
| `tests/test_stage2_binding_repair.py` | 同上，且修复已固化进数据、脚本不可复跑 |
| `tests/test_stage2_conversation_rebuild.py` | 同上；且断言话术含"版本"、恰好 3 轮（按配额造数） |
| `tests/test_stage2_entry_audit.py` | 一次性审计脚本 |
| `tests/test_independent_contract_review.py` | 一次性复核流程 |
| `tests/test_semantic_audit.py` | 测的是脚本内复制的 `cosine`（`semantic_retrieval.py` 已有一份） |
| `tests/test_review_checklist.py` | 子进程写仓库 + 魔数 200 + 与 `test_research_data_validation.py:561` 重复 |

### 部分删除（11 条）

- `tests/test_research_data_validation.py`：删 7 条一次性阶段迁移/配额断言（`:242`、`:255`、`:304`、`:371`、`:464`、`:554`、`:603`），保留 6 条通用校验契约（`:234`、`:551`、`:568`、`:624`、`:640`、`:659`）。
- `tests/test_semantic_retrieval.py`：删 `:18`（无效入参，与另两文件重复）、`:25`（批量上限守卫）。
- `tests/test_hybrid_and_strategy.py`：删 `:23`（无效 alpha，重复）。
- `tests/test_stage3_modules.py`：删 `:57`（防御式参数断言，重复）。

### 合并（不减用例数，仅减文件）

- `tests/test_stage3_baseline_runner.py` + `tests/test_unified_runner_contract.py` → 一个 runner 测试文件。
- `tests/test_retrieval_metrics.py` 两条合一条；`tests/test_stage4_statistics.py:31` 三组非法输入合一条。

### fixtures 问题

`tests/fixtures/invalid/` 的反例**多字段同时破坏**（如 `evidence-unit-invalid-id.json` 除 id 外还改了 audience/keywords/review），因果不纯，可能因错误原因被拒收。**建议每个反例只破坏一条规则。**
另：`data/research/stage2b-withdrawal-annotation-examples.json` 固定 4 版本组 / 4 正例 / 5 反例，且 `validate_research_data.py:2941-2951` 要求反例文本含 5 个指定 marker —— 正反例是为验收话术定制的。随对应用例删除，可一并清理。

---

## 三、一次性脚本（删除清单）

### 可安全删除：一次性 + 全仓库零引用（22 个）

```
scripts/author_stage2_content.py
scripts/build_stage2_content.py
scripts/add_credentials_review.py
scripts/add_stage2_baseline_processes.py
scripts/complete_stage2b_course_selection.py
scripts/complete_stage2b_credentials.py
scripts/complete_stage2b_leave.py
scripts/complete_stage2b_major_change.py
scripts/complete_stage2b_review.py
scripts/complete_stage2b_student_card.py
scripts/fix_all_process_hashes.py
scripts/fix_audit_findings.py
scripts/fix_credentials_contract.py
scripts/fix_leave_contract.py
scripts/fix_literal_newlines.py
scripts/fix_stage2b_student_card.py
scripts/normalize_process_file.py
scripts/repair_process_jsonl.py
scripts/rewrite_process_hash.py
scripts/reconcile_stage2b_review_status.py
scripts/review_stage2b_evidence.py
scripts/update_memory_current.py
```

**重跑风险（支撑删除决策）**：
- `reconcile_stage2b_review_status.py` 会把已 `verified` 的证据和 11 条流程改回 `in_review`。
- `author_stage2_content.py` / `build_stage2_content.py` 会整体重写 `stage2_samples.jsonl`，把冻结版本 `1.0.1-frozen` 改成 `0.2.0-content`。
- 多个 `fix_*.py` 直接就地改写 `data/research/*.jsonl`，无幂等保护。

### 仅被 docs 历史报告引用，建议归档保留（5 个）

`build_stage2a_blueprint.py`、`complete_stage1e_migration.py`、`complete_stage2b_withdrawal.py`、`finalize_stage2_freeze.py`、`repair_credential_process_contract.py`

### 正式流程，保留（26 个）

`capture_official_sources.py`、`validate_*.py`、`run_stage{2,3}_*.py`（`run_stage3_formal.py` 已删）、`audit_stage2_content.py`、`build_stage2_review_checklist.py`、`run_backend.ps1`、`run_frontend.ps1`、`sync_project_skill.ps1` 等。
