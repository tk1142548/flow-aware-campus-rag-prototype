# 2026-09-23-001-stage2b-credentials

## 本轮目标

完成 S2SRC002 学历学位证书补办的数据闭环，分别固化学位证明书与毕业证明书页面、原子证据、流程记录和第二次独立复核。

## 状态摘要

阶段 2B 进行中；S2SRC002 已完成数据闭环待通用阶段验收。

## 实际完成

- 保存 2 个官方服务页面，建立独立来源记录和来源快照。
- 新增 21 条 UGC001 至 UGC021 原子证据，覆盖对象、前置条件、步骤、材料、地点和时限。
- 新增 PROC_UG_CREDENTIAL_DEGREE_V001 与 PROC_UG_CREDENTIAL_DIPLOMA_V001，流程不跨类型合并。
- 新增 21 条第二次独立复核记录，覆盖全部证据。
- 新增 scripts/validate_stage2b_credentials.py，验证来源、证据编号、流程快照哈希和复核覆盖。

## 验证结果

- python scripts/validate_research_data.py 返回 0，正式目标数据为 27 条来源、270 条证据、23 个已保存文件。
- python scripts/validate_stage2b_credentials.py 返回 0。
- python -m unittest discover -s tests -p "test_*.py" -v 返回 0，20 项测试通过。

## 尚未完成

S2SRC002 的正反标注样例和通用验证器接入仍待后续阶段统一处理。

## 下一轮接续任务

执行 S2SRC003 学生证补办来源固化与流程分离，并沿用本轮独立来源、证据和复核结构。
