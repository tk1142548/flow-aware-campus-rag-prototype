from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


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
]

KNOWN_MISMATCH_IDS = {"UGS002", "UGS003", "UGS013", "UGS014"}


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
    for source in source_records:
        source_id = str(source.get("source_id", "<unknown>"))
        for relation in source.get("relations", []):
            target_source_id = str(relation.get("target_source_id", ""))
            if target_source_id not in known_sources:
                errors.append(
                    f"{source_id}: relation references unknown source_id "
                    f"{target_source_id!r}"
                )
        version = source.get("version", {})
        for field in ("supersedes", "superseded_by"):
            for target_source_id in version.get(field, []):
                if target_source_id not in known_sources:
                    errors.append(
                        f"{source_id}: version.{field} references unknown source_id "
                        f"{target_source_id!r}"
                    )

    for evidence in evidence_records:
        source_id = str(evidence.get("source_id", ""))
        if source_id not in known_sources:
            errors.append(
                f"{evidence.get('evidence_id', '<unknown>')}: unknown source_id {source_id!r}"
            )
    return errors


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

    manifest = load_json(manifest_path)
    if not isinstance(manifest, list):
        return [f"{manifest_path}: expected a JSON array"], {}
    evidence_rows = load_jsonl(evidence_path)
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
        "legacy_unmigrated_rows": sum(
            1 for row in evidence_audit if row.get("migration_status") != "migrated"
        ),
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
