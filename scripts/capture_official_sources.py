from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / "data" / "research" / "source_capture_plan.json"
USER_AGENT = "flow-aware-campus-rag-research/1.0 (academic source audit)"
PLAN_ONLY_FIELDS = {"capture_target", "capture_policy"}
OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ZIP_SIGNATURE = b"PK\x03\x04"


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
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            rows.append(row)
    return rows


def safe_output_path(root: Path, relative_path: str) -> Path:
    target = (root / relative_path).resolve()
    allowed_root = (root / "data" / "sources").resolve()
    if target == allowed_root or allowed_root not in target.parents:
        raise ValueError(f"capture path is outside data/sources: {relative_path}")
    return target


def safe_record_path(root: Path, relative_path: str) -> Path:
    target = (root / relative_path).resolve()
    allowed_root = (root / "data" / "research").resolve()
    if target == allowed_root or allowed_root not in target.parents:
        raise ValueError(f"source record path is outside data/research: {relative_path}")
    return target


def media_type(response: requests.Response) -> str:
    return response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()


def validate_content(
    source_id: str,
    content_format: str,
    expected_media_type: str,
    actual_media_type: str,
    content: bytes,
) -> None:
    if actual_media_type != expected_media_type:
        raise ValueError(
            f"{source_id}: media type {actual_media_type!r}, expected {expected_media_type!r}"
        )
    if content_format == "pdf" and not content.startswith(b"%PDF-"):
        raise ValueError(f"{source_id}: response does not have a PDF signature")
    if content_format == "html" and b"<html" not in content[:4096].lower():
        raise ValueError(f"{source_id}: response does not look like HTML")
    if content_format == "png" and not content.startswith(PNG_SIGNATURE):
        raise ValueError(f"{source_id}: response does not have a PNG signature")
    if content_format in {"doc", "xls"} and not content.startswith(OLE_SIGNATURE):
        raise ValueError(
            f"{source_id}: response does not have an OLE compound-file signature"
        )
    if content_format == "docx" and not content.startswith(ZIP_SIGNATURE):
        raise ValueError(f"{source_id}: response does not have an OOXML ZIP signature")


def validate_final_host(
    source_id: str,
    canonical_url: str,
    final_url: str,
    expected_final_host: str | None = None,
) -> None:
    expected_host = expected_final_host or urlparse(canonical_url).hostname
    actual_host = urlparse(final_url).hostname
    if not expected_host or actual_host != expected_host:
        raise ValueError(
            f"{source_id}: unexpected final host {actual_host!r}, "
            f"expected {expected_host!r}"
        )


def planned_record(planned: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in planned.items()
        if key not in PLAN_ONLY_FIELDS
    }


def failed_response_record(
    planned: dict[str, Any],
    captured_at: str,
    response: requests.Response | None,
    reason: str,
) -> dict[str, Any]:
    response_media_type = media_type(response) if response is not None else ""
    response_byte_length = (
        len(response.content) if response is not None and response.content else None
    )
    record = planned_record(planned)
    record["capture"] = {
        "status": "failed",
        "captured_at": captured_at,
        "content_sha256": None,
        "local_path": None,
        "http_status": response.status_code if response is not None else None,
        "final_url": response.url if response is not None else None,
        "media_type": response_media_type or None,
        "byte_length": response_byte_length,
        "last_modified": (
            response.headers.get("Last-Modified") if response is not None else None
        ),
        "failure_reason": (
            f"{reason}; "
            "the error response was not stored as source evidence"
        ),
    }
    return record


def failed_capture_record(
    planned: dict[str, Any],
    captured_at: str,
    error: requests.RequestException,
) -> dict[str, Any]:
    return failed_response_record(
        planned,
        captured_at,
        error.response,
        f"{type(error).__name__}: {error}",
    )


def capture_record(
    root: Path,
    planned: dict[str, Any],
    session: requests.Session,
) -> tuple[dict[str, Any], Path | None, bytes | None]:
    source_id = planned["source_id"]
    target_config = planned["capture_target"]
    target = safe_output_path(root, target_config["local_path"])

    if target.exists():
        raise FileExistsError(
            f"{source_id}: target already exists; create a new source version and path"
        )

    captured_at = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        response = session.get(
            planned["canonical_url"],
            timeout=30,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        if planned.get("capture_policy", "required") != "record_failure":
            raise
        return failed_capture_record(planned, captured_at, exc), None, None

    content = response.content
    actual_media_type = media_type(response)
    try:
        validate_final_host(
            source_id,
            planned["canonical_url"],
            response.url,
            target_config.get("expected_final_host"),
        )
        validate_content(
            source_id,
            planned["content_format"],
            target_config["expected_media_type"],
            actual_media_type,
            content,
        )
    except ValueError as exc:
        if planned.get("capture_policy", "required") != "record_failure":
            raise
        return (
            failed_response_record(
                planned,
                captured_at,
                response,
                f"{type(exc).__name__}: {exc}",
            ),
            None,
            None,
        )

    record = planned_record(planned)
    record["capture"] = {
        "status": "captured",
        "captured_at": captured_at,
        "content_sha256": hashlib.sha256(content).hexdigest(),
        "local_path": target.relative_to(root).as_posix(),
        "http_status": response.status_code,
        "final_url": response.url,
        "media_type": actual_media_type,
        "byte_length": len(content),
        "last_modified": response.headers.get("Last-Modified"),
        "failure_reason": None,
    }
    return record, target, content


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=False))
            handle.write("\n")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"source record output does not exist: {path}")
    if not rows:
        return

    needs_newline = path.stat().st_size > 0
    if needs_newline:
        with path.open("rb") as handle:
            handle.seek(-1, 2)
            needs_newline = handle.read(1) not in {b"\n", b"\r"}

    with path.open("a", encoding="utf-8", newline="\n") as handle:
        if needs_newline:
            handle.write("\n")
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=False))
            handle.write("\n")


