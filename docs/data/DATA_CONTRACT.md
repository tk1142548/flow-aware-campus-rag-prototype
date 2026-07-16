# 来源与证据数据契约

最后更新：2026-07-17
状态：阶段 1A 已验证

## 1. 目的

当前运行数据 `data/raw/source_manifest.json` 与 `data/evidence/evidence_units.jsonl` 是早期演示结构：

- 来源没有本地快照、抓取时间、哈希和版本关系；
- 证据中的 `content` 是人工规范化摘要，不是可定位的官方原文；
- `location_hint` 只能帮助人工寻找内容，不能证明具体声明来自哪个页码或段落；
- 证据通过重复保存标题和网址关联来源，没有稳定的 `source_id` 外键；
- 已发现 UGS002、UGS003、UGS013、UGS014 与当前官方表格存在差异。

阶段 1A 先建立严格的目标契约和审计台账。现有运行数据保持不变，避免在尚未保存来源快照前把未核验摘要直接迁移成“已验证证据”。

## 2. 数据层次

### 2.1 原始来源

目标模式：`data/schemas/source-record.schema.json`

来源记录负责回答：

- 资料来自哪个官方机构和规范网址；
- 文件格式是什么，资料角色是指南、通知、表格、流程还是制度；
- 发布日期是已知、未知还是不适用；
- 何时抓取，保存在哪里，文件哈希是什么；
- 当前记录是现行、历史、已替代、未知还是限时版本；
- 是否已经完成人工复核。

当 `capture.status` 为 `captured` 时，模式强制要求：

- `captured_at`；
- 64 位小写 SHA-256（安全哈希算法）；
- 位于 `data/sources/` 下的本地路径。

抓取失败时必须记录原因，不能用空文件或人工摘要冒充原始来源。

一个来源记录只对应一个能够独立保存和计算哈希的文件。表格落地页和其链接的 PDF 必须使用两个 `source_id`，并通过 `landing_page_for` 与 `attachment_of` 关系连接，不能把两个文件合并成一个无法复核的抓取记录。

### 2.2 证据单元

目标模式：`data/schemas/evidence-unit.schema.json`

证据记录将以下内容分开：

- `verbatim_text`：来源中的原文；
- `normalized_claim`：供检索、流程建模和评测使用的规范化声明；
- `source_locator`：页码、章节、段落、表格单元、表单字段或稳定锚文本；
- `applicability`：时间范围、学期标签和其他适用条件；
- `review`：复核状态、时间、人员和说明。

证据必须通过 `source_id` 引用来源记录，不再以标题和网址作为事实上的外键。

### 2.3 审计台账

当前审计文件：

- `data/audit/source-audit.csv`
- `data/audit/evidence-audit.csv`

审计台账描述早期数据距离目标契约的差距，不是新的运行数据。

当前基线：

- 8 个来源全部缺少受版本控制的快照；
- 30 条证据全部缺少可确认的逐字原文；
- 30 条证据的 `location_hint` 均只算描述性定位；
- 10 条证据缺少发布日期；
- UGS002、UGS003、UGS013、UGS014 标记为 `known_mismatch`；
- 30 条证据的迁移状态均为 `pending`。

只有完成来源保存、原文定位和人工核验后，才能把审计状态改为 `verified` 或迁移状态改为 `migrated`。

## 3. 兼容与迁移边界

本阶段不修改以下运行文件：

- `data/raw/source_manifest.json`
- `data/clean/source_texts.json`
- `data/evidence/evidence_units.jsonl`
- `app/backend/rag_engine.py`

原因是后端 `Evidence` 数据类和前端来源页面仍直接依赖旧字段。迁移将在阶段 1 的后续任务中按以下顺序进行：

1. 保存来源快照并补齐来源记录；
2. 逐条核验原文和定位；
3. 生成符合目标模式的新证据记录；
4. 对迁移数据执行模式和外键校验；
5. 增加旧、新数据行为对照测试；
6. 修改加载器使用新结构；
7. 通过回归验证后停止读取旧结构。

在第 4 步之前，不允许将旧 `content` 字段批量复制到 `verbatim_text`。

## 4. 校验方式

开发依赖：

```powershell
python -m pip install -r requirements-dev.txt
```

执行全部数据校验：

```powershell
python scripts/validate_research_data.py
```

只检查目标模式与正反样例：

```powershell
python scripts/validate_research_data.py --scope schemas
```

只检查现有数据与审计台账的覆盖和一致性：

```powershell
python scripts/validate_research_data.py --scope repository
```

执行自动测试：

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

校验脚本当前检查：

- JSON Schema（JSON 模式）本身是否合法；
- 两个正例必须通过；
- 四个模式反例必须失败，分别覆盖缺少抓取哈希、错误日期、非法证据编号和无定位证据；
- 证据、来源关系或版本关系引用不存在的 `source_id` 时，必须在外键校验中失败；
- 来源、网址、证据和审计编号不得重复；
- 审计表必须完整覆盖 8 个来源和 30 条证据；
- 证据网址必须能映射到唯一来源；
- 审计表中的 `source_id` 与旧数据网址映射一致；
- 证据数量和发布日期缺失状态与旧数据一致；
- 四条已知差异必须被明确标记；
- 状态字段只能使用约定枚举。

## 5. 状态修改规则

- `pending`：尚未开始核验。
- `in_review`：已取得来源并正在逐项核对。
- `verified`：原文、定位、版本和规范化声明均已复核。
- `rejected`：来源或声明不能作为有效证据。
- `known_mismatch`：已经有证据证明早期摘要与当前官方资料不一致。
- `migrated`：已经生成符合目标模式的记录并通过校验，不等同于来源内容天然正确。

任何状态修改都必须在当轮工作报告中记录依据。P0 证据优先于新增事项和模型实验。
