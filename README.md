# 流程感知的校园办事 RAG 问答

面向校园办事场景的检索增强问答研究：把办事事项的官方材料整理成可定位、可区分版本的
证据层，把办事流程表示为结构化中间形式，并用它决定系统该直接回答、该追问、
该纠正提问前提，还是该拒答。

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
  本地保存的官方来源文件，记录网址、获取时间、发布日期与版本标签。
- **证据层**（`data/research/evidence_units.jsonl`）：309 条原子证据，
  每条都能回到原文的具体位置，并带陈述类型（办理步骤、材料、时限、入口、收费、适用对象等）。
- **流程层**（`data/research/process_records.jsonl`）：23 条流程记录，按事项下的子流程划分，
  含五类要素（办理步骤、适用条件、所需材料、时间约束、办理入口）、槽位表，
  以及"允许声明"——每条声明绑定其证据，构成出题与判分的金标准基础。

评测数据：

- `data/evaluation/dev-set.jsonl`：开发集，只用于调试系统，不产生结论数字。
- 确认集：由流程记录确定金标准、经人工审核后定稿，用于报告结果。
- `data/schemas/`：上述记录的 JSON 模式。

## 方法与实现

- `app/backend/sparse_retrieval.py`、`semantic_retrieval.py`、`hybrid_retrieval.py`、
  `retrieval_stack.py`：稀疏（BM25）、语义（向量嵌入）、混合检索与统一调用入口。
- `app/backend/rerank.py`：交叉编码器重排序。
- `app/backend/flow_extractor.py`：由检索到的证据抽取流程骨架，每条要素绑定来源证据。
- `app/backend/systems.py`：基线与本方法各配置的实现。
- `app/backend/scoring_v2.py`：判分。按内容比对要素，不要求系统输出标注编号，
  口径见 `docs/experiments/SCORING_PROTOCOL.md`。
- `app/backend/hypothesis_metrics.py`：按假设的主指标——流程骨架看多步骤题的步骤召回与顺序，
  断言核验看无据断言率，交互控制看应答方式的宏平均 F1 与过度追问率。
- `app/backend/stage4_statistics.py`：配对符号随机化、Holm 校正、事项簇自助区间。
- `app/backend/error_taxonomy.py`：错误分类与最早失效层归因。
- `app/frontend`：对话原型（Next.js）。

## 文档

- `docs/ENVIRONMENT.md`：环境、依赖、启动与校验命令。
- `docs/data/DATA_CONTRACT.md`：三层数据的字段契约。
- `docs/experiments/SCORING_PROTOCOL.md`：判分口径。

## 环境与运行

见 `docs/ENVIRONMENT.md`。快速开始：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_env.ps1
powershell -ExecutionPolicy Bypass -File scripts\verify_all.ps1
```

`verify_all.ps1` 依次执行来源与证据校验、流程记录校验与单元测试。
实验运行器为 `scripts\run_baselines.py`，接口探活为 `scripts\probe_endpoints.py`。

服务启动：`scripts\run_backend.ps1`（后端）与 `scripts\run_frontend.ps1`（前端）。
接口为 `POST /api/query`，前端默认 `http://127.0.0.1:3000`，
后端健康检查 `http://127.0.0.1:8000/api/health`。

## 语料来源

官方页面均以公开链接访问并保存本地副本，见 `data/research/source_records.jsonl`。
