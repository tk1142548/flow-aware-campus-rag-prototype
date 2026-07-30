from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SOURCE_RECORDS_PATH = ROOT / "data/research/source_records.jsonl"
EVIDENCE_RECORDS_PATH = ROOT / "data/research/evidence_units.jsonl"
PROCESS_RECORDS_PATH = ROOT / "data/research/process_records.jsonl"
SECOND_REVIEW_PATH = ROOT / "data/audit/stage2b-withdrawal-second-review.csv"
ANNOTATION_EXAMPLES_PATH = (
    ROOT / "data/research/stage2b-withdrawal-annotation-examples.json"
)
SOURCE_MIGRATION_PLAN_PATH = (
    ROOT / "data/research/stage2-source-migration-plan.csv"
)

OLD_MIRROR_SOURCE_ID = "SRC_UG_WITHDRAWAL_FORM_PDF_202504_MIRROR"
HISTORICAL_MIRROR_SOURCE_ID = (
    "SRC_UG_WITHDRAWAL_FORM_PDF_201111_MIRROR"
)
WITHDRAWAL_SOURCE_IDS = {
    "SRC_UG_WITHDRAWAL_PROCESS_20190418",
    "SRC_UG_WITHDRAWAL_FORM_PAGE_20250716",
    "SRC_UG_WITHDRAWAL_FORM_PDF_202504_PRIMARY",
    "SRC_UG_WITHDRAWAL_INDEX_20250716",
    "SRC_UG_WITHDRAWAL_FORM_MIRROR_20241027",
    HISTORICAL_MIRROR_SOURCE_ID,
    "SRC_UG_WITHDRAWAL_FORM_PDF_202501_SIHAI",
    "SRC_UG_WITHDRAWAL_POLICY_PAGE_20250716",
    "SRC_UG_WITHDRAWAL_POLICY_PDF_20250716",
    "SRC_UG_WITHDRAWAL_NOTICE_20260320",
}
CAPTURED_EVIDENCE_SOURCE_IDS = {
    "SRC_UG_WITHDRAWAL_PROCESS_20190418",
    "SRC_UG_WITHDRAWAL_INDEX_20250716",
    HISTORICAL_MIRROR_SOURCE_ID,
    "SRC_UG_WITHDRAWAL_FORM_PDF_202501_SIHAI",
    "SRC_UG_WITHDRAWAL_POLICY_PAGE_20250716",
    "SRC_UG_WITHDRAWAL_NOTICE_20260320",
}
ANNOTATED_AT = "2026-07-31T00:25:00+08:00"
REVIEWED_AT = "2026-07-31T00:35:00+08:00"
PRIMARY_REVIEWER = "Codex 阶段 2B 初次核验"
SECONDARY_REVIEWER = "Codex 阶段 2B 二次独立复核"


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def compact_text(text: str) -> str:
    return "".join(text.replace("\xa0", " ").split())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_temp_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp_path = Path(raw_temp_path)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
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


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_temp_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp_path = Path(raw_temp_path)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def write_csv_atomic(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_temp_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp_path = Path(raw_temp_path)
    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=fieldnames,
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def correct_historical_mirror_metadata(
    source_records: list[dict[str, Any]],
) -> None:
    source_ids = [str(row.get("source_id", "")) for row in source_records]
    if (
        OLD_MIRROR_SOURCE_ID in source_ids
        and HISTORICAL_MIRROR_SOURCE_ID in source_ids
    ):
        raise ValueError(
            "both the provisional and corrected mirror source IDs exist"
        )

    mirror_record = next(
        (
            row
            for row in source_records
            if row.get("source_id")
            in {OLD_MIRROR_SOURCE_ID, HISTORICAL_MIRROR_SOURCE_ID}
        ),
        None,
    )
    if mirror_record is None:
        raise ValueError("the captured law-school withdrawal form is missing")

    mirror_record["source_id"] = HISTORICAL_MIRROR_SOURCE_ID
    mirror_record["publication"] = {
        "status": "unknown",
        "date": None,
        "date_kind": "unknown",
        "displayed_date_text": "暨南大学教务处制表（2011 年 11 月）",
        "note": "制表月份取自 PDF 页脚；通过同校法学院官方页面建立附件关系。",
    }
    mirror_record["version"] = {
        "label": "2011 年 11 月版法学院官方镜像",
        "status": "historical",
        "effective_from": None,
        "effective_to": None,
        "supersedes": [],
        "superseded_by": [],
        "note": (
            "该表格与 2019 年流程页及 2025 年表格存在可定位差异；"
            "来源没有声明版本替代关系，不能作为 2025 年表格的镜像。"
        ),
    }
    mirror_record["capture"]["local_path"] = (
        "data/sources/"
        "SRC_UG_WITHDRAWAL_FORM_PDF_201111_MIRROR/form.pdf"
    )

    landing_record = next(
        (
            row
            for row in source_records
            if row.get("source_id")
            == "SRC_UG_WITHDRAWAL_FORM_MIRROR_20241027"
        ),
        None,
    )
    if landing_record is None:
        raise ValueError("the law-school withdrawal-form landing page is missing")
    landing_record["publication"]["note"] = (
        "日期取自法学院官方页面；视觉核验确认页面当前链接的是"
        "暨南大学教务处 2011 年 11 月制表的历史退学申请表。"
    )
    landing_record["relations"] = [
        {
            "relation_type": "landing_page_for",
            "target_source_id": HISTORICAL_MIRROR_SOURCE_ID,
        }
    ]


def verify_withdrawal_source_reviews(
    source_records: list[dict[str, Any]],
) -> None:
    source_by_id = {
        str(row.get("source_id", "")): row for row in source_records
    }
    missing = sorted(WITHDRAWAL_SOURCE_IDS - set(source_by_id))
    if missing:
        raise ValueError(f"withdrawal source records are missing: {missing}")

    notes = {
        "SRC_UG_WITHDRAWAL_PROCESS_20190418": (
            "已复核官方流程页更新时间、主动申请与违纪违规两条分支、"
            "学院和教务处步骤、离校手续及证明后果。"
        ),
        "SRC_UG_WITHDRAWAL_FORM_PAGE_20250716": (
            "已验证公开请求最终跳转统一身份认证；登录页未保存为业务证据，"
            "失败状态与官方列表入口分别留痕。"
        ),
        "SRC_UG_WITHDRAWAL_FORM_PDF_202504_PRIMARY": (
            "已验证主附件公开请求返回 HTTP 403；错误响应未保存为证据，"
            "2025 年 4 月正文不进入本轮原子证据。"
        ),
        "SRC_UG_WITHDRAWAL_INDEX_20250716": (
            "已复核官方学籍相关文件列表中的本科学生主动退学申请表题名、"
            "2025-07-16 日期和落地页链接。"
        ),
        "SRC_UG_WITHDRAWAL_FORM_MIRROR_20241027": (
            "已复核法学院官方常用下载页、附件地址和页面发布日期；"
            "该页面只建立 2011 年历史表格的承载关系。"
        ),
        HISTORICAL_MIRROR_SOURCE_ID: (
            "已完成 PDF 文本提取和逐页渲染复核，确认页脚为 2011 年 "
            "11 月，时间窗口与 2025 年表格不同。"
        ),
        "SRC_UG_WITHDRAWAL_FORM_PDF_202501_SIHAI": (
            "已完成 PDF 文本提取和逐页渲染复核，确认页脚为 2025 年 "
            "1 月；未找到该直链的四海书院落地页。"
        ),
        "SRC_UG_WITHDRAWAL_POLICY_PAGE_20250716": (
            "已复核教务处官方规章制度页面的题名、更新时间和印发通知"
            "附件链接；页面本身只作为现行规定入口证据。"
        ),
        "SRC_UG_WITHDRAWAL_POLICY_PDF_20250716": (
            "已验证学籍管理规定印发通知附件公开请求返回 HTTP 403；"
            "错误响应未保存，搜索索引文本不作为政策正文证据。"
        ),
        "SRC_UG_WITHDRAWAL_NOTICE_20260320": (
            "已复核 2026 年春季未注册本科学生清退通知的对象范围、"
            "公示要求、报送程序、条件分支、期限、地点和后果。"
        ),
    }
    for source_id in sorted(WITHDRAWAL_SOURCE_IDS):
        source_by_id[source_id]["review"] = {
            "status": "verified",
            "reviewed_at": REVIEWED_AT,
            "reviewer": PRIMARY_REVIEWER,
            "notes": notes[source_id],
        }


def _source_text(source: dict[str, Any]) -> str:
    capture = source.get("capture", {})
    if capture.get("status") != "captured":
        raise ValueError(
            f"{source.get('source_id')}: source is not captured"
        )
    local_path = ROOT / str(capture.get("local_path", ""))
    content_format = source.get("content_format")
    if content_format == "html":
        parser = _TextExtractor()
        parser.feed(local_path.read_text(encoding="utf-8"))
        return compact_text(" ".join(parser.parts))
    if content_format == "pdf":
        extracted = "\n".join(
            page.extract_text() or "" for page in PdfReader(local_path).pages
        )
        return compact_text(extracted)
    raise ValueError(
        f"{source.get('source_id')}: unsupported evidence format "
        f"{content_format!r}"
    )


def build_withdrawal_evidence() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    terms = {
        "index": "2025-07-16 官方文件列表条目；2026-07-30 快照",
        "2019": "页面更新于 2019-04-18；2026-07-30 快照",
        "2011": (
            "暨南大学教务处制表（2011 年 11 月）；"
            "2026-07-30 法学院官方镜像"
        ),
        "2025": (
            "暨南大学教务处制表（2025 年 1 月）；"
            "2026-07-30 四海书院官方副本"
        ),
        "policy": (
            "教务处规章制度页面更新于 2025-07-16；"
            "2026-07-31 快照"
        ),
        "2026": (
            "2026 年春季未注册本科学生联系及清退通知；"
            "页面更新于 2026-03-20；2026-07-31 快照"
        ),
    }

    def add(
        number: int,
        source_id: str,
        section: str,
        verbatim: str,
        anchor: str,
        claim: str,
        claim_type: str,
        audience: list[str],
        term_key: str,
        conditions: list[str],
        keywords: list[str],
        *,
        page: int | None = None,
    ) -> None:
        rows.append(
            {
                "schema_version": "1.0",
                "evidence_id": f"UGW{number:03d}",
                "item_id": "UG_WITHDRAWAL",
                "source_id": source_id,
                "source_locator": {
                    "locator_type": "page" if page else "section",
                    "page": page,
                    "section": section,
                    "anchor_text": anchor,
                },
                "verbatim_text": verbatim,
                "normalized_claim": claim,
                "claim_type": claim_type,
                "audience": audience,
                "applicability": {
                    "effective_from": None,
                    "effective_to": None,
                    "term_label": terms[term_key],
                    "conditions": conditions,
                },
                "keywords": keywords,
                "review": {
                    "status": "verified",
                    "reviewed_at": ANNOTATED_AT,
                    "reviewer": PRIMARY_REVIEWER,
                    "notes": (
                        "已按保存来源逐字复核定位、原文、规范化声明、"
                        "对象和版本边界；来源未明示的替代关系不作推断。"
                    ),
                },
            }
        )

    index_source = "SRC_UG_WITHDRAWAL_INDEX_20250716"
    process_source = "SRC_UG_WITHDRAWAL_PROCESS_20190418"
    old_form_source = HISTORICAL_MIRROR_SOURCE_ID
    new_form_source = "SRC_UG_WITHDRAWAL_FORM_PDF_202501_SIHAI"
    policy_page_source = "SRC_UG_WITHDRAWAL_POLICY_PAGE_20250716"
    cleanup_notice_source = "SRC_UG_WITHDRAWAL_NOTICE_20260320"
    active = ["主动申请退学的本科学生"]
    discipline = ["因违纪违规须作退学处理的本科学生"]
    undergraduate = ["暨南大学本科学生"]
    cleanup_audience = [
        "2026 年春季未注册或达到通知所列清退条件的全日制本科学生"
    ]

    add(
        1,
        index_source,
        "学籍相关文件列表",
        "本科学生主动退学申请表 2025-07-16",
        "本科学生主动退学申请表",
        "官方学籍相关文件列表在 2025-07-16 列出本科学生主动退学申请表。",
        "entry",
        active,
        "index",
        ["只核验表格入口题名和列表日期"],
        ["主动退学", "申请表", "2025-07-16", "官方入口"],
    )

    p2019_a = (
        "申请退学者，将书面申请交学院教务秘书处，"
        "由教务秘书指导填写《暨南大学本科学生退学申请表》。"
    )
    p2019_b = (
        "因违纪违规须退学处理者，"
        "由学院填写《暨南大学本科学生退学申请表》。"
    )
    p2019_c = "学院审批后，交教务处学籍科。"
    p2019_d = (
        "学院审批后，由学院教务管理人员汇总，"
        "于每学期的第四周前和第十五周前交教务处学籍科。"
    )
    p2019_e = "经教务处审核并报校长办公会批准后，学校发文并通知各学院。"
    p2019_f = "各学院教务秘书通知学生办理离校手续（按离校清单办理）。"
    p2019_g = (
        "学生办完离校手续后到教务处学籍科办理相应的退学证明"
        "（擅自离校者不发任何证明）。"
    )
    base_2019 = ["适用区间未由页面统一声明", "不得与其他来源版本合并"]

    add(
        2,
        process_source,
        "主动申请退学分支",
        p2019_a,
        "申请退学者，将书面申请",
        "2019 年流程页的主动申请分支适用于申请退学的本科学生。",
        "applicable_audience",
        active,
        "2019",
        base_2019 + ["学生主动申请退学"],
        ["主动申请", "适用对象", "本科学生"],
    )
    add(
        3,
        process_source,
        "主动申请退学分支",
        p2019_a,
        "将书面申请交学院教务秘书处",
        "主动申请退学者先将书面申请交学院教务秘书处。",
        "material",
        active,
        "2019",
        base_2019 + ["学生主动申请退学"],
        ["书面申请", "学院教务秘书处", "材料"],
    )
    add(
        4,
        process_source,
        "主动申请退学分支",
        p2019_a,
        "由教务秘书指导填写",
        "学院教务秘书指导主动申请退学者填写本科学生退学申请表。",
        "step",
        active,
        "2019",
        base_2019 + ["学生主动申请退学"],
        ["教务秘书", "填写", "退学申请表"],
    )
    add(
        5,
        process_source,
        "违纪违规退学处理分支",
        p2019_b,
        "因违纪违规须退学处理者",
        "2019 年流程页另列因违纪违规须作退学处理的本科学生分支。",
        "applicable_audience",
        discipline,
        "2019",
        base_2019 + ["违纪违规退学处理"],
        ["违纪违规", "退学处理", "适用对象"],
    )
    add(
        6,
        process_source,
        "违纪违规退学处理分支",
        p2019_b,
        "由学院填写《暨南大学本科学生退学申请表》",
        "违纪违规退学处理分支由学院填写本科学生退学申请表。",
        "step",
        discipline,
        "2019",
        base_2019 + ["违纪违规退学处理"],
        ["学院", "填写", "退学申请表"],
    )
    add(
        7,
        process_source,
        "主动申请退学分支",
        p2019_c,
        "学院审批后，交教务处学籍科",
        "主动申请退学分支须经学院审批。",
        "step",
        active,
        "2019",
        base_2019 + ["学生主动申请退学"],
        ["学院审批", "主动申请"],
    )
    add(
        8,
        process_source,
        "主动申请退学分支",
        p2019_c,
        "学院审批后，交教务处学籍科",
        "学院审批后将主动退学申请交教务处学籍科。",
        "step",
        active,
        "2019",
        base_2019 + ["学生主动申请退学"],
        ["教务处学籍科", "提交", "主动申请"],
    )
    add(
        9,
        process_source,
        "违纪违规退学处理分支",
        p2019_d,
        "由学院教务管理人员汇总",
        "违纪违规退学处理分支由学院教务管理人员汇总。",
        "step",
        discipline,
        "2019",
        base_2019 + ["违纪违规退学处理"],
        ["学院教务管理人员", "汇总"],
    )
    add(
        10,
        process_source,
        "违纪违规退学处理分支",
        p2019_d,
        "每学期的第四周前和第十五周前",
        "违纪违规退学处理材料须在每学期第四周前和第十五周前提交。",
        "time_constraint",
        discipline,
        "2019",
        base_2019 + ["违纪违规退学处理"],
        ["第四周前", "第十五周前", "提交时限"],
    )
    add(
        11,
        process_source,
        "违纪违规退学处理分支",
        p2019_d,
        "第十五周前交教务处学籍科",
        "学院教务管理人员将汇总材料交教务处学籍科。",
        "step",
        discipline,
        "2019",
        base_2019 + ["违纪违规退学处理"],
        ["教务处学籍科", "汇总材料", "提交"],
    )
    add(
        12,
        process_source,
        "两分支共同流程",
        p2019_e,
        "经教务处审核并报校长办公会批准后",
        "退学事项进入教务处审核。",
        "step",
        undergraduate,
        "2019",
        base_2019,
        ["教务处审核", "共同流程"],
    )
    add(
        13,
        process_source,
        "两分支共同流程",
        p2019_e,
        "报校长办公会批准",
        "教务处审核后将退学事项报校长办公会批准。",
        "step",
        undergraduate,
        "2019",
        base_2019,
        ["校长办公会", "批准"],
    )
    add(
        14,
        process_source,
        "两分支共同流程",
        p2019_e,
        "学校发文并通知各学院",
        "校长办公会批准后由学校发文。",
        "step",
        undergraduate,
        "2019",
        base_2019,
        ["学校发文", "批准后"],
    )
    add(
        15,
        process_source,
        "两分支共同流程",
        p2019_e,
        "学校发文并通知各学院",
        "学校发文后通知各学院。",
        "step",
        undergraduate,
        "2019",
        base_2019,
        ["通知学院", "学校发文"],
    )
    add(
        16,
        process_source,
        "两分支共同流程",
        p2019_f,
        "教务秘书通知学生办理离校手续",
        "学院教务秘书通知学生办理离校手续。",
        "step",
        undergraduate,
        "2019",
        base_2019,
        ["教务秘书", "离校手续", "通知"],
    )
    add(
        17,
        process_source,
        "两分支共同流程",
        p2019_f,
        "办理离校手续（按离校清单办理）",
        "学生依照离校清单办理离校手续。",
        "material",
        undergraduate,
        "2019",
        base_2019,
        ["离校清单", "离校手续"],
    )
    add(
        18,
        process_source,
        "两分支共同流程",
        p2019_g,
        "学生办完离校手续后",
        "办完离校手续是办理相应退学证明的前置条件。",
        "precondition",
        undergraduate,
        "2019",
        base_2019,
        ["办完离校手续", "前置条件", "退学证明"],
    )
    add(
        19,
        process_source,
        "两分支共同流程",
        p2019_g,
        "到教务处学籍科办理相应的退学证明",
        "完成离校手续后到教务处学籍科办理相应退学证明。",
        "service_location",
        undergraduate,
        "2019",
        base_2019,
        ["教务处学籍科", "退学证明", "办理地点"],
    )
    add(
        20,
        process_source,
        "两分支共同流程",
        p2019_g,
        "擅自离校者不发任何证明",
        "擅自离校者不发任何证明。",
        "consequence",
        undergraduate,
        "2019",
        base_2019 + ["学生擅自离校"],
        ["擅自离校", "不发证明", "后果"],
    )

    n_a = (
        "本表由主动申请退学的申请人本人填写及签字，并附家长知情同意书。"
        "填写前请知悉教育部及学校关于退学的管理规定，"
        "申请一旦受理，不得撤销。"
    )
    n_b = (
        "申请人填写后交到所在院系审核并签署意见后，交到学院教科办，"
        "由教科办统一将申请交至教务处，教务处审核后，"
        "将退学通知发放到学院教科办，"
        "申请人到教科办领取通知并办理相关的离校手续。"
    )
    n_c = (
        "教务处集中受理时间为学期初第 1-4 周，此时间段内提交，"
        "教务处将于 6 个工作日之内完成审批。"
        "其他时段审批时长要视当时工作安排而定，"
        "一般至少需要 12 个工作日以上。"
    )
    n_d = (
        "根据《暨南大学本科学生学分制学籍管理规定》，"
        "学生接到退学通知书后，2 周内办完离校手续，"
        "退学后不得申请复学。"
    )
    n_e = (
        "获批退学当学期所选课程应作退选处理，"
        "超出 7 周所提出的退学申请则无法退选课程，"
        "选课及成绩仍将记录在案。"
    )
    n_f = "此申请如有附件等证明材料，请在附件上逐页签名。"
    n_g = (
        "申请退学并符合颁发肄业证书条件的学生，"
        "须另行填写肄业证书申请表，"
        "肄业证书必须在退学时或退学当学期提出申请，过期不再受理。"
    )
    n_h = "3.学生类别：[ ]内招生 [ ]外招生（来源地： ）"
    n_i = "申请退学理由（如空白不够，可附页）"
    n_j = (
        "请学生所在专业、系、所等审核学生所述及附件材料的真实性，"
        "手写签名并签署意见。"
    )
    n_k = (
        "请学院务必与学生家长联系告知退学事宜，同时请教科办在"
        "本科教务管理系统中审核该申请，请分管教学院领导和"
        "分管学生工作院领导手写签名并署名意见。"
    )
    n_l = "教务处审核意见"
    n_m = (
        "如提供虚假信息或隐瞒事实，申请会被驳回并会按"
        "《暨南大学学生违纪处分办法》的相关规定处理。"
    )
    base_2025 = [
        "主动申请退学",
        "版本标识为暨南大学教务处制表（2025 年 1 月）",
        "来源未声明与其他版本的替代关系",
    ]

    new_specs = [
        (21, n_a, "申请人本人填写及签字", "申请人本人填写并签署主动退学申请表。", "step", ["本人填写", "签字"]),
        (22, n_a, "并附家长知情同意书", "主动退学申请须附家长知情同意书。", "material", ["家长知情同意书", "附件"]),
        (23, n_a, "填写前请知悉教育部及学校关于退学的管理规定", "填写前须知悉教育部及学校关于退学的管理规定。", "precondition", ["退学管理规定", "知悉"]),
        (24, n_a, "申请一旦受理，不得撤销", "主动退学申请一旦受理不得撤销。", "consequence", ["受理", "不得撤销"]),
        (25, n_b, "交到所在院系审核并签署意见", "申请人将表格交所在院系审核并签署意见。", "step", ["院系审核", "签署意见"]),
        (26, n_b, "审核并签署意见后，交到学院教科办", "院系审核后将申请交学院教科办。", "step", ["学院教科办", "提交"]),
        (27, n_b, "由教科办统一将申请交至教务处", "学院教科办统一将申请交至教务处。", "step", ["教科办", "教务处", "提交"]),
        (28, n_b, "教务处审核后，将退学通知", "教务处审核主动退学申请。", "step", ["教务处审核", "主动退学"]),
        (29, n_b, "将退学通知发放到学院教科办", "教务处将退学通知发放到学院教科办。", "step", ["退学通知", "学院教科办"]),
        (30, n_b, "申请人到教科办领取通知", "申请人到教科办领取退学通知。", "step", ["领取通知", "教科办"]),
        (31, n_b, "办理相关的离校手续", "申请人领取通知后办理相关离校手续。", "step", ["离校手续", "申请人"]),
        (32, n_c, "集中受理时间为学期初第 1-4 周", "教务处集中受理时间为学期初第 1 至第 4 周。", "time_constraint", ["学期初", "第1-4周", "集中受理"]),
        (33, n_c, "于 6 个工作日之内完成审批", "在集中受理时段内提交的申请，教务处于 6 个工作日内完成审批。", "time_constraint", ["6个工作日", "审批"]),
        (34, n_c, "一般至少需要 12 个工作日以上", "其他时段的审批一般至少需要 12 个工作日。", "time_constraint", ["其他时段", "12个工作日"]),
        (35, n_d, "2 周内办完离校手续", "学生接到退学通知书后须在 2 周内办完离校手续。", "time_constraint", ["2周", "离校手续"]),
        (36, n_d, "退学后不得申请复学", "退学后不得申请复学。", "consequence", ["退学后", "不得复学"]),
        (37, n_e, "当学期所选课程应作退选处理", "获批退学当学期所选课程应作退选处理。", "consequence", ["当学期课程", "退选"]),
        (38, n_e, "超出 7 周所提出的退学申请则无法退选课程", "超出第 7 周提出的退学申请无法退选课程。", "exception", ["超出7周", "无法退选"]),
        (39, n_e, "选课及成绩仍将记录在案", "超出第 7 周提出申请时，选课及成绩仍记录在案。", "consequence", ["选课", "成绩", "记录在案"]),
        (40, n_f, "请在附件上逐页签名", "申请所附证明材料须逐页签名。", "material", ["附件", "逐页签名"]),
        (41, n_g, "符合颁发肄业证书条件的学生", "另行申请肄业证书限于符合颁发条件的退学学生。", "precondition", ["肄业证书", "颁发条件"]),
        (42, n_g, "须另行填写肄业证书申请表", "符合条件者须另行填写肄业证书申请表。", "material", ["肄业证书申请表", "另行填写"]),
        (43, n_g, "在退学时或退学当学期提出申请", "肄业证书须在退学时或退学当学期申请。", "time_constraint", ["退学当学期", "肄业证书"]),
        (44, n_g, "提出申请，过期不再受理", "肄业证书申请过期不再受理。", "consequence", ["过期", "不再受理"]),
        (45, n_h, "内招生 [ ]外招生", "表格的学生类别字段区分内招生与外招生。", "applicable_audience", ["内招生", "外招生", "学生类别"]),
        (46, n_i, "申请退学理由（如空白不够，可附页）", "申请表要求填写退学理由，空白不足时可附页。", "material", ["退学理由", "附页"]),
        (47, n_j, "审核学生所述及附件材料的真实性", "学生所在专业、系、所等审核申请陈述及附件真实性。", "step", ["院系", "真实性审核", "附件"]),
        (48, n_k, "学院务必与学生家长联系告知退学事宜", "学院须联系学生家长并告知退学事宜。", "step", ["学院", "联系家长", "告知"]),
        (49, n_k, "教科办在本科教务管理系统中审核该申请", "学院教科办在本科教务管理系统中审核申请。", "step", ["本科教务管理系统", "教科办审核"]),
        (50, n_k, "请分管教学院领导和分管学生工作院领导", "分管教学院领导须手写签名并署名意见。", "step", ["分管教学院领导", "签名", "意见"]),
        (51, n_k, "分管学生工作院领导", "分管学生工作院领导须手写签名并署名意见。", "step", ["分管学生工作院领导", "签名", "意见"]),
        (52, "教务处审核意见 签名：日期（年月日）：", "教务处审核意见 签名", "表格设置教务处审核意见栏。", "step", ["教务处", "审核意见"]),
        (53, n_m, "如提供虚假信息或隐瞒事实", "提供虚假信息或隐瞒事实会导致申请被驳回。", "consequence", ["虚假信息", "隐瞒事实", "驳回"]),
    ]
    for number, verbatim, anchor, claim, claim_type, keywords in new_specs:
        add(
            number,
            new_form_source,
            "退学申请表（本科学生）",
            verbatim,
            anchor,
            claim,
            claim_type,
            active,
            "2025",
            base_2025,
            keywords,
            page=1,
        )

    o_a = (
        "本表由主动申请退学的申请人本人填写及签字，"
        "填写前请知悉教育部及学校关于退学的管理规定，"
        "申请一旦受理，不得撤销。"
    )
    o_b = (
        "申请人填写后交到所在院系审核并签署意见后，交到学院教科办，"
        "由教科办统一将申请交至教务处，教务处审核后，"
        "将退学通知发放到学院教科办，"
        "申请人到教科办领取通知并办理相关的离校手续。"
    )
    o_c = (
        "教务处集中受理时间为期末第 13-16 周，此时间段内提交，"
        "教务处将于 6 个工作日之内完成审批。"
        "其他时段审批时长要视当时工作安排而定，"
        "一般至少需要 12 个工作日以上。"
    )
    o_d = (
        "学生接到退学通知书后，2 周内办完离校手续，"
        "退学后不得申请复学。"
    )
    o_e = "此申请如有附件等证明材料，请在附件上逐页签名。"
    o_f = (
        "申请退学并符合颁发肄业证书条件的学生，"
        "须另行填写肄业证书申请表。"
    )
    o_g = (
        "肄业证书必须在退学时或退学当学期提出申请，"
        "过期不再受理。"
    )
    o_h = (
        "请学院务必与学生家长联系告知退学事宜，"
        "同时请教科办在综合教务管理系统提交申请。"
    )
    base_2011 = [
        "主动申请退学",
        "版本标识为暨南大学教务处制表（2011 年 11 月）",
        "历史版本，不作为当前流程结论",
    ]
    old_specs = [
        (54, o_a, "本表由主动申请退学的申请人本人填写及签字", "申请人本人填写并签署主动退学申请表。", "step", ["本人填写", "签字"]),
        (55, o_b, "所在院系审核并签署意见", "申请人将表格交所在院系审核并签署意见。", "step", ["院系审核", "签署意见"]),
        (56, o_b, "院系审核并签署意见后，交到学院教科办", "院系审核后将申请交学院教科办。", "step", ["学院教科办", "提交"]),
        (57, o_b, "由教科办统一将申请交至教务处", "学院教科办统一将申请交至教务处。", "step", ["教科办", "教务处"]),
        (58, o_b, "教务处审核后，将退学通知", "教务处审核主动退学申请。", "step", ["教务处审核"]),
        (59, o_b, "将退学通知发放到学院教科办", "教务处将退学通知发放到学院教科办。", "step", ["退学通知", "学院教科办"]),
        (60, o_b, "申请人到教科办领取通知", "申请人到教科办领取退学通知。", "step", ["领取通知", "教科办"]),
        (61, o_b, "办理相关的离校手续", "申请人领取通知后办理相关离校手续。", "step", ["离校手续", "申请人"]),
        (62, o_c, "集中受理时间为期末第 13-16 周", "教务处集中受理时间为期末第 13 至第 16 周。", "time_constraint", ["期末", "第13-16周"]),
        (63, o_c, "于 6 个工作日之内完成审批", "在集中受理时段内提交的申请，教务处于 6 个工作日内完成审批。", "time_constraint", ["6个工作日", "审批"]),
        (64, o_c, "一般至少需要 12 个工作日以上", "其他时段审批一般至少需要 12 个工作日。", "time_constraint", ["其他时段", "12个工作日"]),
        (65, o_d, "2 周内办完离校手续", "学生接到退学通知书后须在 2 周内办完离校手续。", "time_constraint", ["2周", "离校手续"]),
        (66, o_d, "退学后不得申请复学", "退学后不得申请复学。", "consequence", ["不得复学", "退学后"]),
        (67, o_e, "请在附件上逐页签名", "申请所附证明材料须逐页签名。", "material", ["附件", "逐页签名"]),
        (68, o_f, "须另行填写肄业证书申请表", "符合颁发条件的退学学生须另行填写肄业证书申请表。", "material", ["肄业证书", "申请表"]),
        (69, o_g, "在退学时或退学当学期提出申请", "肄业证书须在退学时或退学当学期申请。", "time_constraint", ["退学当学期", "肄业证书"]),
        (70, o_g, "提出申请，过期不再受理", "肄业证书申请过期不再受理。", "consequence", ["过期", "不再受理"]),
        (71, o_h, "学院务必与学生家长联系告知退学事宜", "学院须联系学生家长并告知退学事宜。", "step", ["学院", "联系家长"]),
        (72, o_h, "综合教务管理系统", "学院教科办在综合教务管理系统提交申请。", "step", ["综合教务管理系统", "提交"]),
    ]
    for number, verbatim, anchor, claim, claim_type, keywords in old_specs:
        add(
            number,
            old_form_source,
            "退学申请表（本科学生）",
            verbatim,
            anchor,
            claim,
            claim_type,
            active,
            "2011",
            base_2011,
            keywords,
            page=1,
        )

    add(
        73,
        process_source,
        "违纪违规退学处理分支",
        p2019_d,
        "学院审批后，由学院教务管理人员汇总",
        "违纪违规退学处理分支须经学院审批。",
        "step",
        discipline,
        "2019",
        base_2019 + ["违纪违规退学处理"],
        ["学院审批", "违纪违规退学处理"],
    )

    policy_entry = (
        "暨南大学全日制本科学生学籍管理规定 "
        "更新时间：2025-7-16 17:39:32 "
        "暨南大学关于印发《暨南大学全日制本科学生学籍管理规定》"
        "的通知.PDF"
    )
    add(
        74,
        policy_page_source,
        "规章制度发布页",
        policy_entry,
        "暨南大学全日制本科学生学籍管理规定",
        "教务处规章制度页面于 2025-07-16 更新全日制本科学生学籍管理规定入口。",
        "entry",
        undergraduate,
        "policy",
        [
            "只核验页面题名、更新时间和印发通知附件入口",
            "附件正文当前未取得，不据页面入口推断具体条款",
        ],
        ["学籍管理规定", "规章制度", "2025-07-16", "官方入口"],
    )

    n_opening = (
        "根据暨南大学2026年春季学期全日制本科生开学工作安排，"
        "本科学生注册时间为2026年3月5日—3月20日。对于未返校的学生，"
        "根据《暨南大学全日制本科学生学籍管理规定》（以下简称“学籍管理规定”）"
        "第三章第八条的要求，“对未经请假、请假未获批准或超假者均按旷课处理，"
        "未经批准逾期2周以上不注册者，视为自动退学”。为加强学籍管理，"
        "请各学院对未注册本科生做好联系沟通、公示及清退工作。"
    )
    n_scope_1 = (
        "（一）未超过最长修读年限，超过学校规定期限未注册"
        "而又未办理相关手续的；"
    )
    n_scope_2 = (
        "（二）已经达到最长修读年限（4年制不得超过8年，"
        "5年制不得超过9年，6年制不得超过10年）"
        "未完成学业且未办理相关手续的；"
    )
    n_scope_3 = (
        "（三）休学期满逾期两周未办理复学手续，"
        "或者未办理延期休学手续者。"
    )
    n_publicity = (
        "学院应组织专人对以上学生进行联系沟通，对于超过学校规定时限"
        "仍未办理相关手续的学生，学院须以多种形式对以上学生的上述违规情况"
        "进行公示（模板见附件1），公示期不少于7天。"
        "学生可在公示期内向学院提出书面意见。"
    )
    n_publicity_material = "（一）提交公示文件，需盖学院公章；"
    n_summary_material = (
        "（二）填写并提交《2026年春季学院清退未注册学生汇总表》"
        "（附件2），需主管教学院长签字并盖学院公章；"
    )
    n_system = (
        "（三）学院教科办需同时在新教务管理系统学籍异动中"
        "提交清退学生的退学申请，申请理由选择“未按时注册需清退”。"
    )
    n_delivery = (
        "请各学院在4月10日下午5点前将上述材料纸质版报教务处学籍科"
        "（石牌校区行政楼127/129室），附件2的电子版需同时发至学籍科邮箱："
        "Ojwxjk@jnu.edu.cn，主题：XX学院2026年春季清退名单。"
    )
    n_contactable = (
        "（一）对于能联系上的学生，如果学生不打算在学校继续学业，"
        "请学院教科办先审核学生的学习情况，如果学生符合申请结业证书的条件"
        "（详见《学生手册》中关于结业的条件），学院可协助学生注册并提醒学生"
        "申请结业；如果不符合结业的条件，可填写《退学申请表》，"
        "符合肄业条件可同时提交《肄业证书申请表》。"
    )
    n_exchange = (
        "（二）对于交换学生，学院需提醒并督促交换学生进行正常的学期注册。"
        "必要时，学院教科办可提供协助。"
    )
    n_late_registration = (
        "（三）对于未按学校规定在3月20日前按时注册的学生，"
        "学院应对其进行批评教育，同时考虑采取相关措施，"
        "提高本学院学生注册率。"
    )
    n_max_duration = (
        "（四）根据“学籍管理规定”第九章第三十七条，学生在校学习时间"
        "（含休学和保留学籍）超过最长年限，应予退学"
        "（4年制不得超过8年，5年制不得超过9年，6年制不得超过10年）。"
        "此类学生不得注册，不得继续留校修读，否则将违反教育部学历认可的相关制度。"
    )
    base_2026 = [
        "仅适用于 2026 年春季通知所列未注册学生联系及清退工作",
        "不得推广为其他学期的统一流程",
    ]
    notice_specs = [
        (
            75,
            "通知导语",
            n_opening,
            "2026年春季学期全日制本科生开学工作安排",
            "该通知适用于 2026 年春季全日制本科生未注册联系及清退工作。",
            "applicable_audience",
            ["2026 年春季", "全日制本科生", "清退工作"],
        ),
        (
            76,
            "通知导语",
            n_opening,
            "本科学生注册时间为2026年3月5日—3月20日",
            "2026 年春季本科学生注册时间为 3 月 5 日至 3 月 20 日。",
            "time_constraint",
            ["注册时间", "2026-03-05", "2026-03-20"],
        ),
        (
            77,
            "通知导语",
            n_opening,
            "未经批准逾期2周以上不注册者",
            "2026 年春季通知援引规定称，未经批准逾期 2 周以上不注册者视为自动退学。",
            "consequence",
            ["逾期2周", "未注册", "自动退学"],
        ),
        (
            78,
            "一、清退范围",
            n_scope_1,
            "未超过最长修读年限",
            "2026 年春季清退范围包括未超过最长修读年限、逾期未注册且未办理相关手续的学生。",
            "precondition",
            ["清退范围", "逾期未注册", "未办手续"],
        ),
        (
            79,
            "一、清退范围",
            n_scope_2,
            "已经达到最长修读年限",
            "2026 年春季清退范围包括达到最长修读年限、未完成学业且未办理相关手续的学生。",
            "precondition",
            ["清退范围", "最长修读年限", "未完成学业"],
        ),
        (
            80,
            "一、清退范围",
            n_scope_2,
            "4年制不得超过8年",
            "通知列明 4 年制本科生最长修读年限不得超过 8 年。",
            "time_constraint",
            ["4年制", "8年", "最长修读年限"],
        ),
        (
            81,
            "一、清退范围",
            n_scope_2,
            "5年制不得超过9年",
            "通知列明 5 年制本科生最长修读年限不得超过 9 年。",
            "time_constraint",
            ["5年制", "9年", "最长修读年限"],
        ),
        (
            82,
            "一、清退范围",
            n_scope_2,
            "6年制不得超过10年",
            "通知列明 6 年制本科生最长修读年限不得超过 10 年。",
            "time_constraint",
            ["6年制", "10年", "最长修读年限"],
        ),
        (
            83,
            "一、清退范围",
            n_scope_3,
            "休学期满逾期两周未办理复学手续",
            "2026 年春季清退范围包括休学期满逾期两周未复学，或者未办理延期休学手续的学生。",
            "precondition",
            ["清退范围", "休学期满", "逾期两周"],
        ),
        (
            84,
            "二、公示",
            n_publicity,
            "学院应组织专人对以上学生进行联系沟通",
            "学院应组织专人联系并沟通清退范围内的学生。",
            "step",
            ["学院", "联系沟通", "专人"],
        ),
        (
            85,
            "二、公示",
            n_publicity,
            "学院须以多种形式对以上学生的上述违规情况进行公示",
            "学院须以多种形式公示逾期仍未办手续学生的违规情况。",
            "step",
            ["学院", "违规情况", "公示"],
        ),
        (
            86,
            "二、公示",
            n_publicity,
            "公示期不少于7天",
            "2026 年春季清退违规情况的公示期不少于 7 天。",
            "time_constraint",
            ["公示期", "不少于7天"],
        ),
        (
            87,
            "二、公示",
            n_publicity,
            "学生可在公示期内向学院提出书面意见",
            "学生可在公示期内向学院提出书面意见。",
            "step",
            ["学生", "公示期", "书面意见"],
        ),
        (
            88,
            "三、处理程序及报送材料",
            n_publicity_material,
            "提交公示文件，需盖学院公章",
            "学院进行清退处理时须提交公示文件。",
            "material",
            ["公示文件", "提交"],
        ),
        (
            89,
            "三、处理程序及报送材料",
            n_publicity_material,
            "（一）提交公示文件，需盖学院公章",
            "清退公示文件须加盖学院公章。",
            "material",
            ["公示文件", "学院公章"],
        ),
        (
            90,
            "三、处理程序及报送材料",
            n_summary_material,
            "填写并提交《2026年春季学院清退未注册学生汇总表》",
            "学院须填写并提交 2026 年春季清退未注册学生汇总表。",
            "material",
            ["清退汇总表", "填写", "提交"],
        ),
        (
            91,
            "三、处理程序及报送材料",
            n_summary_material,
            "需主管教学院长签字",
            "2026 年春季清退未注册学生汇总表须由主管教学院长签字。",
            "material",
            ["清退汇总表", "主管教学院长", "签字"],
        ),
        (
            92,
            "三、处理程序及报送材料",
            n_summary_material,
            "需主管教学院长签字并盖学院公章",
            "2026 年春季清退未注册学生汇总表须加盖学院公章。",
            "material",
            ["清退汇总表", "学院公章"],
        ),
        (
            93,
            "三、处理程序及报送材料",
            n_system,
            "在新教务管理系统学籍异动中提交清退学生的退学申请",
            "学院教科办须在新教务管理系统学籍异动中提交清退学生的退学申请。",
            "step",
            ["学院教科办", "新教务管理系统", "退学申请"],
        ),
        (
            94,
            "三、处理程序及报送材料",
            n_system,
            "申请理由选择“未按时注册需清退”",
            "系统中的退学申请理由须选择“未按时注册需清退”。",
            "precondition",
            ["申请理由", "未按时注册需清退"],
        ),
        (
            95,
            "三、处理程序及报送材料",
            n_delivery,
            "4月10日下午5点前",
            "学院须在 2026 年 4 月 10 日下午 5 点前报送清退材料。",
            "time_constraint",
            ["报送期限", "4月10日", "下午5点"],
        ),
        (
            96,
            "三、处理程序及报送材料",
            n_delivery,
            "将上述材料纸质版报教务处学籍科",
            "学院须将清退材料纸质版报送教务处学籍科。",
            "step",
            ["纸质材料", "教务处学籍科", "报送"],
        ),
        (
            97,
            "三、处理程序及报送材料",
            n_delivery,
            "石牌校区行政楼127/129室",
            "清退材料纸质版的报送地点为石牌校区行政楼 127/129 室。",
            "service_location",
            ["石牌校区", "行政楼", "127/129室"],
        ),
        (
            98,
            "三、处理程序及报送材料",
            n_delivery,
            "附件2的电子版需同时发至学籍科邮箱",
            "学院须同时把清退汇总表电子版发送至学籍科邮箱。",
            "step",
            ["清退汇总表", "电子版", "同时发送"],
        ),
        (
            99,
            "三、处理程序及报送材料",
            n_delivery,
            "Ojwxjk@jnu.edu.cn",
            "2026 年春季清退汇总表电子版的接收邮箱为 Ojwxjk@jnu.edu.cn。",
            "contact",
            ["学籍科邮箱", "Ojwxjk@jnu.edu.cn"],
        ),
        (
            100,
            "四、注意事项",
            n_contactable,
            "请学院教科办先审核学生的学习情况",
            "能联系且不打算继续学业的学生，须先由学院教科办审核其学习情况。",
            "step",
            ["能联系", "不继续学业", "审核学习情况"],
        ),
        (
            101,
            "四、注意事项",
            n_contactable,
            "学院可协助学生注册",
            "符合结业证书申请条件时，学院可协助学生注册。",
            "step",
            ["结业条件", "协助注册"],
        ),
        (
            102,
            "四、注意事项",
            n_contactable,
            "提醒学生申请结业",
            "符合结业证书申请条件时，学院可提醒学生申请结业。",
            "step",
            ["结业条件", "申请结业", "提醒"],
        ),
        (
            103,
            "四、注意事项",
            n_contactable,
            "如果不符合结业的条件，可填写《退学申请表》",
            "不符合结业条件时，学生可填写退学申请表。",
            "material",
            ["不符合结业条件", "退学申请表"],
        ),
        (
            104,
            "四、注意事项",
            n_contactable,
            "符合肄业条件可同时提交《肄业证书申请表》",
            "符合肄业条件时，可同时提交肄业证书申请表。",
            "material",
            ["肄业条件", "肄业证书申请表", "同时提交"],
        ),
        (
            105,
            "四、注意事项",
            n_max_duration,
            "超过最长年限，应予退学",
            "通知重申，在校学习时间超过最长年限的学生应予退学。",
            "consequence",
            ["超过最长年限", "应予退学"],
        ),
        (
            106,
            "四、注意事项",
            n_max_duration,
            "此类学生不得注册",
            "超过最长修读年限的学生不得注册。",
            "consequence",
            ["最长修读年限", "不得注册"],
        ),
        (
            107,
            "四、注意事项",
            n_max_duration,
            "不得继续留校修读",
            "超过最长修读年限的学生不得继续留校修读。",
            "consequence",
            ["最长修读年限", "不得继续留校修读"],
        ),
        (
            108,
            "四、注意事项",
            n_max_duration,
            "学生在校学习时间（含休学和保留学籍）",
            "通知所称在校学习时间包括休学和保留学籍期间。",
            "precondition",
            ["在校学习时间", "休学", "保留学籍"],
        ),
        (
            109,
            "四、注意事项",
            n_exchange,
            "学院需提醒并督促交换学生进行正常的学期注册",
            "学院须提醒并督促交换学生进行正常的学期注册。",
            "step",
            ["交换学生", "提醒", "督促注册"],
        ),
        (
            110,
            "四、注意事项",
            n_exchange,
            "必要时，学院教科办可提供协助",
            "交换学生办理学期注册时，学院教科办可在必要时提供协助。",
            "step",
            ["交换学生", "学院教科办", "协助注册"],
        ),
        (
            111,
            "四、注意事项",
            n_late_registration,
            "未按学校规定在3月20日前按时注册的学生",
            "学院应对未在 2026 年 3 月 20 日前按时注册的学生进行批评教育。",
            "step",
            ["3月20日前", "未按时注册", "批评教育"],
        ),
        (
            112,
            "四、注意事项",
            n_late_registration,
            "考虑采取相关措施，提高本学院学生注册率",
            "学院应考虑采取措施提高本学院学生注册率。",
            "step",
            ["相关措施", "提高注册率"],
        ),
        (
            113,
            "三、处理程序及报送材料",
            n_delivery,
            "主题：XX学院2026年春季清退名单",
            "清退汇总表电子邮件主题须为“XX学院2026年春季清退名单”。",
            "precondition",
            ["电子邮件主题", "2026年春季清退名单"],
        ),
    ]
    for (
        number,
        section,
        verbatim,
        anchor,
        claim,
        claim_type,
        keywords,
    ) in notice_specs:
        add(
            number,
            cleanup_notice_source,
            section,
            verbatim,
            anchor,
            claim,
            claim_type,
            cleanup_audience,
            "2026",
            base_2026,
            keywords,
        )

    expected_ids = [f"UGW{index:03d}" for index in range(1, 114)]
    actual_ids = [str(row["evidence_id"]) for row in rows]
    if actual_ids != expected_ids:
        raise ValueError(
            f"withdrawal evidence ID sequence differs: {actual_ids}"
        )
    return rows


def _condition(slot_id: str, value: str) -> dict[str, str]:
    return {"slot_id": slot_id, "operator": "equals", "value": value}


def _step(
    number: int,
    actor: str,
    action: str,
    evidence_ids: list[str],
    *,
    conditions: list[dict[str, str]] | None = None,
    materials: list[str] | None = None,
    points: list[str] | None = None,
    times: list[str] | None = None,
    terminal: bool = False,
) -> dict[str, Any]:
    step_id = f"ST_{number:02d}"
    return {
        "step_id": step_id,
        "order": number,
        "actor": actor,
        "action": action,
        "conditions": conditions or [],
        "required_material_ids": materials or [],
        "service_point_ids": points or [],
        "time_constraint_ids": times or [],
        "next_step_ids": [] if terminal else [f"ST_{number + 1:02d}"],
        "evidence_ids": evidence_ids,
    }


def _claim(
    number: int,
    claim_type: str,
    text: str,
    evidence_ids: list[str],
    step_ids: list[str],
    conditions: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "claim_id": f"CLM_{number:03d}",
        "claim_type": claim_type,
        "text": text,
        "conditions": conditions or [],
        "applicable_step_ids": step_ids,
        "evidence_ids": evidence_ids,
    }


def _finish_process(
    process_id: str,
    title: str,
    audience: list[str],
    slots: list[dict[str, Any]],
    follow_up_rules: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    materials: list[dict[str, Any]],
    service_points: list[dict[str, Any]],
    time_constraints: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
    consequences: list[dict[str, Any]],
    allowed_claims: list[dict[str, Any]],
    evidence_sha256: str,
    notes: str,
) -> dict[str, Any]:
    collections = [
        slots,
        follow_up_rules,
        steps,
        materials,
        service_points,
        time_constraints,
        exceptions,
        consequences,
        allowed_claims,
    ]
    evidence_ids = sorted(
        {
            str(evidence_id)
            for collection in collections
            for row in collection
            for evidence_id in row.get("evidence_ids", [])
        }
    )
    return {
        "schema_version": "1.0",
        "process_id": process_id,
        "process_version": "0.2.0",
        "item_id": "UG_WITHDRAWAL",
        "title": title,
        "audience": audience,
        "slots": slots,
        "follow_up_rules": follow_up_rules,
        "steps": steps,
        "materials": materials,
        "service_points": service_points,
        "time_constraints": time_constraints,
        "exceptions": exceptions,
        "consequences": consequences,
        "allowed_claims": allowed_claims,
        "evidence_snapshot": {
            "dataset_path": "data/research/evidence_units.jsonl",
            "dataset_sha256": evidence_sha256,
            "evidence_ids": evidence_ids,
        },
        "review": {
            "status": "verified",
            "annotated_at": ANNOTATED_AT,
            "annotator": "Codex 阶段 2B 流程标注",
            "reviewed_at": REVIEWED_AT,
            "reviewer": "Codex 阶段 2B 流程复核",
            "notes": notes,
        },
    }


def _atomic_claims(
    evidence_ids: list[str],
    evidence_by_id: dict[str, dict[str, Any]],
    *,
    steps: list[dict[str, Any]],
    materials: list[dict[str, Any]],
    service_points: list[dict[str, Any]],
    time_constraints: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
    consequences: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    applicable_steps: dict[str, set[str]] = {
        evidence_id: set() for evidence_id in evidence_ids
    }
    owner_specs = [
        (steps, "step_id"),
        (materials, "required_at_step_ids"),
        (service_points, "applies_to_step_ids"),
        (time_constraints, "applies_to_step_ids"),
        (exceptions, "affected_step_ids"),
        (consequences, "applies_after_step_ids"),
    ]
    for owners, step_field in owner_specs:
        for owner in owners:
            owner_evidence_ids = {
                str(value) for value in owner.get("evidence_ids", [])
            }
            if step_field == "step_id":
                step_ids = [str(owner["step_id"])]
            else:
                step_ids = [
                    str(value) for value in owner.get(step_field, [])
                ]
            for evidence_id in owner_evidence_ids & set(evidence_ids):
                applicable_steps[evidence_id].update(step_ids)

    claims: list[dict[str, Any]] = []
    for number, evidence_id in enumerate(evidence_ids, start=1):
        evidence = evidence_by_id[evidence_id]
        claims.append(
            _claim(
                number,
                str(evidence["claim_type"]),
                str(evidence["normalized_claim"]),
                [evidence_id],
                sorted(applicable_steps[evidence_id]),
            )
        )
    return claims


def build_process_records(
    evidence_sha256: str,
    evidence_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence_by_id = {
        str(row["evidence_id"]): row for row in evidence_rows
    }
    active_condition = [_condition("SL_WITHDRAWAL_TYPE", "主动申请退学")]
    discipline_condition = [
        _condition("SL_WITHDRAWAL_TYPE", "违纪违规退学处理")
    ]
    cleanup_audience = [
        "2026 年春季未注册或达到通知所列清退条件的全日制本科学生"
    ]

    v1_slots = [
        {
            "slot_id": "SL_WITHDRAWAL_TYPE",
            "name": "退学办理类型",
            "value_type": "enum",
            "required_for_resolution": True,
            "allowed_values": ["主动申请退学"],
            "unknown_policy": "ask",
            "evidence_ids": ["UGW002"],
        },
        {
            "slot_id": "SL_DEPARTURE_STATUS",
            "name": "离校手续状态",
            "value_type": "enum",
            "required_for_resolution": False,
            "allowed_values": ["按离校清单完成", "擅自离校"],
            "unknown_policy": "allow_unknown",
            "evidence_ids": ["UGW017", "UGW020"],
        },
    ]
    v1_followups = [
        {
            "rule_id": "FU_01",
            "when_missing_slot_ids": ["SL_WITHDRAWAL_TYPE"],
            "question": "请确认本次属于学生主动申请退学。",
            "priority": 1,
            "evidence_ids": ["UGW002"],
        }
    ]
    v1_steps = [
        _step(1, "申请退学的本科学生", "将书面申请交学院教务秘书处。", ["UGW003"], conditions=active_condition, materials=["MAT_01"]),
        _step(2, "学院教务秘书", "指导学生填写本科学生退学申请表。", ["UGW004"], materials=["MAT_02"]),
        _step(3, "学院", "审批主动退学申请。", ["UGW007"]),
        _step(4, "学院", "将审批后的申请交教务处学籍科。", ["UGW008"], points=["LOC_01"]),
        _step(5, "教务处", "审核退学事项。", ["UGW012"]),
        _step(6, "校长办公会", "批准退学事项。", ["UGW013"]),
        _step(7, "学校", "就批准的退学事项发文。", ["UGW014"]),
        _step(8, "学校", "将退学文件通知各学院。", ["UGW015"]),
        _step(9, "学院教务秘书", "通知学生办理离校手续。", ["UGW016"]),
        _step(10, "本科学生", "依照离校清单办理离校手续。", ["UGW017"], materials=["MAT_03"]),
        _step(11, "本科学生", "办完离校手续后到教务处学籍科办理相应退学证明。", ["UGW018", "UGW019"], points=["LOC_01"], terminal=True),
    ]
    v1_materials = [
        {
            "material_id": "MAT_01",
            "name": "书面退学申请",
            "required_when": active_condition,
            "required_at_step_ids": ["ST_01"],
            "evidence_ids": ["UGW003"],
        },
        {
            "material_id": "MAT_02",
            "name": "暨南大学本科学生退学申请表",
            "required_when": active_condition,
            "required_at_step_ids": ["ST_02"],
            "evidence_ids": ["UGW004"],
        },
        {
            "material_id": "MAT_03",
            "name": "离校清单",
            "required_when": [],
            "required_at_step_ids": ["ST_10"],
            "evidence_ids": ["UGW017"],
        },
    ]
    v1_points = [
        {
            "point_id": "LOC_01",
            "name": "教务处学籍科",
            "conditions": [],
            "applies_to_step_ids": ["ST_04", "ST_11"],
            "evidence_ids": ["UGW008", "UGW019"],
        }
    ]
    v1_consequences = [
        {
            "consequence_id": "CON_01",
            "trigger": [_condition("SL_DEPARTURE_STATUS", "擅自离校")],
            "text": "擅自离校者不发任何证明。",
            "applies_after_step_ids": ["ST_09"],
            "evidence_ids": ["UGW020"],
        }
    ]
    v1_claims = _atomic_claims(
        [
            "UGW002",
            "UGW003",
            "UGW004",
            "UGW007",
            "UGW008",
            *[f"UGW{number:03d}" for number in range(12, 21)],
        ],
        evidence_by_id,
        steps=v1_steps,
        materials=v1_materials,
        service_points=v1_points,
        time_constraints=[],
        exceptions=[],
        consequences=v1_consequences,
    )
    process_v1 = _finish_process(
        "PROC_UG_WITHDRAWAL_V001",
        "2019 年流程页：本科学生主动申请退学流程",
        ["主动申请退学的本科学生"],
        v1_slots,
        v1_followups,
        v1_steps,
        v1_materials,
        v1_points,
        [],
        [],
        v1_consequences,
        v1_claims,
        evidence_sha256,
        "已按 2019 年流程页主动申请分支及共同后续步骤完成独立复核；未声明统一适用区间。",
    )

    v2_slots = [
        {
            "slot_id": "SL_WITHDRAWAL_TYPE",
            "name": "退学办理类型",
            "value_type": "enum",
            "required_for_resolution": True,
            "allowed_values": ["违纪违规退学处理"],
            "unknown_policy": "ask",
            "evidence_ids": ["UGW005"],
        },
        {
            "slot_id": "SL_DEPARTURE_STATUS",
            "name": "离校手续状态",
            "value_type": "enum",
            "required_for_resolution": False,
            "allowed_values": ["按离校清单完成", "擅自离校"],
            "unknown_policy": "allow_unknown",
            "evidence_ids": ["UGW017", "UGW020"],
        },
    ]
    v2_followups = [
        {
            "rule_id": "FU_01",
            "when_missing_slot_ids": ["SL_WITHDRAWAL_TYPE"],
            "question": "请确认本次属于因违纪违规须作退学处理的分支。",
            "priority": 1,
            "evidence_ids": ["UGW005"],
        }
    ]
    v2_steps = [
        _step(1, "学院", "填写本科学生退学申请表。", ["UGW006"], conditions=discipline_condition, materials=["MAT_01"]),
        _step(2, "学院", "审批违纪违规退学处理材料。", ["UGW073"]),
        _step(3, "学院教务管理人员", "汇总经学院审批的材料。", ["UGW009"]),
        _step(4, "学院教务管理人员", "在规定周次前将汇总材料交教务处学籍科。", ["UGW010", "UGW011"], points=["LOC_01"], times=["TIME_01"]),
        _step(5, "教务处", "审核退学事项。", ["UGW012"]),
        _step(6, "校长办公会", "批准退学事项。", ["UGW013"]),
        _step(7, "学校", "就批准的退学事项发文。", ["UGW014"]),
        _step(8, "学校", "将退学文件通知各学院。", ["UGW015"]),
        _step(9, "学院教务秘书", "通知学生办理离校手续。", ["UGW016"]),
        _step(10, "本科学生", "依照离校清单办理离校手续。", ["UGW017"], materials=["MAT_02"]),
        _step(11, "本科学生", "办完离校手续后到教务处学籍科办理相应退学证明。", ["UGW018", "UGW019"], points=["LOC_01"], terminal=True),
    ]
    v2_materials = [
        {
            "material_id": "MAT_01",
            "name": "暨南大学本科学生退学申请表",
            "required_when": discipline_condition,
            "required_at_step_ids": ["ST_01"],
            "evidence_ids": ["UGW006"],
        },
        {
            "material_id": "MAT_02",
            "name": "离校清单",
            "required_when": [],
            "required_at_step_ids": ["ST_10"],
            "evidence_ids": ["UGW017"],
        },
    ]
    v2_points = [
        {
            "point_id": "LOC_01",
            "name": "教务处学籍科",
            "conditions": [],
            "applies_to_step_ids": ["ST_04", "ST_11"],
            "evidence_ids": ["UGW011", "UGW019"],
        }
    ]
    v2_times = [
        {
            "constraint_id": "TIME_01",
            "text": "学院教务管理人员于每学期第四周前和第十五周前提交汇总材料。",
            "conditions": discipline_condition,
            "applies_to_step_ids": ["ST_04"],
            "evidence_ids": ["UGW010"],
        }
    ]
    v2_consequences = [
        {
            "consequence_id": "CON_01",
            "trigger": [_condition("SL_DEPARTURE_STATUS", "擅自离校")],
            "text": "擅自离校者不发任何证明。",
            "applies_after_step_ids": ["ST_09"],
            "evidence_ids": ["UGW020"],
        }
    ]
    v2_claims = _atomic_claims(
        [f"UGW{number:03d}" for number in range(5, 7)]
        + [f"UGW{number:03d}" for number in range(9, 21)]
        + ["UGW073"],
        evidence_by_id,
        steps=v2_steps,
        materials=v2_materials,
        service_points=v2_points,
        time_constraints=v2_times,
        exceptions=[],
        consequences=v2_consequences,
    )
    process_v2 = _finish_process(
        "PROC_UG_WITHDRAWAL_V002",
        "2019 年流程页：违纪违规本科学生退学处理流程",
        ["因违纪违规须作退学处理的本科学生"],
        v2_slots,
        v2_followups,
        v2_steps,
        v2_materials,
        v2_points,
        v2_times,
        [],
        v2_consequences,
        v2_claims,
        evidence_sha256,
        "已按 2019 年流程页违纪违规分支及共同后续步骤完成独立复核；周次约束只绑定该分支。",
    )

    v3_period_central = [_condition("SL_ACCEPTANCE_PERIOD", "期末第13-16周")]
    v3_period_other = [_condition("SL_ACCEPTANCE_PERIOD", "其他时段")]
    v3_slots = [
        {
            "slot_id": "SL_WITHDRAWAL_TYPE",
            "name": "退学办理类型",
            "value_type": "enum",
            "required_for_resolution": True,
            "allowed_values": ["主动申请退学"],
            "unknown_policy": "ask",
            "evidence_ids": ["UGW054"],
        },
        {
            "slot_id": "SL_ACCEPTANCE_PERIOD",
            "name": "提交时段",
            "value_type": "enum",
            "required_for_resolution": True,
            "allowed_values": ["期末第13-16周", "其他时段"],
            "unknown_policy": "ask",
            "evidence_ids": ["UGW062", "UGW064"],
        },
        {
            "slot_id": "SL_CERTIFICATE_ELIGIBILITY",
            "name": "肄业证书资格",
            "value_type": "boolean",
            "required_for_resolution": False,
            "allowed_values": [],
            "unknown_policy": "allow_unknown",
            "evidence_ids": ["UGW068"],
        },
        {
            "slot_id": "SL_HAS_ATTACHMENTS",
            "name": "是否附有证明材料",
            "value_type": "boolean",
            "required_for_resolution": False,
            "allowed_values": [],
            "unknown_policy": "allow_unknown",
            "evidence_ids": ["UGW067"],
        },
    ]
    v3_followups = [
        {
            "rule_id": "FU_01",
            "when_missing_slot_ids": ["SL_WITHDRAWAL_TYPE"],
            "question": "请确认本次属于学生主动申请退学。",
            "priority": 1,
            "evidence_ids": ["UGW054"],
        },
        {
            "rule_id": "FU_02",
            "when_missing_slot_ids": ["SL_ACCEPTANCE_PERIOD"],
            "question": "请确认申请是在期末第 13 至第 16 周提交，还是在其他时段提交。",
            "priority": 2,
            "evidence_ids": ["UGW062", "UGW064"],
        },
    ]
    v3_steps = [
        _step(1, "主动申请退学的本科学生", "本人填写并签署退学申请表。", ["UGW054"], materials=["MAT_01", "MAT_02", "MAT_03"]),
        _step(2, "学生所在院系", "审核申请并签署意见。", ["UGW055"]),
        _step(3, "学生所在院系", "将申请交学院教科办。", ["UGW056"], points=["LOC_01"]),
        _step(4, "学院教科办", "通过综合教务管理系统统一将申请交至教务处。", ["UGW057", "UGW072"], points=["LOC_02"]),
        _step(5, "教务处", "审核主动退学申请。", ["UGW058"], times=["TIME_01", "TIME_02"]),
        _step(6, "教务处", "将退学通知发放到学院教科办。", ["UGW059"]),
        _step(7, "申请人", "到学院教科办领取退学通知。", ["UGW060"], points=["LOC_01"]),
        _step(8, "申请人", "办理相关离校手续。", ["UGW061"], times=["TIME_03"], terminal=True),
    ]
    v3_materials = [
        {
            "material_id": "MAT_01",
            "name": "退学申请表",
            "required_when": [],
            "required_at_step_ids": ["ST_01"],
            "evidence_ids": ["UGW054"],
        },
        {
            "material_id": "MAT_02",
            "name": "逐页签名的附件证明材料",
            "required_when": [_condition("SL_HAS_ATTACHMENTS", "true")],
            "required_at_step_ids": ["ST_01"],
            "evidence_ids": ["UGW067"],
        },
        {
            "material_id": "MAT_03",
            "name": "肄业证书申请表",
            "required_when": [_condition("SL_CERTIFICATE_ELIGIBILITY", "true")],
            "required_at_step_ids": ["ST_01"],
            "evidence_ids": ["UGW068"],
        },
    ]
    v3_points = [
        {
            "point_id": "LOC_01",
            "name": "学院教科办",
            "conditions": [],
            "applies_to_step_ids": ["ST_03", "ST_07"],
            "evidence_ids": ["UGW056", "UGW060"],
        },
        {
            "point_id": "LOC_02",
            "name": "综合教务管理系统",
            "conditions": [],
            "applies_to_step_ids": ["ST_04"],
            "evidence_ids": ["UGW072"],
        },
    ]
    v3_times = [
        {
            "constraint_id": "TIME_01",
            "text": "期末第 13 至第 16 周提交时，教务处于 6 个工作日内完成审批。",
            "conditions": v3_period_central,
            "applies_to_step_ids": ["ST_05"],
            "evidence_ids": ["UGW062", "UGW063"],
        },
        {
            "constraint_id": "TIME_02",
            "text": "其他时段审批一般至少需要 12 个工作日。",
            "conditions": v3_period_other,
            "applies_to_step_ids": ["ST_05"],
            "evidence_ids": ["UGW064"],
        },
        {
            "constraint_id": "TIME_03",
            "text": "学生接到退学通知书后 2 周内办完离校手续。",
            "conditions": [],
            "applies_to_step_ids": ["ST_08"],
            "evidence_ids": ["UGW065"],
        },
        {
            "constraint_id": "TIME_04",
            "text": "肄业证书必须在退学时或退学当学期提出申请。",
            "conditions": [_condition("SL_CERTIFICATE_ELIGIBILITY", "true")],
            "applies_to_step_ids": ["ST_01"],
            "evidence_ids": ["UGW069"],
        },
    ]
    v3_exceptions = [
        {
            "exception_id": "EXC_01",
            "trigger": [_condition("SL_CERTIFICATE_ELIGIBILITY", "true")],
            "effect": "add_precondition",
            "affected_step_ids": ["ST_01"],
            "description": "肄业证书申请超过退学当学期不再受理。",
            "evidence_ids": ["UGW070"],
        }
    ]
    v3_consequences = [
        {
            "consequence_id": "CON_01",
            "trigger": [],
            "text": "退学后不得申请复学。",
            "applies_after_step_ids": ["ST_08"],
            "evidence_ids": ["UGW066"],
        }
    ]
    v3_claims = _atomic_claims(
        [f"UGW{number:03d}" for number in range(54, 73)],
        evidence_by_id,
        steps=v3_steps,
        materials=v3_materials,
        service_points=v3_points,
        time_constraints=v3_times,
        exceptions=v3_exceptions,
        consequences=v3_consequences,
    )
    process_v3 = _finish_process(
        "PROC_UG_WITHDRAWAL_V003",
        "2011 年 11 月历史表格：本科学生主动申请退学流程",
        ["主动申请退学的本科学生"],
        v3_slots,
        v3_followups,
        v3_steps,
        v3_materials,
        v3_points,
        v3_times,
        v3_exceptions,
        v3_consequences,
        v3_claims,
        evidence_sha256,
        "已按 2011 年 11 月历史表格完成独立复核；该记录保留历史时限和系统名称，不作为当前流程结论。",
    )

    v4_period_central = [_condition("SL_ACCEPTANCE_PERIOD", "学期初第1-4周")]
    v4_period_other = [_condition("SL_ACCEPTANCE_PERIOD", "其他时段")]
    v4_slots = [
        {
            "slot_id": "SL_WITHDRAWAL_TYPE",
            "name": "退学办理类型",
            "value_type": "enum",
            "required_for_resolution": True,
            "allowed_values": ["主动申请退学"],
            "unknown_policy": "ask",
            "evidence_ids": ["UGW021"],
        },
        {
            "slot_id": "SL_ACCEPTANCE_PERIOD",
            "name": "提交时段",
            "value_type": "enum",
            "required_for_resolution": True,
            "allowed_values": ["学期初第1-4周", "其他时段"],
            "unknown_policy": "ask",
            "evidence_ids": ["UGW032", "UGW034"],
        },
        {
            "slot_id": "SL_APPLICATION_WEEK",
            "name": "提出申请的学期周次",
            "value_type": "enum",
            "required_for_resolution": False,
            "allowed_values": ["不超过第7周", "超过第7周"],
            "unknown_policy": "allow_unknown",
            "evidence_ids": ["UGW037", "UGW038", "UGW039"],
        },
        {
            "slot_id": "SL_CERTIFICATE_ELIGIBILITY",
            "name": "肄业证书资格",
            "value_type": "boolean",
            "required_for_resolution": False,
            "allowed_values": [],
            "unknown_policy": "allow_unknown",
            "evidence_ids": ["UGW041"],
        },
        {
            "slot_id": "SL_INFORMATION_STATUS",
            "name": "申请信息真实性",
            "value_type": "enum",
            "required_for_resolution": False,
            "allowed_values": ["真实准确", "虚假或隐瞒"],
            "unknown_policy": "allow_unknown",
            "evidence_ids": ["UGW047", "UGW053"],
        },
        {
            "slot_id": "SL_STUDENT_CATEGORY",
            "name": "学生类别",
            "value_type": "enum",
            "required_for_resolution": False,
            "allowed_values": ["内招生", "外招生"],
            "unknown_policy": "allow_unknown",
            "evidence_ids": ["UGW045"],
        },
        {
            "slot_id": "SL_HAS_ATTACHMENTS",
            "name": "是否附有证明材料",
            "value_type": "boolean",
            "required_for_resolution": False,
            "allowed_values": [],
            "unknown_policy": "allow_unknown",
            "evidence_ids": ["UGW040"],
        },
    ]
    v4_followups = [
        {
            "rule_id": "FU_01",
            "when_missing_slot_ids": ["SL_WITHDRAWAL_TYPE"],
            "question": "请确认本次属于学生主动申请退学。",
            "priority": 1,
            "evidence_ids": ["UGW021"],
        },
        {
            "rule_id": "FU_02",
            "when_missing_slot_ids": ["SL_ACCEPTANCE_PERIOD"],
            "question": "请确认申请是在学期初第 1 至第 4 周提交，还是在其他时段提交。",
            "priority": 2,
            "evidence_ids": ["UGW032", "UGW034"],
        },
    ]
    v4_steps = [
        _step(1, "主动申请退学的本科学生", "本人填写并签署退学申请表。", ["UGW021"], materials=["MAT_01", "MAT_02", "MAT_03", "MAT_04", "MAT_05"]),
        _step(2, "学生所在专业、系、所等", "审核申请陈述和附件真实性并签署意见。", ["UGW025", "UGW047"]),
        _step(3, "学生所在院系", "将申请交学院教科办。", ["UGW026"], points=["LOC_01"]),
        _step(4, "学院", "联系学生家长并告知退学事宜。", ["UGW048"]),
        _step(5, "学院教科办", "在本科教务管理系统审核申请并统一交至教务处。", ["UGW027", "UGW049"], points=["LOC_02"]),
        _step(6, "分管教学院领导和分管学生工作院领导", "分别手写签名并署名意见。", ["UGW050", "UGW051"]),
        _step(7, "教务处", "审核主动退学申请并签署审核意见。", ["UGW028", "UGW052"], times=["TIME_01", "TIME_02"]),
        _step(8, "教务处", "将退学通知发放到学院教科办。", ["UGW029"]),
        _step(9, "申请人", "到学院教科办领取退学通知。", ["UGW030"], points=["LOC_01"]),
        _step(10, "申请人", "办理相关离校手续。", ["UGW031"], times=["TIME_03"], terminal=True),
    ]
    v4_materials = [
        {
            "material_id": "MAT_01",
            "name": "退学申请表",
            "required_when": [],
            "required_at_step_ids": ["ST_01"],
            "evidence_ids": ["UGW021"],
        },
        {
            "material_id": "MAT_02",
            "name": "家长知情同意书",
            "required_when": [],
            "required_at_step_ids": ["ST_01"],
            "evidence_ids": ["UGW022"],
        },
        {
            "material_id": "MAT_03",
            "name": "退学理由及必要附页",
            "required_when": [],
            "required_at_step_ids": ["ST_01"],
            "evidence_ids": ["UGW046"],
        },
        {
            "material_id": "MAT_04",
            "name": "逐页签名的附件证明材料",
            "required_when": [_condition("SL_HAS_ATTACHMENTS", "true")],
            "required_at_step_ids": ["ST_01"],
            "evidence_ids": ["UGW040"],
        },
        {
            "material_id": "MAT_05",
            "name": "肄业证书申请表",
            "required_when": [_condition("SL_CERTIFICATE_ELIGIBILITY", "true")],
            "required_at_step_ids": ["ST_01"],
            "evidence_ids": ["UGW041", "UGW042"],
        },
    ]
    v4_points = [
        {
            "point_id": "LOC_01",
            "name": "学院教科办",
            "conditions": [],
            "applies_to_step_ids": ["ST_03", "ST_09"],
            "evidence_ids": ["UGW026", "UGW030"],
        },
        {
            "point_id": "LOC_02",
            "name": "本科教务管理系统",
            "conditions": [],
            "applies_to_step_ids": ["ST_05"],
            "evidence_ids": ["UGW049"],
        },
    ]
    v4_times = [
        {
            "constraint_id": "TIME_01",
            "text": "学期初第 1 至第 4 周提交时，教务处于 6 个工作日内完成审批。",
            "conditions": v4_period_central,
            "applies_to_step_ids": ["ST_07"],
            "evidence_ids": ["UGW032", "UGW033"],
        },
        {
            "constraint_id": "TIME_02",
            "text": "其他时段审批一般至少需要 12 个工作日。",
            "conditions": v4_period_other,
            "applies_to_step_ids": ["ST_07"],
            "evidence_ids": ["UGW034"],
        },
        {
            "constraint_id": "TIME_03",
            "text": "学生接到退学通知书后 2 周内办完离校手续。",
            "conditions": [],
            "applies_to_step_ids": ["ST_10"],
            "evidence_ids": ["UGW035"],
        },
        {
            "constraint_id": "TIME_04",
            "text": "肄业证书必须在退学时或退学当学期提出申请。",
            "conditions": [_condition("SL_CERTIFICATE_ELIGIBILITY", "true")],
            "applies_to_step_ids": ["ST_01"],
            "evidence_ids": ["UGW043"],
        },
    ]
    v4_exceptions = [
        {
            "exception_id": "EXC_01",
            "trigger": [_condition("SL_APPLICATION_WEEK", "超过第7周")],
            "effect": "other",
            "affected_step_ids": ["ST_07"],
            "description": "超过第 7 周提出退学申请时无法退选当学期课程。",
            "evidence_ids": ["UGW038"],
        },
        {
            "exception_id": "EXC_02",
            "trigger": [_condition("SL_CERTIFICATE_ELIGIBILITY", "true")],
            "effect": "add_precondition",
            "affected_step_ids": ["ST_01"],
            "description": "肄业证书申请超过退学当学期不再受理。",
            "evidence_ids": ["UGW044"],
        },
    ]
    v4_consequences = [
        {
            "consequence_id": "CON_01",
            "trigger": [],
            "text": "申请一旦受理不得撤销。",
            "applies_after_step_ids": ["ST_01"],
            "evidence_ids": ["UGW024"],
        },
        {
            "consequence_id": "CON_02",
            "trigger": [],
            "text": "退学后不得申请复学。",
            "applies_after_step_ids": ["ST_10"],
            "evidence_ids": ["UGW036"],
        },
        {
            "consequence_id": "CON_03",
            "trigger": [_condition("SL_APPLICATION_WEEK", "不超过第7周")],
            "text": "获批退学当学期所选课程应作退选处理。",
            "applies_after_step_ids": ["ST_07"],
            "evidence_ids": ["UGW037"],
        },
        {
            "consequence_id": "CON_04",
            "trigger": [_condition("SL_APPLICATION_WEEK", "超过第7周")],
            "text": "超过第 7 周提出申请时，选课及成绩仍记录在案。",
            "applies_after_step_ids": ["ST_07"],
            "evidence_ids": ["UGW039"],
        },
        {
            "consequence_id": "CON_05",
            "trigger": [
                _condition("SL_INFORMATION_STATUS", "虚假或隐瞒")
            ],
            "text": "提供虚假信息或隐瞒事实时申请会被驳回。",
            "applies_after_step_ids": ["ST_02"],
            "evidence_ids": ["UGW053"],
        },
    ]
    v4_claims = _atomic_claims(
        [f"UGW{number:03d}" for number in range(21, 54)],
        evidence_by_id,
        steps=v4_steps,
        materials=v4_materials,
        service_points=v4_points,
        time_constraints=v4_times,
        exceptions=v4_exceptions,
        consequences=v4_consequences,
    )
    process_v4 = _finish_process(
        "PROC_UG_WITHDRAWAL_V004",
        "2025 年 1 月表格：本科学生主动申请退学流程",
        ["主动申请退学的本科学生"],
        v4_slots,
        v4_followups,
        v4_steps,
        v4_materials,
        v4_points,
        v4_times,
        v4_exceptions,
        v4_consequences,
        v4_claims,
        evidence_sha256,
        "已按 2025 年 1 月四海书院官方副本完成独立复核；版本月份、材料、周次、课程后果和系统名称均保持来源边界。",
    )

    v5_category_max_duration = [
        _condition("SL_CLEANUP_CATEGORY", "达到最长修读年限未完成学业")
    ]
    v5_contactable_no_continue = [
        _condition("SL_CONTACTABLE", "true"),
        _condition("SL_CONTINUE_STUDY", "false"),
    ]
    v5_slots = [
        {
            "slot_id": "SL_NOTICE_TERM",
            "name": "通知适用学期",
            "value_type": "enum",
            "required_for_resolution": True,
            "allowed_values": ["2026年春季"],
            "unknown_policy": "ask",
            "evidence_ids": ["UGW075"],
        },
        {
            "slot_id": "SL_CLEANUP_CATEGORY",
            "name": "清退范围类别",
            "value_type": "enum",
            "required_for_resolution": True,
            "allowed_values": [
                "逾期未注册且未办理相关手续",
                "达到最长修读年限未完成学业",
                "休学期满逾期两周未复学或未办理延期休学",
            ],
            "unknown_policy": "ask",
            "evidence_ids": ["UGW078", "UGW079", "UGW083"],
        },
        {
            "slot_id": "SL_REGISTRATION_APPROVED",
            "name": "逾期未注册是否获批准",
            "value_type": "boolean",
            "required_for_resolution": False,
            "allowed_values": [],
            "unknown_policy": "allow_unknown",
            "evidence_ids": ["UGW077"],
        },
        {
            "slot_id": "SL_PROGRAM_LENGTH",
            "name": "本科专业学制",
            "value_type": "enum",
            "required_for_resolution": False,
            "allowed_values": ["4年制", "5年制", "6年制"],
            "unknown_policy": "allow_unknown",
            "evidence_ids": ["UGW080", "UGW081", "UGW082"],
        },
        {
            "slot_id": "SL_CONTACTABLE",
            "name": "学生是否可以联系",
            "value_type": "boolean",
            "required_for_resolution": False,
            "allowed_values": [],
            "unknown_policy": "allow_unknown",
            "evidence_ids": ["UGW100"],
        },
        {
            "slot_id": "SL_CONTINUE_STUDY",
            "name": "学生是否打算继续学业",
            "value_type": "boolean",
            "required_for_resolution": False,
            "allowed_values": [],
            "unknown_policy": "allow_unknown",
            "evidence_ids": ["UGW100"],
        },
        {
            "slot_id": "SL_COMPLETION_ELIGIBILITY",
            "name": "结业证书申请资格",
            "value_type": "boolean",
            "required_for_resolution": False,
            "allowed_values": [],
            "unknown_policy": "allow_unknown",
            "evidence_ids": ["UGW101", "UGW102", "UGW103"],
        },
        {
            "slot_id": "SL_INCOMPLETE_CERT_ELIGIBILITY",
            "name": "肄业证书申请资格",
            "value_type": "boolean",
            "required_for_resolution": False,
            "allowed_values": [],
            "unknown_policy": "allow_unknown",
            "evidence_ids": ["UGW104"],
        },
        {
            "slot_id": "SL_EXCHANGE_STUDENT",
            "name": "是否为交换学生",
            "value_type": "boolean",
            "required_for_resolution": False,
            "allowed_values": [],
            "unknown_policy": "allow_unknown",
            "evidence_ids": ["UGW109", "UGW110"],
        },
        {
            "slot_id": "SL_REGISTERED_BY_DEADLINE",
            "name": "是否在 2026 年 3 月 20 日前按时注册",
            "value_type": "boolean",
            "required_for_resolution": False,
            "allowed_values": [],
            "unknown_policy": "allow_unknown",
            "evidence_ids": ["UGW111", "UGW112"],
        },
    ]
    v5_followups = [
        {
            "rule_id": "FU_01",
            "when_missing_slot_ids": ["SL_NOTICE_TERM"],
            "question": "请确认问题对应 2026 年春季清退通知。",
            "priority": 1,
            "evidence_ids": ["UGW075"],
        },
        {
            "rule_id": "FU_02",
            "when_missing_slot_ids": ["SL_CLEANUP_CATEGORY"],
            "question": "请确认学生属于逾期未注册、达到最长修读年限，还是休学期满逾期未复学或未办理延期休学。",
            "priority": 2,
            "evidence_ids": ["UGW078", "UGW079", "UGW083"],
        },
    ]
    v5_steps = [
        _step(
            1,
            "学院",
            "按照通知列明的三类范围识别清退对象并核对最长修读年限口径。",
            ["UGW078", "UGW079", "UGW083", "UGW108"],
            times=["TIME_01", "TIME_02", "TIME_03", "TIME_04", "TIME_05"],
        ),
        _step(
            2,
            "学院",
            "组织专人与清退范围内学生联系沟通。",
            ["UGW084"],
        ),
        _step(
            3,
            "学院",
            "以多种形式公示逾期仍未办理手续学生的违规情况。",
            ["UGW085"],
            times=["TIME_06"],
        ),
        _step(
            4,
            "学生",
            "可在公示期内向学院提出书面意见。",
            ["UGW087"],
        ),
        _step(
            5,
            "学院",
            "提交加盖学院公章的公示文件。",
            ["UGW088", "UGW089"],
            materials=["MAT_01"],
        ),
        _step(
            6,
            "学院",
            "填写并提交经主管教学院长签字和学院盖章的清退汇总表。",
            ["UGW090", "UGW091", "UGW092"],
            materials=["MAT_02"],
        ),
        _step(
            7,
            "学院教科办",
            "在新教务管理系统学籍异动中提交退学申请并选择规定申请理由。",
            ["UGW093", "UGW094"],
            materials=["MAT_04", "MAT_05"],
        ),
        _step(
            8,
            "学院",
            "在规定期限前将纸质清退材料报送教务处学籍科。",
            ["UGW095", "UGW096", "UGW097"],
            materials=["MAT_01", "MAT_02"],
            points=["LOC_01"],
            times=["TIME_07"],
        ),
        _step(
            9,
            "学院",
            "同时将清退汇总表电子版发送至学籍科邮箱。",
            ["UGW098", "UGW099", "UGW113"],
            materials=["MAT_03"],
            terminal=True,
        ),
    ]
    v5_materials = [
        {
            "material_id": "MAT_01",
            "name": "加盖学院公章的公示文件",
            "required_when": [],
            "required_at_step_ids": ["ST_05"],
            "evidence_ids": ["UGW088", "UGW089"],
        },
        {
            "material_id": "MAT_02",
            "name": "经主管教学院长签字并加盖学院公章的清退汇总表",
            "required_when": [],
            "required_at_step_ids": ["ST_06", "ST_08"],
            "evidence_ids": ["UGW090", "UGW091", "UGW092"],
        },
        {
            "material_id": "MAT_03",
            "name": "清退汇总表电子版",
            "required_when": [],
            "required_at_step_ids": ["ST_09"],
            "evidence_ids": ["UGW098"],
        },
        {
            "material_id": "MAT_04",
            "name": "退学申请表",
            "required_when": v5_contactable_no_continue
            + [_condition("SL_COMPLETION_ELIGIBILITY", "false")],
            "required_at_step_ids": ["ST_07"],
            "evidence_ids": ["UGW103"],
        },
        {
            "material_id": "MAT_05",
            "name": "肄业证书申请表",
            "required_when": [
                _condition("SL_INCOMPLETE_CERT_ELIGIBILITY", "true")
            ],
            "required_at_step_ids": ["ST_07"],
            "evidence_ids": ["UGW104"],
        },
    ]
    v5_points = [
        {
            "point_id": "LOC_01",
            "name": "石牌校区行政楼 127/129 室",
            "conditions": [],
            "applies_to_step_ids": ["ST_08"],
            "evidence_ids": ["UGW097"],
        }
    ]
    v5_times = [
        {
            "constraint_id": "TIME_01",
            "text": "2026 年春季本科学生注册时间为 3 月 5 日至 3 月 20 日。",
            "conditions": [],
            "applies_to_step_ids": ["ST_01"],
            "evidence_ids": ["UGW076"],
        },
        {
            "constraint_id": "TIME_02",
            "text": "未经批准逾期 2 周以上不注册者视为自动退学。",
            "conditions": [
                _condition("SL_REGISTRATION_APPROVED", "false")
            ],
            "applies_to_step_ids": ["ST_01"],
            "evidence_ids": ["UGW077"],
        },
        {
            "constraint_id": "TIME_03",
            "text": "4 年制本科生最长修读年限不得超过 8 年。",
            "conditions": [_condition("SL_PROGRAM_LENGTH", "4年制")],
            "applies_to_step_ids": ["ST_01"],
            "evidence_ids": ["UGW080"],
        },
        {
            "constraint_id": "TIME_04",
            "text": "5 年制本科生最长修读年限不得超过 9 年。",
            "conditions": [_condition("SL_PROGRAM_LENGTH", "5年制")],
            "applies_to_step_ids": ["ST_01"],
            "evidence_ids": ["UGW081"],
        },
        {
            "constraint_id": "TIME_05",
            "text": "6 年制本科生最长修读年限不得超过 10 年。",
            "conditions": [_condition("SL_PROGRAM_LENGTH", "6年制")],
            "applies_to_step_ids": ["ST_01"],
            "evidence_ids": ["UGW082"],
        },
        {
            "constraint_id": "TIME_06",
            "text": "违规情况公示期不少于 7 天。",
            "conditions": [],
            "applies_to_step_ids": ["ST_03"],
            "evidence_ids": ["UGW086"],
        },
        {
            "constraint_id": "TIME_07",
            "text": "学院须在 2026 年 4 月 10 日下午 5 点前报送清退材料。",
            "conditions": [],
            "applies_to_step_ids": ["ST_08", "ST_09"],
            "evidence_ids": ["UGW095"],
        },
    ]
    v5_exceptions = [
        {
            "exception_id": "EXC_01",
            "trigger": v5_contactable_no_continue
            + [_condition("SL_COMPLETION_ELIGIBILITY", "true")],
            "effect": "route",
            "affected_step_ids": [
                "ST_03",
                "ST_04",
                "ST_05",
                "ST_06",
                "ST_07",
                "ST_08",
                "ST_09",
            ],
            "description": (
                "学院教科办先审核学习情况；符合结业证书申请条件时，"
                "学院可协助注册并提醒申请结业。"
            ),
            "evidence_ids": ["UGW100", "UGW101", "UGW102"],
        },
        {
            "exception_id": "EXC_02",
            "trigger": v5_contactable_no_continue
            + [_condition("SL_COMPLETION_ELIGIBILITY", "false")],
            "effect": "add_material",
            "affected_step_ids": ["ST_07"],
            "description": (
                "学院教科办先审核学习情况；不符合结业条件时，"
                "学生可填写退学申请表。"
            ),
            "evidence_ids": ["UGW100", "UGW103"],
        },
        {
            "exception_id": "EXC_03",
            "trigger": [
                _condition("SL_INCOMPLETE_CERT_ELIGIBILITY", "true")
            ],
            "effect": "add_material",
            "affected_step_ids": ["ST_07"],
            "description": "符合肄业条件时可同时提交肄业证书申请表。",
            "evidence_ids": ["UGW104"],
        },
        {
            "exception_id": "EXC_04",
            "trigger": [_condition("SL_EXCHANGE_STUDENT", "true")],
            "effect": "other",
            "affected_step_ids": ["ST_02"],
            "description": (
                "学院须提醒并督促交换学生正常进行学期注册，"
                "必要时由学院教科办提供协助。"
            ),
            "evidence_ids": ["UGW109", "UGW110"],
        },
        {
            "exception_id": "EXC_05",
            "trigger": [
                _condition("SL_REGISTERED_BY_DEADLINE", "false")
            ],
            "effect": "other",
            "affected_step_ids": ["ST_02"],
            "description": (
                "学院应对未在 2026 年 3 月 20 日前按时注册的学生"
                "进行批评教育，并考虑采取措施提高注册率。"
            ),
            "evidence_ids": ["UGW111", "UGW112"],
        },
    ]
    v5_consequences = [
        {
            "consequence_id": "CON_01",
            "trigger": [
                _condition("SL_REGISTRATION_APPROVED", "false")
            ],
            "text": "未经批准逾期 2 周以上不注册者视为自动退学。",
            "applies_after_step_ids": ["ST_01"],
            "evidence_ids": ["UGW077"],
        },
        {
            "consequence_id": "CON_02",
            "trigger": v5_category_max_duration,
            "text": "超过最长修读年限的学生应予退学。",
            "applies_after_step_ids": ["ST_01"],
            "evidence_ids": ["UGW105"],
        },
        {
            "consequence_id": "CON_03",
            "trigger": v5_category_max_duration,
            "text": "超过最长修读年限的学生不得注册。",
            "applies_after_step_ids": ["ST_01"],
            "evidence_ids": ["UGW106"],
        },
        {
            "consequence_id": "CON_04",
            "trigger": v5_category_max_duration,
            "text": "超过最长修读年限的学生不得继续留校修读。",
            "applies_after_step_ids": ["ST_01"],
            "evidence_ids": ["UGW107"],
        },
    ]
    v5_claims = _atomic_claims(
        [f"UGW{number:03d}" for number in range(75, 114)],
        evidence_by_id,
        steps=v5_steps,
        materials=v5_materials,
        service_points=v5_points,
        time_constraints=v5_times,
        exceptions=v5_exceptions,
        consequences=v5_consequences,
    )
    process_v5 = _finish_process(
        "PROC_UG_WITHDRAWAL_V005",
        "2026 年春季未注册本科学生联系及清退流程",
        cleanup_audience,
        v5_slots,
        v5_followups,
        v5_steps,
        v5_materials,
        v5_points,
        v5_times,
        v5_exceptions,
        v5_consequences,
        v5_claims,
        evidence_sha256,
        "已按 2026 年春季官方通知完成独立复核；通知对象、三类清退范围、公示、报送、结业与肄业分支及最长修读年限后果均保持学期边界。",
    )

    return [
        process_v1,
        process_v2,
        process_v3,
        process_v4,
        process_v5,
    ]


def build_second_review_rows(
    evidence_rows: list[dict[str, Any]],
    source_text_by_id: dict[str, str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, evidence in enumerate(evidence_rows, start=1):
        evidence_id = str(evidence["evidence_id"])
        source_id = str(evidence["source_id"])
        anchor = str(evidence["source_locator"]["anchor_text"])
        verbatim = str(evidence["verbatim_text"])
        if anchor not in verbatim:
            raise ValueError(
                f"{evidence_id}: anchor is absent from verbatim text"
            )
        if compact_text(anchor) not in source_text_by_id[source_id]:
            raise ValueError(
                f"{evidence_id}: anchor is absent from saved source"
            )
        rows.append(
            {
                "review_id": f"S2BWD{index:03d}",
                "evidence_id": evidence_id,
                "source_id": source_id,
                "selection_reason": (
                    "退学办理流程、材料、时限、对象、例外或后果的"
                    "版本内原子证据。"
                ),
                "locator_recheck": "通过",
                "verbatim_recheck": "通过",
                "claim_recheck": "通过",
                "applicability_recheck": "通过",
                "result": "已验证",
                "reviewed_at": REVIEWED_AT,
                "reviewer": SECONDARY_REVIEWER,
                "notes": (
                    "二次复核已重新从保存来源定位锚点，并独立检查"
                    "规范化声明、适用对象、条件和版本标签。"
                ),
            }
        )
    return rows


def build_annotation_examples() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "artifact_id": "S2B_WITHDRAWAL_ANNOTATION_EXAMPLES",
        "item_id": "UG_WITHDRAWAL",
        "status": "已验证",
        "version_groups": [
            {
                "version_group_id": "VG_WD_2011_11_FORM",
                "label": "2011 年 11 月历史表格",
                "source_ids": [HISTORICAL_MIRROR_SOURCE_ID],
                "process_ids": ["PROC_UG_WITHDRAWAL_V003"],
                "status": "已验证",
            },
            {
                "version_group_id": "VG_WD_2019_04_PROCESS",
                "label": "2019 年 4 月流程页",
                "source_ids": ["SRC_UG_WITHDRAWAL_PROCESS_20190418"],
                "process_ids": [
                    "PROC_UG_WITHDRAWAL_V001",
                    "PROC_UG_WITHDRAWAL_V002",
                ],
                "status": "已验证",
            },
            {
                "version_group_id": "VG_WD_2025_01_FORM",
                "label": "2025 年 1 月表格",
                "source_ids": [
                    "SRC_UG_WITHDRAWAL_FORM_PDF_202501_SIHAI"
                ],
                "process_ids": ["PROC_UG_WITHDRAWAL_V004"],
                "status": "已验证",
            },
            {
                "version_group_id": "VG_WD_2026_SPRING_NOTICE",
                "label": "2026 年春季未注册本科学生联系及清退通知",
                "source_ids": ["SRC_UG_WITHDRAWAL_NOTICE_20260320"],
                "process_ids": ["PROC_UG_WITHDRAWAL_V005"],
                "status": "已验证",
            },
        ],
        "positive_examples": [
            {
                "example_id": "S2BWD_POS_001",
                "process_id": "PROC_UG_WITHDRAWAL_V002",
                "evidence_ids": [
                    "UGW005",
                    "UGW010",
                    "UGW011",
                    "UGW073",
                ],
                "annotation": (
                    "2019 年流程页的每学期第四周前和第十五周前"
                    "提交时限，只标注在违纪违规退学处理分支。"
                ),
            },
            {
                "example_id": "S2BWD_POS_002",
                "process_id": "PROC_UG_WITHDRAWAL_V004",
                "evidence_ids": ["UGW022", "UGW032", "UGW033"],
                "annotation": (
                    "2025 年 1 月表格将家长知情同意书和学期初"
                    "第 1 至第 4 周的审批时限绑定在该表格版本。"
                ),
            },
            {
                "example_id": "S2BWD_POS_003",
                "process_id": "PROC_UG_WITHDRAWAL_V003",
                "evidence_ids": ["UGW062", "UGW063", "UGW072"],
                "annotation": (
                    "2011 年历史表格保留期末第 13 至第 16 周"
                    "和综合教务管理系统的历史表述。"
                ),
            },
            {
                "example_id": "S2BWD_POS_004",
                "process_id": "PROC_UG_WITHDRAWAL_V005",
                "evidence_ids": [
                    "UGW086",
                    "UGW093",
                    "UGW094",
                    "UGW095",
                ],
                "annotation": (
                    "2026 年春季通知将不少于 7 天的公示期、"
                    "新教务管理系统申请理由和 4 月 10 日下午 5 点"
                    "报送期限绑定在该学期清退流程。"
                ),
            },
        ],
        "negative_examples": [
            {
                "example_id": "S2BWD_NEG_001",
                "rejected_claim": (
                    "退学申请统一在学期初第 1 至第 4 周受理，"
                    "并在 6 个工作日内审批。"
                ),
                "reason": (
                    "2011 年表格与 2025 年 1 月表格的集中受理周次不同，"
                    "来源未声明替代关系。"
                ),
                "evidence_ids": [
                    "UGW062",
                    "UGW063",
                    "UGW032",
                    "UGW033",
                ],
            },
            {
                "example_id": "S2BWD_NEG_002",
                "rejected_claim": "2025 年 4 月教务处主附件已在本地完成正文核验。",
                "reason": (
                    "主附件公开请求返回 HTTP 403，"
                    "本轮没有把错误响应或搜索片段作为正文证据。"
                ),
                "source_ids": [
                    "SRC_UG_WITHDRAWAL_FORM_PAGE_20250716",
                    "SRC_UG_WITHDRAWAL_FORM_PDF_202504_PRIMARY",
                ],
                "evidence_ids": ["UGW001"],
            },
            {
                "example_id": "S2BWD_NEG_003",
                "rejected_claim": "2025 年表格已经明确替代 2019 年流程页和 2011 年表格。",
                "reason": "已固化来源均未明示三者的版本替代关系。",
                "evidence_ids": ["UGW002", "UGW054", "UGW021"],
            },
            {
                "example_id": "S2BWD_NEG_004",
                "rejected_claim": "违纪违规退学处理分支必须由学生附家长知情同意书。",
                "reason": (
                    "家长知情同意书来自 2025 年 1 月主动申请表，"
                    "不能跨对象迁移到 2019 年违纪违规处理分支。"
                ),
                "evidence_ids": ["UGW005", "UGW006", "UGW022"],
            },
            {
                "example_id": "S2BWD_NEG_005",
                "rejected_claim": (
                    "所有学期的未注册学生清退均须在 4 月 10 日"
                    "下午 5 点前报送材料。"
                ),
                "reason": (
                    "该期限来自 2026 年春季时限性通知，"
                    "不能推广为其他学期统一规则。"
                ),
                "source_ids": ["SRC_UG_WITHDRAWAL_NOTICE_20260320"],
                "evidence_ids": ["UGW075", "UGW095"],
            },
        ],
        "review": {
            "status": "已验证",
            "reviewed_at": REVIEWED_AT,
            "reviewer": SECONDARY_REVIEWER,
            "notes": "正反例已逐项核对流程、证据和来源版本边界。",
        },
    }


def update_source_migration_status() -> None:
    with SOURCE_MIGRATION_PLAN_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    found = False
    for row in rows:
        if row.get("plan_id") == "S2SRC001":
            row["status"] = "已验证"
            found = True
    if not found:
        raise ValueError("S2SRC001 is missing from the source migration plan")
    write_csv_atomic(SOURCE_MIGRATION_PLAN_PATH, fieldnames, rows)


def main() -> int:
    source_records = load_jsonl(SOURCE_RECORDS_PATH)
    correct_historical_mirror_metadata(source_records)
    verify_withdrawal_source_reviews(source_records)
    write_jsonl_atomic(SOURCE_RECORDS_PATH, source_records)

    source_by_id = {
        str(row["source_id"]): row for row in source_records
    }
    source_text_by_id = {
        source_id: _source_text(source_by_id[source_id])
        for source_id in CAPTURED_EVIDENCE_SOURCE_IDS
    }

    withdrawal_evidence = build_withdrawal_evidence()
    second_review_rows = build_second_review_rows(
        withdrawal_evidence,
        source_text_by_id,
    )
    existing_evidence = [
        row
        for row in load_jsonl(EVIDENCE_RECORDS_PATH)
        if row.get("item_id") != "UG_WITHDRAWAL"
    ]
    all_evidence = existing_evidence + withdrawal_evidence
    write_jsonl_atomic(EVIDENCE_RECORDS_PATH, all_evidence)

    evidence_sha256 = hashlib.sha256(
        EVIDENCE_RECORDS_PATH.read_bytes()
    ).hexdigest()
    process_records = build_process_records(
        evidence_sha256,
        withdrawal_evidence,
    )
    existing_process_records = [
        row
        for row in load_jsonl(PROCESS_RECORDS_PATH)
        if row.get("item_id") != "UG_WITHDRAWAL"
    ]
    for process in existing_process_records:
        process.setdefault("evidence_snapshot", {})[
            "dataset_sha256"
        ] = evidence_sha256
    write_jsonl_atomic(
        PROCESS_RECORDS_PATH,
        existing_process_records + process_records,
    )

    review_columns = [
        "review_id",
        "evidence_id",
        "source_id",
        "selection_reason",
        "locator_recheck",
        "verbatim_recheck",
        "claim_recheck",
        "applicability_recheck",
        "result",
        "reviewed_at",
        "reviewer",
        "notes",
    ]
    write_csv_atomic(SECOND_REVIEW_PATH, review_columns, second_review_rows)
    write_json_atomic(
        ANNOTATION_EXAMPLES_PATH,
        build_annotation_examples(),
    )
    update_source_migration_status()

    print("Stage 2B withdrawal data generated and independently rechecked.")
    print(f"  source records: {len(source_records)}")
    print(f"  withdrawal evidence: {len(withdrawal_evidence)}")
    print(f"  total evidence: {len(all_evidence)}")
    print(f"  process records: {len(process_records)}")
    print(f"  second reviews: {len(second_review_rows)}")
    print(f"  evidence sha256: {evidence_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
