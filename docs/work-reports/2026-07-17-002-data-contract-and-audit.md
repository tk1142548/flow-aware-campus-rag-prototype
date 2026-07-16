# 工作报告 002：数据契约与审计基线

日期：2026-07-17
总体状态：已验证
对应阶段：阶段 1A，数据契约与审计台账

## 1. 本轮目标

在不修改核心查询链路和旧运行数据的前提下：

- 定义来源记录和证据单元的目标数据契约；
- 建立 8 个现有来源和 30 条现有证据的初始审计台账；
- 明确有效记录与失败条件；
- 实现可重复的数据校验命令和自动测试；
- 为下一轮官方来源保存与逐条证据核验建立稳定入口。

## 2. 状态摘要

| 内容 | 状态 |
|---|---|
| 来源记录模式 | 已验证 |
| 证据单元模式 | 已验证 |
| 来源审计台账 | 已验证，8 行 |
| 证据审计台账 | 已验证，30 行 |
| 正反样例 | 已验证 |
| 外键和旧数据映射校验 | 已验证 |
| 自动测试 | 已验证，4 项通过 |
| 旧运行数据迁移 | 计划，尚未执行 |
| 核心查询代码修改 | 未执行，符合本轮范围 |

## 3. 实际完成

### 3.1 来源记录契约

新增 `data/schemas/source-record.schema.json`，要求来源记录包含：

- 稳定来源编号、标题、规范网址和官方机构；
- 文件格式和资料角色；
- 发布日期状态及日期类型；
- 抓取状态、时间、SHA-256（安全哈希算法）、本地路径和 HTTP 状态；
- 当前、历史、限时或未知版本状态；
- 来源之间的落地页、附件和链接关系；
- 人工复核状态。

模式规定一个来源记录只对应一个可独立保存和计算哈希的文件。表格落地页和 PDF（便携式文档格式）附件必须分别登记。

### 3.2 证据单元契约

新增 `data/schemas/evidence-unit.schema.json`，将以下内容分开：

- 可逐字核验的原文；
- 供检索和流程建模使用的规范化声明；
- 页码、章节、段落、表格单元或表单字段定位；
- 适用对象、时间和条件；
- 声明类型、关键词和人工复核状态。

证据通过 `source_id` 外键引用实际承载原文的来源文件。

### 3.3 初始审计台账

新增：

- `data/audit/source-audit.csv`
- `data/audit/evidence-audit.csv`

台账覆盖：

- 8 个来源；
- 30 条证据；
- 10 条缺少发布日期的旧证据；
- 30 条缺少逐字原文的旧证据；
- 30 条只有描述性 `location_hint` 的旧证据；
- 4 条已知事实差异：UGS002、UGS003、UGS013、UGS014。

所有旧证据的迁移状态保持为 `pending`，没有把人工摘要提前标记为已验证原文。

### 3.4 校验工具与测试

新增 `scripts/validate_research_data.py`，校验：

- JSON Schema（JSON 模式）合法性；
- 正例通过和反例失败；
- 目标证据的来源外键；
- 来源、网址和证据编号唯一性；
- 旧证据网址到来源清单的映射；
- 审计表对当前来源和证据的完整覆盖；
- 审计证据数量、发布日期状态和来源编号一致性；
- 四条已知差异必须明确标记；
- 审计状态枚举和下一步任务非空。

新增 `tests/test_research_data_validation.py`，使用 Python 标准库 `unittest`（单元测试框架），避免为当前四项测试额外引入测试框架。

### 3.5 负例覆盖

模式与外键负例覆盖：

1. 已抓取来源缺少哈希；
2. 非法日历日期 `2026-02-31`；
3. 非法证据编号；
4. 证据没有页码、章节或锚文本；
5. 证据引用不存在的来源编号。

最初只覆盖缺少哈希和无定位。对照推进方案验收条件后，补充了错误日期、非法编号和缺失来源三类负例。

## 4. 文件变更

| 文件 | 类型 | 用途 |
|---|---|---|
| `requirements-dev.txt` | 新增 | 固定数据校验依赖 |
| `data/schemas/source-record.schema.json` | 新增 | 来源目标契约 |
| `data/schemas/evidence-unit.schema.json` | 新增 | 证据目标契约 |
| `data/audit/source-audit.csv` | 新增 | 8 个来源的审计基线 |
| `data/audit/evidence-audit.csv` | 新增 | 30 条证据的审计基线 |
| `scripts/validate_research_data.py` | 新增 | 模式、外键和审计一致性校验 |
| `tests/test_research_data_validation.py` | 新增 | 自动测试 |
| `tests/fixtures/data/` | 新增 | 2 个正例、5 个负例 |
| `docs/data/DATA_CONTRACT.md` | 新增 | 数据层次、迁移边界和命令 |
| `AGENTS.md` | 修改 | 增加数据契约和校验入口 |
| `PROJECT_PLAN.md` | 修改 | 阶段 1 改为进行中并记录 1A 进度 |
| `PROJECT_MEMORY.md` | 修改 | 更新真实状态和阶段 1B 接续点 |
| `DECISIONS.md` | 修改 | 记录迁移隔离和一文件一来源决策 |

