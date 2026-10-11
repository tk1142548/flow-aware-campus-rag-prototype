import unittest

from app.backend.answer_strategy import build_answer_context
from app.backend.hybrid_retrieval import HybridRetriever


class StubRetriever:
    def __init__(self, rows, hits):
        self.rows = rows
        self.hits = hits

    def search(self, query, top_k):
        return self.hits


class HybridStrategyTests(unittest.TestCase):
    def test_hybrid_tie_break_is_stable(self):
        rows = [{'evidence_id': 'E001'}, {'evidence_id': 'E002'}]
        hits = [(rows[1], 1.0), (rows[0], 1.0)]
        result = HybridRetriever(StubRetriever(rows, hits), StubRetriever(rows, hits), .5).search('q', 2)
        self.assertEqual(['E001', 'E002'], [row['evidence_id'] for row, _ in result])

    def test_invalid_alpha(self):
        with self.assertRaises(ValueError):
            HybridRetriever(StubRetriever([], []), StubRetriever([], []), 2)

    def test_answer_context_carries_citations(self):
        process = {'process_id': 'P'}
        claims = [{'claim_id': 'C', 'text': '声明', 'evidence_ids': ['E']}]
        context = build_answer_context(process, claims, {'claim_ids': ['C'], 'step_ids': ['S'], 'material_ids': ['M']})
        self.assertEqual(['E'], context['evidence_ids'])
        self.assertEqual(['S'], context['step_ids'])
