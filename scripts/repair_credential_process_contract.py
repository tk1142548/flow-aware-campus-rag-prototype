"""Align credential process nodes with the claim types in saved evidence."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path


PATH = Path("data/research/process_records.jsonl")


def _atomic_write(path: Path, rows: list[dict]) -> None:
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _rebuild_materials(process: dict, evidence_ids: list[str]) -> None:
    old = {item["evidence_ids"][0]: item for item in process["materials"]}
    materials = []
    for index, evidence_id in enumerate(evidence_ids, 1):
        item = old[evidence_id]
        item["material_id"] = f"MAT_{index:02d}"
        materials.append(item)
    process["materials"] = materials
    for step in process["steps"]:
        step["required_material_ids"] = [item["material_id"] for item in materials if step["step_id"] in item["required_at_step_ids"]]


def repair(path: Path = PATH) -> None:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for process in rows:
        if process["process_id"] == "PROC_UG_CREDENTIAL_DEGREE_V001":
            _rebuild_materials(process, ["UGC006", "UGC007", "UGC008"])
            process["time_constraints"] = [
                {"constraint_id": "TIME_01", "text": "受理时间为每年3月至6月、9月至12月。", "conditions": [], "applies_to_step_ids": ["ST_01"], "evidence_ids": ["UGC003"]},
                {"constraint_id": "TIME_02", "text": "学籍科收到材料后在10个工作日内通知领取学位证明书。", "conditions": [], "applies_to_step_ids": ["ST_02"], "evidence_ids": ["UGC005"]},
            ]
            process["steps"][0]["evidence_ids"] = ["UGC001", "UGC002", "UGC003", "UGC004", "UGC009"]
            process["steps"][1]["evidence_ids"] = ["UGC005"]
            process["steps"][2]["evidence_ids"] = ["UGC010"]
        elif process["process_id"] == "PROC_UG_CREDENTIAL_DIPLOMA_V001":
            process["slots"] = [slot for slot in process["slots"] if slot["slot_id"] != "SL_DIPLOMA_COPY"]
            process["slots"].append({"slot_id": "SL_DIPLOMA_COPY", "name": "是否有毕业证书复印件", "value_type": "boolean", "required_for_resolution": False, "allowed_values": [], "unknown_policy": "allow_unknown", "evidence_ids": ["UGC016"]})
            _rebuild_materials(process, ["UGC012", "UGC013", "UGC014", "UGC015", "UGC016", "UGC017", "UGC018"])
            process["materials"][4]["required_when"] = [{"slot_id": "SL_DIPLOMA_COPY", "operator": "equals", "value": "true"}]
            process["steps"][0]["evidence_ids"] = ["UGC011", "UGC012", "UGC013", "UGC014", "UGC015", "UGC016", "UGC017", "UGC018"]
            process["steps"][1]["evidence_ids"] = ["UGC019", "UGC020"]
            process["steps"][2]["evidence_ids"] = ["UGC021"]
    evidence_path = Path("data/research/evidence_units.jsonl")
    digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    for process in rows:
        process["evidence_snapshot"]["dataset_sha256"] = digest
    _atomic_write(path, rows)


if __name__ == "__main__":
    repair()
