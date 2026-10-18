# 流程感知的校园办事 RAG 问答

面向校园办事场景的检索增强问答研究：把办事事项的官方材料整理成可定位、可区分版本的
证据层，把办事流程表示为结构化中间形式，并用它决定系统该直接回答、该追问、
该按版本限定作答、该纠正对象范围，还是该拒答。

## 语料与数据

以暨南大学本科教学相关事项为语料，覆盖 8 类事项：

| 事项 | 覆盖内容 | 证据条数 |
|---|---|---:|
| 成绩与证明打印 | 成绩单、在学证明、英文毕业证明打印、密封 | 80 |
| 休学复学与学籍状态 | 休学、复学、未注册处理 | 56 |
| 退学办理 | 主动申请退学、清退 | 113 |
| 学历学位证书补办 | 毕业证明书、学位证明书 | 21 |
| 本科生请假 | 事假、病假 | 12 |
| 本科生转专业 | 转专业申请 | 11 |
| 本科选课办理 | 选课与课程调整 | 9 |
| 学生证补办 | 补办与缴费 | 7 |

数据分三层：

- **来源层**（`data/research/source_records.jsonl`、`data/sources/`）：34 条来源记录与 29 个
  本地保存的官方来源文件，按官方发布年份分组，使"同一事项不同时期规定不同"在数据层可区分。
- **证据层**（`data/research/evidence_units.jsonl`）：309 条可定位的原子证据，
  每条都能回到原文的具体位置，并带陈述类型（办理步骤、材料、时限、入口、收费、适用对象等）。
- **流程层**（`data/research/process_records.jsonl`）：23 条流程记录，按事项下的子流程划分，
  含五类要素（办理步骤、适用条件、所需材料、时间约束、办理入口）、槽位表，
  以及"允许声明"——每条声明恰好绑定一条证据，构成出题与判分的金标准基础。

评测数据：

- `data/evaluation/stage2_samples.jsonl`：200 条评测样本，覆盖 8 类事项与 8 类易错情形
  （直接问答、信息缺失、对象错配、步骤错误、材料混淆、版本冲突、多轮、越界）。
  每道题标注了应答方式、应覆盖的要点、所依据的材料与缺失的关键条件。
  这批样本参与过方法迭代，其上的数字属探索性。
- `data/evaluation/independent-set.jsonl`：120 条独立验证样本，8 类事项各 15 条，
  出题只读官方证据与流程记录；指标、对照与判定规则在运行前登记，见
  `docs/experiments/INDEPENDENT_SET_PREREGISTRATION.md`。
- `data/evaluation/high-risk-set.jsonl`：84 条高风险专项题集
  （信息缺失、对象错配、版本冲突、过期入口四类）。
- `data/schemas/`：上述记录的 JSON 模式。
- `data/audit/`：来源与证据的核验记录。

## 方法与实现

- `app/backend/sparse_retrieval.py`、`semantic_retrieval.py`、`hybrid_retrieval.py`、
  `retrieval_stack.py`：稀疏（BM25）、语义（向量嵌入）、混合检索与统一调用入口。
- `app/backend/rerank.py`：交叉编码器重排序。
- `app/backend/flow_extractor.py`：由检索到的证据自动抽取流程骨架，每条要素绑定来源证据。
- `app/backend/systems.py`：十二条配置的实现。三个基线（向量检索直接生成、混合检索加重排序加引用、
  受限工作流）与本方法的逐项开关，含六档应答方式、弱形态与强形态的断言核验。
- `app/backend/scoring_v2.py`：判分。按内容比对要素，不要求系统输出标注编号；
  整体成功率为多项合取，口径见 `docs/experiments/SCORING_PROTOCOL_V2.md`。
- `app/backend/stage4_statistics.py`：配对符号随机化、Holm 校正、事项簇自助区间。
- `app/backend/error_taxonomy.py`：错误分类与失效层归因（检索 → 流程 → 核验 → 生成 → 交互）。
- `app/frontend`：对话原型（Next.js）。

## 实验

| 数据文件 | 内容 |
|---|---|
| `data/experiments/retrieval-v2.json` | 检索策略对照（稀疏 / 语义 / 混合 / 混合+重排序） |
| `data/experiments/flow-extraction.json` | 流程骨架抽取的五类要素覆盖率与证据绑定率 |
| `data/experiments/baselines-final.json` | 开发集十二配置的逐样本结果与配对统计 |
| `data/experiments/baselines-final-verdicts.json` | 开发集上四条判定的机器可读结果 |
| `data/experiments/independent-baselines.json` | 独立集十二配置的逐样本结果 |
| `data/experiments/independent-baselines-verdicts.json` | 独立集预注册判定、配套对照与分层表 |
| `data/experiments/independent-error-analysis.json` | 独立集分层误差归因 |
| `data/experiments/error-analysis.json` | 开发集分层误差归因 |
| `data/experiments/high-risk-results.json` | 高风险题集结果 |
| `data/experiments/task-completion.json` | 任务完成率（60 题人工三档判定） |
| `data/experiments/judge-calibration.json` | LLM 判官的支持性判定与校准结果 |
| `data/experiments/invalid/` | 因接口故障作废的运行结果，仅作留档，不参与任何结论 |

每个逐样本结果都保存了该样本的检索证据编号、预测文本、预测应答方式与逐项指标，
判分可以离线复算，不需要重新调用模型。

## 文档

- `docs/ENVIRONMENT.md`：环境、依赖、启动与校验命令。
- `docs/data/DATA_CONTRACT.md`：三层数据的字段契约。
- `docs/data/STAGE_2_ANNOTATION_GUIDE.md`：样本标注规范，含六档应答方式的定义。
- `docs/experiments/SCORING_PROTOCOL_V2.md`：判分口径。
- `docs/experiments/ERROR_ANALYSIS.md`：开发集十二配置的误差分析。
- `docs/experiments/INDEPENDENT_SET_PREREGISTRATION.md`：独立集预注册。
- `docs/experiments/INDEPENDENT_SET_RESULTS.md`：独立集结果与已知边界。

## 环境与运行

见 `docs/ENVIRONMENT.md`。快速开始：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_env.ps1
powershell -ExecutionPolicy Bypass -File scripts\verify_all.ps1
```

`verify_all.ps1` 依次执行研究数据校验、流程记录校验、评测内容校验与单元测试。
实验运行器为 `scripts\run_baselines.py`，判定脚本为 `scripts\judge_hypotheses.py`，
接口探活为 `scripts\probe_endpoints.py`。

服务启动：`scripts\run_backend.ps1`（后端）与 `scripts\run_frontend.ps1`（前端）。
接口为 `POST /api/query`，前端默认 `http://127.0.0.1:3000`，
后端健康检查 `http://127.0.0.1:8000/api/health`。

## 语料来源

官方页面均以公开链接访问并保存本地副本，见 `data/research/source_records.jsonl`。
