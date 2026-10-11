from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]

SCHEMA_FIXTURES = {
    "source-record.schema.json": {
        "valid": ["tests/fixtures/data/valid/source-record.json"],
        "invalid": [
            "tests/fixtures/data/invalid/source-record-captured-without-hash.json",
            "tests/fixtures/data/invalid/source-record-invalid-date.json",
        ],
    },
    "evidence-unit.schema.json": {
        "valid": ["tests/fixtures/data/valid/evidence-unit.json"],
        "invalid": [
            "tests/fixtures/data/invalid/evidence-unit-invalid-id.json",
            "tests/fixtures/data/invalid/evidence-unit-without-locator.json",
        ],
    },
    "process-record.schema.json": {
        "valid": ["tests/fixtures/data/valid/process-record.json"],
        "invalid": [
            "tests/fixtures/data/invalid/process-record-step-without-evidence.json",
        ],
    },
    "evaluation-sample.schema.json": {
        "valid": ["tests/fixtures/data/valid/evaluation-sample.json"],
        "invalid": [
            "tests/fixtures/data/invalid/evaluation-sample-invalid-id.json",
        ],
    },
    "evaluation-review-record.schema.json": {
        "valid": ["tests/fixtures/data/valid/evaluation-review-record.json"],
        "invalid": [
            "tests/fixtures/data/invalid/evaluation-review-unresolved-disagreement.json",
        ],
    },
    "evaluation-plan.schema.json": {
        "valid": ["data/research/stage2-evaluation-plan.json"],
        "invalid": [
            "tests/fixtures/data/invalid/evaluation-plan-wrong-count.json",
        ],
    },
}

SOURCE_AUDIT_COLUMNS = [
    "source_id",
    "title",
    "source_url",
    "evidence_count",
    "publish_date_status",
    "snapshot_status",
    "locator_status",
    "version_status",
    "content_review_status",
    "priority",
    "known_issue",
    "next_action",
    "review_status",
]

EVIDENCE_AUDIT_COLUMNS = [
    "evidence_id",
    "item_id",
    "source_id",
    "legacy_publish_date_status",
    "legacy_locator_status",
    "verbatim_text_status",
    "claim_review_status",
    "priority",
    "known_issue",
    "next_action",
    "review_status",
    "migration_status",
    "target_evidence_ids",
]

KNOWN_MISMATCH_IDS = {
    "UGP002",
    "UGS002",
    "UGS003",
    "UGS004",
    "UGS012",
    "UGS013",
    "UGS014",
}
TARGET_SOURCE_RECORDS_PATH = Path("data/research/source_records.jsonl")
TARGET_EVIDENCE_RECORDS_PATH = Path("data/research/evidence_units.jsonl")
CANDIDATE_SURVEY_PATH = Path("data/research/candidate-item-survey.csv")
SECOND_REVIEW_PATH = Path("data/audit/stage1-second-review.csv")
STAGE_1_AUDIT_REPORT_PATH = Path("docs/data/STAGE_1_DATA_AUDIT.md")
STAGE_2_EVALUATION_PLAN_PATH = Path(
    "data/research/stage2-evaluation-plan.json"
)
STAGE_2_EVALUATION_BLUEPRINT_PATH = Path(
    "data/research/stage2-evaluation-blueprint.csv"
)
STAGE_2_SOURCE_PLAN_PATH = Path(
    "data/research/stage2-source-migration-plan.csv"
)
STAGE_2_ANNOTATION_GUIDE_PATH = Path(
    "docs/data/STAGE_2_ANNOTATION_GUIDE.md"
)
STAGE_2B_WITHDRAWAL_PROCESS_PATH = Path(
    "data/research/process_records.jsonl"
)
STAGE_2B_WITHDRAWAL_SECOND_REVIEW_PATH = Path(
    "data/audit/stage2b-withdrawal-second-review.csv"
)
STAGE_2B_WITHDRAWAL_EXAMPLES_PATH = Path(
    "data/research/stage2b-withdrawal-annotation-examples.json"
)

STAGE_2B_WITHDRAWAL_SOURCE_IDS = {
    "SRC_UG_WITHDRAWAL_PROCESS_20190418",
    "SRC_UG_WITHDRAWAL_FORM_PAGE_20250716",
    "SRC_UG_WITHDRAWAL_FORM_PDF_202504_PRIMARY",
    "SRC_UG_WITHDRAWAL_INDEX_20250716",
    "SRC_UG_WITHDRAWAL_FORM_MIRROR_20241027",
    "SRC_UG_WITHDRAWAL_FORM_PDF_201111_MIRROR",
    "SRC_UG_WITHDRAWAL_FORM_PDF_202501_SIHAI",
    "SRC_UG_WITHDRAWAL_POLICY_PAGE_20250716",
    "SRC_UG_WITHDRAWAL_POLICY_PDF_20250716",
    "SRC_UG_WITHDRAWAL_NOTICE_20260320",
}
STAGE_2B_WITHDRAWAL_CAPTURED_SOURCE_IDS = {
    "SRC_UG_WITHDRAWAL_PROCESS_20190418",
    "SRC_UG_WITHDRAWAL_INDEX_20250716",
    "SRC_UG_WITHDRAWAL_FORM_MIRROR_20241027",
    "SRC_UG_WITHDRAWAL_FORM_PDF_201111_MIRROR",
    "SRC_UG_WITHDRAWAL_FORM_PDF_202501_SIHAI",
    "SRC_UG_WITHDRAWAL_POLICY_PAGE_20250716",
    "SRC_UG_WITHDRAWAL_NOTICE_20260320",
}
STAGE_2B_WITHDRAWAL_FAILED_SOURCE_IDS = {
    "SRC_UG_WITHDRAWAL_FORM_PAGE_20250716",
    "SRC_UG_WITHDRAWAL_FORM_PDF_202504_PRIMARY",
    "SRC_UG_WITHDRAWAL_POLICY_PDF_20250716",
}

CANDIDATE_SURVEY_COLUMNS = [
    "candidate_id",
    "candidate_name",
    "data_baseline_status",
    "official_source_urls",
    "source_checked_at",
    "source_availability",
    "evidence_completeness_score",
    "condition_branch_score",
    "version_risk_score",
    "evaluation_value_score",
    "annotation_cost_score",
    "observed_evidence",
    "remaining_gap",
    "stage_2_option_group",
    "survey_status",
]

