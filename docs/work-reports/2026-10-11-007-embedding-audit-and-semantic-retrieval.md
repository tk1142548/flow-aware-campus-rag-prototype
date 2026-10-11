# 阶段 2 嵌入审计与阶段 3 语义检索

## 本轮目标

使用用户提供的百炼密钥完成阶段 2 语义近重复审计，并将 `text-embedding-v4` 接入阶段 3 语义检索基线。密钥只在当前子进程环境中读取，没有写入文件、报告或日志。

## 实际完成

- 新增 `scripts/run_stage2_semantic_audit.py`，使用百炼兼容接口、单批最多10条、余弦相似度和固定阈值 `0.98` 检查200条样本。
- 发现此前基于编号生成的对话存在253对高相似样本；重写查询焦点后重新运行，当前近重复对数为0。
- 新增 `app/backend/semantic_retrieval.py`，实现批量嵌入、余弦排序和稳定证据编号排序。
- 新增 `scripts/run_stage3_semantic.py`，保存模型、事项、来源过滤、候选数、命中证据和分数，不保存密钥。
- 完成一条开发查询，返回5条已验证证据，结果保存至 `data/audit/stage3-semantic-development.json`。

## 验证结果

- `python -m unittest discover -s tests -p 'test_*.py' -q` 退出 0，60项测试通过。
- `data/audit/stage2-semantic-audit.json` 记录模型 `text-embedding-v4`、样本数200、阈值0.98、近重复对数0。
- `python scripts/audit_stage2_content.py --output data/audit/stage3-entry-final-audit.json` 显示200个唯一对话、0条重复余量、0项引用或版本错误。
- 阶段2内容冻结仍为0，原因是200条样本的真实独立内容复核尚未完成；语义泄漏复核已通过。

## 下一轮接续

继续记录阶段2逐样本独立复核结果；阶段3将把稀疏检索、语义检索和流程约束统一到同一开发集运行器，并保持正式评测开关关闭。
