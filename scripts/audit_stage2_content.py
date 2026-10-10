"""Check evaluation linkage and actual conversation duplication."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def audit(root: Path) -> dict:
    def rows(relative):
        return [json.loads(line) for line in (root / relative).read_text(encoding="utf-8").splitlines() if line.strip()]
    samples = rows("data/evaluation/stage2_samples.jsonl")
    processes = {p["process_id"]: p for p in rows("data/research/process_records.jsonl")}
    errors = []
    conversations = Counter(tuple((turn["role"], turn["text"].strip()) for turn in s["conversation"]) for s in samples)
    for s in samples:
        process = processes.get(s["process_id"])
        if s["process_id"] is None:
            continue
        if not process:
            errors.append({"sample_id": s["sample_id"], "code": "missing_process"})
            continue
        gold = s["gold"]
        missing = set(gold["supporting_evidence_ids"]) - set(process["evidence_snapshot"]["evidence_ids"])
        if missing:
            errors.append({"sample_id": s["sample_id"], "code": "evidence_outside_process", "ids": sorted(missing)})
        claims = {c["claim_id"]: c for c in process["allowed_claims"]}
        bound = set()
        for identity in gold["allowed_claim_ids"]:
            if identity not in claims:
                errors.append({"sample_id": s["sample_id"], "code": "missing_claim"})
            else:
                bound.update(claims[identity]["evidence_ids"])
        if bound != set(gold["supporting_evidence_ids"]):
            errors.append({"sample_id": s["sample_id"], "code": "claim_evidence_mismatch"})
    plan = json.loads((root / "data/research/stage2-evaluation-plan.json").read_text(encoding="utf-8"))
    versions = sorted({s["dataset_version"] for s in samples})
    if versions != [plan["dataset_release_version"]]:
        errors.append({"code": "release_version_mismatch", "sample_versions": versions, "plan_version": plan["dataset_release_version"]})
    duplicate_excess = sum(n-1 for n in conversations.values())
    return {"status": "阻塞" if errors or duplicate_excess else "已完成待验证", "sample_count": len(samples), "unique_conversations": len(conversations), "duplicate_excess": duplicate_excess, "link_errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(Path(__file__).resolve().parents[1])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: v if k != "link_errors" else len(v) for k, v in result.items()}, ensure_ascii=False))
    return 1 if result["status"] == "阻塞" else 0


if __name__ == "__main__":
    raise SystemExit(main())
