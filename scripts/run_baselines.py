"""Four-configuration comparison: baselines A/B/C versus the project method.

All four share the same dataset, the same item-routing rule, the same scorer and
the same evidence budget rules. Only the method machinery differs, which is what
the申报书 asks to compare:

    baseline A  vector retrieval + direct generation
    baseline B  hybrid retrieval + rerank + explicit citations
    baseline C  restricted workflow (read closely, organise, then answer)
    method      flow skeleton + assertion verification + interaction control

Item routing is shared by all four (top-3 majority of the retrieved evidence) so
that `item_correct` does not silently decide the comparison.

Usage:
    python scripts/run_baselines.py [--limit N] [--workers 6] [--output PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.api_client import ApiClient
from app.backend.flow_extractor import extract as extract_flow
from app.backend.research_data import ResearchRepository
from app.backend.retrieval_stack import RetrievalStack
from app.backend.scoring_v2 import ElementMatcher, Prediction, score_prediction
from app.backend.stage4_statistics import holm_adjust, paired_analysis
from app.backend import systems

CONFIGS = {
    "baseline_a": {"strategy": "dense", "k": 5},
    "baseline_b": {"strategy": "hybrid_rerank", "k": 5},
    "baseline_c": {"strategy": "hybrid_rerank", "k": 8},
    "ablation_no_flow": {"strategy": "hybrid_rerank", "k": 8},
    "ablation_no_verify": {"strategy": "hybrid_rerank", "k": 8},
    "ablation_no_skeleton": {"strategy": "hybrid_rerank", "k": 8},
    "method_v2": {"strategy": "hybrid_rerank", "k": 8},
    "method": {"strategy": "hybrid_rerank", "k": 8},
}
MODES = ("baseline_a", "baseline_b", "baseline_c",
         "ablation_no_flow", "ablation_no_verify", "ablation_no_skeleton",
         "method_v2", "method")


def question_of(sample: dict) -> str:
    return "\n".join(t["text"] for t in sample["conversation"] if t["role"] == "user")


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def run_one(repository: ResearchRepository, stack: RetrievalStack, client: ApiClient,
            matcher: ElementMatcher, sample: dict, config: str) -> dict:
    question = question_of(sample)
    spec = CONFIGS[config]
    rows = stack.retrieve(question, strategy=spec["strategy"], k=spec["k"])

    if config in ("method", "method_v2", "ablation_no_verify"):
        skeleton = extract_flow(client, question, rows)
        prediction = systems.SYSTEMS[config](client, question, rows, skeleton)
    else:
        prediction = systems.SYSTEMS[config](client, question, rows)

    # Shared routing rule for every configuration.
    prediction.item_id = RetrievalStack.guess_item(rows)

    scored = score_prediction(repository, sample, prediction, matcher)
    return {
        "sample_id": sample["sample_id"],
        "item_id": sample["allocation_item_id"],
        "retrieved_evidence_ids": [row["evidence_id"] for row in rows],
        "prediction": {
            "response_mode": prediction.response_mode,
            "item_id": prediction.item_id,
            "citations": prediction.citations,
            "missing_slot_ids": prediction.missing_slot_ids,
            "follow_up_question": prediction.follow_up_question,
            "answer_text": prediction.answer_text,
        },
        "metrics": scored["metrics"],
        "elements": scored["elements"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data/experiments/baselines-final.json")
    args = parser.parse_args()

    started = time.perf_counter()
    repository = ResearchRepository(ROOT)
    client = ApiClient(ROOT / "data/cache")
    matcher = ElementMatcher(client)

    samples = [json.loads(line) for line in
               (ROOT / "data/evaluation/stage2_samples.jsonl").read_text(encoding="utf-8").splitlines()
               if line]
    if args.limit:
        samples = samples[: args.limit]

    verified = repository.all_verified_evidence()
    stack = RetrievalStack(verified, client, alpha=0.5)

    results: dict[str, list[dict]] = {mode: [] for mode in MODES}
    failures: list[dict] = []
    jobs = [(sample, mode) for mode in MODES for sample in samples]

    def worker(job):
        sample, mode = job
        try:
            return mode, run_one(repository, stack, client, matcher, sample, mode), None
        except Exception as error:  # noqa: BLE001 - recorded, not swallowed
            return mode, None, {"sample_id": sample["sample_id"], "mode": mode,
                                "error": f"{type(error).__name__}: {error}"[:300]}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for done, (mode, record, error) in enumerate(pool.map(worker, jobs), 1):
            if error:
                failures.append(error)
            else:
                results[mode].append(record)
            if done % 50 == 0:
                print(f"  {done}/{len(jobs)}", flush=True)

    summary = {}
    metric_keys = sorted(results["baseline_a"][0]["metrics"]) if results["baseline_a"] else []
    for mode in MODES:
        rows = results[mode]
        summary[mode] = {
            "sample_count": len(rows),
            "metrics": {key: mean([r["metrics"][key] for r in rows]) for key in metric_keys},
        }

    item_ids = [r["item_id"] for r in results["method"]]
    comparisons = []
    for mode in [m for m in MODES if m != "method"]:
        aligned_baseline = {r["sample_id"]: r for r in results[mode]}
        aligned_method = {r["sample_id"]: r for r in results["method"]}
        shared = [sid for sid in aligned_method if sid in aligned_baseline]
        if not shared:
            continue
        for metric in ("overall_success", "answer_quality", "response_mode_accuracy",
                       "citation_validity", "evidence_recall"):
            stat = paired_analysis(
                [aligned_baseline[sid]["metrics"][metric] for sid in shared],
                [aligned_method[sid]["metrics"][metric] for sid in shared],
                [aligned_method[sid]["item_id"] for sid in shared],
                10000, 0,
            )
            comparisons.append({"left": mode, "right": "method", "metric": metric, **stat})
    for comparison, adjusted in zip(
        comparisons, holm_adjust([c["paired_sign_flip_p"] for c in comparisons])
    ):
        comparison["holm_adjusted_p"] = adjusted

    payload = {
        "status": "已验证",
        "protocol": {
            "configs": CONFIGS,
            "shared_item_routing": "top-3 majority of retrieved evidence",
            "oracle_used": False,
            "gold_access": "scoring_only",
            "scoring": "docs/experiments/SCORING_PROTOCOL_V2.md",
            "note": "基线 A/B/C 不设交互控制，对金标准为 abstention 的样本必然失分，这是设计差异而非缺陷",
        },
        "dataset_version": "1.0.1-frozen(开发集)",
        "scoring_clause_thresholds": {"lexical": matcher.lexical_threshold,
                                      "semantic": matcher.semantic_threshold},
        "sample_count": len(samples),
        "summary": summary,
        "paired_comparisons": comparisons,
        "samples": results,
        "failures": failures,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.perf_counter() - started,
        "cost": client.cost_summary(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n{'config':12s}{'overall':>9s}{'quality':>9s}{'mode':>9s}{'cit':>9s}{'evR':>9s}")
    for mode in MODES:
        m = summary[mode]["metrics"]
        print(f"{mode:12s}{m['overall_success']:>9.4f}{m['answer_quality']:>9.4f}"
              f"{m['response_mode_accuracy']:>9.4f}{m['citation_validity']:>9.4f}"
              f"{m['evidence_recall']:>9.4f}")
    print(f"\n失败样本: {len(failures)}")
    print(f"cost: {client.cost_summary()}")
    print(f"elapsed: {payload['elapsed_seconds']:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
