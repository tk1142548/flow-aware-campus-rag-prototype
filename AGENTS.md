# 项目导航

正式项目名称：**《面向校园办事场景的流程感知 RAG 问答方法研究》**。

本仓库是代码、研究规划、项目记忆、工作报告、技术决策和项目专用 Skill（技能）的权威来源。进入仓库后按以下顺序恢复状态：

1. 执行 `git status --short`、`git log -5 --oneline --decorate`。
2. 阅读 `docs/project/PROJECT_MEMORY.md`，从“最近接续点”恢复当前任务。
3. 阅读 `docs/project/PROJECT_PLAN.md` 中当前阶段、依赖和验收条件。
4. 涉及方向或范围判断时，阅读 `docs/project/DECISIONS.md`。
5. 使用 `skills/advance-campus-rag-research/SKILL.md` 完成本轮闭环。
6. 需要追溯细节时，再读取 `docs/work-reports/` 中最近一份相关报告。

## 仓库约束

- 保持正式项目名称不变；候选研究定位只能标为待验证方向。
- 以代码、数据、测试和保存的实验结果为准，不根据 README 或界面推断已实现能力。
- 不覆盖、不删除未确认的用户文件和未跟踪产物。
- 密钥、本机缓存、临时文件、可重建大型产物不得提交。
- `skills/advance-campus-rag-research/` 是 Skill 唯一权威源；用户目录中的版本只能由同步脚本生成。
- 低风险整理、测试、数据模式和文档修正可自主完成。核心研究方向、最终范围、大规模删除、显著成本和偏离立项内容的变更必须先请用户确认。
- 每轮实质工作结束前，更新项目记忆，必要时更新推进方案和决策日志，并新增一份工作报告。
- 状态必须使用“已验证、已完成待验证、进行中、计划、阻塞”之一，不得把计划写成完成。

## 关键入口

- 推进方案：`docs/project/PROJECT_PLAN.md`
- 项目记忆：`docs/project/PROJECT_MEMORY.md`
- 决策日志：`docs/project/DECISIONS.md`
- 工作报告：`docs/work-reports/`
- 数据契约：`docs/data/DATA_CONTRACT.md`
- 项目 Skill：`skills/advance-campus-rag-research/SKILL.md`
- Skill 同步：`powershell -ExecutionPolicy Bypass -File scripts/sync_project_skill.ps1`
- 数据校验：`python scripts/validate_research_data.py`
- 现有后端主链路：`app/backend/rag_engine.py`
- 现有接口：`app/backend/main.py`
- 现有证据数据：`data/evidence/evidence_units.jsonl`

当前启动脚本含本机绝对路径，在完成可复现环境改造前，必须先检查脚本和本机环境，不能假设其可跨机器运行。
