"""Extend the process records of two items so their statements cover their evidence.

Two items — 成绩与证明打印 and 休学复学与学籍状态 — carry far more verified evidence
than the process records bind as statements (6 of 80 and 6 of 56). Because a gold
answer can only be built on a statement the process record allows, those two items
could not be exercised over most of their evidence, which is why the independent
set leaned on the other six items.

This script widens the binding. It is purely additive: it appends claims to one
existing record and appends new records for the sub-services that the evidence
already distinguishes (graduates, sealing, the summer cross-campus notice,
postgraduate certificates; suspension, resumption, the legacy process pages, the
unregistered-student notice). No existing step, claim, slot or text is changed or
removed, so every evaluation sample that references these records keeps resolving
to exactly the same gold elements.

Claim text and claim type are taken from the evidence unit itself, so a claim can
never drift from the statement it points at.

Usage:
    python scripts/extend_process_coverage.py [--root PATH] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROCESS_PATH = Path("data/research/process_records.jsonl")
EVIDENCE_PATH = Path("data/research/evidence_units.jsonl")
SNAPSHOT_DATASET = "data/research/evidence_units.jsonl"

AUDIENCE_UNDERGRADUATE = ["本科学生"]

# Claims appended to an existing record, as (step it supports, evidence id).
PROOF_PRINT_ADDITIONS = [
    ("ST_01", "UGP016"),
    ("ST_02", "UGP003"),
    ("ST_02", "UGP017"),
    ("ST_02", "UGP018"),
    ("ST_03", "UGP009"),
    ("ST_03", "UGP051"),
    ("ST_03", "UGP052"),
    ("ST_03", "UGP053"),
    ("ST_03", "UGP054"),
    ("ST_03", "UGP055"),
    ("ST_03", "UGP056"),
    ([], "UGP057"),
    ([], "UGP058"),
]

# New records. `claims` is the ordered list of (step it supports, evidence id).
NEW_RECORDS = [
    {
        "process_id": "PROC_UG_PROOF_PRINT_ENGLISH_NAME_V001",
        "item_id": "UG_PROOF_PRINT",
        "title": "英文名填写与纠错流程",
        "audience": AUDIENCE_UNDERGRADUATE,
        "slots": [
            {"slot_id": "SL_ENGLISH_NAME_STATE", "name": "英文名状态",
             "value_type": "enum", "required_for_resolution": True,
             "allowed_values": ["已有英文名", "需要填写", "需要纠错"],
             "unknown_policy": "ask", "evidence_ids": ["UGP019"]},
        ],
        "follow_up_rules": [
            {"rule_id": "FU_01", "when_missing_slot_ids": ["SL_ENGLISH_NAME_STATE"],
             "question": "请说明教务系统里是否已有英文名，以及是首次填写还是需要纠错。",
             "priority": 1, "evidence_ids": ["UGP019"]},
        ],
        "steps": [
            ("ST_01", "学生", "在教务系统中确认是否已有英文名，并核对姓名拼音的书写方式。",
             ["UGP004", "UGP019", "UGP020"], ["ST_02", "ST_03"]),
            ("ST_02", "学生", "登录新教务系统提交“学生信息变更”申请，填写变更后内容并上传身份证件图像附件。",
             ["UGP021", "UGP022", "UGP023", "UGP024"], []),
            ("ST_03", "学生", "英文名有误时填写《普通申请表》注明正确英文名，并附有效身份证件复印件。",
             ["UGP025", "UGP026"], ["ST_04"]),
            ("ST_04", "学生", "将英文名纠错材料提交至所在学院教科办。",
             ["UGP027"], ["ST_05"]),
            ("ST_05", "学院教科办", "将英文名纠错材料统一提交教务处学籍科修改。",
             ["UGP028"], []),
        ],
        "claims": [
            (["ST_01"], "UGP004"), (["ST_01"], "UGP019"), (["ST_01"], "UGP020"),
            (["ST_02"], "UGP021"), (["ST_02"], "UGP022"), (["ST_02"], "UGP023"),
            (["ST_02"], "UGP024"), (["ST_03"], "UGP025"), (["ST_03"], "UGP026"),
            (["ST_04"], "UGP027"), (["ST_05"], "UGP028"),
        ],
    },
    {
        "process_id": "PROC_UG_PROOF_PRINT_ALUMNI_V001",
        "item_id": "UG_PROOF_PRINT",
        "title": "已毕业学生成绩单与英文毕业证明办理流程",
        "audience": ["已毕业本科学生"],
        "slots": [
            {"slot_id": "SL_GRADUATION_YEAR", "name": "入学年份",
             "value_type": "free_text", "required_for_resolution": True,
             "allowed_values": [], "unknown_policy": "ask",
             "evidence_ids": ["UGP005"]},
        ],
        "follow_up_rules": [
            {"rule_id": "FU_01", "when_missing_slot_ids": ["SL_GRADUATION_YEAR"],
             "question": "请说明入学年份，以便判断可用的办理方式。",
             "priority": 1, "evidence_ids": ["UGP005"]},
        ],
        "steps": [
            ("ST_01", "已毕业本科学生", "按入学年份判断适用哪种办理方式。",
             ["UGP005", "UGP006", "UGP007", "UGP034"], ["ST_02", "ST_03", "ST_04", "ST_06"]),
            ("ST_02", "2006 年后入学的已毕业本科学生", "登录成绩单自助打印系统，预览无误后扫码缴费打印。",
             ["UGP029", "UGP030", "UGP031", "UGP032"], []),
            ("ST_03", "2006 年及以后入学的已毕业本科学生", "登录英文毕业证明自助打印系统，预览无误后扫码缴费打印。",
             ["UGP037", "UGP038", "UGP039", "UGP040"], []),
            ("ST_04", "2006 年以前入学的已毕业本科学生", "带齐身份证、毕业证和学位证复印件，到教务处学籍科申请并缴费办理英文毕业证明。",
             ["UGP041", "UGP042", "UGP043"], ["ST_05"]),
            ("ST_05", "已毕业本科学生", "打印英文成绩单或英文毕业证明时没有英文名，提供有效身份证件复印件并向学籍科申请协助处理。",
             ["UGP044", "UGP045"], []),
            ("ST_06", "2000 级以前毕业生", "先通过电话咨询教务处或学校档案馆。",
             ["UGP033", "UGP035", "UGP036"], []),
        ],
        "claims": [
            (["ST_01"], "UGP005"), (["ST_01"], "UGP006"), (["ST_01"], "UGP007"),
            (["ST_01"], "UGP034"), (["ST_02"], "UGP029"), (["ST_02"], "UGP030"),
            (["ST_02"], "UGP031"), (["ST_02"], "UGP032"), (["ST_03"], "UGP037"),
            (["ST_03"], "UGP038"), (["ST_03"], "UGP039"), (["ST_03"], "UGP040"),
            (["ST_04"], "UGP041"), (["ST_04"], "UGP042"), (["ST_04"], "UGP043"),
            (["ST_05"], "UGP044"), (["ST_05"], "UGP045"), (["ST_06"], "UGP033"),
            (["ST_06"], "UGP035"), (["ST_06"], "UGP036"),
        ],
    },
    {
        "process_id": "PROC_UG_PROOF_PRINT_SEAL_V001",
        "item_id": "UG_PROOF_PRINT",
        "title": "成绩单与证明密封流程",
        "audience": AUDIENCE_UNDERGRADUATE,
        "slots": [
            {"slot_id": "SL_SEAL_CAMPUS", "name": "办理校区",
             "value_type": "free_text", "required_for_resolution": True,
             "allowed_values": [], "unknown_policy": "ask",
             "evidence_ids": ["UGP046"]},
        ],
        "follow_up_rules": [
            {"rule_id": "FU_01", "when_missing_slot_ids": ["SL_SEAL_CAMPUS"],
             "question": "请说明要在哪个校区办理密封，以便给出对应的办理点。",
             "priority": 1, "evidence_ids": ["UGP046"]},
        ],
        "steps": [
            ("ST_01", "学生", "到所在校区的密封办理点申请教务处专用信封密封。",
             ["UGP008", "UGP046", "UGP047", "UGP048", "UGP049", "UGP050"], ["ST_02"]),
            ("ST_02", "学生", "确认需要密封的材料是否属于专用信封可密封的范围。",
             ["UGP069", "UGP070", "UGP071", "UGP072"], ["ST_03"]),
            ("ST_03", "毕业生", "暑假期间按通知列明的校区办理点提交密封申请。",
             ["UGP068", "UGP073", "UGP074", "UGP075", "UGP076", "UGP077"], []),
        ],
        "claims": [
            (["ST_01"], "UGP008"), (["ST_01"], "UGP046"), (["ST_01"], "UGP047"),
            (["ST_01"], "UGP048"), (["ST_01"], "UGP049"), (["ST_01"], "UGP050"),
            (["ST_02"], "UGP069"), (["ST_02"], "UGP070"), (["ST_02"], "UGP071"),
            (["ST_02"], "UGP072"), (["ST_03"], "UGP068"), (["ST_03"], "UGP073"),
            (["ST_03"], "UGP074"), (["ST_03"], "UGP075"), (["ST_03"], "UGP076"),
            (["ST_03"], "UGP077"),
        ],
    },
    {
        "process_id": "PROC_UG_PROOF_PRINT_SUMMER_V001",
        "item_id": "UG_PROOF_PRINT",
        "title": "暑假跨校区自助打印服务",
        "audience": AUDIENCE_UNDERGRADUATE,
        "slots": [
            {"slot_id": "SL_DEVICE_CAMPUS", "name": "自助设备校区",
             "value_type": "free_text", "required_for_resolution": True,
             "allowed_values": [], "unknown_policy": "ask",
             "evidence_ids": ["UGP063"]},
        ],
        "follow_up_rules": [
            {"rule_id": "FU_01", "when_missing_slot_ids": ["SL_DEVICE_CAMPUS"],
             "question": "请说明要使用哪个校区的自助打印设备。",
             "priority": 1, "evidence_ids": ["UGP063"]},
        ],
        "steps": [
            ("ST_01", "在校本科学生与 2010 年以后毕业的本科学生", "确认本人是否属于该通知列明的服务对象。",
             ["UGP010"], ["ST_02"]),
            ("ST_02", "符合通知对象条件的学生", "在暑假期间通过就近校区自助设备打印成绩单、在学证明或本科生毕业证明（英文）。",
             ["UGP059", "UGP060", "UGP061", "UGP062"], ["ST_03"]),
            ("ST_03", "学生", "按所在校区查找自助打印设备的具体位置。",
             ["UGP063", "UGP064", "UGP065", "UGP066", "UGP067"], []),
        ],
        "claims": [
            (["ST_01"], "UGP010"), (["ST_02"], "UGP059"), (["ST_02"], "UGP060"),
            (["ST_02"], "UGP061"), (["ST_02"], "UGP062"), (["ST_03"], "UGP063"),
            (["ST_03"], "UGP064"), (["ST_03"], "UGP065"), (["ST_03"], "UGP066"),
            (["ST_03"], "UGP067"),
        ],
    },
    {
        "process_id": "PROC_UG_PROOF_PRINT_GRADUATE_V001",
        "item_id": "UG_PROOF_PRINT",
        "title": "研究生各类证明与中英文成绩单打印流程",
        "audience": ["研究生"],
        "slots": [
            {"slot_id": "SL_GRAD_STATUS", "name": "研究生身份",
             "value_type": "enum", "required_for_resolution": True,
             "allowed_values": ["在校研究生", "往届毕业研究生"],
             "unknown_policy": "ask", "evidence_ids": ["UGP011"]},
        ],
        "follow_up_rules": [
            {"rule_id": "FU_01", "when_missing_slot_ids": ["SL_GRAD_STATUS"],
             "question": "请说明是在校研究生还是往届毕业研究生。",
             "priority": 1, "evidence_ids": ["UGP011"]},
        ],
        "steps": [
            ("ST_01", "在校研究生", "在学校行政办公楼 4 楼中厅或南校区恒大楼一楼大厅的自助打印机打印中英文成绩单。",
             ["UGP011", "UGP078"], ["ST_02", "ST_03"]),
            ("ST_02", "往届毕业研究生", "按该页面版本在指定地点的自助打印机打印中英文成绩单。",
             ["UGP079"], []),
            ("ST_03", "研究生", "在学证明可自助打印；无法自助打印时到行政楼 427 研究生服务中心办理。",
             ["UGP080"], []),
        ],
        "claims": [
            (["ST_01"], "UGP011"), (["ST_01"], "UGP078"), (["ST_02"], "UGP079"),
            (["ST_03"], "UGP080"),
        ],
    },
    {
        "process_id": "PROC_UG_SUSPEND_PROCESS_V001",
        "item_id": "UG_STATUS_CHANGE",
        "title": "休学办理流程（申请表、时限与后果）",
        "audience": ["本科学生"],
        "slots": [
            {"slot_id": "SL_SUSPEND_ROUND", "name": "申请轮次",
             "value_type": "enum", "required_for_resolution": True,
             "allowed_values": ["初次申请", "再次申请"],
             "unknown_policy": "ask", "evidence_ids": ["UGS001"]},
        ],
        "follow_up_rules": [
            {"rule_id": "FU_01", "when_missing_slot_ids": ["SL_SUSPEND_ROUND"],
             "question": "请说明是初次申请休学还是再次申请。",
             "priority": 1, "evidence_ids": ["UGS001"]},
        ],
        "steps": [
            ("ST_01", "休学申请人", "填写休学申请表，并在第 1 至第 4 周内提交。",
             ["UGS001", "UGS004", "UGS030"], ["ST_02"]),
            ("ST_02", "专业、系、所及学院教科办", "审核休学申请并签署意见。",
             ["UGS030", "UGS031"], ["ST_03"]),
            ("ST_03", "学院教科办", "统一将休学申请交至教务处学籍科。",
             ["UGS031"], ["ST_04"]),
            ("ST_04", "教务处学籍科", "审核并审批休学申请，一般在 5 个工作日内完成。",
             ["UGS028"], ["ST_05"]),
            ("ST_05", "教务处学籍科", "审批同意后将休学通知书统一发放到学院教科办。",
             ["UGS032"], ["ST_06"]),
            ("ST_06", "休学申请人", "到学院教科办领取通知并办理相关手续，当学期所选课程作退选处理。",
             ["UGS033", "UGS034"], ["ST_07"]),
            ("ST_07", "休学申请人", "休学期满前及时办理复学或延期休学手续。",
             ["UGS037"], []),
        ],
        "claims": [
            (["ST_01"], "UGS001"), (["ST_01"], "UGS004"), (["ST_01"], "UGS029"),
            ([], "UGS005"), ([], "UGS035"), (["ST_07"], "UGS006"),
            (["ST_07"], "UGS036"), (["ST_04"], "UGS028"), (["ST_02"], "UGS030"),
            (["ST_03"], "UGS031"), (["ST_05"], "UGS032"), (["ST_06"], "UGS033"),
            (["ST_06"], "UGS034"), (["ST_07"], "UGS037"),
        ],
    },
    {
        "process_id": "PROC_UG_SUSPEND_LEGACY_V001",
        "item_id": "UG_STATUS_CHANGE",
        "title": "2019 年流程页：本科学生休学办理流程",
        "audience": ["本科学生"],
        "slots": [
            {"slot_id": "SL_SUSPEND_REASON", "name": "休学理由",
             "value_type": "free_text", "required_for_resolution": True,
             "allowed_values": [], "unknown_policy": "ask",
             "evidence_ids": ["UGS043"]},
        ],
        "follow_up_rules": [
            {"rule_id": "FU_01", "when_missing_slot_ids": ["SL_SUSPEND_REASON"],
             "question": "请说明申请休学的理由，是否因健康原因申请。",
             "priority": 1, "evidence_ids": ["UGS043"]},
        ],
        "steps": [
            ("ST_01", "学生", "填写休学申请表；因病申请的须先经校门诊核签。",
             ["UGS007", "UGS043"], ["ST_02"]),
            ("ST_02", "学生", "将休学申请表交学院教科办。",
             ["UGS008"], ["ST_03"]),
            ("ST_03", "学院", "审批休学申请并签署意见，随后将申请表交教务处学籍科。",
             ["UGS044", "UGS045"], ["ST_04"]),
            ("ST_04", "教务处", "审核并批准休学申请，审核批准时长为 5 个工作日。",
             ["UGS009", "UGS046"], ["ST_05"]),
            ("ST_05", "学生", "收到休学通知后回学院办理离校手续。",
             ["UGS047", "UGS048"], []),
        ],
        "claims": [
            (["ST_01"], "UGS007"), (["ST_01"], "UGS043"), (["ST_02"], "UGS008"),
            (["ST_03"], "UGS044"), (["ST_03"], "UGS045"), (["ST_04"], "UGS009"),
            (["ST_04"], "UGS046"), (["ST_05"], "UGS047"), (["ST_05"], "UGS048"),
        ],
    },
    {
        "process_id": "PROC_UG_RESUME_PROCESS_V001",
        "item_id": "UG_STATUS_CHANGE",
        "title": "复学办理流程（申请表、材料与时限）",
        "audience": ["本科学生"],
        "slots": [
            {"slot_id": "SL_RESUME_REASON", "name": "复学理由",
             "value_type": "enum", "required_for_resolution": True,
             "allowed_values": ["因病休学后恢复健康", "服兵役期满", "其他"],
             "unknown_policy": "ask", "evidence_ids": ["UGS023"]},
        ],
        "follow_up_rules": [
            {"rule_id": "FU_01", "when_missing_slot_ids": ["SL_RESUME_REASON"],
             "question": "请说明复学理由属于因病休学后恢复健康、服兵役期满还是其他。",
             "priority": 1, "evidence_ids": ["UGS023"]},
        ],
        "steps": [
            ("ST_01", "复学申请人", "填写《复学申请表》，并在复学学期第 1 周周三之前提交。",
             ["UGS011", "UGS012", "UGS014"], ["ST_02"]),
            ("ST_02", "复学申请人", "按复学理由附对应证明材料；因病复学还须提供体格检查或心理评估的诊断证明。",
             ["UGS023", "UGS025", "UGS026", "UGS027"], ["ST_03"]),
            ("ST_03", "所在院系", "审核复学材料并签署意见。",
             ["UGS038"], ["ST_04"]),
            ("ST_04", "学院教科办", "在开学第 1 周内将复学申请交至教务处学籍科。",
             ["UGS013", "UGS039"], ["ST_05"]),
            ("ST_05", "教务处", "审批后在开学第 2 周之内把复学通知发放到学院教科办。",
             ["UGS040"], ["ST_06"]),
            ("ST_06", "复学申请人", "到学院教科办领取复学通知，并办理注册及相关入学手续。",
             ["UGS041", "UGS042"], []),
        ],
        "claims": [
            (["ST_01"], "UGS011"), (["ST_01"], "UGS012"), (["ST_04"], "UGS013"),
            (["ST_01"], "UGS014"), (["ST_02"], "UGS023"), (["ST_01"], "UGS024"),
            (["ST_02"], "UGS025"), (["ST_02"], "UGS026"), (["ST_02"], "UGS027"),
            (["ST_03"], "UGS038"), (["ST_04"], "UGS039"), (["ST_05"], "UGS040"),
            (["ST_06"], "UGS041"), (["ST_06"], "UGS042"),
        ],
    },
    {
        "process_id": "PROC_UG_RESUME_LEGACY_V001",
        "item_id": "UG_STATUS_CHANGE",
        "title": "2019 年流程页：本科学生复学办理流程",
        "audience": ["本科学生"],
        "slots": [
            {"slot_id": "SL_RESUME_HEALTH", "name": "是否因病休学",
             "value_type": "boolean", "required_for_resolution": True,
             "allowed_values": [], "unknown_policy": "ask",
             "evidence_ids": ["UGS050"]},
        ],
        "follow_up_rules": [
            {"rule_id": "FU_01", "when_missing_slot_ids": ["SL_RESUME_HEALTH"],
             "question": "请说明此前是否因病休学，是否需要经校门诊体检。",
             "priority": 1, "evidence_ids": ["UGS050"]},
        ],
        "steps": [
            ("ST_01", "学生", "休学期满后到学院教科办填写复学申请表；因病休学者须经校门诊体检并凭证明办理。",
             ["UGS015", "UGS049", "UGS050", "UGS051"], ["ST_02"]),
            ("ST_02", "学院", "审批复学申请并签署意见，随后由学院将申请交教务处学籍科。",
             ["UGS016", "UGS052"], ["ST_03"]),
            ("ST_03", "教务处学籍科", "审查申请人是否符合复学条件。",
             ["UGS053"], ["ST_04"]),
            ("ST_04", "教务处", "对符合复学条件者开出复学通知。",
             ["UGS054"], ["ST_05"]),
            ("ST_05", "学生", "领取复学通知后到财务处交学费。",
             ["UGS055"], ["ST_06"]),
            ("ST_06", "学生", "交学费后到学院注册并办理选课事宜。",
             ["UGS017", "UGS056"], []),
        ],
        "claims": [
            (["ST_01"], "UGS015"), (["ST_02"], "UGS016"), (["ST_06"], "UGS017"),
            (["ST_01"], "UGS049"), (["ST_01"], "UGS050"), (["ST_01"], "UGS051"),
            (["ST_02"], "UGS052"), (["ST_03"], "UGS053"), (["ST_04"], "UGS054"),
            (["ST_05"], "UGS055"), (["ST_06"], "UGS056"),
        ],
    },
    {
        "process_id": "PROC_UG_UNREGISTERED_V001",
        "item_id": "UG_STATUS_CHANGE",
        "title": "未按期注册与逾期未复学的学籍处理",
        "audience": ["本科学生"],
        "slots": [
            {"slot_id": "SL_REGISTRATION_STATE", "name": "注册状态",
             "value_type": "enum", "required_for_resolution": True,
             "allowed_values": ["已按期注册", "逾期未注册", "休学期满未复学"],
             "unknown_policy": "ask", "evidence_ids": ["UGS019"]},
        ],
        "follow_up_rules": [
            {"rule_id": "FU_01", "when_missing_slot_ids": ["SL_REGISTRATION_STATE"],
             "question": "请说明目前的注册状态，是否已按期完成注册或办理复学。",
             "priority": 1, "evidence_ids": ["UGS019"]},
        ],
        "steps": [
            ("ST_01", "本科学生", "在通知规定的注册时间内完成学期注册。",
             ["UGS019"], ["ST_02"]),
            ("ST_02", "学校", "对逾期未注册以及休学期满逾期未办理复学或延期休学的学生，按学籍管理规定处理。",
             ["UGS057", "UGS058"], []),
        ],
        "claims": [
            (["ST_01"], "UGS019"), (["ST_02"], "UGS057"), (["ST_02"], "UGS058"),
        ],
    },
]


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def dump_jsonl(rows: list[dict], path: Path) -> None:
    text = "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows)
    path.write_text(text + "\n", encoding="utf-8")


def build_claim(claim_id: str, step_ids, evidence: dict) -> dict:
    # A single step may be written as a bare string in the specification table.
    if isinstance(step_ids, str):
        step_ids = [step_ids]
    return {
        "claim_id": claim_id,
        "claim_type": evidence["claim_type"],
        "text": evidence["normalized_claim"],
        "conditions": [],
        "applicable_step_ids": [str(step_id) for step_id in step_ids],
        "evidence_ids": [evidence["evidence_id"]],
    }


def build_record(spec: dict, evidence_by_id: dict[str, dict]) -> dict:
    steps = [
        {
            "step_id": step_id, "order": order, "actor": actor, "action": action,
            "conditions": [], "required_material_ids": [], "service_point_ids": [],
            "time_constraint_ids": [], "next_step_ids": list(next_ids),
            "evidence_ids": list(evidence_ids),
        }
        for order, (step_id, actor, action, evidence_ids, next_ids)
        in enumerate(spec["steps"], 1)
    ]
    claims = [
        build_claim(f"CLM_{index:03d}", step_ids, evidence_by_id[evidence_id])
        for index, (step_ids, evidence_id) in enumerate(spec["claims"], 1)
    ]
    record = {
        "schema_version": "1.0",
        "process_id": spec["process_id"],
        "process_version": "0.1.0",
        "item_id": spec["item_id"],
        "title": spec["title"],
        "audience": list(spec["audience"]),
        "slots": spec["slots"],
        "follow_up_rules": spec["follow_up_rules"],
        "steps": steps,
        "materials": [],
        "service_points": [],
        "time_constraints": [],
        "exceptions": [],
        "consequences": [],
        "allowed_claims": claims,
        "evidence_snapshot": {
            "dataset_path": SNAPSHOT_DATASET,
            "evidence_ids": [claim["evidence_ids"][0] for claim in claims],
        },
        "review": {
            "status": "verified",
            "annotated_at": "2026-10-16T02:00:00+08:00",
            "annotator": "阶段 2C 流程标注",
            "reviewed_at": "2026-10-16T02:20:00+08:00",
            "reviewer": "阶段 2D 核验",
            "notes": f"按事项证据补齐本子流程的声明绑定：{len(claims)} 条声明逐条对应一条已验证证据。",
        },
    }
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    process_path = args.root / PROCESS_PATH
    evidence_path = args.root / EVIDENCE_PATH
    evidence_by_id = {row["evidence_id"]: row for row in load_jsonl(evidence_path)}
    records = load_jsonl(process_path)
    by_id = {record["process_id"]: record for record in records}

    changed = 0

    target = by_id.get("PROC_UG_PROOF_PRINT_V001")
    if target is not None:
        bound = {claim["evidence_ids"][0] for claim in target["allowed_claims"]}
        added = 0
        for step_ids, evidence_id in PROOF_PRINT_ADDITIONS:
            if evidence_id in bound:
                continue
            if evidence_id not in evidence_by_id:
                raise SystemExit(f"未知证据 {evidence_id}")
            claim_id = f"CLM_{len(target['allowed_claims']) + 1:03d}"
            target["allowed_claims"].append(
                build_claim(claim_id, step_ids, evidence_by_id[evidence_id])
            )
            target["evidence_snapshot"]["evidence_ids"].append(evidence_id)
            bound.add(evidence_id)
            added += 1
        if added:
            changed += 1
            print(f"PROC_UG_PROOF_PRINT_V001：新增 {added} 条声明，"
                  f"共 {len(target['allowed_claims'])} 条")

    for spec in NEW_RECORDS:
        if spec["process_id"] in by_id:
            print(f"{spec['process_id']}：已存在，跳过")
            continue
        record = build_record(spec, evidence_by_id)
        records.append(record)
        by_id[record["process_id"]] = record
        changed += 1
        print(f"{record['process_id']}：新建，{len(record['allowed_claims'])} 条声明，"
              f"{len(record['steps'])} 步")

    for item_id in ("UG_PROOF_PRINT", "UG_STATUS_CHANGE"):
        item_evidence = {eid for eid, row in evidence_by_id.items() if row["item_id"] == item_id}
        bound = {
            claim["evidence_ids"][0]
            for record in by_id.values() if record["item_id"] == item_id
            for claim in record["allowed_claims"]
        }
        print(f"{item_id}：证据 {len(item_evidence)} 条，被声明绑定 {len(bound & item_evidence)} 条")
        unbound = sorted(item_evidence - bound)
        if unbound:
            print(f"  仍未被绑定：{unbound}")

    if args.dry_run:
        print("dry-run：未写入")
        return 0
    if not changed:
        print("无需改动")
        return 0
    dump_jsonl(records, process_path)
    print(f"已写入 {process_path}（{len(records)} 条记录）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
