"""Validate process records and their evidence bindings.

The validator is deliberately data driven: it reads the process and evidence
JSONL files under the supplied repository root and does not contain an
allow-list of process IDs, items, or evidence IDs.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker


PROCESS_PATH = Path("data/research/process_records.jsonl")
EVIDENCE_PATH = Path("data/research/evidence_units.jsonl")
PROCESS_SCHEMA_PATH = Path("data/schemas/process-record.schema.json")
EVIDENCE_SCHEMA_PATH = Path("data/schemas/evidence-unit.schema.json")

_EVIDENCE_FIELDS = (
    "slots",
    "follow_up_rules",
    "steps",
    "materials",
    "service_points",
    "time_constraints",
    "exceptions",
    "consequences",
    "allowed_claims",
)


def _read_jsonl(path: Path) -> tuple[list[tuple[int, Any]], list[str]]:
    rows: list[tuple[int, Any]] = []
    errors: list[str] = []
    if not path.exists():
        return rows, [f"{path}: file does not exist"]
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return rows, [f"{path}: cannot read file: {exc}"]
    for line_no, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            rows.append((line_no, json.loads(line)))
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{line_no}: invalid JSON: {exc.msg}")
    return rows, errors


def _format_schema_error(path: Path, line_no: int, error: Any) -> str:
    location = ".".join(str(part) for part in error.absolute_path)
    suffix = f" at {location}" if location else ""
    return f"{path}:{line_no}: schema error{suffix}: {error.message}"


def _iter_evidence_refs(record: dict[str, Any]) -> Iterable[tuple[str, str, Any]]:
    """Yield (field, evidence ID, owning object) for every nested binding."""
    for field in _EVIDENCE_FIELDS:
        values = record.get(field, [])
        if not isinstance(values, list):
            continue
        for obj in values:
            if not isinstance(obj, dict):
                continue
            ids = obj.get("evidence_ids", [])
            if isinstance(ids, list):
                for evidence_id in ids:
                    yield field, str(evidence_id), obj


def _iter_conditions(record: dict[str, Any]) -> Iterable[tuple[str, Any]]:
    """Yield a path label and every condition object in a process record."""
    for field in ("steps", "materials", "service_points", "time_constraints", "exceptions", "consequences", "allowed_claims"):
        values = record.get(field, [])
        if not isinstance(values, list):
            continue
        for index, obj in enumerate(values):
            if not isinstance(obj, dict):
                continue
            for condition_key in ("conditions", "required_when", "trigger"):
                conditions = obj.get(condition_key, [])
                if isinstance(conditions, list):
                    for condition_index, condition in enumerate(conditions):
                        yield f"{field}[{index}].{condition_key}[{condition_index}]", condition


def _add(errors: list[str], counts: Counter[str], kind: str, message: str) -> None:
    errors.append(message)
    counts[kind] += 1


def _check_ids_exist(
    errors: list[str],
    counts: Counter[str],
    process_path: Path,
    process_id: str,
    values: Any,
    known: set[str],
    label: str,
) -> None:
    if not isinstance(values, list):
        return
    for value in values:
        if value not in known:
            _add(
                errors,
                counts,
                "reference_errors",
                f"{process_path}:{process_id}: {label} references missing {value}",
            )


def _check_dag(
    record: dict[str, Any],
    errors: list[str],
    counts: Counter[str],
    process_path: Path,
    process_id: str,
) -> None:
    steps = record.get("steps", [])
    if not isinstance(steps, list):
        return
    step_by_id = {
        step.get("step_id"): step
        for step in steps
        if isinstance(step, dict) and isinstance(step.get("step_id"), str)
    }
    graph: dict[str, list[str]] = {}
    for step_id, step in step_by_id.items():
        successors = step.get("next_step_ids", [])
        if not isinstance(successors, list):
            continue
        graph[step_id] = [str(target) for target in successors]
        for target in successors:
            if target not in step_by_id:
                _add(
                    errors,
                    counts,
                    "reference_errors",
                    f"{process_path}:{process_id}: step {step_id} references missing successor {target}",
                )

    state: dict[str, int] = {}
    reported: set[tuple[str, ...]] = set()

    def visit(node: str, path: list[str]) -> None:
        state[node] = 1
        path.append(node)
        for target in graph.get(node, []):
            if target not in step_by_id:
                continue
            if state.get(target, 0) == 0:
                visit(target, path)
            elif state.get(target) == 1:
                cycle = tuple(path[path.index(target) :] + [target])
                if cycle not in reported:
                    reported.add(cycle)
                    _add(
                        errors,
                        counts,
                        "graph_errors",
                        f"{process_path}:{process_id}: successor graph contains cycle {' -> '.join(cycle)}",
                    )
        path.pop()
        state[node] = 2

    for node in step_by_id:
        if state.get(node, 0) == 0:
            visit(node, [])


def _validate_record(
    root: Path,
    process_path: Path,
    line_no: int,
    record: Any,
    evidence_by_id: dict[str, dict[str, Any]],
    process_validator: Draft202012Validator,
    errors: list[str],
    counts: Counter[str],
) -> bool:
    process_id = str(record.get("process_id", f"line-{line_no}")) if isinstance(record, dict) else f"line-{line_no}"
    before = len(errors)
    if not isinstance(record, dict):
        _add(errors, counts, "schema_errors", f"{process_path}:{line_no}: record must be a JSON object")
        return False

    for schema_error in sorted(process_validator.iter_errors(record), key=lambda item: list(item.absolute_path)):
        _add(errors, counts, "schema_errors", _format_schema_error(process_path, line_no, schema_error))

    item_id = record.get("item_id")
    process_label = f"{process_path}:{process_id}"

    snapshot = record.get("evidence_snapshot", {})
    if isinstance(snapshot, dict):
        snapshot_ids = set(snapshot.get("evidence_ids", [])) if isinstance(snapshot.get("evidence_ids"), list) else set()
        dataset_path = snapshot.get("dataset_path")
        if dataset_path != str(EVIDENCE_PATH).replace("\\", "/"):
            _add(errors, counts, "snapshot_errors", f"{process_label}: evidence snapshot dataset_path must be {EVIDENCE_PATH.as_posix()}")
    else:
        snapshot_ids = set()

    referenced_ids: set[str] = set()
    for field, evidence_id, _obj in _iter_evidence_refs(record):
        referenced_ids.add(evidence_id)
        evidence = evidence_by_id.get(evidence_id)
        if evidence is None:
            _add(errors, counts, "evidence_errors", f"{process_label}: {field} references missing evidence {evidence_id}")
        elif evidence.get("item_id") != item_id:
            _add(errors, counts, "evidence_errors", f"{process_label}: evidence {evidence_id} belongs to item {evidence.get('item_id')}, not {item_id}")

    for evidence_id in snapshot_ids:
        evidence = evidence_by_id.get(evidence_id)
        if evidence is None:
            _add(errors, counts, "evidence_errors", f"{process_label}: evidence snapshot references missing evidence {evidence_id}")
        elif evidence.get("item_id") != item_id:
            _add(errors, counts, "evidence_errors", f"{process_label}: snapshot evidence {evidence_id} belongs to item {evidence.get('item_id')}, not {item_id}")

    if snapshot_ids != referenced_ids:
        _add(errors, counts, "snapshot_errors", f"{process_label}: evidence snapshot IDs must exactly equal all nested evidence references; missing={sorted(referenced_ids - snapshot_ids)}, extra={sorted(snapshot_ids - referenced_ids)}")

    slot_values = record.get("slots", [])
    slot_ids = [x.get("slot_id") for x in slot_values if isinstance(x, dict)] if isinstance(slot_values, list) else []
    slot_set = {x for x in slot_ids if isinstance(x, str)}
    if len(slot_ids) != len(set(slot_ids)):
        _add(errors, counts, "reference_errors", f"{process_label}: slot IDs must be unique")
    for field, evidence_id, _obj in _iter_evidence_refs(record):
        del field, evidence_id, _obj

    for field, condition in _iter_conditions(record):
        if not isinstance(condition, dict):
            continue
        slot_id = condition.get("slot_id")
        if slot_id not in slot_set:
            _add(errors, counts, "condition_errors", f"{process_label}: condition {field} references missing slot {slot_id}")
    followups = record.get("follow_up_rules", [])
    if isinstance(followups, list):
        for index, followup in enumerate(followups):
            if isinstance(followup, dict):
                _check_ids_exist(errors, counts, process_path, process_id, followup.get("when_missing_slot_ids"), slot_set, f"follow_up_rules[{index}]")

    steps = record.get("steps", [])
    step_ids = {x.get("step_id") for x in steps if isinstance(x, dict)} if isinstance(steps, list) else set()
    materials = record.get("materials", [])
    material_ids = {x.get("material_id") for x in materials if isinstance(x, dict)} if isinstance(materials, list) else set()
    service_points = record.get("service_points", [])
    service_ids = {x.get("point_id") for x in service_points if isinstance(x, dict)} if isinstance(service_points, list) else set()
    time_constraints = record.get("time_constraints", [])
    time_ids = {x.get("constraint_id") for x in time_constraints if isinstance(x, dict)} if isinstance(time_constraints, list) else set()

    if isinstance(steps, list):
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            _check_ids_exist(errors, counts, process_path, process_id, step.get("required_material_ids"), material_ids, f"steps[{index}].required_material_ids")
            _check_ids_exist(errors, counts, process_path, process_id, step.get("service_point_ids"), service_ids, f"steps[{index}].service_point_ids")
            _check_ids_exist(errors, counts, process_path, process_id, step.get("time_constraint_ids"), time_ids, f"steps[{index}].time_constraint_ids")
    for field, values, known in (
        ("materials", materials, step_ids),
        ("service_points", service_points, step_ids),
        ("time_constraints", time_constraints, step_ids),
        ("exceptions", record.get("exceptions", []), step_ids),
        ("consequences", record.get("consequences", []), step_ids),
        ("allowed_claims", record.get("allowed_claims", []), step_ids),
    ):
        if not isinstance(values, list):
            continue
        for index, obj in enumerate(values):
            if not isinstance(obj, dict):
                continue
            for key in ("required_at_step_ids", "applies_to_step_ids", "affected_step_ids", "applicable_step_ids"):
                if key in obj:
                    _check_ids_exist(errors, counts, process_path, process_id, obj.get(key), known, f"{field}[{index}].{key}")

    allowed_claims = record.get("allowed_claims", [])
    if isinstance(allowed_claims, list):
        claim_ids: list[str] = []
        claim_evidence_ids: list[str] = []
        for claim in allowed_claims:
            if not isinstance(claim, dict):
                continue
            claim_id = str(claim.get("claim_id", "<unknown>"))
            claim_ids.append(claim_id)
            ids = claim.get("evidence_ids", [])
            if not isinstance(ids, list) or len(ids) != 1:
                _add(errors, counts, "claim_errors", f"{process_label}:{claim_id}: each allowed claim must bind exactly one evidence unit")
                continue
            evidence_id = str(ids[0])
            claim_evidence_ids.append(evidence_id)
            evidence = evidence_by_id.get(evidence_id)
            if evidence is not None:
                if claim.get("text") != evidence.get("normalized_claim"):
                    _add(errors, counts, "claim_errors", f"{process_label}:{claim_id}: allowed-claim text differs from evidence {evidence_id} normalized_claim")
                if claim.get("claim_type") != evidence.get("claim_type"):
                    _add(errors, counts, "claim_errors", f"{process_label}:{claim_id}: allowed-claim type differs from evidence {evidence_id} claim_type")
        if len(claim_ids) != len(set(claim_ids)):
            _add(errors, counts, "claim_errors", f"{process_label}: claim IDs must be unique")
        if set(claim_evidence_ids) != snapshot_ids:
            _add(errors, counts, "claim_errors", f"{process_label}: allowed claims must cover the evidence snapshot exactly; missing={sorted(snapshot_ids - set(claim_evidence_ids))}, extra={sorted(set(claim_evidence_ids) - snapshot_ids)}")

    _check_dag(record, errors, counts, process_path, process_id)

    review = record.get("review", {})
    if isinstance(review, dict) and review.get("status") == "verified" and review.get("annotator") == review.get("reviewer"):
        _add(errors, counts, "review_errors", f"{process_label}: verified review requires different annotator and reviewer identities")

    return len(errors) == before


def validate_process_records(root: Path) -> tuple[list[str], dict[str, int]]:
    """Validate all process records below ``root``.

    Returns a list of human-readable errors and a deterministic count summary.
    The function reports every discovered defect and never changes repository
    data.
    """
    root = Path(root)
    process_path = root / PROCESS_PATH
    evidence_path = root / EVIDENCE_PATH
    process_schema_path = root / PROCESS_SCHEMA_PATH
    evidence_schema_path = root / EVIDENCE_SCHEMA_PATH
    errors: list[str] = []
    counts: Counter[str] = Counter()

    try:
        process_schema = json.loads(process_schema_path.read_text(encoding="utf-8"))
        process_validator = Draft202012Validator(process_schema, format_checker=FormatChecker())
    except (OSError, json.JSONDecodeError) as exc:
        _add(errors, counts, "schema_errors", f"{process_schema_path}: cannot load process schema: {exc}")
        process_validator = None
    except Exception as exc:
        _add(errors, counts, "schema_errors", f"{process_schema_path}: invalid process schema: {exc}")
        process_validator = None

    evidence_rows, evidence_read_errors = _read_jsonl(evidence_path)
    for message in evidence_read_errors:
        _add(errors, counts, "evidence_errors", message)
    evidence_by_id: dict[str, dict[str, Any]] = {}
    try:
        evidence_schema = json.loads(evidence_schema_path.read_text(encoding="utf-8"))
        evidence_validator = Draft202012Validator(evidence_schema, format_checker=FormatChecker())
    except (OSError, json.JSONDecodeError) as exc:
        _add(errors, counts, "schema_errors", f"{evidence_schema_path}: cannot load evidence schema: {exc}")
        evidence_validator = None
    except Exception as exc:
        _add(errors, counts, "schema_errors", f"{evidence_schema_path}: invalid evidence schema: {exc}")
        evidence_validator = None

    for line_no, evidence in evidence_rows:
        if not isinstance(evidence, dict):
            _add(errors, counts, "schema_errors", f"{evidence_path}:{line_no}: evidence record must be a JSON object")
            continue
        evidence_id = str(evidence.get("evidence_id", f"line-{line_no}"))
        if evidence_validator is not None:
            for schema_error in sorted(evidence_validator.iter_errors(evidence), key=lambda item: list(item.absolute_path)):
                _add(errors, counts, "schema_errors", _format_schema_error(evidence_path, line_no, schema_error))
        if evidence_id in evidence_by_id:
            _add(errors, counts, "evidence_errors", f"{evidence_path}:{line_no}: duplicate evidence_id {evidence_id}")
        else:
            evidence_by_id[evidence_id] = evidence

    process_rows, process_read_errors = _read_jsonl(process_path)
    for message in process_read_errors:
        _add(errors, counts, "schema_errors", message)
    counts["records"] = len(process_rows)
    seen_process_ids: set[str] = set()
    valid_records = 0
    for line_no, record in process_rows:
        process_id = str(record.get("process_id", f"line-{line_no}")) if isinstance(record, dict) else f"line-{line_no}"
        if process_id in seen_process_ids:
            _add(errors, counts, "schema_errors", f"{process_path}:{line_no}: duplicate process_id {process_id}")
        seen_process_ids.add(process_id)
        if process_validator is None:
            continue
        if _validate_record(root, process_path, line_no, record, evidence_by_id, process_validator, errors, counts):
            valid_records += 1
    counts["valid_records"] = valid_records
    counts["errors"] = len(errors)
    for key in ("schema_errors", "evidence_errors", "claim_errors", "snapshot_errors", "reference_errors", "condition_errors", "graph_errors", "review_errors"):
        counts.setdefault(key, 0)
    return errors, dict(counts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate process_records.jsonl and evidence bindings")
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors, summary = validate_process_records(args.root)
    for error in errors:
        print(f"[ERROR] {error}")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
