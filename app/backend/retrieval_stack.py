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
ROUTING_DEPTH = 5


def passage_key(row: dict) -> tuple[str, str]:
    return row.get("source_id", ""), row.get("verbatim_text", "")


def distinct_passages(hits: Sequence[tuple[dict, float]], k: int) -> list[tuple[dict, float]]:
    """Keep the best-ranked statement of each passage until ``k`` passages are held.

    Statements cut from one passage share its verbatim text; letting them fill
    several slots crowds out other passages without adding new text. The other
    statements of a kept passage are added back by ``expand_passages``.
    """
    seen: set[tuple[str, str]] = set()
    kept: list[tuple[dict, float]] = []
    for row, score in hits:
        key = passage_key(row)
        if key in seen:
            continue
        seen.add(key)
        kept.append((row, score))
        if len(kept) == k:
            break
    return kept


class RetrievalStack:
    def __init__(self, evidence: Sequence[dict], client: Any, alpha: float = DEFAULT_ALPHA) -> None:
        rows = list(evidence)
        self.evidence = rows
        self.sparse = SparseRetriever(rows)
        self.dense = SemanticRetriever(rows, client.embed)
        self.hybrid = HybridRetriever(self.sparse, self.dense, alpha)
        self.reranker = Reranker(client)
        self.alpha = alpha
        self.by_passage: dict[tuple[str, str], list[dict]] = {}
        for row in sorted(rows, key=lambda r: r["evidence_id"]):
            self.by_passage.setdefault(passage_key(row), []).append(row)

    def scored(
        self,
        query: str,
        *,
        strategy: str = "hybrid_rerank",
        k: int = DEFAULT_K,
        candidates: int = DEFAULT_CANDIDATES,
        items: set[str] | None = None,
    ) -> list[tuple[dict, float]]:
        """Return (evidence_row, score) pairs for the named strategy.

        ``items`` restricts the result to evidence of those items. Filtering is
        applied to the full ranking before the cut, so a restricted search still
        returns ``k`` hits when the items have that many.
        """
        def keep(hits):
            return [hit for hit in hits if items is None or hit[0]["item_id"] in items]

        everything = len(self.evidence)
        if strategy == "sparse":
            return keep(self.sparse.search(query, everything))[:k]
        if strategy == "dense":
            return keep(self.dense.search(query, everything))[:k]
        if strategy == "hybrid":
            return keep(self.hybrid.search(query, everything))[:k]
        if strategy == "hybrid_rerank":
            pool = keep(self.hybrid.search(query, everything))[: max(candidates, k)]
            return self.reranker.rerank(query, pool, len(pool))[:k]
        raise ValueError(f"unknown retrieval strategy: {strategy}")

    def retrieve(self, query: str, *, strategy: str = "hybrid_rerank",
                 k: int = DEFAULT_K, candidates: int = DEFAULT_CANDIDATES) -> list[dict]:
        return [row for row, _ in self.scored(query, strategy=strategy, k=k, candidates=candidates)]

    def route(self, query: str, *, candidates: int = DEFAULT_CANDIDATES) -> set[str]:
        """Pick the item(s) a question belongs to from an unrestricted first pass.

        The top hits vote. A clear majority keeps one item; otherwise the two
        leading items are both kept, so a near tie does not commit the answer to
        the wrong item.
        """
        hits = self.scored(query, k=ROUTING_DEPTH, candidates=candidates)
        votes = Counter(row["item_id"] for row, _ in hits).most_common()
        if not votes:
            return set()
        if len(votes) == 1 or votes[0][1] > ROUTING_DEPTH // 2:
            return {votes[0][0]}
        return {votes[0][0], votes[1][0]}

    def retrieve_routed(self, query: str, *, k: int = DEFAULT_K,
                        candidates: int = DEFAULT_CANDIDATES) -> tuple[list[dict], set[str]]:
        """Route first, then retrieve ``k`` distinct passages inside the routed items."""
        items = self.route(query, candidates=candidates)
        pool = max(candidates, 3 * k)
        hits = self.scored(query, k=pool, candidates=pool, items=items or None)
        return self.expand_passages(distinct_passages(hits, k)), items

    def expand_passages(self, hits: Sequence[tuple[dict, float]]) -> list[dict]:
        """Return every statement of each kept passage, in rank order of the passages."""
        rows: list[dict] = []
        for row, _ in hits:
            rows.extend(self.by_passage.get(passage_key(row), [row]))
        return rows

    @staticmethod
    def guess_item(hits: Sequence[dict], depth: int = 3) -> str | None:
        """Cheap item routing from the top hits. Uses no evaluation labels."""
        counter = Counter(row["item_id"] for row in list(hits)[:depth])
        return counter.most_common(1)[0][0] if counter else None
