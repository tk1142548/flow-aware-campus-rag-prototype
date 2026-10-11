import unittest

from app.backend.error_taxonomy import classify_error


class ErrorTaxonomyTests(unittest.TestCase):
    def test_validation_errors_take_precedence(self):
        self.assertEqual('unsupported_claim', classify_error('step_error', [{'code': 'unknown_claim'}], 3))

    def test_empty_hits_are_retrieval_miss(self):
        self.assertEqual('retrieval_miss', classify_error('direct', [], 0))

    def test_known_scenario_and_none(self):
        self.assertEqual('material_confusion', classify_error('material_confusion', [], 2))
        self.assertEqual('none', classify_error('direct', [], 2))
