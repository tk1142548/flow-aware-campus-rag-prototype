from __future__ import annotations

import csv
import json
import os
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REVIEWED_AT = "2026-07-30T22:07:35+08:00"
REVIEWER = "Codex 自动化核验"

SOURCE_RECORDS_PATH = ROOT / "data/research/source_records.jsonl"
TARGET_EVIDENCE_PATH = ROOT / "data/research/evidence_units.jsonl"
SOURCE_AUDIT_PATH = ROOT / "data/audit/source-audit.csv"
EVIDENCE_AUDIT_PATH = ROOT / "data/audit/evidence-audit.csv"

STAGE_1E_MIGRATIONS = {
    "UGP010": [
        "UGP010",
        "UGP059",
        "UGP060",
        "UGP061",
        "UGP062",
        "UGP063",
        "UGP064",
        "UGP065",
        "UGP066",
        "UGP067",
        "UGP068",
        "UGP069",
        "UGP070",
        "UGP071",
        "UGP072",
        "UGP073",
        "UGP074",
        "UGP075",
        "UGP076",
        "UGP077",
    ],
    "UGP011": ["UGP011", "UGP078", "UGP079", "UGP080"],
    "UGS007": ["UGS007", "UGS043"],
    "UGS008": ["UGS008", "UGS044", "UGS045"],
    "UGS009": ["UGS009", "UGS046", "UGS047", "UGS048"],
    "UGS010": ["UGS008", "UGS045", "UGS048"],
    "UGS015": ["UGS015", "UGS049", "UGS050", "UGS051"],
    "UGS016": ["UGS016", "UGS052", "UGS053", "UGS054"],
    "UGS017": ["UGS017", "UGS055", "UGS056"],
    "UGS018": ["UGS051", "UGS052", "UGS055", "UGS056"],
    "UGS019": ["UGS019", "UGS057", "UGS058"],
}

