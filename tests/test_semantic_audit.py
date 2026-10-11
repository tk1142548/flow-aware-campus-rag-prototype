import unittest

from scripts.run_stage2_semantic_audit import cosine


class SemanticAuditTests(unittest.TestCase):
    def test_cosine_identical(self):
        self.assertAlmostEqual(1.0, cosine([1.0, 2.0], [1.0, 2.0]))

    def test_cosine_orthogonal(self):
        self.assertAlmostEqual(0.0, cosine([1.0, 0.0], [0.0, 1.0]))
