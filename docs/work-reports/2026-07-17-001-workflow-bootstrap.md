# 工作报告 001：跨对话工作流初始化

日期：2026-07-17
总体状态：已验证
对应阶段：阶段 0，项目治理与基线登记

## 1. 本轮目标

在不大规模修改核心代码的前提下，建立能够跨对话持续工作的项目管理与科研闭环：

- 创建仓库级导航；
- 创建推进方案、项目记忆和决策日志；
- 创建项目专用 Skill（技能）；
- 明确第一实施阶段和验收标准；
- 配置 Git（版本控制系统）忽略边界；
- 建立逐轮工作报告机制；
- 提供 Skill 安装镜像的同步方式。

## 2. 状态摘要

| 内容 | 状态 |
|---|---|
| 仓库与未跟踪文件检查 | 已验证 |
| 项目文档体系 | 已验证 |
| 项目专用 Skill | 已验证 |
| Skill 同步脚本 | 已验证 |
| `.gitignore` 边界 | 已验证 |
| 核心代码与现有证据修改 | 未执行，符合本轮范围 |
| Git 提交与推送 | 已验证；本轮基础文件已同步到私有远程仓库 |

## 3. 实际完成内容

### 3.1 仓库导航

新增根目录 `AGENTS.md`，只保留：

- 新对话启动顺序；
- 权威文件入口；
- 自主处理和必须请示的边界；
- 每轮文档闭环要求；
- 当前启动脚本不可直接视为跨机器可复现的提醒。

### 3.2 长期文档

新增：

- `docs/project/PROJECT_PLAN.md`
- `docs/project/PROJECT_MEMORY.md`
- `docs/project/DECISIONS.md`

推进方案已整理此前技术审查结论，并将阶段 1 明确为“来源与证据基线建设”。项目记忆记录当前真实实现、已知问题、重要文件和唯一最近接续点。决策日志区分已确认、暂定和待用户确认内容。

### 3.3 项目专用 Skill

新增 `skills/advance-campus-rag-research/`，仓库内版本为唯一权威源。

Skill 规定：

- 新对话恢复顺序；
- 本轮任务、依赖和验收条件的确定方法；
- 数据、代码、实验和文档工作规范；
- 测试与验证要求；
- 失败和技术决策记录方式；
- 推进方案、项目记忆和工作报告更新规则；
- 自主决定与必须请示的边界；
- 原计划与实际结果冲突时的处理流程。

新增 `scripts/sync_project_skill.ps1`，用于把仓库权威版本复制到 Codex 用户 Skill 目录，并提供哈希一致性检查。

### 3.4 忽略边界

扩展 `.gitignore`，排除：

- 密钥和本机环境；
- Python 与 Node.js 本地缓存；
- Codex 本机状态和本机工具；
- `output/`、`tmp_ppt_extract/` 等可重建产物；
- 数据下载缓存和逐次实验运行产物。

没有忽略申报书、答辩材料等项目文件，因为其长期保存方式和隐私边界尚待用户确认。

## 4. 文件变更

| 文件 | 变更 | 用途 |
|---|---|---|
| `.gitignore` | 修改 | 定义密钥、缓存、临时和大型可重建产物边界 |
| `AGENTS.md` | 新增 | 仓库级导航入口 |
| `docs/project/PROJECT_PLAN.md` | 新增 | 长期推进方案、阶段依赖和验收 |
| `docs/project/PROJECT_MEMORY.md` | 新增 | 跨对话精炼上下文与接续点 |
| `docs/project/DECISIONS.md` | 新增 | 技术和项目决策历史 |
| `docs/work-reports/2026-07-17-001-workflow-bootstrap.md` | 新增 | 本轮永久工作记录 |
| `skills/advance-campus-rag-research/SKILL.md` | 新增 | 项目科研与工程闭环 |
| `skills/advance-campus-rag-research/agents/openai.yaml` | 新增 | Skill 界面元数据 |
| `scripts/sync_project_skill.ps1` | 新增 | 同步和检查 Skill 安装镜像 |

## 5. 已使用的仓库证据

- 核心实现的技术审查基线提交：`869e2a6 Build flow-aware campus RAG prototype`。
- 受版本控制文件：27 个。
- 现有数据：30 条证据、8 个来源、2 个事项、10 条缺失发布日期。
- 现有主链路：`app/backend/rag_engine.py`。
- 现有接口：`app/backend/main.py`。
- 当前未跟踪文件包括用户原有文书、答辩材料、导师准备文档以及临时产物。

## 6. 测试、校验与结果

### 6.1 Skill 结构

执行：

