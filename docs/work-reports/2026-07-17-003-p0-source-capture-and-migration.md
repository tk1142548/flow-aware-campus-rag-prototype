# 工作报告 003：P0 来源固化与已知差异迁移

日期：2026-07-17
阶段：阶段 1B
状态：已验证

## 1. 本轮目标

1. 固化成绩证明、休学表格和复学表格三个 P0 来源组。
2. 为网页与 PDF 分别建立可哈希的来源记录和双向关系。
3. 对休学、复学 PDF 执行文本提取和整页视觉核验。
4. 修正并迁移 UGS002、UGS003、UGS013、UGS014。
5. 扩展数据校验和自动测试，使正式来源文件与迁移映射进入持续校验。
6. 不修改旧运行数据和 `rag_engine.py` 的核心查询行为。

## 2. 状态摘要

### 已完成并验证

- 已保存 3 个官方 HTML（网页文件）页面和 2 个官方 PDF（便携式文档格式）附件。
- 5 个文件均记录了抓取时间、规范网址、最终网址、媒体类型、HTTP（超文本传输协议）状态、字节数和 SHA-256（安全哈希算法）。
- 两个表格落地页与 PDF 的文件名、附件地址和来源关系一致。
- 两份 PDF 均为单页 A4，页面完整、文字可读，文本提取与整页渲染内容一致。
- 4 条旧 P0 记录保留 `known_mismatch` 审计结论，并迁移为 12 条目标证据。
- 目标证据均包含页码、章节、锚文本、逐字原文、规范化声明、适用条件和核验记录。
- 全量数据校验通过，10 项自动测试通过。

### 尚未完成

- 成绩证明页面的 UGP001 至 UGP009 尚未逐条迁移。
- 休学表格的 UGS001、UGS004 至 UGS006 尚未迁移。
- 复学表格的 UGS011、UGS012 尚未迁移。
- 其余 5 个旧来源尚未保存。
- 旧运行数据尚未切换到目标结构。

## 3. 实际完成

### 3.1 官方来源采集

新增 `data/research/source_capture_plan.json`，明确每个文件的：

- 来源编号、标题、发布机构和规范网址；
- 内容格式与资料角色；
- 页面显示日期及其含义；
- 目标保存路径和预期媒体类型；
- 落地页与附件关系；
- 版本状态与证据不足说明。

新增 `scripts/capture_official_sources.py`。脚本具备：

- 只允许写入 `data/sources/` 和 `data/research/` 的路径边界；
- 父目录穿越和目录本身作为文件目标的拒绝逻辑；
- HTTP 状态、媒体类型、HTML 或 PDF 文件签名校验；
- 拒绝覆盖已有快照和来源记录，重新抓取必须建立新版本；
- 自动计算字节数和 SHA-256；
- 自动生成正式来源 JSONL（逐行 JSON）记录。

新增 `.gitattributes`，将 `data/sources/**` 设置为逐字节保存，禁止 Windows 换行转换和文本差异规范化，避免重新检出后 HTML 字节变化导致哈希校验失败。

本次采集结果：

| 来源编号 | 文件 | 字节数 | SHA-256 |
|---|---|---:|---|
| `SRC_UG_PRINT_20210317` | `page.html` | 51,782 | `c5e470710921f927ab44cc81a8bd771bf2dbdac554cd1be9949445dece329eae` |
| `SRC_UG_SUSPEND_FORM` | `page.html` | 30,085 | `83d27dfe798f74f7773bb6971159a10135d215efcf9833cee16882c6f1b112a6` |
| `SRC_UG_SUSPEND_FORM_PDF_202504` | `form.pdf` | 146,024 | `e1dded87a5746939715e5b9e585bb839a6c2929afaf3d647d56899a2ca0798dd` |
| `SRC_UG_RESUME_FORM` | `page.html` | 30,085 | `b6eea47f1136c017a69bf21e434bb9abee363d2330ad399cdaabe77e6c73fe22` |
| `SRC_UG_RESUME_FORM_PDF_202504` | `form.pdf` | 139,646 | `76e5619de4c8dd652aca165d04771ee4cc7048c660401f5290fca2044987b707` |

成绩证明网页包含访问计数等动态字段，因此不同抓取时刻的整页哈希可能变化。本仓库只把本次快照及其哈希作为可复核事实，不用后续在线页面反推已提交快照内容。

### 3.2 来源元数据与关系核验

