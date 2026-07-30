from __future__ import annotations

import argparse
import csv
import hashlib
import json
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

    return errors, summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate target research-data schemas and the current legacy audit baseline."
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