STAGE_1_LOCATOR_CORRECTIONS = {
    "UGS002": {
        "anchor_text": "3.学生类别：[ ]内招生 [ ]外招生",
        "review_note": (
            "阶段 1F 将锚点收缩为不跨越下划线占位区的稳定字段片段；"
            "该片段同时命中逐字原文和保存 PDF 的提取文本。"
        ),
    },
    "UGS014": {
        "anchor_text": "3.学生类别：[ ] 内招生[ ] 外招生",
        "review_note": (
            "阶段 1F 将锚点收缩为不跨越下划线占位区的稳定字段片段；"
            "该片段同时命中逐字原文和保存 PDF 的提取文本。"
        ),
    },
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def normalized_html_text(text: str) -> str:
    parser = _TextExtractor()
    parser.feed(text)
    return " ".join(" ".join(parser.parts).replace("\xa0", " ").split())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    fd, raw_temp_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp_path = Path(raw_temp_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(
                    json.dumps(
                        row,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
                handle.write("\n")
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv_atomic(
    path: Path,
    headers: list[str],
    rows: list[dict[str, str]],
) -> None:
    fd, raw_temp_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp_path = Path(raw_temp_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


SOURCE_TERMS = {
    "SRC_UG_GRAD_NOTICE_20250617": "2025 届夏季通知；暑假期间（未给出统一起止日期）",
    "SRC_GS_CERT_20130903": "页面发布于 2013-09-03；2026-07-30 快照",
    "SRC_UG_SUSPEND_PROCESS_20190418": (
        "页面更新于 2019-04-18；2026-07-30 快照"
    ),
    "SRC_UG_RESUME_PROCESS_20190418": (
        "页面更新于 2019-04-18；2026-07-30 快照"
    ),
    "SRC_UG_UNREGISTERED_20250321": "2025 年春季通知",
}

SOURCE_REVIEW_NOTES = {
    "SRC_UG_GRAD_NOTICE_20250617": (
        "已逐段核验通知日期、毕业批次、暑假服务对象、五个校区自助打印设备、"
        "可密封材料和五个密封点；正文显示更新时间与落款均为 2025-06-18，"
        "网址路径日期为 2025-06-17。两张外部 PNG 附件均已建立逐文件来源记录。"
    ),
    "SRC_UG_GRAD_NOTICE_ATTACHMENT3_20250618": (
        "已核验 PNG 文件签名、685×876 RGBA 图像和整图可读性；图片为本科生"
        "毕业证明英文版式示例，公开样例中的姓名与证书编号已遮蔽。"
    ),
    "SRC_UG_GRAD_NOTICE_ATTACHMENT4_20250618": (
        "已核验 PNG 文件签名、608×806 RGBA 图像和整图可读性；图片为主修与"
        "辅修学士学位合一的英文证明版式示例，公开样例中的姓名与证书编号已遮蔽。"
    ),
    "SRC_GS_CERT_20140616": (
        "官方旧网址重定向后返回 HTTP 410 Gone，错误页面未保存为证据；失败时间、"
        "状态、最终地址和响应元数据已登记。研究生对象与办理渠道由同机构可访问页面"
        " SRC_GS_CERT_20130903 承载，两个页面未声明版本替代关系。"
    ),
    "SRC_GS_CERT_20130903": (
        "已核验页面标题、2013-09-03 发布时间以及在校生、往届毕业研究生的"
        "中英文成绩单与在学证明办理渠道；地点和渠道按本快照版本记录。"
    ),
    "SRC_UG_SUSPEND_PROCESS_20190418": (
        "已逐步骤核验学生填表、因病校门诊核签、学院审批与移交、教务处 5 个"
        "工作日审核、休学通知和离校手续；与 2025 年表格的统一版本关系无来源声明。"
    ),
    "SRC_UG_RESUME_PROCESS_20190418": (
        "已逐步骤核验休学期满、学期开学前、因病校门诊体检、学院与教务处、"
        "复学通知、缴费、注册和选课；页面的“开学前”与 2025 年表格的第一周"
        "周三截止形成跨版本时间差异，当前均按各自来源版本保存。"
    ),
    "SRC_UG_UNREGISTERED_20250321": (
        "已核验 2025 年春季注册期、逾期两周未注册后果、休学期满逾期一个月"
        "条件、公示期、报送期限及两个附件地址；通知只适用于对应学期。"
    ),
    "SRC_UG_UNREGISTERED_NOTICE_TEMPLATE_20250321": (
        "已核验 OLE 复合文件签名；使用 Word 16.0 只读转换并整页渲染，文档为"
        " 1 页、351 个字符，标题、注册期、公示 7 天、反馈字段和示例行完整可读。"
    ),
    "SRC_UG_UNREGISTERED_SUMMARY_20250321": (
        "已核验 OLE 复合文件签名；使用 Excel 16.0 只读转换后由电子表格工具"
        "检查 1 个工作表、15×9 使用区域并完成整页渲染。正文标为“附件2”，"
        "工作表标签为“附件3”，该原始编号不一致已保留记录。"
    ),
}


def evidence(
    evidence_id: str,
    item_id: str,
    source_id: str,
    section: str,
    anchor_text: str,
    verbatim_text: str,
    normalized_claim: str,
    claim_type: str,
    audience: list[str],
    conditions: list[str],
    keywords: list[str],
    *,
    locator_type: str = "paragraph",
    effective_from: str | None = None,
    effective_to: str | None = None,
    term_label: str | None = None,
    notes: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "evidence_id": evidence_id,
        "item_id": item_id,
        "source_id": source_id,
        "source_locator": {
            "locator_type": locator_type,
            "page": None,
            "section": section,
            "anchor_text": anchor_text,
        },
        "verbatim_text": verbatim_text,
        "normalized_claim": normalized_claim,
        "claim_type": claim_type,
        "audience": audience,
        "applicability": {
            "effective_from": effective_from,
            "effective_to": effective_to,
            "term_label": term_label or SOURCE_TERMS[source_id],
            "conditions": conditions,
        },
        "keywords": keywords,
        "review": {
            "status": "verified",
            "reviewed_at": REVIEWED_AT,
            "reviewer": REVIEWER,
            "notes": notes,
        },
    }


GRAD_SOURCE = "SRC_UG_GRAD_NOTICE_20250617"
GRAD_NOTES = (
    "已逐段核对 2025-06-18 官方通知本地快照；暑假服务没有统一起止日期，"
    "毕业生对象限 2010 年以后毕业，各校区地点均绑定该限时通知版本。"
)
GRAD_AUDIENCE = ["在校本科学生", "2010 年以后毕业的本科学生"]
GRAD_CONDITIONS = ["2025 年暑假期间", "已毕业本科学生须为 2010 年以后毕业"]
GRAD_SERVICE_TEXT = (
    "在校本科生及已毕业本科学生（2010年以后毕业）暑假期间如需打印"
    "中英文成绩单、本科生毕业证明（英文）或中英文在学证明等，可在就近"
    "校区自助打印设备上打印。"
)
GRAD_SEAL_TEXT = (
    "毕业生离校前如需办理成绩单密封，可到各校区教学办申请专用信封密封。"
    "只有以下材料可放进专用信封密封：正式的中英文成绩单、本科生毕业证明"
    "（英文）、英文毕业学位证明（主辅合一）、毕业证与学位证的黑白复印件。"
)

NEW_EVIDENCE = [
    evidence(
        "UGP010",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "第三条：暑假打印对象",
        "在校本科生及已毕业本科学生",
        GRAD_SERVICE_TEXT,
        "2025 年暑假跨校区自助打印服务适用于在校本科学生和 2010 年以后毕业的本科学生。",
        "applicable_audience",
        GRAD_AUDIENCE,
        GRAD_CONDITIONS,
        ["在校本科生", "已毕业本科生", "2010年以后毕业", "暑假"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP059",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "第三条：暑假打印时间",
        "暑假期间如需打印",
        GRAD_SERVICE_TEXT,
        "该通知所述跨校区打印服务适用于暑假期间。",
        "time_constraint",
        GRAD_AUDIENCE,
        GRAD_CONDITIONS,
        ["暑假期间", "2025届夏季"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP060",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "第三条：暑假可打印事项",
        "中英文成绩单、本科生毕业证明（英文）",
        GRAD_SERVICE_TEXT,
        "符合通知对象条件的学生可在暑假期间通过就近校区自助设备打印中英文成绩单。",
        "entry",
        GRAD_AUDIENCE,
        GRAD_CONDITIONS + ["打印中英文成绩单"],
        ["中英文成绩单", "自助打印", "就近校区"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP061",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "第三条：暑假可打印事项",
        "本科生毕业证明（英文）或中英文在学证明",
        GRAD_SERVICE_TEXT,
        "符合通知对象条件的学生可在暑假期间通过就近校区自助设备打印本科生毕业证明（英文）。",
        "entry",
        GRAD_AUDIENCE,
        GRAD_CONDITIONS + ["打印本科生毕业证明（英文）"],
        ["本科生毕业证明", "英文", "自助打印"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP062",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "第三条：暑假可打印事项",
        "中英文在学证明等，可在就近校区",
        GRAD_SERVICE_TEXT,
        "符合通知对象条件的学生可在暑假期间通过就近校区自助设备打印中英文在学证明。",
        "entry",
        GRAD_AUDIENCE,
        GRAD_CONDITIONS + ["打印中英文在学证明"],
        ["中英文在学证明", "自助打印", "就近校区"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP063",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "附件1：石牌校区自助打印设备",
        "石牌校区：校本部行政办公楼 129 门口",
        "（1）石牌校区：校本部行政办公楼 129 门口",
        "2025 届夏季通知列明石牌校区自助打印设备位于校本部行政办公楼 129 门口。",
        "service_location",
        GRAD_AUDIENCE,
        GRAD_CONDITIONS + ["在石牌校区使用自助打印设备"],
        ["石牌校区", "行政办公楼129门口", "自助打印设备"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP064",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "附件1：番禺校区自助打印设备",
        "番禺校区：番禺校区教学楼一楼中厅",
        "（2）番禺校区：番禺校区教学楼一楼中厅",
        "2025 届夏季通知列明番禺校区自助打印设备位于番禺校区教学楼一楼中厅。",
        "service_location",
        GRAD_AUDIENCE,
        GRAD_CONDITIONS + ["在番禺校区使用自助打印设备"],
        ["番禺校区", "教学楼一楼中厅", "自助打印设备"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP065",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "附件1：珠海校区自助打印设备",
        "珠海校区：珠海校区行政楼 154 门口",
        "（3）珠海校区：珠海校区行政楼 154 门口",
        "2025 届夏季通知列明珠海校区自助打印设备位于珠海校区行政楼 154 门口。",
        "service_location",
        GRAD_AUDIENCE,
        GRAD_CONDITIONS + ["在珠海校区使用自助打印设备"],
        ["珠海校区", "行政楼154门口", "自助打印设备"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP066",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "附件1：华文校区自助打印设备",
        "华文校区：华文学院办公楼 2 楼中庭（ 212 门口）",
        "（4）华文校区：华文学院办公楼 2 楼中庭（ 212 门口）",
        "2025 届夏季通知列明华文校区自助打印设备位于华文学院办公楼 2 楼中庭（212 门口）。",
        "service_location",
        GRAD_AUDIENCE,
        GRAD_CONDITIONS + ["在华文校区使用自助打印设备"],
        ["华文校区", "办公楼2楼中庭", "212门口", "自助打印设备"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP067",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "附件1：深圳校区自助打印设备",
        "深圳校区：深圳校区教学楼 310 办公室",
        "（5）深圳校区：深圳校区教学楼 310 办公室（教学管理办公室）",
        "2025 届夏季通知列明深圳校区自助打印设备位于深圳校区教学楼 310 办公室（教学管理办公室）。",
        "service_location",
        GRAD_AUDIENCE,
        GRAD_CONDITIONS + ["在深圳校区使用自助打印设备"],
        ["深圳校区", "教学楼310办公室", "教学管理办公室", "自助打印设备"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP068",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "第四条：成绩单密封",
        "毕业生离校前如需办理成绩单密封",
        GRAD_SEAL_TEXT,
        "毕业生离校前如需办理成绩单密封，可到各校区教学办申请专用信封密封。",
        "step",
        ["2025 届夏季本科毕业生"],
        ["毕业生离校前", "办理成绩单密封"],
        ["成绩单密封", "离校前", "教学办", "专用信封"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP069",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "第四条：可密封材料",
        "正式的中英文成绩单",
        GRAD_SEAL_TEXT,
        "专用信封可以密封正式的中英文成绩单。",
        "material",
        ["2025 届夏季本科毕业生"],
        ["毕业生离校前申请专用信封密封"],
        ["正式中英文成绩单", "专用信封", "密封材料"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP070",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "第四条：可密封材料",
        "本科生毕业证明（英文）",
        GRAD_SEAL_TEXT,
        "专用信封可以密封本科生毕业证明（英文）。",
        "material",
        ["2025 届夏季本科毕业生"],
        ["毕业生离校前申请专用信封密封"],
        ["本科生毕业证明", "英文", "专用信封", "密封材料"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP071",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "第四条：可密封材料",
        "英文毕业学位证明（主辅合一）",
        GRAD_SEAL_TEXT,
        "专用信封可以密封英文毕业学位证明（主辅合一）。",
        "material",
        ["2025 届夏季本科毕业生"],
        ["毕业生离校前申请专用信封密封"],
        ["英文毕业学位证明", "主辅合一", "专用信封", "密封材料"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP072",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "第四条：可密封材料",
        "毕业证与学位证的黑白复印件",
        GRAD_SEAL_TEXT,
        "专用信封可以密封毕业证与学位证的黑白复印件。",
        "material",
        ["2025 届夏季本科毕业生"],
        ["毕业生离校前申请专用信封密封"],
        ["毕业证", "学位证", "黑白复印件", "密封材料"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP073",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "附件2：石牌校区密封办理点",
        "石牌校区：校本部行政办公楼 129 室",
        "（1）石牌校区：校本部行政办公楼 129 室",
        "2025 年夏季石牌校区成绩单密封办理点为校本部行政办公楼 129 室。",
        "service_location",
        ["2025 届夏季本科毕业生"],
        ["2025 年夏季", "在石牌校区办理成绩单密封"],
        ["石牌校区", "行政办公楼129室", "密封办理点"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP074",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "附件2：番禺校区密封办理点",
        "番禺校区：番禺校区图书馆 622 室",
        "（2）番禺校区：番禺校区图书馆 622 室",
        "2025 年夏季番禺校区成绩单密封办理点为番禺校区图书馆 622 室。",
        "service_location",
        ["2025 届夏季本科毕业生"],
        ["2025 年夏季", "在番禺校区办理成绩单密封"],
        ["番禺校区", "图书馆622室", "密封办理点"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP075",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "附件2：珠海校区密封办理点",
        "珠海校区：珠海校区行政楼 154 室",
        "（3）珠海校区：珠海校区行政楼 154 室",
        "2025 年夏季珠海校区成绩单密封办理点为珠海校区行政楼 154 室。",
        "service_location",
        ["2025 届夏季本科毕业生"],
        ["2025 年夏季", "在珠海校区办理成绩单密封"],
        ["珠海校区", "行政楼154室", "密封办理点"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP076",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "附件2：华文校区密封办理点",
        "华文校区：华文学院办公楼 212 室",
        "（4）华文校区：华文学院办公楼 212 室",
        "2025 年夏季华文校区成绩单密封办理点为华文学院办公楼 212 室。",
        "service_location",
        ["2025 届夏季本科毕业生"],
        ["2025 年夏季", "在华文校区办理成绩单密封"],
        ["华文校区", "办公楼212室", "密封办理点"],
        notes=GRAD_NOTES,
    ),
    evidence(
        "UGP077",
        "UG_PROOF_PRINT",
        GRAD_SOURCE,
        "附件2：深圳校区密封办理点",
        "深圳校区：深圳校区教学楼 310 办公室",
        "（5）深圳校区：深圳校区教学楼 310 办公室（教学管理办公室）",
        "2025 年夏季深圳校区成绩单密封办理点为深圳校区教学楼 310 办公室（教学管理办公室）。",
        "service_location",
        ["2025 届夏季本科毕业生"],
        ["2025 年夏季", "在深圳校区办理成绩单密封"],
        ["深圳校区", "教学楼310办公室", "教学管理办公室", "密封办理点"],
        notes=GRAD_NOTES,
    ),
]

GS_SOURCE = "SRC_GS_CERT_20130903"
GS_NOTES = (
    "旧运行数据所列研究生页面于 2026-07-30 返回 HTTP 410；本证据来自同机构"
    "可访问页面并只记录其明确写出的研究生对象和办理渠道，未建立两个网址的版本替代关系。"
)
NEW_EVIDENCE.extend(
    [
        evidence(
            "UGP011",
            "UG_PROOF_PRINT",
            GS_SOURCE,
            "页面标题",
            "研究生各类证明、中英文成绩单办理",
            "研究生各类证明、中英文成绩单办理",
            "该官方页面的办理对象和业务范围为研究生各类证明及中英文成绩单。",
            "applicable_audience",
            ["研究生"],
            ["办理研究生证明或中英文成绩单"],
            ["研究生", "证明", "中英文成绩单"],
            locator_type="section",
            notes=GS_NOTES,
        ),
        evidence(
            "UGP078",
            "UG_PROOF_PRINT",
            GS_SOURCE,
            "成绩单：在校生中英文成绩单",
            "在校生 中英文成绩单",
            "在校生 中英文成绩单 可在学校行政办公楼 4 楼中厅、南校区恒大楼一楼大厅自助打印机打印（中英文免费 2 份）。",
            "在校研究生可在学校行政办公楼 4 楼中厅或南校区恒大楼一楼大厅的自助打印机打印中英文成绩单。",
            "entry",
            ["在校研究生"],
            ["办理中英文成绩单", "页面发布于 2013-09-03"],
            ["在校研究生", "中英文成绩单", "自助打印机"],
            locator_type="table_cell",
            notes=GS_NOTES,
        ),
        evidence(
            "UGP079",
            "UG_PROOF_PRINT",
            GS_SOURCE,
            "成绩单：往届毕业生中英文成绩单",
            "往届毕业生 中英文成绩单",
            "往届毕业生 中英文成绩单 可在学校行政办公楼 4 楼中厅、南校区恒大楼一楼大厅自助打印机打印。",
            "往届毕业研究生可按该页面版本在学校行政办公楼 4 楼中厅或南校区恒大楼一楼大厅的自助打印机打印中英文成绩单。",
            "entry",
            ["往届毕业研究生"],
            ["办理中英文成绩单", "页面发布于 2013-09-03"],
            ["往届毕业研究生", "中英文成绩单", "自助打印机"],
            locator_type="table_cell",
            notes=GS_NOTES,
        ),
        evidence(
            "UGP080",
            "UG_PROOF_PRINT",
            GS_SOURCE,
            "在学证明",
            "在学证明 可在学校行政办公楼",
            "在学证明 可在学校行政办公楼 4 楼中厅、南校区恒大楼一楼大厅自助打印机打印，无法自助打印者到研究生服务中心（行政楼 427 ）室办理。",
            "研究生在学证明可按该页面版本通过指定自助打印机打印；无法自助打印时到行政楼 427 研究生服务中心办理。",
            "entry",
            ["研究生"],
            ["办理在学证明", "页面发布于 2013-09-03"],
            ["研究生在学证明", "自助打印", "研究生服务中心", "行政楼427"],
            locator_type="table_cell",
            notes=GS_NOTES,
        ),
    ]
)

SUSPEND_SOURCE = "SRC_UG_SUSPEND_PROCESS_20190418"
SUSPEND_NOTES = (
    "已逐步骤核对 2019-04-18 官方流程页本地快照；页面与 2025 年 4 月表格的"
    "统一版本关系未由来源声明，本证据只表述该页面版本。"
)
SUSPEND_FIRST = "学生填写休学申请表（因病休学须经校门诊核签），交学院教科办。"
SUSPEND_SECOND = "学院审批并签署意见后，将申请表交教务处学籍科。"
SUSPEND_THIRD = "教务处审核批准（5个工作日）后，发出休学通知。"
SUSPEND_FOURTH = "学生凭通知回学院办理离校手续。"
NEW_EVIDENCE.extend(
    [
        evidence(
            "UGS007",
            "UG_STATUS_CHANGE",
            SUSPEND_SOURCE,
            "休学流程第 1 步：填写申请表",
            "学生填写休学申请表",
            SUSPEND_FIRST,
            "学生办理休学流程时填写休学申请表。",
            "step",
            ["本科学生"],
            ["申请休学"],
            ["休学申请表", "填写申请"],
            notes=SUSPEND_NOTES,
        ),
        evidence(
            "UGS043",
            "UG_STATUS_CHANGE",
            SUSPEND_SOURCE,
            "休学流程第 1 步：因病条件",
            "因病休学须经校门诊核签",
            SUSPEND_FIRST,
            "按 2019 年流程页，因病申请休学须经校门诊核签。",
            "precondition",
            ["因病申请休学的本科学生"],
            ["因病休学", "依据 2019-04-18 更新流程页"],
            ["因病休学", "校门诊", "核签"],
            notes=SUSPEND_NOTES,
        ),
        evidence(
            "UGS008",
            "UG_STATUS_CHANGE",
            SUSPEND_SOURCE,
            "休学流程第 1 步：提交学院",
            "学生填写休学申请表（因病休学须经校门诊核签），交学院教科办",
            SUSPEND_FIRST,
            "学生将休学申请表交学院教科办。",
            "step",
            ["本科学生"],
            ["已填写休学申请表"],
            ["学院教科办", "提交申请表"],
            notes=SUSPEND_NOTES,
        ),
        evidence(
            "UGS044",
            "UG_STATUS_CHANGE",
            SUSPEND_SOURCE,
            "休学流程第 2 步：学院审批",
            "学院审批并签署意见后",
            SUSPEND_SECOND,
            "学院审批休学申请并签署意见。",
            "step",
            ["本科学生"],
            ["学院收到休学申请表"],
            ["学院审批", "签署意见"],
            notes=SUSPEND_NOTES,
        ),
        evidence(
            "UGS045",
            "UG_STATUS_CHANGE",
            SUSPEND_SOURCE,
            "休学流程第 2 步：学院移交",
            "将申请表交教务处学籍科",
            SUSPEND_SECOND,
            "学院审批并签署意见后，将休学申请表交教务处学籍科。",
            "step",
            ["本科学生"],
            ["学院已审批并签署意见"],
            ["学院", "教务处学籍科", "移交申请表"],
            notes=SUSPEND_NOTES,
        ),
        evidence(
            "UGS009",
            "UG_STATUS_CHANGE",
            SUSPEND_SOURCE,
            "休学流程第 3 步：教务处审核",
            "教务处审核批准（5个工作日）后",
            SUSPEND_THIRD,
            "教务处审核休学申请并作出批准处理。",
            "step",
            ["本科学生"],
            ["教务处学籍科收到学院移交的申请表"],
            ["教务处审核", "批准"],
            notes=SUSPEND_NOTES,
        ),
        evidence(
            "UGS046",
            "UG_STATUS_CHANGE",
            SUSPEND_SOURCE,
            "休学流程第 3 步：审核时长",
            "审核批准（5个工作日）后",
            SUSPEND_THIRD,
            "2019 年流程页将教务处审核批准时长标为 5 个工作日。",
            "time_constraint",
            ["本科学生"],
            ["教务处审核休学申请", "依据 2019-04-18 更新流程页"],
            ["5个工作日", "教务处审核", "休学"],
            notes=SUSPEND_NOTES,
        ),
        evidence(
            "UGS047",
            "UG_STATUS_CHANGE",
            SUSPEND_SOURCE,
            "休学流程第 3 步：发出通知",
            "教务处审核批准（5个工作日）后，发出休学通知",
            SUSPEND_THIRD,
            "教务处审核批准后发出休学通知。",
            "step",
            ["本科学生"],
            ["休学申请经教务处批准"],
            ["休学通知", "教务处", "审核批准"],
            notes=SUSPEND_NOTES,
        ),
        evidence(
            "UGS048",
            "UG_STATUS_CHANGE",
            SUSPEND_SOURCE,
            "休学流程第 4 步：办理离校",
            "学生凭通知回学院办理离校手续",
            SUSPEND_FOURTH,
            "学生凭休学通知回学院办理离校手续。",
            "step",
            ["本科学生"],
            ["已取得休学通知"],
            ["学院", "离校手续", "休学通知"],
            notes=SUSPEND_NOTES,
        ),
    ]
)

RESUME_SOURCE = "SRC_UG_RESUME_PROCESS_20190418"
RESUME_NOTES = (
    "已逐步骤核对 2019-04-18 官方流程页本地快照；该页的“学期开学前”与"
    " 2025 年 4 月复学表格的第一周周三截止形成跨版本时间差异，当前按来源"
    "版本分别记录，不据页面可访问状态推断现行统一规则。"
)
RESUME_FIRST = (
    "学生休学期满，于学期开学前（因病休学者须经校门诊体检，凭证明）"
    "到学院教科办填写复学申请表。"
)
RESUME_SECOND = "学院审批后，由学院交教务处学籍科。"
RESUME_THIRD = "教务处审查符合复学条件者，即开出复学通知。"
RESUME_FOURTH = "学生领复学通知后，到财务处交学费，然后到学院注册办理选课事宜。"
NEW_EVIDENCE.extend(
    [
        evidence(
            "UGS015",
            "UG_STATUS_CHANGE",
            RESUME_SOURCE,
            "复学流程第 1 步：休学期满",
            "学生休学期满，于学期开学前",
            RESUME_FIRST,
            "按 2019 年流程页，学生在休学期满后进入复学办理流程。",
            "precondition",
            ["休学期满的本科学生"],
            ["休学期满", "依据 2019-04-18 更新流程页"],
            ["休学期满", "复学"],
            notes=RESUME_NOTES,
        ),
        evidence(
            "UGS049",
            "UG_STATUS_CHANGE",
            RESUME_SOURCE,
            "复学流程第 1 步：办理时间",
            "学生休学期满，于学期开学前",
            RESUME_FIRST,
            "2019 年流程页要求学生于学期开学前办理该步复学申请。",
            "time_constraint",
            ["休学期满的本科学生"],
            ["申请复学", "依据 2019-04-18 更新流程页"],
            ["学期开学前", "复学申请"],
            notes=RESUME_NOTES,
        ),
        evidence(
            "UGS050",
            "UG_STATUS_CHANGE",
            RESUME_SOURCE,
            "复学流程第 1 步：因病条件",
            "因病休学者须经校门诊体检，凭证明",
            RESUME_FIRST,
            "按 2019 年流程页，因病休学者申请复学须经校门诊体检并凭证明办理。",
            "precondition",
            ["因病休学后申请复学的本科学生"],
            ["因病休学后申请复学", "依据 2019-04-18 更新流程页"],
            ["因病休学", "校门诊体检", "证明"],
            notes=RESUME_NOTES,
        ),
        evidence(
            "UGS051",
            "UG_STATUS_CHANGE",
            RESUME_SOURCE,
            "复学流程第 1 步：学院填表",
            "到学院教科办填写复学申请表",
            RESUME_FIRST,
            "学生到学院教科办填写复学申请表。",
            "step",
            ["休学期满的本科学生"],
            ["申请复学"],
            ["学院教科办", "复学申请表", "填写"],
            notes=RESUME_NOTES,
        ),
        evidence(
            "UGS016",
            "UG_STATUS_CHANGE",
            RESUME_SOURCE,
            "复学流程第 2 步：学院审批",
            "学院审批后，由学院交教务处学籍科",
            RESUME_SECOND,
            "学院审批复学申请。",
            "step",
            ["申请复学的本科学生"],
            ["学院收到复学申请"],
            ["学院审批", "复学申请"],
            notes=RESUME_NOTES,
        ),
        evidence(
            "UGS052",
            "UG_STATUS_CHANGE",
            RESUME_SOURCE,
            "复学流程第 2 步：学院移交",
            "由学院交教务处学籍科",
            RESUME_SECOND,
            "学院审批后，由学院将复学申请交教务处学籍科。",
            "step",
            ["申请复学的本科学生"],
            ["学院已审批复学申请"],
            ["学院", "教务处学籍科", "移交复学申请"],
            notes=RESUME_NOTES,
        ),
        evidence(
            "UGS053",
            "UG_STATUS_CHANGE",
            RESUME_SOURCE,
            "复学流程第 3 步：教务处审查",
            "教务处审查符合复学条件者",
            RESUME_THIRD,
            "教务处审查申请人是否符合复学条件。",
            "step",
            ["申请复学的本科学生"],
            ["教务处学籍科收到学院移交的复学申请"],
            ["教务处审查", "复学条件"],
            notes=RESUME_NOTES,
        ),
        evidence(
            "UGS054",
            "UG_STATUS_CHANGE",
            RESUME_SOURCE,
            "复学流程第 3 步：开出通知",
            "教务处审查符合复学条件者，即开出复学通知",
            RESUME_THIRD,
            "教务处对符合复学条件者开出复学通知。",
            "step",
            ["符合复学条件的本科学生"],
            ["教务处审查符合复学条件"],
            ["复学通知", "教务处", "符合复学条件"],
            notes=RESUME_NOTES,
        ),
        evidence(
            "UGS017",
            "UG_STATUS_CHANGE",
            RESUME_SOURCE,
            "复学流程第 4 步：领取通知",
            "学生领复学通知后",
            RESUME_FOURTH,
            "学生领取复学通知后进入缴费、注册和选课步骤。",
            "step",
            ["获准复学的本科学生"],
            ["已获教务处开出的复学通知"],
            ["领取复学通知", "后续步骤"],
            notes=RESUME_NOTES,
        ),
        evidence(
            "UGS055",
            "UG_STATUS_CHANGE",
            RESUME_SOURCE,
            "复学流程第 4 步：缴费",
            "学生领复学通知后，到财务处交学费",
            RESUME_FOURTH,
            "学生领取复学通知后到财务处交学费。",
            "step",
            ["获准复学的本科学生"],
            ["已领取复学通知"],
            ["财务处", "交学费", "复学通知"],
            notes=RESUME_NOTES,
        ),
        evidence(
            "UGS056",
            "UG_STATUS_CHANGE",
            RESUME_SOURCE,
            "复学流程第 4 步：注册选课",
            "然后到学院注册办理选课事宜",
            RESUME_FOURTH,
            "学生交学费后到学院注册并办理选课事宜。",
            "step",
            ["获准复学的本科学生"],
            ["已领取复学通知", "已到财务处交学费"],
            ["学院", "注册", "选课", "复学"],
            notes=RESUME_NOTES,
        ),
    ]
)

UNREGISTERED_SOURCE = "SRC_UG_UNREGISTERED_20250321"
UNREGISTERED_NOTES = (
    "已逐段核对 2025-03-21 官方通知本地快照；注册期和清退范围只绑定"
    " 2025 年春季通知，通知引用的学籍管理规定条款未据该通知推断统一生效区间。"
)
NEW_EVIDENCE.extend(
    [
        evidence(
            "UGS019",
            "UG_STATUS_CHANGE",
            UNREGISTERED_SOURCE,
            "通知导语：2025 年春季注册期",
            "本科学生注册时间为",
            "根据暨南大学 2025 年春季学期全日制本科生开学工作安排，本科学生注册时间为 2025 年 3 月 3 日—3 月 14 日。",
            "2025 年春季学期本科学生注册时间为 2025 年 3 月 3 日至 3 月 14 日。",
            "time_constraint",
            ["2025 年春季学期全日制本科学生"],
            ["办理 2025 年春季学期注册"],
            ["2025年春季", "注册时间", "3月3日", "3月14日"],
            effective_from="2025-03-03",
            effective_to="2025-03-14",
            notes=UNREGISTERED_NOTES,
        ),
        evidence(
            "UGS057",
            "UG_STATUS_CHANGE",
            UNREGISTERED_SOURCE,
            "通知导语：逾期两周未注册后果",
            "未经请假逾期两周不注册者，按自动退学处理",
            "根据《暨南大学本科学生学分制学籍管理规定》第一章第四条的要求，“未经请假逾期两周不注册者，按自动退学处理”。",
            "通知引用的学籍管理规定要求：未经请假且逾期两周不注册者，按自动退学处理。",
            "consequence",
            ["本科学生"],
            ["未经请假", "逾期两周未注册"],
            ["逾期两周", "未注册", "自动退学", "未经请假"],
            term_label="2025 年春季通知引用的学籍管理规定",
            notes=UNREGISTERED_NOTES,
        ),
        evidence(
            "UGS058",
            "UG_STATUS_CHANGE",
            UNREGISTERED_SOURCE,
            "第一条第三项：休学期满清退范围",
            "休学期满逾期1个月未办理复学手续",
            "（三）休学期满逾期1个月未办理复学手续，或者未办理延期休学手续者。",
            "2025 年春季本次清退范围包括休学期满逾期 1 个月未办理复学手续，或者未办理延期休学手续者。",
            "consequence",
            ["休学期满的本科学生"],
            ["休学期满逾期1个月未办理复学手续，或未办理延期休学手续"],
            ["休学期满", "逾期1个月", "未办理复学", "延期休学", "清退范围"],
            notes=UNREGISTERED_NOTES,
        ),
    ]
)


EVIDENCE_AUDIT_UPDATES = {
    "UGP010": {
        "known_issue": (
            "通知页面实际日期为 2025-06-18，网址路径为 2025-06-17；服务只适用于"
            " 2025 届夏季与暑假期间，毕业生对象限 2010 年以后毕业，暑假未给出"
            "统一起止日期，设备和密封点均为限时地点。"
        ),
        "next_action": (
            "阶段 2 将毕业年份、毕业批次、暑假时段、校区、打印事项和密封材料"
            "编码为条件与版本冲突样例。"
        ),
    },
    "UGP011": {
        "known_issue": (
            "旧来源网址返回 HTTP 410，标题和 2014-06-16 日期无法复核；迁移证据"
            "来自同机构 2013-09-03 可访问页面，两个网址没有可证明的版本替代关系。"
        ),
        "next_action": (
            "阶段 2 使用可访问页面的明确研究生对象与渠道构造本科生、研究生对象"
            "错配样例，不复用失效页面的人工结论。"
        ),
    },
    "UGS007": {
        "known_issue": (
            "2019 年流程页明确要求因病休学经校门诊核签；2025 年表格列健康原因"
            "证明但未声明两个来源的统一版本关系。"
        ),
        "next_action": "阶段 2 将因病条件绑定 2019 流程页版本，并设置来源版本缺失时的拒答样例。",
    },
    "UGS008": {
        "known_issue": "原文已拆分学生提交、学院审批签署意见和学院移交学籍科三个动作。",
        "next_action": "阶段 2 按办理主体和顺序建立流程节点与步骤遗漏样例。",
    },
    "UGS009": {
        "known_issue": "原文已拆分教务处审核、5 个工作日时长、发出通知和返院离校四个命题。",
        "next_action": "阶段 2 分别标注审批时长、通知前置条件和离校后续动作。",
    },
    "UGS010": {
        "known_issue": "旧记录是对流程节点的人工归纳，迁移映射复用三个已有原子步骤，未新增重复事实。",
        "next_action": "阶段 2 从原子步骤派生地点视图，回答仍绑定实际步骤证据。",
    },
    "UGS015": {
        "known_issue": (
            "2019 年流程页写“学期开学前”，2025 年表格写复学学期第一周周三之前；"
            "两者形成跨版本时间差异，来源未声明替代关系。"
        ),
        "next_action": "阶段 2 将两个时间条件作为版本冲突样例，缺少版本信息时不得合并成统一截止时间。",
    },
    "UGS016": {
        "known_issue": "学院审批、学院移交、教务处条件审查和开出通知已拆成四个原子步骤。",
        "next_action": "阶段 2 按主体、条件和动作建立复学审批流程与步骤遗漏样例。",
    },
    "UGS017": {
        "known_issue": "领取通知、财务处缴费、学院注册选课已拆分，并保留原文的先后顺序。",
        "next_action": "阶段 2 将通知、缴费、注册和选课建成有序步骤及顺序错误样例。",
    },
    "UGS018": {
        "known_issue": "旧记录是对办理地点的人工归纳，迁移映射复用四个已有原子步骤，未新增重复事实。",
        "next_action": "阶段 2 从步骤中的办理主体生成地点视图，不使用脱离步骤的固定地点列表。",
    },
    "UGS019": {
        "known_issue": (
            "通知只适用于 2025 年春季；注册期、逾期两周自动退学条件和休学期满"
            "逾期一个月清退范围已拆开，引用规定未推断统一生效区间。"
        ),
        "next_action": "阶段 2 分别构造学期版本、是否请假、逾期时长和手续状态的条件样例。",
    },
}


SOURCE_AUDIT_UPDATES = {
    "SRC_UG_PRINT_20210317": {
        "next_action": "阶段 2 将对象、年份边界、地点、费用和联系方式纳入版本化评测标注。",
    },
    "SRC_UG_GRAD_NOTICE_20250617": {
        "publish_date_status": "known",
        "snapshot_status": "captured",
        "locator_status": "complete",
        "version_status": "time_bounded",
        "content_review_status": "verified",
        "known_issue": (
            "页面日期为 2025-06-18，网址路径为 2025-06-17；暑假没有统一起止日期，"
            "毕业生限 2010 年以后，五校区设备和密封点只绑定该通知。两张版式附件已固化。"
        ),
        "next_action": "阶段 2 将毕业批次、年份、暑假、校区和密封条件建成版本化样例。",
        "review_status": "verified",
    },
    "SRC_GS_CERT_20140616": {
        "publish_date_status": "needs_verification",
        "snapshot_status": "failed",
        "locator_status": "partial",
        "version_status": "unknown",
        "content_review_status": "rejected",
        "known_issue": (
            "旧网址返回 HTTP 410，旧标题和 2014-06-16 日期无法复核；研究生对象与"
            "渠道改由同机构 SRC_GS_CERT_20130903 页面承载，未建立版本替代关系。"
        ),
        "next_action": "阶段 2 使用可访问研究生院页面构造对象排除样例，并保留旧网址失效标记。",
        "review_status": "verified",
    },
    "SRC_UG_SUSPEND_FORM": {
        "next_action": "阶段 2 将表格字段、材料、周次、后果与 2019 流程页共同纳入版本化流程标注。",
    },
    "SRC_UG_SUSPEND_PROCESS_20190418": {
        "publish_date_status": "known",
        "snapshot_status": "captured",
        "locator_status": "complete",
        "version_status": "unknown",
        "content_review_status": "verified",
        "known_issue": (
            "2019 流程页与 2025 表格的统一版本关系无来源声明；因病校门诊核签和"
            " 5 个工作日审批时长只按该流程页版本保存。"
        ),
        "next_action": "阶段 2 将流程步骤与 2025 表格字段对齐，并显式保存来源版本。",
        "review_status": "verified",
    },
    "SRC_UG_RESUME_FORM": {
        "next_action": "阶段 2 将材料、第一周周三截止、学院提交和第二周通知与 2019 流程页对齐。",
    },
    "SRC_UG_RESUME_PROCESS_20190418": {
        "publish_date_status": "known",
        "snapshot_status": "captured",
        "locator_status": "complete",
        "version_status": "unknown",
        "content_review_status": "verified",
        "known_issue": (
            "2019 流程页的“学期开学前”与 2025 表格的第一周周三截止形成跨版本"
            "时间差异；来源未声明替代关系。"
        ),
        "next_action": "阶段 2 将两个时间条件建成版本冲突样例，流程步骤按各自来源绑定。",
        "review_status": "verified",
    },
    "SRC_UG_UNREGISTERED_20250321": {
        "publish_date_status": "known",
        "snapshot_status": "captured",
        "locator_status": "complete",
        "version_status": "time_bounded",
        "content_review_status": "verified",
        "known_issue": (
            "通知仅适用于 2025 年春季；注册期、清退范围、公示期和 4 月 11 日报送"
            "期限具有不同条件。两个附件已固化，汇总表正文与工作表标签的附件编号不一致。"
        ),
        "next_action": "阶段 2 将学期、请假、逾期时长、复学或延期手续和后果拆成条件样例。",
        "review_status": "verified",
    },
}


def validate_new_evidence(records: list[dict[str, Any]]) -> None:
    ids = [row["evidence_id"] for row in records]
    if len(ids) != 47 or len(ids) != len(set(ids)):
        raise ValueError(
            f"expected 47 unique stage 1E evidence IDs, got {len(ids)} rows"
        )

    source_paths = {
        "SRC_UG_GRAD_NOTICE_20250617": (
            ROOT / "data/sources/SRC_UG_GRAD_NOTICE_20250617/page.html"
        ),
        "SRC_GS_CERT_20130903": (
            ROOT / "data/sources/SRC_GS_CERT_20130903/page.html"
        ),
        "SRC_UG_SUSPEND_PROCESS_20190418": (
            ROOT / "data/sources/SRC_UG_SUSPEND_PROCESS_20190418/page.html"
        ),
        "SRC_UG_RESUME_PROCESS_20190418": (
            ROOT / "data/sources/SRC_UG_RESUME_PROCESS_20190418/page.html"
        ),
        "SRC_UG_UNREGISTERED_20250321": (
            ROOT / "data/sources/SRC_UG_UNREGISTERED_20250321/page.html"
        ),
    }
    source_text = {
        source_id: normalized_html_text(path.read_text(encoding="utf-8"))
        for source_id, path in source_paths.items()
    }
    errors: list[str] = []
    for row in records:
        anchor = " ".join(
            row["source_locator"]["anchor_text"].replace("\xa0", " ").split()
        )
        if anchor not in source_text[row["source_id"]]:
            errors.append(f"{row['evidence_id']}: anchor not found: {anchor!r}")
        if row["source_locator"]["anchor_text"] not in row["verbatim_text"]:
            errors.append(
                f"{row['evidence_id']}: anchor absent from verbatim_text"
            )
    if errors:
        raise ValueError("\n".join(errors))


def main() -> int:
    validate_new_evidence(NEW_EVIDENCE)

    source_records = load_jsonl(SOURCE_RECORDS_PATH)
    source_by_id = {row["source_id"]: row for row in source_records}
    missing_source_updates = sorted(set(SOURCE_REVIEW_NOTES) - set(source_by_id))
    if missing_source_updates:
        raise ValueError(f"missing source records: {missing_source_updates}")
    for source_id, notes in SOURCE_REVIEW_NOTES.items():
        source_by_id[source_id]["review"] = {
            "status": "verified",
            "reviewed_at": REVIEWED_AT,
            "reviewer": REVIEWER,
            "notes": notes,
        }

    target_evidence = load_jsonl(TARGET_EVIDENCE_PATH)
    existing_by_id = {row["evidence_id"]: row for row in target_evidence}
    new_ids = {row["evidence_id"] for row in NEW_EVIDENCE}
    unsafe_collisions = []
    generated_by_id = {row["evidence_id"]: row for row in NEW_EVIDENCE}
    for evidence_id in sorted(set(existing_by_id) & new_ids):
        existing = existing_by_id[evidence_id]
        generated = generated_by_id[evidence_id]
        if (
            existing.get("source_id") != generated["source_id"]
            or existing.get("item_id") != generated["item_id"]
            or existing.get("review", {}).get("reviewer") != REVIEWER
        ):
            unsafe_collisions.append(evidence_id)
    if unsafe_collisions:
        raise ValueError(
            "target evidence IDs are owned by another migration: "
            f"{unsafe_collisions}"
        )
    target_evidence = [
        row for row in target_evidence if row["evidence_id"] not in new_ids
    ]
    target_evidence.extend(NEW_EVIDENCE)
    target_by_id = {row["evidence_id"]: row for row in target_evidence}
    missing_corrections = sorted(
        set(STAGE_1_LOCATOR_CORRECTIONS) - set(target_by_id)
    )
    if missing_corrections:
        raise ValueError(
            f"target evidence missing locator corrections: {missing_corrections}"
        )
    for evidence_id, correction in STAGE_1_LOCATOR_CORRECTIONS.items():
        target = target_by_id[evidence_id]
        target["source_locator"]["anchor_text"] = correction["anchor_text"]
        if correction["anchor_text"] not in target["verbatim_text"]:
            raise ValueError(
                f"{evidence_id}: corrected anchor is absent from verbatim_text"
            )
        target["review"] = {
            "status": "verified",
            "reviewed_at": REVIEWED_AT,
            "reviewer": REVIEWER,
            "notes": correction["review_note"],
        }

    evidence_headers, evidence_audit = load_csv(EVIDENCE_AUDIT_PATH)
    evidence_audit_by_id = {row["evidence_id"]: row for row in evidence_audit}
    for legacy_id, target_ids in STAGE_1E_MIGRATIONS.items():
        row = evidence_audit_by_id[legacy_id]
        update = EVIDENCE_AUDIT_UPDATES[legacy_id]
        row["verbatim_text_status"] = "verified"
        row["claim_review_status"] = "verified"
        row["known_issue"] = update["known_issue"]
        row["next_action"] = update["next_action"]
        row["review_status"] = "verified"
        row["migration_status"] = "migrated"
        row["target_evidence_ids"] = "|".join(target_ids)

    source_headers, source_audit = load_csv(SOURCE_AUDIT_PATH)
    source_audit_by_id = {row["source_id"]: row for row in source_audit}
    for source_id, update in SOURCE_AUDIT_UPDATES.items():
        source_audit_by_id[source_id].update(update)

    write_jsonl_atomic(SOURCE_RECORDS_PATH, source_records)
    write_jsonl_atomic(TARGET_EVIDENCE_PATH, target_evidence)
    write_csv_atomic(SOURCE_AUDIT_PATH, source_headers, source_audit)
    write_csv_atomic(EVIDENCE_AUDIT_PATH, evidence_headers, evidence_audit)

    print("Stage 1E migration written.")
    print(f"  source records reviewed: {len(SOURCE_REVIEW_NOTES)}")
    print(f"  target evidence upserted: {len(NEW_EVIDENCE)}")
    print(f"  legacy mappings completed: {len(STAGE_1E_MIGRATIONS)}")
    print(f"  total target evidence: {len(target_evidence)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
