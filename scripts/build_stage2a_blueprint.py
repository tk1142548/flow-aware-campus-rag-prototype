from __future__ import annotations

import argparse
import csv
import io
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_PATH = Path("data/research/stage2-evaluation-blueprint.csv")
PLAN_PATH = Path("data/research/stage2-evaluation-plan.json")

BLUEPRINT_COLUMNS = [
    "sample_id",
    "item_code",
    "item_id",
    "scenario_type",
    "difficulty",
    "version_risk",
    "turn_structure",
    "expected_response_mode",
    "annotation_status",
    "content_freeze_status",
]

ITEMS = [
    {
        "item_id": "UG_PROOF_PRINT",
        "item_code": "PP",
        "item_name": "成绩与证明打印",
        "data_baseline_status": "verified",
    },
    {
        "item_id": "UG_STATUS_CHANGE",
        "item_code": "SC",
        "item_name": "休学复学与学籍状态",
        "data_baseline_status": "verified",
    },
    {
        "item_id": "UG_WITHDRAWAL",
        "item_code": "WD",
        "item_name": "退学办理",
        "data_baseline_status": "planned",
    },
    {
        "item_id": "UG_CREDENTIAL_REISSUE",
        "item_code": "CR",
        "item_name": "学历学位证书补办",
        "data_baseline_status": "planned",
    },
    {
        "item_id": "UG_STUDENT_CARD_REISSUE",
        "item_code": "SR",
        "item_name": "学生证补办",
        "data_baseline_status": "planned",
    },
    {
        "item_id": "UG_COURSE_SELECTION",
        "item_code": "CS",
        "item_name": "本科选课",
        "data_baseline_status": "planned",
    },
    {
        "item_id": "UG_LEAVE_REQUEST",
        "item_code": "LR",
        "item_name": "本科生请假",
        "data_baseline_status": "planned",
    },
    {
        "item_id": "UG_MAJOR_CHANGE",
        "item_code": "MC",
        "item_name": "本科生转专业",
        "data_baseline_status": "planned",
    },
]

# 每类事项复用同一组 25 个分层槽位，从而使事项宏平均不受样本数影响。
SLOT_TEMPLATES = [
    ("direct", "easy", "stable", "single_turn", "answer"),
    ("direct", "easy", "stable", "single_turn", "answer"),
    ("direct", "easy", "version_sensitive", "single_turn", "answer"),
    ("direct", "medium", "stable", "single_turn", "answer"),
    (
        "condition_missing",
        "easy",
        "stable",
        "single_turn",
        "clarification",
    ),
    (
        "condition_missing",
        "medium",
        "stable",
        "single_turn",
        "clarification",
    ),
    (
        "condition_missing",
        "medium",
        "version_sensitive",
        "single_turn",
        "clarification",
    ),
    (
        "condition_missing",
        "hard",
        "version_sensitive",
        "single_turn",
        "clarification",
    ),
    (
        "object_mismatch",
        "medium",
        "stable",
        "single_turn",
        "scoped_correction",
    ),
    (
        "object_mismatch",
        "medium",
        "version_sensitive",
        "single_turn",
        "scoped_correction",
    ),
    (
        "object_mismatch",
        "hard",
        "stable",
        "single_turn",
        "scoped_correction",
    ),
    (
        "version_conflict",
        "medium",
        "cross_version_conflict",
        "single_turn",
        "version_qualified",
    ),
    (
        "version_conflict",
        "hard",
        "cross_version_conflict",
        "single_turn",
        "version_qualified",
    ),
    (
        "version_conflict",
        "hard",
        "cross_version_conflict",
        "single_turn",
        "version_qualified",
    ),
    ("step_error", "easy", "stable", "single_turn", "scoped_correction"),
    (
        "step_error",
        "medium",
        "version_sensitive",
        "single_turn",
        "scoped_correction",
    ),
    ("step_error", "hard", "stable", "single_turn", "scoped_correction"),
    (
        "material_confusion",
        "easy",
        "stable",
        "single_turn",
        "scoped_correction",
    ),
    (
        "material_confusion",
        "medium",
        "version_sensitive",
        "single_turn",
        "scoped_correction",
    ),
    (
        "material_confusion",
        "medium",
        "stable",
        "single_turn",
        "scoped_correction",
    ),
    (
        "out_of_scope",
        "medium",
        "version_sensitive",
        "single_turn",
        "abstention",
    ),
    ("out_of_scope", "hard", "stable", "single_turn", "abstention"),
    (
        "multi_turn",
        "medium",
        "version_sensitive",
        "multi_turn",
        "conversation_resolution",
    ),
    (
        "multi_turn",
        "medium",
        "version_sensitive",
        "multi_turn",
        "conversation_resolution",
    ),
    (
        "multi_turn",
        "hard",
        "stable",
        "multi_turn",
        "conversation_resolution",
    ),
]

STAGE1_BASELINE = {
    "stage1_data_commit": "cb243dd46b04e4ab113bdaf754894482af999ff6",
    "source_records_path": "data/research/source_records.jsonl",
    "evidence_units_path": "data/research/evidence_units.jsonl",
    "candidate_survey_path": "data/research/candidate-item-survey.csv",
}


