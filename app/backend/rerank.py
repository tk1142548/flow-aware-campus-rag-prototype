"""Cross-encoder style reranking for retrieved evidence.

Wraps a hosted cross-encoder (gte-rerank-v2) behind the same shape as the other
retrievers so it can be switched on and off for ablations.

The reranker only sees the query and the candidate passages. It never sees
which passage is the correct one.
"""
from __future__ import annotations

from typing import Any, Sequence


class Reranker:
    def __init__(self, client: Any, model: str | None = None) -> None:
        self.client = client
        self.model = model

    @staticmethod
    def _text(row: dict) -> str:
        parts = [row.get("normalized_claim", ""), row.get("verbatim_text", "")]
        keywords = row.get("keywords") or []
        if keywords:
            parts.append("、".join(keywords))
        return " ".join(part for part in parts if part).strip()

    def rerank(
        self,
        query: str,
        hits: Sequence[tuple[dict, float]],
        top_k: int = 5,
    ) -> list[tuple[dict, float]]:
        """Reorder `hits` by cross-encoder relevance and keep the best `top_k`."""
        if not hits:
            return []
        documents = [self._text(row) for row, _ in hits]
        ranking = self.client.rerank(query, documents, top_n=len(documents), model=self.model)
        scores = {index: score for index, score in ranking}
        reordered = [
            (row, float(scores.get(index, 0.0)))
            for index, (row, _) in enumerate(hits)
        ]
        reordered.sort(key=lambda hit: (-hit[1], hit[0]["evidence_id"]))
        return reordered[:top_k]


def rerank_logged(
    reranker: Reranker,
    query: str,
    hits: Sequence[tuple[dict, float]],
    top_k: int,
) -> tuple[list[tuple[dict, float]], dict]:
    """Rerank and also return the before/after rank movement for analysis."""
    before = {row["evidence_id"]: rank for rank, (row, _) in enumerate(hits, 1)}
    result = reranker.rerank(query, hits, top_k=top_k)
    movement = {
        row["evidence_id"]: {"before": before.get(row["evidence_id"]), "after": rank}
        for rank, (row, _) in enumerate(result, 1)
    }
    return result, movement
