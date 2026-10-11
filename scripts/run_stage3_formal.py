"""Run the Stage 3 paired retrieval comparison on the frozen Stage 2 set."""
from __future__ import annotations

import argparse, json, os, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from app.backend.claim_validation import validate_claims
from app.backend.error_taxonomy import classify_error
from app.backend.hybrid_retrieval import HybridRetriever
from app.backend.research_data import ResearchRepository
from app.backend.retrieval_metrics import evidence_precision_at_k, recall_at_k
from app.backend.semantic_retrieval import SemanticRetriever, dashscope_embed
from app.backend.sparse_retrieval import SparseRetriever


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--output', type=Path, required=True); ap.add_argument('--top-k', type=int, default=5); ap.add_argument('--alpha', type=float, default=0.5); ap.add_argument('--semantic', action='store_true'); args = ap.parse_args()
    repo = ResearchRepository(ROOT)
    samples = [json.loads(x) for x in (ROOT/'data/evaluation/stage2_samples.jsonl').read_text(encoding='utf8').splitlines() if x.strip()]
    retrievers = {}; semantic_models = {}
    batched_hits = {}
    by_item = defaultdict(list)
    for x in samples:
        if x['scenario_type'] != 'out_of_scope': by_item[x['item_id']].append(x)
    for item, rows in by_item.items():
        evidence = repo.verified_evidence(item)
        sparse = SparseRetriever(evidence); retrievers[(item,'sparse')] = sparse
        if args.semantic:
            key = os.environ.get('DASHSCOPE_API_KEY')
            if not key: raise SystemExit('DASHSCOPE_API_KEY is required for --semantic')
            sem = SemanticRetriever(evidence, lambda texts, k=key: dashscope_embed(texts, k))
            semantic_models[item] = sem
            item_samples = by_item[item]
            queries = [x['conversation'][-1]['text'] for x in item_samples]
            semantic_all = sem.search_many(queries, len(sem.rows))
            for sample, semantic_hits in zip(item_samples, semantic_all):
                sparse_hits = sparse.search(sample['conversation'][-1]['text'], len(sparse.rows))
                sparse_scores = HybridRetriever._normalize(sparse_hits)
                semantic_scores = HybridRetriever._normalize(semantic_hits)
                rows_by_id = {row['evidence_id']: row for row in sparse.rows}
                fused = [(rows_by_id[identity], args.alpha * sparse_scores.get(identity, 0.0) + (1 - args.alpha) * semantic_scores.get(identity, 0.0))
                         for identity in set(sparse_scores) | set(semantic_scores)]
                batched_hits[sample['sample_id']] = {
                    'semantic': semantic_hits[:args.top_k],
                    'hybrid': sorted(fused, key=lambda hit: (-hit[1], hit[0]['evidence_id']))[:args.top_k],
                }
    metrics = {name: {'recall': [], 'precision': [], 'validation_error_samples': 0, 'error_categories': Counter()} for name in (['sparse','semantic','hybrid'] if args.semantic else ['sparse'])}
    sample_rows = []
    for x in samples:
        if x['scenario_type'] == 'out_of_scope': continue
        query = x['conversation'][-1]['text']; relevant = set(x['gold']['supporting_evidence_ids']); p = repo.processes[x['process_id']]
        row = {'sample_id': x['sample_id'], 'item_id': x['item_id'], 'relevant_evidence_ids': sorted(relevant), 'strategies': {}}
        for name in metrics:
            if args.semantic and name in ('semantic', 'hybrid'):
                hits = batched_hits[x['sample_id']][name]
            else:
                hits = retrievers[(x['item_id'], name)].search(query, args.top_k)
            ids = {r['evidence_id'] for r,_ in hits}; claims = repo.supported_claims(x['process_id'], ids); errors = validate_claims(p, ids, claims)
            metrics[name]['recall'].append(recall_at_k(hits, relevant)); metrics[name]['precision'].append(evidence_precision_at_k(hits, relevant)); metrics[name]['validation_error_samples'] += bool(errors); metrics[name]['error_categories'][classify_error(None, errors, len(hits))] += 1
            row['strategies'][name] = {'hits': [r['evidence_id'] for r,_ in hits], 'recall_at_k': metrics[name]['recall'][-1], 'precision_at_k': metrics[name]['precision'][-1], 'error_category': classify_error(None, errors, len(hits)), 'validation_errors': errors}
        sample_rows.append(row)
    summary = {}
    for name, m in metrics.items():
        summary[name] = {'sample_count': len(m['recall']), 'mean_recall_at_k': sum(m['recall'])/len(m['recall']), 'mean_precision_at_k': sum(m['precision'])/len(m['precision']), 'validation_error_samples': m['validation_error_samples'], 'error_categories': dict(m['error_categories'])}
    payload = {'status':'已验证','dataset_version':'1.0.1-frozen','top_k':args.top_k,'alpha':args.alpha,'random_seed':0,'semantic_model':'text-embedding-v4' if args.semantic else None,'formal_evaluation_enabled':True,'semantic_enabled':args.semantic,'summary':summary,'samples':sample_rows,'api_key_logged':False}
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf8'); print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__ == '__main__': main()
