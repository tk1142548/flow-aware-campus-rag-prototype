# 判分口径

实现：`app/backend/scoring_v2.py`（逐样本判分）、`app/backend/hypothesis_metrics.py`（按假设的指标）、
`scripts/judge_assertions.py`（断言支持性判定）。

## 一、原则

金标准中的编号先解析为文本，再与系统回答按内容比对。系统只需把该说的内容说对，
不需要输出任何标注侧编号；编号只用于定位金标准与计算检索层指标。

## 二、预测契约

被测系统一律返回 `Prediction`：

| 字段 | 含义 |
|---|---|
| `answer_text` | 自然语言回答全文 |
| `response_mode` | `answer` / `scoped_correction` / `clarification` / `abstention` / `version_qualified` / `conversation_resolution` |
| `retrieved_evidence_ids` | 本次检索实际使用的证据编号（仅用于检索层指标） |
| `citations` | 回答中出现的证据编号 |
| `missing_slot_ids` | 判定为缺失的条件，以自然语言描述 |
| `follow_up_question` | 追问文本 |
| `item_id` | 判定的事项 |

## 三、逐样本指标

### 检索层

- `evidence_recall` = |检索集 ∩ 金标准支撑证据| / |金标准支撑证据|
- `evidence_precision` = |检索集 ∩ 金标准支撑证据| / |检索集|

### 内容层

金标准的声明、步骤、材料解析为文本元素：

| 类型 | 文本来源 |
|---|---|
| claim | `allowed_claims[].text` |
| step | `steps[].actor + steps[].action` |
| material | `materials[].name` |

回答按标点切成子句，对每个元素取最佳匹配子句：

```
covered  =  lex(子句, 元素) >= 0.50  OR  cos(子句, 元素) >= 0.72
lex      =  元素字符二元组中出现在子句里的比例
cos      =  text-embedding-v4 余弦相似度
```

字面包含覆盖"书面退学申请 ↔ 提交书面申请"这类表述，嵌入覆盖改写。

- `claim_coverage` / `step_coverage` / `material_coverage`：对应类型元素的覆盖率
- `answer_quality`：全部元素的平均覆盖率

### 交互层

- `response_mode_accuracy`：应答方式是否一致（`answer` 与 `conversation_resolution` 互认）
- `missing_slot_f1`：金标准槽位解析为槽位名（如 `SL_REQUEST_TYPE` → "办理类型"），
  与系统输出的缺失条件按内容双向匹配
- `follow_up_correct`：该追问时追问、不该追问时不追问
- `citation_validity`：回答中的证据编号属于本次检索集的占比

### 整体成功

```
overall_success = item_correct
                  AND response_mode_accuracy
                  AND missing_slot_f1 == 1
                  AND follow_up_correct
                  AND citation_validity == 1
                  AND evidence_recall == 1
                  AND 每个出现的元素类型覆盖率 == 1
```

- 金标准为 `abstention`：只看应答方式。
- 金标准为 `clarification`：看事项、应答方式、缺失条件与追问，不看内容覆盖。

整体成功是严格的"完全达标"比例，作为次要指标报告。

## 四、按假设的主指标

| 假设 | 对比 | 指标 | 样本范围 |
|---|---|---|---|
| H1 流程骨架 | 去骨架 → 完整方法 | 步骤召回；步骤顺序一致性（已覆盖步骤在回答中出现的先后与金标准顺序的一致对比例）；材料召回 | 金标准步骤 ≥ 3 |
| H2 断言核验 | 去核验 → 完整方法 | 无据断言率：判官判为 `unsupported` 的原子断言占比 | 金标准与预测均为内容类应答 |
| H3 交互控制 | 基线C → 交互控制 | 应答方式正确率；应答方式宏平均 F1；拒答精确率与召回率；过度追问率（可直接作答的样本中系统追问的比例） | 全部 |

## 五、断言判官

`scripts/judge_assertions.py` 把回答拆成原子断言，逐条依据本次检索到的证据判定
`supported` / `partial` / `unsupported`。判官为 kimi-k2.6，与生成模型不同家族。
无据断言率在与人工标注的一致率报告之前不对外引用。

## 六、统计

配对符号随机化检验（10000 次），Holm 校正，以事项为簇的自助 95% 区间
（`app/backend/stage4_statistics.py`）。

## 七、局限

1. 覆盖率衡量"说到了没有"，不惩罚多说无关内容；无据断言率与 `evidence_precision` 作为约束。
2. 匹配阈值只在开发集上调整，确认集上固定。
3. 断言判官可能受表述流畅度影响，以人工标注校准。