def validate_existing_plan_record(
    planned: dict[str, Any],
    existing: dict[str, Any],
) -> None:
    source_id = planned["source_id"]
    if planned["canonical_url"] != existing.get("canonical_url"):
        raise ValueError(
            f"{source_id}: planned canonical_url differs from existing source record"
        )
    existing_capture = existing.get("capture", {})
    existing_path = existing_capture.get("local_path")
    planned_path = planned["capture_target"]["local_path"]
    if existing_capture.get("status") == "captured" and existing_path != planned_path:
        raise ValueError(
            f"{source_id}: planned local_path differs from existing source record"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture declared official sources and generate auditable source records."
    )
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument(
        "--append",
        action="store_true",
        help=(
            "Append only source IDs absent from an existing output file. "
            "Existing records and source files remain byte-for-byte unchanged."
        ),
    )
    args = parser.parse_args()

    plan_path = args.plan.resolve()
    plan = load_json(plan_path)
    output_path = safe_record_path(ROOT, plan["output_path"])
    if output_path.exists() and not args.append:
        raise FileExistsError(
            f"source record output already exists: {output_path}; "
            "use --append for declared new source IDs or create a new output version"
        )
    if args.append and not output_path.is_file():
        raise FileNotFoundError(
            f"cannot append because source record output is missing: {output_path}"
        )

    planned_ids = [str(row.get("source_id", "")) for row in plan["records"]]
    duplicate_planned_ids = sorted(
        source_id
        for source_id in set(planned_ids)
        if planned_ids.count(source_id) > 1
    )
    if duplicate_planned_ids:
        raise ValueError(
            f"capture plan contains duplicate source IDs: {duplicate_planned_ids}"
        )

    existing_records = load_jsonl(output_path) if args.append else []
    existing_by_id = {
        str(row.get("source_id", "")): row
        for row in existing_records
    }
    if len(existing_by_id) != len(existing_records):
        raise ValueError("existing source record output contains duplicate source IDs")

    new_planned_records: list[dict[str, Any]] = []
    for planned in plan["records"]:
        existing = existing_by_id.get(planned["source_id"])
        if existing is None:
            new_planned_records.append(planned)
        else:
            validate_existing_plan_record(planned, existing)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    target_paths = [
        safe_output_path(ROOT, planned["capture_target"]["local_path"])
        for planned in new_planned_records
    ]
    if len(target_paths) != len(set(target_paths)):
        raise ValueError("capture plan contains duplicate local paths")
    existing_targets = [path for path in target_paths if path.exists()]
    if existing_targets:
        raise FileExistsError(
            "capture targets already exist; create new source versions and paths: "
            f"{existing_targets}"
        )

    captures = [
        capture_record(ROOT, planned, session)
        for planned in new_planned_records
    ]
    records = [record for record, _, _ in captures]
    created_paths: list[Path] = []
    original_output_size = output_path.stat().st_size if args.append else None
    try:
        for _, target, content in captures:
            if target is None or content is None:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(content)
            created_paths.append(target)
        if args.append:
            append_jsonl(output_path, records)
        else:
            write_jsonl(output_path, records)
    except Exception:
        for created_path in reversed(created_paths):
            created_path.unlink(missing_ok=True)
        if (
            args.append
            and original_output_size is not None
            and output_path.exists()
            and output_path.stat().st_size != original_output_size
        ):
            with output_path.open("r+b") as handle:
                handle.truncate(original_output_size)
        raise

    captured_count = sum(
        record["capture"]["status"] == "captured" for record in records
    )
    failed_count = sum(
        record["capture"]["status"] == "failed" for record in records
    )
    print(
        f"Processed {len(records)} new source records: "
        f"{captured_count} captured, {failed_count} failed."
    )
    for record in records:
        capture = record["capture"]
        if capture["status"] == "captured":
            print(
                f"  {record['source_id']}: {capture['byte_length']} bytes, "
                f"sha256={capture['content_sha256']}, {capture['local_path']}"
            )
        else:
            print(
                f"  {record['source_id']}: failed, "
                f"http_status={capture['http_status']}, "
                f"reason={capture['failure_reason']}"
            )
    print(f"Source records: {output_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
