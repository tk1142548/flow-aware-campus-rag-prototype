import unittest

from app.backend.hybrid_retrieval import HybridRetriever


class StubRetriever:
    def __init__(self, rows, hits):
        self.rows = rows
        self.hits = hits

    def search(self, query, top_k):
        return self.hits


class HybridRetrievalTests(unittest.TestCase):
    def test_hybrid_tie_break_is_stable(self):
        rows = [{'evidence_id': 'E001'}, {'evidence_id': 'E002'}]
        hits = [(rows[1], 1.0), (rows[0], 1.0)]
        result = HybridRetriever(StubRetriever(rows, hits), StubRetriever(rows, hits), .5).search('q', 2)
        self.assertEqual(['E001', 'E002'], [row['evidence_id'] for row, _ in result])


if __name__ == "__main__":
    unittest.main()