```powershell
python C:\Users\Lenovo\.codex\skills\.system\skill-creator\scripts\quick_validate.py skills\advance-campus-rag-research
```

结果：退出状态 0，输出 `Skill is valid!`。

### 6.2 Skill 同步与一致性

首次执行同步时失败，原因是当前 Windows PowerShell 的 .NET 不提供 `System.IO.Path.GetRelativePath`。修正相对路径计算后执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\sync_project_skill.ps1
powershell -ExecutionPolicy Bypass -File scripts\sync_project_skill.ps1 -Check
```

结果：退出状态 0。仓库源成功同步至：

`C:\Users\Lenovo\.codex\skills\advance-campus-rag-research`

源文件与安装镜像的 SHA-256 哈希一致。

### 6.3 文件与必需章节

使用 PowerShell 检查 8 个必需文件是否存在，并检查 Skill 是否包含状态恢复、任务确定、实施、验证、记录、请示边界、冲突处理和结束闭环章节。

结果：退出状态 0，输出 `Required files and workflow sections: OK`。

### 6.4 脚本语法与差异

执行 PowerShell 语法解析和：

```powershell
git diff --check
```

结果：

- 同步脚本语法无错误；
- `git diff --check` 退出状态 0；
- 仅出现 Git 对 `.gitignore` 的 LF 到 CRLF 行尾提示，不影响内容正确性；
- 项目文档和 Skill 中无未清理的模板 `TODO`。

### 6.5 忽略边界

使用 `git check-ignore -v` 检查：

- `.env.local`
- `output/`
- `tmp_ppt_extract/`
- `.agents/`
- `.codex/`
- `tools/`

结果：全部命中新增或保留的忽略规则。`AGENTS.md`、`docs/`、`skills/` 和同步脚本均正常显示为待版本控制文件。

### 6.6 Git 状态与核心代码边界

Git 状态显示：

- 修改：`.gitignore`
- 新增：`AGENTS.md`、`docs/`、`skills/`、`scripts/sync_project_skill.ps1`
- 用户原有申报书、导师准备文档和答辩材料仍为未跟踪文件

本轮没有修改 `app/`、`data/`、`README.md`、`requirements.txt` 或现有启动脚本。

### 6.7 提交与远程同步

本轮工作流基础文件形成提交：

`dd7cb60 chore: bootstrap long-term research workflow`

执行 `git push origin main` 成功。推送完成时：

- 本地提交：`dd7cb6047eef8bc691d21386e0c0c4a255d48d1f`
- 远程 `origin/main`：`dd7cb6047eef8bc691d21386e0c0c4a255d48d1f`

两者一致。用户原有申报书、导师准备文档和答辩材料未包含在提交中。

## 7. 尚未验证或未完成

- 尚未创建来源与证据 JSON Schema（JSON 模式）。
- 尚未建立 8 个来源和 30 条证据的审计台账。
- 尚未修正四条已知事实差异。
- 尚未修改核心查询代码。
- 现有申报书、答辩材料和导师准备文档是否进入私有仓库尚未确定。

## 8. 新发现与困难

- 工作区已有 `.agents/`、`.codex/`、`output/` 和 `tmp_ppt_extract/` 本地目录，适合明确排除，避免污染状态。
- 申报书和准备材料可能包含个人信息。虽然仓库为私有仓库，仍应在纳入版本控制前确认隐私边界。
- 当前启动脚本仍包含本机绝对路径；本轮只记录风险，不在工作流初始化阶段顺带修改。
- Skill 首次同步失败：当前 Windows PowerShell 的 .NET（运行时）不支持 `System.IO.Path.GetRelativePath`。已改为在验证源文件属于仓库 Skill 目录后，以目录前缀计算相对路径；重新同步和哈希检查均已通过。

## 9. 对推进方案的影响

- 阶段 0 增加了 Skill 权威源和同步校验要求。
- 阶段 1 的第一任务明确为数据契约和审计台账，不直接修改检索或生成逻辑。
- 最终事项数量和研究贡献延后至数据普查及初步实验后确认。

## 10. 需要用户决定

1. 申报书、答辩材料和导师准备文档采用原文件入库、脱敏版本入库，还是仅保存哈希与清单。
2. 后续是否采用“每轮通过验证后自动提交并推送”的 Git 工作节奏。

## 11. 下一轮接续任务

执行阶段 1A“数据契约与审计台账”：

1. 从现有 `source_manifest.json` 和 `evidence_units.jsonl` 提取当前字段。
2. 定义来源记录、证据单元和审计记录的必需字段。
3. 创建有效与无效最小样例。
4. 实现自动校验脚本和测试。
5. 不修改 `rag_engine.py` 的核心查询行为。