## 5. 测试与校验结果

### 5.1 全量数据校验

执行：

```powershell
python scripts/validate_research_data.py
```

结果：退出状态 0。

```text
valid_fixtures_accepted: 2
invalid_fixtures_rejected: 4
invalid_link_fixtures_rejected: 1
manifest_sources: 8
legacy_evidence_units: 30
source_audit_rows: 8
evidence_audit_rows: 30
legacy_missing_publish_date: 10
known_mismatch_rows: 4
legacy_unmigrated_rows: 30
```

### 5.2 分范围校验

执行：

```powershell
python scripts/validate_research_data.py --scope schemas
python scripts/validate_research_data.py --scope repository
```

结果：两个命令退出状态均为 0。

### 5.3 自动测试

执行：

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

最终提交前结果：4 项测试通过，耗时约 0.029 秒。

### 5.4 Python 语法

执行：

```powershell
python -m compileall -q scripts tests
```

结果：退出状态 0。

### 5.5 开发依赖

当前环境实际使用 `jsonschema==4.26.0`，已写入 `requirements-dev.txt`。

执行：

```powershell
python -m pip install --dry-run -r requirements-dev.txt
```

结果：退出状态 0，运行依赖与 `jsonschema==4.26.0` 均已满足。

### 5.6 提交与远程同步

本轮主要变更形成提交：

`b6aa6d9 feat: add research data contracts and audit baseline`

记录验证结果的后续文档提交：

`528ac95 docs: record stage 1a verification`

两次执行 `git push origin main` 均成功。主要变更推送完成时：

- 本地提交：`b6aa6d993bbf0d773ec698fefb1abd5cee95850b`
- 远程 `origin/main`：`b6aa6d993bbf0d773ec698fefb1abd5cee95850b`

两者一致。三份用户原有材料未包含在提交中。

## 6. 尚未验证或未完成

- 尚未在 `data/sources/` 保存正式官方页面和附件。
- 目标来源记录当前只有测试正例，没有正式数据。
- 目标证据记录当前只有测试正例，没有正式迁移数据。
- 30 条旧证据尚未完成原文级核验。
- 四条 P0 差异尚未修改旧运行数据。
- 当前模式尚未经过第一批真实来源迁移的反馈，阶段 1B 后需要复审字段是否足够。
- 核心加载器仍读取旧 `evidence_units.jsonl`。

## 7. 失败、困难与新发现

- 初始负例覆盖不足，不能证明推进方案列出的全部失败条件。已补齐并重新验证。
- 来源模式最初将文件格式和资料角色混在一个字段，并试图用一个记录表示落地页与 PDF。迁移前自审发现该设计会丢失独立哈希和版本信息，已修正为“一文件一来源记录＋关系字段”。
- `jsonschema.__version__` 检查产生弃用警告，仅出现在临时验证命令中，不影响项目代码；正式工具未使用该接口。
- 最终 Git 状态复核时，本轮开始仍在仓库根目录的三份未跟踪材料副本已经不在该目录。只读搜索确认相同文件名、大小和修改时间的原件仍位于 `E:\个人文件\已产出且可复用的结果文件`：
  - 申报书 DOC（文档文件）：1,857,674 字节；
  - 导师面谈文档：42,328 字节；
  - 答辩 PPTX（演示文稿文件）：47,273 字节。
  用户随后确认这些副本由其主动移出，项目无需恢复、提交或继续考虑这些文件。

## 8. 对推进方案和决策的影响

- 阶段 1 从“计划”改为“进行中”。
- 阶段 1A 已完成，下一步进入 P0 来源保存和登记。
- 确认旧运行结构与目标研究数据结构暂时并存。
- 确认落地页与附件分别登记，证据引用实际承载原文的文件。
- 在首批真实迁移通过前，不修改核心加载器。

## 9. 需要用户决定

本轮没有阻塞性决定。用户已明确允许自动提交，并确认三份材料由其主动移出且无需项目考虑；对应问题已经在决策日志中关闭。

## 10. 下一轮接续任务

执行阶段 1B“P0 来源保存与登记”：

1. 建立受版本控制的 `data/sources/` 目录结构。
2. 保存成绩证明页面。
3. 分别保存休学表格落地页和 PDF。
4. 分别保存复学表格落地页和 PDF。
5. 计算哈希、记录抓取时间、HTTP 状态、规范网址和来源关系。
6. 生成正式目标来源记录并通过模式校验。
7. 更新来源审计表，但未完成内容核验的来源不得标为 `verified`。
8. 开始 UGS002、UGS003、UGS013、UGS014 的逐字段证据核验。
