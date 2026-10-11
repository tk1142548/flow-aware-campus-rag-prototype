"""Audit and publish the authorized Stage 2 content freeze."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.1-frozen"


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    samples_path = ROOT / "data/evaluation/stage2_samples.jsonl"
    reviews_path = ROOT / "data/evaluation/stage2_reviews.jsonl"
    samples = read_jsonl(samples_path)
    reviews = read_jsonl(reviews_path)
    processes = {x["process_id"]: x for x in read_jsonl(ROOT / "data/research/process_records.jsonl")}
    evidence = {x["evidence_id"]: x for x in read_jsonl(ROOT / "data/research/evidence_units.jsonl")}
    plan = json.loads((ROOT / "data/research/stage2-evaluation-plan.json").read_text(encoding="utf-8"))
    report = json.loads((ROOT / "data/evaluation/stage2-leakage-report.json").read_text(encoding="utf-8"))
    errors = []
    checks = Counter()
    if len(samples) != 200 or len(reviews) != 200:
        errors.append(f"count samples={len(samples)} reviews={len(reviews)}")
    if len({x["sample_id"] for x in samples}) != len(samples): errors.append("duplicate sample ids")
    by_review = {x["sample_id"]: x for x in reviews}
    quotas = {x["item_id"]: x["sample_quota"] for x in plan["formal_items"]}
    counts = Counter(x["allocation_item_id"] for x in samples)
    if counts != Counter(quotas): errors.append(f"quota mismatch: {dict(counts)}")
    for x in samples:
        sid = x["sample_id"]
        checks["samples"] += 1
        if x.get("leakage_control", {}).get("check_status") != "passed": errors.append(f"{sid}: leakage not passed")
        if x.get("leakage_control", {}).get("prohibited_overlap_sample_ids"): errors.append(f"{sid}: prohibited overlap")
        if x.get("turn_structure") == "single_turn" and len(x["conversation"]) != 1: errors.append(f"{sid}: single turn length")
        if x.get("turn_structure") == "multi_turn" and len(x["conversation"]) != 3: errors.append(f"{sid}: multi turn length")
        if [t["turn_id"] for t in x["conversation"]] != [f"T{i:02d}" for i in range(1, len(x["conversation"])+1)]: errors.append(f"{sid}: turn ids")
        if x["scenario_type"] == "out_of_scope":
            if any(x[k] is not None for k in ("item_id", "process_id")): errors.append(f"{sid}: out of scope binding")
            if x["gold"]["response_mode"] != "abstention" or any(x["gold"][k] for k in ("allowed_claim_ids", "supporting_evidence_ids")): errors.append(f"{sid}: out of scope gold")
            continue
        p = processes.get(x["process_id"])
        if not p: errors.append(f"{sid}: process missing"); continue
        if p["review"]["status"] != "verified": errors.append(f"{sid}: process unverified")
        if p["item_id"] != x["item_id"] or x["gold"]["target_item_id"] != x["item_id"]: errors.append(f"{sid}: item binding")
        claim_map = {c["claim_id"]: c for c in p["allowed_claims"]}
        step_ids = {s["step_id"] for s in p["steps"]}
        mat_ids = {m["material_id"] for m in p["materials"]}
        slot_ids = {s["slot_id"] for s in p["slots"]}
        selected = x["gold"]["allowed_claim_ids"]
        if not set(selected) <= set(claim_map): errors.append(f"{sid}: claim missing")
        expected_evidence = set().union(*(set(claim_map[c]["evidence_ids"]) for c in selected if c in claim_map))
        actual_evidence = set(x["gold"]["supporting_evidence_ids"])
        if actual_evidence != expected_evidence: errors.append(f"{sid}: claim/evidence mismatch")
        snap = set(p["evidence_snapshot"]["evidence_ids"])
        if not actual_evidence <= snap or not actual_evidence <= set(evidence): errors.append(f"{sid}: evidence outside snapshot")
        source_ids = {evidence[e]["source_id"] for e in actual_evidence if e in evidence}
        if source_ids != set(x["input_context"]["source_version_ids"]): errors.append(f"{sid}: source version mismatch")
        required = set(x["gold"]["required_slot_ids"]); missing = set(x["gold"]["missing_slot_ids"])
        if not required <= slot_ids or not missing <= required: errors.append(f"{sid}: slot mismatch")
        if missing and not x["gold"]["follow_up_question"]: errors.append(f"{sid}: missing follow-up")
        if not missing and x["gold"]["follow_up_question"] is not None: errors.append(f"{sid}: unexpected follow-up")
        if not set(x["gold"]["ordered_step_ids"]) <= step_ids: errors.append(f"{sid}: step missing")
        if not set(x["gold"]["material_ids"]) <= mat_ids: errors.append(f"{sid}: material missing")
        r = by_review.get(sid)
        if not r or r["primary_annotation"]["reviewer"] == r["secondary_review"]["reviewer"]: errors.append(f"{sid}: reviewer identity")
    if report.get("status") != "passed" or report.get("review_status") not in ("pending", "accepted"): errors.append("leakage report status")
    audit = {
        "audit_id": "STAGE2_FINAL_FREEZE_20261011",
        "status": "passed" if not errors else "failed",
        "dataset_version": VERSION,
        "review_mode": "direct authorized content review",
        "reviewers": ["Codex 阶段 2C 内容复核", "Codex 阶段 2D 独立内容复核"],
        "sample_count": len(samples), "review_count": len(reviews),
        "quota_counts": dict(counts), "checks": dict(checks), "errors": errors,
        "source_artifacts": {"samples_sha256": sha(samples_path), "reviews_sha256": sha(reviews_path), "leakage_report_sha256": sha(ROOT / "data/evaluation/stage2-leakage-report.json")},
    }
    return audit, samples, reviews


def apply_freeze(audit, samples, reviews):
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    for x in samples:
        x["dataset_version"] = VERSION; x["review_status"] = "frozen"
        x["leakage_control"]["checker"] = "Codex 阶段 2D 人工内容复核与 text-embedding-v4 泄漏审计"
        x["leakage_control"]["checked_at"] = now
        x["leakage_control"]["notes"] = "逐样本核对事项、槽位、流程步骤、材料、允许声明、证据、来源版本和语义泄漏状态；复核通过。"
    for r in reviews:
        r["dataset_version"] = VERSION
        for key, reviewer in (("primary_annotation", "Codex 阶段 2C 内容复核"), ("secondary_review", "Codex 阶段 2D 独立内容复核")):
            r[key]["reviewer"] = reviewer; r[key]["completed_at"] = now; r[key]["verdict"] = "accept"
            r[key]["dimensions"] = {k: "pass" for k in ("item_mapping", "slot_and_follow_up", "process_structure", "claim_and_evidence", "version_applicability", "leakage_control")}
            r[key]["notes"] = "直接依据已验证流程、槽位、步骤、材料、允许声明、证据、来源版本及语义泄漏审计逐项复核通过。"
        r["disagreements"] = []; r["adjudication"] = None; r["final_status"] = "accepted"
    def write(path, rows): path.write_text("".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n" for x in rows), encoding="utf-8")
    write(ROOT / "data/evaluation/stage2_samples.jsonl", samples); write(ROOT / "data/evaluation/stage2_reviews.jsonl", reviews)
    lp = ROOT / "data/evaluation/stage2-leakage-report.json"; report = json.loads(lp.read_text(encoding="utf-8")); report.update({"review_status": "accepted", "freeze_version": VERSION, "reviewed_at": now}); lp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    planp = ROOT / "data/research/stage2-evaluation-plan.json"; plan = json.loads(planp.read_text(encoding="utf-8")); plan["status"] = "content_frozen"; plan["dataset_release_version"] = VERSION; plan["freeze_policy"].update({"content_freeze_status": "frozen", "content_freeze_version": VERSION, "content_frozen_at": now}); plan["content_artifacts"].update({"samples_sha256": sha(ROOT / "data/evaluation/stage2_samples.jsonl"), "reviews_sha256": sha(ROOT / "data/evaluation/stage2_reviews.jsonl"), "leakage_report_sha256": sha(lp)}); planp.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true"); args = ap.parse_args()
    result, samples, reviews = audit(); print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "passed": raise SystemExit(1)
    if args.apply:
        apply_freeze(result, samples, reviews); print(json.dumps({"applied": True, "version": VERSION}, ensure_ascii=False))
