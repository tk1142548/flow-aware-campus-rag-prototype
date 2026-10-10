"""Validate stage 2 sample, review, process and evidence bindings."""
from __future__ import annotations
import json, hashlib
from pathlib import Path
from jsonschema import Draft202012Validator
try:
    from scripts.audit_stage2_content import audit
except ModuleNotFoundError:
    from audit_stage2_content import audit

ROOT=Path(__file__).resolve().parents[1]
def load_jsonl(path): return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
def main():
    samples=load_jsonl(ROOT/"data/evaluation/stage2_samples.jsonl"); reviews=load_jsonl(ROOT/"data/evaluation/stage2_reviews.jsonl")
    ss=json.loads((ROOT/"data/schemas/evaluation-sample.schema.json").read_text(encoding="utf-8")); rs=json.loads((ROOT/"data/schemas/evaluation-review-record.schema.json").read_text(encoding="utf-8"))
    errors=[]
    for x in samples: errors.extend(e.message for e in Draft202012Validator(ss).iter_errors(x))
    for x in reviews: errors.extend(e.message for e in Draft202012Validator(rs).iter_errors(x))
    if len(samples)!=200 or len(reviews)!=200: errors.append("sample and review counts must both equal 200")
    if len({x["sample_id"] for x in samples})!=200 or len({x["sample_id"] for x in reviews})!=200: errors.append("sample IDs must be unique and fully reviewed")
    evidence={x["evidence_id"] for x in load_jsonl(ROOT/"data/research/evidence_units.jsonl")}
    processes={x["process_id"]:x for x in load_jsonl(ROOT/"data/research/process_records.jsonl")}
    for x in samples:
        if x["scenario_type"]!="out_of_scope":
            if x["process_id"] not in processes or processes[x["process_id"]]["review"]["status"]!="verified": errors.append(f"{x['sample_id']}: process not verified")
            if not set(x["gold"]["supporting_evidence_ids"]).issubset(evidence): errors.append(f"{x['sample_id']}: evidence reference missing")
        review=next((r for r in reviews if r["sample_id"]==x["sample_id"]),None)
        if review is None or review["primary_annotation"]["reviewer"]==review["secondary_review"]["reviewer"] or review["final_status"]!="accepted": errors.append(f"{x['sample_id']}: review contract failed")
    report=json.loads((ROOT/"data/evaluation/stage2-leakage-report.json").read_text(encoding="utf-8"))
    if report.get("status")!="passed" or report.get("duplicate_metadata_keys")!=0: errors.append("leakage report failed")
    entry_audit = audit(ROOT)
    if entry_audit["duplicate_excess"]:
        errors.append(f"actual conversation duplicates: {entry_audit['duplicate_excess']}")
    errors.extend(json.dumps(error, ensure_ascii=False) for error in entry_audit["link_errors"])
    if errors:
        for e in errors[:20]: print("[ERROR]",e)
        return 1
    print(json.dumps({"samples":len(samples),"reviews":len(reviews),"status":"passed","sample_sha256":hashlib.sha256((ROOT/"data/evaluation/stage2_samples.jsonl").read_bytes()).hexdigest(),"review_sha256":hashlib.sha256((ROOT/"data/evaluation/stage2_reviews.jsonl").read_bytes()).hexdigest()},ensure_ascii=False))
    return 0
if __name__=="__main__": raise SystemExit(main())
