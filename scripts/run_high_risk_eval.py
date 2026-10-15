"""Run the four configurations over the newly authored 过期入口 samples.

The other 80 high-risk samples already live in the dev set and are scored by
`run_baselines.py`; re-running them here would just duplicate those numbers.
By default this script therefore evaluates only the samples with
``origin == authored_2026-10-14``.

Usage:
    python scripts/run_high_risk_eval.py [--all] [--output PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.api_client import ApiClient
from app.backend.flow_extractor import extract as extract_flow
from app.backend.research_data import ResearchRepository
from app.backend.retrieval_stack import RetrievalStack
from app.backend.scoring_v2 import ElementMatcher, score_prediction
from app.backend import systems

from scripts.run_baselines import CONFIGS, MODES, question_of


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true",
                        help="evaluate every high-risk sample, not just the authored ones")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data/experiments/high-risk-results.json")
    args = parser.parse_args()

    repository = ResearchRepository(ROOT)
    client = ApiClient(ROOT / "data/cache")
    matcher = ElementMatcher(client)

    records = [json.loads(line) for line in
               (ROOT / "data/evaluation/high-risk-set.jsonl").read_text(encoding="utf-8").splitlines()
               if line]
    if not args.all:
        records = [r for r in records if r["origin"].startswith("authored")]

    verified = repository.all_verified_evidence()
    stack = RetrievalStack(verified, client, alpha=0.5)

    # The authored records carry a subset of the sample schema; the scorer only
    # needs item_id, process_id, scenario_type and gold.
    results = {}
    for record in records:
        sample = {"sample_id": record["sample_id"], "item_id": record["item_id"],
                  "allocation_item_id": record["item_id"], "process_id": record["process_id"],
                  "scenario_type": record["scenario_type"], "gold": record["gold"],
                  "conversation": record["conversation"]}
        question = question_of(sample)
        per_mode = {}
        for mode in MODES:
            spec = CONFIGS[mode]
            rows = stack.retrieve(question, strategy=spec["strategy"], k=spec["k"])
            if mode in ("method", "method_v2", "ablation_no_verify"):
                skeleton = extract_flow(client, question, rows)
                prediction = systems.SYSTEMS[mode](client, question, rows, skeleton)
            else:
                prediction = systems.SYSTEMS[mode](client, question, rows)
            prediction.item_id = RetrievalStack.guess_item(rows)
            scored = score_prediction(repository, sample, prediction, matcher)
            per_mode[mode] = {
                "response_mode": prediction.response_mode,
                "overall_success": scored["metrics"]["overall_success"],
                "metrics": scored["metrics"],
                "answer_text": prediction.answer_text[:600],
                "elements": scored["elements"],
            }
        results[record["sample_id"]] = {
            "risk_category": record["risk_category"],
            "question": question,
            "answer_boundary": record["gold"]["answer_boundary"],
            "modes": per_mode,
        }

    def mean(values):
        return sum(values) / len(values) if values else 0.0

    summary = {mode: {"overall_success": mean(
        [r["modes"][mode]["overall_success"] for r in results.values()])} for mode in MODES}

    payload = {"status": "已验证", "sample_count": len(results),
               "summary": summary, "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"过期入口样本 {len(results)} 条")
    for record_id, entry in results.items():
        print(f"\n--- {record_id} --- {entry['question']}")
        for mode in MODES:
            m = entry["modes"][mode]
            print(f"   {mode:12s} success={m['overall_success']:.0f} "
                  f"mode={m['response_mode']:18s} {m['answer_text'][:100]}")
    print("\n各配置成功率:", {k: round(v["overall_success"], 3) for k, v in summary.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