本地 HTML 快照确认：

- 成绩证明页面显示更新时间为 2023-01-19，不沿用网址路径中的 2021-03-17 作为当前显示日期。
- 休学表格落地页显示更新时间为 2025-04-16，链接 `XX1_休学申请表202504.pdf`。
- 复学表格落地页显示更新时间为 2025-04-16，链接 `FX1_复学申请表202504.pdf`。

两组表格分别使用 `landing_page_for` 和 `attachment_of` 建立反向关系。证据直接引用承载原文的 PDF 来源编号。

PDF 仅显示“暨南大学教务处制表（2025 年 4 月）”，没有可证明的具体发布日期或统一生效区间。来源记录继续使用 `publication.status=unknown` 和 `version.status=unknown`。

### 3.3 PDF 文本与视觉核验

使用 `pdftotext`（PDF 文本提取工具）按版面提取文字，使用 `pdftoppm`（PDF 页面渲染工具）以 150 DPI（每英寸点数）输出整页图像，并逐页查看。

核验结果：

- 休学表格：1 页，A4，PDF 1.7，146,024 字节。
- 复学表格：1 页，A4，PDF 1.7，139,646 字节。
- 两份表格无缺页、裁切、遮挡或不可读区域。
- 文本提取中的核心字段、勾选项、材料要求和签名要求均能在渲染页面中确认。

### 3.4 旧证据差异与迁移

旧记录保持不变，审计表新增 `target_evidence_ids` 保存迁移关系：

| 旧证据 | 核验结论 | 目标证据 |
|---|---|---|
| `UGS002` | “家长写明意见并签名”不符合表格；表格要求家长签字并落款日期的知情同意书。原声明还混合了基本字段、休学时长、附件和申请人签名。 | `UGS002`、`UGS020`、`UGS021`、`UGS022` |
| `UGS003` | 出国、创业、家庭、个人等选项不在该版表格中；实际为健康原因、服兵役和其他。 | `UGS003` |
| `UGS013` | 休学通知书为原件或复印件，不是两者同时提交；医院要求为县级以上医院，并区分外招生；心理健康材料有明确机构和最近半个月限制。 | `UGS013`、`UGS025`、`UGS026`、`UGS027` |
| `UGS014` | 表格没有“休学起止时间”和“申请复学时间”字段；实际包含基本信息、复学理由、附件和申请人签名。 | `UGS014`、`UGS023`、`UGS024` |

12 条目标证据全部标为 `verified`。审计表中的 4 条旧记录标为 `migrated`，其 `known_mismatch` 状态继续保留，用于说明迁移原因。

### 3.5 校验器与测试扩展

`scripts/validate_research_data.py` 新增以下检查：

- 正式来源和证据 JSONL 模式；
- 来源与证据主键唯一性和外键完整性；
- 落地页与附件关系、版本关系的反向一致性；
- 本地来源路径不得越出 `data/sources/`；
- 本地文件存在、字节数和 SHA-256 与记录一致；
- HTML 和 PDF 文件签名、媒体类型一致；
- 规范网址和最终网址主机名属于发布机构域名；
- 已验证记录必须填写核验时间和核验者；
- 证据锚文本必须存在于逐字原文；
- 已迁移旧记录必须具有已验证的目标证据映射；
- 未迁移记录不得提前声明目标证据编号。

新增 `tests/test_source_capture.py`，覆盖合法路径、父目录穿越、目录目标、媒体类型和文件签名。

`tests/test_research_data_validation.py` 新增正式数据哈希一致性和反向关系缺失测试。

## 4. 文件变更

### 新增

- `data/research/source_capture_plan.json`
- `data/research/source_records.jsonl`
- `data/research/evidence_units.jsonl`
- `data/sources/SRC_UG_PRINT_20210317/page.html`
- `data/sources/SRC_UG_SUSPEND_FORM/page.html`
- `data/sources/SRC_UG_SUSPEND_FORM_PDF_202504/form.pdf`
- `data/sources/SRC_UG_RESUME_FORM/page.html`
- `data/sources/SRC_UG_RESUME_FORM_PDF_202504/form.pdf`
- `scripts/capture_official_sources.py`
- `tests/test_source_capture.py`
- 本报告

### 修改

