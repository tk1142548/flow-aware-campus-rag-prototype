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
    "ablation_v2_no_verify": {"strategy": "hybrid_rerank", "k": 8},
    "ablation_v2_no_skeleton": {"strategy": "hybrid_rerank", "k": 8},
    "ablation_no_version_limit": {"strategy": "hybrid_rerank", "k": 8},
    "method_v2": {"strategy": "hybrid_rerank", "k": 8},
    "method_v3": {"strategy": "hybrid_rerank", "k": 8},
    "method": {"strategy": "hybrid_rerank", "k": 8},
}
MODES = ("baseline_a", "baseline_b", "baseline_c",
         "ablation_no_flow", "ablation_no_verify", "ablation_no_skeleton",
         "ablation_v2_no_verify", "ablation_v2_no_skeleton",
         "ablation_no_version_limit",
         "method_v2", "method_v3", "method")

# Configurations that read an extracted flow skeleton before answering.
USES_SKELETON = ("method", "method_v2", "method_v3",
                 "ablation_no_verify", "ablation_v2_no_verify",
                 "ablation_no_version_limit")

# Every metric the scorer returns, listed explicitly so that a checkpoint written
# while some configurations are still running still has a stable set of columns.
SAMPLE_METRIC_KEYS = (
    "item_correct", "response_mode_accuracy", "evidence_recall", "evidence_precision",
    "missing_slot_f1", "follow_up_correct", "citation_validity",
    "claim_coverage", "step_coverage", "material_coverage",
    "answer_quality", "overall_success",
)


def question_of(sample: dict) -> str:
    return "\n".join(t["text"] for t in sample["conversation"] if t["role"] == "user")


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


class EmptyAnswer(RuntimeError):
    """The system returned nothing where an answer was required.

    Almost always an upstream call that failed or returned unparsable output. It
    must surface as a failure: scored as a normal answer it silently deflates the
    metrics and the failure list stays empty, which is how a quota outage turns
    into a fake result.
    """