def build_blueprint_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in ITEMS:
        for slot_number, template in enumerate(SLOT_TEMPLATES, start=1):
            (
                scenario_type,
                difficulty,
                version_risk,
                turn_structure,
                response_mode,
            ) = template
            rows.append(
                {
                    "sample_id": (
                        f"S2E-{item['item_code']}-{slot_number:03d}"
                    ),
                    "item_code": item["item_code"],
                    "item_id": item["item_id"],
                    "scenario_type": scenario_type,
                    "difficulty": difficulty,
                    "version_risk": version_risk,
                    "turn_structure": turn_structure,
                    "expected_response_mode": response_mode,
                    "annotation_status": "planned",
                    "content_freeze_status": "not_frozen",
                }
            )
    return rows


def render_blueprint(rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=BLUEPRINT_COLUMNS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def counts_for(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(row[field] for row in rows).items()))


def build_plan(
    rows: list[dict[str, str]],
    blueprint_bytes: bytes,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "plan_id": "STAGE2_EVAL_200_V1",
        "decision_id": "D-017",
        "status": "allocation_frozen",
        "confirmed_on": "2026-07-30",
        "dataset_id": "CAMPUS_RAG_STAGE2_EVAL",
        "dataset_release_version": "0.1.0-allocation",
        "formal_items": [
            {
                **item,
                "sample_quota": 25,
            }
            for item in ITEMS
        ],
        "transfer_candidates": [
            {
                "item_id": "UG_GRADUATION_INTERNSHIP",
                "item_name": "毕业实习办理",
                "admission_gate": (
                    "完成官方来源固化、原子证据迁移、流程标注和独立复核后，"
                    "登记为跨事项迁移评测候选；不计入 200 条评测样本。"
                ),
                "status": "planned",
            }
        ],
        "target_sample_count": len(rows),
        "allocation": {
            "blueprint_path": BLUEPRINT_PATH.as_posix(),
            "per_item": counts_for(rows, "item_id"),
            "scenario_type": counts_for(rows, "scenario_type"),
            "difficulty": counts_for(rows, "difficulty"),
            "version_risk": counts_for(rows, "version_risk"),
            "turn_structure": counts_for(rows, "turn_structure"),
        },
        "review_policy": {
            "primary_reviews_per_sample": 1,
            "independent_second_reviews_per_sample": 1,
            "second_review_coverage": 1.0,
            "reviewer_identity_must_differ": True,
            "disagreements_require_adjudication": True,
            "unresolved_disagreements_allowed_at_freeze": False,
            "review_dimensions": [
                "item_mapping",
                "slot_and_follow_up",
                "process_structure",
                "claim_and_evidence",
                "version_applicability",
                "leakage_control",
            ],
        },
        "freeze_policy": {
            "allocation_frozen_at": "2026-07-30T22:52:58+08:00",
            "content_freeze_status": "pending",
            "content_freeze_version": None,
            "sample_id_rule": (
                "S2E-<事项两字母代码>-<事项内三位顺序号>；编号一经分配不复用，"
                "被拒绝样本保留编号与拒绝记录。"
            ),
            "version_rule": {
                "major": "事项范围、评测定义、金标准字段语义或泄漏边界发生变化。",
                "minor": "形成新的完整评测发布。",
                "patch": "经裁决修正标注错误；保留旧值、新值、证据、原因和影响记录。",
            },
            "content_freeze_gate": [
                "200 个样本槽位均完成内容标注且通过模式校验",
                "每个样本均绑定已验证流程记录与允许声明",
                "每个非越界样本均绑定可定位的已验证证据",
                "200 个样本均完成第二次独立复核",
                "全部分歧均完成字段级裁决且没有未解决项",
                "模板族、来源版本组和语义近重复泄漏检查均通过",
                "记录流程、来源、证据、样本和复核文件的 SHA-256",
            ],
            "immutable_after_content_freeze": [
                "sample_id",
                "item_id",
                "scenario_type",
                "difficulty",
                "version_risk",
                "conversation",
                "input_context",
                "gold",
                "leakage_control",
                "process_id",
                "supporting_evidence_ids",
            ],
            "method_tuning_boundary": (
                "评测样本的对话、金标准、证据绑定和裁决记录不得用于提示词、"
                "检索参数、模型选择或规则阈值调试；调试仅使用测试集外开发样本。"
            ),
            "hash_algorithm": "sha256",
        },
        "upstream_baseline": STAGE1_BASELINE,
    }


def render_plan(plan: dict[str, Any]) -> bytes:
    return (
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    ).encode("utf-8")


def expected_outputs() -> dict[Path, bytes]:
    rows = build_blueprint_rows()
    blueprint_bytes = render_blueprint(rows)
    plan = build_plan(rows, blueprint_bytes)
    return {
        BLUEPRINT_PATH: blueprint_bytes,
        PLAN_PATH: render_plan(plan),
    }


def write_outputs(root: Path) -> None:
    for relative_path, payload in expected_outputs().items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        print(f"[WRITE] {relative_path.as_posix()}")


def check_outputs(root: Path) -> list[str]:
    errors: list[str] = []
    for relative_path, expected in expected_outputs().items():
        path = root / relative_path
        if not path.is_file():
            errors.append(f"{relative_path.as_posix()}: generated artifact is missing")
            continue
        actual = path.read_bytes()
        if actual != expected:
            errors.append(
                f"{relative_path.as_posix()}: content differs from deterministic blueprint"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build or verify the deterministic stage 2A evaluation allocation."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root. Defaults to the parent of this script directory.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the blueprint and evaluation-plan artifacts.",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    if args.write:
        write_outputs(root)
        return 0

    errors = check_outputs(root)
    if errors:
        print("[FAIL] Stage 2A blueprint verification failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("[OK] Stage 2A blueprint matches deterministic allocation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
