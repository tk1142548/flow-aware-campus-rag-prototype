# 阶段 3 统一检索与流程约束运行器

## 本轮完成

- 新增 `app/backend/hybrid_retrieval.py`，按可配置权重融合稀疏和语义分数，结果按证据编号稳定排序。
- 新增 `app/backend/answer_strategy.py`，从流程本地支持声明派生带证据编号的步骤、材料和回答边界。
- 新增 `scripts/run_stage3_unified.py`，在同一开发查询上运行稀疏、语义和混合检索，并输出流程上下文与声明校验结果。
- 使用 `text-embedding-v4` 完成开发查询，三种检索各返回5条命中；结果保存至 `data/audit/stage3-unified-development.json`。

## 验证结果

- `python -m unittest discover -s tests -p 'test_*.py' -q` 退出 0，64项测试通过。
- 统一运行器的稀疏、语义和混合结果声明校验均无错误。
- 所有正式评测开关保持关闭，运行输入为开发查询。

## 尚未完成

阶段2仍等待200条样本的真实独立内容复核；阶段3尚未执行正式指标和消融实验。

## 下一轮接续

继续完善统一实验记录字段和流程错误分类，并推进阶段2逐样本复核记录；阶段2冻结后再开放正式评测。
