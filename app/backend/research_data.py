"""Load research records independently of the legacy application engine."""
from __future__ import annotations

import json
from pathlib import Path


def read_records(path: Path, key: str) -> dict[str, dict]:
    records = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            identity = row[key]
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"{path.name}:{number}: invalid record") from exc
        if identity in records:
            raise ValueError(f"{path.name}:{number}: duplicate {key} {identity}")
        records[identity] = row
    return records


class ResearchRepository:
    def __init__(self, root: Path):
        directory = Path(root) / "data/research"
        self.sources = read_records(directory / "source_records.jsonl", "source_id")
        self.evidence = read_records(directory / "evidence_units.jsonl", "evidence_id")
        self.processes = read_records(directory / "process_records.jsonl", "process_id")
        for row in self.evidence.values():
            source = self.sources.get(row["source_id"])
            if not source or source["capture"]["status"] != "captured":
                raise ValueError(f"{row['evidence_id']}: missing captured source")
        for process in self.processes.values():
            for identity in process["evidence_snapshot"]["evidence_ids"]:
                row = self.evidence.get(identity)
                if not row or row["item_id"] != process["item_id"]:
                    raise ValueError(f"{process['process_id']}: invalid evidence {identity}")

    def verified_evidence(self, item_id: str, source_ids: set[str] | None = None) -> list[dict]:
        return [row for row in self.evidence.values()
                if row["item_id"] == item_id and row["review"]["status"] == "verified"
                and self.sources[row["source_id"]]["review"]["status"] == "verified"
                and (source_ids is None or row["source_id"] in source_ids)]

    def all_verified_evidence(self) -> list[dict]:
        """Every evidence unit whose own review and source review both passed.

        This is the retrieval pool for every experiment; it carries no label and
        no item hint, so it can be used on the inference side.
        """
        return [row for row in self.evidence.values()
                if row["review"]["status"] == "verified"
                and self.sources[row["source_id"]]["review"]["status"] == "verified"]
