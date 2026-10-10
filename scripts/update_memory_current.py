from pathlib import Path
import re
p=Path('docs/project/PROJECT_MEMORY.md');s=p.read_text(encoding='utf8')
lines=s.splitlines()
lines[2]='最后更新：2026-09-24'
lines[3]='当前阶段：阶段 1 已验证，阶段 2 进行中；阶段 2A 已验证，阶段 2B 进行中，`S2SRC001` 已验证，`S2SRC002` 至 `S2SRC006` 处于进行中'
lines[4]='当前状态：退学办理已形成 10 条来源记录、113 条原子证据、5 条版本化流程和 113 条第二次独立复核记录；正式目标数据现有 34 条来源、29 个本地文件和 309 条证据，其中 25 条来源、249 条证据已验证；新增事项记录与复核清单处于进行中；200 个评测样本槽位保持未冻结；20 项自动测试通过'
lines[5]='最近接续点：完成通用流程记录验收器和 S2SRC002 至 S2SRC006 的逐条独立复核、条件分支审查及正反样例，再处理 S2SRC007 毕业实习迁移候选。'
p.write_text('\n'.join(lines)+'\n',encoding='utf8')
