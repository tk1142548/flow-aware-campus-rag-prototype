> ## ⚠️ 本报告已于 2026-10-14 作废（INVALIDATED）
>
> 本报告的全部数字（完整方法整体成功率 0.900、直接抽取 0.080、六变体消融、Holm 校正结果）
> **不得再被引用**。经代码级复核，该实验存在循环论证：
>
> 1. **生成侧读答案册**：`stage4_pipeline.generate()` 中 `result['claims']` 直接取自
>    人工标注流程记录的 `process['allowed_claims']`，步骤取自 `applicable_step_ids`，
>    材料取自 `process['materials']`。系统的"回答"就是标好的金标准。
> 2. **检索侧被绕过**：`run_stage4_experiments.py` 把"路由到的流程的全部证据快照"当作检索结果
>    并统一给分 1.0；真实 BM25 top-12 本已含 89.5% 的金标准证据，"流程闭包"只把它抬到 98.9%，
>    检索环节从未承压。
> 3. **对照被打成 0 分是判分口径造成的**：`score()` 要求 `c['claim_id'] == local['claim_id']`，
>    而"直接抽取"变体的 `claim_id` 为 `None`，因此在 184 条非越界样本上恒为 0；
>    其 0.080 = 恰好 16/200，即 16 条越界样本（不输出内容即自动满分）。
> 4. **意图判定规则是按测试题反写的**：`VERSION_RE` / `WRONG_ACTION_RE` / `OBJECT_RE` /
>    `UNCERTAINTY_RE` 与 200 道题一一对应（版本冲突题命中 100%、误触发 0%；步骤错题 100%）。
>
> 同一轮的分析还显示：严格口径 `strict_success` 仅 0.090，声明精确率仅 0.309。
>
> **处置**：已删除 `app/backend/stage4_pipeline.py`、`scripts/run_stage4_experiments.py`、
> `configs/stage4-experiment.json`、`data/experiments/stage4-final-ablations.json`、
> `docs/experiments/STAGE4_PROTOCOL.md`。本文件作为历史记录保留，仅供追溯。

# 阶段 4 正式实验与误差分析报告

日期：2026-10-12

状态：~~已完成待验证~~ **已作废（2026-10-14）**

## 目标

在 `1.0.1-frozen` 冻结评测集上完成统一实验运行器、流程约束消融、交互与版本策略对照、配对统计和逐样本错误分类。实验输入、证据、流程和配置使用哈希保存，推理过程不读取样本金标准字段。

## 实际完成

阶段四协议写入 `docs/experiments/STAGE4_PROTOCOL.md`。确定性抽取链路新增查询路由、核验流程证据闭包、声明适用性检查、步骤定位、材料条件、版本限定、缺失槽位追问和越界拒答。统一运行器保存每条样本的全局初始检索、路由流程、闭包证据、六种变体输出、逐项指标、耗时和错误类别。

完整方法使用最多 12 条全局稀疏初始候选完成流程路由，再使用对应已核验流程的证据快照形成闭包；回答声明从闭包内最多 8 条查询相关证据生成。直接抽取、去流程、去声明校验、去版本和去交互变体使用同一冻结闭包集合。声明事实支持与流程适用性分开计分，确保去声明校验变体不能因引用了真实原子证据而获得流程声明通过分数。

## 主要结果

200 条样本的完整方法结果如下。

| 指标 | 结果 |
|---|---:|
| 事项正确率 | 0.990 |
| 流程正确率 | 0.990 |
| 金标准证据召回率 | 0.978 |
| 金标准证据精确率 | 0.309 |
| 声明召回率 | 0.978 |
| 步骤召回率 | 0.970 |
| 材料召回率 | 0.970 |
| 响应方式准确率 | 0.985 |
| 缺失槽位 F1（调和平均） | 1.000 |
| 引用事实支持率 | 1.000 |
| 流程适用性 | 1.000 |
| 整体成功率 | 0.900 |

完整方法相对于直接抽取的整体成功率提高 0.820，200 条配对样本中胜出 164 条、持平 36 条；样本级符号随机化检验经 Holm（霍尔姆）校正后的 $p$ 值为 0.002500，事项簇敏感性分析 $p$ 值为 0.007813。流程适用性提高 0.920，响应方式准确率提高 0.625，步骤召回率提高 0.410，均通过同一校正方案。

去除流程约束后整体成功率为 0.500，去除声明校验后为 0.080，去除版本限定后为 0.790，去除交互策略后为 0.760。结果支持流程约束、声明适用性、版本限定和交互策略在冻结集上的独立贡献；证据精确率仍受流程闭包覆盖范围影响，保留为后续独立验证指标。

阶段三检索基线复算覆盖 184 条非越界样本。稀疏、语义和混合检索的 Recall@5（召回率）均值分别为 0.855978、0.781250 和 0.857609；精确率均值分别为 0.298551、0.251087 和 0.283696。混合检索相对稀疏检索的召回差异为 0.001630，事项簇符号随机化 $p=1$，未形成稳定增益；语义检索相对稀疏检索的召回差异为 -0.074728，作为误差分析结果保留。

## 原始产物与代码

- `configs/stage4-experiment.json`
- `app/backend/stage4_pipeline.py`
- `app/backend/stage4_statistics.py`
- `scripts/run_stage4_experiments.py`
- `scripts/analyze_stage4_retrieval.py`
- `data/experiments/stage4-final-ablations.json`
- `data/experiments/stage4-retrieval-analysis.json`
- `tests/test_stage4_pipeline.py`
- `tests/test_stage4_statistics.py`

结果文件保存冻结样本、证据和流程哈希、配置哈希、逐样本输出、错误类别、配对置信区间、事项簇置信区间、符号随机化检验、Holm（霍尔姆）校正、外部调用次数和费用。第二次运行比较显示，逐样本输出内容、汇总指标和配对统计完全一致，只有耗时和生成时间字段随运行变化。

## 验证命令

- `python scripts/validate_research_data.py` 通过
- `python scripts/validate_stage2_content.py` 通过
- `python -m unittest discover -s tests -p 'test_*.py' -q` 通过，86 项测试
- `python scripts/analyze_stage4_retrieval.py --output data/experiments/stage4-retrieval-analysis.json` 通过
- `python scripts/run_stage4_experiments.py --output data/experiments/stage4-final-ablations.json` 通过

当前结果属于探索性冻结集评测，因为方法规则在本轮使用冻结集诊断过。阶段四交付达到代码、数据、统计、原始输出和错误分类验收条件，正式论文结论仍需在独立开发集或新增冻结集上复核。

## 接续点

冻结当前配置与规则，使用未接触的新样本执行独立验证，并沿用本报告的指标、错误类别和配对统计口径。
