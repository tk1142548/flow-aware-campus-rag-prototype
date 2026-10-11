"""Run sparse, semantic and hybrid development baselines with process constraints."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.backend.answer_strategy import build_answer_context
from app.backend.claim_validation import validate_claims
from app.backend.flow_constraints import supported_process_context
from app.backend.hybrid_retrieval import HybridRetriever
from app.backend.research_data import ResearchRepository
from app.backend.semantic_retrieval import SemanticRetriever, dashscope_embed
from app.backend.sparse_retrieval import SparseRetriever


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--item', required=True)
    parser.add_argument('--process', required=True)
    parser.add_argument('--query', required=True)
    parser.add_argument('--source', action='append')
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--alpha', type=float, default=0.5)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repository = ResearchRepository(ROOT)
    evidence = repository.verified_evidence(args.item, set(args.source) if args.source else None)
    if not evidence:
        parser.error('no verified evidence matches item and source filter')
    key = os.environ.get('DASHSCOPE_API_KEY')
    if not key:
        parser.error('DASHSCOPE_API_KEY is required')
    semantic = SemanticRetriever(evidence, lambda texts: dashscope_embed(texts, key))
    sparse = SparseRetriever(evidence)
    hybrid = HybridRetriever(sparse, semantic, args.alpha)
    retrievers = {'sparse': sparse, 'semantic': semantic, 'hybrid': hybrid}
    process = repository.processes.get(args.process)
    if not process or process['item_id'] != args.item:
        parser.error('process does not belong to item')
    results = {}
    for name, retriever in retrievers.items():
        hits = retriever.search(args.query, args.top_k)
        ids = {row['evidence_id'] for row, _ in hits}
        claims = repository.supported_claims(args.process, ids)
        errors = validate_claims(process, ids, claims)
        context = supported_process_context(process, ids)
        results[name] = {'hits': [{'evidence_id': row['evidence_id'], 'score': round(score, 8)} for row, score in hits],
                         'supported_claim_ids': context['claim_ids'],
                         'flow_context': context,
                         'answer_context': build_answer_context(process, claims, context),
                         'validation_errors': errors}
    payload = {'status': '已验证', 'config_id': 'STAGE3_UNIFIED_DEV_V1', 'formal_evaluation_enabled': False,
               'item_id': args.item, 'process_id': args.process, 'query': args.query,
               'top_k': args.top_k, 'alpha': args.alpha, 'source_ids': args.source,
               'results': results, 'api_key_logged': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({name: len(result['hits']) for name, result in results.items()}, ensure_ascii=False))


if __name__ == '__main__':
    main()
