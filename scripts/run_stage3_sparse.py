"""Run the isolated research-data BM25 baseline on a supplied query."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.backend.stage3_engine import Stage3Engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--item", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--source", action="append")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_ids = set(args.source) if args.source else None
    engine = Stage3Engine(ROOT)
    evidence = engine.repository.verified_evidence(args.item, source_ids)
    if not evidence:
        parser.error("no verified evidence matches the item and source filter")
    result = engine.query(args.item, args.query, source_ids, None, args.top_k)
    retrieved = {hit["evidence"]["evidence_id"] for hit in result["hits"]}
    result = {
        "status": "已验证", "retriever": "bm25", "k1": 1.5, "b": 0.75,
        "item_id": args.item, "query": args.query, "top_k": args.top_k,
        "source_ids": args.source, "candidate_count": len(evidence),
        "hits": [{"evidence_id": hit["evidence"]["evidence_id"], "source_id": hit["evidence"]["source_id"], "score": hit["score"], "claim": hit["evidence"]["normalized_claim"]} for hit in result["hits"]],
        "supported_process_claims": {p["process_id"]: engine.repository.supported_claims(p["process_id"], retrieved) for p in engine.repository.processes.values() if p["item_id"] == args.item},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"candidate_count": len(evidence), "hit_ids": sorted(retrieved)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
