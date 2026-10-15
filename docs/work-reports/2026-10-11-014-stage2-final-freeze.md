# 阶段 2 最终内容定稿报告

日期：2026-10-11

## 结果

200 条样本全部完成，8 类正式事项各 25 条；覆盖事项映射、槽位与追问、流程步骤、材料、允许声明、证据集合、来源版本、对话轮次、越界响应与泄漏状态等字段。

冻结发布版本为 `1.0.1-frozen`。样本、复核记录、泄漏报告和评测规划均已写入该版本，最终审计保存在 `data/audit/stage2-final-freeze-audit.json`。

## 验证

执行并通过：

- `python scripts/validate_stage2_content.py`
- `python scripts/validate_research_data.py`
- `python -m unittest discover -s tests -p 'test_*.py' -q`

最终测试套件为 73 项全部通过。阶段 3 已在冻结集上运行正式稀疏基线：184 条非越界样本，Recall@5（召回率）均值 0.855978，证据精确率均值 0.298551，流程声明校验错误 0 条。语义接口重试结果单独记录。
