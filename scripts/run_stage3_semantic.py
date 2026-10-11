"""Run the Stage 3 DashScope semantic retrieval baseline."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.backend.research_data import ResearchRepository
from app.backend.semantic_retrieval import SemanticRetriever, dashscope_embed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--item', required=True)
    parser.add_argument('--query', required=True)
    parser.add_argument('--source', action='append')
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repository = ResearchRepository(ROOT)
    evidence = repository.verified_evidence(args.item, set(args.source) if args.source else None)
    if not evidence:
        parser.error('no verified evidence matches the item and source filter')
    key = os.environ.get('DASHSCOPE_API_KEY')
    if not key:
        parser.error('DASHSCOPE_API_KEY is required')
    def embed(texts):
        return dashscope_embed(texts, key)
    hits = SemanticRetriever(evidence, embed).search(args.query, args.top_k)
    payload = {'status': '已验证', 'stage': 'stage3', 'retriever': 'semantic',
               'model': 'text-embedding-v4', 'item_id': args.item, 'query': args.query,
               'top_k': args.top_k, 'candidate_count': len(evidence),
               'source_ids': args.source,
               'hits': [{'evidence_id': row['evidence_id'], 'source_id': row['source_id'],
                         'score': round(score, 8), 'claim': row['normalized_claim']}
                        for row, score in hits], 'api_key_logged': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'candidate_count': len(evidence), 'hit_ids': [row['evidence_id'] for row, _ in hits]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