def run_one(repository: ResearchRepository, stack: RetrievalStack, client: ApiClient,
            matcher: ElementMatcher, sample: dict, config: str) -> dict:
    question = question_of(sample)
    spec = CONFIGS[config]
    rows = stack.retrieve(question, strategy=spec["strategy"], k=spec["k"])

    if config in USES_SKELETON:
        skeleton = extract_flow(client, question, rows)
        prediction = systems.SYSTEMS[config](client, question, rows, skeleton)
    else:
        prediction = systems.SYSTEMS[config](client, question, rows)

    # Shared routing rule for every configuration.
    prediction.item_id = RetrievalStack.guess_item(rows)

    if not prediction.answer_text.strip() and sample["gold"]["response_mode"] != "abstention":
        raise EmptyAnswer(f"{config} 未产出回答（接口失败或输出无法解析）")

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
    parser.add_argument("--samples", type=Path,
                        default=ROOT / "data/evaluation/stage2_samples.jsonl",
                        help="evaluation set to run on (development or independent)")
    parser.add_argument("--dataset-label", default="开发集")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data/experiments/baselines-final.json")
    parser.add_argument("--resume", action="store_true",
                        help="skip runs already recorded in the output file")
    parser.add_argument("--checkpoint-every", type=int, default=50,
                        help="write a partial result file every N completed runs")
    args = parser.parse_args()

    started = time.perf_counter()
    repository = ResearchRepository(ROOT)
    client = ApiClient(ROOT / "data/cache")
    matcher = ElementMatcher(client)

    # Preflight: abort before a long run if the model endpoint is unreachable.
    try:
        client.chat([{"role": "user", "content": "ping"}], max_tokens=4)
        print("接口探活：正常", flush=True)
    except Exception as error:  # noqa: BLE001 - reported, then abort
        print(f"接口探活失败，已中止：{type(error).__name__}: {error}")
        return 2

    samples = [json.loads(line) for line in
               args.samples.read_text(encoding="utf-8").splitlines()
               if line]
    if args.limit:
        samples = samples[: args.limit]

    verified = repository.all_verified_evidence()
    stack = RetrievalStack(verified, client, alpha=0.5)

    results: dict[str, list[dict]] = {mode: [] for mode in MODES}
    failures: list[dict] = []
    done: set[tuple[str, str]] = set()
    if args.resume and args.output.exists():
        previous = json.loads(args.output.read_text(encoding="utf-8"))
        for mode, rows in (previous.get("samples") or {}).items():
            if mode in results:
                results[mode] = rows
                done.update((mode, row["sample_id"]) for row in rows)
        failures = previous.get("failures") or []
        print(f"续跑：已有 {len(done)} 条记录", flush=True)

    jobs = [(sample, mode) for mode in MODES for sample in samples
            if (mode, sample["sample_id"]) not in done]
    # A resumed run retries what failed last time, so those failure entries are
    # dropped first; otherwise the list would grow a duplicate on every attempt.
    retrying = {(mode, sample["sample_id"]) for sample, mode in jobs}
    failures = [failure for failure in failures
                if (failure["mode"], failure["sample_id"]) not in retrying]
    print(f"待跑 {len(jobs)} / {len(MODES) * len(samples)}", flush=True)

    metric_keys = sorted(SAMPLE_METRIC_KEYS)

    def build_payload(complete: bool) -> dict:
        summary = {}
        for mode in MODES:
            rows = results[mode]
            summary[mode] = {
                "sample_count": len(rows),
                "metrics": {key: mean([r["metrics"][key] for r in rows]) for key in metric_keys},
            }

        comparisons = []
        for mode in [m for m in MODES if m != "method"]:
            aligned_left = {r["sample_id"]: r for r in results[mode]}
            aligned_right = {r["sample_id"]: r for r in results["method"]}
            shared = [sid for sid in aligned_right if sid in aligned_left]
            if not shared:
                continue
            for metric in ("overall_success", "answer_quality", "response_mode_accuracy",
                           "citation_validity", "evidence_recall"):
                stat = paired_analysis(
                    [aligned_left[sid]["metrics"][metric] for sid in shared],
                    [aligned_right[sid]["metrics"][metric] for sid in shared],
                    [aligned_right[sid]["item_id"] for sid in shared],
                    10000, 0,
                )
                comparisons.append({"left": mode, "right": "method", "metric": metric, **stat})
        for comparison, adjusted in zip(
            comparisons, holm_adjust([c["paired_sign_flip_p"] for c in comparisons])
        ):
            comparison["holm_adjusted_p"] = adjusted

        return {
            "status": "已验证" if complete else "进行中",
            "protocol": {
                "configs": CONFIGS,
                "shared_item_routing": "top-3 majority of retrieved evidence",
                "oracle_used": False,
                "gold_access": "scoring_only",
                "scoring": "docs/experiments/SCORING_PROTOCOL_V2.md",
                "note": "基线 A/B/C 不设交互控制，对金标准为 abstention 的样本必然失分，这是设计差异而非缺陷",
            },
            "dataset": args.dataset_label,
            "samples_path": str(args.samples if not args.samples.is_absolute()
                                else args.samples.relative_to(ROOT)),
            "scoring_clause_thresholds": {"lexical": matcher.lexical_threshold,
                                          "semantic": matcher.semantic_threshold},
            "sample_count": len(samples),
            "summary": summary,
            "paired_comparisons": comparisons,
            "samples": results,
            "failures": failures,
            "empty_answers": {mode: sum(1 for r in results[mode]
                                        if not r["prediction"]["answer_text"].strip())
                              for mode in MODES},
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": time.perf_counter() - started,
            "cost": client.cost_summary(),
        }

    def write_payload(complete: bool) -> None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(build_payload(complete), ensure_ascii=False, indent=1),
                               encoding="utf-8")

    def worker(job):
        sample, mode = job
        try:
            return mode, run_one(repository, stack, client, matcher, sample, mode), None
        except Exception as error:  # noqa: BLE001 - recorded, not swallowed
            return mode, None, {"sample_id": sample["sample_id"], "mode": mode,
                                "error": f"{type(error).__name__}: {error}"[:300]}

    # A long run is checkpointed as it goes: a crash must not throw away every
    # completed call, and the caller can resume from what was written.
    if jobs:
        write_payload(complete=False)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for done_count, (mode, record, error) in enumerate(pool.map(worker, jobs), 1):
                if error:
                    failures.append(error)
                else:
                    results[mode].append(record)
                if done_count % args.checkpoint_every == 0:
                    write_payload(complete=False)
                if done_count % 100 == 0:
                    print(f"  {done_count}/{len(jobs)}", flush=True)

    incomplete = [mode for mode in MODES if len(results[mode]) != len(samples)]
    write_payload(complete=not incomplete)

    final_summary = build_payload(complete=True)["summary"]
    print(f"\n{'config':12s}{'overall':>9s}{'quality':>9s}{'mode':>9s}{'cit':>9s}{'evR':>9s}")
    for mode in MODES:
        m = final_summary[mode]["metrics"]
        print(f"{mode:12s}{m['overall_success']:>9.4f}{m['answer_quality']:>9.4f}"
              f"{m['response_mode_accuracy']:>9.4f}{m['citation_validity']:>9.4f}"
              f"{m['evidence_recall']:>9.4f}")
    print(f"\n失败样本: {len(failures)}")
    if failures:
        by_mode = {}
        for failure in failures:
            by_mode[failure["mode"]] = by_mode.get(failure["mode"], 0) + 1
        print(f"  按配置: {by_mode}")
        print("  注意：失败样本被排除在指标之外，存在失败时不得据此下结论")
    if incomplete:
        print(f"未跑完的配置: {incomplete}；用 --resume 续跑")
    print(f"cost: {client.cost_summary()}")
    print(f"elapsed: {time.perf_counter() - started:.1f}s")
    return 1 if incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
