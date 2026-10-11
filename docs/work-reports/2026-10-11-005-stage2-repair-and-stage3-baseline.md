# 阶段 2 样本修订与阶段 3 开发集基线

## 本轮目标

修复阶段 2 的重复对话和证据绑定问题，重新执行入口审计；在不使用评测样本调参的条件下继续阶段 3 可复现基线。

## 实际完成

- `scripts/rebuild_stage2_conversations.py` 按蓝图事项、场景、难度和版本风险重建 200 条对话，写入 `data/audit/stage2-conversation-rebuild.json`。
- 200 条样本形成 200 个唯一对话，重复余量为 0。
- 23 条样本的声明—证据集合已在上一轮按流程快照修复，当前入口审计引用与版本错误为 0。
- 新增 `configs/stage3-sparse-baseline.json` 和 `scripts/run_stage3_baseline.py`，明确开发集输入、BM25 参数、随机种子和禁止正式评测开关。
- 阶段 3 声明验证和开发集基线运行器已纳入测试。

## 验证结果

- `python -m unittest discover -s tests -p 'test_*.py' -q` 退出 0，51 项测试通过。
- `python scripts/audit_stage2_content.py --output data/audit/stage3-entry-final-audit.json` 入口审计显示 200 个唯一对话、0 条重复余量、0 项引用或版本错误。
- `python scripts/validate_research_data.py` 退出 0，309 条已验证证据有效，阶段2内容冻结计数为 0。
- 开发集基线运行器完成 2 条查询，分别返回 5 条命中，结果保存至 `data/audit/stage3-baseline-development.json`。
- `git diff --check` 退出 0。

## 尚未完成

阶段2的 200 条样本仍需真实独立复核、语义近重复复核和泄漏报告复核；`validate_stage2_content.py` 因复核状态为草稿而保持失败，内容冻结不能宣称完成。

## 下一轮

完成独立复核流程和可追溯记录，随后重新执行阶段2冻结验收；阶段3继续实现流程约束模块和统一实验记录，但保持正式评测开关关闭。