SECOND_REVIEW_COLUMNS = [
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

STAGE_1_EVIDENCE_SOURCE_IDS = {
    "SRC_UG_PRINT_20210317",
    "SRC_UG_SUSPEND_FORM_PDF_202504",
    "SRC_UG_RESUME_FORM_PDF_202504",
    "SRC_UG_GRAD_NOTICE_20250617",
    "SRC_GS_CERT_20130903",
    "SRC_UG_SUSPEND_PROCESS_20190418",
    "SRC_UG_RESUME_PROCESS_20190418",
    "SRC_UG_UNREGISTERED_20250321",
}

STAGE_1_CANDIDATE_IDS = {
    "UG_PROOF_PRINT",
    "UG_STATUS_CHANGE",
    "UG_WITHDRAWAL",
    "UG_CREDENTIAL_REISSUE",
    "UG_STUDENT_CARD_REISSUE",
    "UG_COURSE_SELECTION",
    "UG_LEAVE_REQUEST",
    "UG_MAJOR_CHANGE",
    "UG_GRADUATION_INTERNSHIP",
}

STAGE_2_FORMAL_ITEMS = {
    "UG_PROOF_PRINT": ("PP", "成绩与证明打印", "verified"),
    "UG_STATUS_CHANGE": ("SC", "休学复学与学籍状态", "verified"),
    "UG_WITHDRAWAL": ("WD", "退学办理", "verified"),
    "UG_CREDENTIAL_REISSUE": ("CR", "学历学位证书补办", "verified"),
    "UG_STUDENT_CARD_REISSUE": ("SR", "学生证补办", "verified"),
    "UG_COURSE_SELECTION": ("CS", "本科选课", "verified"),
    "UG_LEAVE_REQUEST": ("LR", "本科生请假", "verified"),
    "UG_MAJOR_CHANGE": ("MC", "本科生转专业", "verified"),
}

STAGE_2_BLUEPRINT_COLUMNS = [
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

STAGE_2_SOURCE_PLAN_COLUMNS = [
    "plan_id",
    "item_id",
    "item_name",
    "scope_role",
    "priority",
    "official_source_urls",
    "required_source_roles",
    "version_questions",
    "required_claim_types",
    "acceptance_gate",
    "status",
]

STAGE_2_SCENARIO_RESPONSE_MODES = {
    "direct": "answer",
    "condition_missing": "clarification",
    "object_mismatch": "scoped_correction",
    "version_conflict": "version_qualified",
    "step_error": "scoped_correction",
    "material_confusion": "scoped_correction",
    "out_of_scope": "abstention",
    "multi_turn": "conversation_resolution",
}

STAGE_2_EXPECTED_COUNTS = {
    "scenario_type": {
        "direct": 32,
        "condition_missing": 32,
        "object_mismatch": 24,
        "version_conflict": 24,
        "step_error": 24,
        "material_confusion": 24,
        "out_of_scope": 16,
        "multi_turn": 24,
    },
    "difficulty": {
        "easy": 48,
        "medium": 96,
        "hard": 56,
    },
    "version_risk": {
        "stable": 104,
        "version_sensitive": 72,
        "cross_version_conflict": 24,
    },
    "turn_structure": {
        "single_turn": 176,
        "multi_turn": 24,
    },
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def compact_text(text: str) -> str:
    return "".join(text.replace("\xa0", " ").split())


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            rows.append(payload)
    return rows


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        return headers, list(reader)


def duplicate_values(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def validate_stage2_fixture_links(
    process: dict[str, Any],
    sample: dict[str, Any],
    review: dict[str, Any],
    evidence_records: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    process_id = str(process.get("process_id", "<unknown>"))
    process_item_id = str(process.get("item_id", ""))

    collection_specs = {
        "slots": "slot_id",
        "follow_up_rules": "rule_id",
        "steps": "step_id",
        "materials": "material_id",
        "service_points": "point_id",
        "time_constraints": "constraint_id",
        "exceptions": "exception_id",
        "consequences": "consequence_id",
        "allowed_claims": "claim_id",
    }
    ids_by_collection: dict[str, set[str]] = {}
    for collection_name, id_field in collection_specs.items():
        values = [
            str(row.get(id_field, ""))
            for row in process.get(collection_name, [])
        ]
        duplicates = duplicate_values(values)
        if duplicates:
            errors.append(
                f"{process_id}: duplicate {collection_name}.{id_field} values: "
                f"{duplicates}"
            )
        ids_by_collection[collection_name] = set(values)

    slot_ids = ids_by_collection["slots"]
    step_ids = ids_by_collection["steps"]
    material_ids = ids_by_collection["materials"]
    point_ids = ids_by_collection["service_points"]
    time_ids = ids_by_collection["time_constraints"]
    claim_ids = ids_by_collection["allowed_claims"]

    referenced_evidence_ids: set[str] = set()

    def collect_evidence(rows: list[dict[str, Any]], collection_name: str) -> None:
        for row in rows:
            evidence_ids = [str(value) for value in row.get("evidence_ids", [])]
            duplicates = duplicate_values(evidence_ids)
            if duplicates:
                errors.append(
                    f"{process_id}:{collection_name}: duplicate evidence IDs "
                    f"{duplicates}"
                )
            referenced_evidence_ids.update(evidence_ids)

    for collection_name in collection_specs:
        collect_evidence(process.get(collection_name, []), collection_name)

    condition_groups: list[tuple[str, list[dict[str, Any]]]] = []
    for step in process.get("steps", []):
        condition_groups.append(
            (str(step.get("step_id", "<unknown>")), step.get("conditions", []))
        )
    for material in process.get("materials", []):
        condition_groups.append(
            (
                str(material.get("material_id", "<unknown>")),
                material.get("required_when", []),
            )
        )
    for point in process.get("service_points", []):
        condition_groups.append(
            (str(point.get("point_id", "<unknown>")), point.get("conditions", []))
        )
    for constraint in process.get("time_constraints", []):
        condition_groups.append(
            (
                str(constraint.get("constraint_id", "<unknown>")),
                constraint.get("conditions", []),
            )
        )
    for exception in process.get("exceptions", []):
        condition_groups.append(
            (
                str(exception.get("exception_id", "<unknown>")),
                exception.get("trigger", []),
            )
        )
    for consequence in process.get("consequences", []):
        condition_groups.append(
            (
                str(consequence.get("consequence_id", "<unknown>")),
                consequence.get("trigger", []),
            )
        )
    for claim in process.get("allowed_claims", []):
        condition_groups.append(
            (str(claim.get("claim_id", "<unknown>")), claim.get("conditions", []))
        )

    for owner_id, conditions in condition_groups:
        for condition in conditions:
            slot_id = str(condition.get("slot_id", ""))
            if slot_id not in slot_ids:
                errors.append(
                    f"{process_id}:{owner_id}: condition references unknown slot "
                    f"{slot_id!r}"
                )
            operator = condition.get("operator")
            value = condition.get("value")
            if operator in {"known", "unknown"} and value is not None:
                errors.append(
                    f"{process_id}:{owner_id}: {operator} condition requires null value"
                )
            if operator in {"equals", "not_equals", "in"} and value is None:
                errors.append(
                    f"{process_id}:{owner_id}: {operator} condition requires a value"
                )

    for slot in process.get("slots", []):
        allowed_values = slot.get("allowed_values", [])
        value_type = slot.get("value_type")
        if value_type == "enum" and not allowed_values:
            errors.append(
                f"{process_id}:{slot.get('slot_id')}: enum slot requires allowed_values"
            )
        if value_type != "enum" and allowed_values:
            errors.append(
                f"{process_id}:{slot.get('slot_id')}: non-enum slot must not "
                "declare allowed_values"
            )

    covered_follow_up_slots: set[str] = set()
    for rule in process.get("follow_up_rules", []):
        for slot_id in rule.get("when_missing_slot_ids", []):
            if slot_id not in slot_ids:
                errors.append(
                    f"{process_id}:{rule.get('rule_id')}: follow-up references "
                    f"unknown slot {slot_id!r}"
                )
            covered_follow_up_slots.add(str(slot_id))
    ask_required_slots = {
        str(slot.get("slot_id"))
        for slot in process.get("slots", [])
        if slot.get("required_for_resolution")
        and slot.get("unknown_policy") == "ask"
    }
    missing_follow_up_rules = sorted(
        ask_required_slots - covered_follow_up_slots
    )
    if missing_follow_up_rules:
        errors.append(
            f"{process_id}: required ask slots lack follow-up rules: "
            f"{missing_follow_up_rules}"
        )

    steps_by_id = {
        str(step.get("step_id", "")): step for step in process.get("steps", [])
    }
    orders = [step.get("order") for step in process.get("steps", [])]
    if sorted(orders) != list(range(1, len(orders) + 1)):
        errors.append(
            f"{process_id}: step order values must be contiguous from 1"
        )

    def require_known_references(
        owner_id: str,
        values: list[str],
        known: set[str],
        field: str,
    ) -> None:
        unknown = sorted(set(str(value) for value in values) - known)
        if unknown:
            errors.append(
                f"{process_id}:{owner_id}: {field} references unknown IDs {unknown}"
            )

    for step in process.get("steps", []):
        step_id = str(step.get("step_id", "<unknown>"))
        require_known_references(
            step_id,
            step.get("required_material_ids", []),
            material_ids,
            "required_material_ids",
        )
        require_known_references(
            step_id,
            step.get("service_point_ids", []),
            point_ids,
            "service_point_ids",
        )
        require_known_references(
            step_id,
            step.get("time_constraint_ids", []),
            time_ids,
            "time_constraint_ids",
        )
        require_known_references(
            step_id,
            step.get("next_step_ids", []),
            step_ids,
            "next_step_ids",
        )
        for next_step_id in step.get("next_step_ids", []):
            next_step = steps_by_id.get(str(next_step_id))
            if next_step and next_step.get("order", 0) <= step.get("order", 0):
                errors.append(
                    f"{process_id}:{step_id}: next step {next_step_id} must have "
                    "a greater order"
                )

    for material in process.get("materials", []):
        require_known_references(
            str(material.get("material_id", "<unknown>")),
            material.get("required_at_step_ids", []),
            step_ids,
            "required_at_step_ids",
        )
    for point in process.get("service_points", []):
        require_known_references(
            str(point.get("point_id", "<unknown>")),
            point.get("applies_to_step_ids", []),
            step_ids,
            "applies_to_step_ids",
        )
    for constraint in process.get("time_constraints", []):
        require_known_references(
            str(constraint.get("constraint_id", "<unknown>")),
            constraint.get("applies_to_step_ids", []),
            step_ids,
            "applies_to_step_ids",
        )
    for exception in process.get("exceptions", []):
        require_known_references(
            str(exception.get("exception_id", "<unknown>")),
            exception.get("affected_step_ids", []),
            step_ids,
            "affected_step_ids",
        )
    for consequence in process.get("consequences", []):
        require_known_references(
            str(consequence.get("consequence_id", "<unknown>")),
            consequence.get("applies_after_step_ids", []),
            step_ids,
            "applies_after_step_ids",
        )
    for claim in process.get("allowed_claims", []):
        require_known_references(
            str(claim.get("claim_id", "<unknown>")),
            claim.get("applicable_step_ids", []),
            step_ids,
            "applicable_step_ids",
        )

    first_step_ids = {
        str(step.get("step_id"))
        for step in process.get("steps", [])
        if step.get("order") == 1
    }
    reachable = set(first_step_ids)
    frontier = list(first_step_ids)
    while frontier:
        current_id = frontier.pop()
        current = steps_by_id.get(current_id, {})
        for next_step_id in current.get("next_step_ids", []):
            next_step_id = str(next_step_id)
            if next_step_id not in reachable:
                reachable.add(next_step_id)
                frontier.append(next_step_id)
    if reachable != step_ids:
        errors.append(
            f"{process_id}: unreachable steps: {sorted(step_ids - reachable)}"
        )
    if process.get("steps") and not any(
        not step.get("next_step_ids") for step in process.get("steps", [])
    ):
        errors.append(f"{process_id}: process must contain a terminal step")

    snapshot_ids = {
        str(value)
        for value in process.get("evidence_snapshot", {}).get(
            "evidence_ids", []
        )
    }
    if snapshot_ids != referenced_evidence_ids:
        errors.append(
            f"{process_id}: evidence_snapshot must exactly equal referenced evidence; "
            f"missing={sorted(referenced_evidence_ids - snapshot_ids)}, "
            f"extra={sorted(snapshot_ids - referenced_evidence_ids)}"
        )

    evidence_by_id = {
        str(row.get("evidence_id")): row for row in evidence_records
    }
    unknown_evidence = sorted(referenced_evidence_ids - set(evidence_by_id))
    if unknown_evidence:
        errors.append(
            f"{process_id}: references unknown evidence IDs {unknown_evidence}"
        )
    wrong_item_evidence = sorted(
        evidence_id
        for evidence_id in referenced_evidence_ids
        if evidence_id in evidence_by_id
        and evidence_by_id[evidence_id].get("item_id") != process_item_id
    )
    if wrong_item_evidence:
        errors.append(
            f"{process_id}: evidence belongs to another item: "
            f"{wrong_item_evidence}"
        )

    sample_id = str(sample.get("sample_id", "<unknown>"))
    allocation_item_id = sample.get("allocation_item_id")
    expected_item = STAGE_2_FORMAL_ITEMS.get(str(allocation_item_id))
    sample_match = re.fullmatch(
        r"S2E-(PP|SC|WD|CR|SR|CS|LR|MC)-[0-9]{3}",
        sample_id,
    )
    if expected_item and sample_match and sample_match.group(1) != expected_item[0]:
        errors.append(
            f"{sample_id}: item code does not match allocation_item_id"
        )
    if sample.get("scenario_type") != "out_of_scope":
        if sample.get("item_id") != process_item_id:
            errors.append(f"{sample_id}: item_id differs from process item_id")
        if sample.get("process_id") != process_id:
            errors.append(f"{sample_id}: process_id differs from process record")
        if sample.get("gold", {}).get("target_item_id") != process_item_id:
            errors.append(
                f"{sample_id}: gold.target_item_id differs from process item_id"
            )
        if allocation_item_id != process_item_id:
            errors.append(
                f"{sample_id}: allocation_item_id differs from process item_id"
            )

    expected_mode = STAGE_2_SCENARIO_RESPONSE_MODES.get(
        str(sample.get("scenario_type"))
    )
    if sample.get("gold", {}).get("response_mode") != expected_mode:
        errors.append(
            f"{sample_id}: response mode must be {expected_mode!r} for "
            f"scenario {sample.get('scenario_type')!r}"
        )

    turns = sample.get("conversation", [])
    expected_turn_ids = [
        f"T{index:02d}" for index in range(1, len(turns) + 1)
    ]
    if [turn.get("turn_id") for turn in turns] != expected_turn_ids:
        errors.append(f"{sample_id}: conversation turn IDs must be contiguous")
    if turns and turns[-1].get("role") != "user":
        errors.append(f"{sample_id}: final conversation turn must be from user")
    if sample.get("turn_structure") == "multi_turn" and not any(
        turn.get("role") == "assistant" for turn in turns[:-1]
    ):
        errors.append(
            f"{sample_id}: multi-turn conversation requires prior assistant context"
        )

    provided_slots = sample.get("input_context", {}).get(
        "provided_slots", []
    )
    provided_slot_ids = [
        str(row.get("slot_id", "")) for row in provided_slots
    ]
    duplicates = duplicate_values(provided_slot_ids)
    if duplicates:
        errors.append(
            f"{sample_id}: duplicate provided slot IDs: {duplicates}"
        )
    require_known_references(
        sample_id,
        provided_slot_ids,
        slot_ids,
        "provided_slots",
    )

    gold = sample.get("gold", {})
    require_known_references(
        sample_id,
        gold.get("required_slot_ids", []),
        slot_ids,
        "gold.required_slot_ids",
    )
    require_known_references(
        sample_id,
        gold.get("missing_slot_ids", []),
        slot_ids,
        "gold.missing_slot_ids",
    )
    require_known_references(
        sample_id,
        gold.get("ordered_step_ids", []),
        step_ids,
        "gold.ordered_step_ids",
    )
    require_known_references(
        sample_id,
        gold.get("material_ids", []),
        material_ids,
        "gold.material_ids",
    )
    require_known_references(
        sample_id,
        gold.get("allowed_claim_ids", []),
        claim_ids,
        "gold.allowed_claim_ids",
    )
    unsupported_evidence = sorted(
        set(str(value) for value in gold.get("supporting_evidence_ids", []))
        - snapshot_ids
    )
    if unsupported_evidence:
        errors.append(
            f"{sample_id}: gold supporting evidence is outside process snapshot: "
            f"{unsupported_evidence}"
        )
    known_provided_slots = {
        str(row.get("slot_id"))
        for row in provided_slots
        if row.get("value_status") == "known"
    }
    contradictory_missing = sorted(
        known_provided_slots
        & set(str(value) for value in gold.get("missing_slot_ids", []))
    )
    if contradictory_missing:
        errors.append(
            f"{sample_id}: known provided slots also marked missing: "
            f"{contradictory_missing}"
        )
    if sample_id in set(
        str(value)
        for value in sample.get("leakage_control", {}).get(
            "prohibited_overlap_sample_ids", []
        )
    ):
        errors.append(f"{sample_id}: sample cannot overlap with itself")

    if review.get("sample_id") != sample_id:
        errors.append(f"{review.get('review_id')}: sample_id differs from fixture")
    if review.get("dataset_version") != sample.get("dataset_version"):
        errors.append(
            f"{review.get('review_id')}: dataset_version differs from sample"
        )
    primary_reviewer = review.get("primary_annotation", {}).get("reviewer")
    secondary_reviewer = review.get("secondary_review", {}).get("reviewer")
    if primary_reviewer == secondary_reviewer:
        errors.append(
            f"{review.get('review_id')}: primary and secondary reviewers must differ"
        )
    adjudication = review.get("adjudication")
    if isinstance(adjudication, dict):
        adjudicator = adjudication.get("adjudicator")
        if adjudicator in {primary_reviewer, secondary_reviewer}:
            errors.append(
                f"{review.get('review_id')}: adjudicator must differ from both reviewers"
            )
        disagreement_paths = {
            str(row.get("field_path"))
            for row in review.get("disagreements", [])
        }
        resolution_paths = {
            str(row.get("field_path"))
            for row in adjudication.get("field_resolutions", [])
        }
        if disagreement_paths != resolution_paths:
            errors.append(
                f"{review.get('review_id')}: adjudication must resolve every "
                "disagreement field exactly once"
            )

    return errors


def validate_target_links(
    source_records: list[dict[str, Any]],
    evidence_records: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    source_ids = [str(row.get("source_id", "")) for row in source_records]
    evidence_ids = [str(row.get("evidence_id", "")) for row in evidence_records]

    duplicate_source_ids = duplicate_values(source_ids)
    duplicate_evidence_ids = duplicate_values(evidence_ids)
    if duplicate_source_ids:
        errors.append(f"duplicate target source_id values: {duplicate_source_ids}")
    if duplicate_evidence_ids:
        errors.append(f"duplicate target evidence_id values: {duplicate_evidence_ids}")

    known_sources = set(source_ids)
    sources_by_id = {
        str(row.get("source_id", "")): row
        for row in source_records
        if row.get("source_id")
    }
    reciprocal_relations = {
        "attachment_of": "landing_page_for",
        "landing_page_for": "attachment_of",
        "same_document_as": "same_document_as",
    }
    for source in source_records:
        source_id = str(source.get("source_id", "<unknown>"))
        for relation in source.get("relations", []):
            target_source_id = str(relation.get("target_source_id", ""))
            if target_source_id not in known_sources:
                errors.append(
                    f"{source_id}: relation references unknown source_id "
                    f"{target_source_id!r}"
                )
                continue
            relation_type = str(relation.get("relation_type", ""))
            reciprocal_type = reciprocal_relations.get(relation_type)
            if reciprocal_type:
                target_relations = sources_by_id[target_source_id].get("relations", [])
                if not any(
                    target_relation.get("relation_type") == reciprocal_type
                    and target_relation.get("target_source_id") == source_id
                    for target_relation in target_relations
                ):
                    errors.append(
                        f"{source_id}: {relation_type} relation to {target_source_id} "
                        f"is missing reciprocal {reciprocal_type}"
                    )
        version = source.get("version", {})
        for field in ("supersedes", "superseded_by"):
            for target_source_id in version.get(field, []):
                if target_source_id not in known_sources:
                    errors.append(
                        f"{source_id}: version.{field} references unknown source_id "
                        f"{target_source_id!r}"
                    )
                    continue
                reciprocal_field = (
                    "superseded_by" if field == "supersedes" else "supersedes"
                )
                reciprocal_values = sources_by_id[target_source_id].get("version", {}).get(
                    reciprocal_field, []
                )
                if source_id not in reciprocal_values:
                    errors.append(
                        f"{source_id}: version.{field} reference to {target_source_id} "
                        f"is missing reciprocal version.{reciprocal_field}"
                    )

    for evidence in evidence_records:
        source_id = str(evidence.get("source_id", ""))
        if source_id not in known_sources:
            errors.append(
                f"{evidence.get('evidence_id', '<unknown>')}: unknown source_id {source_id!r}"
            )
    return errors


def host_matches_domain(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def validate_target_repository(
    root: Path = ROOT,
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    source_path = root / TARGET_SOURCE_RECORDS_PATH
    evidence_path = root / TARGET_EVIDENCE_RECORDS_PATH

    missing_paths = [path for path in (source_path, evidence_path) if not path.is_file()]
    if missing_paths:
        return [f"{path}: required target data file is missing" for path in missing_paths], {}

    try:
        source_records = load_jsonl(source_path)
        evidence_records = load_jsonl(evidence_path)
    except ValueError as exc:
        return [str(exc)], {}

    source_schema = load_json(root / "data/schemas/source-record.schema.json")
    evidence_schema = load_json(root / "data/schemas/evidence-unit.schema.json")
    source_validator = Draft202012Validator(
        source_schema, format_checker=FormatChecker()
    )
    evidence_validator = Draft202012Validator(
        evidence_schema, format_checker=FormatChecker()
    )

    for line_number, source in enumerate(source_records, start=1):
        record_path = Path(f"{source_path}:{line_number}")
        record_errors = sorted(
            source_validator.iter_errors(source), key=lambda item: list(item.path)
        )
        errors.extend(format_schema_error(record_path, error) for error in record_errors)

    for line_number, evidence in enumerate(evidence_records, start=1):
        record_path = Path(f"{evidence_path}:{line_number}")
        record_errors = sorted(
            evidence_validator.iter_errors(evidence), key=lambda item: list(item.path)
        )
        errors.extend(format_schema_error(record_path, error) for error in record_errors)

        evidence_id = str(evidence.get("evidence_id", f"line-{line_number}"))
        review = evidence.get("review", {})
        if review.get("status") == "verified":
            if not review.get("reviewed_at") or not review.get("reviewer"):
                errors.append(
                    f"{evidence_path}:{evidence_id}: verified review requires "
                    "reviewed_at and reviewer"
                )
        anchor_text = evidence.get("source_locator", {}).get("anchor_text")
        if anchor_text and anchor_text not in str(evidence.get("verbatim_text", "")):
            errors.append(
                f"{evidence_path}:{evidence_id}: anchor_text is absent from verbatim_text"
            )

    errors.extend(validate_target_links(source_records, evidence_records))

    allowed_source_root = (root / "data/sources").resolve()
    captured_file_count = 0
    verified_source_count = 0
    expected_media_types = {
        "html": "text/html",
        "pdf": "application/pdf",
        "png": "image/png",
        "doc": "application/msword",
        "xls": "application/vnd.ms-excel",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    source_text_by_id: dict[str, str] = {}
    for source in source_records:
        source_id = str(source.get("source_id", "<unknown>"))
        publisher_domain = str(source.get("publisher", {}).get("domain", "")).lower()
        canonical_host = (urlparse(str(source.get("canonical_url", ""))).hostname or "").lower()
        if publisher_domain and not host_matches_domain(canonical_host, publisher_domain):
            errors.append(
                f"{source_path}:{source_id}: canonical URL host {canonical_host!r} "
                f"does not match publisher domain {publisher_domain!r}"
            )

        review = source.get("review", {})
        if review.get("status") == "verified":
            verified_source_count += 1
            if not review.get("reviewed_at") or not review.get("reviewer"):
                errors.append(
                    f"{source_path}:{source_id}: verified review requires "
                    "reviewed_at and reviewer"
                )

        capture = source.get("capture", {})
        if capture.get("status") != "captured":
            continue
        captured_file_count += 1

        relative_path = str(capture.get("local_path", ""))
        local_path = (root / relative_path).resolve()
        if local_path == allowed_source_root or allowed_source_root not in local_path.parents:
            errors.append(
                f"{source_path}:{source_id}: local_path is outside data/sources"
            )
            continue
        if not local_path.is_file():
            errors.append(
                f"{source_path}:{source_id}: captured file is missing: {relative_path}"
            )
            continue

        content = local_path.read_bytes()
        recorded_length = capture.get("byte_length")
        if recorded_length != len(content):
            errors.append(
                f"{source_path}:{source_id}: byte_length={recorded_length}, "
                f"actual={len(content)}"
            )
        actual_sha256 = hashlib.sha256(content).hexdigest()
        if capture.get("content_sha256") != actual_sha256:
            errors.append(
                f"{source_path}:{source_id}: content_sha256 does not match local file"
            )

        content_format = str(source.get("content_format", ""))
        expected_media_type = expected_media_types.get(content_format)
        if expected_media_type and capture.get("media_type") != expected_media_type:
            errors.append(
                f"{source_path}:{source_id}: media_type={capture.get('media_type')!r}, "
                f"expected={expected_media_type!r}"
            )
        if content_format == "pdf" and not content.startswith(b"%PDF-"):
            errors.append(f"{source_path}:{source_id}: local file lacks PDF signature")
        if content_format == "html" and b"<html" not in content[:4096].lower():
            errors.append(f"{source_path}:{source_id}: local file lacks HTML signature")
        if content_format == "png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
            errors.append(f"{source_path}:{source_id}: local file lacks PNG signature")
        if content_format in {"doc", "xls"} and not content.startswith(
            b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
        ):
            errors.append(
                f"{source_path}:{source_id}: local file lacks OLE compound-file signature"
            )
        if content_format == "docx" and not content.startswith(b"PK\x03\x04"):
            errors.append(f"{source_path}:{source_id}: local file lacks OOXML ZIP signature")

        try:
            if content_format == "html":
                parser = _TextExtractor()
                parser.feed(content.decode("utf-8"))
                source_text_by_id[source_id] = compact_text(" ".join(parser.parts))
            elif content_format == "pdf":
                extracted_text = "\n".join(
                    page.extract_text() or ""
                    for page in PdfReader(local_path).pages
                )
                source_text_by_id[source_id] = compact_text(extracted_text)
        except Exception as exc:
            errors.append(
                f"{source_path}:{source_id}: saved-source text extraction failed: {exc}"
            )

        final_host = (urlparse(str(capture.get("final_url", ""))).hostname or "").lower()
        if publisher_domain and not host_matches_domain(final_host, publisher_domain):
            errors.append(
                f"{source_path}:{source_id}: final URL host {final_host!r} "
                f"does not match publisher domain {publisher_domain!r}"
            )

    source_located_evidence_count = 0
    for evidence in evidence_records:
        evidence_id = str(evidence.get("evidence_id", "<unknown>"))
        source_id = str(evidence.get("source_id", ""))
        source_text = source_text_by_id.get(source_id)
        if source_text is None:
            errors.append(
                f"{evidence_path}:{evidence_id}: source does not provide "
                "extractable saved text"
            )
            continue
        anchor_text = str(evidence.get("source_locator", {}).get("anchor_text", ""))
        if compact_text(anchor_text) not in source_text:
            errors.append(
                f"{evidence_path}:{evidence_id}: anchor_text is absent from "
                "the extracted saved source"
            )
            continue
        source_located_evidence_count += 1

    return errors, {
        "target_source_records": len(source_records),
        "captured_source_files": captured_file_count,
        "verified_source_records": verified_source_count,
        "target_evidence_units": len(evidence_records),
        "verified_target_evidence_units": sum(
            1
            for row in evidence_records
            if row.get("review", {}).get("status") == "verified"
        ),
        "source_located_evidence_units": source_located_evidence_count,
    }


def format_schema_error(path: Path, error: Any) -> str:
    location = ".".join(str(part) for part in error.absolute_path) or "<root>"
    return f"{path}:{location}: {error.message}"


def validate_schemas_and_fixtures(root: Path = ROOT) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    valid_count = 0
    invalid_count = 0

    for schema_name, fixtures in SCHEMA_FIXTURES.items():
        schema_path = root / "data" / "schemas" / schema_name
        try:
            schema = load_json(schema_path)
            Draft202012Validator.check_schema(schema)
        except Exception as exc:
            errors.append(f"{schema_path}: invalid schema: {exc}")
            continue

        validator = Draft202012Validator(schema, format_checker=FormatChecker())

        for relative_path in fixtures["valid"]:
            fixture_path = root / relative_path
            instance = load_json(fixture_path)
            fixture_errors = sorted(validator.iter_errors(instance), key=lambda item: list(item.path))
            if fixture_errors:
                errors.extend(format_schema_error(fixture_path, error) for error in fixture_errors)
            else:
                valid_count += 1

        for relative_path in fixtures["invalid"]:
            fixture_path = root / relative_path
            instance = load_json(fixture_path)
            fixture_errors = list(validator.iter_errors(instance))
            if not fixture_errors:
                errors.append(f"{fixture_path}: invalid fixture unexpectedly passed validation")
            else:
                invalid_count += 1

    valid_source = load_json(root / "tests/fixtures/data/valid/source-record.json")
    valid_evidence = load_json(root / "tests/fixtures/data/valid/evidence-unit.json")
    valid_link_errors = validate_target_links([valid_source], [valid_evidence])
    if valid_link_errors:
        errors.extend(
            f"tests/fixtures/data/valid: {message}" for message in valid_link_errors
        )

    unknown_source_evidence = load_json(
        root / "tests/fixtures/data/invalid/evidence-unit-unknown-source.json"
    )
    evidence_schema = load_json(root / "data/schemas/evidence-unit.schema.json")
    evidence_validator = Draft202012Validator(
        evidence_schema, format_checker=FormatChecker()
    )
    unknown_source_schema_errors = list(
        evidence_validator.iter_errors(unknown_source_evidence)
    )
    if unknown_source_schema_errors:
        errors.extend(
            format_schema_error(
                root / "tests/fixtures/data/invalid/evidence-unit-unknown-source.json",
                error,
            )
            for error in unknown_source_schema_errors
        )
    invalid_link_errors = validate_target_links([valid_source], [unknown_source_evidence])
    if not invalid_link_errors:
        errors.append(
            "tests/fixtures/data/invalid/evidence-unit-unknown-source.json: "
            "unknown source fixture unexpectedly passed link validation"
        )

    return errors, {
        "valid_fixtures_accepted": valid_count,
        "invalid_fixtures_rejected": invalid_count,
        "invalid_link_fixtures_rejected": 1 if invalid_link_errors else 0,
    }


def require_columns(
    actual: list[str],
    expected: list[str],
    path: Path,
    errors: list[str],
) -> None:
    if actual != expected:
        errors.append(
            f"{path}: columns differ from contract; expected {expected}, got {actual}"
        )


def check_enum(
    row: dict[str, str],
    field: str,
    allowed: set[str],
    identity: str,
    path: Path,
    errors: list[str],
) -> None:
    if row.get(field, "") not in allowed:
        errors.append(
            f"{path}:{identity}: {field}={row.get(field)!r} is not one of {sorted(allowed)}"
        )


def validate_repository_audits(root: Path = ROOT) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    manifest_path = root / "data" / "raw" / "source_manifest.json"
    evidence_path = root / "data" / "evidence" / "evidence_units.jsonl"
    source_audit_path = root / "data" / "audit" / "source-audit.csv"
    evidence_audit_path = root / "data" / "audit" / "evidence-audit.csv"
    target_evidence_path = root / TARGET_EVIDENCE_RECORDS_PATH

    manifest = load_json(manifest_path)
    if not isinstance(manifest, list):
        return [f"{manifest_path}: expected a JSON array"], {}
    evidence_rows = load_jsonl(evidence_path)
    target_evidence_rows = (
        load_jsonl(target_evidence_path) if target_evidence_path.is_file() else []
    )
    source_headers, source_audit = load_csv(source_audit_path)
    evidence_headers, evidence_audit = load_csv(evidence_audit_path)

    require_columns(source_headers, SOURCE_AUDIT_COLUMNS, source_audit_path, errors)
    require_columns(evidence_headers, EVIDENCE_AUDIT_COLUMNS, evidence_audit_path, errors)

    source_ids = [str(row.get("source_id", "")) for row in manifest]
    source_urls = [str(row.get("source_url", "")) for row in manifest]
    evidence_ids = [str(row.get("evidence_id", "")) for row in evidence_rows]
    source_audit_ids = [row.get("source_id", "") for row in source_audit]
    evidence_audit_ids = [row.get("evidence_id", "") for row in evidence_audit]

    for label, values, path in [
        ("source_id", source_ids, manifest_path),
        ("source_url", source_urls, manifest_path),
        ("evidence_id", evidence_ids, evidence_path),
        ("source audit source_id", source_audit_ids, source_audit_path),
        ("evidence audit evidence_id", evidence_audit_ids, evidence_audit_path),
    ]:
        duplicates = duplicate_values(values)
        if duplicates:
            errors.append(f"{path}: duplicate {label} values: {duplicates}")

    sources_by_id = {row["source_id"]: row for row in manifest if row.get("source_id")}
    sources_by_url = {row["source_url"]: row for row in manifest if row.get("source_url")}
    evidence_by_id = {row["evidence_id"]: row for row in evidence_rows if row.get("evidence_id")}
    target_evidence_ids = {
        str(row["evidence_id"])
        for row in target_evidence_rows
        if row.get("evidence_id")
    }
    source_audit_by_id = {row["source_id"]: row for row in source_audit if row.get("source_id")}
    evidence_audit_by_id = {
        row["evidence_id"]: row for row in evidence_audit if row.get("evidence_id")
    }

    if set(source_audit_by_id) != set(sources_by_id):
        errors.append(
            f"{source_audit_path}: source IDs must exactly match source_manifest.json; "
            f"missing={sorted(set(sources_by_id) - set(source_audit_by_id))}, "
            f"extra={sorted(set(source_audit_by_id) - set(sources_by_id))}"
        )
    if set(evidence_audit_by_id) != set(evidence_by_id):
        errors.append(
            f"{evidence_audit_path}: evidence IDs must exactly match evidence_units.jsonl; "
            f"missing={sorted(set(evidence_by_id) - set(evidence_audit_by_id))}, "
            f"extra={sorted(set(evidence_audit_by_id) - set(evidence_by_id))}"
        )

    evidence_count_by_url = Counter(str(row.get("source_url", "")) for row in evidence_rows)

    for source_id, source in sources_by_id.items():
        audit = source_audit_by_id.get(source_id)
        if not audit:
            continue
        if audit["title"] != str(source.get("title", "")):
            errors.append(f"{source_audit_path}:{source_id}: title differs from manifest")
        if audit["source_url"] != str(source.get("source_url", "")):
            errors.append(f"{source_audit_path}:{source_id}: source_url differs from manifest")
        try:
            recorded_count = int(audit["evidence_count"])
        except ValueError:
            errors.append(
                f"{source_audit_path}:{source_id}: evidence_count is not an integer"
            )
        else:
            actual_count = evidence_count_by_url[str(source.get("source_url", ""))]
            if recorded_count != actual_count:
                errors.append(
                    f"{source_audit_path}:{source_id}: evidence_count={recorded_count}, "
                    f"actual={actual_count}"
                )

        check_enum(
            audit,
            "publish_date_status",
            {"known", "missing", "needs_verification"},
            source_id,
            source_audit_path,
            errors,
        )
        check_enum(
            audit,
            "snapshot_status",
            {"missing", "captured", "failed", "not_permitted"},
            source_id,
            source_audit_path,
            errors,
        )
        check_enum(
            audit,
            "locator_status",
            {"missing", "partial", "complete"},
            source_id,
            source_audit_path,
            errors,
        )
        check_enum(
            audit,
            "version_status",
            {"unknown", "current", "historical", "superseded", "time_bounded"},
            source_id,
            source_audit_path,
            errors,
        )
        check_enum(
            audit,
            "content_review_status",
            {"not_started", "in_review", "verified", "rejected"},
            source_id,
            source_audit_path,
            errors,
        )
        check_enum(
            audit,
            "priority",
            {"P0", "P1", "P2"},
            source_id,
            source_audit_path,
            errors,
        )
        check_enum(
            audit,
            "review_status",
            {"pending", "in_review", "verified", "rejected"},
            source_id,
            source_audit_path,
            errors,
        )
        if not audit["next_action"].strip():
            errors.append(f"{source_audit_path}:{source_id}: next_action must not be empty")

    marked_mismatches: set[str] = set()
    migrated_legacy_rows = 0
    for evidence_id, evidence in evidence_by_id.items():
        audit = evidence_audit_by_id.get(evidence_id)
        if not audit:
            continue

        source_url = str(evidence.get("source_url", ""))
        source = sources_by_url.get(source_url)
        if not source:
            errors.append(
                f"{evidence_path}:{evidence_id}: source_url is absent from source_manifest.json"
            )
            continue

        expected_source_id = str(source["source_id"])
        if audit["source_id"] != expected_source_id:
            errors.append(
                f"{evidence_audit_path}:{evidence_id}: source_id={audit['source_id']}, "
                f"expected={expected_source_id}"
            )
        if audit["item_id"] != str(evidence.get("item_id", "")):
            errors.append(
                f"{evidence_audit_path}:{evidence_id}: item_id differs from evidence data"
            )
        if str(evidence.get("source_title", "")) != str(source.get("title", "")):
            errors.append(
                f"{evidence_path}:{evidence_id}: source_title differs from source manifest"
            )

        expected_publish_status = "present" if evidence.get("publish_date") else "missing"
        if audit["legacy_publish_date_status"] != expected_publish_status:
            errors.append(
                f"{evidence_audit_path}:{evidence_id}: legacy_publish_date_status="
                f"{audit['legacy_publish_date_status']}, expected={expected_publish_status}"
            )

        check_enum(
            audit,
            "legacy_locator_status",
            {"missing", "descriptive_only", "verifiable"},
            evidence_id,
            evidence_audit_path,
            errors,
        )
        check_enum(
            audit,
            "verbatim_text_status",
            {"missing", "present", "verified"},
            evidence_id,
            evidence_audit_path,
            errors,
        )
        check_enum(
            audit,
            "claim_review_status",
            {"pending", "in_review", "verified", "known_mismatch", "rejected"},
            evidence_id,
            evidence_audit_path,
            errors,
        )
        check_enum(
            audit,
            "priority",
            {"P0", "P1", "P2"},
            evidence_id,
            evidence_audit_path,
            errors,
        )
        check_enum(
            audit,
            "review_status",
            {"pending", "in_review", "verified", "rejected"},
            evidence_id,
            evidence_audit_path,
            errors,
        )
        check_enum(
            audit,
            "migration_status",
            {"pending", "in_progress", "migrated", "not_applicable", "rejected"},
            evidence_id,
            evidence_audit_path,
            errors,
        )
        if audit["claim_review_status"] == "known_mismatch":
            marked_mismatches.add(evidence_id)
        if not audit["next_action"].strip():
            errors.append(f"{evidence_audit_path}:{evidence_id}: next_action must not be empty")

        target_ids = [
            value.strip()
            for value in audit.get("target_evidence_ids", "").split("|")
            if value.strip()
        ]
        duplicate_target_ids = duplicate_values(target_ids)
        if duplicate_target_ids:
            errors.append(
                f"{evidence_audit_path}:{evidence_id}: duplicate target_evidence_ids "
                f"{duplicate_target_ids}"
            )
        unknown_target_ids = sorted(set(target_ids) - target_evidence_ids)
        if unknown_target_ids:
            errors.append(
                f"{evidence_audit_path}:{evidence_id}: unknown target_evidence_ids "
                f"{unknown_target_ids}"
            )

        migration_status = audit["migration_status"]
        if migration_status == "migrated":
            migrated_legacy_rows += 1
            if not target_ids:
                errors.append(
                    f"{evidence_audit_path}:{evidence_id}: migrated row requires "
                    "target_evidence_ids"
                )
            if audit["review_status"] != "verified":
                errors.append(
                    f"{evidence_audit_path}:{evidence_id}: migrated row requires "
                    "review_status=verified"
                )
            if audit["verbatim_text_status"] != "verified":
                errors.append(
                    f"{evidence_audit_path}:{evidence_id}: migrated row requires "
                    "verbatim_text_status=verified"
                )
        elif migration_status in {"pending", "not_applicable", "rejected"} and target_ids:
            errors.append(
                f"{evidence_audit_path}:{evidence_id}: {migration_status} row must not "
                "declare target_evidence_ids"
            )

    if marked_mismatches != KNOWN_MISMATCH_IDS:
        errors.append(
            f"{evidence_audit_path}: known mismatches must be exactly "
            f"{sorted(KNOWN_MISMATCH_IDS)}; got {sorted(marked_mismatches)}"
        )

    return errors, {
        "manifest_sources": len(manifest),
        "legacy_evidence_units": len(evidence_rows),
        "source_audit_rows": len(source_audit),
        "evidence_audit_rows": len(evidence_audit),
        "legacy_missing_publish_date": sum(
            1 for row in evidence_rows if not row.get("publish_date")
        ),
        "known_mismatch_rows": len(marked_mismatches),
        "migrated_legacy_rows": migrated_legacy_rows,
        "legacy_unmigrated_rows": sum(
            1 for row in evidence_audit if row.get("migration_status") != "migrated"
        ),
    }


def validate_stage1_completion_artifacts(
    root: Path = ROOT,
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    survey_path = root / CANDIDATE_SURVEY_PATH
    review_path = root / SECOND_REVIEW_PATH
    report_path = root / STAGE_1_AUDIT_REPORT_PATH
    evidence_path = root / TARGET_EVIDENCE_RECORDS_PATH
    evidence_audit_path = root / "data/audit/evidence-audit.csv"

    required_paths = [
        survey_path,
        review_path,
        report_path,
        evidence_path,
        evidence_audit_path,
    ]
    missing_paths = [path for path in required_paths if not path.is_file()]
    if missing_paths:
        return [f"{path}: required stage 1 artifact is missing" for path in missing_paths], {}

    survey_headers, survey_rows = load_csv(survey_path)
    review_headers, review_rows = load_csv(review_path)
    evidence_rows = load_jsonl(evidence_path)
    _, evidence_audit_rows = load_csv(evidence_audit_path)
    evidence_by_id = {row["evidence_id"]: row for row in evidence_rows}

    require_columns(survey_headers, CANDIDATE_SURVEY_COLUMNS, survey_path, errors)
    require_columns(review_headers, SECOND_REVIEW_COLUMNS, review_path, errors)

    if len(survey_rows) != 9:
        errors.append(f"{survey_path}: expected 9 candidate rows, got {len(survey_rows)}")
    candidate_ids = [row.get("candidate_id", "") for row in survey_rows]
    duplicate_candidate_ids = duplicate_values(candidate_ids)
    if duplicate_candidate_ids:
        errors.append(
            f"{survey_path}: duplicate candidate_id values: {duplicate_candidate_ids}"
        )
    if set(candidate_ids) != STAGE_1_CANDIDATE_IDS:
        errors.append(
            f"{survey_path}: candidate coverage differs; expected "
            f"{sorted(STAGE_1_CANDIDATE_IDS)}, got {sorted(set(candidate_ids))}"
        )

    verified_baselines = {
        row.get("candidate_id", "")
        for row in survey_rows
        if row.get("data_baseline_status") == "已验证"
    }
    if verified_baselines != {"UG_PROOF_PRINT", "UG_STATUS_CHANGE"}:
        errors.append(
            f"{survey_path}: verified data baselines must be UG_PROOF_PRINT and "
            f"UG_STATUS_CHANGE; got {sorted(verified_baselines)}"
        )

    score_fields = {
        "evidence_completeness_score",
        "condition_branch_score",
        "version_risk_score",
        "evaluation_value_score",
        "annotation_cost_score",
    }
    for row in survey_rows:
        candidate_id = row.get("candidate_id", "<unknown>")
        check_enum(
            row,
            "data_baseline_status",
            {"已验证", "计划"},
            candidate_id,
            survey_path,
            errors,
        )
        if row.get("survey_status") != "已验证":
            errors.append(
                f"{survey_path}:{candidate_id}: survey_status must be 已验证"
            )
        check_enum(
            row,
            "stage_2_option_group",
            {"已冻结基线", "优先扩展", "条件分支扩展", "流程对照"},
            candidate_id,
            survey_path,
            errors,
        )
        try:
            checked_at = date.fromisoformat(row.get("source_checked_at", ""))
        except ValueError:
            errors.append(
                f"{survey_path}:{candidate_id}: source_checked_at must be an ISO date"
            )
        else:
            if checked_at > date.today():
                errors.append(
                    f"{survey_path}:{candidate_id}: source_checked_at is in the future"
                )

        urls = [
            value.strip()
            for value in row.get("official_source_urls", "").split("|")
            if value.strip()
        ]
        if not urls:
            errors.append(
                f"{survey_path}:{candidate_id}: official_source_urls must not be empty"
            )
        for url in urls:
            parsed = urlparse(url)
            if (
                parsed.scheme != "https"
                or parsed.hostname not in {"jwc.jnu.edu.cn", "gs.jnu.edu.cn"}
            ):
                errors.append(
                    f"{survey_path}:{candidate_id}: unsupported official URL {url!r}"
                )

        for field in score_fields:
            try:
                score = int(row.get(field, ""))
            except ValueError:
                errors.append(
                    f"{survey_path}:{candidate_id}: {field} must be an integer"
                )
            else:
                if score not in range(4):
                    errors.append(
                        f"{survey_path}:{candidate_id}: {field} must be between 0 and 3"
                    )

        for field in {
            "candidate_name",
            "source_availability",
            "observed_evidence",
            "remaining_gap",
            "stage_2_option_group",
        }:
            if not row.get(field, "").strip():
                errors.append(
                    f"{survey_path}:{candidate_id}: {field} must not be empty"
                )

    if len(review_rows) != 30:
        errors.append(f"{review_path}: expected 30 review rows, got {len(review_rows)}")
    for field in ("review_id", "evidence_id"):
        duplicates = duplicate_values([row.get(field, "") for row in review_rows])
        if duplicates:
            errors.append(f"{review_path}: duplicate {field} values: {duplicates}")

    reviewed_source_ids = {row.get("source_id", "") for row in review_rows}
    if reviewed_source_ids != STAGE_1_EVIDENCE_SOURCE_IDS:
        errors.append(
            f"{review_path}: reviewed source coverage differs; expected "
            f"{sorted(STAGE_1_EVIDENCE_SOURCE_IDS)}, got {sorted(reviewed_source_ids)}"
        )

    reviewed_evidence_ids: set[str] = set()
    for row in review_rows:
        review_id = row.get("review_id", "<unknown>")
        evidence_id = row.get("evidence_id", "")
        target = evidence_by_id.get(evidence_id)
        if target is None:
            errors.append(
                f"{review_path}:{review_id}: unknown evidence_id {evidence_id!r}"
            )
        elif target.get("source_id") != row.get("source_id"):
            errors.append(
                f"{review_path}:{review_id}: source_id differs from target evidence"
            )
        reviewed_evidence_ids.add(evidence_id)

        for field in {
            "locator_recheck",
            "verbatim_recheck",
            "claim_recheck",
            "applicability_recheck",
        }:
            if row.get(field) != "通过":
                errors.append(f"{review_path}:{review_id}: {field} must be 通过")
        if row.get("result") != "已验证":
            errors.append(f"{review_path}:{review_id}: result must be 已验证")
        try:
            datetime.fromisoformat(row.get("reviewed_at", ""))
        except ValueError:
            errors.append(
                f"{review_path}:{review_id}: reviewed_at must be an ISO datetime"
            )
        for field in {"selection_reason", "reviewer", "notes"}:
            if not row.get(field, "").strip():
                errors.append(
                    f"{review_path}:{review_id}: {field} must not be empty"
                )

    for audit in evidence_audit_rows:
        if audit.get("claim_review_status") != "known_mismatch":
            continue
        mapped_ids = {
            value.strip()
            for value in audit.get("target_evidence_ids", "").split("|")
            if value.strip()
        }
        if not reviewed_evidence_ids & mapped_ids:
            errors.append(
                f"{review_path}: known mismatch {audit.get('evidence_id')} "
                "is absent from second-review coverage"
            )

    report_text = report_path.read_text(encoding="utf-8")
    for marker in {
        "# 阶段 1 数据审计报告",
        "30 条旧证据",
        "136 条目标证据",
        "第二次独立复核",
        "候选事项普查",
        "阶段 1 验收结论",
    }:
        if marker not in report_text:
            errors.append(f"{report_path}: missing required marker {marker!r}")

    return errors, {
        "candidate_items_surveyed": len(survey_rows),
        "second_review_rows": len(review_rows),
        "stage1_audit_reports": 1,
    }


def validate_stage2a_contract(
    root: Path = ROOT,
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    plan_path = root / STAGE_2_EVALUATION_PLAN_PATH
    blueprint_path = root / STAGE_2_EVALUATION_BLUEPRINT_PATH
    source_plan_path = root / STAGE_2_SOURCE_PLAN_PATH
    guide_path = root / STAGE_2_ANNOTATION_GUIDE_PATH
    survey_path = root / CANDIDATE_SURVEY_PATH
    evidence_path = root / TARGET_EVIDENCE_RECORDS_PATH
    process_fixture_path = (
        root / "tests/fixtures/data/valid/process-record.json"
    )
    sample_fixture_path = (
        root / "tests/fixtures/data/valid/evaluation-sample.json"
    )
    review_fixture_path = (
        root / "tests/fixtures/data/valid/evaluation-review-record.json"
    )
    builder_path = root / "scripts/build_stage2a_blueprint.py"
    decisions_path = root / "docs/project/DECISIONS.md"
    project_plan_path = root / "docs/project/PROJECT_PLAN.md"

    required_paths = [
        plan_path,
        blueprint_path,
        source_plan_path,
        guide_path,
        survey_path,
        evidence_path,
        process_fixture_path,
        sample_fixture_path,
        review_fixture_path,
        builder_path,
        decisions_path,
        project_plan_path,
    ]
    missing_paths = [path for path in required_paths if not path.is_file()]
    if missing_paths:
        return [
            f"{path}: required stage 2A artifact is missing"
            for path in missing_paths
        ], {}

    try:
        plan = load_json(plan_path)
        process_fixture = load_json(process_fixture_path)
        sample_fixture = load_json(sample_fixture_path)
        review_fixture = load_json(review_fixture_path)
        evidence_records = load_jsonl(evidence_path)
        blueprint_headers, blueprint_rows = load_csv(blueprint_path)
        source_plan_headers, source_plan_rows = load_csv(source_plan_path)
        _, survey_rows = load_csv(survey_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)], {}

    plan_schema = load_json(root / "data/schemas/evaluation-plan.schema.json")
    plan_validator = Draft202012Validator(
        plan_schema, format_checker=FormatChecker()
    )
    plan_errors = sorted(
        plan_validator.iter_errors(plan), key=lambda item: list(item.path)
    )
    errors.extend(format_schema_error(plan_path, error) for error in plan_errors)

    formal_item_rows = plan.get("formal_items", [])
    formal_items_by_id = {
        str(row.get("item_id", "")): row for row in formal_item_rows
    }
    duplicate_formal_ids = duplicate_values(
        [str(row.get("item_id", "")) for row in formal_item_rows]
    )
    if duplicate_formal_ids:
        errors.append(
            f"{plan_path}: duplicate formal item IDs: {duplicate_formal_ids}"
        )
    if set(formal_items_by_id) != set(STAGE_2_FORMAL_ITEMS):
        errors.append(
            f"{plan_path}: formal item coverage differs; expected "
            f"{sorted(STAGE_2_FORMAL_ITEMS)}, got "
            f"{sorted(formal_items_by_id)}"
        )
    for item_id, (code, name, baseline_status) in STAGE_2_FORMAL_ITEMS.items():
        row = formal_items_by_id.get(item_id, {})
        expected_values = {
            "item_code": code,
            "item_name": name,
            "sample_quota": 25,
            "data_baseline_status": baseline_status,
        }
        for field, expected in expected_values.items():
            if row.get(field) != expected:
                errors.append(
                    f"{plan_path}:{item_id}: {field}={row.get(field)!r}, "
                    f"expected={expected!r}"
                )

    transfer_ids = {
        str(row.get("item_id", ""))
        for row in plan.get("transfer_candidates", [])
    }
    if transfer_ids != {"UG_GRADUATION_INTERNSHIP"}:
        errors.append(
            f"{plan_path}: transfer candidate must be "
            "UG_GRADUATION_INTERNSHIP"
        )

    require_columns(
        blueprint_headers,
        STAGE_2_BLUEPRINT_COLUMNS,
        blueprint_path,
        errors,
    )
    if len(blueprint_rows) != 200:
        errors.append(
            f"{blueprint_path}: expected 200 allocation rows, "
            f"got {len(blueprint_rows)}"
        )
    sample_ids = [row.get("sample_id", "") for row in blueprint_rows]
    duplicate_sample_ids = duplicate_values(sample_ids)
    if duplicate_sample_ids:
        errors.append(
            f"{blueprint_path}: duplicate sample IDs: {duplicate_sample_ids}"
        )

    rows_by_item: dict[str, list[dict[str, str]]] = {
        item_id: [] for item_id in STAGE_2_FORMAL_ITEMS
    }
    for row in blueprint_rows:
        sample_id = row.get("sample_id", "<unknown>")
        item_id = row.get("item_id", "")
        expected_item = STAGE_2_FORMAL_ITEMS.get(item_id)
        if expected_item is None:
            errors.append(
                f"{blueprint_path}:{sample_id}: unknown item_id {item_id!r}"
            )
            continue
        rows_by_item[item_id].append(row)
        item_code = expected_item[0]
        if row.get("item_code") != item_code:
            errors.append(
                f"{blueprint_path}:{sample_id}: item_code must be "
                f"{item_code!r}"
            )
        if not re.fullmatch(
            rf"S2E-{re.escape(item_code)}-[0-9]{{3}}",
            sample_id,
        ):
            errors.append(
                f"{blueprint_path}:{sample_id}: sample ID does not match "
                "its item code"
            )

        scenario_type = row.get("scenario_type", "")
        expected_mode = STAGE_2_SCENARIO_RESPONSE_MODES.get(scenario_type)
        if expected_mode is None:
            errors.append(
                f"{blueprint_path}:{sample_id}: unsupported scenario_type "
                f"{scenario_type!r}"
            )
        elif row.get("expected_response_mode") != expected_mode:
            errors.append(
                f"{blueprint_path}:{sample_id}: expected_response_mode must "
                f"be {expected_mode!r}"
            )
        if (
            scenario_type == "version_conflict"
            and row.get("version_risk") != "cross_version_conflict"
        ):
            errors.append(
                f"{blueprint_path}:{sample_id}: version_conflict requires "
                "cross_version_conflict risk"
            )
        expected_turn_structure = (
            "multi_turn" if scenario_type == "multi_turn" else "single_turn"
        )
        if row.get("turn_structure") != expected_turn_structure:
            errors.append(
                f"{blueprint_path}:{sample_id}: turn_structure must be "
                f"{expected_turn_structure!r}"
            )
        if row.get("annotation_status") != "planned":
            errors.append(
                f"{blueprint_path}:{sample_id}: annotation_status must be planned"
            )
        if row.get("content_freeze_status") != "not_frozen":
            errors.append(
                f"{blueprint_path}:{sample_id}: content_freeze_status must "
                "be not_frozen during stage 2A"
            )

    expected_per_item_counts = {
        "scenario_type": {
            "direct": 4,
            "condition_missing": 4,
            "object_mismatch": 3,
            "version_conflict": 3,
            "step_error": 3,
            "material_confusion": 3,
            "out_of_scope": 2,
            "multi_turn": 3,
        },
        "difficulty": {
            "easy": 6,
            "medium": 12,
            "hard": 7,
        },
        "version_risk": {
            "stable": 13,
            "version_sensitive": 9,
            "cross_version_conflict": 3,
        },
        "turn_structure": {
            "single_turn": 22,
            "multi_turn": 3,
        },
    }
    for item_id, item_rows in rows_by_item.items():
        code = STAGE_2_FORMAL_ITEMS[item_id][0]
        expected_ids = {
            f"S2E-{code}-{index:03d}" for index in range(1, 26)
        }
        actual_ids = {row.get("sample_id", "") for row in item_rows}
        if actual_ids != expected_ids:
            errors.append(
                f"{blueprint_path}:{item_id}: sample ID sequence differs; "
                f"missing={sorted(expected_ids - actual_ids)}, "
                f"extra={sorted(actual_ids - expected_ids)}"
            )
        for field, expected_counts in expected_per_item_counts.items():
            actual_counts = dict(
                sorted(Counter(row.get(field, "") for row in item_rows).items())
            )
            if actual_counts != expected_counts:
                errors.append(
                    f"{blueprint_path}:{item_id}: {field} counts "
                    f"{actual_counts}, expected {expected_counts}"
                )

    actual_allocation = {
        "per_item": dict(
            sorted(Counter(row.get("item_id", "") for row in blueprint_rows).items())
        ),
        **{
            field: dict(
                sorted(
                    Counter(
                        row.get(field, "") for row in blueprint_rows
                    ).items()
                )
            )
            for field in STAGE_2_EXPECTED_COUNTS
        },
    }
    if actual_allocation["per_item"] != {
        item_id: 25 for item_id in sorted(STAGE_2_FORMAL_ITEMS)
    }:
        errors.append(
            f"{blueprint_path}: per-item allocation must be 25 for every "
            "formal item"
        )
    for field, expected_counts in STAGE_2_EXPECTED_COUNTS.items():
        if actual_allocation[field] != expected_counts:
            errors.append(
                f"{blueprint_path}: {field} counts "
                f"{actual_allocation[field]}, expected {expected_counts}"
            )
    recorded_allocation = plan.get("allocation", {})
    for field, actual_counts in actual_allocation.items():
        if recorded_allocation.get(field) != actual_counts:
            errors.append(
                f"{plan_path}: allocation.{field} differs from blueprint"
            )
    blueprint_sha256 = hashlib.sha256(blueprint_path.read_bytes()).hexdigest()
    if recorded_allocation.get("blueprint_sha256") != blueprint_sha256:
        errors.append(
            f"{plan_path}: blueprint_sha256 differs from allocation file"
        )

    review_policy = plan.get("review_policy", {})
    if review_policy.get("second_review_coverage") != 1.0:
        errors.append(
            f"{plan_path}: second_review_coverage must be 1.0"
        )
    if not review_policy.get("reviewer_identity_must_differ"):
        errors.append(
            f"{plan_path}: independent reviewers must have different identities"
        )
    if review_policy.get("unresolved_disagreements_allowed_at_freeze") is not False:
        errors.append(
            f"{plan_path}: unresolved disagreements must be forbidden at freeze"
        )
    freeze_policy = plan.get("freeze_policy", {})
    if freeze_policy.get("content_freeze_status") not in {"pending", "frozen"}:
        errors.append(
            f"{plan_path}: content freeze must remain pending during stage 2A"
        )
    if freeze_policy.get("content_freeze_status") == "pending" and freeze_policy.get("content_freeze_version") is not None:
        errors.append(
            f"{plan_path}: content freeze version must remain null during stage 2A"
        )

    require_columns(
        source_plan_headers,
        STAGE_2_SOURCE_PLAN_COLUMNS,
        source_plan_path,
        errors,
    )
    expected_source_plan_ids = (
        set(STAGE_2_FORMAL_ITEMS)
        - {"UG_PROOF_PRINT", "UG_STATUS_CHANGE"}
        | {"UG_GRADUATION_INTERNSHIP"}
    )
    actual_source_plan_ids = {
        row.get("item_id", "") for row in source_plan_rows
    }
    if len(source_plan_rows) != 7:
        errors.append(
            f"{source_plan_path}: expected 7 source migration rows, "
            f"got {len(source_plan_rows)}"
        )
    if actual_source_plan_ids != expected_source_plan_ids:
        errors.append(
            f"{source_plan_path}: item coverage differs; expected "
            f"{sorted(expected_source_plan_ids)}, got "
            f"{sorted(actual_source_plan_ids)}"
        )
    for field in ("plan_id", "item_id"):
        duplicates = duplicate_values(
            [row.get(field, "") for row in source_plan_rows]
        )
        if duplicates:
            errors.append(
                f"{source_plan_path}: duplicate {field} values: {duplicates}"
            )

    survey_by_id = {
        row.get("candidate_id", ""): row for row in survey_rows
    }
    allowed_source_roles = {
        "guide",
        "notice",
        "form",
        "process",
        "policy",
        "service_page",
    }
    allowed_claim_types = {
        "applicable_audience",
        "entry",
        "precondition",
        "step",
        "material",
        "time_constraint",
        "service_location",
        "fee",
        "contact",
        "exception",
        "consequence",
        "conflict",
        "note",
    }
    for row in source_plan_rows:
        plan_id = row.get("plan_id", "<unknown>")
        item_id = row.get("item_id", "")
        expected_scope_role = (
            "迁移评测候选"
            if item_id == "UG_GRADUATION_INTERNSHIP"
            else "正式扩展"
        )
        if row.get("scope_role") != expected_scope_role:
            errors.append(
                f"{source_plan_path}:{plan_id}: scope_role must be "
                f"{expected_scope_role}"
            )
        completed_plan_ids = {"S2SRC001", "S2SRC002", "S2SRC003", "S2SRC004", "S2SRC005", "S2SRC006"}
        expected_statuses = {"已验证"} if plan_id in completed_plan_ids else {"计划"}
        if row.get("status") not in expected_statuses:
            errors.append(
                f"{source_plan_path}:{plan_id}: status must be "
                f"one of {sorted(expected_statuses)}"
            )
        if row.get("priority") not in {"P0", "P1", "P2"}:
            errors.append(
                f"{source_plan_path}:{plan_id}: unsupported priority"
            )
        survey_urls = {
            value.strip()
            for value in survey_by_id.get(item_id, {}).get(
                "official_source_urls", ""
            ).split("|")
            if value.strip()
        }
        planned_urls = {
            value.strip()
            for value in row.get("official_source_urls", "").split("|")
            if value.strip()
        }
        if planned_urls != survey_urls:
            errors.append(
                f"{source_plan_path}:{plan_id}: official URLs differ from "
                "candidate survey"
            )
        source_roles = {
            value.strip()
            for value in row.get("required_source_roles", "").split("|")
            if value.strip()
        }
        unknown_roles = sorted(source_roles - allowed_source_roles)
        if not source_roles or unknown_roles:
            errors.append(
                f"{source_plan_path}:{plan_id}: invalid source roles "
                f"{unknown_roles}"
            )
        claim_types = {
            value.strip()
            for value in row.get("required_claim_types", "").split("|")
            if value.strip()
        }
        unknown_claim_types = sorted(claim_types - allowed_claim_types)
        if not claim_types or unknown_claim_types:
            errors.append(
                f"{source_plan_path}:{plan_id}: invalid claim types "
                f"{unknown_claim_types}"
            )
        for field in {
            "item_name",
            "version_questions",
            "acceptance_gate",
        }:
            if not row.get(field, "").strip():
                errors.append(
                    f"{source_plan_path}:{plan_id}: {field} must not be empty"
                )

    errors.extend(
        validate_stage2_fixture_links(
            process_fixture,
            sample_fixture,
            review_fixture,
            evidence_records,
        )
    )

    guide_text = guide_path.read_text(encoding="utf-8")
    for marker in {
        "# 阶段 2 流程结构与评测标注规范",
        "状态：已验证",
        "Q-003",
        "8 类正式事项",
        "200 条",
        "100% 第二次独立复核",
        "流程记录标注",
        "评测样本标注",
        "分歧裁决",
        "版本冻结",
        "数据泄漏检查",
        "正例",
        "反例",
    }:
        if marker not in guide_text:
            errors.append(
                f"{guide_path}: missing required marker {marker!r}"
            )

    decisions_text = decisions_path.read_text(encoding="utf-8")
    for marker in {
        "### D-017 阶段 2 正式范围与冻结评测复核口径",
        "### Q-003 阶段 2 事项范围、样本规模与复核比例",
        "状态：已由用户明确确认并由 D-017 解决",
    }:
        if marker not in decisions_text:
            errors.append(
                f"{decisions_path}: missing stage 2A decision marker {marker!r}"
            )
    project_plan_text = project_plan_path.read_text(encoding="utf-8")
    for marker in {
        "### 阶段 2：流程结构与评测基准",
        "状态：进行中",
        "阶段 2A“流程模式、标注与冻结契约”已验证",
    }:
        if marker not in project_plan_text:
            errors.append(
                f"{project_plan_path}: missing stage 2A status marker {marker!r}"
            )

    return errors, {
        "stage2_formal_items": len(formal_items_by_id),
        "stage2_allocated_samples": len(blueprint_rows),
        "stage2_source_migration_rows": len(source_plan_rows),
        "stage2_second_review_target_percent": int(
            float(review_policy.get("second_review_coverage", 0)) * 100
        ),
        "stage2_allocation_frozen": (
            1 if plan.get("status") in {"allocation_frozen", "content_frozen"} else 0
        ),
        "stage2_content_frozen": (
            1
            if freeze_policy.get("content_freeze_status") == "frozen"
            else 0
        ),
        "stage2_fixture_link_sets_validated": 1,
    }


def validate_stage2b_withdrawal_contract(
    root: Path = ROOT,
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    source_path = root / TARGET_SOURCE_RECORDS_PATH
    evidence_path = root / TARGET_EVIDENCE_RECORDS_PATH
    process_path = root / STAGE_2B_WITHDRAWAL_PROCESS_PATH
    review_path = root / STAGE_2B_WITHDRAWAL_SECOND_REVIEW_PATH
    examples_path = root / STAGE_2B_WITHDRAWAL_EXAMPLES_PATH
    source_plan_path = root / STAGE_2_SOURCE_PLAN_PATH
    capture_plan_path = root / "data/research/source_capture_plan.json"
    baseline_path = root / "docs/data/STAGE_2B_WITHDRAWAL_BASELINE.md"
    report_path = (
        root
        / "docs/work-reports/"
        "2026-07-30-008-stage-2b-withdrawal-baseline.md"
    )
    decisions_path = root / "docs/project/DECISIONS.md"
    project_plan_path = root / "docs/project/PROJECT_PLAN.md"
    project_memory_path = root / "docs/project/PROJECT_MEMORY.md"
    generator_path = root / "scripts/complete_stage2b_withdrawal.py"
    required_paths = [
        source_path,
        evidence_path,
        process_path,
        review_path,
        examples_path,
        source_plan_path,
        capture_plan_path,
        baseline_path,
        report_path,
        decisions_path,
        project_plan_path,
        project_memory_path,
        generator_path,
        root / "data/schemas/process-record.schema.json",
    ]
    missing_paths = [path for path in required_paths if not path.is_file()]
    if missing_paths:
        return [
            f"{path}: required stage 2B withdrawal artifact is missing"
            for path in missing_paths
        ], {}

    try:
        source_records = load_jsonl(source_path)
        evidence_records = load_jsonl(evidence_path)
        all_process_records = load_jsonl(process_path)
        review_headers, review_rows = load_csv(review_path)
        examples = load_json(examples_path)
        capture_plan = load_json(capture_plan_path)
        _, source_plan_rows = load_csv(source_plan_path)
        process_schema = load_json(
            root / "data/schemas/process-record.schema.json"
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)], {}

    source_by_id = {
        str(row.get("source_id", "")): row for row in source_records
    }
    capture_plan_records = capture_plan.get("records", [])
    withdrawal_capture_plan_by_id = {
        str(row.get("source_id", "")): row
        for row in capture_plan_records
        if str(row.get("source_id", "")).startswith(
            "SRC_UG_WITHDRAWAL"
        )
    }
    if (
        set(withdrawal_capture_plan_by_id)
        != STAGE_2B_WITHDRAWAL_SOURCE_IDS
    ):
        errors.append(
            f"{capture_plan_path}: withdrawal capture-plan coverage differs"
        )
    for source_id in STAGE_2B_WITHDRAWAL_FAILED_SOURCE_IDS:
        if (
            withdrawal_capture_plan_by_id.get(source_id, {}).get(
                "capture_policy"
            )
            != "record_failure"
        ):
            errors.append(
                f"{capture_plan_path}:{source_id}: failed sources must use "
                "record_failure policy"
            )
    actual_withdrawal_source_ids = {
        source_id
        for source_id in source_by_id
        if source_id.startswith("SRC_UG_WITHDRAWAL")
    }
    if actual_withdrawal_source_ids != STAGE_2B_WITHDRAWAL_SOURCE_IDS:
        errors.append(
            f"{source_path}: stage 2B withdrawal source coverage differs; "
            f"expected={sorted(STAGE_2B_WITHDRAWAL_SOURCE_IDS)}, "
            f"got={sorted(actual_withdrawal_source_ids)}"
        )

    captured_source_ids = {
        source_id
        for source_id in actual_withdrawal_source_ids
        if source_by_id[source_id].get("capture", {}).get("status")
        == "captured"
    }
    failed_source_ids = {
        source_id
        for source_id in actual_withdrawal_source_ids
        if source_by_id[source_id].get("capture", {}).get("status")
        == "failed"
    }
    if captured_source_ids != STAGE_2B_WITHDRAWAL_CAPTURED_SOURCE_IDS:
        errors.append(
            f"{source_path}: captured withdrawal source set differs; "
            f"expected={sorted(STAGE_2B_WITHDRAWAL_CAPTURED_SOURCE_IDS)}, "
            f"got={sorted(captured_source_ids)}"
        )
    if failed_source_ids != STAGE_2B_WITHDRAWAL_FAILED_SOURCE_IDS:
        errors.append(
            f"{source_path}: failed withdrawal source set differs; "
            f"expected={sorted(STAGE_2B_WITHDRAWAL_FAILED_SOURCE_IDS)}, "
            f"got={sorted(failed_source_ids)}"
        )

    for source_id in sorted(actual_withdrawal_source_ids):
        source = source_by_id[source_id]
        review = source.get("review", {})
        if review.get("status") != "verified":
            errors.append(
                f"{source_path}:{source_id}: review status must be verified"
            )
        if not review.get("reviewed_at") or not review.get("reviewer"):
            errors.append(
                f"{source_path}:{source_id}: verified source review "
                "requires time and reviewer"
            )
        else:
            try:
                reviewed_at = datetime.fromisoformat(
                    str(review["reviewed_at"])
                )
                captured_at = datetime.fromisoformat(
                    str(source.get("capture", {})["captured_at"])
                )
                if reviewed_at < captured_at:
                    errors.append(
                        f"{source_path}:{source_id}: source review predates "
                        "the capture attempt"
                    )
            except (KeyError, TypeError, ValueError):
                errors.append(
                    f"{source_path}:{source_id}: source capture/review "
                    "timestamps must be valid ISO datetimes"
                )

    auth_page = source_by_id.get(
        "SRC_UG_WITHDRAWAL_FORM_PAGE_20250716",
        {},
    ).get("capture", {})
    auth_final_host = (
        urlparse(str(auth_page.get("final_url", ""))).hostname or ""
    ).lower()
    if (
        auth_page.get("status") != "failed"
        or auth_page.get("http_status") != 200
        or auth_final_host != "icas.jnu.edu.cn"
        or auth_page.get("local_path") is not None
        or auth_page.get("content_sha256") is not None
    ):
        errors.append(
            f"{source_path}: authenticated 2025 landing-page redirect must "
            "remain a non-stored failed capture"
        )

    primary_pdf = source_by_id.get(
        "SRC_UG_WITHDRAWAL_FORM_PDF_202504_PRIMARY",
        {},
    ).get("capture", {})
    if (
        primary_pdf.get("status") != "failed"
        or primary_pdf.get("http_status") != 403
        or primary_pdf.get("local_path") is not None
        or primary_pdf.get("content_sha256") is not None
    ):
        errors.append(
            f"{source_path}: 2025-04 primary PDF must retain the HTTP 403 "
            "non-stored failure record"
        )

    policy_pdf = source_by_id.get(
        "SRC_UG_WITHDRAWAL_POLICY_PDF_20250716",
        {},
    ).get("capture", {})
    if (
        policy_pdf.get("status") != "failed"
        or policy_pdf.get("http_status") != 403
        or policy_pdf.get("local_path") is not None
        or policy_pdf.get("content_sha256") is not None
    ):
        errors.append(
            f"{source_path}: 2025 student-status policy PDF must retain "
            "the HTTP 403 non-stored failure record"
        )

    policy_page = source_by_id.get(
        "SRC_UG_WITHDRAWAL_POLICY_PAGE_20250716",
        {},
    )
    if (
        policy_page.get("document_role") != "policy"
        or policy_page.get("capture", {}).get("status") != "captured"
        or policy_page.get("publication", {}).get("date") != "2025-07-16"
    ):
        errors.append(
            f"{source_path}: 2025 student-status policy landing page must "
            "remain a captured official policy entry"
        )

    cleanup_notice = source_by_id.get(
        "SRC_UG_WITHDRAWAL_NOTICE_20260320",
        {},
    )
    if (
        cleanup_notice.get("document_role") != "notice"
        or cleanup_notice.get("capture", {}).get("status") != "captured"
        or cleanup_notice.get("publication", {}).get("date")
        != "2026-03-20"
        or cleanup_notice.get("version", {}).get("status")
        != "time_bounded"
    ):
        errors.append(
            f"{source_path}: 2026 spring cleanup notice must remain a "
            "captured time-bounded official notice"
        )

    historical_source = source_by_id.get(
        "SRC_UG_WITHDRAWAL_FORM_PDF_201111_MIRROR",
        {},
    )
    historical_text = str(
        historical_source.get("publication", {}).get(
            "displayed_date_text",
            "",
        )
    )
    if (
        historical_source.get("version", {}).get("status") != "historical"
        or "2011 年 11 月" not in historical_text
    ):
        errors.append(
            f"{source_path}: law-school PDF must remain identified as the "
            "2011-11 historical form"
        )
    sihai_text = str(
        source_by_id.get(
            "SRC_UG_WITHDRAWAL_FORM_PDF_202501_SIHAI",
            {},
        )
        .get("publication", {})
        .get("displayed_date_text", "")
    )
    if "2025年1月" not in compact_text(sihai_text):
        errors.append(
            f"{source_path}: Sihai PDF must retain its 2025-01 form marker"
        )

    expected_evidence_ids = {
        f"UGW{number:03d}" for number in range(1, 114)
    }
    withdrawal_evidence = [
        row
        for row in evidence_records
        if row.get("item_id") == "UG_WITHDRAWAL"
    ]
    withdrawal_evidence_by_id = {
        str(row.get("evidence_id", "")): row
        for row in withdrawal_evidence
    }
    if set(withdrawal_evidence_by_id) != expected_evidence_ids:
        errors.append(
            f"{evidence_path}: withdrawal evidence coverage differs; "
            f"missing={sorted(expected_evidence_ids - set(withdrawal_evidence_by_id))}, "
            f"extra={sorted(set(withdrawal_evidence_by_id) - expected_evidence_ids)}"
        )
    for evidence_id, evidence in withdrawal_evidence_by_id.items():
        source_id = str(evidence.get("source_id", ""))
        if source_id not in STAGE_2B_WITHDRAWAL_CAPTURED_SOURCE_IDS:
            errors.append(
                f"{evidence_path}:{evidence_id}: evidence must reference a "
                "captured withdrawal source"
            )
        if source_id == "SRC_UG_WITHDRAWAL_FORM_MIRROR_20241027":
            errors.append(
                f"{evidence_path}:{evidence_id}: law landing page must not "
                "substitute for its historical PDF content"
            )
        review = evidence.get("review", {})
        if (
            review.get("status") != "verified"
            or not review.get("reviewed_at")
            or not review.get("reviewer")
        ):
            errors.append(
                f"{evidence_path}:{evidence_id}: evidence must have a "
                "complete verified primary review"
            )
        else:
            try:
                evidence_reviewed_at = datetime.fromisoformat(
                    str(review["reviewed_at"])
                )
                source_captured_at = datetime.fromisoformat(
                    str(
                        source_by_id[source_id]
                        .get("capture", {})["captured_at"]
                    )
                )
                if evidence_reviewed_at < source_captured_at:
                    errors.append(
                        f"{evidence_path}:{evidence_id}: evidence review "
                        "predates its source capture"
                    )
            except (KeyError, TypeError, ValueError):
                errors.append(
                    f"{evidence_path}:{evidence_id}: evidence/source "
                    "timestamps must be valid ISO datetimes"
                )

    process_validator = Draft202012Validator(
        process_schema,
        format_checker=FormatChecker(),
    )
    process_records = [
        row
        for row in all_process_records
        if row.get("item_id") == "UG_WITHDRAWAL"
    ]
    expected_process_ids = {
        "PROC_UG_WITHDRAWAL_V001",
        "PROC_UG_WITHDRAWAL_V002",
        "PROC_UG_WITHDRAWAL_V003",
        "PROC_UG_WITHDRAWAL_V004",
        "PROC_UG_WITHDRAWAL_V005",
    }
    process_by_id = {
        str(row.get("process_id", "")): row for row in process_records
    }
    if set(process_by_id) != expected_process_ids:
        errors.append(
            f"{process_path}: process coverage differs; "
            f"expected={sorted(expected_process_ids)}, "
            f"got={sorted(process_by_id)}"
        )
    evidence_sha256 = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    expected_process_source_sets = {
        "PROC_UG_WITHDRAWAL_V001": {
            "SRC_UG_WITHDRAWAL_PROCESS_20190418"
        },
        "PROC_UG_WITHDRAWAL_V002": {
            "SRC_UG_WITHDRAWAL_PROCESS_20190418"
        },
        "PROC_UG_WITHDRAWAL_V003": {
            "SRC_UG_WITHDRAWAL_FORM_PDF_201111_MIRROR"
        },
        "PROC_UG_WITHDRAWAL_V004": {
            "SRC_UG_WITHDRAWAL_FORM_PDF_202501_SIHAI"
        },
        "PROC_UG_WITHDRAWAL_V005": {
            "SRC_UG_WITHDRAWAL_NOTICE_20260320"
        },
    }
    expected_process_evidence_sets = {
        "PROC_UG_WITHDRAWAL_V001": {
            "UGW002",
            "UGW003",
            "UGW004",
            "UGW007",
            "UGW008",
            *{f"UGW{number:03d}" for number in range(12, 21)},
        },
        "PROC_UG_WITHDRAWAL_V002": {
            "UGW005",
            "UGW006",
            "UGW009",
            "UGW010",
            "UGW011",
            *{f"UGW{number:03d}" for number in range(12, 21)},
            "UGW073",
        },
        "PROC_UG_WITHDRAWAL_V003": {
            f"UGW{number:03d}" for number in range(54, 73)
        },
        "PROC_UG_WITHDRAWAL_V004": {
            f"UGW{number:03d}" for number in range(21, 54)
        },
        "PROC_UG_WITHDRAWAL_V005": {
            f"UGW{number:03d}" for number in range(75, 114)
        },
    }
    for index, process in enumerate(process_records, start=1):
        process_id = str(process.get("process_id", f"line-{index}"))
        record_path = Path(f"{process_path}:{index}")
        schema_errors = sorted(
            process_validator.iter_errors(process),
            key=lambda item: list(item.path),
        )
        errors.extend(
            format_schema_error(record_path, error)
            for error in schema_errors
        )
        if process.get("item_id") != "UG_WITHDRAWAL":
            errors.append(
                f"{process_path}:{process_id}: item_id must be UG_WITHDRAWAL"
            )
        snapshot = process.get("evidence_snapshot", {})
        if snapshot.get("dataset_sha256") != evidence_sha256:
            errors.append(
                f"{process_path}:{process_id}: evidence dataset hash differs"
            )
        snapshot_ids = {
            str(value) for value in snapshot.get("evidence_ids", [])
        }
        if snapshot_ids != expected_process_evidence_sets.get(
            process_id,
            set(),
        ):
            errors.append(
                f"{process_path}:{process_id}: evidence snapshot coverage "
                "differs from the verified process baseline"
            )
        process_source_ids = {
            str(withdrawal_evidence_by_id[evidence_id].get("source_id", ""))
            for evidence_id in snapshot_ids
            if evidence_id in withdrawal_evidence_by_id
        }
        if process_source_ids != expected_process_source_sets.get(
            process_id,
            set(),
        ):
            errors.append(
                f"{process_path}:{process_id}: source-version group differs; "
                f"got={sorted(process_source_ids)}"
            )
        review = process.get("review", {})
        if review.get("status") != "verified":
            errors.append(
                f"{process_path}:{process_id}: review status must be verified"
            )
        if review.get("annotator") == review.get("reviewer"):
            errors.append(
                f"{process_path}:{process_id}: annotator and reviewer "
                "must differ"
            )
        try:
            process_annotated_at = datetime.fromisoformat(
                str(review["annotated_at"])
            )
            process_reviewed_at = datetime.fromisoformat(
                str(review["reviewed_at"])
            )
            latest_source_capture = max(
                datetime.fromisoformat(
                    str(
                        source_by_id[source_id]
                        .get("capture", {})["captured_at"]
                    )
                )
                for source_id in process_source_ids
            )
            if process_annotated_at < latest_source_capture:
                errors.append(
                    f"{process_path}:{process_id}: process annotation "
                    "predates its source capture"
                )
            if process_reviewed_at < process_annotated_at:
                errors.append(
                    f"{process_path}:{process_id}: process review predates "
                    "its annotation"
                )
        except (KeyError, TypeError, ValueError):
            errors.append(
                f"{process_path}:{process_id}: process/source timestamps "
                "must be valid ISO datetimes"
            )

        allowed_claims = process.get("allowed_claims", [])
        claim_evidence_ids: list[str] = []
        for claim in allowed_claims:
            claim_ids = [
                str(value) for value in claim.get("evidence_ids", [])
            ]
            if len(claim_ids) != 1:
                errors.append(
                    f"{process_path}:{process_id}:{claim.get('claim_id')}: "
                    "each allowed claim must bind exactly one atomic evidence unit"
                )
                continue
            evidence_id = claim_ids[0]
            claim_evidence_ids.append(evidence_id)
            evidence = withdrawal_evidence_by_id.get(evidence_id, {})
            if claim.get("text") != evidence.get("normalized_claim"):
                errors.append(
                    f"{process_path}:{process_id}:{claim.get('claim_id')}: "
                    "allowed-claim text must equal its normalized evidence claim"
                )
            if claim.get("claim_type") != evidence.get("claim_type"):
                errors.append(
                    f"{process_path}:{process_id}:{claim.get('claim_id')}: "
                    "claim type differs from its evidence unit"
                )
        if set(claim_evidence_ids) != snapshot_ids:
            errors.append(
                f"{process_path}:{process_id}: atomic allowed claims must "
                "cover the evidence snapshot exactly"
            )

        sample_id = f"S2E-WD-{index:03d}"
        sample = {
            "sample_id": sample_id,
            "dataset_version": "0.2.0",
            "allocation_item_id": "UG_WITHDRAWAL",
            "item_id": "UG_WITHDRAWAL",
            "process_id": process_id,
            "scenario_type": "direct",
            "turn_structure": "single_turn",
            "conversation": [{"turn_id": "T01", "role": "user"}],
            "input_context": {"provided_slots": []},
            "gold": {
                "target_item_id": "UG_WITHDRAWAL",
                "response_mode": "answer",
                "required_slot_ids": [],
                "missing_slot_ids": [],
                "ordered_step_ids": [],
                "material_ids": [],
                "allowed_claim_ids": [],
                "supporting_evidence_ids": [],
            },
            "leakage_control": {
                "prohibited_overlap_sample_ids": []
            },
        }
        review_fixture = {
            "review_id": f"S2B-LINK-{index:03d}",
            "sample_id": sample_id,
            "dataset_version": "0.2.0",
            "primary_annotation": {"reviewer": "流程标注者"},
            "secondary_review": {"reviewer": "流程复核者"},
            "disagreements": [],
            "adjudication": None,
        }
        errors.extend(
            validate_stage2_fixture_links(
                process,
                sample,
                review_fixture,
                evidence_records,
            )
        )

    require_columns(
        review_headers,
        SECOND_REVIEW_COLUMNS,
        review_path,
        errors,
    )
    expected_review_ids = {
        f"S2BWD{number:03d}" for number in range(1, 114)
    }
    actual_review_ids = {
        row.get("review_id", "") for row in review_rows
    }
    if actual_review_ids != expected_review_ids:
        errors.append(
            f"{review_path}: second-review ID coverage differs"
        )
    reviewed_evidence_ids = [
        row.get("evidence_id", "") for row in review_rows
    ]
    if (
        set(reviewed_evidence_ids) != expected_evidence_ids
        or len(reviewed_evidence_ids) != len(set(reviewed_evidence_ids))
    ):
        errors.append(
            f"{review_path}: second review must cover each withdrawal "
            "evidence unit exactly once"
        )
    for row in review_rows:
        evidence_id = row.get("evidence_id", "")
        evidence = withdrawal_evidence_by_id.get(evidence_id, {})
        if row.get("source_id") != evidence.get("source_id"):
            errors.append(
                f"{review_path}:{row.get('review_id')}: source_id differs "
                "from evidence"
            )
        for field in {
            "locator_recheck",
            "verbatim_recheck",
            "claim_recheck",
            "applicability_recheck",
        }:
            if row.get(field) != "通过":
                errors.append(
                    f"{review_path}:{row.get('review_id')}: {field} "
                    "must be 通过"
                )
        if row.get("result") != "已验证":
            errors.append(
                f"{review_path}:{row.get('review_id')}: result must be 已验证"
            )
        if row.get("reviewer") == evidence.get("review", {}).get("reviewer"):
            errors.append(
                f"{review_path}:{row.get('review_id')}: primary and "
                "secondary reviewer identities must differ"
            )
        for field in {"reviewed_at", "reviewer", "notes"}:
            if not row.get(field, "").strip():
                errors.append(
                    f"{review_path}:{row.get('review_id')}: {field} "
                    "must not be empty"
                )
        try:
            secondary_reviewed_at = datetime.fromisoformat(
                str(row["reviewed_at"])
            )
            primary_reviewed_at = datetime.fromisoformat(
                str(evidence.get("review", {})["reviewed_at"])
            )
            if secondary_reviewed_at < primary_reviewed_at:
                errors.append(
                    f"{review_path}:{row.get('review_id')}: secondary "
                    "review predates primary evidence review"
                )
        except (KeyError, TypeError, ValueError):
            errors.append(
                f"{review_path}:{row.get('review_id')}: review timestamps "
                "must be valid ISO datetimes"
            )

    version_groups = examples.get("version_groups", [])
    positive_examples = examples.get("positive_examples", [])
    negative_examples = examples.get("negative_examples", [])
    expected_version_group_ids = {
        "VG_WD_2011_11_FORM",
        "VG_WD_2019_04_PROCESS",
        "VG_WD_2025_01_FORM",
        "VG_WD_2026_SPRING_NOTICE",
    }
    actual_version_group_ids = {
        str(row.get("version_group_id", "")) for row in version_groups
    }
    if examples.get("status") != "已验证":
        errors.append(f"{examples_path}: status must be 已验证")
    if actual_version_group_ids != expected_version_group_ids:
        errors.append(
            f"{examples_path}: version-group coverage differs"
        )
    for group in version_groups:
        group_id = group.get("version_group_id", "<unknown>")
        if group.get("status") != "已验证":
            errors.append(
                f"{examples_path}:{group_id}: status must be 已验证"
            )
        unknown_sources = (
            set(str(value) for value in group.get("source_ids", []))
            - STAGE_2B_WITHDRAWAL_SOURCE_IDS
        )
        unknown_processes = (
            set(str(value) for value in group.get("process_ids", []))
            - expected_process_ids
        )
        if unknown_sources or unknown_processes:
            errors.append(
                f"{examples_path}:{group_id}: unknown source or process "
                "references"
            )

    for example in positive_examples:
        example_id = example.get("example_id", "<unknown>")
        if example.get("process_id") not in expected_process_ids:
            errors.append(
                f"{examples_path}:{example_id}: unknown process reference"
            )
        unknown_evidence = (
            set(str(value) for value in example.get("evidence_ids", []))
            - expected_evidence_ids
        )
        if unknown_evidence or not example.get("annotation", "").strip():
            errors.append(
                f"{examples_path}:{example_id}: invalid positive example"
            )
    for example in negative_examples:
        example_id = example.get("example_id", "<unknown>")
        unknown_evidence = (
            set(str(value) for value in example.get("evidence_ids", []))
            - expected_evidence_ids
        )
        unknown_sources = (
            set(str(value) for value in example.get("source_ids", []))
            - STAGE_2B_WITHDRAWAL_SOURCE_IDS
        )
        if (
            unknown_evidence
            or unknown_sources
            or not example.get("rejected_claim", "").strip()
            or not example.get("reason", "").strip()
        ):
            errors.append(
                f"{examples_path}:{example_id}: invalid negative example"
            )
    negative_text = json.dumps(
        negative_examples,
        ensure_ascii=False,
    )
    for marker in {
        "HTTP 403",
        "替代关系",
        "家长知情同意书",
        "集中受理周次不同",
        "其他学期统一规则",
    }:
        if marker not in negative_text:
            errors.append(
                f"{examples_path}: negative examples lack marker {marker!r}"
            )

    source_plan_by_id = {
        row.get("plan_id", ""): row for row in source_plan_rows
    }
    if source_plan_by_id.get("S2SRC001", {}).get("status") != "已验证":
        errors.append(
            f"{source_plan_path}: S2SRC001 must be 已验证"
        )
    completed_migration_items = {
        "S2SRC002": "UG_CREDENTIAL_REISSUE",
        "S2SRC003": "UG_STUDENT_CARD_REISSUE",
        "S2SRC004": "UG_COURSE_SELECTION",
        "S2SRC005": "UG_LEAVE_REQUEST",
        "S2SRC006": "UG_MAJOR_CHANGE",
    }
    process_by_item = {}
    for record in all_process_records:
        item_id = record.get("item_id")
        if item_id in completed_migration_items.values():
            process_by_item.setdefault(item_id, []).append(record)
    for plan_id, row in source_plan_by_id.items():
        if plan_id == "S2SRC001":
            continue
        item_id = completed_migration_items.get(plan_id)
        records = process_by_item.get(item_id, []) if item_id else []
        if row.get("status") == "已验证":
            if not records or any(record.get("review", {}).get("status") != "verified" for record in records):
                errors.append(f"{source_plan_path}:{plan_id}: verified status requires verified process records")
        elif row.get("status") != "计划":
            errors.append(f"{source_plan_path}:{plan_id}: status must be 计划 or 已验证")

    required_document_markers = {
        baseline_path: {
            "# 阶段 2B 退学办理来源、证据与流程基线",
            "状态：已验证",
            "`UGW001` 至 `UGW113`",
            "`PROC_UG_WITHDRAWAL_V005`",
            "100% 第二次独立复核",
        },
        report_path: {
            "# 工作报告 008",
            "迁移计划：`S2SRC001`",
            "20 项测试全部通过",
            "最近接续点更新为 `S2SRC002`",
        },
        decisions_path: {
            "### D-018 退学表格按可核验制表月份与流程页分组",
            "- 状态：已验证",
        },
        project_plan_path: {
            "阶段 2B：扩展事项来源固化、原子证据迁移、事项级流程基线和独立复核，状态为已验证",
            "阶段 2B 退学办理验收结果",
        },
        project_memory_path: {
            "阶段 2 内容冻结版本 1.0.1-frozen 已验证",
            "阶段 3 进行中",
        },
    }
    for document_path, markers in required_document_markers.items():
        document_text = document_path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in document_text:
                errors.append(
                    f"{document_path}: missing stage 2B marker {marker!r}"
                )

    return errors, {
        "stage2b_withdrawal_sources": len(actual_withdrawal_source_ids),
        "stage2b_withdrawal_captured_sources": len(captured_source_ids),
        "stage2b_withdrawal_failed_sources": len(failed_source_ids),
        "stage2b_withdrawal_evidence": len(withdrawal_evidence),
        "stage2b_withdrawal_process_records": len(process_records),
        "stage2b_withdrawal_second_reviews": len(review_rows),
        "stage2b_withdrawal_positive_examples": len(positive_examples),
        "stage2b_withdrawal_negative_examples": len(negative_examples),
        "stage2b_withdrawal_version_groups": len(version_groups),
        "stage2b_withdrawal_capture_plan_rows": len(
            withdrawal_capture_plan_by_id
        ),
        "stage2b_withdrawal_primary_access_failures": len(
            STAGE_2B_WITHDRAWAL_FAILED_SOURCE_IDS
        ),
        "stage2b_withdrawal_baseline_reports": 2,
    }


def run_validation(root: Path = ROOT, scope: str = "all") -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    summary: dict[str, int] = {}

    if scope in {"all", "schemas"}:
        schema_errors, schema_summary = validate_schemas_and_fixtures(root)
        errors.extend(schema_errors)
        summary.update(schema_summary)
    if scope in {"all", "repository"}:
        repository_errors, repository_summary = validate_repository_audits(root)
        errors.extend(repository_errors)
        summary.update(repository_summary)
        target_errors, target_summary = validate_target_repository(root)
        errors.extend(target_errors)
        summary.update(target_summary)
        stage1_errors, stage1_summary = validate_stage1_completion_artifacts(root)
        errors.extend(stage1_errors)
        summary.update(stage1_summary)
        stage2a_errors, stage2a_summary = validate_stage2a_contract(root)
        errors.extend(stage2a_errors)
        summary.update(stage2a_summary)
        stage2b_errors, stage2b_summary = (
            validate_stage2b_withdrawal_contract(root)
        )
        errors.extend(stage2b_errors)
        summary.update(stage2b_summary)

    return errors, summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate research-data schemas, repository evidence, and stage "
            "completion contracts."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root. Defaults to the parent of this script directory.",
    )
    parser.add_argument(
        "--scope",
        choices=["all", "schemas", "repository"],
        default="all",
        help="Validation surface to execute.",
    )
    args = parser.parse_args()

    errors, summary = run_validation(args.root.resolve(), args.scope)
    if errors:
        print("[FAIL] Research data validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("[OK] Research data validation passed.")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
