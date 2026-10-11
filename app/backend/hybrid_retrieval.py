"""Deterministic score fusion for sparse and semantic evidence retrieval."""
from __future__ import annotations


class HybridRetriever:
    def __init__(self, sparse, semantic, alpha: float = 0.5):
        if not 0 <= alpha <= 1:
            raise ValueError('alpha must be between 0 and 1')
        self.sparse = sparse
        self.semantic = semantic
        self.alpha = alpha

    def search(self, query: str, top_k: int = 5):
        sparse_hits = self.sparse.search(query, max(top_k, len(self.sparse.rows)))
        semantic_hits = self.semantic.search(query, max(top_k, len(self.semantic.rows)))
        sparse_scores = self._normalize(sparse_hits)
        semantic_scores = self._normalize(semantic_hits)
        rows = {row['evidence_id']: row for row in self.sparse.rows}
        identities = set(sparse_scores) | set(semantic_scores)
        fused = [(rows[identity], self.alpha * sparse_scores.get(identity, 0.0) +
                  (1 - self.alpha) * semantic_scores.get(identity, 0.0)) for identity in identities]
        return sorted(fused, key=lambda hit: (-hit[1], hit[0]['evidence_id']))[:top_k]

    @staticmethod
    def _normalize(hits):
        if not hits:
            return {}
        scores = {row['evidence_id']: score for row, score in hits}
        low, high = min(scores.values()), max(scores.values())
        if high == low:
            return {identity: 1.0 for identity in scores}
        return {identity: (score - low) / (high - low) for identity, score in scores.items()}
