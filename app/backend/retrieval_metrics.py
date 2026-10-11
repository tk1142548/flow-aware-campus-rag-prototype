"""Metrics for development retrieval runs."""
from __future__ import annotations


def recall_at_k(hits: list[tuple[dict, float]], relevant_ids: set[str]) -> float:
    if not relevant_ids:
        raise ValueError('relevant_ids must not be empty')
    found = {row['evidence_id'] for row, _ in hits}
    return len(found & relevant_ids) / len(relevant_ids)


def evidence_precision_at_k(hits: list[tuple[dict, float]], relevant_ids: set[str]) -> float:
    if not hits:
        return 0.0
    found = {row['evidence_id'] for row, _ in hits}
    return len(found & relevant_ids) / len(hits)
