"""Development answer contexts for direct and flow-constrained baselines."""
from __future__ import annotations


def direct_answer_context(hits: list[tuple[dict, float]]) -> dict:
    return {
        'strategy': 'direct',
        'claims': [{'evidence_id': row['evidence_id'], 'text': row['normalized_claim']}
                   for row, _ in hits],
        'evidence_ids': [row['evidence_id'] for row, _ in hits],
        'answer_boundary': '仅展示检索候选声明，未应用流程步骤和材料约束。',
    }
