"""Evaluate sparse, semantic and hybrid retrieval on development queries."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.backend.hybrid_retrieval import HybridRetriever
from app.backend.research_data import ResearchRepository
from app.backend.retrieval_metrics import evidence_precision_at_k, recall_at_k
from app.backend.semantic_retrieval import SemanticRetriever, dashscope_embed
from app.backend.sparse_retrieval import SparseRetriever


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queries', type=Path, default=ROOT / 'data/development/stage3_queries.jsonl')
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    key = os.environ.get('DASHSCOPE_API_KEY')
    if not key:
        parser.error('DASHSCOPE_API_KEY is required')
    repository = ResearchRepository(ROOT)
    queries = [json.loads(line) for line in args.queries.read_text(encoding='utf-8').splitlines() if line.strip()]
    results = []
    for query in queries:
        evidence = repository.verified_evidence(query['item_id'])
        sparse = SparseRetriever(evidence)
        semantic = SemanticRetriever(evidence, lambda texts: dashscope_embed(texts, key))
        retrievers = {'sparse': sparse, 'semantic': semantic, 'hybrid': HybridRetriever(sparse, semantic)}
        relevant = set(query['relevant_evidence_ids'])
        row = {'query_id': query['query_id'], 'item_id': query['item_id'], 'query': query['query'], 'relevant_evidence_ids': sorted(relevant), 'strategies': {}}
        for name, retriever in retrievers.items():
            hits = retriever.search(query['query'], args.top_k)
            row['strategies'][name] = {'hit_ids': [hit[0]['evidence_id'] for hit in hits],
                                       'recall_at_k': recall_at_k(hits, relevant),
                                       'evidence_precision_at_k': evidence_precision_at_k(hits, relevant)}
        results.append(row)
    summary = {}
    for name in ('sparse', 'semantic', 'hybrid'):
        summary[name] = {'mean_recall_at_k': sum(row['strategies'][name]['recall_at_k'] for row in results) / len(results),
                         'mean_evidence_precision_at_k': sum(row['strategies'][name]['evidence_precision_at_k'] for row in results) / len(results)}
    payload = {'status': '已验证', 'config_id': 'STAGE3_DEV_METRICS_V1', 'formal_evaluation_enabled': False,
               'top_k': args.top_k, 'query_count': len(results), 'summary': summary, 'results': results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
