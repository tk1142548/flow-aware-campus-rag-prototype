# Flow-Aware Campus RAG Prototype

面向项目申报和演示截图的“流程感知校园办事 RAG”最小原型。

当前原型只覆盖两个本科事项：

- `UG_PROOF_PRINT`：本科成绩单 / 在学证明 / 毕业证明打印
- `UG_STATUS_CHANGE`：本科休学 / 复学

## 技术栈

- `FastAPI`：主链路与 `/api/query`
- `Next.js + Tailwind`：单页前端
- `JSONL + BM25 + FAISS`：轻量证据检索
- `OpenAI-compatible API`：槽位补全、流程骨架生成、断言核验、答案润色

## 目录

- `app/frontend`：Next.js 前端
- `app/backend`：FastAPI 后端
- `data/raw`：来源清单
- `data/clean`：清洗文本
- `data/evidence`：evidence units
- `scripts`：启动脚本
- `tools/node-v22.14.0-win-x64`：本地 Node 运行时

## 当前实现

- 规则优先识别事项与关键槽位
- 在事项内做 `BM25 + FAISS` 混合检索
- 右侧展示证据包、流程骨架、断言核验和官方入口/下载
- 支持同一会话内的轻量上下文继承
  - 例如先问“我想打证明”，再补“本科，在学证明”，系统会继续完成同一事项
- 若模型不可用，会自动退回证据驱动回答，但不会退回成写死的固定答案

## 数据说明

证据库当前共 30 条 evidence units，主证据来自暨南大学本科生院和研究生院官方页面。

已经修正为稳定可用的关键链接包括：

- 打印成绩单、证明页：
  - `https://jwc.jnu.edu.cn/2021/0317/c11805a602515/page.htm`
- 休学申请表页：
  - `https://jwc.jnu.edu.cn/2021/0313/c6757a600991/page.htm`
- 休学申请表 PDF：
  - `https://jwc.jnu.edu.cn/_upload/article/files/26/18/5fde309f47a3a4eb7f037a4a720b/1b6a2c01-631c-4162-8915-510adeddc284.pdf`
- 复学申请表页：
  - `https://jwc.jnu.edu.cn/2021/0313/c6757a600999/page.htm`
- 复学申请表 PDF：
  - `https://jwc.jnu.edu.cn/_upload/article/files/85/ed/532b7c2740ea81fbf5515c8eae02/e9589e0b-b39a-4964-a7bf-cc892fe2082e.pdf`

## 环境

根目录 `.env.local` 需要：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`

前端 `app/frontend/.env.local` 需要：

- `BACKEND_API_BASE=http://127.0.0.1:8000`

可参考 `.env.example`。

## 启动

后端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_backend.ps1
```

前端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_frontend.ps1
```

访问：

- 前端 [http://127.0.0.1:3000](http://127.0.0.1:3000)
- 后端健康检查 [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

## API

`POST /api/query`

请求体：

```json
{
  "query": "我是本科生，想打印在学证明，需要去哪里？",
  "session_id": "optional-session-id"
}
```

返回字段包括：

- `item_id`
- `slots`
- `action`
- `follow_up_question`
- `evidence_cards`
- `official_links`
- `flow_skeleton`
- `assertions`
- `final_answer`

## 固定演示问题

1. 我是本科生，想打印在学证明，需要去哪里？
2. 本科生办理休学要怎么做，需要准备什么材料？
3. 我复学是不是开学第二周前都可以提交申请？
4. 我想打证明。
