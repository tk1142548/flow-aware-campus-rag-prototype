import unittest

from app.backend.retrieval_metrics import evidence_precision_at_k, recall_at_k


class RetrievalMetricsTests(unittest.TestCase):
    def hits(self):
        return [({'evidence_id': 'E1'}, .9), ({'evidence_id': 'E2'}, .8)]

    def test_recall_and_precision(self):
        self.assertEqual(0.5, recall_at_k(self.hits(), {'E1', 'E3'}))
        self.assertEqual(0.5, evidence_precision_at_k(self.hits(), {'E1'}))

    def test_empty_and_invalid_relevant(self):
        self.assertEqual(0.0, evidence_precision_at_k([], {'E1'}))
        with self.assertRaises(ValueError):
            recall_at_k(self.hits(), set())
