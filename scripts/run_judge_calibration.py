"""Judge-supported calibration slice.

Runs the LLM judge over a fixed slice of answers and writes a table a human can
check by hand. The judge is not a primary metric -- TREC 2024 RAG Track measured
only 56% agreement between GPT-4o and human support judgements -- so its output
is only useful once the agreement rate on this slice is known.

Usage:
    python scripts/run_judge_calibration.py [--per-config 30] [--output PATH]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.api_client import ApiClient
from app.backend.research_data import ResearchRepository
from app.backend.scoring_v2 import judge_support

CONFIGS = ("baseline_c", "ablation_no_flow", "method_v2")


def question_of(sample: dict) -> str:
    return "\n".join(t["text"] for t in sample["conversation"] if t["role"] == "user")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-config", type=int, default=30,
                        help="how many answers per configuration enter the slice")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data/experiments/judge-calibration.json")
    parser.add_argument("--csv", type=Path,
                        default=ROOT / "data/experiments/judge-calibration.csv")
    args = parser.parse_args()

    started = time.perf_counter()
    repository = ResearchRepository(ROOT)
    client = ApiClient(ROOT / "data/cache")
    results = json.loads(
        (ROOT / "data/experiments/baselines-final.json").read_text(encoding="utf-8"))
    samples = {row["sample_id"]: row for row in
               (json.loads(line) for line in
                (ROOT / "data/evaluation/stage2_samples.jsonl")
                .read_text(encoding="utf-8").splitlines() if line)}

    # Round-robin across risk categories so the slice is not all one scenario type.
    by_category: dict[str, list[str]] = defaultdict(list)
    for record in results["samples"][CONFIGS[0]]:
        sample_id = record["sample_id"]
        if sample_id in samples:
            by_category[samples[sample_id]["scenario_type"]].append(sample_id)
    ordered: list[str] = []
    while any(by_category.values()):
        for key in sorted(by_category):
            if by_category[key]:
                ordered.append(by_category[key].pop(0))
    slice_ids = ordered[: args.per_config]

    jobs = [(config, sample_id) for config in CONFIGS for sample_id in slice_ids]

    def run(job: tuple[str, str]) -> dict:
        config, sample_id = job
        record = next(r for r in results["samples"][config] if r["sample_id"] == sample_id)
        evidence = [repository.evidence[eid] for eid in record["retrieved_evidence_ids"]
                    if eid in repository.evidence]
        verdict = judge_support(client, question_of(samples[sample_id]),
                                record["prediction"]["answer_text"], evidence)
        return {
            "config": config,
            "sample_id": sample_id,
            "item_id": record["item_id"],
            "scenario_type": samples[sample_id]["scenario_type"],
            "question": question_of(samples[sample_id]),
            "answer": record["prediction"]["answer_text"],
            "evidence_ids": record["retrieved_evidence_ids"],
            "unsupported_ratio": verdict.get("unsupported_ratio"),
            "judge_items": verdict.get("supported") or [],
            "judge_reason": verdict.get("reason", ""),
            "judge_error": verdict.get("error"),
        }

    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(run, jobs))

    summary = {}
    for config in CONFIGS:
        values = [r["unsupported_ratio"] for r in rows
                  if r["config"] == config and r["unsupported_ratio"] is not None]
        items = [i for r in rows if r["config"] == config for i in r["judge_items"]]
        summary[config] = {
            "judged": len(values),
            "mean_unsupported_ratio": sum(values) / len(values) if values else None,
            "claims_judged": len(items),
            "claims_unsupported": sum(1 for i in items if i.get("verdict") == "unsupported"),
        }

    payload = {
        "status": "待人工校准",
        "protocol": {
            "per_config": args.per_config,
            "configs": CONFIGS,
            "note": "判官仅用于校准切片，不作为主指标；需人工逐条核对后计算一致率",
        },
        "sample_count": len(rows),
        "summary": summary,
        "rows": rows,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.perf_counter() - started,
        "cost": client.cost_summary(),
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    with args.csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["配置", "样本", "场景", "判官：无据比例", "判官：不支持的陈述",
                         "人工判定(支持/不支持/部分)", "人工备注", "证据编号"])
        for row in rows:
            unsupported = " | ".join(i.get("claim", "") for i in row["judge_items"]
                                     if i.get("verdict") == "unsupported")
            writer.writerow([row["config"], row["sample_id"], row["scenario_type"],
                             row["unsupported_ratio"], unsupported, "", "",
                             ",".join(row["evidence_ids"])])

    print(f"{'配置':<18}{'判官条数':>8}{'平均无据比例':>12}{'陈述条数':>8}{'判为无据':>8}")
    for config, entry in summary.items():
        ratio = entry["mean_unsupported_ratio"]
        print(f"{config:<18}{entry['judged']:>8}"
              f"{(f'{ratio:.4f}' if ratio is not None else 'n/a'):>12}"
              f"{entry['claims_judged']:>8}{entry['claims_unsupported']:>8}")
    print(f"\n切片 {len(rows)} 条 -> {args.output.name} 与 {args.csv.name}")
    print(f"cost: {json.dumps(client.cost_summary(), ensure_ascii=False)}")
    print(f"elapsed: {payload['elapsed_seconds']:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
