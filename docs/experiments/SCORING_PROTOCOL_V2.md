# 判分口径 v2

状态：已验证（`app/backend/scoring_v2.py`，`tests/test_scoring_v2.py` 9 项通过）
制定日期：2026-10-14

## 一、为什么必须换判分口径

旧判分（`scripts/run_stage4_experiments.py` 的 `score()`）要求系统输出中的声明携带标注的
`claim_id`：

```python
if cited and local and c.get('claim_id') == local['claim_id']:
    applicable += 1
    mapped.append(local['claim_id'])
```

生成式系统不可能产出标注编号，因此**任何**生成式基线在该口径下都会被判 0 分——
旧结果里"直接抽取 0.080"正是这么来的（0.080 = 16/200，恰好等于 16 条越界样本自动满分）。
这不是能力差异，是口径造成的假象。

## 二、v2 的核心原则

**把金标准解析成文本，再按内容比对；编号只用于定位，不用于判分。**

推理侧不产生编号，评分侧也不要求编号。任何"把该说的话说对了"的系统都能得分，
无论它如何组织输出、是否给出引用编号。

## 三、评分对象：统一预测契约

被测系统一律返回 `Prediction`：

| 字段 | 含义 |
|---|---|
| `answer_text` | 自然语言回答全文（不要求任何内部编号） |
| `response_mode` | `answer` / `scoped_correction` / `clarification` / `abstention` / `version_qualified` / `conversation_resolution` |
| `retrieved_evidence_ids` | 本次检索实际使用的证据编号（**仅用于检索层指标**） |
| `citations` | 回答中明确声明的引用编号 |
| `missing_slot_ids` | 判定为缺失的槽位，**以自然语言描述**；判分侧把金标准槽位 ID 解析为槽位名后按内容匹配 |
| `follow_up_question` | 追问文本 |
| `item_id` | 判定的事项 |

## 四、四层指标

### 检索层（按证据编号计算，推理侧确实会产生编号）

- `evidence_recall` = |预测检索集 ∩ 金标准支撑证据| / |金标准支撑证据|
- `evidence_precision` = |预测检索集 ∩ 金标准支撑证据| / |预测检索集|

### 流程层（按内容匹配，不看编号）

金标准的 `allowed_claim_ids` / `ordered_step_ids` / `material_ids` 先由流程标注解析为**文本元素**：

| 类型 | 文本来源 |
|---|---|
| claim | `allowed_claims[].text` |
| step | `steps[].actor + steps[].action` |
| material | `materials[].name` |

再把回答按标点切成子句，对每个元素取"最佳匹配子句"：

```
covered  =  lex(子句, 元素) >= 0.50  OR  cos(子句, 元素) >= 0.72
lex      =  元素字符二元组中出现在子句里的比例（定向包含，不是 Jaccard）
cos      =  text-embedding-v4 余弦相似度
```

- `claim_coverage` / `step_coverage` / `material_coverage` = 对应类型元素的覆盖率
- `answer_quality` = 全部元素的平均覆盖率（连续值，用于看趋势）

**为什么用"或"而不是加权**：中文短文本上，字面包含能抓住"书面退学申请 ↔ 提交书面申请"这类
表述，嵌入能抓住改写；两者互补。阈值按 `0.50 / 0.72` 为中档设置，结果同时报告
宽松档（`0.40 / 0.65`）与严格档（`0.60 / 0.80`）做灵敏度分析。

### 核验层

- `citation_validity` = 引用中确实属于本次检索集的占比
- `unsupported_ratio` = LLM 判官（`judge_support`）判定为"无证据支持"的实质陈述占比。
  **判官只用于校准切片，不作为主指标**——TREC 2024 RAG Track 测得 GPT-4o 与人工的
  支持性判定一致率仅 56%，人工后编辑后 72%，单独使用不可靠。
  运行方式：`python scripts/run_judge_calibration.py`，产出
  `data/experiments/judge-calibration.json` 与同名 `.csv`。CSV 留有"人工判定"两列，
  逐条核对后即可算出判官与人工的一致率；**一致率出来之前，`unsupported_ratio` 不得对外引用。**

### 交互层

- `response_mode_accuracy` = 响应方式是否兼容（`answer` 与 `conversation_resolution` 互认）
- `missing_slot_f1` = 缺失槽位的 F1，**按内容匹配**：金标准的槽位 ID 先由流程标注解析为槽位名
  （如 `SL_REQUEST_TYPE` → "办理类型"），再与系统输出的自然语言缺失条件双向匹配
  （召回：每个金标准槽位名是否被某条预测条件覆盖；精确：每条预测条件是否对应某个金标准槽位名）。
  若直接拿 ID 与自由文本做集合交，交集恒为空，任何生成式系统都无法得分。
- `follow_up_correct` = 是否该追问时追问、不该追问时不追问

## 五、整体成功

```
overall_success = item_correct
                  AND response_mode_accuracy
                  AND missing_slot_f1 == 1
                  AND follow_up_correct
                  AND citation_validity == 1
                  AND evidence_recall == 1
                  AND 每个出现的元素类型覆盖率 == 1
```

特例：金标准为 `abstention` 的样本**只看响应方式**——不输出内容才算对。
这样"拒答"不会被"多说几句碰巧命中"蒙对。

`overall_success` 是**7 项精确等于 1 的合取**，属最严口径，只能用来看"完全达标"的比例；
定位问题必须同时读各分项。2026-10-15 复核发现，它在两处表示不一致时会把 86 条样本压成
结构性 0 分，详见 `REPRESENTATION_AUDIT.md`。

## 六、与旧口径的关系

- 旧口径的结论（0.900 / 0.080）**已作废**，不得与新口径的数字并列比较。
- 新旧口径不可换算，因为旧口径下生成式系统恒为 0。
- 新的基线 A/B/C 与本方法全部在 v2 口径下评测，四行数字互为对照。

## 七、已知局限

1. 覆盖率是"说到了没有"，不惩罚"多说无关内容"。因此另设 `citation_validity` 与
   LLM 判官的无据断言率作为约束，并在报告中同时给出 `evidence_precision`。
2. 语义阈值是超参。当前在**开发集**上按中档取值，独立验证集上**不再调整**。
3. LLM 判官存在位置偏好与流畅度偏好，必须配人工校准切片。
