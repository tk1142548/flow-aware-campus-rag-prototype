"""Validate the source and evidence layers.

Checks, for every record: schema conformance, unique identifiers, resolvable
source links (including reciprocal relations and version links), that each
captured source file exists with the recorded size and format, and that every
evidence anchor can be found in the text extracted from its saved source.

Process records are checked separately by validate_process_records.py.

Usage:
    python scripts/validate_research_data.py
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
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
        "invalid": ["tests/fixtures/data/invalid/source-record-invalid-date.json"],
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
        "invalid": ["tests/fixtures/data/invalid/process-record-step-without-evidence.json"],
    },
    "evaluation-sample.schema.json": {
        "valid": ["tests/fixtures/data/valid/evaluation-sample.json"],
        "invalid": ["tests/fixtures/data/invalid/evaluation-sample-invalid-id.json"],
    },
}

TARGET_SOURCE_RECORDS_PATH = Path("data/research/source_records.jsonl")
TARGET_EVIDENCE_RECORDS_PATH = Path("data/research/evidence_units.jsonl")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def compact_text(text: str) -> str:
    return "".join(text.replace(" ", " ").split())


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


def run_validation(root: Path = ROOT) -> tuple[list[str], dict[str, int]]:
    errors, summary = validate_schemas_and_fixtures(root)
    target_errors, target_summary = validate_target_repository(root)
    return errors + target_errors, {**summary, **target_summary}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the source and evidence layers.")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()

    errors, summary = run_validation(args.root.resolve())
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
