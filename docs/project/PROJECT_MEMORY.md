# 项目记忆

最后更新：2026-07-17
当前阶段：阶段 1 进行中，阶段 1A、1B 已验证
当前状态：首批 5 个官方来源文件已固化，4 条旧 P0 记录已迁移为 12 条可定位证据；核心代码与旧运行数据尚未修改
最近接续点：执行阶段 1C，使用已保存的休学、复学 PDF 完成 UGS001、UGS004 至 UGS006、UGS011、UGS012 的逐条核验和迁移。

## 1. 项目背景与不可变约束

- 正式项目名称为《面向校园办事场景的流程感知 RAG 问答方法研究》，不得擅自改名。
- 项目已立项。内部候选定位可以调整，但核心研究方向和最终成果范围需要用户确认。
- 本地仓库是实际工作区，GitHub（代码托管平台）仓库是长期保存、同步和审计的事实源。
- 代码、研究规划、项目记忆、工作报告、技术决策和项目 Skill（技能）源文件保存在本仓库。
- 密钥、本机缓存、临时文件、可重建大型产物和敏感数据不得提交。
- 暂不大规模修改核心代码。先完成数据溯源、证据核验和评测基础。
- 低风险整理、测试、数据结构和文档修正可自主完成；方向、范围、大规模删除、显著成本和立项偏离需先请用户确认。

## 2. 当前真实实现状态

### 已验证

- 核心实现的技术审查基线提交为 `869e2a6`；阶段 0 工作流由提交 `dd7cb60` 引入并已同步到远程仓库。
- 阶段 1A 数据契约和审计基线由提交 `b6aa6d9` 引入并已同步到远程仓库。
- 受版本控制文件 27 个。
- 后端主链路位于 `app/backend/rag_engine.py`，核心类为 `EvidenceIndex` 和 `FlowAwareCampusRAG`。
- 当前只支持 `UG_PROOF_PRINT` 与 `UG_STATUS_CHANGE` 两个事项。
- 检索为 BM25 加字符级 TF-IDF 融合，并使用 FAISS 保存字符特征；不是真正的语义嵌入检索。
- 后端提供 `/`、`/api/health`、`/api/query`。
- 前端为单页 Next.js 应用，展示聊天、证据卡、流程骨架和断言状态。
- 前端生产构建成功；后端健康检查和查询接口冒烟测试成功。
- 大模型不可用时使用固定流程与回答模板。
- 数据包含 30 条证据、8 个来源、2 个事项，10 条证据缺少发布日期。
- 正式目标数据包含 5 条来源记录、5 个本地来源文件和 12 条已验证证据。
- 数据层 10 项自动测试通过；核心查询行为测试、持续集成、评测集、基线实验、消融实验和跨机器部署配置仍缺失。

### 已发现且仍影响旧运行链路

- UGS002、UGS003、UGS013、UGS014 的事实差异已在目标证据中修正，但旧 `data/evidence/evidence_units.jsonl` 仍保留原摘要，现有演示链路尚未切换。
- 流程骨架可能引用本次检索结果之外的固定证据编号。
- “第二周”冲突检测包含固定关键词触发。
- README 中“非硬编码回退”等表述与代码不完全一致。
- 启动脚本包含本机绝对路径。
- Next.js 15.2.4 存在已公开的严重安全风险，工程化阶段必须升级并回归测试。
- 仓库根目录曾存在申报书、答辩材料和导师准备文档的未跟踪副本；用户于 2026-07-17 确认这些文件由其主动移出，项目无需恢复、跟踪或考虑这些副本。

## 3. 工作状态

### 已完成并验证

- 完整技术审查：仓库、提交历史、代码、数据、前后端、构建、接口和外部参考项目。
- 建立 `AGENTS.md` 项目导航。
- 建立推进方案、项目记忆和决策日志。
- 创建项目专用 Skill `advance-campus-rag-research`。
- 创建 Skill 同步脚本。
- 扩展 `.gitignore` 的密钥、缓存、临时产物和实验产物边界。
- 生成首份工作报告。
- 建立来源记录和证据单元 JSON Schema（JSON 模式）。
- 建立 8 行来源审计表和 30 行证据审计表。
- 实现数据模式、外键、旧数据映射和审计覆盖校验。
- 添加 2 个正例、4 个模式反例和 1 个缺失来源外键反例。
- 保存成绩证明页面、休学表格落地页与 PDF、复学表格落地页与 PDF，共 5 个官方来源文件。
- 为 5 个文件记录抓取时间、最终地址、媒体类型、字节数、HTTP 状态和 SHA-256。
- 核验两份单页 A4 表格的文本提取和整页渲染；核验两个落地页与附件地址的对应关系。
- 将 UGS002、UGS003、UGS013、UGS014 拆分迁移为 12 条目标证据，并在审计表建立一对多映射。
- 数据校验覆盖正式 JSONL（逐行 JSON）模式、反向来源关系、路径、哈希、文件签名、发布域名和迁移闭环。
- 数据校验脚本和 10 项自动测试通过。

### 进行中

- 无。

### 下一步

1. 从休学 PDF 迁移 UGS001、UGS004、UGS005、UGS006。
2. 从复学 PDF 迁移 UGS011、UGS012。
3. 对时间约束、课程处理和学籍后果拆成独立证据，不把多个条件压缩到一条声明。
4. 更新审计映射和来源复核进度。
5. 为新增证据补充模式、外键、锚文本和迁移状态校验。
6. 完成后进入成绩证明页面 UGP001 至 UGP009 的迁移。

