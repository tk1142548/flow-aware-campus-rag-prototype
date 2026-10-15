"""Stage-3 retrieval baselines under an id-free, oracle-free protocol.

The earlier formal run conditioned retrieval on each sample's gold `process_id`,
which means it measured "find the evidence once you already know the answer".
Here retrieval sees only the user question. Two scopes are reported:

* ``global``          - search the whole verified evidence pool (the headline)
* ``item_conditioned`` - search inside the gold item only (diagnostic upper bound,
                        must not be reported as the retrieval result)

Usage:
    python scripts/run_retrieval_v2.py [--limit N] [--output PATH]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.api_client import ApiClient
from app.backend.hybrid_retrieval import HybridRetriever
from app.backend.rerank import Reranker
from app.backend.research_data import ResearchRepository
from app.backend.semantic_retrieval import SemanticRetriever
from app.backend.sparse_retrieval import SparseRetriever
from app.backend.stage4_statistics import holm_adjust, paired_analysis

RETRIEVE_K = 10
CANDIDATE_K = 20
HEADLINE_K = 5
ALPHA = 0.5
STRATEGIES = ["sparse", "dense", "hybrid", "hybrid_rerank"]


def query_text(sample: dict) -> str:
    return "\n".join(t["text"] for t in sample["conversation"] if t["role"] == "user")


def recall_at(hits: list[dict], relevant: set[str], k: int) -> float:
    if not relevant:
        return 1.0
    top = {row["evidence_id"] for row in hits[:k]}
    return len(top & relevant) / len(relevant)


def precision_at(hits: list[dict], relevant: set[str], k: int) -> float:
    top = hits[:k]
    if not top:
        return 1.0 if not relevant else 0.0
    return len({row["evidence_id"] for row in top} & relevant) / len(top)


def reciprocal_rank_at(hits: list[dict], relevant: set[str], k: int) -> float:
    for rank, row in enumerate(hits[:k], 1):
        if row["evidence_id"] in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at(hits: list[dict], relevant: set[str], k: int) -> float:
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, row in enumerate(hits[:k], 1)
        if row["evidence_id"] in relevant
    )
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(len(relevant), k) + 1))
    return dcg / ideal if ideal else 1.0


def retrieval_metrics(hits: list[dict], relevant: set[str]) -> dict:
    return {
        "recall_at_5": recall_at(hits, relevant, HEADLINE_K),
        "precision_at_5": precision_at(hits, relevant, HEADLINE_K),
        "mrr_at_10": reciprocal_rank_at(hits, relevant, RETRIEVE_K),
        "ndcg_at_5": ndcg_at(hits, relevant, HEADLINE_K),
        "complete_evidence": float(relevant <= {r["evidence_id"] for r in hits[:RETRIEVE_K]}),
    }


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def build_strategy(repo: ResearchRepository, client: ApiClient, evidence: list[dict]) -> dict:
    sparse = SparseRetriever(evidence)
    dense = SemanticRetriever(evidence, client.embed)
    hybrid = HybridRetriever(sparse, dense, ALPHA)
    return {"sparse": sparse, "dense": dense, "hybrid": hybrid, "reranker": Reranker(client)}


def run_scope(samples: list[dict], repo: ResearchRepository, client: ApiClient,
              evidence_pool: list[dict], scope: str) -> list[dict]:
    strategy = build_strategy(repo, client, evidence_pool)
    per_sample = []
    for sample in samples:
        query = query_text(sample)
        relevant = set(sample["gold"]["supporting_evidence_ids"])
        entry = {"sample_id": sample["sample_id"], "item_id": sample["allocation_item_id"],
                 "scope": scope, "metrics": {}}
        for name in STRATEGIES:
            if name == "hybrid_rerank":
                candidates = strategy["hybrid"].search(query, CANDIDATE_K)
                hits = strategy["reranker"].rerank(query, candidates, RETRIEVE_K)
            else:
                hits = strategy[name].search(query, RETRIEVE_K)
            rows = [row for row, _ in hits]
            entry["metrics"][name] = retrieval_metrics(rows, relevant)
            entry.setdefault("hits", {})[name] = [row["evidence_id"] for row in rows]
        baseline_hits = strategy["hybrid"].search(query, RETRIEVE_K)[:3]
        top_items = Counter(row["item_id"] for row, _ in baseline_hits)
        entry["top3_item_guess"] = top_items.most_common(1)[0][0] if top_items else None
        per_sample.append(entry)
    return per_sample


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data/experiments/retrieval-v2.json")
    args = parser.parse_args()

    started = time.perf_counter()
    repo = ResearchRepository(ROOT)
    client = ApiClient(ROOT / "data/cache")

    samples = [json.loads(line) for line in
               (ROOT / "data/evaluation/stage2_samples.jsonl").read_text(encoding="utf-8").splitlines()
               if line]
    samples = [s for s in samples if s["gold"]["supporting_evidence_ids"]]
    if args.limit:
        samples = samples[: args.limit]

    verified = repo.all_verified_evidence()

    print(f"samples={len(samples)} verified_evidence={len(verified)}", flush=True)

    print("[scope] global", flush=True)
    global_rows = run_scope(samples, repo, client, verified, "global")

    print("[scope] item_conditioned", flush=True)
    by_item: dict[str, list[dict]] = defaultdict(list)
    for sample in samples:
        by_item[sample["allocation_item_id"]].append(sample)
    item_rows = []
    for item_id, group in sorted(by_item.items()):
        pool = [row for row in verified if row["item_id"] == item_id]
        item_rows.extend(run_scope(group, repo, client, pool, "item_conditioned"))

    summary = {"global": {}, "item_conditioned": {}}
    for scope, rows in (("global", global_rows), ("item_conditioned", item_rows)):
        summary[scope] = {
            name: {key: mean([r["metrics"][name][key] for r in rows])
                   for key in ("recall_at_5", "precision_at_5", "mrr_at_10", "ndcg_at_5",
                               "complete_evidence")}
            for name in STRATEGIES
        }
        summary[scope]["sample_count"] = len(rows)
        summary[scope]["item_routing_accuracy"] = (
            mean([1.0 if r["top3_item_guess"] == r["item_id"] else 0.0 for r in rows])
        )

    item_ids = [r["item_id"] for r in global_rows]
    comparisons = []
    for left, right in (("sparse", "dense"), ("sparse", "hybrid"), ("hybrid", "hybrid_rerank")):
        for metric in ("recall_at_5", "mrr_at_10", "ndcg_at_5"):
            stat = paired_analysis(
                [r["metrics"][left][metric] for r in global_rows],
                [r["metrics"][right][metric] for r in global_rows],
                item_ids, 10000, 0,
            )
            comparisons.append({"left": left, "right": right, "metric": metric, **stat})
    for comparison, adjusted in zip(
        comparisons, holm_adjust([c["paired_sign_flip_p"] for c in comparisons])
    ):
        comparison["holm_adjusted_p"] = adjusted

    payload = {
        "status": "已验证",
        "protocol": {"retrieve_k": RETRIEVE_K, "candidate_k": CANDIDATE_K,
                     "headline_k": HEADLINE_K, "alpha": ALPHA,
                     "oracle_used": False,
                     "note": "检索只看到用户问题，不使用样本的 process_id 或 gold 字段"},
        "sample_count": len(samples),
        "verified_evidence_count": len(verified),
        "dataset": "开发集",
        "summary": summary,
        "paired_comparisons": comparisons,
        "samples": global_rows,
        "item_conditioned_samples": item_rows,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.perf_counter() - started,
        "cost": client.cost_summary(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    for scope in ("global", "item_conditioned"):
        print(f"\n=== {scope} ===")
        print(f"{'strategy':16s}{'R@5':>9s}{'P@5':>9s}{'MRR@10':>9s}{'nDCG@5':>9s}")
        for name in STRATEGIES:
            s = summary[scope][name]
            print(f"{name:16s}{s['recall_at_5']:>9.4f}{s['precision_at_5']:>9.4f}"
                  f"{s['mrr_at_10']:>9.4f}{s['ndcg_at_5']:>9.4f}")
        print(f"item routing accuracy: {summary[scope]['item_routing_accuracy']:.4f}")
    print(f"\ncost: {client.cost_summary()}")
    print(f"elapsed: {payload['elapsed_seconds']:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
