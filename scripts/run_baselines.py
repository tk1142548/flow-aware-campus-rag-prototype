"""Run every configuration over an evaluation set and score it.

Retrieval per configuration:

    baseline_a      dense, top 5
    baseline_b      hybrid + rerank, top 5
    others          item routing, then hybrid + rerank inside the routed item(s),
                    8 distinct passages

Every configuration receives the whole conversation, including earlier assistant
turns. Item correctness is scored against the routed item for routed
configurations and against the top-3 majority for the two plain baselines.

Usage:
    python scripts/run_baselines.py --samples data/evaluation/dev-set.jsonl \
        --output data/experiments/dev-run.json [--model qwen-plus] [--configs a,b]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Parallelism comes from the worker threads; keep BLAS single-threaded under them.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

from app.backend import systems
from app.backend.api_client import ApiClient
from app.backend.flow_extractor import extract as extract_flow
from app.backend.research_data import ResearchRepository
from app.backend.retrieval_stack import RetrievalStack
from app.backend.scoring_v2 import ElementMatcher, score_prediction
from app.backend.stage4_statistics import paired_analysis

CONFIGS = {
    "baseline_a": {"strategy": "dense", "k": 5, "routed": False},
    "baseline_b": {"strategy": "hybrid_rerank", "k": 5, "routed": False},
    "baseline_c": {"strategy": "hybrid_rerank", "k": 8, "routed": True},
    "interaction": {"strategy": "hybrid_rerank", "k": 8, "routed": True},
    "full": {"strategy": "hybrid_rerank", "k": 8, "routed": True},
    "full_no_skeleton": {"strategy": "hybrid_rerank", "k": 8, "routed": True},
    "full_no_verify": {"strategy": "hybrid_rerank", "k": 8, "routed": True},
}
MODES = tuple(CONFIGS)

# Each comparison isolates one component.
CONTRASTS = (
    ("baseline_c", "interaction", "H3 交互控制"),
    ("full_no_skeleton", "full", "H1 流程骨架"),
    ("full_no_verify", "full", "H2 断言核验"),
    ("baseline_c", "full", "完整方法 vs 基线C"),
)

SAMPLE_METRIC_KEYS = (
    "item_correct", "response_mode_accuracy", "evidence_recall", "evidence_precision",
    "missing_slot_f1", "follow_up_correct", "citation_validity",
    "claim_coverage", "step_coverage", "material_coverage",
    "answer_quality", "overall_success",
)


def user_text(sample: dict) -> str:
    """The query used for retrieval: everything the student has said so far."""
    return "\n".join(t["text"] for t in sample["conversation"] if t["role"] == "user")


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


class EmptyAnswer(RuntimeError):
    """The system returned nothing where an answer was required.

    Almost always an upstream call that failed or returned unparsable output. It
    must surface as a failure rather than being scored as a normal answer.
    """


def retrieve(stack: RetrievalStack, sample: dict, config: str) -> tuple[list[dict], str | None]:
    spec = CONFIGS[config]
    query = user_text(sample)
    if spec["routed"]:
        rows, items = stack.retrieve_routed(query, k=spec["k"])
        item = RetrievalStack.guess_item(rows) if len(items) != 1 else next(iter(items))
        return rows, item
    rows = stack.retrieve(query, strategy=spec["strategy"], k=spec["k"])
    return rows, RetrievalStack.guess_item(rows)


def run_one(repository: ResearchRepository, stack: RetrievalStack, client: ApiClient,
            matcher: ElementMatcher, sample: dict, config: str) -> dict:
    turns = sample["conversation"]
    rows, item = retrieve(stack, sample, config)

    if config in systems.USES_SKELETON:
        skeleton = extract_flow(client, turns, rows)
        prediction = systems.SYSTEMS[config](client, turns, rows, skeleton)
    else:
        skeleton = None
        prediction = systems.SYSTEMS[config](client, turns, rows)
    prediction.item_id = item

    if (not prediction.answer_text.strip()
            and prediction.response_mode != "clarification"
            and sample["gold"]["response_mode"] != "abstention"):
        raise EmptyAnswer(f"{config} 未产出回答（接口失败或输出无法解析）")

    scored = score_prediction(repository, sample, prediction, matcher)
    record = {
        "sample_id": sample["sample_id"],
        "item_id": sample["allocation_item_id"] or "OUT_OF_SCOPE",
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
    if skeleton is not None:
        record["skeleton"] = skeleton
    return record


def compare(results: dict[str, list[dict]]) -> list[dict]:
    """Paired differences for each contrast, descriptive only.

    Hypothesis tests, with one primary metric per hypothesis and Holm correction
    across models, are made by analyze_hypotheses.py.
    """
    comparisons = []
    for left, right, label in CONTRASTS:
        aligned_left = {r["sample_id"]: r for r in results.get(left, [])}
        aligned_right = {r["sample_id"]: r for r in results.get(right, [])}
        shared = [sid for sid in aligned_right if sid in aligned_left]
        if not shared:
            continue
        for metric in ("overall_success", "response_mode_accuracy", "step_coverage",
                       "material_coverage", "answer_quality"):
            stat = paired_analysis(
                [aligned_left[sid]["metrics"][metric] for sid in shared],
                [aligned_right[sid]["metrics"][metric] for sid in shared],
                [aligned_right[sid]["item_id"] for sid in shared],
                10000, 0,
            )
            comparisons.append({"label": label, "left": left, "right": right,
                                "metric": metric, **stat})
    return comparisons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=None, help="generation model; defaults to the client's")
    parser.add_argument("--configs", default=",".join(MODES))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--resume", action="store_true",
                        help="skip runs already recorded in the output file")
    parser.add_argument("--checkpoint-every", type=int, default=50)
    args = parser.parse_args()

    modes = tuple(m.strip() for m in args.configs.split(",") if m.strip())
    unknown = [m for m in modes if m not in CONFIGS]
    if unknown:
        print(f"未知配置: {unknown}")
        return 2

    started = time.perf_counter()
    repository = ResearchRepository(ROOT)
    client = ApiClient(ROOT / "data/cache", chat_model=args.model)
    scoring_client = ApiClient(ROOT / "data/cache")
    matcher = ElementMatcher(scoring_client)

    try:
        client.chat([{"role": "user", "content": "ping"}], max_tokens=4)
        print(f"接口探活：正常（{client.chat_model}）", flush=True)
    except Exception as error:  # noqa: BLE001 - reported, then abort
        print(f"接口探活失败，已中止：{type(error).__name__}: {error}")
        return 2

    samples = [json.loads(line) for line in
               args.samples.read_text(encoding="utf-8").splitlines() if line]
    if args.limit:
        samples = samples[: args.limit]

    stack = RetrievalStack(repository.all_verified_evidence(), scoring_client)

    results: dict[str, list[dict]] = {mode: [] for mode in modes}
    failures: list[dict] = []
    done: set[tuple[str, str]] = set()
    if args.resume and args.output.exists():
        previous = json.loads(args.output.read_text(encoding="utf-8"))
        for mode, rows in (previous.get("samples") or {}).items():
            if mode in results:
                results[mode] = rows
                done.update((mode, row["sample_id"]) for row in rows)
        print(f"续跑：已有 {len(done)} 条记录", flush=True)

    jobs = [(sample, mode) for mode in modes for sample in samples
            if (mode, sample["sample_id"]) not in done]
    print(f"待跑 {len(jobs)} / {len(modes) * len(samples)}", flush=True)

    def build_payload(complete: bool) -> dict:
        return {
            "status": "complete" if complete else "running",
            "generation_model": client.chat_model,
            "configs": {m: CONFIGS[m] for m in modes},
            "samples_path": args.samples.as_posix(),
            "sample_count": len(samples),
            "scoring_clause_thresholds": {"lexical": matcher.lexical_threshold,
                                          "semantic": matcher.semantic_threshold},
            "summary": {
                mode: {"sample_count": len(results[mode]),
                       "metrics": {key: mean([r["metrics"][key] for r in results[mode]])
                                   for key in SAMPLE_METRIC_KEYS}}
                for mode in modes
            },
            "paired_comparisons": compare(results),
            "samples": results,
            "failures": failures,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": time.perf_counter() - started,
            "cost": {"generation": client.cost_summary(), "scoring": scoring_client.cost_summary()},
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

    if jobs:
        write_payload(complete=False)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for count, (mode, record, error) in enumerate(pool.map(worker, jobs), 1):
                if error:
                    failures.append(error)
                else:
                    results[mode].append(record)
                if count % args.checkpoint_every == 0:
                    write_payload(complete=False)
                if count % 100 == 0:
                    print(f"  {count}/{len(jobs)}", flush=True)

    incomplete = [mode for mode in modes if len(results[mode]) != len(samples)]
    write_payload(complete=not incomplete)

    summary = build_payload(complete=True)["summary"]
    print(f"\n{'config':18s}{'overall':>9s}{'mode':>9s}{'step':>9s}{'mat':>9s}{'claim':>9s}{'evR':>9s}")
    for mode in modes:
        m = summary[mode]["metrics"]
        print(f"{mode:18s}{m['overall_success']:>9.4f}{m['response_mode_accuracy']:>9.4f}"
              f"{m['step_coverage']:>9.4f}{m['material_coverage']:>9.4f}"
              f"{m['claim_coverage']:>9.4f}{m['evidence_recall']:>9.4f}")
    print(f"\n失败样本: {len(failures)}")
    if incomplete:
        print(f"未跑完的配置: {incomplete}；用 --resume 续跑")
    print(f"cost: {client.cost_summary()}")
    print(f"elapsed: {time.perf_counter() - started:.1f}s")
    return 1 if incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
