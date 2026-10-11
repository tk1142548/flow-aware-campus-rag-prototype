import unittest

from app.backend.experiment_logging import build_experiment_record
from app.backend.generation_strategies import direct_answer_context


class GenerationLoggingTests(unittest.TestCase):
    def test_direct_context_preserves_candidates(self):
        rows = [{'evidence_id': 'E1', 'normalized_claim': '声明'}]
        context = direct_answer_context([(rows[0], 0.8)])
        self.assertEqual('direct', context['strategy'])
        self.assertEqual(['E1'], context['evidence_ids'])

    def test_record_is_reproducibility_safe(self):
        record = build_experiment_record('C', 'development_queries', 'q', {'sparse': {'hits': [], 'validation_errors': []}})
        self.assertFalse(record['formal_evaluation_enabled'])
        self.assertNotIn('api_key', record)
        self.assertEqual(0, record['results']['sparse']['hit_count'])
