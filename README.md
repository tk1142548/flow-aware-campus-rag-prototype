# 流程感知的校园办事 RAG 问答

面向校园办事场景的检索增强问答研究：把办事事项的官方材料整理成可定位、可区分版本的
证据层，把办事流程表示为结构化中间形式，并用它决定系统该直接回答、该追问、
该按版本限定作答、该纠正对象范围，还是该拒答。

## 语料与数据

以暨南大学本科教学相关事项为语料，覆盖 8 类事项：

| 事项 | 内容 |
|---|---|
| 成绩与证明打印 | 成绩单、在学证明、英文毕业证明打印 |
| 学籍状态变更 | 休学、复学 |
| 退学办理 | 主动申请退学、清退 |
| 学生证补办 | 补办与缴费 |
| 选课事务 | 选课与课程调整 |
| 请假事务 | 事假、病假 |
| 转专业 | 转专业申请 |
| 证书补办 | 各类证明与证书补办 |

数据分三层：

- **来源层**（`data/research/source_records.jsonl`、`data/sources/`）：34 条来源记录与 29 个
  本地保存的官方来源文件，按官方发布年份分组，使"同一事项不同时期规定不同"在数据层可区分。
- **证据层**（`data/research/evidence_units.jsonl`）：309 条可定位的原子证据，
  每条都能回到原文的具体位置。
- **流程层**（`data/research/process_records.jsonl`）：13 条流程记录，
  含五类要素（办理步骤、适用条件、所需材料、时间约束、办理入口）、槽位表与允许声明。

评测数据：

- `data/evaluation/stage2_samples.jsonl`：200 条评测样本，覆盖 8 类事项与 8 类易错情形。
  每道题标注了应答方式、应覆盖的要点、所依据的材料与缺失的关键条件。
- `data/evaluation/high-risk-set.jsonl`：84 条高风险专项题集
  （信息缺失、对象错配、版本冲突、过期入口四类）。
- `data/schemas/`：上述记录的 JSON 模式。
- `data/audit/`：来源与证据的核验记录。

## 方法与实现

- `app/backend/sparse_retrieval.py`、`semantic_retrieval.py`、`hybrid_retrieval.py`：
  稀疏（BM25）、语义（向量嵌入）、混合检索。
- `app/backend/rerank.py`：交叉编码器重排序。
- `app/backend/flow_extractor.py`：由检索到的证据自动抽取流程骨架，每条要素绑定来源证据。
- `app/backend/systems.py`：基线 A/B/C 与本方法共用的预测契约。
- `app/backend/scoring_v2.py`：判分（按内容比对，不要求系统输出标注编号）。
- `app/backend/error_taxonomy.py`：错误分类与失效层归因。
- `app/frontend`：对话原型（Next.js）。

## 实验

| 数据文件 | 内容 |
|---|---|
| `data/experiments/retrieval-v2.json` | 检索策略对照（稀疏 / 语义 / 混合 / 混合+重排序） |
| `data/experiments/flow-extraction.json` | 流程骨架抽取的五类要素覆盖率与证据绑定率 |
| `data/experiments/baselines-final.json` | 八配置对照的逐样本结果与配对统计 |
| `data/experiments/error-analysis.json` | 分层误差归因 |
| `data/experiments/high-risk-results.json` | 高风险题集结果 |
| `data/experiments/task-completion.json` | 任务完成率（60 题判定） |

口径与误差分析见 `docs/experiments/`。

## 环境与运行

见 `docs/ENVIRONMENT.md`。快速开始：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_env.ps1
powershell -ExecutionPolicy Bypass -File scripts\verify_all.ps1
```

服务启动：`scripts\run_backend.ps1`（后端）与 `scripts\run_frontend.ps1`（前端）。
接口为 `POST /api/query`，前端默认 `http://127.0.0.1:3000`，
后端健康检查 `http://127.0.0.1:8000/api/health`。

## 语料来源

官方页面均以公开链接访问并保存本地副本，见 `data/research/source_records.jsonl`。
