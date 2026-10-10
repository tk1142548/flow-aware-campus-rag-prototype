# 阶段 2 证据绑定修复与阶段 3 声明校验

## 本轮目标与范围

依据已验证流程记录修复评测样本的声明—证据外键，建立阶段 3 结构化声明校验。修改样本证据集合、复核状态、校验模块和项目记录，保持正式事项范围及 200 条配额。原值保存在审计文件与版本历史中。

## 状态与实际完成

阶段 3 进行中，阶段 2 内容验收阻塞。

- `scripts/repair_stage2_bindings.py` 从既有允许声明重建证据集合，校验事项归属及流程快照边界，采用逐行解析和临时文件替换。
- 修复 23 条样本的证据集合；200 条样本回到草稿，泄漏检查进入待复核。
- `data/audit/stage2-binding-repairs.json` 保留样本编号、声明编号、旧证据和新证据，以及原泄漏报告。
- `app/backend/claim_validation.py` 校验结构化声明编号、文本、引用集合和候选证据边界，已接入阶段 3 引擎。
- 当前样本状态与泄漏检查状态纳入内容验收，历史复核文件不作为修订样本的完成依据。

## 验证

- `python -m unittest discover -s tests -p 'test_*.py' -q` 退出 0，47 项测试通过。
- `python scripts/validate_process_records.py` 退出 0，13 条流程有效。
- `python scripts/validate_research_data.py` 退出 0，309 条证据有效，内容冻结计数为 0。
- `python scripts/audit_stage2_content.py --output data/audit/stage3-entry-after-binding-repair.json` 退出 1，200 条样本、64 个唯一对话、136 条重复余量，引用与版本错误 0。
- `python scripts/validate_stage2_content.py` 退出 1，样本复核、泄漏检查和重复对话阻塞内容验收。
- `git diff --check` 退出 0。

## 未完成事项与问题

136 条重复对话需要按来源支持的真实对象、条件和步骤重建。200 条样本需要重新执行完整内容复核与独立复核。结构化声明校验验证编号、文本与证据绑定，尚未覆盖自由生成文本中的隐含断言或条件适用性。

## 项目影响与接续任务

正式指标实验继续等待阶段 2 内容验收，无新增需用户决定事项。下一轮从重复对话场景重建开始，逐条核验输入槽位、响应方式、步骤和证据；阶段 3 使用测试集外输入开发流程策略。