## 4. 关键技术决策

- 正式项目名称保持不变。
- 当前候选研究问题是流程结构、条件槽位和证据绑定能否降低对象、版本、步骤和无证据断言错误；该问题尚待数据与实验验证。
- 第一实施阶段聚焦来源与证据，不先更换框架或增加复杂模型。
- 原始来源、规范化证据、流程结构和评测样本必须分层保存。
- 一个来源记录只对应一个能够独立保存并计算哈希的文件；落地页与附件必须使用不同来源编号并建立关系。
- 旧运行数据和目标数据契约暂时并存，完成快照、原文定位和校验后再切换加载器。
- 旧错误摘要保留在原数据与审计台账中；修正内容写入目标证据，通过 `target_evidence_ids` 保存一对一或一对多迁移关系。
- 复合声明按可独立定位和评测的事实拆成原子证据。
- 任何回答声明都应能够绑定本次实际检索到的证据。
- 实验必须记录数据版本、配置、随机种子、模型版本、原始输出、指标、耗时和费用。

## 5. 已知问题、技术债与风险

- 其余 5 个旧来源尚未保存；已保存成绩证明页面的 9 条旧证据尚未逐条定位。
- 26 条旧证据尚未迁移，旧证据正文仍可能混入解释和错误。
- 休学和复学 PDF 只显示制表月份，具体发布日期、生效区间和替代关系仍无证据。
- 两个检索器都高度依赖词面重合，缺乏真正独立的语义信号。
- 检索、流程生成、回答和验证集中在单个大文件中。
- 会话保存在进程内存中。
- 大模型调用缺少重试、缓存、模式强校验和费用记录。
- 输入校验、跨域限制和依赖安全尚未完善。
- 没有自动测试，任何数据或代码修改都可能引入静默回退。
- 真实版本冲突和复杂条件样本数量尚不确定，可能影响研究问题成立。

## 6. 重要文件与命令

### 导航与长期文档

- `AGENTS.md`
- `docs/project/PROJECT_PLAN.md`
- `docs/project/PROJECT_MEMORY.md`
- `docs/project/DECISIONS.md`
- `docs/work-reports/`
- `docs/data/DATA_CONTRACT.md`
- `skills/advance-campus-rag-research/SKILL.md`

### 代码与数据

- 后端主链路：`app/backend/rag_engine.py`
- 接口：`app/backend/main.py`
- 大模型客户端：`app/backend/llm_client.py`
- 前端页面：`app/frontend/app/page.js`
- 来源登记：`data/raw/source_manifest.json`
- 清洗摘要：`data/clean/source_texts.json`
- 证据单元：`data/evidence/evidence_units.jsonl`
- 来源审计：`data/audit/source-audit.csv`
- 证据审计：`data/audit/evidence-audit.csv`
- 来源模式：`data/schemas/source-record.schema.json`
- 证据模式：`data/schemas/evidence-unit.schema.json`
- 来源采集清单：`data/research/source_capture_plan.json`
- 正式来源记录：`data/research/source_records.jsonl`
- 正式目标证据：`data/research/evidence_units.jsonl`
- 来源快照：`data/sources/`
- 来源采集脚本：`scripts/capture_official_sources.py`
- 原始来源字节保护：`.gitattributes`

### 状态恢复

```powershell
git status --short
git log -5 --oneline --decorate
Get-Content -Raw docs/project/PROJECT_MEMORY.md
Get-Content -Raw docs/project/PROJECT_PLAN.md
```

### Skill 同步

```powershell
powershell -ExecutionPolicy Bypass -File scripts/sync_project_skill.ps1
```

### 已验证接口

- `GET /`
- `GET /api/health`
- `POST /api/query`

启动脚本当前含本机路径，使用前先检查 `scripts/run_backend.ps1` 和 `scripts/run_frontend.ps1`。

### 数据校验

```powershell
python scripts/validate_research_data.py
python -m unittest discover -s tests -p "test_*.py" -v
```

首次按清单采集来源：

```powershell
python scripts/capture_official_sources.py
```

已存在快照时脚本拒绝覆盖；重新抓取必须建立新版本编号、路径和来源记录输出。

## 7. 需要用户确认的问题

- 最终事项范围和评测样本规模：阶段 1 资料普查后提交选项。
- 核心研究贡献及最终成果形式：阶段 2 初步基线后提交选项。

## 8. 最近一次工作的明确接续点

下一轮从“阶段 1C：已保存休学、复学表格的剩余证据迁移”开始：

1. 读取本文件、推进方案阶段 1 和决策日志。
2. 检查当前 Git 状态，确认未覆盖用户未跟踪文件。
3. 读取 `data/research/evidence_units.jsonl` 中本轮 12 条证据，沿用原子化与定位规则。
4. 依据休学 PDF 核验 UGS001、UGS004 至 UGS006。
5. 依据复学 PDF 核验 UGS011、UGS012。
6. 更新 `target_evidence_ids`、来源审计进度和自动测试预期。
7. 执行完整数据校验与 10 项以上自动测试。
8. 本轮仍不修改 `rag_engine.py` 的核心查询行为。
