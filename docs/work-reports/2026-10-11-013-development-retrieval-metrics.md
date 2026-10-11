# 阶段 3 开发集检索指标

## 本轮完成

- 新增 `data/development/stage3_queries.jsonl`，保存3条独立于阶段2冻结样本的开发查询和相关证据集合。
- 新增 `app/backend/retrieval_metrics.py`，计算 Recall@K（召回率）和证据精确率。
- 新增 `scripts/run_stage3_metrics.py`，在同一开发查询上比较稀疏、语义和混合检索。
- 结果保存至 `data/audit/stage3-dev-metrics.json`，正式评测开关关闭。

## 验证结果

- `python -m unittest discover -s tests -p 'test_*.py' -q` 退出0，73项测试通过。
- 开发集包含3条查询，三种策略均完成指标计算。
- 当前开发集均值：稀疏检索 Recall@5 为0.5，语义检索为0.3333333333，混合检索为0.5；该结果只用于开发基线，不代表正式评测结论。
- 当前结果没有支持语义或混合检索相对稀疏检索的增益，后续正式评测保留三种策略并执行配对比较。

## 下一轮接续

继续扩充开发查询覆盖版本冲突和对象边界，并完成阶段2人工复核记录。
