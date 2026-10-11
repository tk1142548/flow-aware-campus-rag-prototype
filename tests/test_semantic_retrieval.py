import unittest

from app.backend.semantic_retrieval import SemanticRetriever, dashscope_embed


class SemanticRetrievalTests(unittest.TestCase):
    def embed(self, texts):
        return [[float(len(text)), float(text.count('照片')), float(text.count('地点'))] for text in texts]

    def test_deterministic_rank_and_tie_break(self):
        rows = [
            {'evidence_id': 'E002', 'normalized_claim': '地点', 'verbatim_text': '地点', 'keywords': []},
            {'evidence_id': 'E001', 'normalized_claim': '照片', 'verbatim_text': '照片', 'keywords': []},
        ]
        retriever = SemanticRetriever(rows, self.embed)
        self.assertEqual(['E001', 'E002'], [row['evidence_id'] for row, _ in retriever.search('照片')])

    def test_invalid_input(self):
        retriever = SemanticRetriever([], self.embed)
        with self.assertRaises(ValueError):
            retriever.search('')
        with self.assertRaises(ValueError):
            retriever.search('x', 0)

    def test_dashscope_batch_contract(self):
        with self.assertRaises(ValueError):
            dashscope_embed(['x'] * 11, api_key='test')
