# 来源、证据、流程与评测数据契约

## 1. 数据文件

| 文件 | 内容 |
|---|---|
| `data/research/source_capture_plan.json` | 官方来源采集清单 |
| `data/research/source_records.jsonl` | 逐文件来源记录 |
| `data/research/evidence_units.jsonl` | 已核验的原子证据 |
| `data/research/process_records.jsonl` | 按来源版本和条件分支保存的事项流程 |
| `data/sources/` | 按来源编号保存的原始 HTML、PDF、PNG、Word 与 Excel 旧格式快照 |
| `data/evaluation/` | 评测样本 |
| `data/schemas/` | 上述记录的 JSON 模式 |

`.gitattributes` 将 `data/sources/**` 标记为逐字节保存，禁止换行转换，
确保重新检出后文件字节与来源记录一致。

## 2. 数据层次

### 2.1 原始来源

模式：`data/schemas/source-record.schema.json`

来源记录负责回答：

- 资料来自哪个官方机构和规范网址；
- 文件格式是什么，资料角色是指南、通知、表格、流程还是制度；
- 发布日期是已知、未知还是不适用；
- 何时抓取，保存在哪里；
- 当前记录是现行、历史、已替代、未知还是限时版本；
- 是否已经完成核验。

当 `capture.status` 为 `captured` 时，模式强制要求：

- `captured_at`；
- 位于 `data/sources/` 下的本地路径。
- 最终访问地址、媒体类型和非零字节数；
- HTTP（超文本传输协议）状态及可用时的 `Last-Modified`（最后修改时间）响应头。

抓取失败时必须记录原因，不能用空文件或人工摘要冒充原始来源。

一个来源记录只对应一个能够独立保存的文件。表格落地页和其链接的 PDF 必须使用两个 `source_id`，并通过 `landing_page_for` 与 `attachment_of` 关系连接，不能把两个文件合并成一个无法追溯的抓取记录。

### 2.2 证据单元

模式：`data/schemas/evidence-unit.schema.json`

证据记录将以下内容分开：

- `verbatim_text`：来源中的原文；
- `normalized_claim`：供检索、流程建模和评测使用的规范化声明；
- `source_locator`：页码、章节、段落、表格单元、表单字段或稳定锚文本；
- `applicability`：时间范围、学期标签和其他适用条件；
- `review`：复核状态、时间、人员和说明。

证据必须通过 `source_id` 引用来源记录，不再以标题和网址作为事实上的外键。

### 2.3 流程记录

模式：`data/schemas/process-record.schema.json`

流程记录负责将以下结构绑定到同一事项和来源版本组：

- 适用对象；
- 决定回答和追问的条件槽位；
- 缺失槽位对应的追问规则；
- 有序步骤及其主体、动作和后继关系；
- 材料、地点、入口、时限、例外和后果；
- 可以进入回答的原子声明；
- 支持每个字段的目标证据；
- 证据数据文件路径和实际引用编号。

跨字段校验要求步骤从首步可达、顺序连续、至少存在一个终止步骤，所有内部编号均存在，必填追问槽位均有追问规则，证据快照与实际引用完全一致，且证据属于同一事项。

### 2.4 评测样本

模式：`data/schemas/evaluation-sample.schema.json`

评测样本分别保存：

- 分配事项与实际目标事项；
- 场景、难度、版本风险和单轮/多轮结构；
- 对话文本和已知、未知、歧义槽位；
- 预期响应方式；
- 金标准事项、追问、步骤、材料、允许声明和支持证据；
- 禁止声明和回答边界；
- 模板族、来源版本组、语义簇和近重复检查状态。

开发集与确认集共用这一模式。

## 3. 校验

```powershell
python scripts/validate_research_data.py
python scripts/validate_process_records.py
python -m unittest discover -s tests -p "test_*.py"
```

`validate_research_data.py` 检查：

- 各模式本身合法，正例通过、反例失败；
- 来源与证据编号不重复，证据及来源关系、版本关系引用的 `source_id` 均存在；
- 落地页与附件关系、版本替代关系具有约定的反向关系；
- 本地来源文件位于 `data/sources/` 且存在，字节数、媒体类型与文件签名与来源记录一致；
- 规范网址和最终地址的主机名与发布机构域名一致；
- 已验证记录填写了核验时间与核验者；
- 每条证据的锚文本出现在其逐字原文中，并能在保存来源的提取文本中找到。

`validate_process_records.py` 检查流程记录的模式、步骤可达性、内部引用与证据绑定。

## 4. 采集官方来源

```powershell
python scripts/capture_official_sources.py
python scripts/capture_official_sources.py --append
```

追加模式逐字节保留已有来源记录和快照，只处理新的 `source_id`。
再次抓取已有内容应建立新的来源版本、路径和记录，不能静默替换已有记录。

## 5. 核验状态

- `pending`：尚未开始核验。
- `in_review`：已取得来源并正在逐项核对。
- `verified`：原文、定位、版本和规范化声明均已复核。
- `rejected`：来源或声明不能作为有效证据。