- `.gitignore`
- `.gitattributes`
- `data/schemas/source-record.schema.json`
- `data/audit/source-audit.csv`
- `data/audit/evidence-audit.csv`
- `scripts/validate_research_data.py`
- `tests/test_research_data_validation.py`
- 来源记录正反测试样例
- `docs/data/DATA_CONTRACT.md`
- `docs/project/PROJECT_PLAN.md`
- `docs/project/PROJECT_MEMORY.md`
- `docs/project/DECISIONS.md`

### 未修改

- `data/raw/source_manifest.json`
- `data/clean/source_texts.json`
- `data/evidence/evidence_units.jsonl`
- `app/backend/rag_engine.py`

## 5. 测试、实验与数据校验

### 5.1 正式来源采集

命令：

```powershell
python scripts/capture_official_sources.py
```

结果：退出状态 0，采集 5 个文件并生成 5 条来源记录。

### 5.2 全量数据校验

命令：

```powershell
python scripts/validate_research_data.py --scope all
```

结果：退出状态 0。

关键统计：

- 8 个旧来源、30 条旧证据和对应审计记录完整覆盖；
- 4 条已知差异保持明确标记；
- 4 条旧记录已迁移，26 条尚未迁移；
- 5 条正式来源记录、5 个本地来源文件；
- 4 条来源记录完成核验；
- 12 条目标证据全部完成核验。

### 5.3 自动测试

命令：

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

结果：退出状态 0，10 项测试全部通过。

### 5.4 Python 语法检查

命令：

```powershell
python -m py_compile scripts/validate_research_data.py scripts/capture_official_sources.py tests/test_research_data_validation.py tests/test_source_capture.py
```

结果：退出状态 0。

### 5.5 PDF 工具核验

- `pdftotext.exe`：两份 PDF 文本提取成功。
- `pdftoppm.exe`：两份 PDF 整页渲染成功。
- `pdfinfo.exe`：页数、页面尺寸、文件大小和 PDF 版本读取成功。
- 两张渲染图已人工查看；临时文本和图片不纳入版本控制。

## 6. 尚未验证或未完成

- 尚未执行独立第二次人工复核；该任务保留到阶段 1F。
- 页面“当前可访问”不证明长期有效；版本生效和替代关系仍需其他官方资料支持。
- 成绩证明页面虽已保存，但 9 条旧证据尚未逐段核验。
- 休学、复学表格仍有 6 条旧证据待迁移。
- 其余来源尚未采集，阶段 1 整体未达到验收。
- 旧运行链路仍会读取原错误摘要；在行为回归测试建立前不切换加载器。

## 7. 失败、困难与新发现

### 已处理的工具问题

工作区依赖提供的 `pdfinfo.cmd` 包装命令在当前路径下返回“系统找不到指定的路径”。已改用同机可用的 `pdfinfo.exe`，两份文件均成功读取。该问题只影响本地工具入口，不影响来源文件或核验结论。

### 新发现

- 成绩证明页面包含动态访问计数字段，HTML 整页哈希会随抓取时刻变化；仓库快照必须与其抓取时间和哈希一起解释。
- 休学表格中的“从某年春季或秋季起计”不能无条件概括成“休学起止时间”。
- 复学健康材料的医院层级和对象分支比旧摘要更细，适合用于后续条件分支评测。
- “未按要求提供证明，将不予受理”应作为独立后果证据，便于流程与回答指标分别计算。

## 8. 对推进方案和决策的影响

- 阶段 1B 已验证，阶段 1 继续进行。
- 阶段 1 的剩余执行顺序细化为表格剩余证据、成绩证明证据、其余来源和最终普查复核。
- 新增决策 D-012：旧错误摘要保留审计记录，目标证据按原子事实拆分并建立迁移映射。
- 当前结果进一步证明旧人工摘要不能直接作为实验金标准；目标数据迁移和回归测试仍是后续系统实验的前置依赖。

## 9. 需要用户决定

本轮没有新增需要用户确认的重大事项。工作未改变正式项目名称、核心研究方向、最终成果范围或成本边界。

## 10. 下一轮接续任务

执行阶段 1C：

1. 依据已保存休学 PDF 迁移 UGS001、UGS004、UGS005、UGS006。
2. 依据已保存复学 PDF 迁移 UGS011、UGS012。
3. 将时间、步骤、课程处理、材料和后果拆成独立证据。
4. 更新旧到新映射、来源审计进度和自动测试预期。
5. 执行完整数据校验。
6. 继续保持旧运行数据和核心查询代码不变。
