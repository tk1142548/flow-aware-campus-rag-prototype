from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / "data" / "research" / "source_capture_plan.json"
USER_AGENT = "flow-aware-campus-rag-research/1.0 (academic source audit)"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def capture_record(
    root: Path,
    planned: dict[str, Any],
    session: requests.Session,
) -> tuple[dict[str, Any], Path, bytes]:
    source_id = planned["source_id"]
    target_config = planned["capture_target"]
    target = safe_output_path(root, target_config["local_path"])

    if target.exists():
        raise FileExistsError(
            f"{source_id}: target already exists; create a new source version and path"
        )

    response = session.get(planned["canonical_url"], timeout=30, allow_redirects=True)
    response.raise_for_status()
    content = response.content
    actual_media_type = media_type(response)
    validate_content(
        source_id,
        planned["content_format"],
        target_config["expected_media_type"],
        actual_media_type,
        content,
    )

    captured_at = datetime.now().astimezone().isoformat(timespec="seconds")

    record = {key: value for key, value in planned.items() if key != "capture_target"}
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture declared official sources and generate auditable source records."
    )
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    args = parser.parse_args()

    plan_path = args.plan.resolve()
    plan = load_json(plan_path)
    output_path = safe_record_path(ROOT, plan["output_path"])
    if output_path.exists():
        raise FileExistsError(
            f"source record output already exists: {output_path}; "
            "create a new source-record output for a new capture version"
        )

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    target_paths = [
        safe_output_path(ROOT, planned["capture_target"]["local_path"])
        for planned in plan["records"]
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
        for planned in plan["records"]
    ]
    records = [record for record, _, _ in captures]
    created_paths: list[Path] = []
    try:
        for _, target, content in captures:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(content)
            created_paths.append(target)
        write_jsonl(output_path, records)
    except Exception:
        for created_path in reversed(created_paths):
            created_path.unlink(missing_ok=True)
        raise

    print(f"Captured {len(records)} official source files.")
    for record in records:
        capture = record["capture"]
        print(
            f"  {record['source_id']}: {capture['byte_length']} bytes, "
            f"sha256={capture['content_sha256']}, {capture['local_path']}"
        )
    print(f"Source records: {output_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
