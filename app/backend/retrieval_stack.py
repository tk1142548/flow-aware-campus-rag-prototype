"""One place that assembles the retrieval stack, so experiments share it.

Every experiment that needs "given a question, get evidence" goes through here.
Sharing one stack is what makes the ablations comparable: the only thing that
changes between runs is the switch, never the index or the weights.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

from .hybrid_retrieval import HybridRetriever
from .rerank import Reranker
from .semantic_retrieval import SemanticRetriever
from .sparse_retrieval import SparseRetriever

DEFAULT_ALPHA = 0.5
DEFAULT_CANDIDATES = 20
DEFAULT_K = 10


class RetrievalStack:
    def __init__(self, evidence: Sequence[dict], client: Any, alpha: float = DEFAULT_ALPHA) -> None:
        rows = list(evidence)
        self.evidence = rows
        self.sparse = SparseRetriever(rows)
        self.dense = SemanticRetriever(rows, client.embed)
        self.hybrid = HybridRetriever(self.sparse, self.dense, alpha)
        self.reranker = Reranker(client)
        self.alpha = alpha

    def scored(
        self,
        query: str,
        *,
        strategy: str = "hybrid_rerank",
        k: int = DEFAULT_K,
        candidates: int = DEFAULT_CANDIDATES,
    ) -> list[tuple[dict, float]]:
        """Return (evidence_row, score) pairs for the named strategy."""
        if strategy == "sparse":
            return self.sparse.search(query, k)
        if strategy == "dense":
            return self.dense.search(query, k)
        if strategy == "hybrid":
            return self.hybrid.search(query, k)
        if strategy == "hybrid_rerank":
            pool = self.hybrid.search(query, max(candidates, k))
            return self.reranker.rerank(query, pool, k)
        raise ValueError(f"unknown retrieval strategy: {strategy}")

    def retrieve(self, query: str, *, strategy: str = "hybrid_rerank",
                 k: int = DEFAULT_K, candidates: int = DEFAULT_CANDIDATES) -> list[dict]:
        return [row for row, _ in self.scored(query, strategy=strategy, k=k, candidates=candidates)]

    @staticmethod
    def guess_item(hits: Sequence[dict], depth: int = 3) -> str | None:
        """Cheap item routing from the top hits. Uses no evaluation labels."""
        counter = Counter(row["item_id"] for row in list(hits)[:depth])
        return counter.most_common(1)[0][0] if counter else None
