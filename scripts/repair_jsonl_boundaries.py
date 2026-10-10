"""Recover JSON object boundaries without changing any record values."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path


def decode_records(text: str) -> list[dict]:
    decoder = json.JSONDecoder()
    records = []
    offset = 0
    while offset < len(text):
        while offset < len(text):
            if text[offset].isspace():
                offset += 1
            elif text.startswith((r"\n", r"\r"), offset):
                offset += 2
            else:
                break
        if offset == len(text):
            break
        record, offset = decoder.raw_decode(text, offset)
        if not isinstance(record, dict):
            raise ValueError("JSONL records must be objects")
        records.append(record)
    if not records:
        raise ValueError("No records to recover")
    return records


def repair(path: Path, backup: Path) -> int:
    original = path.read_bytes()
    records = decode_records(original.decode("utf-8"))
    serialized = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in records)
    if [json.loads(line) for line in serialized.splitlines()] != records:
        raise ValueError("Round-trip changed record values")
    backup.parent.mkdir(parents=True, exist_ok=True)
    with backup.open("xb") as stream:
        stream.write(original)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--backup", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps({"recovered_records": repair(args.path, args.backup)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
